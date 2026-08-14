"""Phase T — Regime Engine Softening / Layer 2B Revisit.

Phase T is the first upstream sprint since the project turned to ML meta
allocators. Phases Q/R/S exhausted the trust-layer frontier. All three
sprints left the same residual: holdout raw composite Δ vs production stuck
at -0.013, rolling win-rate stuck near 40-47%, bootstrap stuck near 40-47%.
Phase S's diagnostic concluded explicitly that the residual is no longer
addressable from Layer 3 — it is baked into the hard `market_state` label
and into the hard regime-bucket assignment built on top of it.

Phase T tests that hypothesis narrowly: replace the hard per-week bucket
assignment with a causal soft posterior over the same four buckets, and see
whether the downstream allocator behaves better near state boundaries.

Three candidates only:

  T1 `improved_phaset_soft_regime_posterior_allocator`
    - Softens the bucket assignment from a deterministic rule to a
      probability distribution computed per week from the same causal
      features the hard rule already used.
    - Keeps Phase R/S's base mixes per bucket, the 3-week persistence, and
      the light-abstention overlay.
    - Expert mix per week = sum over buckets (bucket_posterior * base_mix).
    - Diagnostic: how often the soft posterior disagrees with the hard
      bucket, how concentrated the posterior is, which weeks are actually
      boundary weeks.

  T2 `improved_phaset_soft_trust_weighted_allocator`
    - Builds on T1 but adds an uncertainty-aware trust pull: when the soft
      posterior is diffuse (max bucket probability < 0.55), the overall
      mix is linearly pulled toward the production-heavy `defense_production`
      base mix. When the posterior is concentrated, it behaves like T1.
    - Designed to fix boundary weeks specifically, where the hard rule
      guesses and the trust layer inherits the guess.

  T3 `improved_phaset_production_anchored_soft_combo`
    - Builds on T2 and adds a "production anchor at the ETF level" during
      high-uncertainty weeks: a small slice of the final weight is explicitly
      blended with production's actual ETF weights on top of the bucket
      averaging. This is the explicit implementation of Phase S's
      recommendation #2 — let the portfolio look more like production
      exactly when the regime engine is uncertain, without forcing it
      elsewhere.

Causal / walk-forward safety:
  - The posterior is a closed-form, handcrafted softmax over the same
    deterministic, per-week causal features the hard rule already consumes.
    No new fitted model, no new training window, no lookahead.
  - The trailing-excess signals and classifier probabilities reused from
    Phase P / S are already walk-forward safe.
  - The soft posterior's 3-week EMA smoothing uses only past probabilities.

Outputs to data/05_layer3_portfolio_construction/:
  phase_t_controls_{version}.csv
  phase_t_trust_summary.csv
  phase_t_trust_by_state.csv
  phase_t_bucket_summary.csv
  phase_t_posterior_summary.csv          [T-specific]
  phase_t_candidate_metrics_{full,dev,holdout}.csv
  phase_t_rolling_origin_summary.csv
  phase_t_pairwise_validation.csv
  phase_t_candidate_classification.csv
  phase_t_validation_protocol.json
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

PHASE_T_CANDIDATES = {
    "improved_phaset_soft_regime_posterior_allocator": "T1 soft regime posterior over 4 buckets",
    "improved_phaset_soft_trust_weighted_allocator":   "T2 T1 + uncertainty-aware defensive pull",
    "improved_phaset_production_anchored_soft_combo":  "T3 T2 + ETF-level production anchor on boundary",
}

BUCKETS = ["calm_trust", "recovery_trust", "defense_production", "ambiguous_abstain"]

# R2 base mixes reused so comparability with Phase S is clean.
R2_BASE_MIX = {
    "calm_trust":         {"production": 0.20, "phasen": 0.25, "phaseo": 0.55, "abstain": 0.00},
    "recovery_trust":     {"production": 0.25, "phasen": 0.50, "phaseo": 0.25, "abstain": 0.00},
    "defense_production": {"production": 0.85, "phasen": 0.075, "phaseo": 0.075, "abstain": 0.00},
    "ambiguous_abstain":  {"production": 0.65, "phasen": 0.13, "phaseo": 0.12, "abstain": 0.10},
}

# Light abstention overlay (R2-style) settings.
R2_ABSTAIN_SCORE_GATE = 0.60
R2_ABSTAIN_MAX_WEIGHT = 0.10

# Soft posterior settings.
POSTERIOR_EMA_HALF_LIFE = 3  # weeks; smooth the posterior so small flickers don't flip behavior.
POSTERIOR_EMA_ALPHA = 1.0 - 0.5 ** (1.0 / POSTERIOR_EMA_HALF_LIFE)

# Softmax temperature on the handcrafted bucket scores.
POSTERIOR_TEMPERATURE = 0.45

# T2 defensive pull settings.
T2_SHARPNESS_LOW = 0.40   # max-prob below this => full defensive pull
T2_SHARPNESS_HIGH = 0.65  # max-prob above this => no defensive pull
T2_DEFENSIVE_PULL_MAX = 0.30  # up to 30% of the mix is replaced with defense_production

# T3 production-anchor settings.
T3_ANCHOR_MAX = 0.15  # up to 15% of the final ETF weight replaced with production on high-uncertainty weeks
T3_ANCHOR_LOW = 0.40  # max-prob below this => full anchor
T3_ANCHOR_HIGH = 0.60  # max-prob above this => no anchor

EPS = 1e-9


# --------------------------------------------------------------------------
#                       soft bucket posterior
# --------------------------------------------------------------------------

def _bucket_raw_scores(
    *,
    state_text: str,
    calm_conf: float,
    recovery_conf: float,
    stress_conf: float,
    chop_conf: float,
    model_confidence: float,
    model_uncertainty: float,
    margin_conf: float,
    risk_guard: float,
    gate_entropy: float,
    agreement: float,
) -> dict[str, float]:
    """Per-week affinity scores for each of the four buckets.

    Handcrafted so the argmax approximately recovers the Phase Q hard rule
    but softens it at the boundaries. Scores are unnormalized (a softmax is
    applied downstream with temperature).
    """
    # Calm-trust: calm regime + calm conviction + low uncertainty.
    calm_state_boost = 1.0 if state_text == "calm_trend" else 0.0
    calm_score = (
        0.55 * calm_conf
        + 0.30 * (1.0 - model_uncertainty)
        + 0.25 * margin_conf
        + 0.35 * calm_state_boost
        - 0.30 * risk_guard
        - 0.15 * stress_conf
    )

    # Recovery-trust: recovery or mild-stress + agreement + non-defensive.
    recovery_state_boost = (
        1.0 if state_text in ("recovery_confirmed", "recovery_fragile") else 0.0
    )
    stressed_with_agreement = (
        1.0 if (state_text == "stressed_panic" and agreement >= 0.45 and margin_conf >= 0.40) else 0.0
    )
    recovery_score = (
        0.50 * recovery_conf
        + 0.30 * agreement
        + 0.20 * margin_conf
        + 0.35 * recovery_state_boost
        + 0.20 * stressed_with_agreement
        - 0.30 * risk_guard
        - 0.15 * stress_conf
    )

    # Defense-production: high risk_guard / stress with weak conviction.
    defense_score = (
        0.50 * risk_guard
        + 0.30 * stress_conf
        + 0.25 * model_uncertainty
        + 0.20 * (1.0 - margin_conf)
        - 0.25 * calm_conf
        - 0.25 * recovery_conf
    )

    # Ambiguous-abstain: mushy / uncertain midstates.
    chop_like = (
        0.20 if state_text in ("neutral_mixed",) else 0.0
    )
    ambig_score = (
        0.40 * model_uncertainty
        + 0.30 * (1.0 - margin_conf)
        + 0.25 * gate_entropy
        + 0.15 * chop_conf
        + chop_like
        - 0.25 * calm_conf
        - 0.25 * recovery_conf
        - 0.20 * risk_guard
    )

    return {
        "calm_trust":         float(calm_score),
        "recovery_trust":     float(recovery_score),
        "defense_production": float(defense_score),
        "ambiguous_abstain":  float(ambig_score),
    }


def soft_posterior(scores: dict[str, float], temperature: float = POSTERIOR_TEMPERATURE) -> dict[str, float]:
    """Softmax over bucket affinity scores with a temperature parameter."""
    vals = np.array([scores[b] for b in BUCKETS], dtype=float) / max(temperature, 1e-3)
    vals = vals - vals.max()
    exps = np.exp(vals)
    tot = exps.sum()
    if tot <= EPS:
        return {b: 1.0 / len(BUCKETS) for b in BUCKETS}
    return {b: float(exps[i] / tot) for i, b in enumerate(BUCKETS)}


def smooth_posterior_series(posterior_rows: list[dict[str, float]], alpha: float = POSTERIOR_EMA_ALPHA) -> list[dict[str, float]]:
    """3-week-half-life EMA of the per-week posterior. Causal (uses only past)."""
    if not posterior_rows:
        return posterior_rows
    smoothed = [dict(posterior_rows[0])]
    for i in range(1, len(posterior_rows)):
        prev = smoothed[i - 1]
        cur = posterior_rows[i]
        blend = {b: alpha * cur[b] + (1 - alpha) * prev[b] for b in BUCKETS}
        # Renormalize to guard against float drift.
        total = sum(blend.values())
        if total > EPS:
            blend = {b: v / total for b, v in blend.items()}
        smoothed.append(blend)
    return smoothed


def weighted_mix_from_posterior(
    posterior: dict[str, float],
    base_mix_table: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Blend per-bucket base mixes by the posterior."""
    out = {"production": 0.0, "phasen": 0.0, "phaseo": 0.0, "abstain": 0.0}
    for bucket, prob in posterior.items():
        base = base_mix_table[bucket]
        for k in out:
            out[k] += prob * base[k]
    total = sum(out.values())
    if total > EPS:
        out = {k: v / total for k, v in out.items()}
    return out


