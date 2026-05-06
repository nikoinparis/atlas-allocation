"""ML Phase 2 — Decision-Aware Portfolio Allocation.

Phase O takes the ML Phase 1 outputs produced by Phase N (decision predictions,
tail predictions, per-sleeve uncertainty, MoE gate probabilities, etc.) and
re-uses them to build five decision-aware allocators that push in distinct,
non-redundant directions:

  - P2-A uncertainty-aware       (improved_phaseo_uncertainty_shrunk_allocator)
  - P2-B turnover-aware          (improved_phaseo_turnover_gated_allocator)
  - P2-C tail-aware              (improved_phaseo_tail_priority_allocator)
  - P2-D production-proximity    (improved_phaseo_production_proximity_allocator)
  - P2-E best justified combo    (improved_phaseo_combo_decision_allocator)

No retraining happens here. This sprint is strictly about the allocation step:
turning the same ML Phase 1 confidence/uncertainty/tail predictions into
different weight paths, then validating each under the Phase D discipline
(full-history, dev, 104-week holdout, rolling origin, 13-week block bootstrap
vs production) against the fixed comparator set.

Output artifacts in data/05_layer3_portfolio_construction/:
  phase_o_allocator_variant_summary.csv
  phase_o_allocator_state_summary.csv
  phase_o_sleeve_allocation_summary.csv
  phase_o_sleeve_allocation_by_state.csv
  phase_o_concentration_summary.csv
  phase_o_concentration_by_state.csv
  phase_o_uncertainty_summary.csv
  phase_o_controls_{version_name}.csv
  phase_o_candidate_metrics_{full,dev,holdout}.csv
  phase_o_pairwise_vs_production.csv
  phase_o_rolling_origin_summary.csv
  phase_o_validation_protocol.json
  portfolio_version_{returns,weights,sleeve_weights}_{version_name}.csv (each candidate)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import phase_d_validate as pdv
import phase_h_refined_panel_allocator as ph
import phase_i_refined_allocator_refinement as pi
import phase_j_structural_allocator as pj
import phase_k_allocator_framework as pk


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

# -- References into existing allocator lineage -----------------------------

CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
CURRENT_LEARNING_BRANCH = "improved_phasel_tail_turnover_learning_allocator"
TAIL_AWARE_BRANCH = "improved_phasek_tail_aware_role_framework"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"
DISTRIBUTIONAL_TAIL_BRANCH = "improved_phasen_distributional_tail_allocator"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN = "improved_phase2b_combo_abc"

# Fixed comparator set for ML Phase 2 as specified in the sprint brief.
FIXED_COMPARATORS = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    CURRENT_REFINED_REFERENCE,
    DISTRIBUTIONAL_TAIL_BRANCH,
    CURRENT_LEARNING_BRANCH,
    ACTIVE_PANEL_BASELINE,
]

PHASE_O_CANDIDATES = {
    "improved_phaseo_uncertainty_shrunk_allocator":    "P2-A uncertainty-shrunk decision allocator",
    "improved_phaseo_turnover_gated_allocator":        "P2-B turnover-gated decision allocator",
    "improved_phaseo_tail_priority_allocator":         "P2-C tail-priority decision allocator",
    "improved_phaseo_production_proximity_allocator":  "P2-D production-proximity decision allocator",
    "improved_phaseo_combo_decision_allocator":        "P2-E best-justified decision allocator",
}

EPS = 1e-9


def normalize(weights: pd.Series) -> pd.Series:
    clean = pd.Series(weights, dtype=float).reindex(ph.ACTIVE_PANEL).fillna(0.0).clip(lower=0.0)
    total = float(clean.sum())
    if total <= 0.0:
        return pd.Series(1.0 / len(ph.ACTIVE_PANEL), index=ph.ACTIVE_PANEL, dtype=float)
    return clean / total


def load_phase_n_predictions(index: pd.Index) -> dict[str, pd.DataFrame]:
    """Load ML Phase 1 outputs produced by Phase N, reindex to allocator index."""
    def read(name: str) -> pd.DataFrame:
        fp = LAYER3_DIR / name
        frame = pd.read_csv(fp, index_col=0, parse_dates=True)
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        return frame.reindex(index).fillna(0.0)

    decision = read("phase_n_decision_predictions.csv")[ph.ACTIVE_PANEL]
    tail = read("phase_n_tail_predictions.csv")[ph.ACTIVE_PANEL]
    uncertainty = read("phase_n_prediction_uncertainty.csv")[ph.ACTIVE_PANEL]
    # uncertainty pre-walkforward is 2/3 placeholder — clip to reasonable range.
    uncertainty = uncertainty.clip(0.0, 1.0)
    gate_raw = read("phase_n_gate_probabilities.csv")
    # gate fills 0 → evenly share, so renormalize.
    gate = gate_raw.div(gate_raw.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(1.0 / 3.0)
    return {"decision": decision, "tail": tail, "uncertainty": uncertainty, "gate": gate}


def candidate_signal(
    candidate_name: str,
    date: pd.Timestamp,
    decision: pd.DataFrame,
    tail: pd.DataFrame,
    uncertainty: pd.DataFrame,
    state_prior: pd.DataFrame,
    reference_weights: pd.DataFrame,
    learning_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
) -> pd.Series:
    """Build candidate-specific rank signal atop ML Phase 1 predictions."""
    opp_rank = ph.centered_rank(decision.loc[date, ph.ACTIVE_PANEL])
    tail_rank = ph.centered_rank(tail.loc[date, ph.ACTIVE_PANEL])
    unc = uncertainty.loc[date, ph.ACTIVE_PANEL].astype(float).clip(0.0, 1.0)
    certainty_rank = ph.centered_rank(1.0 - unc)
    prior_rank = ph.centered_rank(state_prior.loc[date, ph.ACTIVE_PANEL])
    ref_rank = ph.centered_rank(reference_weights.loc[date, ph.ACTIVE_PANEL])
    learn_rank = ph.centered_rank(learning_weights.loc[date, ph.ACTIVE_PANEL])
    tail_ref_rank = ph.centered_rank(tail_weights.loc[date, ph.ACTIVE_PANEL])

    if candidate_name == "improved_phaseo_uncertainty_shrunk_allocator":
        # P2-A: shrink opportunity rank per-sleeve by (1 - uncertainty).
        sleeve_certainty = (1.0 - unc).clip(lower=0.10)
        shrunk_opp = opp_rank.mul(sleeve_certainty)
        shrunk_tail = tail_rank.mul(sleeve_certainty)
        return (
            0.34 * shrunk_opp
            + 0.18 * shrunk_tail
            + 0.14 * certainty_rank
            + 0.12 * prior_rank
            + 0.12 * ref_rank
            + 0.06 * learn_rank
            + 0.04 * tail_ref_rank
        ).fillna(0.0)

    if candidate_name == "improved_phaseo_turnover_gated_allocator":
        # P2-B: stable signal that leans on reference weights so drift stays small.
        return (
            0.30 * opp_rank
            + 0.14 * certainty_rank
            + 0.22 * ref_rank
            + 0.14 * learn_rank
            + 0.10 * prior_rank
            + 0.06 * tail_rank
            + 0.04 * tail_ref_rank
        ).fillna(0.0)

    if candidate_name == "improved_phaseo_tail_priority_allocator":
        # P2-C: tail predictions lead; opportunity is the secondary lens.
        return (
            0.34 * tail_rank
            + 0.22 * opp_rank
            + 0.14 * certainty_rank
            + 0.12 * tail_ref_rank
            + 0.10 * prior_rank
            + 0.08 * ref_rank
        ).fillna(0.0)

    if candidate_name == "improved_phaseo_production_proximity_allocator":
        # P2-D: almost all weight on reference rank — signal merely breaks ties.
        return (
            0.42 * ref_rank
            + 0.22 * opp_rank
            + 0.14 * certainty_rank
            + 0.10 * prior_rank
            + 0.06 * learn_rank
            + 0.04 * tail_rank
            + 0.02 * tail_ref_rank
        ).fillna(0.0)

    if candidate_name == "improved_phaseo_combo_decision_allocator":
        # P2-E: blend of A (uncertainty-shrunk) + C (tail-aware) + D (proximity).
        sleeve_certainty = (1.0 - unc).clip(lower=0.10)
        shrunk_opp = opp_rank.mul(sleeve_certainty)
        shrunk_tail = tail_rank.mul(sleeve_certainty)
        return (
            0.26 * shrunk_opp
            + 0.22 * shrunk_tail
            + 0.20 * ref_rank
            + 0.12 * certainty_rank
            + 0.10 * prior_rank
            + 0.06 * learn_rank
            + 0.04 * tail_ref_rank
        ).fillna(0.0)

    raise ValueError(candidate_name)


def candidate_context(
    candidate_name: str,
    date: pd.Timestamp,
    signal: pd.Series,
    uncertainty: pd.DataFrame,
    meta: pd.DataFrame,
    gate: pd.DataFrame,
    state_features: pd.DataFrame,
) -> tuple[float, float, float]:
    """Return (confidence, total_uncertainty, risk_guard) for this candidate."""
    margin_conf = float(meta.loc[date, "margin_confidence"])
    agreement = float(meta.loc[date, "agreement"])
    signal_gap = pj.top_margin(signal)
    risk_guard = float(meta.loc[date, "risk_guard"])

    sleeve_unc = uncertainty.loc[date, ph.ACTIVE_PANEL].astype(float).clip(0.0, 1.0)
    signal_focus = (signal - float(signal.min()) + EPS).clip(lower=0.0)
    total_focus = float(signal_focus.sum())
    if total_focus > 0:
        signal_focus = signal_focus / total_focus
    else:
        signal_focus = pd.Series(1.0 / len(signal), index=signal.index, dtype=float)
    focus_uncertainty = float((signal_focus.reindex(ph.ACTIVE_PANEL) * sleeve_unc).sum())

    gate_top = float(gate.loc[date].max()) if date in gate.index else 1.0 / 3.0
    gate_entropy = 0.0
    if date in gate.index:
        probs = gate.loc[date].clip(lower=1e-6)
        gate_entropy = float(-(probs * np.log(probs)).sum() / np.log(max(len(probs), 2)))

    confidence = (
        0.28 * ph.bounded_zero_to_one(signal_gap, 0.03, 0.75)
        + 0.22 * margin_conf
        + 0.18 * agreement
        + 0.14 * gate_top
        + 0.10 * (1.0 - gate_entropy)
        - 0.22 * focus_uncertainty
    )

    if candidate_name == "improved_phaseo_production_proximity_allocator":
        confidence += 0.08 * margin_conf - 0.05 * focus_uncertainty
    elif candidate_name == "improved_phaseo_uncertainty_shrunk_allocator":
        confidence -= 0.06 * focus_uncertainty
    elif candidate_name == "improved_phaseo_tail_priority_allocator":
        confidence -= 0.04 * risk_guard

    confidence = float(np.clip(confidence, 0.0, 1.0))
    total_uncertainty = float(np.clip(0.65 * focus_uncertainty + 0.35 * (1.0 - gate_top), 0.0, 1.0))
    return confidence, total_uncertainty, risk_guard


def candidate_bounds(
    candidate_name: str,
    st: pd.Series,
    margin_conf: float,
    agreement: float,
    confidence: float,
    total_uncertainty: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Candidate-specific floors / caps layered on the structural dynamic bounds."""
    floors, caps = pj.dynamic_bounds(st, margin_conf, agreement)
    floors = dict(floors)
    caps = dict(caps)
    risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))
    calm = float(st["calm_confidence"])
    recovery = float(st["recovery_confidence"])

    if candidate_name == "improved_phaseo_uncertainty_shrunk_allocator":
        # High uncertainty tightens caps so nothing pushes hard.
        if total_uncertainty > 0.55:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(caps.get(sleeve, 1.0), 0.26)
        elif confidence > 0.70 and total_uncertainty < 0.32:
            if calm >= max(recovery, risk_guard):
                caps["composite_calm_trend_specialist"] = max(caps.get("composite_calm_trend_specialist", 0.36), 0.42)
                caps["taa_10m_sma"] = max(caps.get("taa_10m_sma", 0.36), 0.40)

    elif candidate_name == "improved_phaseo_turnover_gated_allocator":
        # Keep wider caps than production when confident, but never widen beyond 0.42.
        if confidence > 0.60:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(max(caps.get(sleeve, 0.36), 0.40), 0.44)
        # Deep risk-guard => clip offense caps tighter than default to mimic production.
        if risk_guard > 0.40:
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.12)
            caps["composite_healthier_recovery_specialist"] = min(
                caps.get("composite_healthier_recovery_specialist", 1.0), 0.18
            )

    elif candidate_name == "improved_phaseo_tail_priority_allocator":
        # Push defensive floors whenever tail risk is elevated.
        floors["composite_regime_conditioned"] = max(
            floors.get("composite_regime_conditioned", 0.0), 0.12 + 0.10 * risk_guard
        )
        floors["composite_anti_chop_clarity"] = max(
            floors.get("composite_anti_chop_clarity", 0.0), 0.10 + 0.10 * float(st["chop_confidence"])
        )
        if risk_guard > 0.35 or total_uncertainty > 0.50:
            caps["dual_momentum_topn"] = min(caps.get("dual_momentum_topn", 1.0), 0.10)
            caps["composite_healthier_recovery_specialist"] = min(
                caps.get("composite_healthier_recovery_specialist", 1.0), 0.18
            )
            caps["composite_calm_trend_specialist"] = min(caps.get("composite_calm_trend_specialist", 1.0), 0.22)

    elif candidate_name == "improved_phaseo_production_proximity_allocator":
        # Pull caps back toward production-ish levels (no sleeve above 0.32 default),
        # widen only when confidence AND certainty are both high.
        for sleeve in ph.ACTIVE_PANEL:
            caps[sleeve] = min(caps.get(sleeve, 0.36), 0.34)
        if confidence > 0.75 and total_uncertainty < 0.30:
            if calm >= max(recovery, risk_guard):
                caps["composite_calm_trend_specialist"] = max(caps.get("composite_calm_trend_specialist", 0.32), 0.38)
            if recovery >= max(calm, risk_guard):
                caps["composite_healthier_recovery_specialist"] = max(
                    caps.get("composite_healthier_recovery_specialist", 0.32), 0.38
                )

    elif candidate_name == "improved_phaseo_combo_decision_allocator":
        # Combo: moderate tail floors + proximity cap clip.
        floors["composite_regime_conditioned"] = max(
            floors.get("composite_regime_conditioned", 0.0), 0.10 + 0.08 * risk_guard
        )
        if total_uncertainty > 0.50:
            for sleeve in ph.ACTIVE_PANEL:
                caps[sleeve] = min(caps.get(sleeve, 1.0), 0.32)
        elif confidence > 0.72 and total_uncertainty < 0.32:
            if calm >= max(recovery, risk_guard):
                caps["composite_calm_trend_specialist"] = max(caps.get("composite_calm_trend_specialist", 0.36), 0.40)
            if recovery >= max(calm, risk_guard):
                caps["composite_healthier_recovery_specialist"] = max(
                    caps.get("composite_healthier_recovery_specialist", 0.36), 0.40
                )
    return floors, caps


