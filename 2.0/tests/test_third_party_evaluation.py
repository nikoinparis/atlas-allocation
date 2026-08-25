import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "third_party_evaluation/runner.py"
CONTRACT_PATH = ROOT / "third_party_evaluation/adapters/kronos_feature_contract.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUNNER = load_module("third_party_evaluation_runner", RUNNER_PATH)
CONTRACT = load_module("kronos_contract_test", CONTRACT_PATH)


class ThirdPartyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.manifest = RUNNER.load_manifest(RUNNER.DEFAULT_MANIFEST)

    def test_inventory_is_complete_and_github_sources_are_pinned(self):
        self.assertEqual(
            {tool["id"] for tool in self.manifest["tools"]},
            {"kronos", "openbb", "scrapling", "nautilus_trader", "everything_claude_code", "das_replay", "trading_systems"},
        )
        for tool in self.manifest["tools"]:
            if tool["kind"] == "github":
                self.assertRegex(tool["commit"], r"^[0-9a-f]{40}$")

    def test_policy_and_results_fail_closed(self):
        self.assertFalse(self.manifest["policy"]["host_install_allowed"])
        self.assertFalse(self.manifest["policy"]["core_import_allowed"])
        self.assertFalse(self.manifest["policy"]["live_trading_allowed"])
        rows = RUNNER.evaluate(self.manifest, live=False)
        self.assertTrue(all(not row["approved_for_core_import"] for row in rows))
        self.assertTrue(all(not row["approved_for_live_trading"] for row in rows))
        unresolved = next(row for row in rows if row["id"] == "trading_systems")
        self.assertEqual(unresolved["probe"]["source_status"], "blocked_missing_exact_url")

    def test_offline_report_writes_one_raw_result_per_tool(self):
        rows = RUNNER.evaluate(self.manifest, live=False)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            RUNNER._write_report(output, RUNNER.DEFAULT_MANIFEST, self.manifest, rows, False)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["summary"]["tools_declared"], 7)
            self.assertEqual(report["summary"]["core_imports_approved"], 0)
            self.assertEqual(len(list((output / "raw").glob("*.json"))), 7)

    def test_kronos_contract_materializes_bounded_features(self):
        result = CONTRACT.smoke_fixture()
        self.assertEqual(result["contract_version"], "kronos_feature_contract_v1")
        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["horizon_bars"], 2)
        self.assertIn("no_direct_order_generation", result["usage_constraints"])
        self.assertGreaterEqual(result["features"]["positive_path_fraction"], 0.0)
        self.assertLessEqual(result["features"]["positive_path_fraction"], 1.0)

    def test_kronos_contract_rejects_lookahead_timestamp(self):
        history = [{"timestamp": "2026-01-02T16:00:00+00:00", "open": 1, "high": 2, "low": 1, "close": 2}]
        forecast = [[{"timestamp": "2026-01-02T16:00:00+00:00", "open": 2, "high": 2, "low": 1, "close": 1}]]
        with self.assertRaisesRegex(ValueError, "strictly after history"):
            CONTRACT.materialize_forecast_features(
                history,
                forecast,
                source_commit="a" * 40,
                model_revision="b" * 40,
                tokenizer_revision="c" * 40,
                generated_at="2026-01-02T16:00:01+00:00",
            )

    def test_license_detection(self):
        self.assertEqual(RUNNER.detect_license("MIT License\nPermission is hereby granted, free of charge"), "MIT")
        self.assertEqual(RUNNER.detect_license("GNU AFFERO GENERAL PUBLIC LICENSE Version 3"), "AGPL-3.0")
        self.assertEqual(RUNNER.detect_license("GNU LESSER GENERAL PUBLIC LICENSE Version 3"), "LGPL-3.0")
        self.assertEqual(RUNNER.detect_license("BSD 3-Clause License"), "BSD-3-Clause")


if __name__ == "__main__":
    unittest.main()
