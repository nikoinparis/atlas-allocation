"""Dependency-free accounting and state rules for causal long-short pairs."""

from __future__ import annotations


def update_pair_state(state: int, z_score: float, *, invert: bool = False) -> tuple[int, bool]:
    """Apply fixed entry, exit, and relationship-break rules."""
    if abs(z_score) >= 4.0:
        return 0, True
    if state == 0:
        if z_score >= 2.0:
            state = -1
        elif z_score <= -2.0:
            state = 1
        if invert:
            state = -state
    elif abs(z_score) <= 0.5:
        state = 0
    return state, False


def long_short_turnover(previous: dict[str, float], target: dict[str, float]) -> float:
    """Return total traded notional, without the long-only half-L1 convention."""
    return sum(abs(target.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in set(previous) | set(target))


def frictional_pair_return(
    gross_return: float, turnover: float, short_exposure: float,
    *, cost_bps: float, annual_borrow_fee: float, periods_per_year: int = 252,
) -> float:
    return gross_return - turnover * cost_bps / 10_000.0 - short_exposure * annual_borrow_fee / periods_per_year
