import unittest

from src.systematic_trader.cross_sectional_factors import (
    asset_features,
    capped_inverse_volatility_weights,
    fixed_composite_scores,
    minimum_allowed_asof,
    percentile_ranks,
)


class CrossSectionalFactorTests(unittest.TestCase):
    def test_feature_asof_and_skip_momentum_are_causal(self):
        prices = [100.0 + index for index in range(60)]
        result = asset_features(prices, asof_date="2026-01-02")
        self.assertEqual("2026-01-02", result["feature_asof_date"])
        self.assertAlmostEqual(prices[-5] / prices[-53] - 1.0, result["momentum_52w_skip_4w"])
        self.assertEqual("2026-01-02", minimum_allowed_asof("2026-01-09"))

    def test_percentile_ranks_are_centered_and_ties_match(self):
        ranks = percentile_ranks({"A": 1.0, "B": 2.0, "C": 2.0, "D": 4.0})
        self.assertAlmostEqual(0.0, sum(ranks.values()))
        self.assertEqual(ranks["B"], ranks["C"])

    def test_fixed_composite_uses_cross_sectional_ranks(self):
        rows = [
            {"asset": "A", "momentum": 1.0, "volatility": 3.0},
            {"asset": "B", "momentum": 2.0, "volatility": 2.0},
            {"asset": "C", "momentum": 3.0, "volatility": 1.0},
        ]
        scores = fixed_composite_scores(rows, {"momentum": 0.5, "volatility": -0.5})
        self.assertGreater(scores["C"], scores["A"])

    def test_inverse_volatility_weights_are_capped_and_invested(self):
        weights = capped_inverse_volatility_weights(
            ["A", "B", "C", "D"], {"A": 0.01, "B": 0.1, "C": 0.1, "D": 0.1}, 0.35
        )
        self.assertAlmostEqual(1.0, sum(weights.values()))
        self.assertLessEqual(max(weights.values()), 0.35 + 1e-12)


if __name__ == "__main__":
    unittest.main()
