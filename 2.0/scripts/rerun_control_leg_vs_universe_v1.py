#!/usr/bin/env python3
"""Re-run Step 222 with both sides priced identically, on repaired prices.

Step 222 concluded that the control leg loses to an equal-weight portfolio of
its own universe -- 17.72% against 26.55% -- and that result is why
FORWARD_CLOCK_DECISION_V1 describes the composite as four fifths a leg that
underperforms.  Two things found since make it unsafe to cite as it stands:

  Step 239  the panel that priced the benchmark carries 211 weekly returns above
            +100% and one infinite, none of which any strategy holds.  The
            contamination is on the benchmark side only, so it biases the
            comparison against the strategy.

  Step 240  a from-definition rebuild of the same book matches the saved path at
            0.90 correlation only after a one-week date-labelling shift.  Two
            series built by different code paths are therefore not necessarily
            aligned, and a strategy-versus-benchmark comparison across code paths
            can be a week out.

This computes both legs in one place, from one price file, with one convention,
so neither of those can explain the answer.  It does not attempt to reproduce
Step 222's exact setup -- that setup is not fully recorded -- so this is a fresh
measurement of the same question, and it is reported as such.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
BOOK = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv"
PRICES = {
    "repaired": "data/clean_corporate_action_prices_v1/weekly_adjusted_prices_clean.csv.gz",
    "unrepaired": "data/sec_broad_panel_inputs_v3/weekly_adjusted_prices.csv.gz",
}


def returns_from(relative: str) -> pd.DataFrame:
    frame = pd.read_csv(ROOT / relative, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    frame = frame.apply(pd.to_numeric, errors="coerce")
    return (frame / frame.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def run_book(schedule: dict, returns: pd.DataFrame, cost_bps: float) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for week in returns.index:
        cost = 0.0
        if week in schedule:
            holdings = pd.Series(0.0, index=returns.columns, dtype=float)
            names, weights = schedule[week]
            holdings.loc[names] = weights
            cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
            previous = holdings.copy()
        values.append(float((holdings * returns.loc[week].fillna(0.0)).sum()) - cost)
    return pd.Series(values, index=returns.index)


def metrics(series: pd.Series) -> dict[str, float]:
    years = len(series) / 52.0
    total = float((1.0 + series.fillna(0.0)).prod())
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    drawdown = float((wealth / wealth.cummax() - 1.0).min())
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    cagr = float(total ** (1.0 / years) - 1.0) if years else float("nan")
    recent = series.tail(52)
    return {
        "cagr": cagr,
        "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
        "annualised_volatility": volatility,
        "max_drawdown": drawdown,
        "recent_52w_return": float((1.0 + recent.fillna(0.0)).prod() - 1.0),
        "weeks": int(len(series)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost-bps", type=float, default=50.0)
    parser.add_argument("--output", default="evidence/control_leg_vs_universe_rerun_v1")
    args = parser.parse_args()

    scores = pd.read_csv(DISCOVERY, dtype={"cik10": str}, parse_dates=["decision_at"])
    scores = scores[scores.family == "cash_conversion"].dropna(subset=["score"])
    book = pd.read_csv(BOOK, dtype={"cik10": str}, parse_dates=["decision_at"])

    findings = {}
    for label, relative in PRICES.items():
        if not (ROOT / relative).is_file():
            continue
        returns = returns_from(relative)
        index = returns.index

        def execution(value) -> pd.Timestamp | None:
            value = pd.Timestamp(value)
            if value.tzinfo is None:
                value = value.tz_localize("UTC")
            later = index[index > value]
            return later[0] if len(later) else None

        strategy_schedule, universe_schedule = {}, {}
        for decision, frame in book.groupby("decision_at"):
            week = execution(decision)
            names = [c for c in frame.cik10 if c in returns.columns]
            if week is not None and names:
                strategy_schedule[week] = (names, np.repeat(1.0 / len(names), len(names)))
        for decision, frame in scores.groupby("decision_at"):
            week = execution(decision)
            names = [c for c in frame.cik10 if c in returns.columns]
            if week is not None and names:
                universe_schedule[week] = (names, np.repeat(1.0 / len(names), len(names)))

        strategy = run_book(strategy_schedule, returns, args.cost_bps)
        universe = run_book(universe_schedule, returns, args.cost_bps)
        start = min(strategy_schedule) if strategy_schedule else index[0]
        strategy, universe = strategy.loc[start:], universe.loc[start:]

        difference = strategy - universe
        block, draws = 13, 5000
        rng = np.random.default_rng(20260905)
        values = difference.to_numpy()
        blocks = max(1, len(values) // block)
        means = []
        for _ in range(draws):
            starts = rng.integers(0, max(1, len(values) - block), size=blocks)
            means.append(float(np.mean([values[s:s + block].mean() for s in starts])))
        findings[label] = {
            "strategy": metrics(strategy),
            "equal_weight_universe": metrics(universe),
            "universe_size_median": float(np.median([len(v[0]) for v in universe_schedule.values()])),
            "book_size_median": float(np.median([len(v[0]) for v in strategy_schedule.values()])),
            "cagr_gap_pp": round((metrics(strategy)["cagr"] - metrics(universe)["cagr"]) * 100, 2),
            "probability_strategy_beats_universe": float(np.mean([m > 0 for m in means])),
            "bootstrap_blocks_weeks": block,
            "bootstrap_draws": draws,
        }

    result = {
        "experiment": "control_leg_vs_universe_rerun_v1",
        "question": "does the cash-conversion breadth-20 book beat an equal weight of the universe it selects from",
        "both_legs_priced_from_one_file_with_one_convention": True,
        "not_a_reproduction_of_step_222": "Step 222's exact universe, coverage bar and cost convention are not fully recorded; this is a fresh measurement of the same question",
        "cost_bps": args.cost_bps,
        "findings": findings,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for label, f in findings.items():
        s, u = f["strategy"], f["equal_weight_universe"]
        print(f"== {label} prices ({f['book_size_median']:.0f} names from {f['universe_size_median']:.0f})")
        print(f"   strategy : CAGR {s['cagr']*100:7.2f}%  Sharpe {s['sharpe']:.3f}  vol {s['annualised_volatility']*100:5.1f}%  maxDD {s['max_drawdown']*100:7.2f}%  recent52 {s['recent_52w_return']*100:7.2f}%")
        print(f"   universe : CAGR {u['cagr']*100:7.2f}%  Sharpe {u['sharpe']:.3f}  vol {u['annualised_volatility']*100:5.1f}%  maxDD {u['max_drawdown']*100:7.2f}%  recent52 {u['recent_52w_return']*100:7.2f}%")
        print(f"   gap {f['cagr_gap_pp']:+.2f}pp   P(strategy beats universe) = {f['probability_strategy_beats_universe']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
