import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/challenger_program_v1.json"
QUEUE = ROOT / "evidence/challenger_program_v1/source_queue.csv"


class ChallengerProgramTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(CONFIG.read_text(encoding="utf-8"))
        with QUEUE.open(newline="", encoding="utf-8") as handle:
            self.queue = list(csv.DictReader(handle))

    def test_all_six_tracks_are_predeclared(self):
        tracks = {item["track_id"] for item in self.config["tracks"]}
        self.assertEqual(
            tracks,
            {
                "trade_buffering",
                "fragility_guard",
                "independent_strategy_sleeves",
                "portfolio_libraries",
                "machine_learning_sandbox",
                "vectorbt_equivalence",
            },
        )

    def test_all_ten_repositories_are_pinned(self):
        self.assertEqual(len(self.queue), 10)
        self.assertEqual(len({row["entry_id"] for row in self.queue}), 10)
        for row in self.queue:
            self.assertRegex(row["head_commit"], r"^[0-9a-f]{40}$")
            self.assertEqual(row["queue_status"], "ready")

    def test_safety_and_no_cherry_pick_rules_are_explicit(self):
        self.assertFalse(self.config["claims_policy"]["profitability_claim_allowed"])
        self.assertTrue(self.config["claims_policy"]["failed_and_blocked_trials_must_be_retained"])
        self.assertTrue(self.config["claims_policy"]["all_attempted_configurations_count_toward_multiple_testing"])
        self.assertFalse(self.config["promotion_rule"]["baseline_files_may_be_modified"])
        self.assertEqual(self.config["promotion_rule"]["minimum_forward_weeks"], 52)

    def test_all_pinned_sources_passed_nonexecution_acquisition(self):
        summary = json.loads(
            (ROOT / "evidence/challenger_program_v1/source_smoke/summary.json").read_text()
        )
        self.assertEqual(summary["total"], 10)
        self.assertEqual(summary["passed"], 10)
        self.assertFalse(summary["repository_code_executed"])


if __name__ == "__main__":
    unittest.main()
