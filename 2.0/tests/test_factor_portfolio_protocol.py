import unittest

from src.systematic_trader.factor_portfolio_protocol import (
    CASH,
    cap_and_normalize,
    drift_aware_path,
    target_weights,
)


class FactorPortfolioProtocolTests(unittest.TestCase):
    def test_cap_and_normalize(self):
        weights = cap_and_normalize({"a": 10.0, "b": 2.0, "c": 2.0, "d": 2.0}, 0.4)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertLessEqual(max(weights.values()), 0.4)

    def test_equal_top_five(self):
        scores = {letter: float(index) for index, letter in enumerate("abcdef")}
        weights = target_weights(scores, {}, candidate="equal_weight_top5", top_n=5, maximum_weight=0.3)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertEqual(weights["f"], 0.2)
        self.assertEqual(weights[CASH], 0.0)

    def test_insufficient_assets_is_cash(self):
        weights = target_weights({"a": 1.0}, {}, candidate="equal_weight_top5", top_n=5, maximum_weight=0.3)
        self.assertEqual(weights, {CASH: 1.0})

    def test_drifted_holdings_reduce_rebalance_turnover(self):
        dates = ["2020-01-03", "2020-01-10", "2020-01-17"]
        weights = {day: {"a": 0.5, "b": 0.5, CASH: 0.0} for day in dates}
        returns = {
            "2020-01-10": {"a": 0.1, "b": 0.0},
            "2020-01-17": {"a": 0.0, "b": 0.0},
        }
        rows, audit = drift_aware_path(dates, weights, returns, cost_bps=0.0)
        self.assertAlmostEqual(rows[0]["turnover"], 1.0)
        self.assertGreater(rows[1]["turnover"], 0.0)
        self.assertTrue(audit["cost_identity_pass"])

    def test_none_target_holds_drifted_weights_without_turnover(self):
        dates = ["2020-01-03", "2020-01-10", "2020-01-17"]
        weights = {
            "2020-01-03": {"a": 0.5, "b": 0.5, CASH: 0.0},
            "2020-01-10": None,
            "2020-01-17": None,
        }
        returns = {
            "2020-01-10": {"a": 0.1, "b": 0.0},
            "2020-01-17": {"a": 0.0, "b": 0.0},
        }
        rows, _ = drift_aware_path(dates, weights, returns, cost_bps=50.0)
        self.assertAlmostEqual(rows[0]["turnover"], 1.0)
        self.assertEqual(rows[1]["turnover"], 0.0)


if __name__ == "__main__":
    unittest.main()
