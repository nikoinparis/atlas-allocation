"""Phase HH — Refined-state regime-confidence FEATURE (not portfolio multiplier).

Phases DD/EE/FF/GG closed the direct hint→portfolio-multiplier consumption
branch. Phase HH tests whether Phase CC's refined_state can improve the
existing Phase 2B regime-confidence logic AS A FEATURE — i.e., it nudges the
existing regime confidence score before portfolio construction, never the
sleeve weights or ETF weights directly.

Three candidates:

  HH1 = improved_phasehh_refined_confidence_additive
        phase2b_mode='regime_confidence_boost_refined_v1'
        Adds ±0.02 to regime_multiplier inside apply_overlays_custom based on
        refined_state (healthy +0.02; deteriorating -0.02; recovery_confirmed
        +0.01). Same production allocator pipeline; only the existing
        regime confidence score is nudged. Causal: refined_state was built
        walk-forward.

  HH2 = improved_phasehh_refined_confidence_smoothing
        phase2b_mode='regime_confidence_boost_refined_v2'
        Scales dynamic_speed by 0.85 ONLY in neutral_deteriorating weeks.
        No effect in healthy / calm / recovery_confirmed. Slows re-risking
        without imposing defensive drag in healthy states. No new threshold
        — reuses the existing dynamic_speed mechanism.

  HH3 = phase_hh_feature_ablation (REPORT ONLY — no portfolio version)
        Quantitative test: does augmenting p_regime_confidence with a
        refined_state indicator improve forward-stress prediction quality
        (Brier score) over p_regime_confidence alone? Strictly causal.

The HH1/HH2 candidate returns/weights are produced through the same
build_improvement_artifacts.py production pipeline as the production pin.
The HH3 ablation is a separate, report-only diagnostic that does not
touch any portfolio.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
HH1_NAME = "improved_phasehh_refined_confidence_additive"
HH2_NAME = "improved_phasehh_refined_confidence_smoothing"
PHASE_HH_PORTFOLIO_CANDIDATES = [HH1_NAME, HH2_NAME]


# ----------------------------------------------------------------------
# subprocess invocation of build_improvement_artifacts.py (production path)
# ----------------------------------------------------------------------

def run_production_path(rebuild_production: bool = True) -> None:
    targets = list(PHASE_HH_PORTFOLIO_CANDIDATES)
    if rebuild_production:
        targets.append(PRODUCTION)
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    print(f"Invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=1800)
    print("--- subprocess stdout (last 30 lines) ---")
    for line in (res.stdout or "").splitlines()[-30:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 40 lines) ---")
        for line in (res.stderr or "").splitlines()[-40:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


# ----------------------------------------------------------------------
# data loading
# ----------------------------------------------------------------------

def load_refined_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history_refined.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_phase2b_predictions() -> pd.DataFrame:
    p = roc.LAYER2B_DIR / "phase2b_meta_predictions.csv"
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


# ----------------------------------------------------------------------
# evaluation helpers
# ----------------------------------------------------------------------

def state_breakdown(net: pd.Series, prod_net: pd.Series, refined: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("hh"), prod_net.rename("prod")], axis=1).join(
        refined[["market_state", "refined_state"]], how="inner"
    ).dropna()
    rows = []
    for col in ["market_state", "refined_state"]:
        for s, sub in df.groupby(col):
            rows.append({
                "state_kind": col,
                "state": s,
                "n_weeks": int(len(sub)),
                "hh_mean_wkly": float(sub["hh"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["hh"].mean() - sub["prod"].mean()),
                "hh_minus_prod_cumulative": float(((1 + sub["hh"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
            })
    return pd.DataFrame(rows)


def headline(name: str, weekly: pd.Series, weights: pd.DataFrame | None) -> dict:
    full_m = roc.metric_block(weekly)
    hold_m = roc.metric_block(weekly.tail(roc.HOLDOUT_WEEKS))
    out = {
        "name": name,
        "full_ann_return": full_m["ann_return"],
        "full_ann_vol": full_m["ann_vol"],
        "full_sharpe": full_m["sharpe"],
        "full_max_drawdown": full_m["max_drawdown"],
        "full_cvar_5": full_m["cvar_5"],
        "full_calmar": full_m["calmar"],
        "holdout_ann_return": hold_m["ann_return"],
        "holdout_sharpe": hold_m["sharpe"],
        "holdout_max_drawdown": hold_m["max_drawdown"],
    }
    if weights is not None:
        out["avg_BIL"] = float(weights["BIL"].mean()) if "BIL" in weights.columns else float("nan")
        out["avg_SPY"] = float(weights["SPY"].mean()) if "SPY" in weights.columns else float("nan")
        out["max_etf_weight"] = float(weights.max(axis=1).max())
        t = weights.diff().abs().sum(axis=1).fillna(0.0)
        out["avg_turnover"] = float(t.mean())
    return out


def select_best(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_HH_PORTFOLIO_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_drag_pp = (prod["full_ann_return"] - r["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        sub = state_df[state_df["candidate"] == name]
        det_row = sub[(sub["state_kind"] == "refined_state") & (sub["state"] == "neutral_deteriorating")]
        det_delta_wkly = float(det_row["delta_mean_wkly"].iloc[0]) if not det_row.empty else float("nan")
        # also check healthy/recovery_confirmed for participation degradation
        h_row = sub[(sub["state_kind"] == "refined_state") & (sub["state"] == "neutral_healthy")]
        h_delta_wkly = float(h_row["delta_mean_wkly"].iloc[0]) if not h_row.empty else float("nan")
        rc_row = sub[(sub["state_kind"] == "refined_state") & (sub["state"] == "recovery_confirmed")]
        rc_delta_wkly = float(rc_row["delta_mean_wkly"].iloc[0]) if not rc_row.empty else float("nan")
        cond_drag = ann_drag_pp <= 0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0
        cond_det = (not np.isnan(det_delta_wkly)) and det_delta_wkly >= 0
        # "materially" worsening healthy/recovery_confirmed: more negative than 0.0001/wk
        cond_h = np.isnan(h_delta_wkly) or h_delta_wkly >= -1e-4
        cond_rc = np.isnan(rc_delta_wkly) or rc_delta_wkly >= -1e-4
        passes = all([cond_drag, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_det, cond_h, cond_rc])
        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({ann_drag_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"bil_inc>5pp ({bil_inc_pp:+.2f}pp)" if not cond_bil else "",
            f"underperforms in neutral_deteriorating (Δ={det_delta_wkly:+.6f}/wk)" if not cond_det else "",
            f"materially worsens neutral_healthy (Δ={h_delta_wkly:+.6f}/wk)" if not cond_h else "",
            f"materially worsens recovery_confirmed (Δ={rc_delta_wkly:+.6f}/wk)" if not cond_rc else "",
        ])) or "none"
        rows.append({
            "name": name,
            "ann_drag_pp": ann_drag_pp,
            "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp,
            "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio,
            "bil_inc_pp": bil_inc_pp,
            "deteriorating_state_delta_wkly": det_delta_wkly,
            "neutral_healthy_delta_wkly": h_delta_wkly,
            "recovery_confirmed_delta_wkly": rc_delta_wkly,
            "passes_all_gates": passes,
            "fail_reasons": fail,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
        rationale = f"Selected {best['name']}: passes all 9 gates; sharpe_imp +{best['sharpe_imp']:.4f}; det_delta {best['deteriorating_state_delta_wkly']:+.6f}/wk."
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
    rationale = f"NO Phase HH portfolio candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


# ----------------------------------------------------------------------
# HH3 — feature ablation (report only)
# ----------------------------------------------------------------------

def feature_ablation_report(refined: pd.DataFrame, p2b: pd.DataFrame) -> dict:
    """Does augmenting p_regime_confidence with a refined_state indicator
    improve forward-stress prediction quality? Causal walk-forward Brier
    score comparison.

    Outcome label: forward-4-week max indicator of stressed_panic state.
    Baseline predictor: p_regime_confidence (Phase 2B logistic).
    Augmented predictor: simple linear blend of p_regime_confidence and a
    refined_state indicator (healthy=+1, mixed=0, deteriorating=-1).
    """
    if p2b.empty:
        return {"available": False, "reason": "phase2b_meta_predictions.csv missing"}
    # Build outcome
    state = refined["market_state"].astype(str)
    panic = (state == "stressed_panic").astype(int)
    fwd_panic = panic.shift(-1).rolling(window=4, min_periods=4).max().shift(-(4 - 1))
    df = pd.DataFrame({
        "p_regime_confidence": p2b["p_regime_confidence"],
        "refined_state": refined["refined_state"].astype(str),
    }).dropna()
    df["fwd_panic"] = fwd_panic
    df = df.dropna()
    if df.empty:
        return {"available": False, "reason": "insufficient overlapping data"}
    # Baseline: p_regime_confidence as pseudo-prob of "regime is healthy" — convert to
    # pseudo-prob of stress via 1 - p_regime_confidence (lower confidence ~ more risk).
    p_baseline = (1.0 - df["p_regime_confidence"].astype(float)).clip(0, 1)
    # Augmented: subtract a small shift based on refined_state (deteriorating raises prob)
    state_indicator = df["refined_state"].map({
        "neutral_healthy": -0.05,
        "neutral_mixed": 0.0,
        "neutral_deteriorating": +0.05,
        "calm_trend": -0.05,
        "recovery_confirmed": -0.03,
        "recovery_fragile": +0.03,
        "stressed_panic": 0.0,
    }).astype(float).fillna(0.0)
    p_aug = (p_baseline + state_indicator).clip(0, 1)
    y = df["fwd_panic"].astype(float)
    brier_baseline = float(((p_baseline - y) ** 2).mean())
    brier_aug = float(((p_aug - y) ** 2).mean())
    improvement = brier_baseline - brier_aug  # positive = augmented is BETTER
    return {
        "available": True,
        "n_obs": int(len(df)),
        "brier_baseline": brier_baseline,
        "brier_aug_with_refined_state": brier_aug,
        "improvement_baseline_minus_aug": improvement,
        "interpretation": ("augmented improves forward-panic Brier"
                           if improvement > 0
                           else "augmented does NOT improve forward-panic Brier (refined_state adds no incremental information beyond p_regime_confidence)"),
    }


# ----------------------------------------------------------------------
# main
# ----------------------------------------------------------------------

def main():
    if "--no-rebuild" not in sys.argv:
        run_production_path(rebuild_production=True)
    else:
        print("--no-rebuild: using existing files")

    refined = load_refined_state()
    p2b = load_phase2b_predictions()

    summaries = []
    state_rows = []
    for name in PHASE_HH_PORTFOLIO_CANDIDATES + [PRODUCTION, SHADOW]:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            print(f"WARNING: {name} returns missing — skipping")
            continue
        w = roc.load_portfolio_weights(name)
        net = ret["net_return"].dropna()
        h = headline(name, net, w)
        if "avg_turnover" not in h and "turnover" in ret.columns:
            h["avg_turnover"] = float(ret["turnover"].mean())
        summaries.append(h)
    summary = pd.DataFrame(summaries)
    summary.to_csv(roc.LAYER3_DIR / "phase_hh_candidate_metrics_full.csv", index=False)

    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    if prod_ret is None:
        raise RuntimeError("Production returns missing")
    prod_net = prod_ret["net_return"]
    for name in PHASE_HH_PORTFOLIO_CANDIDATES:
        cret = roc.load_portfolio_returns(name)
        if cret is None: continue
        sb = state_breakdown(cret["net_return"], prod_net, refined)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_df.empty:
        state_df.to_csv(roc.LAYER3_DIR / "phase_hh_state_summary.csv", index=False)

    best, rationale, decision_records = select_best(summary, state_df)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + decision_records).to_csv(
        roc.LAYER3_DIR / "phase_hh_selection_table.csv", index=False)

    # HH3 feature ablation
    print("\nRunning HH3 — feature ablation...")
    ablation = feature_ablation_report(refined, p2b)
    pd.DataFrame([ablation]).to_csv(roc.LAYER3_DIR / "phase_hh_feature_ablation.csv", index=False)
    print(json.dumps(ablation, indent=2))

    print("\n=== Phase HH candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    if not state_df.empty:
        print("\n=== Phase HH state-by-state (refined_state) ===")
        view = state_df[state_df["state_kind"] == "refined_state"][[
            "candidate", "state", "n_weeks", "delta_mean_wkly", "hh_minus_prod_cumulative"]]
        print(view.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    print(f"\n{rationale}")

    # Branch retire/continue decision per spec
    branch_should_retire = True
    for r in decision_records:
        if r["passes_all_gates"]:
            branch_should_retire = False
            break
    branch_decision = (
        "RETIRE Phase CC refined-state PORTFOLIO-CONSUMPTION path. Refined state remains useful upstream intelligence (state classification reporting / dashboards), but does not deliver portfolio improvement either as a sleeve/ETF multiplier (DD/EE/FF/GG) or as a regime-confidence feature (HH1/HH2)."
        if branch_should_retire
        else "CONTINUE — at least one Phase HH variant passes all gates."
    )

    protocol = {
        "phase": "Phase HH — Refined-state regime-confidence FEATURE",
        "portfolio_candidates": PHASE_HH_PORTFOLIO_CANDIDATES,
        "ablation_only": ["phase_hh_feature_ablation"],
        "integration_point": "scripts/build_improvement_artifacts.py — apply_overlays_custom (HH1 adds ±0.02 to regime_multiplier from refined_state; HH2 scales dynamic_speed by 0.85 in neutral_deteriorating only)",
        "selection_rule": {
            "ann_ret_drag_max_pp": 0.30,
            "sharpe_improvement_min": 0.005,
            "mdd_worsening_max_pp": 0.5,
            "cvar_worsening_max_pp": 0.05,
            "turnover_ratio_max_vs_prod": 1.10,
            "bil_increase_max_pp": 5.0,
            "neutral_deteriorating_state_must_not_underperform": True,
            "neutral_healthy_must_not_materially_worsen": True,
            "recovery_confirmed_must_not_materially_worsen": True,
        },
        "best_candidate": best,
        "rationale": rationale,
        "branch_should_retire": branch_should_retire,
        "branch_decision": branch_decision,
        "feature_ablation": ablation,
    }
    (roc.LAYER3_DIR / "phase_hh_protocol.json").write_text(json.dumps(protocol, indent=2))
    print(f"\nBranch decision: {branch_decision}")
    print("\nSaved Phase HH artifacts.")
    return best, branch_should_retire


if __name__ == "__main__":
    main()
