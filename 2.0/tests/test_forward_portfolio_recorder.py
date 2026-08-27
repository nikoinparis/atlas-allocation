import hashlib
import json
import unittest
from pathlib import Path


class ForwardPortfolioRecorderTests(unittest.TestCase):
    def test_current_state_matches_append_only_forward_logs(self):
        root = Path(__file__).resolve().parents[1]
        output = root / "evidence/forward_covariance_minimum_variance_v1"
        status = json.loads((output / "status.json").read_text())
        anchor = json.loads((output / "anchor.json").read_text())
        self.assertEqual("2026-08-07", anchor["anchor_decision_date"])
        decision_count = sum(1 for line in (output / "decisions.jsonl").read_text().splitlines() if line)
        observation_count = sum(1 for line in (output / "observations.jsonl").read_text().splitlines() if line)
        self.assertEqual(decision_count, status["saved_decisions"])
        self.assertEqual(observation_count, status["observed_weeks"])
        self.assertEqual(status["required_weeks"] - observation_count, status["remaining_weeks"])
        self.assertFalse(status["clock_complete"])
        self.assertFalse(status["execution_enabled"])

    def test_protocol_and_registry_preserve_non_final_status(self):
        root = Path(__file__).resolve().parents[1]
        protocol_path = root / "config/forward/covariance_minimum_variance_v1.json"
        protocol = json.loads(protocol_path.read_text())
        self.assertEqual("2026-08-14", protocol["first_eligible_decision_date"])
        self.assertEqual("2026-08-21", protocol["first_eligible_realization_date"])
        manifest_path = root / protocol["portfolio_manifest"]
        self.assertEqual(
            protocol["portfolio_manifest_sha256"],
            hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        )
        registry = json.loads((root / "research_registry/portfolio_candidates.json").read_text())
        candidate = registry["candidates"][0]
        status = json.loads((root / candidate["forward_clock"]["status_file"]).read_text())
        self.assertEqual(status["observed_weeks"], candidate["forward_clock"]["observed_weeks"])
        self.assertLess(candidate["forward_clock"]["observed_weeks"], candidate["forward_clock"]["required_weeks"])
        self.assertFalse(candidate["final"])
        self.assertFalse(candidate["approved_for_live_trading"])


if __name__ == "__main__":
    unittest.main()
