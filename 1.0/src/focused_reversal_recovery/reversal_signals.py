"""Focused reversal signal definitions.

Only the three reversal families are scored as primary alpha:

1. short-horizon reversal
2. drawdown reversal
3. momentum/reversal interaction

Credit and volatility filters are consumed as gates, not as score families.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


FOCUSED_FAMILIES = {
    "short_horizon_reversal": {
        "score": "score_short_horizon_reversal",
        "description": "recent 1/2/4-week weakness with non-panic reversal pressure",
    },
    "drawdown_reversal": {
        "score": "score_drawdown_reversal",
        "description": "drawdown depth plus early recovery and moving-average reclaim",
    },
    "momentum_reversal_interaction": {
        "score": "score_momentum_reversal_interaction",
        "description": "medium-term trend interacting with short-term pullback or rebound",
    },
}

FOCUSED_SCORE_COLUMNS = [meta["score"] for meta in FOCUSED_FAMILIES.values()]

CANDIDATES = {
    "short_reversal_only": {
        "score": "score_short_reversal_only",
        "active": "active_short_reversal_only",
        "threshold": 0.58,
        "description": "recent negative 1/2/4-week return with non-panic filter",
    },
    "drawdown_recovery_only": {
        "score": "score_drawdown_recovery_only",
        "active": "active_drawdown_recovery_only",
        "threshold": 0.55,
        "description": "drawdown plus recovery from recent low and trend reclaim",
    },
    "pullback_in_uptrend": {
        "score": "score_pullback_in_uptrend",
        "active": "active_pullback_in_uptrend",
        "threshold": 0.55,
        "description": "medium-term uptrend with short-term pullback and benign filters",
    },
    "oversold_rebound_after_stress": {
        "score": "score_oversold_rebound_after_stress",
        "active": "active_oversold_rebound_after_stress",
        "threshold": 0.50,
        "description": "stress followed by sharp loss and early stabilization",
    },
    "momentum_reversal_interaction_score": {
        "score": "score_momentum_reversal_interaction",
        "active": "active_momentum_reversal_interaction_score",
        "threshold": 0.60,
        "description": "focused momentum/reversal interaction while avoiding bearish continuation",
    },
    "focused_reversal_composite": {
        "score": "score_focused_reversal_composite",
        "active": "active_focused_reversal_composite",
        "threshold": 0.58,
        "description": "equal blend of only the three focused reversal families",
    },
}

RULE_CANDIDATES = list(CANDIDATES.keys())
CLASSIFIER_CANDIDATES = ["classifier_logistic_reversal", "classifier_ridge_reversal"]
ALL_CANDIDATES = RULE_CANDIDATES + CLASSIFIER_CANDIDATES


def add_reversal_signals(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    non_panic = _col(p, "filter_non_panic", 1.0)
    entry_ok = _col(p, "filter_reversal_entry_ok", 1.0)
    vol_ok = _col(p, "filter_vol_stabilizing", 1.0)
    credit_ok = _col(p, "filter_credit_not_deteriorating", 1.0)
    market_ok = _col(p, "filter_market_improving_or_neutral", 1.0)

    # Family 1: sharp recent weakness, intentionally simple and short-horizon.
    short_loss = _mean(
        [
            (_col(p, "loss_magnitude_1w") / 0.03).clip(0, 1),
            (_col(p, "loss_magnitude_2w") / 0.05).clip(0, 1),
            (_col(p, "loss_magnitude_4w") / 0.08).clip(0, 1),
            (-_col(p, "ret_1w_z_52") / 1.5).clip(0, 1),
            (-_col(p, "ret_2w_z_52") / 1.5).clip(0, 1),
            (-_col(p, "ret_4w_z_52") / 1.5).clip(0, 1),
        ]
    )
    early_bounce = _mean(
        [
            (_col(p, "bounce_strength_1w") / 0.025).clip(0, 1),
            (_col(p, "bounce_strength_2w") / 0.040).clip(0, 1),
            _col(p, "above_4w_ma"),
        ]
    )
    p["recent_loss_x_non_panic"] = _col(p, "recent_loss_magnitude") * non_panic
    p["reversal_pressure_score"] = _mean([short_loss, early_bounce, p["recent_loss_x_non_panic"] / 0.06])
    p["score_short_horizon_reversal"] = _mean(
        [
            short_loss,
            _col(p, "short_term_oversold_score"),
            p["reversal_pressure_score"],
            non_panic,
        ]
    )

    # Family 2: drawdown depth, recent-low recovery, and reclaim confirmation.
    drawdown_depth = _mean(
        [
            (_col(p, "drawdown_depth_13w") / 0.10).clip(0, 1),
            (_col(p, "drawdown_depth_26w") / 0.16).clip(0, 1),
            (_col(p, "drawdown_depth_52w") / 0.22).clip(0, 1),
        ]
    )
    recovery_confirmation = _mean(
        [
            (_col(p, "recovery_from_4w_low") / 0.04).clip(0, 1),
            (_col(p, "recovery_from_8w_low") / 0.06).clip(0, 1),
            _col(p, "above_4w_ma"),
            _col(p, "above_8w_ma"),
            _col(p, "reclaim_4w_ma"),
            _col(p, "reclaim_8w_ma"),
        ]
    )
    p["score_drawdown_reversal"] = _mean(
        [
            drawdown_depth,
            recovery_confirmation,
            (_col(p, "drawdown_depth_x_recovery_confirmation") / 0.08).clip(0, 1),
            (_col(p, "bounce_from_low_after_drawdown") / 0.010).clip(0, 1),
        ]
    )

    # Family 3: two cases: uptrend pullback and downtrend rebound acceleration.
    uptrend_pullback = _mean(
        [
            (_col(p, "medium_momentum_12w") / 0.10).clip(0, 1),
            (_col(p, "medium_momentum_26w") / 0.18).clip(0, 1),
            (_col(p, "uptrend_short_pullback") / 0.04).clip(0, 1),
            _col(p, "trend_positive_short_oversold"),
        ]
    )
    downtrend_rebound = _mean(
        [
            (_col(p, "downtrend_short_bounce") / 0.04).clip(0, 1),
            (_col(p, "trend_negative_recovery_acceleration") / 0.06).clip(0, 1),
            (_col(p, "recovery_from_8w_low") / 0.06).clip(0, 1),
            _col(p, "filter_panic_fading"),
        ]
    )
    p["score_momentum_reversal_interaction"] = _mean(
        [
            uptrend_pullback,
            downtrend_rebound,
            _col(p, "momentum_reversal_interaction_raw"),
            p["score_short_horizon_reversal"],
            p["score_drawdown_reversal"],
        ]
    )

    p["score_short_reversal_only"] = p["score_short_horizon_reversal"]
    p["score_drawdown_recovery_only"] = p["score_drawdown_reversal"]
    p["score_pullback_in_uptrend"] = _mean([uptrend_pullback, _col(p, "medium_uptrend_flag"), short_loss])
    p["score_oversold_rebound_after_stress"] = _mean(
        [
            _col(p, "short_term_oversold_score"),
            _col(p, "filter_panic_fading"),
            (_col(p, "recent_stress_26w") > 0).astype(float),
            early_bounce,
            (_col(p, "vix_fading_from_13w_high").abs() / 0.25).clip(0, 1),
        ]
    )
    p["score_focused_reversal_composite"] = p[FOCUSED_SCORE_COLUMNS].mean(axis=1, skipna=True).fillna(0.0).clip(0, 1)

    continuation_bearish = p["momentum_reversal_state"].fillna("").astype(str).eq("continuation_bearish")
    p["active_short_reversal_only"] = (
        (p["score_short_reversal_only"] >= CANDIDATES["short_reversal_only"]["threshold"])
        & (non_panic == 1)
    ).astype(float)
    p["active_drawdown_recovery_only"] = (
        (p["score_drawdown_recovery_only"] >= CANDIDATES["drawdown_recovery_only"]["threshold"])
        & (non_panic == 1)
        & (market_ok == 1)
    ).astype(float)
    p["active_pullback_in_uptrend"] = (
        (p["score_pullback_in_uptrend"] >= CANDIDATES["pullback_in_uptrend"]["threshold"])
        & (vol_ok == 1)
        & (credit_ok == 1)
    ).astype(float)
    p["active_oversold_rebound_after_stress"] = (
        (p["score_oversold_rebound_after_stress"] >= CANDIDATES["oversold_rebound_after_stress"]["threshold"])
        & (non_panic == 1)
        & (vol_ok == 1)
    ).astype(float)
    p["active_momentum_reversal_interaction_score"] = (
        (p["score_momentum_reversal_interaction"] >= CANDIDATES["momentum_reversal_interaction_score"]["threshold"])
        & (~continuation_bearish)
        & (entry_ok == 1)
    ).astype(float)
    p["active_focused_reversal_composite"] = (
        (p["score_focused_reversal_composite"] >= CANDIDATES["focused_reversal_composite"]["threshold"])
        & (entry_ok == 1)
    ).astype(float)

    return p


def score_for_candidate(candidate: str) -> str:
    return CANDIDATES[candidate]["score"]


def active_for_candidate(candidate: str) -> str:
    return CANDIDATES[candidate]["active"]


def threshold_for_candidate(candidate: str) -> float:
    return float(CANDIDATES[candidate]["threshold"])


def family_for_feature(feature: str) -> str:
    for family, meta in FOCUSED_FAMILIES.items():
        if feature == meta["score"]:
            return family
    if "short" in feature or "loss" in feature or "oversold" in feature or "reversal_pressure" in feature:
        return "short_horizon_reversal"
    if "drawdown" in feature or "low" in feature or "reclaim" in feature or "bounce_from_low" in feature:
        return "drawdown_reversal"
    if "momentum" in feature or "trend" in feature or "uptrend" in feature or "downtrend" in feature:
        return "momentum_reversal_interaction"
    if feature.startswith("filter_") or "credit_" in feature or "vix" in feature or "vol" in feature:
        return "filter_only"
    return "other"


def _col(df: pd.DataFrame, name: str, default: float = 0.0) -> pd.Series:
    if name not in df.columns:
        return pd.Series(default, index=df.index, dtype=float)
    return pd.to_numeric(df[name], errors="coerce").fillna(default)


def _mean(parts: list[pd.Series]) -> pd.Series:
    frame = pd.concat(parts, axis=1)
    return frame.mean(axis=1, skipna=True).fillna(0.0).clip(0, 1)

