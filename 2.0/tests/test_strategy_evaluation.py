import math
import unittest

from src.systematic_trader.evaluation import (
    benchmark_regression,
    block_bootstrap_intervals,
    performance_metrics,
    rolling_window_summary,
)


class StrategyEvaluationTests(unittest.TestCase):
    def test_constant_growth_has_expected_compounding_and_no_drawdown(self):
        returns = [0.01] * 52
        result = performance_metrics(returns)
        self.assertAlmostEqual((1.01**52) - 1.0, result.annual_return)
        self.assertEqual(0.0, result.max_drawdown)
        self.assertEqual(0, result.max_drawdown_duration_weeks)

    def test_drawdown_and_tail_metrics_use_period_returns(self):
        result = performance_metrics([0.10, -0.20, 0.05, -0.01])
        self.assertAlmostEqual(-0.20, result.max_drawdown)
        self.assertEqual(-0.20, result.cvar_5_weekly)
        self.assertTrue(math.isfinite(result.sharpe_zero_rf))

    def test_benchmark_regression_identifies_exact_double_beta(self):
        benchmark = [-0.02, -0.01, 0.01, 0.02, 0.03]
        strategy = [2 * value for value in benchmark]
        result = benchmark_regression(strategy, benchmark)
        self.assertAlmostEqual(2.0, result["beta_to_spy"])
        self.assertAlmostEqual(0.0, result["annual_alpha_zero_rf"])

    def test_bootstrap_is_deterministic_and_rolling_windows_are_counted(self):
        returns = [0.002, -0.001, 0.003, 0.0] * 50
        first = block_bootstrap_intervals(returns, seed=7, samples=20, block_size=4)
        second = block_bootstrap_intervals(returns, seed=7, samples=20, block_size=4)
        self.assertEqual(first, second)
        rolling = rolling_window_summary(returns, [0.0] * len(returns), window=52)
        self.assertEqual(149, rolling["rolling_windows"])

    def test_nonfinite_and_total_loss_returns_are_rejected(self):
        for values in ([float("nan")], [float("inf")], [-1.0]):
            with self.assertRaises(ValueError):
                performance_metrics(values)


if __name__ == "__main__":
    unittest.main()
