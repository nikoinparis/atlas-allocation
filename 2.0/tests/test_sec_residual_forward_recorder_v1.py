import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import record_sec_residual_controlled_sleeve_forward_v1 as recorder
from scripts.record_sec_residual_controlled_sleeve_forward_v1 import (
    ForwardEvidenceError,
    blend_weights,
    levered_return,
    normalize_weights,
    observed_in_weekly_window,
    turnover,
)


class SECResidualForwardRecorderTests(unittest.TestCase):
    def test_weekly_window_is_friday_2100_utc_and_fail_closed(self):
        self.assertFalse(observed_in_weekly_window("2026-08-28T20:59:59Z", "2026-08-28"))
        self.assertTrue(observed_in_weekly_window("2026-08-28T21:00:00Z", "2026-08-28"))
        self.assertTrue(observed_in_weekly_window("2026-09-04T20:59:59Z", "2026-08-28"))
        self.assertFalse(observed_in_weekly_window("2026-09-04T21:00:00Z", "2026-08-28"))
        with self.assertRaises(ForwardEvidenceError):
            observed_in_weekly_window("2026-08-29T21:00:00Z", "2026-08-29")

    def test_weights_are_long_only_and_fully_invested(self):
        self.assertEqual({"A": 0.6, "B": 0.4}, normalize_weights({"B": 0.4, "A": 0.6}, label="test"))
        with self.assertRaises(ForwardEvidenceError):
            normalize_weights({"A": 0.9}, label="test")
        with self.assertRaises(ForwardEvidenceError):
            normalize_weights({"A": 1.1, "B": -0.1}, label="test")

    def test_fixed_80_20_blend_and_turnover(self):
        blended = blend_weights({"A": 1.0}, {"B": 1.0}, 0.2)
        self.assertAlmostEqual(0.8, blended["A"])
        self.assertAlmostEqual(0.2, blended["B"])
        self.assertAlmostEqual(1.0, turnover({"cash::USD": 1.0}, {"A": 1.0}))

    def test_leverage_charges_only_the_borrowed_fraction(self):
        self.assertAlmostEqual(1.25 * 0.02 - 0.25 * 0.08 / 52.0, levered_return(0.02, 1.25, 0.08))

    def test_decision_and_observation_are_computed_from_hashed_source_packets(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            manifest = root / "source.json"
            manifest.write_text('{"snapshot":"fixed"}\n')
            manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
            protocol_file = root / "protocol.json"
            protocol_file.write_text("{}\n")
            decisions = root / "decisions.jsonl"
            observations = root / "observations.jsonl"
            protocol = {
                "protocol_version": "test_v1",
                "first_eligible_decision_date": "2026-08-28",
                "first_eligible_realization_date": "2026-09-04",
                "residual_sleeve_weight": 0.2,
                "cost_bps_per_unit_turnover": 50,
                "financing_rates": [0.05, 0.08],
            }
            anchor = {
                "first_decision_prior_control_weights": {"cash::USD": 1.0},
                "first_decision_prior_residual_weights": {"cash::USD": 1.0},
            }
            decision_basis = {
                "packet_type": "sec_residual_forward_decision_v1",
                "protocol_version": "test_v1",
                "decision_date": "2026-08-28",
                "observed_at_utc": "2026-08-28T21:30:00Z",
                "source_data_through": "2026-08-28",
                "snapshot_id": "decision-1",
                "source_manifest": "source.json",
                "source_manifest_sha256": manifest_hash,
                "control_target_weights": {"A": 1.0},
                "residual_target_weights": {"B": 1.0},
            }
            decision_packet = {**decision_basis, "packet_sha256": recorder.sha256_value(decision_basis)}
            observation_basis = {
                "packet_type": "sec_residual_forward_observation_v1",
                "protocol_version": "test_v1",
                "realization_date": "2026-09-04",
                "observed_at_utc": "2026-09-04T21:30:00Z",
                "source_data_through": "2026-09-04",
                "snapshot_id": "observation-1",
                "source_manifest": "source.json",
                "source_manifest_sha256": manifest_hash,
                "asset_total_returns": {"A": 0.01, "B": 0.03},
            }
            observation_packet = {**observation_basis, "packet_sha256": recorder.sha256_value(observation_basis)}
            with patch.object(recorder, "ROOT", root), patch.object(recorder, "PROTOCOL_PATH", protocol_file), patch.object(recorder, "DECISIONS_PATH", decisions), patch.object(recorder, "OBSERVATIONS_PATH", observations):
                decision = recorder.append_decision(protocol, anchor, decision_packet)
                observation = recorder.append_observation(protocol, observation_packet)
            self.assertAlmostEqual(1.0, decision["control_turnover"])
            self.assertAlmostEqual(1.0, decision["residual_turnover"])
            expected = 0.8 * (0.01 - 0.005) + 0.2 * (0.03 - 0.005)
            self.assertAlmostEqual(expected, observation["path_net_returns"]["unlevered_1.00x"])
            self.assertAlmostEqual(
                1.25 * expected - 0.25 * 0.08 / 52.0,
                observation["path_net_returns"]["levered_1.25x_8pct_financing"],
            )

    def test_late_observation_packet_is_rejected(self):
        packet_time = "2026-09-11T21:00:00Z"
        self.assertFalse(observed_in_weekly_window(packet_time, "2026-09-04"))


if __name__ == "__main__":
    unittest.main()
