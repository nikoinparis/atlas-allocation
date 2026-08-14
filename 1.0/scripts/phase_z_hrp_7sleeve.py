"""Phase Z — Production HRP / Dynamic-Risk-Budget Architecture on the 7-Sleeve Panel.

Phase X tried the production allocator FAMILY (inverse-vol + state risk multiplier
+ Phase 2B regime_confidence_boost) on the upgraded 7-sleeve panel. All four
candidates classified Drop / Research-only because the inverse-vol allocator
cannot use W1 efficiently inside production guardrails — it either over-uses
W1 (heavy: hurts returns) or under-uses W1 (light: loses defensive benefit).

Phase Y tried three CONDITIONAL W1 sizing rules on the same inverse-vol family
(state-capped, trigger-driven, cash-replacement). All classified Drop because
the inverse-vol family on a 7-sleeve panel cannot reproduce the production
pin's gate alignment regardless of how W1 is sized.

Phase Z is the architecture-equivalent test. It ports the actual production
allocator architecture — HRP sleeve weighting, dynamic_risk_budget tilt with
rank-based 26-week conviction, lighter_both_targeted_narrow_plus_confirmed
overlay, Phase 2B regime_confidence_boost — onto the upgraded 7-sleeve panel.

Candidates:
  Z1 — production architecture rerun on 7-sleeve panel
       HRP + dynamic_risk_budget + lighter_both_targeted_narrow_plus_confirmed
       overlay + regime_confidence_boost. The strongest direct comparison
       to the production pin: same architecture, upgraded sleeve panel.

  Z2 — shadow architecture rerun on 7-sleeve panel
       Same architecture as Z1 but with combo_abc meta layer (A regime boost
       + B transition gate + C tail suppression). Direct comparison to the
       shadow pin (improved_phase2b_combo_abc).

  Z3 — W1 integration variant inside HRP family
       Z1 architecture + W1-aware defensive overlay: W1 is added to
       DEFENSIVE_SLEEVE_CANDIDATES (gets +5% bump in stressed_panic) AND
       a 5% W1 floor is enforced in non-stressed states inside HRP output.
       Tests whether explicit W1 integration inside the HRP family converts
       W1's structural defense into measurable outperformance.

  Z4 — 5-sleeve vs 7-sleeve ablation under same architecture
       Z1 architecture rerun on the original production 5-sleeve subset
       (dual_momentum_topn, cta_trend_long_only, composite_selective_signals,
       composite_regime_conditioned, taa_10m_sma). Isolates the marginal
       contribution of switching from the original sleeves to the new
       7-sleeve panel under identical architecture.

Causal walk-forward safety:
  - All sleeve features 1-week-lagged.
  - Covariance from 156-week trailing returns, t-1 only.
  - State multipliers and ML predictions from existing walk-forward sources.
  - No retraining of any branch.

Outputs to data/05_layer3_portfolio_construction/:
  portfolio_version_{returns,weights,sleeve_weights}_{Z1,Z2,Z3,Z4}.csv
  phase_z_candidate_metrics_{full,dev,holdout}.csv
  phase_z_pairwise_validation.csv
  phase_z_rolling_origin_summary.csv
  phase_z_candidate_classification.csv
  phase_z_w1_diagnostics.csv
  phase_z_state_w1_usage.csv
  phase_z_validation_protocol.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

try:
    from sklearn.covariance import LedoitWolf
except Exception:
    LedoitWolf = None

sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase_d_validate as pdv
import phase_p_evaluate as ppe
import phase_p_meta_allocator as pp


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"


# --------------------------------------------------------------------------
# constants — match production architecture exactly
# --------------------------------------------------------------------------

EPS = 1e-9
WEEKS_PER_YEAR = 52
TRAIN_WINDOW_WEEKS = 156
MIN_TRAIN_OBS = 78
MAX_SLEEVE_WEIGHT = 0.45
TARGET_VOL_ANN = 0.12
TARGET_VOL_FLOOR = 0.35
TARGET_VOL_CEIL = 1.00
SLEEVE_REALLOCATION_SPEED = 0.40
RERISK_SPEED = 1.00
TURNOVER_HALFSPREAD = 0.0005 * 0.5  # 5bp half-spread
CASH_PROXY = "BIL"

# Hard state risk multiplier ceiling (used to derive cash share AFTER overlay).
# In production this is the regime engine's overlay_multiplier from
# defensive_overlay_states.csv (which the variant `good_state_fragile_expression`
# clips with floors). We replicate the floors below in
# build_variant_overlay_multiplier().

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
PHASET_T1_REFERENCE = "improved_phaset_soft_regime_posterior_allocator"
PHASEU_U1A_REFERENCE = "improved_phaseu_prod90_r2_10_holdings_blend"
PHASEU_U3_REFERENCE = "improved_phaseu_conditional_prod_r2_holdings_blend"
PHASEV_V1_REFERENCE = "improved_phasev_prod90_phasen_10_holdings_blend"

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
    PHASET_T1_REFERENCE,
    PHASEU_U1A_REFERENCE,
    PHASEU_U3_REFERENCE,
    PHASEV_V1_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

# Panels.
PANEL_7 = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
    "composite_structural_defense_sleeve",  # W1
]
PANEL_5_PRODUCTION = [
    # The actual original production 5-sleeve subset.
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "composite_regime_conditioned",
    "taa_10m_sma",
]
W1_NAME = "composite_structural_defense_sleeve"
W1_FLOOR_NONSTRESSED = 0.05  # Z3 only

# Production sleeve role taxonomy. Used by dynamic_risk_budget
# fragile/stressed bumps. Specialists pass through unmodified by these
# bumps (they still receive conviction tilt) — faithful to how the
# production architecture treats sleeves it wasn't originally designed
# around.
OFFENSIVE_SLEEVE_CANDIDATES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "composite_selective_signals",
    "composite_selective_trend_ensemble",
    "composite_selective_concentrated",
    "composite_equal_weight",
    "composite_trend_quality_module",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "sector_rotation_with_sma_filter",
]
DEFENSIVE_SLEEVE_CANDIDATES = ["composite_regime_conditioned", "taa_10m_sma"]
DEFENSIVE_SLEEVE_CANDIDATES_Z3 = DEFENSIVE_SLEEVE_CANDIDATES + [W1_NAME]
SELF_GATED_SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "taa_10m_sma",
]


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------

def load_sleeve_returns(sleeve: str) -> pd.Series:
    df = pd.read_csv(LAYER2A_DIR / f"strategy_returns_{sleeve}.csv", index_col=0, parse_dates=True)
    s = df["net_return"].astype(float)
    s.index.name = None
    return s.sort_index()


def load_sleeve_positions(sleeve: str) -> pd.DataFrame:
    df = pd.read_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index().fillna(0.0)


def load_market_state() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_overlay_states() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "defensive_overlay_states.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_phase2b_predictions() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "phase2b_meta_predictions.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


def load_weekly_returns() -> pd.DataFrame:
    df = pd.read_csv(LAYER1_DIR / "weekly_returns.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


# --------------------------------------------------------------------------
# helpers — covariance, normalization, HRP
# --------------------------------------------------------------------------

def normalize_long_only(weights: pd.Series, max_weight: float = MAX_SLEEVE_WEIGHT) -> pd.Series:
    weights = pd.Series(weights, dtype=float).clip(lower=0.0).fillna(0.0)
    if weights.sum() <= 0:
        if len(weights):
            weights[:] = 1.0 / len(weights)
        return weights
    weights = weights / weights.sum()
    for _ in range(25):
        over = weights > max_weight
        if not over.any():
            break
        excess = (weights[over] - max_weight).sum()
        weights.loc[over] = max_weight
        under = weights < max_weight - 1e-12
        if under.any() and excess > 0:
            weights.loc[under] += excess * weights.loc[under] / weights.loc[under].sum()
        elif excess > 0:
            weights += excess / len(weights)
        weights = weights.clip(lower=0.0)
        weights = weights / weights.sum()
    return weights / weights.sum()


def sanitize_covariance(cov: pd.DataFrame, var_floor: float = 1e-12) -> pd.DataFrame:
    cov = pd.DataFrame(cov).copy()
    if cov.empty:
        return cov
    cov = cov.replace([np.inf, -np.inf], np.nan)
    common = cov.index.intersection(cov.columns)
    cov = cov.loc[common, common]
    if cov.empty:
        return cov
    cov = (cov + cov.T) / 2.0
    diag = pd.Series(np.diag(cov.values), index=cov.index).replace([np.inf, -np.inf], np.nan)
    keep = diag[diag > var_floor].index
    cov = cov.loc[keep, keep]
    if cov.empty:
        return cov
    finite = pd.Series(np.isfinite(cov.to_numpy()).all(axis=1), index=cov.index)
    cov = cov.loc[finite[finite].index, finite[finite].index]
    if cov.empty:
        return cov
    di = np.diag_indices_from(cov.values)
    cov.values[di] = np.maximum(np.diag(cov.values), var_floor)
    return cov


def estimate_covariance(train: pd.DataFrame) -> pd.DataFrame:
    if train.empty:
        return pd.DataFrame()
    if train.shape[1] < 2 or train.shape[0] < 10:
        return sanitize_covariance(train.cov())
    if LedoitWolf is not None:
        try:
            lw = LedoitWolf().fit(train.values)
            return sanitize_covariance(pd.DataFrame(lw.covariance_, index=train.columns, columns=train.columns))
        except Exception:
            pass
    return sanitize_covariance(train.cov())


def cov_to_corr(cov: pd.DataFrame) -> pd.DataFrame:
    cov = sanitize_covariance(cov)
    if cov.empty:
        return pd.DataFrame()
    vol = np.sqrt(np.diag(cov.values))
    denom = np.outer(vol, vol)
    corr = cov.values / np.where(denom <= 0, np.nan, denom)
    corr = pd.DataFrame(corr, index=cov.index, columns=cov.columns)
    corr = corr.replace([np.inf, -np.inf], np.nan).clip(-1.0, 1.0)
    np.fill_diagonal(corr.values, 1.0)
    return corr


def inverse_vol_from_cov(cov: pd.DataFrame) -> pd.Series:
    vol = pd.Series(np.sqrt(np.diag(cov.values)), index=cov.index)
    inv = 1.0 / vol.replace(0.0, np.nan).clip(lower=1e-12)
    inv = inv.fillna(inv.median()).fillna(1.0)
    return normalize_long_only(inv, max_weight=1.0)


def cluster_variance(cov: pd.DataFrame, members: list[str]) -> float:
    sub = cov.loc[members, members]
    w = inverse_vol_from_cov(sub)
    return float(w.values @ sub.values @ w.values)


def hierarchical_fallback(cov: pd.DataFrame) -> pd.Series:
    clean = sanitize_covariance(cov)
    if clean.empty:
        return pd.Series(dtype=float)
    if clean.shape[0] == 1:
        return pd.Series([1.0], index=clean.index)
    return inverse_vol_from_cov(clean)


def optimize_hrp(cov: pd.DataFrame) -> pd.Series:
    """Lopez de Prado HRP — single-linkage on correlation distance."""
    clean = sanitize_covariance(cov)
    if clean.shape[0] < 2:
        return hierarchical_fallback(clean if not clean.empty else cov)
    corr = cov_to_corr(clean)
    if corr.empty or not np.isfinite(corr.values).all():
        return hierarchical_fallback(clean)
    dist = np.sqrt(np.clip((1.0 - corr.values) / 2.0, 0.0, 1.0))
    np.fill_diagonal(dist, 0.0)
    if not np.isfinite(dist).all():
        return hierarchical_fallback(clean)
    condensed = squareform(dist, checks=False)
    if condensed.size == 0 or not np.isfinite(condensed).all():
        return hierarchical_fallback(clean)
    try:
        link = linkage(condensed, method="single")
        ordered = corr.index[leaves_list(link)].tolist()
        weights = pd.Series(1.0, index=ordered)
        clusters = [ordered]
        while clusters:
            cluster = clusters.pop(0)
            if len(cluster) <= 1:
                continue
            split = len(cluster) // 2
            left = cluster[:split]
            right = cluster[split:]
            lvar = cluster_variance(clean, left)
            rvar = cluster_variance(clean, right)
            alpha = 1.0 - lvar / max(lvar + rvar, 1e-12)
            weights[left] *= alpha
            weights[right] *= 1.0 - alpha
            clusters.extend([left, right])
        return normalize_long_only(weights.reindex(clean.index).fillna(0.0), max_weight=MAX_SLEEVE_WEIGHT)
    except Exception:
        return hierarchical_fallback(clean)


# --------------------------------------------------------------------------
# helpers — conviction, state, overlay multiplier, ML offset
# --------------------------------------------------------------------------

def rolling_sleeve_conviction(
    sleeve_panel: pd.DataFrame, as_of: pd.Timestamp, sleeves: list[str], lookback_weeks: int = 26
) -> pd.Series:
    """Rank-based rolling Sharpe conviction in [-1, +1] (production logic)."""
    if not sleeves:
        return pd.Series(dtype=float)
    cols = [s for s in sleeves if s in sleeve_panel.columns]
    window = sleeve_panel.loc[:as_of, cols]
    # walk-forward: drop the as-of row itself (use t-1 features only)
    if len(window) > 1:
        window = window.iloc[:-1]
    window = window.tail(lookback_weeks)
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


def is_strong_neutral(market_state_row: pd.Series) -> bool:
    if market_state_row is None or not isinstance(market_state_row, pd.Series) or market_state_row.empty:
        return False
    state = str(market_state_row.get("market_state") or "")
    mtp = float(market_state_row.get("market_trend_positive") or 0.0)
    bsma = float(market_state_row.get("breadth_sma_43") or 0.0)
    bmom = float(market_state_row.get("breadth_26w_mom") or 0.0)
    return state == "neutral_mixed" and mtp > 0.0 and bsma >= 0.55 and bmom >= 0.50


def overlay_multiplier_at(
    overlay_states: pd.DataFrame, market_state_row: pd.Series, date: pd.Timestamp
) -> float:
    """Replicate good_state_fragile_expression overlay variant: applies the
    production floors to the regime engine's overlay_multiplier."""
    if date not in overlay_states.index:
        return 1.0
    base = float(overlay_states.loc[date, "overlay_multiplier"])
    risk_state = str(overlay_states.loc[date].get("risk_state") or "")
    state = str(market_state_row.get("market_state") or "") if isinstance(market_state_row, pd.Series) else ""
    strong_neutral = is_strong_neutral(market_state_row) if isinstance(market_state_row, pd.Series) else False
    multiplier = base
    if risk_state == "neutral":
        multiplier = max(multiplier, 0.80)
    elif risk_state == "stressed":
        multiplier = max(multiplier, 0.40)
    if state == "recovery_fragile":
        multiplier = max(multiplier, 0.96)
    elif state == "recovery_confirmed":
        multiplier = max(multiplier, 0.92)
    elif state == "calm_trend":
        multiplier = max(multiplier, 1.00)
    elif strong_neutral:
        multiplier = max(multiplier, 0.94)
    return float(multiplier)


