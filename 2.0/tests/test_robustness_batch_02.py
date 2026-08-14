import csv
import hashlib
import json
import unittest
from pathlib import Path


class RobustnessBatch02Tests(unittest.TestCase):
    def test_every_candidate_has_a_non_final_robustness_decision(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/robustness_batch_02/result.json").read_text())
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        covered = [item for item in registry["candidates"] if "robustness_batch_02" in item]
        self.assertEqual(result["candidate_count"], len(covered))
        self.assertEqual(result["candidate_count"], result["robust_count"] + result["fragile_count"])
        for candidate in covered:
            self.assertIn("robustness_batch_02", candidate)
            self.assertFalse(candidate["final"])
            self.assertFalse(candidate["approved_for_live_trading"])
            self.assertIn("52_week_untouched_forward_record", candidate["missing_gates"])

    def test_artifacts_are_integral_and_all_neighborhoods_have_nine_members(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/robustness_batch_02"
        result = json.loads((output / "result.json").read_text())
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        with (output / "neighborhoods.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertTrue(all(int(row["neighbor_count"]) == 9 for row in rows))


if __name__ == "__main__":
    unittest.main()
