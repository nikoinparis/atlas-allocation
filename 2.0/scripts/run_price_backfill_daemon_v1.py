#!/usr/bin/env python3
"""One command, then leave it alone for a month.

The backfill is 17,970 request pairs against a 50-per-hour, 1,000-per-day free
tier. That is not a batch job anyone should babysit, so this paces itself, resumes
cleanly, and writes a terminal record for every issuer before starting the next
one. Killing it costs at most one issuer.

    export TIINGO_API_TOKEN=...
    python3 scripts/run_price_backfill_daemon_v1.py            # runs until done
    python3 scripts/run_price_backfill_daemon_v1.py --max-requests 200 --dry-run

The token is read from the environment only and never written to disk, a log, or
a source manifest.
"""

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
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.tiingo_delisted import issuer_name_match, issuer_name_score  # noqa: E402

CONFIG = ROOT / "config/price_backfill_2012_v1.json"
QUEUE = ROOT / "data/price_backfill_2012_v1/queue.csv.gz"
CACHE = ROOT / "data/price_backfill_2012_v1/cache"
PROGRESS = ROOT / "data/price_backfill_2012_v1/progress.jsonl"
STATE = ROOT / "data/price_backfill_2012_v1/state.json"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-requests", type=int, default=0, help="stop after N requests (0 = run to completion)")
    parser.add_argument("--max-tier", type=int, default=3, help="stop after finishing this tier")
    parser.add_argument("--dry-run", action="store_true", help="plan and report without contacting the provider")
    return parser.parse_args()


class RateLimiter:
    """Self-pacing against a per-hour and per-day budget, persisted across restarts."""

    def __init__(self, per_hour: int, per_day: int, minimum_interval: float):
        self.per_hour = per_hour
        self.per_day = per_day
        self.minimum_interval = minimum_interval
        self.last_request = 0.0
        self.stamps: list[float] = []
        if STATE.exists():
            try:
                saved = json.loads(STATE.read_text())
                cutoff = time.time() - 86400
                self.stamps = [s for s in saved.get("request_epochs", []) if s > cutoff]
            except (OSError, json.JSONDecodeError):
                self.stamps = []

    def _prune(self) -> None:
        cutoff = time.time() - 86400
        self.stamps = [s for s in self.stamps if s > cutoff]

    def wait(self) -> None:
        while True:
            self._prune()
            now = time.time()
            hour_used = sum(1 for s in self.stamps if s > now - 3600)
            day_used = len(self.stamps)
            if day_used >= self.per_day:
                sleep_for = self.stamps[0] + 86400 - now + 5
                print(f"  daily budget spent ({day_used}/{self.per_day}); sleeping {sleep_for/3600:.1f}h", flush=True)
            elif hour_used >= self.per_hour:
                oldest_in_hour = min(s for s in self.stamps if s > now - 3600)
                sleep_for = oldest_in_hour + 3600 - now + 5
                print(f"  hourly budget spent ({hour_used}/{self.per_hour}); sleeping {sleep_for/60:.1f}m", flush=True)
            else:
                gap = self.minimum_interval - (time.monotonic() - self.last_request)
                if gap > 0:
                    time.sleep(gap)
                return
            time.sleep(max(sleep_for, 5))

    def record(self) -> None:
        self.stamps.append(time.time())
        self.last_request = time.monotonic()
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps({"request_epochs": self.stamps[-2000:]}) + "\n")


