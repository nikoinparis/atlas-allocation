#!/usr/bin/env python3
"""A2: try to repair the breadth these books destroy, and check whether it pays.

Step 245 measured the problem and nobody acted on it for thirty steps. The equity
books hold 10-28 names but only 5-7 of them are independent, and 61-71% of
positions survive from one quarterly rebalance to the next, so a nominal 40-114
decisions a year collapses to an effective 8.5. Breadth is squared-rooted in
`IR = IC * sqrt(BR)`, so on paper this is the cheapest lever available and it
needs no new signal and no new data.

Step 277 is the reason this script reports two numbers instead of one. Adding
XLE to the two-leg blend raised effective independent bets from 2.00 to 2.88 and
raised Sharpe by 0.021, because XLE's own skill is poor. Breadth bought at the
cost of IC pays nothing. So every intervention here reports the breadth it buys
*and* the risk-adjusted return it lands on, and an intervention that raises the
first while lowering the second is a failure however good the breadth looks.

Four interventions, declared before running:
  baseline      breadth 20, quarterly, equal weight -- what the books do now
  sector_cap    at most 3 names per sector, to attack the 5-7 effective names
  wide          breadth 40, to attack the same thing by dilution instead
  depersist     drop any name held the previous two quarters, to attack the 61-71%

Nothing here is a new signal. This is construction only, and Step 245's own note
stands: the realistic ceiling is 40-60 bets a year against the 91 an IR of 0.25
would need, so this cannot be sufficient on its own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/breadth_repair_v1"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
PANELS = {
    "valuation": ROOT / "evidence/sec_survivorship_valuation_discovery_v1/factor_scores.csv",
    "fundamental": ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv",
}
FAMILIES = {"valuation": "earnings_yield", "fundamental": "cash_conversion"}
COST_BPS = 50.0
BREAK = pd.Timestamp("2025-04-04", tz="UTC")


def load_returns() -> pd.DataFrame:
    frame = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    out = (frame / frame.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    return out.where(out.abs() <= 1.0)


def metrics(returns: pd.Series) -> dict[str, float]:
    if len(returns) < 20:
        return {}
    total = float((1.0 + returns).prod())
    years = len(returns) / 52.0
    cagr = total ** (1.0 / years) - 1.0 if total > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "volatility": vol, "max_drawdown": float((curve / curve.cummax() - 1.0).min())}


def participation_ratio(correlation: np.ndarray) -> float:
    """Effective number of independent series. (sum lambda)^2 / sum lambda^2."""
    values = np.linalg.eigvalsh(correlation)
    values = values[values > 0]
    return float(values.sum() ** 2 / (values ** 2).sum()) if len(values) else float("nan")


def pick(block: pd.DataFrame, breadth: int, sector_cap: int | None,
         banned: set[str]) -> list[str]:
    ordered = block.sort_values("score", ascending=False)
    if banned:
        ordered = ordered[~ordered.cik10.isin(banned)]
    if sector_cap is None:
        return list(ordered.head(breadth).cik10)
    chosen, per_sector = [], {}
    for row in ordered.itertuples():
        sector = str(getattr(row, "sector", "unknown"))
        if per_sector.get(sector, 0) >= sector_cap:
            continue
        chosen.append(row.cik10)
        per_sector[sector] = per_sector.get(sector, 0) + 1
        if len(chosen) >= breadth:
            break
    return chosen


def run(scores: pd.DataFrame, returns: pd.DataFrame, breadth: int,
        sector_cap: int | None, depersist: bool) -> dict:
    execution = {}
    for value in sorted(scores.decision_at.unique()):
        later = returns.index[returns.index > value]
        if len(later):
            execution[value] = later[0]

    schedule, history, independence = {}, [], []
    previous: list[set[str]] = []
    persistence = []
    for decision, block in scores.groupby("decision_at"):
        week = execution.get(decision)
        if week is None or len(block) < breadth:
            continue
        banned = set()
        if depersist and len(previous) >= 2:
            banned = previous[-1] & previous[-2]
        names = pick(block, breadth, sector_cap, banned)
        if len(names) < max(5, breadth // 2):
            names = pick(block, breadth, sector_cap, set())
        held = set(names)
        if previous:
            overlap = len(held & previous[-1]) / max(1, len(held))
            persistence.append(overlap)
        previous.append(held)
        schedule[week] = names
        history.append((week, names))

    # Effective independent names, measured on the returns actually held.
    for week, names in history:
        window = returns.loc[:week].tail(52)
        held = [n for n in names if n in window.columns]
        block = window[held].dropna(axis=1, how="all")
        if block.shape[1] < 3:
            continue
        corr = block.corr().to_numpy()
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
        independence.append(participation_ratio(corr))

    # Price the book.
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    values = []
    start = min(schedule) if schedule else None
    for week in returns.index:
        if start is None or week < start:
            continue
        cost = 0.0
        if week in schedule:
            target = pd.Series(0.0, index=returns.columns, dtype=float)
            names = [n for n in schedule[week] if n in target.index]
            if names:
                target[names] = 1.0 / len(names)
            cost = float((target - holdings).abs().sum()) / 2.0 * COST_BPS / 10_000.0
            holdings = target
        row = returns.loc[week].fillna(0.0)
        values.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    path = pd.Series(dict(values)).sort_index()

    rebalances_per_year = len(schedule) / (len(path) / 52.0) if len(path) else float("nan")
    mean_independent = float(np.mean(independence)) if independence else float("nan")
    mean_persistence = float(np.mean(persistence)) if persistence else 0.0
    # Grinold's breadth adjusted for how much of the book is a repeat of last quarter's.
    effective_bets = rebalances_per_year * mean_independent * (1.0 - mean_persistence)

    out = {
        "nominal_names": breadth,
        "rebalances_per_year": rebalances_per_year,
        "effective_independent_names": mean_independent,
        "persistence": mean_persistence,
        "effective_bets_per_year": effective_bets,
        **metrics(path),
    }
    pre, post = path[path.index < BREAK], path[path.index >= BREAK]
    out["pre_break_cagr"] = metrics(pre).get("cagr", float("nan"))
    out["post_break_cagr"] = metrics(post).get("cagr", float("nan"))
    return out, path


def main() -> int:
    returns = load_returns()
    interventions = {
        "baseline":   dict(breadth=20, sector_cap=None, depersist=False),
        "sector_cap": dict(breadth=20, sector_cap=3,    depersist=False),
        "wide":       dict(breadth=40, sector_cap=None, depersist=False),
        "depersist":  dict(breadth=20, sector_cap=None, depersist=True),
        "combined":   dict(breadth=40, sector_cap=3,    depersist=True),
    }

    rows, paths = [], {}
    for book, panel in PANELS.items():
        scores = pd.read_csv(panel, dtype={"cik10": str})
        scores["decision_at"] = pd.to_datetime(scores.decision_at, utc=True)
        scores = scores[scores.family == FAMILIES[book]].dropna(subset=["score"])
        scores = scores[scores.cik10.isin(returns.columns)]
        for name, kwargs in interventions.items():
            result, path = run(scores, returns, **kwargs)
            rows.append({"book": book, "intervention": name, **result})
            paths[f"{book}__{name}"] = path

    frame = pd.DataFrame(rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "interventions.csv", index=False)

    for book in PANELS:
        sub = frame[frame.book == book]
        base = sub[sub.intervention == "baseline"].iloc[0]
        print(f"\n{book} ({FAMILIES[book]})")
        print(f"  {'intervention':12s} {'names':>6s} {'indep':>6s} {'persist':>8s} "
              f"{'bets/yr':>8s} {'CAGR':>8s} {'Sharpe':>7s} {'maxDD':>8s}")
        for _, r in sub.iterrows():
            flag = ""
            if r.intervention != "baseline":
                better_breadth = r.effective_bets_per_year > base.effective_bets_per_year
                better_sharpe = r.sharpe > base.sharpe
                flag = "  <- breadth and Sharpe both up" if (better_breadth and better_sharpe) else (
                       "  breadth up, Sharpe down" if better_breadth else "")
            print(f"  {r.intervention:12s} {r.nominal_names:6.0f} {r.effective_independent_names:6.2f} "
                  f"{r.persistence:7.1%} {r.effective_bets_per_year:8.1f} {r.cagr:8.2%} "
                  f"{r.sharpe:7.3f} {r.max_drawdown:8.2%}{flag}")

    wins = []
    for book in PANELS:
        sub = frame[frame.book == book]
        base = sub[sub.intervention == "baseline"].iloc[0]
        for _, r in sub[sub.intervention != "baseline"].iterrows():
            if r.effective_bets_per_year > base.effective_bets_per_year and r.sharpe > base.sharpe:
                wins.append(f"{book}/{r.intervention}")

    result = {
        "interventions_declared_before_running": list(interventions),
        "books": list(PANELS),
        "raised_breadth_and_sharpe_together": wins,
        "count_raised_both": len(wins),
        "count_tested": int(len(frame) - len(PANELS)),
        "step_245_baseline_effective_bets": 8.5,
        "this_is_construction_not_a_new_signal": True,
        "note": ("Step 277: breadth bought at the cost of IC pays nothing. An intervention "
                 "that raises effective bets while lowering Sharpe is a failure."),
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("\n" + json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
