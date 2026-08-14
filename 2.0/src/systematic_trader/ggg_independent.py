"""Independent Version 2 implementation of the Version 1 GGG allocator.

The module intentionally imports no Version 1 Python or notebook code. It
consumes pinned CSV artifacts, implements the six allocator stages directly,
and exposes stage traces for equivalence and anti-leakage testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "composite_regime_offense_component",
    "composite_regime_defense_component",
    "taa_10m_sma",
]
OFFENSIVE_SLEEVES = SLEEVES[:4]
DEFENSIVE_SLEEVES = SLEEVES[4:]
SELF_GATED_SLEEVES = {"dual_momentum_topn", "cta_trend_long_only", "taa_10m_sma"}
DEFAULT_OFFENSE = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
RECOVERY_OFFENSE = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ"]
DEFENSE_ASSETS = ["HYG", "LQD", "GLD", "TLT"]
CASH_PROXY = "BIL"
CHECKPOINT_STAGES = [
    "raw_hrp_sleeve_weights",
    "post_state_tilt_sleeve_weights",
    "post_layer3_expression_sleeve_weights",
    "post_overlay_pre_lookthrough_sleeve_weights",
    "final_sleeve_weights",
    "final_etf_weights",
]


@dataclass
class GGGResult:
    stages: dict[str, pd.DataFrame]
    returns: pd.DataFrame
    audit_log: pd.DataFrame
    sleeve_return_panel: pd.DataFrame
    component_positions: dict[str, pd.DataFrame]


def read_dated_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame else "date" if "date" in frame else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)


def next_week_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Map each date to the following row's close-to-close return.

    This avoids negative-shift syntax in decision code. The final date has no
    following observation and is filled with zero for saved-path compatibility.
    """
    ordinary = prices.apply(pd.to_numeric, errors="coerce").pct_change()
    result = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns, dtype=float)
    if len(prices) > 1:
        result.iloc[:-1] = ordinary.iloc[1:].to_numpy()
    return result


def normalize_long_only(weights: pd.Series, max_weight: float = 0.45) -> pd.Series:
    result = pd.Series(weights, dtype=float).clip(lower=0.0).fillna(0.0)
    if result.sum() <= 0:
        result[:] = 1.0 / len(result) if len(result) else 0.0
        return result
    result /= result.sum()
    for _ in range(25):
        over = result > max_weight
        if not over.any():
            break
        excess = (result[over] - max_weight).sum()
        result.loc[over] = max_weight
        under = result < max_weight - 1e-12
        if under.any() and excess > 0:
            result.loc[under] += excess * result.loc[under] / result.loc[under].sum()
        elif excess > 0:
            result += excess / len(result)
        result = result.clip(lower=0.0)
        result /= result.sum()
    return result / result.sum()


def sanitize_covariance(covariance: pd.DataFrame, variance_floor: float = 1e-12) -> pd.DataFrame:
    covariance = pd.DataFrame(covariance).copy().replace([np.inf, -np.inf], np.nan)
    common = covariance.index.intersection(covariance.columns)
    covariance = covariance.loc[common, common]
    if covariance.empty:
        return covariance
    covariance = (covariance + covariance.T) / 2.0
    diagonal = pd.Series(np.diag(covariance.to_numpy()), index=covariance.index)
    keep = diagonal[diagonal > variance_floor].index
    covariance = covariance.loc[keep, keep]
    if covariance.empty:
        return covariance
    finite = pd.Series(np.isfinite(covariance.to_numpy()).all(axis=1), index=covariance.index)
    covariance = covariance.loc[finite[finite].index, finite[finite].index]
    if covariance.empty:
        return covariance
    values = covariance.to_numpy(copy=True)
    diagonal_index = np.diag_indices_from(values)
    values[diagonal_index] = np.maximum(np.diag(values), variance_floor)
    return pd.DataFrame(values, index=covariance.index, columns=covariance.columns)


