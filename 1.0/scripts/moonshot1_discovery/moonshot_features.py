"""Causal feature panel and targets for the moonshot discovery sprint.

Causality convention (stricter than production): every feature is shifted one
extra week beyond the Friday-close convention, so week-t decisions use only
week t-1 information. The Layer 2B/frontier signal files already embed their
own construction lags; the extra shift removes any timing dispute.

Feature groups (used for ablations):
    trend     - market trend, SPY momentum, distance from highs/lows
    breadth   - Layer 2B breadth stack
    credit    - R2A credit confirmation components
    vol       - VIX term structure, correlation stress
    quality   - R2A path clarity / persistence / leadership
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from path1_path3_research_utils import (  # noqa: E402
    DATA,
    HUB,
    OFFENSE,
    load_numeric_panel,
    load_states,
    load_weekly_prices,
    load_weekly_returns_file,
)

PHASE1_R2 = DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
PHASE4_LEAD = DATA / "research" / "frontier_phase4" / "leadership_signals.csv"

FEATURE_GROUPS = {
    "trend": ["market_trend_positive", "spy_ret_4w", "spy_ret_13w", "spy_dist_26w_high", "spy_dist_26w_low", "market_drawdown"],
    "breadth": ["breadth_sma_43", "breadth_13w_mom", "breadth_change_4w", "breadth_quality_score"],
    "credit": ["credit_confirmation", "credit_relative_momentum"],
    "vol": ["vix_slope_1m_3m", "vix_contango", "avg_corr_risk_off_z"],
    "quality": ["path_clarity_r2", "state_persistence_score", "leadership_quality_composite", "transition_non_stress_prob"],
}
ALL_FEATURES = [f for group in FEATURE_GROUPS.values() for f in group]


def _dated(path: Path, warnings: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    col = "date" if "date" in df.columns else "Date"
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df.dropna(subset=[col]).set_index(col).sort_index()


def build_feature_panel(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    """Assemble the causal feature matrix, shifted one week, on `index`."""

    states = load_states(warnings)
    prices = load_weekly_prices(warnings)
    vix = load_numeric_panel(HUB / "vix_term_structure.csv", warnings, "vix_term_structure.csv")
    r2 = _dated(PHASE1_R2, warnings)
    lead = _dated(PHASE4_LEAD, warnings)

    spy = prices["SPY"]
    feats = pd.DataFrame(index=prices.index)
    feats["spy_ret_4w"] = spy.pct_change(4)
    feats["spy_ret_13w"] = spy.pct_change(13)
    feats["spy_dist_26w_high"] = spy / spy.rolling(26).max() - 1.0
    feats["spy_dist_26w_low"] = spy / spy.rolling(26).min() - 1.0

    for col in [
        "market_trend_positive", "market_drawdown", "breadth_sma_43", "breadth_13w_mom",
        "breadth_change_4w", "avg_corr_risk_off_z", "transition_non_stress_prob",
    ]:
        feats[col] = pd.to_numeric(states.get(col), errors="coerce")

    for col in ["breadth_quality_score", "credit_confirmation", "credit_relative_momentum",
                "path_clarity_r2", "state_persistence_score"]:
        feats[col] = pd.to_numeric(r2.get(col), errors="coerce")

    feats["leadership_quality_composite"] = pd.to_numeric(
        lead.get("leadership_quality_composite"), errors="coerce"
    )
    feats["vix_slope_1m_3m"] = pd.to_numeric(vix.get("slope_1m_3m"), errors="coerce")
    feats["vix_contango"] = pd.to_numeric(vix.get("contango"), errors="coerce")

    return feats[ALL_FEATURES].shift(1).reindex(index)


def panic_improvement_composite(feats: pd.DataFrame) -> pd.DataFrame:
    """Panic-but-improving (PBI) confirmation count, causal by construction.

    Three binary confirmations evaluated on the (already one-week-shifted)
    feature panel:
        c_credit  - credit confirmation positive
        c_breadth - 4-week breadth change positive
        c_vix     - VIX term structure back in contango
    plus a deep-drawdown context flag (market drawdown at or below -10%).
    """

    out = pd.DataFrame(index=feats.index)
    out["c_credit"] = (feats["credit_confirmation"] > 0).astype(float)
    out["c_breadth"] = (feats["breadth_change_4w"] > 0).astype(float)
    out["c_vix"] = (feats["vix_slope_1m_3m"] > 0).astype(float)
    known = feats[["credit_confirmation", "breadth_change_4w", "vix_slope_1m_3m"]].notna().all(axis=1)
    out["confirm_count"] = out[["c_credit", "c_breadth", "c_vix"]].sum(axis=1).where(known)
    out["deep_dd_context"] = (feats["market_drawdown"] <= -0.10).astype(float)
    out["market_drawdown_ctx"] = feats["market_drawdown"]
    return out


def offense_excess_forward(
    final_weights: pd.DataFrame,
    index: pd.Index,
    warnings: list[str],
    horizon: int = 4,
) -> pd.Series:
    """Forward `horizon`-week return of the GGG offense basket minus BIL.

    This is the decision-quality target: a positive value means scaling
    offense up at week t would have helped over the next `horizon` weeks.
    Uses the same next-week-return convention as the production path.
    """

    weekly = load_weekly_returns_file(warnings)
    offense_cols = [c for c in final_weights.columns if c in OFFENSE and c in weekly.columns]
    w = final_weights[offense_cols].reindex(index).fillna(0.0)
    row_sum = w.sum(axis=1).replace(0.0, np.nan)
    w_norm = w.div(row_sum, axis=0)
    fwd = weekly[offense_cols].shift(-1).reindex(index)
    off_week = (w_norm * fwd).sum(axis=1).where(row_sum.notna())
    bil_week = weekly["BIL"].shift(-1).reindex(index).fillna(0.0)
    excess_week = off_week - bil_week
    out = pd.Series(index=index, dtype=float)
    arr = excess_week.to_numpy()
    for i in range(len(index)):
        chunk = arr[i : i + horizon]
        if len(chunk) < horizon or np.isnan(chunk).any():
            out.iloc[i] = np.nan
        else:
            out.iloc[i] = float(np.prod(1.0 + chunk) - 1.0)
    return out


def expanding_standardize(feats: pd.DataFrame, min_periods: int = 104) -> pd.DataFrame:
    """Walk-forward z-scores: each row standardized by expanding past stats."""

    mean = feats.expanding(min_periods=min_periods).mean().shift(1)
    std = feats.expanding(min_periods=min_periods).std(ddof=1).shift(1)
    return (feats - mean) / std.replace(0.0, np.nan)
