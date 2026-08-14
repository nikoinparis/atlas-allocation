"""Causal fragility-guard challenger inspired by the platform's 1.0 research."""

from __future__ import annotations

import statistics


def _clip(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def causal_quality_and_fragility(
    dates: list[str],
    prices: dict[str, dict[str, float | None]],
    risk_assets: list[str],
    *,
    lookback_weeks: int = 26,
) -> dict[str, dict[str, float | bool]]:
    """Use current-and-prior prices only; callers realize positions next week."""
    result: dict[str, dict[str, float | bool]] = {}
    persistent_positive = 0
    for index, decision in enumerate(dates):
        if index < lookback_weeks:
            result[decision] = {
                "breadth": 0.5, "path_clarity": 0.0, "persistence": 0.0,
                "quality": 0.0, "leadership_fragility": 0.0, "stressed": True,
            }
            continue
        start = dates[index - lookback_weeks]
        returns = []
        for asset in risk_assets:
            current = prices.get(decision, {}).get(asset)
            past = prices.get(start, {}).get(asset)
            if current is not None and past is not None and past > 0:
                returns.append((asset, current / past - 1.0))
        breadth = sum(value > 0.0 for _, value in returns) / len(returns) if returns else 0.0
        spy_path = []
        for offset in range(index - lookback_weeks + 1, index + 1):
            current = prices.get(dates[offset], {}).get("SPY")
            prior = prices.get(dates[offset - 1], {}).get("SPY")
            if current is not None and prior is not None and prior > 0:
                spy_path.append(current / prior - 1.0)
        total_spy = 1.0
        for value in spy_path:
            total_spy *= 1.0 + value
        total_spy -= 1.0
        path_clarity = abs(total_spy) / sum(abs(value) for value in spy_path) if spy_path and sum(abs(value) for value in spy_path) else 0.0
        persistent_positive = persistent_positive + 1 if breadth >= 0.5 else 0
        persistence = min(1.0, persistent_positive / 13.0)
        quality = _clip(((breadth - 0.5) * 2.0 + (path_clarity - 0.5) * 2.0 + (persistence - 0.5) * 2.0) / 3.0, -1.0, 1.0)
        values = [value for _, value in returns]
        leadership_spread = max(values) - statistics.median(values) if values else 0.0
        leadership_fragility = _clip(0.5 * breadth + 0.5 * leadership_spread / 0.25, 0.0, 1.0)
        spy_return = next((value for asset, value in returns if asset == "SPY"), -1.0)
        result[decision] = {
            "breadth": breadth,
            "path_clarity": path_clarity,
            "persistence": persistence,
            "quality": quality,
            "leadership_fragility": leadership_fragility,
            "stressed": breadth < 0.30 or spy_return < 0.0,
        }
    return result


def apply_fragility_guard(
    dates: list[str],
    targets: dict[str, dict[str, float]],
    features: dict[str, dict[str, float | bool]],
    *,
    offense_assets: set[str],
    boost_strength: float,
    crowding_threshold: float,
) -> tuple[dict[str, dict[str, float]], list[dict[str, float | str | bool]]]:
    output: dict[str, dict[str, float]] = {}
    audit: list[dict[str, float | str | bool]] = []
    for decision in dates:
        row = targets[decision]
        signal = features[decision]
        scale = 1.0
        if not bool(signal["stressed"]):
            scale = 1.0 + boost_strength * float(signal["quality"])
            if float(signal["leadership_fragility"]) > crowding_threshold:
                scale = min(1.0, scale)
        adjusted = {
            asset: weight * scale if asset in offense_assets else weight
            for asset, weight in row.items()
        }
        total = sum(adjusted.values())
        adjusted = {asset: value / total for asset, value in adjusted.items()}
        output[decision] = adjusted
        audit.append({"decision_date": decision, "offense_scale": scale, **signal})
    return output, audit
