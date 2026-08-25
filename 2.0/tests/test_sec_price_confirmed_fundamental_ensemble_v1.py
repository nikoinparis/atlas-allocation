from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_sec_price_confirmed_fundamental_ensemble_v1.py"
SPEC = importlib.util.spec_from_file_location("price_confirmed", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class PriceConfirmedFundamentalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config/sec_price_confirmed_fundamental_ensemble_v1.json").read_text())

    def test_latest_score_uses_nothing_after_decision(self) -> None:
        index = pd.date_range("2025-01-03", periods=6, freq="W-FRI")
        signal = pd.DataFrame({"a": range(6)}, index=index, dtype=float)
        ciks = pd.Series(["a"])
        before = module.latest_price_score(signal, pd.Timestamp("2025-01-18"), ciks)
        changed = signal.copy()
        changed.loc[changed.index >= pd.Timestamp("2025-01-24"), "a"] = 999.0
        after = module.latest_price_score(changed, pd.Timestamp("2025-01-18"), ciks)
        pd.testing.assert_series_equal(before, after)

    def test_control_has_zero_price_weight(self) -> None:
        control = self.config["candidate_specs"][0]
        self.assertEqual(control["name"], "fundamental_control")
        self.assertEqual(float(control["price_weight"]), 0.0)

    def test_no_ticker_specific_rules_and_live_disabled(self) -> None:
        text = json.dumps(self.config).lower()
        self.assertNotIn("micron", text)
        self.assertNotIn('"mu"', text)
        self.assertFalse(bool(self.config["strategy_promotion_authorized"]))
        self.assertFalse(bool(self.config["live_trading_enabled"]))

    def test_price_signal_delay_is_at_least_one_week(self) -> None:
        self.assertGreaterEqual(int(self.config["price_signals"]["full_observation_delay_weeks"]), 1)


if __name__ == "__main__":
    unittest.main()
