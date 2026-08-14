import unittest

from src.systematic_trader.term_structure_challenger import (
    carry_roll_scores,
    latest_curve_with_full_week_lag,
    target_weights,
)


class TermStructureChallengerTests(unittest.TestCase):
    def test_full_week_lag_excludes_newer_curve(self):
        curves = [
            {"observation_date": "2026-01-02"},
            {"observation_date": "2026-01-09"},
            {"observation_date": "2026-01-16"},
        ]
        selected = latest_curve_with_full_week_lag(curves, "2026-01-16")
        self.assertEqual("2026-01-09", selected["observation_date"])

    def test_carry_roll_selects_maximum_fixed_score(self):
        curve = {"1Y": 4.0, "2Y": 4.2, "7Y": 4.3, "10Y": 4.6, "20Y": 5.0}
        scores = carry_roll_scores(curve)
        weights = target_weights("carry_roll", curve)
        self.assertEqual(max(scores, key=scores.get), max(weights, key=weights.get))
        self.assertAlmostEqual(1.0, sum(weights.values()))

    def test_inverted_curve_slope_regime_uses_short_treasuries(self):
        curve = {"1Y": 5.0, "2Y": 5.0, "7Y": 4.5, "10Y": 4.0, "20Y": 4.2}
        self.assertEqual({"SHY": 1.0, "IEF": 0.0, "TLT": 0.0}, target_weights("slope_regime", curve))


if __name__ == "__main__":
    unittest.main()
