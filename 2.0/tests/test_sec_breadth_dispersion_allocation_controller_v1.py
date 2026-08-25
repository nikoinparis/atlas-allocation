import unittest
from unittest import mock

import pandas as pd

import scripts.run_sec_breadth_dispersion_allocation_controller_v1 as subject


class BreadthDispersionAllocationControllerTests(unittest.TestCase):
    def test_candidate_name_is_stable(self):
        self.assertEqual(
            subject.candidate_name(13, 52, 0.6, "breadth_high", 0.25, 0.8),
            "h13__cal52__q60__breadth_high__w25_80",
        )

    def test_signal_does_not_use_current_price(self):
        index = pd.date_range("2025-01-03", periods=8, freq="W-FRI")
        weekly = pd.DataFrame({"1": range(100, 108), "2": range(100, 92, -1)}, index=index)
        original = subject.breadth_dispersion_signals(weekly, 2)
        changed = weekly.copy()
        changed.iloc[-1] = [1000, 1]
        revised = subject.breadth_dispersion_signals(changed, 2)

        pd.testing.assert_series_equal(original.iloc[-1], revised.iloc[-1])

    def test_controller_only_scales_an_active_sleeve(self):
        index = pd.date_range("2025-01-03", periods=6, freq="W-FRI")
        base_target = pd.DataFrame(
            {"leader": [1.0, 1.0, 0.5, 0.5, 0.5, 1.0], "cash_conversion": [0.0, 0.0, 0.5, 0.5, 0.5, 0.0]},
            index=index,
        )
        signals = pd.DataFrame(
            {"breadth": [0.4, 0.5, 0.7, 0.8, 0.9, 0.9], "dispersion": [0.2] * 6, "issuer_coverage": [100] * 6},
            index=index,
        )

        with mock.patch.object(subject, "regime_state", return_value=pd.Series(True, index=index)):
            target, _ = subject.controller_target(base_target, signals, 2, 0.5, "breadth_high", 0.25, 0.8)

        self.assertTrue((target.loc[base_target.cash_conversion == 0, "cash_conversion"] == 0).all())
        self.assertTrue((target.loc[base_target.cash_conversion > 0, "cash_conversion"] == 0.8).all())

    def test_machine_precision_differences_are_ties(self):
        index = pd.date_range("2025-01-03", periods=30, freq="W-FRI")
        joined = pd.DataFrame(
            {
                "candidate": [0.01 + 1e-16] * 30,
                "control": [0.01] * 30,
            },
            index=index,
        )

        excess = subject.stable_excess_returns(joined)
        share, windows = subject.stable_completed_rolling_outperformance(joined, 26)

        self.assertTrue((excess == 0).all())
        self.assertEqual(share, 0.0)
        self.assertEqual(windows, 5)


if __name__ == "__main__":
    unittest.main()
