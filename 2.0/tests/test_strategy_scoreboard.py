import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_strategy_scoreboard.py"
spec = importlib.util.spec_from_file_location("strategy_scoreboard", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class StrategyScoreboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = module.build()

    def test_all_saved_return_position_pairs_are_included(self):
        self.assertEqual(33, self.result["summary"]["strategy_count"])
        self.assertEqual(33, len(self.result["rows"]))

    def test_decision_dates_are_mapped_to_following_realization_dates(self):
        self.assertEqual("2005-01-14", module.realized_date("2005-01-07"))

    def test_known_baseline_reconstructs_to_machine_precision(self):
        row = next(
            row for row in self.result["rows"]
            if row["strategy"] == "baseline_market_proxy_buy_hold"
        )
        self.assertTrue(row["return_reconstruction_pass"])
        self.assertLess(row["max_return_reconstruction_error"], 1e-12)
        self.assertTrue(row["cost_reconciliation_pass"])

    def test_nonreconciling_artifact_is_visible_but_grade_d(self):
        row = next(
            row for row in self.result["rows"]
            if row["strategy"] == "composite_calm_carry_sleeve"
        )
        self.assertFalse(row["return_reconstruction_pass"])
        self.assertEqual("D", row["evidence_grade"])
        self.assertFalse(row["eligible_for_trustworthy_ranking"])

    def test_no_strategy_is_promoted_or_claimed_as_untouched(self):
        self.assertEqual(0, self.result["summary"]["promoted"])
        self.assertFalse(self.result["summary"]["recent_window_is_untouched_holdout"])
        self.assertTrue(
            all(row["promotion_status"] == "research_only_no_untouched_holdout" for row in self.result["rows"])
        )
        self.assertEqual(
            "2026-08-14", self.result["validation_protocol"]["first_genuinely_untouched_week_end"]
        )

    def test_free_rebalancing_and_short_financing_reduce_evidence_grade(self):
        by_name = {row["strategy"]: row for row in self.result["rows"]}
        self.assertEqual("C", by_name["baseline_60_40_proxy"]["evidence_grade"])
        self.assertTrue(by_name["baseline_60_40_proxy"]["static_multi_asset_zero_turnover"])
        self.assertEqual("C", by_name["cta_trend_long_short_research"]["evidence_grade"])
        self.assertGreater(by_name["cta_trend_long_short_research"]["negative_exposure_weeks"], 0)


if __name__ == "__main__":
    unittest.main()
