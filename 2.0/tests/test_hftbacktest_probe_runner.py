import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("hft_probe_runner", SCRIPTS / "run_hftbacktest_behavioral_probe.py")
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class HftbacktestProbeRunnerTests(unittest.TestCase):
    def test_injection_is_offline_and_uses_only_named_volume(self):
        command = module.injection_command("named-volume")
        self.assertIn("--network=none", command)
        self.assertIn("named-volume:/work:rw", command)
        self.assertNotIn("/Users/", " ".join(command))

    def test_probe_covers_required_execution_boundaries(self):
        source = module.PROBE.read_text(encoding="utf-8")
        for phrase in (
            "partial_fill_exchange", "cancellation_processed", "fees_cash_position",
            "risk_adverse_queue", "technical_rejection", "accepts_overfill", "nonfinite_fee",
        ):
            self.assertIn(phrase, source)

    def test_recorded_result_and_report_preserve_conditional_outcome(self):
        result = json.loads(
            (ROOT / "evidence/hftbacktest_behavioral/result.json").read_text(encoding="utf-8")
        )
        self.assertEqual("completed", result["status"])
        self.assertEqual(8, result["tests_passed"])
        self.assertEqual(0, result["tests_failed"])
        self.assertTrue(result["lockfile_matches_prior_gate"])
        self.assertEqual("disabled", result["probe_network"])
        self.assertFalse(result["host_mounts"])

        report = (ROOT / "evidence/hftbacktest_behavioral/report.md").read_text(encoding="utf-8")
        for phrase in ("conditional sandbox candidate", "larger than the order quantity", "non-finite fee"):
            self.assertIn(phrase, report)


if __name__ == "__main__":
    unittest.main()
