#!/usr/bin/env python3
"""Acquire a bounded batch of free prices and SEC facts for the broad universe."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))

from acquire_sec_recent_companyfacts_v1 import acquire_one
from acquire_yahoo_recent_current_sec_prices_v1 import safe_name, yahoo_symbol
from recover_sec_historical_symbols_v1 import SecFetcher


ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"
OUTPUT_ROOT = ROOT / "data/sec_broad_current_data_vintages"
FACTS_CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
START = pd.Timestamp("2022-12-01", tz="UTC")


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        choices=["acquire_price_only", "acquire_price_and_facts"],
        default="acquire_price_only",
    )
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--only-ciks", default="", help="Comma-separated CIKs for an explicit retry batch")
    parser.add_argument("--label", default="sec-broad-current-data-v2")
    return parser.parse_args()


def price_history(frame: pd.DataFrame, symbol: str, symbol_count: int) -> pd.DataFrame:
    if frame.empty:
        raise RuntimeError("empty batch response")
    if isinstance(frame.columns, pd.MultiIndex):
        if symbol in set(frame.columns.get_level_values(0)):
            one = frame[symbol].copy()
        elif symbol in set(frame.columns.get_level_values(1)):
            one = frame.xs(symbol, axis=1, level=1).copy()
        elif symbol_count == 1:
            one = frame.copy()
            one.columns = one.columns.get_level_values(0)
        else:
            raise RuntimeError("symbol absent from batch response")
    elif symbol_count == 1:
        one = frame.copy()
    else:
        raise RuntimeError("unexpected non-multiindex batch response")
    one = one.dropna(how="all").reset_index()
    if one.empty or "Close" not in one or one["Close"].dropna().empty:
        raise RuntimeError("empty symbol history")
    date_column = "Date" if "Date" in one else one.columns[0]
    one[date_column] = pd.to_datetime(one[date_column], utc=True, errors="coerce")
    return one.dropna(subset=[date_column])


def acquire_prices(records: list[dict], history: Path) -> list[dict]:
    symbols = [str(row["yahoo_symbol"]) for row in records]
    try:
        frame = yf.download(
            symbols,
            start=START.date().isoformat(),
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=False,
            group_by="ticker",
            threads=8,
            progress=False,
        )
        batch_error = None
    except Exception as exc:
        frame = pd.DataFrame()
        batch_error = f"batch_error:{type(exc).__name__}:{str(exc)[:240]}"
    rows = []
    for identity in records:
        symbol = str(identity["yahoo_symbol"])
        result = {
            **identity,
            "status": "failed",
            "rows": 0,
            "first_price_date": None,
            "last_price_date": None,
            "history_overlaps_eligible_interval": False,
            "history_file": None,
            "error": batch_error,
        }
        try:
            if batch_error:
                raise RuntimeError(batch_error)
            one = price_history(frame, symbol, len(symbols))
            date_column = "Date" if "Date" in one else one.columns[0]
            first = one[date_column].min()
            last = one[date_column].max()
            first_eligible = pd.Timestamp(identity["first_recent_decision"])
            last_eligible = pd.Timestamp(identity["last_recent_decision"])
            overlaps = bool(first <= first_eligible + pd.Timedelta(days=10) and last >= last_eligible)
            serialized = one.copy()
            serialized[date_column] = serialized[date_column].dt.strftime("%Y-%m-%d")
            payload = serialized.to_csv(index=False).encode("utf-8")
            destination = history / f"{safe_name(symbol)}.csv.gz"
            destination.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
            result.update({
                "status": "ok" if overlaps else "interval_mismatch",
                "rows": int(len(serialized)),
                "first_price_date": first.date().isoformat(),
                "last_price_date": last.date().isoformat(),
                "history_overlaps_eligible_interval": overlaps,
                "history_file": str(destination.relative_to(history.parent)),
                "compressed_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "error": None,
            })
        except Exception as exc:
            result["error"] = result["error"] or f"{type(exc).__name__}:{str(exc)[:300]}"
        rows.append(result)
    return rows


def main() -> int:
    args = arguments()
    if args.offset < 0 or args.limit <= 0 or args.limit > 200:
        raise ValueError("offset must be non-negative and limit must be between 1 and 200")
    queue = pd.read_csv(QUEUE, dtype={"cik10": str})
    eligible = queue[queue["queue_status"].eq(args.status)].copy()
    requested_ciks = {value.strip().zfill(10) for value in args.only_ciks.split(",") if value.strip()}
    if requested_ciks:
        selected = eligible[eligible["cik10"].isin(requested_ciks)].copy()
        missing = requested_ciks - set(selected["cik10"])
        if missing:
            raise RuntimeError(f"requested CIKs are absent from the selected queue: {sorted(missing)}")
    else:
        selected = eligible.iloc[args.offset:args.offset + args.limit].copy()
    if selected.empty:
        raise RuntimeError("selected queue slice is empty")
    if (~selected["single_current_ticker"].astype(bool)).any():
        raise RuntimeError("batch contains an issuer without one unambiguous current ticker")
    selected["yahoo_symbol"] = selected["current_tickers"].map(yahoo_symbol)
    if selected["yahoo_symbol"].duplicated().any():
        raise RuntimeError("batch contains duplicate current ticker mappings")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-{args.label}-{args.status}-o{args.offset}-n{len(selected)}"
    history = output / "histories"
    history.mkdir(parents=True, exist_ok=False)
    records = selected.to_dict("records")
    prices = pd.DataFrame(acquire_prices(records, history)).sort_values(["status", "yahoo_symbol"])
    prices.to_csv(output / "price_results.csv", index=False)

    fact_rows: list[dict] = []
    if args.status == "acquire_price_and_facts":
        user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
        if "@" not in user_agent:
            raise RuntimeError("SEC_USER_AGENT with a real contact is required")
        fetcher = SecFetcher(FACTS_CACHE, user_agent, minimum_interval=0.13)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(acquire_one, str(row["cik10"]), fetcher) for row in records]
            fact_rows = [future.result() for future in concurrent.futures.as_completed(futures)]
    else:
        fact_rows = [{"cik10": str(row["cik10"]), "status": "already_cached"} for row in records]
    facts = pd.DataFrame(fact_rows).sort_values(["status", "cik10"])
    facts.to_csv(output / "companyfacts_results.csv", index=False)

    valid_prices = int(prices["history_overlaps_eligible_interval"].astype(bool).sum())
    valid_facts = int(facts["status"].isin(["ok", "already_cached"]).sum())
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "queue_source": str(QUEUE),
        "queue_sha256": hashlib.sha256(QUEUE.read_bytes()).hexdigest(),
        "queue_status": args.status,
        "offset": int(args.offset),
        "selection_mode": "explicit_cik_retry" if requested_ciks else "queue_slice",
        "selected_ciks_sha256": hashlib.sha256("\n".join(sorted(selected["cik10"])).encode("utf-8")).hexdigest(),
        "requested_ciks": int(len(selected)),
        "valid_price_histories": valid_prices,
        "price_failures": int(len(selected) - valid_prices),
        "valid_companyfacts": valid_facts,
        "companyfacts_failures": int(len(selected) - valid_facts),
        "provider": "Yahoo Finance via pinned yfinance container and SEC Company Facts",
        "yfinance_version": yf.__version__,
        "python_version": platform.python_version(),
        "terminal_outcomes_complete": False,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
