import json
import unittest
from copy import deepcopy
from pathlib import Path

from systematic_trader.adapters.tradingview import parse_recorded_screener_fixture


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evidence/tradingview_adapter/fixtures/america_scan_2026-08-08.json"


class TradingViewAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_recorded_response_is_strictly_parsed_but_not_point_in_time_eligible(self):
        snapshot = parse_recorded_screener_fixture(self.fixture)
        self.assertEqual(3, len(snapshot.rows))
        self.assertFalse(snapshot.point_in_time_eligible)
        self.assertIn("no_per_row", snapshot.rejection_reason)
        spy = next(row for row in snapshot.rows if row.symbol == "AMEX:SPY")
        self.assertEqual(("market_cap_basic",), spy.missing_columns)
        self.assertEqual("delayed_streaming_900", spy.update_mode)

    def test_column_misalignment_is_rejected(self):
        malformed = deepcopy(self.fixture)
        malformed["response"]["data"][0]["d"].pop()
        with self.assertRaisesRegex(ValueError, "column/value length mismatch"):
            parse_recorded_screener_fixture(malformed)

    def test_nonfinite_value_is_rejected(self):
        malformed = deepcopy(self.fixture)
        malformed["response"]["data"][0]["d"][1] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            parse_recorded_screener_fixture(malformed)

    def test_duplicate_symbol_is_rejected(self):
        malformed = deepcopy(self.fixture)
        malformed["response"]["data"][1]["s"] = "NASDAQ:AAPL"
        with self.assertRaisesRegex(ValueError, "duplicate symbol"):
            parse_recorded_screener_fixture(malformed)


if __name__ == "__main__":
    unittest.main()
