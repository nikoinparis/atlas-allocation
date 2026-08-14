import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.systematic_trader.data_vintage import DataVintageError, SnapshotStore


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class DataVintageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bundle = self.root / "bundle"
        self.bundle.mkdir()
        known = "2020-01-10T20:00:00+00:00"
        write_csv(
            self.bundle / "prices.csv",
            ["observation_date", "security_id", "ticker", "adjusted_close", "knowledge_at_utc", "source_revision"],
            [{"observation_date": "2020-01-10", "security_id": "perm:1", "ticker": "AAA", "adjusted_close": 10, "knowledge_at_utc": known, "source_revision": "v1"}],
        )
        write_csv(
            self.bundle / "universe_membership.csv",
            ["security_id", "ticker", "universe", "effective_from", "effective_to", "knowledge_at_utc", "source_revision"],
            [{"security_id": "perm:1", "ticker": "AAA", "universe": "TEST", "effective_from": "2019-01-01", "effective_to": "", "knowledge_at_utc": known, "source_revision": "v1"}],
        )
        write_csv(
            self.bundle / "security_master.csv",
            ["security_id", "permanent_id_source", "ticker", "first_observed_date", "last_observed_date", "delisting_date", "knowledge_at_utc"],
            [{"security_id": "perm:1", "permanent_id_source": "test", "ticker": "AAA", "first_observed_date": "2019-01-01", "last_observed_date": "2020-01-10", "delisting_date": "", "knowledge_at_utc": known}],
        )
        write_csv(
            self.bundle / "corporate_actions.csv",
            ["security_id", "ticker", "event_date", "action_type", "amount", "knowledge_at_utc", "source_revision"],
            [{"security_id": "perm:1", "ticker": "AAA", "event_date": "2020-01-10", "action_type": "distribution", "amount": 0.1, "knowledge_at_utc": known, "source_revision": "v1"}],
        )
        write_csv(
            self.bundle / "delistings.csv",
            ["security_id", "ticker", "delisting_date", "delisting_return", "reason", "knowledge_at_utc", "source_revision"],
            [],
        )
        self.files = {path.name: path for path in self.bundle.glob("*.csv")}
        self.descriptor = {
            "provider": "test_vendor",
            "dataset_kind": "point_in_time_market_bundle",
            "observed_at_utc": known,
            "observed_at_basis": "test export completion",
            "source_uri": "test://export/v1",
            "source_license": "test",
            "revision_policy": "retain every vintage",
            "publication_lag_policy": "row knowledge timestamps",
            "claims": {
                "point_in_time_prices": True,
                "point_in_time_universe": True,
                "permanent_security_ids": True,
                "corporate_actions": True,
                "delistings": True,
                "vintage_revisions": True,
            },
        }
        self.store = SnapshotStore(self.root / "store")

    def tearDown(self):
        self.temporary.cleanup()

    def test_content_addressed_ingestion_is_idempotent(self):
        first = self.store.ingest(self.files, self.descriptor)
        second = self.store.ingest(self.files, self.descriptor)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(1, len(self.store.manifests()))
        self.assertTrue(self.store.verify(first["snapshot_id"]))

    def test_snapshot_cannot_be_used_before_it_was_known(self):
        self.store.ingest(self.files, self.descriptor)
        with self.assertRaises(DataVintageError):
            self.store.select("2020-01-09T20:00:00+00:00")
        selected = self.store.select("2020-01-10T20:00:00+00:00", required_claims=("delistings",))
        self.assertTrue(selected.snapshot_id)

    def test_integrity_verification_detects_tampering(self):
        manifest = self.store.ingest(self.files, self.descriptor)
        target = self.store.root / manifest["snapshot_id"] / "payload/prices.csv"
        target.write_text(target.read_text() + "\n", encoding="utf-8")
        with self.assertRaises(DataVintageError):
            self.store.verify(manifest["snapshot_id"])

    def test_claim_requires_its_schema(self):
        incomplete = dict(self.files)
        incomplete.pop("universe_membership.csv")
        with self.assertRaises(DataVintageError):
            self.store.ingest(incomplete, self.descriptor)

    def test_future_knowledge_inside_export_is_rejected(self):
        with (self.bundle / "prices.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["knowledge_at_utc"] = "2020-01-11T20:00:00+00:00"
        write_csv(self.bundle / "prices.csv", list(rows[0]), rows)
        with self.assertRaises(DataVintageError):
            self.store.ingest(self.files, self.descriptor)


class CheckedInLegacySnapshotTests(unittest.TestCase):
    def test_legacy_snapshot_is_quarantined_as_research_only(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/data_vintage_store/result.json").read_text())
        self.assertEqual("research_only", result["historical_simulation_grade"])
        self.assertTrue(result["historical_lookahead_rejection_pass"])
        self.assertTrue(result["production_claim_rejection_pass"])
        self.assertTrue(result["snapshot_integrity_pass"])


if __name__ == "__main__":
    unittest.main()
