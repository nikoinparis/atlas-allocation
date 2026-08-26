#!/usr/bin/env python3
"""Score one realised week against a size- and volatility-matched random null.

Registered by config/forward_prediction_registry_v1.json before any forward data
existed. Each completed week, every tracked strategy's realised return is placed
inside the distribution of 4,000 random portfolios holding the same number of
names at the same volatility percentile over that same week.

Run with --rehearse to exercise the machinery on historical weeks. A rehearsal
writes to a separate file, is stamped as such, and never advances a forward clock.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/forward_prediction_registry_v1.json"
PRICES = ROOT / "data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/forward_prediction_registry_v1"

FIRST_ELIGIBLE = pd.Timestamp("2026-09-04")


def ticker_to_cik() -> dict[str, str]:
    out: dict[str, str] = {}
    with INVENTORY.open() as h:
        for row in csv.DictReader(h):
            m = re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
            if m:
                out.setdefault(m.group(1).upper(), row["cik10"])
    return out


def score_week(stamp, item, returns, volpct, tickers, draws, rng, tolerance):
    """Percentile of the strategy's realised week inside the matched random null."""
    records = {pd.Timestamp(r["date"]): r for r in item["records"]}
    if stamp not in records or stamp not in returns.index:
        return None
    record = records[stamp]
    names = [h for h in record["holdings"] if not h["symbol"].startswith("cash")]
    if not names:
        return None
    gross = sum(abs(float(h["weight"])) for h in names)
    realised = float(record["grossReturn"]) / max(1.0, gross)

    row = volpct.loc[stamp] if stamp in volpct.index else None
    weighted = total = 0.0
    if row is not None:
        for h in names:
            cik = tickers.get(h["symbol"].upper())
            if cik and cik in row.index and pd.notna(row[cik]):
                w = abs(float(h["weight"])); weighted += float(row[cik]) * w; total += w
    tilt = weighted / total if total else 0.5

    week = returns.loc[stamp].dropna()
    if len(week) < 200 or row is None:
        return None
    pool = row.reindex(week.index).dropna()
    eligible = pool.index[(pool - tilt).abs() <= tolerance]
    universe = week.reindex(eligible).dropna()
    size = min(len(names), max(1, len(universe) - 1))
    if len(universe) < size * 2:
        universe = week
        size = min(len(names), max(1, len(universe) - 1))
    values = universe.to_numpy()
    picks = rng.random((draws, len(values))).argsort(axis=1)[:, :size]
    null = values[picks].mean(axis=1)
    return {
        "date": str(stamp.date()), "strategy": item["strategy"]["id"],
        "short_name": item["strategy"]["shortName"],
        "names_held": len(names), "volatility_tilt": round(tilt, 4),
        "realised_return": round(realised, 6),
        "null_median": round(float(np.median(null)), 6),
        "percentile": round(float((null < realised).mean()), 4),
        "matched_pool": int(len(eligible)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rehearse", action="store_true", help="exercise on historical weeks; never advances a clock")
    parser.add_argument("--weeks", type=int, default=8)
    args = parser.parse_args()

    registry = json.loads(REGISTRY.read_text())
    prices = pd.read_csv(PRICES, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan)
    volpct = returns.rolling(52, min_periods=40).std(ddof=1).rank(axis=1, pct=True)

    tickers = ticker_to_cik()
    document = json.loads(DASHBOARD.read_text())
    tracked = {s["strategy"]["id"]: s for s in document["strategies"]
               if s["strategy"]["id"] in registry["strategies_tracked"]}

    method = registry["scoring_method"]
    rng = np.random.default_rng(20260904)
    stamps = [s for s in returns.index if s <= pd.Timestamp("2026-08-21")][-args.weeks:] if args.rehearse else \
             [s for s in returns.index if s >= FIRST_ELIGIBLE]

    if not args.rehearse and not stamps:
        print(json.dumps({"status": "no_eligible_week_yet",
                          "first_eligible_realization": str(FIRST_ELIGIBLE.date()),
                          "today": str(datetime.now(timezone.utc).date())}, indent=2))
        return 0

    rows = []
    for stamp in stamps:
        for item in tracked.values():
            scored = score_week(stamp, item, returns, volpct, tickers, method["draws"], rng, 0.05)
            if scored:
                rows.append(scored)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    name = "rehearsal_scores.csv" if args.rehearse else "forward_scores.csv"
    frame.to_csv(OUTPUT / name, index=False)

    summary = {
        "mode": "REHEARSAL - not forward evidence" if args.rehearse else "forward",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weeks_scored": int(frame.date.nunique()) if len(frame) else 0,
        "advances_forward_clock": False if args.rehearse else True,
        "median_percentile_by_strategy": (frame.groupby("short_name").percentile.median().round(4).to_dict()
                                          if len(frame) else {}),
        "live_trading_enabled": False,
    }
    (OUTPUT / ("rehearsal_summary.json" if args.rehearse else "forward_summary.json")).write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")

    print(f"{summary['mode']}   weeks scored: {summary['weeks_scored']}\n")
    if len(frame):
        print(f"  {'strategy':<26}{'median pctile':>15}{'weeks':>8}")
        for name_, group in frame.groupby("short_name"):
            print(f"  {name_:<26}{group.percentile.median():>15.3f}{len(group):>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