def inverse_volatility_weights(covariance: pd.DataFrame) -> pd.Series:
    volatility = pd.Series(np.sqrt(np.diag(covariance.to_numpy())), index=covariance.index)
    inverse = 1.0 / volatility.replace(0.0, np.nan)
    return normalize_long_only(inverse, max_weight=1.0)


def cluster_variance(covariance: pd.DataFrame, members: list[str]) -> float:
    subcovariance = covariance.loc[members, members]
    weights = inverse_volatility_weights(subcovariance)
    return float(weights.to_numpy() @ subcovariance.to_numpy() @ weights.to_numpy())


def optimize_hrp(covariance: pd.DataFrame) -> pd.Series:
    covariance = sanitize_covariance(covariance)
    if covariance.empty:
        return pd.Series(dtype=float)
    if len(covariance) == 1:
        return pd.Series(1.0, index=covariance.index)
    values = covariance.to_numpy()
    volatility = np.sqrt(np.diag(values))
    correlation = values / np.outer(volatility, volatility)
    correlation = np.clip(correlation, -1.0, 1.0)
    np.fill_diagonal(correlation, 1.0)
    distance = np.sqrt(np.clip((1.0 - correlation) / 2.0, 0.0, 1.0))
    np.fill_diagonal(distance, 0.0)
    tree = linkage(squareform(distance, checks=False), method="single")
    ordered = covariance.index[leaves_list(tree)].tolist()
    weights = pd.Series(1.0, index=ordered)
    clusters = [ordered]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        split = len(cluster) // 2
        left, right = cluster[:split], cluster[split:]
        left_variance = cluster_variance(covariance, left)
        right_variance = cluster_variance(covariance, right)
        alpha = 1.0 - left_variance / max(left_variance + right_variance, 1e-12)
        weights.loc[left] *= alpha
        weights.loc[right] *= 1.0 - alpha
        clusters.extend([left, right])
    return normalize_long_only(weights.reindex(covariance.index).fillna(0.0), max_weight=0.45)


def compute_strategy_returns(weights: pd.DataFrame, forward_returns: pd.DataFrame, cost_bps: float = 10.0) -> pd.Series:
    aligned = weights.reindex(index=forward_returns.index, columns=forward_returns.columns).fillna(0.0)
    gross = (aligned * forward_returns).sum(axis=1)
    turnover = 0.5 * aligned.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    return gross - turnover.fillna(0.0) * cost_bps / 10000.0


def project_component(source: pd.DataFrame, states: pd.Series, *, defense: bool = False) -> pd.DataFrame:
    output = pd.DataFrame(0.0, index=source.index, columns=source.columns)
    for date in source.index:
        if defense:
            columns = [column for column in DEFENSE_ASSETS if column in source]
        else:
            recipe = RECOVERY_OFFENSE if states.get(date) == "recovery_confirmed" else DEFAULT_OFFENSE
            columns = [column for column in recipe if column in source]
        total = float(source.loc[date, columns].sum()) if columns else 0.0
        if total > 1e-12:
            output.loc[date, columns] = source.loc[date, columns] / total
        else:
            output.loc[date, CASH_PROXY] = 1.0
    return output


