"""Phase V — Final Holdings-Blend Refinement.

This is the *final disciplined sprint* in the current allocator / trust /
regime / holdings-blend branch. Phase U produced multiple candidates that
each cleared four of the six Phase D production gates, but never aligned
all six. Phase V's job is to close the remaining mechanical misses inside
the holdings-level blend framework that Phase U validated. If it does not,
the branch is exhausted.

Three candidates only — high-conviction, narrowly justified:

  V1 — 90/10 production + phasen holdings blend
    `improved_phasev_prod90_phasen_10_holdings_blend`
    Designed to close U1a's residual full-history-Δ gap (+0.015 floor;
    U1a delivered +0.0067). phasen has full-history composite ~0.567 vs
    R2's ~0.520, a +0.047 advantage. A 10% phasen weight should mechanically
    add ~+0.0047 to full Δ on top of U1a's +0.0067, projecting roughly
    +0.011-0.012 — still short of the floor but the closest
    high-conviction shot, and the holdout-Δ axis (already cleared by U1a)
    is unlikely to break with a phasen partner whose holdout behavior is
    less defensive than R2/R3 but still tail-aware.

  V2 — 90/10 production + phaseo holdings blend
    `improved_phasev_prod90_phaseo_10_holdings_blend`
    Same ratio, different partner. phaseo carries the strongest
    holdout-Sharpe profile of the meta-allocator references and a
    different correlation structure with production than R2/R3. Tests
    whether a different partner with a different tradeoff between
    Sharpe, full-Δ, and bootstrap can produce a more aligned candidate.

  V3 — tighter conditional production-heavy blend
    `improved_phasev_conditional95_80_holdings_blend`
    95/5 in `defense_production` weeks, 80/20 elsewhere, partner = phasen
    (the most justified partner from V1's reasoning). This sharpens
    Phase U's U3 conditional candidate (which cleared bootstrap 71% but
    failed rolling win at 40% with a 90/10 → 70/30 split) toward
    preserving production positioning more strongly in defense weeks
    while letting the partner contribute meaningfully in calm/recovery
    weeks. The partner switch from R2 to phasen also lifts the
    full-history-Δ ceiling.

Causal / walk-forward safety:
  - All inputs (production, phasen, phaseo, R2 weights, Phase Q hard
    bucket) are already walk-forward safe.
  - Linear blends and a 2-branch bucket-keyed conditional cannot
    introduce lookahead.
  - No retraining of any branch.

Outputs to data/05_layer3_portfolio_construction/:
  phase_v_controls_{version}.csv
  phase_v_holdings_diagnostics.csv
  phase_v_candidate_metrics_{full,dev,holdout}.csv
  phase_v_rolling_origin_summary.csv
  phase_v_pairwise_validation.csv
  phase_v_candidate_classification.csv
  phase_v_validation_protocol.json
  portfolio_version_{weights,returns}_{version}.csv
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import phase_d_validate as pdv
import phase_h_refined_panel_allocator as ph
import phase_p_meta_allocator as pp
import phase_p_evaluate as ppe
import phase_q_abstention_meta_allocator as pq


ROOT = Path(__file__).resolve().parents[1]
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = pp.PRODUCTION_PIN
SHADOW_PIN = pp.SHADOW_PIN
PHASEH_REFERENCE = pp.PHASEH_REFERENCE
PHASEN_REFERENCE = pp.PHASEN_REFERENCE
PHASEO_REFERENCE = pp.PHASEO_REFERENCE
ACTIVE_PANEL_BASELINE = pp.ACTIVE_PANEL_BASELINE
PHASEP_REFERENCE = "improved_phasep_regret_aware_meta_allocator"
PHASEQ_BUCKET_REFERENCE = "improved_phaseq_regime_bucket_meta_allocator"
PHASER_R2_REFERENCE = "improved_phaser_light_abstention_overlay_allocator"
PHASER_R3_REFERENCE = "improved_phaser_fast_narrow_regret_allocator"
PHASET_T1_REFERENCE = "improved_phaset_soft_regime_posterior_allocator"
PHASEU_U1A_REFERENCE = "improved_phaseu_prod90_r2_10_holdings_blend"
PHASEU_U3_REFERENCE = "improved_phaseu_conditional_prod_r2_holdings_blend"

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    PHASEP_REFERENCE,
    PHASEQ_BUCKET_REFERENCE,
    PHASER_R2_REFERENCE,
    PHASER_R3_REFERENCE,
    PHASET_T1_REFERENCE,
    PHASEU_U1A_REFERENCE,
    PHASEU_U3_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

# Phase V candidate definitions.
# Static candidates: (version_name, description, partner_version, prod_share, partner_share).
PHASE_V_STATIC_CANDIDATES = [
    ("improved_phasev_prod90_phasen_10_holdings_blend", "V1 90/10 production+phasen", PHASEN_REFERENCE, 0.90, 0.10),
    ("improved_phasev_prod90_phaseo_10_holdings_blend", "V2 90/10 production+phaseo", PHASEO_REFERENCE, 0.90, 0.10),
]

# V3 conditional candidate.
PHASE_V_CONDITIONAL_NAME = "improved_phasev_conditional95_80_holdings_blend"
PHASE_V_CONDITIONAL_PARTNER = PHASEN_REFERENCE  # justified by V1 reasoning
PHASE_V_CONDITIONAL_DEFENSE_BLEND = (0.95, 0.05)   # 95/5 in defense_production
PHASE_V_CONDITIONAL_OTHER_BLEND = (0.80, 0.20)     # 80/20 elsewhere

EPS = 1e-9


# --------------------------------------------------------------------------
#                       weight loading
# --------------------------------------------------------------------------

def load_weights(version: str) -> pd.DataFrame:
    path = LAYER3_DIR / f"portfolio_version_weights_{version}.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    return df


def compute_hard_bucket_series(feature_frame: pd.DataFrame) -> pd.Series:
    """Per-week Phase Q hard bucket label. Reuses the existing causal rule."""
    rows = []
    for date in feature_frame.index:
        bucket = pq.compute_regime_bucket(
            state_text=feature_frame.loc[date, "state_text"],
            calm_conf=float(feature_frame.loc[date, "calm_confidence"]),
            recovery_conf=float(feature_frame.loc[date, "recovery_confidence"]),
            stress_conf=float(feature_frame.loc[date, "stress_confidence"]),
            chop_conf=float(feature_frame.loc[date, "chop_confidence"]),
            model_confidence=float(feature_frame.loc[date, "model_confidence"]),
            model_uncertainty=float(feature_frame.loc[date, "model_uncertainty"]),
            agreement=float(feature_frame.loc[date, "agreement"]),
            risk_guard=float(feature_frame.loc[date, "risk_guard"]),
            margin_conf=float(feature_frame.loc[date, "margin_confidence"]),
            gate_entropy=float(feature_frame.loc[date, "phase_n_gate_entropy"]),
        )
        rows.append({"date": date, "bucket": bucket})
    return pd.DataFrame(rows).set_index("date")["bucket"]


# --------------------------------------------------------------------------
#                      blend builders
# --------------------------------------------------------------------------

def static_blend(
    prod_w: pd.DataFrame, partner_w: pd.DataFrame, prod_share: float, partner_share: float,
) -> pd.DataFrame:
    """Per-week static blend at the holdings level."""
    prod_aligned, partner_aligned = prod_w.align(partner_w, join="inner", axis=1, fill_value=0.0)
    common = prod_aligned.index.intersection(partner_aligned.index)
    p = prod_aligned.loc[common]
    a = partner_aligned.loc[common]
    blended = prod_share * p + partner_share * a
    sums = blended.sum(axis=1).replace(0.0, np.nan)
    blended = blended.div(sums, axis=0).fillna(0.0)
    return blended


def conditional_blend(
    prod_w: pd.DataFrame,
    partner_w: pd.DataFrame,
    bucket_series: pd.Series,
    defense_prod_share: float,
    other_prod_share: float,
) -> pd.DataFrame:
    """Conditional holdings blend keyed off Phase Q's hard bucket label."""
    prod_aligned, partner_aligned = prod_w.align(partner_w, join="inner", axis=1, fill_value=0.0)
    common = prod_aligned.index.intersection(partner_aligned.index).intersection(bucket_series.index)
    p = prod_aligned.loc[common]
    a = partner_aligned.loc[common]
    bucket = bucket_series.loc[common]

    is_defense = (bucket == "defense_production")
    prod_share_series = is_defense.map({True: defense_prod_share, False: other_prod_share}).astype(float)
    partner_share_series = 1.0 - prod_share_series

    blended = p.mul(prod_share_series, axis=0) + a.mul(partner_share_series, axis=0)
    sums = blended.sum(axis=1).replace(0.0, np.nan)
    blended = blended.div(sums, axis=0).fillna(0.0)
    return blended


