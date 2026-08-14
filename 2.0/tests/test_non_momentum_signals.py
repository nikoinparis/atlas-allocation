import csv
import tempfile
import unittest
from pathlib import Path

from src.systematic_trader.non_momentum_signals import (
    moving_average_reversal,
    rsi_reversal,
    trailing_distribution_yield,
)


class NonMomentumSignalTests(unittest.TestCase):
    def test_reversal_prefers_the_more_depressed_asset(self):
        dates = [f"2025-01-{day:02d}" for day in range(1, 9)]
        prices = {day: {"A": 100.0, "B": 100.0} for day in dates}
        prices[dates[-1]] = {"A": 80.0, "B": 110.0}
        raw = moving_average_reversal(prices, dates, ["A", "B"], window=4)
        self.assertGreater(raw[dates[-1]]["A"], raw[dates[-1]]["B"])

    def test_low_rsi_has_higher_reversal_value(self):
        dates = [str(index) for index in range(8)]
        returns = {
            day: {"A": -0.02 if index else None, "B": 0.02 if index else None}
            for index, day in enumerate(dates)
        }
        signal = rsi_reversal(returns, dates, ["A", "B"], window=6)
        self.assertGreater(signal[dates[-1]]["A"], signal[dates[-1]]["B"])

    def test_distribution_yield_uses_only_events_on_or_before_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actions.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["ticker", "event_date", "action_type", "amount"])
                writer.writeheader()
                writer.writerows([
                    {"ticker": "A", "event_date": "2025-01-01", "action_type": "cash_distribution", "amount": 1},
                    {"ticker": "A", "event_date": "2025-03-01", "action_type": "cash_distribution", "amount": 9},
                ])
            dates = ["2025-02-01"]
            panel = trailing_distribution_yield(
                actions_path=path, dates=dates, assets=["A"], close_prices={dates[0]: {"A": 100.0}}
            )
            self.assertAlmostEqual(0.01, panel[dates[0]]["A"])


if __name__ == "__main__":
    unittest.main()
