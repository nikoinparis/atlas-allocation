import csv
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = PROJECT_ROOT / "evidence" / "batch_01_backtest_execution"
REGISTRY_PATH = PROJECT_ROOT / "research_registry" / "registry.csv"
BATCH = "01_backtest_execution_and_simulation"


class Batch01EvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (EVIDENCE_DIR / "source_health.csv").open(encoding="utf-8") as handle:
            cls.evidence = list(csv.DictReader(handle))
        with REGISTRY_PATH.open(encoding="utf-8") as handle:
            cls.registry = list(csv.DictReader(handle))
        cls.summary = json.loads((EVIDENCE_DIR / "summary.json").read_text())
        cls.metadata = json.loads((EVIDENCE_DIR / "github_metadata.json").read_text())

    def test_all_41_repositories_have_current_evidence(self) -> None:
        self.assertEqual(41, len(self.evidence))
        self.assertEqual(41, len(self.metadata["data"]))
        self.assertTrue(all(row["head_commit"] for row in self.evidence))
        self.assertTrue(all(row["pushed_at"] for row in self.evidence))

    def test_action_counts_match_summary(self) -> None:
        actual: dict[str, int] = {}
        for row in self.evidence:
            actual[row["recommended_action"]] = actual.get(row["recommended_action"], 0) + 1
        self.assertEqual(self.summary["actions"], dict(sorted(actual.items())))

    def test_license_snapshots_resolve(self) -> None:
        for row in self.evidence:
            if row["license_evidence_path"]:
                self.assertTrue((EVIDENCE_DIR / row["license_evidence_path"]).is_file())

    def test_master_registry_records_batch_screening(self) -> None:
        batch_rows = [row for row in self.registry if row["review_batch"] == BATCH]
        self.assertEqual(41, len(batch_rows))
        allowed_statuses = {
            "source_screened", "bundled_tests_passed_offline", "dependency_failed",
            "recorded_fixture_guarded", "behavioral_probe_conditional",
        }
        self.assertTrue(all(row["test_status"] in allowed_statuses for row in batch_rows))
        self.assertTrue(all(row["evidence_path"] for row in batch_rows))
        self.assertTrue(all(row["decision"] in {"sandbox", "review", "historical_test"} for row in batch_rows))


if __name__ == "__main__":
    unittest.main()
