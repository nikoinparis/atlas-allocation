#!/usr/bin/env python3
"""Mark each dashboard strategy's final decided book to market on the new weeks.

This is deliberately NOT a forward record for any strategy, and it must never be
presented as one. Every dashboard strategy's weekly record stops at 2026-08-07
because that is where its backtest stops, not because prices are missing.
Advancing the strategies themselves would mean re-running their selection
pipelines on new point-in-time SEC data, which re-opens selection and is exactly
what CLAUDE.md forbids doing casually.

What this does instead is answer the narrower, answerable question: if the last
book each strategy actually decided had simply been held, what would it have
returned over the weeks that have closed since? That is a held snapshot, and the
output labels it as one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "evidence/dashboard_last_books_v1/last_books.csv"
OUTPUT = ROOT / "evidence/dashboard_held_book_marks_v1"

ANCHOR = pd.Timestamp("2026-08-07")
FINANCING_ANNUAL = {
    "sec-residual-controlled-1.25x-5pct-v1": 0.05,
    "sec-sector-ensemble-fragile-1.35x-v1": 0.05,
}


def last_closed_friday(now: pd.Timestamp) -> pd.Timestamp:
    """The most recent Friday that has already ended in US market terms."""
    candidate = now.normalize() - pd.Timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 21:
        candidate -= pd.Timedelta(days=7)
    return candidate


def main() -> int:
    books = pd.read_csv(BOOKS)
    symbols = sorted({s for s in books["symbol"] if not str(s).startswith("cash")})
    print(f"pricing {len(symbols)} symbols", flush=True)

    cutoff = last_closed_friday(pd.Timestamp.now(tz="UTC").tz_localize(None))
    daily = yf.download(symbols, start="2026-07-25", end=str((cutoff + pd.Timedelta(days=3)).date()),
                        interval="1d", auto_adjust=False, progress=False, threads=False,
                        group_by="column")
    adjusted = daily["Adj Close"]
    adjusted.index = pd.to_datetime(adjusted.index).tz_localize(None)
    weekly = adjusted.resample("W-FRI").last()
    weekly = weekly.loc[weekly.index >= ANCHOR]
    weekly = weekly.loc[weekly.index <= cutoff]
    returns = weekly.pct_change().dropna(how="all")
    print("weeks priced:", [str(d.date()) for d in returns.index], flush=True)

    rows, summary = [], []
    for strategy_id, group in books.groupby("strategy_id"):
        held = group[~group["symbol"].astype(str).str.startswith("cash")]
        weights = held.set_index("symbol")["weight"].astype(float)
        missing = [s for s in weights.index if s not in returns.columns or returns[s].isna().all()]
        priced = weights.drop(index=missing)
        gross = float(priced.abs().sum())
        financing_weekly = FINANCING_ANNUAL.get(strategy_id, 0.0) * max(gross - 1.0, 0.0) / 52.0
        wealth = 1.0
        for date, week in returns.iterrows():
            contribution = float((priced * week.reindex(priced.index)).fillna(0.0).sum())
            net = contribution - financing_weekly
            wealth *= 1.0 + net
            rows.append({
                "strategy_id": strategy_id, "week_ending": str(date.date()),
                "held_book_return": contribution, "financing": -financing_weekly,
                "net_return": net, "cumulative": wealth - 1.0,
            })
        summary.append({
            "strategy_id": strategy_id,
            "book_as_of": str(ANCHOR.date()),
            "names_in_book": int(len(weights)),
            "names_priced": int(len(priced)),
            "names_unpriced": missing,
            "gross_exposure_priced": gross,
            "financing_annual": FINANCING_ANNUAL.get(strategy_id, 0.0),
            "weeks_marked": int(len(returns)),
            "cumulative_return": wealth - 1.0,
        })
        print(f"{strategy_id}: {wealth - 1.0:+.4%} over {len(returns)} held weeks "
              f"({len(priced)}/{len(weights)} names priced)", flush=True)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "held_book_weekly_marks.csv", index=False)
    payload = {
        "experiment": "dashboard_held_book_marks_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "what_this_is": "the last decided book of each dashboard strategy, held unchanged and marked to market",
        "what_this_is_not": "This is not a forward observation of any strategy. No strategy decided these weeks: each book last decided on 2026-08-07 and nothing rebalanced it since.",
        "weeks": [str(d.date()) for d in returns.index],
        "cost_treatment": "no turnover occurs in a held book, so no trading cost is charged; the two levered books are charged their own stated 5% annual financing on the borrowed portion",
        "strategies": summary,
        "live_trading_enabled": False,
        "promotion_authorized": False,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