def regime_confidence_offset(state: str, p_regime: float, p_trans: float, p_tail: float, mode: str) -> float:
    """Phase 2B meta-layer offset replicated from build_improvement_artifacts."""
    if mode == "none":
        return 0.0
    offset = 0.0
    apply_a = mode in {"regime_confidence_boost", "combo_abc"}
    apply_b = mode in {"combo_abc"}
    apply_c = mode in {"combo_abc"}
    if apply_a and state != "stressed_panic" and not np.isnan(p_regime):
        if p_regime >= 0.55:
            raw = 0.10 * (p_regime - 0.55) / max(EPS, 1.0 - 0.55)
            offset += float(min(0.045, max(0.0, raw)))
    if apply_b and state in {"neutral_mixed", "recovery_fragile"} and not np.isnan(p_trans):
        if p_trans > 0.60:
            offset += 0.04
        elif p_trans < 0.40:
            offset -= 0.03
    if apply_c and state != "stressed_panic" and not np.isnan(p_tail):
        if p_tail > 0.55:
            raw = -0.10 * (p_tail - 0.55) / max(EPS, 1.0 - 0.55)
            offset += float(max(-0.10, min(0.0, raw)))
    return offset


# --------------------------------------------------------------------------
# tilt — dynamic_risk_budget (production)
# --------------------------------------------------------------------------

