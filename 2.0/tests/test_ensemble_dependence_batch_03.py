import csv
import hashlib
import json
import unittest
from pathlib import Path


class EnsembleDependenceBatch03Tests(unittest.TestCase):
    def test_batch_covers_every_candidate_without_finalizing_any(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/ensemble_dependence_batch_03"
        result = json.loads((output / "result.json").read_text())
        registry = json.loads((root / "research_registry/strategy_candidates.json").read_text())
        covered = [item for item in registry["candidates"] if "ensemble_dependence_batch_03" in item]
        self.assertEqual(result["candidate_count"], len(covered))
        self.assertEqual(45, result["pair_count"])
        self.assertTrue(all(not item["final"] for item in registry["candidates"]))
        self.assertEqual(10, len(covered))

    def test_ensemble_accounting_and_artifact_integrity(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/ensemble_dependence_batch_03"
        result = json.loads((output / "result.json").read_text())
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        with (output / "ensemble_scoreboard.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(4, len(rows))
        self.assertTrue(all(row["fully_invested_pass"] == "True" for row in rows))
        self.assertTrue(all(int(row["unpriced_exposure_events"]) == 0 for row in rows))

    def test_multiple_testing_uses_original_search_count(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/ensemble_dependence_batch_03"
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(288, result["multiple_testing"]["original_experiment_search_count"])
        self.assertGreaterEqual(result["multiple_testing"]["bootstrap_samples"], 17280)
        with (output / "multiple_testing.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(result["candidate_count"], len(rows))
        self.assertTrue(all(0.0 <= float(row["bonferroni_288_pvalue"]) <= 1.0 for row in rows))


if __name__ == "__main__":
    unittest.main()
