"""Causal confidence sizing helpers for the isolated ML challenger."""

from __future__ import annotations

import math
import statistics


def buffered_membership(
    previous_assets: list[str], scores: dict[str, float], *, portfolio_size: int = 5,
    iqr_multiplier: float = 0.25,
) -> tuple[list[str], dict[str, float | int]]:
    """Retain incumbents unless a challenger clears a scale-aware score hurdle."""
    if len(scores) < portfolio_size:
        raise ValueError("not enough scored assets for requested portfolio size")
    ranked = sorted(scores, key=lambda asset: (scores[asset], asset), reverse=True)
    incumbents = [asset for asset in previous_assets if asset in scores][:portfolio_size]
    for asset in ranked:
        if len(incumbents) >= portfolio_size:
            break
        if asset not in incumbents:
            incumbents.append(asset)
    values = list(scores.values())
    buffer = iqr_multiplier * (linear_percentile(values, 0.75) - linear_percentile(values, 0.25))
    replacements = 0
    while True:
        weakest = min(incumbents, key=lambda asset: (scores[asset], asset))
        challengers = [asset for asset in ranked if asset not in incumbents]
        if not challengers or scores[challengers[0]] <= scores[weakest] + buffer:
            break
        incumbents[incumbents.index(weakest)] = challengers[0]
        replacements += 1
    selected = sorted(incumbents, key=lambda asset: (scores[asset], asset), reverse=True)
    return selected, {"prediction_iqr": buffer / iqr_multiplier if iqr_multiplier else 0.0, "replacement_buffer": buffer, "replacements": replacements}


def apply_weight_turnover_buffer(
    previous: dict[str, float], target: dict[str, float], hurdle: float = 0.10,
) -> tuple[dict[str, float], dict[str, float | bool]]:
    """Skip economically small target changes using one-way turnover."""
    assets = set(previous) | set(target)
    turnover = 0.5 * sum(abs(target.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in assets)
    skipped = bool(previous) and turnover < hurdle
    return (dict(previous) if skipped else dict(target)), {"proposed_turnover": turnover, "weight_update_skipped": skipped}


def linear_percentile(values: list[float], probability: float) -> float:
    """Return a deterministic, linearly interpolated percentile."""
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between zero and one")
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def raw_confidence(
    selected_predictions: list[float], comparison_predictions: list[float],
    selected_sign_agreement: list[float], selected_member_std: list[float],
    selected_family_std: list[float], denominator_floor: float = 0.01,
) -> dict[str, float]:
    """Combine ensemble separation, agreement, and disagreement without outcomes."""
    lengths = {len(selected_predictions), len(selected_sign_agreement), len(selected_member_std), len(selected_family_std)}
    if lengths != {len(selected_predictions)} or not selected_predictions or not comparison_predictions:
        raise ValueError("confidence inputs are empty or have inconsistent selected lengths")
    separation = statistics.fmean(selected_predictions) - statistics.fmean(comparison_predictions)
    agreement = statistics.fmean(selected_sign_agreement)
    member_std = statistics.fmean(selected_member_std)
    family_std = statistics.fmean(selected_family_std)
    disagreement = member_std + family_std
    score = separation * agreement / max(disagreement, denominator_floor)
    return {
        "separation": separation,
        "agreement": agreement,
        "member_std": member_std,
        "family_std": family_std,
        "disagreement": disagreement,
        "raw_confidence": score,
    }


def causal_weight(score: float, prior_scores: list[float], minimum_history: int = 24) -> tuple[float, dict[str, float | None]]:
    """Size from expanding thresholds that exclude the current score."""
    if len(prior_scores) < minimum_history:
        return 0.0, {"p60": None, "p80": None, "p95": None}
    thresholds = {
        "p60": linear_percentile(prior_scores, 0.60),
        "p80": linear_percentile(prior_scores, 0.80),
        "p95": linear_percentile(prior_scores, 0.95),
    }
    if score >= thresholds["p95"]:
        weight = 0.30
    elif score >= thresholds["p80"]:
        weight = 0.20
    elif score >= thresholds["p60"]:
        weight = 0.10
    else:
        weight = 0.0
    return weight, thresholds


def causal_strong_weight(
    score: float, prior_scores: list[float], minimum_history: int = 24,
) -> tuple[float, dict[str, float | None]]:
    """Abstain below the prior 80th percentile; reserve capital for strong tiers."""
    if len(prior_scores) < minimum_history:
        return 0.0, {"p80": None, "p95": None}
    thresholds = {
        "p80": linear_percentile(prior_scores, 0.80),
        "p95": linear_percentile(prior_scores, 0.95),
    }
    if score >= thresholds["p95"]:
        weight = 0.30
    elif score >= thresholds["p80"]:
        weight = 0.20
    else:
        weight = 0.0
    return weight, thresholds


def persistent_cost_aware_weight(
    current_strong_weight: float, previous_strong_weight: float | None,
    prior_high_cost_excess_returns: list[float], minimum_cost_history: int = 26,
) -> tuple[float, dict[str, float | int | bool | None]]:
    """Activate only after persistent confidence and positive prior high-cost excess."""
    persistent = (
        previous_strong_weight is not None
        and current_strong_weight > 0.0
        and previous_strong_weight > 0.0
    )
    enough_cost_history = len(prior_high_cost_excess_returns) >= minimum_cost_history
    trailing_mean = (
        statistics.fmean(prior_high_cost_excess_returns[-minimum_cost_history:])
        if enough_cost_history else None
    )
    cost_hurdle_pass = trailing_mean is not None and trailing_mean > 0.0
    weight = min(current_strong_weight, previous_strong_weight) if persistent and cost_hurdle_pass else 0.0
    return weight, {
        "persistence_pass": persistent,
        "cost_history_observations": min(len(prior_high_cost_excess_returns), minimum_cost_history),
        "trailing_high_cost_mean_excess": trailing_mean,
        "cost_hurdle_pass": cost_hurdle_pass,
    }


def guarded_weight(
    desired_weight: float, prior_realized_returns: list[float], *, volatility_weeks: int = 13,
    volatility_limit: float = 0.18, volatility_cap: float = 0.10,
    drawdown_weeks: int = 26, drawdown_stop: float = -0.12,
) -> tuple[float, dict[str, float | bool | None]]:
    """Apply trailing risk guards using only returns already realized."""
    volatility = None
    if len(prior_realized_returns) >= volatility_weeks:
        recent = prior_realized_returns[-volatility_weeks:]
        volatility = statistics.pstdev(recent) * math.sqrt(52.0)
    drawdown = None
    if prior_realized_returns:
        recent = prior_realized_returns[-drawdown_weeks:]
        wealth = 1.0
        peak = 1.0
        drawdown = 0.0
        for value in recent:
            wealth *= 1.0 + value
            peak = max(peak, wealth)
            drawdown = min(drawdown, wealth / peak - 1.0)
    stopped = drawdown is not None and drawdown <= drawdown_stop
    volatility_capped = volatility is not None and volatility > volatility_limit
    weight = 0.0 if stopped else min(desired_weight, volatility_cap) if volatility_capped else desired_weight
    return weight, {
        "trailing_annualized_volatility": volatility,
        "trailing_drawdown": drawdown,
        "volatility_cap_active": volatility_capped,
        "drawdown_stop_active": stopped,
    }
