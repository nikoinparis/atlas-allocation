#!/usr/bin/env python3
"""Recover explicit as-filed symbols for a bounded broad-universe identity batch."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from recover_sec_historical_symbols_v1 import SecFetcher, recover_one


QUEUE = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"
CACHE = ROOT / "data/sec_broad_identity_cache_v2"
OUTPUT_ROOT = ROOT / "data/sec_broad_identity_vintages"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def latest_broad_vintage() -> Path:
    values = sorted((ROOT / "data/sec_historical_universe_vintages").glob("*-sec-historical-filers-broad-v2"))
    if not values:
        raise RuntimeError("no broad-v2 SEC universe vintage found")
    return values[-1]


def main() -> int:
    args = arguments()
    if args.offset < 0 or args.limit <= 0 or args.limit > 200:
        raise ValueError("offset must be non-negative and limit must be between 1 and 200")
    queue = pd.read_csv(QUEUE, dtype={"cik10": str})
    eligible = queue[queue["queue_status"].eq("identity_recovery_required")]
    selected = eligible.iloc[args.offset:args.offset + args.limit].copy()
    if selected.empty:
        raise RuntimeError("selected identity-recovery queue slice is empty")

    universe = latest_broad_vintage()
    submissions = pd.read_csv(universe / "qualifying_submissions.csv", dtype={"cik10": str})
    last = (
        submissions[~submissions["form"].str.endswith("/A", na=False)]
        .sort_values(["available_at", "adsh"])
        .drop_duplicates("cik10", keep="last")
    )
    records = selected[["cik10"]].merge(last, on="cik10", how="left").to_dict("records")
    if any(pd.isna(row.get("adsh")) for row in records):
        raise RuntimeError("identity queue contains a CIK without an eligible filing")

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    fetcher = SecFetcher(CACHE, user_agent, minimum_interval=0.13)
    rows: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(recover_one, row, fetcher) for row in records]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            rows.append(future.result())
            if index % 50 == 0 or index == len(futures):
                recovered = sum(row["recovery_status"] == "xbrl_symbol_recovered" for row in rows)
                print(f"processed {index}/{len(futures)}; recovered {recovered}", flush=True)

    results = pd.DataFrame(rows).sort_values(["recovery_status", "sector", "cik10"]).reset_index(drop=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-sec-broad-symbol-recovery-v2-o{args.offset}-n{len(selected)}"
    output.mkdir(parents=True, exist_ok=False)
    results.to_csv(output / "symbol_recovery.csv", index=False)
    counts = results["recovery_status"].value_counts().to_dict()
    single = results["recovered_symbols"].fillna("").astype(str).str.count(r"\|").eq(0) & results["recovered_symbols"].notna()
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_universe_vintage": universe.name,
        "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
        "selected_ciks_sha256": hashlib.sha256("\n".join(sorted(selected["cik10"])).encode("utf-8")).hexdigest(),
        "offset": int(args.offset),
        "targets": int(len(results)),
        "xbrl_symbols_recovered": int((results["recovery_status"] == "xbrl_symbol_recovered").sum()),
        "single_symbols_recovered": int(single.sum()),
        "status_counts": {str(key): int(value) for key, value in counts.items()},
        "ticker_reuse_validated": False,
        "price_testing_authorized": False,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
