from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_sec_recent_return_risk_scaling_v1.py"
SPEC = importlib.util.spec_from_file_location("risk_scaling", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class RecentReturnRiskScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config/sec_recent_return_risk_scaling_v1.json").read_text())
        cls.rules = cls.config["signal_rules"]

    def returns(self) -> pd.Series:
        index = pd.date_range("2020-01-03", periods=120, freq="W-FRI")
        values = 0.004 + 0.015 * np.sin(np.arange(len(index)) / 5.0)
        return pd.Series(values, index=index)

    def test_future_mutation_does_not_change_prior_exposure(self) -> None:
        source = self.returns()
        spec = {"name": "test", "family": "trend_drawdown_inverse_volatility", "target_volatility": 0.25}
        first = module.simulate(source, spec, self.rules, 0.06, 25)
        mutated = source.copy()
        mutated.iloc[91:] = -0.5
        second = module.simulate(mutated, spec, self.rules, 0.06, 25)
        pd.testing.assert_series_equal(first.exposure.iloc[:91], second.exposure.iloc[:91])

    def test_exposure_bounds_and_weekly_change_limit(self) -> None:
        spec = {"name": "test", "family": "inverse_volatility", "target_volatility": 0.30}
        path = module.simulate(self.returns(), spec, self.rules, 0.06, 25)
        self.assertGreaterEqual(float(path.exposure.min()), float(self.rules["minimum_exposure"]))
        self.assertLessEqual(float(path.exposure.max()), float(self.rules["maximum_exposure"]))
        self.assertLessEqual(float(path.exposure.diff().abs().dropna().max()),
                             float(self.rules["maximum_weekly_exposure_change"]) + 1e-12)

    def test_unscaled_control_is_exact_without_extra_costs(self) -> None:
        source = self.returns()
        spec = {"name": "control", "family": "fixed", "fixed_exposure": 1.0}
        path = module.simulate(source, spec, self.rules, 0.06, 25)
        np.testing.assert_allclose(path.net_return.to_numpy(), source.to_numpy(), rtol=0, atol=1e-15)

    def test_financing_and_outer_costs_are_nonnegative(self) -> None:
        spec = {"name": "levered", "family": "fixed", "fixed_exposure": 1.35}
        path = module.simulate(self.returns(), spec, self.rules, 0.06, 25)
        self.assertTrue((path.financing_cost >= 0).all())
        self.assertTrue((path.outer_cost >= 0).all())
        self.assertGreater(float(path.financing_cost.sum()), 0.0)

    def test_config_forbids_more_than_one_point_five_exposure(self) -> None:
        self.assertLessEqual(float(self.rules["maximum_exposure"]), 1.5)
        self.assertFalse(bool(self.config["strategy_promotion_authorized"]))
        self.assertFalse(bool(self.config["live_trading_enabled"]))


if __name__ == "__main__":
    unittest.main()
