import unittest

from src.systematic_trader.pair_protocol import frictional_pair_return, long_short_turnover, update_pair_state


class PairProtocolTests(unittest.TestCase):
    def test_signal_at_close_changes_only_next_period_state(self):
        self.assertEqual((-1, False), update_pair_state(0, 2.1))
        self.assertEqual((1, False), update_pair_state(0, -2.1))
        self.assertEqual((0, False), update_pair_state(-1, 0.4))

    def test_inverted_control_does_not_flip_existing_state_each_day(self):
        self.assertEqual((1, False), update_pair_state(0, 2.1, invert=True))
        self.assertEqual((1, False), update_pair_state(1, 2.2, invert=True))

    def test_relationship_break_exits_and_disables(self):
        self.assertEqual((0, True), update_pair_state(1, 4.0))

    def test_long_short_turnover_is_full_traded_notional(self):
        self.assertEqual(1.0, long_short_turnover({}, {"LONG": 0.5, "SHORT": -0.5}))
        self.assertEqual(2.0, long_short_turnover({"LONG": 0.5, "SHORT": -0.5}, {"LONG": -0.5, "SHORT": 0.5}))

    def test_cost_and_borrow_are_both_charged(self):
        value = frictional_pair_return(0.01, 1.0, 0.5, cost_bps=50.0, annual_borrow_fee=0.03)
        self.assertAlmostEqual(0.01 - 0.005 - 0.5 * 0.03 / 252.0, value)


if __name__ == "__main__":
    unittest.main()
