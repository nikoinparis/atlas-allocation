from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "02_layer1_signals"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"


def load_notebook_namespace(notebook_path: Path, code_cell_indices: list[int]) -> dict:
    notebook = json.loads(notebook_path.read_text())
    namespace: dict = {"__name__": "__main__"}
    for idx in code_cell_indices:
        cell = notebook["cells"][idx]
        if cell["cell_type"] != "code":
            continue
        exec(compile("".join(cell["source"]), f"{notebook_path.name}:cell_{idx}", "exec"), namespace)
    return namespace


def replace_or_append_row(df: pd.DataFrame, key_col: str, row: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([row])
    out = df.copy()
    if key_col in out.columns:
        out = out[out[key_col] != row[key_col]]
    return pd.concat([out, pd.DataFrame([row])], ignore_index=True)


def safe_mean(series: pd.Series) -> float:
    series = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    return float(series.mean()) if not series.empty else np.nan


def cumulative_return(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return np.nan
    return float((1.0 + series).prod() - 1.0)


def window_drawdown(return_series: pd.Series) -> float:
    series = pd.Series(return_series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if series.empty:
        return np.nan
    wealth = (1.0 + series).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def classify_allocations(weight_panel: pd.DataFrame, cash_proxy: str) -> tuple[list[str], list[str]]:
    defensive_assets = [ticker for ticker in ["IEF", "SHY", "TLT", "TIP", "GLD"] if ticker in weight_panel.columns and ticker != cash_proxy]
    offensive_assets = [ticker for ticker in weight_panel.columns if ticker not in set(defensive_assets + [cash_proxy])]
    return offensive_assets, defensive_assets


def version_state_label(current_offensive: float, current_defensive: float, current_cash: float) -> str:
    if current_cash + current_defensive >= 0.55:
        return "defensive"
    if current_offensive >= 0.60 and current_cash <= 0.20:
        return "risk_on"
    return "neutral"


def load_benchmark_returns(file_name: str) -> pd.Series:
    frame = pd.read_csv(LAYER2A_DIR / file_name, parse_dates=["Date"])
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    frame = frame.set_index("Date").sort_index()
    return pd.Series(frame["net_return"], name=file_name.replace("strategy_returns_", "").replace(".csv", ""))


ns3 = load_notebook_namespace(
    ROOT / "03_layer2a_strategy_logic.ipynb",
    [2, 3, 4, 5, 6, 8],
)
ns5 = load_notebook_namespace(
    ROOT / "05_layer3_portfolio_construction.ipynb",
    [2, 4, 5, 7, 9, 11],
)

SELF_GATED_SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "taa_10m_sma",
]

OFFENSIVE_SLEEVE_CANDIDATES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "composite_selective_signals",
    "composite_regime_offense_component",
    "composite_selective_trend_ensemble",
    "composite_selective_concentrated",
    "composite_equal_weight",
    "composite_trend_quality_module",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "sector_rotation_with_sma_filter",
]
DEFENSIVE_SLEEVE_CANDIDATES = ["composite_regime_conditioned", "composite_regime_defense_component", "taa_10m_sma"]
PHASEC_LEARNED_QUALITY_CACHE: dict[tuple[str, ...], pd.DataFrame] = {}
FILTERED_VERSION_NAMES = {
    name.strip()
    for name in os.environ.get("BUILD_VERSION_NAMES", "").split(",")
    if name.strip()
}
FILTERED_VERSION_BUILD = bool(FILTERED_VERSION_NAMES)
SAVE_ALLOCATOR_CHECKPOINTS = os.environ.get("SAVE_ALLOCATOR_CHECKPOINTS", "").strip() == "1"
ALLOCATOR_CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
PHASE4_SIGNAL_LOOKUPS: dict[str, dict[pd.Timestamp, object]] = {}
PHASE4B_SIGNAL_LOOKUPS: dict[str, dict[pd.Timestamp, object]] = {}


def checkpoint_stage_template(sleeve_names: list[str]) -> pd.Series:
    columns = list(dict.fromkeys(list(sleeve_names) + [f"cash::{ns5['cash_proxy']}"]))
    return pd.Series(0.0, index=columns, dtype=float)


def _shift_bucket_mass(
    weights: pd.Series,
    *,
    source_names: list[str],
    shift_amount: float,
    target_mix: dict[str, float],
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    valid_sources = [name for name in source_names if name in adjusted.index]
    valid_targets = {name: float(weight) for name, weight in target_mix.items() if name in adjusted.index and float(weight) > 0.0}
    if not valid_sources or not valid_targets or shift_amount <= 0.0:
        return adjusted

    source_weights = adjusted.reindex(valid_sources).fillna(0.0).clip(lower=0.0)
    source_total = float(source_weights.sum())
    if source_total <= 1e-12:
        return adjusted
    shift = float(min(shift_amount, source_total * 0.35))
    if shift <= 1e-12:
        return adjusted

    adjusted.loc[valid_sources] = (source_weights - shift * source_weights / source_total).clip(lower=0.0)
    target_share = pd.Series(valid_targets, dtype=float)
    target_share = target_share / float(target_share.sum())
    for name, share in target_share.items():
        adjusted.loc[name] = float(adjusted.get(name, 0.0) or 0.0) + shift * float(share)
    return adjusted


def _phase4_shift_to_sector_budget(
    weights: pd.Series,
    *,
    sector_sleeve: str,
    target_budget: float,
    source_names: list[str],
) -> pd.Series:
    """Move sleeve budget into a dedicated Phase 4 sector sleeve.

    This is intentionally deterministic and state-gated by the caller. It
    targets a fixed sector-sleeve budget in confirmed non-stressed states,
    funded proportionally from cash, defense, and older diversified offense
    sleeves. It never runs in stressed_panic.
    """
    adjusted = pd.Series(weights, dtype=float).copy()
    if sector_sleeve not in adjusted.index or target_budget <= 0.0:
        return adjusted
    current = float(adjusted.get(sector_sleeve, 0.0) or 0.0)
    needed = max(0.0, float(target_budget) - current)
    if needed <= 1e-12:
        return adjusted

    valid_sources = [name for name in source_names if name in adjusted.index and name != sector_sleeve]
    if not valid_sources:
        return adjusted
    source_weights = adjusted.reindex(valid_sources).fillna(0.0).clip(lower=0.0)
    source_total = float(source_weights.sum())
    if source_total <= 1e-12:
        return adjusted

    shift = min(needed, source_total * 0.80)
    if shift <= 1e-12:
        return adjusted
    adjusted.loc[valid_sources] = (source_weights - shift * source_weights / source_total).clip(lower=0.0)
    adjusted.loc[sector_sleeve] = current + shift
    return adjusted


def _rebalance_bucket_to_mix(
    weights: pd.Series,
    *,
    bucket_names: list[str],
    target_mix: dict[str, float],
    strength: float,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    valid_bucket = [name for name in bucket_names if name in adjusted.index]
    valid_targets = {name: float(weight) for name, weight in target_mix.items() if name in valid_bucket and float(weight) > 0.0}
    if not valid_bucket or not valid_targets or strength <= 0.0:
        return adjusted

    bucket_weights = adjusted.reindex(valid_bucket).fillna(0.0).clip(lower=0.0)
    bucket_total = float(bucket_weights.sum())
    if bucket_total <= 1e-12:
        return adjusted

    current_share = bucket_weights / bucket_total
    target_share = pd.Series(0.0, index=valid_bucket, dtype=float)
    target_series = pd.Series(valid_targets, dtype=float)
    target_series = target_series / float(target_series.sum())
    target_share.loc[target_series.index] = target_series
    blended = ((1.0 - strength) * current_share + strength * target_share).clip(lower=0.0)
    if float(blended.sum()) <= 1e-12:
        return adjusted
    adjusted.loc[valid_bucket] = bucket_total * (blended / float(blended.sum()))
    return adjusted


def _apply_phase_rr_bucket_architecture(
    weights: pd.Series,
    *,
    tilt_mode: str,
    market_state: str | None,
    strong_neutral_flag: bool,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    offense_bucket = [
        name
        for name in [
            "dual_momentum_topn",
            "cta_trend_long_only",
            "composite_selective_signals",
        ]
        if name in adjusted.index
    ]
    composite_bucket = [name for name in ["composite_regime_conditioned"] if name in adjusted.index]
    if not offense_bucket or not composite_bucket:
        return adjusted

    include_good = tilt_mode in {
        "phase_rr_good_state_bucket_participation",
        "phase_rr_combined_bucket_allocator",
    }
    include_recovery = tilt_mode in {
        "phase_rr_recovery_bucket_repair",
        "phase_rr_combined_bucket_allocator",
    }

    if include_good and market_state == "calm_trend":
        shift_amount = 0.05 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.04
        adjusted = _shift_bucket_mass(
            adjusted,
            source_names=composite_bucket,
            shift_amount=shift_amount,
            target_mix={
                "composite_selective_signals": 0.55,
                "dual_momentum_topn": 0.30,
                "cta_trend_long_only": 0.15,
            },
        )
        adjusted = _rebalance_bucket_to_mix(
            adjusted,
            bucket_names=offense_bucket,
            target_mix={
                "composite_selective_signals": 0.52,
                "dual_momentum_topn": 0.30,
                "cta_trend_long_only": 0.18,
            },
            strength=0.35 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.28,
        )
    elif include_good and strong_neutral_flag:
        shift_amount = 0.035 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.025
        adjusted = _shift_bucket_mass(
            adjusted,
            source_names=composite_bucket,
            shift_amount=shift_amount,
            target_mix={
                "dual_momentum_topn": 0.40,
                "cta_trend_long_only": 0.35,
                "composite_selective_signals": 0.25,
            },
        )
        adjusted = _rebalance_bucket_to_mix(
            adjusted,
            bucket_names=offense_bucket,
            target_mix={
                "dual_momentum_topn": 0.40,
                "cta_trend_long_only": 0.34,
                "composite_selective_signals": 0.26,
            },
            strength=0.25 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.20,
        )

    if include_recovery and market_state == "recovery_confirmed":
        shift_amount = 0.065 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.055
        adjusted = _shift_bucket_mass(
            adjusted,
            source_names=composite_bucket,
            shift_amount=shift_amount,
            target_mix={
                "cta_trend_long_only": 0.60,
                "taa_10m_sma": 0.25,
                "dual_momentum_topn": 0.15,
            },
        )
        adjusted = _rebalance_bucket_to_mix(
            adjusted,
            bucket_names=offense_bucket,
            target_mix={
                "cta_trend_long_only": 0.62,
                "dual_momentum_topn": 0.24,
                "composite_selective_signals": 0.14,
            },
            strength=0.45 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.38,
        )
    elif include_recovery and market_state == "recovery_fragile":
        shift_amount = 0.055 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.045
        adjusted = _shift_bucket_mass(
            adjusted,
            source_names=composite_bucket,
            shift_amount=shift_amount,
            target_mix={
                "cta_trend_long_only": 0.45,
                "dual_momentum_topn": 0.35,
                "taa_10m_sma": 0.20,
            },
        )
        adjusted = _rebalance_bucket_to_mix(
            adjusted,
            bucket_names=offense_bucket,
            target_mix={
                "cta_trend_long_only": 0.45,
                "dual_momentum_topn": 0.40,
                "composite_selective_signals": 0.15,
            },
            strength=0.35 if tilt_mode == "phase_rr_combined_bucket_allocator" else 0.28,
        )
    return adjusted


def _apply_explicit_bucket_budget(
    weights: pd.Series,
    *,
    target_bucket_weights: dict[str, float],
    offense_target_mix: dict[str, float] | None = None,
    offense_mix_strength: float = 0.40,
    defense_target_mix: dict[str, float] | None = None,
    defense_mix_strength: float = 0.40,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    bucket_members = {
        "offense": [name for name in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"] if name in adjusted.index],
        "defense": [name for name in ["taa_10m_sma", "composite_regime_defense_component"] if name in adjusted.index],
        "composite": [name for name in ["composite_regime_conditioned"] if name in adjusted.index],
    }
    valid_buckets = {bucket: members for bucket, members in bucket_members.items() if members}
    target_series = pd.Series({bucket: float(weight) for bucket, weight in target_bucket_weights.items() if bucket in valid_buckets}, dtype=float)
    if target_series.empty or float(target_series.sum()) <= 1e-12:
        return adjusted
    target_series = target_series / float(target_series.sum())

    for bucket_name, members in valid_buckets.items():
        bucket_total_target = float(target_series.get(bucket_name, 0.0))
        current_weights = adjusted.reindex(members).fillna(0.0).clip(lower=0.0)
        current_total = float(current_weights.sum())
        if current_total <= 1e-12:
            current_share = pd.Series(1.0 / len(members), index=members, dtype=float)
        else:
            current_share = current_weights / current_total

        if bucket_name == "offense" and offense_target_mix:
            target_mix = pd.Series(
                {name: float(weight) for name, weight in offense_target_mix.items() if name in members and float(weight) > 0.0},
                dtype=float,
            )
            if not target_mix.empty and float(target_mix.sum()) > 1e-12:
                target_mix = target_mix / float(target_mix.sum())
                full_target = pd.Series(0.0, index=members, dtype=float)
                full_target.loc[target_mix.index] = target_mix
                internal_share = ((1.0 - offense_mix_strength) * current_share + offense_mix_strength * full_target).clip(lower=0.0)
                if float(internal_share.sum()) > 1e-12:
                    current_share = internal_share / float(internal_share.sum())

        # Phase AAA — symmetric defense_target_mix for within-defense rebudget.
        if bucket_name == "defense" and defense_target_mix:
            d_target_mix = pd.Series(
                {name: float(weight) for name, weight in defense_target_mix.items() if name in members and float(weight) > 0.0},
                dtype=float,
            )
            if not d_target_mix.empty and float(d_target_mix.sum()) > 1e-12:
                d_target_mix = d_target_mix / float(d_target_mix.sum())
                full_target = pd.Series(0.0, index=members, dtype=float)
                full_target.loc[d_target_mix.index] = d_target_mix
                internal_share = ((1.0 - defense_mix_strength) * current_share + defense_mix_strength * full_target).clip(lower=0.0)
                if float(internal_share.sum()) > 1e-12:
                    current_share = internal_share / float(internal_share.sum())

        adjusted.loc[members] = bucket_total_target * current_share
    return adjusted


def _apply_bucket_share_caps(
    weights: pd.Series,
    *,
    bucket_names: list[str],
    share_caps: dict[str, float],
    reallocate_mix: dict[str, float],
) -> pd.Series:
    """Hard-cap bucket members by share of the bucket and reallocate excess.

    Used for bounded pruning phases where soft target mixes were not enough
    to keep weak sleeves from re-absorbing confirmed-state offense budget.
    """
    adjusted = pd.Series(weights, dtype=float).copy()
    members = [name for name in bucket_names if name in adjusted.index]
    if not members:
        return adjusted

    bucket_total = float(adjusted.reindex(members).fillna(0.0).clip(lower=0.0).sum())
    if bucket_total <= 1e-12:
        return adjusted

    excess = 0.0
    for name, share_cap in share_caps.items():
        if name not in members:
            continue
        cap_weight = float(max(0.0, share_cap)) * bucket_total
        current_weight = float(adjusted.get(name, 0.0) or 0.0)
        if current_weight > cap_weight:
            excess += current_weight - cap_weight
            adjusted.loc[name] = cap_weight

    if excess <= 1e-12:
        return adjusted

    recipients = {name: float(weight) for name, weight in reallocate_mix.items() if name in members and float(weight) > 0.0}
    if not recipients:
        return adjusted
    recipient_weights = pd.Series(recipients, dtype=float)
    recipient_weights = recipient_weights / float(recipient_weights.sum())
    for name, frac in recipient_weights.items():
        adjusted.loc[name] = float(adjusted.get(name, 0.0) or 0.0) + excess * float(frac)
    return adjusted


def _apply_phase_ss_explicit_bucket_architecture(
    weights: pd.Series,
    *,
    tilt_mode: str,
    market_state: str | None,
    strong_neutral_flag: bool,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()

    # Target cash is reported diagnostically in Phase SS, but the production
    # pipeline still creates explicit BIL later through the incumbent overlay
    # stage. The in-allocator bucket architecture therefore sets the risky
    # sleeve budgets across offense / defense / composite here.
    if tilt_mode == "phase_ss_recovery_explicit_bucket":
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.54, "defense": 0.22, "composite": 0.24},
                offense_target_mix={
                    "cta_trend_long_only": 0.60,
                    "dual_momentum_topn": 0.25,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.55,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.54, "defense": 0.21, "composite": 0.25},
                offense_target_mix={
                    "cta_trend_long_only": 0.48,
                    "dual_momentum_topn": 0.37,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.50,
            )
        return adjusted

    if tilt_mode == "phase_ss_good_state_explicit_bucket":
        if market_state == "calm_trend":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.57, "defense": 0.19, "composite": 0.24},
                offense_target_mix={
                    "composite_selective_signals": 0.50,
                    "dual_momentum_topn": 0.30,
                    "cta_trend_long_only": 0.20,
                },
                offense_mix_strength=0.45,
            )
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.56, "defense": 0.19, "composite": 0.25},
                offense_target_mix={
                    "dual_momentum_topn": 0.40,
                    "cta_trend_long_only": 0.35,
                    "composite_selective_signals": 0.25,
                },
                offense_mix_strength=0.42,
            )
        return adjusted

    if tilt_mode == "phase_ss_combined_explicit_bucket":
        if market_state == "calm_trend":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.56, "defense": 0.19, "composite": 0.25},
                offense_target_mix={
                    "composite_selective_signals": 0.48,
                    "dual_momentum_topn": 0.31,
                    "cta_trend_long_only": 0.21,
                },
                offense_mix_strength=0.40,
            )
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.55, "defense": 0.19, "composite": 0.26},
                offense_target_mix={
                    "dual_momentum_topn": 0.40,
                    "cta_trend_long_only": 0.35,
                    "composite_selective_signals": 0.25,
                },
                offense_mix_strength=0.38,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.53, "defense": 0.22, "composite": 0.25},
                offense_target_mix={
                    "cta_trend_long_only": 0.58,
                    "dual_momentum_topn": 0.27,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.52,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.52, "defense": 0.22, "composite": 0.26},
                offense_target_mix={
                    "cta_trend_long_only": 0.47,
                    "dual_momentum_topn": 0.38,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.48,
            )
        return adjusted

    return adjusted


def _apply_phase_yy_decomposition_architecture(
    weights: pd.Series,
    *,
    tilt_mode: str,
    market_state: str | None,
    strong_neutral_flag: bool,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()

    if tilt_mode == "phase_yy_conservative_decomposition":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.22,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.32,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.62, "defense": 0.38},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.28,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.54, "defense": 0.46},
                offense_target_mix={
                    "dual_momentum_topn": 0.20,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.50,
                },
                offense_mix_strength=0.30,
            )
        return adjusted

    # =====================================================================
    # Phase ZZ — Decomposed-component rebudget. Same architecture as
    # phase_yy_conservative_decomposition but rebudgets the offense/defense
    # bucket targets in recovery states (and optionally strong_neutral) to
    # repair YY's recovery-state underperformance. Stressed_panic and
    # calm_trend behaviour unchanged.
    # =====================================================================
    # ZZ1 — recovery offense rebudget (only recovery_confirmed and recovery_fragile)
    if tilt_mode == "phase_zz_recovery_offense_rebudget":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.22,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.32,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.26,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.46,
                },
                offense_mix_strength=0.50,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # ZZ2 — recovery_offense + neutral_healthy rebudget
    if tilt_mode == "phase_zz_recovery_neutral_offense_rebudget":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.26,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.46,
                },
                offense_mix_strength=0.50,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # ZZ3 — confirmed freer / fragile conservative
    if tilt_mode == "phase_zz_confirmed_freer_fragile_conservative":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.22,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.32,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.72, "defense": 0.28},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.28,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.55,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.58, "defense": 0.42},
                offense_target_mix={
                    "dual_momentum_topn": 0.20,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.50,
                },
                offense_mix_strength=0.36,
            )
        return adjusted

    # =====================================================================
    # Phase AAA — Recovery_confirmed-only deeper rebudget on top of ZZ2.
    # Strong_neutral and recovery_fragile remain identical to ZZ2.
    # Stressed_panic protected upstream.
    # =====================================================================
    # AAA1 — confirmed offense escalation (push offense bucket higher in confirmed only)
    if tilt_mode == "phase_aaa_confirmed_offense_escalation":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.78, "defense": 0.22},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.26,
                    "composite_selective_signals": 0.06,
                    "composite_regime_offense_component": 0.50,
                },
                offense_mix_strength=0.60,
            )
        if market_state == "recovery_fragile":  # unchanged from ZZ2
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # AAA2 — confirmed offense-mix tilt (keep ZZ2 bucket totals; bias internal mix toward higher-conviction sleeves)
    if tilt_mode == "phase_aaa_confirmed_offense_mix_tilt":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.16, "cta_trend_long_only": 0.34,
                    "composite_selective_signals": 0.06,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.65,
            )
        if market_state == "recovery_fragile":  # unchanged from ZZ2
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # AAA3 — confirmed defense composition repair (keep ZZ2 totals; bias defense bucket toward taa_10m_sma)
    if tilt_mode == "phase_aaa_confirmed_defense_composition_repair":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.26,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.46,
                },
                offense_mix_strength=0.50,
                defense_target_mix={
                    "taa_10m_sma": 0.70,
                    "composite_regime_defense_component": 0.30,
                },
                defense_mix_strength=0.55,
            )
        if market_state == "recovery_fragile":  # unchanged from ZZ2
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # AAA4 — confirmed-only combined repair (small offense escalation + offense-mix tilt + defense composition repair)
    if tilt_mode == "phase_aaa_confirmed_only_combined_repair":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.72, "defense": 0.28},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.30,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.55,
                defense_target_mix={
                    "taa_10m_sma": 0.65,
                    "composite_regime_defense_component": 0.35,
                },
                defense_mix_strength=0.45,
            )
        if market_state == "recovery_fragile":  # unchanged from ZZ2
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # =====================================================================
    # Phase BBB — Recovery_confirmed bounded offense-composition extension
    # on top of AAA2. Strong_neutral and recovery_fragile remain identical
    # to ZZ2 / AAA2; only recovery_confirmed composition is adjusted.
    # =====================================================================
    # BBB1 — stronger AAA2 offense mix (same confirmed bucket totals, higher
    # offense_mix_strength)
    if tilt_mode == "phase_bbb_stronger_confirmed_offense_mix":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.16, "cta_trend_long_only": 0.34,
                    "composite_selective_signals": 0.06,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.75,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # BBB2 — composite offense component tilt (same confirmed bucket totals,
    # more emphasis on the high-Sharpe offense component)
    if tilt_mode == "phase_bbb_composite_offense_component_tilt":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.12, "cta_trend_long_only": 0.30,
                    "composite_selective_signals": 0.04,
                    "composite_regime_offense_component": 0.54,
                },
                offense_mix_strength=0.70,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # BBB3 — offense + defense composition combo. Repo diagnostics show the
    # decomposed defense component is the stronger recovery_confirmed defense
    # leg, so the defense repair tilts toward it rather than toward TAA.
    if tilt_mode == "phase_bbb_offense_defense_composition_combo":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.12, "cta_trend_long_only": 0.30,
                    "composite_selective_signals": 0.04,
                    "composite_regime_offense_component": 0.54,
                },
                offense_mix_strength=0.75,
                defense_target_mix={
                    "taa_10m_sma": 0.30,
                    "composite_regime_defense_component": 0.70,
                },
                defense_mix_strength=0.65,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # BBB4 — conservative confirmed composition repair (minimum bounded
    # increase vs AAA2, intended to preserve AAA2's strong full-window profile)
    if tilt_mode == "phase_bbb_conservative_confirmed_composition":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.14, "cta_trend_long_only": 0.32,
                    "composite_selective_signals": 0.05,
                    "composite_regime_offense_component": 0.49,
                },
                offense_mix_strength=0.70,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
        return adjusted

    # =====================================================================
    # Phase CCC — bounded recovery_confirmed offense pruning on top of BBB3.
    # The objective is to hard-cap the confirmed-state weak offense sleeves
    # (composite_selective_signals / dual_momentum_topn) while keeping the
    # BBB3 bucket totals, recovery_fragile behavior, and stressed guardrails.
    # =====================================================================
    if tilt_mode in {
        "phase_ccc_confirmed_cap_css",
        "phase_ccc_confirmed_cap_dual",
        "phase_ccc_confirmed_cap_dual_css",
        "phase_ccc_conservative_confirmed_pruning",
        "phase_ddd_confirmed_harder_dual_cap",
        "phase_ddd_confirmed_near_exclude_dual",
        "phase_ddd_confirmed_dual_hard_css_soft",
        "phase_ddd_confirmed_defensive_balanced_substitution",
        "phase_ddd_minimal_dual_polish",
        "phase_ddd_confirmed_comp_off_receiver",
        "phase_jjj3_calm_css_cap",
        "phase_jjj4_state_risk_contribution_caps",
        "phase_jjj4_adaptive_mom_vol_corr_budget",
        "phase_jjj4_conservative_adaptive_risk_budget",
        "phase_mmm_recovery_confirmed_css_cap",
        "phase_mmm_conservative_css_polish",
        "phase_ooo6_efa_spy_selective_tilt",
        "phase_ooo6_efa_spy_vol_filtered_tilt",
        "phase_ooo6_efa_spy_trend_confirmed_tilt",
    }:
        ooo6_modes = {
            "phase_ooo6_efa_spy_selective_tilt",
            "phase_ooo6_efa_spy_vol_filtered_tilt",
            "phase_ooo6_efa_spy_trend_confirmed_tilt",
        }

        def _ooo6_event_fires(mode: str) -> bool:
            date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
            if date_key is None:
                return False
            date_key = pd.to_datetime(date_key).tz_localize(None)
            if mode == "phase_ooo6_efa_spy_selective_tilt":
                return bool(OOO3_EVENT_LOOKUPS.get("efa_spy_raw_top10_event", {}).get(date_key, 0))
            if mode == "phase_ooo6_efa_spy_vol_filtered_tilt":
                return bool(OOO3_EVENT_LOOKUPS.get("efa_spy_vol_filtered_top20_event", {}).get(date_key, 0))
            if mode == "phase_ooo6_efa_spy_trend_confirmed_tilt":
                efa_gate = bool(OOO3_EVENT_LOOKUPS.get("efa_spy_market_trend_confirmed_top20_event", {}).get(date_key, 0))
                trend_gate = bool(OOO3_EVENT_LOOKUPS.get("market_trend_breadth_confirmed_event", {}).get(date_key, 0))
                return efa_gate and trend_gate
            return False

        def _apply_ooo6_event_tilt(base: pd.Series, mode: str) -> pd.Series:
            if mode not in ooo6_modes:
                return base
            if market_state not in {"calm_trend", "neutral_mixed"} and not strong_neutral_flag:
                return base
            if not _ooo6_event_fires(mode):
                return base
            if mode == "phase_ooo6_efa_spy_selective_tilt":
                multipliers = {
                    "composite_regime_offense_component": 1.06,
                    "cta_trend_long_only": 1.02,
                    "composite_regime_defense_component": 0.96,
                    "taa_10m_sma": 0.98,
                }
            elif mode == "phase_ooo6_efa_spy_vol_filtered_tilt":
                multipliers = {
                    "composite_regime_offense_component": 1.04,
                    "cta_trend_long_only": 1.01,
                    "composite_regime_defense_component": 0.98,
                    "taa_10m_sma": 0.99,
                }
            else:
                multipliers = {
                    "composite_regime_offense_component": 1.05,
                    "cta_trend_long_only": 1.015,
                    "composite_regime_defense_component": 0.97,
                    "taa_10m_sma": 0.985,
                }
            out = pd.Series(base, dtype=float).copy()
            for sleeve, multiplier in multipliers.items():
                if sleeve in out.index:
                    out.loc[sleeve] *= multiplier
            return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

        def _jjj4_adaptive_budget(base: pd.Series, strength: float = 0.05) -> pd.Series:
            if conviction is None and state_lead_tilt is None:
                return base
            score = pd.Series(0.0, index=base.index, dtype=float)
            if conviction is not None and not conviction.empty:
                score = score.add(pd.Series(conviction, dtype=float).reindex(base.index).fillna(0.0) * 0.60, fill_value=0.0)
            if state_lead_tilt is not None and not state_lead_tilt.empty:
                score = score.add(pd.Series(state_lead_tilt, dtype=float).reindex(base.index).fillna(0.0) * 0.40, fill_value=0.0)
            score = score.clip(-1.0, 1.0)
            out = pd.Series(base, dtype=float).copy()
            for name in out.index:
                out.loc[name] *= float(np.clip(1.0 + strength * float(score.get(name, 0.0)), 0.94, 1.06))
            return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

        if strong_neutral_flag:
            strong_neutral_base = _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.65, "defense": 0.35},
                offense_target_mix={
                    "dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.40,
            )
            return _apply_ooo6_event_tilt(strong_neutral_base, tilt_mode)
        if market_state == "recovery_confirmed":
            confirmed = _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.68, "defense": 0.32},
                offense_target_mix={
                    "dual_momentum_topn": 0.12, "cta_trend_long_only": 0.30,
                    "composite_selective_signals": 0.04,
                    "composite_regime_offense_component": 0.54,
                },
                offense_mix_strength=0.75,
                defense_target_mix={
                    "taa_10m_sma": 0.30,
                    "composite_regime_defense_component": 0.70,
                },
                defense_mix_strength=0.65,
            )
            offense_members = [
                name
                for name in [
                    "dual_momentum_topn",
                    "cta_trend_long_only",
                    "composite_selective_signals",
                    "composite_regime_offense_component",
                ]
                if name in confirmed.index
            ]
            if tilt_mode == "phase_ccc_confirmed_cap_css":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"composite_selective_signals": 0.16},
                    reallocate_mix={
                        "composite_regime_offense_component": 0.72,
                        "cta_trend_long_only": 0.28,
                    },
                )
            if tilt_mode == "phase_ccc_confirmed_cap_dual":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"dual_momentum_topn": 0.12},
                    reallocate_mix={
                        "composite_regime_offense_component": 0.65,
                        "cta_trend_long_only": 0.35,
                    },
                )
            if tilt_mode == "phase_ccc_confirmed_cap_dual_css":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={
                        "dual_momentum_topn": 0.10,
                        "composite_selective_signals": 0.14,
                    },
                    reallocate_mix={
                        "composite_regime_offense_component": 0.78,
                        "cta_trend_long_only": 0.22,
                    },
                )
            # ============================================================
            # Phase DDD — harder confirmed-only weak-sleeve exclusion.
            # Start from CCC2 (dual cap 0.12) and push the dual cap lower,
            # optionally with a CSS soft-cap and/or a defense receiver.
            # ============================================================
            if tilt_mode == "phase_ddd_confirmed_harder_dual_cap":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"dual_momentum_topn": 0.07},
                    reallocate_mix={
                        "composite_regime_offense_component": 0.70,
                        "cta_trend_long_only": 0.30,
                    },
                )
            if tilt_mode in {
                "phase_ddd_confirmed_near_exclude_dual",
                "phase_jjj3_calm_css_cap",
                "phase_jjj4_state_risk_contribution_caps",
                "phase_jjj4_adaptive_mom_vol_corr_budget",
                "phase_jjj4_conservative_adaptive_risk_budget",
                "phase_mmm_recovery_confirmed_css_cap",
                "phase_mmm_conservative_css_polish",
                "phase_ooo6_efa_spy_selective_tilt",
                "phase_ooo6_efa_spy_vol_filtered_tilt",
                "phase_ooo6_efa_spy_trend_confirmed_tilt",
            }:
                confirmed_base = _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"dual_momentum_topn": 0.03},
                    reallocate_mix={
                        "composite_regime_offense_component": 0.70,
                        "cta_trend_long_only": 0.30,
                    },
                )
                if tilt_mode == "phase_jjj4_state_risk_contribution_caps":
                    return _apply_bucket_share_caps(
                        confirmed_base,
                        bucket_names=offense_members,
                        share_caps={"composite_regime_offense_component": 0.50},
                        reallocate_mix={"cta_trend_long_only": 1.00},
                    )
                if tilt_mode == "phase_jjj4_adaptive_mom_vol_corr_budget":
                    return _jjj4_adaptive_budget(confirmed_base, strength=0.04)
                if tilt_mode == "phase_mmm_recovery_confirmed_css_cap":
                    return _apply_bucket_share_caps(
                        confirmed_base,
                        bucket_names=offense_members,
                        share_caps={"composite_selective_signals": 0.08},
                        reallocate_mix={
                            "composite_regime_offense_component": 0.70,
                            "cta_trend_long_only": 0.30,
                        },
                    )
                if tilt_mode == "phase_mmm_conservative_css_polish":
                    return _apply_bucket_share_caps(
                        confirmed_base,
                        bucket_names=offense_members,
                        share_caps={"composite_selective_signals": 0.12},
                        reallocate_mix={
                            "composite_regime_offense_component": 0.70,
                            "cta_trend_long_only": 0.30,
                        },
                    )
                return confirmed_base
            if tilt_mode == "phase_ddd_confirmed_dual_hard_css_soft":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={
                        "dual_momentum_topn": 0.06,
                        "composite_selective_signals": 0.10,
                    },
                    reallocate_mix={
                        "composite_regime_offense_component": 0.75,
                        "cta_trend_long_only": 0.25,
                    },
                )
            if tilt_mode == "phase_ddd_confirmed_defensive_balanced_substitution":
                # Cap dual hard, css mild; route some freed weight into the
                # defense_component receiver too.
                offense_members_with_def = [
                    name for name in offense_members + ["composite_regime_defense_component"]
                    if name in confirmed.index
                ]
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members_with_def,
                    share_caps={
                        "dual_momentum_topn": 0.06,
                        "composite_selective_signals": 0.12,
                    },
                    reallocate_mix={
                        "composite_regime_offense_component": 0.55,
                        "cta_trend_long_only": 0.25,
                        "composite_regime_defense_component": 0.20,
                    },
                )
            # ---- rescue variants (only used if main DDD candidates fail narrowly) ----
            if tilt_mode == "phase_ddd_minimal_dual_polish":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"dual_momentum_topn": 0.10},
                    reallocate_mix={
                        "composite_regime_offense_component": 1.00,
                    },
                )
            if tilt_mode == "phase_ddd_confirmed_comp_off_receiver":
                return _apply_bucket_share_caps(
                    confirmed,
                    bucket_names=offense_members,
                    share_caps={"dual_momentum_topn": 0.07},
                    reallocate_mix={
                        "composite_regime_offense_component": 1.00,
                    },
                )
            return _apply_bucket_share_caps(
                confirmed,
                bucket_names=offense_members,
                share_caps={
                    "dual_momentum_topn": 0.13,
                    "composite_selective_signals": 0.18,
                },
                reallocate_mix={
                    "composite_regime_offense_component": 0.60,
                    "cta_trend_long_only": 0.30,
                    "dual_momentum_topn": 0.10,
                },
            )
        if market_state == "recovery_fragile":
            fragile_base = _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.52,
                },
                offense_mix_strength=0.40,
            )
            if tilt_mode == "phase_jjj4_adaptive_mom_vol_corr_budget":
                return _jjj4_adaptive_budget(fragile_base, strength=0.03)
            if tilt_mode == "phase_jjj4_conservative_adaptive_risk_budget":
                return _apply_bucket_share_caps(
                    fragile_base,
                    bucket_names=["taa_10m_sma", "composite_regime_defense_component"],
                    share_caps={"composite_regime_defense_component": 0.58},
                    reallocate_mix={"taa_10m_sma": 1.00},
                )
            return fragile_base
        if tilt_mode == "phase_jjj4_adaptive_mom_vol_corr_budget" and (
            market_state in {"calm_trend", "neutral_mixed"} or strong_neutral_flag
        ):
            return _jjj4_adaptive_budget(adjusted, strength=0.05)
        if tilt_mode in ooo6_modes:
            return _apply_ooo6_event_tilt(adjusted, tilt_mode)
        if tilt_mode == "phase_jjj3_calm_css_cap" and market_state == "calm_trend":
            offense_members = [
                name
                for name in [
                    "dual_momentum_topn",
                    "cta_trend_long_only",
                    "composite_selective_signals",
                    "composite_regime_offense_component",
                ]
                if name in adjusted.index
            ]
            return _apply_bucket_share_caps(
                adjusted,
                bucket_names=offense_members,
                share_caps={"composite_selective_signals": 0.30},
                reallocate_mix={
                    "composite_regime_offense_component": 0.70,
                    "cta_trend_long_only": 0.30,
                },
            )
        return adjusted

    # ZZ4 — conservative decomposition repair (minimum shift)
    if tilt_mode == "phase_zz_conservative_decomposition_repair":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.60, "defense": 0.40},
                offense_target_mix={
                    "dual_momentum_topn": 0.22,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.14,
                    "composite_regime_offense_component": 0.42,
                },
                offense_mix_strength=0.32,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.66, "defense": 0.34},
                offense_target_mix={
                    "dual_momentum_topn": 0.18,
                    "cta_trend_long_only": 0.28,
                    "composite_selective_signals": 0.10,
                    "composite_regime_offense_component": 0.44,
                },
                offense_mix_strength=0.45,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.57, "defense": 0.43},
                offense_target_mix={
                    "dual_momentum_topn": 0.20,
                    "cta_trend_long_only": 0.22,
                    "composite_selective_signals": 0.08,
                    "composite_regime_offense_component": 0.50,
                },
                offense_mix_strength=0.34,
            )
        return adjusted

    return adjusted


def _apply_phase_tt_two_stage_bucket_architecture(
    weights: pd.Series,
    *,
    tilt_mode: str,
    market_state: str | None,
    strong_neutral_flag: bool,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()

    if tilt_mode == "phase_tt_recovery_two_stage_bucket":
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.58, "defense": 0.20, "composite": 0.22},
                offense_target_mix={
                    "cta_trend_long_only": 0.64,
                    "dual_momentum_topn": 0.24,
                    "composite_selective_signals": 0.12,
                },
                offense_mix_strength=0.62,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.50, "defense": 0.28, "composite": 0.22},
                offense_target_mix={
                    "cta_trend_long_only": 0.44,
                    "dual_momentum_topn": 0.41,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.58,
            )
        return adjusted

    if tilt_mode == "phase_tt_recovery_neutral_two_stage_bucket":
        if strong_neutral_flag:
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.54, "defense": 0.21, "composite": 0.25},
                offense_target_mix={
                    "dual_momentum_topn": 0.41,
                    "cta_trend_long_only": 0.36,
                    "composite_selective_signals": 0.23,
                },
                offense_mix_strength=0.50,
            )
        if market_state == "recovery_confirmed":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.57, "defense": 0.21, "composite": 0.22},
                offense_target_mix={
                    "cta_trend_long_only": 0.62,
                    "dual_momentum_topn": 0.25,
                    "composite_selective_signals": 0.13,
                },
                offense_mix_strength=0.60,
            )
        if market_state == "recovery_fragile":
            return _apply_explicit_bucket_budget(
                adjusted,
                target_bucket_weights={"offense": 0.49, "defense": 0.29, "composite": 0.22},
                offense_target_mix={
                    "cta_trend_long_only": 0.43,
                    "dual_momentum_topn": 0.42,
                    "composite_selective_signals": 0.15,
                },
                offense_mix_strength=0.56,
            )
        return adjusted

    return adjusted


def save_allocator_checkpoint_tables(
    checkpoint_name: str | None,
    checkpoint_tables: dict[str, pd.DataFrame],
) -> None:
    if not SAVE_ALLOCATOR_CHECKPOINTS or not checkpoint_name:
        return
    ALLOCATOR_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = str(checkpoint_name).strip()
    for stage_name, table in checkpoint_tables.items():
        if table is None or table.empty:
            continue
        out_path = ALLOCATOR_CHECKPOINT_DIR / f"{safe_name}__{stage_name}.csv"
        table.to_csv(out_path)


# ----------------------------------------------------------------------
# Phase FF — defensive_overlay_hint lookup from Phase CC's refined state
# file. Loaded once at module load. Used ONLY by tilt modes
# 'dynamic_risk_budget_phaseff_*'; production tilt mode 'dynamic_risk_budget'
# does not consult these lookups, so adding this is strictly additive.
# Empty if the refined state file is absent.
# ----------------------------------------------------------------------
PHASEFF_HINT_LOOKUP: dict = {}
PHASEFF_REFINED_STATE_LOOKUP: dict = {}
try:
    _phaseff_refined_path = LAYER2B_DIR / "market_state_history_refined.csv"
    if _phaseff_refined_path.exists():
        _phaseff_df = pd.read_csv(_phaseff_refined_path, parse_dates=["Date"])
        _phaseff_df["Date"] = pd.to_datetime(_phaseff_df["Date"]).dt.tz_localize(None)
        _phaseff_df = _phaseff_df.set_index("Date")
        if "defensive_overlay_hint" in _phaseff_df.columns:
            PHASEFF_HINT_LOOKUP = _phaseff_df["defensive_overlay_hint"].fillna(0).astype(int).to_dict()
        if "refined_state" in _phaseff_df.columns:
            PHASEFF_REFINED_STATE_LOOKUP = _phaseff_df["refined_state"].astype(str).fillna("").to_dict()
except Exception:
    pass

# ----------------------------------------------------------------------
# Phase JJ — ML blended p_regime_confidence lookup (loaded from
# phase_jj_blended_predictions.csv if present). Used ONLY by phase2b_modes
# 'regime_confidence_boost_jj_riskdial_25' and '..._jj_riskdial_50'.
# Empty if the file is absent.
# ----------------------------------------------------------------------
PHASEJJ_BLENDED_25_LOOKUP: dict = {}
PHASEJJ_BLENDED_50_LOOKUP: dict = {}
try:
    _phasejj_path = LAYER2B_DIR / "phase_jj_blended_predictions.csv"
    if _phasejj_path.exists():
        _phasejj_df = pd.read_csv(_phasejj_path, parse_dates=["Date"])
        _phasejj_df["Date"] = pd.to_datetime(_phasejj_df["Date"]).dt.tz_localize(None)
        _phasejj_df = _phasejj_df.set_index("Date")
        if "p_regime_confidence_blended_25" in _phasejj_df.columns:
            PHASEJJ_BLENDED_25_LOOKUP = _phasejj_df["p_regime_confidence_blended_25"].astype(float).to_dict()
        if "p_regime_confidence_blended_50" in _phasejj_df.columns:
            PHASEJJ_BLENDED_50_LOOKUP = _phasejj_df["p_regime_confidence_blended_50"].astype(float).to_dict()
except Exception:
    pass

# ----------------------------------------------------------------------
# Phase KK — Refreshed Target-A regime confidence lookups. Loaded from
# phase_kk_targeta_regime_confidence_predictions.csv if present.
#   * KK1 'replacement': replaces p_regime_confidence with refreshed score
#   * KK2 'blend25':     0.75 * existing + 0.25 * refreshed
# ----------------------------------------------------------------------
PHASEKK_REPLACEMENT_LOOKUP: dict = {}
PHASEKK_BLEND25_LOOKUP: dict = {}
try:
    _phasekk_path = LAYER2B_DIR / "phase_kk_targeta_regime_confidence_predictions.csv"
    if _phasekk_path.exists():
        _phasekk_df = pd.read_csv(_phasekk_path, parse_dates=["Date"])
        _phasekk_df["Date"] = pd.to_datetime(_phasekk_df["Date"]).dt.tz_localize(None)
        _phasekk_df = _phasekk_df.set_index("Date")
        if "p_regime_confidence_refreshed" in _phasekk_df.columns:
            PHASEKK_REPLACEMENT_LOOKUP = _phasekk_df["p_regime_confidence_refreshed"].astype(float).to_dict()
        if "p_regime_confidence_blend25" in _phasekk_df.columns:
            PHASEKK_BLEND25_LOOKUP = _phasekk_df["p_regime_confidence_blend25"].astype(float).to_dict()
except Exception:
    pass

# ----------------------------------------------------------------------
# Phase NNN — hard-ML meta-layer predictions on top of GGG1.
# Loaded from phase_nnn_ml_meta_predictions.csv if present.
#   * risk_dial: bounded risk reduction when underperformance/stress risk is high
#   * opportunity_dial: bounded participation lift when underperformance/stress
#     risk is low. These modes only nudge regime_multiplier; they do not
#     replace GGG1 sleeve/component logic.
# ----------------------------------------------------------------------
PHASENNN_UNDERPERF_LOOKUP: dict = {}
PHASENNN_STRESS_LOOKUP: dict = {}
try:
    _phasennn_path = LAYER2B_DIR / "phase_nnn_ml_meta_predictions.csv"
    if _phasennn_path.exists():
        _phasennn_df = pd.read_csv(_phasennn_path, parse_dates=["Date"])
        _phasennn_df["Date"] = pd.to_datetime(_phasennn_df["Date"]).dt.tz_localize(None)
        _phasennn_df = _phasennn_df.set_index("Date")
        if "p_nnn_ggg1_underperformance_4w" in _phasennn_df.columns:
            PHASENNN_UNDERPERF_LOOKUP = _phasennn_df["p_nnn_ggg1_underperformance_4w"].astype(float).to_dict()
        if "p_nnn_stress_transition_4w" in _phasennn_df.columns:
            PHASENNN_STRESS_LOOKUP = _phasennn_df["p_nnn_stress_transition_4w"].astype(float).to_dict()
except Exception:
    pass

# ----------------------------------------------------------------------
# Phase OOO6 — OOO3-sized signal events for portfolio pass-through tests.
# These are lagged/causal event indicators written by the OOO3 diagnostic.
# They are used only by OOO6 state_tilt modes and do not alter GGG1 unless
# those explicit candidate versions are requested.
# ----------------------------------------------------------------------
OOO3_EVENT_LOOKUPS: dict[str, dict] = {}
try:
    _ooo3_event_panel_path = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo3_vol_managed_signal_sizing" / "ooo3_sized_signal_event_panel.csv"
    if _ooo3_event_panel_path.exists():
        _ooo3_events = pd.read_csv(_ooo3_event_panel_path, parse_dates=["date"])
        _ooo3_events["date"] = pd.to_datetime(_ooo3_events["date"]).dt.tz_localize(None)
        _ooo3_events = _ooo3_events.set_index("date").sort_index()
        for _col in _ooo3_events.columns:
            OOO3_EVENT_LOOKUPS[_col] = _ooo3_events[_col].fillna(0).astype(int).to_dict()
except Exception:
    OOO3_EVENT_LOOKUPS = {}


# ----------------------------------------------------------------------
# Phase SSS3 — SSS2-validated regime-sequence signal pass-through tests.
# These are explicit lagged/causal binary signals written by the SSS2
# diagnostic. They are used only by SSS3 state_tilt modes and do not alter
# GGG1 unless those explicit candidate versions are requested.
# ----------------------------------------------------------------------
SSS2_SIGNAL_LOOKUPS: dict[str, dict] = {}
try:
    _sss2_signal_panel_path = ROOT / "data" / "research" / "phase_sss2_sequence_signal_validation" / "sss2_sequence_signal_panel.csv"
    if _sss2_signal_panel_path.exists():
        _sss2_signals = pd.read_csv(_sss2_signal_panel_path, parse_dates=["date"])
        _sss2_signals["date"] = pd.to_datetime(_sss2_signals["date"]).dt.tz_localize(None)
        _sss2_signals = _sss2_signals.set_index("date").sort_index()
        for _col in _sss2_signals.columns:
            if _col.endswith("_signal"):
                SSS2_SIGNAL_LOOKUPS[_col] = _sss2_signals[_col].fillna(0).astype(int).to_dict()
except Exception:
    SSS2_SIGNAL_LOOKUPS = {}


# ----------------------------------------------------------------------
# Phase 2B: walk-forward interpretable-ML meta predictions.
#
# Loaded once at module level. Used by apply_phase2b_adjustment() to
# modify regime_multiplier ONLY (orthogonal to overlay_penalty_mode).
# Empty DataFrame if the file hasn't been built yet — all phase2b_mode
# logic then becomes a no-op and behaviour matches Phase 2A control.
# ----------------------------------------------------------------------
PHASE2B_META_PREDICTIONS_PATH = LAYER2B_DIR / "phase2b_meta_predictions.csv"
if PHASE2B_META_PREDICTIONS_PATH.exists():
    phase2b_meta_predictions = pd.read_csv(PHASE2B_META_PREDICTIONS_PATH, parse_dates=["Date"])
    phase2b_meta_predictions["Date"] = pd.to_datetime(phase2b_meta_predictions["Date"]).dt.tz_localize(None)
    phase2b_meta_predictions = phase2b_meta_predictions.set_index("Date").sort_index()
else:
    phase2b_meta_predictions = pd.DataFrame()


def bounded_interp(series: pd.Series, *, xp: list[float], fp: list[float]) -> pd.Series:
    values = pd.Series(series, dtype=float)
    return pd.Series(
        np.interp(values.fillna(values.median(skipna=True) if values.notna().any() else 0.0), xp, fp),
        index=values.index,
        dtype=float,
    )


def evaluate_signal_combo(
    signal_names: list[str],
    *,
    top_n: int | None = None,
    min_signal: float = 0.0,
    weight_mode: str = "equal_top_n",
    strength_power: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    signal_panels = {name: ns3["baseline_signal_panels"][name] for name in signal_names if name in ns3["baseline_signal_panels"]}
    composite_signal = ns3["combine_signal_panels"](
        signal_panels,
        weight_history=None,
        smoothing_weeks=ns3["COMPOSITE_SMOOTHING_WEEKS"],
    )
    chosen_top_n = top_n if top_n is not None else min(5, max(3, len(ns3["broad_risk_assets"]) // 3)) if ns3["broad_risk_assets"] else 1
    signal_panel = composite_signal.reindex(columns=ns3["broad_risk_assets"])
    if weight_mode == "equal_top_n":
        weights = ns3["build_top_n_long_only_weights"](
            signal_panel,
            top_n=chosen_top_n,
            min_signal=min_signal,
            defensive_asset=ns3["defensive_asset"],
            fill_to_defensive=True,
        )
    elif weight_mode == "strength_weighted":
        weight_rows: list[pd.Series] = []
        for date, row in signal_panel.iterrows():
            score_row = pd.Series(row, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
            weights_row = pd.Series(0.0, index=signal_panel.columns, dtype=float)
            selected = score_row.loc[score_row >= min_signal].nlargest(chosen_top_n)
            if not selected.empty:
                strength = selected.sub(min_signal).clip(lower=0.0)
                if strength_power != 1.0:
                    strength = strength.pow(strength_power)
                if float(strength.sum()) > 1e-12:
                    weights_row.loc[strength.index] = strength / strength.sum()
                else:
                    weights_row.loc[selected.index] = 1.0 / len(selected)
            if ns3["defensive_asset"] in weights_row.index:
                remaining = max(0.0, 1.0 - float(weights_row.sum()))
                weights_row.loc[ns3["defensive_asset"]] = remaining
            weight_rows.append(weights_row.rename(date))
        weights = pd.DataFrame(weight_rows).reindex(columns=signal_panel.columns).fillna(0.0)
    else:
        raise ValueError(f"Unknown signal weight mode: {weight_mode}")
    weights, _ = ns3["apply_rebalance_schedule"](weights, "monthly")
    path = ns3["compute_strategy_path"](
        weights,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=weights,
        allocation_panel=weights,
        trials=max(len(signal_names), 2),
    )
    metrics["avg_bil_weight"] = weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weights.columns else np.nan
    metrics["avg_spy_weight"] = weights.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weights.columns else np.nan
    subperiod_df = ns5["subperiod_summary"]("combo", path["net_return"])
    metrics["subperiod_sharpe_range"] = (
        subperiod_df["sharpe"].max() - subperiod_df["sharpe"].min() if not subperiod_df.empty else np.nan
    )
    return weights, path, metrics


def register_strategy_output(
    strategy_name: str,
    weights: pd.DataFrame,
    path: pd.DataFrame,
    summary_row: dict,
    manifest_row: dict,
) -> None:
    (LAYER2A_DIR / f"strategy_positions_{strategy_name}.csv").write_text(weights.to_csv())
    (LAYER2A_DIR / f"strategy_returns_{strategy_name}.csv").write_text(path.to_csv())

    strategy_summary = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
    strategy_summary = replace_or_append_row(strategy_summary, "strategy_name", summary_row)
    strategy_summary = strategy_summary.sort_values(["benchmark_group", "validation_score"], ascending=[True, False]).reset_index(drop=True)
    strategy_summary.to_csv(LAYER2A_DIR / "strategy_summary_table.csv", index=False)

    layer2_manifest = json.loads((LAYER2A_DIR / "layer2_manifest.json").read_text())
    layer2_manifest = [row for row in layer2_manifest if row.get("strategy_name") != strategy_name]
    layer2_manifest.append(manifest_row)
    (LAYER2A_DIR / "layer2_manifest.json").write_text(json.dumps(layer2_manifest, indent=2))


def load_layer1_signal_panel(file_name: str, value_col: str) -> pd.DataFrame:
    signal_long = ns3["read_signal_long"](LAYER1_DIR / file_name)
    return ns3["long_signal_to_panel"](
        signal_long,
        value_col,
        index=ns3["weekly_prices"].index,
        columns=ns3["weekly_prices"].columns,
    )


def build_market_state_history() -> pd.DataFrame:
    regime_states = ns5["regime_states"].copy()
    regime_score = ns5["regime_score"].copy()
    weekly_prices = ns5["weekly_prices"].copy()
    proxy_mapping = ns5.get("proxy_mapping", {})
    market_ticker = proxy_mapping.get("market_proxy", {}).get("ticker", "SPY")
    cash_proxy = ns5["cash_proxy"]

    offensive_assets = list(ns3.get("broad_risk_assets", []))
    if not offensive_assets:
        offensive_assets = [ticker for ticker in weekly_prices.columns if ticker not in {cash_proxy, "IEF", "SHY", "TLT", "TIP", "GLD"}]
    offensive_assets = [ticker for ticker in offensive_assets if ticker in weekly_prices.columns]

    market_price = weekly_prices[market_ticker].copy() if market_ticker in weekly_prices.columns else pd.Series(dtype=float)
    market_sma_43 = market_price.rolling(43, min_periods=20).mean()
    market_trend_positive = market_price > market_sma_43
    market_drawdown = market_price.div(market_price.cummax()).sub(1.0)

    offensive_prices = weekly_prices.reindex(columns=offensive_assets)
    breadth_sma_43 = offensive_prices.gt(offensive_prices.rolling(43, min_periods=20).mean()).mean(axis=1)
    breadth_26w_mom = offensive_prices.pct_change(26).gt(0.0).mean(axis=1)
    breadth_13w_mom = offensive_prices.pct_change(13).gt(0.0).mean(axis=1)
    breadth_change_4w = breadth_sma_43.sub(breadth_sma_43.shift(4))

    # Separate canary diagnostics for the conditional research pass. The broader
    # set mirrors the existing notebook convention; the pair proxy is a smaller,
    # public-research-style implementation that approximates BND/VWO using the
    # available ETF universe.
    canary_assets_default = [ticker for ticker in ["VWO", "HYG", "VNQ", "EFA", "PDBC"] if ticker in weekly_prices.columns]
    canary_pair_assets = [ticker for ticker in ["VWO", "IEF"] if ticker in weekly_prices.columns]
    if len(canary_pair_assets) < 2:
        canary_pair_assets = [ticker for ticker in ["VWO", "LQD"] if ticker in weekly_prices.columns]

    def lagged_abs_momentum_breadth(tickers: list[str]) -> pd.Series:
        if not tickers:
            return pd.Series(np.nan, index=weekly_prices.index, dtype=float)
        trailing_52_4w = weekly_prices[tickers].shift(4).div(weekly_prices[tickers].shift(52)).sub(1.0)
        return trailing_52_4w.gt(0.0).mean(axis=1)

    canary_breadth_default = lagged_abs_momentum_breadth(canary_assets_default)
    canary_breadth_pair = lagged_abs_momentum_breadth(canary_pair_assets)

    recent_stress = regime_states["risk_state"].eq("stressed").rolling(26, min_periods=1).max().fillna(0.0).astype(bool)
    avg_corr_risk_off_z = regime_score.get("avg_corr_risk_off_z", pd.Series(np.nan, index=regime_states.index))
    google_fear = regime_score.get("google_fear_z_tradable", pd.Series(np.nan, index=regime_states.index))
    risk_score = regime_score.get("risk_regime_score", pd.Series(np.nan, index=regime_states.index))

    state = pd.Series("neutral_mixed", index=regime_states.index, dtype=object)
    stressed_mask = regime_states["risk_state"].eq("stressed") | ((market_drawdown <= -0.18) & (breadth_sma_43 < 0.35))
    # Recovery universe: any rebound off stress with trend and breadth improving.
    recovery_universe = (
        ~stressed_mask
        & recent_stress
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.45)
        & (breadth_26w_mom >= 0.45)
        & (breadth_change_4w >= 0.05)
    )
    # Confirmed recovery: stricter breadth / momentum / trend / risk score confirmation.
    confirm_breadth = breadth_sma_43 >= 0.58
    confirm_breadth_mom_26 = breadth_26w_mom >= 0.55
    confirm_breadth_mom_13 = breadth_13w_mom >= 0.55
    confirm_trend = market_trend_positive.fillna(False)
    confirm_drawdown = market_drawdown >= -0.06
    confirm_risk = risk_score.reindex(regime_states.index).fillna(0.0) <= 0.35
    recovery_confirmed_mask = (
        recovery_universe
        & confirm_breadth
        & confirm_breadth_mom_26
        & confirm_breadth_mom_13
        & confirm_trend
        & confirm_drawdown
        & confirm_risk
    )
    recovery_fragile_mask = recovery_universe & ~recovery_confirmed_mask
    calm_mask = (
        ~stressed_mask
        & regime_states["risk_state"].eq("calm")
        & market_trend_positive.fillna(False)
        & (breadth_sma_43 >= 0.60)
        & (breadth_26w_mom >= 0.55)
    )
    state.loc[stressed_mask] = "stressed_panic"
    state.loc[recovery_fragile_mask] = "recovery_fragile"
    state.loc[recovery_confirmed_mask] = "recovery_confirmed"
    state.loc[calm_mask] = "calm_trend"

    state_reason = pd.Series("mixed inputs", index=state.index, dtype=object)
    state_reason.loc[stressed_mask] = "stress state, weak breadth, or deep drawdown"
    state_reason.loc[recovery_fragile_mask] = "recent stress with improving breadth but confirmation still partial"
    state_reason.loc[recovery_confirmed_mask] = "recent stress plus confirmed breadth, 13w and 26w momentum, trend, low drawdown, and low risk score"
    state_reason.loc[calm_mask] = "calm regime with strong trend breadth"

    # --- Causal transition-probability features ----------------------------------
    # For each week t (in state S), compute trailing-window estimates of
    #   P(next state == S | current state == S)            -> transition_persistence_prob
    #   P(next state in good regimes | current state == S) -> transition_good_state_prob
    # using only transitions that completed strictly before t (shift(1) after rolling).
    state_series = pd.Series(state.values, index=regime_states.index, dtype=object)
    state_next = state_series.shift(-1)
    pair_df = pd.DataFrame({"curr": state_series, "next": state_next}).dropna(subset=["next"])
    good_states_set = {"calm_trend", "recovery_fragile", "recovery_confirmed"}
    pair_df["stays"] = (pair_df["curr"] == pair_df["next"]).astype(float)
    pair_df["good_next"] = pair_df["next"].isin(good_states_set).astype(float)
    pair_df["non_stress_next"] = (~pair_df["next"].eq("stressed_panic")).astype(float)

    TRANSITION_WINDOW_WEEKS = 156  # ~3 years
    MIN_TRANSITION_PAIRS = 10

    persistence_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    good_state_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    non_stress_prob = pd.Series(np.nan, index=regime_states.index, dtype=float)
    for state_name in pair_df["curr"].dropna().unique():
        subset_mask = pair_df["curr"] == state_name
        if not subset_mask.any():
            continue
        subset = pair_df.loc[subset_mask]
        rolling_stays = (
            subset["stays"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        rolling_good = (
            subset["good_next"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        rolling_non_stress = (
            subset["non_stress_next"].rolling(TRANSITION_WINDOW_WEEKS, min_periods=MIN_TRANSITION_PAIRS).mean().shift(1)
        )
        mask_full = state_series == state_name
        if not mask_full.any():
            continue
        stays_ff = rolling_stays.reindex(state_series.index, method="ffill")
        good_ff = rolling_good.reindex(state_series.index, method="ffill")
        non_stress_ff = rolling_non_stress.reindex(state_series.index, method="ffill")
        persistence_prob.loc[mask_full] = stays_ff.loc[mask_full]
        good_state_prob.loc[mask_full] = good_ff.loc[mask_full]
        non_stress_prob.loc[mask_full] = non_stress_ff.loc[mask_full]

    # --- Stabilized state (one-sided hysteresis on entry into stressed_panic) -----
    # Delay the first week of stressed_panic entry by one week unless the drawdown is
    # already severe (<= -10%) or the risk_regime_score is very high (> 0.85). Exits
    # are NOT delayed; this only dampens one-week false entries into stress.
    risk_score_full = risk_score.reindex(regime_states.index).fillna(0.0)
    dd_full = market_drawdown.reindex(regime_states.index).fillna(0.0)
    severe_mask = (dd_full <= -0.10) | (risk_score_full > 0.85)
    state_shift_prev = state_series.shift(1)
    just_entered_stress = (
        state_series.eq("stressed_panic")
        & state_shift_prev.ne("stressed_panic")
        & ~severe_mask.reindex(state_series.index).fillna(False)
    )
    market_state_stable = state_series.copy()
    market_state_stable.loc[just_entered_stress] = state_shift_prev.loc[just_entered_stress]
    market_state_stable = market_state_stable.fillna(state_series)

    out = pd.DataFrame(
        {
            "Date": regime_states.index,
            "market_state": state.values,
            "market_state_stable": market_state_stable.reindex(regime_states.index).values,
            "market_state_reason": state_reason.values,
            "risk_state": regime_states["risk_state"].values,
            "signal_environment": regime_states.get("signal_environment", pd.Series(index=regime_states.index, dtype=object)).values,
            "risk_regime_score": risk_score.reindex(regime_states.index).values,
            "market_drawdown": market_drawdown.reindex(regime_states.index).values,
            "market_trend_positive": market_trend_positive.reindex(regime_states.index).astype(float).values,
            "breadth_sma_43": breadth_sma_43.reindex(regime_states.index).values,
            "breadth_26w_mom": breadth_26w_mom.reindex(regime_states.index).values,
            "breadth_13w_mom": breadth_13w_mom.reindex(regime_states.index).values,
            "breadth_change_4w": breadth_change_4w.reindex(regime_states.index).values,
            "canary_breadth_default": canary_breadth_default.reindex(regime_states.index).values,
            "canary_breadth_pair": canary_breadth_pair.reindex(regime_states.index).values,
            "recent_stress_26w": recent_stress.reindex(regime_states.index).astype(float).values,
            "avg_corr_risk_off_z": avg_corr_risk_off_z.reindex(regime_states.index).values,
            "google_fear_z_tradable": google_fear.reindex(regime_states.index).values,
            "transition_persistence_prob": persistence_prob.reindex(regime_states.index).values,
            "transition_good_state_prob": good_state_prob.reindex(regime_states.index).values,
            "transition_non_stress_prob": non_stress_prob.reindex(regime_states.index).values,
        }
    ).set_index("Date")
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.to_csv(LAYER2B_DIR / "market_state_history.csv")
    return out


def build_variant_regime_states(
    base_regime_states: pd.DataFrame,
    market_state_history: pd.DataFrame,
    overlay_variant: str,
) -> pd.DataFrame:
    adjusted = base_regime_states.copy()
    extra_columns = [
        "market_state",
        "market_state_reason",
        "breadth_sma_43",
        "breadth_26w_mom",
        "market_trend_positive",
        "canary_breadth_default",
        "canary_breadth_pair",
    ]
    for optional_column in (
        "transition_persistence_prob",
        "transition_good_state_prob",
        "transition_non_stress_prob",
        "market_state_stable",
    ):
        if market_state_history is not None and optional_column in market_state_history.columns:
            extra_columns.append(optional_column)
    adjusted = adjusted.join(market_state_history[extra_columns], how="left")
    if adjusted.empty or "overlay_multiplier" not in adjusted.columns:
        return adjusted
    if overlay_variant == "baseline":
        return adjusted

    # Variants with a raised neutral base (they lift the overall neutral floor modestly).
    neutral_floor_overrides = {
        "good_state_strong_offense": 0.83,
        "good_state_combo_plus": 0.83,
    }
    neutral_floor = neutral_floor_overrides.get(overlay_variant, 0.80)

    neutral_mask = adjusted["risk_state"].eq("neutral")
    stressed_mask = adjusted["risk_state"].eq("stressed")
    adjusted.loc[neutral_mask, "overlay_multiplier"] = adjusted.loc[neutral_mask, "overlay_multiplier"].clip(lower=neutral_floor)
    adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(lower=0.40)

    if overlay_variant == "looser_neutral_stress":
        return adjusted

    # Legacy aggregated-recovery flag (either sub-state counts as recovery for backward compat)
    recovery_any_mask = adjusted["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])
    recovery_confirmed_mask = adjusted["market_state"].eq("recovery_confirmed")
    recovery_fragile_mask = adjusted["market_state"].eq("recovery_fragile")
    calm_mask = adjusted["market_state"].eq("calm_trend")
    strong_neutral_mask = (
        adjusted["market_state"].eq("neutral_mixed")
        & adjusted["market_trend_positive"].fillna(0.0).gt(0.0)
        & adjusted["breadth_sma_43"].fillna(0.0).ge(0.55)
        & adjusted["breadth_26w_mom"].fillna(0.0).ge(0.50)
    )
    recentered_strong_neutral_mask = (
        adjusted["market_state"].eq("neutral_mixed")
        & adjusted["market_trend_positive"].fillna(0.0).gt(0.0)
        & adjusted["breadth_sma_43"].fillna(0.0).ge(0.52)
        & adjusted["breadth_26w_mom"].fillna(0.0).ge(0.48)
    )

    if overlay_variant == "recovery_breadth_rerisk":
        # Original aggregated-recovery overlay: single 0.92 floor.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "neutral_positive_ease":
        # Keep the incumbent recovery logic, but make positive-trend neutral weeks slightly less
        # punitive so we can test whether long-run underdeployment is mostly a neutral-state issue.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "good_state_participation":
        # Control already fixed part of the neutral-state bottleneck. This variant tests whether the
        # remaining weakness is still too much overlay cash in clearly good states.
        adjusted.loc[recovery_any_mask, "overlay_multiplier"] = adjusted.loc[recovery_any_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "recovery_fragile_participation":
        # Early recovery gets a slightly higher floor than confirmed recovery so we can test whether
        # the main missed-upside problem is hesitation during the fragile handoff out of stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.95)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "neutral_positive_ease_fragile_participation":
        # Combination test: keep the benign neutral easing from Variant A while also letting fragile
        # recovery rerisk slightly faster than confirmed recovery.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.95)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "fragile_expression_only":
        # Distinct from the already-refuted confirmed-offense ladder: keep the current neutral easing,
        # leave confirmed recovery on the control floor, and only let fragile recovery rerisk a touch
        # faster if the lag is really in the handoff out of stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    if overlay_variant == "good_state_fragile_expression":
        # Best justified combination after the standalone pass: keep the stronger calm / strong-neutral
        # floors from the good-state offense variant, and add only the modest fragile-recovery lift.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "continuous_neutral_mapping":
        # Map the continuous risk_regime_score directly into the neutral-state deployment
        # multiplier so moderately good / moderately bad neutral weeks are not forced
        # through the same blunt neutral response. Recovery / calm / stress keep the
        # current control floors.
        mapped = bounded_interp(
            adjusted.get("risk_regime_score", pd.Series(np.nan, index=adjusted.index)),
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[1.00, 0.99, 0.95, 0.90, 0.76, 0.48, 0.28],
        )
        neutral_state_mask = adjusted["market_state"].eq("neutral_mixed")
        adjusted.loc[neutral_state_mask, "overlay_multiplier"] = mapped.loc[neutral_state_mask]
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(upper=0.40)
        return adjusted

    if overlay_variant == "continuous_neutral_mapping_careful":
        # Conservative continuous map: weak-neutral stays near the control path,
        # while clearly benign strong-neutral weeks get a smoother release valve.
        risk_values = adjusted.get("risk_regime_score", pd.Series(np.nan, index=adjusted.index))
        neutral_base_map = bounded_interp(
            risk_values,
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[0.91, 0.90, 0.88, 0.85, 0.73, 0.46, 0.28],
        )
        strong_neutral_map = bounded_interp(
            risk_values,
            xp=[-1.25, -0.60, -0.10, 0.25, 0.75, 1.50, 3.00],
            fp=[0.97, 0.96, 0.95, 0.92, 0.82, 0.48, 0.28],
        )
        neutral_state_mask = adjusted["market_state"].eq("neutral_mixed")
        adjusted.loc[neutral_state_mask, "overlay_multiplier"] = neutral_base_map.loc[neutral_state_mask]
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = strong_neutral_map.loc[strong_neutral_mask]
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(upper=0.40)
        return adjusted

    if overlay_variant == "separate_canary_proxy":
        # Minimal separate-canary test. If the canary pair is fully healthy, lift
        # only the clearly benign states slightly; otherwise stay on the control path.
        canary_pair_breadth = adjusted.get("canary_breadth_pair", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
        canary_all_clear_mask = canary_pair_breadth >= 0.999
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        adjusted.loc[strong_neutral_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            strong_neutral_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.96)
        adjusted.loc[recovery_fragile_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            recovery_fragile_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.97)
        adjusted.loc[recovery_confirmed_mask & canary_all_clear_mask, "overlay_multiplier"] = adjusted.loc[
            recovery_confirmed_mask & canary_all_clear_mask, "overlay_multiplier"
        ].clip(lower=0.93)
        return adjusted

    if overlay_variant == "threshold_recentering":
        # Minimal threshold recentering only.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[recentered_strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[
            recentered_strong_neutral_mask, "overlay_multiplier"
        ].clip(lower=0.94)
        return adjusted

    if overlay_variant == "recovery_split_baseline":
        # Variant A: split recovery into two buckets but keep offense intensity roughly symmetric
        # with the aggregated recovery overlay. Confirmed gets a slightly stronger floor than fragile.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.90)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.94)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=0.98)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "recovery_split_confirmed_offense":
        # Variant B: split recovery + meaningfully stronger re-risking in confirmed recovery.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.88)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.85)
        return adjusted

    if overlay_variant == "recovery_split_confirmed_offense_neutral_ease":
        # Variant C: same as B + slightly less punitive neutral-state cash behavior when
        # neutral still has a positive trend (not a global relaxation of neutral stance).
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.88)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        # Raise the strong-neutral floor modestly (0.85 -> 0.90) so "quiet but trending up" weeks
        # carry a bit less sleeve-level cash.
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.90)
        return adjusted

    # ------------------------------------------------------------------
    # Good-state transition-aware / stabilizer / mix-rotation family
    # (current research task, control = improved_hrp_good_state_fragile_combo)
    # ------------------------------------------------------------------
    transition_good_prob = adjusted.get("transition_good_state_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
    transition_persistence = adjusted.get("transition_persistence_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)
    transition_non_stress = adjusted.get("transition_non_stress_prob", pd.Series(np.nan, index=adjusted.index)).fillna(0.0)

    if overlay_variant == "good_state_fragile_transition_aware":
        # Variant A. Keep the control's floors but, when the trailing-window transition
        # matrix says the current regime is both persistent (>= 0.70) AND rarely
        # transitions to stressed_panic (>= 0.92 P(non-stress next)), lift the
        # strong-neutral floor from 0.94 -> 0.97. This targets observed cash drag
        # in strong-neutral weeks where the regime engine itself predicts benign
        # continuation. Using P(non-stress next) rather than P(next in good states)
        # is the decision-useful framing: persistence itself is a benign outcome
        # from neutral_mixed, since neutral_mixed rarely steps directly to stress.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        transition_boost_mask = (
            strong_neutral_mask
            & (transition_non_stress >= 0.92)
            & (transition_persistence >= 0.70)
        )
        adjusted.loc[transition_boost_mask, "overlay_multiplier"] = adjusted.loc[transition_boost_mask, "overlay_multiplier"].clip(lower=0.97)
        return adjusted

    if overlay_variant == "good_state_fragile_stabilizer":
        # Variant B. Identical floors to control, but run with market_state_stable
        # (one-sided hysteresis on entry into stressed_panic). The caller substitutes
        # market_state_stable into market_state upstream, so the masks here already
        # reflect the stabilized state; no extra overlay work needed.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "good_state_strong_offense":
        # Variant C. Raise the strong-neutral floor 0.94 -> 0.98 and the neutral base
        # 0.80 -> 0.83 (applied earlier) so clearly-benign states carry even less
        # residual overlay cash. Keeps fragile at 0.96 and confirmed at 0.92.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.98)
        return adjusted

    if overlay_variant == "good_state_mix_rotation":
        # Variant D. Same overlay floors as control; the change is entirely in the
        # state-conditioned sleeve tilt (fragile_plus_mix_rotation), which rotates
        # weight away from composite_regime_conditioned in calm_trend and toward the
        # trend-following trio (dual_momentum / cta_trend / composite_selective) in
        # calm + fragile.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.94)
        return adjusted

    if overlay_variant == "good_state_combo_plus":
        # Variant E. Best justified combination after standalone pass: keeps the
        # control fragile/confirmed/calm floors, layers in the transition-aware
        # strong-neutral boost (A) and the stronger strong-neutral floor (C), and
        # pairs with the mix-rotation tilt (D) at the tilt layer. Also uses the
        # stabilizer (B) via market_state_stable at the caller.
        adjusted.loc[recovery_fragile_mask, "overlay_multiplier"] = adjusted.loc[recovery_fragile_mask, "overlay_multiplier"].clip(lower=0.96)
        adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"] = adjusted.loc[recovery_confirmed_mask, "overlay_multiplier"].clip(lower=0.92)
        adjusted.loc[calm_mask, "overlay_multiplier"] = adjusted.loc[calm_mask, "overlay_multiplier"].clip(lower=1.00)
        adjusted.loc[strong_neutral_mask, "overlay_multiplier"] = adjusted.loc[strong_neutral_mask, "overlay_multiplier"].clip(lower=0.97)
        transition_boost_mask = (
            strong_neutral_mask
            & (transition_non_stress >= 0.92)
            & (transition_persistence >= 0.70)
        )
        adjusted.loc[transition_boost_mask, "overlay_multiplier"] = adjusted.loc[transition_boost_mask, "overlay_multiplier"].clip(lower=0.98)
        return adjusted

    # Fallback: behave like looser_neutral_stress if an unknown variant string is passed.
    return adjusted


def compute_causal_confidence(market_state_row: pd.Series | None) -> float:
    """Bounded Layer 2B causal-confidence score in [0, 1].

    Composite of:
      - transition_non_stress_prob (regime engine stay-out-of-stress), normalized 0.85 -> 0, 1.00 -> 1
      - breadth_sma_43,                                                  normalized 0.50 -> 0, 0.80 -> 1
      - market_trend_positive > 0                                        (binary)
      - market_drawdown > -0.08                                          (binary: drawdown shallower than -8%)
    Weights: 0.40 / 0.25 / 0.20 / 0.15. Fully deterministic, no hindsight.
    """
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return 0.0

    def _safe_float(key: str, default: float = 0.0) -> float:
        value = market_state_row.get(key, default)
        try:
            if value is None or pd.isna(value):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    persistence = _safe_float("transition_non_stress_prob", 0.0)
    persistence_norm = float(np.clip((persistence - 0.85) / 0.15, 0.0, 1.0))
    breadth = _safe_float("breadth_sma_43", 0.0)
    breadth_norm = float(np.clip((breadth - 0.50) / 0.30, 0.0, 1.0))
    trend_positive = 1.0 if _safe_float("market_trend_positive", 0.0) > 0.0 else 0.0
    drawdown_shallow = 1.0 if _safe_float("market_drawdown", 0.0) > -0.08 else 0.0
    score = 0.40 * persistence_norm + 0.25 * breadth_norm + 0.20 * trend_positive + 0.15 * drawdown_shallow
    return float(np.clip(score, 0.0, 1.0))


def apply_phase2b_adjustment(
    regime_multiplier: float,
    market_state: str | None,
    ml_pred_row: pd.Series | None,
    *,
    mode: str = "none",
    market_state_row: pd.Series | None = None,
) -> tuple[float, dict]:
    """Apply interpretable-ML meta adjustment to regime_multiplier.

    Orthogonal to overlay_penalty_mode — this modifies the raw
    regime_multiplier BEFORE self/non-self-gated relief is computed.
    The ML predictions are walk-forward (no look-ahead) and all
    predictions are gated through hard caps + state filters so the
    ML can only nudge, never dominate.

    Modes:
      - "none": no-op.
      - "regime_confidence_boost" (A): in non-stressed states,
            offset = min(0.045, 0.10 * (p_regime_confidence - 0.55) / 0.45)
            when p_regime_confidence >= 0.55. Boost only.
      - "transition_quality_gate" (B): in strong_neutral or
            recovery_fragile, p_trans > 0.60 -> +0.04,
            p_trans < 0.40 -> -0.03, else no change.
      - "tail_risk_suppression" (C): in all states except stressed_panic,
            p_tail > 0.55 -> offset = -min(0.10, 0.10 * (p_tail - 0.55) / 0.45).
            Suppress only.
      - "combo_ac" (E): A + C.
      - "combo_abc" (F): A + B + C.

    Returns (adjusted_regime_multiplier, diag_dict).
    """
    diag = {
        "phase2b_mode": mode,
        "phase2b_regime_confidence": np.nan,
        "phase2b_transition_quality": np.nan,
        "phase2b_tail_risk": np.nan,
        "phase_nnn_underperformance_risk": np.nan,
        "phase_nnn_stress_transition_risk": np.nan,
        "phase2b_offset": 0.0,
    }
    if mode == "none" or ml_pred_row is None:
        return regime_multiplier, diag
    if not isinstance(ml_pred_row, pd.Series) or ml_pred_row.empty:
        return regime_multiplier, diag

    def _safe_pred(col: str) -> float:
        val = ml_pred_row.get(col)
        try:
            if val is None or pd.isna(val):
                return np.nan
            return float(val)
        except (TypeError, ValueError):
            return np.nan

    p_regime = _safe_pred("p_regime_confidence")
    # Phase JJ: override p_regime with ML-blended value if requested.
    if mode in {"regime_confidence_boost_jj_riskdial_25", "regime_confidence_boost_jj_riskdial_50"}:
        date_key = ml_pred_row.name if hasattr(ml_pred_row, "name") else None
        if date_key is not None:
            lookup = (PHASEJJ_BLENDED_25_LOOKUP
                       if mode == "regime_confidence_boost_jj_riskdial_25"
                       else PHASEJJ_BLENDED_50_LOOKUP)
            blended = lookup.get(date_key)
            if blended is not None and not (isinstance(blended, float) and np.isnan(blended)):
                p_regime = float(blended)
    # Phase KK: override p_regime with refreshed Target-A score (replacement) or
    # 75/25 blend (blend25).
    if mode in {"regime_confidence_boost_kk_replacement", "regime_confidence_boost_kk_blend25"}:
        date_key = ml_pred_row.name if hasattr(ml_pred_row, "name") else None
        if date_key is not None:
            lookup = (PHASEKK_REPLACEMENT_LOOKUP
                       if mode == "regime_confidence_boost_kk_replacement"
                       else PHASEKK_BLEND25_LOOKUP)
            refreshed = lookup.get(date_key)
            if refreshed is not None and not (isinstance(refreshed, float) and np.isnan(refreshed)):
                p_regime = float(refreshed)
    p_nnn_underperf = np.nan
    p_nnn_stress = np.nan
    if mode in {"regime_confidence_boost_nnn_risk_dial", "regime_confidence_boost_nnn_opportunity_dial"}:
        date_key = ml_pred_row.name if hasattr(ml_pred_row, "name") else None
        if date_key is not None:
            underperf_val = PHASENNN_UNDERPERF_LOOKUP.get(date_key)
            stress_val = PHASENNN_STRESS_LOOKUP.get(date_key)
            if underperf_val is not None and not (isinstance(underperf_val, float) and np.isnan(underperf_val)):
                p_nnn_underperf = float(underperf_val)
            if stress_val is not None and not (isinstance(stress_val, float) and np.isnan(stress_val)):
                p_nnn_stress = float(stress_val)
    p_trans = _safe_pred("p_transition_quality")
    p_tail = _safe_pred("p_tail_risk")
    diag["phase2b_regime_confidence"] = p_regime
    diag["phase2b_transition_quality"] = p_trans
    diag["phase2b_tail_risk"] = p_tail
    diag["phase_nnn_underperformance_risk"] = p_nnn_underperf
    diag["phase_nnn_stress_transition_risk"] = p_nnn_stress

    strong_neutral = False
    if isinstance(market_state_row, pd.Series) and not market_state_row.empty:
        try:
            strong_neutral = bool(is_strong_neutral_state_row(market_state_row))
        except Exception:  # pragma: no cover
            strong_neutral = False

    offset = 0.0

    apply_a = mode in {"regime_confidence_boost", "combo_ac", "combo_abc",
                       "regime_confidence_boost_refined_v1",
                       "regime_confidence_boost_refined_v2",
                       "regime_confidence_boost_participation_v1",
                       "regime_confidence_boost_participation_v2",
                       "regime_confidence_boost_jj_riskdial_25",
                       "regime_confidence_boost_jj_riskdial_50",
                       "regime_confidence_boost_kk_replacement",
                       "regime_confidence_boost_kk_blend25",
                       "regime_confidence_boost_nnn_risk_dial",
                       "regime_confidence_boost_nnn_opportunity_dial"}
    apply_b = mode in {"transition_quality_gate", "combo_abc"}
    apply_c = mode in {"tail_risk_suppression", "combo_ac", "combo_abc"}

    # Variant A: regime confidence boost (non-stressed only, boost only).
    if apply_a and market_state != "stressed_panic" and not np.isnan(p_regime):
        if p_regime >= 0.55:
            raw_boost = 0.10 * (p_regime - 0.55) / max(1e-9, 1.0 - 0.55)
            offset += float(min(0.045, max(0.0, raw_boost)))

    # Variant B: transition quality gate (strong_neutral or recovery_fragile only).
    if apply_b and (strong_neutral or market_state == "recovery_fragile") and not np.isnan(p_trans):
        if p_trans > 0.60:
            offset += 0.04
        elif p_trans < 0.40:
            offset -= 0.03

    # Variant C: tail-risk suppression (all except stressed_panic, suppress only).
    if apply_c and market_state != "stressed_panic" and not np.isnan(p_tail):
        if p_tail > 0.55:
            raw_suppress = -0.10 * (p_tail - 0.55) / max(1e-9, 1.0 - 0.55)
            offset += float(max(-0.10, min(0.0, raw_suppress)))

    # Phase NNN: hard-ML meta-layer on top of GGG1. Both modes are bounded
    # regime-multiplier nudges only; stressed_panic is not weakened.
    if mode == "regime_confidence_boost_nnn_risk_dial" and market_state != "stressed_panic":
        if not np.isnan(p_nnn_underperf) and p_nnn_underperf >= 0.58:
            offset -= float(min(0.035, 0.07 * (p_nnn_underperf - 0.58) / max(1e-9, 1.0 - 0.58)))
        if not np.isnan(p_nnn_stress) and p_nnn_stress >= 0.65:
            offset -= float(min(0.040, 0.06 * (p_nnn_stress - 0.65) / max(1e-9, 1.0 - 0.65)))

    if mode == "regime_confidence_boost_nnn_opportunity_dial" and market_state != "stressed_panic":
        favorable = market_state in {"calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile"} or strong_neutral
        if favorable and not np.isnan(p_nnn_underperf) and not np.isnan(p_nnn_stress):
            if p_nnn_underperf <= 0.30 and p_nnn_stress <= 0.20:
                offset += float(min(0.025, 0.04 * (0.30 - p_nnn_underperf) / 0.30))

    # Phase 2 Aggressive: flat regime_multiplier boost in favorable non-stressed states.
    # Larger unconditional offset vs the confidence-gated +0.045 cap used by GGG1.
    # stressed_panic is never touched.
    if mode in {"phase2_aggressive_neutral_boost", "phase2_aggressive_full_mandate"} and market_state != "stressed_panic":
        if market_state == "recovery_fragile":
            offset += 0.02
        elif market_state in {"calm_trend", "neutral_mixed", "recovery_confirmed"} or strong_neutral:
            flat_boost = 0.08 if mode == "phase2_aggressive_neutral_boost" else 0.10
            offset += flat_boost
        if not np.isnan(p_regime) and p_regime >= 0.55:
            raw_boost = 0.10 * (p_regime - 0.55) / max(1e-9, 1.0 - 0.55)
            offset += float(min(0.045, max(0.0, raw_boost)))

    adjusted = float(np.clip(regime_multiplier + offset, 0.0, 1.0))
    diag["phase2b_offset"] = float(adjusted - regime_multiplier)
    return adjusted, diag


def compute_rolling_sleeve_conviction(
    sleeve_return_panel: pd.DataFrame,
    as_of_date: pd.Timestamp,
    sleeves: list[str],
    *,
    lookback_weeks: int = 26,
) -> pd.Series:
    """Rank-based rolling Sharpe conviction in [-1, +1] for each sleeve.

    Uses only returns strictly up to and including `as_of_date` (no hindsight).
    Rank 1.0 (best in subset) -> +1; rank 0.0 (worst) -> -1. Returns 0 when
    there isn't enough history.
    """
    if not sleeves:
        return pd.Series(dtype=float)
    window = sleeve_return_panel.loc[:as_of_date, [s for s in sleeves if s in sleeve_return_panel.columns]].tail(lookback_weeks)
    if window.empty or len(window) < max(8, lookback_weeks // 4):
        return pd.Series(0.0, index=sleeves, dtype=float)
    mean = window.mean(axis=0)
    std = window.std(axis=0, ddof=0)
    sharpe = mean.div(std.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    if sharpe.dropna().empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    ranks = sharpe.rank(pct=True, method="average")
    conviction = (ranks - 0.5) * 2.0
    return conviction.reindex(sleeves).fillna(0.0)


def compute_confirmed_sleeve_quality(
    sleeve_return_panel: pd.DataFrame,
    as_of_date: pd.Timestamp,
    sleeves: list[str],
    *,
    short_lookback: int = 13,
    long_lookback: int = 52,
) -> pd.Series:
    """Phase 3 B1: persistence-confirmed rolling-Sharpe sleeve-quality score.

    Computes rank-based rolling-Sharpe conviction on two horizons (short: 13w
    momentum of sleeve quality; long: 52w structural quality). Combines as a
    50/50 blend, then:
      - amplifies by 1.3x when both horizons agree on sign (persistent quality)
      - dampens to 0.4x when they disagree (noisy / transitory)
    Returns a value in roughly [-1.3, +1.3] which is clipped to [-1, +1] so
    downstream tilt math stays bounded. Walk-forward, no lookahead.
    """
    if not sleeves:
        return pd.Series(dtype=float)
    short = compute_rolling_sleeve_conviction(
        sleeve_return_panel, as_of_date, sleeves, lookback_weeks=short_lookback
    )
    long = compute_rolling_sleeve_conviction(
        sleeve_return_panel, as_of_date, sleeves, lookback_weeks=long_lookback
    )
    if short.empty or long.empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    blended = 0.5 * short + 0.5 * long
    same_sign = (np.sign(short) * np.sign(long)) > 0
    out = blended.where(~same_sign, blended * 1.3)
    out = out.where(same_sign | (short.abs() < 1e-9) | (long.abs() < 1e-9), blended * 0.4)
    return out.clip(-1.0, 1.0).reindex(sleeves).fillna(0.0)


def compute_state_sleeve_lead_tilt(
    sleeve_return_panel: pd.DataFrame,
    market_state_history: pd.DataFrame | None,
    as_of_date: pd.Timestamp,
    sleeves: list[str],
    *,
    lookback_weeks: int = 156,
    min_state_obs: int = 16,
) -> pd.Series:
    """Phase 3 C1: walk-forward state-conditioned sleeve-leadership tilt.

    Looks up the current market_state at `as_of_date` and computes the trailing
    Sharpe of each sleeve during weeks where the state matched, using only
    history strictly up to `as_of_date`. Returns a rank-based tilt in [-1, +1]
    (top sleeve in current state -> +1, worst -> -1). Returns zero if the
    current state is unknown or has too few past observations.
    """
    if not sleeves or market_state_history is None or market_state_history.empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    if "market_state" not in market_state_history.columns:
        return pd.Series(0.0, index=sleeves, dtype=float)
    try:
        current_row = market_state_history.loc[as_of_date]
    except KeyError:
        return pd.Series(0.0, index=sleeves, dtype=float)
    current_state = ""
    if isinstance(current_row, pd.Series):
        current_state = str(current_row.get("market_state", "") or "")
    if not current_state:
        return pd.Series(0.0, index=sleeves, dtype=float)
    history = market_state_history.loc[:as_of_date]
    if history.empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    history = history.iloc[:-1] if len(history) > 1 else history  # exclude current week
    history = history.tail(lookback_weeks)
    mask = history["market_state"] == current_state
    if int(mask.sum()) < min_state_obs:
        return pd.Series(0.0, index=sleeves, dtype=float)
    state_dates = history.index[mask]
    valid = [s for s in sleeves if s in sleeve_return_panel.columns]
    if not valid:
        return pd.Series(0.0, index=sleeves, dtype=float)
    sub = sleeve_return_panel.loc[
        sleeve_return_panel.index.intersection(state_dates), valid
    ]
    if sub.empty or len(sub) < min_state_obs:
        return pd.Series(0.0, index=sleeves, dtype=float)
    mean = sub.mean(axis=0)
    std = sub.std(axis=0, ddof=0)
    sharpe = mean.div(std.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    if sharpe.dropna().empty:
        return pd.Series(0.0, index=sleeves, dtype=float)
    ranks = sharpe.rank(pct=True, method="average")
    tilt = (ranks - 0.5) * 2.0
    return tilt.reindex(sleeves).fillna(0.0)


def compute_phasec_learned_sleeve_quality(
    sleeve_return_panel: pd.DataFrame,
    market_state_history: pd.DataFrame | None,
    sleeves: list[str],
    *,
    horizon_weeks: int = 4,
    min_train_weeks: int = 104,
    retrain_frequency: int = 13,
) -> pd.DataFrame:
    """Phase C C1: walk-forward logistic sleeve-leadership probabilities.

    Builds a pooled sleeve-date panel using only causal sleeve and market-state
    features, then fits an expanding-window LogisticRegression to estimate the
    probability that a sleeve will land in the top half of the active sleeve
    set over the next `horizon_weeks`. Predictions are cached per sleeve set.
    """
    valid_sleeves = [name for name in sleeves if name in sleeve_return_panel.columns]
    if not valid_sleeves:
        return pd.DataFrame(index=sleeve_return_panel.index, columns=sleeves, dtype=float)
    if market_state_history is None or market_state_history.empty:
        return pd.DataFrame(0.5, index=sleeve_return_panel.index, columns=sleeves, dtype=float)

    cache_key = tuple(valid_sleeves)
    cached = PHASEC_LEARNED_QUALITY_CACHE.get(cache_key)
    if cached is not None:
        return cached.reindex(index=sleeve_return_panel.index, columns=sleeves).fillna(0.5)

    returns = sleeve_return_panel.reindex(columns=valid_sleeves).sort_index().fillna(0.0)
    market_features = market_state_history.reindex(returns.index).copy()
    if market_features.empty:
        out = pd.DataFrame(0.5, index=returns.index, columns=sleeves, dtype=float)
        PHASEC_LEARNED_QUALITY_CACHE[cache_key] = out.reindex(columns=valid_sleeves).copy()
        return out

    state_dummies = pd.get_dummies(market_features["market_state"].fillna("unknown"), prefix="state", dtype=float)
    market_feature_frame = pd.DataFrame(index=returns.index)
    for col in [
        "market_trend_positive",
        "breadth_13w_mom",
        "breadth_26w_mom",
        "breadth_change_4w",
        "transition_good_state_prob",
        "transition_persistence_prob",
        "transition_non_stress_prob",
        "recent_stress_26w",
        "market_drawdown",
        "risk_regime_score",
        "canary_breadth_pair",
    ]:
        if col in market_features.columns:
            market_feature_frame[col] = pd.to_numeric(market_features[col], errors="coerce")
    market_feature_frame = market_feature_frame.join(state_dummies, how="left").fillna(0.0)

    trailing_mean_13 = returns.rolling(13, min_periods=8).mean().shift(1)
    trailing_std_13 = returns.rolling(13, min_periods=8).std(ddof=0).shift(1)
    trailing_mean_52 = returns.rolling(52, min_periods=16).mean().shift(1)
    trailing_std_52 = returns.rolling(52, min_periods=16).std(ddof=0).shift(1)
    trailing_win_13 = (returns > 0.0).astype(float).rolling(13, min_periods=8).mean().shift(1)
    trailing_cum_13 = ((1.0 + returns).rolling(13, min_periods=8).apply(np.prod, raw=True) - 1.0).shift(1)
    trailing_cum_26 = ((1.0 + returns).rolling(26, min_periods=8).apply(np.prod, raw=True) - 1.0).shift(1)
    trailing_dd_13 = (
        returns.rolling(13, min_periods=8)
        .apply(lambda x: (np.cumprod(1.0 + x) / np.maximum.accumulate(np.cumprod(1.0 + x)) - 1.0).min(), raw=True)
        .shift(1)
    )
    trailing_dd_52 = (
        returns.rolling(52, min_periods=16)
        .apply(lambda x: (np.cumprod(1.0 + x) / np.maximum.accumulate(np.cumprod(1.0 + x)) - 1.0).min(), raw=True)
        .shift(1)
    )

    shifted_forward = returns.shift(-1)
    forward_4w = (1.0 + shifted_forward).rolling(horizon_weeks, min_periods=horizon_weeks).apply(np.prod, raw=True).shift(-(horizon_weeks - 1)) - 1.0
    future_rank_cut = forward_4w.median(axis=1, skipna=True)
    future_top_half = forward_4w.ge(future_rank_cut, axis=0).astype(float)

    feature_rows: list[pd.DataFrame] = []
    for sleeve_name in valid_sleeves:
        sleeve_frame = pd.DataFrame(index=returns.index)
        sleeve_frame["Date"] = returns.index
        sleeve_frame["sleeve"] = sleeve_name
        sleeve_frame["quality_13"] = trailing_mean_13[sleeve_name].div(trailing_std_13[sleeve_name].replace(0.0, np.nan))
        sleeve_frame["quality_52"] = trailing_mean_52[sleeve_name].div(trailing_std_52[sleeve_name].replace(0.0, np.nan))
        sleeve_frame["cum_13"] = trailing_cum_13[sleeve_name]
        sleeve_frame["cum_26"] = trailing_cum_26[sleeve_name]
        sleeve_frame["vol_13"] = trailing_std_13[sleeve_name]
        sleeve_frame["win_13"] = trailing_win_13[sleeve_name]
        sleeve_frame["dd_13"] = trailing_dd_13[sleeve_name]
        sleeve_frame["dd_52"] = trailing_dd_52[sleeve_name]
        sleeve_frame["future_top_half"] = future_top_half[sleeve_name]
        sleeve_frame = sleeve_frame.join(market_feature_frame, how="left")
        feature_rows.append(sleeve_frame)

    panel = pd.concat(feature_rows, axis=0, ignore_index=True)
    panel["Date"] = pd.to_datetime(panel["Date"]).dt.tz_localize(None)
    panel = panel.sort_values(["Date", "sleeve"]).reset_index(drop=True)
    sleeve_dummies = pd.get_dummies(panel["sleeve"], prefix="sleeve", dtype=float)
    feature_cols = [col for col in panel.columns if col not in {"Date", "sleeve", "future_top_half"}]
    model_frame = pd.concat([panel[["Date", "future_top_half"] + feature_cols], sleeve_dummies], axis=1)
    model_feature_cols = [col for col in model_frame.columns if col not in {"Date", "future_top_half"}]
    model_frame[model_feature_cols] = model_frame[model_feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    dates = list(returns.index)
    pred_rows: list[pd.Series] = []
    last_fit_cutoff: pd.Timestamp | None = None
    fitted_model: LogisticRegression | None = None
    fitted_feature_cols: list[str] = []

    for date in dates:
        prediction_row = pd.Series(0.5, index=valid_sleeves, dtype=float, name=date)
        train_cutoff = date - pd.Timedelta(weeks=horizon_weeks)
        if last_fit_cutoff is None or (date - last_fit_cutoff).days >= 7 * retrain_frequency:
            train_mask = model_frame["Date"] <= train_cutoff
            train_data = model_frame.loc[train_mask].dropna(subset=["future_top_half"])
            unique_train_dates = int(train_data["Date"].nunique()) if not train_data.empty else 0
            if unique_train_dates >= min_train_weeks and train_data["future_top_half"].nunique() > 1:
                X_train = train_data[model_feature_cols]
                y_train = train_data["future_top_half"].astype(int)
                model = LogisticRegression(
                    max_iter=1000,
                    C=0.5,
                    solver="lbfgs",
                    class_weight="balanced",
                )
                model.fit(X_train, y_train)
                fitted_model = model
                fitted_feature_cols = list(model_feature_cols)
                last_fit_cutoff = date
        if fitted_model is not None:
            pred_data = model_frame.loc[model_frame["Date"] == date, ["Date"] + fitted_feature_cols].copy()
            if not pred_data.empty:
                pred_index = panel.loc[panel["Date"] == date, "sleeve"].tolist()
                probs = fitted_model.predict_proba(pred_data[fitted_feature_cols])[:, 1]
                prediction_row.loc[pred_index] = probs
        pred_rows.append(prediction_row)

    pred_df = pd.DataFrame(pred_rows).sort_index().reindex(index=returns.index, columns=valid_sleeves).fillna(0.5)
    PHASEC_LEARNED_QUALITY_CACHE[cache_key] = pred_df.copy()
    return pred_df.reindex(columns=sleeves).fillna(0.5)


def _apply_sector_state_gate(
    weights: pd.Series,
    market_state: str | None,
    *,
    gate_states: frozenset[str] = frozenset({"recovery_fragile", "recovery_confirmed"}),
) -> pd.Series:
    """Phase 3.1 A1g (and 3.2 R1 tightened): gate sector_rotation_with_sma_filter.

    Deploy the sleeve only in the market states listed in `gate_states`. In
    every other state its weight is forced to zero before long-only
    renormalisation.

    Phase 3.1 A1g uses the default two-state gate. Phase 3.2 R1 passes
    `frozenset({"recovery_confirmed"})` to further restrict deployment to the
    single state where the prior per-state Sharpe evidence was overwhelmingly
    strongest.
    """
    out = weights.copy()
    sector_name = "sector_rotation_with_sma_filter"
    if sector_name in out.index:
        if market_state not in gate_states:
            out.loc[sector_name] = 0.0
    return out


def _apply_sector_dd_guard(
    weights: pd.Series,
    market_state_row: pd.Series | None,
) -> pd.Series:
    """Phase 3.2 R2: drawdown-proximity guard on sector_rotation_with_sma_filter.

    When the benchmark is already in a material drawdown the offensive
    sector sleeve is shrunk proportionally:
      - market_drawdown <= -0.10                  → sector weight *= 0.00
      - -0.10 <  market_drawdown <= -0.05         → sector weight *= 0.50
      - market_drawdown >   -0.05                 → sector weight *= 1.00

    Rationale: even inside the favorable recovery states, DD depths vary
    widely. Early recovery_fragile weeks can still sit at -10% to -15%
    benchmark drawdown, and that is exactly where the ungated sector sleeve
    added portfolio DD in Combo1. A shallow, causal throttle based on the
    benchmark's own drawdown (which is in `market_state_row`) is a narrow,
    interpretable defensive modifier — it does not introduce a new overlay
    system or a second risk engine.
    """
    out = weights.copy()
    sector_name = "sector_rotation_with_sma_filter"
    if sector_name not in out.index:
        return out
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return out
    try:
        md = float(market_state_row.get("market_drawdown", 0.0) or 0.0)
    except (TypeError, ValueError):
        md = 0.0
    if md <= -0.10:
        out.loc[sector_name] *= 0.0
    elif md <= -0.05:
        out.loc[sector_name] *= 0.5
    return out


def _apply_sector_fragile_dd_guard(
    weights: pd.Series,
    market_state: str | None,
    market_state_row: pd.Series | None,
) -> pd.Series:
    """Phase 3.4 T1: narrow, fragile-only DD guard on the sector sleeve.

    Identical in shape to `_apply_sector_dd_guard` (Phase 3.2 R2) but scoped
    ONLY to market_state == "recovery_fragile". In `recovery_confirmed` the
    sector sleeve keeps full exposure — per the Phase 3.2 finding that the
    DD tail is concentrated in fragile-recovery weeks (benchmark DD in
    recovery_fragile has median -1.9% and 25th pct -12.9%; in
    recovery_confirmed it only reaches about -5.8% at worst).

    Thresholds were set on the actual recovery_fragile drawdown distribution
    (not tuned against the portfolio composite):
      - recovery_fragile & market_drawdown <= -0.15  → sector weight *= 0.00
      - recovery_fragile & -0.15 < md <= -0.05       → sector weight *= 0.50
      - everywhere else                              → unchanged
    """
    if market_state != "recovery_fragile":
        return weights
    out = weights.copy()
    sector_name = "sector_rotation_with_sma_filter"
    if sector_name not in out.index:
        return out
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return out
    try:
        md = float(market_state_row.get("market_drawdown", 0.0) or 0.0)
    except (TypeError, ValueError):
        md = 0.0
    if md <= -0.15:
        out.loc[sector_name] *= 0.0
    elif md <= -0.05:
        out.loc[sector_name] *= 0.5
    return out


def _dd_gradient_tilt_dampener(market_state_row: pd.Series | None) -> float:
    """Phase 3.4 T2: benchmark-drawdown tilt-magnitude dampener.

    When the benchmark is already in a material drawdown, shrink the
    state-leader tilt magnitude across all sleeves and all states. Returns
    a multiplicative factor in (0, 1] that is applied to the tilt bound.

      - market_drawdown <= -0.10  → 0.5   (halve the tilt magnitude)
      - -0.10 < md <= -0.05       → 0.75  (modest shrink)
      - md > -0.05                → 1.0   (full tilt)

    Causal: uses only the walk-forward-available `market_drawdown` feature
    on the market-state row. Does not affect the sector gate and does not
    add any new overlay.
    """
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return 1.0
    try:
        md = float(market_state_row.get("market_drawdown", 0.0) or 0.0)
    except (TypeError, ValueError):
        md = 0.0
    if md <= -0.10:
        return 0.5
    if md <= -0.05:
        return 0.75
    return 1.0


def _phasec_favorable_state(market_state: str | None, strong_neutral_flag: bool) -> bool:
    return market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"} or strong_neutral_flag


def _apply_phasec_state_map(
    weights: pd.Series,
    market_state: str | None,
    *,
    strong_neutral_flag: bool = False,
) -> pd.Series:
    out = pd.Series(weights, dtype=float).copy()

    def bump(name: str, multiplier: float) -> None:
        if name in out.index:
            out.loc[name] *= multiplier

    if market_state == "calm_trend":
        bump("composite_trend_quality_refined", 1.10)
        bump("dual_momentum_topn", 1.04)
        bump("cta_trend_long_only", 1.03)
        bump("composite_confirmation_aware_momentum", 0.97)
        bump("composite_regime_conditioned", 0.90)
    elif market_state == "recovery_confirmed":
        bump("composite_confirmation_aware_momentum", 1.10)
        bump("composite_trend_quality_refined", 1.06)
        bump("cta_trend_long_only", 1.03)
        bump("dual_momentum_topn", 0.98)
        bump("composite_regime_conditioned", 0.90)
    elif market_state == "recovery_fragile":
        bump("composite_trend_quality_refined", 1.08)
        bump("cta_trend_long_only", 1.06)
        bump("composite_confirmation_aware_momentum", 1.03)
        bump("composite_regime_conditioned", 0.92)
    elif strong_neutral_flag:
        bump("composite_trend_quality_refined", 1.08)
        bump("composite_confirmation_aware_momentum", 1.05)
        bump("dual_momentum_topn", 1.03)
        bump("composite_regime_conditioned", 0.93)
        bump("taa_10m_sma", 0.98)
    return out


def apply_state_conditioned_tilt(
    raw_weights: pd.Series,
    market_state: str | None,
    tilt_mode: str = "none",
    *,
    conviction: pd.Series | None = None,
    market_state_row: pd.Series | None = None,
    state_lead_tilt: pd.Series | None = None,
) -> pd.Series:
    if tilt_mode == "none":
        return ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    tilted = pd.Series(raw_weights, dtype=float).copy()
    offensive_sleeves = [name for name in OFFENSIVE_SLEEVE_CANDIDATES if name in tilted.index]
    defensive_sleeves = [name for name in DEFENSIVE_SLEEVE_CANDIDATES if name in tilted.index]

    strong_neutral_flag = False
    if market_state_row is not None and isinstance(market_state_row, pd.Series) and not market_state_row.empty:
        strong_neutral_flag = is_strong_neutral_state_row(market_state_row)

    ooo6_modes = {
        "phase_ooo6_efa_spy_selective_tilt",
        "phase_ooo6_efa_spy_vol_filtered_tilt",
        "phase_ooo6_efa_spy_trend_confirmed_tilt",
    }
    sss3_modes = {
        "phase_sss3_calm_old_low_stress_derisk",
        "phase_sss3_stress_new_state_defense",
        "phase_sss3_recovery_sequence_rerisk",
        "phase_sss3_combined_sequence_overlay",
    }
    if tilt_mode in sss3_modes:
        # Start from GGG1's confirmed-only robust offense architecture, then
        # apply tiny sequence overlays only when the explicit SSS2 lagged signal
        # is active. This keeps recovery/stress component logic intact.
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase_ddd_confirmed_near_exclude_dual",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
        if date_key is None:
            return base
        date_key = pd.to_datetime(date_key).tz_localize(None)

        def _sss2_signal_fires(signal_name: str) -> bool:
            return bool(SSS2_SIGNAL_LOOKUPS.get(signal_name, {}).get(date_key, 0))

        offense_sources = [
            name for name in [
                "dual_momentum_topn",
                "cta_trend_long_only",
                "composite_selective_signals",
                "composite_regime_offense_component",
            ]
            if name in base.index
        ]
        defense_sources = [
            name for name in ["composite_regime_defense_component", "taa_10m_sma"]
            if name in base.index
        ]

        def _sequence_derisk(weights: pd.Series, amount: float) -> pd.Series:
            out = _shift_bucket_mass(
                weights,
                source_names=offense_sources,
                shift_amount=amount,
                target_mix={
                    "composite_regime_defense_component": 0.65,
                    "taa_10m_sma": 0.35,
                },
            )
            return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

        def _sequence_rerisk(weights: pd.Series, amount: float) -> pd.Series:
            out = _shift_bucket_mass(
                weights,
                source_names=defense_sources,
                shift_amount=amount,
                target_mix={
                    "composite_regime_offense_component": 0.62,
                    "cta_trend_long_only": 0.28,
                    "dual_momentum_topn": 0.10,
                },
            )
            return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

        calm_warning = _sss2_signal_fires("calm_old_low_stress_signal")
        stress_warning = _sss2_signal_fires("stress_new_state_signal")
        rerisk_confirm = _sss2_signal_fires("qqq_efa_spy_trend_after_calm_or_recovery_signal")

        if tilt_mode == "phase_sss3_calm_old_low_stress_derisk":
            if calm_warning and market_state in {"calm_trend", "neutral_mixed"}:
                return _sequence_derisk(base, 0.015)
            return base
        if tilt_mode == "phase_sss3_stress_new_state_defense":
            if stress_warning and market_state == "stressed_panic":
                return _sequence_derisk(base, 0.020)
            return base
        if tilt_mode == "phase_sss3_recovery_sequence_rerisk":
            if rerisk_confirm and (market_state in {"recovery_confirmed", "calm_trend"} or strong_neutral_flag):
                return _sequence_rerisk(base, 0.015)
            return base
        if tilt_mode == "phase_sss3_combined_sequence_overlay":
            if stress_warning and market_state == "stressed_panic":
                return _sequence_derisk(base, 0.015)
            if calm_warning and market_state in {"calm_trend", "neutral_mixed"}:
                return _sequence_derisk(base, 0.010)
            if rerisk_confirm and (market_state in {"recovery_confirmed", "calm_trend"} or strong_neutral_flag):
                return _sequence_rerisk(base, 0.012)
            return base

    if tilt_mode in ooo6_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase_ddd_confirmed_near_exclude_dual",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        if market_state not in {"calm_trend", "neutral_mixed"} and not strong_neutral_flag:
            return base
        date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
        if date_key is None:
            return base
        date_key = pd.to_datetime(date_key).tz_localize(None)
        if tilt_mode == "phase_ooo6_efa_spy_selective_tilt":
            fires = bool(OOO3_EVENT_LOOKUPS.get("efa_spy_raw_top10_event", {}).get(date_key, 0))
            multipliers = {
                "composite_regime_offense_component": 1.06,
                "cta_trend_long_only": 1.02,
                "composite_regime_defense_component": 0.96,
                "taa_10m_sma": 0.98,
            }
        elif tilt_mode == "phase_ooo6_efa_spy_vol_filtered_tilt":
            fires = bool(OOO3_EVENT_LOOKUPS.get("efa_spy_vol_filtered_top20_event", {}).get(date_key, 0))
            multipliers = {
                "composite_regime_offense_component": 1.04,
                "cta_trend_long_only": 1.01,
                "composite_regime_defense_component": 0.98,
                "taa_10m_sma": 0.99,
            }
        else:
            efa_gate = bool(OOO3_EVENT_LOOKUPS.get("efa_spy_market_trend_confirmed_top20_event", {}).get(date_key, 0))
            trend_gate = bool(OOO3_EVENT_LOOKUPS.get("market_trend_breadth_confirmed_event", {}).get(date_key, 0))
            fires = efa_gate and trend_gate
            multipliers = {
                "composite_regime_offense_component": 1.05,
                "cta_trend_long_only": 1.015,
                "composite_regime_defense_component": 0.97,
                "taa_10m_sma": 0.985,
            }
        if not fires:
            return base
        out = pd.Series(base, dtype=float).copy()
        for sleeve, multiplier in multipliers.items():
            if sleeve in out.index:
                out.loc[sleeve] *= multiplier
        return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 4 — dedicated sector-rotation offense sleeve.
    # All modes start from GGG1 and only add sector exposure when the
    # precomputed causal sector signal is active. stressed_panic is untouched.
    _phase4_modes = {
        "phase4_sector_small_overlay",
        "phase4_sector_20pct_offense",
        "phase4_sector_25pct_offense",
        "phase4_balanced_sector_breadth",
        "phase4_stretch_sector_momentum",
        "phase4_sector_us_hybrid",
    }
    if tilt_mode in _phase4_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase_ddd_confirmed_near_exclude_dual",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        if market_state == "stressed_panic":
            return base

        date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
        if date_key is None:
            return base
        date_key = pd.to_datetime(date_key).tz_localize(None)

        def _phase4_fires(signal_name: str) -> bool:
            return bool(PHASE4_SIGNAL_LOOKUPS.get(signal_name, {}).get(date_key, 0))

        phase4_configs = {
            "phase4_sector_small_overlay": {
                "sector_sleeve": "phase4_top5_sector_momentum_sleeve",
                "signal": "sector_breadth_confirmed",
                "target_budget": 0.12,
            },
            "phase4_sector_20pct_offense": {
                "sector_sleeve": "phase4_top3_sector_momentum_sleeve",
                "signal": "sector_breadth_confirmed",
                "target_budget": 0.20,
            },
            "phase4_sector_25pct_offense": {
                "sector_sleeve": "phase4_top3_sector_momentum_sleeve",
                "signal": "sector_breadth_confirmed",
                "target_budget": 0.25,
            },
            "phase4_balanced_sector_breadth": {
                "sector_sleeve": "phase4_balanced_sector_breadth_sleeve",
                "signal": "sector_breadth_confirmed",
                "target_budget": 0.20,
            },
            "phase4_stretch_sector_momentum": {
                "sector_sleeve": "phase4_stretch_sector_momentum_sleeve",
                "signal": "high_breadth_sector_bull",
                "target_budget": 0.25,
            },
            "phase4_sector_us_hybrid": {
                "sector_sleeve": "phase4_balanced_sector_breadth_sleeve",
                "signal": "sector_leadership_confirmed",
                "target_budget": 0.16,
            },
        }
        cfg = phase4_configs.get(tilt_mode, {})
        if not cfg or not _phase4_fires(str(cfg["signal"])):
            return base
        if market_state == "recovery_fragile" and not _phase4_fires("high_breadth_sector_bull"):
            return base

        sources = [
            f"cash::{ns5['cash_proxy']}",
            "composite_regime_defense_component",
            "taa_10m_sma",
            "composite_selective_signals",
            "composite_regime_offense_component",
        ]
        out = _phase4_shift_to_sector_budget(
            base,
            sector_sleeve=str(cfg["sector_sleeve"]),
            target_budget=float(cfg["target_budget"]),
            source_names=sources,
        )
        return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 4B — refined sector-rotation timing. These modes again start
    # from GGG1, but use the narrower Phase 4B causal signal panel and avoid
    # recovery_fragile/stressed_panic by construction.
    _phase4b_modes = {
        "phase4b_refined_sector_small_overlay",
        "phase4b_refined_sector_20pct",
        "phase4b_refined_sector_25pct_selective",
        "phase4b_sector_phase3_hybrid",
        "phase4b_return_unlock_stretch",
    }
    if tilt_mode in _phase4b_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase_ddd_confirmed_near_exclude_dual",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        phase4b_sector_sleeves = [
            "phase4b_top5_smooth_sector_sleeve",
            "phase4b_top4_risk_adjusted_sector_sleeve",
            "phase4b_top3_strict_sector_sleeve",
            "phase4b_defensive_aware_top5_sleeve",
            "phase4b_sector_blend_spy_qqq_sleeve",
            "phase4b_balanced_carry_forward_sleeve",
        ]

        def _strip_phase4b_sector_sleeves(weights: pd.Series) -> pd.Series:
            out = pd.Series(weights, dtype=float).copy()
            for sleeve_name in phase4b_sector_sleeves:
                if sleeve_name in out.index:
                    out.loc[sleeve_name] = 0.0
            return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

        base = _strip_phase4b_sector_sleeves(base)
        if market_state in {"stressed_panic", "recovery_fragile"}:
            return base

        date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
        if date_key is None:
            return base
        date_key = pd.to_datetime(date_key).tz_localize(None)

        def _phase4b_fires(signal_name: str) -> bool:
            return bool(PHASE4B_SIGNAL_LOOKUPS.get(signal_name, {}).get(date_key, 0))

        phase4b_configs = {
            "phase4b_refined_sector_small_overlay": {
                "sector_sleeve": "phase4b_top5_smooth_sector_sleeve",
                "signals_any": ["high_quality_sector_bull"],
                "target_budget": 0.12,
            },
            "phase4b_refined_sector_20pct": {
                "sector_sleeve": "phase4b_defensive_aware_top5_sleeve",
                "signals_any": ["high_quality_sector_bull", "calm_sector_leadership_only"],
                "target_budget": 0.20,
            },
            "phase4b_refined_sector_25pct_selective": {
                "sector_sleeve": "phase4b_top3_strict_sector_sleeve",
                "signals_any": ["sector_quality_score_high"],
                "target_budget": 0.25,
            },
            "phase4b_sector_phase3_hybrid": {
                "sector_sleeve": "phase4b_sector_blend_spy_qqq_sleeve",
                "signals_any": ["high_quality_sector_bull", "calm_sector_leadership_only"],
                "target_budget": 0.16,
            },
            "phase4b_return_unlock_stretch": {
                "sector_sleeve": "phase4b_top3_strict_sector_sleeve",
                "signals_any": ["sector_quality_score_high", "neutral_sector_confirmed_only"],
                "target_budget": 0.25,
            },
        }
        cfg = phase4b_configs.get(tilt_mode, {})
        if not cfg:
            return base
        if _phase4b_fires("defensive_sector_warning"):
            return base
        if not any(_phase4b_fires(signal) for signal in cfg["signals_any"]):
            return base

        sources = [
            f"cash::{ns5['cash_proxy']}",
            "composite_regime_defense_component",
            "taa_10m_sma",
            "composite_selective_signals",
            "composite_regime_offense_component",
        ]
        out = _phase4_shift_to_sector_budget(
            base,
            sector_sleeve=str(cfg["sector_sleeve"]),
            target_budget=float(cfg["target_budget"]),
            source_names=sources,
        )
        return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # ── Phase 6 — Market-State Classifier Rebuild ─────────────────────────────
    # All modes start from Phase 4B best base, then apply incremental classifier
    # improvements using market_state_row features directly (causal, no lookups).
    # stressed_panic is never modified.
    _phase6_modes = {
        "phase6_neutral_classifier_unlock",
        "phase6_calm_bull_quality_offense",
        "phase6_recovery_quality_rerisk",
        "phase6_continuous_aggression_score",
        "phase6_balanced_classifier_rebuild",
    }
    if tilt_mode in _phase6_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase4b_refined_sector_20pct",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        if market_state == "stressed_panic":
            return base

        _p6_sector = "phase4b_defensive_aware_top5_sleeve"
        _p6_def_srcs = [n for n in ["composite_regime_defense_component", "taa_10m_sma"] if n in base.index]

        # Inline classifier helpers — read market_state_row features directly
        def _p6_safe(key: str, default: float = 0.0) -> float:
            if market_state_row is None or not isinstance(market_state_row, pd.Series):
                return default
            v = market_state_row.get(key, default)
            try:
                return float(v) if v is not None and not pd.isna(v) else default
            except (TypeError, ValueError):
                return default

        _p6_breadth = _p6_safe("breadth_sma_43")
        _p6_trend = _p6_safe("market_trend_positive")
        _p6_canary = _p6_safe("canary_breadth_default")
        _p6_good_prob = _p6_safe("transition_good_state_prob")
        _p6_b_chg = _p6_safe("breadth_change_4w")
        _p6_b26 = _p6_safe("breadth_26w_mom")

        # Classifier conditions (all causal — features from week T applied to T+1)
        _extreme_quality_calm = (
            market_state == "calm_trend"
            and _p6_breadth >= 0.80
            and _p6_trend > 0.0
            and _p6_canary >= 1.0
        )
        _high_quality_neutral = (
            market_state == "neutral_mixed"
            and _p6_breadth >= 0.70
            and _p6_trend > 0.0
            and _p6_canary >= 1.0
            and _p6_good_prob >= 0.60
        )
        _low_quality_neutral = (
            market_state == "neutral_mixed"
            and (_p6_breadth < 0.50 or _p6_b_chg < -0.05)
        )
        _strong_recovery = (
            market_state == "recovery_confirmed"
            and _p6_b_chg >= 0.0
            and _p6_good_prob >= 0.55
        )
        # Composite aggression score (0-1) from breadth/trend/transition
        _p6_score = float(np.clip(
            0.35 * np.clip((_p6_breadth - 0.50) / 0.35, 0.0, 1.0) +
            0.25 * np.clip((_p6_b26 - 0.45) / 0.35, 0.0, 1.0) +
            0.15 * min(_p6_trend, 1.0) +
            0.15 * min(_p6_canary, 1.0) +
            0.10 * np.clip((_p6_good_prob - 0.50) / 0.30, 0.0, 1.0),
            0.0, 1.0,
        ))

        def _p6_boost(w: pd.Series, delta: float) -> pd.Series:
            """Shift delta from defense sources to sector sleeve."""
            if _p6_sector not in w.index or delta <= 0.0 or not _p6_def_srcs:
                return w
            current_sector = float(w.get(_p6_sector) or 0.0)
            new_target = float(np.clip(current_sector + delta, 0.0, 0.26))
            return _phase4_shift_to_sector_budget(
                w, sector_sleeve=_p6_sector, target_budget=new_target, source_names=_p6_def_srcs,
            )

        def _p6_retract(w: pd.Series, delta: float) -> pd.Series:
            """Shift delta from sector sleeve back to defense."""
            if _p6_sector not in w.index or delta <= 0.0 or not _p6_def_srcs:
                return w
            n_def = max(len(_p6_def_srcs), 1)
            return _shift_bucket_mass(
                w, source_names=[_p6_sector], shift_amount=delta,
                target_mix={n: 1.0 / n_def for n in _p6_def_srcs},
            )

        if tilt_mode == "phase6_neutral_classifier_unlock":
            if _high_quality_neutral:
                return ns5["normalize_long_only"](_p6_boost(base, 0.04), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if _low_quality_neutral:
                return ns5["normalize_long_only"](_p6_retract(base, 0.03), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase6_calm_bull_quality_offense":
            if _extreme_quality_calm:
                return ns5["normalize_long_only"](_p6_boost(base, 0.04), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase6_recovery_quality_rerisk":
            if _strong_recovery:
                return ns5["normalize_long_only"](_p6_boost(base, 0.04), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase6_continuous_aggression_score":
            if _p6_score >= 0.72:
                return ns5["normalize_long_only"](_p6_boost(base, 0.03), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if _p6_score <= 0.28:
                return ns5["normalize_long_only"](_p6_retract(base, 0.02), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase6_balanced_classifier_rebuild":
            if _high_quality_neutral or _extreme_quality_calm:
                return ns5["normalize_long_only"](_p6_boost(base, 0.035), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if _strong_recovery:
                return ns5["normalize_long_only"](_p6_boost(base, 0.025), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if _low_quality_neutral:
                return ns5["normalize_long_only"](_p6_retract(base, 0.025), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        return base

    # ── Phase 7 — Allocator Objective Rewrite ────────────────────────────────
    # All modes start from Phase 4B best, then apply larger sector sleeve budgets
    # using the same _phase4b_fires signals. The key change: target budget increases
    # from Phase4B's 20% to 28-32%, pulling from defense/cash sources.
    # stressed_panic is never modified. All signals from PHASE4B_SIGNAL_LOOKUPS.
    _phase7_modes = {
        "phase7_larger_sector_calm",
        "phase7_expression_boost",
        "phase7_max_sector_rerisk",
        "phase7_combined_offensive",
        "phase7_stretch_target",
    }
    if tilt_mode in _phase7_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase4b_refined_sector_20pct",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        if market_state == "stressed_panic":
            return base

        _p7_sector = "phase4b_defensive_aware_top5_sleeve"
        _p7_sources = [
            n for n in [
                f"cash::{ns5['cash_proxy']}",
                "composite_regime_defense_component",
                "taa_10m_sma",
                "composite_selective_signals",
            ]
            if n in base.index
        ]
        date_key = getattr(market_state_row, "name", None) if isinstance(market_state_row, pd.Series) else None
        if date_key is not None:
            date_key = pd.to_datetime(date_key).tz_localize(None)

        def _p7_fires(signal_name: str) -> bool:
            return bool(PHASE4B_SIGNAL_LOOKUPS.get(signal_name, {}).get(date_key, 0))

        _quality_on = (
            _p7_fires("high_quality_sector_bull") or
            _p7_fires("calm_sector_leadership_only")
        )

        if tilt_mode == "phase7_larger_sector_calm":
            if _quality_on and _p7_sector in base.index:
                out = _phase4_shift_to_sector_budget(
                    base, sector_sleeve=_p7_sector, target_budget=0.28, source_names=_p7_sources,
                )
                return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase7_expression_boost":
            # Same tilt as Phase4B; expression mode handles the additional shift
            # (layer3_expression_mode="phase7_aggressive_expression" in version spec)
            return base

        if tilt_mode == "phase7_max_sector_rerisk":
            if _quality_on and _p7_sector in base.index:
                out = _phase4_shift_to_sector_budget(
                    base, sector_sleeve=_p7_sector, target_budget=0.28, source_names=_p7_sources,
                )
                return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase7_combined_offensive":
            target = 0.28 if _quality_on else float(base.get(_p7_sector, 0.0) or 0.0)
            if _quality_on and _p7_sector in base.index and target > float(base.get(_p7_sector, 0.0) or 0.0):
                out = _phase4_shift_to_sector_budget(
                    base, sector_sleeve=_p7_sector, target_budget=target, source_names=_p7_sources,
                )
                return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        if tilt_mode == "phase7_stretch_target":
            target = 0.32 if _quality_on else float(base.get(_p7_sector, 0.0) or 0.0)
            if _quality_on and _p7_sector in base.index and target > float(base.get(_p7_sector, 0.0) or 0.0):
                out = _phase4_shift_to_sector_budget(
                    base, sector_sleeve=_p7_sector, target_budget=target, source_names=_p7_sources,
                )
                return ns5["normalize_long_only"](out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base

        return base

    # Phase 2 Aggressive ETF Variant — state-conditioned defense->offense sleeve shifts.
    # All modes start from GGG1's confirmed-near-exclude-dual base, then apply
    # bounded _shift_bucket_mass calls only in the target states.
    # stressed_panic is never modified; recovery_fragile is left alone (cautious).
    _phase2_aggressive_modes = {
        "phase2_aggressive_calm_offense",
        "phase2_aggressive_recovery_offense",
        "phase2_aggressive_nonstressed_offense",
        "phase2_aggressive_balanced_offense",
        "phase2_aggressive_stretch_offense",
    }
    if tilt_mode in _phase2_aggressive_modes:
        base = apply_state_conditioned_tilt(
            raw_weights,
            market_state,
            "phase_ddd_confirmed_near_exclude_dual",
            conviction=conviction,
            market_state_row=market_state_row,
            state_lead_tilt=state_lead_tilt,
        )
        _p2_offense_targets = {
            "composite_selective_signals": 0.45,
            "composite_regime_offense_component": 0.20,
            "dual_momentum_topn": 0.22,
            "cta_trend_long_only": 0.13,
        }
        _p2_defense_sources = [
            n for n in ["composite_regime_defense_component", "taa_10m_sma"] if n in base.index
        ]
        if tilt_mode == "phase2_aggressive_calm_offense":
            if market_state == "calm_trend":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.09, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base
        if tilt_mode == "phase2_aggressive_recovery_offense":
            if market_state == "recovery_confirmed":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.06, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base
        if tilt_mode == "phase2_aggressive_nonstressed_offense":
            if market_state == "calm_trend":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.09, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if market_state == "neutral_mixed" or strong_neutral_flag:
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.05, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if market_state == "recovery_confirmed":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.04, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base
        if tilt_mode == "phase2_aggressive_balanced_offense":
            if market_state == "calm_trend":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.06, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if market_state == "neutral_mixed" or strong_neutral_flag:
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.03, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base
        if tilt_mode == "phase2_aggressive_stretch_offense":
            if market_state == "calm_trend":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.12, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if market_state == "neutral_mixed" or strong_neutral_flag:
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.08, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            if market_state == "recovery_confirmed":
                _out = _shift_bucket_mass(base, source_names=_p2_defense_sources, shift_amount=0.07, target_mix=_p2_offense_targets)
                return ns5["normalize_long_only"](_out, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
            return base
        return base

    if tilt_mode in {
        "phase_rr_good_state_bucket_participation",
        "phase_rr_recovery_bucket_repair",
        "phase_rr_combined_bucket_allocator",
    }:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        tilted = _apply_phase_rr_bucket_architecture(
            tilted,
            tilt_mode=tilt_mode,
            market_state=market_state,
            strong_neutral_flag=strong_neutral_flag,
        )
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    if tilt_mode in {
        "phase_ss_recovery_explicit_bucket",
        "phase_ss_good_state_explicit_bucket",
        "phase_ss_combined_explicit_bucket",
    }:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.12 * c, 0.88, 1.12))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.03
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.97
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        tilted = _apply_phase_ss_explicit_bucket_architecture(
            tilted,
            tilt_mode=tilt_mode,
            market_state=market_state,
            strong_neutral_flag=strong_neutral_flag,
        )
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    if tilt_mode in {
        "phase_tt_recovery_two_stage_bucket",
        "phase_tt_recovery_neutral_two_stage_bucket",
    }:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed"}
            or (tilt_mode == "phase_tt_recovery_neutral_two_stage_bucket" and strong_neutral_flag)
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.10 * c, 0.90, 1.10))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.01
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.99
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        tilted = _apply_phase_tt_two_stage_bucket_architecture(
            tilted,
            tilt_mode=tilt_mode,
            market_state=market_state,
            strong_neutral_flag=strong_neutral_flag,
        )
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    if tilt_mode in {"phase_yy_conservative_decomposition",
                       "phase_zz_recovery_offense_rebudget",
                       "phase_zz_recovery_neutral_offense_rebudget",
                       "phase_zz_confirmed_freer_fragile_conservative",
                       "phase_zz_conservative_decomposition_repair",
                       "phase_aaa_confirmed_offense_escalation",
                       "phase_aaa_confirmed_offense_mix_tilt",
                       "phase_aaa_confirmed_defense_composition_repair",
                       "phase_aaa_confirmed_only_combined_repair",
                       "phase_bbb_stronger_confirmed_offense_mix",
                       "phase_bbb_composite_offense_component_tilt",
                       "phase_bbb_offense_defense_composition_combo",
                       "phase_bbb_conservative_confirmed_composition",
                       "phase_ccc_confirmed_cap_css",
                       "phase_ccc_confirmed_cap_dual",
                       "phase_ccc_confirmed_cap_dual_css",
                       "phase_ccc_conservative_confirmed_pruning",
                       "phase_ddd_confirmed_harder_dual_cap",
                       "phase_ddd_confirmed_near_exclude_dual",
                       "phase_ddd_confirmed_dual_hard_css_soft",
                       "phase_ddd_confirmed_defensive_balanced_substitution",
                       "phase_ddd_minimal_dual_polish",
                       "phase_ddd_confirmed_comp_off_receiver"}:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.08 * c, 0.92, 1.08))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.01
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.99
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_defense_component" in tilted.index:
                tilted.loc["composite_regime_defense_component"] *= 1.06
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        tilted = _apply_phase_yy_decomposition_architecture(
            tilted,
            tilt_mode=tilt_mode,
            market_state=market_state,
            strong_neutral_flag=strong_neutral_flag,
        )
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 1 Variant A: dynamic risk budgeting.
    # Apply a bounded rank-based conviction tilt on favorable states only.
    # Stressed_panic keeps the existing defensive shift; unknown / neutral
    # states pass through unchanged.
    if tilt_mode in {"dynamic_risk_budget", "dynamic_risk_budget_phasemm_recovery_confirmed_fix"}:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            # Mild re-risk on top of the conviction tilt so the handoff
            # doesn't stall in fragile weeks.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        if tilt_mode == "dynamic_risk_budget_phasemm_recovery_confirmed_fix" and market_state == "recovery_confirmed":
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.78
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.12
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.06
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.03
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # ======================================================================
    # Phase FF / GG — In-allocator integration of Phase CC's defensive_overlay_hint.
    # Identical to dynamic_risk_budget EXCEPT that on gate weeks an additional
    # offensive-sleeve multiplier (1 - delta) is applied before the cap
    # normalization. The cap and lighter_both overlay downstream apply
    # unchanged, preserving cost / overlay / cap pipeline fidelity vs production.
    #
    # Variants:
    #   'dynamic_risk_budget_phaseff_light'        — gate=hint+state guard, delta=0.05
    #   'dynamic_risk_budget_phaseff_state_gated'  — gate=refined_state, delta=0.05
    #   'dynamic_risk_budget_phasegg_10'           — gate=hint+state guard, delta=0.10
    #   'dynamic_risk_budget_phasegg_15'           — gate=hint+state guard, delta=0.15
    # ======================================================================
    PHASE_HINT_TILT_MAGNITUDES = {
        "dynamic_risk_budget_phaseff_light": 0.05,
        "dynamic_risk_budget_phaseff_state_gated": 0.05,
        "dynamic_risk_budget_phasegg_10": 0.10,
        "dynamic_risk_budget_phasegg_15": 0.15,
    }
    PHASE_HINT_TILT_GATES = {
        "dynamic_risk_budget_phaseff_light": "hint_excluding_already_stressed",
        "dynamic_risk_budget_phaseff_state_gated": "refined_state_neutral_deteriorating",
        "dynamic_risk_budget_phasegg_10": "hint_excluding_already_stressed",
        "dynamic_risk_budget_phasegg_15": "hint_excluding_already_stressed",
    }
    if tilt_mode in PHASE_HINT_TILT_MAGNITUDES:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        # Phase FF / GG hint augmentation — additive on top of dynamic_risk_budget.
        # Looks up the hint / refined_state for the current date via market_state_row.name.
        gate_fires = False
        if market_state_row is not None and isinstance(market_state_row, pd.Series) and getattr(market_state_row, "name", None) is not None:
            date_key = market_state_row.name
            hint_val = int(PHASEFF_HINT_LOOKUP.get(date_key, 0))
            ref_state = str(PHASEFF_REFINED_STATE_LOOKUP.get(date_key, ""))
            gate_kind = PHASE_HINT_TILT_GATES[tilt_mode]
            if gate_kind == "hint_excluding_already_stressed":
                gate_fires = (hint_val == 1) and (market_state not in {"stressed_panic", "recovery_fragile"})
            elif gate_kind == "refined_state_neutral_deteriorating":
                gate_fires = (ref_state == "neutral_deteriorating")
        if gate_fires:
            multiplier = 1.0 - PHASE_HINT_TILT_MAGNITUDES[tilt_mode]
            for name in offensive_sleeves:
                tilted.loc[name] *= multiplier
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # ======================================================================
    # Phase C tilt modes.
    # Uses the stronger Phase B sleeve universe and tests whether a bounded
    # sleeve-quality / allocation layer can deploy capital more intelligently
    # across sleeves without changing the top-level overlay architecture.
    # ======================================================================
    if tilt_mode in {
        "phasec_learned_quality",
        "phasec_dynamic_opportunity_budget",
        "phasec_state_map",
        "phasec_combo",
    }:
        favorable = _phasec_favorable_state(market_state, strong_neutral_flag)

        if favorable and conviction is not None and not conviction.empty:
            conviction_bound = 0.15
            if tilt_mode == "phasec_combo":
                conviction_bound = 0.12
            elif tilt_mode == "phasec_state_map":
                conviction_bound = 0.10
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + conviction_bound * c, 1.0 - conviction_bound, 1.0 + conviction_bound))
                tilted.loc[name] *= multiplier

        if favorable and tilt_mode in {"phasec_dynamic_opportunity_budget", "phasec_combo"} and conviction is not None and not conviction.empty:
            offensive_conv = conviction.reindex(offensive_sleeves).fillna(0.0)
            defensive_conv = conviction.reindex(defensive_sleeves).fillna(0.0)
            cluster_edge = float(
                np.clip(
                    offensive_conv.mean() - defensive_conv.mean() if not offensive_conv.empty else 0.0,
                    0.0,
                    1.0,
                )
            )
            if cluster_edge > 0.0:
                leader_names = list(offensive_conv.sort_values(ascending=False).head(2).index)
                for name in offensive_sleeves:
                    sleeve_bonus = 1.0 + 0.04 * cluster_edge
                    if name in leader_names:
                        sleeve_bonus += 0.04 * cluster_edge
                    tilted.loc[name] *= float(np.clip(sleeve_bonus, 0.96, 1.12))
                for name in defensive_sleeves:
                    tilted.loc[name] *= float(np.clip(1.0 - 0.08 * cluster_edge, 0.92, 1.04))

        if favorable and tilt_mode in {"phasec_state_map", "phasec_combo"}:
            if state_lead_tilt is not None and not state_lead_tilt.empty:
                lead_bound = 0.08 if tilt_mode == "phasec_combo" else 0.10
                for name in tilted.index:
                    s = float(state_lead_tilt.get(name, 0.0) or 0.0)
                    multiplier = float(np.clip(1.0 + lead_bound * s, 1.0 - lead_bound, 1.0 + lead_bound))
                    tilted.loc[name] *= multiplier
            tilted = _apply_phasec_state_map(
                tilted,
                market_state,
                strong_neutral_flag=strong_neutral_flag,
            )

        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # ======================================================================
    # Phase 3 tilt modes. All three reuse the dynamic_risk_budget base shape
    # (favorable-state conviction tilt + recovery_fragile / stressed_panic
    # protection) but swap the conviction signal and/or add a state-leader
    # layer. Bounds kept conservative (±15% per sleeve) to avoid compounding.
    # ======================================================================
    if tilt_mode in {
        "dynamic_risk_budget_confirmed_quality",
        "dynamic_risk_budget_state_leader",
        "dynamic_risk_budget_full_phase3",
    }:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        # Conviction stage (uses confirmed-quality conviction when caller
        # supplies it; otherwise falls back to whatever conviction was passed).
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier
        # State-leader stage: bounded ±10% tilt toward sleeves whose trailing
        # same-state Sharpe rank is top. Only applied when the mode asks for
        # it AND when a non-null lead series is supplied by the caller.
        if tilt_mode in {"dynamic_risk_budget_state_leader", "dynamic_risk_budget_full_phase3"}:
            if state_lead_tilt is not None and not state_lead_tilt.empty and favorable:
                for name in tilted.index:
                    s = float(state_lead_tilt.get(name, 0.0) or 0.0)
                    multiplier = float(np.clip(1.0 + 0.10 * s, 0.90, 1.10))
                    tilted.loc[name] *= multiplier
        # Shared state-level protection (same as dynamic_risk_budget).
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # ======================================================================
    # Phase 3.1 refinement modes.
    # These are narrow refinements of the Phase 3 C1 (state-leader) mechanism
    # and of the Phase 3 A1 (sector-rotation sleeve) hypothesis. They share
    # the same favorable-state gate and the same recovery_fragile /
    # stressed_panic protection as dynamic_risk_budget, and only change:
    #   - C1a:   state-leader bound widened from ±0.10 to ±0.15
    #   - C1b:   state-leader tilt fires only when |rank-tilt| > 0.30
    #            (conviction floor — middle-ranked sleeves don't move)
    #   - A1g:   sector_rotation_with_sma_filter gated to recovery states only
    #   - Combo: C1a bounds + A1g sector gate
    # ======================================================================
    if tilt_mode in {
        "dynamic_risk_budget_state_leader_wider",         # C1a
        "dynamic_risk_budget_state_leader_conviction_gated",  # C1b
        "dynamic_risk_budget_sector_gated",               # A1g
        "dynamic_risk_budget_state_leader_wider_sector_gated",  # Combo1
        "dynamic_risk_budget_state_leader_wider_sector_gated_tight",  # 3.2 R1
        "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",  # 3.2 R2
        "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",  # 3.2 R3
        "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",  # 3.4 T1
        "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",  # 3.4 T2
        "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",  # 3.4 T3
    }:
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        # Conviction stage — same rolling-Sharpe conviction signal as the
        # original dynamic_risk_budget, ±15% multiplier.
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
                tilted.loc[name] *= multiplier

        # State-leader stage — only for the two C1 refinement modes, the
        # combo, and the Phase 3.2 refinements (not for pure A1g).
        if tilt_mode in {
            "dynamic_risk_budget_state_leader_wider",
            "dynamic_risk_budget_state_leader_conviction_gated",
            "dynamic_risk_budget_state_leader_wider_sector_gated",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tight",
            "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
        }:
            if state_lead_tilt is not None and not state_lead_tilt.empty and favorable:
                # C1a widens the bound to ±0.15.
                # C1b keeps the ±0.10 bound but only fires on high-conviction
                # ranks (|tilt| > 0.30).
                if tilt_mode == "dynamic_risk_budget_state_leader_conviction_gated":
                    bound = 0.10
                    floor = 0.30
                else:
                    bound = 0.15
                    floor = 0.0
                # Phase 3.4 T2 / T3 — benchmark-DD tilt-magnitude dampener.
                # Shrinks the state-leader bound pre-emptively when the
                # benchmark is already deep in a drawdown. Scoped to the two
                # T2-family tilt modes; leaves Combo1 / T1 unchanged.
                if tilt_mode in {
                    "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
                    "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
                }:
                    bound *= _dd_gradient_tilt_dampener(market_state_row)
                for name in tilted.index:
                    s = float(state_lead_tilt.get(name, 0.0) or 0.0)
                    if abs(s) <= floor:
                        continue
                    multiplier = float(np.clip(1.0 + bound * s, 1.0 - bound, 1.0 + bound))
                    tilted.loc[name] *= multiplier

        # Shared state-level protection (same as dynamic_risk_budget).
        if market_state == "recovery_fragile":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.04
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05

        # A1g / combo sector gate — executed AFTER all tilts so that the gate
        # is the final word on sector exposure. Redistribution happens in
        # normalize_long_only below.
        #
        # Phase 3.1 modes use the default two-state gate
        # ({recovery_fragile, recovery_confirmed}). The Phase 3.2 R1 / R3
        # modes tighten it to {recovery_confirmed} only — the state where
        # the prior per-state Sharpe evidence was overwhelmingly strongest.
        if tilt_mode in {
            "dynamic_risk_budget_sector_gated",
            "dynamic_risk_budget_state_leader_wider_sector_gated",
            "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
        }:
            tilted = _apply_sector_state_gate(tilted, market_state)
        elif tilt_mode in {
            "dynamic_risk_budget_state_leader_wider_sector_gated_tight",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
        }:
            tilted = _apply_sector_state_gate(
                tilted,
                market_state,
                gate_states=frozenset({"recovery_confirmed"}),
            )

        # Phase 3.2 R2 / R3 drawdown-proximity guard on the sector sleeve.
        # Applied after the state gate so that within the favorable states
        # the sleeve can still be shrunk when the benchmark is already in a
        # material drawdown.
        if tilt_mode in {
            "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
        }:
            tilted = _apply_sector_dd_guard(tilted, market_state_row)

        # Phase 3.4 T1 / T3 recovery-fragile-only drawdown guard on the
        # sector sleeve. Narrower than the Phase 3.2 R2 guard (which applied
        # in every favorable state): this fires only when the market state
        # itself is `recovery_fragile`, the regime where benchmark DD depths
        # actually made the Phase 3.2 guard meaningful.
        if tilt_mode in {
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
        }:
            tilted = _apply_sector_fragile_dd_guard(tilted, market_state, market_state_row)

        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 1 Combo F: dynamic risk budget combined with good-state leadership
    # rotation. Applies the leadership rotation first (sleeve-mix level) and
    # then layers the conviction tilt on top, still bounded per-sleeve. Shared
    # stressed-panic protection.
    if tilt_mode == "dynamic_risk_budget_and_leadership":
        # --- Leadership stage (Variant E, bounded ±15%) ---
        if market_state == "calm_trend":
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.08
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.02
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.85
        elif market_state == "recovery_confirmed":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.95
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.88
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.88
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        elif market_state == "recovery_fragile":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.12
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.12
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.10
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.96
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.90
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        elif strong_neutral_flag:
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.10
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.08
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.04
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        # --- Conviction stage (Variant A, bounded ±10% inside combo) ---
        # Dampen the conviction modifier to ±10% since leadership is already
        # rotating the mix; avoid compounding into ±30% per sleeve.
        favorable = (
            market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"}
            or strong_neutral_flag
        )
        if favorable and conviction is not None and not conviction.empty:
            for name in tilted.index:
                c = float(conviction.get(name, 0.0) or 0.0)
                multiplier = float(np.clip(1.0 + 0.10 * c, 0.90, 1.10))
                tilted.loc[name] *= multiplier
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Phase 1 Variant E: good-state sleeve leadership (bounded ±15%).
    # Lean toward sleeves that lead in each favorable state and lighten the
    # chronic laggards, leaving gross-risk alone.
    if tilt_mode == "phase1_leadership":
        if market_state == "calm_trend":
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.08
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.02
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.85
        elif market_state == "recovery_confirmed":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.95
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.88
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.88
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        elif market_state == "recovery_fragile":
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.12
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.12
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.10
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.96
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.90
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
        elif market_state == "stressed_panic":
            for name in offensive_sleeves:
                tilted.loc[name] *= 0.92
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.05
        elif strong_neutral_flag:
            # Strong-neutral: boost the trend trio moderately, soft fade
            # composite_regime_conditioned.
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.10
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.08
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.08
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.04
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
        else:
            # Plain neutral_mixed, no signal: pass through unchanged.
            pass
        return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])

    # Backward compatibility: legacy "modest" tilt on the aggregated recovery state.
    if market_state == "recovery_rebound":
        for name in offensive_sleeves:
            tilted.loc[name] *= 1.12
        for name in defensive_sleeves:
            tilted.loc[name] *= 0.90
    elif market_state == "recovery_fragile":
        if tilt_mode == "fragile_first":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.12
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.92
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.10
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus_mix_rotation":
            # Variant D (fragile leg). Like fragile_plus but leans harder toward the
            # trend-following trio observed to score best in recovery_fragile weeks
            # (cta_trend and dual_momentum by sleeve-by-state Sharpe).
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.15
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.15
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.12
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.06
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.06
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.88
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        # Fragile: modest re-risk only. Never lean hard into an unconfirmed bounce.
        if tilt_mode in {"modest", "split_modest", "split_aggressive"}:
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.06
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.96
    elif market_state == "recovery_confirmed":
        if tilt_mode == "fragile_first":
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.08
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.94
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode in {"confirmed_leadership", "calm_confirmed_leadership", "calm_confirmed_fragile_leadership"}:
            # Recovery-confirmed is not an argument for "more offense everywhere";
            # it is an argument for better sleeve leadership. The sleeve-by-state
            # table shows CTA trend and TAA leading here, while selective and the
            # regime sleeve lag materially, so rotate the mix instead of loosening
            # the gross risk budget.
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.20
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.20
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 0.94
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 0.82
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 0.82
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.86
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode in {"modest", "split_modest", "fragile_plus", "fragile_plus_mix_rotation"}:
            # Treat confirmed like the legacy "modest" tilt. Do not revive a stronger
            # confirmed-offense ladder in the mix-rotation variant; the rotation is
            # concentrated in fragile + calm only.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.12
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.90
        elif tilt_mode == "split_aggressive":
            # Aggressive offense only when breadth/trend/momentum/drawdown all confirm.
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.22
            for name in defensive_sleeves:
                tilted.loc[name] *= 0.82
    elif market_state == "calm_trend":
        if tilt_mode in {"calm_confirmed_leadership", "calm_confirmed_fragile_leadership"}:
            # Calm-trend still undercaptures badly despite very little overlay cash.
            # That points to sleeve mix quality, not gross deployment. Favor the
            # sleeves that hold up best in calm conditions (TAA and selective),
            # keep dual roughly neutral, and reduce the regime-conditioned sleeve.
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 1.14
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.10
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.10
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.02
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 0.98
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 0.98
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.84
            return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        if tilt_mode == "fragile_plus_mix_rotation":
            # Variant D (calm leg). Rotate away from composite_regime_conditioned
            # (lowest sleeve Sharpe in calm weeks) and toward the trend-following
            # trio. Keep taa_10m_sma roughly neutral so the rotation is about mix
            # quality, not simply adding more defense.
            if "dual_momentum_topn" in tilted.index:
                tilted.loc["dual_momentum_topn"] *= 1.14
            if "cta_trend_long_only" in tilted.index:
                tilted.loc["cta_trend_long_only"] *= 1.14
            if "cta_trend_vol_managed" in tilted.index:
                tilted.loc["cta_trend_vol_managed"] *= 1.14
            if "composite_selective_signals" in tilted.index:
                tilted.loc["composite_selective_signals"] *= 1.12
            if "composite_selective_trend_ensemble" in tilted.index:
                tilted.loc["composite_selective_trend_ensemble"] *= 1.12
            if "composite_selective_concentrated" in tilted.index:
                tilted.loc["composite_selective_concentrated"] *= 1.10
            if "composite_equal_weight" in tilted.index:
                tilted.loc["composite_equal_weight"] *= 1.05
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.80
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.98
        else:
            for name in offensive_sleeves:
                tilted.loc[name] *= 1.08
            if "composite_regime_conditioned" in tilted.index:
                tilted.loc["composite_regime_conditioned"] *= 0.94
            if "taa_10m_sma" in tilted.index:
                tilted.loc["taa_10m_sma"] *= 0.96
    elif market_state == "stressed_panic":
        for name in offensive_sleeves:
            tilted.loc[name] *= 0.92
        if "composite_regime_conditioned" in tilted.index:
            tilted.loc["composite_regime_conditioned"] *= 1.08
        if "taa_10m_sma" in tilted.index:
            tilted.loc["taa_10m_sma"] *= 1.05
    if market_state == "recovery_fragile" and tilt_mode == "calm_confirmed_fragile_leadership":
        # Recovery-fragile is still a rerisk handoff, but CTA and dual momentum
        # are the leaders here. Make the existing fragile tilt more selective by
        # pulling weight away from the weaker regime/selection sleeves.
        if "cta_trend_long_only" in tilted.index:
            tilted.loc["cta_trend_long_only"] *= 1.16
        if "cta_trend_vol_managed" in tilted.index:
            tilted.loc["cta_trend_vol_managed"] *= 1.16
        if "dual_momentum_topn" in tilted.index:
            tilted.loc["dual_momentum_topn"] *= 1.10
        if "composite_selective_signals" in tilted.index:
            tilted.loc["composite_selective_signals"] *= 0.94
        if "composite_selective_trend_ensemble" in tilted.index:
            tilted.loc["composite_selective_trend_ensemble"] *= 0.94
        if "composite_regime_conditioned" in tilted.index:
            tilted.loc["composite_regime_conditioned"] *= 0.88
        if "taa_10m_sma" in tilted.index:
            tilted.loc["taa_10m_sma"] *= 0.98
    return ns5["normalize_long_only"](tilted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])


def is_strong_neutral_state_row(market_state_row: pd.Series | None) -> bool:
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return False
    market_state = str(market_state_row.get("market_state") or "")
    market_trend_positive = float(market_state_row.get("market_trend_positive") or 0.0)
    breadth_sma_43 = float(market_state_row.get("breadth_sma_43") or 0.0)
    breadth_26w_mom = float(market_state_row.get("breadth_26w_mom") or 0.0)
    return (
        market_state == "neutral_mixed"
        and market_trend_positive > 0.0
        and breadth_sma_43 >= 0.55
        and breadth_26w_mom >= 0.50
    )


def apply_layer3_expression(
    raw_weights: pd.Series,
    market_state_row: pd.Series | None,
    conviction_row: pd.Series | None,
    *,
    expression_mode: str = "none",
) -> tuple[pd.Series, dict]:
    normalized = ns5["normalize_long_only"](pd.Series(raw_weights, dtype=float), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    diagnostics = {
        "layer3_expression_shift": 0.0,
        "layer3_expression_triggered": 0.0,
        "layer3_expression_mode": expression_mode,
    }
    if expression_mode == "none" or market_state_row is None or market_state_row.empty:
        return normalized, diagnostics

    market_state = str(market_state_row.get("market_state") or "")
    strong_neutral = is_strong_neutral_state_row(market_state_row)
    shift_budget = 0.0
    if expression_mode == "good_state_conviction_relax":
        if market_state == "calm_trend":
            shift_budget = 0.06
        elif strong_neutral:
            shift_budget = 0.05
        elif market_state == "recovery_fragile":
            shift_budget = 0.04
    # Phase 7: more aggressive expression in calm and confirmed-good states
    elif expression_mode == "phase7_aggressive_expression":
        if market_state == "calm_trend":
            shift_budget = 0.12
        elif strong_neutral:
            shift_budget = 0.09
        elif market_state in ("recovery_confirmed", "recovery_fragile"):
            shift_budget = 0.06
    if shift_budget <= 0.0:
        return normalized, diagnostics

    offensive_sleeves = [
        name
        for name in [
            "dual_momentum_topn",
            "cta_trend_long_only",
            "cta_trend_vol_managed",
            "composite_selective_signals",
            "composite_selective_trend_ensemble",
            "composite_selective_strength_weighted",
            "composite_selective_concentrated",
            "composite_equal_weight",
        ]
        if name in normalized.index
    ]
    defensive_sleeves = [name for name in ["composite_regime_conditioned", "taa_10m_sma"] if name in normalized.index]
    if not offensive_sleeves or not defensive_sleeves:
        return normalized, diagnostics

    defensive_budget = float(normalized.reindex(defensive_sleeves).sum())
    shift = min(shift_budget, defensive_budget * 0.35)
    if shift <= 1e-12:
        return normalized, diagnostics

    conviction = pd.Series(dtype=float) if conviction_row is None else pd.Series(conviction_row, dtype=float)
    conviction = conviction.reindex(offensive_sleeves).replace([np.inf, -np.inf], np.nan)
    if conviction.notna().any():
        conviction = conviction.fillna(float(conviction.median()))
    else:
        conviction = pd.Series(0.0, index=offensive_sleeves, dtype=float)
    strength = conviction.sub(float(conviction.min())).clip(lower=0.0)
    if float(strength.sum()) <= 1e-12:
        current_offense = normalized.reindex(offensive_sleeves).clip(lower=0.0)
        strength = current_offense if float(current_offense.sum()) > 1e-12 else pd.Series(1.0, index=offensive_sleeves, dtype=float)
    strength = strength / strength.sum()

    adjusted = normalized.copy()
    defensive_weights = adjusted.reindex(defensive_sleeves).fillna(0.0)
    adjusted.loc[defensive_sleeves] = (defensive_weights - shift * defensive_weights / defensive_weights.sum()).clip(lower=0.0)
    adjusted.loc[offensive_sleeves] = adjusted.reindex(offensive_sleeves).fillna(0.0) + shift * strength
    adjusted = ns5["normalize_long_only"](adjusted, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    diagnostics["layer3_expression_shift"] = shift
    diagnostics["layer3_expression_triggered"] = 1.0
    return adjusted, diagnostics


def apply_beta_participation_overlay(
    etf_weights: pd.Series,
    market_state_row: pd.Series | None,
    *,
    beta_overlay_mode: str = "none",
) -> tuple[pd.Series, dict]:
    adjusted = pd.Series(etf_weights, dtype=float).copy()
    overlay_contribution = {"SPY": 0.0, ns5["cash_proxy"]: 0.0}
    if beta_overlay_mode == "none" or market_state_row is None or market_state_row.empty:
        return adjusted, overlay_contribution

    market_state = str(market_state_row.get("market_state") or "")
    strong_neutral = is_strong_neutral_state_row(market_state_row)

    desired_shift = 0.0
    if beta_overlay_mode == "good_state_spy":
        if market_state == "calm_trend":
            desired_shift = 0.06
        elif market_state == "recovery_fragile":
            desired_shift = 0.05
        elif strong_neutral:
            desired_shift = 0.04
    elif beta_overlay_mode == "good_state_spy_light":
        if market_state == "calm_trend":
            desired_shift = 0.04
        elif market_state == "recovery_fragile":
            desired_shift = 0.03
        elif strong_neutral:
            desired_shift = 0.025

    if desired_shift <= 0.0:
        return adjusted, overlay_contribution

    bil_ticker = ns5["cash_proxy"]
    current_bil = float(adjusted.get(bil_ticker, 0.0) or 0.0)
    current_spy = float(adjusted.get("SPY", 0.0) or 0.0)
    shift = min(current_bil, desired_shift, max(0.0, 0.18 - current_spy))
    if shift <= 0.0:
        return adjusted, overlay_contribution

    adjusted.loc[bil_ticker] = current_bil - shift
    adjusted.loc["SPY"] = current_spy + shift
    overlay_contribution[bil_ticker] = -shift
    overlay_contribution["SPY"] = shift
    return adjusted, overlay_contribution


def apply_overlays_custom(
    raw_weights: pd.Series,
    cov: pd.DataFrame,
    regime_row: pd.Series,
    *,
    prev_weights: pd.Series | None = None,
    target_vol_ceil: float = ns5["TARGET_VOL_CEIL"],
    sleeve_reallocation_speed: float = ns5["SLEEVE_REALLOCATION_SPEED"],
    rerisk_speed: float | None = None,
    market_state: str | None = None,
    market_state_row: pd.Series | None = None,
    prev_regime_multiplier: float | None = None,
    overlay_penalty_mode: str = "none",
    speed_mode: str = "default",
    improving_speed: float | None = None,
    deteriorating_speed: float | None = None,
    phase2b_mode: str = "none",
    ml_pred_row: pd.Series | None = None,
) -> tuple[pd.Series, float, dict]:
    raw_weights = ns5["normalize_long_only"](raw_weights, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    raw_regime_multiplier = float(regime_row.get("overlay_multiplier", 1.0)) if isinstance(regime_row, pd.Series) else 1.0
    # Phase 2B: apply interpretable-ML meta adjustment BEFORE self/non-self-
    # gated relief is computed. Orthogonal to overlay_penalty_mode — the
    # overlay still sees a "regime_multiplier" to act on, just one that has
    # been nudged by the ML. Default mode="none" is a no-op.
    regime_multiplier, phase2b_diag = apply_phase2b_adjustment(
        raw_regime_multiplier,
        market_state,
        ml_pred_row,
        mode=phase2b_mode,
        market_state_row=market_state_row if isinstance(market_state_row, pd.Series) else None,
    )
    # ------------------------------------------------------------------
    # Phase HH1 — refined-state additive confidence adjustment.
    # Adds a small bounded offset (±0.02) to regime_multiplier based on
    # Phase CC's refined_state. Causal: refined_state was computed
    # walk-forward from past data in Phase CC. No portfolio weights are
    # touched directly; only the existing regime confidence score is
    # nudged.
    # ------------------------------------------------------------------
    if phase2b_mode == "regime_confidence_boost_refined_v1":
        date_key = (
            market_state_row.name
            if isinstance(market_state_row, pd.Series) and market_state_row is not None
            else None
        )
        if date_key is not None:
            ref_state = str(PHASEFF_REFINED_STATE_LOOKUP.get(date_key, ""))
            refined_offset = 0.0
            if ref_state == "neutral_healthy":
                refined_offset = 0.02
            elif ref_state == "neutral_deteriorating":
                refined_offset = -0.02
            elif ref_state == "recovery_confirmed":
                refined_offset = 0.01
            if refined_offset != 0.0:
                pre = regime_multiplier
                regime_multiplier = float(np.clip(regime_multiplier + refined_offset, 0.0, 1.0))
                phase2b_diag = dict(phase2b_diag) if isinstance(phase2b_diag, dict) else {}
                phase2b_diag["phasehh_refined_offset"] = float(regime_multiplier - pre)
    strong_neutral = is_strong_neutral_state_row(market_state_row)
    # ------------------------------------------------------------------
    # Phase II — return-participation upgrade using ONLY existing
    # non-Phase-CC features (market_state, breadth_sma_43, breadth_26w_mom,
    # market_trend_positive, plus the existing strong_neutral helper).
    # Adds a small bounded +0.015 to regime_multiplier in clearly favorable
    # weeks. Never fires in stressed_panic, recovery_fragile, or weeks
    # without breadth/trend support.
    #   II1 ('regime_confidence_boost_participation_v1'):
    #     calm_trend OR strong_neutral, breadth_sma_43 >= 0.65,
    #     breadth_26w_mom >= 0.50, market_trend_positive > 0
    #   II2 ('regime_confidence_boost_participation_v2'):
    #     recovery_confirmed AND breadth_sma_43 >= 0.55 AND
    #     breadth_26w_mom >= 0.50
    # ------------------------------------------------------------------
    if phase2b_mode in {"regime_confidence_boost_participation_v1",
                         "regime_confidence_boost_participation_v2"}:
        if isinstance(market_state_row, pd.Series) and not market_state_row.empty:
            try:
                b43 = float(market_state_row.get("breadth_sma_43") or 0.0)
            except (TypeError, ValueError):
                b43 = 0.0
            try:
                b26 = float(market_state_row.get("breadth_26w_mom") or 0.0)
            except (TypeError, ValueError):
                b26 = 0.0
            try:
                mtp = float(market_state_row.get("market_trend_positive") or 0.0)
            except (TypeError, ValueError):
                mtp = 0.0
            participation_offset = 0.0
            never_fire = market_state in {"stressed_panic", "recovery_fragile"}
            if not never_fire:
                if phase2b_mode == "regime_confidence_boost_participation_v1":
                    eligible_state = (market_state == "calm_trend") or strong_neutral
                    if eligible_state and b43 >= 0.65 and b26 >= 0.50 and mtp > 0:
                        participation_offset = 0.015
                elif phase2b_mode == "regime_confidence_boost_participation_v2":
                    if market_state == "recovery_confirmed" and b43 >= 0.55 and b26 >= 0.50:
                        participation_offset = 0.015
            if participation_offset != 0.0:
                pre = regime_multiplier
                regime_multiplier = float(np.clip(regime_multiplier + participation_offset, 0.0, 1.0))
                phase2b_diag = dict(phase2b_diag) if isinstance(phase2b_diag, dict) else {}
                phase2b_diag["phaseii_participation_offset"] = float(regime_multiplier - pre)
    dynamic_speed = sleeve_reallocation_speed
    if rerisk_speed is not None:
        if market_state in {"recovery_rebound", "recovery_confirmed", "calm_trend"}:
            dynamic_speed = rerisk_speed
        elif market_state == "recovery_fragile":
            # Partial re-risk during fragile recovery: halfway between baseline speed and rerisk_speed.
            dynamic_speed = sleeve_reallocation_speed + 0.5 * (rerisk_speed - sleeve_reallocation_speed)
    if speed_mode == "asymmetric_reallocation":
        improving = (
            strong_neutral
            or market_state in {"calm_trend", "recovery_fragile", "recovery_confirmed"}
            or (prev_regime_multiplier is not None and regime_multiplier >= prev_regime_multiplier + 0.02)
        )
        deteriorating = (
            market_state == "stressed_panic"
            or (prev_regime_multiplier is not None and regime_multiplier <= prev_regime_multiplier - 0.02)
        )
        if improving:
            dynamic_speed = max(dynamic_speed, improving_speed if improving_speed is not None else 0.75)
        if deteriorating:
            dynamic_speed = min(dynamic_speed, deteriorating_speed if deteriorating_speed is not None else sleeve_reallocation_speed)
    # ------------------------------------------------------------------
    # Phase HH2 — refined-state gated confidence smoothing.
    # Slows re-risking by 15% on neutral_deteriorating weeks; does not
    # touch dynamic_speed in neutral_healthy / calm / recovery_confirmed
    # so participation is not eroded. No new hard threshold; reuses the
    # existing dynamic_speed mechanism.
    # ------------------------------------------------------------------
    if phase2b_mode == "regime_confidence_boost_refined_v2":
        date_key = (
            market_state_row.name
            if isinstance(market_state_row, pd.Series) and market_state_row is not None
            else None
        )
        if date_key is not None:
            ref_state = str(PHASEFF_REFINED_STATE_LOOKUP.get(date_key, ""))
            if ref_state == "neutral_deteriorating":
                dynamic_speed = float(dynamic_speed) * 0.85
    if prev_weights is not None and not prev_weights.empty:
        prev_weights = ns5["normalize_long_only"](prev_weights.reindex(raw_weights.index).fillna(0.0), max_weight=ns5["MAX_SLEEVE_WEIGHT"])
        blended = (1.0 - dynamic_speed) * prev_weights + dynamic_speed * raw_weights
    else:
        blended = raw_weights.copy()
    blended = ns5["normalize_long_only"](blended, max_weight=ns5["MAX_SLEEVE_WEIGHT"])
    predicted_ann_vol = np.sqrt(max(float(blended.values @ cov.values @ blended.values), 0.0)) * np.sqrt(ns5["WEEKS_PER_YEAR"])
    target_vol_multiplier = (
        1.0
        if predicted_ann_vol <= 0 or pd.isna(predicted_ann_vol)
        else float(np.clip(ns5["TARGET_VOL_ANN"] / predicted_ann_vol, ns5["TARGET_VOL_FLOOR"], target_vol_ceil))
    )
    regime_binding = float(regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999)
    target_vol_binding = float(target_vol_multiplier < regime_multiplier and target_vol_multiplier < 0.999)
    both_binding = float(abs(regime_multiplier - target_vol_multiplier) <= 1e-6 and regime_multiplier < 0.999)

    per_sleeve_multiplier = pd.Series(float(min(1.0, regime_multiplier, target_vol_multiplier)), index=blended.index, dtype=float)
    self_gated_relief = 0.0
    non_self_gated_relief = 0.0
    self_gated_regime_multiplier = regime_multiplier
    non_self_gated_regime_multiplier = regime_multiplier
    final_self_gated_multiplier = float(per_sleeve_multiplier.iloc[0]) if not per_sleeve_multiplier.empty else np.nan
    final_non_self_gated_multiplier = float(per_sleeve_multiplier.iloc[0]) if not per_sleeve_multiplier.empty else np.nan
    apply_self_gated_relief = False
    apply_non_self_gated_relief = False
    # self-gated relief shape
    relief_cap = 0.06
    relief_scale = 0.50
    # non-self-gated relief shape (only used when apply_non_self_gated_relief is True)
    ns_relief_cap = 0.025
    ns_relief_scale = 0.20
    ns_relief_flat: float | None = None
    if (
        overlay_penalty_mode == "lighter_self_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
    ):
        apply_self_gated_relief = True
    elif (
        overlay_penalty_mode == "lighter_self_gated_targeted"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
    elif (
        # Variant A: narrower targeted follow-up. Keeps the self-gated relief
        # line intact in {strong_neutral, recovery_fragile, recovery_confirmed}
        # and ADDS a smaller, scale-bounded relief to non-self-gated sleeves in
        # {strong_neutral, recovery_fragile} ONLY. recovery_confirmed is
        # intentionally excluded for non-self-gated sleeves to respect the
        # prior rule "do not revive confirmed-recovery aggression".
        overlay_penalty_mode == "lighter_both_targeted_narrow"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
    elif (
        # Variant B: flat-form non-self-gated relief. Same self-gated behavior,
        # but the non-self-gated relief is a fixed 0.02 nudge instead of being
        # scaled by (1 - regime_multiplier). Tests whether the signal is the
        # proportional-to-binding shape or a small fixed release.
        overlay_penalty_mode == "lighter_both_targeted_flat"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_flat = 0.02
    elif (
        # Variant C: extends the narrow scale-bounded non-self-gated relief
        # from Variant A to also include recovery_confirmed, but at a tighter
        # cap (0.015 vs 0.025) so it does not count as "confirmed-recovery
        # aggression". All other states behave exactly like Variant A. Self-
        # gated relief is unchanged. Stressed-panic protection unchanged.
        overlay_penalty_mode == "lighter_both_targeted_narrow_plus_confirmed"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Phase MM1: narrow recovery-fragile-only cash relief.
        # Same structure as the incumbent narrow_plus_confirmed overlay except
        # recovery_fragile gets a slightly wider release on both self-gated
        # and non-self-gated sleeves. strong_neutral / recovery_confirmed keep
        # the incumbent settings, and stressed_panic remains untouched.
        overlay_penalty_mode == "phasemm_recovery_cash_relief"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if market_state == "recovery_fragile":
            relief_cap = 0.05
            relief_scale = 0.40
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.035
            ns_relief_scale = 0.24
            ns_relief_flat = None
        elif strong_neutral:
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Phase MM2: relax good-state overlay drag only in calm_trend and
        # strong_neutral weeks. recovery_fragile / stressed_panic remain at
        # the incumbent settings so this is a clean good-state participation
        # test rather than a broad rerisk change.
        overlay_penalty_mode == "phasemm_good_state_overlay_relief"
        and regime_binding > 0.0
        and (market_state == "calm_trend" or strong_neutral)
    ):
        apply_self_gated_relief = True
        relief_cap = 0.045
        relief_scale = 0.38
        apply_non_self_gated_relief = True
        ns_relief_cap = 0.030
        ns_relief_scale = 0.22
        ns_relief_flat = None
    elif (
        # Sprint Variant A: `lighter_both_wider_cap`. Same structure as the
        # narrow_plus_confirmed incumbent except the non-self-gated relief is
        # widened ONLY in strong_neutral and recovery_fragile (cap 0.045,
        # scale 0.28 vs incumbent 0.025 / 0.20). recovery_confirmed remains at
        # the incumbent tight values (0.015 / 0.15). Self-gated relief line
        # is unchanged. Stressed-panic protection is unchanged. This attacks
        # the cap-driven deployment bottleneck in the two good-but-not-
        # confirmed states without reviving confirmed-recovery aggression.
        overlay_penalty_mode == "lighter_both_wider_cap"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.045
            ns_relief_scale = 0.28
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Sprint Variant B: `lighter_both_wider_cap_persistence_gated`. Same as
        # Variant A but the widened cap in strong_neutral / recovery_fragile
        # only engages when the Layer 2B causal regime engine's
        # transition_non_stress_prob is high (>= 0.92). When the persistence
        # signal is weaker, the relief falls back to the incumbent narrow
        # values (0.025 / 0.20). This tests whether conditioning deployment
        # on the regime engine's own stay-out-of-stress confidence sharpens
        # the release to the "safest" fraction of those weeks and leaves the
        # tail-prone fraction defended.
        overlay_penalty_mode == "lighter_both_wider_cap_persistence_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            persistence_score = 0.0
            if isinstance(market_state_row, pd.Series):
                raw_persistence = market_state_row.get("transition_non_stress_prob", 0.0)
                try:
                    persistence_score = float(raw_persistence) if raw_persistence is not None and not pd.isna(raw_persistence) else 0.0
                except (TypeError, ValueError):
                    persistence_score = 0.0
            apply_non_self_gated_relief = True
            if persistence_score >= 0.92:
                ns_relief_cap = 0.045
                ns_relief_scale = 0.28
            else:
                ns_relief_cap = 0.025
                ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        # Phase 1 Variant B: continuous causal-confidence map. Non-self-gated
        # relief cap and scale are a linear function of the Layer 2B causal
        # confidence score (persistence + breadth + trend + shallow DD). At
        # confidence=0 the relief is tighter than incumbent (0.015 / 0.15);
        # at confidence=1 it is modestly wider than incumbent in the two
        # good-but-unconfirmed states (0.045 / 0.32). recovery_confirmed is
        # kept tighter overall so the "no confirmed-recovery aggression"
        # rule is preserved. Self-gated relief and stressed-panic
        # protection are unchanged.
        overlay_penalty_mode == "lighter_both_continuous_confidence_map"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        confidence_score = compute_causal_confidence(market_state_row if isinstance(market_state_row, pd.Series) else None)
        apply_non_self_gated_relief = True
        if strong_neutral or market_state == "recovery_fragile":
            ns_relief_cap = 0.015 + confidence_score * (0.045 - 0.015)
            ns_relief_scale = 0.15 + confidence_score * (0.32 - 0.15)
        elif market_state == "recovery_confirmed":
            ns_relief_cap = 0.010 + confidence_score * (0.025 - 0.010)
            ns_relief_scale = 0.10 + confidence_score * (0.20 - 0.10)
        ns_relief_flat = None
    elif (
        # Phase 1 Variant C: confidence-gated relief. Multiplicative gate
        # on the incumbent narrow values. High confidence pushes the cap
        # up to 0.045 / 0.30; low confidence stays near incumbent 0.025 /
        # 0.20. Same state set and protections as Variant B.
        overlay_penalty_mode == "lighter_both_confidence_gated"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        confidence_score = compute_causal_confidence(market_state_row if isinstance(market_state_row, pd.Series) else None)
        apply_non_self_gated_relief = True
        if strong_neutral or market_state == "recovery_fragile":
            ns_relief_cap = 0.025 + confidence_score * 0.020
            ns_relief_scale = 0.20 + confidence_score * 0.10
        elif market_state == "recovery_confirmed":
            ns_relief_cap = 0.015 + confidence_score * 0.010
            ns_relief_scale = 0.15 + confidence_score * 0.05
        ns_relief_flat = None
    elif (
        # Phase 2A Variant B: principled bounded continuous state-conditioned
        # mapping. Same base state set and incumbent tight values as
        # lighter_both_targeted_narrow_plus_confirmed. A linear confidence
        # lift activates ONLY when causal_confidence >= 0.55 (gate), and is
        # bounded at 1.40x of incumbent at confidence=1.0. Below the gate,
        # behaviour is IDENTICAL to the CONTROL overlay (no loosening in
        # low-conviction regimes). recovery_confirmed stays tighter than
        # fragile/strong_neutral so the "no confirmed-recovery aggression"
        # rule is preserved. Stressed-panic and neutral (non-strong) are
        # unchanged. Tighter than the too-loose Phase 1 continuous map and
        # adds a confidence gate the Phase 1 version lacked.
        overlay_penalty_mode == "phase2a_principled_continuous"
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"})
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        confidence_score = compute_causal_confidence(market_state_row if isinstance(market_state_row, pd.Series) else None)
        confidence_gate = 0.55
        if confidence_score >= confidence_gate:
            lift = 1.0 + 0.40 * (confidence_score - confidence_gate) / max(1e-9, 1.0 - confidence_gate)
        else:
            lift = 1.0
        lift = float(min(max(lift, 1.0), 1.40))
        apply_non_self_gated_relief = True
        if strong_neutral or market_state == "recovery_fragile":
            ns_relief_cap = 0.025 * lift
            ns_relief_scale = 0.20 * lift
        elif market_state == "recovery_confirmed":
            ns_relief_cap = 0.015 * lift
            ns_relief_scale = 0.15 * lift
        ns_relief_flat = None
    elif (
        overlay_penalty_mode in {
            "phasett_recovery_two_stage_bucket",
            "phasett_recovery_neutral_two_stage_bucket",
            "phasett_ss1_overlay_coordinated",
        }
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (
            market_state in {"recovery_fragile", "recovery_confirmed"}
            or (overlay_penalty_mode == "phasett_recovery_neutral_two_stage_bucket" and strong_neutral)
        )
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
            ns_relief_flat = None
        elif market_state == "recovery_confirmed":
            apply_non_self_gated_relief = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
            ns_relief_flat = None
    elif (
        overlay_penalty_mode in {
            "phaseuu_tt1_overlay_preserved_recovery",
            "phaseuu_recovery_overlay_cash_cap",
            "phaseuu_tt1_budget_aware_lighter_both",
            "phasevv_recovery_budget_aware_overlay",
            "phasevv_recovery_overlay_tolerance_band",
            "phasevv_recovery_neutral_budget_aware_overlay",
            "phaseww_recovery_budget_native_lighter_both",
            "phaseww_split_recovery_lighter_both",
            "phaseww_vv_direct_lighter_both_rewrite",
            "phaseww_confirmed_only_lighter_both",
            "phaseww_fragile_defense_lighter_both",
            "phaseww_vv_shadow_polish",
            "phasexx_guardrail_only_overlay",
            "phasexx_guardrail_overlay_fragile_floor",
            "phasexx_recovery_neutral_overlay_simplified",
            "phasexx_conservative_hybrid_overlay",
        }
        and regime_binding > 0.0
        and market_state != "stressed_panic"
        and (
            market_state in {"recovery_fragile", "recovery_confirmed"}
            or (
                overlay_penalty_mode in {
                    "phasevv_recovery_neutral_budget_aware_overlay",
                    "phaseww_vv_direct_lighter_both_rewrite",
                    "phaseww_vv_shadow_polish",
                    "phasexx_recovery_neutral_overlay_simplified",
                    "phasexx_conservative_hybrid_overlay",
                }
                and strong_neutral
            )
        )
    ):
        apply_self_gated_relief = True
        relief_cap = 0.04
        relief_scale = 0.35
        apply_non_self_gated_relief = True
        if overlay_penalty_mode == "phaseuu_tt1_overlay_preserved_recovery":
            if market_state == "recovery_fragile":
                relief_cap = 0.045
                relief_scale = 0.38
                ns_relief_cap = 0.030
                ns_relief_scale = 0.22
            else:
                ns_relief_cap = 0.020
                ns_relief_scale = 0.18
        elif overlay_penalty_mode == "phaseuu_recovery_overlay_cash_cap":
            if market_state == "recovery_fragile":
                ns_relief_cap = 0.026
                ns_relief_scale = 0.20
            else:
                ns_relief_cap = 0.017
                ns_relief_scale = 0.15
        elif overlay_penalty_mode == "phaseuu_tt1_budget_aware_lighter_both":
            if market_state == "recovery_fragile":
                relief_cap = 0.047
                relief_scale = 0.40
                ns_relief_cap = 0.032
                ns_relief_scale = 0.24
            else:
                relief_cap = 0.045
                relief_scale = 0.38
                ns_relief_cap = 0.022
                ns_relief_scale = 0.19
        elif overlay_penalty_mode == "phasevv_recovery_budget_aware_overlay":
            if market_state == "recovery_fragile":
                relief_cap = 0.040
                relief_scale = 0.35
                ns_relief_cap = 0.020
                ns_relief_scale = 0.16
            else:
                relief_cap = 0.038
                relief_scale = 0.33
                ns_relief_cap = 0.016
                ns_relief_scale = 0.13
        elif overlay_penalty_mode == "phasevv_recovery_overlay_tolerance_band":
            if market_state == "recovery_fragile":
                relief_cap = 0.041
                relief_scale = 0.35
                ns_relief_cap = 0.022
                ns_relief_scale = 0.17
            else:
                relief_cap = 0.039
                relief_scale = 0.33
                ns_relief_cap = 0.018
                ns_relief_scale = 0.14
        elif overlay_penalty_mode == "phasevv_recovery_neutral_budget_aware_overlay":
            if strong_neutral:
                relief_cap = 0.032
                relief_scale = 0.26
                ns_relief_cap = 0.012
                ns_relief_scale = 0.10
            elif market_state == "recovery_fragile":
                relief_cap = 0.040
                relief_scale = 0.35
                ns_relief_cap = 0.020
                ns_relief_scale = 0.16
            else:
                relief_cap = 0.038
                relief_scale = 0.33
                ns_relief_cap = 0.016
                ns_relief_scale = 0.13
        elif overlay_penalty_mode == "phaseww_recovery_budget_native_lighter_both":
            if market_state == "recovery_fragile":
                relief_cap = 0.052
                relief_scale = 0.43
                ns_relief_cap = 0.026
                ns_relief_scale = 0.18
            else:
                relief_cap = 0.050
                relief_scale = 0.41
                ns_relief_cap = 0.020
                ns_relief_scale = 0.15
        elif overlay_penalty_mode == "phaseww_split_recovery_lighter_both":
            if market_state == "recovery_fragile":
                relief_cap = 0.048
                relief_scale = 0.39
                ns_relief_cap = 0.021
                ns_relief_scale = 0.15
            else:
                relief_cap = 0.054
                relief_scale = 0.45
                ns_relief_cap = 0.024
                ns_relief_scale = 0.18
        elif overlay_penalty_mode == "phaseww_vv_direct_lighter_both_rewrite":
            if strong_neutral:
                relief_cap = 0.036
                relief_scale = 0.28
                ns_relief_cap = 0.014
                ns_relief_scale = 0.11
            elif market_state == "recovery_fragile":
                relief_cap = 0.052
                relief_scale = 0.42
                ns_relief_cap = 0.025
                ns_relief_scale = 0.17
            else:
                relief_cap = 0.050
                relief_scale = 0.40
                ns_relief_cap = 0.020
                ns_relief_scale = 0.15
        elif overlay_penalty_mode == "phaseww_confirmed_only_lighter_both":
            relief_cap = 0.055
            relief_scale = 0.46
            ns_relief_cap = 0.026
            ns_relief_scale = 0.19
        elif overlay_penalty_mode == "phaseww_fragile_defense_lighter_both":
            if market_state == "recovery_fragile":
                relief_cap = 0.047
                relief_scale = 0.38
                ns_relief_cap = 0.019
                ns_relief_scale = 0.14
            else:
                relief_cap = 0.052
                relief_scale = 0.42
                ns_relief_cap = 0.022
                ns_relief_scale = 0.16
        elif overlay_penalty_mode == "phaseww_vv_shadow_polish":
            if strong_neutral:
                relief_cap = 0.035
                relief_scale = 0.27
                ns_relief_cap = 0.013
                ns_relief_scale = 0.10
            elif market_state == "recovery_fragile":
                relief_cap = 0.050
                relief_scale = 0.40
                ns_relief_cap = 0.022
                ns_relief_scale = 0.15
            else:
                relief_cap = 0.051
                relief_scale = 0.42
                ns_relief_cap = 0.021
                ns_relief_scale = 0.15
        elif overlay_penalty_mode == "phasexx_guardrail_only_overlay":
            if market_state == "recovery_fragile":
                relief_cap = 0.048
                relief_scale = 0.38
                ns_relief_cap = 0.019
                ns_relief_scale = 0.14
            else:
                relief_cap = 0.050
                relief_scale = 0.40
                ns_relief_cap = 0.020
                ns_relief_scale = 0.15
        elif overlay_penalty_mode == "phasexx_guardrail_overlay_fragile_floor":
            if market_state == "recovery_fragile":
                relief_cap = 0.046
                relief_scale = 0.36
                ns_relief_cap = 0.018
                ns_relief_scale = 0.13
            else:
                relief_cap = 0.052
                relief_scale = 0.42
                ns_relief_cap = 0.022
                ns_relief_scale = 0.16
        elif overlay_penalty_mode == "phasexx_recovery_neutral_overlay_simplified":
            if strong_neutral:
                relief_cap = 0.034
                relief_scale = 0.27
                ns_relief_cap = 0.013
                ns_relief_scale = 0.10
            elif market_state == "recovery_fragile":
                relief_cap = 0.046
                relief_scale = 0.36
                ns_relief_cap = 0.018
                ns_relief_scale = 0.13
            else:
                relief_cap = 0.052
                relief_scale = 0.42
                ns_relief_cap = 0.022
                ns_relief_scale = 0.16
        elif overlay_penalty_mode == "phasexx_conservative_hybrid_overlay":
            if strong_neutral:
                relief_cap = 0.033
                relief_scale = 0.26
                ns_relief_cap = 0.012
                ns_relief_scale = 0.09
            elif market_state == "recovery_fragile":
                relief_cap = 0.045
                relief_scale = 0.34
                ns_relief_cap = 0.016
                ns_relief_scale = 0.12
            else:
                relief_cap = 0.048
                relief_scale = 0.38
                ns_relief_cap = 0.019
                ns_relief_scale = 0.14
        ns_relief_flat = None

    tt_target_risky_budget: float | None = None
    if overlay_penalty_mode == "phasett_recovery_two_stage_bucket":
        if market_state == "recovery_confirmed":
            tt_target_risky_budget = 0.94
        elif market_state == "recovery_fragile":
            tt_target_risky_budget = 0.90
    elif overlay_penalty_mode == "phasett_recovery_neutral_two_stage_bucket":
        if strong_neutral:
            tt_target_risky_budget = 0.84
        elif market_state == "recovery_confirmed":
            tt_target_risky_budget = 0.94
        elif market_state == "recovery_fragile":
            tt_target_risky_budget = 0.90
    elif overlay_penalty_mode == "phasett_ss1_overlay_coordinated":
        if market_state == "recovery_confirmed":
            tt_target_risky_budget = 0.935
        elif market_state == "recovery_fragile":
            tt_target_risky_budget = 0.895
    elif overlay_penalty_mode in {
        "phasevv_recovery_budget_aware_overlay",
        "phasevv_recovery_overlay_tolerance_band",
        "phasevv_recovery_neutral_budget_aware_overlay",
    }:
        if strong_neutral and overlay_penalty_mode == "phasevv_recovery_neutral_budget_aware_overlay":
            tt_target_risky_budget = 0.875
        elif market_state == "recovery_confirmed":
            tt_target_risky_budget = 0.94
        elif market_state == "recovery_fragile":
            tt_target_risky_budget = 0.90

    uu_target_cash_cap: float | None = None
    if overlay_penalty_mode == "phaseuu_tt1_overlay_preserved_recovery":
        if market_state == "recovery_confirmed":
            uu_target_cash_cap = 0.055
        elif market_state == "recovery_fragile":
            uu_target_cash_cap = 0.115
    elif overlay_penalty_mode == "phaseuu_recovery_overlay_cash_cap":
        if market_state == "recovery_confirmed":
            uu_target_cash_cap = 0.070
        elif market_state == "recovery_fragile":
            uu_target_cash_cap = 0.120
    elif overlay_penalty_mode == "phaseuu_tt1_budget_aware_lighter_both":
        if market_state == "recovery_confirmed":
            uu_target_cash_cap = 0.052
        elif market_state == "recovery_fragile":
            uu_target_cash_cap = 0.112

    vv_target_cash_budget: float | None = None
    vv_cash_tolerance_band: float | None = None
    if overlay_penalty_mode == "phasevv_recovery_budget_aware_overlay":
        if market_state == "recovery_confirmed":
            vv_target_cash_budget = 0.060
            vv_cash_tolerance_band = 0.000
        elif market_state == "recovery_fragile":
            vv_target_cash_budget = 0.100
            vv_cash_tolerance_band = 0.000
    elif overlay_penalty_mode == "phasevv_recovery_overlay_tolerance_band":
        if market_state == "recovery_confirmed":
            vv_target_cash_budget = 0.060
            vv_cash_tolerance_band = 0.015
        elif market_state == "recovery_fragile":
            vv_target_cash_budget = 0.100
            vv_cash_tolerance_band = 0.015
    elif overlay_penalty_mode == "phasevv_recovery_neutral_budget_aware_overlay":
        if strong_neutral:
            vv_target_cash_budget = 0.125
            vv_cash_tolerance_band = 0.010
        elif market_state == "recovery_confirmed":
            vv_target_cash_budget = 0.060
            vv_cash_tolerance_band = 0.000
        elif market_state == "recovery_fragile":
            vv_target_cash_budget = 0.100
            vv_cash_tolerance_band = 0.000

    ww_target_cash_budget: float | None = None
    ww_target_vol_required_cash = np.nan
    ww_guardrail_cash = np.nan
    ww_target_cash_final = np.nan
    ww_budget_native_applied = 0.0
    ww_target_vol_guardrail_active = 0.0
    ww_panic_guardrail_active = 0.0
    ww_excess_cash_pre = np.nan
    ww_excess_cash_post = np.nan
    ww_target_source = "none"
    if overlay_penalty_mode == "phaseww_recovery_budget_native_lighter_both":
        if market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.055
            ww_target_source = "tt1_recovery_native"
        elif market_state == "recovery_fragile":
            ww_target_cash_budget = 0.095
            ww_target_source = "tt1_recovery_native"
    elif overlay_penalty_mode == "phaseww_split_recovery_lighter_both":
        if market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.045
            ww_target_source = "split_recovery_confirmed"
        elif market_state == "recovery_fragile":
            ww_target_cash_budget = 0.105
            ww_target_source = "split_recovery_fragile"
    elif overlay_penalty_mode == "phaseww_vv_direct_lighter_both_rewrite":
        if strong_neutral:
            ww_target_cash_budget = 0.120
            ww_target_source = "vv_direct_strong_neutral"
        elif market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.050
            ww_target_source = "vv_direct_recovery_confirmed"
        elif market_state == "recovery_fragile":
            ww_target_cash_budget = 0.095
            ww_target_source = "vv_direct_recovery_fragile"
    elif overlay_penalty_mode == "phaseww_confirmed_only_lighter_both":
        if market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.045
            ww_target_source = "rescue_confirmed_only"
    elif overlay_penalty_mode == "phaseww_fragile_defense_lighter_both":
        if market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.050
            ww_target_source = "rescue_fragile_defense_confirmed"
        elif market_state == "recovery_fragile":
            ww_target_cash_budget = 0.110
            ww_target_source = "rescue_fragile_defense_fragile"
    elif overlay_penalty_mode == "phaseww_vv_shadow_polish":
        if strong_neutral:
            ww_target_cash_budget = 0.123
            ww_target_source = "rescue_vv_shadow_neutral"
        elif market_state == "recovery_confirmed":
            ww_target_cash_budget = 0.052
            ww_target_source = "rescue_vv_shadow_confirmed"
        elif market_state == "recovery_fragile":
            ww_target_cash_budget = 0.100
            ww_target_source = "rescue_vv_shadow_fragile"

    xx_target_cash_budget: float | None = None
    xx_cash_tolerance_band: float | None = None
    xx_target_vol_required_cash = np.nan
    xx_guardrail_cash = np.nan
    xx_target_cash_final = np.nan
    xx_budget_unification_applied = 0.0
    xx_target_vol_guardrail_active = 0.0
    xx_panic_guardrail_active = 0.0
    xx_duplicate_cash_pre = np.nan
    xx_duplicate_cash_post = np.nan
    xx_target_source = "none"
    xx_hybrid_mode = False
    if overlay_penalty_mode == "phasexx_guardrail_only_overlay":
        if market_state == "recovery_confirmed":
            xx_target_cash_budget = 0.060
            xx_target_source = "guardrail_only_recovery_confirmed"
        elif market_state == "recovery_fragile":
            xx_target_cash_budget = 0.100
            xx_target_source = "guardrail_only_recovery_fragile"
    elif overlay_penalty_mode == "phasexx_guardrail_overlay_fragile_floor":
        if market_state == "recovery_confirmed":
            xx_target_cash_budget = 0.055
            xx_target_source = "fragile_floor_recovery_confirmed"
        elif market_state == "recovery_fragile":
            xx_target_cash_budget = 0.120
            xx_target_source = "fragile_floor_recovery_fragile"
    elif overlay_penalty_mode == "phasexx_recovery_neutral_overlay_simplified":
        if strong_neutral:
            xx_target_cash_budget = 0.130
            xx_target_source = "simplified_strong_neutral"
        elif market_state == "recovery_confirmed":
            xx_target_cash_budget = 0.055
            xx_target_source = "simplified_recovery_confirmed"
        elif market_state == "recovery_fragile":
            xx_target_cash_budget = 0.115
            xx_target_source = "simplified_recovery_fragile"
    elif overlay_penalty_mode == "phasexx_conservative_hybrid_overlay":
        xx_hybrid_mode = True
        if strong_neutral:
            xx_target_cash_budget = 0.130
            xx_cash_tolerance_band = 0.010
            xx_target_source = "hybrid_strong_neutral"
        elif market_state == "recovery_confirmed":
            xx_target_cash_budget = 0.055
            xx_cash_tolerance_band = 0.010
            xx_target_source = "hybrid_recovery_confirmed"
        elif market_state == "recovery_fragile":
            xx_target_cash_budget = 0.115
            xx_cash_tolerance_band = 0.015
            xx_target_source = "hybrid_recovery_fragile"

    if apply_self_gated_relief:
        self_gated_names = [name for name in blended.index if name in SELF_GATED_SLEEVES]
        non_self_gated_names = [name for name in blended.index if name not in SELF_GATED_SLEEVES]
        per_sleeve_multiplier.loc[:] = regime_multiplier
        headroom = max(0.0, target_vol_multiplier - regime_multiplier)
        if self_gated_names:
            relief = min(relief_cap, relief_scale * max(0.0, 1.0 - regime_multiplier), 0.75 * headroom if headroom > 0 else relief_cap)
            self_gated_relief = max(0.0, relief)
            self_gated_regime_multiplier = min(1.0, regime_multiplier + self_gated_relief)
            per_sleeve_multiplier.loc[self_gated_names] = self_gated_regime_multiplier
        if apply_non_self_gated_relief and non_self_gated_names:
            if ns_relief_flat is not None:
                ns_relief = min(ns_relief_flat, 0.75 * headroom if headroom > 0 else ns_relief_flat)
            else:
                ns_relief = min(
                    ns_relief_cap,
                    ns_relief_scale * max(0.0, 1.0 - regime_multiplier),
                    0.75 * headroom if headroom > 0 else ns_relief_cap,
                )
            non_self_gated_relief = max(0.0, ns_relief)
            non_self_gated_regime_multiplier = min(1.0, regime_multiplier + non_self_gated_relief)
            per_sleeve_multiplier.loc[non_self_gated_names] = non_self_gated_regime_multiplier
        if target_vol_multiplier < 1.0:
            total_risky = float((blended * per_sleeve_multiplier).sum())
            if total_risky > target_vol_multiplier and total_risky > 1e-12:
                per_sleeve_multiplier *= target_vol_multiplier / total_risky
        final_self_gated_multiplier = (
            float(per_sleeve_multiplier.loc[self_gated_names].mean()) if self_gated_names else np.nan
        )
        final_non_self_gated_multiplier = (
            float(per_sleeve_multiplier.loc[non_self_gated_names].mean())
            if non_self_gated_names
            else final_self_gated_multiplier
        )

    tt_precoord_risky_budget = float((blended * per_sleeve_multiplier).sum())
    tt_overlay_coord_applied = 0.0
    if tt_target_risky_budget is not None and market_state != "stressed_panic":
        target_floor = float(min(max(tt_target_risky_budget, 0.0), max(0.0, target_vol_multiplier)))
        if target_floor > tt_precoord_risky_budget + 1e-12 and tt_precoord_risky_budget > 1e-12:
            scale = target_floor / tt_precoord_risky_budget
            per_sleeve_multiplier *= scale
            post_scale_total = float((blended * per_sleeve_multiplier).sum())
            if target_vol_multiplier < 1.0 and post_scale_total > target_vol_multiplier + 1e-12:
                per_sleeve_multiplier *= target_vol_multiplier / post_scale_total
            tt_overlay_coord_applied = 1.0
    tt_postcoord_risky_budget = float((blended * per_sleeve_multiplier).sum())

    risky_weights = blended * per_sleeve_multiplier
    uu_precap_cash_weight = max(0.0, 1.0 - float(risky_weights.sum()))
    uu_cash_cap_applied = 0.0
    if uu_target_cash_cap is not None and market_state != "stressed_panic":
        cap_cash = float(max(0.0, uu_target_cash_cap))
        desired_risky_floor = float(min(1.0 - cap_cash, target_vol_multiplier))
        current_risky = float(risky_weights.sum())
        if current_risky > 1e-12 and desired_risky_floor > current_risky + 1e-12 and target_vol_binding <= 0.0:
            risky_weights *= desired_risky_floor / current_risky
            uu_cash_cap_applied = 1.0
    vv_target_risky_floor = np.nan
    vv_budget_override_applied = 0.0
    vv_target_vol_guardrail_active = 0.0
    vv_budget_gap_pre = np.nan
    if vv_target_cash_budget is not None and market_state != "stressed_panic":
        tolerance = float(max(0.0, vv_cash_tolerance_band or 0.0))
        allowed_cash = float(max(0.0, vv_target_cash_budget + tolerance))
        vv_target_risky_floor = float(min(1.0, max(0.0, 1.0 - allowed_cash)))
        current_cash = max(0.0, 1.0 - float(risky_weights.sum()))
        vv_budget_gap_pre = float(current_cash - allowed_cash)
        vv_target_vol_guardrail_active = float(target_vol_binding > 0.0)
        if (
            float(risky_weights.sum()) > 1e-12
            and vv_target_risky_floor > float(risky_weights.sum()) + 1e-12
            and vv_target_vol_guardrail_active <= 0.0
        ):
            risky_weights *= vv_target_risky_floor / float(risky_weights.sum())
            vv_budget_override_applied = 1.0
    if ww_target_cash_budget is not None and market_state != "stressed_panic":
        current_risky = float(risky_weights.sum())
        current_cash = max(0.0, 1.0 - current_risky)
        ww_target_vol_required_cash = float(max(0.0, 1.0 - float(target_vol_multiplier)))
        ww_target_vol_guardrail_active = float(ww_target_vol_required_cash > float(ww_target_cash_budget) + 1e-12)
        ww_panic_guardrail_active = float(market_state == "stressed_panic")
        ww_guardrail_cash = float(max(0.0, ww_target_vol_required_cash, 1.0 if ww_panic_guardrail_active > 0.0 else 0.0))
        ww_target_cash_final = float(max(float(ww_target_cash_budget), ww_guardrail_cash))
        ww_excess_cash_pre = float(max(0.0, current_cash - ww_target_cash_final))
        desired_risky = float(min(1.0, max(0.0, 1.0 - ww_target_cash_final)))
        if current_risky > 1e-12 and abs(desired_risky - current_risky) > 1e-12:
            risky_weights *= desired_risky / current_risky
            ww_budget_native_applied = 1.0
    if xx_target_cash_budget is not None and market_state != "stressed_panic":
        current_risky = float(risky_weights.sum())
        current_cash = max(0.0, 1.0 - current_risky)
        xx_target_vol_required_cash = float(max(0.0, 1.0 - float(target_vol_multiplier)))
        xx_target_vol_guardrail_active = float(xx_target_vol_required_cash > float(xx_target_cash_budget) + 1e-12)
        xx_panic_guardrail_active = float(market_state == "stressed_panic")
        xx_guardrail_cash = float(max(0.0, xx_target_vol_required_cash, 1.0 if xx_panic_guardrail_active > 0.0 else 0.0))
        base_target_cash = float(max(float(xx_target_cash_budget), xx_guardrail_cash))
        tolerance = float(max(0.0, xx_cash_tolerance_band or 0.0))
        xx_target_cash_final = base_target_cash
        duplicate_threshold_cash = base_target_cash + tolerance
        xx_duplicate_cash_pre = float(max(0.0, current_cash - duplicate_threshold_cash))
        if xx_hybrid_mode:
            desired_cash = current_cash if current_cash <= duplicate_threshold_cash + 1e-12 else duplicate_threshold_cash
        else:
            desired_cash = base_target_cash
        desired_risky = float(min(1.0, max(0.0, 1.0 - desired_cash)))
        if current_risky > 1e-12 and abs(desired_risky - current_risky) > 1e-12:
            risky_weights *= desired_risky / current_risky
            xx_budget_unification_applied = 1.0
    gross_multiplier = float(risky_weights.sum())
    if overlay_penalty_mode == "none":
        final_self_gated_multiplier = gross_multiplier
        final_non_self_gated_multiplier = gross_multiplier
    cash_weight = max(0.0, 1.0 - risky_weights.sum())
    vv_budget_gap_post = np.nan
    if vv_target_cash_budget is not None and market_state != "stressed_panic":
        allowed_cash = float(max(0.0, vv_target_cash_budget + float(max(0.0, vv_cash_tolerance_band or 0.0))))
        vv_budget_gap_post = float(cash_weight - allowed_cash)
    if ww_target_cash_budget is not None and market_state != "stressed_panic":
        ww_excess_cash_post = float(max(0.0, cash_weight - float(ww_target_cash_final)))
    if xx_target_cash_budget is not None and market_state != "stressed_panic":
        tolerance = float(max(0.0, xx_cash_tolerance_band or 0.0))
        xx_duplicate_cash_post = float(max(0.0, cash_weight - (float(xx_target_cash_final) + tolerance)))
    diagnostics = {
        "predicted_ann_vol": predicted_ann_vol,
        "target_vol_multiplier": target_vol_multiplier,
        "regime_multiplier": regime_multiplier,
        "raw_regime_multiplier": raw_regime_multiplier,
        **phase2b_diag,
        "gross_multiplier": gross_multiplier,
        "cash_weight": cash_weight,
        "dynamic_speed": dynamic_speed,
        "regime_binding": regime_binding,
        "target_vol_binding": target_vol_binding,
        "both_binding": both_binding,
        "self_gated_relief": self_gated_relief,
        "self_gated_regime_multiplier": self_gated_regime_multiplier,
        "non_self_gated_relief": non_self_gated_relief,
        "non_self_gated_regime_multiplier": non_self_gated_regime_multiplier,
        "final_self_gated_multiplier": final_self_gated_multiplier,
        "final_non_self_gated_multiplier": final_non_self_gated_multiplier,
        "tt_target_risky_budget": np.nan if tt_target_risky_budget is None else float(tt_target_risky_budget),
        "tt_precoord_risky_budget": tt_precoord_risky_budget,
        "tt_postcoord_risky_budget": tt_postcoord_risky_budget,
        "tt_overlay_coord_applied": tt_overlay_coord_applied,
        "uu_target_cash_cap": np.nan if uu_target_cash_cap is None else float(uu_target_cash_cap),
        "uu_precap_cash_weight": uu_precap_cash_weight,
        "uu_postcap_cash_weight": cash_weight,
        "uu_cash_cap_applied": uu_cash_cap_applied,
        "vv_target_cash_budget": np.nan if vv_target_cash_budget is None else float(vv_target_cash_budget),
        "vv_cash_tolerance_band": np.nan if vv_cash_tolerance_band is None else float(vv_cash_tolerance_band),
        "vv_target_risky_floor": float(vv_target_risky_floor) if np.isfinite(vv_target_risky_floor) else np.nan,
        "vv_budget_override_applied": float(vv_budget_override_applied),
        "vv_target_vol_guardrail_active": float(vv_target_vol_guardrail_active),
        "vv_budget_gap_pre": float(vv_budget_gap_pre) if np.isfinite(vv_budget_gap_pre) else np.nan,
        "vv_budget_gap_post": float(vv_budget_gap_post) if np.isfinite(vv_budget_gap_post) else np.nan,
        "ww_target_cash_budget": np.nan if ww_target_cash_budget is None else float(ww_target_cash_budget),
        "ww_target_vol_required_cash": float(ww_target_vol_required_cash) if np.isfinite(ww_target_vol_required_cash) else np.nan,
        "ww_guardrail_cash": float(ww_guardrail_cash) if np.isfinite(ww_guardrail_cash) else np.nan,
        "ww_target_cash_final": float(ww_target_cash_final) if np.isfinite(ww_target_cash_final) else np.nan,
        "ww_budget_native_applied": float(ww_budget_native_applied),
        "ww_target_vol_guardrail_active": float(ww_target_vol_guardrail_active),
        "ww_panic_guardrail_active": float(ww_panic_guardrail_active),
        "ww_excess_cash_pre": float(ww_excess_cash_pre) if np.isfinite(ww_excess_cash_pre) else np.nan,
        "ww_excess_cash_post": float(ww_excess_cash_post) if np.isfinite(ww_excess_cash_post) else np.nan,
        "ww_target_source": ww_target_source,
        "xx_target_cash_budget": np.nan if xx_target_cash_budget is None else float(xx_target_cash_budget),
        "xx_cash_tolerance_band": np.nan if xx_cash_tolerance_band is None else float(xx_cash_tolerance_band),
        "xx_target_vol_required_cash": float(xx_target_vol_required_cash) if np.isfinite(xx_target_vol_required_cash) else np.nan,
        "xx_guardrail_cash": float(xx_guardrail_cash) if np.isfinite(xx_guardrail_cash) else np.nan,
        "xx_target_cash_final": float(xx_target_cash_final) if np.isfinite(xx_target_cash_final) else np.nan,
        "xx_budget_unification_applied": float(xx_budget_unification_applied),
        "xx_target_vol_guardrail_active": float(xx_target_vol_guardrail_active),
        "xx_panic_guardrail_active": float(xx_panic_guardrail_active),
        "xx_duplicate_cash_pre": float(xx_duplicate_cash_pre) if np.isfinite(xx_duplicate_cash_pre) else np.nan,
        "xx_duplicate_cash_post": float(xx_duplicate_cash_post) if np.isfinite(xx_duplicate_cash_post) else np.nan,
        "xx_target_source": xx_target_source,
        "overlay_penalty_mode": overlay_penalty_mode,
        "speed_mode": speed_mode,
    }
    return risky_weights, cash_weight, diagnostics


def run_subset_custom(
    method_name: str,
    subset_name: str,
    subset_sleeves: list[str],
    *,
    overlay_variant: str = "baseline",
    speed: float = ns5["SLEEVE_REALLOCATION_SPEED"],
    target_vol_ceil: float = ns5["TARGET_VOL_CEIL"],
    rerisk_speed: float | None = None,
    state_tilt: str = "none",
    layer3_expression_mode: str = "none",
    overlay_penalty_mode: str = "none",
    speed_mode: str = "default",
    improving_speed: float | None = None,
    deteriorating_speed: float | None = None,
    beta_overlay_mode: str = "none",
    market_state_history: pd.DataFrame | None = None,
    stabilize_market_state: bool = False,
    phase2b_mode: str = "none",
    checkpoint_name: str | None = None,
    sleeve_return_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    subset = [name for name in subset_sleeves if name in sleeve_return_panel.columns]
    if not subset:
        raise ValueError(f"No valid sleeves for subset {subset_name}")
    method_spec = next(spec for spec in ns5["method_specs"] if spec["method_name"] == method_name)
    # Optional one-sided hysteresis: swap in stabilized market_state (delays entry
    # into stressed_panic by 1 week unless the entry is severe). Only used by the
    # stabilizer variants; other variants continue to use the raw market_state.
    if (
        stabilize_market_state
        and market_state_history is not None
        and "market_state_stable" in market_state_history.columns
    ):
        effective_market_state_history = market_state_history.copy()
        effective_market_state_history["market_state"] = effective_market_state_history["market_state_stable"]
    else:
        effective_market_state_history = market_state_history
    variant_regime_states = build_variant_regime_states(ns5["regime_states"], effective_market_state_history, overlay_variant)
    conviction_inputs = {
        key: value.reindex(columns=[name for name in subset if name in value.columns])
        for key, value in ns5["conviction_inputs"].items()
    }
    forward_weekly_returns = ns5["next_week_returns"].reindex(columns=ns5["weekly_prices"].columns)
    all_dates = sleeve_return_panel.index
    rebalance_dates = ns5["rebalance_mask"](all_dates, ns5["REBALANCE_FREQUENCY"])
    current_risky_alloc = pd.Series(0.0, index=subset, dtype=float)
    current_cash_weight = 1.0
    prev_regime_multiplier_value: float | None = None
    sleeve_alloc_rows: list[pd.Series] = []
    etf_weight_rows: list[pd.Series] = []
    diag_rows: list[dict] = []
    beta_overlay_rows: list[pd.Series] = []
    checkpoint_rows: dict[str, list[pd.Series]] = {
        "raw_hrp_sleeve_weights": [],
        "post_state_tilt_sleeve_weights": [],
        "post_layer3_expression_sleeve_weights": [],
        "post_overlay_pre_lookthrough_sleeve_weights": [],
        "final_sleeve_weights": [],
        "final_etf_weights": [],
    }
    last_checkpoint_stage: dict[str, pd.Series] = {
        "raw_hrp_sleeve_weights": checkpoint_stage_template(subset),
        "post_state_tilt_sleeve_weights": checkpoint_stage_template(subset),
        "post_layer3_expression_sleeve_weights": checkpoint_stage_template(subset),
        "post_overlay_pre_lookthrough_sleeve_weights": checkpoint_stage_template(subset),
        "final_sleeve_weights": checkpoint_stage_template(subset),
        "final_etf_weights": pd.Series({ns5["cash_proxy"]: 1.0}, dtype=float),
    }
    for stage_series in last_checkpoint_stage.values():
        if f"cash::{ns5['cash_proxy']}" in stage_series.index:
            stage_series.loc[f"cash::{ns5['cash_proxy']}"] = 1.0

    def _stage_series_from_sleeves(weights: pd.Series, cash_weight: float) -> pd.Series:
        stage = checkpoint_stage_template(subset)
        if weights is not None and not weights.empty:
            active_cols = [name for name in weights.index if name in stage.index]
            if active_cols:
                stage.loc[active_cols] = pd.Series(weights, dtype=float).reindex(active_cols).fillna(0.0)
        stage.loc[f"cash::{ns5['cash_proxy']}"] = float(max(0.0, cash_weight))
        return stage

    for date in all_dates:
        market_state_row = (
            effective_market_state_history.loc[date]
            if effective_market_state_history is not None and date in effective_market_state_history.index
            else pd.Series(dtype=float)
        )
        market_state = market_state_row.get("market_state") if isinstance(market_state_row, pd.Series) else None
        if rebalance_dates.loc[date]:
            train_slice = sleeve_return_panel.loc[:date, subset].tail(ns5["TRAIN_WINDOW_WEEKS"])
            active = ns5["select_active_sleeves"](train_slice)
            if len(active) >= 2:
                train = train_slice[active].dropna(how="any")
                if len(train) >= max(26, min(ns5["MIN_TRAIN_OBS"], ns5["TRAIN_WINDOW_WEEKS"] // 2)):
                    cov = ns5["estimate_covariance"](train, method=method_spec["covariance_method"])
                    if not cov.empty:
                        active = list(cov.index)
                        train = train.reindex(columns=active).dropna(how="any")
                        prev_active = current_risky_alloc.reindex(active).fillna(0.0)
                        mu = pd.Series(0.0, index=active)
                        bl_diag = {"view_count": 0, "view_confidence": np.nan, "view_spread": np.nan}
                        hier_diag = {"hierarchical_fallback": False, "hierarchical_reason": "", "hierarchical_valid_sleeves": len(active)}
                        expected_return_key = method_spec["expected_return_key"]
                        if expected_return_key is not None and expected_return_key in conviction_inputs:
                            score_row = conviction_inputs[expected_return_key].reindex(columns=subset).loc[date].reindex(active)
                            mu = ns5["score_row_to_weekly_mu"](score_row, train)

                        engine = method_spec["engine"]
                        if engine == "equal_weight":
                            raw = pd.Series(1.0 / len(active), index=active)
                        elif engine == "inverse_vol":
                            raw = ns5["inverse_vol_weights_from_cov"](cov)
                        elif engine == "min_variance":
                            raw = ns5["optimize_min_variance"](cov, prev_weights=prev_active)
                        elif engine == "mvo":
                            raw = ns5["optimize_mean_variance"](mu, cov, prev_weights=prev_active)
                        elif engine == "max_sharpe":
                            raw = ns5["optimize_max_sharpe"](mu, cov, prev_weights=prev_active)
                        elif engine == "black_litterman":
                            posterior_mu, bl_diag = ns5["black_litterman_posterior"](
                                cov,
                                conviction_inputs[expected_return_key].loc[date].reindex(active),
                                prior_weights=prev_active if prev_active.sum() > 0 else None,
                            )
                            raw = ns5["optimize_mean_variance"](posterior_mu, cov, prev_weights=prev_active)
                        elif engine == "erc":
                            raw = ns5["optimize_erc"](cov, prev_weights=prev_active)
                        elif engine == "hrp":
                            raw, hier_diag = ns5["optimize_hrp"](cov, return_diagnostics=True)
                        elif engine == "herc":
                            raw, hier_diag = ns5["optimize_herc"](cov, return_diagnostics=True)
                        elif engine == "max_diversification":
                            raw = ns5["optimize_max_diversification"](cov, prev_weights=prev_active)
                        elif engine == "cvar":
                            raw = ns5["optimize_cvar"](train, prev_weights=prev_active)
                        else:
                            raise ValueError(f"Unknown engine: {engine}")

                        if state_tilt in {
                            "dynamic_risk_budget_confirmed_quality",
                            "dynamic_risk_budget_full_phase3",
                        }:
                            conviction_row = compute_confirmed_sleeve_quality(
                                sleeve_return_panel, date, list(active)
                            )
                        elif state_tilt in {
                            "phasec_learned_quality",
                            "phasec_dynamic_opportunity_budget",
                            "phasec_combo",
                        }:
                            learned_quality_panel = compute_phasec_learned_sleeve_quality(
                                sleeve_return_panel,
                                effective_market_state_history,
                                list(active),
                            )
                            if date in learned_quality_panel.index:
                                conviction_row = (
                                    (learned_quality_panel.loc[date].reindex(active).fillna(0.5) - 0.5) * 2.0
                                ).clip(-1.0, 1.0)
                            else:
                                conviction_row = pd.Series(0.0, index=active, dtype=float)
                        elif state_tilt in {
                            "dynamic_risk_budget",
                            "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
                            "dynamic_risk_budget_and_leadership",
                            "dynamic_risk_budget_state_leader",
                            "dynamic_risk_budget_state_leader_wider",
                            "dynamic_risk_budget_state_leader_conviction_gated",
                            "dynamic_risk_budget_sector_gated",
                            "dynamic_risk_budget_state_leader_wider_sector_gated",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tight",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
                            "phase_jjj4_adaptive_mom_vol_corr_budget",
                            "phasec_state_map",
                        }:
                            conviction_row = compute_rolling_sleeve_conviction(
                                sleeve_return_panel, date, list(active), lookback_weeks=26
                            )
                        else:
                            conviction_row = None
                        if state_tilt in {
                            "dynamic_risk_budget_state_leader",
                            "dynamic_risk_budget_full_phase3",
                            "dynamic_risk_budget_state_leader_wider",
                            "dynamic_risk_budget_state_leader_conviction_gated",
                            "dynamic_risk_budget_state_leader_wider_sector_gated",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tight",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
                            "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
                            "phase_jjj4_adaptive_mom_vol_corr_budget",
                            "phasec_state_map",
                            "phasec_combo",
                        }:
                            state_lead_tilt_row = compute_state_sleeve_lead_tilt(
                                sleeve_return_panel,
                                effective_market_state_history,
                                date,
                                list(active),
                            )
                        else:
                            state_lead_tilt_row = None
                        raw_pre_tilt = pd.Series(raw, dtype=float).copy()
                        raw = apply_state_conditioned_tilt(
                            raw_pre_tilt,
                            market_state,
                            tilt_mode=state_tilt,
                            conviction=conviction_row,
                            market_state_row=market_state_row if isinstance(market_state_row, pd.Series) else None,
                            state_lead_tilt=state_lead_tilt_row,
                        )
                        post_tilt_weights = pd.Series(raw, dtype=float).copy()
                        default_conviction_row = (
                            conviction_inputs["default_blend"].loc[date].reindex(active)
                            if "default_blend" in conviction_inputs and date in conviction_inputs["default_blend"].index
                            else pd.Series(dtype=float)
                        )
                        raw, layer3_diag = apply_layer3_expression(
                            post_tilt_weights,
                            market_state_row if isinstance(market_state_row, pd.Series) else None,
                            default_conviction_row,
                            expression_mode=layer3_expression_mode,
                        )
                        post_expression_weights = pd.Series(raw, dtype=float).copy()
                        overlay_row = variant_regime_states.loc[date] if date in variant_regime_states.index else pd.Series(dtype=float)
                        ml_pred_row = (
                            phase2b_meta_predictions.loc[date]
                            if phase2b_mode != "none"
                            and not phase2b_meta_predictions.empty
                            and date in phase2b_meta_predictions.index
                            else None
                        )
                        risky_weights, cash_weight, overlay_diag = apply_overlays_custom(
                            post_expression_weights,
                            cov,
                            overlay_row,
                            prev_weights=prev_active,
                            target_vol_ceil=target_vol_ceil,
                            sleeve_reallocation_speed=speed,
                            rerisk_speed=rerisk_speed,
                            market_state=market_state,
                            market_state_row=market_state_row if isinstance(market_state_row, pd.Series) else None,
                            prev_regime_multiplier=prev_regime_multiplier_value,
                            overlay_penalty_mode=overlay_penalty_mode,
                            speed_mode=speed_mode,
                            improving_speed=improving_speed,
                            deteriorating_speed=deteriorating_speed,
                            phase2b_mode=phase2b_mode,
                            ml_pred_row=ml_pred_row,
                        )
                        prev_regime_multiplier_value = float(overlay_diag.get("regime_multiplier", np.nan)) if overlay_diag else prev_regime_multiplier_value
                        current_risky_alloc = pd.Series(0.0, index=subset, dtype=float)
                        current_risky_alloc.loc[risky_weights.index] = risky_weights
                        current_cash_weight = cash_weight
                        last_checkpoint_stage["raw_hrp_sleeve_weights"] = _stage_series_from_sleeves(
                            raw_pre_tilt, max(0.0, 1.0 - float(raw_pre_tilt.sum()))
                        )
                        last_checkpoint_stage["post_state_tilt_sleeve_weights"] = _stage_series_from_sleeves(
                            post_tilt_weights, max(0.0, 1.0 - float(post_tilt_weights.sum()))
                        )
                        last_checkpoint_stage["post_layer3_expression_sleeve_weights"] = _stage_series_from_sleeves(
                            post_expression_weights, max(0.0, 1.0 - float(post_expression_weights.sum()))
                        )
                        last_checkpoint_stage["post_overlay_pre_lookthrough_sleeve_weights"] = _stage_series_from_sleeves(
                            current_risky_alloc, current_cash_weight
                        )
                        diag_rows.append(
                            {
                                "Date": date,
                                "method_name": method_name,
                                "engine": engine,
                                "method_category": "improvement_lab",
                                "active_sleeves": len(active),
                                "expected_return_key": expected_return_key or "n/a",
                                "covariance_method": method_spec["covariance_method"],
                                "overlay_variant": overlay_variant,
                                "state_tilt": state_tilt,
                                "layer3_expression_mode": layer3_expression_mode,
                                "overlay_penalty_mode": overlay_penalty_mode,
                                "speed_mode": speed_mode,
                                "beta_overlay_mode": beta_overlay_mode,
                                "phase2b_mode_spec": phase2b_mode,
                                "market_state": market_state,
                                **overlay_diag,
                                **layer3_diag,
                                **bl_diag,
                                **hier_diag,
                            }
                        )

        allocation_row = current_risky_alloc.copy()
        allocation_row.loc[f"cash::{ns5['cash_proxy']}"] = current_cash_weight
        allocation_row.name = date
        sleeve_alloc_rows.append(allocation_row)
        last_checkpoint_stage["final_sleeve_weights"] = allocation_row.copy()
        for stage_name, stage_series in last_checkpoint_stage.items():
            if stage_name == "final_etf_weights":
                continue
            stage_row = pd.Series(stage_series, dtype=float).copy()
            stage_row.name = date
            checkpoint_rows[stage_name].append(stage_row)

        etf_row = ns5["build_lookthrough_etf_weights"](
            date=date,
            sleeve_weights=current_risky_alloc,
            sleeve_positions=sleeve_positions,
            universe_columns=list(forward_weekly_returns.columns),
            cash_proxy=ns5["cash_proxy"],
            cash_weight=current_cash_weight,
        )
        etf_row, beta_overlay_diag = apply_beta_participation_overlay(
            etf_row,
            market_state_row if isinstance(market_state_row, pd.Series) else None,
            beta_overlay_mode=beta_overlay_mode,
        )
        etf_row.name = date
        etf_weight_rows.append(etf_row)
        last_checkpoint_stage["final_etf_weights"] = etf_row.copy()
        checkpoint_rows["final_etf_weights"].append(etf_row.copy())
        beta_overlay_rows.append(
            pd.Series(
                {
                    "beta_overlay_spy": beta_overlay_diag.get("SPY", 0.0),
                    "beta_overlay_bil": beta_overlay_diag.get(ns5["cash_proxy"], 0.0),
                },
                name=date,
            )
        )

    sleeve_alloc = pd.DataFrame(sleeve_alloc_rows).sort_index().fillna(0.0)
    etf_weights = pd.DataFrame(etf_weight_rows).sort_index().fillna(0.0)
    beta_overlay_panel = pd.DataFrame(beta_overlay_rows).sort_index().fillna(0.0)
    path = ns5["compute_portfolio_path"](
        etf_weights,
        forward_weekly_returns.reindex(index=etf_weights.index, columns=etf_weights.columns),
        transaction_cost_bps=ns5["DEFAULT_COST_BPS"],
    )
    diagnostics = pd.DataFrame(diag_rows)
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=etf_weights,
        allocation_panel=sleeve_alloc,
        trials=max(len(subset), 2),
    )
    if SAVE_ALLOCATOR_CHECKPOINTS and checkpoint_name:
        checkpoint_tables = {
            stage_name: pd.DataFrame(rows).sort_index().fillna(0.0)
            for stage_name, rows in checkpoint_rows.items()
            if rows
        }
        save_allocator_checkpoint_tables(checkpoint_name, checkpoint_tables)
    return sleeve_alloc, etf_weights, path, diagnostics, beta_overlay_panel, metrics


def version_capture_summary(
    version_name: str,
    version_returns: pd.Series,
    benchmark_returns: pd.Series,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> dict:
    aligned = pd.concat([version_returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    positive = aligned["benchmark"] > 0
    negative = aligned["benchmark"] < 0
    upside_capture = aligned.loc[positive, "portfolio"].mean() / aligned.loc[positive, "benchmark"].mean() if positive.any() else np.nan
    downside_capture = aligned.loc[negative, "portfolio"].mean() / aligned.loc[negative, "benchmark"].mean() if negative.any() else np.nan

    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)

    joined = pd.DataFrame(
        {
            "portfolio": aligned["portfolio"],
            "benchmark": aligned["benchmark"],
            "offensive_weight": offensive_weight.reindex(aligned.index),
            "defensive_weight": defensive_weight.reindex(aligned.index),
            "cash_weight": cash_weight.reindex(aligned.index),
            "market_state": market_state_history.reindex(aligned.index)["market_state"],
        }
    )
    if not diag_idx.empty:
        for col in ["regime_multiplier", "target_vol_multiplier", "gross_multiplier", "dynamic_speed"]:
            joined[col] = diag_idx.reindex(aligned.index)[col]

    recovery_any_mask = joined["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])
    recovery_fragile_mask = joined["market_state"].eq("recovery_fragile")
    recovery_confirmed_mask = joined["market_state"].eq("recovery_confirmed")
    calm_mask = joined["market_state"].eq("calm_trend")
    stressed_mask = joined["market_state"].eq("stressed_panic")

    def bucket_capture(mask: pd.Series) -> float:
        if not mask.any():
            return np.nan
        bench_sum = joined.loc[mask, "benchmark"].sum()
        return joined.loc[mask, "portfolio"].sum() / bench_sum if bench_sum != 0 else np.nan

    return {
        "version_name": version_name,
        "upside_capture_positive_weeks": upside_capture,
        "downside_capture_negative_weeks": downside_capture,
        "recovery_week_capture": bucket_capture(recovery_any_mask),
        "recovery_fragile_capture": bucket_capture(recovery_fragile_mask),
        "recovery_confirmed_capture": bucket_capture(recovery_confirmed_mask),
        "calm_week_capture": bucket_capture(calm_mask),
        "stress_downside_capture": bucket_capture(stressed_mask),
        "avg_offensive_when_benchmark_positive": safe_mean(joined.loc[positive, "offensive_weight"]),
        "avg_cash_when_benchmark_positive": safe_mean(joined.loc[positive, "cash_weight"]),
        "avg_regime_multiplier_when_benchmark_positive": safe_mean(joined.loc[positive, "regime_multiplier"]) if "regime_multiplier" in joined else np.nan,
        "avg_target_vol_multiplier_when_benchmark_positive": safe_mean(joined.loc[positive, "target_vol_multiplier"]) if "target_vol_multiplier" in joined else np.nan,
        "avg_dynamic_speed_when_benchmark_positive": safe_mean(joined.loc[positive, "dynamic_speed"]) if "dynamic_speed" in joined else np.nan,
    }


def top_rally_windows(benchmark_returns: pd.Series, lookback_weeks: int = 26, top_n: int = 5, min_spacing_weeks: int = 20) -> list[dict]:
    rolling = (1.0 + benchmark_returns).rolling(lookback_weeks).apply(np.prod, raw=True) - 1.0
    candidates = rolling.dropna().sort_values(ascending=False)
    selected: list[dict] = []
    used_endpoints: list[pd.Timestamp] = []
    for end_date, value in candidates.items():
        if any(abs((end_date - prev).days) < min_spacing_weeks * 7 for prev in used_endpoints):
            continue
        start_date = benchmark_returns.index[max(0, benchmark_returns.index.get_loc(end_date) - lookback_weeks + 1)]
        selected.append(
            {
                "window_name": f"top_rally_{len(selected) + 1}",
                "window_type": "auto_rally",
                "start_date": start_date,
                "end_date": end_date,
                "benchmark_return": float(value),
            }
        )
        used_endpoints.append(end_date)
        if len(selected) >= top_n:
            break
    return selected


def manual_windows(index: pd.DatetimeIndex) -> list[dict]:
    specs = [
        ("stress_2008_2009", "stress", "2007-10-12", "2009-03-06"),
        ("recovery_2009_2010", "recovery", "2009-03-13", "2010-04-30"),
        ("calm_bull_2013_2014", "rising", "2013-01-04", "2014-06-27"),
        ("choppy_2015_2016", "choppy", "2015-05-29", "2016-11-04"),
        ("stress_2020_crash", "stress", "2020-02-21", "2020-03-27"),
        ("recovery_2020_2021", "recovery", "2020-04-03", "2021-12-31"),
        ("stress_2022_rates", "stress", "2022-01-07", "2022-10-14"),
        ("recovery_2023_2024", "recovery", "2023-01-06", "2024-12-27"),
        ("calm_rally_2017_2019", "rising", "2017-01-06", "2019-12-27"),
    ]
    out = []
    min_date, max_date = index.min(), index.max()
    for name, window_type, start, end in specs:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        if end_ts < min_date or start_ts > max_date:
            continue
        out.append(
            {
                "window_name": name,
                "window_type": window_type,
                "start_date": max(start_ts, min_date),
                "end_date": min(end_ts, max_date),
            }
        )
    return out


def summarize_window(
    window: dict,
    version_name: str,
    version_returns: pd.Series,
    benchmark_returns: pd.Series,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> dict:
    start = pd.Timestamp(window["start_date"])
    end = pd.Timestamp(window["end_date"])
    version_window = version_returns.loc[(version_returns.index >= start) & (version_returns.index <= end)]
    benchmark_window = benchmark_returns.loc[(benchmark_returns.index >= start) & (benchmark_returns.index <= end)]
    aligned = pd.concat([version_window.rename("portfolio"), benchmark_window.rename("benchmark")], axis=1).dropna()
    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)

    mask = (weight_panel.index >= start) & (weight_panel.index <= end)
    weight_slice = weight_panel.loc[mask]
    market_state_slice = market_state_history.loc[(market_state_history.index >= start) & (market_state_history.index <= end)]

    benchmark_ret = cumulative_return(aligned["benchmark"])
    portfolio_ret = cumulative_return(aligned["portfolio"])
    capture = portfolio_ret / benchmark_ret if pd.notna(benchmark_ret) and benchmark_ret != 0 else np.nan

    return {
        "version_name": version_name,
        "window_name": window["window_name"],
        "window_type": window["window_type"],
        "start_date": str(start.date()),
        "end_date": str(end.date()),
        "observations": int(len(aligned)),
        "portfolio_return": portfolio_ret,
        "benchmark_return": benchmark_ret,
        "excess_return": portfolio_ret - benchmark_ret if pd.notna(portfolio_ret) and pd.notna(benchmark_ret) else np.nan,
        "capture_ratio": capture,
        "portfolio_max_drawdown": window_drawdown(aligned["portfolio"]),
        "benchmark_max_drawdown": window_drawdown(aligned["benchmark"]),
        "avg_offensive_weight": safe_mean(offensive_weight.reindex(weight_slice.index)),
        "avg_defensive_weight": safe_mean(defensive_weight.reindex(weight_slice.index)),
        "avg_cash_weight": safe_mean(cash_weight.reindex(weight_slice.index)),
        "avg_bil_weight": safe_mean(weight_panel.get("BIL", pd.Series(index=weight_panel.index, dtype=float)).reindex(weight_slice.index)),
        "avg_spy_weight": safe_mean(weight_panel.get("SPY", pd.Series(index=weight_panel.index, dtype=float)).reindex(weight_slice.index)),
        "avg_regime_multiplier": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "regime_multiplier"]) if not diag_idx.empty else np.nan,
        "avg_target_vol_multiplier": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "target_vol_multiplier"]) if not diag_idx.empty else np.nan,
        "avg_dynamic_speed": safe_mean(diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end), "dynamic_speed"]) if not diag_idx.empty else np.nan,
        "avg_market_state_recovery": safe_mean(market_state_slice["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"]).astype(float)),
        "avg_market_state_recovery_fragile": safe_mean(market_state_slice["market_state"].eq("recovery_fragile").astype(float)),
        "avg_market_state_recovery_confirmed": safe_mean(market_state_slice["market_state"].eq("recovery_confirmed").astype(float)),
        "avg_market_state_stressed": safe_mean(market_state_slice["market_state"].eq("stressed_panic").astype(float)),
    }


def rerisking_lag_summary(
    window: dict,
    version_name: str,
    weight_panel: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> dict:
    start = pd.Timestamp(window["start_date"])
    end = pd.Timestamp(window["end_date"])
    offensive_assets, _ = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))
    offensive_slice = offensive_weight.loc[(offensive_weight.index >= start) & (offensive_weight.index <= end)]
    cash_slice = cash_weight.loc[(cash_weight.index >= start) & (cash_weight.index <= end)]

    def first_hit(series: pd.Series, threshold_func) -> float:
        if series.empty:
            return np.nan
        hits = np.flatnonzero(threshold_func(series.to_numpy(dtype=float)))
        return float(hits[0]) if len(hits) else np.nan

    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)
        diag_slice = diag_idx.loc[(diag_idx.index >= start) & (diag_idx.index <= end)]
    else:
        diag_slice = pd.DataFrame()

    return {
        "version_name": version_name,
        "window_name": window["window_name"],
        "window_type": window["window_type"],
        "weeks_to_offensive_50": first_hit(offensive_slice, lambda arr: arr >= 0.50),
        "weeks_to_offensive_60": first_hit(offensive_slice, lambda arr: arr >= 0.60),
        "weeks_to_cash_below_35": first_hit(cash_slice, lambda arr: arr <= 0.35),
        "weeks_to_cash_below_25": first_hit(cash_slice, lambda arr: arr <= 0.25),
        "avg_dynamic_speed": safe_mean(diag_slice["dynamic_speed"]) if not diag_slice.empty else np.nan,
    }


base_signal_set = ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"]
current_signal_set = list(ns3["baseline_signal_names"])
signal_incremental_rows: list[dict] = []
signal_subset_rows: list[dict] = []

_, _, base_signal_metrics = evaluate_signal_combo(base_signal_set)
signal_incremental_rows.append(
    {
        "study": "base_core",
        "test_type": "baseline",
        "candidate_signal": "base_core",
        "signal_count": len(base_signal_set),
        "signal_names": "|".join(base_signal_set),
        **base_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    _, _, metrics = evaluate_signal_combo(base_signal_set + [candidate])
    signal_incremental_rows.append(
        {
            "study": "base_plus_one",
            "test_type": "add_one",
            "candidate_signal": candidate,
            "signal_count": len(base_signal_set) + 1,
            "signal_names": "|".join(base_signal_set + [candidate]),
            **metrics,
            "delta_ann_return_vs_base": metrics["ann_return"] - base_signal_metrics["ann_return"],
            "delta_sharpe_vs_base": metrics["sharpe"] - base_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_base": metrics["max_drawdown"] - base_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_base": metrics["cvar_5"] - base_signal_metrics["cvar_5"],
            "delta_turnover_vs_base": metrics["avg_weekly_turnover"] - base_signal_metrics["avg_weekly_turnover"],
        }
    )

_, _, full_signal_metrics = evaluate_signal_combo(current_signal_set)
signal_incremental_rows.append(
    {
        "study": "current_full",
        "test_type": "baseline",
        "candidate_signal": "current_full",
        "signal_count": len(current_signal_set),
        "signal_names": "|".join(current_signal_set),
        **full_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    reduced = [name for name in current_signal_set if name != candidate]
    _, _, metrics = evaluate_signal_combo(reduced)
    signal_incremental_rows.append(
        {
            "study": "drop_from_current_full",
            "test_type": "drop_one",
            "candidate_signal": candidate,
            "signal_count": len(reduced),
            "signal_names": "|".join(reduced),
            **metrics,
            "delta_ann_return_vs_current_full": metrics["ann_return"] - full_signal_metrics["ann_return"],
            "delta_sharpe_vs_current_full": metrics["sharpe"] - full_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_current_full": metrics["max_drawdown"] - full_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_current_full": metrics["cvar_5"] - full_signal_metrics["cvar_5"],
            "delta_turnover_vs_current_full": metrics["avg_weekly_turnover"] - full_signal_metrics["avg_weekly_turnover"],
        }
    )

signal_subset_specs = {
    "core4": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"],
    "core4_bab": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy"],
    "core4_bab_carry": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy", "carry_proxy"],
    "current_full": current_signal_set,
    "current_drop_residual": [name for name in current_signal_set if name != "residual_momentum"],
    "current_drop_reversal": [name for name in current_signal_set if name != "reversal_4w_global"],
    "current_drop_residual_reversal": [name for name in current_signal_set if name not in {"residual_momentum", "reversal_4w_global"}],
}

for combo_name, signal_names in signal_subset_specs.items():
    _, _, metrics = evaluate_signal_combo(signal_names)
    signal_subset_rows.append(
        {
            "combo_name": combo_name,
            "signal_count": len(signal_names),
            "signal_names": "|".join(signal_names),
            **metrics,
        }
    )

signal_incremental_df = pd.DataFrame(signal_incremental_rows)
signal_subset_df = pd.DataFrame(signal_subset_rows)
signal_incremental_df.to_csv(LAYER1_DIR / "signal_incremental_contribution.csv", index=False)
signal_subset_df.to_csv(LAYER1_DIR / "signal_subset_comparison.csv", index=False)


phase_a_signal_specs = {
    "trend_clarity_momentum": ("signal_trend_quality.csv", "trend_clarity_momentum_score_tradable"),
    "breadth_confirmed_momentum": ("signal_breadth_confirmation.csv", "breadth_confirmed_momentum_score_tradable"),
    "moving_average_distance": ("signal_moving_average_distance.csv", "moving_average_distance_score_tradable"),
}
for signal_name, (file_name, value_col) in phase_a_signal_specs.items():
    panel = load_layer1_signal_panel(file_name, value_col)
    if not panel.empty:
        ns3["baseline_signal_panels"][signal_name] = panel


selective_signal_names = signal_subset_specs["core4_bab_carry"]
trend_ensemble_signal_names = [
    "xsmom_global",
    "multi_mom_equal",
    "multi_mom_invvol",
    "tsmom_vol_scaled",
    "quality_proxy",
    "value_proxy",
    "bab_proxy",
    "carry_proxy",
]
trend_quality_signal_names = [
    "xsmom_global",
    "multi_mom_invvol",
    "tsmom_vol_scaled",
    "trend_clarity_momentum",
]
confirmation_signal_names = [
    "xsmom_global",
    "multi_mom_invvol",
    "breadth_confirmed_momentum",
]
trend_quality_refined_signal_names = [
    "xsmom_global",
    "multi_mom_invvol",
    "tsmom_vol_scaled",
    "trend_clarity_momentum",
    "moving_average_distance",
]
selective_weights, selective_path, selective_metrics = evaluate_signal_combo(selective_signal_names)
strength_weighted_weights, strength_weighted_path, strength_weighted_metrics = evaluate_signal_combo(
    selective_signal_names,
    weight_mode="strength_weighted",
    strength_power=1.35,
)
concentrated_weights, concentrated_path, concentrated_metrics = evaluate_signal_combo(selective_signal_names, top_n=3, min_signal=0.05)
trend_ensemble_weights, trend_ensemble_path, trend_ensemble_metrics = evaluate_signal_combo(trend_ensemble_signal_names)
trend_quality_weights, trend_quality_path, trend_quality_metrics = evaluate_signal_combo(
    trend_quality_signal_names,
    top_n=4,
    min_signal=0.05,
)
confirmation_weights, confirmation_path, confirmation_metrics = evaluate_signal_combo(
    confirmation_signal_names,
    top_n=4,
    min_signal=0.05,
)
trend_quality_refined_weights, trend_quality_refined_path, trend_quality_refined_metrics = evaluate_signal_combo(
    trend_quality_refined_signal_names,
    top_n=4,
    min_signal=0.05,
)
selective_strategy_name = "composite_selective_signals"
strength_weighted_strategy_name = "composite_selective_strength_weighted"
concentrated_strategy_name = "composite_selective_concentrated"
trend_ensemble_strategy_name = "composite_selective_trend_ensemble"
trend_quality_strategy_name = "composite_trend_quality_module"
confirmation_strategy_name = "composite_confirmation_aware_momentum"
trend_quality_refined_strategy_name = "composite_trend_quality_refined"

selective_summary = ns3["summary_metrics"](selective_path["net_return"], turnover_series=selective_path["turnover"])
selective_summary.update(
    {
        "strategy_name": selective_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            selective_summary["sharpe"]
            + 0.5 * selective_summary["calmar"]
            + 0.2 * selective_summary["hit_rate"]
            - 0.1 * selective_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    selective_strategy_name,
    selective_weights,
    selective_path,
    selective_summary,
    {
        "strategy_name": selective_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{selective_strategy_name}.csv",
            f"strategy_returns_{selective_strategy_name}.csv",
        ],
        "caveats": "Selective composite keeps the signals that improved the long-only ETF sleeve most cleanly in the incremental study; it is still a practical top-N proxy rather than a fully optimized ensemble.",
        "description": "Top-N long-only strategy using the selective signal blend that retained trend, quality/value, BAB, and carry while excluding weaker add-ons.",
    },
)

trend_ensemble_summary = ns3["summary_metrics"](trend_ensemble_path["net_return"], turnover_series=trend_ensemble_path["turnover"])
trend_ensemble_summary.update(
    {
        "strategy_name": trend_ensemble_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            trend_ensemble_summary["sharpe"]
            + 0.5 * trend_ensemble_summary["calmar"]
            + 0.2 * trend_ensemble_summary["hit_rate"]
            - 0.1 * trend_ensemble_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    trend_ensemble_strategy_name,
    trend_ensemble_weights,
    trend_ensemble_path,
    trend_ensemble_summary,
    {
        "strategy_name": trend_ensemble_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_tsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; multi-horizon trend signals remain lagged and are combined with the same monthly rebalance schedule as the incumbent selective sleeve.",
        "output_files": [
            f"strategy_positions_{trend_ensemble_strategy_name}.csv",
            f"strategy_returns_{trend_ensemble_strategy_name}.csv",
        ],
        "caveats": "Minimal conditional test only. This adds a simple fast/slow trend ensemble to the incumbent selective sleeve rather than redesigning Layer 1 from scratch, and it should only survive if it adds value beyond the existing momentum complex.",
        "description": "Top-N long-only sleeve that augments the incumbent selective blend with a simple multi-horizon trend ensemble (cross-sectional momentum, multi-horizon momentum, and time-series momentum).",
    },
)

trend_quality_summary = ns3["summary_metrics"](trend_quality_path["net_return"], turnover_series=trend_quality_path["turnover"])
trend_quality_summary.update(
    {
        "strategy_name": trend_quality_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            trend_quality_summary["sharpe"]
            + 0.5 * trend_quality_summary["calmar"]
            + 0.2 * trend_quality_summary["hit_rate"]
            - 0.1 * trend_quality_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    trend_quality_strategy_name,
    trend_quality_weights,
    trend_quality_path,
    trend_quality_summary,
    {
        "strategy_name": trend_quality_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_tsmom.csv",
            "signal_trend_quality.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals only; trend-clarity score is computed from lagged prices and passed through the standard monthly rebalance schedule.",
        "output_files": [
            f"strategy_positions_{trend_quality_strategy_name}.csv",
            f"strategy_returns_{trend_quality_strategy_name}.csv",
        ],
        "caveats": "Phase B trend-quality module: a cleaner offensive trend sleeve, not a wholesale regime overlay. It should only survive if calmer / confirmed trend participation improves without simply becoming a higher-beta rewrite of the existing selective sleeve.",
        "description": "Top-N long-only trend-quality sleeve that combines cross-sectional momentum, multi-horizon momentum, time-series momentum, and trend-clarity to emphasize cleaner, less choppy trends.",
    },
)

confirmation_summary = ns3["summary_metrics"](confirmation_path["net_return"], turnover_series=confirmation_path["turnover"])
confirmation_summary.update(
    {
        "strategy_name": confirmation_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            confirmation_summary["sharpe"]
            + 0.5 * confirmation_summary["calmar"]
            + 0.2 * confirmation_summary["hit_rate"]
            - 0.1 * confirmation_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    confirmation_strategy_name,
    confirmation_weights,
    confirmation_path,
    confirmation_summary,
    {
        "strategy_name": confirmation_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_breadth_confirmation.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals only; breadth confirmation is lagged and used as an activation-quality input inside the sleeve rather than as a top-level overlay.",
        "output_files": [
            f"strategy_positions_{confirmation_strategy_name}.csv",
            f"strategy_returns_{confirmation_strategy_name}.csv",
        ],
        "caveats": "Phase B confirmation-aware sleeve: intended to express safer improving-state offense when momentum has broader confirmation. It is not a crash canary and should only survive if it adds distinct participation quality.",
        "description": "Top-N long-only sleeve that combines momentum with breadth-confirmed momentum so offensive deployment is strongest when cross-asset participation confirms the setup.",
    },
)

trend_quality_refined_summary = ns3["summary_metrics"](trend_quality_refined_path["net_return"], turnover_series=trend_quality_refined_path["turnover"])
trend_quality_refined_summary.update(
    {
        "strategy_name": trend_quality_refined_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            trend_quality_refined_summary["sharpe"]
            + 0.5 * trend_quality_refined_summary["calmar"]
            + 0.2 * trend_quality_refined_summary["hit_rate"]
            - 0.1 * trend_quality_refined_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    trend_quality_refined_strategy_name,
    trend_quality_refined_weights,
    trend_quality_refined_path,
    trend_quality_refined_summary,
    {
        "strategy_name": trend_quality_refined_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_tsmom.csv",
            "signal_trend_quality.csv",
            "signal_moving_average_distance.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals only; moving-average distance is treated as a refinement feature, not a separate overlay or timing layer.",
        "output_files": [
            f"strategy_positions_{trend_quality_refined_strategy_name}.csv",
            f"strategy_returns_{trend_quality_refined_strategy_name}.csv",
        ],
        "caveats": "Phase B refinement-only sleeve: moving-average distance is only allowed to stay if it materially improves the simpler trend-quality module. Otherwise it is just a redundant feature.",
        "description": "Refined trend-quality sleeve that augments the trend-quality module with moving-average distance as a setup-quality feature.",
    },
)

strength_weighted_summary = ns3["summary_metrics"](strength_weighted_path["net_return"], turnover_series=strength_weighted_path["turnover"])
strength_weighted_summary.update(
    {
        "strategy_name": strength_weighted_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            strength_weighted_summary["sharpe"]
            + 0.5 * strength_weighted_summary["calmar"]
            + 0.2 * strength_weighted_summary["hit_rate"]
            - 0.1 * strength_weighted_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    strength_weighted_strategy_name,
    strength_weighted_weights,
    strength_weighted_path,
    strength_weighted_summary,
    {
        "strategy_name": strength_weighted_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{strength_weighted_strategy_name}.csv",
            f"strategy_returns_{strength_weighted_strategy_name}.csv",
        ],
        "caveats": "This keeps the same selective signal blend and top-N universe as the incumbent sleeve, but weights selected ETFs by normalized signal strength so strong setups can express more than merely weak-positive ones.",
        "description": "Top-N long-only sleeve that uses the selective signal blend while scaling chosen ETF weights by normalized composite signal strength rather than equal slots.",
    },
)

concentrated_summary = ns3["summary_metrics"](concentrated_path["net_return"], turnover_series=concentrated_path["turnover"])
concentrated_summary.update(
    {
        "strategy_name": concentrated_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            concentrated_summary["sharpe"]
            + 0.5 * concentrated_summary["calmar"]
            + 0.2 * concentrated_summary["hit_rate"]
            - 0.1 * concentrated_summary["avg_weekly_turnover"]
        ),
    }
)
register_strategy_output(
    concentrated_strategy_name,
    concentrated_weights,
    concentrated_path,
    concentrated_summary,
    {
        "strategy_name": concentrated_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{concentrated_strategy_name}.csv",
            f"strategy_returns_{concentrated_strategy_name}.csv",
        ],
        "caveats": "This is a more selective offensive sleeve for upside-capture testing. It is only promoted if better upside participation survives the drawdown and turnover checks.",
        "description": "A more concentrated top-3 version of the selective signal sleeve, used as a disciplined upside-capture test rather than a new default.",
    },
)

market_state_history = build_market_state_history()


def build_internal_redeployed_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    market_state_hist: pd.DataFrame,
    *,
    target_sleeves: list[str],
    redeploy_config: dict[str, float] | None = None,
    strong_neutral_fraction: float = 0.30,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Phase 1 Variant D: reduce per-sleeve internal BIL in favorable states
    and redistribute to the sleeve's existing risky picks proportionally.
    Recompute sleeve returns via the canonical compute_strategy_path so
    transaction costs and cash accrual stay consistent.

    Rules:
      - Only target sleeves in `target_sleeves`; others untouched.
      - Redeploy fraction is state-dependent (see defaults).
      - 100% BIL rows are preserved (no_signal defensive role untouched).
      - Redistribution is proportional to each risky pick's existing weight.
      - No hindsight: redeploy decisions use only the market_state at date t.
    """
    if redeploy_config is None:
        redeploy_config = {
            "recovery_fragile": 0.30,
            "recovery_confirmed": 0.20,
            "calm_trend": 0.40,
        }
    cash_proxy = ns5["cash_proxy"]
    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    state_hist = market_state_hist.reindex(base_return_panel.index)

    for sleeve_name in target_sleeves:
        if sleeve_name not in new_positions:
            continue
        positions = new_positions[sleeve_name].copy()
        if cash_proxy not in positions.columns:
            continue
        modified = positions.copy()
        for date, row in positions.iterrows():
            if date not in state_hist.index:
                continue
            state_row = state_hist.loc[date]
            market_state = str(state_row.get("market_state") or "")
            strong_neutral = is_strong_neutral_state_row(state_row)
            redeploy_fraction = 0.0
            if strong_neutral:
                redeploy_fraction = strong_neutral_fraction
            elif market_state in redeploy_config:
                redeploy_fraction = redeploy_config[market_state]
            if redeploy_fraction <= 0.0:
                continue
            bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
            if bil_weight <= 0.0:
                continue
            risky_row = row.drop(cash_proxy) if cash_proxy in row.index else row
            risky_sum = float(risky_row.sum())
            if risky_sum <= 1e-9:
                # 100% BIL row: preserve defensive role (no-signal state).
                continue
            bil_shift = bil_weight * redeploy_fraction
            new_bil = bil_weight - bil_shift
            modified.at[date, cash_proxy] = new_bil
            for col in risky_row.index:
                w = float(risky_row.get(col, 0.0) or 0.0)
                if w > 0.0:
                    modified.at[date, col] = w + bil_shift * (w / risky_sum)
        new_positions[sleeve_name] = modified
        path = ns3["compute_strategy_path"](
            modified,
            ns3["next_week_returns"],
            transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
            cash_proxy_returns=ns3["cash_proxy_return_series"],
        )
        new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)

    return new_return_panel, new_positions


def build_favorable_fallback_redesign_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    market_state_hist: pd.DataFrame,
    *,
    sleeve_name: str,
    favorable_keep_bil_fraction: float,
    fallback_mix: dict[str, float],
    apply_market_states: set[str] | None = None,
    apply_strong_neutral: bool = True,
    target_bil_tier: float = 0.25,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Directly redesign the sleeve's favorable-state 25% cash fallback.

    Rules:
      - Only the named sleeve is modified.
      - Only rows on the target favorable-state BIL tier are modified
        (default 25% BIL). The stressed 65% tier is untouched.
      - Only specified market states and/or strong-neutral proxy weeks are
        eligible.
      - Shifted BIL is reallocated into the provided fallback ETF mix, which
        may add weight to ETFs that are already in the sleeve universe.
      - Recompute sleeve returns through the canonical compute_strategy_path.
    """
    if apply_market_states is None:
        apply_market_states = {"calm_trend", "recovery_confirmed", "recovery_fragile"}
    cash_proxy = ns5["cash_proxy"]
    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    state_hist = market_state_hist.reindex(base_return_panel.index)

    if sleeve_name not in new_positions:
        return new_return_panel, new_positions
    positions = new_positions[sleeve_name].copy()
    if cash_proxy not in positions.columns:
        return new_return_panel, new_positions

    available_mix = {etf: float(weight) for etf, weight in fallback_mix.items() if etf in positions.columns and etf != cash_proxy and float(weight) > 0.0}
    mix_sum = float(sum(available_mix.values()))
    if mix_sum <= 0.0:
        return new_return_panel, new_positions

    modified = positions.copy()
    for date, row in positions.iterrows():
        if date not in state_hist.index:
            continue
        state_row = state_hist.loc[date]
        market_state = str(state_row.get("market_state") or "")
        strong_neutral = is_strong_neutral_state_row(state_row)
        should_apply = market_state in apply_market_states or (apply_strong_neutral and strong_neutral)
        if not should_apply:
            continue
        bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
        if abs(bil_weight - target_bil_tier) > 1e-9:
            continue
        new_bil = bil_weight * favorable_keep_bil_fraction
        bil_shift = bil_weight - new_bil
        if bil_shift <= 0.0:
            continue
        modified.at[date, cash_proxy] = new_bil
        for etf, weight in available_mix.items():
            modified.at[date, etf] = float(modified.at[date, etf]) + bil_shift * (weight / mix_sum)

    new_positions[sleeve_name] = modified
    path = ns3["compute_strategy_path"](
        modified,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    return new_return_panel, new_positions


def build_state_filtered_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    market_state_hist: pd.DataFrame,
    *,
    sleeve_name: str,
    state_filter_cols: dict[str, list[str]],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """State-condition one sleeve's internal ETF lookthrough by filtering columns.

    Used only for narrow diagnostics: per eligible state, project the sleeve's
    existing ETF weights onto a smaller existing ETF subset and recompute the
    sleeve path. No allocator weights are reconstructed post hoc.
    """
    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    if sleeve_name not in new_positions:
        return new_return_panel, new_positions
    cash_proxy = ns5["cash_proxy"]
    positions = new_positions[sleeve_name].copy().reindex(
        index=ns5["weekly_prices"].index,
        columns=ns5["weekly_prices"].columns,
    ).fillna(0.0)
    state_hist = market_state_hist.reindex(positions.index)
    modified = positions.copy()
    for date, row in positions.iterrows():
        if date not in state_hist.index:
            continue
        market_state = str(state_hist.loc[date].get("market_state") or "")
        keep_cols = [c for c in state_filter_cols.get(market_state, []) if c in positions.columns]
        if not keep_cols:
            continue
        kept_sum = float(row.reindex(keep_cols).fillna(0.0).sum())
        if kept_sum <= 1e-12:
            modified.loc[date, :] = 0.0
            modified.at[date, cash_proxy] = 1.0
            continue
        modified.loc[date, :] = 0.0
        modified.loc[date, keep_cols] = row.reindex(keep_cols).fillna(0.0) / kept_sum
    new_positions[sleeve_name] = modified
    path = ns3["compute_strategy_path"](
        modified,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    return new_return_panel, new_positions


def build_action_directed_fallback_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    market_state_hist: pd.DataFrame,
    action_frame: pd.DataFrame,
    *,
    sleeve_name: str,
    action_col: str,
    action_map: dict[str, dict[str, object]],
    apply_market_states: set[str] | None = None,
    apply_strong_neutral: bool = True,
    target_bil_tier: float = 0.25,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Apply precomputed causal action labels to favorable-state BIL rows."""
    if apply_market_states is None:
        apply_market_states = {"calm_trend", "recovery_confirmed", "recovery_fragile"}
    cash_proxy = ns5["cash_proxy"]
    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    state_hist = market_state_hist.reindex(base_return_panel.index)

    if sleeve_name not in new_positions or action_col not in action_frame.columns:
        return new_return_panel, new_positions
    positions = new_positions[sleeve_name].copy()
    if cash_proxy not in positions.columns:
        return new_return_panel, new_positions

    action_lookup = action_frame.copy()
    action_lookup.index = pd.to_datetime(action_lookup.index)
    action_lookup = action_lookup.reindex(positions.index)
    modified = positions.copy()

    for date, row in positions.iterrows():
        if date not in state_hist.index or date not in action_lookup.index:
            continue
        state_row = state_hist.loc[date]
        market_state = str(state_row.get("market_state") or "")
        strong_neutral = is_strong_neutral_state_row(state_row)
        should_apply = market_state in apply_market_states or (apply_strong_neutral and strong_neutral)
        if not should_apply:
            continue
        bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
        if abs(bil_weight - target_bil_tier) > 1e-9:
            continue
        action_name = str(action_lookup.at[date, action_col] or "").strip()
        action_spec = action_map.get(action_name)
        if not action_spec:
            continue

        keep_bil_fraction = float(action_spec.get("keep_bil_fraction", 1.0))
        bil_shift = bil_weight * max(0.0, 1.0 - keep_bil_fraction)
        if bil_shift <= 0.0:
            continue
        modified.at[date, cash_proxy] = bil_weight - bil_shift

        kind = str(action_spec.get("kind", "mix"))
        if kind == "active":
            risky_row = row.drop(cash_proxy, errors="ignore")
            risky_sum = float(risky_row.sum())
            if risky_sum <= 1e-9:
                modified.at[date, cash_proxy] = bil_weight
                continue
            for col in risky_row.index:
                w = float(risky_row.get(col, 0.0) or 0.0)
                if w > 0.0:
                    modified.at[date, col] = w + bil_shift * (w / risky_sum)
            continue

        fallback_mix = {
            etf: float(weight)
            for etf, weight in dict(action_spec.get("fallback_mix", {})).items()
            if etf in positions.columns and etf != cash_proxy and float(weight) > 0.0
        }
        mix_sum = float(sum(fallback_mix.values()))
        if mix_sum <= 0.0:
            modified.at[date, cash_proxy] = bil_weight
            continue
        for etf, weight in fallback_mix.items():
            modified.at[date, etf] = float(modified.at[date, etf]) + bil_shift * (weight / mix_sum)

    new_positions[sleeve_name] = modified
    path = ns3["compute_strategy_path"](
        modified,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    return new_return_panel, new_positions


def build_composite_decomposition_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    *,
    offense_cols_override: list[str] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Create explicit offense / defense / cash sleeves from the composite.

    This is a causal decomposition of the existing composite ETF positions,
    not a new alpha model. The allocator can then decide offense, defense,
    and cash explicitly instead of inheriting a hidden mix from the composite
    sleeve.

    Phase FFF: optional `offense_cols_override` lets us re-engineer the
    offense_component by filtering the source ETF list (e.g., dropping weak
    commodity/Japan exposures).
    """
    source_name = "composite_regime_conditioned"
    cash_proxy = ns5["cash_proxy"]
    default_offense = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
    offense_list = offense_cols_override if offense_cols_override is not None else default_offense
    offense_cols = [c for c in offense_list if c in ns5["weekly_prices"].columns]
    defense_cols = [c for c in ["HYG", "LQD", "GLD", "TLT"] if c in ns5["weekly_prices"].columns]

    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    if source_name not in base_positions:
        return new_return_panel, new_positions

    source_positions = base_positions[source_name].copy().reindex(
        index=ns5["weekly_prices"].index,
        columns=ns5["weekly_prices"].columns,
    ).fillna(0.0)

    component_specs = {
        "composite_regime_offense_component": offense_cols,
        "composite_regime_defense_component": defense_cols,
    }
    for sleeve_name, cols in component_specs.items():
        component_positions = pd.DataFrame(0.0, index=source_positions.index, columns=source_positions.columns)
        component_sum = source_positions.reindex(columns=cols).sum(axis=1)
        active_mask = component_sum > 1e-12
        if cols:
            component_positions.loc[active_mask, cols] = source_positions.loc[active_mask, cols].div(component_sum.loc[active_mask], axis=0)
        component_positions.loc[~active_mask, cash_proxy] = 1.0
        path = ns3["compute_strategy_path"](
            component_positions,
            ns3["next_week_returns"],
            transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
            cash_proxy_returns=ns3["cash_proxy_return_series"],
        )
        new_positions[sleeve_name] = component_positions
        new_return_panel[sleeve_name] = path["net_return"].reindex(new_return_panel.index).fillna(0.0)

    cash_positions = pd.DataFrame(0.0, index=source_positions.index, columns=source_positions.columns)
    cash_positions[cash_proxy] = 1.0
    cash_path = ns3["compute_strategy_path"](
        cash_positions,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_positions["composite_regime_cash_component"] = cash_positions
    new_return_panel["composite_regime_cash_component"] = cash_path["net_return"].reindex(new_return_panel.index).fillna(0.0)

    return new_return_panel, new_positions


def build_state_conditional_decomposition_sleeve_panels(
    base_return_panel: pd.DataFrame,
    base_positions: dict[str, pd.DataFrame],
    *,
    default_offense_cols: list[str],
    state_offense_recipe: dict[str, list[tuple[list[str], float]]],
    market_state_series: pd.Series,
    state_defense_recipe: dict[str, list[tuple[list[str], float]]] | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Phase GGG: state-conditional composite_regime_offense_component.

    Like ``build_composite_decomposition_sleeve_panels`` but allows the
    offense ETF subset to vary by ``market_state``. ``state_offense_recipe``
    maps state -> list of ``(cols, weight)`` pairs. For dates whose state is
    not in the recipe, the default offense cols are used (weight 1.0).

    For each date and each recipe element ``(cols, w)``: re-project source
    positions onto ``cols`` (per-row sum-1 normalisation), then linearly
    blend by weights and renormalise so each output row sums to 1 over the
    contributing columns. Defense and cash components are unchanged unless
    ``state_defense_recipe`` is supplied.
    """
    source_name = "composite_regime_conditioned"
    cash_proxy = ns5["cash_proxy"]
    defense_cols = [c for c in ["HYG", "LQD", "GLD", "TLT"] if c in ns5["weekly_prices"].columns]

    new_return_panel = base_return_panel.copy()
    new_positions = {k: v.copy() for k, v in base_positions.items()}
    if source_name not in base_positions:
        return new_return_panel, new_positions

    source_positions = base_positions[source_name].copy().reindex(
        index=ns5["weekly_prices"].index,
        columns=ns5["weekly_prices"].columns,
    ).fillna(0.0)

    states = market_state_series.reindex(source_positions.index).fillna("__default__")
    default_recipe = [(default_offense_cols, 1.0)]

    def _state_project_component(
        *,
        default_cols: list[str],
        state_recipe: dict[str, list[tuple[list[str], float]]],
    ) -> pd.DataFrame:
        out_positions = pd.DataFrame(0.0, index=source_positions.index, columns=source_positions.columns)
        default_local = [(default_cols, 1.0)]
        for state_name, dates_idx in states.groupby(states).groups.items():
            recipe = state_recipe.get(state_name, default_local)
            sub_blended = pd.DataFrame(0.0, index=dates_idx, columns=source_positions.columns)
            weight_total = pd.Series(0.0, index=dates_idx)
            for cols, weight in recipe:
                cols = [c for c in cols if c in source_positions.columns]
                if not cols or weight <= 0:
                    continue
                sub = source_positions.loc[dates_idx, cols]
                sub_sum = sub.sum(axis=1)
                active = sub_sum > 1e-12
                if active.any():
                    norm = sub.loc[active].div(sub_sum.loc[active], axis=0)
                    active_dates = norm.index
                    sub_blended.loc[active_dates, cols] = (
                        sub_blended.loc[active_dates, cols].add(norm * weight, fill_value=0.0)
                    )
                    weight_total.loc[active_dates] += weight
            positive = weight_total > 1e-12
            if positive.any():
                sub_blended.loc[positive] = sub_blended.loc[positive].div(weight_total.loc[positive], axis=0)
            inactive = ~positive
            if inactive.any():
                sub_blended.loc[inactive, :] = 0.0
                sub_blended.loc[inactive, cash_proxy] = 1.0
            out_positions.loc[dates_idx, :] = sub_blended.values
        return out_positions

    offense_positions = _state_project_component(
        default_cols=default_offense_cols,
        state_recipe=state_offense_recipe,
    )

    offense_path = ns3["compute_strategy_path"](
        offense_positions,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_positions["composite_regime_offense_component"] = offense_positions
    new_return_panel["composite_regime_offense_component"] = (
        offense_path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    )

    defense_positions = _state_project_component(
        default_cols=defense_cols,
        state_recipe=state_defense_recipe or {},
    )
    defense_path = ns3["compute_strategy_path"](
        defense_positions,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_positions["composite_regime_defense_component"] = defense_positions
    new_return_panel["composite_regime_defense_component"] = (
        defense_path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    )

    # Cash component (unchanged)
    cash_positions = pd.DataFrame(0.0, index=source_positions.index, columns=source_positions.columns)
    cash_positions[cash_proxy] = 1.0
    cash_path = ns3["compute_strategy_path"](
        cash_positions,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    new_positions["composite_regime_cash_component"] = cash_positions
    new_return_panel["composite_regime_cash_component"] = (
        cash_path["net_return"].reindex(new_return_panel.index).fillna(0.0)
    )

    return new_return_panel, new_positions


strategy_lookup = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
strategy_lookup = strategy_lookup.set_index("strategy_name") if not strategy_lookup.empty else pd.DataFrame().set_index(pd.Index([], name="strategy_name"))

base_sleeve_return_panel = ns5["sleeve_return_panel"].copy()
base_sleeve_positions = dict(ns5["sleeve_positions"])
base_sleeve_return_panel[selective_strategy_name] = selective_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[selective_strategy_name] = selective_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[strength_weighted_strategy_name] = strength_weighted_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[strength_weighted_strategy_name] = strength_weighted_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[concentrated_strategy_name] = concentrated_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[concentrated_strategy_name] = concentrated_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[trend_ensemble_strategy_name] = trend_ensemble_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[trend_ensemble_strategy_name] = trend_ensemble_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[trend_quality_strategy_name] = trend_quality_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[trend_quality_strategy_name] = trend_quality_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[confirmation_strategy_name] = confirmation_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[confirmation_strategy_name] = confirmation_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)
base_sleeve_return_panel[trend_quality_refined_strategy_name] = trend_quality_refined_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[trend_quality_refined_strategy_name] = trend_quality_refined_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)

# Phase 3 Variant A1: register sector_rotation_with_sma_filter into the base
# sleeve panel so it can be selected by the richer-sleeve Phase 3 subsets.
# Loaded from the layer 2A strategy outputs (same path the other sleeves use).
_phase3_sector_name = "sector_rotation_with_sma_filter"
if _phase3_sector_name not in base_sleeve_return_panel.columns:
    _phase3_sector_returns_path = LAYER2A_DIR / f"strategy_returns_{_phase3_sector_name}.csv"
    _phase3_sector_positions_path = LAYER2A_DIR / f"strategy_positions_{_phase3_sector_name}.csv"
    if _phase3_sector_returns_path.exists():
        _phase3_sector_returns_df = pd.read_csv(_phase3_sector_returns_path, index_col=0, parse_dates=True)
        _col = "net_return" if "net_return" in _phase3_sector_returns_df.columns else _phase3_sector_returns_df.columns[0]
        base_sleeve_return_panel[_phase3_sector_name] = (
            _phase3_sector_returns_df[_col].reindex(base_sleeve_return_panel.index).fillna(0.0)
        )
    if _phase3_sector_positions_path.exists():
        _phase3_sector_positions_df = pd.read_csv(_phase3_sector_positions_path, index_col=0, parse_dates=True)
        base_sleeve_positions[_phase3_sector_name] = _phase3_sector_positions_df.reindex(
            index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns
        ).fillna(0.0)

# Phase 4 sector rotation sleeves are generated by
# scripts/phase_4_sector_breadth_rotation.py before the filtered build runs.
# Loading them here keeps portfolio construction on the canonical cost/path
# model while allowing the research script to own the causal sector signals.
_phase4_dir = ROOT / "data" / "research" / "phase_4_sector_breadth_rotation"
_phase4_signal_path = _phase4_dir / "phase4_sector_rotation_signal_panel.csv"
if _phase4_signal_path.exists():
    _phase4_signal_df = pd.read_csv(_phase4_signal_path, index_col=0, parse_dates=True)
    _phase4_signal_df.index = pd.to_datetime(_phase4_signal_df.index).tz_localize(None)
    PHASE4_SIGNAL_LOOKUPS = {
        col: _phase4_signal_df[col].fillna(0).to_dict()
        for col in _phase4_signal_df.columns
        if col not in {"market_state", "risk_state", "signal_environment"}
    }

for _phase4_sleeve_name in [
    "phase4_equal_weight_sector_sleeve",
    "phase4_top3_sector_momentum_sleeve",
    "phase4_top5_sector_momentum_sleeve",
    "phase4_risk_adjusted_top3_sleeve",
    "phase4_balanced_sector_breadth_sleeve",
    "phase4_stretch_sector_momentum_sleeve",
]:
    _phase4_weights_path = _phase4_dir / f"phase4_build_sleeve_weights_{_phase4_sleeve_name}.csv"
    if not _phase4_weights_path.exists():
        continue
    _phase4_weights = pd.read_csv(_phase4_weights_path, index_col=0, parse_dates=True)
    _phase4_weights.index = pd.to_datetime(_phase4_weights.index).tz_localize(None)
    _phase4_weights = _phase4_weights.reindex(
        index=ns5["weekly_prices"].index,
        columns=ns5["weekly_prices"].columns,
    ).fillna(0.0)
    _phase4_path = ns3["compute_strategy_path"](
        _phase4_weights,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    base_sleeve_positions[_phase4_sleeve_name] = _phase4_weights
    base_sleeve_return_panel[_phase4_sleeve_name] = (
        _phase4_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
    )

# Phase 4B refined sector rotation sleeves are generated by
# scripts/phase_4b_refined_sector_rotation.py. They are loaded into the same
# canonical sleeve/path machinery as Phase 4 so filtered builds only need the
# requested candidate names.
_phase4b_dir = ROOT / "data" / "research" / "phase_4b_refined_sector_rotation"
_phase4b_signal_path = _phase4b_dir / "phase4b_refined_sector_signal_panel.csv"
if _phase4b_signal_path.exists():
    _phase4b_signal_df = pd.read_csv(_phase4b_signal_path, index_col=0, parse_dates=True)
    _phase4b_signal_df.index = pd.to_datetime(_phase4b_signal_df.index).tz_localize(None)
    PHASE4B_SIGNAL_LOOKUPS = {
        col: _phase4b_signal_df[col].fillna(0).to_dict()
        for col in _phase4b_signal_df.columns
        if col not in {"market_state", "risk_state", "signal_environment"}
    }

for _phase4b_sleeve_name in [
    "phase4b_top5_smooth_sector_sleeve",
    "phase4b_top4_risk_adjusted_sector_sleeve",
    "phase4b_top3_strict_sector_sleeve",
    "phase4b_defensive_aware_top5_sleeve",
    "phase4b_sector_blend_spy_qqq_sleeve",
    "phase4b_balanced_carry_forward_sleeve",
]:
    _phase4b_weights_path = _phase4b_dir / f"phase4b_build_sleeve_weights_{_phase4b_sleeve_name}.csv"
    if not _phase4b_weights_path.exists():
        continue
    _phase4b_weights = pd.read_csv(_phase4b_weights_path, index_col=0, parse_dates=True)
    _phase4b_weights.index = pd.to_datetime(_phase4b_weights.index).tz_localize(None)
    _phase4b_weights = _phase4b_weights.reindex(
        index=ns5["weekly_prices"].index,
        columns=ns5["weekly_prices"].columns,
    ).fillna(0.0)
    _phase4b_path = ns3["compute_strategy_path"](
        _phase4b_weights,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    base_sleeve_positions[_phase4b_sleeve_name] = _phase4b_weights
    base_sleeve_return_panel[_phase4b_sleeve_name] = (
        _phase4b_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
    )

# Phase 1 Variant D: build redeployed sleeve panels once, used only by the
# Variant D version_spec (and any combo that consumes it). Other variants
# continue to use `base_sleeve_return_panel` / `base_sleeve_positions`.
redeploy_target_sleeves = ["composite_regime_conditioned", "dual_momentum_topn", "cta_trend_long_only"]
redeployed_sleeve_return_panel, redeployed_sleeve_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=redeploy_target_sleeves,
)

# Restricted redeploy for combos: drops recovery_confirmed (where standalone
# Variant D hurt badly) and keeps strong_neutral / recovery_fragile / calm
# redeploy. Used by Combo G.
redeployed_restricted_return_panel, redeployed_restricted_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=redeploy_target_sleeves,
    redeploy_config={
        "recovery_fragile": 0.25,
        "calm_trend": 0.35,
        # recovery_confirmed intentionally omitted — standalone Variant D
        # showed recovery_confirmed_capture collapse from 41% -> 29%.
    },
    strong_neutral_fraction=0.25,
)

# Phase NN — narrow sleeve-to-ETF / lookthrough relief panels.
# These panels reduce internal sleeve-level BIL only in the specific states
# and sleeves identified by the Phase MM audit as major hidden-cash sources.
phasenn_recovery_return_panel, phasenn_recovery_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned", "dual_momentum_topn"],
    redeploy_config={
        "recovery_fragile": 0.20,
        "recovery_confirmed": 0.18,
    },
    strong_neutral_fraction=0.0,
)
phasenn_neutral_return_panel, phasenn_neutral_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned"],
    redeploy_config={},
    strong_neutral_fraction=0.12,
)
phasenn_combo_return_panel, phasenn_combo_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned", "dual_momentum_topn"],
    redeploy_config={
        "recovery_fragile": 0.18,
        "recovery_confirmed": 0.15,
    },
    strong_neutral_fraction=0.0,
)

# Phase OO — composite_regime_conditioned sleeve-internal cash architecture
# audit. Composite-only internal BIL relief, preserving stressed-panic.
phaseoo_recovery_return_panel, phaseoo_recovery_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned"],
    redeploy_config={
        "recovery_fragile": 0.24,
        "recovery_confirmed": 0.18,
    },
    strong_neutral_fraction=0.0,
)
phaseoo_neutral_return_panel, phaseoo_neutral_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned"],
    redeploy_config={},
    strong_neutral_fraction=0.16,
)
phaseoo_combo_return_panel, phaseoo_combo_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned"],
    redeploy_config={
        "recovery_fragile": 0.20,
        "recovery_confirmed": 0.15,
    },
    strong_neutral_fraction=0.10,
)

# Phase PP — direct redesign of composite_regime_conditioned's favorable-state
# 25% BIL fallback tier. Preserve the stressed 65% tier.
phasepp_bond_gold_return_panel, phasepp_bond_gold_positions = build_favorable_fallback_redesign_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    sleeve_name="composite_regime_conditioned",
    favorable_keep_bil_fraction=0.50,
    fallback_mix={"GLD": 0.50, "TLT": 0.50},
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)
phasepp_balanced_return_panel, phasepp_balanced_positions = build_favorable_fallback_redesign_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    sleeve_name="composite_regime_conditioned",
    favorable_keep_bil_fraction=0.45,
    fallback_mix={"GLD": 0.35, "TLT": 0.30, "LQD": 0.20, "HYG": 0.15},
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)
phasepp_combo_base_return_panel, phasepp_combo_base_positions = build_internal_redeployed_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    target_sleeves=["composite_regime_conditioned"],
    redeploy_config={
        "recovery_fragile": 0.20,
        "recovery_confirmed": 0.15,
    },
    strong_neutral_fraction=0.10,
)
phasepp_combo_return_panel, phasepp_combo_positions = build_favorable_fallback_redesign_sleeve_panels(
    phasepp_combo_base_return_panel,
    phasepp_combo_base_positions,
    market_state_history,
    sleeve_name="composite_regime_conditioned",
    favorable_keep_bil_fraction=0.50,
    fallback_mix={"GLD": 0.50, "TLT": 0.50},
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)

# Phase QQ — causal cash-defense score redesign for composite_regime_conditioned.
# The audit script writes per-date action labels consumed here; without the
# action file these fall back to the unmodified base panels.
phaseqq_dir = ROOT / "data" / "research" / "phase_qq_composite_cash_reason_score"
phaseqq_action_path = phaseqq_dir / "phase_qq_cash_defense_score.csv"
if phaseqq_action_path.exists():
    phaseqq_action_frame = pd.read_csv(phaseqq_action_path, parse_dates=["Date"]).set_index("Date").sort_index()
else:
    phaseqq_action_frame = pd.DataFrame()

phaseqq_score_action_map = {
    "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
    "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.75, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
    "low_mix": {"kind": "mix", "keep_bil_fraction": 0.50, "fallback_mix": {"GLD": 0.50, "TLT": 0.30, "LQD": 0.20}},
}
phaseqq_reason_action_map = {
    "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
    "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.80, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
    "low_mix": {"kind": "mix", "keep_bil_fraction": 0.60, "fallback_mix": {"GLD": 0.40, "TLT": 0.35, "LQD": 0.15, "HYG": 0.10}},
    "active_redeploy": {"kind": "active", "keep_bil_fraction": 0.55},
}
phaseqq_ppfiltered_action_map = {
    "keep": {"kind": "mix", "keep_bil_fraction": 1.00, "fallback_mix": {}},
    "medium_mix": {"kind": "mix", "keep_bil_fraction": 0.70, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
    "low_mix": {"kind": "mix", "keep_bil_fraction": 0.50, "fallback_mix": {"GLD": 0.50, "TLT": 0.50}},
}
phaseqq_score_return_panel, phaseqq_score_positions = build_action_directed_fallback_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    phaseqq_action_frame,
    sleeve_name="composite_regime_conditioned",
    action_col="candidate_qq1_action",
    action_map=phaseqq_score_action_map,
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)
phaseqq_reason_return_panel, phaseqq_reason_positions = build_action_directed_fallback_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
    market_state_history,
    phaseqq_action_frame,
    sleeve_name="composite_regime_conditioned",
    action_col="candidate_qq2_action",
    action_map=phaseqq_reason_action_map,
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)
phaseqq_ppfiltered_return_panel, phaseqq_ppfiltered_positions = build_action_directed_fallback_sleeve_panels(
    phasepp_combo_base_return_panel,
    phasepp_combo_base_positions,
    market_state_history,
    phaseqq_action_frame,
    sleeve_name="composite_regime_conditioned",
    action_col="candidate_qq3_action",
    action_map=phaseqq_ppfiltered_action_map,
    apply_market_states={"calm_trend", "recovery_confirmed", "recovery_fragile"},
    apply_strong_neutral=True,
    target_bil_tier=0.25,
)

# Phase YY — explicit decomposition of composite_regime_conditioned into
# allocator-visible offense / defense / cash sleeves.
phaseyy_decomposed_return_panel, phaseyy_decomposed_positions = build_composite_decomposition_sleeve_panels(
    base_sleeve_return_panel,
    base_sleeve_positions,
)

# Phase FFF — Layer 2A re-engineered offense components. Same architecture
# as Phase YY decomposition but the offense component is built from
# narrower ETF subsets that exclude historically weak recovery_confirmed
# contributors (commodities first, then Japan/REITs in the more aggressive
# variants). defense and cash components unchanged.
phasefff_quality_filtered_return_panel, phasefff_quality_filtered_positions = build_composite_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    # FFF1: drop PDBC, DBA (commodities), EWJ (Japan-only) — keeps broad equity
    offense_cols_override=["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "VNQ"],
)
phasefff_core_equity_return_panel, phasefff_core_equity_positions = build_composite_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    # FFF2: keep only the highest-Sharpe broad equity ETFs (drop EWJ, VNQ, PDBC, DBA)
    offense_cols_override=["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO"],
)
phasefff_robust_return_panel, phasefff_robust_positions = build_composite_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    # FFF3: drop only commodities (PDBC, DBA), keep all equity exposure
    offense_cols_override=["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ"],
)
phasefff_polish_return_panel, phasefff_polish_positions = build_composite_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    # FFF4: smallest safe change — drop only PDBC (the weakest commodity)
    offense_cols_override=["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "DBA"],
)

# Phase GGG — state-conditional composite_regime_offense_component.
# Use the broad EEE1/YY offense subset everywhere except recovery_confirmed,
# where each variant swaps in a narrower / blended subset to repair RC
# without disturbing the other states (recovery_fragile, calm_trend,
# neutral_mixed, stressed_panic). Defense and cash components unchanged.
_ggg_default_offense = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
_ggg_robust_offense = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ"]      # FFF3
_ggg_quality_offense = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "VNQ"]            # FFF1
_ggg_state_series = market_state_history["market_state"]

phaseggg_confirmed_robust_return_panel, phaseggg_confirmed_robust_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # Only recovery_confirmed swaps to FFF3 robust (drop PDBC + DBA)
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_ggg_state_series,
)
phaseggg_confirmed_quality_return_panel, phaseggg_confirmed_quality_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # Only recovery_confirmed swaps to FFF1 quality_filtered (drop PDBC + DBA + EWJ)
        "recovery_confirmed": [(_ggg_quality_offense, 1.0)],
    },
    market_state_series=_ggg_state_series,
)
phaseggg_blended_robust_return_panel, phaseggg_blended_robust_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # Conservative: in recovery_confirmed, blend 50/50 broad + robust
        "recovery_confirmed": [(_ggg_default_offense, 0.5), (_ggg_robust_offense, 0.5)],
    },
    market_state_series=_ggg_state_series,
)

# Phase LLL — rebuild only composite_regime_defense_component on top of GGG1.
# KKK found recovery_confirmed drag was concentrated in TLT, while
# recovery_fragile drag was concentrated in GLD. Stressed-panic defense remains
# unchanged in all LLL candidates.
_lll_default_defense = ["HYG", "LQD", "GLD", "TLT"]
_lll_rc_filter_defense = ["HYG", "LQD", "GLD"]
_lll_rf_filter_defense = ["HYG", "LQD", "TLT"]

phaselll_recovery_filter_return_panel, phaselll_recovery_filter_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={"recovery_confirmed": [(_ggg_robust_offense, 1.0)]},
    state_defense_recipe={
        "recovery_confirmed": [(_lll_rc_filter_defense, 1.0)],
        "recovery_fragile": [(_lll_rf_filter_defense, 1.0)],
    },
    market_state_series=_ggg_state_series,
)
phaselll_recovery_blend_return_panel, phaselll_recovery_blend_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={"recovery_confirmed": [(_ggg_robust_offense, 1.0)]},
    state_defense_recipe={
        "recovery_confirmed": [(_lll_default_defense, 0.50), (_lll_rc_filter_defense, 0.50)],
        "recovery_fragile": [(_lll_default_defense, 0.50), (_lll_rf_filter_defense, 0.50)],
    },
    market_state_series=_ggg_state_series,
)
phaselll_conservative_polish_return_panel, phaselll_conservative_polish_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={"recovery_confirmed": [(_ggg_robust_offense, 1.0)]},
    state_defense_recipe={
        "recovery_confirmed": [(_lll_default_defense, 0.75), (_lll_rc_filter_defense, 0.25)],
        "recovery_fragile": [(_lll_default_defense, 0.75), (_lll_rf_filter_defense, 0.25)],
    },
    market_state_series=_ggg_state_series,
)

# Phase MMM — rebuild only composite_selective_signals in recovery_confirmed.
# Diagnostics show DBA is the main RC drag inside CSS and TLT is dead weight.
_mmm_css_rc_keep = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "BIL"]
phasemmm_css_filter_return_panel, phasemmm_css_filter_positions = build_state_filtered_sleeve_panels(
    phaseggg_confirmed_robust_return_panel,
    phaseggg_confirmed_robust_positions,
    market_state_history,
    sleeve_name="composite_selective_signals",
    state_filter_cols={"recovery_confirmed": _mmm_css_rc_keep},
)

# Phase HHH — extend GGG1's state-conditional swap to ALSO cover stressed_panic.
# GGG diagnostic showed filtered offense helps stressed_panic by +0.41pp ann
# (without weakening cash/defense routes). Three candidates, all keep
# recovery_fragile / neutral_mixed / calm_trend on broad EEE1.
phasehhh_confirmed_stressed_robust_return_panel, phasehhh_confirmed_stressed_robust_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # HHH1: GGG1 + same robust filter in stressed_panic
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
        "stressed_panic":     [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_ggg_state_series,
)
phasehhh_confirmed_robust_stressed_blended_return_panel, phasehhh_confirmed_robust_stressed_blended_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # HHH2: GGG1's RC swap kept; stressed_panic uses 50/50 broad+robust blend (safety)
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
        "stressed_panic":     [(_ggg_default_offense, 0.5), (_ggg_robust_offense, 0.5)],
    },
    market_state_series=_ggg_state_series,
)
phasehhh_confirmed_quality_stressed_robust_return_panel, phasehhh_confirmed_quality_stressed_robust_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        # HHH3: stronger RC filter (FFF1 quality_filtered: drop PDBC + DBA + EWJ)
        # paired with FFF3 robust in stressed_panic
        "recovery_confirmed": [(_ggg_quality_offense, 1.0)],
        "stressed_panic":     [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_ggg_state_series,
)

# ── Phase 3 — Breadth-Confirmed US Offense Upgrade ────────────────────────
# Switches composite_regime_offense_component from GGG1's diversified basket
# (SPY/QQQ/IWM + EFA/VEA/VWO/EWJ/VNQ/PDBC/DBA) to a concentrated US equity
# basket (SPY/QQQ/IWM) during high-breadth non-stressed states.
#
# Signal: breadth_sma_43 >= 0.65 AND market_trend_positive == 1
#         AND market_state not in {stressed_panic, recovery_fragile}
# All market_state_history features are computed from week-T prices and
# applied to week-T+1 allocation (causal, no look-ahead).
_p3_us_pure_offense = ["SPY", "QQQ", "IWM"]
_p3_us_growth_offense = ["QQQ", "SPY", "VUG"]

_p3_breadth_raw = (
    (market_state_history["breadth_sma_43"] >= 0.65) &
    (market_state_history["market_trend_positive"] == 1) &
    (~market_state_history["market_state"].isin(["stressed_panic", "recovery_fragile"]))
)
_p3_canary_col = "canary_breadth_default"
_p3_credit_raw = (
    _p3_breadth_raw & (market_state_history[_p3_canary_col] == 1)
    if _p3_canary_col in market_state_history.columns
    else _p3_breadth_raw
)


def _p3_augment_states(signal: pd.Series, states_to_split: list[str], suffix: str = "breadth_on") -> pd.Series:
    aug = market_state_history["market_state"].copy()
    for state in states_to_split:
        mask = signal & (aug == state)
        aug.loc[mask] = f"{state}_{suffix}"
    return aug


_p3_aug_neutral = _p3_augment_states(_p3_breadth_raw, ["neutral_mixed"])
_p3_aug_calm = _p3_augment_states(_p3_breadth_raw, ["calm_trend"])
_p3_aug_calm_growth = _p3_augment_states(_p3_breadth_raw, ["calm_trend", "neutral_mixed"])
_p3_aug_credit = _p3_augment_states(_p3_credit_raw, ["calm_trend", "neutral_mixed"])
_p3_aug_both = _p3_augment_states(_p3_breadth_raw, ["calm_trend", "neutral_mixed"])
_p3_aug_stretch = _p3_augment_states(_p3_breadth_raw, ["calm_trend", "neutral_mixed", "recovery_confirmed"])

# C1: neutral_mixed breadth_on → US pure offense
p3_neutral_us_return_panel, p3_neutral_us_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "neutral_mixed_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_neutral,
)

# C2: calm_trend breadth_on → US pure offense
p3_calm_us_return_panel, p3_calm_us_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "calm_trend_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_calm,
)

# C3: calm+neutral breadth_on → QQQ/SPY/VUG growth offense
p3_qqq_growth_return_panel, p3_qqq_growth_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "calm_trend_breadth_on": [(_p3_us_growth_offense, 1.0)],
        "neutral_mixed_breadth_on": [(_p3_us_growth_offense, 0.5), (_p3_us_pure_offense, 0.5)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_calm_growth,
)

# C4: double-confirmed (breadth + canary) → US pure offense
p3_credit_us_return_panel, p3_credit_us_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "calm_trend_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "neutral_mixed_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_credit,
)

# C5: calm + neutral breadth_on → US pure offense (balanced)
p3_balanced_us_return_panel, p3_balanced_us_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "calm_trend_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "neutral_mixed_breadth_on": [(_p3_us_pure_offense, 1.0)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_both,
)

# C6: stretch — all breadth_on states → US growth offense
p3_stretch_return_panel, p3_stretch_positions = build_state_conditional_decomposition_sleeve_panels(
    base_sleeve_return_panel, base_sleeve_positions,
    default_offense_cols=_ggg_default_offense,
    state_offense_recipe={
        "calm_trend_breadth_on": [(_p3_us_growth_offense, 1.0)],
        "neutral_mixed_breadth_on": [(_p3_us_pure_offense, 0.6), (_p3_us_growth_offense, 0.4)],
        "recovery_confirmed_breadth_on": [(_p3_us_pure_offense, 0.5), (_ggg_robust_offense, 0.5)],
        "recovery_confirmed": [(_ggg_robust_offense, 1.0)],
    },
    market_state_series=_p3_aug_stretch,
)

baseline_subset = list(ns5["sleeve_return_panel"].columns)
drop_breadth_subset = [name for name in baseline_subset if name != "composite_breadth_filtered"]
replace_equal_subset = ["dual_momentum_topn", "cta_trend_long_only", selective_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
replace_equal_strength_weighted_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    strength_weighted_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
replace_equal_concentrated_subset = ["dual_momentum_topn", "cta_trend_long_only", concentrated_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
replace_equal_trend_ensemble_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_ensemble_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
replace_equal_trend_quality_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_quality_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
replace_equal_trend_quality_refined_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_quality_refined_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
phaseb_confirmation_addon_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    selective_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
    confirmation_strategy_name,
]
phaseb_trend_quality_confirmation_combo_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_quality_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
    confirmation_strategy_name,
]
phasec_enhanced_sleeve_universe_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    trend_quality_refined_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
    confirmation_strategy_name,
]
replace_cta_with_vol_managed_subset = [
    "dual_momentum_topn",
    "cta_trend_vol_managed",
    selective_strategy_name,
    "composite_regime_conditioned",
    "taa_10m_sma",
]
improved_subset = replace_equal_subset
phaseyy_decomposed_subset = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    selective_strategy_name,
    "composite_regime_offense_component",
    "composite_regime_defense_component",
    "taa_10m_sma",
]
phase4_sector_small_subset = phaseyy_decomposed_subset + ["phase4_top5_sector_momentum_sleeve"]
phase4_sector_top3_subset = phaseyy_decomposed_subset + ["phase4_top3_sector_momentum_sleeve"]
phase4_sector_balanced_subset = phaseyy_decomposed_subset + ["phase4_balanced_sector_breadth_sleeve"]
phase4_sector_stretch_subset = phaseyy_decomposed_subset + ["phase4_stretch_sector_momentum_sleeve"]
phase4b_sector_small_subset = phaseyy_decomposed_subset + ["phase4b_top5_smooth_sector_sleeve"]
phase4b_sector_20_subset = phaseyy_decomposed_subset + ["phase4b_defensive_aware_top5_sleeve"]
phase4b_sector_25_subset = phaseyy_decomposed_subset + ["phase4b_top3_strict_sector_sleeve"]
phase4b_sector_hybrid_subset = phaseyy_decomposed_subset + ["phase4b_sector_blend_spy_qqq_sleeve"]
phase4b_sector_stretch_subset = phaseyy_decomposed_subset + ["phase4b_top3_strict_sector_sleeve"]

subset_specs = {
    "baseline_current": baseline_subset,
    "drop_breadth": drop_breadth_subset,
    "drop_regime": [name for name in baseline_subset if name != "composite_regime_conditioned"],
    "replace_equal_with_selective": replace_equal_subset,
    "replace_equal_with_strength_weighted": replace_equal_strength_weighted_subset,
    "replace_equal_with_concentrated": replace_equal_concentrated_subset,
    "replace_equal_with_trend_ensemble": replace_equal_trend_ensemble_subset,
    "replace_equal_with_trend_quality": replace_equal_trend_quality_subset,
    "replace_equal_with_trend_quality_refined": replace_equal_trend_quality_refined_subset,
    "phaseb_confirmation_addon": phaseb_confirmation_addon_subset,
    "phaseb_trend_quality_confirmation_combo": phaseb_trend_quality_confirmation_combo_subset,
    "phasec_enhanced_sleeve_universe": phasec_enhanced_sleeve_universe_subset,
    "replace_cta_with_vol_managed": replace_cta_with_vol_managed_subset,
    "add_selective_drop_breadth": drop_breadth_subset + [selective_strategy_name],
    "add_strength_weighted_drop_breadth": drop_breadth_subset + [strength_weighted_strategy_name],
    "add_concentrated_drop_breadth": drop_breadth_subset + [concentrated_strategy_name],
}


portfolio_version_rows: list[dict] = []
portfolio_version_regime_rows: list[pd.DataFrame] = []
portfolio_version_subperiod_rows: list[pd.DataFrame] = []
allocation_driver_rows: list[dict] = []
allocation_driver_breakdown_rows: list[dict] = []
allocation_driver_timeseries_rows: list[dict] = []
version_diagnostics_timeseries_rows: list[dict] = []
stacked_defense_timeseries_rows: list[dict] = []
sleeve_incremental_rows: list[dict] = []
sleeve_subset_rows: list[dict] = []
upside_capture_rows: list[dict] = []
rally_window_rows: list[dict] = []
targeted_window_rows: list[dict] = []
window_capture_rows: list[dict] = []
rerisk_lag_rows: list[dict] = []
state_conditioned_allocation_rows: list[dict] = []
sleeve_performance_by_state_rows: list[dict] = []


baseline_rows_by_method: dict[str, dict] = {}
if not FILTERED_VERSION_BUILD:
    for method_name in ["hrp", "max_diversification"]:
        _, baseline_weights, _, baseline_diag, _, baseline_metrics = run_subset_custom(
            method_name,
            "baseline_current",
            baseline_subset,
            overlay_variant="baseline",
            speed=ns5["SLEEVE_REALLOCATION_SPEED"],
            market_state_history=market_state_history,
            sleeve_return_panel=base_sleeve_return_panel,
            sleeve_positions=base_sleeve_positions,
        )
        baseline_rows_by_method[method_name] = {
            "metrics": baseline_metrics,
            "avg_bil": baseline_weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in baseline_weights.columns else np.nan,
            "avg_cash_weight": baseline_diag["cash_weight"].mean() if not baseline_diag.empty else np.nan,
        }
        for subset_name, subset_sleeves in subset_specs.items():
            _, weight_panel, path, diagnostics, _, metrics = run_subset_custom(
                method_name,
                subset_name,
                subset_sleeves,
                overlay_variant="baseline",
                speed=ns5["SLEEVE_REALLOCATION_SPEED"],
                market_state_history=market_state_history,
                sleeve_return_panel=base_sleeve_return_panel,
                sleeve_positions=base_sleeve_positions,
            )
            row = {
                "method_name": method_name,
                "subset_name": subset_name,
                "sleeve_count": len(subset_sleeves),
                "sleeve_names": "|".join(subset_sleeves),
                **metrics,
                "avg_bil_weight": weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan,
                "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
                "avg_cash_weight": diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan,
            }
            baseline = baseline_rows_by_method[method_name]["metrics"]
            row["delta_ann_return_vs_baseline"] = row["ann_return"] - baseline["ann_return"]
            row["delta_sharpe_vs_baseline"] = row["sharpe"] - baseline["sharpe"]
            row["delta_max_drawdown_vs_baseline"] = row["max_drawdown"] - baseline["max_drawdown"]
            row["delta_cvar_5_vs_baseline"] = row["cvar_5"] - baseline["cvar_5"]
            row["delta_turnover_vs_baseline"] = row["avg_weekly_turnover"] - baseline["avg_weekly_turnover"]
            row["delta_avg_bil_vs_baseline"] = row["avg_bil_weight"] - baseline_rows_by_method[method_name]["avg_bil"]
            row["delta_avg_cash_vs_baseline"] = row["avg_cash_weight"] - baseline_rows_by_method[method_name]["avg_cash_weight"]
            sleeve_subset_rows.append(row)

            if subset_name == "baseline_current":
                continue
            changed_sleeves = sorted(set(baseline_subset).symmetric_difference(set(subset_sleeves)))
            for sleeve_name in changed_sleeves:
                standalone = strategy_lookup.loc[sleeve_name].to_dict() if sleeve_name in strategy_lookup.index else {}
                sleeve_incremental_rows.append(
                    {
                        "method_name": method_name,
                        "subset_name": subset_name,
                        "candidate_sleeve": sleeve_name,
                        "standalone_ann_return": standalone.get("ann_return"),
                        "standalone_sharpe": standalone.get("sharpe"),
                        "standalone_max_drawdown": standalone.get("max_drawdown"),
                        "standalone_avg_weekly_turnover": standalone.get("avg_weekly_turnover"),
                        **row,
                    }
                )


version_specs = [
    {
        "version_name": "baseline_hrp_default",
        "method_name": "hrp",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Original baseline stack with the experimental breadth sleeve still active.",
    },
    {
        "version_name": "improved_hrp_selective",
        "method_name": "hrp",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Current improved reference: selective sleeve plus a looser but still symmetric overlay.",
    },
    {
        "version_name": "improved_hrp_recovery_tilt",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Adds a causal recovery state, faster re-risking than de-risking, and modest sleeve tilts when breadth and trend confirm recovery.",
    },
    {
        "version_name": "improved_hrp_recovery_concentrated",
        "method_name": "hrp",
        "subset_name": "upside_capture_concentrated",
        "subset_sleeves": replace_equal_concentrated_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Uses the same causal recovery logic but tests a slightly stronger offensive sleeve rather than assuming the broader sleeve is always best.",
    },
    {
        "version_name": "baseline_max_div_default",
        "method_name": "max_diversification",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Original maximum-diversification baseline.",
    },
    {
        "version_name": "improved_max_div_selective",
        "method_name": "max_diversification",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "rerisk_speed": None,
        "state_tilt": "none",
        "target_vol_ceil": 1.00,
        "note": "Current improved maximum-diversification reference.",
    },
    {
        "version_name": "improved_max_div_recovery_tilt",
        "method_name": "max_diversification",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Maximum-diversification allocator with causal recovery re-risking and modest sleeve tilts.",
    },
    {
        "version_name": "improved_inverse_vol_recovery_tilt",
        "method_name": "inverse_vol",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Inverse-vol reference run on the best causal recovery configuration.",
    },
    {
        "version_name": "improved_herc_recovery_tilt",
        "method_name": "herc",
        "subset_name": "upside_capture_recovery_tilt",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "HERC reference run on the best causal recovery configuration.",
    },
    # ======================================================================
    # State-split controlled experiment (Part A of the current research task)
    #
    # Control        = improved_hrp_recovery_tilt (already above).
    # Variant A      = improved_hrp_recovery_split
    #                  Splits the recovery state into fragile vs confirmed but keeps
    #                  the same symmetric "modest" offense and the same rerisk_speed
    #                  trigger as the control, so the only change under test is the
    #                  state classifier precision itself.
    # Variant B      = improved_hrp_recovery_split_confirmed_offense
    #                  Adds meaningfully stronger offense only when breadth, 13w and
    #                  26w momentum, trend, drawdown and risk score all confirm the
    #                  recovery. Fragile recovery stays modest.
    # Variant C      = improved_hrp_recovery_split_confirmed_offense_neutral_ease
    #                  Variant B + a slightly less punitive neutral-state floor in
    #                  weeks that still have a positive market trend. Targets the
    #                  residual sleeve-level BIL/cash drag outside confirmed recovery.
    # ======================================================================
    {
        "version_name": "improved_hrp_recovery_split",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_baseline",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_modest",
        "target_vol_ceil": 1.00,
        "note": "Variant A: splits recovery into fragile vs confirmed using causal breadth / 13w and 26w momentum / trend / drawdown / risk-score confirmation, but keeps the same symmetric modest offense and rerisk pacing as improved_hrp_recovery_tilt so the classifier split itself can be tested in isolation.",
    },
    {
        "version_name": "improved_hrp_recovery_split_confirmed_offense",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split_confirmed_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_confirmed_offense",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_aggressive",
        "target_vol_ceil": 1.00,
        "note": "Variant B: adds the recovery state split plus a meaningfully stronger offense ladder only in confirmed recovery. Fragile recovery stays modest and uses a partial rerisk speed to avoid leaning hard into unconfirmed bounces.",
    },
    {
        "version_name": "improved_hrp_recovery_split_confirmed_offense_neutral_ease",
        "method_name": "hrp",
        "subset_name": "upside_capture_recovery_split_confirmed_offense_neutral_ease",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_split_confirmed_offense_neutral_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "split_aggressive",
        "target_vol_ceil": 1.00,
        "note": "Variant C: Variant B plus a slightly less punitive neutral-state sleeve floor during neutral weeks whose market trend is still positive. Targets the residual BIL/cash drag that shows up outside confirmed recovery without globally relaxing the neutral stance.",
    },
    # ======================================================================
    # Participation-efficiency controlled experiment (current research task)
    #
    # Control        = improved_hrp_recovery_tilt (already above).
    # Variant A      = improved_hrp_neutral_ease
    #                  Mildly reduces positive-trend neutral cash drag without
    #                  changing the recovery split or adding confirmed offense.
    # Variant B      = improved_hrp_fragile_participation
    #                  Tests whether early / fragile recovery deserves slightly
    #                  more participation than confirmed recovery.
    # Variant C      = improved_hrp_beta_participation
    #                  Adds a small state-conditioned SPY budget by recycling a
    #                  slice of BIL in good states to test the "missing beta"
    #                  hypothesis directly.
    # Variant D      = improved_hrp_neutral_fragile_combo
    #                  Best justified combination after standalone tests:
    #                  neutral easing + fragile-first participation.
    # ======================================================================
    {
        "version_name": "improved_hrp_neutral_ease",
        "method_name": "hrp",
        "subset_name": "upside_capture_neutral_ease",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "target_vol_ceil": 1.00,
        "note": "Variant A: keeps the incumbent recovery logic but raises the floor modestly in positive-trend neutral weeks so benign environments carry less residual BIL drag.",
    },
    {
        "version_name": "improved_hrp_fragile_participation",
        "method_name": "hrp",
        "subset_name": "upside_capture_fragile_participation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_fragile_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_first",
        "target_vol_ceil": 1.00,
        "note": "Variant B: prioritizes fragile recovery over confirmed recovery with a slightly higher floor and sleeve tilt, testing whether the system is still rerisking too late after stress breaks.",
    },
    {
        "version_name": "improved_hrp_beta_participation",
        "method_name": "hrp",
        "subset_name": "upside_capture_beta_participation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "recovery_breadth_rerisk",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "beta_overlay_mode": "good_state_spy",
        "target_vol_ceil": 1.00,
        "note": "Variant C: keeps the incumbent sleeve logic but recycles a small amount of BIL into SPY only in calm, fragile-recovery, and strong positive-trend neutral states to test whether missing benchmark beta is the main return lag.",
    },
    {
        "version_name": "improved_hrp_neutral_fragile_combo",
        "method_name": "hrp",
        "subset_name": "upside_capture_neutral_fragile_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease_fragile_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_first",
        "target_vol_ceil": 1.00,
        "note": "Variant D: combines the winning mild neutral-state easing with the modest fragile-recovery-first participation tweak, without adding explicit benchmark-beta recycling.",
    },
    # ======================================================================
    # Good-state participation bottleneck study (current task)
    # ======================================================================
    {
        "version_name": "improved_hrp_strength_weighted_selective",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_strength_weighted_selective",
        "subset_sleeves": replace_equal_strength_weighted_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: momentum-strength-aware sleeve deployment. The selective sleeve keeps the same signal blend and top-N count as the control, but scales selected ETF weights by signal strength so strong positive setups can express more than weak ones.",
    },
    {
        "version_name": "improved_hrp_good_state_offense",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_participation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant B: better good-state offense rules. Calm-trend and strong positive-trend neutral weeks carry a little less overlay cash, while stressed states stay unchanged.",
    },
    {
        "version_name": "improved_hrp_layer3_expression_relax",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_layer3_expression_relax",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "good_state_conviction_relax",
        "target_vol_ceil": 1.00,
        "note": "Variant C: modest Layer 3 dampener relaxation. In calm, strong-neutral, and fragile-recovery states, HRP shifts a small budget from defensive sleeves toward the strongest offensive sleeves rather than holding the defensive mix flat.",
    },
    {
        "version_name": "improved_hrp_fragile_expression",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_fragile_expression",
        "subset_sleeves": improved_subset,
        "overlay_variant": "fragile_expression_only",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: modest fragile-recovery expression only. It raises fragile-recovery participation slightly without reviving any stronger confirmed-recovery offense ladder.",
    },
    {
        "version_name": "improved_hrp_neutral_ease_beta_diag",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_beta_diagnostic",
        "subset_sleeves": improved_subset,
        "overlay_variant": "neutral_positive_ease",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "modest",
        "layer3_expression_mode": "none",
        "beta_overlay_mode": "good_state_spy_light",
        "target_vol_ceil": 1.00,
        "note": "Variant F: controlled broad-beta diagnostic. Starting from the neutral-ease control, recycle only a small amount of BIL into SPY in clearly good states to test whether missing beta is still a major part of the lag.",
    },
    {
        "version_name": "improved_hrp_good_state_fragile_combo",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_fragile_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant E (prior round): best justified combination after the standalone pass. Keeps the stronger good-state overlay floors and combines them with modest fragile-recovery expression.",
    },
    # ======================================================================
    # Transition-aware / stabilizer / mix-rotation study (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_good_state_transition_aware
    #                  Uses trailing-window P(stay) and P(next in good state) to
    #                  lift the strong-neutral floor only when the current regime
    #                  is observationally both persistent and benign-continuing.
    # Variant B      = improved_hrp_good_state_stabilizer
    #                  One-sided hysteresis on entry into stressed_panic to damp
    #                  1-week false entries; does not delay exits.
    # Variant C      = improved_hrp_good_state_strong_offense
    #                  Raises the strong-neutral floor 0.94 -> 0.98 and the base
    #                  neutral floor 0.80 -> 0.83 so clearly benign states carry
    #                  less residual overlay cash.
    # Variant D      = improved_hrp_good_state_mix_rotation
    #                  Rotates away from composite_regime_conditioned in calm and
    #                  recovery_fragile (low sleeve-by-state Sharpe) and toward
    #                  the trend-following trio; no overlay floor change.
    # Variant E      = improved_hrp_good_state_combo_plus
    #                  Combines A + B + C + D where each helped or was neutral.
    # ======================================================================
    {
        "version_name": "improved_hrp_good_state_transition_aware",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_transition_aware",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_transition_aware",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: adds an observable, causal transition-matrix feature (trailing 156w P(stay) and P(next in good state)) and lifts the strong-neutral floor 0.94 -> 0.97 only when both are high, so benign-continuing regimes deploy more fully without globally relaxing the neutral stance.",
    },
    {
        "version_name": "improved_hrp_good_state_stabilizer",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_stabilizer",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_stabilizer",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "stabilize_market_state": True,
        "note": "Variant B: one-sided hysteresis on entry into stressed_panic. A new stressed week is delayed by one week unless drawdown is already <= -10% or the risk_regime_score > 0.85. Exits are never delayed, so the de-risking response to real stress is preserved.",
    },
    {
        "version_name": "improved_hrp_good_state_strong_offense",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_strong_offense",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_strong_offense",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant C: stronger strong-neutral and calm offense. Raises the strong-neutral overlay floor 0.94 -> 0.98 and the base neutral floor 0.80 -> 0.83 so the 45 percent of history that sits in neutral_mixed carries less residual overlay cash.",
    },
    {
        "version_name": "improved_hrp_good_state_mix_rotation",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_mix_rotation",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_mix_rotation",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus_mix_rotation",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: better good-state sleeve mix. Rotates weight away from composite_regime_conditioned (weakest sleeve-by-state Sharpe in calm and fragile) and toward the trend-following trio (dual_momentum, cta_trend, composite_selective_signals) in those states; overlay floors unchanged.",
    },
    {
        "version_name": "improved_hrp_good_state_combo_plus",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_good_state_combo_plus",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_combo_plus",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus_mix_rotation",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "stabilize_market_state": True,
        "note": "Variant E: combination build. Uses the stabilizer (B), raises the strong-neutral floor to 0.97 with a further transition-aware lift to 0.98 when the trailing transition matrix says the regime is persistent and benign-continuing, and pairs the mix-rotation tilt (D). Keeps the neutral base floor at 0.83 (C).",
    },
    # ======================================================================
    # Stacked-defense tax study (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_stacked_defense_continuous_overlay
    #                  Replace the blunt neutral-state overlay response with a
    #                  bounded continuous map from risk_regime_score into neutral
    #                  deployment, while keeping the control's calm/recovery/stress
    #                  floors.
    # Variant B      = improved_hrp_stacked_defense_self_gated_overlay
    #                  Apply a lighter regime haircut to sleeves that already
    #                  self-gate internally (dual_momentum, cta_trend, taa_10m_sma)
    #                  so they are not de-risked twice in good states.
    # Variant C      = improved_hrp_stacked_defense_asymmetric_speed
    #                  Keep the control overlay, but let re-risking happen faster
    #                  in improving / strong-neutral states while leaving
    #                  deteriorating states at the baseline speed.
    # Variant D      = improved_hrp_stacked_defense_continuous_self_gated_combo
    #                  Best justified combination after the standalone readout:
    #                  pair the smoother continuous neutral mapping (A) with the
    #                  lighter haircut on self-gated sleeves (B). This tests
    #                  whether the deployment gain from A can survive once the
    #                  double-defense tax on internally gated sleeves is reduced.
    # ======================================================================
    {
        "version_name": "improved_hrp_stacked_defense_continuous_overlay",
        "method_name": "hrp",
        "subset_name": "stacked_defense_continuous_overlay",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant A: continuous overlay mapping only. Neutral-state deployment is mapped continuously from risk_regime_score instead of relying on the current blunt neutral response, while calm/recovery/stress keep the control floors.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_self_gated_overlay",
        "method_name": "hrp",
        "subset_name": "stacked_defense_self_gated_overlay",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated",
        "target_vol_ceil": 1.00,
        "note": "Variant B: reduced overlay penalty on self-gated sleeves only. Dual momentum, CTA trend, and TAA already gate risk internally, so the portfolio overlay applies a lighter regime haircut to them outside stressed states.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_asymmetric_speed",
        "method_name": "hrp",
        "subset_name": "stacked_defense_asymmetric_speed",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "speed_mode": "asymmetric_reallocation",
        "improving_speed": 0.80,
        "deteriorating_speed": 0.40,
        "target_vol_ceil": 1.00,
        "note": "Variant C: asymmetric reallocation speed only. Strong-neutral and improving good states re-risk faster, while deteriorating states stay on the baseline de-risk speed rather than slowing the defense response.",
    },
    {
        "version_name": "improved_hrp_stacked_defense_continuous_self_gated_combo",
        "method_name": "hrp",
        "subset_name": "stacked_defense_continuous_self_gated_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated",
        "target_vol_ceil": 1.00,
        "note": "Variant D: justified A+B combination only. Keep the continuous neutral-state overlay map, but reduce the portfolio-level haircut on sleeves that already self-gate internally so the smoother overlay does not still double-tax the same sleeves.",
    },
    # ======================================================================
    # Disciplined good-state deployment sprint (current research task)
    #
    # Control        = improved_hrp_good_state_fragile_combo (above).
    # Variant A      = improved_hrp_self_gated_relief_targeted
    #                  Tight, state-targeted relief for internally self-gated
    #                  sleeves only in strong-neutral and recovery states.
    # Variant B      = improved_hrp_continuous_overlay_careful
    #                  Conservative continuous mapping that mainly smooths
    #                  strong-neutral deployment while preserving stressed-state
    #                  protection and the control's recovery floors.
    # Variant C      = improved_hrp_targeted_relief_continuous_combo
    #                  Best justified A+B combination if the standalone readout
    #                  says both attack the same stacked-defense bottleneck.
    # Variant D      = improved_hrp_separate_canary_proxy
    #                  Minimal separate-canary overlay check using a tiny
    #                  principled canary proxy pair rather than broad mining.
    # Variant E      = improved_hrp_threshold_recentering
    #                  Tiny threshold recentering only; no broader tuning.
    # Variant F      = improved_hrp_trend_horizon_ensemble
    #                  Minimal horizon-ensemble trend sleeve replacing the
    #                  current equal-weight selective sleeve.
    # Variant G      = improved_hrp_cta_vol_managed_local
    #                  Sleeve-local volatility management by swapping in the
    #                  existing vol-managed CTA sleeve for the long-only CTA
    #                  sleeve, leaving the broader portfolio stack intact.
    # ======================================================================
    {
        "version_name": "improved_hrp_self_gated_relief_targeted",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_self_gated_relief_targeted",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated_targeted",
        "target_vol_ceil": 1.00,
        "note": "Variant A: reduce the overlay penalty only for sleeves that already self-gate internally, and only in strong-neutral plus early-recovery states. Keeps stressed-state protection and broader overlay discipline intact.",
    },
    {
        "version_name": "improved_hrp_continuous_overlay_careful",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_continuous_overlay_careful",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping_careful",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant B: a more careful continuous overlay map. It smooths deployment mainly in strong-neutral weeks while keeping weak-neutral and stressed states close to the control path.",
    },
    {
        "version_name": "improved_hrp_targeted_relief_continuous_combo",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_targeted_relief_continuous_combo",
        "subset_sleeves": improved_subset,
        "overlay_variant": "continuous_neutral_mapping_careful",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_self_gated_targeted",
        "target_vol_ceil": 1.00,
        "note": "Variant C: pair the careful continuous map with the tighter self-gated relief so only the sleeves most exposed to double-defense get extra release in good states.",
    },
    {
        "version_name": "improved_hrp_separate_canary_proxy",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_separate_canary_proxy",
        "subset_sleeves": improved_subset,
        "overlay_variant": "separate_canary_proxy",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant D: minimal separate-canary test. Uses a tiny canary proxy pair to modestly lift deployment only when the canary pair is fully healthy, without broad architecture sprawl.",
    },
    {
        "version_name": "improved_hrp_threshold_recentering",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_threshold_recentering",
        "subset_sleeves": improved_subset,
        "overlay_variant": "threshold_recentering",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant E: tiny threshold recentering only. Broadens the strong-neutral bucket slightly while leaving the rest of the control architecture intact.",
    },
    {
        "version_name": "improved_hrp_trend_horizon_ensemble",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_trend_horizon_ensemble",
        "subset_sleeves": replace_equal_trend_ensemble_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant F: replace the current selective sleeve with a simple multi-horizon trend ensemble sleeve to test whether a more graded trend aggregate improves deployment translation beyond the existing Layer 1 momentum blend.",
    },
    {
        "version_name": "improved_hrp_cta_vol_managed_local",
        "method_name": "hrp",
        "subset_name": "disciplined_good_state_cta_vol_managed_local",
        "subset_sleeves": replace_cta_with_vol_managed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "target_vol_ceil": 1.00,
        "note": "Variant G: sleeve-local volatility-aware deployment. Swaps in the existing vol-managed CTA sleeve in place of the long-only CTA sleeve, leaving the broader overlay and allocator stack unchanged.",
    },
    # ======================================================================
    # Non-self-gated overlay relief study (current sprint)
    #
    # Motivation: `improved_hrp_self_gated_relief_targeted` was the cleanest
    # positive result on the prior sprint but the delta was too small to
    # beat the promotion margin. The remaining overlay-cash bottleneck is on
    # the non-self-gated sleeves (composite_selective_signals and
    # composite_regime_conditioned) in strong-neutral and recovery-fragile
    # states, where sleeves self-defend AND overlay cuts again AND target-vol
    # is not binding. The follow-up is to extend relief narrowly to those
    # non-self-gated sleeves, with tighter caps, in only those two states.
    #
    # Control     = improved_hrp_good_state_fragile_combo (above).
    # Variant A   = improved_hrp_non_self_gated_relief_narrow
    #               Scale-bounded non-self-gated relief (cap 0.025, scale
    #               0.20) in strong_neutral + recovery_fragile ONLY. Keeps
    #               the existing self-gated relief shape (cap 0.04, scale
    #               0.35) in strong_neutral + recovery_fragile + recovery_
    #               confirmed. Non-self-gated relief deliberately excludes
    #               recovery_confirmed to avoid reviving confirmed-recovery
    #               aggression.
    # Variant B   = improved_hrp_non_self_gated_relief_flat
    #               Same structure but non-self-gated relief is a flat 0.02
    #               nudge (no scaling). Tests whether the signal is in the
    #               proportional-to-binding shape or just a small fixed
    #               release.
    # Variant C   = improved_hrp_non_self_gated_relief_combo
    #               Created only if A and B each independently clear the
    #               Pareto bar. Pairs the narrower shape with the existing
    #               careful continuous map. Held in reserve; only added in
    #               a follow-up edit if warranted.
    # ======================================================================
    {
        "version_name": "improved_hrp_non_self_gated_relief_narrow",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_narrow",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow",
        "target_vol_ceil": 1.00,
        "note": "Variant A: extend overlay relief narrowly to non-self-gated sleeves (composite_selective_signals, composite_regime_conditioned) only in strong_neutral and recovery_fragile, cap 0.025 and scale 0.20. Self-gated relief line unchanged. Stressed-panic protection unchanged. Does not touch recovery_confirmed on the non-self-gated side.",
    },
    {
        "version_name": "improved_hrp_non_self_gated_relief_flat",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_flat",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_flat",
        "target_vol_ceil": 1.00,
        "note": "Variant B: same targeted state set as Variant A but the non-self-gated relief is a flat 0.02 nudge instead of scaled by (1 - regime_multiplier). Tests shape sensitivity.",
    },
    {
        "version_name": "improved_hrp_non_self_gated_relief_narrow_plus_confirmed",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_non_self_gated_relief_narrow_plus_confirmed",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant C: extends Variant A's non-self-gated relief to recovery_confirmed at a tighter cap (0.015) and scale (0.15). Tests whether the signal strengthens when the relief reaches additional binding weeks without crossing into confirmed-recovery aggression.",
    },
    # ======================================================================
    # Narrow sleeve-leadership follow-up (current research task)
    #
    # Control     = improved_hrp_non_self_gated_relief_narrow_plus_confirmed.
    # Variant A   = improved_hrp_confirmed_leadership
    #               Keep the incumbent overlay / relief logic, but rotate sleeve
    #               leadership inside recovery_confirmed toward the sleeves that
    #               actually lead there (CTA trend, then TAA) and away from the
    #               laggards (selective, regime-conditioned).
    # Variant B   = improved_hrp_calm_confirmed_leadership
    #               Extend the same idea to calm_trend, where overlay cash is
    #               already low and the remaining drag appears to come from a
    #               still-too-heavy regime-conditioned sleeve.
    # Variant C   = improved_hrp_calm_confirmed_fragile_leadership
    #               Add a more selective fragile-recovery leadership rotation to
    #               Variant B, favoring CTA and dual momentum over the weaker
    #               sleeves in that handoff regime.
    # ======================================================================
    {
        "version_name": "improved_hrp_confirmed_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_confirmed_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "confirmed_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant A: keep the current gross-risk and overlay design, but improve recovery_confirmed sleeve leadership by rotating toward CTA trend and TAA, away from selective and regime-conditioned sleeves that have lagged in that state.",
    },
    {
        "version_name": "improved_hrp_calm_confirmed_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_calm_confirmed_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "calm_confirmed_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant B: extend the leadership rotation to calm_trend as well. Targets the remaining undercapture in prolonged benign markets where overlay cash is already low and sleeve mix looks like the bottleneck.",
    },
    {
        "version_name": "improved_hrp_calm_confirmed_fragile_leadership",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_calm_confirmed_fragile_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "calm_confirmed_fragile_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Variant C: add a selective fragile-recovery leadership rotation on top of Variant B, favoring CTA and dual momentum in recovery_fragile while still keeping the incumbent overlay state set and stressed-state protection intact.",
    },
    # ======================================================================
    # Final classical sprint: wider overlay-cash relief in the two good-but-
    # not-confirmed states (strong_neutral, recovery_fragile).
    #
    # Control     = improved_hrp_non_self_gated_relief_narrow_plus_confirmed
    #               (incumbent, identical sleeve/state logic, incumbent caps).
    # Variant A   = improved_hrp_overlay_cash_wider_cap
    #               Same structure as the incumbent but widens the non-self-
    #               gated relief cap from 0.025 -> 0.045 and the scale from
    #               0.20 -> 0.28 in strong_neutral and recovery_fragile only.
    #               recovery_confirmed keeps incumbent tight values (0.015 /
    #               0.15). Self-gated relief and stressed-panic protection
    #               are unchanged. Directly attacks the cap-bound overlay
    #               cash (~15.3% / ~13.0%) in those two states.
    # Variant B   = improved_hrp_overlay_cash_wider_cap_persistence_gated
    #               Persistence-conditioned version of A. Engages the widened
    #               cap only when the Layer 2B causal regime engine's
    #               transition_non_stress_prob >= 0.92; otherwise falls back
    #               to incumbent narrow (0.025 / 0.20). Tests whether
    #               conditioning deployment on the regime engine's own
    #               stay-out-of-stress confidence cleans the tail.
    # ======================================================================
    {
        "version_name": "improved_hrp_overlay_cash_wider_cap",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_overlay_cash_wider_cap",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_wider_cap",
        "target_vol_ceil": 1.00,
        "note": "Sprint Variant A: widen the non-self-gated relief cap (0.025 -> 0.045) and scale (0.20 -> 0.28) in strong_neutral and recovery_fragile only. recovery_confirmed unchanged (0.015 / 0.15). Self-gated relief unchanged. Stressed-panic protection unchanged. Directly targets the ~15% strong_neutral and ~13% recovery_fragile overlay-cash that is cap-bound, not vol-bound.",
    },
    {
        "version_name": "improved_hrp_overlay_cash_wider_cap_persistence_gated",
        "method_name": "hrp",
        "subset_name": "uptrend_participation_overlay_cash_wider_cap_persistence_gated",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_wider_cap_persistence_gated",
        "target_vol_ceil": 1.00,
        "note": "Sprint Variant B: persistence-gated widening. Same structure as Variant A but the widened non-self-gated cap (0.045 / 0.28) only fires when the Layer 2B regime engine's transition_non_stress_prob >= 0.92; otherwise falls back to incumbent narrow (0.025 / 0.20). recovery_confirmed unchanged. Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    # ======================================================================
    # Phase 1 upgrade sprint (current sprint). Tests five standalone Phase 1
    # improvements plus justified combinations. Control for all of these is
    # `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` (incumbent).
    #
    # Variant A  = improved_hrp_phase1_dynamic_risk_budget
    #   Dynamic risk budgeting: rolling-Sharpe rank-based ±15% sleeve
    #   conviction tilt in favorable states only. Stressed-panic keeps
    #   the existing defensive shift.
    # Variant B  = improved_hrp_phase1_continuous_confidence
    #   Continuous causal-confidence map: non-self-gated relief cap and
    #   scale linearly interpolated by the Layer 2B confidence score.
    # Variant C  = improved_hrp_phase1_confidence_gated
    #   Confidence-gated relief: multiplicative confidence gate on the
    #   incumbent narrow values.
    # Variant D  = improved_hrp_phase1_internal_redeploy
    #   Sleeve-internal cash redesign: reduce per-sleeve BIL in favorable
    #   states, redistribute to existing risky picks. Recomputed through
    #   the canonical compute_strategy_path cost model. Defensive full-
    #   BIL rows preserved.
    # Variant E  = improved_hrp_phase1_leadership
    #   Good-state sleeve leadership rotation bounded at ±15% per sleeve.
    # ======================================================================
    {
        "version_name": "improved_hrp_phase1_dynamic_risk_budget",
        "method_name": "hrp",
        "subset_name": "phase1_dynamic_risk_budget",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant A: rolling 26w rank-based sleeve-conviction tilt (±15%) in favorable states; incumbent overlay relief kept. Stressed-panic unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_continuous_confidence",
        "method_name": "hrp",
        "subset_name": "phase1_continuous_confidence",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_continuous_confidence_map",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant B: continuous causal-confidence map on the non-self-gated relief. cap/scale LERP from tight (0.015/0.15) at confidence=0 to wide (0.045/0.32) at confidence=1 in strong_neutral and recovery_fragile; recovery_confirmed kept tighter (0.010-0.025 / 0.10-0.20). Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_confidence_gated",
        "method_name": "hrp",
        "subset_name": "phase1_confidence_gated",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_confidence_gated",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant C: multiplicative confidence gate on the incumbent narrow values. ns_relief_cap = 0.025 + confidence*0.020; ns_relief_scale = 0.20 + confidence*0.10 in strong_neutral and recovery_fragile; recovery_confirmed uses tighter additive gates (0.015+conf*0.010 / 0.15+conf*0.05). Self-gated relief unchanged. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_internal_redeploy",
        "method_name": "hrp",
        "subset_name": "phase1_internal_redeploy",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "fragile_plus",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "internal_redeploy": True,
        "note": "Phase 1 Variant D: sleeve-internal cash redesign. Reduce per-sleeve internal BIL by 30% in strong_neutral and recovery_fragile, 20% in recovery_confirmed, 40% in calm_trend; redistribute to existing risky picks proportionally. Targets composite_regime_conditioned, dual_momentum_topn, cta_trend_long_only. 100%-BIL defensive rows preserved. Recomputed through compute_strategy_path. Overlay/tilt unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_leadership",
        "method_name": "hrp",
        "subset_name": "phase1_leadership",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase1_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Variant E: bounded ±15% good-state sleeve-leadership rotation. Calm_trend and strong_neutral favor trend trio + TAA / selective and fade regime_conditioned; recovery_confirmed favors CTA/TAA; recovery_fragile favors CTA + dual momentum. Overlay relief and gross-risk unchanged.",
    },
    # ======================================================================
    # Phase 1 justified combinations (current sprint).
    #
    # Combo F  = improved_hrp_phase1_combo_f_a_plus_e
    #   Two-way combo of the cleanest winner (A, dynamic risk budgeting)
    #   and the closest-to-neutral variant (E, leadership rotation).
    #   Applies the leadership rotation first, then layers a dampened
    #   conviction tilt on top (±10% instead of ±15%) to avoid compound
    #   blow-ups. Incumbent overlay/relief kept.
    # Combo G  = improved_hrp_phase1_combo_g_a_e_d_restricted
    #   Three-way combo of A + E + a restricted version of D that
    #   excludes recovery_confirmed (where standalone D hurt capture
    #   materially) and runs internal redeploy at lower fractions in
    #   strong_neutral / recovery_fragile / calm_trend only. Tests
    #   whether the disciplined D layer helps once A+E has set a
    #   cleaner sleeve mix.
    # ======================================================================
    {
        "version_name": "improved_hrp_phase1_combo_f_a_plus_e",
        "method_name": "hrp",
        "subset_name": "phase1_combo_f",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_and_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 1 Combo F: dynamic risk budgeting (A, dampened to ±10%) layered on top of good-state leadership rotation (E, ±15%). Same state set as A, B, C, E. Incumbent overlay relief kept. Stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_hrp_phase1_combo_g_a_e_d_restricted",
        "method_name": "hrp",
        "subset_name": "phase1_combo_g",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_and_leadership",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "internal_redeploy": "restricted",
        "note": "Phase 1 Combo G: Combo F (A + E) plus restricted sleeve-internal cash redeploy (D-restricted) in strong_neutral (25%), recovery_fragile (25%), calm_trend (35%). recovery_confirmed intentionally EXCLUDED (standalone D hurt capture there). Targets composite_regime_conditioned, dual_momentum_topn, cta_trend_long_only. Incumbent overlay relief kept.",
    },
    # ======================================================================
    # Phase 2A bridge layer: harder classical / allocator / state-mapping
    # upgrades that remain mostly non-ML. All variants preserve the Phase 1
    # winner's dynamic_risk_budget state tilt and the stressed-panic
    # protection. Control = improved_hrp_phase1_dynamic_risk_budget.
    #
    # Variant A = improved_phase2a_erc_dynamic_risk_budget
    #   Swap HRP + sample covariance for flat ERC + Ledoit-Wolf shrinkage.
    #   Tests the pillar 1 / pillar 3 upgrade: robust risk parity with a
    #   disciplined covariance estimator. Same subset, same state tilt,
    #   same incumbent overlay.
    # Variant B = improved_phase2a_principled_continuous_map
    #   Keep HRP allocator. Swap the incumbent tight narrow_plus_confirmed
    #   overlay for the new phase2a_principled_continuous overlay:
    #   confidence-gated continuous mapping with bounded lift (max 1.40x
    #   incumbent at confidence=1, no loosening below confidence=0.55).
    #   Tests the pillar 2 upgrade: principled bounded continuous state
    #   mapping.
    # Variant C = improved_phase2a_herc_dynamic_risk_budget
    #   Swap HRP (bisection-based HRP) for HERC (cluster-level ERC, intra-
    #   cluster inverse vol). Tests the pillar 3 upgrade: cluster-aware
    #   covariance / risk-budget allocator. Same covariance regime as the
    #   HRP incumbent (sample) so the effect is clearly attributable to
    #   the hierarchical structure.
    # Variant D = SKIPPED
    #   Factor integration across value/quality/momentum families requires
    #   wiring new factor-family sleeves into the sleeve panel, which
    #   exceeds Phase 2A scope (sleeve generation is Layer 2 / Phase 2B
    #   plumbing). Classified Research-only for this sprint.
    # Variant E = improved_phase2a_combo_erc_plus_principled_continuous
    #   Combo A + B: ERC + Ledoit-Wolf allocator with the new principled
    #   continuous overlay.
    # Variant F = improved_phase2a_combo_herc_plus_principled_continuous
    #   Combo C + B: HERC allocator with the new principled continuous
    #   overlay. Tests whether cluster-aware risk-budgeting benefits more
    #   or less from the tighter continuous mapping than flat ERC.
    # ======================================================================
    {
        "version_name": "improved_phase2a_erc_dynamic_risk_budget",
        "method_name": "erc_risk_parity",
        "subset_name": "phase2a_erc_dynamic_risk_budget",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 2A Variant A: swap HRP+sample cov for flat ERC (equal risk contribution) with Ledoit-Wolf shrinkage. Same subset, state_tilt (dynamic_risk_budget), and incumbent narrow_plus_confirmed overlay as the CONTROL. Tests the canonical robust-risk-parity + shrinkage combination.",
    },
    {
        "version_name": "improved_phase2a_principled_continuous_map",
        "method_name": "hrp",
        "subset_name": "phase2a_principled_continuous_map",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phase2a_principled_continuous",
        "target_vol_ceil": 1.00,
        "note": "Phase 2A Variant B: HRP allocator + new phase2a_principled_continuous overlay. Confidence-gated (causal_confidence >= 0.55) bounded linear lift of non-self-gated relief cap/scale, max 1.40x incumbent at confidence=1. Below gate, behaviour identical to incumbent narrow_plus_confirmed. recovery_confirmed stays tighter than fragile/strong_neutral. Stressed-panic and neutral (non-strong) unchanged.",
    },
    {
        "version_name": "improved_phase2a_herc_dynamic_risk_budget",
        "method_name": "herc",
        "subset_name": "phase2a_herc_dynamic_risk_budget",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "note": "Phase 2A Variant C: swap HRP for HERC (hierarchical equal risk contribution, cluster-level ERC + intra-cluster inverse vol). Same subset, state_tilt (dynamic_risk_budget), and incumbent overlay as CONTROL. Tests cluster-aware risk-budget allocator on the same covariance regime (sample).",
    },
    {
        "version_name": "improved_phase2a_combo_erc_plus_principled_continuous",
        "method_name": "erc_risk_parity",
        "subset_name": "phase2a_combo_e_erc_plus_principled",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phase2a_principled_continuous",
        "target_vol_ceil": 1.00,
        "note": "Phase 2A Combo E (A + B): ERC+Ledoit-Wolf allocator combined with the new phase2a_principled_continuous overlay. Tests the cleanest allocator upgrade against the tighter continuous mapping jointly.",
    },
    {
        "version_name": "improved_phase2a_combo_herc_plus_principled_continuous",
        "method_name": "herc",
        "subset_name": "phase2a_combo_f_herc_plus_principled",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phase2a_principled_continuous",
        "target_vol_ceil": 1.00,
        "note": "Phase 2A Combo F (C + B): HERC allocator combined with the new phase2a_principled_continuous overlay. Tests whether cluster-aware allocation benefits more or less than flat ERC from the tighter continuous mapping.",
    },
    # ======================================================================
    # Phase 2B meta layer: interpretable ML (walk-forward, no lookahead).
    # Three decoupled meta signals modify regime_multiplier only
    # (orthogonal to overlay_penalty_mode, which is kept at the CONTROL's
    # incumbent relief shape). All 5 variants preserve the CONTROL's
    # state_tilt="dynamic_risk_budget", overlay="lighter_both_targeted_
    # narrow_plus_confirmed", HRP allocator, and stressed-panic protection.
    # Predictions come from scripts/build_phase2b_meta_predictions.py
    # (interpretable ML only: logistic, shallow tree, monotonic GBM).
    #
    # Variant A = improved_phase2b_regime_confidence_boost
    #   p_regime_confidence (logistic) boosts regime_multiplier by up to
    #   +0.045 in non-stressed states, gated at p >= 0.55. Tests whether
    #   the ML's conviction that the next 4 weeks are sharpe-positive
    #   and shallow-drawdown lets us re-risk faster.
    # Variant B = improved_phase2b_transition_quality_gate
    #   p_transition_quality (shallow tree) gates re-risking in
    #   strong_neutral / recovery_fragile only. p > 0.60 -> +0.04;
    #   p < 0.40 -> -0.03. Tests whether the tree can separate
    #   high-quality transition windows from false-starts.
    # Variant C = improved_phase2b_tail_risk_suppression
    #   p_tail_risk (monotonic HGBM) suppresses regime_multiplier by up
    #   to -0.10 in all states except stressed_panic when p > 0.55.
    #   Tests whether the monotonic GBM can forecast unreached drawdown
    #   early enough to tighten risk before the overlay flips.
    # Variant E = improved_phase2b_combo_ac
    #   A + C. Confidence boost + tail suppression both active.
    #   Asymmetric: boosts only when confident AND tail-risk low.
    # Variant F = improved_phase2b_combo_abc
    #   A + B + C. Full meta stack — adds the transition-quality gate
    #   on top of A + C.
    # ======================================================================
    {
        "version_name": "improved_phase2b_regime_confidence_boost",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 2B Variant A: interpretable-ML regime confidence boost. Walk-forward LogisticRegression(p_regime_confidence) adds +0.0 to +0.045 to regime_multiplier in non-stressed states when p >= 0.55 (linear in (p - 0.55) / 0.45). Boost-only. Orthogonal to the CONTROL's incumbent narrow_plus_confirmed overlay relief. HRP allocator, dynamic_risk_budget tilt, stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_phase2b_transition_quality_gate",
        "method_name": "hrp",
        "subset_name": "phase2b_transition_quality_gate",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "transition_quality_gate",
        "note": "Phase 2B Variant B: interpretable-ML transition-quality gate. Walk-forward DecisionTreeClassifier depth 4 (p_transition_quality), trained only on transition-state observations. In strong_neutral/recovery_fragile: p > 0.60 -> +0.04; p < 0.40 -> -0.03. Tests whether a shallow tree can separate high-quality transitions from false-starts. Orthogonal to CONTROL overlay relief. HRP, dynamic_risk_budget, stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_phase2b_tail_risk_suppression",
        "method_name": "hrp",
        "subset_name": "phase2b_tail_risk_suppression",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "tail_risk_suppression",
        "note": "Phase 2B Variant C: interpretable-ML tail-risk suppression. Walk-forward HistGradientBoostingClassifier with monotonic constraints (breadth/trend/persistence -> decreasing tail risk; canary_breadth_default/recent_stress_26w -> increasing). All states except stressed_panic: p > 0.55 -> regime_multiplier += -0.10 * (p - 0.55) / 0.45 (capped at -0.10). Suppress-only. Orthogonal to CONTROL overlay relief. HRP, dynamic_risk_budget, stressed-panic protection unchanged.",
    },
    {
        "version_name": "improved_phase2b_combo_ac",
        "method_name": "hrp",
        "subset_name": "phase2b_combo_ac",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "combo_ac",
        "note": "Phase 2B Combo E (A + C): regime-confidence boost AND tail-risk suppression both active. Asymmetric: regime_multiplier only lifts when p_regime_confidence >= 0.55 AND p_tail_risk <= 0.55 (no suppression). Otherwise tail suppression dominates. Same overlay and allocator as CONTROL.",
    },
    {
        "version_name": "improved_phase2b_combo_abc",
        "method_name": "hrp",
        "subset_name": "phase2b_combo_abc",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "combo_abc",
        "note": "Phase 2B Combo F (A + B + C): full interpretable-ML meta stack. Regime-confidence boost + transition-quality gate + tail-risk suppression. Most-aggressive combo. Tests whether the three interpretable signals combine or interfere.",
    },
    # ======================================================================
    # Phase B: Sleeve Construction / Opportunity Modules.
    # Build better sleeves from the strongest Phase A inputs rather than
    # continuing the top-layer overlay search.
    #
    # S1 = trend-quality / anti-chop sleeve
    #   Replaces the incumbent selective sleeve with a cleaner trend module
    #   that combines momentum, time-series trend, and trend clarity.
    # S2 = confirmation-aware improving-state sleeve
    #   Adds a breadth-confirmed momentum sleeve as a sixth sleeve.
    # S3 = refined trend-quality sleeve
    #   Same S1 thesis, but only allows moving-average distance to survive
    #   if it adds something beyond the simpler trend-quality module.
    # Combo = S1 + S2, only justified because both address different
    #   sleeve-construction hypotheses from Phase A.
    # ======================================================================
    {
        "version_name": "improved_phaseb_trend_quality_module",
        "method_name": "hrp",
        "subset_name": "phaseb_trend_quality_module",
        "subset_sleeves": replace_equal_trend_quality_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase B Sleeve S1: replace the incumbent selective sleeve with a trend-quality / anti-chop module built from momentum, time-series trend, and trend-clarity. Keeps the production overlay and regime-confidence boost unchanged so the test isolates sleeve quality.",
    },
    {
        "version_name": "improved_phaseb_confirmation_module",
        "method_name": "hrp",
        "subset_name": "phaseb_confirmation_module",
        "subset_sleeves": phaseb_confirmation_addon_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase B Sleeve S2: add a confirmation-aware improving-state sleeve that uses breadth-confirmed momentum to express safer offensive deployment when momentum has broader support.",
    },
    {
        "version_name": "improved_phaseb_trend_quality_refined",
        "method_name": "hrp",
        "subset_name": "phaseb_trend_quality_refined",
        "subset_sleeves": replace_equal_trend_quality_refined_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase B Sleeve S3: refinement-only variant of the trend-quality sleeve that adds moving-average distance. It should only survive if it improves the simpler S1 sleeve materially.",
    },
    {
        "version_name": "improved_phaseb_combo_trend_quality_confirmation",
        "method_name": "hrp",
        "subset_name": "phaseb_combo_trend_quality_confirmation",
        "subset_sleeves": phaseb_trend_quality_confirmation_combo_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase B Sleeve Combo: combine the trend-quality replacement sleeve with the breadth-confirmed improving-state sleeve. Tests whether the new opportunity modules complement rather than duplicate each other.",
    },
    # ======================================================================
    # Phase C: Learned Sleeve Allocation / Sleeve-Quality Layer.
    # Uses the stronger Phase B sleeve universe:
    #   - composite_trend_quality_refined
    #   - composite_confirmation_aware_momentum
    # on top of the current production controller (Phase 2B A).
    #
    # Base = stronger sleeve universe only
    # C1   = learned sleeve-quality score (walk-forward logistic)
    # C2   = dynamic opportunity budget from learned sleeve quality
    # C3   = state-conditioned sleeve allocation map
    # C4   = best justified combination of C1/C2/C3
    # ======================================================================
    {
        "version_name": "improved_phasec_sleeve_universe_base",
        "method_name": "hrp",
        "subset_name": "phasec_sleeve_universe_base",
        "subset_sleeves": phasec_enhanced_sleeve_universe_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase C reference base: stronger Phase B sleeve universe without a new allocator. Isolates whether the improved sleeve panel alone is enough before introducing learned sleeve allocation.",
    },
    {
        "version_name": "improved_phasec_learned_sleeve_quality",
        "method_name": "hrp",
        "subset_name": "phasec_learned_sleeve_quality",
        "subset_sleeves": phasec_enhanced_sleeve_universe_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phasec_learned_quality",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase C Variant C1: walk-forward interpretable sleeve-quality score. Logistic sleeve-leadership probabilities reweight sleeves only in favorable states, bounded at the same long-only sleeve allocator layer.",
    },
    {
        "version_name": "improved_phasec_dynamic_risk_budget",
        "method_name": "hrp",
        "subset_name": "phasec_dynamic_risk_budget",
        "subset_sleeves": phasec_enhanced_sleeve_universe_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phasec_dynamic_opportunity_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase C Variant C2: dynamic sleeve risk budgeting. Starts from the learned sleeve-quality score, then lets the highest-quality offensive sleeves carry modestly more portfolio risk while trimming defensive sleeves only when the offensive opportunity set is genuinely stronger.",
    },
    {
        "version_name": "improved_phasec_state_conditioned_map",
        "method_name": "hrp",
        "subset_name": "phasec_state_conditioned_map",
        "subset_sleeves": phasec_enhanced_sleeve_universe_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phasec_state_map",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase C Variant C3: state-conditioned sleeve allocation map. Uses the stronger sleeve universe plus bounded same-state leadership and explicit sleeve-type preferences in strong-neutral, calm, and improving recovery states.",
    },
    {
        "version_name": "improved_phasec_combo_learned_state",
        "method_name": "hrp",
        "subset_name": "phasec_combo_learned_state",
        "subset_sleeves": phasec_enhanced_sleeve_universe_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phasec_combo",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase C Variant C4: best justified combination. Learned sleeve-quality probabilities, bounded opportunity budgeting, and the state-conditioned sleeve map are combined only at small amplitudes to test whether they are additive rather than noisy.",
    },
    # ======================================================================
    # Phase 3 opening sprint. All five variants are layered on top of the
    # Phase 2B production default (regime_confidence_boost) so that any gain
    # is orthogonal to production track A. The sprint probes three Phase 3
    # frontier areas:
    #   - A1 = richer sleeve-layer upgrade (add orthogonal sector rotation)
    #   - B1 = learned sleeve-quality (confirmed short+long rolling-Sharpe)
    #   - C1 = richer state-conditioned sleeve allocation (state-leader tilt)
    #   - E1 = best justified combo (A1 + B1)
    #   - F1 = broader combo (A1 + B1 + C1)
    # No heavier black-box method is tested in this opening sprint; that
    # door is reserved for a follow-up only if A1-F1 under-deliver.
    # ======================================================================
    {
        "version_name": "improved_phase3_richer_sleeve_sector_rotation",
        "method_name": "hrp",
        "subset_name": "phase3_richer_sleeve_sector_rotation",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3 Variant A1: add sector_rotation_with_sma_filter as a 6th orthogonal offensive sleeve. Correlation to existing 5 sleeves averages 0.58 (max 0.66), standalone Sharpe 0.63, SMA-filtered sector tilt that historically leads in recovery_fragile/recovery_confirmed states. Phase 2B A (regime_confidence_boost) stays on top; everything else identical to production default.",
    },
    {
        "version_name": "improved_phase3_sleeve_quality_confirmed",
        "method_name": "hrp",
        "subset_name": "phase3_sleeve_quality_confirmed",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_confirmed_quality",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3 Variant B1: learned sleeve-quality via persistence-confirmed rolling Sharpe. Short (13w) and long (52w) rank-based Sharpe conviction are blended 50/50; amplified 1.3x when signs agree, dampened to 0.4x when they disagree. Same ±15% bound as dynamic_risk_budget; replaces only the conviction signal. Phase 2B A on top; subset and overlay unchanged.",
    },
    {
        "version_name": "improved_phase3_state_conditioned_sleeve_lead",
        "method_name": "hrp",
        "subset_name": "phase3_state_conditioned_sleeve_lead",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3 Variant C1: richer state-conditioned sleeve allocation. Layers a walk-forward state-leader tilt on top of dynamic_risk_budget: trailing 156w same-state Sharpe is rank-transformed to [-1,+1] and multiplies each sleeve by clip(1 + 0.10 * tilt, 0.90, 1.10). Active only in favorable states. Requires ≥16 same-state observations or falls back to zero. Phase 2B A on top.",
    },
    {
        "version_name": "improved_phase3_combo_a1b1",
        "method_name": "hrp",
        "subset_name": "phase3_combo_a1b1",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_confirmed_quality",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3 Combo E1 = A1 + B1: richer sleeve set (add sector_rotation_with_sma_filter) combined with persistence-confirmed sleeve-quality conviction. Tests whether the two orthogonal upgrades compound cleanly.",
    },
    {
        "version_name": "improved_phase3_combo_a1b1c1",
        "method_name": "hrp",
        "subset_name": "phase3_combo_a1b1c1",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_full_phase3",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3 Combo F1 = A1 + B1 + C1: richer sleeve set + confirmed-quality conviction + state-leader tilt. Most-layered Phase 3 variant. Tests whether adding the state-leader tilt on top of A1 + B1 is additive or noisy.",
    },
    # ======================================================================
    # Phase 3.1 refinement sprint.
    # Narrow, targeted refinements of the two concrete levers identified by
    # the opening Phase 3 sprint:
    #   - C1a  = state-leader tilt bound widened ±0.10 → ±0.15
    #   - C1b  = state-leader tilt kept at ±0.10 but gated by |rank-tilt| > 0.30
    #   - A1g  = sector_rotation_with_sma_filter gated to recovery states only
    #   - Combo1 = C1a + A1g
    # No new sleeves, no new allocators, no black-box method. Every variant
    # keeps Phase 2B A (regime_confidence_boost) on top and HRP as the engine.
    # ======================================================================
    {
        "version_name": "improved_phase3_1_c1_widened",
        "method_name": "hrp",
        "subset_name": "phase3_1_c1_widened",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.1 Variant C1a: widened state-conditioned sleeve-leadership tilt. Identical to Phase 3 C1 except the state-leader multiplier bound is widened from ±0.10 to ±0.15. All other logic (favorable-state gate, 156w prior-same-state lookback, ≥16 obs minimum, shared recovery_fragile / stressed_panic protection) is unchanged. Tests whether C1 was simply too conservatively sized (C1 missed the +0.05 production promotion margin by 0.005).",
    },
    {
        "version_name": "improved_phase3_1_c1_conviction_gated",
        "method_name": "hrp",
        "subset_name": "phase3_1_c1_conviction_gated",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_conviction_gated",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.1 Variant C1b: conviction-gated state-conditioned sleeve-leadership tilt. Keeps Phase 3 C1's ±0.10 bound but only fires when the rank-tilt magnitude exceeds 0.30 — i.e., the sleeve is clearly in the top/bottom third of same-state performance. Middle-ranked sleeves are left alone. Tests whether selective deployment of the same C1 mechanism crosses the promotion bar without widening the bound.",
    },
    {
        "version_name": "improved_phase3_1_a1_state_gated",
        "method_name": "hrp",
        "subset_name": "phase3_1_a1_state_gated",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_sector_gated",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.1 Variant A1g: state-gated sector_rotation_with_sma_filter sleeve. Membership identical to Phase 3 A1 (improved_subset + sector_rotation_with_sma_filter) but the sector sleeve weight is forced to zero in calm_trend, neutral_mixed, and stressed_panic — deployed only in recovery_fragile and recovery_confirmed. Tests whether the recovery capture edge of A1 can be preserved without the calm / stress / downside drag that made A1 fail.",
    },
    {
        "version_name": "improved_phase3_1_combo_c1a_a1g",
        "method_name": "hrp",
        "subset_name": "phase3_1_combo_c1a_a1g",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.1 Combo1 = C1a + A1g: widened state-leader tilt (±0.15) stacked with the state-gated sector_rotation_with_sma_filter sleeve (deployed only in recovery_fragile / recovery_confirmed). Combo is evaluated only if both standalones show promise; promoted only if it beats both standalones on the composite without collateral damage.",
    },
    # ======================================================================
    # Phase 3.2 refinement sprint.
    # Combo1 was the strongest Phase 3 / 3.1 result but missed the +0.05
    # composite promotion gate by 0.001. The analysis identified a small
    # DD and turnover friction inside the recovery-state deployment of the
    # sector sleeve as the binding constraint. Phase 3.2 tries exactly two
    # narrow refinements of Combo1 (plus their combination):
    #   - R1 = tighten the A1g gate from {recovery_fragile, recovery_confirmed}
    #          to {recovery_confirmed} only
    #   - R2 = add a benchmark-drawdown proximity guard on the sector sleeve
    #   - R3 = apply both refinements together
    # Every variant keeps Phase 2B A (regime_confidence_boost) on top, HRP
    # as the engine, and every Combo1 lever intact.
    # ======================================================================
    {
        "version_name": "improved_phase3_2_combo_tight_gate",
        "method_name": "hrp",
        "subset_name": "phase3_2_combo_tight_gate",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_tight",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.2 Variant R1: Combo1 with the sector_rotation_with_sma_filter state gate tightened to {recovery_confirmed} only. Prior per-state Sharpe evidence put the sleeve at Sharpe 1.10 in recovery_confirmed vs 0.63 average standalone; recovery_fragile is noisier. Hypothesis: the tighter gate preserves the recovery-confirmed character edge while trimming the DD / turnover friction that kept Combo1 0.001 short of the +0.05 composite gate.",
    },
    {
        "version_name": "improved_phase3_2_combo_dd_guard",
        "method_name": "hrp",
        "subset_name": "phase3_2_combo_dd_guard",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.2 Variant R2: Combo1 with a benchmark-drawdown proximity guard on the sector sleeve. Within the existing {recovery_fragile, recovery_confirmed} gate, the sleeve weight is shrunk when the benchmark is already in a material drawdown: 0% when market_drawdown ≤ -0.10, 50% when -0.10 < market_drawdown ≤ -0.05, 100% when market_drawdown > -0.05. Causal (uses only information in the current market_state_row). Designed to reduce the DD / turnover friction that kept Combo1 0.001 short of promotion without touching the state-leader tilt.",
    },
    {
        "version_name": "improved_phase3_2_combo_tight_gate_dd_guard",
        "method_name": "hrp",
        "subset_name": "phase3_2_combo_tight_gate_dd_guard",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.2 Variant R3: Combo1 with BOTH the tightened {recovery_confirmed} gate (R1) and the benchmark-drawdown proximity guard (R2). Tests whether the two defensive refinements compound, or whether R1 already neutralises the DD friction and R2 becomes a no-op.",
    },
    # ----------------------------------------------------------------------
    # Phase 3.4 — tail-focused structural variants on top of Combo1.
    # All three share the Combo1 base (C1a widened bound + A1g recovery
    # state gate). The only differences are causal tail guards that target
    # the residual DD friction Phase 3.3 bootstrap showed was not improved:
    #
    #   T1 — sector sleeve DD guard scoped to recovery_fragile only.
    #        Thresholds set on the actual recovery_fragile market_drawdown
    #        distribution (median -1.9%, 25th pct -12.9%). This is the
    #        regime Phase 3.2 R2's broader DD guard never really touched
    #        because its trigger sat below the recovery_confirmed floor.
    #
    #   T2 — state-leader tilt-magnitude dampener driven by market_drawdown.
    #        Shrinks the ±0.15 tilt bound to 0.75x at md ≤ -0.05 and 0.5x
    #        at md ≤ -0.10. Applies across all favorable states; reduces
    #        offensive tilt pre-emptively when benchmark DD is already deep.
    #
    #   T3 — T1 + T2 combined. Only interesting if T1 and T2 both show
    #        standalone directional improvement without killing the mean.
    # ----------------------------------------------------------------------
    {
        "version_name": "improved_phase3_4_combo_fragile_guard",
        "method_name": "hrp",
        "subset_name": "phase3_4_combo_fragile_guard",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.4 Variant T1: Combo1 + a narrow DD guard on the sector sleeve scoped ONLY to recovery_fragile. Same step function as the Phase 3.2 R2 guard (×0 at md ≤ -0.15 / ×0.5 at md ≤ -0.05 within recovery_fragile; recovery_confirmed untouched). Targets the specific regime where Phase 3.3 bootstrap showed Combo1's DD was indistinguishable-but-slightly-worse than A.",
    },
    {
        "version_name": "improved_phase3_4_combo_tilt_dampened",
        "method_name": "hrp",
        "subset_name": "phase3_4_combo_tilt_dampened",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.4 Variant T2: Combo1 + a benchmark-DD-gradient dampener on the state-leader tilt magnitude. When market_drawdown ≤ -0.05 the ±0.15 bound is scaled by 0.75; when md ≤ -0.10 it is scaled by 0.5. Causal (uses only the current market_state_row). Pulls offensive state-leader tilt in pre-emptively when the benchmark is already deep in a drawdown. Sector state gate unchanged.",
    },
    {
        "version_name": "improved_phase3_4_combo_fragile_guard_tilt_dampened",
        "method_name": "hrp",
        "subset_name": "phase3_4_combo_fragile_guard_tilt_dampened",
        "subset_sleeves": improved_subset + ["sector_rotation_with_sma_filter"],
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase 3.4 Variant T3: Combo1 + BOTH the fragile-only sector DD guard (T1) and the DD-gradient tilt-magnitude dampener (T2). Tests whether the two narrow tail guards compound, or whether one already absorbs most of the available tail lift.",
    },
    # ======================================================================
    # Phase FF — In-allocator integration of Phase CC's defensive_overlay_hint.
    # Identical to the production candidate (improved_phase2b_regime_confidence_boost)
    # except for the state_tilt mode, which is the Phase FF augmented version of
    # dynamic_risk_budget. The augmented tilt scales offensive sleeves by an
    # additional 0.95 multiplier on Phase CC gate weeks, BEFORE the per-sleeve
    # cap and the lighter_both overlay run, so cost / overlay / cap pipeline
    # fidelity is preserved vs production.
    # ======================================================================
    {
        "version_name": "improved_phaseff_hint_inallocator_light",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phaseff_light",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase FF Variant L1 (light): inside production allocator construction, scale offensive sleeves by additional 0.95 on weeks where defensive_overlay_hint == +1 AND market_state is NOT in {stressed_panic, recovery_fragile}. All other production logic (cap, lighter_both overlay, regime_confidence_boost meta layer, cost pipeline) is preserved unchanged.",
    },
    {
        "version_name": "improved_phaseff_hint_inallocator_state_gated",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phaseff_state_gated",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase FF Variant S1 (state_gated): inside production allocator construction, scale offensive sleeves by additional 0.95 ONLY on weeks where Phase CC's refined_state == 'neutral_deteriorating'. All other production logic preserved.",
    },
    # ======================================================================
    # Phase GG — Magnitude test for Phase CC hint integration. LAST test in
    # the Phase CC consumption branch. Same gate as Phase FF light
    # (hint=+1 AND state NOT IN {stressed_panic, recovery_fragile}); the
    # only difference vs Phase FF is the offensive-sleeve scale-down magnitude.
    # ======================================================================
    {
        "version_name": "improved_phasegg_hint_inallocator_10",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasegg_10",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase GG magnitude test: same gate as Phase FF light (hint=+1 AND state NOT IN stressed_panic/recovery_fragile); offensive sleeve multiplier = 0.90 (10pp scale-down). All other production logic preserved.",
    },
    {
        "version_name": "improved_phasegg_hint_inallocator_15",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasegg_15",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase GG magnitude test: same gate as Phase FF light; offensive sleeve multiplier = 0.85 (15pp scale-down). LAST magnitude in this branch — if neither GG1 nor GG2 helps, the Phase CC hint-consumption branch is retired.",
    },
    # ======================================================================
    # Phase HH — Refined-state regime-confidence FEATURE.
    # Identical to production EXCEPT Phase CC's refined_state nudges:
    #   HH1 (phase2b_mode='regime_confidence_boost_refined_v1'):
    #     adds ±0.02 to regime_multiplier inside apply_overlays_custom
    #     (additive confidence offset; healthy +0.02, deteriorating -0.02,
    #      recovery_confirmed +0.01).
    #   HH2 (phase2b_mode='regime_confidence_boost_refined_v2'):
    #     scales dynamic_speed by 0.85 in neutral_deteriorating only
    #     (slows re-risking; no defensive drag in healthy weeks).
    # The base ML offset (regime_confidence_boost) is preserved; refined
    # state acts as an additive feature on top, never as a sleeve/ETF
    # multiplier.
    # ======================================================================
    {
        "version_name": "improved_phasehh_refined_confidence_additive",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_refined_v1",
        "note": "Phase HH1: refined-state additive confidence adjustment. Same as production except an additional small bounded offset (±0.02) is applied to regime_multiplier based on Phase CC's refined_state. Causal walk-forward; no sleeve/ETF multiplier change.",
    },
    {
        "version_name": "improved_phasehh_refined_confidence_smoothing",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_refined_v2",
        "note": "Phase HH2: refined-state gated confidence smoothing. Same as production except dynamic_speed is scaled by 0.85 ONLY in neutral_deteriorating weeks. No change in healthy / calm / recovery_confirmed. Slows re-risking without imposing defensive drag in healthy states.",
    },
    # ======================================================================
    # Phase II — Return-participation upgrade for production using ONLY
    # existing non-Phase-CC features (market_state, breadth_sma_43,
    # breadth_26w_mom, market_trend_positive, strong_neutral helper).
    # Adds a small bounded +0.015 to regime_multiplier in clearly favorable
    # weeks. Never fires in stressed_panic / recovery_fragile.
    # ======================================================================
    {
        "version_name": "improved_phaseii_good_state_participation_light",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_participation_v1",
        "note": "Phase II1: good-state participation light. Same as production except in calm_trend OR strong_neutral weeks with breadth_sma_43>=0.65, breadth_26w_mom>=0.50, market_trend_positive>0, regime_multiplier += 0.015 (capped at 1.0). Causal walk-forward; no Phase CC artifact. Never fires in stressed_panic / recovery_fragile.",
    },
    {
        "version_name": "improved_phaseii_recovery_confirmed_participation_light",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_participation_v2",
        "note": "Phase II2: recovery-confirmed participation light. Same as production except in recovery_confirmed weeks with breadth_sma_43>=0.55 and breadth_26w_mom>=0.50, regime_multiplier += 0.015. Narrow gate (~44 weeks total). Causal walk-forward; no Phase CC artifact.",
    },
    # ======================================================================
    # Phase JJ — Controlled ML risk-dial sprint. Same production allocator,
    # tilt, overlay, cost pipeline. Only difference: p_regime_confidence is
    # OVERRIDDEN at runtime by a blended value of (production p_regime_confidence,
    # ML forward-stress probability) loaded from phase_jj_blended_predictions.csv.
    # ML model is selected and trained walk-forward in phase_jj_ml_regime_sprint.py.
    # ======================================================================
    {
        "version_name": "improved_phasejj_ml_riskdial_25",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_jj_riskdial_25",
        "note": "Phase JJ1: bounded ML risk-dial 25/75 blend. Same as production except p_regime_confidence is overridden at runtime with 0.75 * existing p_regime_confidence + 0.25 * (1 - p_ml_stress) where p_ml_stress is the best Phase JJ ML model's walk-forward forward-stress probability. All other production logic unchanged.",
    },
    {
        "version_name": "improved_phasejj_ml_riskdial_50",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_jj_riskdial_50",
        "note": "Phase JJ2: bounded ML risk-dial 50/50 blend. Same as production except p_regime_confidence is overridden at runtime with 0.50 * existing + 0.50 * (1 - p_ml_stress). All other production logic unchanged.",
    },
    # ======================================================================
    # Phase KK — Targeted Phase 2B ML refresh (Target A + Group A only).
    # Same production allocator/overlay/cost pipeline. p_regime_confidence is
    # OVERRIDDEN at runtime by the refreshed Target-A walk-forward logistic
    # regression score (loaded from phase_kk_targeta_regime_confidence_predictions.csv).
    #   KK1 'replacement': p_regime_confidence ← refreshed score
    #   KK2 'blend25':     p_regime_confidence ← 0.75 existing + 0.25 refreshed
    # No Phase CC features used.
    # ======================================================================
    {
        "version_name": "improved_phasekk_targeta_confidence_replacement",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_kk_replacement",
        "note": "Phase KK1: refreshed Target-A confidence replacement. Same as production except p_regime_confidence is replaced with the Phase KK refreshed walk-forward Target-A score (1 - p_stress_4w). All other production logic unchanged. Group A features only; no Phase CC features.",
    },
    {
        "version_name": "improved_phasekk_targeta_confidence_blend25",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost_kk_blend25",
        "note": "Phase KK2: refreshed-confidence 25/75 blend. Same as production except p_regime_confidence is replaced with 0.75 * existing + 0.25 * refreshed. Group A features only; no Phase CC features.",
    },
    # ======================================================================
    # Phase MM — Offensive participation ceiling / overlay audit.
    # Narrow structural tests only. No new sleeves, no new ML, no phase-CC
    # refined_state or defensive_overlay_hint consumption.
    #   MM1 = slightly reduce overlay cash drag in recovery_fragile only
    #   MM2 = relax lighter_both in calm_trend / strong_neutral only
    #   MM3 = recovery_confirmed sleeve fix for composite_selective_signals
    # ======================================================================
    {
        "version_name": "improved_phasemm_recovery_cash_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasemm_recovery_cash_relief",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase MM1: narrow recovery_fragile-only overlay cash relief. Same as production except the lighter_both relief is modestly widened in recovery_fragile only. No change in stressed_panic; no new sleeves; no Phase CC artifacts.",
    },
    {
        "version_name": "improved_phasemm_good_state_overlay_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasemm_good_state_overlay_relief",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase MM2: good-state overlay relief. Same as production except calm_trend / strong_neutral weeks get a slightly lighter overlay penalty when regime binding is active. recovery_fragile and stressed_panic stay unchanged.",
    },
    {
        "version_name": "improved_phasemm_recovery_confirmed_sleeve_fix",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase MM3: recovery_confirmed sleeve fix. Same as production except composite_selective_signals is modestly trimmed in recovery_confirmed and capital is redistributed within the existing sleeve set toward stronger recovery-confirmed sleeves. No new sleeves; no Phase CC artifacts.",
    },
    # ======================================================================
    # Phase NN — sleeve-to-ETF / lookthrough participation audit.
    # Narrow, state-specific fixes to reduce hidden BIL created by sleeve
    # internals during the final sleeve-to-ETF translation.
    # ======================================================================
    {
        "version_name": "improved_phasenn_recovery_lookthrough_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasenn_recovery",
        "note": "Phase NN1: recovery-only lookthrough relief. Same as production except internal sleeve BIL is modestly reduced within composite_regime_conditioned and dual_momentum_topn in recovery_confirmed / recovery_fragile before lookthrough. No stressed-panic change; no explicit SPY add.",
    },
    {
        "version_name": "improved_phasenn_neutral_lookthrough_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasenn_neutral",
        "note": "Phase NN2: neutral-healthy lookthrough relief. Same as production except composite_regime_conditioned redeploys a small amount of internal BIL only in strong-neutral weeks. No stressed-panic or fragile-recovery change; no explicit SPY add.",
    },
    {
        "version_name": "improved_phasenn_mm_plus_lookthrough_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasenn_combo",
        "note": "Phase NN3: combine Phase MM's recovery-confirmed sleeve fix with the smallest recovery-scoped lookthrough relief. Targets composite_selective_signals misuse plus hidden internal BIL in recovery states, without broad risk-on changes.",
    },
    # ======================================================================
    # Phase OO — composite_regime_conditioned sleeve-internal cash
    # architecture audit. Composite-only internal BIL relief to test whether
    # the main hidden-cash source can be reduced without damaging stress
    # protection.
    # ======================================================================
    {
        "version_name": "improved_phaseoo_composite_recovery_cash_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseoo_recovery",
        "note": "Phase OO1: composite_regime_conditioned recovery-only internal cash relief. Reduce sleeve-internal BIL only in recovery_confirmed / recovery_fragile and redeploy proportionally into the sleeve's own active ETF mix. Stressed-panic untouched.",
    },
    {
        "version_name": "improved_phaseoo_composite_neutral_cash_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseoo_neutral",
        "note": "Phase OO2: composite_regime_conditioned strong-neutral internal cash relief. Reduce sleeve-internal BIL only in healthier neutral weeks and redeploy into the sleeve's own active ETF mix. No stressed-panic change.",
    },
    {
        "version_name": "improved_phaseoo_composite_combined_cash_relief",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseoo_combo",
        "note": "Phase OO3: combine safe composite_regime_conditioned recovery + neutral internal cash relief with the narrow Phase MM recovery_confirmed sleeve fix. No stressed-panic change and no broad risk-on stack.",
    },
    # ======================================================================
    # Phase PP — direct redesign of composite_regime_conditioned's favorable-
    # state 25% BIL fallback tier. The stressed 65% tier is preserved.
    # ======================================================================
    {
        "version_name": "improved_phasepp_composite_bond_gold_fallback",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasepp_bond_gold",
        "note": "Phase PP1: direct redesign of composite_regime_conditioned's favorable-state 25% BIL tier. Keep half the 25% fallback in BIL and replace the other half with a conservative GLD/TLT fallback mix in calm, strong-neutral, and recovery states. Stressed 65% tier untouched.",
    },
    {
        "version_name": "improved_phasepp_composite_balanced_defensive_fallback",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasepp_balanced",
        "note": "Phase PP2: favorable-state composite fallback redesign with a balanced defensive mix. Replace part of the 25% BIL tier with GLD/TLT/LQD/HYG while keeping a reduced BIL sleeve-internal reserve. Stressed 65% tier untouched.",
    },
    {
        "version_name": "improved_phasepp_composite_combined_fallback_redesign",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasepp_combo",
        "note": "Phase PP3: combine the safest OO-style composite internal cash relief with the Phase MM recovery_confirmed sleeve fix and the direct favorable-state bond/gold fallback redesign. Stressed 65% tier untouched.",
    },
    # ======================================================================
    # Phase QQ — component-level / reason-level cash-defense score redesign.
    # Preserve the stressed 65% BIL tier and only act on favorable-state 25%
    # rows using the causal action labels written by the Phase QQ audit script.
    # ======================================================================
    {
        "version_name": "improved_phaseqq_cash_defense_score_fallback",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseqq_score",
        "note": "Phase QQ1: causal cash-defense score fallback. High-defense weeks keep the favorable 25% BIL tier unchanged, medium-defense weeks replace a small fraction with a conservative fallback mix, and low-defense weeks replace a larger fraction. Stressed 65% tier untouched.",
    },
    {
        "version_name": "improved_phaseqq_reason_specific_fallback",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseqq_reason",
        "note": "Phase QQ2: reason-specific fallback. Keep BIL for dangerous inferred cash reasons and only reduce BIL for mechanical or benign inferred reasons. Unknown reasons default to production behavior. Stressed 65% tier untouched.",
    },
    {
        "version_name": "improved_phaseqq_pp_combined_score_filtered",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget_phasemm_recovery_confirmed_fix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseqq_ppfiltered",
        "note": "Phase QQ3: start from the safest PP-combined base but only apply favorable-state fallback redesign when the causal cash-defense score says BIL is likely unnecessary drag. High-defense weeks keep production behavior. Stressed 65% tier untouched.",
    },
    # ======================================================================
    # Phase RR — broader sleeve-architecture / bucket allocator redesign.
    # Keep the production overlay stack, but move sleeve allocation more
    # explicitly across offensive / defensive / composite buckets in the
    # states where participation has been bottlenecked.
    # ======================================================================
    {
        "version_name": "improved_phaserr_good_state_bucket_participation",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_rr_good_state_bucket_participation",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase RR1: explicit good-state bucket participation. In calm_trend and strong-neutral healthy weeks, move a bounded amount of sleeve weight out of the composite bucket and toward the offensive participation bucket, with within-offense mix skewed toward the empirically stronger good-state sleeves. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phaserr_recovery_bucket_repair",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_rr_recovery_bucket_repair",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase RR2: explicit recovery bucket repair. In recovery_confirmed and recovery_fragile, reduce composite drag and re-route that weight toward the strongest recovery sleeves, while keeping stressed_panic unchanged and avoiding a blunt SPY-only beta add.",
    },
    {
        "version_name": "improved_phaserr_combined_bucket_allocator",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_rr_combined_bucket_allocator",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase RR3: combined bucket allocator. Blend the safe good-state participation shifts and the recovery-bucket repair into one bounded sleeve-architecture redesign, while preserving stressed-panic behavior and leaving the production overlay path intact.",
    },
    # ======================================================================
    # Phase SS — explicit in-allocator multi-bucket architecture.
    # Hard state-conditioned bucket budgets across offense / defense /
    # composite, with the incumbent overlay stack left intact to create the
    # final explicit cash/BIL posture downstream.
    # ======================================================================
    {
        "version_name": "improved_phasess_recovery_explicit_bucket",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ss_recovery_explicit_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase SS1: explicit recovery bucket budgets. Only recovery_confirmed and recovery_fragile are re-budgeted at the sleeve-allocation layer, with lower composite weight and stronger recovery offense leadership. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasess_good_state_explicit_bucket",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ss_good_state_explicit_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase SS2: explicit good-state bucket budgets. calm_trend and strong-neutral healthy weeks get a lower composite ceiling and a modest offense increase, while stressed-panic remains unchanged.",
    },
    {
        "version_name": "improved_phasess_combined_explicit_bucket",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ss_combined_explicit_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "lighter_both_targeted_narrow_plus_confirmed",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase SS3: combined explicit bucket architecture. Applies hard state-conditioned sleeve bucket budgets in good and recovery states with a tighter composite ceiling, while preserving stressed-panic guardrails and the incumbent overlay/cash stack.",
    },
    # ======================================================================
    # Phase TT — stricter two-stage bucket allocator.
    # Stage 1 coordinates desired risky-vs-cash budgets with the downstream
    # overlay path; Stage 2 allocates the risky budget across offense /
    # defense / composite with stricter composite ceilings in the targeted
    # states.
    # ======================================================================
    {
        "version_name": "improved_phasett_recovery_two_stage_bucket",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasett_recovery_two_stage_bucket",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase TT1: recovery-only two-stage bucket allocator. Recovery_confirmed and recovery_fragile get explicit risky-budget floors plus stricter offense / defense / composite risky-bucket budgets. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasett_recovery_neutral_two_stage_bucket",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_neutral_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasett_recovery_neutral_two_stage_bucket",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase TT2: recovery + neutral two-stage bucket allocator. Extends the coordinated risky-budget design into strong neutral healthy weeks while leaving calm_trend and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasett_ss1_overlay_coordinated",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ss_recovery_explicit_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasett_ss1_overlay_coordinated",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase TT3: start from the best SS1 recovery explicit bucket allocator and add only the overlay-side risky-budget coordination so the downstream cash path absorbs less of the intended recovery-state sleeve budget.",
    },
    # ======================================================================
    # Phase UU — budget-preserving overlay redesign.
    # Keep the TT1 upstream allocator and redesign only the recovery-state
    # overlay cash clawback so more of the recovery bucket decision survives
    # downstream without loosening stressed-panic protection.
    # ======================================================================
    {
        "version_name": "improved_phaseuu_tt1_overlay_preserved_recovery",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseuu_tt1_overlay_preserved_recovery",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase UU1: keep the TT1 recovery two-stage bucket allocator upstream, then cap recovery-state overlay cash more tightly so the intended bucket decision survives further downstream. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phaseuu_recovery_overlay_cash_cap",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseuu_recovery_overlay_cash_cap",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase UU2: keep the TT1 upstream allocator but add an explicit recovery-state max overlay cash cap with a small buffer over the intended state cash floor. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phaseuu_tt1_budget_aware_lighter_both",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseuu_tt1_budget_aware_lighter_both",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase UU3: keep the TT1 upstream allocator and redesign lighter_both to be budget-aware in recovery states, preserving more of the risky budget unless target-vol or panic guardrails require otherwise.",
    },
    # ======================================================================
    # Phase VV — first-class budget-aware overlay architecture.
    # Keep TT1 upstream recovery budgets, but make the overlay explicitly
    # respect those budgets unless target-vol is the true active guardrail.
    # ======================================================================
    {
        "version_name": "improved_phasevv_recovery_budget_aware_overlay",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasevv_recovery_budget_aware_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase VV1: keep the TT1 two-stage recovery allocator, but make the overlay respect the intended recovery cash budget directly unless target-vol is actually the binding guardrail.",
    },
    {
        "version_name": "improved_phasevv_recovery_overlay_tolerance_band",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasevv_recovery_overlay_tolerance_band",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase VV2: same budget-aware overlay as TT1 recovery, but allow a small 1.5pp recovery cash tolerance band before the overlay is forced back toward the intended budget.",
    },
    {
        "version_name": "improved_phasevv_recovery_neutral_budget_aware_overlay",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasevv_recovery_neutral_budget_aware_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase VV3: use the recovery budget-aware overlay and add a lighter neutral-healthy version only where overlay cash materially exceeds the upstream intended bucket budget.",
    },
    # ======================================================================
    # Phase WW — focused recovery-overlay rescue sprint.
    # Rewrite the recovery-side lighter_both branch itself so it becomes
    # budget-native rather than behaving like a separate cash engine that
    # gets corrected after the fact.
    # ======================================================================
    {
        "version_name": "improved_phaseww_recovery_budget_native_lighter_both",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_recovery_budget_native_lighter_both",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW1: rewrite the recovery-side lighter_both branch so recovery_confirmed and recovery_fragile use explicit budget-native overlay cash targets, with extra cash allowed only when true guardrails require it.",
    },
    {
        "version_name": "improved_phaseww_split_recovery_lighter_both",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_split_recovery_lighter_both",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW2: split recovery overlay rewrite. recovery_confirmed gets a freer budget-native lighter_both rule, while recovery_fragile keeps a higher cash floor and only removes clearly unjustified relief cash.",
    },
    {
        "version_name": "improved_phaseww_vv_direct_lighter_both_rewrite",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_vv_direct_lighter_both_rewrite",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW3: start from the best VV architecture and rewrite the internal lighter_both recovery/strong-neutral cash rule directly from intended budget and guardrail activation instead of adding a post-branch cap.",
    },
    {
        "version_name": "improved_phaseww_confirmed_only_lighter_both",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_confirmed_only_lighter_both",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW rescue 1: apply the direct lighter_both rewrite only in recovery_confirmed and leave recovery_fragile closer to production if the main family fails because fragile still needs more defense.",
    },
    {
        "version_name": "improved_phaseww_fragile_defense_lighter_both",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_fragile_defense_lighter_both",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW rescue 2: freer recovery_confirmed rewrite plus only mild cash relief in recovery_fragile so the branch can keep more fragile defense if the main rewrite pushes too hard.",
    },
    {
        "version_name": "improved_phaseww_vv_shadow_polish",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phaseww_vv_shadow_polish",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase WW rescue 3: smallest VV-style direct lighter_both rewrite meant only to polish the exact Sharpe gate if the broader recovery rewrites fail narrowly but the branch still looks alive.",
    },
    # ======================================================================
    # Phase XX — overlay simplification / allocator-overlay unification.
    # The allocator should choose risky/cash once; the overlay should only
    # enforce true guardrails and state cash floors, rather than creating a
    # second independent recovery cash budget.
    # ======================================================================
    {
        "version_name": "improved_phasexx_guardrail_only_overlay",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_guardrail_only_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase XX1: unify allocator and overlay by removing independent recovery regime-relief cash creation. In recovery states the overlay adds cash only for target-vol, panic/stress guardrails, or the minimum recovery cash floor.",
    },
    {
        "version_name": "improved_phasexx_guardrail_overlay_fragile_floor",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_guardrail_overlay_fragile_floor",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase XX2: guardrail-only overlay with a higher recovery-fragile cash floor so the overlay stops inventing a second cash budget while still respecting the fact that recovery_fragile is harder to loosen safely.",
    },
    {
        "version_name": "improved_phasexx_recovery_neutral_overlay_simplified",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_recovery_neutral_overlay_simplified",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase XX3: extend the simplified guardrail-only overlay to strong neutral healthy weeks as well as recovery states, while leaving calm_trend and stressed_panic alone.",
    },
    {
        "version_name": "improved_phasexx_conservative_hybrid_overlay",
        "method_name": "hrp",
        "subset_name": "phase2b_regime_confidence_boost",
        "subset_sleeves": improved_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "note": "Phase XX4: conservative hybrid. Use the simplified overlay only when duplicated cash clearly exceeds a tolerance band; otherwise stay closer to the stronger recent VV-style behavior.",
    },
    # ======================================================================
    # Phase YY — composite sleeve decomposition / sleeve-architecture
    # simplification. Expose the composite sleeve's offense / defense / cash
    # decisions to the allocator instead of hiding them inside one sleeve.
    # ======================================================================
    {
        "version_name": "improved_phaseyy_composite_cash_explicit",
        "method_name": "hrp",
        "subset_name": "phaseyy_composite_cash_explicit",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "dynamic_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase YY1: replace composite_regime_conditioned with explicit offense and defense sleeves while keeping cash at allocator level only. Tests whether hidden composite cash can be removed without another overlay rewrite.",
    },
    {
        "version_name": "improved_phaseyy_composite_offense_defense_split",
        "method_name": "hrp",
        "subset_name": "phaseyy_composite_offense_defense_split",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase YY2: decomposed composite offense/defense sleeves plus TT-style recovery bucket budgets, with overlay simplification kept at the cleaner XX reference.",
    },
    {
        "version_name": "improved_phaseyy_decomposition_vv_reference",
        "method_name": "hrp",
        "subset_name": "phaseyy_decomposition_vv_reference",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_tt_recovery_two_stage_bucket",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasevv_recovery_neutral_budget_aware_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase YY3: start from the strongest recent full-metric overlay reference, but replace the composite sleeve with explicit offense and defense sleeves so allocator decisions stay visible.",
    },
    {
        "version_name": "improved_phaseyy_conservative_decomposition",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_yy_conservative_decomposition",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase YY4: conservative decomposition. Keep fragile and stressed behavior tighter, but still move composite cash to allocator level and expose offense/defense explicitly in confirmed recovery and healthy-neutral states.",
    },
    # ======================================================================
    # Phase ZZ — Decomposed-component rebudget. Same architecture as YY
    # conservative_decomposition; rebudgets recovery_confirmed/recovery_fragile
    # bucket targets toward more offense and less explicit defense to repair
    # YY's recovery-state underperformance. stressed_panic and calm_trend
    # behaviour are unchanged from YY.
    # ======================================================================
    {
        "version_name": "improved_phasezz_recovery_offense_rebudget",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_zz_recovery_offense_rebudget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase ZZ1: recovery offense rebudget. Same as YY conservative decomposition but recovery_confirmed offense bucket target raised 0.62→0.68 (defense 0.38→0.32, mix_strength 0.40→0.50, offense_component 0.44→0.46) and recovery_fragile offense bucket target raised 0.54→0.60 (defense 0.46→0.40, mix_strength 0.30→0.40, offense_component 0.50→0.52). strong_neutral and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasezz_recovery_neutral_offense_rebudget",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_zz_recovery_neutral_offense_rebudget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase ZZ2: ZZ1 recovery shifts plus a smaller strong_neutral rebudget (offense 0.60→0.65, defense 0.40→0.35, mix_strength 0.32→0.40). stressed_panic and calm_trend unchanged.",
    },
    {
        "version_name": "improved_phasezz_confirmed_freer_fragile_conservative",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_zz_confirmed_freer_fragile_conservative",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase ZZ3: stronger shift in confirmed recovery (offense 0.62→0.72, mix_strength 0.40→0.55), smaller shift in fragile recovery (offense 0.54→0.58, mix_strength 0.30→0.36). strong_neutral and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasezz_conservative_decomposition_repair",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_zz_conservative_decomposition_repair",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase ZZ4: minimum-shift safety-first repair. recovery_confirmed offense 0.62→0.66 (mix_strength 0.40→0.45). recovery_fragile offense 0.54→0.57 (mix_strength 0.30→0.34). Safest of the four. strong_neutral and stressed_panic unchanged.",
    },
    # ======================================================================
    # Phase AAA — Recovery_confirmed-only deeper rebudget on top of ZZ2.
    # Strong_neutral and recovery_fragile remain identical to ZZ2; only
    # recovery_confirmed bucket parameters are modified.
    # ======================================================================
    {
        "version_name": "improved_phaseaaa_confirmed_offense_escalation",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_aaa_confirmed_offense_escalation",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase AAA1: recovery_confirmed offense escalation. ZZ2 baseline; recovery_confirmed offense 0.68→0.78, defense 0.32→0.22, offense_mix_strength 0.50→0.60, offense_component target 0.46→0.50. recovery_fragile and strong_neutral unchanged from ZZ2.",
    },
    {
        "version_name": "improved_phaseaaa_confirmed_offense_mix_tilt",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_aaa_confirmed_offense_mix_tilt",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase AAA2: recovery_confirmed offense-mix tilt. ZZ2 bucket totals (offense 0.68 / defense 0.32) preserved; internal offense mix biased toward cta_trend_long_only (0.26→0.34) and away from composite_selective_signals (0.10→0.06); offense_mix_strength 0.50→0.65. recovery_fragile and strong_neutral unchanged from ZZ2.",
    },
    {
        "version_name": "improved_phaseaaa_confirmed_defense_composition_repair",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_aaa_confirmed_defense_composition_repair",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase AAA3: recovery_confirmed defense composition repair. ZZ2 totals preserved; defense_target_mix biased toward taa_10m_sma 0.70 / composite_regime_defense_component 0.30; defense_mix_strength 0.55. recovery_fragile and strong_neutral unchanged from ZZ2.",
    },
    {
        "version_name": "improved_phaseaaa_confirmed_only_combined_repair",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_aaa_confirmed_only_combined_repair",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase AAA4: recovery_confirmed combined repair. recovery_confirmed offense 0.72 / defense 0.28; offense_target_mix biased toward cta_trend_long_only 0.30; offense_mix_strength 0.55; defense_target_mix biased toward taa_10m_sma 0.65; defense_mix_strength 0.45. Safest combined variant. recovery_fragile and strong_neutral unchanged from ZZ2.",
    },
    # ======================================================================
    # Phase BBB — bounded recovery_confirmed offense-composition extension
    # on top of AAA2. Same decomposed-component architecture; only the
    # recovery_confirmed component mix is adjusted.
    # ======================================================================
    {
        "version_name": "improved_phasebbb_stronger_confirmed_offense_mix",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_bbb_stronger_confirmed_offense_mix",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase BBB1: start from AAA2; recovery_confirmed only. Keep offense/defense totals at 0.68 / 0.32, keep AAA2 offense_target_mix, raise offense_mix_strength 0.65→0.75. recovery_fragile, strong_neutral, and stressed_panic unchanged from AAA2 / ZZ2.",
    },
    {
        "version_name": "improved_phasebbb_composite_offense_component_tilt",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_bbb_composite_offense_component_tilt",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase BBB2: start from AAA2; recovery_confirmed only. Keep totals at 0.68 / 0.32, tilt offense mix toward composite_regime_offense_component 0.54 and cta_trend_long_only 0.30, reduce dual_momentum_topn to 0.12 and composite_selective_signals to 0.04; offense_mix_strength 0.70.",
    },
    {
        "version_name": "improved_phasebbb_offense_defense_composition_combo",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_bbb_offense_defense_composition_combo",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase BBB3: start from AAA2; recovery_confirmed only. Keep totals at 0.68 / 0.32, use the BBB2 offense mix with offense_mix_strength 0.75, and add a defense mix repair informed by repo diagnostics: tilt defense toward composite_regime_defense_component 0.70 / taa_10m_sma 0.30 with defense_mix_strength 0.65. recovery_fragile and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phasebbb_conservative_confirmed_composition",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_bbb_conservative_confirmed_composition",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase BBB4: start from AAA2; recovery_confirmed only. Keep totals at 0.68 / 0.32 and use a minimal mix-strength increase with a modest offense mix rebalance (dual 0.14 / cta 0.32 / composite_selective 0.05 / composite_offense 0.49; offense_mix_strength 0.70). Safety-first variant.",
    },
    # ======================================================================
    # Phase CCC — bounded recovery_confirmed offense pruning on top of BBB3.
    # Keep the decomposed architecture and BBB3 bucket totals; hard-cap the
    # weak confirmed-state offense sleeves and reallocate within offense.
    # ======================================================================
    {
        "version_name": "improved_phaseccc_confirmed_cap_css",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ccc_confirmed_cap_css",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase CCC1: start from BBB3; recovery_confirmed only. Hard-cap composite_selective_signals inside the confirmed offense bucket and reallocate the freed offense weight mostly to composite_regime_offense_component and secondarily to cta_trend_long_only. recovery_fragile and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phaseccc_confirmed_cap_dual",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ccc_confirmed_cap_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase CCC2: start from BBB3; recovery_confirmed only. Hard-cap dual_momentum_topn inside the confirmed offense bucket and reallocate the freed weight to composite_regime_offense_component and cta_trend_long_only. recovery_fragile and stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phaseccc_confirmed_cap_dual_css",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ccc_confirmed_cap_dual_css",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase CCC3: start from BBB3; recovery_confirmed only. Hard-cap both dual_momentum_topn and composite_selective_signals, then reallocate the freed offense weight mostly to composite_regime_offense_component and secondarily to cta_trend_long_only. Keeps BBB3 bucket totals and defense structure.",
    },
    {
        "version_name": "improved_phaseccc_conservative_confirmed_pruning",
        "method_name": "hrp",
        "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40,
        "rerisk_speed": 1.00,
        "state_tilt": "phase_ccc_conservative_confirmed_pruning",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00,
        "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase CCC4: start from BBB3; recovery_confirmed only. Apply smaller confirmed-state caps to dual_momentum_topn and composite_selective_signals and reallocate conservatively within the offense bucket. Safety-first variant.",
    },
    # ======================================================================
    # Phase DDD — harder confirmed-only weak-sleeve exclusion on top of CCC2.
    # Start from CCC2 (dual cap 0.12). Push the dual cap lower; optional CSS
    # soft-cap; optional defense receiver. Strong_neutral, recovery_fragile,
    # stressed_panic identical to CCC.
    # ======================================================================
    {
        "version_name": "improved_phaseddd_confirmed_harder_dual_cap",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_confirmed_harder_dual_cap",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD1: start from CCC2; recovery_confirmed only. Push dual_momentum_topn share-cap from 0.12 -> 0.07; reallocate 70% to composite_regime_offense_component / 30% to cta_trend_long_only.",
    },
    {
        "version_name": "improved_phaseddd_confirmed_near_exclude_dual",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD2: nearly exclude dual_momentum_topn in recovery_confirmed (cap 0.03). Reallocate 70% to composite_regime_offense_component / 30% to cta_trend_long_only.",
    },
    {
        "version_name": "improved_phaseddd_confirmed_dual_hard_css_soft",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_confirmed_dual_hard_css_soft",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD3: dual_momentum_topn cap 0.06 plus mild CSS cap 0.10 in recovery_confirmed. Reallocate 75% to composite_regime_offense_component / 25% to cta_trend_long_only.",
    },
    {
        "version_name": "improved_phaseddd_confirmed_defensive_balanced_substitution",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_confirmed_defensive_balanced_substitution",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD4: dual cap 0.06 + CSS cap 0.12. Reallocate 55% to composite_regime_offense_component, 25% to cta_trend_long_only, 20% to composite_regime_defense_component (defensive receiver).",
    },
    # ---- Optional rescue variants — registered but only used if main DDD fail ----
    {
        "version_name": "improved_phaseddd_minimal_dual_polish",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_minimal_dual_polish",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD5 (rescue): minimal polish on CCC2. dual cap 0.10 (down from 0.12); 100% reallocation to composite_regime_offense_component.",
    },
    {
        "version_name": "improved_phaseddd_confirmed_comp_off_receiver",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase_ddd_confirmed_comp_off_receiver",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase DDD6 (rescue): same dual cap as DDD1 (0.07) but 100% reallocation to composite_regime_offense_component (no cta share).",
    },
    # ======================================================================
    # Phase EEE — Turnover-smoothed aggressive dual cap. Reuse DDD2/DDD1 tilt
    # branches (no new tilt code) and lower rerisk_speed so the production
    # overlay's dynamic_speed mechanism smooths cap engagement transitions
    # in recovery_confirmed. recovery_fragile and stressed_panic unchanged.
    # ======================================================================
    {
        "version_name": "improved_phaseeee_smoothed_near_exclude_dual",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase EEE1: DDD2 near-exclude dual (cap 0.03) with rerisk_speed lowered 1.00 -> 0.80 in recovery_confirmed. The overlay dynamic_speed mechanism smooths cap engagement transitions; total turnover should drop materially while preserving DDD2's confirmed repair.",
    },
    {
        "version_name": "improved_phaseeee_turnover_aware_dual_cap",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.90,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase EEE2: DDD2 near-exclude dual (cap 0.03) with rerisk_speed lowered 1.00 -> 0.90 (moderate smoothing). Lighter smoothing than EEE1, target preserving more of DDD2's recovery_confirmed repair while still reducing turnover under the 1.10x gate.",
    },
    {
        "version_name": "improved_phaseeee_selective_dual_escalation",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.95,
        "state_tilt": "phase_ddd_confirmed_harder_dual_cap",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseyy_decomposed",
        "note": "Phase EEE3: DDD1 harder dual cap (0.07) with rerisk_speed lowered 1.00 -> 0.95 (very mild smoothing). Conservative variant: starts from the safe DDD1 base and adds a small turnover cushion.",
    },
    # ======================================================================
    # Phase FFF — Layer 2A re-engineered offense_component on top of EEE1.
    # Same EEE1 architecture (state_tilt phase_ddd_confirmed_near_exclude_dual,
    # rerisk_speed 0.80), but the offense_component is built from a narrower
    # ETF subset that excludes weak recovery_confirmed contributors.
    # ======================================================================
    {
        "version_name": "improved_phasefff_recovery_quality_filtered_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasefff_quality_filtered",
        "note": "Phase FFF1: EEE1 architecture; offense_component rebuilt to exclude PDBC/DBA (commodities) and EWJ (Japan-only). Keeps SPY/QQQ/IWM/EFA/VEA/VWO/VNQ.",
    },
    {
        "version_name": "improved_phasefff_recovery_confirmed_tilted_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasefff_core_equity",
        "note": "Phase FFF2: EEE1 architecture; offense_component rebuilt as core-equity-only (SPY/QQQ/IWM/EFA/VEA/VWO). Drops EWJ/VNQ/PDBC/DBA. Highest concentration toward broad equity.",
    },
    {
        "version_name": "improved_phasefff_robust_composite_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasefff_robust",
        "note": "Phase FFF3: EEE1 architecture; offense_component rebuilt to drop only commodities (PDBC/DBA). Keeps all 8 equity ETFs incl. EWJ/VNQ.",
    },
    {
        "version_name": "improved_phasefff_conservative_offense_polish",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasefff_polish",
        "note": "Phase FFF4: EEE1 architecture; offense_component rebuilt to drop only PDBC (the weakest commodity). Smallest safe Layer 2A change.",
    },
    {
        "version_name": "improved_phaseggg_confirmed_only_robust_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase GGG1: EEE1 architecture; offense_component is broad EEE1 in all states EXCEPT recovery_confirmed, which uses FFF3 robust subset (drop PDBC + DBA).",
    },
    {
        "version_name": "improved_phasennn_ml_risk_dial_overlay",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost_nnn_risk_dial",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase NNN1: GGG1 plus a bounded hard-ML risk dial. Uses OOS NNN underperformance/stress probabilities to modestly lower regime_multiplier only when predicted GGG1 risk is high. GGG1 component logic unchanged.",
    },
    {
        "version_name": "improved_phasennn_ml_opportunity_dial_overlay",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost_nnn_opportunity_dial",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase NNN2: GGG1 plus a bounded hard-ML opportunity dial. Uses low OOS NNN underperformance/stress probabilities to modestly lift regime_multiplier in favorable states only. GGG1 component logic unchanged.",
    },
    {
        "version_name": "improved_phasejjj3_targeted_lookthrough_repair",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_jjj3_calm_css_cap",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase JJJ3: GGG1 plus one targeted calm_trend cap on composite_selective_signals share of the offense bucket; excess stays in offense-family sleeves.",
    },
    {
        "version_name": "improved_phasejjj4_state_risk_contribution_caps",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_jjj4_state_risk_contribution_caps",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase JJJ4-1: GGG1 plus a recovery_confirmed risk-contribution cap on composite_regime_offense_component; excess stays in cta_trend_long_only.",
    },
    {
        "version_name": "improved_phasejjj4_adaptive_mom_vol_corr_budget",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_jjj4_adaptive_mom_vol_corr_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase JJJ4-2: GGG1 plus small causal momentum/volatility and state-leadership tilts bounded at +/-6% before overlay/lookthrough.",
    },
    {
        "version_name": "improved_phasejjj4_conservative_adaptive_risk_budget",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_jjj4_conservative_adaptive_risk_budget",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase JJJ4-3: GGG1 plus a minimal recovery_fragile defense-bucket risk budget shift from defense_component to taa_10m_sma.",
    },
    {
        "version_name": "improved_phaselll_recovery_defense_filter",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaselll_recovery_filter",
        "note": "Phase LLL1: GGG1 offense logic unchanged; defense_component drops TLT in recovery_confirmed and GLD in recovery_fragile. Stressed-panic defense unchanged.",
    },
    {
        "version_name": "improved_phaselll_recovery_defense_blend",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaselll_recovery_blend",
        "note": "Phase LLL2: GGG1 offense logic unchanged; defense_component uses 50/50 original plus recovery-filtered defense in recovery_confirmed/recovery_fragile only.",
    },
    {
        "version_name": "improved_phaselll_conservative_defense_polish",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaselll_conservative_polish",
        "note": "Phase LLL3: GGG1 offense logic unchanged; defense_component uses a 25% recovery-state filter blend, the smallest defense rebuild.",
    },
    {
        "version_name": "improved_phasemmm_recovery_confirmed_css_cap",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_mmm_recovery_confirmed_css_cap",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase MMM1: GGG1 plus recovery_confirmed-only CSS cap at 0.08 of offense bucket; freed weight goes to offense_component/CTA.",
    },
    {
        "version_name": "improved_phasemmm_recovery_confirmed_css_filter",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasemmm_css_filter",
        "note": "Phase MMM2: GGG1 plus recovery_confirmed-only CSS internal filter dropping DBA/TLT; all other states unchanged.",
    },
    {
        "version_name": "improved_phasemmm_conservative_css_polish",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_mmm_conservative_css_polish",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase MMM3: GGG1 plus recovery_confirmed-only conservative CSS cap at 0.12 of offense bucket.",
    },
    {
        "version_name": "improved_phaseooo6_efa_spy_selective_tilt",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ooo6_efa_spy_selective_tilt",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase OOO6-1: GGG1 plus a small calm/neutral offense-family tilt when efa_spy_raw_top10_event fires. Recovery and stressed states unchanged.",
    },
    {
        "version_name": "improved_phaseooo6_efa_spy_vol_filtered_tilt",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ooo6_efa_spy_vol_filtered_tilt",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase OOO6-2: GGG1 plus a smaller calm/neutral offense-family tilt when efa_spy_vol_filtered_top20_event fires. Recovery and stressed states unchanged.",
    },
    {
        "version_name": "improved_phaseooo6_efa_spy_trend_confirmed_tilt",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ooo6_efa_spy_trend_confirmed_tilt",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase OOO6-3: GGG1 plus a small calm/neutral offense-family tilt only when EFA/SPY strength and market trend/breadth confirmation both fire.",
    },
    {
        "version_name": "improved_phasesss3_calm_old_low_stress_derisk",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_sss3_calm_old_low_stress_derisk",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase SSS3-1: GGG1 plus a tiny mature-calm sequence de-risk overlay, shifting at most 1.5% sleeve mass from offense to existing defense sleeves when calm_old_low_stress_signal fires.",
    },
    {
        "version_name": "improved_phasesss3_stress_new_state_defense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_sss3_stress_new_state_defense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase SSS3-2: GGG1 plus a tiny early-stressed-panic defense overlay, shifting at most 2% sleeve mass from offense to existing defense sleeves when stress_new_state_signal fires in stressed_panic.",
    },
    {
        "version_name": "improved_phasesss3_recovery_sequence_rerisk",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_sss3_recovery_sequence_rerisk",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase SSS3-3: GGG1 plus a tiny recovery/calm re-risk confirmation tilt, shifting at most 1.5% sleeve mass from existing defense sleeves to offense-approved sleeves when qqq_efa_spy_trend_after_calm_or_recovery_signal fires.",
    },
    {
        "version_name": "improved_phasesss3_combined_sequence_overlay",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_sss3_combined_sequence_overlay",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase SSS3-4: GGG1 plus conservative combined sequence overlay. Stress/calm de-risk warnings dominate conflicts; re-risk confirmation applies only when no de-risk sequence warning is active.",
    },
    {
        "version_name": "improved_phaseggg_confirmed_only_quality_filtered_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_quality",
        "note": "Phase GGG2: EEE1 architecture; broad offense in all states except recovery_confirmed, which uses FFF1 quality_filtered subset (drop PDBC + DBA + EWJ).",
    },
    {
        "version_name": "improved_phaseggg_blended_confirmed_robust_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_blended_robust",
        "note": "Phase GGG3: EEE1 architecture; broad offense in all states except recovery_confirmed, which uses 50/50 blend of broad EEE1 and FFF3 robust subsets (conservative half-step).",
    },
    {
        "version_name": "improved_phasehhh_confirmed_stressed_robust_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasehhh_confirmed_stressed_robust",
        "note": "Phase HHH1: GGG1 architecture extended; FFF3 robust offense_component in BOTH recovery_confirmed AND stressed_panic. Broad EEE1 in calm_trend / neutral_mixed / recovery_fragile.",
    },
    {
        "version_name": "improved_phasehhh_confirmed_robust_stressed_blended_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasehhh_confirmed_robust_stressed_blended",
        "note": "Phase HHH2: GGG1 RC swap kept; stressed_panic uses 50/50 blend of broad + FFF3 robust (safety-first stressed_panic version).",
    },
    {
        "version_name": "improved_phasehhh_confirmed_quality_stressed_robust_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phasehhh_confirmed_quality_stressed_robust",
        "note": "Phase HHH3: stronger RC filter (FFF1 quality_filtered drops PDBC + DBA + EWJ) paired with FFF3 robust in stressed_panic.",
    },
    {
        "version_name": "improved_phase2_aggressive_neutral_cash_unlock",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C1: GGG1 base plus aggressive regime_multiplier boost (+0.08 flat) in neutral_mixed/calm/recovery_confirmed. Targets the neutral_mixed BIL bottleneck. State_tilt unchanged from GGG1.",
    },
    {
        "version_name": "improved_phase2_aggressive_calm_offense_unlock",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase2_aggressive_calm_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C2: GGG1 base plus calm_trend defense->offense sleeve shift (-0.09 from defense_component+taa). Targets calm_trend underparticipation. Phase2b unchanged from GGG1.",
    },
    {
        "version_name": "improved_phase2_aggressive_recovery_confirmed_boost",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 1.00,
        "state_tilt": "phase2_aggressive_recovery_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C3: GGG1 base plus recovery_confirmed defense->offense shift (-0.06) and faster rerisk_speed (1.00). Tests high-opportunity recovery participation. recovery_fragile untouched.",
    },
    {
        "version_name": "improved_phase2_aggressive_nonstressed_offense_mandate",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 1.00,
        "state_tilt": "phase2_aggressive_nonstressed_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C4: Combined neutral cash unlock + calm/neutral defense->offense + recovery boost + faster rerisk. Main 9-10.5% target candidate. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase2_aggressive_balanced_mandate",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase2_aggressive_balanced_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C5: Conservative aggressive mandate. Smaller shifts (calm -0.06, neutral -0.03). Same phase2b boost as C4. Targets 9-10% with better Sharpe/drawdown control.",
    },
    {
        "version_name": "improved_phase2_aggressive_stretch_mandate",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.60, "rerisk_speed": 1.00,
        "state_tilt": "phase2_aggressive_stretch_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_full_mandate",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 2 C6: Stretch mandate. Large shifts (calm -0.12, neutral -0.08, RC -0.07) plus full +0.10 regime boost. Targets 10.5-12% but allows max DD 20-22%. Reject if disguised SPY.",
    },
    {
        "version_name": "improved_phase3_breadth_neutral_cash_unlock",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "p3_neutral_us",
        "note": "Phase 3 C1: neutral_mixed breadth_on offense_component → US pure (SPY/QQQ/IWM). Phase2b neutral boost. Fixes neutral_mixed US-offense quality.",
    },
    {
        "version_name": "improved_phase3_high_breadth_calm_us_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "p3_calm_us",
        "note": "Phase 3 C2: calm_trend breadth_on offense_component → US pure (SPY/QQQ/IWM). Fixes calm_trend opportunity cost by removing international/commodity drag.",
    },
    {
        "version_name": "improved_phase3_qqq_us_growth_leadership",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "p3_qqq_growth",
        "note": "Phase 3 C3: calm_trend breadth_on → QQQ/SPY/VUG growth offense; neutral_mixed → blended US growth/pure. Concentrated US growth tilt.",
    },
    {
        "version_name": "improved_phase3_breadth_credit_risk_on_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase_ddd_confirmed_near_exclude_dual",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "p3_credit_us",
        "note": "Phase 3 C4: double-confirmed signal (breadth_sma_43>=0.65 + market_trend + canary) → US pure offense. Stricter signal filter.",
    },
    {
        "version_name": "improved_phase3_balanced_breadth_aggressive",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 1.00,
        "state_tilt": "phase2_aggressive_nonstressed_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "p3_balanced_us",
        "note": "Phase 3 C5: calm+neutral breadth_on → US pure offense PLUS Phase2 nonstressed_offense sleeve_tilt PLUS neutral boost. Combined ETF + sleeve + regime upgrade.",
    },
    {
        "version_name": "improved_phase3_stretch_breadth_aggressive",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phaseyy_decomposed_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.60, "rerisk_speed": 1.00,
        "state_tilt": "phase2_aggressive_stretch_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_full_mandate",
        "internal_redeploy": "p3_stretch",
        "note": "Phase 3 C6: All breadth_on states → QQQ/SPY/IWM growth offense PLUS Phase2 stretch sleeve_tilt PLUS full mandate boost. Maximum return target 10.5-12%.",
    },
    {
        "version_name": "improved_phase4_sector_small_overlay",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_small_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase4_sector_small_overlay",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4 C1: GGG1 plus a 10-15% top5 sector momentum sleeve only when sector_breadth_confirmed is active. Clean incremental overlay; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4_sector_20pct_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_top3_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 1.00,
        "state_tilt": "phase4_sector_20pct_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4 C2: GGG1 plus a dedicated 20% top3 sector momentum sleeve in sector_breadth_confirmed states, funded from cash/defense/old offense. stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4_sector_25pct_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_top3_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.55, "rerisk_speed": 1.00,
        "state_tilt": "phase4_sector_25pct_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4 C3: GGG1 plus a dedicated 25% top3 sector momentum sleeve in sector_breadth_confirmed states. Aggressive return-unlock test; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4_balanced_sector_breadth",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_balanced_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.90,
        "state_tilt": "phase4_balanced_sector_breadth",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4 C4: GGG1 plus a 20% diversified top5/inverse-vol sector sleeve in sector_breadth_confirmed states. Designed for Sharpe preservation; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4_stretch_sector_momentum",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_stretch_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.60, "rerisk_speed": 1.00,
        "state_tilt": "phase4_stretch_sector_momentum",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_full_mandate",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4 C5: GGG1 plus a 25% concentrated top3 sector sleeve only in high_breadth_sector_bull states. Stretch return candidate; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4_sector_us_hybrid",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4_sector_balanced_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.90,
        "state_tilt": "phase4_sector_us_hybrid",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "p3_calm_us",
        "note": "Phase 4 C6: Phase 3 calm US offense component plus a 16% balanced sector sleeve when sector_leadership_confirmed is active. Hybrid risk-adjusted test; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4b_refined_sector_small_overlay",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_small_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.40, "rerisk_speed": 0.80,
        "state_tilt": "phase4b_refined_sector_small_overlay",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4B C1: GGG1 plus a 10-15% smoother top5 sector sleeve only in high_quality_sector_bull weeks. Sharpe-first refinement; stressed_panic/recovery_fragile unchanged.",
    },
    {
        "version_name": "improved_phase4b_refined_sector_20pct",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.95,
        "state_tilt": "phase4b_refined_sector_20pct",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4B C2: GGG1 plus a refined 20% defensive-aware top5 sector sleeve in high-quality/calm-leadership sector regimes. Avoids weak neutral and recovery_fragile states.",
    },
    {
        "version_name": "improved_phase4b_refined_sector_25pct_selective",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_25_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.55, "rerisk_speed": 0.95,
        "state_tilt": "phase4b_refined_sector_25pct_selective",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4B C3: GGG1 plus a 25% strict top3 sector sleeve only when the fixed sector_quality_score is high. Selective return-unlock test; stressed_panic/recovery_fragile unchanged.",
    },
    {
        "version_name": "improved_phase4b_sector_phase3_hybrid",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_hybrid_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.90,
        "state_tilt": "phase4b_sector_phase3_hybrid",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "regime_confidence_boost",
        "internal_redeploy": "p3_calm_us",
        "note": "Phase 4B C4: Phase 3 calm US offense plus a 16% SPY/QQQ-blended refined sector sleeve in high-quality/calm leadership sector regimes. Risk-adjusted hybrid; stressed_panic unchanged.",
    },
    {
        "version_name": "improved_phase4b_return_unlock_stretch",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_stretch_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.60, "rerisk_speed": 1.00,
        "state_tilt": "phase4b_return_unlock_stretch",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_full_mandate",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 4B C5: strongest return-unlock variant. 25% strict top3 sector sleeve in highest-quality sector regimes with full aggressive mandate boost. Reject if Sharpe/drawdown/stress checks fail.",
    },
    {
        "version_name": "improved_phase6_neutral_classifier_unlock",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.95,
        "state_tilt": "phase6_neutral_classifier_unlock",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 6 C1: Phase4B best + classifier-gated neutral boost. In high_quality_neutral (breadth>=0.70, canary, trend, good_prob>=0.60): +4pp sector. In low_quality_neutral: -3pp retract.",
    },
    {
        "version_name": "improved_phase6_calm_bull_quality_offense",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.95,
        "state_tilt": "phase6_calm_bull_quality_offense",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 6 C2: Phase4B best + extra +4pp sector in extreme_quality_calm (breadth>=0.80, trend, canary). Targets calm_trend opportunity cost.",
    },
    {
        "version_name": "improved_phase6_recovery_quality_rerisk",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 1.00,
        "state_tilt": "phase6_recovery_quality_rerisk",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 6 C3: Phase4B best + extra +4pp sector in strong_recovery (breadth_change>=0, good_prob>=0.55). Faster rerisk. recovery_fragile unchanged.",
    },
    {
        "version_name": "improved_phase6_continuous_aggression_score",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.95,
        "state_tilt": "phase6_continuous_aggression_score",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 6 C4: Phase4B best + continuous 0-1 aggression score from breadth/b26w/trend/canary/transition. +3pp sector when score>=0.72, -2pp when score<=0.28.",
    },
    {
        "version_name": "improved_phase6_balanced_classifier_rebuild",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.50, "rerisk_speed": 0.95,
        "state_tilt": "phase6_balanced_classifier_rebuild",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 6 C5: Phase4B best + balanced combination of all Phase 6 classifier signals. +3.5pp in high_quality_neutral/extreme_quality_calm; +2.5pp in strong_recovery; -2.5pp in low_quality_neutral.",
    },
    {
        "version_name": "improved_phase7_larger_sector_calm",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.55, "rerisk_speed": 1.00,
        "state_tilt": "phase7_larger_sector_calm",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 7 C1: Phase4B base + 28% sector budget (vs 20%) when quality signals fire. Tests larger allocator commitment to sector offense.",
    },
    {
        "version_name": "improved_phase7_expression_boost",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.55, "rerisk_speed": 0.95,
        "state_tilt": "phase7_expression_boost",
        "layer3_expression_mode": "phase7_aggressive_expression",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 7 C2: Phase4B base + aggressive layer3 expression (shift_budget=0.12 in calm vs 0.06 normally). Rebalances sleeve mix within the risky budget toward offense.",
    },
    {
        "version_name": "improved_phase7_max_sector_rerisk",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.65, "rerisk_speed": 1.00,
        "state_tilt": "phase7_max_sector_rerisk",
        "layer3_expression_mode": "none",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 7 C3: Phase4B + 28% sector + max rerisk (1.0) + faster sleeve reallocation (0.65). Tests speed-of-commitment improvement.",
    },
    {
        "version_name": "improved_phase7_combined_offensive",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.60, "rerisk_speed": 1.00,
        "state_tilt": "phase7_combined_offensive",
        "layer3_expression_mode": "phase7_aggressive_expression",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_neutral_boost",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 7 C4: Combined — 28% sector budget + aggressive layer3 expression + max rerisk + neutral boost. Main 8%+ return candidate.",
    },
    {
        "version_name": "improved_phase7_stretch_target",
        "method_name": "hrp", "subset_name": "phaseyy_conservative_decomposition",
        "subset_sleeves": phase4b_sector_20_subset,
        "overlay_variant": "good_state_fragile_expression",
        "sleeve_reallocation_speed": 0.70, "rerisk_speed": 1.00,
        "state_tilt": "phase7_stretch_target",
        "layer3_expression_mode": "phase7_aggressive_expression",
        "overlay_penalty_mode": "phasexx_conservative_hybrid_overlay",
        "target_vol_ceil": 1.00, "phase2b_mode": "phase2_aggressive_full_mandate",
        "internal_redeploy": "phaseggg_confirmed_robust",
        "note": "Phase 7 C5: Stretch — 32% sector budget + aggressive expression + full mandate. Targets 8.5%+. Reject if max DD > 22% or Sharpe < 0.90.",
    },
]

if FILTERED_VERSION_BUILD:
    version_specs = [spec for spec in version_specs if spec["version_name"] in FILTERED_VERSION_NAMES]
    print(f"Filtered improvement build: {len(version_specs)} versions -> {sorted(FILTERED_VERSION_NAMES)}")


benchmark_market_returns = load_benchmark_returns("strategy_returns_baseline_market_proxy_buy_hold.csv")
benchmark_6040_returns = load_benchmark_returns("strategy_returns_baseline_60_40_proxy.csv")

version_results: dict[str, dict] = {}
version_baselines: dict[str, dict] = {}

for version in version_specs:
    version_redeploy_mode = version.get("internal_redeploy", False)
    if version_redeploy_mode == "restricted":
        version_sleeve_return_panel = redeployed_restricted_return_panel
        version_sleeve_positions = redeployed_restricted_positions
    elif version_redeploy_mode == "phasenn_recovery":
        version_sleeve_return_panel = phasenn_recovery_return_panel
        version_sleeve_positions = phasenn_recovery_positions
    elif version_redeploy_mode == "phasenn_neutral":
        version_sleeve_return_panel = phasenn_neutral_return_panel
        version_sleeve_positions = phasenn_neutral_positions
    elif version_redeploy_mode == "phasenn_combo":
        version_sleeve_return_panel = phasenn_combo_return_panel
        version_sleeve_positions = phasenn_combo_positions
    elif version_redeploy_mode == "phaseoo_recovery":
        version_sleeve_return_panel = phaseoo_recovery_return_panel
        version_sleeve_positions = phaseoo_recovery_positions
    elif version_redeploy_mode == "phaseoo_neutral":
        version_sleeve_return_panel = phaseoo_neutral_return_panel
        version_sleeve_positions = phaseoo_neutral_positions
    elif version_redeploy_mode == "phaseoo_combo":
        version_sleeve_return_panel = phaseoo_combo_return_panel
        version_sleeve_positions = phaseoo_combo_positions
    elif version_redeploy_mode == "phasepp_bond_gold":
        version_sleeve_return_panel = phasepp_bond_gold_return_panel
        version_sleeve_positions = phasepp_bond_gold_positions
    elif version_redeploy_mode == "phasepp_balanced":
        version_sleeve_return_panel = phasepp_balanced_return_panel
        version_sleeve_positions = phasepp_balanced_positions
    elif version_redeploy_mode == "phasepp_combo":
        version_sleeve_return_panel = phasepp_combo_return_panel
        version_sleeve_positions = phasepp_combo_positions
    elif version_redeploy_mode == "phaseqq_score":
        version_sleeve_return_panel = phaseqq_score_return_panel
        version_sleeve_positions = phaseqq_score_positions
    elif version_redeploy_mode == "phaseqq_reason":
        version_sleeve_return_panel = phaseqq_reason_return_panel
        version_sleeve_positions = phaseqq_reason_positions
    elif version_redeploy_mode == "phaseqq_ppfiltered":
        version_sleeve_return_panel = phaseqq_ppfiltered_return_panel
        version_sleeve_positions = phaseqq_ppfiltered_positions
    elif version_redeploy_mode == "phaseyy_decomposed":
        version_sleeve_return_panel = phaseyy_decomposed_return_panel
        version_sleeve_positions = phaseyy_decomposed_positions
    elif version_redeploy_mode == "phasefff_quality_filtered":
        version_sleeve_return_panel = phasefff_quality_filtered_return_panel
        version_sleeve_positions = phasefff_quality_filtered_positions
    elif version_redeploy_mode == "phasefff_core_equity":
        version_sleeve_return_panel = phasefff_core_equity_return_panel
        version_sleeve_positions = phasefff_core_equity_positions
    elif version_redeploy_mode == "phasefff_robust":
        version_sleeve_return_panel = phasefff_robust_return_panel
        version_sleeve_positions = phasefff_robust_positions
    elif version_redeploy_mode == "phasefff_polish":
        version_sleeve_return_panel = phasefff_polish_return_panel
        version_sleeve_positions = phasefff_polish_positions
    elif version_redeploy_mode == "phaseggg_confirmed_robust":
        version_sleeve_return_panel = phaseggg_confirmed_robust_return_panel
        version_sleeve_positions = phaseggg_confirmed_robust_positions
    elif version_redeploy_mode == "phaseggg_confirmed_quality":
        version_sleeve_return_panel = phaseggg_confirmed_quality_return_panel
        version_sleeve_positions = phaseggg_confirmed_quality_positions
    elif version_redeploy_mode == "phaseggg_blended_robust":
        version_sleeve_return_panel = phaseggg_blended_robust_return_panel
        version_sleeve_positions = phaseggg_blended_robust_positions
    elif version_redeploy_mode == "phaselll_recovery_filter":
        version_sleeve_return_panel = phaselll_recovery_filter_return_panel
        version_sleeve_positions = phaselll_recovery_filter_positions
    elif version_redeploy_mode == "phaselll_recovery_blend":
        version_sleeve_return_panel = phaselll_recovery_blend_return_panel
        version_sleeve_positions = phaselll_recovery_blend_positions
    elif version_redeploy_mode == "phaselll_conservative_polish":
        version_sleeve_return_panel = phaselll_conservative_polish_return_panel
        version_sleeve_positions = phaselll_conservative_polish_positions
    elif version_redeploy_mode == "phasemmm_css_filter":
        version_sleeve_return_panel = phasemmm_css_filter_return_panel
        version_sleeve_positions = phasemmm_css_filter_positions
    elif version_redeploy_mode == "phasehhh_confirmed_stressed_robust":
        version_sleeve_return_panel = phasehhh_confirmed_stressed_robust_return_panel
        version_sleeve_positions = phasehhh_confirmed_stressed_robust_positions
    elif version_redeploy_mode == "phasehhh_confirmed_robust_stressed_blended":
        version_sleeve_return_panel = phasehhh_confirmed_robust_stressed_blended_return_panel
        version_sleeve_positions = phasehhh_confirmed_robust_stressed_blended_positions
    elif version_redeploy_mode == "phasehhh_confirmed_quality_stressed_robust":
        version_sleeve_return_panel = phasehhh_confirmed_quality_stressed_robust_return_panel
        version_sleeve_positions = phasehhh_confirmed_quality_stressed_robust_positions
    elif version_redeploy_mode == "p3_neutral_us":
        version_sleeve_return_panel = p3_neutral_us_return_panel
        version_sleeve_positions = p3_neutral_us_positions
    elif version_redeploy_mode == "p3_calm_us":
        version_sleeve_return_panel = p3_calm_us_return_panel
        version_sleeve_positions = p3_calm_us_positions
    elif version_redeploy_mode == "p3_qqq_growth":
        version_sleeve_return_panel = p3_qqq_growth_return_panel
        version_sleeve_positions = p3_qqq_growth_positions
    elif version_redeploy_mode == "p3_credit_us":
        version_sleeve_return_panel = p3_credit_us_return_panel
        version_sleeve_positions = p3_credit_us_positions
    elif version_redeploy_mode == "p3_balanced_us":
        version_sleeve_return_panel = p3_balanced_us_return_panel
        version_sleeve_positions = p3_balanced_us_positions
    elif version_redeploy_mode == "p3_stretch":
        version_sleeve_return_panel = p3_stretch_return_panel
        version_sleeve_positions = p3_stretch_positions
    elif bool(version_redeploy_mode):
        version_sleeve_return_panel = redeployed_sleeve_return_panel
        version_sleeve_positions = redeployed_sleeve_positions
    else:
        version_sleeve_return_panel = base_sleeve_return_panel
        version_sleeve_positions = base_sleeve_positions
    sleeve_alloc, weight_panel, path, diagnostics, beta_overlay_panel, metrics = run_subset_custom(
        version["method_name"],
        version["subset_name"],
        version["subset_sleeves"],
        overlay_variant=version["overlay_variant"],
        speed=version["sleeve_reallocation_speed"],
        rerisk_speed=version["rerisk_speed"],
        state_tilt=version["state_tilt"],
        layer3_expression_mode=version.get("layer3_expression_mode", "none"),
        overlay_penalty_mode=version.get("overlay_penalty_mode", "none"),
        speed_mode=version.get("speed_mode", "default"),
        improving_speed=version.get("improving_speed"),
        deteriorating_speed=version.get("deteriorating_speed"),
        beta_overlay_mode=version.get("beta_overlay_mode", "none"),
        target_vol_ceil=version["target_vol_ceil"],
        market_state_history=market_state_history,
        stabilize_market_state=bool(version.get("stabilize_market_state", False)),
        phase2b_mode=version.get("phase2b_mode", "none"),
        checkpoint_name=version["version_name"],
        sleeve_return_panel=version_sleeve_return_panel,
        sleeve_positions=version_sleeve_positions,
    )

    weight_panel.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version['version_name']}.csv")
    sleeve_alloc.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version['version_name']}.csv")
    path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version['version_name']}.csv")

    regime_split = ns5["regime_split_summary"](version["version_name"], path["net_return"], ns5["regime_states"].get("risk_state", pd.Series(dtype=object)))
    subperiod_split = ns5["subperiod_summary"](version["version_name"], path["net_return"])
    if not regime_split.empty:
        portfolio_version_regime_rows.append(regime_split)
    if not subperiod_split.empty:
        portfolio_version_subperiod_rows.append(subperiod_split)

    avg_bil = weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan
    avg_spy = weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan
    avg_cash = diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan

    row = {
        **version,
        "beta_overlay_mode": version.get("beta_overlay_mode", "none"),
        **metrics,
        "avg_bil_weight": avg_bil,
        "avg_spy_weight": avg_spy,
        "avg_cash_weight": avg_cash,
        "avg_beta_overlay_spy": beta_overlay_panel["beta_overlay_spy"].mean() if not beta_overlay_panel.empty else 0.0,
        "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
        "avg_layer3_expression_shift": diagnostics["layer3_expression_shift"].mean() if not diagnostics.empty and "layer3_expression_shift" in diagnostics.columns else 0.0,
        "layer3_expression_trigger_rate": diagnostics["layer3_expression_triggered"].mean() if not diagnostics.empty and "layer3_expression_triggered" in diagnostics.columns else 0.0,
    }
    family = version["method_name"]
    if version["version_name"].startswith("baseline_"):
        version_baselines[family] = row
    elif family in version_baselines:
        base = version_baselines[family]
        for key in [
            "ann_return",
            "ann_vol",
            "sharpe",
            "max_drawdown",
            "calmar",
            "cvar_5",
            "avg_weekly_turnover",
            "avg_effective_n",
            "avg_bil_weight",
            "avg_spy_weight",
            "avg_cash_weight",
        ]:
            row[f"delta_{key}_vs_baseline"] = row[key] - base[key]
    portfolio_version_rows.append(row)

    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))
    overlay_cash = sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", pd.Series(0.0, index=weight_panel.index))
    sleeve_bil = (cash_weight - overlay_cash).clip(lower=0.0)
    beta_overlay_spy = beta_overlay_panel.get("beta_overlay_spy", pd.Series(0.0, index=weight_panel.index))
    beta_overlay_bil = beta_overlay_panel.get("beta_overlay_bil", pd.Series(0.0, index=weight_panel.index))
    diag_idx = diagnostics.copy()
    if not diag_idx.empty:
        diag_idx = diag_idx.set_index("Date").sort_index()
        diag_idx.index = pd.to_datetime(diag_idx.index).tz_localize(None)
    else:
        diag_idx = pd.DataFrame(index=weight_panel.index)
    latest_date = weight_panel.index[-1]
    current_offensive = offensive_weight.loc[latest_date]
    current_defensive = defensive_weight.loc[latest_date]
    current_cash = cash_weight.loc[latest_date]
    current_state = version_state_label(current_offensive, current_defensive, current_cash)

    allocation_driver_rows.append(
        {
            "version_name": version["version_name"],
            "method_name": version["method_name"],
            "current_date": str(latest_date.date()),
            "current_risk_state": ns5["regime_states"].loc[latest_date, "risk_state"] if latest_date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
            "current_market_state": market_state_history.loc[latest_date, "market_state"] if latest_date in market_state_history.index else None,
            "current_market_state_reason": market_state_history.loc[latest_date, "market_state_reason"] if latest_date in market_state_history.index else None,
            "current_state_label": current_state,
            "current_offensive_weight": current_offensive,
            "current_defensive_weight": current_defensive,
            "current_cash_proxy_weight": current_cash,
            "current_bil_weight": cash_weight.loc[latest_date],
            "current_spy_weight": weight_panel.loc[latest_date].get("SPY", np.nan),
            "avg_offensive_weight": offensive_weight.mean(),
            "avg_defensive_weight": defensive_weight.mean(),
            "avg_cash_proxy_weight": cash_weight.mean(),
            "avg_bil_weight": cash_weight.mean(),
            "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
            "avg_overlay_cash_weight": overlay_cash.mean(),
            "avg_sleeve_bil_weight": sleeve_bil.mean(),
            "avg_beta_overlay_spy_weight": beta_overlay_spy.mean(),
            "current_overlay_cash_weight": overlay_cash.loc[latest_date],
            "current_sleeve_bil_weight": sleeve_bil.loc[latest_date],
            "current_beta_overlay_spy_weight": beta_overlay_spy.loc[latest_date],
            "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_dynamic_speed": diagnostics["dynamic_speed"].mean() if not diagnostics.empty else np.nan,
            "avg_layer3_expression_shift": diagnostics["layer3_expression_shift"].mean() if not diagnostics.empty and "layer3_expression_shift" in diagnostics.columns else 0.0,
            "layer3_expression_trigger_rate": diagnostics["layer3_expression_triggered"].mean() if not diagnostics.empty and "layer3_expression_triggered" in diagnostics.columns else 0.0,
            "calm_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("calm").mean(),
            "neutral_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("neutral").mean(),
            "stressed_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("stressed").mean(),
            "recovery_market_state_frequency": market_state_history["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"]).mean(),
            "calm_market_state_frequency": market_state_history["market_state"].eq("calm_trend").mean(),
        }
    )

    for date in weight_panel.index:
        diag_row = diag_idx.loc[date] if date in diag_idx.index else pd.Series(dtype=float)
        regime_multiplier = float(diag_row.get("regime_multiplier", np.nan)) if len(diag_row) else np.nan
        target_vol_multiplier = float(diag_row.get("target_vol_multiplier", np.nan)) if len(diag_row) else np.nan
        gross_multiplier = float(diag_row.get("gross_multiplier", np.nan)) if len(diag_row) else np.nan
        self_gated_multiplier = float(diag_row.get("final_self_gated_multiplier", gross_multiplier)) if len(diag_row) else np.nan
        non_self_gated_multiplier = float(diag_row.get("final_non_self_gated_multiplier", gross_multiplier)) if len(diag_row) else np.nan
        if pd.isna(regime_multiplier):
            binding_source = "none"
        elif abs(regime_multiplier - target_vol_multiplier) <= 1e-6 and regime_multiplier < 0.999:
            binding_source = "both"
        elif regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999:
            binding_source = "regime"
        elif target_vol_multiplier < regime_multiplier and target_vol_multiplier < 0.999:
            binding_source = "target_vol"
        else:
            binding_source = "none"
        version_diagnostics_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
                "regime_multiplier": regime_multiplier,
                "target_vol_multiplier": target_vol_multiplier,
                "gross_multiplier": gross_multiplier,
                "predicted_ann_vol": float(diag_row.get("predicted_ann_vol", np.nan)) if len(diag_row) else np.nan,
                "dynamic_speed": float(diag_row.get("dynamic_speed", np.nan)) if len(diag_row) else np.nan,
                "regime_binding": float(diag_row.get("regime_binding", 0.0)) if len(diag_row) else 0.0,
                "target_vol_binding": float(diag_row.get("target_vol_binding", 0.0)) if len(diag_row) else 0.0,
                "both_binding": float(diag_row.get("both_binding", 0.0)) if len(diag_row) else 0.0,
                "binding_source": binding_source,
                "self_gated_relief": float(diag_row.get("self_gated_relief", 0.0)) if len(diag_row) else 0.0,
                "final_self_gated_multiplier": self_gated_multiplier,
                "final_non_self_gated_multiplier": non_self_gated_multiplier,
                "overlay_penalty_mode": diag_row.get("overlay_penalty_mode", "none") if len(diag_row) else "none",
                "speed_mode": diag_row.get("speed_mode", "default") if len(diag_row) else "default",
            }
        )

        sleeve_row = sleeve_alloc.loc[date] if date in sleeve_alloc.index else pd.Series(dtype=float)
        sleeve_internal_bil_weight = 0.0
        self_gated_internal_bil_weight = 0.0
        self_gated_overlay_cut_total = 0.0
        self_gated_overlay_cut_risky = 0.0
        non_self_gated_overlay_cut_total = 0.0
        non_self_gated_overlay_cut_risky = 0.0
        for sleeve_name in [name for name in sleeve_row.index if not str(name).startswith("cash::")]:
            post_weight = float(sleeve_row.get(sleeve_name, 0.0) or 0.0)
            sleeve_positions_row = (
                version_sleeve_positions[sleeve_name].loc[date]
                if sleeve_name in version_sleeve_positions and date in version_sleeve_positions[sleeve_name].index
                else pd.Series(dtype=float)
            )
            internal_bil = float(sleeve_positions_row.get(ns5["cash_proxy"], 0.0) or 0.0)
            multiplier_used = self_gated_multiplier if sleeve_name in SELF_GATED_SLEEVES else non_self_gated_multiplier
            pre_overlay_weight = post_weight / multiplier_used if pd.notna(multiplier_used) and multiplier_used > 1e-9 else post_weight
            overlay_cut_total = max(0.0, pre_overlay_weight - post_weight)
            overlay_cut_risky = overlay_cut_total * max(0.0, 1.0 - internal_bil)
            sleeve_internal_bil_contrib = post_weight * internal_bil
            sleeve_internal_bil_weight += sleeve_internal_bil_contrib
            if sleeve_name in SELF_GATED_SLEEVES:
                self_gated_internal_bil_weight += sleeve_internal_bil_contrib
                self_gated_overlay_cut_total += overlay_cut_total
                self_gated_overlay_cut_risky += overlay_cut_risky
            else:
                non_self_gated_overlay_cut_total += overlay_cut_total
                non_self_gated_overlay_cut_risky += overlay_cut_risky
        stacked_defense_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
                "strong_neutral": float(
                    date in market_state_history.index
                    and market_state_history.loc[date, "market_state"] == "neutral_mixed"
                    and float(market_state_history.loc[date, "market_trend_positive"]) > 0.0
                    and float(market_state_history.loc[date, "breadth_sma_43"]) >= 0.55
                    and float(market_state_history.loc[date, "breadth_26w_mom"]) >= 0.50
                ),
                "bil_weight": cash_weight.loc[date],
                "overlay_cash_weight": overlay_cash.loc[date],
                "sleeve_bil_weight": sleeve_bil.loc[date],
                "sleeve_internal_bil_weight": sleeve_internal_bil_weight,
                "self_gated_internal_bil_weight": self_gated_internal_bil_weight,
                "self_gated_overlay_cut_total": self_gated_overlay_cut_total,
                "self_gated_overlay_cut_risky": self_gated_overlay_cut_risky,
                "non_self_gated_overlay_cut_total": non_self_gated_overlay_cut_total,
                "non_self_gated_overlay_cut_risky": non_self_gated_overlay_cut_risky,
                "regime_multiplier": regime_multiplier,
                "target_vol_multiplier": target_vol_multiplier,
                "gross_multiplier": gross_multiplier,
                "binding_source": binding_source,
            }
        )

        allocation_driver_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "offensive_weight": offensive_weight.loc[date],
                "defensive_weight": defensive_weight.loc[date],
                "cash_proxy_weight": cash_weight.loc[date],
                "bil_weight": cash_weight.loc[date],
                "spy_weight": weight_panel.loc[date].get("SPY", np.nan),
                "overlay_cash_weight": overlay_cash.loc[date],
                "sleeve_bil_weight": sleeve_bil.loc[date],
                "beta_overlay_spy_weight": beta_overlay_spy.loc[date],
                "beta_overlay_bil_weight": beta_overlay_bil.loc[date],
                "risk_state": ns5["regime_states"].loc[date, "risk_state"] if date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
                "market_state": market_state_history.loc[date, "market_state"] if date in market_state_history.index else None,
            }
        )

    current_sleeve_alloc = sleeve_alloc.loc[latest_date] if latest_date in sleeve_alloc.index else pd.Series(dtype=float)
    for asset in [ns5["cash_proxy"], "SPY"]:
        overlay_value = current_sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", 0.0) if asset == ns5["cash_proxy"] else 0.0
        beta_overlay_value = beta_overlay_bil.loc[latest_date] if asset == ns5["cash_proxy"] else beta_overlay_spy.loc[latest_date]
        allocation_driver_breakdown_rows.append(
            {
                "version_name": version["version_name"],
                "horizon": "current",
                "asset": asset,
                "driver": "overlay_cash",
                "contribution": overlay_value,
            }
        )
        if abs(beta_overlay_value) > 1e-9:
            allocation_driver_breakdown_rows.append(
                {
                    "version_name": version["version_name"],
                    "horizon": "current",
                    "asset": asset,
                    "driver": "beta_overlay",
                    "contribution": beta_overlay_value,
                }
            )
        for sleeve_name in [name for name in current_sleeve_alloc.index if not str(name).startswith("cash::")]:
            sleeve_weight = current_sleeve_alloc.get(sleeve_name, 0.0)
            sleeve_position = version_sleeve_positions[sleeve_name].loc[latest_date].get(asset, 0.0) if sleeve_name in version_sleeve_positions and latest_date in version_sleeve_positions[sleeve_name].index else 0.0
            allocation_driver_breakdown_rows.append(
                {
                    "version_name": version["version_name"],
                    "horizon": "current",
                    "asset": asset,
                    "driver": sleeve_name,
                    "contribution": sleeve_weight * sleeve_position,
                }
            )

    state_conditioned_rows = sleeve_alloc.join(market_state_history[["market_state"]], how="left")
    for state_name, group in state_conditioned_rows.groupby("market_state"):
        if state_name is None or str(state_name) == "nan":
            continue
        sleeve_means = group.drop(columns=["market_state"], errors="ignore").mean()
        for sleeve_name, value in sleeve_means.items():
            state_conditioned_allocation_rows.append(
                {
                    "version_name": version["version_name"],
                    "method_name": version["method_name"],
                    "market_state": state_name,
                    "sleeve_name": sleeve_name,
                    "avg_weight": value,
                }
            )

    version_results[version["version_name"]] = {
        "weights": weight_panel,
        "sleeve_alloc": sleeve_alloc,
        "path": path,
        "diagnostics": diagnostics,
        "beta_overlay": beta_overlay_panel,
    }


candidate_strategy_returns = {
    "dual_momentum_topn": pd.read_csv(LAYER2A_DIR / "strategy_returns_dual_momentum_topn.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "cta_trend_long_only": pd.read_csv(LAYER2A_DIR / "strategy_returns_cta_trend_long_only.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "composite_regime_conditioned": pd.read_csv(LAYER2A_DIR / "strategy_returns_composite_regime_conditioned.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    "taa_10m_sma": pd.read_csv(LAYER2A_DIR / "strategy_returns_taa_10m_sma.csv", parse_dates=["Date"]).set_index("Date")["net_return"],
    selective_strategy_name: selective_path["net_return"],
    strength_weighted_strategy_name: strength_weighted_path["net_return"],
    concentrated_strategy_name: concentrated_path["net_return"],
}
for strategy_name, strategy_returns in candidate_strategy_returns.items():
    aligned = pd.DataFrame({"return": strategy_returns}).join(market_state_history[["market_state"]], how="left").dropna()
    for state_name, group in aligned.groupby("market_state"):
        sample = group["return"].dropna()
        if sample.empty:
            continue
        metrics = ns5["summary_metrics"](sample, trials=max(len(candidate_strategy_returns), 2))
        sleeve_performance_by_state_rows.append(
            {
                "strategy_name": strategy_name,
                "market_state": state_name,
                **metrics,
            }
        )


benchmark_index = benchmark_market_returns.index.intersection(next(iter(version_results.values()))["path"].index)
target_windows = manual_windows(benchmark_index) + top_rally_windows(benchmark_market_returns.reindex(benchmark_index).dropna())

for version_name, payload in version_results.items():
    version_returns = payload["path"]["net_return"]
    weight_panel = payload["weights"]
    diagnostics = payload["diagnostics"]
    capture_row = version_capture_summary(version_name, version_returns, benchmark_market_returns, weight_panel, diagnostics, market_state_history)
    upside_capture_rows.append(capture_row)
    for window in target_windows:
        summary_row = summarize_window(window, version_name, version_returns, benchmark_market_returns, weight_panel, diagnostics, market_state_history)
        targeted_window_rows.append(summary_row)
        window_capture_rows.append(
            {
                "version_name": version_name,
                "window_name": window["window_name"],
                "window_type": window["window_type"],
                "capture_ratio": summary_row["capture_ratio"],
                "portfolio_return": summary_row["portfolio_return"],
                "benchmark_return": summary_row["benchmark_return"],
            }
        )
        if window["window_type"] in {"recovery", "rising", "auto_rally"}:
            rally_window_rows.append(summary_row)
        if window["window_type"] == "recovery":
            rerisk_lag_rows.append(rerisking_lag_summary(window, version_name, weight_panel, diagnostics))


upside_capture_df = pd.DataFrame(upside_capture_rows)
rally_window_df = pd.DataFrame(rally_window_rows)
targeted_window_df = pd.DataFrame(targeted_window_rows)
window_capture_df = pd.DataFrame(window_capture_rows)
rerisk_lag_df = pd.DataFrame(rerisk_lag_rows)
version_diagnostics_timeseries_df = pd.DataFrame(version_diagnostics_timeseries_rows)
stacked_defense_df = pd.DataFrame(stacked_defense_timeseries_rows)
off_def_cash_rallies_df = rally_window_df[
    [
        "version_name",
        "window_name",
        "window_type",
        "avg_offensive_weight",
        "avg_defensive_weight",
        "avg_cash_weight",
        "avg_bil_weight",
        "avg_spy_weight",
        "avg_regime_multiplier",
        "avg_target_vol_multiplier",
        "avg_dynamic_speed",
    ]
].copy()


version_df = pd.DataFrame(portfolio_version_rows).merge(upside_capture_df, on="version_name", how="left")


def rank_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    numeric = pd.Series(series, dtype=float)
    if not higher_is_better:
        numeric = -numeric
    return numeric.rank(pct=True, method="average")


version_df["production_score"] = (
    0.22 * rank_score(version_df["sharpe"], True)
    + 0.16 * rank_score(version_df["calmar"], True)
    + 0.14 * rank_score(version_df["max_drawdown"].abs(), False)
    + 0.10 * rank_score(version_df["cvar_5"].abs(), False)
    + 0.12 * rank_score(version_df["upside_capture_positive_weeks"], True)
    + 0.10 * rank_score(version_df["recovery_week_capture"], True)
    + 0.08 * rank_score(version_df["avg_cash_weight"], False)
    + 0.08 * rank_score(version_df["avg_weekly_turnover"], False)
)

portfolio_version_rows = version_df.to_dict(orient="records")
upside_capture_df = upside_capture_df.merge(version_df[["version_name", "production_score"]], on="version_name", how="left")

if not version_diagnostics_timeseries_df.empty:
    version_diagnostics_state_summary_df = (
        version_diagnostics_timeseries_df.groupby(["version_name", "market_state"], dropna=False)[
            [
                "regime_multiplier",
                "target_vol_multiplier",
                "gross_multiplier",
                "dynamic_speed",
                "regime_binding",
                "target_vol_binding",
                "both_binding",
                "self_gated_relief",
                "final_self_gated_multiplier",
                "final_non_self_gated_multiplier",
            ]
        ]
        .mean()
        .reset_index()
    )
else:
    version_diagnostics_state_summary_df = pd.DataFrame()

if not stacked_defense_df.empty:
    stacked_defense_state_summary_df = (
        stacked_defense_df.groupby(["version_name", "market_state", "strong_neutral"], dropna=False)[
            [
                "bil_weight",
                "overlay_cash_weight",
                "sleeve_bil_weight",
                "sleeve_internal_bil_weight",
                "self_gated_internal_bil_weight",
                "self_gated_overlay_cut_total",
                "self_gated_overlay_cut_risky",
                "non_self_gated_overlay_cut_total",
                "non_self_gated_overlay_cut_risky",
                "regime_multiplier",
                "target_vol_multiplier",
                "gross_multiplier",
            ]
        ]
        .mean()
        .reset_index()
    )
else:
    stacked_defense_state_summary_df = pd.DataFrame()

version_diagnostics_timeseries_df.to_csv(LAYER3_DIR / "portfolio_version_diagnostics_timeseries.csv", index=False)
version_diagnostics_state_summary_df.to_csv(LAYER3_DIR / "portfolio_version_diagnostics_by_state.csv", index=False)
stacked_defense_df.to_csv(LAYER3_DIR / "stacked_defense_timeseries.csv", index=False)
stacked_defense_state_summary_df.to_csv(LAYER3_DIR / "stacked_defense_by_state.csv", index=False)
pd.DataFrame(allocation_driver_timeseries_rows).to_csv(LAYER3_DIR / "allocation_driver_timeseries.csv", index=False)
pd.DataFrame(allocation_driver_rows).to_csv(LAYER3_DIR / "allocation_driver_summary.csv", index=False)
pd.DataFrame(allocation_driver_breakdown_rows).to_csv(LAYER3_DIR / "allocation_driver_breakdown.csv", index=False)


if not FILTERED_VERSION_BUILD:
    upside_capture_df.to_csv(LAYER3_DIR / "upside_capture_analysis.csv", index=False)
    rally_window_df.to_csv(LAYER3_DIR / "rally_window_attribution.csv", index=False)
    off_def_cash_rallies_df.to_csv(LAYER3_DIR / "offensive_defensive_cash_during_rallies.csv", index=False)
    targeted_window_df.to_csv(LAYER3_DIR / "targeted_window_summary.csv", index=False)
    window_capture_df.to_csv(LAYER3_DIR / "upside_downside_capture_by_window.csv", index=False)
    rerisk_lag_df.to_csv(LAYER3_DIR / "rerisking_lag_by_window.csv", index=False)
    pd.DataFrame(sleeve_performance_by_state_rows).to_csv(LAYER2B_DIR / "sleeve_performance_by_state.csv", index=False)
    pd.DataFrame(state_conditioned_allocation_rows).to_csv(LAYER3_DIR / "state_conditioned_allocation_summary.csv", index=False)
    upside_capture_df.to_csv(LAYER3_DIR / "upside_capture_version_comparison.csv", index=False)

    pd.DataFrame(sleeve_incremental_rows).to_csv(LAYER3_DIR / "sleeve_incremental_contribution.csv", index=False)
    pd.DataFrame(sleeve_subset_rows).to_csv(LAYER3_DIR / "sleeve_subset_comparison.csv", index=False)
    pd.DataFrame(portfolio_version_rows).to_csv(LAYER3_DIR / "portfolio_version_comparison.csv", index=False)
    pd.concat(portfolio_version_regime_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_regime_split_summary.csv", index=False)
    pd.concat(portfolio_version_subperiod_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_subperiod_summary.csv", index=False)
    print("Saved improvement artifacts:")
    for name in [
        "data/02_layer1_signals/signal_incremental_contribution.csv",
        "data/02_layer1_signals/signal_subset_comparison.csv",
        f"data/03_layer2a_strategy_logic/strategy_positions_{selective_strategy_name}.csv",
        f"data/03_layer2a_strategy_logic/strategy_returns_{selective_strategy_name}.csv",
        f"data/03_layer2a_strategy_logic/strategy_positions_{strength_weighted_strategy_name}.csv",
        f"data/03_layer2a_strategy_logic/strategy_returns_{strength_weighted_strategy_name}.csv",
        f"data/03_layer2a_strategy_logic/strategy_positions_{concentrated_strategy_name}.csv",
        f"data/03_layer2a_strategy_logic/strategy_returns_{concentrated_strategy_name}.csv",
        "data/04_layer2b_risk_regime_engine/market_state_history.csv",
        "data/04_layer2b_risk_regime_engine/sleeve_performance_by_state.csv",
        "data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv",
        "data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv",
        "data/05_layer3_portfolio_construction/portfolio_version_comparison.csv",
        "data/05_layer3_portfolio_construction/allocation_driver_summary.csv",
        "data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv",
        "data/05_layer3_portfolio_construction/portfolio_version_diagnostics_by_state.csv",
        "data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv",
        "data/05_layer3_portfolio_construction/stacked_defense_by_state.csv",
        "data/05_layer3_portfolio_construction/upside_capture_analysis.csv",
        "data/05_layer3_portfolio_construction/rally_window_attribution.csv",
        "data/05_layer3_portfolio_construction/targeted_window_summary.csv",
    ]:
        print(" -", name)
else:
    print("Filtered improvement build wrote version-specific artifacts only; shared comparison tables were preserved.")