def _explicit_bucket_budget(
    weights: pd.Series,
    target_bucket_weights: dict[str, float],
    offense_target_mix: dict[str, float] | None = None,
    offense_mix_strength: float = 0.40,
    defense_target_mix: dict[str, float] | None = None,
    defense_mix_strength: float = 0.40,
) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    buckets = {
        "offense": [name for name in OFFENSIVE_SLEEVES if name in adjusted],
        "defense": [name for name in DEFENSIVE_SLEEVES if name in adjusted],
    }
    targets = pd.Series({key: float(value) for key, value in target_bucket_weights.items() if buckets.get(key)}, dtype=float)
    targets /= targets.sum()
    for bucket, members in buckets.items():
        if not members:
            continue
        current = adjusted.reindex(members).fillna(0.0).clip(lower=0.0)
        shares = current / current.sum() if current.sum() > 1e-12 else pd.Series(1.0 / len(members), index=members)
        requested_mix = offense_target_mix if bucket == "offense" else defense_target_mix if bucket == "defense" else None
        strength = offense_mix_strength if bucket == "offense" else defense_mix_strength
        if requested_mix:
            target = pd.Series({name: float(value) for name, value in requested_mix.items() if name in members and value > 0.0})
            if not target.empty:
                target /= target.sum()
                full_target = pd.Series(0.0, index=members)
                full_target.loc[target.index] = target
                shares = ((1.0 - strength) * shares + strength * full_target).clip(lower=0.0)
                shares /= shares.sum()
        adjusted.loc[members] = float(targets.get(bucket, 0.0)) * shares
    return adjusted


def _bucket_share_cap(weights: pd.Series, bucket: list[str], cap_name: str, cap_share: float) -> pd.Series:
    adjusted = pd.Series(weights, dtype=float).copy()
    members = [name for name in bucket if name in adjusted]
    total = float(adjusted.reindex(members).clip(lower=0.0).sum())
    cap = cap_share * total
    current = float(adjusted.get(cap_name, 0.0))
    if current <= cap:
        return adjusted
    excess = current - cap
    adjusted.loc[cap_name] = cap
    adjusted.loc["composite_regime_offense_component"] += 0.70 * excess
    adjusted.loc["cta_trend_long_only"] += 0.30 * excess
    return adjusted


def is_strong_neutral(row: pd.Series) -> bool:
    def number(key: str) -> float:
        value = row.get(key, 0.0)
        return 0.0 if value is None or pd.isna(value) else float(value)
    return (
        str(row.get("market_state") or "") == "neutral_mixed"
        and number("market_trend_positive") > 0.0
        and number("breadth_sma_43") >= 0.55
        and number("breadth_26w_mom") >= 0.50
    )


def apply_state_tilt(raw_weights: pd.Series, state_row: pd.Series) -> pd.Series:
    adjusted = pd.Series(raw_weights, dtype=float).copy()
    state = str(state_row.get("market_state") or "")
    strong_neutral = is_strong_neutral(state_row)
    if state == "recovery_fragile":
        adjusted.loc[[name for name in OFFENSIVE_SLEEVES if name in adjusted]] *= 1.01
        adjusted.loc[[name for name in DEFENSIVE_SLEEVES if name in adjusted]] *= 0.99
    elif state == "stressed_panic":
        adjusted.loc[[name for name in OFFENSIVE_SLEEVES if name in adjusted]] *= 0.92
        if "composite_regime_defense_component" in adjusted:
            adjusted.loc["composite_regime_defense_component"] *= 1.06
        if "taa_10m_sma" in adjusted:
            adjusted.loc["taa_10m_sma"] *= 1.05
    if strong_neutral:
        adjusted = _explicit_bucket_budget(
            adjusted, {"offense": 0.65, "defense": 0.35},
            {"dual_momentum_topn": 0.22, "cta_trend_long_only": 0.22, "composite_selective_signals": 0.14, "composite_regime_offense_component": 0.42}, 0.40,
        )
    elif state == "recovery_confirmed":
        adjusted = _explicit_bucket_budget(
            adjusted, {"offense": 0.68, "defense": 0.32},
            {"dual_momentum_topn": 0.12, "cta_trend_long_only": 0.30, "composite_selective_signals": 0.04, "composite_regime_offense_component": 0.54}, 0.75,
            {"taa_10m_sma": 0.30, "composite_regime_defense_component": 0.70}, 0.65,
        )
        adjusted = _bucket_share_cap(adjusted, OFFENSIVE_SLEEVES, "dual_momentum_topn", 0.03)
    elif state == "recovery_fragile":
        adjusted = _explicit_bucket_budget(
            adjusted, {"offense": 0.60, "defense": 0.40},
            {"dual_momentum_topn": 0.18, "cta_trend_long_only": 0.22, "composite_selective_signals": 0.08, "composite_regime_offense_component": 0.52}, 0.40,
        )
    return normalize_long_only(adjusted, max_weight=0.45)


