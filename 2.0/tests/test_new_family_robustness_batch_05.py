import csv
import hashlib
import json
import unittest
from pathlib import Path


class NewFamilyRobustnessBatch05Tests(unittest.TestCase):
    def test_all_three_new_family_leaders_receive_non_final_decisions(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/new_family_robustness_batch_05/result.json").read_text())
        self.assertEqual(3, result["candidate_count"])
        self.assertEqual(3, result["robust_count"] + result["fragile_count"])
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        candidates = [item for item in registry["candidates"] if item.get("source_batch") == "new_families_batch_04"]
        self.assertEqual(3, len(candidates))
        self.assertTrue(all("new_family_robustness_batch_05" in item for item in candidates))
        self.assertTrue(all(not item["final"] and not item["approved_for_live_trading"] for item in candidates))

    def test_multiple_testing_has_tail_resolution_and_carry_stays_research_only(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/new_family_robustness_batch_05"
        result = json.loads((output / "result.json").read_text())
        self.assertGreaterEqual(result["rules_fixed_before_results"]["multiple_testing"]["bootstrap_samples"], 34560)
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        carry = next(item for item in registry["candidates"] if item.get("family") == "carry_proxy")
        self.assertIn("archived_point_in_time_distribution_history", carry["missing_gates"])
        self.assertNotEqual("final", carry["status"])
        with (output / "multiple_testing.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(3, len(rows))

    def test_artifact_hashes_and_ensemble_accounting(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/new_family_robustness_batch_05"
        result = json.loads((output / "result.json").read_text())
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        with (output / "robust_ensemble_diagnostics.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertTrue(all(row["fully_invested_pass"] == "True" for row in rows))
        self.assertTrue(all(int(row["unpriced_exposure_events"]) == 0 for row in rows))


if __name__ == "__main__":
    unittest.main()
