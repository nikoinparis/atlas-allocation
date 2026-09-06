#!/usr/bin/env python3
"""Measure what breadth a multi-asset universe supplies, before building anything on it.

Step 245 measured the equity construction at 8.5 effective bets per year and an
IR ceiling below 0.1, and the arithmetic said reaching an IR of 0.25 needs 91
independent bets a year.  The owner chose to pursue new asset classes.

The discipline that Step 245 asked for is to measure breadth *first*.  This
project's habit is to build a strategy, find a return, and never ask whether the
return could have come from the number of independent bets the design supports.
Two cross-asset strategies have already been built on exactly this data and both
were rejected.  Neither measured breadth.  This measures breadth and builds
nothing.

Breadth is capacity, not return.  A universe that supplies 300 independent bets a
year is not thereby profitable; it is merely capable of expressing skill that a
universe supplying 8 cannot.  Nothing here is evidence that any cross-asset
strategy makes money.

Nothing is authorised to trade, and nothing frozen is modified.
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

REGISTRY = ROOT / "config/multi_asset_breadth_registry_v1.json"

ASSET_CLASSES = {
    "us_equity_broad": ["SPY", "QQQ", "IWM", "VTV", "VUG"],
    "us_equity_sector": ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"],
    "international_equity": ["EFA", "EEM", "EWJ", "VEA", "VWO"],
    "government_bonds": ["TLT", "IEF", "SHY", "TIP", "BIL"],
    "credit": ["LQD", "HYG", "MBB"],
    "commodities": ["GLD", "IAU", "SLV", "USO", "DBA", "PDBC"],
    "real_assets_fx": ["VNQ", "UUP"],
}

REGIMES = {
    "full_2005_2026": (None, None),
    "gfc_2008_2009": ("2008-01-01", "2009-12-31"),
    "covid_2020": ("2020-01-01", "2020-12-31"),
    "recent_104w": ("__tail__", 104),
    "recent_52w": ("__tail__", 52),
}

TREND_LOOKBACK_WEEKS = 12


def effective_assets(returns: pd.DataFrame) -> dict[str, float]:
    usable = returns.dropna(axis=1, thresh=max(26, int(0.5 * len(returns))))
    usable = usable.dropna()
    if usable.shape[1] < 3 or usable.shape[0] < 26:
        return {"assets": int(usable.shape[1]), "weeks": int(usable.shape[0]), "effective": None}
    correlation = usable.corr().to_numpy()
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    pr = _bets.participation_ratio(correlation)
    return {
        "assets": int(usable.shape[1]),
        "weeks": int(usable.shape[0]),
        "effective": float(pr),
        "independence_null": float(_bets.independence_null(usable.shape[1], usable.shape[0])),
        "share_of_nominal": float(pr / usable.shape[1]),
        "median_abs_pairwise_correlation": float(
            np.median(np.abs(correlation[np.triu_indices_from(correlation, k=1)]))),
    }


def signal_persistence(returns: pd.DataFrame, every: int) -> float:
    """How much of a trend book carries over from one rebalance to the next.

    A signal that says the same thing next quarter has not placed a new bet, and
    this is the term that destroyed 61 to 71 percent of the equity book's breadth
    in Step 245. Estimated here from the sign of a 12-week trend, sampled at the
    rebalance frequency, which is the cheapest honest proxy.
    """
    trend = (1.0 + returns.fillna(0.0)).rolling(TREND_LOOKBACK_WEEKS).apply(np.prod, raw=True) - 1.0
    sampled = np.sign(trend.iloc[::every]).dropna(how="all")
    if len(sampled) < 3:
        return 1.0
    agreements = []
    for earlier, later in zip(sampled.index, sampled.index[1:]):
        pair = pd.concat([sampled.loc[earlier], sampled.loc[later]], axis=1).dropna()
        if pair.empty:
            continue
        agreements.append(float((pair.iloc[:, 0] == pair.iloc[:, 1]).mean()))
    return float(np.mean(agreements)) if agreements else 1.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/multi_asset_breadth_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    prices = pd.read_csv(ROOT / registry["universe"], index_col=0, parse_dates=True)
    prices = prices.apply(pd.to_numeric, errors="coerce")
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan).iloc[1:]

    per_regime = {}
    for name, window in REGIMES.items():
        if window[0] == "__tail__":
            piece = returns.tail(int(window[1]))
        elif window[0] is None:
            piece = returns
        else:
            piece = returns.loc[(returns.index >= window[0]) & (returns.index <= window[1])]
        per_regime[name] = effective_assets(piece)

    per_class = {}
    for label, tickers in ASSET_CLASSES.items():
        present = [t for t in tickers if t in returns.columns]
        per_class[label] = effective_assets(returns[present]) if len(present) >= 3 else {
            "assets": len(present), "effective": None, "note": "fewer than three assets"}

    # What does one asset from each class buy, versus everything?
    representatives = [tickers[0] for tickers in ASSET_CLASSES.values() if tickers[0] in returns.columns]
    one_per_class = effective_assets(returns[representatives])

    full = per_regime["full_2005_2026"]
    projections = []
    for every in registry["method"]["rebalance_frequencies_projected"]:
        rebalances = 52 / every
        persistence = signal_persistence(returns, every)
        independent_share = 1.0 - persistence
        breadth = (full["effective"] or 0.0) * rebalances * max(independent_share, 1e-6)
        projections.append({
            "rebalance_every_weeks": every,
            "rebalances_per_year": rebalances,
            "trend_signal_persistence": persistence,
            "independent_share_of_each_rebalance": independent_share,
            "projected_breadth_per_year": breadth,
            "clears_ir_0.25_requirement_of_91": bool(breadth >= 91),
            "clears_ir_0.50_requirement_of_362": bool(breadth >= 362),
        })

    baseline = registry["comparison_baseline"]
    best = max(projections, key=lambda p: p["projected_breadth_per_year"])
    if (full["effective"] or 0) < 8:
        verdict = "refuted: the multi-asset universe supplies no more independence than the equity book"
    elif best["projected_breadth_per_year"] < 91:
        verdict = "insufficient: a real improvement that still cannot reach an IR of 0.25 at the measured IC"
    else:
        verdict = "premise holds: projected breadth clears the IR 0.25 requirement, subject to every existing gate"

    result = {
        "experiment": "multi_asset_breadth_measurement_v1",
        "declared_trials": 0,
        "builds_no_strategy": True,
        "universe": registry["universe"],
        "assets": int(returns.shape[1]),
        "weeks": int(returns.shape[0]),
        "effective_independent_assets_by_regime": per_regime,
        "effective_independent_assets_by_class": per_class,
        "one_representative_per_class": one_per_class,
        "breadth_projections": projections,
        "comparison_baseline": baseline,
        "verdict_against_predeclared_interpretation": verdict,
        "caveat": "breadth is capacity, not return; two cross-asset strategies on this data have already been rejected",
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

    print(f"universe: {result['assets']} assets, {result['weeks']} weeks\n")
    print(f"{'regime':<20}{'assets':>8}{'effective':>11}{'share':>8}{'null':>8}{'med |corr|':>12}")
    for name, data in per_regime.items():
        if data.get("effective") is None:
            print(f"{name:<20}{data['assets']:>8}{'n/a':>11}"); continue
        print(f"{name:<20}{data['assets']:>8}{data['effective']:>11.2f}{data['share_of_nominal']:>8.2f}"
              f"{data['independence_null']:>8.2f}{data['median_abs_pairwise_correlation']:>12.3f}")
    print(f"\n{'asset class':<24}{'assets':>8}{'effective':>11}")
    for label, data in per_class.items():
        e = data.get("effective")
        print(f"{label:<24}{data['assets']:>8}{(f'{e:.2f}' if e else 'n/a'):>11}")
    print(f"\none representative per class ({len(representatives)} assets): "
          f"effective {one_per_class.get('effective'):.2f}" if one_per_class.get("effective") else "")
    print(f"\n{'rebalance':<12}{'per year':>10}{'persistence':>13}{'independent':>13}{'breadth/yr':>12}{'>=91':>7}{'>=362':>7}")
    for p in projections:
        print(f"every {p['rebalance_every_weeks']:>2}w{'':<4}{p['rebalances_per_year']:>10.0f}"
              f"{p['trend_signal_persistence']:>13.3f}{p['independent_share_of_each_rebalance']:>13.3f}"
              f"{p['projected_breadth_per_year']:>12.1f}{str(p['clears_ir_0.25_requirement_of_91']):>7}"
              f"{str(p['clears_ir_0.50_requirement_of_362']):>7}")
    print(f"\nequity book baseline: {baseline['equity_book_effective_breadth_per_year']} bets/year "
          f"from {baseline['equity_book_effective_names']} effective names")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
