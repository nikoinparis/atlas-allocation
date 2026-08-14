"""Reusable bounded deployment rules for research harnesses.

Rules return modifier series only. They do not write files and do not directly
mutate weights. Inputs are expected to come from C3 confidence inputs, whose
composed scores are already lagged one week; callers can request an additional
lag if they pass raw inputs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from path1_path3_research_utils import DATA


CONFIDENCE_PATH = DATA / "research" / "native_confidence" / "c3_confidence_inputs.csv"


def load_confidence_inputs(index: pd.Index, already_lagged: bool = True) -> pd.DataFrame:
    """Load C3 confidence inputs and align them to a portfolio weekly index."""

    if not CONFIDENCE_PATH.exists():
        out = pd.DataFrame(index=index)
        for col in REQUIRED_NUMERIC_COLUMNS:
            out[col] = 0.5
        out["market_state"] = "unknown"
        out["offense_eligible"] = False
        return out
    df = pd.read_csv(CONFIDENCE_PATH)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    out = df.reindex(index).ffill().bfill()
    for col in REQUIRED_NUMERIC_COLUMNS:
        if col not in out.columns:
            out[col] = 0.5
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.5).clip(0.0, 1.0)
        if not already_lagged:
            out[col] = out[col].shift(1).ffill().fillna(0.5)
    if "market_state" not in out.columns:
        out["market_state"] = "unknown"
    if "offense_eligible" not in out.columns:
        out["offense_eligible"] = False
    out["offense_eligible"] = out["offense_eligible"].astype(str).str.lower().isin(["true", "1", "yes"])
    return out


REQUIRED_NUMERIC_COLUMNS = [
    "breadth_confidence",
    "sector_confidence",
    "risk_on_confidence",
    "macro_stress_filter",
    "dollar_pressure_filter",
    "transition_quality_score",
    "combined_market_quality_score",
    "offense_eligibility_score",
    "deterioration_score",
    "signal_agreement",
    "signal_dispersion",
]


def _score(inputs: pd.DataFrame, column: str, default: float = 0.5) -> pd.Series:
    if column not in inputs.columns:
        return pd.Series(default, index=inputs.index)
    return pd.to_numeric(inputs[column], errors="coerce").fillna(default).clip(0.0, 1.0)


def _bounded(series: pd.Series, lower: float = 0.93, upper: float = 1.03) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(1.0).clip(lower, upper)


def _centered_modifier(score: pd.Series, max_increase: float = 0.02, max_reduction: float = 0.05) -> pd.Series:
    centered = score.fillna(0.5).clip(0.0, 1.0) - 0.5
    mod = 1.0 + np.where(centered >= 0.0, centered / 0.5 * max_increase, centered / 0.5 * max_reduction)
    return _bounded(pd.Series(mod, index=score.index), 1.0 - max_reduction, 1.0 + max_increase)


def offense_eligibility_rule(inputs: pd.DataFrame, min_score: float = 0.55, weak_multiplier: float = 0.97) -> pd.Series:
    """Intended checkpoint: offense_budget.

    Suppresses offense slightly when the lagged offense eligibility score is
    weak or when the explicit eligibility flag is false.
    """

    score = _score(inputs, "offense_eligibility_score")
    eligible = inputs.get("offense_eligible", pd.Series(False, index=inputs.index)).astype(bool)
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[(score < min_score) | (~eligible)] = weak_multiplier
    return _bounded(mod, weak_multiplier, 1.0)


def breadth_confirmation_rule(inputs: pd.DataFrame, weak_threshold: float = 0.45) -> pd.Series:
    """Intended checkpoint: regime_multipliers.

    Applies a small risky-budget reduction when lagged ETF breadth confirmation
    is weak; no aggressive risk increase is allowed.
    """

    breadth = _score(inputs, "breadth_confidence")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[breadth < weak_threshold] = 0.96
    mod.loc[breadth > 0.70] = 1.01
    return _bounded(mod, 0.96, 1.01)


def sector_breadth_confirmation_rule(inputs: pd.DataFrame, weak_threshold: float = 0.45) -> pd.Series:
    """Intended checkpoint: regime_multipliers.

    Uses sector breadth as a less noisy participation-quality check.
    """

    sector = _score(inputs, "sector_confidence")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[sector < weak_threshold] = 0.965
    mod.loc[sector > 0.70] = 1.01
    return _bounded(mod, 0.965, 1.01)


def risk_on_participation_rule(inputs: pd.DataFrame, weak_threshold: float = 0.45) -> pd.Series:
    """Intended checkpoint: offense_budget.

    Reduces offense only when lagged risk-on participation is poor.
    """

    risk_on = _score(inputs, "risk_on_confidence")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[risk_on < weak_threshold] = 0.965
    return _bounded(mod, 0.965, 1.0)


def dollar_pressure_filter(inputs: pd.DataFrame, pressure_threshold: float = 0.35) -> pd.Series:
    """Intended checkpoint: offense_budget.

    Higher C3 dollar_pressure_filter means less dollar pressure; this rule
    trims offense when the lagged pressure filter is low.
    """

    dollar_filter = _score(inputs, "dollar_pressure_filter")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[dollar_filter < pressure_threshold] = 0.97
    mod.loc[dollar_filter < pressure_threshold - 0.10] = 0.95
    return _bounded(mod, 0.95, 1.0)


def macro_stress_filter(inputs: pd.DataFrame, stress_threshold: float = 0.40) -> pd.Series:
    """Intended checkpoint: regime_multipliers.

    Trims risky budget only when lagged macro/VIX/credit stress is active.
    """

    macro = _score(inputs, "macro_stress_filter")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[macro < stress_threshold] = 0.965
    mod.loc[macro < stress_threshold - 0.10] = 0.94
    return _bounded(mod, 0.94, 1.0)


def deterioration_acceleration_rule(inputs: pd.DataFrame, threshold: float = 0.65) -> pd.Series:
    """Intended checkpoint: derisk_smoothing.

    Speeds up de-risking when lagged deterioration is high. The rule never
    increases risk.
    """

    deterioration = _score(inputs, "deterioration_score")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[deterioration > threshold] = 0.96
    mod.loc[deterioration > threshold + 0.15] = 0.93
    return _bounded(mod, 0.93, 1.0)


def transition_quality_rerisk_rule(inputs: pd.DataFrame, threshold: float = 0.62) -> pd.Series:
    """Intended checkpoint: transition_rerisk_smoothing.

    Allows a tiny re-risk boost only when transition quality and breadth are
    both strong, and never in stressed_panic.
    """

    transition = _score(inputs, "transition_quality_score")
    breadth = _score(inputs, "breadth_confidence")
    state = inputs.get("market_state", pd.Series("unknown", index=inputs.index)).astype(str)
    mod = pd.Series(1.0, index=inputs.index)
    strong = (transition >= threshold) & (breadth >= 0.58) & (~state.eq("stressed_panic"))
    weak = (transition < 0.42) & (~state.eq("stressed_panic"))
    mod.loc[strong] = 1.015
    mod.loc[weak] = 0.985
    return _bounded(mod, 0.985, 1.015)


def confidence_score_modifier(inputs: pd.DataFrame, max_increase: float = 0.02, max_reduction: float = 0.05) -> pd.Series:
    """Intended checkpoint: volatility_risk_overlay or regime_multipliers.

    Converts the lagged combined market-quality score into a small bounded
    risky-budget modifier. It suppresses any increase in stressed_panic.
    """

    quality = _score(inputs, "combined_market_quality_score")
    mod = _centered_modifier(quality, max_increase=max_increase, max_reduction=max_reduction)
    state = inputs.get("market_state", pd.Series("unknown", index=inputs.index)).astype(str)
    mod.loc[state.eq("stressed_panic") & (mod > 1.0)] = 1.0
    return _bounded(mod, 1.0 - max_reduction, 1.0 + max_increase)


def final_safety_clamp(inputs: pd.DataFrame) -> pd.Series:
    """Intended checkpoint: final_etf_lookthrough_weights.

    Final bounded safety modifier for research comparison only. It never
    increases risk and should not be a preferred production insertion point.
    """

    macro = _score(inputs, "macro_stress_filter")
    deterioration = _score(inputs, "deterioration_score")
    mod = pd.Series(1.0, index=inputs.index)
    mod.loc[(macro < 0.35) | (deterioration > 0.70)] = 0.97
    mod.loc[(macro < 0.25) | (deterioration > 0.82)] = 0.94
    return _bounded(mod, 0.94, 1.0)


def combined_conservative_rule(inputs: pd.DataFrame) -> pd.Series:
    """Intended checkpoint: volatility_risk_overlay.

    Blends confidence, breadth, transition quality, macro stress, dollar
    pressure, and deterioration into a tiny bounded deployment modifier.
    """

    quality = (
        0.35 * _score(inputs, "combined_market_quality_score")
        + 0.20 * _score(inputs, "breadth_confidence")
        + 0.15 * _score(inputs, "transition_quality_score")
        + 0.15 * _score(inputs, "macro_stress_filter")
        + 0.10 * _score(inputs, "dollar_pressure_filter")
        + 0.05 * (1.0 - _score(inputs, "deterioration_score"))
    )
    mod = _centered_modifier(quality.clip(0.0, 1.0), max_increase=0.02, max_reduction=0.05)
    state = inputs.get("market_state", pd.Series("unknown", index=inputs.index)).astype(str)
    mod.loc[state.eq("stressed_panic") & (mod > 1.0)] = 1.0
    return _bounded(mod, 0.95, 1.02)


RULE_REGISTRY = {
    "offense_eligibility": {
        "checkpoint": "offense_budget",
        "function": offense_eligibility_rule,
        "description": "Small offense suppression when lagged eligibility is weak.",
    },
    "breadth_confirmation": {
        "checkpoint": "regime_multipliers",
        "function": breadth_confirmation_rule,
        "description": "Small risky-budget adjustment from ETF breadth confirmation.",
    },
    "sector_breadth_confirmation": {
        "checkpoint": "regime_multipliers",
        "function": sector_breadth_confirmation_rule,
        "description": "Small risky-budget adjustment from sector breadth confirmation.",
    },
    "risk_on_participation": {
        "checkpoint": "offense_budget",
        "function": risk_on_participation_rule,
        "description": "Offense trim when risk-on participation is weak.",
    },
    "dollar_pressure": {
        "checkpoint": "offense_budget",
        "function": dollar_pressure_filter,
        "description": "Offense trim when dollar pressure is high.",
    },
    "macro_stress": {
        "checkpoint": "regime_multipliers",
        "function": macro_stress_filter,
        "description": "Risk trim when macro/VIX/credit stress is active.",
    },
    "deterioration_acceleration": {
        "checkpoint": "derisk_smoothing",
        "function": deterioration_acceleration_rule,
        "description": "Faster de-risking when deterioration is high.",
    },
    "transition_quality_rerisk": {
        "checkpoint": "transition_rerisk_smoothing",
        "function": transition_quality_rerisk_rule,
        "description": "Tiny re-risk boost only during high-quality transitions.",
    },
    "confidence_score_modifier": {
        "checkpoint": "volatility_risk_overlay",
        "function": confidence_score_modifier,
        "description": "Combined confidence modifier at overlay-aware checkpoint.",
    },
    "final_safety_clamp": {
        "checkpoint": "final_etf_lookthrough_weights",
        "function": final_safety_clamp,
        "description": "Final no-increase safety clamp for comparison.",
    },
    "combined_conservative": {
        "checkpoint": "volatility_risk_overlay",
        "function": combined_conservative_rule,
        "description": "Conservative multi-input confidence deployment rule.",
    },
}


def rule_summary() -> pd.DataFrame:
    rows = []
    for name, spec in RULE_REGISTRY.items():
        rows.append(
            {
                "rule": name,
                "intended_checkpoint": spec["checkpoint"],
                "bounded": True,
                "lagged_inputs": "C3 one-week lagged scores",
                "description": spec["description"],
            }
        )
    return pd.DataFrame(rows)
