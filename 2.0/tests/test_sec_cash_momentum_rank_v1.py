import unittest
from unittest import mock

import pandas as pd

import scripts.run_sec_cash_momentum_rank_v1 as subject


class CashMomentumRankTests(unittest.TestCase):
    def test_candidate_name_is_stable(self):
        self.assertEqual(subject.candidate_name(52, 0.15, 30, 5), "mom52__w15__b30__buf5")

    def test_signal_reference_is_strictly_before_decision(self):
        dates = pd.date_range("2024-01-05", periods=32, freq="W-FRI")
        history = pd.DataFrame(
            {
                "1": range(100, 132),
                "2": range(132, 100, -1),
            },
            index=dates,
        )
        panel = pd.DataFrame(
            {
                "decision_at": pd.to_datetime(["2024-01-01", "2024-01-01"], utc=True),
                "cik10": ["1", "2"],
                "company_name_as_filed": ["A", "B"],
                "sector": ["technology", "technology"],
                "cash_score": [0.5, 0.5],
            }
        )

        choices = subject.momentum_choices(panel, history, dates[28:], 26, 0.2, 1, 0)

        self.assertFalse(choices.empty)
        self.assertTrue((choices.signal_reference_at < choices.decision_at).all())
        self.assertEqual(choices.iloc[0].cik10, "1")

    def test_fixed_target_is_reused_in_cost_stress(self):
        index = pd.date_range("2026-01-02", periods=3, freq="W-FRI")
        leader = pd.Series([0.01, 0.02, -0.01], index=index)
        sleeve = pd.DataFrame({"net_return": [0.02, 0.01, 0.00]}, index=index)
        fixed_target = pd.DataFrame({"leader": [0.5] * 3, "cash_conversion": [0.5] * 3}, index=index)
        config = {"overlay_lookback_weeks": 11, "overlay_active_allocation": 0.5}

        with mock.patch.object(subject.capped, "overlay_target", side_effect=AssertionError("must not recalculate")):
            with mock.patch.object(subject.dynamic, "simulate", return_value="path") as simulate:
                result = subject.composite_path(leader, sleeve, config, 200.0, fixed_target=fixed_target)

        self.assertEqual(result, "path")
        self.assertIs(simulate.call_args.args[1], fixed_target)


if __name__ == "__main__":
    unittest.main()