def build_variant_regime(regime: pd.DataFrame, state_history: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "market_state", "market_state_reason", "breadth_sma_43", "breadth_26w_mom",
        "market_trend_positive", "canary_breadth_default", "canary_breadth_pair",
        "transition_persistence_prob", "transition_good_state_prob", "transition_non_stress_prob",
        "market_state_stable",
    ]
    available = [column for column in columns if column in state_history]
    adjusted = regime.join(state_history[available], how="left")
    adjusted.loc[adjusted["risk_state"].eq("neutral"), "overlay_multiplier"] = adjusted.loc[
        adjusted["risk_state"].eq("neutral"), "overlay_multiplier"
    ].clip(lower=0.80)
    adjusted.loc[adjusted["risk_state"].eq("stressed"), "overlay_multiplier"] = adjusted.loc[
        adjusted["risk_state"].eq("stressed"), "overlay_multiplier"
    ].clip(lower=0.40)
    strong = adjusted.apply(is_strong_neutral, axis=1)
    floors = {
        "recovery_fragile": 0.96,
        "recovery_confirmed": 0.92,
        "calm_trend": 1.00,
    }
    for state, floor in floors.items():
        mask = adjusted["market_state"].eq(state)
        adjusted.loc[mask, "overlay_multiplier"] = adjusted.loc[mask, "overlay_multiplier"].clip(lower=floor)
    adjusted.loc[strong, "overlay_multiplier"] = adjusted.loc[strong, "overlay_multiplier"].clip(lower=0.94)
    return adjusted


def regime_confidence_boost(regime_multiplier: float, market_state: str, prediction: pd.Series | None) -> float:
    if market_state == "stressed_panic" or prediction is None or prediction.empty:
        return regime_multiplier
    value = prediction.get("p_regime_confidence")
    if value is None or pd.isna(value) or float(value) < 0.55:
        return regime_multiplier
    boost = min(0.045, max(0.0, 0.10 * (float(value) - 0.55) / 0.45))
    return float(np.clip(regime_multiplier + boost, 0.0, 1.0))


