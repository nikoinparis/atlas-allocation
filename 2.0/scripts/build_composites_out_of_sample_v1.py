#!/usr/bin/env python3
"""Test the two composite strategies out of sample, from their own component rules.

Step 289 tested the four fundamental signals and none survived. Both composites
on the dashboard are built from those signals plus an allocator, so the question
left is whether the allocators rescue them -- a composite can beat its parts if
the switching rule adds something, and that is worth measuring rather than
assuming either way.

Reconstructed from the frozen rules, not approximated by blending returns:

  sector ensemble stock leg   0.9 cash conversion + 0.1 balance sheet quality at
                              the SCORE level, which is what mix_targets does --
                              blending two books' returns is a different portfolio
                              from blending their scores and picking once.

  residual composite          leader_share x (0.4 growth + 0.6 ETF) + cc_share x
                              cash conversion, with cc_share set by the frozen
                              11-week trend rule: switch to cash conversion when
                              its trailing 11-week total beats the leader's AND is
                              positive. The ETF leg is priced from
                              frozen_weights.csv, which spans 2005-2026 and so
                              covers this window without extrapolation.

Same universe restriction and the same book-against-its-own-universe comparison
as Step 289.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import build_dashboard_signals_out_of_sample_v1 as base

ETF_WEIGHTS = ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
ETF_PANEL = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/composites_out_of_sample_v1"
CASH = "cash::USD"
GROWTH_SHARE_OF_LEADER = 0.4
OVERLAY_LOOKBACK = 11
OVERLAY_ALLOCATION = 0.5
IN_SAMPLE = {"sector_ensemble_stock_leg": 0.10, "residual_composite": 0.10}


def etf_path(weeks: pd.DatetimeIndex) -> pd.Series:
    prices = pd.read_csv(ETF_PANEL, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    weights = pd.read_csv(ETF_WEIGHTS, index_col=0, parse_dates=True)
    weights.index = pd.to_datetime(weights.index, utc=True)
    weights = weights.drop(columns=[CASH], errors="ignore")
    rows = []
    for week in weeks:
        prior = weights.index[weights.index <= week]
        if not len(prior) or week not in returns.index:
            continue
        row = weights.loc[prior[-1]]
        held = [c for c in row.index if c in returns.columns and abs(row[c]) > 1e-12]
        if not held:
            rows.append((week, 0.0))
            continue
        realized = returns.loc[week, held].fillna(0.0)
        # Uninvested weight sits in cash at zero, which is what the frozen book does.
        rows.append((week, float((row[held] * realized).sum())))
    return pd.Series(dict(rows)).sort_index()


def build_book(facts, returns, decisions, spec_weights, breadth):
    """Score-level mix, then pick once -- not a blend of two finished books."""
    schedule, universe, coverage = {}, {}, []
    for decision in decisions:
        known = facts[facts.filed < decision]
        if known.empty:
            continue
        latest = known.sort_values("filed").groupby("cik10").last()
        latest = latest[latest.index.isin(returns.columns)]
        if len(latest) < breadth * 2:
            continue
        blended = None
        for name, weight in spec_weights.items():
            scored = base.score(latest, base.SIGNALS[name])
            if blended is None:
                blended = weight * scored
            else:
                blended = blended.add(weight * scored, fill_value=np.nan)
        blended = blended.dropna()
        if len(blended) < breadth:
            continue
        execution = returns.index[returns.index > decision]
        if not len(execution):
            continue
        week = execution[0]
        schedule[week] = list(blended.nlargest(breadth).index)
        universe[week] = list(blended.index)
        coverage.append(len(blended))
    return schedule, universe, coverage


def report(name, book, universe, in_sample):
    joined = pd.concat({"book": book, "universe": universe}, axis=1).dropna().loc[:"2023-01-01"]
    bm, um = base.metrics(joined.book), base.metrics(joined.universe)
    excess = bm["cagr"] - um["cagr"]
    retained = excess / in_sample
    beats = bm["sharpe"] > um["sharpe"]
    supports = bool(excess > 0 and retained >= 0.25 and beats)
    print(f"{name}  ({len(joined)} weeks)")
    print(f"  book      CAGR {bm['cagr']:7.2%}  Sharpe {bm['sharpe']:6.3f}  maxDD {bm['max_drawdown']:7.2%}")
    print(f"  universe  CAGR {um['cagr']:7.2%}  Sharpe {um['sharpe']:6.3f}  maxDD {um['max_drawdown']:7.2%}")
    print(f"  EXCESS {excess:+.2%}   in-sample ~{in_sample:+.0%}   retained {retained:.0%}   "
          f"Sharpe beats universe: {beats}")
    print(f"  -> {'SUPPORTS' if supports else 'REFUTES'}\n")
    return {"book": bm, "universe": um, "excess_cagr": excess, "retained": retained,
            "book_sharpe_beats_universe": beats, "supports": supports, "weeks": len(joined)}, joined


def main() -> int:
    prices = base.load_prices()
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    facts = base.add_features(base.build_facts())
    facts = facts[facts.cik10.isin(prices.columns)]
    decisions = pd.date_range("2013-04-01", "2022-10-01", freq="QS", tz="UTC")
    results, paths = {}, {}

    # 1. Sector ensemble stock leg: 0.9 cash conversion + 0.1 balance sheet quality.
    schedule, universe, coverage = build_book(
        facts, returns, decisions,
        {"cash_conversion_breadth20": 0.9, "balance_sheet_quality": 0.1}, 20)
    if len(schedule) >= 20:
        book = base.simulate(schedule, returns)
        uni = base.simulate(universe, returns)
        results["sector_ensemble_stock_leg"], joined = report(
            "sector_ensemble_stock_leg", book, uni, IN_SAMPLE["sector_ensemble_stock_leg"])
        results["sector_ensemble_stock_leg"]["decisions"] = len(schedule)
        results["sector_ensemble_stock_leg"]["median_scored"] = int(np.median(coverage))
        paths["sector_ensemble_stock_leg"] = joined.book

    # 2. Residual composite: leader (0.4 growth + 0.6 ETF) with a cash-conversion overlay.
    g_sched, g_uni, _ = build_book(facts, returns, decisions, {"growth_top5": 1.0}, 5)
    c_sched, c_uni, _ = build_book(facts, returns, decisions, {"cash_conversion_breadth20": 1.0}, 20)
    growth = base.simulate(g_sched, returns)
    cashconv = base.simulate(c_sched, returns)
    etf = etf_path(returns.index)
    frame = pd.concat({"g": growth, "c": cashconv, "e": etf}, axis=1).dropna()
    leader = GROWTH_SHARE_OF_LEADER * frame.g + (1 - GROWTH_SHARE_OF_LEADER) * frame.e

    # Frozen overlay rule, applied causally: the trailing 11-week totals use only
    # weeks strictly before the decision, then set the following week's allocation.
    trend_leader = leader.rolling(OVERLAY_LOOKBACK).sum().shift(1)
    trend_cash = frame.c.rolling(OVERLAY_LOOKBACK).sum().shift(1)
    active = (trend_cash > trend_leader) & (trend_cash > 0)
    cc_share = active.astype(float) * OVERLAY_ALLOCATION
    composite = (1 - cc_share) * leader + cc_share * frame.c

    uni_growth = base.simulate(g_uni, returns)
    uni_cash = base.simulate(c_uni, returns)
    uframe = pd.concat({"g": uni_growth, "c": uni_cash, "e": etf}, axis=1).dropna()
    uleader = GROWTH_SHARE_OF_LEADER * uframe.g + (1 - GROWTH_SHARE_OF_LEADER) * uframe.e
    ushare = cc_share.reindex(uframe.index).fillna(0.0)
    composite_universe = (1 - ushare) * uleader + ushare * uframe.c

    print(f"overlay active in {active.mean():.1%} of weeks\n")
    results["residual_composite"], joined = report(
        "residual_composite", composite.dropna(), composite_universe.dropna(),
        IN_SAMPLE["residual_composite"])
    results["residual_composite"]["overlay_active_share"] = float(active.mean())
    paths["residual_composite"] = joined.book

    supported = [k for k, v in results.items() if v.get("supports")]
    print(f"composites whose edge survives out of sample: {len(supported)} of {len(results)}"
          + (f" -- {supported}" if supported else ""))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, path in paths.items():
        path.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / f"path__{name}__50bps.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "window": "2013-2022", "reconstructed_from_frozen_rules": True,
        "results": results, "supported": supported,
        "note": ("Composites rebuilt at the score and allocator level from their own frozen "
                 "rules, not by blending finished return series."),
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
