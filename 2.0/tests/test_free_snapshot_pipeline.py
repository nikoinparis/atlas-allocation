import csv
import hashlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.systematic_trader.point_in_time import monthly_rebalance_dates
from src.systematic_trader.weekly_data import friday_label, prepare_weekly_adjusted_prices, weekly_log_returns


class WeeklyPreparationTests(unittest.TestCase):
    def test_daily_rows_use_last_observation_in_completed_friday_week(self):
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "prices.csv"
            fields = ["observation_date", "security_id", "ticker", "adjusted_close"]
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows([
                    {"observation_date": "2026-08-03", "security_id": "a", "ticker": "AAA", "adjusted_close": 10},
                    {"observation_date": "2026-08-07", "security_id": "a", "ticker": "AAA", "adjusted_close": 11},
                    {"observation_date": "2026-08-10", "security_id": "a", "ticker": "AAA", "adjusted_close": 12},
                ])
            dates, prices, audit = prepare_weekly_adjusted_prices(
                path, observed_at_date=date(2026, 8, 8), start_date=date(2026, 8, 1), expected_symbols=["AAA"]
            )
            self.assertEqual(["2026-08-07"], dates)
            self.assertEqual(11.0, prices["2026-08-07"]["AAA"])
            self.assertEqual(1, audit["completed_weeks"])

    def test_weekly_log_return_requires_consecutive_prices(self):
        dates = ["2026-07-31", "2026-08-07"]
        prices = {dates[0]: {"AAA": 10.0}, dates[1]: {"AAA": 11.0}}
        returns = weekly_log_returns(dates, ["AAA"], prices)
        self.assertIsNone(returns[dates[0]]["AAA"])
        self.assertGreater(returns[dates[1]]["AAA"], 0.0)

    def test_sample_endpoint_is_not_forced_into_live_monthly_rebalance(self):
        dates = ["2026-07-24", "2026-07-31", "2026-08-07"]
        artifact = monthly_rebalance_dates(dates)
        causal = monthly_rebalance_dates(dates, include_sample_endpoint=False)
        self.assertIn("2026-08-07", artifact)
        self.assertNotIn("2026-08-07", causal)
        self.assertIn("2026-07-31", causal)


class CheckedInFreePipelineTests(unittest.TestCase):
    def test_pipeline_is_non_trading_and_forward_test_has_not_started(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/free_snapshot_research_pipeline/result.json").read_text())
        target = result["paper_target"]
        self.assertFalse(target["execution_enabled"])
        self.assertIsNone(target["broker_connection"])
        self.assertFalse(target["decision_is_monthly_rebalance"])
        self.assertEqual("waiting_for_next_scheduled_rebalance", target["activation_status"])
        self.assertEqual(0, result["forward_validation"]["untouched_returns_available"])
        self.assertTrue(result["accounting"]["unpriced_exposure_pass"])

    def test_derived_files_match_their_manifest(self):
        root = Path(__file__).resolve().parents[1]
        result = json.loads((root / "evidence/free_snapshot_research_pipeline/result.json").read_text())
        manifest_path = Path(result["derived_manifest"])
        manifest = json.loads(manifest_path.read_text())
        for name, record in manifest["files"].items():
            path = manifest_path.parent / name
            self.assertEqual(record["bytes"], path.stat().st_size)
            self.assertEqual(record["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
