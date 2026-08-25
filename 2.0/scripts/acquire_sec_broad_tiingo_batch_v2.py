#!/usr/bin/env python3
"""Acquire one free-tier-safe Tiingo batch for the broad SEC universe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import acquire_tiingo_delisted_probe_batch_v1 as legacy


CANDIDATES = ROOT / "evidence/sec_broad_tiingo_queue_v2/candidates.csv"
SUPPLEMENT = ROOT / "evidence/sec_broad_tiingo_multi_symbol_supplement_v2/candidates.csv"
CACHE = ROOT / "data/sec_broad_tiingo_cache_v2"
RUNS = ROOT / "data/sec_broad_tiingo_runs_v2"
AUDIT = ROOT / "evidence/sec_broad_tiingo_audit_v2/candidate_audit.csv"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--minimum-seconds-between-requests", type=float, default=1.0)
    return parser.parse_args()


def completed_ciks() -> set[str]:
    values = set()
    for path in CACHE.glob("*/result.json"):
        try:
            payload = json.loads(path.read_text())
            if payload.get("terminal"):
                values.add(str(payload["cik10"]).zfill(10))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    # The strict broad audit can also validate previously downloaded,
    # authenticated Tiingo histories.  Treat only its accepted rows as done.
    if AUDIT.exists():
        audit = pd.read_csv(AUDIT, dtype={"cik10": str})
        accepted = {
            "validated_history_through_last_decision",
            "validated_sec_confirmed_early_delisting",
        }
        values.update(audit.loc[audit["audit_status"].isin(accepted), "cik10"].str.zfill(10))
    return values


def load_candidates() -> pd.DataFrame:
    paths = [CANDIDATES] + ([SUPPLEMENT] if SUPPLEMENT.exists() else [])
    frame = pd.concat([pd.read_csv(path, dtype={"cik10": str}) for path in paths], ignore_index=True)
    # Rank the combined queue, rather than exhausting the single-symbol file
    # before considering supplements. Long-lived issuers close the most
    # decision-date gaps per scarce hourly request, while the date and CIK make
    # the queue deterministic across reruns.
    return (
        frame.drop_duplicates("cik10", keep="first")
        .sort_values(
            ["recent_decision_rows", "last_eligible_decision", "cik10"],
            ascending=[False, False, True],
            kind="mergesort",
        )
        .reset_index(drop=True)
    )


def main() -> int:
    args = arguments()
    if args.batch_size < 1 or args.batch_size > 24:
        raise ValueError("batch-size must be 1..24 to remain inside Tiingo's 50-request hourly free tier")
    token = os.environ.get("TIINGO_API_TOKEN", "").strip()
    if len(token) < 16:
        raise RuntimeError("TIINGO_API_TOKEN is required as a transient environment variable")
    candidates = load_candidates()
    candidates["company_name_as_filed"] = candidates["sec_company_name"]
    done = completed_ciks()
    batch = candidates[~candidates["cik10"].isin(done)].head(args.batch_size)
    if batch.empty:
        print(json.dumps({"complete": True, "remaining": 0}, indent=2))
        return 0

    legacy.CACHE = CACHE
    client = legacy.TiingoClient(token, args.minimum_seconds_between_requests)
    results = []
    for row in batch.to_dict("records"):
        result = legacy.acquire(pd.Series(row), client)
        results.append(result)
        print(f"{result['tiingo_symbol']}: {result['status']}", flush=True)
        if result["status"] == "rate_limited_retry_later":
            break
    remaining = len(set(candidates["cik10"]) - completed_ciks())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RUNS.mkdir(parents=True, exist_ok=True)
    run = {
        "run_id": f"{stamp}-sec-broad-tiingo-batch-v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_batch_size": int(args.batch_size),
        "processed": int(len(results)),
        "status_counts": pd.Series([row["status"] for row in results]).value_counts().to_dict(),
        "remaining_candidate_ciks": int(remaining),
        "token_persisted": False,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (RUNS / f"{run['run_id']}.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    print(json.dumps(run, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
