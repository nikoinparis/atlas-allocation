from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/sec_fragility_exposure_daily_audit_v2.json").read_text())
SPEC = importlib.util.spec_from_file_location("daily_audit", ROOT / "scripts/run_sec_fragility_exposure_daily_audit_v2.py")
module = importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(module)


class FragilityExposureDailyAuditTests(unittest.TestCase):
    def test_overweight_components_have_balancing_cash_not_free_return(self) -> None:
        index = pd.date_range("2026-01-05", periods=5, freq="B")
        components = pd.DataFrame({"core": 0.0, "sector": 0.0}, index=index)
        targets = pd.DataFrame({"core": [1.1], "sector": [0.3]}, index=[module.week_label(index[0])])
        path = module.simulate_component_blend(components, targets)
        self.assertTrue(np.allclose(path.net_return, 0.0))
        self.assertTrue(np.allclose(path.wealth, 1.0))

    def test_component_blend_reconciles_weekly_compounding(self) -> None:
        index = pd.date_range("2026-01-05", periods=20, freq="B")
        components = pd.DataFrame({"a": 0.01, "b": -0.002}, index=index)
        weeks = sorted({module.week_label(date) for date in index})
        targets = pd.DataFrame({"a": 0.7, "b": 0.3}, index=weeks)
        path = module.simulate_component_blend(components, targets)
        for _, block in components.groupby(components.index.map(module.week_label)):
            expected = 0.7 * ((1 + block.a).prod() - 1) + 0.3 * ((1 + block.b).prod() - 1)
            actual = (1 + path.loc[block.index].net_return).prod() - 1
            self.assertAlmostEqual(actual, expected, places=12)

    def test_cash_only_has_no_financing_or_exposure_cost(self) -> None:
        index = pd.date_range("2026-01-05", periods=20, freq="B")
        source = pd.Series(0.001, index=index)
        rule = next(item for item in CONFIG["daily_paths"] if item["name"] == "cash_only_1.00x")
        gross = module.desired_exposure(source, rule)
        path = module.apply_daily_exposure(source, gross, rule["financing_rate"], CONFIG["exposure_change_cost_bps"])
        self.assertEqual(float(path.financing_cost.sum()), 0.0)
        self.assertEqual(float(path.exposure_change_cost.sum()), 0.0)
        pd.testing.assert_series_equal(path.net_return, source, check_names=False, check_freq=False)

    def test_daily_volatility_target_is_lagged_and_capped(self) -> None:
        index = pd.date_range("2025-01-02", periods=180, freq="B")
        source = pd.Series(0.001 + 0.01 * np.sin(np.arange(len(index))), index=index)
        rule = next(item for item in CONFIG["daily_paths"] if item["kind"] == "volatility_target")
        gross = module.desired_exposure(source, rule)
        changed = source.copy(); changed.iloc[140] = 0.8
        altered = module.desired_exposure(changed, rule)
        self.assertEqual(gross.iloc[140], altered.iloc[140])
        self.assertLessEqual(gross.max(), rule["maximum_gross"])


if __name__ == "__main__":
    unittest.main()
