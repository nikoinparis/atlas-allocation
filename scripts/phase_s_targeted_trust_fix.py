"""Phase S — Final Targeted Trust-Layer Fix.

Phase S is the smallest disciplined sprint aimed at closing the remaining
production-gate gap after Phase R. No new sleeves, no new signals, no new
ML models. It tests exactly two levers — the two levers that Phase R
explicitly identified as the remaining weaknesses:

  S1 `improved_phases_defense_reshape_allocator`
    - Keeps Phase R's R2 bucket skeleton, persistence, and overlay logic.
    - Only change: inside `defense_production` the internal expert blend is
      tightened from R2's (production 0.85 / phasen 0.075 / phaseo 0.075 /
      abstain 0.00) to (production 0.95 / phasen 0.025 / phaseo 0.025 /
      abstain 0.00). This reduces over-diversification away from the actual
      production holdings in adverse tape — the single structural cause of
      R2's residual downside-capture drag.

  S2 `improved_phases_conditional_ml_attenuator_allocator`
    - Keeps R2's base mixes exactly.
    - Adds a causal conditional ML-share attenuator: when the trailing 13-week
      realised excess return of each ML expert vs production is negative,
      that expert's weight inside trust buckets (calm_trust, recovery_trust,
      ambiguous_abstain) is scaled down linearly, bounded between 0.40 and
      1.00 of its base weight. Weight removed from ML is redistributed to
      production. `defense_production` is not touched because the attenuator
      is only about damping ML share in weeks where ML is demonstrably in a
      weak patch.

  S3 `improved_phases_defense_reshape_ml_attenuator_combo`
    - S1 base mixes + S2 conditional ML attenuator.
    - Only built because the two levers target independent residuals (tail
      blend shape vs rolling win-rate in ML buckets) and combine cleanly
      without double-counting.

All candidates reuse Phase P's walk-forward classifier probabilities, the
Phase Q feature frame, and Phase Q's bucket rule / 3-week persistence.
Validation uses the standing Phase D rule set against the fixed 10-member
comparator set.

Outputs to data/05_layer3_portfolio_construction/:
  phase_s_controls_{version}.csv
  phase_s_trust_summary.csv
  phase_s_trust_by_state.csv
  phase_s_bucket_summary.csv
  phase_s_candidate_metrics_{full,dev,holdout}.csv
  phase_s_rolling_origin_summary.csv
  phase_s_pairwise_validation.csv
  phase_s_candidate_classification.csv
  phase_s_validation_protocol.json
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
    ACTIVE_PANEL_BASELINE,
]

PHASE_S_CANDIDATES = {
    "improved_phases_defense_reshape_allocator":                  "S1 defense_production internal reshape",
    "improved_phases_conditional_ml_attenuator_allocator":        "S2 conditional ML-share attenuator",
    "improved_phases_defense_reshape_ml_attenuator_combo":        "S3 combo S1 + S2",
}

# Bucket persistence preserved from Phase Q / R.
BUCKET_PERSISTENCE = pq.BUCKET_PERSISTENCE

# R2's base mixes (abstain-light). S1 tightens defense_production.
R2_BASE_MIX = {
    "calm_trust":         {"production": 0.20, "phasen": 0.25, "phaseo": 0.55, "abstain": 0.00},
    "recovery_trust":     {"production": 0.25, "phasen": 0.50, "phaseo": 0.25, "abstain": 0.00},
    "defense_production": {"production": 0.85, "phasen": 0.075, "phaseo": 0.075, "abstain": 0.00},
    "ambiguous_abstain":  {"production": 0.65, "phasen": 0.13, "phaseo": 0.12, "abstain": 0.10},
}

# S1 base mix — only defense_production is changed. Everything else == R2.
S1_BASE_MIX = {
    "calm_trust":         dict(R2_BASE_MIX["calm_trust"]),
    "recovery_trust":     dict(R2_BASE_MIX["recovery_trust"]),
    "defense_production": {"production": 0.95, "phasen": 0.025, "phaseo": 0.025, "abstain": 0.00},
    "ambiguous_abstain":  dict(R2_BASE_MIX["ambiguous_abstain"]),
}

# R2's light abstention overlay parameters preserved so S1/S2/S3 behave
# identically to R2 except where stated.
R2_ABSTAIN_SCORE_GATE = 0.60
R2_ABSTAIN_MAX_WEIGHT = 0.10

# Conditional ML-share attenuator settings.
# - `ATTEN_WINDOW` — rolling window for realised ML excess return vs production
# - `ATTEN_THRESHOLD_ABS` — threshold beyond which attenuation saturates
# - `ATTEN_FLOOR` — minimum fraction of base ML weight retained
# - `ATTEN_BUCKETS` — only bucket contexts where the attenuator can fire
ATTEN_WINDOW = 13
ATTEN_THRESHOLD_ABS = 0.0015  # per-week average excess; saturates beyond this
ATTEN_FLOOR = 0.40
ATTEN_BUCKETS = {"calm_trust", "recovery_trust", "ambiguous_abstain"}

EPS = 1e-9


def _normalize(mix: dict[str, float]) -> dict[str, float]:
    mix = {k: max(v, 0.0) for k, v in mix.items()}
    total = sum(mix.values())
    if total <= EPS:
        return {"production": 1.0, "phasen": 0.0, "phaseo": 0.0, "abstain": 0.0}
    return {k: v / total for k, v in mix.items()}


def rolling_excess(expert_returns: pd.Series, prod_returns: pd.Series, window: int = ATTEN_WINDOW) -> pd.Series:
    """Causal trailing-mean excess return of expert vs production.

    Shifted by 1 week so the value at date t uses only info up through t-1.
    """
    excess = (expert_returns - prod_returns).shift(1).fillna(0.0)
    return excess.rolling(window=window, min_periods=max(4, window // 3)).mean().fillna(0.0)


def ml_attenuation_factor(trailing_excess: float) -> float:
    """Map trailing ML excess to a multiplicative attenuation factor in [FLOOR, 1.0].

    Positive or zero excess => factor = 1.0 (no attenuation).
    Negative excess => linearly scale toward FLOOR, saturating at THRESHOLD.
    """
    if trailing_excess >= 0.0:
        return 1.0
    severity = min(1.0, abs(trailing_excess) / ATTEN_THRESHOLD_ABS)
    return float(ATTEN_FLOOR + (1.0 - ATTEN_FLOOR) * (1.0 - severity))


def apply_conditional_ml_attenuator(
    mix: dict[str, float],
    *,
    bucket: str,
    phaseo_trailing: float,
    phasen_trailing: float,
) -> tuple[dict[str, float], float, float, float]:
    """Attenuate ML experts only if (a) bucket allows it and (b) trailing
    excess is negative. Mass removed from ML goes to production.
    """
    if bucket not in ATTEN_BUCKETS:
        return dict(mix), 1.0, 1.0, 0.0
    factor_o = ml_attenuation_factor(phaseo_trailing)
    factor_n = ml_attenuation_factor(phasen_trailing)
    out = dict(mix)
    base_o, base_n = out["phaseo"], out["phasen"]
    new_o = base_o * factor_o
    new_n = base_n * factor_n
    removed = (base_o - new_o) + (base_n - new_n)
    out["phaseo"] = new_o
    out["phasen"] = new_n
    out["production"] = out["production"] + removed
    return out, factor_o, factor_n, removed


def build_candidate(
    *,
    version_name: str,
    feature_frame: pd.DataFrame,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    phaseo_trailing_excess: pd.Series,
    phasen_trailing_excess: pd.Series,
    base_mix_table: dict[str, dict[str, float]],
    use_light_abstention: bool = True,
    use_conditional_attenuator: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generic Phase S builder. Shares the Phase R trust skeleton."""
    prod_w = weights_map[PRODUCTION_PIN]
    phasen_w = weights_map[PHASEN_REFERENCE]
    phaseo_w = weights_map[PHASEO_REFERENCE]
    columns = list(prod_w.columns)
    anchor = pq.abstain_anchor(columns)

    rows: list[pd.Series] = []
    ctrl_rows: list[pd.Series] = []

    active_bucket = "defense_production"
    proposed_bucket = active_bucket
    proposal_streak = 0

    for date in feature_frame.index:
        st = feature_frame.loc[date, "state_text"]
        model_confidence = float(feature_frame.loc[date, "model_confidence"])
        model_uncertainty = float(feature_frame.loc[date, "model_uncertainty"])
        margin_conf = float(feature_frame.loc[date, "margin_confidence"])
        agreement = float(feature_frame.loc[date, "agreement"])
        risk_guard = float(feature_frame.loc[date, "risk_guard"])
        gate_entropy = float(feature_frame.loc[date, "phase_n_gate_entropy"])
        calm_conf = float(feature_frame.loc[date, "calm_confidence"])
        recovery_conf = float(feature_frame.loc[date, "recovery_confidence"])
        stress_conf = float(feature_frame.loc[date, "stress_confidence"])
        chop_conf = float(feature_frame.loc[date, "chop_confidence"])
        p_phaseo = float(phaseo_prob.loc[date])
        p_phasen = float(phasen_prob.loc[date])

        this_bucket = pq.compute_regime_bucket(
            state_text=st,
            calm_conf=calm_conf,
            recovery_conf=recovery_conf,
            stress_conf=stress_conf,
            chop_conf=chop_conf,
            model_confidence=model_confidence,
            model_uncertainty=model_uncertainty,
            agreement=agreement,
            risk_guard=risk_guard,
            margin_conf=margin_conf,
            gate_entropy=gate_entropy,
        )
        if this_bucket == proposed_bucket:
            proposal_streak += 1
        else:
            proposed_bucket = this_bucket
            proposal_streak = 1
        if proposal_streak >= BUCKET_PERSISTENCE:
            active_bucket = proposed_bucket

        base = dict(base_mix_table[active_bucket])
        mix = dict(base)

        a_score = pq.abstention_score(
            model_uncertainty=model_uncertainty,
            margin_conf=margin_conf,
            risk_guard=risk_guard,
            gate_entropy=gate_entropy,
            phaseo_prob=p_phaseo,
            phasen_prob=p_phasen,
        )

        # Conditional ML-share attenuator (S2 / S3). Applied BEFORE the
        # light-abstention overlay so the overlay operates on already-attenuated
        # ML mass and never adds weight back to ML.
        phaseo_trailing = float(phaseo_trailing_excess.loc[date])
        phasen_trailing = float(phasen_trailing_excess.loc[date])
        atten_removed = 0.0
        factor_o = 1.0
        factor_n = 1.0
        if use_conditional_attenuator:
            mix, factor_o, factor_n, atten_removed = apply_conditional_ml_attenuator(
                mix,
                bucket=active_bucket,
                phaseo_trailing=phaseo_trailing,
                phasen_trailing=phasen_trailing,
            )

        # Light-abstention overlay (R2-style).
        overlay_fired = 0.0
        if use_light_abstention and active_bucket != "defense_production":
            if a_score > R2_ABSTAIN_SCORE_GATE:
                ml_mass = mix["phaseo"] + mix["phasen"]
                pull = min(R2_ABSTAIN_MAX_WEIGHT, 0.50 * (a_score - R2_ABSTAIN_SCORE_GATE) * max(ml_mass, mix["production"]))
                if ml_mass > EPS:
                    scale_o = pull * (mix["phaseo"] / max(ml_mass, EPS))
                    scale_n = pull * (mix["phasen"] / max(ml_mass, EPS))
                    mix["phaseo"] = max(0.0, mix["phaseo"] - scale_o)
                    mix["phasen"] = max(0.0, mix["phasen"] - scale_n)
                    mix["abstain"] += pull
                    overlay_fired = pull

        mix = _normalize(mix)

        w = (
            mix["production"] * prod_w.loc[date]
            + mix["phasen"] * phasen_w.loc[date]
            + mix["phaseo"] * phaseo_w.loc[date]
            + mix["abstain"] * anchor
        ).reindex(columns).fillna(0.0)
        rows.append(w.rename(date))

        selected = max(mix.items(), key=lambda kv: kv[1])[0]
        ctrl_rows.append(pd.Series(
            {
                "state_text": st,
                "bucket": active_bucket,
                "proposed_bucket": this_bucket,
                "bucket_streak": proposal_streak,
                "production_weight": mix["production"],
                "phasen_weight": mix["phasen"],
                "phaseo_weight": mix["phaseo"],
                "abstain_weight": mix["abstain"],
                "overlay_abstain_added": overlay_fired,
                "atten_removed_ml_mass": atten_removed,
                "atten_factor_phaseo": factor_o,
                "atten_factor_phasen": factor_n,
                "phaseo_trailing_excess": phaseo_trailing,
                "phasen_trailing_excess": phasen_trailing,
                "trust_score": mix["phaseo"] + 0.5 * mix["phasen"],
                "abstention_score": a_score,
                "phaseo_prob": p_phaseo,
                "phasen_prob": p_phasen,
                "model_uncertainty": model_uncertainty,
                "margin_confidence": margin_conf,
                "risk_guard": risk_guard,
                "gate_entropy": gate_entropy,
                "selected_expert": selected,
            },
            name=date,
        ))

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(ctrl_rows).sort_index()


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
    r2_full = full_idx.loc[PHASER_R2_REFERENCE]
    r2_holdout = holdout_idx.loc[PHASER_R2_REFERENCE]
    r2_holdout_returns = returns_map[PHASER_R2_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

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
            "full_raw_delta_vs_r2": float(cand_full["raw_target_composite"] - r2_full["raw_target_composite"]),
            "holdout_raw_delta_vs_r2": float(cand_holdout["raw_target_composite"] - r2_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_r2": float(cand_holdout["sharpe"] - r2_holdout["sharpe"]),
            "bootstrap_prob_vs_r2": ppe.safe_bootstrap(cand_holdout_returns, r2_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    phases_names = [n for n in candidate_names if n.startswith("improved_phases")]
    classification_df = pairwise_df[pairwise_df["version_name"].isin(phases_names)].copy()

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
            row["full_raw_delta_vs_r2"] > 0.0
            or row["holdout_sharpe_delta_vs_r2"] > 0.0
            or row["holdout_raw_delta_vs_r2"] > 0.0
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_s_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_s_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_s_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_s_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_s_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_s_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase S — Final Targeted Trust-Layer Fix",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_s_candidates": list(PHASE_S_CANDIDATES.keys()),
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "bucket_persistence_weeks": BUCKET_PERSISTENCE,
        "s1_defense_production_mix": S1_BASE_MIX["defense_production"],
        "attenuator": {
            "window_weeks": ATTEN_WINDOW,
            "threshold_abs_per_week_excess": ATTEN_THRESHOLD_ABS,
            "floor": ATTEN_FLOOR,
            "buckets": sorted(ATTEN_BUCKETS),
        },
    }
    (LAYER3_DIR / "phase_s_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {
        "full": full_df,
        "dev": dev_df,
        "holdout": holdout_df,
        "rolling": rolling_df,
        "pairwise": pairwise_df,
        "classification": classification_df,
    }


def main() -> None:
    feature_frame, returns_map, weights_map, target_frame, next_week_returns, market_state_history = pp.build_feature_frame()

    feature_cols = [c for c in feature_frame.columns if c != "state_text"]

    phaseo_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phaseo_trust_label"], feature_cols,
        model_name="phases_binary_phaseo_vs_production",
    )
    phasen_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phasen_trust_label"], feature_cols,
        model_name="phases_binary_phasen_vs_production",
    )

    # Causal trailing ML excess vs production.
    phaseo_trailing = rolling_excess(returns_map[PHASEO_REFERENCE], returns_map[PRODUCTION_PIN]).reindex(feature_frame.index).fillna(0.0)
    phasen_trailing = rolling_excess(returns_map[PHASEN_REFERENCE], returns_map[PRODUCTION_PIN]).reindex(feature_frame.index).fillna(0.0)

    # S1 — defense_production reshape (R2 overlay preserved).
    s1_weights, s1_controls = build_candidate(
        version_name="improved_phases_defense_reshape_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_trailing_excess=phaseo_trailing,
        phasen_trailing_excess=phasen_trailing,
        base_mix_table=S1_BASE_MIX,
        use_light_abstention=True,
        use_conditional_attenuator=False,
    )

    # S2 — conditional ML-share attenuator on R2 base mixes.
    s2_weights, s2_controls = build_candidate(
        version_name="improved_phases_conditional_ml_attenuator_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_trailing_excess=phaseo_trailing,
        phasen_trailing_excess=phasen_trailing,
        base_mix_table=R2_BASE_MIX,
        use_light_abstention=True,
        use_conditional_attenuator=True,
    )

    # S3 — combo S1 base + S2 attenuator.
    s3_weights, s3_controls = build_candidate(
        version_name="improved_phases_defense_reshape_ml_attenuator_combo",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_trailing_excess=phaseo_trailing,
        phasen_trailing_excess=phasen_trailing,
        base_mix_table=S1_BASE_MIX,
        use_light_abstention=True,
        use_conditional_attenuator=True,
    )

    weight_frames = {
        "improved_phases_defense_reshape_allocator": s1_weights,
        "improved_phases_conditional_ml_attenuator_allocator": s2_weights,
        "improved_phases_defense_reshape_ml_attenuator_combo": s3_weights,
    }
    control_frames = {
        "improved_phases_defense_reshape_allocator": s1_controls,
        "improved_phases_conditional_ml_attenuator_allocator": s2_controls,
        "improved_phases_defense_reshape_ml_attenuator_combo": s3_controls,
    }

    trust_overall_rows = []
    trust_state_rows = []
    bucket_rows = []
    for version_name, etf_weights in weight_frames.items():
        path = pp.save_meta_portfolio_version(version_name, etf_weights, next_week_returns)
        controls = control_frames[version_name]
        controls.to_csv(LAYER3_DIR / f"phase_s_controls_{version_name}.csv")
        overall, by_state = pq.trust_summary(version_name, controls)
        trust_overall_rows.append(overall)
        trust_state_rows.append(by_state)
        bucket_rows.append(pq.bucket_summary(version_name, controls))
        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        print(
            f"{version_name}: ann_return={ann_ret:.4f} "
            f"sharpe={(ann_ret / ann_vol) if ann_vol > 0 else float('nan'):.4f} "
            f"turnover={path['turnover'].dropna().mean():.4f}"
        )

    pd.concat(trust_overall_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_s_trust_summary.csv", index=False)
    pd.concat(trust_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_s_trust_by_state.csv", index=False)
    pd.concat(bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_s_bucket_summary.csv", index=False)

    results = build_validation_bundle(list(weight_frames.keys()))

    print("\n=== Phase S FULL metrics ===")
    cols = ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
            "recovery_capture", "raw_target_composite", "raw_composite_position"]
    print(results["full"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase S HOLDOUT metrics ===")
    print(results["holdout"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase S pairwise vs production + vs R2 ===")
    keep = [n for n in results["pairwise"]["version_name"]
            if n.startswith("improved_phases") or n == PHASER_R2_REFERENCE or n == PRODUCTION_PIN]
    pcols = ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
             "holdout_sharpe_delta_vs_production", "bootstrap_prob_vs_production",
             "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production",
             "full_raw_delta_vs_r2", "holdout_raw_delta_vs_r2",
             "holdout_sharpe_delta_vs_r2", "bootstrap_prob_vs_r2"]
    print(results["pairwise"].set_index("version_name").loc[keep, pcols].round(4).to_string())

    print("\n=== Phase S classification ===")
    print(results["classification"].set_index("version_name")[["classification", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production", "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production", "bootstrap_prob_vs_production"]].round(4).to_string())
    print("\nSaved Phase S artifacts.")


if __name__ == "__main__":
    main()
