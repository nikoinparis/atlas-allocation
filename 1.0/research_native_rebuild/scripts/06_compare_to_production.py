"""
Sprint 6 — Production Comparison + Gate Evaluation
Evaluates all promotion gates against the production pin and produces the final verdict.

Run ONLY after Sprint 5 completes.
Run: python3 research_native_rebuild/scripts/06_compare_to_production.py

Outputs:
  outputs/comparison/gate_evaluation.csv
  outputs/comparison/bootstrap_report.txt
  outputs/comparison/cost_sensitivity.csv
  outputs/comparison/extreme_year_exclusion.csv
  outputs/comparison/rolling_sharpe.csv
  outputs/comparison/final_verdict_sprint6.txt

Verdict options:
  PROMOTE_TO_PHASE_D_TEST  — all gates pass, human authorization required before any change
  RESEARCH-ONLY             — some gates pass, promising but not promotable
  DROP                      — fails basic gates or hard stop triggered

Human authorization required before any production change, regardless of verdict.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).parent.parent.parent
OUT_DIR = ROOT / "research_native_rebuild" / "outputs" / "comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEV_END = pd.Timestamp("2024-04-12")
HOLDOUT_START = pd.Timestamp("2024-04-19")
COST_PER_TO = 0.001
ANNUALIZATION = 52
SQRT_ANN = np.sqrt(ANNUALIZATION)

# Production pin benchmarks (from Sprint 0 design memo + Phase 10A evaluation)
PROD_SHARPE_FULL = 0.9542
PROD_SHARPE_HOLDOUT = 2.0479
PROD_ANNUAL_RETURN = 0.0718
PROD_MAX_DRAWDOWN = -0.1160
PROD_ANNUAL_TURNOVER = None     # to be filled from Sprint 0.5 equivalence audit


# ─── Gate Thresholds ─────────────────────────────────────────────────────────
GATES = {
    "G1_full_sharpe":      {"threshold": 0.01,  "direction": "delta_ge"},
    "G2_holdout_sharpe":   {"threshold": -0.02, "direction": "delta_ge"},
    "G3_annual_return":    {"threshold": 0.0,   "direction": "delta_ge"},
    "G4_max_drawdown":     {"threshold": 0.01,  "direction": "worsening_le"},
    "G5_cvar":             {"threshold": 0.005, "direction": "worsening_le"},
    "G6_turnover":         {"threshold": 0.03,  "direction": "delta_le"},
    "G7_2x_cost":          {"threshold": 0.0,   "direction": "delta_ge"},
    "G8_stressed_panic":   {"threshold": -0.02, "direction": "delta_ge"},
    "G9_recovery_fragile": {"threshold": -0.02, "direction": "delta_ge"},
    "G10_state_obs":       {"threshold": 30,    "direction": "min_ge"},
    "G11_not_extreme":     {"threshold": None,  "direction": "manual"},
    "G12_rolling_win":     {"threshold": 0.55,  "direction": "ge"},
    "G13_bootstrap":       {"threshold": 0.70,  "direction": "ge"},
}


# ─── Metric Helpers ──────────────────────────────────────────────────────────

def sharpe(returns):
    if len(returns) == 0 or returns.std() < 1e-10:
        return 0.0
    return float(returns.mean() / returns.std() * SQRT_ANN)


def max_drawdown(returns):
    if len(returns) == 0:
        return 0.0
    wealth = (1 + returns).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def cvar(returns, pct=0.05):
    if len(returns) == 0:
        return 0.0
    threshold = returns.quantile(pct)
    return float(returns[returns <= threshold].mean())


def annual_return(returns):
    return float(returns.mean() * ANNUALIZATION)


# ─── Bootstrap ────────────────────────────────────────────────────────────────

def block_bootstrap_sharpe(shadow_ret, prod_ret, n_draws=1000, block_size=52, seed=42):
    rng = np.random.default_rng(seed)
    n = len(shadow_ret)
    shadow_wins = 0
    for _ in range(n_draws):
        starts = rng.integers(0, n - block_size + 1, size=(n // block_size + 1))
        indices = np.concatenate([np.arange(s, min(s + block_size, n)) for s in starts])[:n]
        s_sh = sharpe(shadow_ret.iloc[indices])
        p_sh = sharpe(prod_ret.iloc[indices])
        if s_sh > p_sh:
            shadow_wins += 1
    return shadow_wins / n_draws


# ─── Gate Evaluation ─────────────────────────────────────────────────────────

def evaluate_gates(shadow_metrics, shadow_state_metrics, shadow_net, prod_net, turnover):
    results = []

    def _row(gate_id, desc, threshold, shadow_val, prod_val, delta, passes):
        return {
            "gate_id": gate_id,
            "gate_description": desc,
            "threshold": threshold,
            "shadow_value": shadow_val,
            "production_value": prod_val,
            "delta": delta,
            "pass": passes,
        }

    # G1 — full-period Sharpe
    shadow_sh = shadow_metrics.loc[shadow_metrics["period"] == "full_period", "sharpe"].values
    sh = float(shadow_sh[0]) if len(shadow_sh) > 0 else 0.0
    delta = sh - PROD_SHARPE_FULL
    results.append(_row("G1", "Full Sharpe improvement >= +0.01", 0.01, sh, PROD_SHARPE_FULL, delta, delta >= 0.01))

    # G2 — holdout Sharpe
    hsh = shadow_metrics.loc[shadow_metrics["period"] == "holdout_period", "sharpe"].values
    h = float(hsh[0]) if len(hsh) > 0 else 0.0
    delta2 = h - PROD_SHARPE_HOLDOUT
    results.append(_row("G2", "Holdout Sharpe not worse by > -0.02", -0.02, h, PROD_SHARPE_HOLDOUT, delta2, delta2 >= -0.02))

    # G3 — annual return
    ar_s = shadow_metrics.loc[shadow_metrics["period"] == "full_period", "annual_return"].values
    ar = float(ar_s[0]) if len(ar_s) > 0 else 0.0
    delta3 = ar - PROD_ANNUAL_RETURN
    results.append(_row("G3", "Annual return neutral or better", 0.0, ar, PROD_ANNUAL_RETURN, delta3, delta3 >= 0.0))

    # G4 — max drawdown
    mdd_s = shadow_metrics.loc[shadow_metrics["period"] == "full_period", "max_drawdown"].values
    mdd = float(mdd_s[0]) if len(mdd_s) > 0 else 0.0
    dd_worse = mdd - PROD_MAX_DRAWDOWN   # negative means more negative = worse
    results.append(_row("G4", "Max drawdown worsens by <= 1pp", -0.01, mdd, PROD_MAX_DRAWDOWN, dd_worse, dd_worse >= -0.01))

    # G5 — CVaR (placeholder)
    results.append(_row("G5", "CVaR 5% does not materially worsen", None, None, None, None, None))

    # G6 — turnover
    to_s = shadow_metrics.loc[shadow_metrics["period"] == "full_period", "annual_turnover"].values
    to = float(to_s[0]) if len(to_s) > 0 else 0.0
    prod_to = PROD_ANNUAL_TURNOVER or 0.0
    delta6 = to - prod_to
    results.append(_row("G6", "Annual turnover increase <= 0.03", 0.03, to, prod_to, delta6, delta6 <= 0.03))

    # G7 — 2x cost sensitivity (placeholder)
    results.append(_row("G7", "2x cost scenario does not erase improvement", None, None, None, None, None))

    # G8 — stressed_panic
    sp_row = shadow_state_metrics[shadow_state_metrics["state"] == "stressed_panic"] if "state" in shadow_state_metrics.columns else pd.DataFrame()
    sp_sh = float(sp_row["sharpe"].values[0]) if len(sp_row) > 0 else None
    results.append(_row("G8", "stressed_panic protection preserved", -0.02, sp_sh, None, None,
                        sp_sh is not None and sp_sh >= -0.02))

    # G9 — recovery_fragile (placeholder)
    results.append(_row("G9", "recovery_fragile not materially harmed", -0.02, None, None, None, None))

    # G10 — min state obs
    min_obs = shadow_state_metrics["dev_obs"].min() if "dev_obs" in shadow_state_metrics.columns and len(shadow_state_metrics) > 0 else None
    results.append(_row("G10", "No state < 30 dev observations", 30, min_obs, None, None,
                        min_obs is not None and min_obs >= 30))

    # G11-G13 placeholder
    for gid, desc in [("G11", "Improvement not driven by 2020/2024-2025 only"),
                      ("G12", "Rolling 104-week win rate >= 55%"),
                      ("G13", "Bootstrap P(shadow > prod) >= 70%")]:
        results.append(_row(gid, desc, None, None, None, None, None))

    return pd.DataFrame(results)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * 70)
    print("  Sprint 6 — Production Comparison + Gate Evaluation")
    print("=" * 70 + "\n")

    # Load shadow backtest outputs
    metrics_path = ROOT / "research_native_rebuild" / "outputs" / "portfolio_backtest" / "shadow_metrics.csv"
    state_metrics_path = ROOT / "research_native_rebuild" / "outputs" / "portfolio_backtest" / "shadow_state_metrics.csv"
    net_path = ROOT / "research_native_rebuild" / "outputs" / "portfolio_backtest" / "shadow_net_returns.csv"
    turnover_path = ROOT / "research_native_rebuild" / "outputs" / "portfolio_backtest" / "shadow_turnover.csv"

    for p in [metrics_path, state_metrics_path, net_path, turnover_path]:
        if not p.exists():
            print(f"  ERROR: {p.name} not found. Run Script 05 first.")
            sys.exit(1)

    shadow_metrics = pd.read_csv(metrics_path)
    shadow_state_metrics = pd.read_csv(state_metrics_path)
    shadow_net = pd.read_csv(net_path, index_col=0, parse_dates=True)["net_return"]
    turnover = pd.read_csv(turnover_path, index_col=0, parse_dates=True)["turnover"]

    # Placeholder production net returns (to be loaded from production portfolio artifact in Sprint 6)
    prod_net = shadow_net * 0.0  # placeholder — replace with production pin net returns

    # Gate evaluation
    print("  Evaluating promotion gates...")
    gate_df = evaluate_gates(shadow_metrics, shadow_state_metrics, shadow_net, prod_net, turnover)

    # Bootstrap (placeholder)
    bootstrap_p = None

    # Summary
    n_pass = gate_df["pass"].sum()
    n_fail = (gate_df["pass"] == False).sum()
    n_unknown = gate_df["pass"].isna().sum()

    # Verdict
    hard_stop_gates = {"G8", "G10"}
    hard_stop_fails = gate_df[(gate_df["gate_id"].isin(hard_stop_gates)) & (gate_df["pass"] == False)]

    if len(hard_stop_fails) > 0:
        verdict = "HARD_STOP"
    elif n_pass == len(gate_df):
        verdict = "PROMOTE_TO_PHASE_D_TEST"
    elif n_pass >= 8:
        verdict = "RESEARCH-ONLY (conditional — most gates pass)"
    else:
        verdict = "RESEARCH-ONLY"

    print(f"\n  Gates: {int(n_pass)} PASS / {int(n_fail)} FAIL / {int(n_unknown)} UNKNOWN")
    print(f"  VERDICT: {verdict}")
    if verdict == "PROMOTE_TO_PHASE_D_TEST":
        print("  >>> Human authorization required before any production change. <<<")

    # Write outputs
    gate_df.to_csv(OUT_DIR / "gate_evaluation.csv", index=False)

    verdict_lines = [
        "Sprint 6 — Final Verdict",
        "=" * 60,
        f"Shadow vs production pin: improved_frontier_phase5_fragility_guard",
        f"Production Sharpe: {PROD_SHARPE_FULL} (full) / {PROD_SHARPE_HOLDOUT} (holdout)",
        "",
        f"Gate results: {int(n_pass)} PASS / {int(n_fail)} FAIL / {int(n_unknown)} UNKNOWN / {len(gate_df)} total",
        "",
        "Gate details:",
    ]
    for _, row in gate_df.iterrows():
        status = "PASS" if row["pass"] is True else ("FAIL" if row["pass"] is False else "?")
        verdict_lines.append(f"  [{status}] {row['gate_id']}: {row['gate_description']}")
    verdict_lines += [
        "",
        f"VERDICT: {verdict}",
        "",
        "IMPORTANT: Human authorization required before any production change.",
        "Production pin remains: improved_frontier_phase5_fragility_guard",
    ]
    (OUT_DIR / "final_verdict_sprint6.txt").write_text("\n".join(verdict_lines))

    # Stub outputs for other artifacts
    (OUT_DIR / "bootstrap_report.txt").write_text("Bootstrap report — to be filled in Sprint 6")
    pd.DataFrame({"cost_multiple": [1.0, 2.0], "shadow_sharpe": [None, None], "prod_sharpe": [None, None]}).to_csv(
        OUT_DIR / "cost_sensitivity.csv", index=False)
    pd.DataFrame({"exclusion": ["remove_2020", "remove_2024_2025"], "shadow_sharpe": [None, None], "g1_passes": [None, None]}).to_csv(
        OUT_DIR / "extreme_year_exclusion.csv", index=False)

    print(f"\n  Verdict written to: {OUT_DIR / 'final_verdict_sprint6.txt'}")
    print("  Sprint 6 complete.")


if __name__ == "__main__":
    main()
