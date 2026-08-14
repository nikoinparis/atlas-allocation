"""Pure Heikin-Ashi transformation, state, and safe unit weighting."""

from __future__ import annotations

from collections.abc import Sequence


def heikin_ashi_bars(bars: Sequence[dict[str, float]]) -> list[dict[str, float]]:
    if not bars:
        raise ValueError("at least one bar is required")
    result = []
    previous_open = previous_close = 0.0
    for index, bar in enumerate(bars):
        values = [float(bar[key]) for key in ("open", "high", "low", "close")]
        scale = max(values)
        tolerance = 1e-12 * scale
        if min(values) <= 0.0 or values[1] + tolerance < max(values[0], values[3]) or values[2] - tolerance > min(values[0], values[3]):
            raise ValueError("invalid positive OHLC bar")
        close = sum(values) / 4.0
        open_ = values[0] if index == 0 else (previous_open + previous_close) / 2.0
        result.append({"open": open_, "close": close, "high": max(values[1], open_, close), "low": min(values[2], open_, close)})
        previous_open, previous_close = open_, close
    return result


def no_upper_wick(bar: dict[str, float], tolerance: float = 1e-12) -> bool:
    scale = max(abs(bar["high"]), 1.0)
    return abs(bar["high"] - max(bar["open"], bar["close"])) <= tolerance * scale


def no_lower_wick(bar: dict[str, float], tolerance: float = 1e-12) -> bool:
    scale = max(abs(bar["low"]), 1.0)
    return abs(bar["low"] - min(bar["open"], bar["close"])) <= tolerance * scale


def update_state(previous: dict[str, float], current: dict[str, float], units: int, *, corrected: bool, maximum_units: int = 3) -> tuple[int, str]:
    if not 0 <= units <= maximum_units:
        raise ValueError("units outside fixed limit")
    previous_bullish = previous["close"] > previous["open"]
    current_bullish = current["close"] > current["open"]
    body_growing = abs(current["close"] - current["open"]) > abs(previous["close"] - previous["open"])
    bullish_entry = previous_bullish and current_bullish and no_lower_wick(current) and body_growing
    bearish_entry = not previous_bullish and not current_bullish and no_upper_wick(current) and body_growing
    bullish_exit = previous_bullish and current_bullish and no_lower_wick(current)
    bearish_exit = not previous_bullish and not current_bullish and no_upper_wick(current)
    entry, exit_ = (bullish_entry, bearish_exit) if corrected else (bearish_entry, bullish_exit)
    if entry and units < maximum_units:
        return units + 1, "entry"
    if exit_ and units > 0:
        return 0, "exit_all"
    return units, "hold"


def capped_unit_weights(states: dict[str, int], assets: Sequence[str], cap: float = 0.2) -> dict[str, float]:
    if not 0.0 < cap <= 1.0 or any(states.get(asset, 0) < 0 for asset in assets):
        raise ValueError("invalid cap or state")
    total = sum(states.get(asset, 0) for asset in assets)
    weights = {asset: min(cap, states.get(asset, 0) / total) if total else 0.0 for asset in assets}
    weights["cash::USD"] = 1.0 - sum(weights.values())
    return weights
