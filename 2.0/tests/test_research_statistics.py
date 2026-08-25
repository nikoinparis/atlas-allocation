import math
import unittest

from src.systematic_trader.evaluation import block_bootstrap_intervals
from src.systematic_trader.research_statistics import (
    deflated_sharpe_ratio,
    information_coefficient_ratio,
    probability_of_backtest_overfitting,
    probabilistic_sharpe_ratio,
    white_reality_check_pvalue,
)


class ResearchStatisticsTests(unittest.TestCase):
    def test_icir_matches_definition_and_optional_annualization(self):
        result = information_coefficient_ratio([0.01, 0.03, 0.05], periods_per_year=12)
        self.assertAlmostEqual(result["mean_ic"], 0.03)
        self.assertAlmostEqual(result["ic_std"], 0.02)
        self.assertAlmostEqual(result["icir"], 1.5)
        self.assertAlmostEqual(result["annualized_icir"], 1.5 * math.sqrt(12))

    def test_probabilistic_and_deflated_sharpe_penalize_trials(self):
        returns = [0.02, 0.01, -0.005, 0.015] * 20
        raw = probabilistic_sharpe_ratio(returns)
        one = deflated_sharpe_ratio(returns, trial_sharpes=[0.1])
        many = deflated_sharpe_ratio(returns, trial_sharpes=[-0.5, 0.0, 0.5, 1.0, 1.5])
        self.assertAlmostEqual(raw, one["deflated_sharpe_probability"])
        self.assertLess(many["deflated_sharpe_probability"], raw)

    def test_pbo_detects_in_sample_rotation(self):
        trials = []
        for winner_fold in range(4):
            row = []
            for fold in range(4):
                row.extend(([0.04, 0.03, 0.02, 0.01] if fold == winner_fold else [-0.02, -0.01, 0.0, 0.0]))
            trials.append(row)
        result = probability_of_backtest_overfitting(trials, folds=4)
        self.assertGreaterEqual(result["pbo"], 0.5)
        self.assertEqual(result["splits"], 3)

    def test_reality_check_is_deterministic_and_penalizes_noise(self):
        trials = [
            [0.01, -0.01] * 20,
            [0.005, -0.005] * 20,
            [0.0] * 40,
        ]
        first = white_reality_check_pvalue(trials, block_size=4, replicates=200, seed=7)
        second = white_reality_check_pvalue(trials, block_size=4, replicates=200, seed=7)
        self.assertEqual(first, second)
        self.assertGreater(first["pvalue"], 0.05)

    def test_invalid_ic_values_fail_closed(self):
        with self.assertRaises(ValueError):
            information_coefficient_ratio([0.1, math.nan])

    def test_monthly_bootstrap_uses_monthly_annualization(self):
        monthly = block_bootstrap_intervals(
            [0.01, -0.005] * 24, seed=3, samples=50, block_size=3, periods_per_year=12
        )
        self.assertEqual(monthly["periods_per_year"], 12)
        self.assertEqual(monthly["bootstrap_block_periods"], 3)
        self.assertNotIn("bootstrap_block_weeks", monthly)


if __name__ == "__main__":
    unittest.main()