def apply_overlay(
    tilted: pd.Series,
    covariance: pd.DataFrame,
    previous: pd.Series,
    state_row: pd.Series,
    regime_row: pd.Series,
    prediction: pd.Series | None,
    target_volatility: float = 0.12,
) -> tuple[pd.Series, float, dict]:
    raw = normalize_long_only(tilted, max_weight=0.45)
    state = str(state_row.get("market_state") or "")
    regime_multiplier = regime_confidence_boost(float(regime_row.get("overlay_multiplier", 1.0)), state, prediction)
    speed = 0.80 if state in {"recovery_rebound", "recovery_confirmed", "calm_trend"} else 0.60 if state == "recovery_fragile" else 0.40
    previous = normalize_long_only(previous.reindex(raw.index).fillna(0.0), max_weight=0.45)
    blended = normalize_long_only((1.0 - speed) * previous + speed * raw, max_weight=0.45)
    covariance = covariance.reindex(index=blended.index, columns=blended.index)
    predicted_volatility = np.sqrt(max(float(blended.to_numpy() @ covariance.to_numpy() @ blended.to_numpy()), 0.0)) * np.sqrt(52.0)
    if target_volatility <= 0:
        raise ValueError("target_volatility must be positive")
    target_vol_multiplier = 1.0 if predicted_volatility <= 0 or pd.isna(predicted_volatility) else float(np.clip(target_volatility / predicted_volatility, 0.35, 1.0))
    regime_binding = regime_multiplier < target_vol_multiplier and regime_multiplier < 0.999
    multipliers = pd.Series(min(1.0, regime_multiplier, target_vol_multiplier), index=blended.index)
    strong = is_strong_neutral(state_row)
    if regime_binding and state != "stressed_panic" and (strong or state in {"recovery_fragile", "recovery_confirmed"}):
        if strong:
            relief_cap, relief_scale, other_cap, other_scale = 0.033, 0.26, 0.012, 0.09
        elif state == "recovery_fragile":
            relief_cap, relief_scale, other_cap, other_scale = 0.045, 0.34, 0.016, 0.12
        else:
            relief_cap, relief_scale, other_cap, other_scale = 0.048, 0.38, 0.019, 0.14
        headroom = max(0.0, target_vol_multiplier - regime_multiplier)
        headroom_cap = 0.75 * headroom if headroom > 0 else relief_cap
        self_relief = min(relief_cap, relief_scale * max(0.0, 1.0 - regime_multiplier), headroom_cap)
        other_relief = min(other_cap, other_scale * max(0.0, 1.0 - regime_multiplier), 0.75 * headroom if headroom > 0 else other_cap)
        multipliers.loc[:] = regime_multiplier
        self_names = [name for name in multipliers.index if name in SELF_GATED_SLEEVES]
        other_names = [name for name in multipliers.index if name not in SELF_GATED_SLEEVES]
        multipliers.loc[self_names] = min(1.0, regime_multiplier + self_relief)
        multipliers.loc[other_names] = min(1.0, regime_multiplier + other_relief)
        total = float((blended * multipliers).sum())
        if target_vol_multiplier < 1.0 and total > target_vol_multiplier and total > 1e-12:
            multipliers *= target_vol_multiplier / total
    risky = blended * multipliers
    target_cash = 0.130 if strong else 0.055 if state == "recovery_confirmed" else 0.115 if state == "recovery_fragile" else None
    tolerance = 0.010 if strong or state == "recovery_confirmed" else 0.015 if state == "recovery_fragile" else 0.0
    if target_cash is not None and state != "stressed_panic":
        current_risky = float(risky.sum())
        current_cash = max(0.0, 1.0 - current_risky)
        guardrail_cash = max(0.0, 1.0 - target_vol_multiplier)
        base_target_cash = max(target_cash, guardrail_cash)
        duplicate_threshold = base_target_cash + tolerance
        desired_cash = current_cash if current_cash <= duplicate_threshold + 1e-12 else duplicate_threshold
        desired_risky = min(1.0, max(0.0, 1.0 - desired_cash))
        if current_risky > 1e-12 and abs(desired_risky - current_risky) > 1e-12:
            risky *= desired_risky / current_risky
    cash = max(0.0, 1.0 - float(risky.sum()))
    return risky, cash, {
        "market_state": state, "reallocation_speed": speed,
        "regime_multiplier": regime_multiplier, "target_vol_multiplier": target_vol_multiplier,
        "predicted_ann_vol": predicted_volatility, "cash_weight": cash,
    }


def apply_etf_cap(weights: pd.Series, max_risky_weight: float | None = 0.35) -> pd.Series:
    weights = pd.Series(weights, dtype=float).clip(lower=0.0).fillna(0.0)
    risky = weights.drop(labels=[CASH_PROXY], errors="ignore")
    if max_risky_weight is not None:
        if max_risky_weight <= 0 or max_risky_weight > 1:
            raise ValueError("max_risky_weight must be in (0, 1]")
        risky = risky.clip(upper=max_risky_weight)
    if risky.sum() > 1.0:
        risky /= risky.sum()
    result = risky.reindex(weights.index, fill_value=0.0)
    result.loc[CASH_PROXY] = 1.0 - risky.sum()
    return result


