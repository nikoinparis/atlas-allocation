"""Phase Q — Abstention-Aware / Regime-Bucket Meta-Allocator.

Phase Q is a tightly targeted follow-up to Phase P. It does not retrain any ML
layer. It reuses the Phase P feature frame and trust-probability predictions,
and only changes how those predictions are converted into expert weights.

The explicit failure modes Phase Q attacks, in order:

  1. Phase P's smooth softmax blend produced mild, noisy trust that never
     actually committed - production weight hovered 0.30-0.40 across every
     regime. That diluted both the ML edge and the production defence.
     Phase Q introduces an explicit ABSTAIN mode (defensive production-heavy
     fallback) so low-conviction weeks stop forcing an opinion.

  2. Phase P's trust decision moved smoothly week-to-week. That hurt rolling
     win-rate and bootstrap support because the trust itself became noise.
     Phase Q buckets the decision into coarser regime-trust states with
     persistence / hysteresis so the trust signal does not thrash.

  3. Phase P's recent-quality features were simple rolling means. Phase Q
     replaces them with an exponentially-decayed regret signal ("regret decay
     memory") so recent underperformance weighs heavier but ancient history
     stops dominating.

Three candidates are built:
  Q1 `improved_phaseq_abstention_aware_meta_allocator`
  Q2 `improved_phaseq_regime_bucket_meta_allocator`
  Q3 `improved_phaseq_abstention_regime_regret_meta_allocator`

All three reuse Phase P's walk-forward classifier probabilities and feature
frame. Only the mapping from (trust signals, state, regret memory) to expert
weights differs.

Outputs written to data/05_layer3_portfolio_construction/:
  phase_q_controls_{version}.csv
  phase_q_trust_summary.csv
  phase_q_trust_by_state.csv
  phase_q_bucket_summary.csv
  phase_q_candidate_metrics_{full,dev,holdout}.csv
  phase_q_rolling_origin_summary.csv
  phase_q_pairwise_validation.csv
  phase_q_candidate_classification.csv
  phase_q_validation_protocol.json
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


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = pp.PRODUCTION_PIN
SHADOW_PIN = pp.SHADOW_PIN
PHASEH_REFERENCE = pp.PHASEH_REFERENCE
PHASEN_REFERENCE = pp.PHASEN_REFERENCE
PHASEO_REFERENCE = pp.PHASEO_REFERENCE
ACTIVE_PANEL_BASELINE = pp.ACTIVE_PANEL_BASELINE
PHASEP_REFERENCE = "improved_phasep_regret_aware_meta_allocator"

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    PHASEP_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

PHASE_Q_CANDIDATES = {
    "improved_phaseq_abstention_aware_meta_allocator":     "Q1 abstention-aware meta allocator",
    "improved_phaseq_regime_bucket_meta_allocator":        "Q2 regime-bucket meta allocator",
    "improved_phaseq_abstention_regime_regret_meta_allocator": "Q3 combo abstention + regime + regret",
}

# Coarser regime buckets. Each bucket encodes a stable trust posture.
BUCKETS = [
    "calm_trust",          # ML phaseo preferred - high calm confidence, low uncertainty
    "recovery_trust",      # ML phasen preferred - recovery/stress with good agreement
    "defense_production",  # production preferred - risk_guard dominant, offense risky
    "ambiguous_abstain",   # abstain fallback - low conviction, mushy signal
]

EPS = 1e-9

# Regret decay half-life in weeks. EMA weights recent excess return heavier.
REGRET_HALF_LIFE = 20  # ~20 week half-life
REGRET_ALPHA = 1.0 - 0.5 ** (1.0 / REGRET_HALF_LIFE)

# Bucket persistence: only switch when a new bucket has been "winning" 3 weeks.
BUCKET_PERSISTENCE = 3


def ema_excess(excess: pd.Series, alpha: float) -> pd.Series:
    """Causal EMA — uses only data up to t-1 (shifted by 1 week)."""
    lagged = excess.shift(1).fillna(0.0)
    return lagged.ewm(alpha=alpha, adjust=False, min_periods=1).mean().fillna(0.0)


def abstain_anchor(columns: list[str]) -> pd.Series:
    """Defensive fallback weights. Bias toward BIL + SHY + IEF with small SPY."""
    vals = {c: 0.0 for c in columns}
    safe_alloc = {"BIL": 0.45, "SHY": 0.20, "IEF": 0.15, "TIP": 0.08, "GLD": 0.06, "SPY": 0.06}
    for k, v in safe_alloc.items():
        if k in vals:
            vals[k] = v
    total = sum(vals.values())
    if total <= 0:
        return pd.Series(0.0, index=columns, dtype=float)
    return pd.Series({k: v / total for k, v in vals.items()}, index=columns, dtype=float)


def compute_regime_bucket(
    *,
    state_text: str,
    calm_conf: float,
    recovery_conf: float,
    stress_conf: float,
    chop_conf: float,
    model_confidence: float,
    model_uncertainty: float,
    agreement: float,
    risk_guard: float,
    margin_conf: float,
    gate_entropy: float,
) -> str:
    """Rule-based bucket assignment using only information available at t.

    Bucket ordering: defense_production > ambiguous_abstain > calm_trust > recovery_trust
    Defensive modes take precedence when risk is elevated.
    """
    # Defensive first: high risk_guard with weak conviction → production
    if risk_guard >= 0.45 and margin_conf < 0.45:
        return "defense_production"
    if stress_conf >= 0.55 and model_uncertainty >= 0.58:
        return "defense_production"

    # Abstain: truly mushy/ambiguous cases
    if model_uncertainty >= 0.58 and margin_conf < 0.40 and gate_entropy >= 0.85:
        return "ambiguous_abstain"
    if state_text in ("neutral_mixed", "recovery_confirmed") and margin_conf < 0.38 and model_uncertainty >= 0.54:
        return "ambiguous_abstain"

    # Calm-trust: calm regime with reasonable conviction → trust phaseo
    if state_text == "calm_trend" and calm_conf >= 0.55 and model_uncertainty < 0.58:
        return "calm_trust"

    # Recovery-trust: recovery or mild-stress with reasonable agreement → trust phasen
    if state_text in ("recovery_fragile", "recovery_confirmed") and recovery_conf >= 0.40:
        return "recovery_trust"
    if state_text == "stressed_panic" and agreement >= 0.45 and margin_conf >= 0.40:
        return "recovery_trust"

    # Fallback: production is always safer than guessing.
    return "defense_production"


def bucket_base_mix(bucket: str) -> dict[str, float]:
    """Base expert mix per bucket. 'abstain' is a 4th expert = abstain_anchor."""
    if bucket == "calm_trust":
        # ML phaseo leads, phasen supports, small production floor.
        return {"production": 0.20, "phasen": 0.25, "phaseo": 0.55, "abstain": 0.00}
    if bucket == "recovery_trust":
        # ML phasen leads, phaseo supports, production floor.
        return {"production": 0.25, "phasen": 0.50, "phaseo": 0.25, "abstain": 0.00}
    if bucket == "defense_production":
        # Production dominates, small abstain cushion.
        return {"production": 0.78, "phasen": 0.07, "phaseo": 0.07, "abstain": 0.08}
    if bucket == "ambiguous_abstain":
        # Heavy abstain + production; ML has almost no say.
        return {"production": 0.55, "phasen": 0.05, "phaseo": 0.05, "abstain": 0.35}
    raise ValueError(bucket)


def apply_regret_modulation(
    base_mix: dict[str, float],
    *,
    phaseo_regret: float,
    phasen_regret: float,
    scale: float = 0.35,
    floor: float = 0.05,
) -> dict[str, float]:
    """Nudge the ML experts up or down based on recent EMA excess return.

    Positive regret = recent outperformance → bigger ML share.
    Negative regret = recent underperformance → shrink ML, reallocate to
    production and abstain.
    """
    mix = dict(base_mix)
    # Clip regret signals to plausible range [-0.003, 0.003] per-week excess.
    phaseo_adj = float(np.clip(phaseo_regret, -0.003, 0.003)) / 0.003
    phasen_adj = float(np.clip(phasen_regret, -0.003, 0.003)) / 0.003
    # Shifts are scaled shares (at most `scale` of base ML share gets moved).
    phaseo_shift = scale * phaseo_adj * mix["phaseo"]
    phasen_shift = scale * phasen_adj * mix["phasen"]
    mix["phaseo"] = max(floor * min(mix["phaseo"], 0.10), mix["phaseo"] + phaseo_shift) if mix["phaseo"] > 0 else 0.0
    mix["phasen"] = max(floor * min(mix["phasen"], 0.10), mix["phasen"] + phasen_shift) if mix["phasen"] > 0 else 0.0

    removed_from_ml = (base_mix["phaseo"] - mix["phaseo"]) + (base_mix["phasen"] - mix["phasen"])
    # Positive removed_from_ml means we are pulling away from ML → pad production + abstain.
    # Negative removed_from_ml means ML gained weight at expense of production + abstain.
    # Split the shift 60/40 between production and abstain (absolute mass preserved).
    if abs(removed_from_ml) > EPS:
        mix["production"] += 0.60 * removed_from_ml
        mix["abstain"] += 0.40 * removed_from_ml

    # Renormalize to 1.0 and enforce non-negativity.
    mix = {k: max(v, 0.0) for k, v in mix.items()}
    total = sum(mix.values())
    if total <= 0:
        return {"production": 1.0, "phasen": 0.0, "phaseo": 0.0, "abstain": 0.0}
    return {k: v / total for k, v in mix.items()}


def abstention_score(
    *,
    model_uncertainty: float,
    margin_conf: float,
    risk_guard: float,
    gate_entropy: float,
    phaseo_prob: float,
    phasen_prob: float,
) -> float:
    """Higher → more abstain weight. Used by Q1."""
    # High model uncertainty, low margin confidence, high gate entropy, weak trust probs → abstain.
    trust_strength = max(phaseo_prob, phasen_prob)
    score = (
        0.35 * model_uncertainty
        + 0.30 * (1.0 - margin_conf)
        + 0.15 * gate_entropy
        + 0.20 * max(0.0, risk_guard - 0.35)
        - 0.50 * trust_strength
    )
    return float(np.clip(0.15 + 0.65 * score, 0.0, 0.90))


def build_q1_abstention_aware(
    feature_frame: pd.DataFrame,
    *,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q1: explicit abstention mode added to a softmax blend over
    production / phasen / phaseo. When abstention score is high, the abstain
    anchor absorbs weight first.
    """
    prod_w = weights_map[PRODUCTION_PIN]
    phasen_w = weights_map[PHASEN_REFERENCE]
    phaseo_w = weights_map[PHASEO_REFERENCE]
    columns = list(prod_w.columns)
    anchor = abstain_anchor(columns)

    rows: list[pd.Series] = []
    ctrl_rows: list[pd.Series] = []

    for date in feature_frame.index:
        st = feature_frame.loc[date, "state_text"]
        model_uncertainty = float(feature_frame.loc[date, "model_uncertainty"])
        margin_conf = float(feature_frame.loc[date, "margin_confidence"])
        risk_guard = float(feature_frame.loc[date, "risk_guard"])
        gate_entropy = float(feature_frame.loc[date, "phase_n_gate_entropy"])
        agreement = float(feature_frame.loc[date, "agreement"])
        p_phaseo = float(phaseo_prob.loc[date])
        p_phasen = float(phasen_prob.loc[date])
        phaseo_ex = float(feature_frame.loc[date, "phaseo_ex_mean_13"])
        phasen_ex = float(feature_frame.loc[date, "phasen_ex_mean_13"])
        phaseo_edge = float(feature_frame.loc[date, "phaseo_state_edge_mean"])
        phasen_edge = float(feature_frame.loc[date, "phasen_state_edge_mean"])

        a_score = abstention_score(
            model_uncertainty=model_uncertainty,
            margin_conf=margin_conf,
            risk_guard=risk_guard,
            gate_entropy=gate_entropy,
            phaseo_prob=p_phaseo,
            phasen_prob=p_phasen,
        )

        # Non-abstain experts scored via softmax.
        scores = {
            "production": 0.55
                + 0.10 * (1.0 - max(p_phaseo, p_phasen))
                + 0.06 * max(0.0, risk_guard - 0.30)
                - 0.05 * agreement,
            "phasen": 0.15
                + 0.75 * p_phasen
                + 0.06 * pp.tanh_clip(phasen_edge, 0.0015)
                + 0.04 * pp.tanh_clip(phasen_ex, 0.0010),
            "phaseo": 0.15
                + 0.80 * p_phaseo
                + 0.08 * pp.tanh_clip(phaseo_edge, 0.0015)
                + 0.05 * pp.tanh_clip(phaseo_ex, 0.0010)
                - 0.06 * model_uncertainty,
        }
        non_abstain = pp.softmax_weights(scores)

        # Final mix: abstain gets a_score, non-abstain shares the remainder.
        mix = {
            "abstain": a_score,
            "production": (1.0 - a_score) * non_abstain["production"],
            "phasen": (1.0 - a_score) * non_abstain["phasen"],
            "phaseo": (1.0 - a_score) * non_abstain["phaseo"],
        }

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
                "bucket": "abstention_softmax",
                "production_weight": mix["production"],
                "phasen_weight": mix["phasen"],
                "phaseo_weight": mix["phaseo"],
                "abstain_weight": mix["abstain"],
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