def apply_dynamic_risk_budget_tilt(
    raw_weights: pd.Series,
    market_state: str,
    market_state_row: pd.Series,
    conviction: pd.Series,
    *,
    defensive_sleeves: list[str],
) -> pd.Series:
    tilted = pd.Series(raw_weights, dtype=float).copy()
    offensive = [n for n in OFFENSIVE_SLEEVE_CANDIDATES if n in tilted.index]
    defensive = [n for n in defensive_sleeves if n in tilted.index]
    strong_neutral = is_strong_neutral(market_state_row)
    favorable = (
        market_state in {"recovery_fragile", "recovery_confirmed", "calm_trend"} or strong_neutral
    )
    if favorable and conviction is not None and not conviction.empty:
        for name in tilted.index:
            c = float(conviction.get(name, 0.0) or 0.0)
            mult = float(np.clip(1.0 + 0.15 * c, 0.85, 1.15))
            tilted.loc[name] *= mult
    if market_state == "recovery_fragile":
        for name in offensive:
            tilted.loc[name] *= 1.04
        for name in defensive:
            tilted.loc[name] *= 0.96
    elif market_state == "stressed_panic":
        for name in offensive:
            tilted.loc[name] *= 0.92
        if "composite_regime_conditioned" in tilted.index:
            tilted.loc["composite_regime_conditioned"] *= 1.08
        if "taa_10m_sma" in tilted.index:
            tilted.loc["taa_10m_sma"] *= 1.05
        if W1_NAME in defensive and W1_NAME in tilted.index:
            tilted.loc[W1_NAME] *= 1.05
    return normalize_long_only(tilted, max_weight=MAX_SLEEVE_WEIGHT)


