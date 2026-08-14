import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts.run_guarded_weekly_forward_cycle import (
    WeeklyCycleError,
    acquire_lock,
    latest_closed_decision_week,
    release_lock,
)


class GuardedWeeklyForwardCycleTests(unittest.TestCase):
    def test_friday_cutoff_is_fail_closed(self):
        before = datetime(2026, 8, 14, 20, 59, tzinfo=timezone.utc)
        after = datetime(2026, 8, 14, 21, 0, tzinfo=timezone.utc)
        self.assertEqual("2026-08-07", latest_closed_decision_week(before).isoformat())
        self.assertEqual("2026-08-14", latest_closed_decision_week(after).isoformat())

    def test_cycle_lock_rejects_concurrent_run(self):
        with tempfile.TemporaryDirectory() as name:
            temporary = Path(name)
            with patch("scripts.run_guarded_weekly_forward_cycle.OUTPUT", temporary), patch(
                "scripts.run_guarded_weekly_forward_cycle.LOCK_PATH", temporary / ".cycle.lock"
            ):
                descriptor = acquire_lock()
                try:
                    with self.assertRaises(WeeklyCycleError):
                        acquire_lock()
                finally:
                    release_lock(descriptor)

    def test_completed_cycle_keeps_execution_disabled(self):
        root = Path(__file__).resolve().parents[1]
        latest = root / "evidence/weekly_forward_cycles/latest_result.json"
        result = json.loads(latest.read_text())
        self.assertEqual("complete", result["status"])
        self.assertFalse(result["execution_enabled"])
        self.assertIsNone(result["broker_connection"])
        self.assertEqual(0, result["forward_status"]["observed_weeks"])


if __name__ == "__main__":
    unittest.main()