def lookthrough(
    date: pd.Timestamp,
    sleeve_weights: pd.Series,
    sleeve_positions: dict[str, pd.DataFrame],
    universe: list[str],
    cash_weight: float,
    max_etf_weight: float | None = 0.35,
) -> pd.Series:
    final = pd.Series(0.0, index=universe)
    for sleeve, weight in sleeve_weights.dropna().items():
        panel = sleeve_positions.get(sleeve)
        if panel is None or date not in panel.index:
            continue
        final = final.add(float(weight) * panel.loc[date].reindex(universe).fillna(0.0), fill_value=0.0)
    final.loc[CASH_PROXY] += cash_weight
    return apply_etf_cap(final, max_risky_weight=max_etf_weight)


def portfolio_path(weights: pd.DataFrame, forward_returns: pd.DataFrame, cost_bps: float = 10.0) -> pd.DataFrame:
    aligned_returns = forward_returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    gross = (weights * aligned_returns).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame({"gross_return": gross, "net_return": net, "turnover": turnover, "cost": cost, "wealth": wealth, "drawdown": drawdown})


def run_from_artifacts(
    source_root: Path,
    *,
    prices_override: pd.DataFrame | None = None,
    causal_training: bool = False,
    legacy_terminal_rebalance: bool = True,
    target_volatility: float = 0.12,
    max_etf_weight: float | None = 0.35,
) -> GGGResult:
    source_root = Path(source_root)
    data = source_root / "data"
    layer2a = data / "03_layer2a_strategy_logic"
    prices = (
        prices_override.copy()
        if prices_override is not None
        else read_dated_csv(data / "01_data_hub/weekly_prices.csv")
    ).apply(pd.to_numeric, errors="coerce")
    forward_returns = next_week_returns(prices)
    state_history = read_dated_csv(data / "04_layer2b_risk_regime_engine/market_state_history.csv")
    regime = read_dated_csv(data / "04_layer2b_risk_regime_engine/regime_states.csv")
    predictions = read_dated_csv(data / "04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv")
    states = state_history["market_state"].reindex(prices.index)
    source_composite = read_dated_csv(layer2a / "strategy_positions_composite_regime_conditioned.csv").reindex(index=prices.index, columns=prices.columns).fillna(0.0)
    offense_positions = project_component(source_composite, states, defense=False)
    defense_positions = project_component(source_composite, states, defense=True)
    sleeve_positions = {
        name: read_dated_csv(layer2a / f"strategy_positions_{name}.csv").reindex(index=prices.index, columns=prices.columns).fillna(0.0)
        for name in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "taa_10m_sma"]
    }
    sleeve_positions["composite_regime_offense_component"] = offense_positions
    sleeve_positions["composite_regime_defense_component"] = defense_positions
    sleeve_returns = pd.DataFrame(index=prices.index)
    for name in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "taa_10m_sma"]:
        sleeve_returns[name] = pd.to_numeric(read_dated_csv(layer2a / f"strategy_returns_{name}.csv")["net_return"], errors="coerce").reindex(prices.index).fillna(0.0)
    sleeve_returns["composite_regime_offense_component"] = compute_strategy_returns(offense_positions, forward_returns)
    sleeve_returns["composite_regime_defense_component"] = compute_strategy_returns(defense_positions, forward_returns)
    sleeve_returns = sleeve_returns.reindex(columns=SLEEVES)
    variant_regime = build_variant_regime(regime, state_history)

    month = prices.index.to_period("M").astype(str).to_numpy()
    rebalance_values = np.zeros(len(prices), dtype=bool)
    if len(prices) > 1:
        rebalance_values[:-1] = month[:-1] != month[1:]
    if len(prices):
        rebalance_values[-1] = bool(legacy_terminal_rebalance) or (
            (prices.index[-1] + pd.Timedelta(days=7)).month != prices.index[-1].month
        )
    rebalance = pd.Series(rebalance_values, index=prices.index)
    if len(rebalance):
        rebalance.iloc[0] = True
    current_risky = pd.Series(0.0, index=SLEEVES)
    current_cash = 1.0
    last_stage = {stage: pd.Series(0.0, index=SLEEVES + [f"cash::{CASH_PROXY}"]) for stage in CHECKPOINT_STAGES[:-1]}
    for stage in last_stage:
        last_stage[stage].loc[f"cash::{CASH_PROXY}"] = 1.0
    stage_rows = {stage: [] for stage in CHECKPOINT_STAGES}
    previous_regime_multiplier: float | None = None
    audit_rows = []

    def stage_series(weights: pd.Series, cash: float) -> pd.Series:
        row = pd.Series(0.0, index=SLEEVES + [f"cash::{CASH_PROXY}"])
        row.loc[weights.index.intersection(row.index)] = weights.reindex(row.index).dropna()
        row.loc[f"cash::{CASH_PROXY}"] = max(0.0, cash)
        return row

    for date in prices.index:
        if bool(rebalance.loc[date]):
            available_history = sleeve_returns.loc[:date, SLEEVES]
            # Each row is labeled by the date of the weights that earn the
            # following week's return. The historical V1 allocator included
            # the current row; a causal decision must stop at the prior row.
            if causal_training and len(available_history):
                available_history = available_history.iloc[:-1]
            train_slice = available_history.tail(156)
            counts = train_slice.count()
            active = counts[counts >= 78].index.tolist()
            if len(active) >= 2:
                train = train_slice[active].dropna(how="any")
                if len(train) >= 78:
                    covariance = sanitize_covariance(train.cov())
                    active = list(covariance.index)
                    raw = optimize_hrp(covariance)
                    state_row = state_history.loc[date] if date in state_history.index else pd.Series(dtype=float)
                    tilted = apply_state_tilt(raw, state_row)
                    expression = normalize_long_only(tilted, max_weight=0.45)
                    regime_row = variant_regime.loc[date] if date in variant_regime.index else pd.Series(dtype=float)
                    prediction = predictions.loc[date] if date in predictions.index else None
                    risky, cash, overlay_log = apply_overlay(
                        expression, covariance, current_risky.reindex(active).fillna(0.0),
                        state_row, regime_row, prediction, target_volatility,
                    )
                    current_risky = pd.Series(0.0, index=SLEEVES)
                    current_risky.loc[risky.index] = risky
                    current_cash = cash
                    previous_regime_multiplier = overlay_log["regime_multiplier"]
                    last_stage["raw_hrp_sleeve_weights"] = stage_series(raw, max(0.0, 1.0 - raw.sum()))
                    last_stage["post_state_tilt_sleeve_weights"] = stage_series(tilted, max(0.0, 1.0 - tilted.sum()))
                    last_stage["post_layer3_expression_sleeve_weights"] = stage_series(expression, max(0.0, 1.0 - expression.sum()))
                    last_stage["post_overlay_pre_lookthrough_sleeve_weights"] = stage_series(current_risky, current_cash)
                    audit_rows.append({"Date": date, "active_sleeves": len(active), "train_observations": len(train), **overlay_log})
        final_sleeve = stage_series(current_risky, current_cash)
        last_stage["final_sleeve_weights"] = final_sleeve
        for stage in CHECKPOINT_STAGES[:-1]:
            row = last_stage[stage].copy()
            row.name = date
            stage_rows[stage].append(row)
        final_etf = lookthrough(
            date, current_risky, sleeve_positions, list(prices.columns), current_cash,
            max_etf_weight=max_etf_weight,
        )
        final_etf.name = date
        stage_rows["final_etf_weights"].append(final_etf)

    stages = {stage: pd.DataFrame(rows).sort_index().fillna(0.0) for stage, rows in stage_rows.items()}
    returns = portfolio_path(stages["final_etf_weights"], forward_returns, cost_bps=10.0)
    return GGGResult(
        stages=stages, returns=returns,
        audit_log=pd.DataFrame(audit_rows).set_index("Date") if audit_rows else pd.DataFrame(),
        sleeve_return_panel=sleeve_returns,
        component_positions={"offense": offense_positions, "defense": defense_positions},
    )