def candidate_knobs(
    candidate_name: str,
    confidence: float,
    total_uncertainty: float,
    risk_guard: float,
) -> dict[str, float]:
    """Return mu_scale, lambda_*, safe_mix, cash_weight, anchor blend."""
    if candidate_name == "improved_phaseo_uncertainty_shrunk_allocator":
        return {
            "mu_scale":      0.92 * (0.24 + 0.92 * confidence) * (1.0 - 0.26 * total_uncertainty),
            "lambda_var":    1.05 * (1.0 + 0.22 * risk_guard + 0.08 * total_uncertainty),
            "lambda_down":   0.86 * (1.0 + 0.32 * risk_guard + 0.14 * total_uncertainty),
            "lambda_tail":   0.82 * (1.0 + 0.44 * risk_guard + 0.16 * total_uncertainty),
            "lambda_turn":   0.90 * (1.10 - 0.38 * confidence + 0.30 * total_uncertainty),
            "lambda_anchor": 0.80 * (1.04 - 0.18 * confidence + 0.14 * total_uncertainty),
            "lambda_hhi":    0.28 * (1.12 - 0.42 * confidence + 0.26 * total_uncertainty),
            "safe_mix":      min(0.08 + 0.18 * risk_guard + 0.22 * total_uncertainty + 0.06 * (1 - confidence), 0.30),
            "cash_weight":   float(np.clip(0.02 + 0.10 * risk_guard + 0.08 * total_uncertainty - 0.03 * confidence, 0.0, 0.12)),
            "ref_mix":       0.58,  # anchor = 0.58 ref + 0.24 learn + 0.18 tail_ref
            "learn_mix":     0.24,
            "tail_ref_mix":  0.18,
        }

    if candidate_name == "improved_phaseo_turnover_gated_allocator":
        # Strong turnover penalty when signal is mushy; anchor dominated by reference.
        return {
            "mu_scale":      0.88 * (0.24 + 0.95 * confidence) * (1.0 - 0.12 * total_uncertainty),
            "lambda_var":    1.02 * (1.0 + 0.20 * risk_guard),
            "lambda_down":   0.84 * (1.0 + 0.30 * risk_guard),
            "lambda_tail":   0.78 * (1.0 + 0.42 * risk_guard),
            # BIG turnover penalty — our distinctive lever.
            "lambda_turn":   1.30 * (1.20 - 0.45 * confidence + 0.32 * total_uncertainty),
            "lambda_anchor": 0.95 * (1.08 - 0.14 * confidence + 0.12 * total_uncertainty),
            "lambda_hhi":    0.24 * (1.06 - 0.32 * confidence + 0.18 * total_uncertainty),
            "safe_mix":      min(0.05 + 0.15 * risk_guard + 0.12 * total_uncertainty, 0.22),
            "cash_weight":   float(np.clip(0.015 + 0.10 * risk_guard + 0.04 * total_uncertainty - 0.03 * confidence, 0.0, 0.10)),
            "ref_mix":       0.68,
            "learn_mix":     0.20,
            "tail_ref_mix":  0.12,
        }

    if candidate_name == "improved_phaseo_tail_priority_allocator":
        return {
            "mu_scale":      0.82 * (0.20 + 0.84 * confidence) * (1.0 - 0.22 * total_uncertainty),
            "lambda_var":    1.14 * (1.0 + 0.28 * risk_guard + 0.10 * total_uncertainty),
            "lambda_down":   1.05 * (1.0 + 0.48 * risk_guard + 0.18 * total_uncertainty),
            "lambda_tail":   1.15 * (1.15 + 0.66 * risk_guard + 0.24 * total_uncertainty),
            "lambda_turn":   0.95 * (1.12 - 0.30 * confidence + 0.28 * total_uncertainty),
            "lambda_anchor": 0.86 * (1.10 - 0.12 * confidence + 0.14 * total_uncertainty),
            "lambda_hhi":    0.32 * (1.08 - 0.26 * confidence + 0.18 * total_uncertainty),
            "safe_mix":      min(0.10 + 0.22 * risk_guard + 0.16 * total_uncertainty + 0.06 * (1 - confidence), 0.34),
            "cash_weight":   float(np.clip(0.025 + 0.14 * risk_guard + 0.10 * total_uncertainty - 0.04 * confidence, 0.0, 0.16)),
            "ref_mix":       0.46,
            "learn_mix":     0.22,
            "tail_ref_mix":  0.32,
        }

    if candidate_name == "improved_phaseo_production_proximity_allocator":
        # The allocator is meant to look like production unless model is very sure.
        return {
            "mu_scale":      0.60 * (0.18 + 0.85 * confidence) * (1.0 - 0.15 * total_uncertainty),
            "lambda_var":    1.00 * (1.0 + 0.18 * risk_guard),
            "lambda_down":   0.78 * (1.0 + 0.26 * risk_guard),
            "lambda_tail":   0.72 * (1.0 + 0.34 * risk_guard),
            "lambda_turn":   1.10 * (1.08 - 0.30 * confidence + 0.20 * total_uncertainty),
            # Crucial lever: very strong anchor pull.
            "lambda_anchor": 1.35 * (1.05 - 0.10 * confidence + 0.10 * total_uncertainty),
            "lambda_hhi":    0.22 * (1.02 - 0.22 * confidence + 0.12 * total_uncertainty),
            "safe_mix":      min(0.06 + 0.14 * risk_guard + 0.10 * total_uncertainty, 0.22),
            "cash_weight":   float(np.clip(0.010 + 0.08 * risk_guard + 0.04 * total_uncertainty - 0.03 * confidence, 0.0, 0.08)),
            "ref_mix":       0.82,   # most weight on reference allocator
            "learn_mix":     0.12,
            "tail_ref_mix":  0.06,
        }

    if candidate_name == "improved_phaseo_combo_decision_allocator":
        return {
            "mu_scale":      0.82 * (0.22 + 0.90 * confidence) * (1.0 - 0.18 * total_uncertainty),
            "lambda_var":    1.08 * (1.0 + 0.22 * risk_guard + 0.08 * total_uncertainty),
            "lambda_down":   0.92 * (1.0 + 0.38 * risk_guard + 0.14 * total_uncertainty),
            "lambda_tail":   0.94 * (1.0 + 0.52 * risk_guard + 0.20 * total_uncertainty),
            "lambda_turn":   1.15 * (1.15 - 0.38 * confidence + 0.28 * total_uncertainty),
            "lambda_anchor": 1.05 * (1.06 - 0.14 * confidence + 0.12 * total_uncertainty),
            "lambda_hhi":    0.26 * (1.08 - 0.32 * confidence + 0.20 * total_uncertainty),
            "safe_mix":      min(0.08 + 0.18 * risk_guard + 0.16 * total_uncertainty + 0.05 * (1 - confidence), 0.28),
            "cash_weight":   float(np.clip(0.015 + 0.10 * risk_guard + 0.06 * total_uncertainty - 0.03 * confidence, 0.0, 0.12)),
            "ref_mix":       0.60,
            "learn_mix":     0.22,
            "tail_ref_mix":  0.18,
        }
    raise ValueError(candidate_name)


