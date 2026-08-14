import hashlib
import json
import unittest
from pathlib import Path


class NewFamiliesBatch04Tests(unittest.TestCase):
    def test_batch_has_three_family_leaders_and_no_final_claims(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/new_families_batch_04/result.json").read_text())
        self.assertEqual(288, result["experiment_count"])
        self.assertEqual({"mean_reversion", "defensive", "carry_proxy"}, {
            row["family"] for row in result["family_leaders"]
        })
        self.assertEqual(4, len(result["multi_family_ensemble_diagnostics"]))
        self.assertTrue(all(row["fully_invested_pass"] for row in result["multi_family_ensemble_diagnostics"]))
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        new = [item for item in registry["candidates"] if item.get("source_batch") == "new_families_batch_04"]
        self.assertEqual(3, len(new))
        self.assertTrue(all(not item["final"] and not item["approved_for_live_trading"] for item in new))

    def test_carry_limitation_and_artifact_integrity_are_preserved(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/new_families_batch_04"
        result = json.loads((output / "result.json").read_text())
        self.assertIn("not a historically archived point-in-time feed", result["signal_audit"]["distribution_history_knowledge_limitation"])
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        carry = next(item for item in registry["candidates"] if item.get("family") == "carry_proxy")
        self.assertIn("archived_point_in_time_distribution_history", carry["missing_gates"])
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)


if __name__ == "__main__":
    unittest.main()
