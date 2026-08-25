import unittest
from unittest import mock

import pandas as pd

import scripts.run_sec_persistent_earnings_acceleration_rank_v1 as subject


class PersistentEarningsAccelerationRankTests(unittest.TestCase):
    def test_candidate_name_is_stable(self):
        self.assertEqual(subject.candidate_name(52, 3, 0.2, 0.1, 5), "age52__persist3__a20__e10__buf5")

    def test_ranker_combines_both_features(self):
        decision = pd.Timestamp("2026-04-01", tz="UTC")
        panel = pd.DataFrame(
            {
                "decision_at": [decision] * 3,
                "cik10": ["1", "2", "3"],
                "company_name_as_filed": ["A", "B", "C"],
                "sector": ["technology"] * 3,
                "cash_score": [0.9, 0.8, 0.7],
                "acceleration_score": [0.0, 0.5, 1.0],
                "earnings_score": [0.0, 0.5, 1.0],
                "acceleration_event_time": pd.to_datetime(["2026-03-01"] * 3),
                "earnings_response_date": pd.to_datetime(["2026-03-06"] * 3),
            }
        )

        choices = subject.ranked_choices(panel, 0.3, 0.3, 1, 0)

        self.assertEqual(choices.cik10.tolist(), ["3"])

    def test_feature_panel_uses_only_strictly_prior_evidence(self):
        decision = pd.Timestamp("2026-04-01", tz="UTC")
        cash = pd.DataFrame(
            {
                "decision_at": [decision] * 3,
                "cik10": ["1", "2", "3"],
                "company_name_as_filed": ["A", "B", "C"],
                "sector": ["technology"] * 3,
                "cash_score": [0.5] * 3,
            }
        )
        filings = pd.DataFrame(
            {
                "event_time": pd.to_datetime(["2026-03-01T12:00:00Z"] * 3),
                "cik10": ["1", "2", "3"],
                "sector": ["technology"] * 3,
                "revenue_acceleration": [1.0, 2.0, 3.0],
                "operating_income_acceleration": [1.0, 2.0, 3.0],
                "operating_cash_flow_acceleration": [1.0, 2.0, 3.0],
            }
        )
        reactions = pd.DataFrame(
            {
                "cik10": ["1", "1", "2", "2", "3", "3"],
                "sector": ["technology"] * 6,
                "accepted_at": pd.to_datetime(["2025-10-01"] * 6),
                "response_date": pd.to_datetime(
                    ["2025-10-03", "2026-01-09", "2025-10-03", "2026-01-09", "2025-10-03", "2026-01-09"]
                ),
                "abnormal_reaction": [-0.1, 0.0, 0.0, 0.1, 0.1, 0.2],
            }
        )

        panel = subject.build_feature_panel(cash, filings, reactions, 26, 2, 104)
        decision_naive = pd.to_datetime(panel.decision_at, utc=True).dt.tz_localize(None)

        self.assertTrue((panel.acceleration_event_time < decision_naive).all())
        self.assertTrue((panel.earnings_response_date < decision_naive).all())
        self.assertTrue(panel.acceleration_available.all())
        self.assertTrue(panel.earnings_available.all())

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
        pd.testing.assert_frame_equal(simulate.call_args.args[1], fixed_target)


if __name__ == "__main__":
    unittest.main()
