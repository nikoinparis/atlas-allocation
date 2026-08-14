import importlib.util
import sys
import unittest
from pathlib import Path

from src.systematic_trader.point_in_time import read_wide_panel
from src.systematic_trader.raw_signals import reconstruct_five_signals


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/rebuild_raw_signals_and_strategy.py"
spec = importlib.util.spec_from_file_location("rebuild_raw_signals_and_strategy", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class RawSignalRebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = module.build()

    def test_all_signal_components_are_checked(self):
        self.assertEqual(31, self.result["raw_formula_audit"]["component_columns_checked"])

    def test_raw_formulas_reconstruct_saved_signal_values(self):
        self.assertTrue(self.result["raw_formula_audit"]["all_formula_components_reconstruct"])
        self.assertEqual(0, self.result["raw_formula_audit"]["total_missingness_mismatches"])

    def test_raw_strategy_has_clean_accounting(self):
        self.assertTrue(self.result["audit"]["unpriced_exposure_pass"])
        self.assertTrue(self.result["audit"]["fully_invested_pass"])
        self.assertTrue(self.result["audit"]["cost_identity_pass"])

    def test_raw_rebuild_is_not_promoted(self):
        self.assertEqual("research_only_not_promoted", self.result["status"])
        self.assertEqual(52, self.result["forward_lock"]["minimum_weeks"])

    def test_signal_values_are_invariant_to_future_data_truncation(self):
        dates, assets, prices = read_wide_panel(module.base.DATA_HUB / "weekly_prices.csv")
        _, _, returns = read_wide_panel(module.base.DATA_HUB / "weekly_returns.csv")
        dates = dates[:220]
        assets = assets[:6]
        prices = {day: {asset: prices[day][asset] for asset in assets} for day in dates}
        aligned = {day: {asset: returns.get(day, {}).get(asset) for asset in assets} for day in dates}
        full, _ = reconstruct_five_signals(
            dates=dates, assets=assets, prices=prices, weekly_log_returns=aligned
        )
        prefix_dates = dates[:200]
        prefix, _ = reconstruct_five_signals(
            dates=prefix_dates,
            assets=assets,
            prices={day: prices[day] for day in prefix_dates},
            weekly_log_returns={day: aligned[day] for day in prefix_dates},
        )
        for name in full:
            for day in prefix_dates:
                self.assertEqual(full[name][day], prefix[name][day])


if __name__ == "__main__":
    unittest.main()
