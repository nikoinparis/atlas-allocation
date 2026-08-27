import csv
import hashlib
import json
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REGISTRY_DIR = PROJECT_ROOT / "research_registry"


class PinnedInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (REGISTRY_DIR / "registry.csv").open(encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))
        cls.summary = json.loads((REGISTRY_DIR / "inventory_summary.json").read_text())

    def test_every_linked_catalog_bullet_has_one_row(self) -> None:
        expected = sum(
            audit["linked_bullet_count"]
            for audit in self.summary["coverage_audit"].values()
        )
        self.assertEqual(expected, len(self.rows))
        self.assertEqual(344, expected)

    def test_source_snapshots_match_recorded_hashes(self) -> None:
        for metadata in self.summary["source_files"].values():
            snapshot = REGISTRY_DIR / metadata["snapshot"]
            self.assertEqual(metadata["sha256"], hashlib.sha256(snapshot.read_bytes()).hexdigest())

    def test_rows_have_required_inventory_classification(self) -> None:
        for row in self.rows:
            self.assertTrue(row["entry_id"])
            self.assertTrue(row["name"])
            self.assertTrue(row["primary_url"])
            self.assertTrue(row["category_path"])
            self.assertTrue(row["entry_type"])
            self.assertTrue(row["review_batch"])
            self.assertIn(
                row["test_status"],
                {
                    "inventory", "source_screened", "bundled_tests_passed_offline",
                    "dependency_failed", "recorded_fixture_guarded",
                    "behavioral_probe_conditional",
                    "drawdown_component_tested_not_promoted",
                    "upstream_tests_failed",
                },
            )

    def test_duplicate_references_resolve(self) -> None:
        identifiers = {row["entry_id"] for row in self.rows}
        for row in self.rows:
            self.assertTrue(not row["duplicate_of"] or row["duplicate_of"] in identifiers)


if __name__ == "__main__":
    unittest.main()
