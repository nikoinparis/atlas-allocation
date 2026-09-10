#!/usr/bin/env python3
"""Does the market-neutral structure rescue a weak but real signal?

Pre-registered in config/long_short_cash_conversion_registry_v1.json.

Step 293 built the first long-short book here and it cleared the orthogonality
gate by construction -- the gate fourteen families died on before they ever
reached a skill test -- but the signal inside it had no skill. This runs the
reverse case. Cash conversion is the only dashboard signal that survived Step
289's out-of-sample test with both a positive excess over its own universe
(+1.08pp) and a Sharpe above it (0.698 vs 0.673). Weak, but the only candidate
for "real".

The long leg is the SAME top twenty the frozen long-only book holds, so the
experiment isolates exactly what the short leg adds. Gross exposure is 100%
(50% long, 50% short) rather than the 200% a conventional dollar-neutral book
carries, so the comparison to the long-only book is like for like.

Gates 1 and 4 are close to guaranteed by construction and prove only that the
arithmetic works. **Gate 3 is the hypothesis**: the long-short book must beat the
long-only book of the identical signal, out of sample. If the structure does not
improve the same signal, it has bought cost and complexity for nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.systematic_trader.return_conventions import load_aligned
import build_dashboard_signals_out_of_sample_v1 as oos

REGISTRY = ROOT / "config/long_short_cash_conversion_registry_v1.json"
ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/long_short_cash_conversion_v1"
VALUATION = "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
GROWTH = "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"
SPEC = oos.SIGNALS["cash_conversion_breadth20"]


def simulate(schedule: dict, returns: pd.DataFrame, cost_bps: float,
             borrow_bps: float) -> pd.Series:
    """Price a dated book of signed weights, charging borrow on net short exposure."""
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    rows, started = [], min(schedule) if schedule else None
    for week in returns.index:
        if started is None or week < started:
            continue
        cost = 0.0
        if week in schedule:
            target = pd.Series(0.0, index=returns.columns, dtype=float)
            for name, weight in schedule[week].items():
                if name in target.index:
                    target[name] = weight
            cost = float((target - holdings).abs().sum()) / 2.0 * cost_bps / 10_000.0
            holdings = target
        row = returns.loc[week].fillna(0.0)
        borrow = float(holdings[holdings < 0].abs().sum()) * borrow_bps / 10_000.0 / 52.0
        rows.append((week, float((holdings * row).sum()) - cost - borrow))
        # Long and short legs drift apart; the book is only reset at a rebalance.
        holdings = holdings * (1.0 + row)
    return pd.Series(dict(rows)).sort_index()


def build_schedules(facts: pd.DataFrame, returns: pd.DataFrame,
                    decisions: pd.DatetimeIndex, breadth: int):
    """Long-short and long-only schedules from the identical score, same dates."""
    long_short, long_only, coverage = {}, {}, []
    for decision in decisions:
        known = facts[facts.filed < decision]          # point in time
        if known.empty:
            continue
        latest = known.sort_values("filed").groupby("cik10").last()
        latest = latest[latest.index.isin(returns.columns)]
        if len(latest) < breadth * 4:
            continue
        scored = oos.score(latest, SPEC).dropna()
        if len(scored) < breadth * 2:
            continue
        execution = returns.index[returns.index > decision]
        if not len(execution):
            continue
        week = execution[0]
        top = list(scored.nlargest(breadth).index)
        bottom = list(scored.nsmallest(breadth).index)
        long_short[week] = ({n: 0.5 / breadth for n in top}
                            | {n: -0.5 / breadth for n in bottom})
        long_only[week] = {n: 1.0 / breadth for n in top}
        coverage.append(len(scored))
    return long_short, long_only, coverage


def assess(book: pd.Series, long_only: pd.Series, spy: pd.Series,
           valuation: pd.Series, growth: pd.Series, label: str) -> dict:
    m, mo = oos.metrics(book), oos.metrics(long_only)
    joined = pd.concat({"b": book, "v": valuation, "g": growth}, axis=1).dropna()
    cv = float(joined.b.corr(joined.v)) if len(joined) > 30 else float("nan")
    cg = float(joined.b.corr(joined.g)) if len(joined) > 30 else float("nan")
    bj = pd.concat({"b": book, "m": spy}, axis=1).dropna()
    beta, intercept = np.polyfit(bj.m, bj.b, 1)
    residual = bj.b - (beta * bj.m + intercept)
    r2 = 1.0 - residual.var() / bj.b.var()
    print(f"{label}  ({len(book)} weeks)")
    print(f"  long-short  CAGR {m['cagr']:7.2%}  Sharpe {m['sharpe']:6.3f}  "
          f"vol {m['volatility']:5.1%}  maxDD {m['max_drawdown']:7.2%}")
    print(f"  long-only   CAGR {mo['cagr']:7.2%}  Sharpe {mo['sharpe']:6.3f}  "
          f"vol {mo['volatility']:5.1%}  maxDD {mo['max_drawdown']:7.2%}")
    print(f"  market beta {beta:+.3f} R2 {r2:.3f} | corr vs valuation {cv:+.3f} vs growth {cg:+.3f}")
    print(f"  structure beats its own long-only twin on Sharpe: "
          f"{'YES' if m['sharpe'] > mo['sharpe'] else 'NO'}\n")
    return {"long_short": m, "long_only": mo, "market_beta": float(beta), "market_r2": float(r2),
            "correlation_vs_valuation": cv, "correlation_vs_growth": cg,
            "beats_long_only": bool(m["sharpe"] > mo["sharpe"]), "weeks": int(len(book))}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    cfg = registry["declared_configurations"]
    breadth, cost, borrow = cfg["breadth_per_leg"][0], cfg["cost_bps_per_leg"][0], cfg["annual_borrow_bps"][0]

    prices = oos.load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    etf = pd.read_csv(ETF, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    etf.index = pd.to_datetime(etf.index, utc=True)
    spy = ((etf / etf.shift(1) - 1.0)["SPY"]).dropna()
    valuation, growth = load_aligned(VALUATION, root=ROOT), load_aligned(GROWTH, root=ROOT)

    facts = oos.add_features(oos.build_facts())
    facts = facts[facts.cik10.isin(prices.columns)]
    print(f"FSDS facts: {len(facts):,} filings, {facts.cik10.nunique():,} issuers, "
          f"{facts.filed.min().date()} -> {facts.filed.max().date()}\n")

    results, paths = {}, {}
    windows = {"out_of_sample_2013_2022": (pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC"), "2023-01-01"),
               "in_sample_2023_2026": (pd.date_range("2023-04-01", "2026-07-01", freq="QS", tz="UTC"), None)}
    for label, (decisions, cutoff) in windows.items():
        ls_sched, lo_sched, coverage = build_schedules(facts, returns, decisions, breadth)
        if len(ls_sched) < 8:
            print(f"{label}: INCONCLUSIVE, only {len(ls_sched)} decisions built\n")
            results[label] = {"inconclusive": len(ls_sched)}
            continue
        ls = simulate(ls_sched, returns, cost, borrow)
        lo = simulate(lo_sched, returns, cost, 0.0)
        if cutoff:
            ls, lo = ls.loc[:cutoff], lo.loc[:cutoff]
        results[label] = assess(ls, lo, spy, valuation, growth, label)
        results[label]["decisions"] = len(ls_sched)
        results[label]["median_scored"] = int(np.median(coverage))
        paths[label] = ls

    oos_key = "out_of_sample_2013_2022"
    decisive = results.get(oos_key, {})
    if "inconclusive" in decisive or not decisive:
        print("VERDICT: INCONCLUSIVE out of sample; no gate can be judged")
        return 1
    # Gate 1 is UNTESTABLE on the out-of-sample window: the valuation and growth
    # books only exist from 2023, so there is no overlap with 2013-2022 and the
    # correlation is NaN. Reporting NaN as a failure would claim a comparison was
    # made and lost when it could not be made at all -- the same distinction
    # Step 286 had to draw for its routine leg. Judge gate 1 where overlap exists.
    overlap = results.get("in_sample_2023_2026", {})
    gate_1_testable = bool(np.isfinite(decisive["correlation_vs_valuation"]))
    if gate_1_testable:
        gate_1 = bool(abs(decisive["correlation_vs_valuation"]) < 0.30
                      and abs(decisive["correlation_vs_growth"]) < 0.30)
        gate_1_source = "out of sample"
    elif overlap and np.isfinite(overlap.get("correlation_vs_valuation", float("nan"))):
        gate_1 = bool(abs(overlap["correlation_vs_valuation"]) < 0.30
                      and abs(overlap["correlation_vs_growth"]) < 0.30)
        gate_1_source = "in sample only, no pre-2023 overlap exists"
    else:
        gate_1, gate_1_source = False, "untestable"
    gate_2 = bool(decisive["long_short"]["sharpe"] >= 1.0)
    gate_3 = bool(decisive["beats_long_only"])
    gate_4 = bool(abs(decisive["market_beta"]) < 0.30)
    passed = gate_1 and gate_2 and gate_3 and gate_4
    print("gates judged on the OUT-OF-SAMPLE window only")
    print(f"gate 1 orthogonality              {'PASS' if gate_1 else 'FAIL'}  ({gate_1_source})")
    print(f"gate 2 standalone Sharpe >= 1.0   {'PASS' if gate_2 else 'FAIL'}")
    print(f"gate 3 beats its long-only twin   {'PASS' if gate_3 else 'FAIL'}  <- the hypothesis")
    print(f"gate 4 truly market neutral       {'PASS' if gate_4 else 'FAIL'}")
    print(f"\nVERDICT: {'ALL FOUR GATES PASS -- candidate' if passed else 'did not clear all four declared gates'}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for label, path in paths.items():
        path.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / f"path__{label}__50bps.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "breadth_per_leg": breadth, "cost_bps_per_leg": cost, "annual_borrow_bps": borrow,
        "gross_exposure": "100% (50 long / 50 short)",
        "results": results,
        "gate_1_orthogonality": gate_1, "gate_1_judged_on": gate_1_source, "gate_2_standalone_skill": gate_2,
        "gate_3_beats_long_only": gate_3, "gate_4_market_neutral": gate_4,
        "all_gates_passed": passed, "gates_judged_on": oos_key, "trials_declared": 1,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