def build_candidate_weights(
    candidate_name: str,
    state_features: pd.DataFrame,
    state_prior: pd.DataFrame,
    ml_predictions: dict[str, pd.DataFrame],
    reference_weights: pd.DataFrame,
    learning_weights: pd.DataFrame,
    tail_weights: pd.DataFrame,
    meta: pd.DataFrame,
    cov_map: dict[pd.Timestamp, pd.DataFrame],
    down_cov_map: dict[pd.Timestamp, pd.DataFrame],
    tail_map: dict[pd.Timestamp, pd.Series],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.Series] = []
    control_rows: list[pd.Series] = []
    prev_risky: pd.Series | None = None

    decision = ml_predictions["decision"]
    tail = ml_predictions["tail"]
    uncertainty = ml_predictions["uncertainty"]
    gate = ml_predictions["gate"]

    # P2-B freezes weights when top-gap is mushy AND prev is already inside bounds.
    is_turnover_gated = candidate_name == "improved_phaseo_turnover_gated_allocator"

    for date in reference_weights.index:
        st = state_features.loc[date]
        margin_conf = float(meta.loc[date, "margin_confidence"])
        agreement = float(meta.loc[date, "agreement"])
        risk_guard = max(float(st["stress_confidence"]), float(st["chop_confidence"]))

        ref = normalize(reference_weights.loc[date, ph.ACTIVE_PANEL])
        learn = normalize(learning_weights.loc[date, ph.ACTIVE_PANEL])
        tail_ref = normalize(tail_weights.loc[date, ph.ACTIVE_PANEL])
        prev = ref.copy() if prev_risky is None else prev_risky.copy()

        signal = candidate_signal(
            candidate_name,
            date,
            decision,
            tail,
            uncertainty,
            state_prior,
            reference_weights,
            learning_weights,
            tail_weights,
        )
        confidence, total_uncertainty, _ = candidate_context(
            candidate_name, date, signal, uncertainty, meta, gate, state_features
        )
        floors, caps = candidate_bounds(
            candidate_name, st, margin_conf, agreement, confidence, total_uncertainty
        )
        knobs = candidate_knobs(candidate_name, confidence, total_uncertainty, risk_guard)

        anchor_core = (
            knobs["ref_mix"] * ref
            + knobs["learn_mix"] * learn
            + knobs["tail_ref_mix"] * tail_ref
        )
        anchor = normalize((1.0 - knobs["safe_mix"]) * anchor_core + knobs["safe_mix"] * pi.SAFE_ANCHOR)
        role_penalty = pj.risk_penalty_vector(st)

        # P2-B turnover gate: if previous risky is inside bounds and signal top-gap is small,
        # keep previous weights verbatim (zero turnover this week).
        freeze_prev = False
        if is_turnover_gated and prev_risky is not None:
            signal_gap = pj.top_margin(signal)
            if signal_gap < 0.10 and total_uncertainty > 0.45 and confidence < 0.55:
                # Still respect current floors / caps — bound previous and reuse.
                bounded_prev = pi.bounded_normalize(prev_risky, floors=floors, caps=caps)
                freeze_prev = True
                risky = bounded_prev
        if not freeze_prev:
            risky = pk.solve_objective(
                signal,
                anchor,
                prev,
                cov_map[date],
                down_cov_map[date],
                tail_map[date],
                role_penalty,
                mu_scale=knobs["mu_scale"],
                lambda_var=knobs["lambda_var"],
                lambda_down=knobs["lambda_down"],
                lambda_tail=knobs["lambda_tail"],
                lambda_turn=knobs["lambda_turn"],
                lambda_anchor=knobs["lambda_anchor"],
                lambda_hhi=knobs["lambda_hhi"],
                floors=floors,
                caps=caps,
            )

        cash_weight = knobs["cash_weight"]
        row = pd.Series(0.0, index=ph.ACTIVE_PANEL + [ph.CASH_COLUMN], dtype=float, name=date)
        row.loc[ph.ACTIVE_PANEL] = (1.0 - cash_weight) * risky
        row.loc[ph.CASH_COLUMN] = cash_weight
        rows.append(row)

        control_rows.append(
            pd.Series(
                {
                    "model_confidence": confidence,
                    "model_uncertainty": total_uncertainty,
                    "margin_confidence": margin_conf,
                    "agreement": agreement,
                    "signal_top_gap": pj.top_margin(signal),
                    "risk_guard": risk_guard,
                    "cash_weight": cash_weight,
                    "mu_scale": knobs["mu_scale"],
                    "lambda_turn": knobs["lambda_turn"],
                    "lambda_tail": knobs["lambda_tail"],
                    "lambda_anchor": knobs["lambda_anchor"],
                    "safe_mix": knobs["safe_mix"],
                    "freeze_prev": int(freeze_prev),
                },
                name=date,
            )
        )
        prev_risky = normalize(row.loc[ph.ACTIVE_PANEL])

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(control_rows).sort_index()