# --------------------------------------------------------------------------
#                  controls / diagnostics
# --------------------------------------------------------------------------

def control_frame(
    blended_w: pd.DataFrame,
    prod_w: pd.DataFrame,
    partner_w: pd.DataFrame,
    bucket_series: pd.Series | None,
    prod_share_series: pd.Series,
    partner_share_series: pd.Series,
    u1a_w: pd.DataFrame | None = None,
) -> pd.DataFrame:
    common = blended_w.index
    p = prod_w.reindex(common).reindex(columns=blended_w.columns, fill_value=0.0)
    a = partner_w.reindex(common).reindex(columns=blended_w.columns, fill_value=0.0)
    if u1a_w is not None:
        u1 = u1a_w.reindex(common).reindex(columns=blended_w.columns, fill_value=0.0)
    else:
        u1 = None
    rows = []
    for date in common:
        l1_to_prod = float((blended_w.loc[date] - p.loc[date]).abs().sum())
        l1_to_partner = float((blended_w.loc[date] - a.loc[date]).abs().sum())
        l1_to_u1a = float((blended_w.loc[date] - u1.loc[date]).abs().sum()) if u1 is not None else float("nan")
        bil_share = float(blended_w.loc[date].get("BIL", 0.0))
        rows.append({
            "date": date,
            "bucket": bucket_series.loc[date] if bucket_series is not None and date in bucket_series.index else "n/a",
            "prod_share": float(prod_share_series.loc[date]),
            "partner_share": float(partner_share_series.loc[date]),
            "l1_distance_to_production": l1_to_prod,
            "l1_distance_to_partner": l1_to_partner,
            "l1_distance_to_u1a": l1_to_u1a,
            "bil_weight": bil_share,
        })
    return pd.DataFrame(rows).set_index("date")


