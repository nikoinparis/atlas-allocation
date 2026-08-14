"""Causal reproduction of repository RSI and its seven-node pattern state."""

from __future__ import annotations

from collections.abc import Sequence


def repository_rsi(prices: Sequence[float], lag: int = 14) -> list[float | None]:
    if lag <= 0 or len(prices) <= lag or any(float(value) <= 0 for value in prices):
        raise ValueError("positive price history longer than lag required")
    changes = [float(prices[index]) - float(prices[index - 1]) for index in range(1, len(prices))]
    up = [max(value, 0.0) for value in changes]
    down = [max(-value, 0.0) for value in changes]
    average_up, average_down = up[0], down[0]
    raw: list[float | None] = []
    for index in range(len(changes)):
        if index:
            average_up = (average_up * (lag - 1) + up[index]) / lag
            average_down = (average_down * (lag - 1) + down[index]) / lag
        if average_down == 0.0:
            value = 100.0 if average_up > 0.0 else None
        else:
            value = 100.0 - 100.0 / (1.0 + average_up / average_down)
        raw.append(value)
    return [None] * lag + raw[lag - 1:]


def threshold_states(rsi: Sequence[float | None], *, long_only: bool) -> list[int]:
    result = []
    for value in rsi:
        if value is not None and value < 30.0:
            result.append(1)
        elif not long_only and value is not None and value > 70.0:
            result.append(-1)
        else:
            result.append(0)
    return result


def _pattern_at(index: int, series: Sequence[float | None], *, period: int = 25, delta: float = .2) -> tuple[int, int, int, int, int, int, int] | None:
    if index < period or series[index] is None:
        return None
    window = series[index - period:index]
    if any(value is None for value in window):
        return None
    current = float(series[index])
    values = [float(value) for value in window]
    if current == max(values):
        return None
    j = index - period + values.index(max(values))
    if abs(float(series[j]) - current) <= 1.1 * delta:
        return None
    bottom = current
    k = next((node for node in range(j, index) if abs(float(series[node]) - bottom) < delta), None)
    if k is None:
        return None
    l = next((node for node in range(j, index - period, -1) if abs(float(series[node]) - bottom) < delta), None)
    if l is None:
        return None
    m = next((node for node in range(index - period, l) if abs(float(series[node]) - bottom) < delta), None)
    if m is None or m >= l:
        return None
    shoulder_window = [float(series[node]) for node in range(m, l)]
    if not shoulder_window:
        return None
    n = m + shoulder_window.index(max(shoulder_window))
    top = float(series[n])
    if top - bottom <= 1.1 * delta or float(series[j]) - top <= 1.1 * delta:
        return None
    o = next((node for node in range(k, index) if abs(float(series[node]) - top) < delta), None)
    return (m, n, l, j, k, o, index) if o is not None else None


def head_shoulders_short_states(
    prices: Sequence[float], rsi: Sequence[float | None], *, use_rsi_nodes: bool,
    period: int = 25, delta: float = .2, exit_rsi: float = 4.0, exit_days: int = 5,
) -> tuple[list[int], list[str], list[tuple[int, int, int, int, int, int, int] | None]]:
    if len(prices) != len(rsi):
        raise ValueError("prices and RSI must align")
    series: list[float | None] = list(rsi) if use_rsi_nodes else [float(value) for value in prices]
    states, events, coordinates = [0] * len(prices), ["warmup"] * len(prices), [None] * len(prices)
    holding = False; entry_value: float | None = None; counter = 0
    for index in range(period + 14, len(prices)):
        pattern = None if holding else _pattern_at(index, series, period=period, delta=delta)
        if pattern is not None:
            holding = True; entry_value = rsi[index]; counter = 0
            events[index] = "short_entry"; coordinates[index] = pattern
        elif holding and entry_value is not None:
            counter += 1
            if (rsi[index] is not None and rsi[index] - entry_value > exit_rsi) or counter > exit_days:
                holding = False; entry_value = None; counter = 0; events[index] = "exit"
            else:
                events[index] = "hold_short"
        else:
            events[index] = "flat"
        states[index] = -1 if holding else 0
    return states, events, coordinates
