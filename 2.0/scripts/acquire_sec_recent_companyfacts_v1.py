#!/usr/bin/env python3
"""Acquire resumable SEC Company Facts for the recent historical membership panel."""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.recover_sec_historical_symbols_v1 import SecFetcher

MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
RUNS = ROOT / "data/sec_recent_companyfacts_runs"


def acquire_one(cik10: str, fetcher: SecFetcher) -> dict:
    try:
        _, metadata = fetcher.json(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json",
            f"companyfacts_{cik10}",
        )
        return {"cik10": cik10, "status": "ok", **metadata}
    except Exception as exc:
        return {"cik10": cik10, "status": f"error:{type(exc).__name__}", "error": str(exc)[:500]}


def main() -> int:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    targets = sorted(set(membership.loc[membership["tradable_member"].astype(bool), "cik10"]))
    fetcher = SecFetcher(CACHE, user_agent, minimum_interval=0.13)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(acquire_one, cik10, fetcher) for cik10 in targets]
        for index, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            rows.append(future.result())
            if index % 50 == 0 or index == len(futures):
                ok = sum(row["status"] == "ok" for row in rows)
                print(f"processed {index}/{len(futures)}; successful {ok}", flush=True)
    results = pd.DataFrame(rows).sort_values(["status", "cik10"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = f"{stamp}-sec-recent-companyfacts-v1"
    results.to_csv(RUNS / f"{run_id}.csv", index=False)
    result = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_ciks": int(len(targets)),
        "successful_ciks": int((results["status"] == "ok").sum()),
        "failed_ciks": int((results["status"] != "ok").sum()),
        "cache_root": str(CACHE),
        "contact_persisted": False,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (RUNS / f"{run_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
