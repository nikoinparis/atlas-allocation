#!/usr/bin/env python3
"""Rebuild the benchmark and energy-attribution context for the held-book marks.

Both files were first written by hand for three weeks. They feed the forward
tracker, so they have to roll forward with the marks rather than be re-made each
week; a stale benchmark file silently mis-states every comparison on the page.

The energy classification is deliberately not recomputed. It was declared on
2026-09-02 after seeing three weeks, which is recorded there as a bias; the books
are frozen so the symbol set cannot change, and re-deriving the list each week
would let it drift toward whatever happened to work.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
MARKS = ROOT / "evidence/dashboard_held_book_marks_v1/held_book_weekly_marks.csv"
BOOKS = ROOT / "evidence/dashboard_last_books_v1/last_books.csv"
SUMMARY = ROOT / "evidence/dashboard_held_book_marks_v1/summary.json"
PANEL = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
OUTPUT = ROOT / "evidence/dashboard_held_book_marks_v1"

ANCHOR = pd.Timestamp("2026-08-07")
BENCHMARKS = ["QQQ", "SPY", "XLK"]
ENERGY = ["BKV", "EQT", "HPK", "MTDR", "NOG", "USO", "XLE"]


def main() -> int:
    marks = pd.read_csv(MARKS)
    weeks = [pd.Timestamp(w) for w in sorted(marks.week_ending.unique())]
    last = max(weeks)

    daily = yf.download(BENCHMARKS, start="2026-07-25", end=str((last + pd.Timedelta(days=3)).date()),
                        interval="1d", auto_adjust=False, progress=False, threads=False,
                        group_by="column")["Adj Close"]
    daily.index = pd.to_datetime(daily.index).tz_localize(None)
    bench = daily.resample("W-FRI").last().loc[lambda f: f.index >= ANCHOR].pct_change().reindex(weeks)

    panel = pd.read_csv(PANEL, index_col=0)
    panel.index = pd.to_datetime(panel.index)
    universe = panel.pct_change().reindex(weeks).mean(axis=1)
    bench["equal_weight_issuer_universe"] = universe

    week_labels = [str(w.date()) for w in weeks]
    payload = {
        "weeks": week_labels,
        "cumulative": {c: float((1 + bench[c]).prod() - 1) for c in bench.columns},
        "weekly": {c: {str(w.date()): float(bench.at[w, c]) for w in weeks} for c in bench.columns},
        "note": "context for the held-book marks; these are the same closed weeks",
    }
    (OUTPUT / "benchmarks.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    # Per-instrument contributions: the marks are weight-times-return sums, so the
    # energy share is recoverable by re-pricing only the energy leg of each book.
    books = pd.read_csv(BOOKS)
    books = books[~books.symbol.astype(str).str.startswith("cash")]
    symbols = sorted(set(books.symbol))
    prices = yf.download(symbols, start="2026-07-25", end=str((last + pd.Timedelta(days=3)).date()),
                         interval="1d", auto_adjust=False, progress=False, threads=False,
                         group_by="column")["Adj Close"]
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    returns = prices.resample("W-FRI").last().loc[lambda f: f.index >= ANCHOR].pct_change().reindex(weeks)

    gross_by_id = {s["strategy_id"]: s["gross_exposure_priced"]
                   for s in json.loads(SUMMARY.read_text())["strategies"]}
    rows = []
    for strategy_id, group in books.groupby("strategy_id"):
        weights = group.set_index("symbol").weight.astype(float)
        energy = weights.reindex([s for s in weights.index if s in ENERGY]).dropna()
        contrib = float((returns.reindex(columns=weights.index).fillna(0.0) * weights).sum(axis=1).sum())
        energy_contrib = float((returns.reindex(columns=energy.index).fillna(0.0) * energy).sum(axis=1).sum())
        energy_weight = float(energy.abs().sum())
        non_energy_weight = gross_by_id[strategy_id] - energy_weight
        rows.append({
            "strategy": strategy_id,
            "weeks_total": contrib,
            "energy_contrib": energy_contrib,
            "energy_weight": energy_weight,
            "ex_energy": contrib - energy_contrib,
            "ex_energy_sleeve_return": (contrib - energy_contrib) / non_energy_weight,
            "energy_share_of_gain": energy_contrib / contrib if contrib else None,
        })

    attribution = {
        "weeks": week_labels,
        "energy_symbols_classified": ENERGY,
        "rows": sorted(rows, key=lambda r: -r["weeks_total"]),
        "note": ("arithmetic weekly weight-times-return contributions summed over the closed weeks; "
                 "energy classification was fixed on 2026-09-02 after seeing the first three weeks "
                 "and is held constant since, so it is a hypothesis about later weeks rather than a "
                 "finding about the ones that produced it"),
    }
    (OUTPUT / "energy_attribution.json").write_text(json.dumps(attribution, indent=2, sort_keys=True) + "\n")

    print(f"weeks: {week_labels}")
    print(f"  {'book':<44}{'total':>9}{'energy':>9}{'ex-E':>9}{'ex-E sleeve':>13}")
    for r in attribution["rows"]:
        print(f"  {r['strategy']:<44}{r['weeks_total']:>8.2%}{r['energy_contrib']:>9.2%}"
              f"{r['ex_energy']:>9.2%}{r['ex_energy_sleeve_return']:>13.2%}")
    print("  benchmarks: " + "  ".join(f"{k} {v:+.2%}" for k, v in payload["cumulative"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
