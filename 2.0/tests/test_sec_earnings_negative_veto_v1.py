import unittest
from unittest import mock

import pandas as pd

import scripts.run_sec_earnings_negative_veto_v1 as subject


class EarningsNegativeVetoTests(unittest.TestCase):
    def test_candidate_name_is_stable(self):
        self.assertEqual(subject.candidate_name(4, 0.30, 2), "veto4__q30__max2")

    def test_negative_top_ranked_issuer_is_replaced(self):
        decision = pd.Timestamp("2026-04-01", tz="UTC")
        scores = pd.DataFrame(
            {
                "decision_at": [decision] * 3,
                "cik10": ["1", "2", "3"],
                "company_name_as_filed": ["A", "B", "C"],
                "sector": ["technology"] * 3,
                "score": [0.9, 0.8, 0.7],
            }
        )
        reactions = pd.DataFrame(
            {
                "cik10": ["1", "2", "3"],
                "company_name_as_filed": ["A", "B", "C"],
                "sector": ["technology"] * 3,
                "accepted_at": pd.to_datetime(
                    ["2026-03-01T12:00:00Z", "2026-03-01T12:00:00Z", "2026-03-01T12:00:00Z"]
                ),
                "response_date": pd.to_datetime(["2026-03-06"] * 3),
                "abnormal_reaction": [-0.30, 0.01, 0.02],
            }
        )

        choices, vetoes = subject.veto_choices(scores, reactions, 2, 4, 0.50, 1)

        self.assertEqual(set(choices.cik10), {"2", "3"})
        self.assertEqual(vetoes.cik10.tolist(), ["1"])

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
        self.assertEqual(simulate.call_args.args[2], 200.0)


if __name__ == "__main__":
    unittest.main()
