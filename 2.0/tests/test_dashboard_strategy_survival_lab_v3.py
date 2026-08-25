from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("survival_lab", ROOT / "scripts/run_dashboard_strategy_survival_lab_v3.py")
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



class MonteCarloDistributionTests(unittest.TestCase):
    """v3 additions: the exported Monte Carlo distributions."""

    def test_histogram_bins_cover_every_observation(self) -> None:
        values = np.array([-0.5, -0.1, 0.0, 0.2, 0.9, 1.4])
        report = module.histogram(values, bins=8)
        self.assertEqual(len(report["edges"]), len(report["counts"]) + 1)
        self.assertEqual(sum(report["counts"]), len(values))
        self.assertLessEqual(report["edges"][0], float(values.min()))
        self.assertGreaterEqual(report["edges"][-1], float(values.max()))

    def test_curve_bands_are_monotone_across_percentiles(self) -> None:
        rng = np.random.default_rng(3)
        wealth = np.cumprod(1.0 + rng.normal(0.004, 0.02, (500, 52)), axis=1)
        bands = module.curve_bands(wealth)
        self.assertEqual(bands["week"], list(range(1, 53)))
        for week in range(52):
            self.assertLessEqual(bands["p05"][week], bands["p25"][week])
            self.assertLessEqual(bands["p25"][week], bands["p50"][week])
            self.assertLessEqual(bands["p50"][week], bands["p75"][week])
            self.assertLessEqual(bands["p75"][week], bands["p95"][week])

    def test_sample_curves_are_deterministic_and_shaped(self) -> None:
        rng = np.random.default_rng(4)
        wealth = np.cumprod(1.0 + rng.normal(0.004, 0.02, (300, 52)), axis=1)
        first = module.sample_curves(wealth, 24, seed=99)
        second = module.sample_curves(wealth, 24, seed=99)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 24)
        self.assertTrue(all(len(curve) == 52 for curve in first))

    def test_distributions_only_attach_when_requested(self) -> None:
        rng = np.random.default_rng(5)
        paths = rng.normal(0.004, 0.02, (400, 52))
        plain = module.monte_carlo_summary(paths)
        rich = module.monte_carlo_summary(paths, distributions=True, seed=7)
        self.assertNotIn("return_histogram", plain)
        self.assertIn("return_histogram", rich)
        for key in ("probability_of_profit", "median_return", "p05_return"):
            self.assertEqual(plain[key], rich[key])

    def test_distribution_payload_is_json_safe(self) -> None:
        rng = np.random.default_rng(6)
        paths = rng.normal(0.004, 0.02, (400, 52))
        rich = module.monte_carlo_summary(paths, distributions=True, seed=7)
        self.assertGreater(len(json.dumps(rich, allow_nan=False)), 0)


if __name__ == "__main__":
    unittest.main()