def holdings_diagnostics(version: str, controls: pd.DataFrame, partner_name: str) -> dict:
    return {
        "version_name": version,
        "partner": partner_name,
        "observations": int(len(controls)),
        "avg_prod_share": float(controls["prod_share"].mean()),
        "avg_partner_share": float(controls["partner_share"].mean()),
        "avg_l1_distance_to_production": float(controls["l1_distance_to_production"].mean()),
        "avg_l1_distance_to_partner": float(controls["l1_distance_to_partner"].mean()),
        "avg_l1_distance_to_u1a": float(controls["l1_distance_to_u1a"].mean()),
        "avg_bil_weight": float(controls["bil_weight"].mean()),
    }


# --------------------------------------------------------------------------
#                         validation bundle
# --------------------------------------------------------------------------

def build_validation_bundle(candidate_names: list[str]) -> dict:
    all_versions = list(FIXED_COMPARATOR_SET) + candidate_names
    returns_map, weights_map, turnover_map, benchmark_returns, market_state_history = ppe.candidate_frames(all_versions)

    full_rows, dev_rows, holdout_rows = [], [], []
    for name in all_versions:
        full_rows.append(ppe.metric_row(name, returns_map[name], weights_map[name], turnover_map[name], benchmark_returns, market_state_history))
        dev_ret, hold_ret, dev_w, hold_w = pdv.split_dev_holdout(returns_map[name], weights_map[name], pdv.HOLDOUT_WEEKS)
        dev_rows.append(ppe.metric_row(name, dev_ret, dev_w, turnover_map[name].reindex(dev_ret.index), benchmark_returns.reindex(dev_ret.index), market_state_history))
        holdout_rows.append(ppe.metric_row(name, hold_ret, hold_w, turnover_map[name].reindex(hold_ret.index), benchmark_returns.reindex(hold_ret.index), market_state_history))
    full_df = pd.DataFrame(full_rows)
    dev_df = pd.DataFrame(dev_rows)
    holdout_df = pd.DataFrame(holdout_rows)
    for df in [full_df, dev_df, holdout_df]:
        df["fixed_rank_composite"] = pdv.fixed_rank_composite(df.set_index("version_name")).values
        df["fixed_rank_position"] = df["fixed_rank_composite"].rank(ascending=False, method="dense").astype(int)
        df["raw_composite_position"] = df["raw_target_composite"].rank(ascending=False, method="dense").astype(int)

    rolling_df, rolling_pairwise = ppe.rolling_evaluation(all_versions, returns_map, weights_map, turnover_map, benchmark_returns, market_state_history)

    full_idx = full_df.set_index("version_name")
    holdout_idx = holdout_df.set_index("version_name")
    production_full = full_idx.loc[PRODUCTION_PIN]
    production_holdout = holdout_idx.loc[PRODUCTION_PIN]
    production_holdout_returns = returns_map[PRODUCTION_PIN].tail(pdv.HOLDOUT_WEEKS)
    u1a_full = full_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout = holdout_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout_returns = returns_map[PHASEU_U1A_REFERENCE].tail(pdv.HOLDOUT_WEEKS)
    u3_full = full_idx.loc[PHASEU_U3_REFERENCE]
    u3_holdout = holdout_idx.loc[PHASEU_U3_REFERENCE]
    u3_holdout_returns = returns_map[PHASEU_U3_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

    pairwise_rows = []
    for name in all_versions:
        cand_full = full_idx.loc[name]
        cand_holdout = holdout_idx.loc[name]
        cand_holdout_returns = returns_map[name].tail(pdv.HOLDOUT_WEEKS)
        roll = rolling_pairwise.set_index("version_name").loc[name]
        row = {
            "version_name": name,
            "full_raw_delta_vs_production": float(cand_full["raw_target_composite"] - production_full["raw_target_composite"]),
            "holdout_raw_delta_vs_production": float(cand_holdout["raw_target_composite"] - production_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_production": float(cand_holdout["sharpe"] - production_holdout["sharpe"]),
            "bootstrap_prob_vs_production": ppe.safe_bootstrap(cand_holdout_returns, production_holdout_returns),
            "full_raw_delta_vs_u1a": float(cand_full["raw_target_composite"] - u1a_full["raw_target_composite"]),
            "holdout_raw_delta_vs_u1a": float(cand_holdout["raw_target_composite"] - u1a_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_u1a": float(cand_holdout["sharpe"] - u1a_holdout["sharpe"]),
            "bootstrap_prob_vs_u1a": ppe.safe_bootstrap(cand_holdout_returns, u1a_holdout_returns),
            "full_raw_delta_vs_u3": float(cand_full["raw_target_composite"] - u3_full["raw_target_composite"]),
            "holdout_raw_delta_vs_u3": float(cand_holdout["raw_target_composite"] - u3_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_u3": float(cand_holdout["sharpe"] - u3_holdout["sharpe"]),
            "bootstrap_prob_vs_u3": ppe.safe_bootstrap(cand_holdout_returns, u3_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    phasev_names = [n for n in candidate_names if n.startswith("improved_phasev")]
    classification_df = pairwise_df[pairwise_df["version_name"].isin(phasev_names)].copy()

    best_non_prod = (
        full_df[full_df["version_name"] != PRODUCTION_PIN]
        .sort_values("raw_target_composite", ascending=False)
        .iloc[0]["version_name"]
    )

    def classify(row: pd.Series) -> str:
        prod_rule_pass = (
            row["full_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["full_raw_composite_delta_vs_production_min"]
            and row["holdout_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["holdout_sharpe_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_sharpe_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.PRODUCTION_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["rolling_mean_raw_delta_vs_production"] > ppe.PRODUCTION_RULE["rolling_mean_raw_delta_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.PRODUCTION_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.PRODUCTION_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.PRODUCTION_RULE["cvar_worsening_cap"]
        )
        if prod_rule_pass:
            return "Promote now"
        shadow_pass = (
            str(row["version_name"]) == best_non_prod
            and row["holdout_raw_delta_vs_production"] >= ppe.SHADOW_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.SHADOW_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.SHADOW_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.SHADOW_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.SHADOW_RULE["cvar_worsening_cap"]
        )
        if shadow_pass:
            return "Conditional"
        research = (
            row["full_raw_delta_vs_u1a"] > 0.0
            or row["holdout_sharpe_delta_vs_u1a"] > 0.0
            or row["holdout_raw_delta_vs_u1a"] > 0.0
            or row["bootstrap_prob_vs_u1a"] > 0.5
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_v_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_v_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_v_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_v_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_v_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_v_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase V — Final Holdings-Blend Refinement",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_v_static_candidates": [c[0] for c in PHASE_V_STATIC_CANDIDATES],
        "phase_v_conditional_candidate": PHASE_V_CONDITIONAL_NAME,
        "phase_v_conditional_partner": PHASE_V_CONDITIONAL_PARTNER,
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "conditional_rule": {
            "defense_prod_share": PHASE_V_CONDITIONAL_DEFENSE_BLEND[0],
            "defense_partner_share": PHASE_V_CONDITIONAL_DEFENSE_BLEND[1],
            "other_prod_share": PHASE_V_CONDITIONAL_OTHER_BLEND[0],
            "other_partner_share": PHASE_V_CONDITIONAL_OTHER_BLEND[1],
        },
    }
    (LAYER3_DIR / "phase_v_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {
        "full": full_df,
        "dev": dev_df,
        "holdout": holdout_df,
        "rolling": rolling_df,
        "pairwise": pairwise_df,
        "classification": classification_df,
    }


# --------------------------------------------------------------------------
#                                 main
# --------------------------------------------------------------------------

def main() -> None:
    feature_frame, _, _, _, next_week_returns, _ = pp.build_feature_frame()

    prod_w = load_weights(PRODUCTION_PIN)
    phasen_w = load_weights(PHASEN_REFERENCE)
    phaseo_w = load_weights(PHASEO_REFERENCE)
    u1a_w = load_weights(PHASEU_U1A_REFERENCE)

    bucket_series = compute_hard_bucket_series(feature_frame)

    candidate_names: list[str] = []
    diagnostics_rows = []
    control_frames: dict[str, pd.DataFrame] = {}

    partner_lookup = {PHASEN_REFERENCE: phasen_w, PHASEO_REFERENCE: phaseo_w}

    # V1, V2 — static blends.
    for (name, _desc, partner_name, prod_share, partner_share) in PHASE_V_STATIC_CANDIDATES:
        partner_w = partner_lookup[partner_name]
        blended = static_blend(prod_w, partner_w, prod_share, partner_share)
        prod_share_series = pd.Series(prod_share, index=blended.index)
        partner_share_series = pd.Series(partner_share, index=blended.index)
        controls = control_frame(blended, prod_w, partner_w, bucket_series, prod_share_series, partner_share_series, u1a_w=u1a_w)
        controls.to_csv(LAYER3_DIR / f"phase_v_controls_{name}.csv")
        control_frames[name] = controls
        diag = holdings_diagnostics(name, controls, partner_name)
        diagnostics_rows.append(diag)
        path = pp.save_meta_portfolio_version(name, blended, next_week_returns)
        candidate_names.append(name)
        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        sharpe = (ann_ret / ann_vol) if ann_vol > 0 else float("nan")
        print(f"{name}: ann_return={ann_ret:.4f} sharpe={sharpe:.4f} turnover={path['turnover'].dropna().mean():.4f}")

    # V3 — tighter conditional blend (95/5 in defense, 80/20 elsewhere) with phasen.
    cond_partner_w = partner_lookup[PHASE_V_CONDITIONAL_PARTNER]
    blended_cond = conditional_blend(
        prod_w, cond_partner_w, bucket_series,
        defense_prod_share=PHASE_V_CONDITIONAL_DEFENSE_BLEND[0],
        other_prod_share=PHASE_V_CONDITIONAL_OTHER_BLEND[0],
    )
    common = blended_cond.index
    bucket_aligned = bucket_series.reindex(common)
    prod_share_series_cond = (bucket_aligned == "defense_production").map(
        {True: PHASE_V_CONDITIONAL_DEFENSE_BLEND[0], False: PHASE_V_CONDITIONAL_OTHER_BLEND[0]}
    ).astype(float)
    partner_share_series_cond = 1.0 - prod_share_series_cond
    controls_cond = control_frame(blended_cond, prod_w, cond_partner_w, bucket_series, prod_share_series_cond, partner_share_series_cond, u1a_w=u1a_w)
    controls_cond.to_csv(LAYER3_DIR / f"phase_v_controls_{PHASE_V_CONDITIONAL_NAME}.csv")
    control_frames[PHASE_V_CONDITIONAL_NAME] = controls_cond
    diag_cond = holdings_diagnostics(PHASE_V_CONDITIONAL_NAME, controls_cond, PHASE_V_CONDITIONAL_PARTNER)
    diagnostics_rows.append(diag_cond)
    path_cond = pp.save_meta_portfolio_version(PHASE_V_CONDITIONAL_NAME, blended_cond, next_week_returns)
    candidate_names.append(PHASE_V_CONDITIONAL_NAME)
    ann_ret = ph.annualized_return(path_cond["net_return"])
    ann_vol = ph.annualized_vol(path_cond["net_return"])
    sharpe = (ann_ret / ann_vol) if ann_vol > 0 else float("nan")
    print(f"{PHASE_V_CONDITIONAL_NAME}: ann_return={ann_ret:.4f} sharpe={sharpe:.4f} turnover={path_cond['turnover'].dropna().mean():.4f}")

    diag_df = pd.DataFrame(diagnostics_rows)
    diag_df.to_csv(LAYER3_DIR / "phase_v_holdings_diagnostics.csv", index=False)

    results = build_validation_bundle(candidate_names)

    print("\n=== Phase V holdings diagnostics ===")
    print(diag_df.round(4).to_string(index=False))

    cols = ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
            "recovery_capture", "raw_target_composite", "raw_composite_position"]
    print("\n=== Phase V FULL metrics (cohort) ===")
    print(results["full"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase V HOLDOUT metrics (cohort) ===")
    print(results["holdout"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase V pairwise vs production / U1a / U3 ===")
    keep = [n for n in results["pairwise"]["version_name"]
            if n.startswith("improved_phasev")
            or n in {PRODUCTION_PIN, PHASEU_U1A_REFERENCE, PHASEU_U3_REFERENCE,
                     PHASEN_REFERENCE, PHASEO_REFERENCE, PHASER_R2_REFERENCE,
                     PHASER_R3_REFERENCE}]
    pcols = ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
             "holdout_sharpe_delta_vs_production", "bootstrap_prob_vs_production",
             "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production",
             "full_raw_delta_vs_u1a", "holdout_raw_delta_vs_u1a",
             "holdout_sharpe_delta_vs_u1a", "bootstrap_prob_vs_u1a",
             "holdout_sharpe_delta_vs_u3", "bootstrap_prob_vs_u3",
             "max_drawdown_delta_vs_production", "cvar_delta_vs_production"]
    print(results["pairwise"].set_index("version_name").loc[keep, pcols].round(4).to_string())

    print("\n=== Phase V classification ===")
    print(results["classification"].set_index("version_name")[
        ["classification", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
         "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production",
         "bootstrap_prob_vs_production",
         "max_drawdown_delta_vs_production", "cvar_delta_vs_production"]].round(4).to_string())

    print("\nSaved Phase V artifacts.")


if __name__ == "__main__":
    main()
