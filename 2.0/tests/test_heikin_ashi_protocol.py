import unittest

from src.systematic_trader.heikin_ashi_protocol import capped_unit_weights, heikin_ashi_bars, update_state


class HeikinAshiProtocolTests(unittest.TestCase):
    def test_recursive_transform(self):
        rows = heikin_ashi_bars([
            {"open": 10, "high": 13, "low": 9, "close": 12},
            {"open": 12, "high": 15, "low": 11, "close": 14},
        ])
        self.assertEqual(rows[0], {"open": 10.0, "close": 11.0, "high": 13.0, "low": 9.0})
        self.assertEqual(rows[1]["open"], 10.5)
        self.assertEqual(rows[1]["close"], 13.0)

    def test_source_direction_enters_on_growing_bearish_no_upper_wick(self):
        prior = {"open": 11.0, "close": 10.5, "high": 11.2, "low": 10.0}
        current = {"open": 11.0, "close": 9.0, "high": 11.0, "low": 8.5}
        self.assertEqual(update_state(prior, current, 0, corrected=False), (1, "entry"))
        self.assertEqual(update_state(prior, current, 0, corrected=True), (0, "hold"))

    def test_corrected_direction_enters_bullish_and_source_exits(self):
        prior = {"open": 10.0, "close": 10.5, "high": 11.0, "low": 9.8}
        current = {"open": 10.0, "close": 12.0, "high": 12.5, "low": 10.0}
        self.assertEqual(update_state(prior, current, 0, corrected=True), (1, "entry"))
        self.assertEqual(update_state(prior, current, 2, corrected=False), (0, "exit_all"))

    def test_unit_weights_cap_concentration_and_hold_cash(self):
        weights = capped_unit_weights({"A": 3, "B": 1}, ["A", "B"])
        self.assertEqual(weights["A"], 0.2)
        self.assertEqual(weights["B"], 0.2)
        self.assertAlmostEqual(weights["cash::USD"], 0.6)


if __name__ == "__main__":
    unittest.main()
