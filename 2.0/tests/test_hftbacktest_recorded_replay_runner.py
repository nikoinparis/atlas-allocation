import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "hft_replay_runner", SCRIPTS / "run_hftbacktest_recorded_replay.py"
)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class HftbacktestRecordedReplayRunnerTests(unittest.TestCase):
    def test_fixture_has_pinned_recorded_rows_and_retains_inversion(self):
        rows = module.fixture_rows()
        self.assertEqual(23, len(rows))
        self.assertEqual(list(range(1, 24)), [int(row["source_seq"]) for row in rows])
        self.assertEqual(1, module.timestamp_inversions(rows))
        self.assertTrue(all(float(row["px"]) > 0 for row in rows))

    def test_injection_and_replay_are_offline_and_named_volume_only(self):
        command = module.injection_command("named-volume")
        self.assertIn("--network=none", command)
        self.assertIn("named-volume:/work:rw", command)
        self.assertNotIn("/Users/", " ".join(command))

    def test_metrics_parser_rejects_missing_or_nonfinite_fields(self):
        valid = (
            'REPLAY_METRICS {"source_rows":23,"engine_events":42,'
            '"timestamp_inversions":1,"market_trades":4,"best_bid":22183.4,'
            '"best_ask":22194.3,"best_bid_qty":0.014,"best_ask_qty":0.27,'
            '"safe_order_qty":0.1,"oversized_order_qty":0.5,"simulated_fills":0}'
        )
        parsed = module.parse_metrics(valid)
        self.assertEqual(23, parsed["source_rows"])
        with self.assertRaises(ValueError):
            module.parse_metrics("test result: ok")
        broken = valid.replace('"best_ask":22194.3', '"best_ask":NaN')
        with self.assertRaises(ValueError):
            module.parse_metrics(broken)

    def test_recorded_result_and_report_preserve_scope(self):
        result = json.loads(
            (ROOT / "evidence/hftbacktest_recorded_replay/result.json").read_text(encoding="utf-8")
        )
        self.assertEqual("completed", result["status"])
        self.assertEqual(23, result["fixture_rows"])
        self.assertEqual(42, result["metrics"]["engine_events"])
        self.assertEqual(0, result["metrics"]["simulated_fills"])
        self.assertEqual("disabled", result["replay_network"])
        self.assertTrue(result["lockfile_matches_prior_gate"])

        report = (ROOT / "evidence/hftbacktest_recorded_replay/report.md").read_text(encoding="utf-8")
        for phrase in ("not a strategy backtest", "complete initial order-book snapshot", "still not approved"):
            self.assertIn(phrase, report)

    def test_living_project_history_records_truth_and_update_protocol(self):
        history = (ROOT / "PROJECT_HISTORY.md").read_text(encoding="utf-8")
        for phrase in (
            "Repositories whose code has genuinely executed: **13**",
            "Repositories or strategies proven durably profitable: **0**",
            "Step 12 — Replay pinned recorded order-book events",
            "Update protocol for future work",
        ):
            self.assertIn(phrase, history)


if __name__ == "__main__":
    unittest.main()
