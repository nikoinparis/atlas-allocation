"""Quote and output guards for the optional FlashAlpha fill component."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from typing import Any

from systematic_trader.execution import quote_is_valid


@dataclass(frozen=True)
class SafeFillResult:
    status: str
    third_party_result: Any | None
    reason: str = ""


def simulate_flashalpha_safely(
    *,
    bar_ts: datetime,
    chain: Mapping[tuple[date, float], tuple[float, float]],
    candidates: Sequence[Any],
    config: Any = None,
    simulator: Callable[..., Any] | None = None,
    max_relative_spread: float = 0.50,
) -> SafeFillResult:
    for key, quote in chain.items():
        if len(quote) != 2 or not quote_is_valid(quote[0], quote[1], max_relative_spread=max_relative_spread):
            return SafeFillResult("rejected", None, f"invalid_quote:{key}")

    if simulator is None:
        from fillsim import simulate_fill as simulator  # type: ignore[import-not-found]

    kwargs = {"bar_ts": bar_ts, "chain": chain, "candidates": candidates}
    if config is not None:
        kwargs["config"] = config
    result = simulator(**kwargs)
    fill = getattr(result, "fill", None)
    if fill is not None:
        diagnostics = (
            getattr(fill, "fill_price", None),
            getattr(fill, "mid_at_fill", None),
            getattr(fill, "edge_captured", None),
        )
        if not all(isinstance(value, (int, float)) and isfinite(value) for value in diagnostics):
            return SafeFillResult("rejected", None, "nonfinite_fill_diagnostics")
    return SafeFillResult("evaluated", result)
