#!/usr/bin/env python3
"""Account for this portfolio's breadth, the way Grinold and Kahn define it.

`IR = IC x sqrt(BR)`.  This project has spent 240-odd steps searching for IC and
almost none measuring BR, and CLAUDE.md already names the consequence: an
effective independent strategy count near 1.15, which is the real ceiling on
risk-adjusted return here.  Retuning signals cannot raise it.

This measures, per strategy and then across strategies:

  IC          rank correlation between the score at decision time and the
              realised forward return over the period that score was acted on
  BR nominal  names held times rebalances per year, the number people quote
  BR effective the same thing after the two ways breadth is actually lost:
              holdings that move together, and books that barely change between
              rebalances
  TC          the transfer coefficient, realised IR divided by IC x sqrt(BR).
              Below one means skill is being lost between signal and portfolio;
              far above one means the return is not coming from the signal at all

The last of those is the diagnostic worth having.  A strategy whose realised IR
is five times what its IC and breadth can support is not a strategy with a large
IC -- it is a strategy whose return came from somewhere the model does not see.

This claims no alpha and proposes no trade.  It is an accounting exercise, and
its output is a set of numbers about work already done.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("effective_bets", ROOT / "scripts/measure_effective_bets_v1.py")
_bets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bets)

PRICES = "data/clean_corporate_action_prices_v1/weekly_adjusted_prices_clean.csv.gz"
DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"

STRATEGIES = {
    "cash_conversion_breadth20": {
        "book": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv",
        "date_column": "decision_at",
        "scores": ("factor_scores", "cash_conversion"),
    },
    "growth_top_five": {
        "book": "evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv",
        "date_column": "decision_at",
        "scores": ("growth_scores", None),
    },
    "sector_ensemble": {
        "book": "evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv",
        "date_column": "rebalance_at",
        "scores": None,
    },
}


def returns_frame() -> pd.DataFrame:
    frame = pd.read_csv(ROOT / PRICES, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    frame = frame.apply(pd.to_numeric, errors="coerce")
    return (frame / frame.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def load_scores(spec) -> pd.DataFrame | None:
    if spec is None:
        return None
    kind, family = spec
    if kind == "factor_scores":
        frame = pd.read_csv(DISCOVERY, dtype={"cik10": str}, parse_dates=["decision_at"])
        frame = frame[frame.family == family]
    else:
        frame = pd.read_csv(ROOT / "evidence/sec_growth_survivorship_retest_v1/growth_scores.csv",
                            dtype={"cik10": str}, parse_dates=["decision_at"])
    frame["decision_at"] = pd.to_datetime(frame.decision_at, utc=True)
    return frame[["decision_at", "cik10", "score"]].dropna(subset=["score"])


def information_coefficient(scores: pd.DataFrame, returns: pd.DataFrame) -> dict[str, object]:
    """Spearman IC between the score and the return actually earned after it."""
    index = returns.index
    decisions = sorted(scores.decision_at.unique())
    values = []
    for position, decision in enumerate(decisions):
        later = index[index > decision]
        if not len(later):
            continue
        start = later[0]
        end = (index[index > decisions[position + 1]][0]
               if position + 1 < len(decisions) and len(index[index > decisions[position + 1]])
               else index[-1])
        window = returns.loc[(returns.index >= start) & (returns.index <= end)]
        if window.empty:
            continue
        forward = (1.0 + window.fillna(0.0)).prod() - 1.0
        block = scores[scores.decision_at == decision]
        common = [c for c in block.cik10 if c in forward.index]
        if len(common) < 30:
            continue
        paired = pd.DataFrame({
            "score": block.set_index("cik10").score.reindex(common).to_numpy(),
            "forward": forward.reindex(common).to_numpy(),
        }).dropna()
        if len(paired) < 30:
            continue
        values.append(float(paired.score.rank().corr(paired.forward.rank())))
    if not values:
        return {"decisions": 0}
    array = np.array(values)
    return {
        "decisions": len(array),
        "mean_ic": float(array.mean()),
        "ic_std": float(array.std(ddof=1)),
        "ic_t_stat": float(array.mean() / (array.std(ddof=1) / np.sqrt(len(array)))) if len(array) > 1 else None,
        "share_positive": float((array > 0).mean()),
    }


def breadth(book: pd.DataFrame, returns: pd.DataFrame) -> dict[str, object]:
    dates = sorted(book.execution_at.unique())
    sizes = [len(book[book.execution_at == d]) for d in dates]
    span_years = (dates[-1] - dates[0]).days / 365.25 if len(dates) > 1 else 1.0
    rebalances_per_year = (len(dates) - 1) / span_years if span_years > 0 else float(len(dates))

    # Cross-sectional: holdings that move together are not separate bets.
    effective_names = []
    for date in dates:
        names = [c for c in book[book.execution_at == date].cik10 if c in returns.columns]
        window = returns.loc[returns.index <= date].tail(52)[names].dropna(axis=1, how="all")
        if window.shape[1] < 3 or window.shape[0] < 12:
            continue
        correlation = window.corr().to_numpy()
        correlation = np.nan_to_num(correlation, nan=0.0)
        np.fill_diagonal(correlation, 1.0)
        effective_names.append(_bets.participation_ratio(correlation))
    effective_name_count = float(np.median(effective_names)) if effective_names else float(np.median(sizes))

    # Temporal: a book that barely changes has not placed a new bet.
    overlaps = []
    for earlier, later in zip(dates, dates[1:]):
        before = set(book[book.execution_at == earlier].cik10)
        after = set(book[book.execution_at == later].cik10)
        if before:
            overlaps.append(len(before & after) / len(before))
    persistence = float(np.mean(overlaps)) if overlaps else 0.0
    independent_rebalance_share = 1.0 - persistence

    nominal = float(np.median(sizes)) * rebalances_per_year
    effective = effective_name_count * rebalances_per_year * max(independent_rebalance_share, 1e-6)
    return {
        "rebalances": len(dates),
        "rebalances_per_year": rebalances_per_year,
        "median_names_held": float(np.median(sizes)),
        "effective_independent_names": effective_name_count,
        "book_persistence_between_rebalances": persistence,
        "independent_share_of_each_rebalance": independent_rebalance_share,
        "breadth_nominal_per_year": nominal,
        "breadth_effective_per_year": effective,
        "breadth_lost_to_correlation_and_persistence": round(1.0 - effective / nominal, 4) if nominal else None,
    }


def realised_ir(strategy: pd.Series, benchmark: pd.Series) -> dict[str, float]:
    joined = pd.concat([strategy.rename("s"), benchmark.rename("b")], axis=1).dropna()
    excess = joined.s - joined.b
    volatility = float(excess.std(ddof=1) * np.sqrt(52))
    return {
        "weeks": int(len(excess)),
        "mean_annual_excess": float(excess.mean() * 52),
        "tracking_error": volatility,
        "realised_information_ratio": float(excess.mean() * 52 / volatility) if volatility else float("nan"),
    }


def run_book(schedule: dict, returns: pd.DataFrame, cost_bps: float) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    previous = holdings.copy()
    values = []
    for week in returns.index:
        cost = 0.0
        if week in schedule:
            names = schedule[week]
            holdings = pd.Series(0.0, index=returns.columns, dtype=float)
            holdings.loc[names] = 1.0 / len(names)
            cost = float((holdings - previous).abs().sum()) * cost_bps / 10_000.0
            previous = holdings.copy()
        values.append(float((holdings * returns.loc[week].fillna(0.0)).sum()) - cost)
    return pd.Series(values, index=returns.index)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cost-bps", type=float, default=50.0)
    parser.add_argument("--output", default="evidence/breadth_accounting_v1")
    args = parser.parse_args()

    returns = returns_frame()
    index = returns.index
    findings, paths = {}, {}

    for name, spec in STRATEGIES.items():
        book = pd.read_csv(ROOT / spec["book"], dtype={"cik10": str})
        book[spec["date_column"]] = pd.to_datetime(book[spec["date_column"]], utc=True)
        book = book.rename(columns={spec["date_column"]: "decision_at"})
        mapping = {}
        for value in sorted(book.decision_at.unique()):
            later = index[index > value]
            if len(later):
                mapping[value] = later[0]
        book = book[book.decision_at.isin(mapping)].copy()
        book["execution_at"] = book.decision_at.map(mapping)
        book = book[book.cik10.isin(returns.columns)]
        if book.empty:
            findings[name] = {"error": "no held issuer is priced"}
            continue

        schedule = {d: sorted(f.cik10) for d, f in book.groupby("execution_at")}
        strategy = run_book(schedule, returns, args.cost_bps)
        start = min(schedule)
        strategy = strategy.loc[start:]
        paths[name] = strategy

        scores = load_scores(spec["scores"])
        ic = information_coefficient(scores, returns) if scores is not None else {"decisions": 0}
        br = breadth(book, returns)

        if scores is not None and not scores.empty:
            universe_schedule = {}
            for decision, frame in scores.groupby("decision_at"):
                week = mapping.get(decision) or (index[index > decision][0] if len(index[index > decision]) else None)
                names = [c for c in frame.cik10 if c in returns.columns]
                if week is not None and names:
                    universe_schedule[week] = names
            benchmark = run_book(universe_schedule, returns, args.cost_bps).loc[start:]
        else:
            benchmark = returns.mean(axis=1, skipna=True).loc[start:]

        realised = realised_ir(strategy, benchmark)
        predicted = (ic.get("mean_ic") * np.sqrt(br["breadth_effective_per_year"])
                     if ic.get("mean_ic") is not None else None)
        findings[name] = {
            "information_coefficient": ic,
            "breadth": br,
            "realised": realised,
            "predicted_information_ratio": float(predicted) if predicted is not None else None,
            "transfer_coefficient": (
                float(realised["realised_information_ratio"] / predicted)
                if predicted not in (None, 0.0) and np.isfinite(predicted) else None),
        }

    # How many independent strategies does this project actually have?
    frame = pd.DataFrame(paths).dropna()
    correlation = frame.corr().to_numpy()
    pr = _bets.participation_ratio(correlation)
    low, high = _bets.block_bootstrap_pr(frame, 2000, 13)
    cross = {
        "strategies": list(frame.columns),
        "weeks": int(len(frame)),
        "pairwise_correlations": {f"{a}|{b}": round(float(frame[a].corr(frame[b])), 4)
                                  for i, a in enumerate(frame.columns) for b in frame.columns[i + 1:]},
        "effective_independent_strategies": float(pr),
        "bootstrap_95_interval": [float(low), float(high)],
        "independence_null": float(_bets.independence_null(frame.shape[1], frame.shape[0])),
        "nominal_strategies": int(frame.shape[1]),
    }

    result = {
        "experiment": "breadth_accounting_v1",
        "framework": "Grinold & Kahn, IR = IC x sqrt(BR); TC reported as realised IR over predicted",
        "claims_no_alpha": True,
        "prices": PRICES,
        "cost_bps": args.cost_bps,
        "per_strategy": findings,
        "cross_strategy_breadth": cross,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
