from __future__ import annotations

import pandas as pd

from scripts.run_indonesia_dynamic_breadth_challenger_v1 import (
    breadth_state,
    scale_to_stock_allocation,
)


def test_scale_to_stock_allocation_preserves_relative_weights_and_adds_cash() -> None:
    result = scale_to_stock_allocation({"AAAA": 0.6, "BBBB": 0.4}, 0.25)
    assert result == {"AAAA": 0.15, "BBBB": 0.10, "CASH_IDR": 0.75}


def test_breadth_state_uses_only_prices_before_decision() -> None:
    dates = pd.date_range("2023-01-06", periods=44, freq="W-FRI")
    frames = []
    for ticker in ("AAAA", "BBBB"):
        values = [float(value) for value in range(1, 45)]
        frames.append(
            pd.DataFrame(
                {
                    "local_ticker": ticker,
                    "observation_date": dates,
                    "adjusted_close": values,
                }
            )
        )
    prices = pd.concat(frames, ignore_index=True)
    tiers = [
        {"minimum_breadth_inclusive": 0.60, "stock_allocation": 1.0, "state": "broad"},
        {"minimum_breadth_inclusive": 0.40, "stock_allocation": 0.6, "state": "mixed"},
        {"minimum_breadth_inclusive": 0.00, "stock_allocation": 0.25, "state": "weak"},
    ]
    decision = pd.Timestamp(dates[-1]).tz_localize("UTC")
    original = breadth_state(prices, ["AAAA", "BBBB"], decision, tiers, 2)
    shocked = prices.copy()
    shocked.loc[shocked["observation_date"] >= dates[-1], "adjusted_close"] = 0.01
    revised = breadth_state(shocked, ["AAAA", "BBBB"], decision, tiers, 2)
    assert original == revised
    assert original[1:3] == (1.0, "broad")
