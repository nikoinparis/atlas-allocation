import unittest

from src.systematic_trader.oscillator_protocol import (
    adjusted_bar, capped_equal_weights, deterministic_matched_active,
    ewm_adjust_true, long_only_turnover, rolling_mean,
)


class OscillatorProtocolTests(unittest.TestCase):
    def test_adjusted_ohlc_uses_close_factor(self):
        self.assertEqual(adjusted_bar(90, 110, 80, 100, 50), {"open": 45, "high": 55, "low": 40, "close": 50, "median": 47.5})

    def test_rolling_mean_has_full_window_only(self):
        self.assertEqual(rolling_mean([1, 2, 3, 4], 3), [None, None, 2.0, 3.0])

    def test_adjust_true_ewm_matches_hand_calculation(self):
        values = ewm_adjust_true([1, 2, 3], 3)
        self.assertAlmostEqual(values[0], 1.0)
        self.assertAlmostEqual(values[1], 5 / 3)
        self.assertAlmostEqual(values[2], 17 / 7)

    def test_cap_leaves_cash_and_turnover_counts_cash_leg(self):
        assets = ["A", "B", "C"]
        empty = capped_equal_weights([], assets)
        target = capped_equal_weights(["A", "B"], assets)
        self.assertEqual(target["cash::USD"], 0.6)
        self.assertAlmostEqual(long_only_turnover(empty, target), 0.4)

    def test_turnover_uses_full_cash_aware_half_l1(self):
        drifted = {"A": 0.55, "B": 0.45, "cash::USD": 0.0}
        target = {"A": 0.5, "B": 0.4, "cash::USD": 0.1}
        self.assertAlmostEqual(long_only_turnover(drifted, target), 0.1)

    def test_random_control_is_deterministic_and_count_matched(self):
        left = deterministic_matched_active(["A", "B", "C"], 2, "2020-01-02", 7)
        self.assertEqual(left, deterministic_matched_active(["A", "B", "C"], 2, "2020-01-02", 7))
        self.assertEqual(len(left), 2)


if __name__ == "__main__":
    unittest.main()
