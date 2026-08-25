#!/usr/bin/env python3
"""Acquire bounded SEC primary-symbol price and fundamentals batches."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from acquire_sec_broad_current_data_batch_v2 import acquire_prices, yahoo_symbol
from acquire_sec_recent_companyfacts_v1 import acquire_one
from recover_sec_historical_symbols_v1 import SecFetcher


QUEUE = ROOT / "evidence/sec_broad_multi_symbol_primary_v2/primary_symbol_queue.csv"
FACTS_CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
OUTPUT_ROOT = ROOT / "data/sec_broad_multi_symbol_data_vintages"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--queue", default=str(QUEUE))
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.offset < 0 or args.limit <= 0 or args.limit > 200:
        raise ValueError("offset must be non-negative and limit must be between 1 and 200")
    queue_path = Path(args.queue).resolve()
    queue = pd.read_csv(queue_path, dtype={"cik10": str})
    selected = queue.iloc[args.offset:args.offset + args.limit].copy()
    if selected.empty:
        raise RuntimeError("selected primary-symbol queue slice is empty")
    selected["yahoo_symbol"] = selected["recovered_symbol"].map(yahoo_symbol)
    if selected["yahoo_symbol"].duplicated().any():
        raise RuntimeError("batch contains duplicate primary symbols")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-sec-broad-multi-primary-v2-o{args.offset}-n{len(selected)}"
    history = output / "histories"
    history.mkdir(parents=True, exist_ok=False)
    records = selected.to_dict("records")
    prices = pd.DataFrame(acquire_prices(records, history)).sort_values(["status", "yahoo_symbol"])
    prices.to_csv(output / "price_results.csv", index=False)

    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact is required")
    fetcher = SecFetcher(FACTS_CACHE, user_agent, minimum_interval=0.13)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(acquire_one, str(row["cik10"]), fetcher) for row in records]
        facts = pd.DataFrame([future.result() for future in concurrent.futures.as_completed(futures)])
    facts = facts.sort_values(["status", "cik10"])
    facts.to_csv(output / "companyfacts_results.csv", index=False)

    valid_prices = int(prices["history_overlaps_eligible_interval"].astype(bool).sum())
    valid_facts = int(facts["status"].eq("ok").sum())
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "queue": str(queue_path),
        "queue_sha256": hashlib.sha256(queue_path.read_bytes()).hexdigest(),
        "selected_ciks_sha256": hashlib.sha256("\n".join(sorted(selected["cik10"])).encode()).hexdigest(),
        "offset": int(args.offset),
        "requested_ciks": int(len(selected)),
        "valid_price_histories": valid_prices,
        "price_failures": int(len(selected) - valid_prices),
        "valid_companyfacts": valid_facts,
        "companyfacts_failures": int(len(selected) - valid_facts),
        "provider": "Yahoo Finance SEC-reported primary symbols plus SEC Company Facts",
        "yfinance_version": yf.__version__,
        "python_version": platform.python_version(),
        "primary_symbol_selection_frozen": True,
        "ticker_reuse_validated_by_interval": True,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
