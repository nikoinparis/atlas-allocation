#!/usr/bin/env python3
"""Recover last as-filed symbols for former/unmapped CIKs from SEC filing covers."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_historical_universe import extract_trading_symbols


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe-vintage", default=None)
    parser.add_argument("--output-root", default=str(ROOT / "data/sec_historical_identity_vintages"))
    parser.add_argument("--cache-root", default=str(ROOT / "data/sec_historical_identity_cache"))
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


class SecFetcher:
    def __init__(self, cache: Path, user_agent: str, minimum_interval: float = 0.13):
        self.cache = cache
        self.user_agent = user_agent
        self.minimum_interval = minimum_interval
        self.lock = threading.Lock()
        self.last_request = 0.0
        cache.mkdir(parents=True, exist_ok=True)

    def _pace(self) -> None:
        with self.lock:
            remaining = self.minimum_interval - (time.monotonic() - self.last_request)
            if remaining > 0:
                time.sleep(remaining)
            self.last_request = time.monotonic()

    def get(self, url: str, key: str) -> tuple[bytes, dict]:
        body_path = self.cache / f"{key}.gz"
        meta_path = self.cache / f"{key}.json"
        if body_path.exists() and meta_path.exists():
            return gzip.decompress(body_path.read_bytes()), json.loads(meta_path.read_text())
        error: Exception | None = None
        for attempt in range(4):
            try:
                self._pace()
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = response.read()
                    if (response.headers.get("Content-Encoding") or "").lower() == "gzip" or payload[:2] == b"\x1f\x8b":
                        payload = gzip.decompress(payload)
                    status = int(response.status)
                body_path.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
                metadata = {
                    "url": url,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "http_status": status,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "cache_key": key,
                }
                meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
                return payload, metadata
            except Exception as exc:
                error = exc
                time.sleep(2 ** attempt)
        raise RuntimeError(f"failed {url}: {error}")

    def json(self, url: str, key: str) -> tuple[dict, dict]:
        payload, metadata = self.get(url, key)
        return json.loads(payload), metadata


def columnar_lookup(payload: dict) -> dict[str, str]:
    rows = payload.get("filings", {}).get("recent", payload)
    accessions = rows.get("accessionNumber", [])
    documents = rows.get("primaryDocument", [])
    return {str(accession): str(documents[index]) for index, accession in enumerate(accessions) if index < len(documents)}


def recover_one(row: dict, fetcher: SecFetcher) -> dict:
    cik10 = row["cik10"]
    accession = row["adsh"]
    result = {
        "cik10": cik10,
        "company_name_as_filed": row["company_name_as_filed"],
        "sector": row["sector"],
        "last_eligible_accession": accession,
        "last_eligible_available_at": row["available_at"],
        "recovered_symbols": None,
        "recovery_status": "not_started",
        "primary_document": None,
        "source_sha256": None,
    }
    try:
        submission_url = f"https://data.sec.gov/submissions/CIK{cik10}.json"
        submission, _ = fetcher.json(submission_url, f"submissions_{cik10}")
        lookup = columnar_lookup(submission)
        if accession not in lookup:
            for spec in submission.get("filings", {}).get("files", []):
                filename = spec["name"]
                history, _ = fetcher.json(f"https://data.sec.gov/submissions/{filename}", f"submissions_{cik10}_{filename[:-5]}")
                lookup.update(columnar_lookup(history))
                if accession in lookup:
                    break
        primary = lookup.get(accession)
        if not primary:
            result["recovery_status"] = "accession_not_in_submissions"
            return result
        accession_plain = accession.replace("-", "")
        cik_plain = str(int(cik10))
        document_url = f"https://www.sec.gov/Archives/edgar/data/{cik_plain}/{accession_plain}/{primary}"
        document, metadata = fetcher.get(document_url, f"filing_{cik10}_{accession_plain}_{Path(primary).name}")
        symbols = extract_trading_symbols(document)
        result["primary_document"] = primary
        result["source_sha256"] = metadata["sha256"]
        result["recovered_symbols"] = "|".join(symbols) if symbols else None
        result["recovery_status"] = "xbrl_symbol_recovered" if symbols else "no_explicit_symbol_tag"
        return result
    except Exception as exc:
        result["recovery_status"] = f"request_error:{type(exc).__name__}"
        return result


def main() -> int:
    args = arguments()
    vintage = Path(args.universe_vintage).resolve() if args.universe_vintage else sorted((ROOT / "data/sec_historical_universe_vintages").glob("*"))[-1]
    identities = pd.read_csv(vintage / "cik_identity_coverage.csv", dtype={"cik10": str})
    submissions = pd.read_csv(vintage / "qualifying_submissions.csv", dtype={"cik10": str})
    targets = identities[identities["identity_status"] == "former_or_unmapped"][["cik10", "company_name_as_filed", "sector"]]
    last = submissions[~submissions["form"].str.endswith("/A", na=False)].sort_values(["available_at", "adsh"]).drop_duplicates("cik10", keep="last")
    targets = targets.drop(columns=["company_name_as_filed", "sector"]).merge(last, on="cik10", how="left")
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    fetcher = SecFetcher(Path(args.cache_root).resolve(), user_agent)
    rows: list[dict] = []
    records = targets.to_dict("records")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(recover_one, row, fetcher) for row in records]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            rows.append(future.result())
            if index % 50 == 0 or index == len(futures):
                recovered = sum(row["recovery_status"] == "xbrl_symbol_recovered" for row in rows)
                print(f"processed {index}/{len(futures)}; recovered {recovered}", flush=True)
    results = pd.DataFrame(rows).sort_values(["recovery_status", "sector", "cik10"]).reset_index(drop=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root).resolve() / f"{stamp}-sec-symbol-recovery-v1"
    output.mkdir(parents=True, exist_ok=False)
    results.to_csv(output / "symbol_recovery.csv", index=False)
    counts = results["recovery_status"].value_counts().to_dict()
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_universe_vintage": str(vintage),
        "targets": int(len(results)),
        "xbrl_symbols_recovered": int((results["recovery_status"] == "xbrl_symbol_recovered").sum()),
        "recovery_rate": float((results["recovery_status"] == "xbrl_symbol_recovered").mean()),
        "status_counts": {str(key): int(value) for key, value in counts.items()},
        "historical_mapping_complete": False,
        "mapping_scope": "last non-amended eligible filing per former/unmapped CIK",
        "ticker_reuse_validated": False,
        "price_testing_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
