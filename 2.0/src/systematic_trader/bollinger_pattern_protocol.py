"""Causal Bollinger-band bottom-W recognition matching repository search order."""

from __future__ import annotations

import statistics
from collections.abc import Sequence


def bollinger_bands(prices: Sequence[float], window: int = 20) -> tuple[list[float | None], list[float | None], list[float | None], list[float | None]]:
    if window < 2 or not prices or any(float(value) <= 0.0 for value in prices):
        raise ValueError("positive prices and window >= 2 required")
    mid, std, upper, lower = [], [], [], []
    for index in range(len(prices)):
        if index + 1 < window:
            mid.append(None); std.append(None); upper.append(None); lower.append(None)
            continue
        values = [float(value) for value in prices[index - window + 1:index + 1]]
        mean, deviation = statistics.fmean(values), statistics.stdev(values)
        mid.append(mean); std.append(deviation); upper.append(mean + 2.0 * deviation); lower.append(mean - 2.0 * deviation)
    return mid, std, upper, lower


def _close_enough(left: float, right: float, alpha: float, normalized: bool) -> bool:
    denominator = max(abs(right), 1e-30) if normalized else 1.0
    return abs(left - right) / denominator < alpha


def find_bottom_w(
    index: int, prices: Sequence[float], mid: Sequence[float | None], upper: Sequence[float | None],
    lower: Sequence[float | None], *, period: int, alpha: float, normalized: bool,
) -> tuple[int, int, int, int, int] | None:
    if index < period or upper[index] is None or not float(prices[index]) > float(upper[index]):
        return None
    boundary = index - period
    found_j = None
    for j in range(index, boundary, -1):
        if mid[j] is not None and _close_enough(float(mid[j]), float(prices[j]), alpha, normalized) and _close_enough(float(mid[j]), float(upper[index]), alpha, normalized):
            found_j = j; break
    if found_j is None:
        return None
    found_k = None
    for k in range(found_j, boundary, -1):
        if lower[k] is not None and _close_enough(float(lower[k]), float(prices[k]), alpha, normalized):
            found_k = k; break
    if found_k is None:
        return None
    found_l = None
    for l in range(found_k, boundary, -1):
        if mid[l] is not None and float(mid[l]) < float(prices[l]):
            found_l = l; break
    if found_l is None:
        return None
    for m in range(index, found_j, -1):
        if lower[m] is None:
            continue
        difference = float(prices[m]) - float(lower[m])
        denominator = max(abs(float(prices[m])), 1e-30) if normalized else 1.0
        if 0.0 < difference / denominator < alpha and float(prices[m]) < float(prices[found_k]):
            return found_l, found_k, found_j, m, index
    return None


def bottom_w_positions(
    prices: Sequence[float], *, period: int = 75, alpha: float = 0.0001,
    beta: float = 0.0001, normalized: bool = False,
) -> tuple[list[bool], list[str], list[tuple[int, int, int, int, int] | None]]:
    mid, std, upper, lower = bollinger_bands(prices)
    positions = [False] * len(prices)
    events = ["warmup"] * len(prices)
    coordinates: list[tuple[int, int, int, int, int] | None] = [None] * len(prices)
    holding = False
    for index in range(period, len(prices)):
        pattern = None if holding else find_bottom_w(index, prices, mid, upper, lower, period=period, alpha=alpha, normalized=normalized)
        if pattern is not None:
            holding = True; events[index] = "entry"; coordinates[index] = pattern
        else:
            contraction = std[index] is not None and (
                float(std[index]) / float(mid[index]) < beta if normalized else float(std[index]) < beta
            )
            if holding and contraction:
                holding = False; events[index] = "exit"
            else:
                events[index] = "hold"
        positions[index] = holding
    return positions, events, coordinates
