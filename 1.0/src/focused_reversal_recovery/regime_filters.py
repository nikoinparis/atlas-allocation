"""Coarse regime filters for focused reversal research.

Credit and volatility appear here only as filters. They do not define primary
alpha families and are not used as standalone score families.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


FILTER_COLUMNS = [
    "filter_non_panic",
    "filter_vol_stabilizing",
    "filter_realized_vol_not_exploding",
    "filter_vix_not_extreme",
    "filter_credit_not_deteriorating",
    "filter_risk_regime_not_panic",
    "filter_market_improving_or_neutral",
    "filter_reversal_entry_ok",
]


def add_regime_filters(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    market_state = p["market_state"].fillna("").astype(str).str.lower()
    risk_state = p["risk_state"].fillna("").astype(str).str.lower()
    signal_environment = p["signal_environment"].fillna("").astype(str).str.lower()

    panic_words = market_state.str.contains("panic|crash|stress", regex=True, na=False)
    risk_off_words = risk_state.str.contains("risk_off|panic|crash", regex=True, na=False)
    p["filter_non_panic"] = (~(panic_words & risk_off_words)).astype(float)
    p["filter_risk_regime_not_panic"] = (~risk_off_words).astype(float)

    p["filter_vix_not_extreme"] = (
        pd.to_numeric(p["vix_percentile_52w"], errors="coerce").fillna(0.50) <= 0.90
    ).astype(float)
    p["filter_vol_stabilizing"] = (
        (pd.to_numeric(p["vix_change_2w"], errors="coerce").fillna(0.0) <= 0.20)
        & (pd.to_numeric(p["vix_change_4w"], errors="coerce").fillna(0.0) <= 0.35)
        & (pd.to_numeric(p["vix_percentile_52w"], errors="coerce").fillna(0.50) <= 0.85)
    ).astype(float)
    p["filter_realized_vol_not_exploding"] = (
        pd.to_numeric(p["realized_vol_change_4w"], errors="coerce").fillna(0.0) <= 0.50
    ).astype(float)

    p["filter_credit_not_deteriorating"] = (
        (pd.to_numeric(p["credit_hyg_lqd_ret_4w"], errors="coerce").fillna(0.0) >= -0.025)
        & (pd.to_numeric(p["credit_hyg_lqd_ma_slope_4w"], errors="coerce").fillna(0.0) >= -0.015)
    ).astype(float)

    p["filter_market_improving_or_neutral"] = (
        market_state.str.contains("neutral|bull|recovery|expansion|mixed", regex=True, na=False)
        | signal_environment.str.contains("reversal|risk_on|mixed", regex=True, na=False)
        | (pd.to_numeric(p["market_trend_positive"], errors="coerce").fillna(0.0) > 0)
        | (pd.to_numeric(p["transition_non_stress_prob"], errors="coerce").fillna(0.5) >= 0.45)
    ).astype(float)

    p["filter_panic_fading"] = (
        (pd.to_numeric(p["recent_stress_26w"], errors="coerce").fillna(0.0) > 0)
        & (pd.to_numeric(p["vix_change_2w"], errors="coerce").fillna(0.0) <= 0.10)
        & (pd.to_numeric(p["risk_basket_ret_1w"], errors="coerce").fillna(0.0) >= -0.03)
    ).astype(float)

    p["filter_reversal_entry_ok"] = _mean(
        [
            p["filter_non_panic"],
            p["filter_vol_stabilizing"],
            p["filter_realized_vol_not_exploding"],
            p["filter_vix_not_extreme"],
            p["filter_credit_not_deteriorating"],
            p["filter_risk_regime_not_panic"],
        ]
    )
    p["filter_reversal_entry_ok"] = (p["filter_reversal_entry_ok"] >= 0.80).astype(float)

    return p


def _mean(parts: list[pd.Series]) -> pd.Series:
    frame = pd.concat(parts, axis=1)
    return frame.mean(axis=1, skipna=True).fillna(0.0).clip(0, 1)

