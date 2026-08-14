"""Safety boundary for bt research signals.

bt can transact on the same timestamp whose close generated a signal. The
platform therefore lags every signal before it reaches a bt strategy and keeps
actual execution in the platform-owned broker simulator.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypeVar


T = TypeVar("T")


def lag_signals_one_bar(signals: Sequence[Mapping[str, T]], *, inactive: T) -> list[dict[str, T]]:
    if not signals:
        return []
    symbols = set().union(*(row.keys() for row in signals))
    lagged: list[dict[str, T]] = [{symbol: inactive for symbol in symbols}]
    for previous in signals[:-1]:
        lagged.append({symbol: previous.get(symbol, inactive) for symbol in symbols})
    return lagged
