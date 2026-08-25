from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_sec_sector_ensemble_daily_risk_scaling_audit_v1.py"
SPEC = importlib.util.spec_from_file_location("daily_scaling", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class DailyRiskScalingAuditTests(unittest.TestCase):
    def test_one_x_reproduces_source_when_called_as_control(self) -> None:
        index = pd.date_range("2025-01-02", periods=20, freq="B")
        returns = pd.Series(np.linspace(-0.01, 0.02, len(index)), index=index)
        source = pd.DataFrame({"net_return": returns})
        path = module.leverage_path(source, 1.0, 0.06, 25)
        np.testing.assert_allclose(path.net_return, returns, rtol=0, atol=1e-15)

    def test_financing_is_charged_only_above_one_x(self) -> None:
        index = pd.date_range("2025-01-02", periods=20, freq="B")
        source = pd.DataFrame({"net_return": 0.0}, index=index)
        levered = module.leverage_path(source, 1.35, 0.06, 25)
        self.assertGreater(float(levered.financing_cost.sum()), 0.0)
        self.assertTrue((levered.financing_cost >= 0).all())

    def test_config_is_research_only(self) -> None:
        config = json.loads((ROOT / "config/sec_sector_ensemble_daily_risk_scaling_audit_v1.json").read_text())
        self.assertFalse(config["strategy_promotion_authorized"])
        self.assertFalse(config["live_trading_enabled"])
        self.assertLessEqual(max(config["fixed_exposures"]), 1.35)


if __name__ == "__main__":
    unittest.main()
