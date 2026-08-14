import unittest

from src.systematic_trader.point_in_time import CASH_ASSET
from src.systematic_trader.strategy_allocation import (
    allocate_two_sleeves,
    cap_non_cash_weights,
    combine_dynamic_weight_histories,
    portfolio_variance,
    safe_allocate_two_sleeves,
    shrunk_covariance,
)


class StrategyAllocationTests(unittest.TestCase):
    def test_covariance_shrinkage_and_allocators(self):
        observations = {"trend": [0.01, -0.02, 0.03], "defensive": [0.01, 0.00, 0.01]}
        raw = shrunk_covariance(observations, diagonal_shrinkage=0.0)
        diagonal = shrunk_covariance(observations, diagonal_shrinkage=1.0)
        self.assertNotEqual(0.0, raw["trend"]["defensive"])
        self.assertEqual(0.0, diagonal["trend"]["defensive"])
        for method in (
            "equal_weight", "inverse_volatility", "minimum_variance",
            "maximum_diversification", "hrp_two_sleeve",
        ):
            weights = allocate_two_sleeves(method, raw, maximum_weight=0.8)
            self.assertAlmostEqual(1.0, sum(weights.values()))
            self.assertTrue(all(0.2 - 1e-12 <= value <= 0.8 + 1e-12 for value in weights.values()))
            self.assertGreaterEqual(portfolio_variance(weights, raw), 0.0)

    def test_maximum_diversification_matches_inverse_volatility_for_two_sleeves(self):
        covariance = {"a": {"a": 0.04, "b": 0.01}, "b": {"a": 0.01, "b": 0.01}}
        self.assertEqual(
            allocate_two_sleeves("inverse_volatility", covariance),
            allocate_two_sleeves("maximum_diversification", covariance),
        )

    def test_dynamic_combination_places_uninvested_exposure_in_cash(self):
        histories = {
            "a": {"d": {"A": 1.0}},
            "b": {"d": {"B": 1.0}},
        }
        result = combine_dynamic_weight_histories(
            ["d"], histories, {"d": {"a": 0.3, "b": 0.2}}
        )
        self.assertEqual({"A": 0.3, "B": 0.2, CASH_ASSET: 0.5}, result["d"])

    def test_underlying_concentration_is_moved_to_cash(self):
        result = cap_non_cash_weights(
            {"d": {"A": 0.7, "B": 0.3, CASH_ASSET: 0.0}}, maximum_asset_weight=0.4
        )
        self.assertEqual(0.4, result["d"]["A"])
        self.assertEqual(0.3, result["d"]["B"])
        self.assertAlmostEqual(0.3, result["d"][CASH_ASSET])
        self.assertAlmostEqual(1.0, sum(result["d"].values()))

    def test_invalid_covariance_falls_back_to_equal_weight(self):
        invalid_cases = (
            {"a": {"a": float("nan"), "b": 0.0}, "b": {"a": 0.0, "b": 0.1}},
            {"a": {"a": -0.1, "b": 0.0}, "b": {"a": 0.0, "b": 0.1}},
            {"a": {"a": 0.1}},
        )
        for covariance in invalid_cases:
            weights, reason = safe_allocate_two_sleeves(
                "minimum_variance", covariance, sleeve_names=("a", "b")
            )
            self.assertEqual({"a": 0.5, "b": 0.5}, weights)
            self.assertTrue(reason)

    def test_valid_zero_variance_is_handled_without_failure(self):
        covariance = {"a": {"a": 0.0, "b": 0.0}, "b": {"a": 0.0, "b": 0.0}}
        weights, reason = safe_allocate_two_sleeves(
            "minimum_variance", covariance, sleeve_names=("a", "b")
        )
        self.assertEqual({"a": 0.5, "b": 0.5}, weights)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
