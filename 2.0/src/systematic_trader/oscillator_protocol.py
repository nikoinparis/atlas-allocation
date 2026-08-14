"""Causal, dependency-free oscillator calculations and long-only accounting."""

from __future__ import annotations

import random
from collections.abc import Sequence


def adjusted_bar(open_: float, high: float, low: float, close: float, adjusted_close: float) -> dict[str, float]:
    if close <= 0.0 or min(open_, high, low, adjusted_close) <= 0.0:
        raise ValueError("OHLC and adjusted close must be positive")
    factor = adjusted_close / close
    return {
        "open": open_ * factor,
        "high": high * factor,
        "low": low * factor,
        "close": adjusted_close,
        "median": (high + low) * 0.5 * factor,
    }


def rolling_mean(values: Sequence[float], window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[float | None] = []
    running = 0.0
    for index, value in enumerate(values):
        running += float(value)
        if index >= window:
            running -= float(values[index - window])
        result.append(running / window if index + 1 >= window else None)
    return result


def ewm_adjust_true(values: Sequence[float], span: int) -> list[float]:
    """Match pandas ewm(span=span, adjust=True).mean() for finite values."""
    if span <= 0 or not values:
        raise ValueError("span and values must be non-empty and positive")
    alpha = 2.0 / (span + 1.0)
    decay = 1.0 - alpha
    numerator = 0.0
    denominator = 0.0
    result = []
    for value in values:
        numerator = float(value) + decay * numerator
        denominator = 1.0 + decay * denominator
        result.append(numerator / denominator)
    return result


def capped_equal_weights(active: Sequence[str], assets: Sequence[str], cap: float = 0.2) -> dict[str, float]:
    if not 0.0 < cap <= 1.0:
        raise ValueError("cap must be in (0, 1]")
    active_set = set(active)
    eligible = [asset for asset in assets if asset in active_set]
    weight = min(cap, 1.0 / len(eligible)) if eligible else 0.0
    result = {asset: weight if asset in active_set else 0.0 for asset in assets}
    result["cash::USD"] = 1.0 - sum(result.values())
    return result


def long_only_turnover(previous: dict[str, float], target: dict[str, float]) -> float:
    names = set(previous) | set(target)
    return 0.5 * sum(abs(target.get(name, 0.0) - previous.get(name, 0.0)) for name in names)


def deterministic_matched_active(assets: Sequence[str], count: int, decision_date: str, seed: int) -> list[str]:
    if not 0 <= count <= len(assets):
        raise ValueError("count outside asset universe")
    generator = random.Random(f"{seed}:{decision_date}")
    return sorted(generator.sample(list(assets), count))
