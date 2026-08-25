import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import scripts.acquire_sec_broad_tiingo_batch_v2 as subject


class SECBroadTiingoBatchTests(unittest.TestCase):
    def test_combined_queue_prioritizes_decision_coverage_not_source_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = root / "base.csv"
            supplement = root / "supplement.csv"
            pd.DataFrame([
                {
                    "cik10": "0000000001", "sec_company_name": "BASE",
                    "recent_decision_rows": 4, "last_eligible_decision": "2024-01-01",
                },
            ]).to_csv(base, index=False)
            pd.DataFrame([
                {
                    "cik10": "0000000002", "sec_company_name": "SUPPLEMENT",
                    "recent_decision_rows": 12, "last_eligible_decision": "2026-01-01",
                },
            ]).to_csv(supplement, index=False)

            with patch.object(subject, "CANDIDATES", base), patch.object(subject, "SUPPLEMENT", supplement):
                result = subject.load_candidates()

            self.assertEqual(result["cik10"].tolist(), ["0000000002", "0000000001"])


if __name__ == "__main__":
    unittest.main()