def get_json(url: str, token: str, limiter: RateLimiter) -> tuple[object, dict]:
    limiter.wait()
    request = urllib.request.Request(url, headers={
        "Authorization": f"Token {token}",
        "User-Agent": "Portfolio Optimizer research",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
            status = int(response.status)
    finally:
        limiter.record()
    return json.loads(payload), {
        "url": url.split("?")[0],
        "http_status": status,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def target_for(row: pd.Series) -> Path:
    return CACHE / f"{str(row['cik10'])}__{str(row['ticker']).replace('/', '_')}"


def completed_keys() -> set[str]:
    done = set()
    if not PROGRESS.exists():
        return done
    with PROGRESS.open() as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("terminal"):
                done.add(f"{record['cik10']}__{record['ticker']}")
    return done


def acquire(row: pd.Series, token: str, limiter: RateLimiter) -> dict:
    symbol = str(row["ticker"])
    encoded = urllib.parse.quote(symbol, safe="-")
    target = target_for(row)
    record = {
        "cik10": str(row["cik10"]),
        "ticker": symbol,
        "tier": int(row["tier"]),
        "sec_company_name": row["company_name_latest"],
        "attempted_at_utc": datetime.now(timezone.utc).isoformat(),
        "terminal": False,
    }
    sources = []
    try:
        metadata, meta_source = get_json(f"https://api.tiingo.com/tiingo/daily/{encoded}", token, limiter)
        sources.append(meta_source)
        provider_name = metadata.get("name") if isinstance(metadata, dict) else None
        record["provider_name"] = provider_name
        record["issuer_name_score"] = issuer_name_score(row["company_name_latest"], provider_name)
        if not issuer_name_match(row["company_name_latest"], provider_name):
            # Recycled tickers are the main failure mode; do not spend the second
            # request, and never accept the history silently.
            record.update({"status": "rejected_name_mismatch_or_ticker_reuse", "terminal": True})
            return record

        start = pd.Timestamp(row["request_start"]).date().isoformat()
        end = pd.Timestamp(row["request_end"]).date().isoformat()
        prices, price_source = get_json(
            f"https://api.tiingo.com/tiingo/daily/{encoded}/prices"
            f"?startDate={start}&endDate={end}&resampleFreq=daily",
            token, limiter,
        )
        sources.append(price_source)
        frame = pd.DataFrame(prices)
        if frame.empty:
            record.update({"status": "empty_history", "price_rows": 0, "terminal": True})
            return record
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        target.mkdir(parents=True, exist_ok=True)
        (target / "prices.csv.gz").write_bytes(
            gzip.compress(frame.to_csv(index=False).encode("utf-8"), compresslevel=6, mtime=0)
        )
        record.update({
            "status": "acquired",
            "price_rows": int(len(frame)),
            "first_price_date": frame["date"].min().date().isoformat(),
            "last_price_date": frame["date"].max().date().isoformat(),
            "terminal": True,
        })
    except urllib.error.HTTPError as exc:
        # 404 is terminal (no such symbol); 429 and 5xx are not, so they are retried
        # on the next pass rather than burning the row.
        record.update({
            "status": f"http_error_{exc.code}",
            "terminal": exc.code in (400, 404),
            "error": str(exc)[:300],
        })
    except Exception as exc:  # noqa: BLE001 - the daemon must never die on one row
        record.update({"status": f"request_error_{type(exc).__name__}", "terminal": False, "error": str(exc)[:300]})
    finally:
        if sources:
            target.mkdir(parents=True, exist_ok=True)
            (target / "sources.json").write_text(json.dumps(sources, indent=2, sort_keys=True) + "\n")
    return record


def main() -> int:
    args = arguments()
    config = json.loads(CONFIG.read_text())
    limits = config["declared_before_running"]["rate_limits"]

    if not QUEUE.exists():
        raise SystemExit("queue missing - run scripts/build_price_backfill_queue_v1.py first")
    queue = pd.read_csv(QUEUE, dtype={"cik10": str, "ticker": str})
    queue = queue[queue["tier"] <= args.max_tier]

    done = completed_keys()
    queue["key"] = queue["cik10"] + "__" + queue["ticker"]
    pending = queue[~queue["key"].isin(done)].reset_index(drop=True)

    plan = {
        "queue_rows_in_scope": int(len(queue)),
        "already_terminal": int(len(queue) - len(pending)),
        "pending": int(len(pending)),
        "estimated_days_remaining": round(len(pending) * 2 / limits["requests_per_day"], 1),
        "next_tier": int(pending["tier"].iloc[0]) if len(pending) else None,
    }
    print(json.dumps(plan, indent=2), flush=True)
    if args.dry_run:
        print("dry run - no provider contact made")
        return 0
    if pending.empty:
        print("backfill complete for the requested tiers")
        return 0

    token = os.environ.get("TIINGO_API_TOKEN", "").strip()
    if len(token) < 16:
        raise SystemExit(
            "TIINGO_API_TOKEN is required as a transient environment variable.\n"
            "  export TIINGO_API_TOKEN=your_token   (free tier: https://www.tiingo.com)"
        )

    limiter = RateLimiter(limits["requests_per_hour"], limits["requests_per_day"],
                          limits["minimum_seconds_between_requests"])
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)

    used = 0
    started = time.time()
    for position, row in pending.iterrows():
        if args.max_requests and used >= args.max_requests:
            print(f"stopping at requested budget of {args.max_requests} requests")
            break
        record = acquire(row, token, limiter)
        used += 1 if record.get("status", "").startswith("rejected") else 2
        with PROGRESS.open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        if position % 25 == 0:
            elapsed = timedelta(seconds=int(time.time() - started))
            print(f"[{position + 1}/{len(pending)}] tier {row['tier']} {row['ticker']:8s} "
                  f"{record['status']:44s} elapsed {elapsed}", flush=True)
    print(json.dumps({"requests_used_this_run": used, "rows_attempted": int(position + 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
