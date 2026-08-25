from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_sec_form4_dynamic_overlay_v1 as audit


class DynamicOverlayAuditTests(unittest.TestCase):
    def test_completed_rolling_windows_exclude_incomplete_prefix(self) -> None:
        frame = pd.DataFrame(
            {
                "candidate": [0.01, 0.01, 0.01, -0.02],
                "control": [0.00, 0.00, 0.00, 0.02],
            },
            index=pd.date_range("2026-01-02", periods=4, freq="W-FRI"),
        )
        share, completed = audit.completed_rolling_outperformance(frame, 3)
        self.assertEqual(completed, 2)
        self.assertEqual(share, 0.5)

    def test_required_gate_list_does_not_ignore_failed_boolean(self) -> None:
        values = {"screen": True, "bootstrap": False, "diagnostic_probability": 0.99}
        self.assertFalse(audit.required_gates_pass(values, ["screen", "bootstrap"]))
        self.assertTrue(audit.required_gates_pass({"screen": True}, ["screen"]))


if __name__ == "__main__":
    unittest.main()
