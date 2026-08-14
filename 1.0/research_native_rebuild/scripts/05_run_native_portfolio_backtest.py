"""
Sprint 5 — Native Portfolio Backtest
Constructs the shadow portfolio using all native components and computes full metrics.

Run ONLY after Sprints 1–4 complete and are reviewed.
Run: python3 research_native_rebuild/scripts/05_run_native_portfolio_backtest.py

Outputs:
  outputs/portfolio_backtest/shadow_weights.parquet
  outputs/portfolio_backtest/shadow_gross_returns.csv
  outputs/portfolio_backtest/shadow_net_returns.csv
  outputs/portfolio_backtest/shadow_turnover.csv
  outputs/portfolio_backtest/shadow_metrics.csv
  outputs/portfolio_backtest/shadow_state_metrics.csv

Critical invariants (violated = hard stop, not research-only):
  - All weights >= 0 (long-only)
  - Sum of weights == 1.0 at every date (no leverage)
  - Return convention: gross[t] = w[t] @ etf_rets[t+1] (1-week execution delay)
  - Net return: gross[t] - turnover[t] * 0.001 (10 bps per unit half-round-trip)
  - Holdout period data never used for calibration
  - Metrics computed with identical annualization convention as production

No performance claims made until Sprint 6 gates are checked.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import yaml

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "portfolio_backtest"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEV_END = pd.Timestamp("2024-04-12")
HOLDOUT_START = pd.Timestamp("2024-04-19")
COST_PER_TO = 0.001
ANNUALIZATION = 52
SQRT_ANN = np.sqrt(ANNUALIZATION)


# ─── Metric Helpers ──────────────────────────────────────────────────────────

def sharpe(returns):
    if returns.std() < 1e-10:
        return 0.0
    return returns.mean() / returns.std() * SQRT_ANN


def max_drawdown(returns):
    wealth = (1 + returns).cumprod()
    peak = wealth.cummax()
    dd = (wealth / peak - 1)
    return float(dd.min())


def cvar(returns, pct=0.05):
    threshold = returns.quantile(pct)
    tail = returns[returns <= threshold]
    return float(tail.mean()) if len(tail) > 0 else float(returns.min())


def annual_return(returns):
    return float(returns.mean() * ANNUALIZATION)


def annual_turnover(turnover_series):
    return float(turnover_series.mean() * ANNUALIZATION)


def compute_metrics(net_returns, turnover, label):
    return {
        "period": label,
        "sharpe": sharpe(net_returns),
        "annual_return": annual_return(net_returns),
        "max_drawdown": max_drawdown(net_returns),
        "cvar_5pct": cvar(net_returns),
        "annual_turnover": annual_turnover(turnover),
        "n_weeks": len(net_returns),
    }


# ─── Turnover Calculation ────────────────────────────────────────────────────

def compute_turnover(weights):
    """
    Half-round-trip turnover: sum(|w[t] - drift(w[t-1])|) / 2
    drift(w[t-1]) = w[t-1] * (1 + r[t]) / sum(w[t-1] * (1 + r[t]))
    Simplified: assume drift is approx w[t-1] (conservative — overestimates turnover slightly)
    """
    drift = weights.shift(1).fillna(method="bfill")
    to = (weights - drift).abs().sum(axis=1) / 2
    return to


# ─── Simple Sleeve-Based Weight Builder ─────────────────────────────────────
# This is a skeleton. Sprint 5 implementation must integrate:
# - Native state labels from Script 02
# - Signal weights from Script 03
# - Risk budgets from Script 04
# - Production sleeve CSV files (REUSE_EXISTING)
# The portfolio construction math (HRP / inverse-vol) is unchanged from production.

def build_shadow_weights(prices, native_states, signal_weights, state_risk_params):
    """
    Skeleton: constructs shadow weights using native states and risk budgets.
    Full implementation in Sprint 5 integrates production sleeve allocator.
    """
    n = len(prices)
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)

    # Fallback: equal weight across all ETFs (placeholder until sleeve integration)
    n_etf = len(prices.columns)
    weights[:] = 1.0 / n_etf

    # Normalize to ensure sum = 1 and all >= 0
    weights = weights.clip(lower=0)
    row_sums = weights.sum(axis=1)
    weights = weights.div(row_sums, axis=0)

    return weights


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  Sprint 5 — Native Portfolio Backtest")
    print("=" * 70 + "\n")

    # ── Load prices ──────────────────────────────────────────────────────────
    prices_path = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
    prices = pd.read_csv(prices_path, index_col=0, parse_dates=True)
    returns = prices.pct_change()
    fwd_returns = returns.shift(-1)  # forward return for execution delay
    print(f"  Prices: {prices.shape}")

    # ── Load native states ───────────────────────────────────────────────────
    states_path = ROOT / "research_native_rebuild" / "outputs" / "regime_engine" / "native_states.csv"
    if not states_path.exists():
        print("  ERROR: Native states not found. Run Script 02 first.")
        sys.exit(1)
    native_states = pd.read_csv(states_path, index_col=0, parse_dates=True)["native_state"]
    print(f"  Native states loaded: {native_states.nunique()} distinct states")

    # ── Load signal weights ──────────────────────────────────────────────────
    sw_path = ROOT / "research_native_rebuild" / "outputs" / "signal_weighting" / "signal_weights_by_state.csv"
    signal_weights = None
    if sw_path.exists():
        signal_weights = pd.read_csv(sw_path)
        print(f"  Signal weights loaded: {len(signal_weights)} rows")
    else:
        print("  WARNING: Signal weights not found. Run Script 03 first.")

    # ── Load risk params ─────────────────────────────────────────────────────
    rp_path = ROOT / "research_native_rebuild" / "outputs" / "risk_budgets" / "state_risk_params.yaml"
    if not rp_path.exists():
        print("  ERROR: Risk params not found. Run Script 04 first.")
        sys.exit(1)
    with open(rp_path) as f:
        rp_cfg = yaml.safe_load(f)
    state_risk_params = rp_cfg["state_risk_params"]
    print("  Risk params loaded")

    # ── Build shadow weights (Sprint 5 — skeleton) ───────────────────────────
    print("\n  Building shadow weights (skeleton — integrate sleeve allocator in Sprint 5)...")
    print("  NOTE: Full implementation requires integrating production sleeve CSV files.")
    weights = build_shadow_weights(prices, native_states, signal_weights, state_risk_params)

    # ── Constraint validation ────────────────────────────────────────────────
    min_w = float(weights.min().min())
    max_sum_dev = float((weights.sum(axis=1) - 1.0).abs().max())
    max_single = float(weights.max().max())

    print(f"\n  Constraint checks:")
    print(f"    min weight: {min_w:.6f} (must be >= 0) {'PASS' if min_w >= -1e-8 else 'FAIL'}")
    print(f"    max |sum-1|: {max_sum_dev:.8f} (must be < 1e-6) {'PASS' if max_sum_dev < 1e-6 else 'FAIL'}")
    print(f"    max single weight: {max_single:.4f} (must be <= 0.35) {'PASS' if max_single <= 0.35 else 'FAIL'}")

    if min_w < -1e-8:
        print("  HARD STOP: Negative weights found. Fix portfolio construction.")
        sys.exit(1)
    if max_sum_dev > 1e-6:
        print("  HARD STOP: Weights do not sum to 1. Fix normalization.")
        sys.exit(1)

    # ── Compute returns ───────────────────────────────────────────────────────
    # gross[t] = w[t] @ etf_rets[t+1] — 1-week execution delay
    aligned_fwd = fwd_returns.reindex(columns=weights.columns).fillna(0)
    gross_ret = (weights * aligned_fwd).sum(axis=1)
    gross_ret = gross_ret[:-1]  # last week has no forward return

    turnover = compute_turnover(weights).reindex(gross_ret.index)
    net_ret = gross_ret - turnover * COST_PER_TO

    # ── Compute metrics ───────────────────────────────────────────────────────
    dev_mask = net_ret.index <= DEV_END
    holdout_mask = net_ret.index >= HOLDOUT_START

    metrics_rows = [
        compute_metrics(net_ret, turnover, "full_period"),
        compute_metrics(net_ret[dev_mask], turnover[dev_mask], "dev_period"),
        compute_metrics(net_ret[holdout_mask], turnover[holdout_mask], "holdout_period"),
    ]
    metrics_df = pd.DataFrame(metrics_rows)

    # State-level metrics (dev only)
    state_metrics_rows = []
    for state in native_states.unique():
        state_mask = (native_states == state) & dev_mask
        if state_mask.sum() < 10:
            continue
        state_ret = net_ret[state_mask]
        state_to = turnover[state_mask]
        row = compute_metrics(state_ret, state_to, state)
        row["state"] = state
        row["dev_obs"] = int(state_mask.sum())
        state_metrics_rows.append(row)
    state_metrics_df = pd.DataFrame(state_metrics_rows)

    # ── Write outputs ─────────────────────────────────────────────────────────
    weights.to_parquet(OUT_DIR / "shadow_weights.parquet")
    gross_ret.to_frame("gross_return").to_csv(OUT_DIR / "shadow_gross_returns.csv")
    net_ret.to_frame("net_return").to_csv(OUT_DIR / "shadow_net_returns.csv")
    turnover.to_frame("turnover").to_csv(OUT_DIR / "shadow_turnover.csv")
    metrics_df.to_csv(OUT_DIR / "shadow_metrics.csv", index=False)
    state_metrics_df.to_csv(OUT_DIR / "shadow_state_metrics.csv", index=False)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n  Shadow portfolio metrics:")
    for _, row in metrics_df.iterrows():
        print(f"    [{row['period']}] Sharpe={row['sharpe']:.4f}  AnnRet={row['annual_return']:.4f}  "
              f"MaxDD={row['max_drawdown']:.4f}  TO={row['annual_turnover']:.3f}")

    print(f"\n  Metrics written to: {OUT_DIR}")
    print("\n  Sprint 5 complete (skeleton).")
    print("  IMPORTANT: Full implementation requires integrating production sleeve allocator.")
    print("  No performance claims until Sprint 6 gate evaluation.")


if __name__ == "__main__":
    main()
