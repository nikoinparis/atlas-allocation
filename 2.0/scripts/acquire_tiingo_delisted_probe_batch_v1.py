#!/usr/bin/env python3
"""Acquire one resumable free-tier batch of Tiingo delisted-price candidates."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.tiingo_delisted import candidate_cache_key, issuer_name_match, issuer_name_score

CONFIG = ROOT / "config/tiingo_delisted_price_probe_v1.json"
CANDIDATES = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/yahoo_failures_tiingo_candidates.csv"
MEMBERSHIP = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
CACHE = ROOT / "data/tiingo_delisted_price_probe_cache_v1"
RUNS = ROOT / "data/tiingo_delisted_price_probe_runs"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--minimum-seconds-between-requests", type=float, default=1.0)
    return parser.parse_args()


class TiingoClient:
    def __init__(self, token: str, minimum_interval: float):
        self.token = token
        self.minimum_interval = minimum_interval
        self.last_request = 0.0

    def get_json(self, url: str) -> tuple[object, dict]:
        remaining = self.minimum_interval - (time.monotonic() - self.last_request)
        if remaining > 0:
            time.sleep(remaining)
        request = urllib.request.Request(url, headers={
            "Authorization": f"Token {self.token}",
            "User-Agent": "Portfolio Optimizer research",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
            status = int(response.status)
            headers = {key.lower(): value for key, value in response.headers.items() if key.lower().startswith("x-")}
        self.last_request = time.monotonic()
        return json.loads(payload), {
            "url": url,
            "http_status": status,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
            "response_headers": headers,
        }


def completed_symbols() -> set[str]:
    values = set()
    for path in CACHE.glob("*/result.json"):
        try:
            payload = json.loads(path.read_text())
            if payload.get("terminal"):
                values.add(payload["tiingo_symbol"])
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return values


def completed_ciks() -> set[str]:
    values = set()
    for path in CACHE.glob("*/result.json"):
        try:
            payload = json.loads(path.read_text())
            if payload.get("terminal"):
                values.add(str(payload["cik10"]))
        except (OSError, json.JSONDecodeError, KeyError):
            continue
    return values


def cache_target(symbol: str, cik10: str) -> Path:
    base = CACHE / candidate_cache_key(symbol, cik10)
    occupied_cik = None
    result_path = base / "result.json"
    if result_path.exists():
        try:
            occupied_cik = json.loads(result_path.read_text()).get("cik10")
        except (OSError, json.JSONDecodeError):
            occupied_cik = "unreadable"
    return CACHE / candidate_cache_key(symbol, cik10, occupied_cik)


def acquire(row: pd.Series, client: TiingoClient) -> dict:
    symbol = str(row["tiingo_symbol"])
    cik10 = str(row["cik10"])
    target = cache_target(symbol, cik10)
    target.mkdir(parents=True, exist_ok=True)
    result = {
        "cik10": str(row["cik10"]),
        "sec_company_name": row["company_name_as_filed"],
        "tiingo_symbol": symbol,
        "first_eligible_decision": row["first_eligible_decision"],
        "last_eligible_decision": row["last_eligible_decision"],
        "terminal": False,
        "status": "started",
    }
    source_rows = []
    try:
        encoded = urllib.parse.quote(symbol, safe="-")
        metadata, metadata_source = client.get_json(f"https://api.tiingo.com/tiingo/daily/{encoded}")
        source_rows.append(metadata_source)
        provider_name = metadata.get("name") if isinstance(metadata, dict) else None
        score = issuer_name_score(row["company_name_as_filed"], provider_name)
        name_ok = issuer_name_match(row["company_name_as_filed"], provider_name)
        start = pd.Timestamp(row["first_eligible_decision"]).date().isoformat()
        end = (pd.Timestamp(row["last_eligible_decision"]) + pd.Timedelta(days=10)).date().isoformat()
        prices, price_source = client.get_json(
            f"https://api.tiingo.com/tiingo/daily/{encoded}/prices?startDate={start}&endDate={end}&resampleFreq=daily"
        )
        source_rows.append(price_source)
        frame = pd.DataFrame(prices)
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
            payload = frame.to_csv(index=False).encode("utf-8")
            price_path = target / "prices.csv.gz"
            price_path.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
            first_price = frame["date"].min().date().isoformat()
            last_price = frame["date"].max().date().isoformat()
        else:
            price_path, first_price, last_price = None, None, None
        first_eligible = pd.Timestamp(row["first_eligible_decision"])
        first_price_timestamp = pd.to_datetime(first_price, utc=True, errors="coerce")
        covers_start = bool(pd.notna(first_price_timestamp) and first_price_timestamp <= first_eligible + pd.Timedelta(days=10))
        if not name_ok:
            validation_status = "rejected_name_mismatch_or_ticker_reuse"
        elif not covers_start:
            validation_status = "rejected_missing_start_of_eligibility"
        elif len(frame) < 2:
            validation_status = "rejected_insufficient_prices"
        else:
            validation_status = "identity_and_start_validated"
        result.update({
            "provider_name": provider_name,
            "provider_exchange": metadata.get("exchangeCode") if isinstance(metadata, dict) else None,
            "provider_start_date": metadata.get("startDate") if isinstance(metadata, dict) else None,
            "provider_end_date": metadata.get("endDate") if isinstance(metadata, dict) else None,
            "issuer_name_score": score,
            "issuer_name_match": name_ok,
            "covers_first_eligible_decision": covers_start,
            "price_rows": int(len(frame)),
            "first_price_date": first_price,
            "last_price_date": last_price,
            "price_file": str(price_path) if price_path else None,
            "status": validation_status,
            "terminal": True,
        })
    except urllib.error.HTTPError as exc:
        result.update({
            "status": "rate_limited_retry_later" if exc.code == 429 else f"http_error_{exc.code}",
            "terminal": exc.code != 429,
            "error": str(exc),
        })
    except Exception as exc:
        result.update({"status": f"request_error_{type(exc).__name__}", "terminal": False, "error": str(exc)[:500]})
    (target / "sources.json").write_text(json.dumps(source_rows, indent=2, sort_keys=True) + "\n")
    (target / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> int:
    args = arguments()
    if args.batch_size < 1 or args.batch_size > 24:
        raise ValueError("batch-size must be 1..24 to remain within the documented 50-request hourly free tier")
    token = os.environ.get("TIINGO_API_TOKEN", "").strip()
    if len(token) < 16:
        raise RuntimeError("TIINGO_API_TOKEN is required and must be supplied only as a transient environment variable")
    candidates = pd.read_csv(CANDIDATES, dtype={"cik10": str})
    candidates = candidates[candidates["inventory_interval_overlap"].astype(bool)].copy()
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    recent_counts = (
        membership[membership["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")]
        .groupby("cik10")["decision_at"].nunique()
    )
    candidates["recent_decision_count"] = candidates["cik10"].map(recent_counts).fillna(0).astype(int)
    candidates["recent_priority"] = pd.to_datetime(candidates["last_eligible_decision"], utc=True, errors="coerce")
    candidates = candidates.sort_values(["recent_decision_count", "recent_priority", "cik10"], ascending=[False, False, True])
    done_ciks = completed_ciks()
    batch = candidates[~candidates["cik10"].isin(done_ciks)].drop_duplicates("cik10").head(args.batch_size)
    client = TiingoClient(token, args.minimum_seconds_between_requests)
    results = []
    for row in batch.to_dict("records"):
        result = acquire(pd.Series(row), client)
        results.append(result)
        print(f"{result['tiingo_symbol']}: {result['status']}", flush=True)
        if result["status"] == "rate_limited_retry_later":
            break
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    RUNS.mkdir(parents=True, exist_ok=True)
    run = {
        "run_id": f"{stamp}-tiingo-delisted-probe-batch-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_batch_size": args.batch_size,
        "processed": len(results),
        "status_counts": pd.Series([row["status"] for row in results]).value_counts().to_dict() if results else {},
        "remaining_candidate_symbols": int(len(set(candidates["tiingo_symbol"]) - completed_symbols())),
        "remaining_candidate_ciks": int(len(set(candidates["cik10"]) - completed_ciks())),
        "token_persisted": False,
        "strategy_testing_authorized": False,
    }
    (RUNS / f"{run['run_id']}.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
    print(json.dumps(run, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
