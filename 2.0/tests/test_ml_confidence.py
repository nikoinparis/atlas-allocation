import unittest

from src.systematic_trader.ml_confidence import apply_weight_turnover_buffer, buffered_membership, causal_strong_weight, causal_weight, guarded_weight, linear_percentile, persistent_cost_aware_weight, raw_confidence


class MlConfidenceTests(unittest.TestCase):
    def test_raw_confidence_rewards_separation_and_agreement(self):
        low = raw_confidence([0.2] * 5, [0.19] * 5, [0.6] * 5, [0.1] * 5, [0.05] * 5)
        high = raw_confidence([0.3] * 5, [0.1] * 5, [1.0] * 5, [0.05] * 5, [0.02] * 5)
        self.assertGreater(high["raw_confidence"], low["raw_confidence"])

    def test_current_score_is_not_needed_to_make_thresholds(self):
        prior = [float(value) for value in range(24)]
        weight, thresholds = causal_weight(100.0, prior)
        self.assertEqual(0.30, weight)
        self.assertEqual(linear_percentile(prior, 0.95), thresholds["p95"])
        self.assertEqual((0.0, {"p60": None, "p80": None, "p95": None}), causal_weight(100.0, prior[:-1]))

    def test_drawdown_stop_overrides_volatility_cap(self):
        weight, audit = guarded_weight(0.30, [0.0] * 20 + [-0.04] * 4)
        self.assertEqual(0.0, weight)
        self.assertTrue(audit["drawdown_stop_active"])

    def test_high_volatility_caps_but_does_not_increase_weight(self):
        weight, audit = guarded_weight(0.30, [0.08, -0.08] * 7)
        self.assertEqual(0.10, weight)
        self.assertTrue(audit["volatility_cap_active"])
        low_weight, _ = guarded_weight(0.0, [0.08, -0.08] * 7)
        self.assertEqual(0.0, low_weight)

    def test_strong_rule_abstains_from_moderate_confidence(self):
        prior = [float(value) for value in range(100)]
        moderate, thresholds = causal_strong_weight(70.0, prior)
        strong, _ = causal_strong_weight(85.0, prior)
        extreme, _ = causal_strong_weight(99.0, prior)
        self.assertEqual(0.0, moderate)
        self.assertEqual(0.20, strong)
        self.assertEqual(0.30, extreme)
        self.assertGreater(thresholds["p80"], 70.0)

    def test_strong_rule_requires_two_year_warmup(self):
        self.assertEqual((0.0, {"p80": None, "p95": None}), causal_strong_weight(100.0, [1.0] * 23))

    def test_persistent_cost_rule_requires_both_consecutive_signals(self):
        history = [0.001] * 26
        self.assertEqual(0.0, persistent_cost_aware_weight(0.2, 0.0, history)[0])
        self.assertEqual(0.0, persistent_cost_aware_weight(0.0, 0.2, history)[0])
        self.assertEqual(0.2, persistent_cost_aware_weight(0.3, 0.2, history)[0])

    def test_persistent_cost_rule_requires_positive_high_cost_history(self):
        weight, audit = persistent_cost_aware_weight(0.3, 0.3, [-0.001] * 26)
        self.assertEqual(0.0, weight)
        self.assertFalse(audit["cost_hurdle_pass"])
        self.assertEqual(0.0, persistent_cost_aware_weight(0.3, 0.3, [0.001] * 25)[0])

    def test_membership_buffer_retains_close_incumbent(self):
        scores = {"A": 1.0, "B": 0.9, "C": 0.8, "D": 0.7, "E": 0.6, "F": 0.61, "G": 0.0}
        selected, audit = buffered_membership(["A", "B", "C", "D", "E"], scores)
        self.assertIn("E", selected)
        self.assertNotIn("F", selected)
        self.assertEqual(0, audit["replacements"])

    def test_membership_buffer_allows_material_replacement(self):
        scores = {"A": 1.0, "B": 0.9, "C": 0.8, "D": 0.7, "E": 0.1, "F": 0.65, "G": 0.0}
        selected, audit = buffered_membership(["A", "B", "C", "D", "E"], scores)
        self.assertIn("F", selected)
        self.assertNotIn("E", selected)
        self.assertEqual(1, audit["replacements"])

    def test_weight_buffer_skips_small_change(self):
        previous = {"A": 0.5, "B": 0.5}
        kept, audit = apply_weight_turnover_buffer(previous, {"A": 0.55, "B": 0.45})
        self.assertEqual(previous, kept)
        self.assertTrue(audit["weight_update_skipped"])
        changed, _ = apply_weight_turnover_buffer(previous, {"A": 0.7, "B": 0.3})
        self.assertNotEqual(previous, changed)


if __name__ == "__main__":
    unittest.main()
