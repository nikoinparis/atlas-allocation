import csv
import hashlib
import json
import unittest
from pathlib import Path


class CovariancePortfoliosBatch06Tests(unittest.TestCase):
    def test_declared_methods_and_causal_allocations(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/covariance_portfolios_batch_06"
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(6, result["primary_method_count"])
        self.assertEqual(45, result["sensitivity_configuration_count"])
        with (output / "allocation_history.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows)
        self.assertTrue(all(row["causal_history_pass"] == "True" for row in rows))
        self.assertTrue(all(float(row["trend_v4_weight"]) <= 0.8 + 1e-12 for row in rows))
        self.assertTrue(all(float(row["defensive_weight"]) <= 0.8 + 1e-12 for row in rows))

    def test_accounting_registry_and_artifact_hashes(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/covariance_portfolios_batch_06"
        result = json.loads((output / "result.json").read_text())
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        with (output / "method_scoreboard.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(12, len(rows))
        self.assertTrue(all(row["fully_invested_pass"] == "True" for row in rows))
        self.assertTrue(all(int(row["unpriced_exposure_events"]) == 0 for row in rows))
        self.assertTrue(all(float(row["maximum_realized_asset_weight"]) <= 0.35 + 1e-12 for row in rows))
        registry = json.loads((root / "research_registry/portfolio_candidates.json").read_text())
        self.assertEqual(1, registry["candidate_count"])
        candidate = registry["candidates"][0]
        self.assertFalse(candidate["final"])
        self.assertFalse(candidate["approved_for_live_trading"])

    def test_duplicate_methods_are_disclosed(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/covariance_portfolios_batch_06/result.json").read_text())
        pairs = {(row["left"], row["right"]) for row in result["duplicate_primary_method_pairs"]}
        self.assertIn(("inverse_volatility", "maximum_diversification"), pairs)


if __name__ == "__main__":
    unittest.main()
