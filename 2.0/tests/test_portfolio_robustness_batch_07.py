import csv
import hashlib
import json
import unittest
from pathlib import Path


class PortfolioRobustnessBatch07Tests(unittest.TestCase):
    def test_all_declared_stress_layers_have_evidence(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/portfolio_robustness_batch_07"
        result = json.loads((output / "result.json").read_text())
        self.assertEqual(20000, result["rules_fixed_before_results"]["bootstrap"]["samples"])
        with (output / "input_stress.csv").open(encoding="utf-8", newline="") as handle:
            inputs = list(csv.DictReader(handle))
        self.assertEqual(7, len(inputs))
        self.assertIn("delay_13_weeks", {row["scenario"] for row in inputs})
        with (output / "rolling_windows.csv").open(encoding="utf-8", newline="") as handle:
            self.assertGreaterEqual(len(list(csv.DictReader(handle))), 10)

    def test_artifacts_accounting_and_failure_fallbacks(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/portfolio_robustness_batch_07"
        result = json.loads((output / "result.json").read_text())
        for name, record in result["artifacts"].items():
            path = output / name
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(record["bytes"], path.stat().st_size)
        with (output / "input_stress.csv").open(encoding="utf-8", newline="") as handle:
            inputs = list(csv.DictReader(handle))
        self.assertTrue(all(row["fully_invested_pass"] == "True" for row in inputs))
        self.assertTrue(all(int(row["unpriced_exposure_events"]) == 0 for row in inputs))
        with (output / "allocator_failures.csv").open(encoding="utf-8", newline="") as handle:
            failures = list(csv.DictReader(handle))
        self.assertEqual(4, len(failures))
        self.assertTrue(all(row["pass"] == "True" for row in failures))

    def test_candidate_never_becomes_final_or_live_approved(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/portfolio_robustness_batch_07/result.json").read_text())
        registry = json.loads((root / "research_registry/portfolio_candidates.json").read_text())
        candidate = registry["candidates"][0]
        self.assertFalse(candidate["final"])
        self.assertFalse(candidate["approved_for_live_trading"])
        if result["robustness_pass"]:
            manifest = json.loads((root / result["frozen_manifest"]).read_text())
            self.assertLess(
                candidate["forward_clock"]["observed_weeks"],
                candidate["forward_clock"]["required_weeks"],
            )
            self.assertFalse(manifest["final"])
            self.assertFalse(manifest["approved_for_live_trading"])


if __name__ == "__main__":
    unittest.main()
