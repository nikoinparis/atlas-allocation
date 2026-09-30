#!/usr/bin/env python3
"""Collect, daily and forward-only, the two data channels A12 found worth watching.

Step 326 found two in-sample candidates on WorldQuant BRAIN -- analyst estimate revision
breadth (H1c) and the call-minus-put implied-volatility spread (H4b) -- and both weakened in
2023, the only year BRAIN collected that data live. Step 327 found BRAIN cannot simulate past
2023. Neither channel has a free point-in-time history, so the only honest way to test them
on data nobody has searched is to start recording it now and wait.

What one run saves, for one US session, per S&P 500 member:
- analyst revisions: up/down counts over the last 7 and 30 days, per period (0q, +1q, 0y,
  +1y), plus analyst count and the EPS-trend drift -- the free analogue of H1's fields;
- options: for the expirations nearest 30 and 90 calendar days, the strikes nearest spot
  (both calls and puts) with bid, ask, volume, open interest and implied volatility -- enough
  to rebuild H4's ATM call-minus-put IV at either horizon, and to change that construction
  later without having thrown the inputs away.

Each file is a snapshot of what Yahoo showed at `observed_at_utc`. It cannot be re-fetched
for a past date, so it is committed rather than cached, and an existing session is never
overwritten. The universe is the S&P 500 as listed on the collection day and is saved with
the snapshot, so later readers know exactly who was in it.

Research only: nothing here trades, and nothing here is a signal until it has been
pre-registered and has accumulated enough sessions to read.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/forward_signal_collection_v1"
UNIVERSE_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
TARGET_DAYS = (30, 90)
STRIKES_EACH_SIDE = 8


def session_date() -> date:
    """The latest US session that has printed a daily bar, taken from SPY rather than a calendar."""
    bars = yf.Ticker("SPY").history(period="10d", interval="1d", auto_adjust=False)
    return pd.Timestamp(bars.index[-1]).date()


def universe() -> list[str]:
    html = requests.get(UNIVERSE_URL, headers={"User-Agent": "portfolio-optimizer-research"}, timeout=30).text
    table = pd.read_html(io.StringIO(html))[0]
    return sorted({str(s).strip().replace(".", "-") for s in table["Symbol"]})


def revisions(ticker: yf.Ticker, symbol: str) -> list[dict]:
    rows = []
    rev, trend, estimate = ticker.eps_revisions, ticker.eps_trend, ticker.earnings_estimate
    if rev is None or rev.empty:
        return rows
    for period, row in rev.iterrows():
        record = {"symbol": symbol, "period": str(period)}
        record.update({k: (None if pd.isna(v) else v) for k, v in row.items() if k != "currency"})
        if trend is not None and period in trend.index:
            record.update({f"trend_{k}": (None if pd.isna(v) else float(v)) for k, v in trend.loc[period].items() if k != "currency"})
        if estimate is not None and period in estimate.index and "numberOfAnalysts" in estimate.columns:
            value = estimate.loc[period, "numberOfAnalysts"]
            record["number_of_analysts"] = None if pd.isna(value) else int(value)
        rows.append(record)
    return rows


def options(ticker: yf.Ticker, symbol: str, day: date) -> list[dict]:
    expirations = list(ticker.options or [])
    if not expirations:
        return []
    spot = float(ticker.fast_info["last_price"])
    chosen = {}
    for target in TARGET_DAYS:
        best = min(expirations, key=lambda e: abs((date.fromisoformat(e) - day).days - target))
        chosen.setdefault(best, target)
    rows = []
    for expiration, target in chosen.items():
        chain = ticker.option_chain(expiration)
        for side, frame in (("call", chain.calls), ("put", chain.puts)):
            if frame is None or frame.empty:
                continue
            near = frame.assign(distance=(frame["strike"] - spot).abs()).nsmallest(2 * STRIKES_EACH_SIDE, "distance")
            for row in near.itertuples():
                rows.append({
                    "symbol": symbol, "expiration": expiration, "target_days": target,
                    "days_to_expiry": (date.fromisoformat(expiration) - day).days, "side": side,
                    "spot": spot, "strike": float(row.strike), "bid": row.bid, "ask": row.ask,
                    "last_price": row.lastPrice, "volume": row.volume, "open_interest": row.openInterest,
                    "implied_volatility": row.impliedVolatility, "last_trade_utc": str(row.lastTradeDate),
                })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="first N symbols only, for a smoke test")
    parser.add_argument("--pause", type=float, default=0.25)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    day = session_date()
    folder = args.output / day.isoformat()
    if (folder / "manifest.json").exists():
        print(f"session {day} already collected; not overwriting")
        return 0

    symbols = universe()
    if args.limit:
        symbols = symbols[: args.limit]
    started = datetime.now(timezone.utc)
    revision_rows, option_rows, failures = [], [], {}
    for index, symbol in enumerate(symbols, 1):
        ticker = yf.Ticker(symbol)
        for name, collect, sink in (("revisions", lambda: revisions(ticker, symbol), revision_rows),
                                    ("options", lambda: options(ticker, symbol, day), option_rows)):
            try:
                sink.extend(collect())
            except Exception as error:                    # noqa: BLE001 -- one bad name must not stop the day
                failures.setdefault(symbol, {})[name] = f"{type(error).__name__}: {str(error)[:160]}"
        if index % 50 == 0:
            print(f"  {index}/{len(symbols)}", flush=True)
        time.sleep(args.pause)

    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(revision_rows).to_csv(folder / "analyst_revisions.csv.gz", index=False)
    pd.DataFrame(option_rows).to_csv(folder / "options_near_atm.csv.gz", index=False)
    covered = lambda rows: len({r["symbol"] for r in rows})
    manifest = {
        "session_date": day.isoformat(), "observed_at_utc": started.isoformat(),
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance via yfinance (free; a snapshot, not re-fetchable for past dates)",
        "universe": "S&P 500 as listed on Wikipedia on the collection day", "universe_symbols": symbols,
        "symbols_with_revisions": covered(revision_rows), "symbols_with_options": covered(option_rows),
        "revision_rows": len(revision_rows), "option_rows": len(option_rows),
        "option_targets_days": list(TARGET_DAYS), "strikes_each_side": STRIKES_EACH_SIDE,
        "failures": failures, "live_trading_enabled": False,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"session {day}: revisions for {manifest['symbols_with_revisions']}/{len(symbols)}, "
          f"options for {manifest['symbols_with_options']}/{len(symbols)}, {len(failures)} names with a failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
