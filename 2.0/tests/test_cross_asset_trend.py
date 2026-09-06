from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from systematic_trader.cross_asset_trend import apply_next_week_returns, build_trend_weights


class CrossAssetTrendTests(unittest.TestCase):
    def setUp(self) -> None:
        index = pd.date_range("2020-01-03", periods=90, freq="W-FRI")
        self.prices = pd.DataFrame(
            {
                "A": 100.0 * np.exp(np.arange(90) * 0.01),
                "B": 100.0 * np.exp(np.arange(90) * -0.005),
                "BIL": 100.0 * np.exp(np.arange(90) * 0.0002),
            },
            index=index,
        )

    def test_future_changes_do_not_change_prior_weights(self) -> None:
        original = build_trend_weights(self.prices, ["A", "B"], "BIL", maximum_asset_weight=1.0)
        changed = self.prices.copy()
        changed.loc[changed.index[-10]:, "A"] *= 10.0
        rebuilt = build_trend_weights(changed, ["A", "B"], "BIL", maximum_asset_weight=1.0)
        cutoff = self.prices.index[-11]
        pd.testing.assert_frame_equal(original.loc[:cutoff], rebuilt.loc[:cutoff])

    def test_positive_asset_is_held_and_negative_asset_is_not(self) -> None:
        weights = build_trend_weights(self.prices, ["A", "B"], "BIL", maximum_asset_weight=1.0)
        self.assertGreater(weights.iloc[-1]["A"], 0.99)
        self.assertEqual(weights.iloc[-1]["B"], 0.0)

    def test_decision_weight_receives_next_week_return(self) -> None:
        weights = pd.DataFrame(0.0, index=self.prices.index, columns=["A", "BIL"])
        weights["A"] = 1.0
        path = apply_next_week_returns(self.prices[["A", "BIL"]], weights, 0.0)
        expected = self.prices["A"].iloc[1] / self.prices["A"].iloc[0] - 1.0
        self.assertAlmostEqual(path.iloc[0].net_return, expected)


if __name__ == "__main__":
    unittest.main()
