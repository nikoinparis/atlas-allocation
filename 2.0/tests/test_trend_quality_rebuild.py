import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/rebuild_trend_quality_strategy.py"
spec = importlib.util.spec_from_file_location("rebuild_trend_quality_strategy", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TrendQualityRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = module.build()

    def test_all_five_signal_lags_reconcile(self):
        self.assertEqual(5, len(self.result["signal_lag_audits"]))
        self.assertTrue(self.result["audit"]["independent_signal_lag_checks_pass"])

    def test_rebuild_has_no_unpriced_exposure(self):
        self.assertTrue(self.result["audit"]["unpriced_exposure_pass"])
        self.assertEqual(0, self.result["audit"]["unpriced_exposure_events"])

    def test_weights_and_costs_reconcile(self):
        self.assertTrue(self.result["audit"]["fully_invested_pass"])
        self.assertTrue(self.result["audit"]["cost_identity_pass"])

    def test_saved_position_drift_is_detected_and_not_hidden(self):
        self.assertFalse(self.result["audit"]["current_signal_inputs_reproduce_saved_positions"])
        self.assertGreater(self.result["audit"]["saved_position_mismatch_weeks"], 0)

    def test_rebuild_remains_research_only(self):
        self.assertEqual("research_only_not_promoted", self.result["status"])
        self.assertEqual("2026-08-14", self.result["forward_lock"]["first_untouched_week_end"])


if __name__ == "__main__":
    unittest.main()
