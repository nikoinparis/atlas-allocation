import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.systematic_trader.data_revision import compare_price_files, snapshot_freshness


def write_prices(path: Path, rows: list[dict[str, object]]) -> None:
    fields = ["observation_date", "security_id", "ticker", "adjusted_close", "close", "knowledge_at_utc", "source_revision"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class FreeDataDiagnosticsTests(unittest.TestCase):
    def test_revision_comparison_counts_changes_new_and_missing_rows(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            base = {"knowledge_at_utc": "2026-08-07T22:00:00+00:00", "source_revision": "v1"}
            write_prices(root / "old.csv", [
                {**base, "observation_date": "2026-08-06", "security_id": "id:a", "ticker": "AAA", "adjusted_close": 10, "close": 10},
                {**base, "observation_date": "2026-08-06", "security_id": "id:b", "ticker": "BBB", "adjusted_close": 20, "close": 20},
            ])
            write_prices(root / "new.csv", [
                {**base, "observation_date": "2026-08-06", "security_id": "id:a", "ticker": "AAA", "adjusted_close": 11, "close": 10},
                {**base, "observation_date": "2026-08-07", "security_id": "id:a", "ticker": "AAA", "adjusted_close": 12, "close": 12},
            ])
            result = compare_price_files(root / "old.csv", root / "new.csv")
            self.assertEqual(1, result["revised_rows"])
            self.assertEqual(1, result["new_keys"])
            self.assertEqual(1, result["disappeared_keys"])
            self.assertEqual(1, result["magnitude_by_field"]["adjusted_close"]["exact_change_count"])
            self.assertEqual(0, result["magnitude_by_field"]["close"]["exact_change_count"])
            self.assertEqual(1, result["economically_material_adjusted_close_rows"])

    def test_freshness_requires_every_symbol_and_recent_data(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "prices.csv"
            base = {"knowledge_at_utc": "2026-08-08T20:00:00+00:00", "source_revision": "v1", "close": 10}
            write_prices(path, [
                {**base, "observation_date": "2026-08-07", "security_id": "id:a", "ticker": "AAA", "adjusted_close": 10},
            ])
            passed = snapshot_freshness(path, "2026-08-08T20:00:00+00:00", {"AAA"})
            failed = snapshot_freshness(path, "2026-08-20T20:00:00+00:00", {"AAA", "BBB"})
            self.assertTrue(passed["freshness_pass"])
            self.assertFalse(failed["freshness_pass"])
            self.assertEqual(["BBB"], failed["missing_symbols"])


class CheckedInFreeAcquisitionTests(unittest.TestCase):
    def test_free_snapshot_is_complete_but_research_only(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/free_data_acquisition/latest_result.json").read_text())
        self.assertEqual(35, result["acquisition"]["symbol_count"])
        self.assertGreater(result["acquisition"]["price_rows"], 200_000)
        self.assertTrue(result["freshness"]["freshness_pass"])
        self.assertEqual("research_only", result["historical_simulation_grade"])
        self.assertFalse(any(result["claims"].values()))
        self.assertFalse(result["paid_data_required"])

    def test_downloader_is_pinned_and_uses_container_copy_not_host_mounts(self):
        root = Path(__file__).resolve().parents[1]
        requirements = (root / "config/free_data_requirements.lock").read_text()
        launcher = (root / "scripts/acquire_free_etf_snapshot.py").read_text()
        self.assertIn("yfinance==1.5.2", requirements)
        self.assertIn('"podman", "cp"', launcher)
        self.assertNotIn('"--volume"', launcher)
        self.assertNotIn('"-v"', launcher)


if __name__ == "__main__":
    unittest.main()
