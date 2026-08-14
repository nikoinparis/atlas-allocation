"""Causal shooting-star detection and close-based short-position state."""

from __future__ import annotations

from collections.abc import Sequence


def _validated_bars(bars: Sequence[dict[str, float]]) -> list[dict[str, float]]:
    if len(bars) < 3:
        raise ValueError("at least three OHLC bars are required")
    result = []
    for bar in bars:
        row = {key: float(bar[key]) for key in ("open", "high", "low", "close")}
        tolerance = max(row.values()) * 1e-12
        if min(row.values()) <= 0.0 or row["high"] + tolerance < max(row["open"], row["close"]) or row["low"] - tolerance > min(row["open"], row["close"]):
            raise ValueError("invalid positive OHLC bar")
        result.append(row)
    return result


def shooting_star_shapes(
    bars: Sequence[dict[str, float]], *, body_mode: str,
    lower_bound: float = 0.2, body_size: float = 0.5,
) -> tuple[list[bool], list[dict[str, float | int]]]:
    """Return causal six-condition star shapes and per-bar diagnostics."""
    rows = _validated_bars(bars)
    if body_mode not in {"source_signed_expanding", "normalized_absolute_expanding"}:
        raise ValueError("unknown body reference mode")
    if lower_bound <= 0.0 or body_size <= 0.0:
        raise ValueError("positive shape parameters required")
    signed_total = absolute_fraction_total = 0.0
    shapes: list[bool] = []
    diagnostics: list[dict[str, float | int]] = []
    for index, row in enumerate(rows):
        signed_body = row["open"] - row["close"]
        absolute_body = abs(signed_body)
        signed_total += signed_body
        absolute_fraction_total += absolute_body / row["close"]
        if body_mode == "source_signed_expanding":
            observed_body = absolute_body
            reference = abs(signed_total / (index + 1)) * body_size
        else:
            observed_body = absolute_body / row["close"]
            reference = absolute_fraction_total / (index + 1) * body_size
        lower_wick = min(row["open"], row["close"]) - row["low"]
        upper_wick = row["high"] - max(row["open"], row["close"])
        conditions = [
            signed_body >= 0.0,
            lower_wick < lower_bound * absolute_body,
            observed_body < reference,
            upper_wick >= 2.0 * absolute_body,
            index >= 1 and row["close"] >= rows[index - 1]["close"],
            index >= 2 and rows[index - 1]["close"] >= rows[index - 2]["close"],
        ]
        shapes.append(all(conditions))
        diagnostics.append({
            "index": index, "condition_count": sum(conditions), "body": absolute_body,
            "body_observation": observed_body, "body_reference": reference,
            "lower_wick": lower_wick, "upper_wick": upper_wick,
        })
    return shapes, diagnostics


def shooting_star_short_states(
    bars: Sequence[dict[str, float]], *, body_mode: str, require_confirmation: bool,
    lower_bound: float = 0.2, body_size: float = 0.5,
    stop_threshold: float = 0.05, holding_period: int = 7,
) -> tuple[list[int], list[str], list[int | None], list[dict[str, float | int]]]:
    """Create a causal flat/short state observed at each completed close."""
    rows = _validated_bars(bars)
    if stop_threshold <= 0.0 or holding_period < 1:
        raise ValueError("invalid exit parameters")
    shapes, diagnostics = shooting_star_shapes(
        rows, body_mode=body_mode, lower_bound=lower_bound, body_size=body_size,
    )
    states, events, star_indices = [0] * len(rows), ["flat"] * len(rows), [None] * len(rows)
    active_star: int | None = None
    for index, row in enumerate(rows):
        if active_star is not None:
            elapsed = index - active_star
            moved = abs(row["close"] / rows[active_star]["close"] - 1.0) > stop_threshold
            if moved or elapsed >= holding_period:
                events[index] = "exit_stop" if moved else "exit_time"
                active_star = None
            else:
                events[index] = "hold_short"
        if active_star is None:
            candidate = index - 1 if require_confirmation else index
            detected = candidate >= 0 and shapes[candidate]
            if detected and require_confirmation:
                detected = row["high"] <= rows[candidate]["high"] and row["close"] <= rows[candidate]["close"]
                if detected and abs(row["close"] / rows[candidate]["close"] - 1.0) > stop_threshold:
                    detected = False
                    events[index] = "confirmation_stop_collision"
            if detected:
                active_star = candidate
                events[index] = "short_entry_confirmed" if require_confirmation else "short_entry"
        if active_star is not None:
            states[index] = -1
            star_indices[index] = active_star
    return states, events, star_indices, diagnostics
