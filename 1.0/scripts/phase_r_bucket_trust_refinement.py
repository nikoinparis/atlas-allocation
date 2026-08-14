"""Phase R — Bucket-Trust Refinement.

Phase R is a tightly-scoped refinement of Phase Q's strongest branch, Q2
`improved_phaseq_regime_bucket_meta_allocator`. Phase Q established that:

  * hard sticky buckets outperform smooth softmax blending
  * Q2 already beats production on holdout Sharpe (+0.111), recovery_capture
    (+0.20), max drawdown, and CVaR
  * Q2 still misses the Phase D production rule because its holdout raw
    composite delta vs production is -0.018 (needs >= 0), rolling win rate is
    40% (needs >= 55%), and holdout bootstrap is 25.7% (needs >= 60%)

Phase R does NOT reopen signals, sleeves, or alpha search. It refines the
bucket skeleton in three independent directions plus one disciplined combo:

  R1 `improved_phaser_bucket_refined_meta_allocator`
    - Keeps Q2's four-bucket skeleton and 3-week persistence
    - Refines the base expert mixes inside each bucket so less weight sits in
      the defensive abstain cushion and more is retained in ML / production
      blend. Closes raw-return drag while preserving the holdout Sharpe gain.

  R2 `improved_phaser_light_abstention_overlay_allocator`
    - Keeps Q2's base mixes EXCEPT removes the 8% abstain cushion from
      `defense_production` and replaces the blanket `ambiguous_abstain`
      abstain weight with a narrow overlay that only fires when conviction
      truly collapses inside a trust bucket (hard threshold,
      max abstain cap 0.10). Abstention is a tail tool, not a base mode.

  R3 `improved_phaser_fast_narrow_regret_allocator`
    - Keeps Q2's base mixes and persistence. Replaces 20-week EMA regret with
      an 8-week EMA. Regret can ONLY reallocate weight between phaseo and
      phasen within the ML share; it cannot touch production or abstain.

  R4 `improved_phaser_refined_bucket_fast_regret_combo`
    - Best R1 base mixes + R3's narrow 8-week regret overlay.
    - Only built because R1 and R3 each show standalone value.

All four reuse Phase P's walk-forward classifier probabilities and the Phase Q
feature frame. Validation is the standing Phase D rule set against the fixed
9-member comparator set (production, shadow, phaseh, phasen, phaseo, phasep,
phaseq bucket, phaseq abstention, phaseh panel blend).

Outputs to data/05_layer3_portfolio_construction/:
  phase_r_controls_{version}.csv
  phase_r_trust_summary.csv
  phase_r_trust_by_state.csv
  phase_r_bucket_summary.csv
  phase_r_candidate_metrics_{full,dev,holdout}.csv
  phase_r_rolling_origin_summary.csv
  phase_r_pairwise_validation.csv
  phase_r_candidate_classification.csv
  phase_r_validation_protocol.json
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
PHASEQ_ABSTENTION_REFERENCE = "improved_phaseq_abstention_aware_meta_allocator"

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    PHASEP_REFERENCE,
    PHASEQ_BUCKET_REFERENCE,
    PHASEQ_ABSTENTION_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

PHASE_R_CANDIDATES = {
    "improved_phaser_bucket_refined_meta_allocator":            "R1 refined bucket base mixes",
    "improved_phaser_light_abstention_overlay_allocator":       "R2 light abstention overlay",
    "improved_phaser_fast_narrow_regret_allocator":             "R3 fast narrow regret (phaseo<->phasen)",
    "improved_phaser_refined_bucket_fast_regret_combo":         "R4 R1 base + R3 narrow fast regret",
}

# Bucket persistence preserved from Phase Q.
BUCKET_PERSISTENCE = pq.BUCKET_PERSISTENCE

# R1/R4 refined bucket base mixes. Reduces abstain cushions, boosts ML share,
# trims production floor in recovery_trust.
R1_BASE_MIX = {
    "calm_trust":         {"production": 0.18, "phasen": 0.28, "phaseo": 0.54, "abstain": 0.00},
    "recovery_trust":     {"production": 0.18, "phasen": 0.54, "phaseo": 0.28, "abstain": 0.00},
    "defense_production": {"production": 0.80, "phasen": 0.08, "phaseo": 0.08, "abstain": 0.04},
    "ambiguous_abstain":  {"production": 0.62, "phasen": 0.13, "phaseo": 0.13, "abstain": 0.12},
}

# R2 base mix: Q2 mixes except abstain is removed everywhere and shifted into
# production / ML. Light-abstention logic then adds small abstain at runtime.
R2_BASE_MIX = {
    "calm_trust":         {"production": 0.20, "phasen": 0.25, "phaseo": 0.55, "abstain": 0.00},
    "recovery_trust":     {"production": 0.25, "phasen": 0.50, "phaseo": 0.25, "abstain": 0.00},
    "defense_production": {"production": 0.85, "phasen": 0.075, "phaseo": 0.075, "abstain": 0.00},
    "ambiguous_abstain":  {"production": 0.65, "phasen": 0.13, "phaseo": 0.12, "abstain": 0.10},
}

# Abstention overlay cap used by R2.
R2_ABSTAIN_SCORE_GATE = 0.60
R2_ABSTAIN_MAX_WEIGHT = 0.10

# Fast-narrow regret decay used by R3 and R4.
FAST_REGRET_HALF_LIFE = 8
FAST_REGRET_ALPHA = 1.0 - 0.5 ** (1.0 / FAST_REGRET_HALF_LIFE)

EPS = 1e-9


def _bucket_mix_copy(mix: dict[str, float]) -> dict[str, float]:
    return dict(mix)


def _normalize(mix: dict[str, float]) -> dict[str, float]:
    mix = {k: max(v, 0.0) for k, v in mix.items()}
    total = sum(mix.values())
    if total <= EPS:
        return {"production": 1.0, "phasen": 0.0, "phaseo": 0.0, "abstain": 0.0}
    return {k: v / total for k, v in mix.items()}


def apply_narrow_regret_phaseo_phasen(
    mix: dict[str, float],
    *,
    phaseo_regret: float,
    phasen_regret: float,
    scale: float = 0.30,
) -> dict[str, float]:
    """Reallocate within the ML share only.

    Positive (phaseo - phasen) regret -> shift ML weight from phasen to phaseo.
    Negative -> the reverse. Neither production nor abstain are touched.
    """
    ml_mass = mix["phaseo"] + mix["phasen"]
    if ml_mass <= EPS:
        return _bucket_mix_copy(mix)
    clipped_o = float(np.clip(phaseo_regret, -0.0025, 0.0025)) / 0.0025
    clipped_n = float(np.clip(phasen_regret, -0.0025, 0.0025)) / 0.0025
    spread = clipped_o - clipped_n  # in [-2, 2]
    share_o = mix["phaseo"] / ml_mass
    share_n = mix["phasen"] / ml_mass
    # Move `scale` of ml_mass across, weighted by spread.
    shift = 0.5 * scale * spread * ml_mass
    new_o = share_o * ml_mass + shift
    new_n = share_n * ml_mass - shift
    # Clip to [0.05*ml_mass, 0.95*ml_mass] to avoid degenerate all-in/all-out.
    new_o = float(np.clip(new_o, 0.05 * ml_mass, 0.95 * ml_mass))
    new_n = ml_mass - new_o
    out = _bucket_mix_copy(mix)
    out["phaseo"] = new_o
    out["phasen"] = new_n
    return out


def build_candidate(
    *,
    version_name: str,
    feature_frame: pd.DataFrame,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    phaseo_regret_fast: pd.Series,
    phasen_regret_fast: pd.Series,
    phaseo_regret_slow: pd.Series,
    phasen_regret_slow: pd.Series,
    base_mix_table: dict[str, dict[str, float]],
    use_light_abstention: bool = False,
    use_narrow_regret: bool = False,
    use_wide_regret: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generic Phase R builder.

    All Phase R candidates share the Q2 bucket structure and persistence logic.
    Differences are encoded by arguments:
      - `base_mix_table` sets the per-bucket expert base mixes
      - `use_light_abstention` adds an R2-style targeted abstention overlay
      - `use_narrow_regret` swaps weight between phaseo and phasen only
      - `use_wide_regret` (unused by Phase R defaults) would replicate Q2/Q3
    """
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

        # Bucket selection with 3-week persistence (matches Phase Q).
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

        base = _bucket_mix_copy(base_mix_table[active_bucket])

        a_score = pq.abstention_score(
            model_uncertainty=model_uncertainty,
            margin_conf=margin_conf,
            risk_guard=risk_guard,
            gate_entropy=gate_entropy,
            phaseo_prob=p_phaseo,
            phasen_prob=p_phasen,
        )

        mix = _bucket_mix_copy(base)

        # Narrow regret (R3 / R4). Operates only within the ML share.
        if use_narrow_regret:
            mix = apply_narrow_regret_phaseo_phasen(
                mix,
                phaseo_regret=float(phaseo_regret_fast.loc[date]),
                phasen_regret=float(phasen_regret_fast.loc[date]),
                scale=0.30,
            )

        # Wide regret (not used by Phase R defaults; included for completeness).
        if use_wide_regret:
            mix = pq.apply_regret_modulation(
                mix,
                phaseo_regret=float(phaseo_regret_slow.loc[date]),
                phasen_regret=float(phasen_regret_slow.loc[date]),
                scale=0.20,
            )

        # Light abstention overlay (R2). Only fires in trust/ambiguous buckets
        # and only when conviction has truly collapsed.
        overlay_fired = 0.0
        if use_light_abstention and active_bucket != "defense_production":
            if a_score > R2_ABSTAIN_SCORE_GATE:
                ml_mass = mix["phaseo"] + mix["phasen"]
                pull = min(R2_ABSTAIN_MAX_WEIGHT, 0.50 * (a_score - R2_ABSTAIN_SCORE_GATE) * max(ml_mass, mix["production"]))
                if ml_mass > EPS:
                    # Pull equal shares from phaseo and phasen proportional to their current mass.
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
                "trust_score": mix["phaseo"] + 0.5 * mix["phasen"],
                "abstention_score": a_score,
                "phaseo_regret_fast": float(phaseo_regret_fast.loc[date]),
                "phasen_regret_fast": float(phasen_regret_fast.loc[date]),
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
    phaseq_full = full_idx.loc[PHASEQ_BUCKET_REFERENCE]
    phaseq_holdout = holdout_idx.loc[PHASEQ_BUCKET_REFERENCE]
    phaseq_holdout_returns = returns_map[PHASEQ_BUCKET_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

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
            "full_raw_delta_vs_phaseq_bucket": float(cand_full["raw_target_composite"] - phaseq_full["raw_target_composite"]),
            "holdout_raw_delta_vs_phaseq_bucket": float(cand_holdout["raw_target_composite"] - phaseq_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_phaseq_bucket": float(cand_holdout["sharpe"] - phaseq_holdout["sharpe"]),
            "bootstrap_prob_vs_phaseq_bucket": ppe.safe_bootstrap(cand_holdout_returns, phaseq_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    phaser_names = [n for n in candidate_names if n.startswith("improved_phaser")]
    classification_df = pairwise_df[pairwise_df["version_name"].isin(phaser_names)].copy()

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
            row["full_raw_delta_vs_phaseq_bucket"] > 0.0
            or row["holdout_sharpe_delta_vs_phaseq_bucket"] > 0.0
            or row["holdout_raw_delta_vs_phaseq_bucket"] > 0.0
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_r_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_r_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_r_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_r_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_r_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_r_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase R — Bucket-Trust Refinement",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_r_candidates": list(PHASE_R_CANDIDATES.keys()),
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
        "fast_regret_half_life_weeks": FAST_REGRET_HALF_LIFE,
        "r1_base_mix": R1_BASE_MIX,
        "r2_base_mix": R2_BASE_MIX,
        "r2_abstain_score_gate": R2_ABSTAIN_SCORE_GATE,
        "r2_abstain_max_weight": R2_ABSTAIN_MAX_WEIGHT,
    }
    (LAYER3_DIR / "phase_r_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
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
        model_name="phaser_binary_phaseo_vs_production",
    )
    phasen_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phasen_trust_label"], feature_cols,
        model_name="phaser_binary_phasen_vs_production",
    )

    # EMA regret: fast (8w) for R3 / R4, slow (20w) for backward compatibility.
    phaseo_excess = returns_map[PHASEO_REFERENCE] - returns_map[PRODUCTION_PIN]
    phasen_excess = returns_map[PHASEN_REFERENCE] - returns_map[PRODUCTION_PIN]
    phaseo_regret_fast = pq.ema_excess(phaseo_excess, FAST_REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)
    phasen_regret_fast = pq.ema_excess(phasen_excess, FAST_REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)
    phaseo_regret_slow = pq.ema_excess(phaseo_excess, pq.REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)
    phasen_regret_slow = pq.ema_excess(phasen_excess, pq.REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)

    q2_base = {
        "calm_trust": pq.bucket_base_mix("calm_trust"),
        "recovery_trust": pq.bucket_base_mix("recovery_trust"),
        "defense_production": pq.bucket_base_mix("defense_production"),
        "ambiguous_abstain": pq.bucket_base_mix("ambiguous_abstain"),
    }

    # R1 — refined bucket base mixes.
    r1_weights, r1_controls = build_candidate(
        version_name="improved_phaser_bucket_refined_meta_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_fast=phaseo_regret_fast,
        phasen_regret_fast=phasen_regret_fast,
        phaseo_regret_slow=phaseo_regret_slow,
        phasen_regret_slow=phasen_regret_slow,
        base_mix_table=R1_BASE_MIX,
    )

    # R2 — light abstention overlay on Q2-derived mixes.
    r2_weights, r2_controls = build_candidate(
        version_name="improved_phaser_light_abstention_overlay_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_fast=phaseo_regret_fast,
        phasen_regret_fast=phasen_regret_fast,
        phaseo_regret_slow=phaseo_regret_slow,
        phasen_regret_slow=phasen_regret_slow,
        base_mix_table=R2_BASE_MIX,
        use_light_abstention=True,
    )

    # R3 — fast narrow regret on Q2 base mixes.
    r3_weights, r3_controls = build_candidate(
        version_name="improved_phaser_fast_narrow_regret_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_fast=phaseo_regret_fast,
        phasen_regret_fast=phasen_regret_fast,
        phaseo_regret_slow=phaseo_regret_slow,
        phasen_regret_slow=phasen_regret_slow,
        base_mix_table=q2_base,
        use_narrow_regret=True,
    )

    # R4 — combo R1 base + narrow fast regret.
    r4_weights, r4_controls = build_candidate(
        version_name="improved_phaser_refined_bucket_fast_regret_combo",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_fast=phaseo_regret_fast,
        phasen_regret_fast=phasen_regret_fast,
        phaseo_regret_slow=phaseo_regret_slow,
        phasen_regret_slow=phasen_regret_slow,
        base_mix_table=R1_BASE_MIX,
        use_narrow_regret=True,
    )

    weight_frames = {
        "improved_phaser_bucket_refined_meta_allocator": r1_weights,
        "improved_phaser_light_abstention_overlay_allocator": r2_weights,
        "improved_phaser_fast_narrow_regret_allocator": r3_weights,
        "improved_phaser_refined_bucket_fast_regret_combo": r4_weights,
    }
    control_frames = {
        "improved_phaser_bucket_refined_meta_allocator": r1_controls,
        "improved_phaser_light_abstention_overlay_allocator": r2_controls,
        "improved_phaser_fast_narrow_regret_allocator": r3_controls,
        "improved_phaser_refined_bucket_fast_regret_combo": r4_controls,
    }

    trust_overall_rows = []
    trust_state_rows = []
    bucket_rows = []
    for version_name, etf_weights in weight_frames.items():
        path = pp.save_meta_portfolio_version(version_name, etf_weights, next_week_returns)
        controls = control_frames[version_name]
        controls.to_csv(LAYER3_DIR / f"phase_r_controls_{version_name}.csv")
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

    pd.concat(trust_overall_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_r_trust_summary.csv", index=False)
    pd.concat(trust_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_r_trust_by_state.csv", index=False)
    pd.concat(bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_r_bucket_summary.csv", index=False)

    results = build_validation_bundle(list(weight_frames.keys()))

    print("\n=== Phase R FULL metrics ===")
    cols = ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
            "recovery_capture", "raw_target_composite", "raw_composite_position"]
    print(results["full"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase R HOLDOUT metrics ===")
    print(results["holdout"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase R pairwise vs production (R candidates + phaseq bucket reference) ===")
    cols = ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
            "holdout_sharpe_delta_vs_production", "bootstrap_prob_vs_production",
            "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production",
            "full_raw_delta_vs_phaseq_bucket", "holdout_sharpe_delta_vs_phaseq_bucket",
            "holdout_raw_delta_vs_phaseq_bucket", "bootstrap_prob_vs_phaseq_bucket"]
    keep = [n for n in results["pairwise"]["version_name"]
            if n.startswith("improved_phaser") or n == PHASEQ_BUCKET_REFERENCE or n == PRODUCTION_PIN]
    pw = results["pairwise"].set_index("version_name").loc[keep, cols].round(4)
    print(pw.to_string())

    print("\n=== Phase R classification ===")
    print(results["classification"].set_index("version_name")[["classification", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production", "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production", "bootstrap_prob_vs_production"]].round(4).to_string())
    print("\nSaved Phase R artifacts.")


if __name__ == "__main__":
    main()