def uncertainty_summary(version_name: str, controls: pd.DataFrame, sleeve_weights: pd.DataFrame) -> pd.DataFrame:
    risky = sleeve_weights[ph.ACTIVE_PANEL]
    risky_norm = risky.div(risky.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    return pd.DataFrame(
        [
            {
                "version_name": version_name,
                "avg_model_confidence": float(controls["model_confidence"].mean()),
                "avg_model_uncertainty": float(controls["model_uncertainty"].mean()),
                "avg_cash_weight": float(controls["cash_weight"].mean()),
                "avg_top1_share": float(risky_norm.max(axis=1).mean()),
                "avg_top2_share": float(np.sort(risky_norm.to_numpy(), axis=1)[:, -2:].sum(axis=1).mean()),
                "avg_hhi": float(risky_norm.pow(2).sum(axis=1).mean()),
                "freeze_share": float(controls["freeze_prev"].mean()),
            }
        ]
    )


# ---------------------------------------------------------------------------
# Phase D-style validation for the fixed comparator set + Phase O candidates.
# ---------------------------------------------------------------------------


def run_validation(candidate_names: list[str]) -> dict:
    """Compute full / dev / holdout metrics + pairwise vs production for all versions."""
    all_versions = list(FIXED_COMPARATORS) + candidate_names

    benchmark_returns = pdv.read_return_csv(
        LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv"
    )["net_return"]
    market_state_history = pd.read_csv(
        LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"]
    )
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index()

    returns_map: dict[str, pd.Series] = {}
    weights_map: dict[str, pd.DataFrame] = {}
    turnover_map: dict[str, pd.Series] = {}
    common_index: pd.Index | None = None

    for name in all_versions:
        returns_df = pdv.read_return_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        weights_df = pdv.read_weight_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        returns_map[name] = returns_df["net_return"]
        turnover_map[name] = returns_df["turnover"] if "turnover" in returns_df.columns else pd.Series(dtype=float)
        weights_map[name] = weights_df
        common_index = returns_df.index if common_index is None else common_index.intersection(returns_df.index)

    assert common_index is not None
    common_index = common_index.intersection(benchmark_returns.index)
    for name in all_versions:
        returns_map[name] = returns_map[name].reindex(common_index).dropna()
        aligned_index = returns_map[name].index
        weights_map[name] = weights_map[name].reindex(aligned_index).fillna(0.0)
        turnover_map[name] = turnover_map[name].reindex(aligned_index)
    benchmark_returns = benchmark_returns.reindex(common_index).dropna()

    def block_metrics(ret: pd.Series, wt: pd.DataFrame, bench: pd.Series, turnover: pd.Series | None) -> dict:
        metrics = pdv.summary_metrics(ret, wt, bench, turnover)
        metrics["recovery_capture"] = pdv.recovery_capture(ret, bench, market_state_history)
        return metrics

    full_rows, dev_rows, holdout_rows = [], [], []
    for name in all_versions:
        full_rows.append({"version_name": name, **block_metrics(returns_map[name], weights_map[name], benchmark_returns, turnover_map[name])})
        dev_ret, hold_ret, dev_w, hold_w = pdv.split_dev_holdout(returns_map[name], weights_map[name], pdv.HOLDOUT_WEEKS)
        bench_dev = benchmark_returns.reindex(dev_ret.index)
        bench_hold = benchmark_returns.reindex(hold_ret.index)
        dev_rows.append({"version_name": name, **block_metrics(dev_ret, dev_w, bench_dev, turnover_map[name].reindex(dev_ret.index))})
        holdout_rows.append({"version_name": name, **block_metrics(hold_ret, hold_w, bench_hold, turnover_map[name].reindex(hold_ret.index))})

    full_df = pd.DataFrame(full_rows)
    dev_df = pd.DataFrame(dev_rows)
    holdout_df = pd.DataFrame(holdout_rows)
    for df in [full_df, dev_df, holdout_df]:
        df["raw_target_composite"] = df.apply(pdv.raw_metric_composite, axis=1)
        df["fixed_rank_composite"] = pdv.fixed_rank_composite(df)
        df["raw_composite_position"] = df["raw_target_composite"].rank(ascending=False, method="min").astype(int)
        df["fixed_rank_position"] = df["fixed_rank_composite"].rank(ascending=False, method="min").astype(int)

    windows = pdv.rolling_origin_windows(
        benchmark_returns.index, pdv.ROLLING_MIN_TRAIN_WEEKS, pdv.ROLLING_TEST_WEEKS, pdv.ROLLING_STEP_WEEKS
    )

    rolling_rows = []
    for name in all_versions:
        comps, sharpes, rets = [], [], []
        for _, test_index in windows:
            cand_ret = returns_map[name].reindex(test_index).dropna()
            if len(cand_ret) != len(test_index):
                continue
            cand_w = weights_map[name].reindex(test_index).fillna(0.0)
            bench = benchmark_returns.reindex(test_index)
            metrics = block_metrics(cand_ret, cand_w, bench, turnover_map[name].reindex(cand_ret.index))
            comps.append(pdv.raw_metric_composite(pd.Series(metrics)))
            sharpes.append(metrics["sharpe"])
            rets.append(metrics["ann_return"])
        rolling_rows.append({
            "version_name": name,
            "rolling_windows": int(len(comps)),
            "rolling_avg_raw_composite": float(np.nanmean(comps)) if comps else np.nan,
            "rolling_median_raw_composite": float(np.nanmedian(comps)) if comps else np.nan,
            "rolling_avg_sharpe": float(np.nanmean(sharpes)) if sharpes else np.nan,
            "rolling_avg_ann_return": float(np.nanmean(rets)) if rets else np.nan,
        })

    production_holdout = returns_map[PRODUCTION_PIN].tail(pdv.HOLDOUT_WEEKS)
    production_full = full_df.set_index("version_name").loc[PRODUCTION_PIN]
    production_hold = holdout_df.set_index("version_name").loc[PRODUCTION_PIN]
    production_hold_sharpe = production_hold["sharpe"]

    pairwise_rows = []
    for name in all_versions:
        if name == PRODUCTION_PIN:
            continue
        candidate_holdout = returns_map[name].reindex(production_holdout.index).dropna()
        diff = candidate_holdout - production_holdout.reindex(candidate_holdout.index)
        bootstrap_prob = pdv.moving_block_bootstrap_prob(diff)

        wins = comparable = 0
        raw_deltas, sharpe_deltas, return_deltas, dd_deltas, cvar_deltas = [], [], [], [], []
        for _, test_index in windows:
            cand_ret = returns_map[name].reindex(test_index).dropna()
            prod_ret = returns_map[PRODUCTION_PIN].reindex(test_index).dropna()
            if len(cand_ret) != len(test_index) or len(prod_ret) != len(test_index):
                continue
            cand_w = weights_map[name].reindex(test_index).fillna(0.0)
            prod_w = weights_map[PRODUCTION_PIN].reindex(test_index).fillna(0.0)
            bench = benchmark_returns.reindex(test_index)
            cand_m = block_metrics(cand_ret, cand_w, bench, turnover_map[name].reindex(cand_ret.index))
            prod_m = block_metrics(prod_ret, prod_w, bench, turnover_map[PRODUCTION_PIN].reindex(prod_ret.index))
            cand_c = pdv.raw_metric_composite(pd.Series(cand_m))
            prod_c = pdv.raw_metric_composite(pd.Series(prod_m))
            raw_deltas.append(cand_c - prod_c)
            sharpe_deltas.append(cand_m["sharpe"] - prod_m["sharpe"])
            return_deltas.append(cand_m["ann_return"] - prod_m["ann_return"])
            dd_deltas.append(cand_m["max_drawdown"] - prod_m["max_drawdown"])
            cvar_deltas.append(cand_m["cvar_5"] - prod_m["cvar_5"])
            comparable += 1
            if cand_c > prod_c:
                wins += 1

        pairwise_rows.append({
            "version_name": name,
            "full_raw_delta_vs_production": float(full_df.set_index("version_name").loc[name, "raw_target_composite"] - production_full["raw_target_composite"]),
            "holdout_raw_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "raw_target_composite"] - production_hold["raw_target_composite"]),
            "holdout_sharpe_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "sharpe"] - production_hold_sharpe),
            "holdout_max_drawdown_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "max_drawdown"] - production_hold["max_drawdown"]),
            "holdout_cvar_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "cvar_5"] - production_hold["cvar_5"]),
            "holdout_bootstrap_prob_excess_return": bootstrap_prob,
            "rolling_windows": int(comparable),
            "rolling_raw_win_rate_vs_production": float(wins / comparable) if comparable else np.nan,
            "rolling_mean_raw_delta_vs_production": float(np.nanmean(raw_deltas)) if raw_deltas else np.nan,
            "rolling_mean_sharpe_delta_vs_production": float(np.nanmean(sharpe_deltas)) if sharpe_deltas else np.nan,
            "rolling_mean_ann_return_delta_vs_production": float(np.nanmean(return_deltas)) if return_deltas else np.nan,
            "rolling_mean_max_drawdown_delta_vs_production": float(np.nanmean(dd_deltas)) if dd_deltas else np.nan,
            "rolling_mean_cvar_delta_vs_production": float(np.nanmean(cvar_deltas)) if cvar_deltas else np.nan,
        })

    pairwise_df = pd.DataFrame(pairwise_rows)
    rolling_df = pd.DataFrame(rolling_rows)

    full_df.to_csv(LAYER3_DIR / "phase_o_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_o_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_o_candidate_metrics_holdout.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_o_pairwise_vs_production.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_o_rolling_origin_summary.csv", index=False)

    protocol = {
        "phase": "Phase O — Decision-Aware Portfolio Allocation (ML Phase 2)",
        "fixed_comparator_set": FIXED_COMPARATORS,
        "phase_o_candidates": list(PHASE_O_CANDIDATES.keys()),
        "production_pin": PRODUCTION_PIN,
        "shadow_pin": SHADOW_PIN,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin_rule": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap_rule": {
            "method": "moving_block_bootstrap",
            "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS,
            "samples": pdv.BOOTSTRAP_SAMPLES,
        },
        "phase_d_promotion_gate": {
            "full_raw_composite_delta_vs_production_min": 0.015,
            "holdout_raw_composite_delta_vs_production_min": 0.0,
            "holdout_sharpe_delta_vs_production_min": -0.02,
            "rolling_raw_win_rate_vs_production_min": 0.55,
            "holdout_bootstrap_prob_excess_return_min": 0.60,
            "max_drawdown_worsening_cap": -0.010,
            "cvar_worsening_cap": -0.002,
        },
    }
    (LAYER3_DIR / "phase_o_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {
        "full": full_df,
        "dev": dev_df,
        "holdout": holdout_df,
        "pairwise": pairwise_df,
        "rolling": rolling_df,
        "protocol": protocol,
    }


def main() -> None:
    next_week_returns, active_returns, active_positions, _, market_state_history = ph.load_inputs()
    state_features = ph.state_feature_frame(active_returns.index, market_state_history)
    state_prior = ph.role_alignment_score(state_features)

    reference_weights = ph.read_panel_csv(
        LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_REFINED_REFERENCE}.csv"
    ).reindex(state_prior.index).fillna(0.0)
    learning_weights = ph.read_panel_csv(
        LAYER3_DIR / f"portfolio_version_sleeve_weights_{CURRENT_LEARNING_BRANCH}.csv"
    ).reindex(state_prior.index).fillna(0.0)
    tail_weights = ph.read_panel_csv(
        LAYER3_DIR / f"portfolio_version_sleeve_weights_{TAIL_AWARE_BRANCH}.csv"
    ).reindex(state_prior.index).fillna(0.0)

    ml_predictions = load_phase_n_predictions(state_prior.index)

    _, _, simple_score_panel = ph.build_feature_panels(active_returns, state_features, state_prior)

    _, meta = pk.build_margin_meta(
        state_prior,
        simple_score_panel,
        ml_predictions["decision"],
        reference_weights,
        state_features,
    )
    meta = meta.reindex(state_prior.index).fillna(0.0)
    cov_map, down_cov_map, tail_map = pk.risk_maps(active_returns)
    universe_columns = list(next_week_returns.columns)

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    concentration_rows: list[pd.DataFrame] = []
    concentration_state_rows: list[pd.DataFrame] = []
    uncertainty_rows: list[pd.DataFrame] = []

    for version_name in PHASE_O_CANDIDATES:
        sleeve_weights, controls = build_candidate_weights(
            version_name,
            state_features,
            state_prior,
            ml_predictions,
            reference_weights,
            learning_weights,
            tail_weights,
            meta,
            cov_map,
            down_cov_map,
            tail_map,
        )
        etf_weights = ph.build_lookthrough_weights(sleeve_weights, active_positions, universe_columns)
        path = ph.save_portfolio_version(version_name, sleeve_weights, etf_weights, next_week_returns)

        state_rows.append(ph.state_summary(path["net_return"], etf_weights, market_state_history, version_name))
        alloc_summary, alloc_state = ph.sleeve_allocation_summary(sleeve_weights, market_state_history, version_name)
        sleeve_rows.append(alloc_summary)
        sleeve_state_rows.append(alloc_state)
        conc_summary, conc_state = ph.concentration_summary(sleeve_weights, market_state_history, version_name)
        concentration_rows.append(conc_summary)
        concentration_state_rows.append(conc_state)
        uncertainty_rows.append(uncertainty_summary(version_name, controls, sleeve_weights))
        controls.to_csv(LAYER3_DIR / f"phase_o_controls_{version_name}.csv")

        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        variant_rows.append(
            {
                "version_name": version_name,
                "ann_return": ann_ret,
                "ann_vol": ann_vol,
                "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
                "max_drawdown": ph.max_drawdown(path["net_return"]),
                "turnover": float(path["turnover"].mean()),
                "avg_bil": float(etf_weights.get("BIL", pd.Series(0.0, index=etf_weights.index)).mean()),
                "avg_spy": float(etf_weights.get("SPY", pd.Series(0.0, index=etf_weights.index)).mean()),
            }
        )

    pd.DataFrame(variant_rows).to_csv(LAYER3_DIR / "phase_o_allocator_variant_summary.csv", index=False)
    pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_allocator_state_summary.csv", index=False)
    pd.concat(sleeve_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_sleeve_allocation_summary.csv", index=False)
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_sleeve_allocation_by_state.csv", index=False)
    pd.concat(concentration_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_concentration_summary.csv", index=False)
    pd.concat(concentration_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_concentration_by_state.csv", index=False)
    pd.concat(uncertainty_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_o_uncertainty_summary.csv", index=False)

    # Now run full Phase D-style validation against the fixed comparator set.
    results = run_validation(list(PHASE_O_CANDIDATES.keys()))

    print("\n=== Phase O FULL metrics ===")
    print(results["full"].set_index("version_name")[
        ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
         "recovery_capture", "raw_target_composite", "raw_composite_position"]
    ].round(4).to_string())
    print("\n=== Phase O HOLDOUT metrics ===")
    print(results["holdout"].set_index("version_name")[
        ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
         "recovery_capture", "raw_target_composite", "raw_composite_position"]
    ].round(4).to_string())
    print("\n=== Phase O pairwise vs production ===")
    print(results["pairwise"].set_index("version_name")[
        ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
         "holdout_sharpe_delta_vs_production", "holdout_bootstrap_prob_excess_return",
         "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production"]
    ].round(4).to_string())

    print("\nSaved Phase O artifacts.")


if __name__ == "__main__":
    main()
