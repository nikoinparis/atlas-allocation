"""Independent, dependency-free trade buffering for challenger research.

The implementation uses only the high-level no-trade-band idea. It does not
copy source from any external project. Targets remain long-only and fully
invested because every buffered portfolio is a convex combination of the
previous buffered target and the new unbuffered target.
"""

from __future__ import annotations


def buffered_target(
    previous: dict[str, float] | None,
    target: dict[str, float],
    *,
    no_trade_turnover: float,
) -> tuple[dict[str, float], dict[str, float | bool]]:
    if no_trade_turnover < 0.0 or no_trade_turnover >= 1.0:
        raise ValueError("no_trade_turnover must be in [0, 1)")
    if previous is None:
        return dict(target), {
            "target_turnover": 0.0,
            "realized_turnover": 0.0,
            "buffer_held": False,
            "adjustment_fraction": 1.0,
        }
    assets = set(previous) | set(target)
    target_turnover = 0.5 * sum(
        abs(target.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in assets
    )
    if target_turnover <= no_trade_turnover + 1e-15:
        return dict(previous), {
            "target_turnover": target_turnover,
            "realized_turnover": 0.0,
            "buffer_held": True,
            "adjustment_fraction": 0.0,
        }
    fraction = (target_turnover - no_trade_turnover) / target_turnover
    result = {
        asset: previous.get(asset, 0.0)
        + fraction * (target.get(asset, 0.0) - previous.get(asset, 0.0))
        for asset in assets
    }
    realized_turnover = 0.5 * sum(
        abs(result.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in assets
    )
    return result, {
        "target_turnover": target_turnover,
        "realized_turnover": realized_turnover,
        "buffer_held": False,
        "adjustment_fraction": fraction,
    }


def buffer_history(
    dates: list[str],
    targets: dict[str, dict[str, float]],
    *,
    entry_band: float,
    exit_band: float | None = None,
    cash_asset: str = "cash::USD",
) -> tuple[dict[str, dict[str, float]], list[dict[str, float | str | bool]]]:
    if exit_band is None:
        exit_band = entry_band
    previous: dict[str, float] | None = None
    output: dict[str, dict[str, float]] = {}
    audit: list[dict[str, float | str | bool]] = []
    for decision in dates:
        target = targets[decision]
        if previous is None:
            band = entry_band
            direction = "initial"
        else:
            previous_cash = previous.get(cash_asset, 0.0)
            target_cash = target.get(cash_asset, 0.0)
            direction = "risk_entry" if target_cash < previous_cash else "risk_exit"
            band = entry_band if direction == "risk_entry" else exit_band
        current, details = buffered_target(previous, target, no_trade_turnover=band)
        if abs(sum(current.values()) - 1.0) > 1e-10:
            raise ValueError("buffering must preserve fully invested weights")
        if any(value < -1e-12 for value in current.values()):
            raise ValueError("buffering must preserve long-only weights")
        output[decision] = current
        audit.append({"decision_date": decision, "direction": direction, "band": band, **details})
        previous = current
    return output, audit
