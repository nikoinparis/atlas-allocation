import json
import tempfile
import unittest
from pathlib import Path

from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError,
    append_record,
    read_and_verify_log,
)


class ForwardEvidenceTests(unittest.TestCase):
    def test_append_chain_and_duplicate_rejection(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "observations.jsonl"
            first = append_record(
                path, {"realization_date": "2026-08-21", "net_return": 0.01},
                date_field="realization_date", first_eligible_date="2026-08-21",
            )
            second = append_record(
                path, {"realization_date": "2026-08-28", "net_return": -0.01},
                date_field="realization_date", first_eligible_date="2026-08-21",
            )
            self.assertEqual(first["record_hash"], second["previous_record_hash"])
            self.assertEqual(2, len(read_and_verify_log(
                path, date_field="realization_date", first_eligible_date="2026-08-21"
            )))
            with self.assertRaises(ForwardEvidenceError):
                append_record(
                    path, {"realization_date": "2026-08-28", "net_return": 0.02},
                    date_field="realization_date", first_eligible_date="2026-08-21",
                )

    def test_prefreeze_and_out_of_order_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "decisions.jsonl"
            with self.assertRaises(ForwardEvidenceError):
                append_record(
                    path, {"decision_date": "2026-08-07"},
                    date_field="decision_date", first_eligible_date="2026-08-14",
                )
            append_record(
                path, {"decision_date": "2026-08-21"},
                date_field="decision_date", first_eligible_date="2026-08-14",
            )
            with self.assertRaises(ForwardEvidenceError):
                append_record(
                    path, {"decision_date": "2026-08-14"},
                    date_field="decision_date", first_eligible_date="2026-08-14",
                )

    def test_tampering_breaks_verification(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "observations.jsonl"
            append_record(
                path, {"realization_date": "2026-08-21", "net_return": 0.01},
                date_field="realization_date", first_eligible_date="2026-08-21",
            )
            record = json.loads(path.read_text())
            record["net_return"] = 0.50
            path.write_text(json.dumps(record) + "\n")
            with self.assertRaises(ForwardEvidenceError):
                read_and_verify_log(
                    path, date_field="realization_date", first_eligible_date="2026-08-21"
                )


if __name__ == "__main__":
    unittest.main()
