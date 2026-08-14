"""Composite recovery prediction scores."""

from __future__ import annotations

import pandas as pd

from .signal_families import FAMILY_SCORE_COLUMNS


def build_ensemble_predictions(features: pd.DataFrame, classifier_predictions: pd.DataFrame | None = None) -> pd.DataFrame:
    raw_cols = ["Date", "ticker", "market_state"] + FAMILY_SCORE_COLUMNS + [
        "score_equal_weight_composite",
        "score_regime_gated_composite",
        "score_and_gated_composite",
        "score_or_composite",
        "score_momentum_reversal_interaction",
    ]
    cols = list(dict.fromkeys(raw_cols))
    out = features[[c for c in cols if c in features.columns]].copy()
    out["equal_weight_active"] = out["score_equal_weight_composite"] >= 0.65
    out["regime_gated_active"] = out["score_regime_gated_composite"] >= 0.60
    out["and_gated_active"] = out["score_and_gated_composite"] >= 0.55
    out["or_score_active"] = out["score_or_composite"] >= 0.75
    out["momentum_interaction_active"] = out["score_momentum_reversal_interaction"] >= 0.65
    if classifier_predictions is not None and not classifier_predictions.empty:
        logi = classifier_predictions[classifier_predictions["model"] == "logistic_l2"][
            ["Date", "ticker", "prediction", "active"]
        ].rename(columns={"prediction": "logistic_probability", "active": "logistic_active"})
        out = out.merge(logi, on=["Date", "ticker"], how="left")
    return out