# --------------------------------------------------------------------------
# overlay — lighter_both_targeted_narrow_plus_confirmed (production)
# --------------------------------------------------------------------------

def apply_production_overlay(
    raw_weights: pd.Series,
    cov: pd.DataFrame,
    *,
    raw_overlay_multiplier: float,
    prev_weights: pd.Series | None,
    market_state: str,
    market_state_row: pd.Series,
    phase2b_offset: float,
    sleeve_reallocation_speed: float = SLEEVE_REALLOCATION_SPEED,
    rerisk_speed: float = RERISK_SPEED,
    target_vol_ceil: float = TARGET_VOL_CEIL,
) -> tuple[pd.Series, float, dict]:
    raw_weights = normalize_long_only(raw_weights, max_weight=MAX_SLEEVE_WEIGHT)
    regime_multiplier = float(np.clip(raw_overlay_multiplier + phase2b_offset, 0.0, 1.0))
    strong_neutral = is_strong_neutral(market_state_row)
    dynamic_speed = sleeve_reallocation_speed
    if market_state in {"recovery_rebound", "recovery_confirmed", "calm_trend"}:
        dynamic_speed = rerisk_speed
    elif market_state == "recovery_fragile":
        dynamic_speed = sleeve_reallocation_speed + 0.5 * (rerisk_speed - sleeve_reallocation_speed)
    if prev_weights is not None and not prev_weights.empty:
        prev_weights = normalize_long_only(prev_weights.reindex(raw_weights.index).fillna(0.0), max_weight=MAX_SLEEVE_WEIGHT)
        blended = (1.0 - dynamic_speed) * prev_weights + dynamic_speed * raw_weights
    else:
        blended = raw_weights.copy()
    blended = normalize_long_only(blended, max_weight=MAX_SLEEVE_WEIGHT)
    predicted_ann_vol = np.sqrt(max(float(blended.values @ cov.values @ blended.values), 0.0)) * np.sqrt(WEEKS_PER_YEAR)
    target_vol_multiplier = (
        1.0
        if predicted_ann_vol <= 0 or pd.isna(predicted_ann_vol)
        else float(np.clip(TARGET_VOL_ANN / predicted_ann_vol, TARGET_VOL_FLOOR, target_vol_ceil))
    )
    regime_binding = float(regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999)
    per_sleeve = pd.Series(float(min(1.0, regime_multiplier, target_vol_multiplier)), index=blended.index, dtype=float)
    self_gated_relief = 0.0
    non_self_gated_relief = 0.0
    apply_self_gated = False
    apply_non_self_gated = False
    relief_cap = 0.04
    relief_scale = 0.35
    ns_relief_cap = 0.025
    ns_relief_scale = 0.20
    in_targeted_state = strong_neutral or market_state in {"recovery_fragile", "recovery_confirmed"}
    if regime_binding > 0.0 and market_state != "stressed_panic" and in_targeted_state:
        # lighter_both_targeted_narrow_plus_confirmed
        apply_self_gated = True
        if strong_neutral or market_state == "recovery_fragile":
            apply_non_self_gated = True
            ns_relief_cap = 0.025
            ns_relief_scale = 0.20
        elif market_state == "recovery_confirmed":
            apply_non_self_gated = True
            ns_relief_cap = 0.015
            ns_relief_scale = 0.15
    if apply_self_gated:
        sg = [n for n in blended.index if n in SELF_GATED_SLEEVES]
        nsg = [n for n in blended.index if n not in SELF_GATED_SLEEVES]
        per_sleeve.loc[:] = regime_multiplier
        headroom = max(0.0, target_vol_multiplier - regime_multiplier)
        if sg:
            relief = min(relief_cap, relief_scale * max(0.0, 1.0 - regime_multiplier), 0.75 * headroom if headroom > 0 else relief_cap)
            self_gated_relief = max(0.0, relief)
            per_sleeve.loc[sg] = min(1.0, regime_multiplier + self_gated_relief)
        if apply_non_self_gated and nsg:
            ns_relief = min(ns_relief_cap, ns_relief_scale * max(0.0, 1.0 - regime_multiplier), 0.75 * headroom if headroom > 0 else ns_relief_cap)
            non_self_gated_relief = max(0.0, ns_relief)
            per_sleeve.loc[nsg] = min(1.0, regime_multiplier + non_self_gated_relief)
        if target_vol_multiplier < 1.0:
            total_risky = float((blended * per_sleeve).sum())
            if total_risky > target_vol_multiplier and total_risky > 1e-12:
                per_sleeve *= target_vol_multiplier / total_risky
    risky = blended * per_sleeve
    cash_weight = max(0.0, 1.0 - float(risky.sum()))
    diag = {
        "regime_multiplier": regime_multiplier,
        "raw_overlay_multiplier": raw_overlay_multiplier,
        "phase2b_offset": phase2b_offset,
        "target_vol_multiplier": target_vol_multiplier,
        "regime_binding": regime_binding,
        "self_gated_relief": self_gated_relief,
        "non_self_gated_relief": non_self_gated_relief,
        "predicted_ann_vol": predicted_ann_vol,
        "cash_weight": cash_weight,
    }
    return risky, cash_weight, diag


