import json
import unittest
from pathlib import Path


class StrategyCandidateRegistryTests(unittest.TestCase):
    def test_candidates_are_explicitly_provisional_and_traceable(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        self.assertGreaterEqual(registry["candidate_count"], 8)
        self.assertEqual(registry["candidate_count"], len(registry["candidates"]))
        experiment_ids = set()
        for candidate in registry["candidates"]:
            self.assertFalse(candidate["final"])
            self.assertFalse(candidate["approved_for_live_trading"])
            self.assertIn(candidate["status"], {
                "provisional_not_approved", "provisional_robust", "provisional_fragile",
                "provisional_new_family", "provisional_robust_new_family",
                "provisional_robust_research_only",
            })
            self.assertIn("52_week_untouched_forward_record", candidate["missing_gates"])
            self.assertNotIn(candidate["experiment_id"], experiment_ids)
            experiment_ids.add(candidate["experiment_id"])

    def test_frozen_v4_and_walk_forward_choices_are_preserved(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        candidates = {item["experiment_id"]: item for item in registry["candidates"]}
        self.assertIn("exp-fc7248702f02b421", candidates)
        self.assertIn("exact_frozen_v4_benchmark", candidates["exp-fc7248702f02b421"]["selection_reasons"])
        self.assertTrue(any(
            any(reason.startswith("selected_using_training_window_") for reason in item["selection_reasons"])
            for item in candidates.values()
        ))


if __name__ == "__main__":
    unittest.main()
