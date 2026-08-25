from __future__ import annotations

import pandas as pd

from scripts.run_indonesia_multihorizon_momentum_challenger_v1 import (
    medium_momentum_26w_skip_4w,
)


def test_medium_momentum_ignores_decision_and_future_prices() -> None:
    dates = pd.date_range("2023-01-06", periods=32, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "local_ticker": "AAAA",
            "observation_date": dates,
            "adjusted_close": [float(value) for value in range(100, 132)],
        }
    )
    decision = pd.Timestamp(dates[-1]).tz_localize("UTC")
    original = medium_momentum_26w_skip_4w(prices, ["AAAA"], decision)
    changed = prices.copy()
    changed.loc[changed["observation_date"] >= dates[-1], "adjusted_close"] = 1.0
    revised = medium_momentum_26w_skip_4w(changed, ["AAAA"], decision)
    assert original == revised
    assert original["AAAA"] == (126.0 / 100.0 - 1.0)
