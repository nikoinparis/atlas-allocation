"""Causal cross-sectional factor construction for fixed and ML challengers."""

from __future__ import annotations

import math
import statistics
from datetime import date, timedelta


FEATURES = (
    "momentum_4w",
    "momentum_13w",
    "momentum_26w",
    "momentum_52w_skip_4w",
    "moving_average_distance_13w",
    "moving_average_distance_26w",
    "volatility_13w",
    "volatility_26w",
    "downside_volatility_26w",
    "drawdown_26w",
    "positive_week_share_26w",
)


def monthly_decision_dates(dates: list[str]) -> list[str]:
    return [day for index, day in enumerate(dates) if index == 0 or day[:7] != dates[index - 1][:7]]


def _trailing_return(values: list[float], lookback: int, skip: int = 0) -> float:
    end = len(values) - 1 - skip
    start = end - lookback
    if start < 0 or values[start] <= 0.0:
        raise ValueError("insufficient trailing price history")
    return values[end] / values[start] - 1.0


def asset_features(prices: list[float], *, asof_date: str) -> dict[str, float | str]:
    """Calculate features using a price vector ending at the permitted as-of date."""
    if len(prices) < 53 or any(not math.isfinite(value) or value <= 0.0 for value in prices):
        raise ValueError("53 valid positive prices are required")
    returns = [math.log(prices[index] / prices[index - 1]) for index in range(1, len(prices))]
    recent_13 = returns[-13:]
    recent_26 = returns[-26:]
    downside = [min(value, 0.0) for value in recent_26]
    trailing_prices = prices[-26:]
    return {
        "feature_asof_date": asof_date,
        "momentum_4w": _trailing_return(prices, 4),
        "momentum_13w": _trailing_return(prices, 13),
        "momentum_26w": _trailing_return(prices, 26),
        "momentum_52w_skip_4w": _trailing_return(prices, 48, skip=4),
        "moving_average_distance_13w": prices[-1] / statistics.fmean(prices[-13:]) - 1.0,
        "moving_average_distance_26w": prices[-1] / statistics.fmean(prices[-26:]) - 1.0,
        "volatility_13w": statistics.stdev(recent_13) * math.sqrt(52.0),
        "volatility_26w": statistics.stdev(recent_26) * math.sqrt(52.0),
        "downside_volatility_26w": math.sqrt(statistics.fmean(value * value for value in downside)) * math.sqrt(52.0),
        "drawdown_26w": prices[-1] / max(trailing_prices) - 1.0,
        "positive_week_share_26w": sum(value > 0.0 for value in recent_26) / 26.0,
    }


def percentile_ranks(values: dict[str, float]) -> dict[str, float]:
    """Return deterministic centered ranks in [-0.5, 0.5], averaging ties."""
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    result: dict[str, float] = {}
    index = 0
    denominator = max(1, len(ordered) - 1)
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_position = (index + end - 1) / 2.0
        rank = average_position / denominator - 0.5 if len(ordered) > 1 else 0.0
        for offset in range(index, end):
            result[ordered[offset][0]] = rank
        index = end
    return result


def fixed_composite_scores(
    rows: list[dict[str, float | str]], weights: dict[str, float]
) -> dict[str, float]:
    assets = [str(row["asset"]) for row in rows]
    ranks = {
        feature: percentile_ranks({str(row["asset"]): float(row[feature]) for row in rows})
        for feature in weights
    }
    return {
        asset: sum(float(weight) * ranks[feature][asset] for feature, weight in weights.items())
        for asset in assets
    }


def capped_inverse_volatility_weights(
    selected: list[str], volatility: dict[str, float], maximum_weight: float
) -> dict[str, float]:
    raw = {asset: 1.0 / max(volatility[asset], 1e-8) for asset in selected}
    result = {asset: value / sum(raw.values()) for asset, value in raw.items()}
    # Repeatedly redistribute excess to uncapped assets.
    for _ in range(len(selected)):
        excess = sum(max(0.0, value - maximum_weight) for value in result.values())
        if excess <= 1e-12:
            break
        uncapped = [asset for asset, value in result.items() if value < maximum_weight - 1e-12]
        for asset in result:
            result[asset] = min(result[asset], maximum_weight)
        if not uncapped:
            break
        basis = sum(result[asset] for asset in uncapped)
        for asset in uncapped:
            result[asset] += excess * result[asset] / basis
    total = sum(result.values())
    return {asset: value / total for asset, value in result.items()}


def minimum_allowed_asof(decision_date: str) -> str:
    return (date.fromisoformat(decision_date) - timedelta(days=7)).isoformat()
