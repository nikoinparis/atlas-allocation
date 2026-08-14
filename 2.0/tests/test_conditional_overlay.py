import unittest

from src.systematic_trader.conditional_overlay import overlay_path


class ConditionalOverlayTests(unittest.TestCase):
    def test_inactive_equals_core_without_turnover(self):
        core = [{"decision_date": "a", "realization_date": "b", "net_return": 0.01}]
        factor = [{"decision_date": "a", "realization_date": "b", "net_return": 0.10}]
        rows, audit = overlay_path(core, factor, [False], maximum_factor_weight=0.1, top_level_cost_bps=50)
        self.assertEqual(rows[0]["net_return"], 0.01)
        self.assertEqual(rows[0]["allocation_turnover"], 0.0)
        self.assertTrue(audit["return_identity_pass"])

    def test_activation_charges_allocation_turnover(self):
        core = [{"decision_date": "a", "realization_date": "b", "net_return": 0.0}]
        factor = [{"decision_date": "a", "realization_date": "b", "net_return": 0.0}]
        rows, _ = overlay_path(core, factor, [True], maximum_factor_weight=0.1, top_level_cost_bps=100)
        self.assertAlmostEqual(rows[0]["allocation_turnover"], 0.1)
        self.assertAlmostEqual(rows[0]["net_return"], -0.001)

    def test_dates_must_align(self):
        core = [{"decision_date": "a", "realization_date": "b", "net_return": 0.0}]
        factor = [{"decision_date": "a", "realization_date": "c", "net_return": 0.0}]
        with self.assertRaises(ValueError):
            overlay_path(core, factor, [True], maximum_factor_weight=0.1, top_level_cost_bps=0)


if __name__ == "__main__":
    unittest.main()
