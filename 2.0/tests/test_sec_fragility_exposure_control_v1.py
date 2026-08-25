from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/sec_fragility_exposure_control_v1.json").read_text())
SPEC = importlib.util.spec_from_file_location("exposure_control", ROOT / "scripts/run_sec_fragility_exposure_control_v1.py")
module = importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(module)


class FragilityExposureControlTests(unittest.TestCase):
    def setUp(self) -> None:
        index = pd.date_range("2023-01-06", periods=90, freq="W-FRI", tz="UTC")
        self.base = pd.Series(0.004 + 0.02 * np.sin(np.arange(len(index)) / 4), index=index)
        self.risk_on = pd.Series(np.arange(len(index)) % 3 != 0, index=index)

    def test_candidate_count_is_predeclared(self) -> None:
        count = len(CONFIG["fixed_rules"]) + len(CONFIG["volatility_target_rules"]) + len(CONFIG["fractional_kelly_rules"]) + len(CONFIG["fragility_tier_rules"])
        self.assertEqual(count, CONFIG["candidate_count"])

    def test_volatility_rule_is_prefix_causal(self) -> None:
        rule = CONFIG["volatility_target_rules"][0]
        original = module.dynamic_exposure(self.base, rule, CONFIG["dynamic_rule_common"], self.risk_on)
        changed = self.base.copy(); changed.iloc[50] = 0.80
        altered = module.dynamic_exposure(changed, rule, CONFIG["dynamic_rule_common"], self.risk_on)
        self.assertEqual(original.iloc[50], altered.iloc[50])

    def test_kelly_rule_is_prefix_causal_and_capped(self) -> None:
        rule = CONFIG["fractional_kelly_rules"][-1]
        gross = module.dynamic_exposure(self.base, rule, CONFIG["dynamic_rule_common"], self.risk_on)
        self.assertLessEqual(gross.max(), rule["maximum_gross"])
        changed = self.base.copy(); changed.iloc[60] = -0.95
        altered = module.dynamic_exposure(changed, rule, CONFIG["dynamic_rule_common"], self.risk_on)
        self.assertEqual(gross.iloc[60], altered.iloc[60])

    def test_tier_rule_uses_only_precomputed_guard(self) -> None:
        rule = CONFIG["fragility_tier_rules"][1]
        gross = module.dynamic_exposure(self.base, rule, CONFIG["dynamic_rule_common"], self.risk_on)
        self.assertTrue((gross[self.risk_on] == rule["risk_on_gross"]).all())
        self.assertTrue((gross[~self.risk_on] == rule["risk_off_gross"]).all())


if __name__ == "__main__":
    unittest.main()