def _normalize(mix: dict[str, float]) -> dict[str, float]:
    mix = {k: max(v, 0.0) for k, v in mix.items()}
    total = sum(mix.values())
    if total <= EPS:
        return {"production": 1.0, "phasen": 0.0, "phaseo": 0.0, "abstain": 0.0}
    return {k: v / total for k, v in mix.items()}


# --------------------------------------------------------------------------
#                         candidate builder
# --------------------------------------------------------------------------

def build_candidate(
    *,
    version_name: str,
    feature_frame: pd.DataFrame,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    base_mix_table: dict[str, dict[str, float]],
    use_light_abstention: bool = True,
    use_defensive_pull: bool = False,        # T2 / T3
    use_production_anchor: bool = False,     # T3
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Soft-posterior allocator. Differs from S-family only in how the
    bucket mapping is computed and whether defensive pull / production
    anchor overlays fire."""
    prod_w = weights_map[PRODUCTION_PIN]
    phasen_w = weights_map[PHASEN_REFERENCE]
    phaseo_w = weights_map[PHASEO_REFERENCE]
    columns = list(prod_w.columns)
    anchor_vec = pq.abstain_anchor(columns)

    # First pass: compute raw posteriors.
    raw_posterior_rows: list[dict[str, float]] = []
    hard_bucket_rows: list[str] = []
    per_row_meta: list[dict] = []

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

        scores = _bucket_raw_scores(
            state_text=st,
            calm_conf=calm_conf,
            recovery_conf=recovery_conf,
            stress_conf=stress_conf,
            chop_conf=chop_conf,
            model_confidence=model_confidence,
            model_uncertainty=model_uncertainty,
            margin_conf=margin_conf,
            risk_guard=risk_guard,
            gate_entropy=gate_entropy,
            agreement=agreement,
        )
        posterior = soft_posterior(scores, temperature=POSTERIOR_TEMPERATURE)
        hard_bucket = pq.compute_regime_bucket(
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

        raw_posterior_rows.append(posterior)
        hard_bucket_rows.append(hard_bucket)
        per_row_meta.append({
            "date": date,
            "state_text": st,
            "model_uncertainty": model_uncertainty,
            "margin_confidence": margin_conf,
            "risk_guard": risk_guard,
            "gate_entropy": gate_entropy,
            "phaseo_prob": float(phaseo_prob.loc[date]),
            "phasen_prob": float(phasen_prob.loc[date]),
        })

    # Second pass: smooth the posterior with a 3-week EMA so small flickers
    # don't induce turnover.
    smoothed_posterior_rows = smooth_posterior_series(raw_posterior_rows, alpha=POSTERIOR_EMA_ALPHA)

    rows: list[pd.Series] = []
    ctrl_rows: list[pd.Series] = []

    for i, date in enumerate(feature_frame.index):
        posterior = smoothed_posterior_rows[i]
        raw_posterior = raw_posterior_rows[i]
        meta = per_row_meta[i]
        hard_bucket = hard_bucket_rows[i]

        # Argmax of smoothed posterior — the "effective bucket" for reporting.
        effective_bucket = max(posterior.items(), key=lambda kv: kv[1])[0]
        max_prob = posterior[effective_bucket]

        # Bucket-weighted mix from the posterior.
        mix = weighted_mix_from_posterior(posterior, base_mix_table)

        # T2 defensive pull on diffuse posteriors.
        defensive_pull_applied = 0.0
        if use_defensive_pull:
            if max_prob <= T2_SHARPNESS_LOW:
                defensive_pull_applied = T2_DEFENSIVE_PULL_MAX
            elif max_prob >= T2_SHARPNESS_HIGH:
                defensive_pull_applied = 0.0
            else:
                frac = (T2_SHARPNESS_HIGH - max_prob) / (T2_SHARPNESS_HIGH - T2_SHARPNESS_LOW)
                defensive_pull_applied = T2_DEFENSIVE_PULL_MAX * frac
            if defensive_pull_applied > EPS:
                defensive_mix = base_mix_table["defense_production"]
                mix = {
                    k: (1 - defensive_pull_applied) * mix[k] + defensive_pull_applied * defensive_mix[k]
                    for k in mix
                }

        mix = _normalize(mix)

        # Light abstention overlay — only fires when the effective bucket is
        # not defense and there is meaningful ML mass.
        a_score = pq.abstention_score(
            model_uncertainty=meta["model_uncertainty"],
            margin_conf=meta["margin_confidence"],
            risk_guard=meta["risk_guard"],
            gate_entropy=meta["gate_entropy"],
            phaseo_prob=meta["phaseo_prob"],
            phasen_prob=meta["phasen_prob"],
        )
        overlay_fired = 0.0
        if use_light_abstention and effective_bucket != "defense_production":
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

        # Compose the raw ETF weights from the expert mix.
        w = (
            mix["production"] * prod_w.loc[date]
            + mix["phasen"] * phasen_w.loc[date]
            + mix["phaseo"] * phaseo_w.loc[date]
            + mix["abstain"] * anchor_vec
        ).reindex(columns).fillna(0.0)

        # T3 ETF-level production anchor on high-uncertainty weeks.
        anchor_frac_applied = 0.0
        if use_production_anchor:
            if max_prob <= T3_ANCHOR_LOW:
                anchor_frac_applied = T3_ANCHOR_MAX
            elif max_prob >= T3_ANCHOR_HIGH:
                anchor_frac_applied = 0.0
            else:
                frac = (T3_ANCHOR_HIGH - max_prob) / (T3_ANCHOR_HIGH - T3_ANCHOR_LOW)
                anchor_frac_applied = T3_ANCHOR_MAX * frac
            if anchor_frac_applied > EPS:
                w = (1 - anchor_frac_applied) * w + anchor_frac_applied * prod_w.loc[date]

        # Renormalize the final ETF weights just in case.
        total_w = w.sum()
        if total_w > EPS:
            w = w / total_w
        rows.append(w.rename(date))

        selected = max(mix.items(), key=lambda kv: kv[1])[0]
        ctrl_rows.append(pd.Series(
            {
                "state_text": meta["state_text"],
                "hard_bucket": hard_bucket,
                "effective_bucket": effective_bucket,
                "posterior_calm_trust": posterior["calm_trust"],
                "posterior_recovery_trust": posterior["recovery_trust"],
                "posterior_defense_production": posterior["defense_production"],
                "posterior_ambiguous_abstain": posterior["ambiguous_abstain"],
                "posterior_max_prob": max_prob,
                "raw_posterior_max_prob": max(raw_posterior.values()),
                "production_weight": mix["production"],
                "phasen_weight": mix["phasen"],
                "phaseo_weight": mix["phaseo"],
                "abstain_weight": mix["abstain"],
                "overlay_abstain_added": overlay_fired,
                "defensive_pull_applied": defensive_pull_applied,
                "production_anchor_applied": anchor_frac_applied,
                "trust_score": mix["phaseo"] + 0.5 * mix["phasen"],
                "abstention_score": a_score,
                "phaseo_prob": meta["phaseo_prob"],
                "phasen_prob": meta["phasen_prob"],
                "model_uncertainty": meta["model_uncertainty"],
                "margin_confidence": meta["margin_confidence"],
                "risk_guard": meta["risk_guard"],
                "gate_entropy": meta["gate_entropy"],
                "selected_expert": selected,
                # Use effective_bucket as the "bucket" column for downstream
                # compatibility with pq.bucket_summary().
                "bucket": effective_bucket,
            },
            name=date,
        ))

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(ctrl_rows).sort_index()


# --------------------------------------------------------------------------
#                  posterior diagnostics
# --------------------------------------------------------------------------

def posterior_summary(version_name: str, controls: pd.DataFrame) -> pd.DataFrame:
    if "posterior_max_prob" not in controls.columns:
        return pd.DataFrame()
    hard = controls["hard_bucket"]
    soft = controls["effective_bucket"]
    disagree = (hard != soft)
    max_prob = controls["posterior_max_prob"]
    rows = [{
        "version_name": version_name,
        "observations": int(len(controls)),
        "hard_vs_soft_disagreement_share": float(disagree.mean()),
        "avg_posterior_max_prob": float(max_prob.mean()),
        "median_posterior_max_prob": float(max_prob.median()),
        "share_high_confidence_weeks_max_prob_ge_065": float((max_prob >= 0.65).mean()),
        "share_boundary_weeks_max_prob_lt_055": float((max_prob < 0.55).mean()),
        "share_diffuse_weeks_max_prob_lt_045": float((max_prob < 0.45).mean()),
        "avg_defensive_pull_applied": float(controls.get("defensive_pull_applied", pd.Series(0.0)).mean()),
        "avg_production_anchor_applied": float(controls.get("production_anchor_applied", pd.Series(0.0)).mean()),
    }]
    return pd.DataFrame(rows)


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
    r2_full = full_idx.loc[PHASER_R2_REFERENCE]
    r2_holdout = holdout_idx.loc[PHASER_R2_REFERENCE]
    r2_holdout_returns = returns_map[PHASER_R2_REFERENCE].tail(pdv.HOLDOUT_WEEKS)
    r3_full = full_idx.loc[PHASER_R3_REFERENCE]
    r3_holdout = holdout_idx.loc[PHASER_R3_REFERENCE]
    r3_holdout_returns = returns_map[PHASER_R3_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

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
            "full_raw_delta_vs_r3": float(cand_full["raw_target_composite"] - r3_full["raw_target_composite"]),
            "holdout_raw_delta_vs_r3": float(cand_holdout["raw_target_composite"] - r3_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_r3": float(cand_holdout["sharpe"] - r3_holdout["sharpe"]),
            "bootstrap_prob_vs_r3": ppe.safe_bootstrap(cand_holdout_returns, r3_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    phaset_names = [n for n in candidate_names if n.startswith("improved_phaset")]
    classification_df = pairwise_df[pairwise_df["version_name"].isin(phaset_names)].copy()

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
            or row["holdout_sharpe_delta_vs_r3"] > 0.0
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_t_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_t_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_t_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_t_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_t_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_t_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase T — Regime Engine Softening / Layer 2B Revisit",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_t_candidates": list(PHASE_T_CANDIDATES.keys()),
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "posterior": {
            "temperature": POSTERIOR_TEMPERATURE,
            "ema_half_life_weeks": POSTERIOR_EMA_HALF_LIFE,
            "buckets": BUCKETS,
        },
        "t2": {"sharpness_low": T2_SHARPNESS_LOW, "sharpness_high": T2_SHARPNESS_HIGH, "defensive_pull_max": T2_DEFENSIVE_PULL_MAX},
        "t3": {"anchor_low": T3_ANCHOR_LOW, "anchor_high": T3_ANCHOR_HIGH, "anchor_max": T3_ANCHOR_MAX},
    }
    (LAYER3_DIR / "phase_t_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
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
    feature_frame, returns_map, weights_map, target_frame, next_week_returns, market_state_history = pp.build_feature_frame()

    feature_cols = [c for c in feature_frame.columns if c != "state_text"]

    phaseo_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phaseo_trust_label"], feature_cols,
        model_name="phaset_binary_phaseo_vs_production",
    )
    phasen_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phasen_trust_label"], feature_cols,
        model_name="phaset_binary_phasen_vs_production",
    )

    # T1: soft posterior only.
    t1_weights, t1_controls = build_candidate(
        version_name="improved_phaset_soft_regime_posterior_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        base_mix_table=R2_BASE_MIX,
        use_light_abstention=True,
        use_defensive_pull=False,
        use_production_anchor=False,
    )

    # T2: soft posterior + defensive pull on diffuse weeks.
    t2_weights, t2_controls = build_candidate(
        version_name="improved_phaset_soft_trust_weighted_allocator",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        base_mix_table=R2_BASE_MIX,
        use_light_abstention=True,
        use_defensive_pull=True,
        use_production_anchor=False,
    )

    # T3: T2 + ETF-level production anchor on diffuse weeks.
    t3_weights, t3_controls = build_candidate(
        version_name="improved_phaset_production_anchored_soft_combo",
        feature_frame=feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        base_mix_table=R2_BASE_MIX,
        use_light_abstention=True,
        use_defensive_pull=True,
        use_production_anchor=True,
    )

    weight_frames = {
        "improved_phaset_soft_regime_posterior_allocator": t1_weights,
        "improved_phaset_soft_trust_weighted_allocator": t2_weights,
        "improved_phaset_production_anchored_soft_combo": t3_weights,
    }
    control_frames = {
        "improved_phaset_soft_regime_posterior_allocator": t1_controls,
        "improved_phaset_soft_trust_weighted_allocator": t2_controls,
        "improved_phaset_production_anchored_soft_combo": t3_controls,
    }

    trust_overall_rows = []
    trust_state_rows = []
    bucket_rows = []
    posterior_rows = []
    for version_name, etf_weights in weight_frames.items():
        path = pp.save_meta_portfolio_version(version_name, etf_weights, next_week_returns)
        controls = control_frames[version_name]
        controls.to_csv(LAYER3_DIR / f"phase_t_controls_{version_name}.csv")
        overall, by_state = pq.trust_summary(version_name, controls)
        trust_overall_rows.append(overall)
        trust_state_rows.append(by_state)
        bucket_rows.append(pq.bucket_summary(version_name, controls))
        posterior_rows.append(posterior_summary(version_name, controls))
        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        print(
            f"{version_name}: ann_return={ann_ret:.4f} "
            f"sharpe={(ann_ret / ann_vol) if ann_vol > 0 else float('nan'):.4f} "
            f"turnover={path['turnover'].dropna().mean():.4f}"
        )

    pd.concat(trust_overall_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_t_trust_summary.csv", index=False)
    pd.concat(trust_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_t_trust_by_state.csv", index=False)
    pd.concat(bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_t_bucket_summary.csv", index=False)
    pd.concat(posterior_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_t_posterior_summary.csv", index=False)

    results = build_validation_bundle(list(weight_frames.keys()))

    print("\n=== Phase T FULL metrics ===")
    cols = ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
            "recovery_capture", "raw_target_composite", "raw_composite_position"]
    print(results["full"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase T HOLDOUT metrics ===")
    print(results["holdout"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase T pairwise vs production + vs R2 / R3 ===")
    keep = [n for n in results["pairwise"]["version_name"]
            if n.startswith("improved_phaset") or n in {PHASER_R2_REFERENCE, PHASER_R3_REFERENCE, PRODUCTION_PIN}]
    pcols = ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
             "holdout_sharpe_delta_vs_production", "bootstrap_prob_vs_production",
             "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production",
             "full_raw_delta_vs_r2", "holdout_raw_delta_vs_r2",
             "holdout_sharpe_delta_vs_r2", "bootstrap_prob_vs_r2",
             "holdout_sharpe_delta_vs_r3", "bootstrap_prob_vs_r3"]
    print(results["pairwise"].set_index("version_name").loc[keep, pcols].round(4).to_string())

    print("\n=== Phase T classification ===")
    print(results["classification"].set_index("version_name")[["classification", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production", "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production", "bootstrap_prob_vs_production"]].round(4).to_string())

    print("\n=== Phase T posterior diagnostics ===")
    print(pd.concat(posterior_rows, ignore_index=True).round(4).to_string(index=False))
    print("\nSaved Phase T artifacts.")


if __name__ == "__main__":
    main()
