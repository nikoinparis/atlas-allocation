import unittest

import numpy as np
import pandas as pd

from scripts.run_sec_independent_sleeve_return_accelerator_v1 import (
    causal_allocator,
    exposure_multiplier,
    parameter_grid,
    split_index,
)


class SECIndependentSleeveReturnAcceleratorTests(unittest.TestCase):
    def test_allocator_is_prefix_invariant(self):
        index = pd.date_range("2020-01-03", periods=80, freq="W-FRI", tz="UTC")
        control = pd.Series(np.linspace(-0.01, 0.01, len(index)), index=index)
        sleeves = pd.DataFrame({"a": control + 0.005, "b": control - 0.002}, index=index)
        original, weights = causal_allocator(sleeves, control, lookback=13, top_k=1, low_allocation=0.1, high_allocation=0.3, cost_bps=50)
        changed = sleeves.copy()
        changed.iloc[-1] = 100.0
        altered, altered_weights = causal_allocator(changed, control, lookback=13, top_k=1, low_allocation=0.1, high_allocation=0.3, cost_bps=50)
        pd.testing.assert_series_equal(original.iloc[:-1], altered.iloc[:-1])
        pd.testing.assert_frame_equal(weights.iloc[:-1], altered_weights.iloc[:-1])

    def test_exposure_uses_only_prior_volatility(self):
        index = pd.date_range("2020-01-03", periods=30, freq="W-FRI", tz="UTC")
        base = pd.Series(np.linspace(-0.02, 0.02, len(index)), index=index)
        first = exposure_multiplier(base, volatility_target=0.35, maximum_leverage=1.5, lookback=13, minimum_exposure=0.5)
        changed = base.copy()
        changed.iloc[-1] = 2.0
        second = exposure_multiplier(changed, volatility_target=0.35, maximum_leverage=1.5, lookback=13, minimum_exposure=0.5)
        pd.testing.assert_series_equal(first, second)

    def test_split_has_one_locked_52_week_block(self):
        index = pd.date_range("2020-01-03", periods=188, freq="W-FRI", tz="UTC")
        config = {"development_weeks": 84, "validation_weeks": 52, "locked_test_weeks": 52}
        splits = split_index(index, config)
        self.assertEqual(84, len(splits["development"]))
        self.assertEqual(52, len(splits["validation"]))
        self.assertEqual(52, len(splits["locked_test"]))
        self.assertLess(splits["development"].max(), splits["validation"].min())
        self.assertLess(splits["validation"].max(), splits["locked_test"].min())

    def test_grid_is_finite_and_contains_no_unbounded_leverage(self):
        config = {
            "allocator_grid": {
                "lookback_weeks": [13, 26, 52],
                "top_k_sleeves": [1, 2, 3],
                "low_alpha_allocations": [0.1, 0.2],
                "high_alpha_allocations": [0.2, 0.3, 0.4],
                "volatility_targets": [None, 0.35, 0.5],
                "maximum_leverage": [1.0, 1.25, 1.5],
            }
        }
        grid = parameter_grid(config)
        self.assertEqual(378, len(grid))
        self.assertLessEqual(max(row["maximum_leverage"] for row in grid), 1.5)


if __name__ == "__main__":
    unittest.main()
