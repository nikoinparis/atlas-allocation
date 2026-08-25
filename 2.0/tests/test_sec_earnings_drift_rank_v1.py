import unittest
from unittest import mock

import pandas as pd

import scripts.run_sec_earnings_drift_rank_v1 as subject


class EarningsDriftRankTests(unittest.TestCase):
    def test_candidate_name_is_stable(self):
        self.assertEqual(subject.candidate_name(4, 0.30, 20, 5), "pead4__w30__b20__buf5")

    def test_response_close_is_strictly_after_acceptance_date(self):
        history = pd.DataFrame(
            {"1": [100.0, 105.0, 106.0], "2": [100.0, 101.0, 102.0]},
            index=pd.date_range("2026-01-02", periods=3, freq="W-FRI"),
        )
        events = pd.DataFrame(
            {
                "cik10": ["1"],
                "company_name_as_filed": ["A"],
                "sector": ["technology"],
                "accession": ["x"],
                "filing_date": ["2026-01-09"],
                "report_date": ["2025-12-31"],
                "available_at": ["2026-01-09T13:00:00Z"],
            }
        )

        reactions = subject.build_event_reactions(events, history, {"1": "technology", "2": "technology"})

        self.assertEqual(reactions.iloc[0].prior_price_date, pd.Timestamp("2026-01-02"))
        self.assertEqual(reactions.iloc[0].response_date, pd.Timestamp("2026-01-16"))
        self.assertGreater(reactions.iloc[0].response_date, reactions.iloc[0].accepted_at.normalize())

    def test_fixed_target_is_reused_in_cost_stress(self):
        index = pd.date_range("2026-01-02", periods=3, freq="W-FRI")
        leader = pd.Series([0.01, 0.02, -0.01], index=index)
        sleeve = pd.DataFrame({"net_return": [0.02, 0.01, 0.00]}, index=index)
        fixed_target = pd.DataFrame({"leader": [0.5] * 3, "cash_conversion": [0.5] * 3}, index=index)
        config = {"overlay_lookback_weeks": 11, "overlay_active_allocation": 0.5}

        with mock.patch.object(subject.capped, "overlay_target", side_effect=AssertionError("must not recalculate")):
            with mock.patch.object(subject.dynamic, "simulate", return_value="path") as simulate:
                result = subject.composite(leader, sleeve, config, 200.0, fixed_target=fixed_target)

        self.assertEqual(result, "path")
        self.assertIs(simulate.call_args.args[1], fixed_target)


if __name__ == "__main__":
    unittest.main()
