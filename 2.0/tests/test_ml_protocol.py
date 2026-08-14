import unittest

from src.systematic_trader.ml_protocol import eligible_training_row, outer_test_years, promotion_gates


class RobustMlProtocolTests(unittest.TestCase):
    def test_label_embargo_excludes_overlapping_training_row(self):
        overlapping = {"decision_date": "2020-12-11", "label_end_date": "2021-01-08"}
        eligible = {"decision_date": "2020-11-27", "label_end_date": "2020-12-25"}
        self.assertFalse(eligible_training_row(overlapping, "2021-01-01"))
        self.assertTrue(eligible_training_row(eligible, "2021-01-01"))

    def test_outer_years_are_chronological_and_unique(self):
        rows = [{"decision_date": day} for day in ("2011-01-01", "2012-02-01", "2012-03-01", "2014-01-01")]
        self.assertEqual([2012, 2014], outer_test_years(rows, 2012))

    def test_promotion_is_fail_closed(self):
        gates = promotion_gates(
            rank_ic_pass=True, beats_fixed=True, beats_winner=True, later_cost_pass=True,
            drawdown_pass=True,
            dependence_pass=True, controls_pass=True, fold_stability_pass=True,
            survivorship_safe=False, forward_weeks=0,
        )
        self.assertFalse(gates["all"])
        self.assertFalse(gates["survivorship_safe"])
        self.assertFalse(gates["untouched_forward_52w"])


if __name__ == "__main__":
    unittest.main()
