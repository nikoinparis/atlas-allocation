import math
import sys
import unittest
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from systematic_trader.adapters import lag_signals_one_bar, simulate_flashalpha_safely  # noqa: E402


@dataclass
class FakeFill:
    fill_price: float
    mid_at_fill: float

    @property
    def edge_captured(self):
        return self.fill_price - self.mid_at_fill


@dataclass
class FakeResult:
    fill: FakeFill | None


class GuardedAdapterTests(unittest.TestCase):
    def test_bt_signals_are_lagged_one_full_bar(self):
        original = [{"SPY": False}, {"SPY": True}, {"SPY": False}]
        self.assertEqual(
            lag_signals_one_bar(original, inactive=False),
            [{"SPY": False}, {"SPY": False}, {"SPY": True}],
        )

    def test_flashalpha_is_not_called_for_nan_quote(self):
        called = False

        def unsafe_simulator(**kwargs):
            nonlocal called
            called = True
            return FakeResult(FakeFill(0.4, math.nan))

        expiry = date(2026, 5, 15)
        result = simulate_flashalpha_safely(
            bar_ts=datetime(2026, 4, 15),
            chain={(expiry, 440.0): (1.3, 1.3), (expiry, 435.0): (math.nan, 0.88)},
            candidates=[object()],
            simulator=unsafe_simulator,
        )
        self.assertEqual(result.status, "rejected")
        self.assertFalse(called)

    def test_flashalpha_valid_input_is_evaluated(self):
        def simulator(**kwargs):
            return FakeResult(FakeFill(0.4, 0.39))

        expiry = date(2026, 5, 15)
        result = simulate_flashalpha_safely(
            bar_ts=datetime(2026, 4, 15),
            chain={(expiry, 440.0): (1.3, 1.3), (expiry, 435.0): (0.86, 0.88)},
            candidates=[object()],
            simulator=simulator,
        )
        self.assertEqual(result.status, "evaluated")
        self.assertIsNotNone(result.third_party_result)

    def test_nonfinite_third_party_output_is_rejected(self):
        def simulator(**kwargs):
            return FakeResult(FakeFill(0.4, math.nan))

        expiry = date(2026, 5, 15)
        result = simulate_flashalpha_safely(
            bar_ts=datetime(2026, 4, 15),
            chain={(expiry, 440.0): (1.3, 1.3), (expiry, 435.0): (0.86, 0.88)},
            candidates=[object()],
            simulator=simulator,
        )
        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason, "nonfinite_fill_diagnostics")


if __name__ == "__main__":
    unittest.main()
