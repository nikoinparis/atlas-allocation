#!/usr/bin/env python3
"""Acquire SEC Company Facts for every still-missing broad-universe issuer."""

from __future__ import annotations

import concurrent.futures
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from acquire_sec_recent_companyfacts_v1 import acquire_one
from recover_sec_historical_symbols_v1 import SecFetcher


READINESS = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"
CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
RUNS = ROOT / "data/sec_broad_missing_companyfacts_runs_v2"


def main() -> int:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    readiness = pd.read_csv(READINESS, dtype={"cik10": str})
    targets = sorted(set(readiness.loc[~readiness["companyfacts_cached"].astype(bool), "cik10"]))
    fetcher = SecFetcher(CACHE, user_agent, minimum_interval=0.13)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        rows = [future.result() for future in concurrent.futures.as_completed(
            [pool.submit(acquire_one, cik10, fetcher) for cik10 in targets]
        )]
    results = pd.DataFrame(rows).sort_values(["status", "cik10"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RUNS.mkdir(parents=True, exist_ok=True)
    run_id = f"{stamp}-sec-broad-missing-companyfacts-v2"
    results.to_csv(RUNS / f"{run_id}.csv", index=False)
    result = {
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "target_ciks": int(len(targets)),
        "successful_ciks": int(results["status"].eq("ok").sum()),
        "failed_ciks": int((~results["status"].eq("ok")).sum()),
        "contact_persisted": False,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (RUNS / f"{run_id}.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