def build_q2_regime_bucket(
    feature_frame: pd.DataFrame,
    *,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    phaseo_regret_ema: pd.Series,
    phasen_regret_ema: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q2: coarse regime buckets with persistence / hysteresis.

    Each week a bucket is proposed by rule; we only switch the active bucket
    once the proposal has been active for BUCKET_PERSISTENCE weeks. Regret
    decay modulates the bucket's ML vs production mix.
    """
    prod_w = weights_map[PRODUCTION_PIN]
    phasen_w = weights_map[PHASEN_REFERENCE]
    phaseo_w = weights_map[PHASEO_REFERENCE]
    columns = list(prod_w.columns)
    anchor = abstain_anchor(columns)

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

        this_bucket = compute_regime_bucket(
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
        # Persistence: switch only after a new bucket has been proposed >= k weeks.
        if this_bucket == proposed_bucket:
            proposal_streak += 1
        else:
            proposed_bucket = this_bucket
            proposal_streak = 1
        if proposal_streak >= BUCKET_PERSISTENCE:
            active_bucket = proposed_bucket

        base = bucket_base_mix(active_bucket)
        regret_phaseo = float(phaseo_regret_ema.loc[date])
        regret_phasen = float(phasen_regret_ema.loc[date])
        mix = apply_regret_modulation(
            base,
            phaseo_regret=regret_phaseo,
            phasen_regret=regret_phasen,
            scale=0.25,
        )

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
                "trust_score": mix["phaseo"] + 0.5 * mix["phasen"],
                "phaseo_regret_ema": regret_phaseo,
                "phasen_regret_ema": regret_phasen,
                "phaseo_prob": float(phaseo_prob.loc[date]),
                "phasen_prob": float(phasen_prob.loc[date]),
                "model_uncertainty": model_uncertainty,
                "margin_confidence": margin_conf,
                "risk_guard": risk_guard,
                "gate_entropy": gate_entropy,
                "selected_expert": selected,
            },
            name=date,
        ))

    return pd.DataFrame(rows).sort_index().fillna(0.0), pd.DataFrame(ctrl_rows).sort_index()


def build_q3_combo(
    feature_frame: pd.DataFrame,
    *,
    weights_map: dict[str, pd.DataFrame],
    phaseo_prob: pd.Series,
    phasen_prob: pd.Series,
    phaseo_regret_ema: pd.Series,
    phasen_regret_ema: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Q3: regime-bucket + explicit abstention + stronger regret decay.

    Bucket selection uses the same rule as Q2 with persistence, but the mix is
    further modulated by an abstention score that can push weight out of ML
    into abstain when conviction collapses - even inside a "trust" bucket.
    Regret decay is scaled stronger (0.40 vs 0.25).
    """
    prod_w = weights_map[PRODUCTION_PIN]
    phasen_w = weights_map[PHASEN_REFERENCE]
    phaseo_w = weights_map[PHASEO_REFERENCE]
    columns = list(prod_w.columns)
    anchor = abstain_anchor(columns)

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

        this_bucket = compute_regime_bucket(
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

        base = bucket_base_mix(active_bucket)
        regret_phaseo = float(phaseo_regret_ema.loc[date])
        regret_phasen = float(phasen_regret_ema.loc[date])
        mix = apply_regret_modulation(
            base,
            phaseo_regret=regret_phaseo,
            phasen_regret=regret_phasen,
            scale=0.40,
        )

        # Abstention overlay: if conviction collapses even inside a trust bucket,
        # pull additional weight out of ML and into abstain.
        a_score = abstention_score(
            model_uncertainty=model_uncertainty,
            margin_conf=margin_conf,
            risk_guard=risk_guard,
            gate_entropy=gate_entropy,
            phaseo_prob=p_phaseo,
            phasen_prob=p_phasen,
        )
        # Only apply abstention overlay when bucket is an ML-trust bucket.
        if active_bucket in ("calm_trust", "recovery_trust"):
            ml_mass = mix["phaseo"] + mix["phasen"]
            pull = 0.50 * a_score * ml_mass
            if ml_mass > EPS:
                mix["phaseo"] *= 1.0 - 0.50 * a_score
                mix["phasen"] *= 1.0 - 0.50 * a_score
                mix["abstain"] += 0.6 * pull
                mix["production"] += 0.4 * pull

        total = sum(mix.values())
        if total > 0:
            mix = {k: v / total for k, v in mix.items()}

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
                "trust_score": mix["phaseo"] + 0.5 * mix["phasen"],
                "abstention_score": a_score,
                "phaseo_regret_ema": regret_phaseo,
                "phasen_regret_ema": regret_phasen,
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


def trust_summary(version_name: str, controls: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    def g(c: pd.DataFrame, col: str) -> float:
        if col in c.columns:
            return float(pd.to_numeric(c[col], errors="coerce").fillna(0.0).mean())
        return float("nan")

    overall = pd.DataFrame([{
        "version_name": version_name,
        "avg_production_weight": g(controls, "production_weight"),
        "avg_phasen_weight": g(controls, "phasen_weight"),
        "avg_phaseo_weight": g(controls, "phaseo_weight"),
        "avg_abstain_weight": g(controls, "abstain_weight"),
        "avg_trust_score": g(controls, "trust_score"),
        "avg_abstention_score": g(controls, "abstention_score") if "abstention_score" in controls.columns else float("nan"),
        "avg_model_uncertainty": g(controls, "model_uncertainty"),
        "phaseo_selected_share": float((controls["selected_expert"] == "phaseo").mean()) if "selected_expert" in controls.columns else 0.0,
        "phasen_selected_share": float((controls["selected_expert"] == "phasen").mean()) if "selected_expert" in controls.columns else 0.0,
        "production_selected_share": float((controls["selected_expert"] == "production").mean()) if "selected_expert" in controls.columns else 0.0,
        "abstain_selected_share": float((controls["selected_expert"] == "abstain").mean()) if "selected_expert" in controls.columns else 0.0,
    }])
    rows = []
    for st, grp in controls.groupby("state_text"):
        rows.append({
            "version_name": version_name,
            "market_state": st,
            "observations": int(len(grp)),
            "avg_production_weight": g(grp, "production_weight"),
            "avg_phasen_weight": g(grp, "phasen_weight"),
            "avg_phaseo_weight": g(grp, "phaseo_weight"),
            "avg_abstain_weight": g(grp, "abstain_weight"),
            "avg_trust_score": g(grp, "trust_score"),
            "avg_model_uncertainty": g(grp, "model_uncertainty"),
            "phaseo_selected_share": float((grp["selected_expert"] == "phaseo").mean()) if "selected_expert" in grp.columns else 0.0,
            "phasen_selected_share": float((grp["selected_expert"] == "phasen").mean()) if "selected_expert" in grp.columns else 0.0,
            "production_selected_share": float((grp["selected_expert"] == "production").mean()) if "selected_expert" in grp.columns else 0.0,
            "abstain_selected_share": float((grp["selected_expert"] == "abstain").mean()) if "selected_expert" in grp.columns else 0.0,
        })
    return overall, pd.DataFrame(rows)


def bucket_summary(version_name: str, controls: pd.DataFrame) -> pd.DataFrame:
    if "bucket" not in controls.columns:
        return pd.DataFrame(columns=["version_name", "bucket", "observations", "share"])
    rows = []
    total = len(controls)
    for bucket, grp in controls.groupby("bucket"):
        rows.append({
            "version_name": version_name,
            "bucket": str(bucket),
            "observations": int(len(grp)),
            "share": float(len(grp) / total) if total else 0.0,
            "avg_production_weight": float(grp.get("production_weight", pd.Series(dtype=float)).mean()) if "production_weight" in grp.columns else float("nan"),
            "avg_phasen_weight": float(grp.get("phasen_weight", pd.Series(dtype=float)).mean()) if "phasen_weight" in grp.columns else float("nan"),
            "avg_phaseo_weight": float(grp.get("phaseo_weight", pd.Series(dtype=float)).mean()) if "phaseo_weight" in grp.columns else float("nan"),
            "avg_abstain_weight": float(grp.get("abstain_weight", pd.Series(dtype=float)).mean()) if "abstain_weight" in grp.columns else float("nan"),
        })
    return pd.DataFrame(rows)


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
    phasep_full = full_idx.loc[PHASEP_REFERENCE]
    phasep_holdout = holdout_idx.loc[PHASEP_REFERENCE]
    phasep_holdout_returns = returns_map[PHASEP_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

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
            "full_raw_delta_vs_phasep": float(cand_full["raw_target_composite"] - phasep_full["raw_target_composite"]),
            "holdout_raw_delta_vs_phasep": float(cand_holdout["raw_target_composite"] - phasep_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_phasep": float(cand_holdout["sharpe"] - phasep_holdout["sharpe"]),
            "bootstrap_prob_vs_phasep": ppe.safe_bootstrap(cand_holdout_returns, phasep_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    phaseq_names = [n for n in candidate_names if n.startswith("improved_phaseq")]
    classification_df = pairwise_df[pairwise_df["version_name"].isin(phaseq_names)].copy()

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
            row["full_raw_delta_vs_phasep"] > 0.0
            or row["holdout_sharpe_delta_vs_phasep"] > 0.0
            or row["holdout_raw_delta_vs_phasep"] > 0.0
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_q_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_q_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_q_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_q_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_q_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_q_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase Q — Abstention-Aware / Regime-Bucket Meta-Allocator",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_q_candidates": list(PHASE_Q_CANDIDATES.keys()),
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "regret_decay_half_life_weeks": REGRET_HALF_LIFE,
        "bucket_persistence_weeks": BUCKET_PERSISTENCE,
    }
    (LAYER3_DIR / "phase_q_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
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
        model_name="phaseq_binary_phaseo_vs_production",
    )
    phasen_prob, _ = pp.walkforward_binary_classifier(
        feature_frame, target_frame["phasen_trust_label"], feature_cols,
        model_name="phaseq_binary_phasen_vs_production",
    )

    # Regret memory: EMA of (expert return - production return), shifted 1w so causal.
    phaseo_excess = returns_map[PHASEO_REFERENCE] - returns_map[PRODUCTION_PIN]
    phasen_excess = returns_map[PHASEN_REFERENCE] - returns_map[PRODUCTION_PIN]
    phaseo_regret_ema = ema_excess(phaseo_excess, REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)
    phasen_regret_ema = ema_excess(phasen_excess, REGRET_ALPHA).reindex(feature_frame.index).fillna(0.0)

    # Build each candidate.
    q1_weights, q1_controls = build_q1_abstention_aware(
        feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
    )
    q2_weights, q2_controls = build_q2_regime_bucket(
        feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_ema=phaseo_regret_ema,
        phasen_regret_ema=phasen_regret_ema,
    )
    q3_weights, q3_controls = build_q3_combo(
        feature_frame,
        weights_map=weights_map,
        phaseo_prob=phaseo_prob,
        phasen_prob=phasen_prob,
        phaseo_regret_ema=phaseo_regret_ema,
        phasen_regret_ema=phasen_regret_ema,
    )

    weight_frames = {
        "improved_phaseq_abstention_aware_meta_allocator": q1_weights,
        "improved_phaseq_regime_bucket_meta_allocator": q2_weights,
        "improved_phaseq_abstention_regime_regret_meta_allocator": q3_weights,
    }
    control_frames = {
        "improved_phaseq_abstention_aware_meta_allocator": q1_controls,
        "improved_phaseq_regime_bucket_meta_allocator": q2_controls,
        "improved_phaseq_abstention_regime_regret_meta_allocator": q3_controls,
    }

    trust_overall_rows = []
    trust_state_rows = []
    bucket_rows = []
    for version_name, etf_weights in weight_frames.items():
        path = pp.save_meta_portfolio_version(version_name, etf_weights, next_week_returns)
        controls = control_frames[version_name]
        controls.to_csv(LAYER3_DIR / f"phase_q_controls_{version_name}.csv")
        overall, by_state = trust_summary(version_name, controls)
        trust_overall_rows.append(overall)
        trust_state_rows.append(by_state)
        bucket_rows.append(bucket_summary(version_name, controls))
        ann_ret = ph.annualized_return(path["net_return"])
        ann_vol = ph.annualized_vol(path["net_return"])
        print(
            f"{version_name}: ann_return={ann_ret:.4f} "
            f"sharpe={(ann_ret / ann_vol) if ann_vol > 0 else float('nan'):.4f} "
            f"turnover={path['turnover'].dropna().mean():.4f}"
        )

    pd.concat(trust_overall_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_q_trust_summary.csv", index=False)
    pd.concat(trust_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_q_trust_by_state.csv", index=False)
    pd.concat(bucket_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_q_bucket_summary.csv", index=False)

    results = build_validation_bundle(list(weight_frames.keys()))

    print("\n=== Phase Q FULL metrics (Phase Q + fixed comparators) ===")
    cols = ["ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover", "avg_bil",
            "recovery_capture", "raw_target_composite", "raw_composite_position"]
    print(results["full"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase Q HOLDOUT metrics ===")
    print(results["holdout"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase Q pairwise vs production ===")
    cols = ["full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
            "holdout_sharpe_delta_vs_production", "bootstrap_prob_vs_production",
            "rolling_raw_win_rate_vs_production", "rolling_mean_raw_delta_vs_production",
            "full_raw_delta_vs_phasep", "holdout_sharpe_delta_vs_phasep"]
    print(results["pairwise"].set_index("version_name")[cols].round(4).to_string())

    print("\n=== Phase Q classification ===")
    print(results["classification"].set_index("version_name")[["classification", "full_raw_delta_vs_production", "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production", "bootstrap_prob_vs_production"]].round(4).to_string())
    print("\nSaved Phase Q artifacts.")


if __name__ == "__main__":
    main()
