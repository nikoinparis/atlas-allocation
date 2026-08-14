import unittest

from src.systematic_trader.monte_carlo_risk import (
    path_statistics,
    simulate_paths,
    source_best_fit_direction,
    summarize_simulations,
    wilson_lower,
    worst_compounded_block,
)


class MonteCarloRiskTests(unittest.TestCase):
    def test_path_statistics_compound_and_drawdown(self):
        row = path_statistics([0.10, -0.20, 0.05])
        self.assertAlmostEqual(row["terminal_return"], 1.10 * 0.80 * 1.05 - 1.0)
        self.assertAlmostEqual(row["max_drawdown"], -0.20)

    def test_worst_block_uses_compounded_return(self):
        start, block, value = worst_compounded_block([0.1, -0.2, -0.2, 0.1], 2)
        self.assertEqual(start, 1)
        self.assertEqual(block, [-0.2, -0.2])
        self.assertAlmostEqual(value, -0.36)

    def test_simulation_is_seed_deterministic(self):
        first = simulate_paths([0.01, -0.02, 0.03], weeks=8, paths=20, method="moving_block_13w", seed=7, block_weeks=2)
        second = simulate_paths([0.01, -0.02, 0.03], weeks=8, paths=20, method="moving_block_13w", seed=7, block_weeks=2)
        self.assertEqual(first, second)
        self.assertEqual(summarize_simulations(first), summarize_simulations(second))

    def test_forced_crash_reports_recovery(self):
        rows = simulate_paths([0.10, 0.10], weeks=3, paths=2, method="forced_worst_13w_then_blocks", seed=3, block_weeks=1, forced_initial_block=[-0.10])
        self.assertTrue(all(row["recovered_initial_wealth"] for row in rows))

    def test_best_fit_diagnostic_never_reads_test_for_estimation(self):
        first = source_best_fit_direction([0.01, -0.01, 0.02], [0.03], simulations=10, seed=4)
        second = source_best_fit_direction([0.01, -0.01, 0.02], [-0.03], simulations=10, seed=4)
        self.assertEqual(first["predicted_return"], second["predicted_return"])
        self.assertNotEqual(first["realized_return"], second["realized_return"])

    def test_wilson_lower_is_conservative(self):
        self.assertLess(wilson_lower(6, 10), 0.6)
        self.assertGreaterEqual(wilson_lower(10, 10), 0.7)


if __name__ == "__main__":
    unittest.main()
