"""Layer 5 — Backtest Realism Audit.

Tests whether a candidate strategy survives stricter execution
assumptions: cost sensitivity, rebalance delay, and turnover thresholds.

Liquidity / volume data is not present in this repo, so a flat slippage
proxy (basis-point grid) is used instead and the report says so explicitly.

Usage:
    python scripts/backtest_realism_audit.py [candidate_name]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


COST_GRID_BPS = [0, 5, 10, 25, 50]
DELAY_GRID_DAYS = [0, 1, 5]   # 5w = next monthly rebalance approx
TURNOVER_THRESHOLDS = [0.0, 0.005, 0.01]   # ignore trades smaller than these


def autoselect_candidate() -> str:
    """Use the most recent portfolio_version_returns file as candidate."""
    for prefix in ["improved_phasebb_", "improved_phaseaa_", "improved_phasez_", "improved_phasev_"]:
        files = sorted(roc.LAYER3_DIR.glob(f"portfolio_version_returns_{prefix}*.csv"))
        if files:
            return files[-1].stem.replace("portfolio_version_returns_", "")
    return roc.PHASEZ_Z1


def apply_cost(weights: pd.DataFrame, gross: pd.Series, halfspread: float) -> pd.Series:
    turn = roc.weekly_turnover(weights)
    cost = turn * halfspread
    return (gross - cost.reindex(gross.index).fillna(0.0))


def apply_delay(weights: pd.DataFrame, weekly_returns: pd.DataFrame, halfspread: float, lag_weeks: int) -> pd.Series:
    """Re-run portfolio with weights lagged by lag_weeks. Very simple model."""
    if lag_weeks <= 0:
        cols = [c for c in weights.columns if c in weekly_returns.columns]
        next_w = weekly_returns.shift(-1)
        common = weights.index.intersection(next_w.index)
        gross = (weights.loc[common, cols] * next_w.loc[common, cols].fillna(0.0)).sum(axis=1)
        return apply_cost(weights, gross, halfspread)
    lagged_w = weights.shift(lag_weeks).bfill()
    cols = [c for c in lagged_w.columns if c in weekly_returns.columns]
    next_w = weekly_returns.shift(-1)
    common = lagged_w.index.intersection(next_w.index)
    gross = (lagged_w.loc[common, cols] * next_w.loc[common, cols].fillna(0.0)).sum(axis=1)
    return apply_cost(lagged_w, gross, halfspread)


def apply_turnover_threshold(weights: pd.DataFrame, weekly_returns: pd.DataFrame, halfspread: float,
                             threshold: float) -> pd.Series:
    """Drop trades whose absolute weight change is below threshold; renormalise."""
    if threshold <= 0:
        cols = [c for c in weights.columns if c in weekly_returns.columns]
        next_w = weekly_returns.shift(-1)
        common = weights.index.intersection(next_w.index)
        gross = (weights.loc[common, cols] * next_w.loc[common, cols].fillna(0.0)).sum(axis=1)
        return apply_cost(weights, gross, halfspread)
    new_w = weights.copy()
    prev = new_w.iloc[0].copy()
    for i in range(1, len(new_w)):
        cur = new_w.iloc[i].copy()
        delta = cur - prev
        small = delta.abs() < threshold
        cur[small] = prev[small]
        # renormalise to sum to 1
        s = float(cur.sum())
        if s > 0:
            cur = cur / s
        new_w.iloc[i] = cur
        prev = cur
    cols = [c for c in new_w.columns if c in weekly_returns.columns]
    next_w = weekly_returns.shift(-1)
    common = new_w.index.intersection(next_w.index)
    gross = (new_w.loc[common, cols] * next_w.loc[common, cols].fillna(0.0)).sum(axis=1)
    return apply_cost(new_w, gross, halfspread)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate", nargs="?", default=None)
    parser.add_argument("--quick", action="store_true", help="Quick screen — restricts cost grid to {0,5,10}bps and skips delay/turnover sensitivities.")
    args = parser.parse_args()
    quick = args.quick
    if quick:
        global COST_GRID_BPS, DELAY_GRID_DAYS, TURNOVER_THRESHOLDS
        COST_GRID_BPS = [0, 5, 10]
        DELAY_GRID_DAYS = [0, 1]
        TURNOVER_THRESHOLDS = [0.0, 0.005]
    candidate = args.candidate or autoselect_candidate()
    baseline = roc.PRODUCTION_PIN
    print(f"Realism audit: candidate={candidate}, baseline={baseline}")

    cw = roc.load_portfolio_weights(candidate)
    pw = roc.load_portfolio_weights(baseline)
    weekly = roc.load_weekly_returns()

    if cw is None or pw is None:
        print("ERROR: missing weights file(s); aborting")
        sys.exit(1)

    out_lines = [f"# Backtest Realism Audit — {candidate}\n\n"]
    out_lines.append(f"**Production baseline:** `{baseline}`\n\n")
    out_lines.append(f"**Date range:** {cw.index.min().date()} → {cw.index.max().date()} ({len(cw)} weeks)\n\n")
    out_lines.append("**Cost convention baseline:** 5bp half-spread (project default).\n\n")
    out_lines.append("**Liquidity / volume data:** not available in this repo — slippage grid is used as proxy.\n\n")

    # ------------ Cost sensitivity ------------
    cost_rows = []
    for bps in COST_GRID_BPS:
        hs = bps / 10000.0 * 0.5
        cand_net = apply_cost(cw, _gross_from_w(cw, weekly), hs)
        prod_net = apply_cost(pw, _gross_from_w(pw, weekly), hs)
        common = cand_net.index.intersection(prod_net.index)
        cand_net = cand_net.loc[common]; prod_net = prod_net.loc[common]
        cm = roc.metric_block(cand_net); pm = roc.metric_block(prod_net)
        cost_rows.append({
            "halfspread_bps": bps,
            "cand_ann_return": cm["ann_return"],
            "prod_ann_return": pm["ann_return"],
            "delta_ann_return": cm["ann_return"] - pm["ann_return"],
            "cand_sharpe": cm["sharpe"],
            "prod_sharpe": pm["sharpe"],
            "delta_sharpe": cm["sharpe"] - pm["sharpe"],
            "cand_max_dd": cm["max_drawdown"],
            "cand_cvar5": cm["cvar_5"],
            "cand_calmar": cm["calmar"],
        })
    cost_df = pd.DataFrame(cost_rows)
    cost_csv = roc.ROOT / "data" / "research" / "backtest_realism" / f"{candidate}_cost_sensitivity.csv"
    cost_csv.parent.mkdir(parents=True, exist_ok=True)
    cost_df.to_csv(cost_csv, index=False)

    out_lines.append("## Cost Sensitivity\n\n")
    out_lines.append("Half-spread varied across {0, 5, 10, 25, 50} bps. (Project default = 5bp.)\n\n")
    out_lines.append("```\n" + cost_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    # ------------ Delay sensitivity ------------
    delay_rows = []
    for d_w in DELAY_GRID_DAYS:
        cand_net = apply_delay(cw, weekly, halfspread=roc.DEFAULT_HALFSPREAD, lag_weeks=d_w)
        prod_net = apply_delay(pw, weekly, halfspread=roc.DEFAULT_HALFSPREAD, lag_weeks=d_w)
        common = cand_net.index.intersection(prod_net.index)
        cand_net = cand_net.loc[common]; prod_net = prod_net.loc[common]
        cm = roc.metric_block(cand_net); pm = roc.metric_block(prod_net)
        delay_rows.append({
            "delay_weeks": d_w,
            "cand_ann_return": cm["ann_return"],
            "prod_ann_return": pm["ann_return"],
            "delta_ann_return": cm["ann_return"] - pm["ann_return"],
            "cand_sharpe": cm["sharpe"],
            "delta_sharpe": cm["sharpe"] - pm["sharpe"],
            "cand_max_dd": cm["max_drawdown"],
        })
    delay_df = pd.DataFrame(delay_rows)
    delay_csv = roc.ROOT / "data" / "research" / "backtest_realism" / f"{candidate}_rebalance_delay_sensitivity.csv"
    delay_df.to_csv(delay_csv, index=False)
    out_lines.append("## Rebalance Delay Sensitivity\n\n")
    out_lines.append("Weights lagged by {0, 1, 5} weeks (5w ≈ next monthly rebalance miss).\n\n")
    out_lines.append("```\n" + delay_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    # ------------ Turnover threshold sensitivity ------------
    turn_rows = []
    for thr in TURNOVER_THRESHOLDS:
        cand_net = apply_turnover_threshold(cw, weekly, halfspread=roc.DEFAULT_HALFSPREAD, threshold=thr)
        prod_net = apply_turnover_threshold(pw, weekly, halfspread=roc.DEFAULT_HALFSPREAD, threshold=thr)
        common = cand_net.index.intersection(prod_net.index)
        cand_net = cand_net.loc[common]; prod_net = prod_net.loc[common]
        cm = roc.metric_block(cand_net); pm = roc.metric_block(prod_net)
        turn_rows.append({
            "min_trade_size": thr,
            "cand_ann_return": cm["ann_return"],
            "prod_ann_return": pm["ann_return"],
            "delta_ann_return": cm["ann_return"] - pm["ann_return"],
            "cand_sharpe": cm["sharpe"],
            "delta_sharpe": cm["sharpe"] - pm["sharpe"],
        })
    turn_df = pd.DataFrame(turn_rows)
    turn_csv = roc.ROOT / "data" / "research" / "backtest_realism" / f"{candidate}_turnover_threshold_sensitivity.csv"
    turn_df.to_csv(turn_csv, index=False)
    out_lines.append("## Turnover-Threshold Sensitivity\n\n")
    out_lines.append("Trades smaller than {0, 0.5%, 1%} of book are dropped (no transaction cost incurred for them).\n\n")
    out_lines.append("```\n" + turn_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") + "\n```\n\n")

    # ------------ Verdict ------------
    out_lines.append("## Realism Verdict\n\n")
    # Does candidate still beat production at doubled cost (10bp half-spread)?
    base_idx = next((i for i, r in enumerate(cost_rows) if r["halfspread_bps"] == 5), None)
    doub_idx = next((i for i, r in enumerate(cost_rows) if r["halfspread_bps"] == 10), None)
    surv_doubled = False
    if base_idx is not None and doub_idx is not None:
        d_base = cost_rows[base_idx]["delta_ann_return"]
        d_doub = cost_rows[doub_idx]["delta_ann_return"]
        out_lines.append(f"- Δ ann return at 5bp (baseline): {d_base*100:+.2f}pp\n")
        out_lines.append(f"- Δ ann return at 10bp (doubled): {d_doub*100:+.2f}pp\n")
        surv_doubled = d_doub >= 0
    delay1 = next((r for r in delay_rows if r["delay_weeks"] == 1), None)
    if delay1:
        out_lines.append(f"- Δ ann return with 1-week delay: {delay1['delta_ann_return']*100:+.2f}pp\n")
    out_lines.append("\n")
    if surv_doubled:
        out_lines.append("**Verdict: candidate survives doubled-cost scenario.**\n\n")
    else:
        out_lines.append("**Verdict: candidate does NOT survive doubled-cost scenario.**\n\n")

    out_lines.append("## Warnings\n\n")
    out_lines.append("- ETF volume / liquidity data not present in repo; slippage modelled as flat half-spread.\n")
    out_lines.append("- 5-week rebalance delay is an extreme proxy for missing a monthly rebalance.\n")

    rep_path = roc.REPORTS_DIR / "backtest_realism" / f"{candidate}_realism_audit.md"
    rep_path.write_text("".join(out_lines))
    print(f"Wrote {rep_path}")
    print(f"Wrote {cost_csv}")
    print(f"Wrote {delay_csv}")
    print(f"Wrote {turn_csv}")


def _gross_from_w(weights: pd.DataFrame, weekly_returns: pd.DataFrame) -> pd.Series:
    cols = [c for c in weights.columns if c in weekly_returns.columns]
    next_w = weekly_returns.shift(-1)
    common = weights.index.intersection(next_w.index)
    return (weights.loc[common, cols] * next_w.loc[common, cols].fillna(0.0)).sum(axis=1)


if __name__ == "__main__":
    main()
