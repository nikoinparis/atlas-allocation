#!/usr/bin/env python3
"""Recover symbols from standalone XBRL instance files for pre-inline filings."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.recover_sec_historical_symbols_v1 import SecFetcher
from systematic_trader.sec_historical_universe import extract_trading_symbols


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol-vintage", default=None)
    parser.add_argument("--output-root", default=str(ROOT / "data/sec_historical_identity_vintages"))
    parser.add_argument("--cache-root", default=str(ROOT / "data/sec_historical_identity_cache"))
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def candidate_instances(items: list[dict]) -> list[str]:
    rejected = ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml", "_ref.xml")
    values = []
    for item in items:
        name = str(item.get("name", ""))
        lower = name.lower()
        if not lower.endswith(".xml") or lower.endswith(rejected):
            continue
        if lower in {"filingsummary.xml", "metalinks.json"} or lower.startswith("report"):
            continue
        values.append((int(item.get("size") or 0), name))
    return [name for _, name in sorted(values, reverse=True)]


def recover(row: dict, fetcher: SecFetcher) -> dict:
    result = dict(row)
    result["legacy_symbols"] = None
    result["legacy_status"] = "not_started"
    result["instance_document"] = None
    result["instance_sha256"] = None
    cik10 = str(row["cik10"])
    accession = str(row["last_eligible_accession"])
    accession_plain = accession.replace("-", "")
    cik_plain = str(int(cik10))
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{accession_plain}"
    try:
        index, _ = fetcher.json(f"{base}/index.json", f"index_{cik10}_{accession_plain}")
        candidates = candidate_instances(index.get("directory", {}).get("item", []))
        if not candidates:
            result["legacy_status"] = "no_instance_candidate"
            return result
        for filename in candidates:
            document, metadata = fetcher.get(f"{base}/{filename}", f"instance_{cik10}_{accession_plain}_{Path(filename).name}")
            symbols = extract_trading_symbols(document)
            if symbols:
                result["legacy_symbols"] = "|".join(symbols)
                result["legacy_status"] = "instance_symbol_recovered"
                result["instance_document"] = filename
                result["instance_sha256"] = metadata["sha256"]
                return result
        result["legacy_status"] = "instance_has_no_explicit_symbol"
        return result
    except Exception as exc:
        result["legacy_status"] = f"request_error:{type(exc).__name__}"
        return result


def main() -> int:
    args = arguments()
    if args.symbol_vintage:
        parent = Path(args.symbol_vintage).resolve()
    else:
        candidates = sorted((ROOT / "data/sec_historical_identity_vintages").glob("*-sec-symbol-recovery-v1"))
        parent = candidates[-1]
    first = pd.read_csv(parent / "symbol_recovery.csv", dtype={"cik10": str})
    targets = first[first["recovery_status"] == "no_explicit_symbol_tag"].copy()
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    fetcher = SecFetcher(Path(args.cache_root).resolve(), user_agent)
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(recover, row, fetcher) for row in targets.to_dict("records")]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            rows.append(future.result())
            if index % 50 == 0 or index == len(futures):
                recovered = sum(row["legacy_status"] == "instance_symbol_recovered" for row in rows)
                print(f"processed {index}/{len(futures)}; recovered {recovered}", flush=True)
    legacy = pd.DataFrame(rows).sort_values(["legacy_status", "sector", "cik10"]).reset_index(drop=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root).resolve() / f"{stamp}-sec-legacy-symbol-recovery-v1"
    output.mkdir(parents=True, exist_ok=False)
    legacy.to_csv(output / "legacy_symbol_recovery.csv", index=False)
    counts = legacy["legacy_status"].value_counts().to_dict()
    recovered = int((legacy["legacy_status"] == "instance_symbol_recovered").sum())
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_symbol_vintage": str(parent),
        "targets": int(len(legacy)),
        "instance_symbols_recovered": recovered,
        "recovery_rate": float(recovered / len(legacy)) if len(legacy) else 0.0,
        "status_counts": {str(key): int(value) for key, value in counts.items()},
        "historical_mapping_complete": False,
        "ticker_reuse_validated": False,
        "price_testing_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
