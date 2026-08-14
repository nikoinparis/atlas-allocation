import unittest

from src.systematic_trader.factor_decay_turnover_protocol import (
    buffered_membership,
    month_end_weekly_dates,
)


class FactorDecayTurnoverProtocolTests(unittest.TestCase):
    def test_buffer_prevents_small_improvement(self):
        current = ["a", "b"]
        selected, _, changed = buffered_membership(
            current, {"a": 4, "b": 4}, {"a": 1.0, "b": 0.5, "c": 0.9},
            top_n=2, minimum_age=4, entry_buffer=0.5,
        )
        self.assertEqual(selected, current)
        self.assertFalse(changed)

    def test_at_most_one_replacement(self):
        selected, ages, changed = buffered_membership(
            ["a", "b"], {"a": 4, "b": 4}, {"a": 0.0, "b": 0.1, "c": 2.0, "d": 1.5},
            top_n=2, minimum_age=4, entry_buffer=0.5,
        )
        self.assertEqual(len(set(selected) & {"a", "b"}), 1)
        self.assertTrue(changed)
        self.assertEqual(ages["c"], 0)

    def test_minimum_age_blocks_replacement(self):
        selected, _, changed = buffered_membership(
            ["a", "b"], {"a": 2, "b": 2}, {"a": 0.0, "b": 0.1, "c": 2.0},
            top_n=2, minimum_age=4, entry_buffer=0.5,
        )
        self.assertEqual(selected, ["a", "b"])
        self.assertFalse(changed)

    def test_month_end_weekly_dates(self):
        dates = ["2020-01-03", "2020-01-31", "2020-02-07"]
        self.assertEqual(month_end_weekly_dates(dates), {"2020-01-31", "2020-02-07"})


if __name__ == "__main__":
    unittest.main()