# --------------------------------------------------------------------------
# build candidate
# --------------------------------------------------------------------------

def last_friday_mask(index: pd.DatetimeIndex) -> pd.Series:
    month_key = pd.Series(pd.Index(index).to_period("M").astype(str), index=index)
    mask = month_key.ne(month_key.shift(-1))
    if len(mask) > 0:
        mask.iloc[0] = True
    return mask


def build_candidate(
    panel: list[str],
    *,
    meta_mode: str,
    sleeve_returns_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    market_state_history: pd.DataFrame,
    overlay_states: pd.DataFrame,
    phase2b_pred: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    w1_floor_nonstressed: bool = False,
    w1_in_defensive: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Compute weekly sleeve weights + ETF weights for one candidate.

    Returns:
      sleeve_weights_df: rows=dates, cols=panel + ['cash::BIL']
      etf_weights_df:    rows=dates, cols=ETF universe (incl 'BIL'), sums to 1
      net_returns:       weekly net return series
    """
    common_idx = sleeve_returns_panel.index.intersection(market_state_history.index).sort_values()
    rebalance = last_friday_mask(common_idx)

    etf_universe = sorted({c for sleeve in panel for c in sleeve_positions[sleeve].columns})
    if CASH_PROXY not in etf_universe:
        etf_universe = sorted(set(etf_universe) | {CASH_PROXY})
    sleeve_w_rows: list[pd.Series] = []
    etf_w_rows: list[pd.Series] = []

    current_risky = pd.Series(0.0, index=panel, dtype=float)
    current_cash = 1.0
    prev_active_alloc = pd.Series(dtype=float)
    defensive_set = DEFENSIVE_SLEEVE_CANDIDATES_Z3 if w1_in_defensive else DEFENSIVE_SLEEVE_CANDIDATES

    for date in common_idx:
        market_state_row = market_state_history.loc[date] if date in market_state_history.index else pd.Series(dtype=float)
        market_state = str(market_state_row.get("market_state") or "") if isinstance(market_state_row, pd.Series) else ""

        if rebalance.loc[date]:
            train_slice = sleeve_returns_panel.loc[:date, panel]
            # Walk-forward: t-1 only
            if len(train_slice) > 1:
                train_slice = train_slice.iloc[:-1]
            train_slice = train_slice.tail(TRAIN_WINDOW_WEEKS)
            counts = train_slice.count()
            active = counts[counts >= MIN_TRAIN_OBS].index.tolist()
            if len(active) >= 2:
                train = train_slice[active].dropna(how="any")
                if len(train) >= max(26, MIN_TRAIN_OBS // 2):
                    cov = estimate_covariance(train)
                    if not cov.empty:
                        active = list(cov.index)
                        # HRP raw weights
                        raw = optimize_hrp(cov)
                        # Conviction
                        conviction = rolling_sleeve_conviction(
                            sleeve_returns_panel, date, list(active), lookback_weeks=26
                        )
                        # Dynamic risk budget tilt
                        raw = apply_dynamic_risk_budget_tilt(
                            raw,
                            market_state,
                            market_state_row,
                            conviction,
                            defensive_sleeves=defensive_set,
                        )
                        # Phase 2B offset
                        if meta_mode != "none" and date in phase2b_pred.index:
                            row = phase2b_pred.loc[date]
                            p_regime = float(row.get("p_regime_confidence", np.nan))
                            p_trans = float(row.get("p_transition_quality", np.nan))
                            p_tail = float(row.get("p_tail_risk", np.nan))
                            offset = regime_confidence_offset(market_state, p_regime, p_trans, p_tail, meta_mode)
                        else:
                            offset = 0.0
                        # Overlay multiplier
                        raw_overlay = overlay_multiplier_at(overlay_states, market_state_row, date)
                        # Production overlay
                        risky, cash_w, _ = apply_production_overlay(
                            raw,
                            cov,
                            raw_overlay_multiplier=raw_overlay,
                            prev_weights=prev_active_alloc.reindex(active).fillna(0.0) if not prev_active_alloc.empty else None,
                            market_state=market_state,
                            market_state_row=market_state_row,
                            phase2b_offset=offset,
                        )
                        # Z3-only: enforce W1 floor in non-stressed states
                        if w1_floor_nonstressed and W1_NAME in active and market_state != "stressed_panic":
                            current_w1 = float(risky.get(W1_NAME, 0.0))
                            target_w1 = max(current_w1, W1_FLOOR_NONSTRESSED)
                            # Only enforce if there's room in risky budget
                            risky_total = float(risky.sum())
                            if target_w1 > current_w1 and risky_total > target_w1:
                                deficit = target_w1 - current_w1
                                others = [n for n in risky.index if n != W1_NAME and risky.get(n, 0.0) > 1e-9]
                                if others:
                                    other_total = float(sum(risky[n] for n in others))
                                    for n in others:
                                        risky.loc[n] -= deficit * (risky[n] / other_total)
                                    risky.loc[W1_NAME] = target_w1
                        # Update state
                        current_risky = pd.Series(0.0, index=panel, dtype=float)
                        current_risky.loc[risky.index] = risky.values
                        current_cash = max(0.0, 1.0 - float(current_risky.sum()))
                        prev_active_alloc = pd.Series(0.0, index=active, dtype=float)
                        prev_active_alloc.loc[risky.index] = risky.values

        # Record sleeve weights
        sleeve_alloc = current_risky.copy()
        sleeve_alloc[f"cash::{CASH_PROXY}"] = current_cash
        sleeve_alloc.name = date
        sleeve_w_rows.append(sleeve_alloc)

        # Roll up to ETF level (look-through using sleeve positions)
        etf_w = pd.Series(0.0, index=etf_universe)
        for sleeve in panel:
            if sleeve in sleeve_positions:
                pos_today = sleeve_positions[sleeve].reindex([date]).fillna(0.0).iloc[0]
                etf_w = etf_w.add(current_risky[sleeve] * pos_today.reindex(etf_universe).fillna(0.0), fill_value=0.0)
        etf_w[CASH_PROXY] = float(etf_w.get(CASH_PROXY, 0.0)) + current_cash
        total = float(etf_w.sum())
        if total > EPS:
            etf_w = etf_w / total
        else:
            etf_w[:] = 0.0
            etf_w[CASH_PROXY] = 1.0
        etf_w.name = date
        etf_w_rows.append(etf_w)

    sleeve_weights_df = pd.DataFrame(sleeve_w_rows).fillna(0.0)
    sleeve_weights_df.index.name = None
    etf_weights_df = pd.DataFrame(etf_w_rows).fillna(0.0)
    etf_weights_df.index.name = None

    # Net returns: weights at t earn returns realized t -> t+1
    next_week = weekly_returns.shift(-1)
    common = etf_weights_df.index.intersection(next_week.index)
    common_etfs = [c for c in etf_weights_df.columns if c in next_week.columns]
    aligned_w = etf_weights_df.loc[common, common_etfs]
    aligned_r = next_week.loc[common, common_etfs].fillna(0.0)
    gross = (aligned_w * aligned_r).sum(axis=1)
    turnover = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * TURNOVER_HALFSPREAD
    net = gross - cost

    return sleeve_weights_df, etf_weights_df, net


# --------------------------------------------------------------------------
# diagnostics
# --------------------------------------------------------------------------

def w1_diagnostics(sleeve_weights: pd.DataFrame, name: str) -> dict:
    panel_cols = [c for c in sleeve_weights.columns if not c.startswith("cash::")]
    if W1_NAME not in sleeve_weights.columns:
        return {
            "version_name": name,
            "panel_size": int(len(panel_cols)),
            "w1_in_panel": False,
            "avg_w1_weight": 0.0,
            "median_w1_weight": 0.0,
            "max_w1_weight": 0.0,
            "p90_w1_weight": 0.0,
            "obs": int(len(sleeve_weights)),
        }
    w1 = sleeve_weights[W1_NAME]
    return {
        "version_name": name,
        "panel_size": int(len(panel_cols)),
        "w1_in_panel": True,
        "avg_w1_weight": float(w1.mean()),
        "median_w1_weight": float(w1.median()),
        "max_w1_weight": float(w1.max()),
        "p90_w1_weight": float(w1.quantile(0.90)),
        "obs": int(len(sleeve_weights)),
    }


def w1_state_usage(sleeve_weights: pd.DataFrame, market_state_history: pd.DataFrame, name: str) -> pd.DataFrame:
    if W1_NAME not in sleeve_weights.columns:
        return pd.DataFrame()
    aligned = sleeve_weights[[W1_NAME]].join(market_state_history[["market_state"]], how="inner")
    rows = []
    for state, sub in aligned.groupby("market_state"):
        rows.append({
            "version_name": name,
            "market_state": state,
            "observations": int(len(sub)),
            "avg_w1_weight": float(sub[W1_NAME].mean()),
            "median_w1_weight": float(sub[W1_NAME].median()),
            "max_w1_weight": float(sub[W1_NAME].max()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# validation bundle (mirrors Phase X / Y)
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
    u1a_full = full_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout = holdout_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout_returns = returns_map[PHASEU_U1A_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

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
            "full_raw_delta_vs_u1a": float(cand_full["raw_target_composite"] - u1a_full["raw_target_composite"]),
            "holdout_raw_delta_vs_u1a": float(cand_holdout["raw_target_composite"] - u1a_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_u1a": float(cand_holdout["sharpe"] - u1a_holdout["sharpe"]),
            "bootstrap_prob_vs_u1a": ppe.safe_bootstrap(cand_holdout_returns, u1a_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    classification_df = pairwise_df[pairwise_df["version_name"].isin(candidate_names)].copy()

    best_non_prod = (
        full_df[full_df["version_name"] != PRODUCTION_PIN]
        .sort_values("raw_target_composite", ascending=False)
        .iloc[0]["version_name"]
    )

    def classify(row: pd.Series) -> str:
        prod_pass = (
            row["full_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["full_raw_composite_delta_vs_production_min"]
            and row["holdout_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["holdout_sharpe_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_sharpe_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.PRODUCTION_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["rolling_mean_raw_delta_vs_production"] > ppe.PRODUCTION_RULE["rolling_mean_raw_delta_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.PRODUCTION_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.PRODUCTION_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.PRODUCTION_RULE["cvar_worsening_cap"]
        )
        if prod_pass:
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
            row["full_raw_delta_vs_u1a"] > 0.0
            or row["holdout_sharpe_delta_vs_u1a"] > 0.0
            or row["holdout_raw_delta_vs_u1a"] > 0.0
            or row["bootstrap_prob_vs_u1a"] > 0.5
        )
        return "Research-only" if research else "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_z_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_z_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_z_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_z_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_z_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_z_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase Z — Production HRP / Dynamic-Risk-Budget Architecture on the 7-Sleeve Panel",
        "panel_7": PANEL_7,
        "panel_5_production": PANEL_5_PRODUCTION,
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_z_candidates": list(candidate_names),
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "architecture": {
            "allocator": "HRP (single-linkage on correlation distance, bisection inverse-variance)",
            "tilt": "dynamic_risk_budget (rank-based 26w conviction, ±15%; recovery_fragile +4/-4 off/def; stressed_panic -8 off, +8 RC, +5 TAA)",
            "overlay": "lighter_both_targeted_narrow_plus_confirmed (self-gated 0.04/0.35; non-self-gated 0.025/0.20 in fragile/strong_neutral; 0.015/0.15 in confirmed)",
            "meta": "Z1=regime_confidence_boost; Z2=combo_abc; Z3/Z4=regime_confidence_boost",
            "max_sleeve_weight": MAX_SLEEVE_WEIGHT,
            "target_vol_ann": TARGET_VOL_ANN,
        },
    }
    (LAYER3_DIR / "phase_z_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {"full": full_df, "dev": dev_df, "holdout": holdout_df, "rolling": rolling_df, "pairwise": pairwise_df, "classification": classification_df}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

Z1_NAME = "improved_phasez_production_hrp_7sleeve"
Z2_NAME = "improved_phasez_shadow_hrp_7sleeve"
Z3_NAME = "improved_phasez_w1_integrated_hrp_7sleeve"
Z4_NAME = "improved_phasez_production_hrp_5sleeve_ablation"
PHASE_Z_CANDIDATES = [Z1_NAME, Z2_NAME, Z3_NAME, Z4_NAME]


def main() -> None:
    print("Loading sleeve panels...")
    sleeves_all = sorted(set(PANEL_7) | set(PANEL_5_PRODUCTION))
    sleeve_returns_all = pd.DataFrame({s: load_sleeve_returns(s) for s in sleeves_all}).dropna(how="all")
    sleeve_positions_all = {s: load_sleeve_positions(s) for s in sleeves_all}
    market_state_history = load_market_state()
    overlay_states = load_overlay_states()
    phase2b_pred = load_phase2b_predictions()
    weekly_returns = load_weekly_returns()

    print("\n=== Building Z1 (production HRP architecture on 7-sleeve panel) ===")
    z1_sw, z1_ew, z1_ret = build_candidate(
        PANEL_7,
        meta_mode="regime_confidence_boost",
        sleeve_returns_panel=sleeve_returns_all[PANEL_7],
        sleeve_positions={s: sleeve_positions_all[s] for s in PANEL_7},
        market_state_history=market_state_history,
        overlay_states=overlay_states,
        phase2b_pred=phase2b_pred,
        weekly_returns=weekly_returns,
    )

    print("=== Building Z2 (shadow HRP architecture on 7-sleeve panel) ===")
    z2_sw, z2_ew, z2_ret = build_candidate(
        PANEL_7,
        meta_mode="combo_abc",
        sleeve_returns_panel=sleeve_returns_all[PANEL_7],
        sleeve_positions={s: sleeve_positions_all[s] for s in PANEL_7},
        market_state_history=market_state_history,
        overlay_states=overlay_states,
        phase2b_pred=phase2b_pred,
        weekly_returns=weekly_returns,
    )

    print("=== Building Z3 (W1-integrated HRP variant on 7-sleeve panel) ===")
    z3_sw, z3_ew, z3_ret = build_candidate(
        PANEL_7,
        meta_mode="regime_confidence_boost",
        sleeve_returns_panel=sleeve_returns_all[PANEL_7],
        sleeve_positions={s: sleeve_positions_all[s] for s in PANEL_7},
        market_state_history=market_state_history,
        overlay_states=overlay_states,
        phase2b_pred=phase2b_pred,
        weekly_returns=weekly_returns,
        w1_floor_nonstressed=True,
        w1_in_defensive=True,
    )

    print("=== Building Z4 (production HRP architecture on original 5-sleeve subset — ablation) ===")
    z4_sw, z4_ew, z4_ret = build_candidate(
        PANEL_5_PRODUCTION,
        meta_mode="regime_confidence_boost",
        sleeve_returns_panel=sleeve_returns_all[PANEL_5_PRODUCTION],
        sleeve_positions={s: sleeve_positions_all[s] for s in PANEL_5_PRODUCTION},
        market_state_history=market_state_history,
        overlay_states=overlay_states,
        phase2b_pred=phase2b_pred,
        weekly_returns=weekly_returns,
    )

    bundles = [
        (Z1_NAME, z1_sw, z1_ew, z1_ret),
        (Z2_NAME, z2_sw, z2_ew, z2_ret),
        (Z3_NAME, z3_sw, z3_ew, z3_ret),
        (Z4_NAME, z4_sw, z4_ew, z4_ret),
    ]

    print("\n=== Saving portfolio_version files ===")
    w1_diag_rows = []
    w1_state_rows = []
    for name, sw, ew, ret in bundles:
        sw.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")
        ew.to_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        turnover = ew.diff().abs().sum(axis=1).fillna(0.0)
        cost = turnover * TURNOVER_HALFSPREAD
        gross = ret + cost
        wealth = (1.0 + ret.fillna(0.0)).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        ret_df = pd.DataFrame({
            "gross_return": gross,
            "net_return": ret,
            "turnover": turnover.reindex(ret.index).fillna(0.0),
            "cost": cost.reindex(ret.index).fillna(0.0),
            "wealth": wealth,
            "drawdown": drawdown,
        })
        ret_df.to_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        w1_diag_rows.append(w1_diagnostics(sw, name))
        sus = w1_state_usage(sw, market_state_history, name)
        if not sus.empty:
            w1_state_rows.append(sus)

    pd.DataFrame(w1_diag_rows).to_csv(LAYER3_DIR / "phase_z_w1_diagnostics.csv", index=False)
    if w1_state_rows:
        pd.concat(w1_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_z_state_w1_usage.csv", index=False)

    print("\n=== Validation under Phase D rules ===")
    bundle = build_validation_bundle(PHASE_Z_CANDIDATES)

    print("\n=== Phase Z — full-history metrics ===")
    full_view = bundle["full"][bundle["full"]["version_name"].isin([
        PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASER_R3_REFERENCE, PHASEV_V1_REFERENCE
    ] + PHASE_Z_CANDIDATES)][[
        "version_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "raw_target_composite"
    ]]
    print(full_view.to_string(index=False))

    print("\n=== Phase Z — holdout metrics ===")
    holdout_view = bundle["holdout"][bundle["holdout"]["version_name"].isin([
        PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASER_R3_REFERENCE, PHASEV_V1_REFERENCE
    ] + PHASE_Z_CANDIDATES)][[
        "version_name", "ann_return", "sharpe", "max_drawdown", "raw_target_composite"
    ]]
    print(holdout_view.to_string(index=False))

    print("\n=== Phase Z — pairwise vs production ===")
    pw = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_Z_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
        "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production",
        "rolling_mean_raw_delta_vs_production", "bootstrap_prob_vs_production",
        "max_drawdown_delta_vs_production", "cvar_delta_vs_production",
    ]]
    print(pw.to_string(index=False))

    print("\n=== Phase Z — classification ===")
    cls = bundle["classification"][["version_name", "classification"]]
    print(cls.to_string(index=False))

    print("\n=== Phase Z — W1 weight diagnostics ===")
    print(pd.DataFrame(w1_diag_rows).to_string(index=False))

    if w1_state_rows:
        print("\n=== Phase Z — W1 state-conditional usage (Z1) ===")
        sus_z1 = pd.concat(w1_state_rows, ignore_index=True)
        sus_z1 = sus_z1[sus_z1["version_name"] == Z1_NAME]
        print(sus_z1.to_string(index=False))

    print("\nSaved Phase Z artifacts.")


if __name__ == "__main__":
    main()
