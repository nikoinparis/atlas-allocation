#!/usr/bin/env python3
"""Widen the valuation book until it passes the gate it failed, and see what survives.

Step 273 found valuation is the only genuinely separate thing this project has
built, and that it earned 62.34% at Sharpe 1.115 in the 117 weeks when the growth
book earned 8.15% at 0.497. It was set aside for concentration rather than for
returns: `sales_yield__top10` passed the replacement-return gate and failed the
concentration gate.

Ten names is the reason. This widens to twenty, thirty and fifty with issuer caps.
If the return is a property of ten names it will not survive; if it is a property
of the signal it should. Both outcomes are worth knowing and both are declared.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/valuation_revival_registry_v1.json"
SCORES = ROOT / "evidence/sec_survivorship_valuation_discovery_v1/factor_scores.csv"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")


def build_book(block: pd.DataFrame, breadth: int, cap: float) -> tuple[list[str], np.ndarray]:
    picked = block.nlargest(breadth, "score")
    weights = np.repeat(1.0 / len(picked), len(picked))
    if cap < 1.0 / len(picked):
        cap = 1.0 / len(picked)
    weights = np.minimum(weights, cap)
    return list(picked.cik10), weights / weights.sum()


def simulate(schedule: dict, returns: pd.DataFrame, cost_bps: float):
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values, contribution = [], pd.Series(0.0, index=returns.columns, dtype=float)
    for week in returns.index:
        cost = 0.0
        if week in schedule:
            names, weights = schedule[week]
            holdings = pd.Series(0.0, index=returns.columns, dtype=float)
            holdings.loc[names] = weights
            cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
            previous = holdings.copy()
        observed = returns.loc[week].fillna(0.0)
        contribution = contribution.add(holdings * observed, fill_value=0.0)
        values.append(float((holdings * observed).sum()) - cost)
    return pd.Series(values, index=returns.index), contribution


def metrics(series: pd.Series) -> dict[str, float]:
    if len(series) < 10:
        return {}
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    years = len(series) / 52.0
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return {"cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
            "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
            "max_drawdown": float((wealth / wealth.cummax() - 1.0).min())}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/valuation_revival_v1")
    parser.add_argument("--family", default="")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    declared = registry["declared_configurations"]

    scores = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    scores["decision_at"] = pd.to_datetime(scores.decision_at, utc=True)
    family = args.family or scores.family.value_counts().index[0]
    scores = scores[(scores.family == family)].dropna(subset=["score"])

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    scores = scores[scores.cik10.isin(returns.columns)]

    execution = {}
    for value in sorted(scores.decision_at.unique()):
        later = returns.index[returns.index > value]
        if len(later):
            execution[value] = later[0]

    universe_schedule = {}
    for decision, block in scores.groupby("decision_at"):
        week = execution.get(decision)
        if week is None:
            continue
        names = list(block.cik10)
        universe_schedule[week] = (names, np.repeat(1.0 / len(names), len(names)))

    rows = []
    for breadth in declared["breadth"]:
        for cap in declared["maximum_issuer_weight"]:
            schedule = {}
            for decision, block in scores.groupby("decision_at"):
                week = execution.get(decision)
                if week is not None and len(block) >= breadth:
                    schedule[week] = build_book(block, breadth, cap)
            if len(schedule) < 8:
                continue
            for cost in declared["cost_bps"]:
                path, contribution = simulate(schedule, returns, float(cost))
                universe, _ = simulate(universe_schedule, returns, float(cost))
                start = min(schedule)
                path, universe = path.loc[start:], universe.loc[start:]
                positive = contribution.clip(lower=0)
                concentration = float(positive.max() / positive.sum()) if positive.sum() else 1.0
                entry = {"family": family, "breadth": breadth, "issuer_cap": cap, "cost_bps": cost,
                         "weeks": len(path), "concentration_top_issuer": concentration,
                         "concentration_gate_passed": bool(concentration <= 0.10)}
                for label, mask in (("full", pd.Series(True, index=path.index)),
                                    ("pre_break", path.index < BREAK), ("post_break", path.index >= BREAK)):
                    a, b = path[mask], universe[mask]
                    if len(a) < 20:
                        continue
                    ma, mb = metrics(a), metrics(b)
                    entry[f"{label}_cagr"] = ma["cagr"]
                    entry[f"{label}_universe_cagr"] = mb["cagr"]
                    entry[f"{label}_excess"] = ma["cagr"] - mb["cagr"]
                    entry[f"{label}_sharpe"] = ma["sharpe"]
                rows.append(entry)
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "revival.csv", index=False)

    survivors = table[(table.concentration_gate_passed)
                      & (table.get("full_excess", pd.Series(dtype=float)) > 0)
                      & (table.get("pre_break_excess", pd.Series(dtype=float)) > 0)
                      & (table.get("post_break_excess", pd.Series(dtype=float)) > 0)]
    if table.empty:
        verdict = "no configuration produced enough rebalances"
    elif survivors.empty:
        passing = table[table.concentration_gate_passed]
        verdict = (f"{len(passing)} of {len(table)} configurations pass concentration, and none of "
                   f"them beats an equal weight of its own scored universe in both sub-periods. "
                   f"Widening the book destroys the result: the valuation return was the ten names, "
                   f"not the signal. The family closes properly.")
    else:
        best = survivors.sort_values("full_excess", ascending=False).iloc[0]
        verdict = (f"{len(survivors)} configuration(s) pass concentration AND beat their own universe "
                   f"in both sub-periods; best is breadth {int(best.breadth)} at cap {best.issuer_cap}, "
                   f"{best.full_excess*100:+.1f} points of excess. First strategy here to pass a gate "
                   f"it previously failed. It has no forward evidence.")

    result = {"experiment": "valuation_revival_v1", "family": family,
              "declared_trials": declared["total_trials"], "rows": rows,
              "survivors": int(len(survivors)), "verdict": verdict,
              "caveat": registry["interpretation_fixed_in_advance"]["always"],
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    show = [c for c in ["breadth", "issuer_cap", "cost_bps", "concentration_top_issuer",
                        "concentration_gate_passed", "full_cagr", "full_universe_cagr", "full_excess",
                        "pre_break_excess", "post_break_excess", "full_sharpe"] if c in table.columns]
    print(f"family: {family}\n")
    print(table[show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
