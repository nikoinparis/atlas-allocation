from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("survival_lab", ROOT / "scripts/run_dashboard_strategy_survival_lab_v2.py")
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class DashboardStrategySurvivalLabTests(unittest.TestCase):
    def test_statistics_compound_and_drawdown(self) -> None:
        result = module.statistics(np.array([0.10, -0.10, 0.05]), periods=3)
        self.assertAlmostEqual(result["total_return"], 1.10 * 0.90 * 1.05 - 1.0)
        self.assertLess(result["max_drawdown"], 0.0)

    def test_block_bootstrap_is_deterministic_and_shaped(self) -> None:
        returns = np.array([0.01, -0.02, 0.03, 0.00, 0.02])
        left = module.moving_block_paths(returns, 100, 52, 4, 7)
        right = module.moving_block_paths(returns, 100, 52, 4, 7)
        self.assertEqual(left.shape, (100, 52))
        np.testing.assert_array_equal(left, right)

    def test_monte_carlo_summary_known_constant_path(self) -> None:
        paths = np.full((10, 52), 0.01)
        result = module.monte_carlo_summary(paths)
        self.assertEqual(result["probability_of_profit"], 1.0)
        self.assertEqual(result["probability_drawdown_over_30pct"], 0.0)

    def test_rolling_windows_use_native_observations(self) -> None:
        returns = np.full(60, 0.001)
        result = module.rolling_year_metrics(returns, 52)
        self.assertEqual(result["windows"], 9)
        self.assertEqual(result["positive_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
