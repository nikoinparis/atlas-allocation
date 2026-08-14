import unittest

from src.systematic_trader.factor_ic_protocol import (
    circular_block_bootstrap_means,
    quantile,
    summarize,
)


class FactorIcProtocolTests(unittest.TestCase):
    def test_quantile_interpolates(self):
        self.assertEqual(quantile([0.0, 10.0], 0.25), 2.5)

    def test_circular_bootstrap_is_seed_deterministic(self):
        first = circular_block_bootstrap_means([1.0, 2.0, 3.0], block_size=2, replicates=10, seed=7)
        second = circular_block_bootstrap_means([1.0, 2.0, 3.0], block_size=2, replicates=10, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 10)

    def test_constant_sample_remains_constant(self):
        values = circular_block_bootstrap_means([0.2] * 8, block_size=3, replicates=20, seed=9)
        self.assertTrue(all(abs(value - 0.2) < 1e-12 for value in values))

    def test_summary(self):
        row = summarize([-1.0, 1.0, 2.0])
        self.assertEqual(row["observations"], 3)
        self.assertAlmostEqual(row["mean_ic"], 2.0 / 3.0)
        self.assertAlmostEqual(row["positive_rate"], 2.0 / 3.0)


if __name__ == "__main__":
    unittest.main()
