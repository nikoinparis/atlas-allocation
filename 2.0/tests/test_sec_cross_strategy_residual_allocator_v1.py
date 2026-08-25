from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("allocator", ROOT / "scripts/run_sec_cross_strategy_residual_allocator_v1.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class CrossStrategyResidualAllocatorTests(unittest.TestCase):
    def test_allocator_has_no_lookahead_and_charges_turnover(self) -> None:
        dates = pd.date_range("2025-01-03", periods=4, freq="W-FRI")
        frame = pd.DataFrame({"base": [0.0] * 4, "sleeve": [0.1] * 4}, index=dates)
        targets = pd.Series([0.2, 0.2, 0.0, 0.0], index=dates)
        result = module.apply_allocator(frame, targets, 50.0, delay=1)
        self.assertEqual(result.target_weight.iloc[0], 0.0)
        self.assertEqual(result.target_weight.iloc[1], 0.2)
        self.assertAlmostEqual(result.outer_cost.iloc[1], 0.2 * 50 / 10000)

    def test_causal_signal_ignores_current_return(self) -> None:
        dates = pd.date_range("2024-01-05", periods=70, freq="W-FRI")
        config = {"signal": {"beta_correlation_lookback_weeks": 52, "minimum_history_weeks": 26, "short_residual_momentum_weeks": 13, "long_residual_momentum_weeks": 26, "maximum_correlation": 0.60, "maximum_residual_information_ratio": 2.0}}
        frame = pd.DataFrame({"base": np.linspace(-0.01, 0.02, 70), "sleeve": np.linspace(0.02, -0.01, 70)}, index=dates)
        before = module.causal_signals(frame, config)
        frame.iloc[-1, 1] = 9.0
        after = module.causal_signals(frame, config)
        pd.testing.assert_series_equal(before.iloc[-1], after.iloc[-1])

    def test_expanding_folds_include_purge(self) -> None:
        config = {"selection": {"minimum_training_weeks": 52, "purge_weeks": 4, "validation_weeks": 26, "step_weeks": 26}}
        folds = module.expanding_folds(110, config)
        self.assertEqual(folds[0], (56, 82))
        self.assertEqual(folds[1], (82, 108))

    def test_paired_bootstrap_is_deterministic(self) -> None:
        selected = pd.Series([0.02, 0.01, -0.01] * 20)
        base = pd.Series([0.01, 0.00, -0.02] * 20)
        left = module.paired_block_probability(selected, base, 100, 4, 9)
        right = module.paired_block_probability(selected, base, 100, 4, 9)
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
