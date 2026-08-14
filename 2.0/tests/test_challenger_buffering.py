import unittest

from src.systematic_trader.challenger_buffering import buffer_history, buffered_target


class ChallengerBufferingTests(unittest.TestCase):
    def test_inside_band_does_not_trade(self):
        previous = {"A": 0.50, "B": 0.50}
        target = {"A": 0.54, "B": 0.46}
        result, audit = buffered_target(previous, target, no_trade_turnover=0.05)
        self.assertEqual(previous, result)
        self.assertTrue(audit["buffer_held"])

    def test_outside_band_trades_only_to_band_edge(self):
        previous = {"A": 0.50, "B": 0.50}
        target = {"A": 0.70, "B": 0.30}
        result, audit = buffered_target(previous, target, no_trade_turnover=0.05)
        self.assertAlmostEqual(result["A"], 0.65)
        self.assertAlmostEqual(result["B"], 0.35)
        self.assertAlmostEqual(audit["realized_turnover"], 0.15)

    def test_history_is_long_only_and_fully_invested(self):
        dates = ["2026-01-02", "2026-01-09", "2026-01-16"]
        targets = {
            dates[0]: {"A": 0.5, "cash::USD": 0.5},
            dates[1]: {"A": 0.8, "cash::USD": 0.2},
            dates[2]: {"A": 0.1, "cash::USD": 0.9},
        }
        output, audit = buffer_history(dates, targets, entry_band=0.10, exit_band=0.02)
        self.assertEqual(len(audit), 3)
        for row in output.values():
            self.assertAlmostEqual(sum(row.values()), 1.0)
            self.assertTrue(all(value >= 0.0 for value in row.values()))


if __name__ == "__main__":
    unittest.main()
