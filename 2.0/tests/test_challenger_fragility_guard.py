import unittest

from src.systematic_trader.challenger_fragility_guard import apply_fragility_guard


class FragilityGuardTests(unittest.TestCase):
    def test_stress_never_boosts_offense(self):
        dates = ["2026-01-02"]
        targets = {dates[0]: {"SPY": 0.5, "TLT": 0.5}}
        features = {dates[0]: {"quality": 1.0, "leadership_fragility": 0.0, "stressed": True}}
        output, audit = apply_fragility_guard(
            dates, targets, features, offense_assets={"SPY"},
            boost_strength=0.08, crowding_threshold=0.5,
        )
        self.assertAlmostEqual(output[dates[0]]["SPY"], 0.5)
        self.assertEqual(audit[0]["offense_scale"], 1.0)

    def test_crowding_caps_positive_boost(self):
        dates = ["2026-01-02"]
        targets = {dates[0]: {"SPY": 0.5, "TLT": 0.5}}
        features = {dates[0]: {"quality": 1.0, "leadership_fragility": 0.8, "stressed": False}}
        output, audit = apply_fragility_guard(
            dates, targets, features, offense_assets={"SPY"},
            boost_strength=0.08, crowding_threshold=0.5,
        )
        self.assertAlmostEqual(output[dates[0]]["SPY"], 0.5)
        self.assertEqual(audit[0]["offense_scale"], 1.0)

    def test_uncrowded_quality_can_boost_and_preserves_sum(self):
        dates = ["2026-01-02"]
        targets = {dates[0]: {"SPY": 0.5, "TLT": 0.5}}
        features = {dates[0]: {"quality": 1.0, "leadership_fragility": 0.2, "stressed": False}}
        output, _ = apply_fragility_guard(
            dates, targets, features, offense_assets={"SPY"},
            boost_strength=0.08, crowding_threshold=0.5,
        )
        self.assertGreater(output[dates[0]]["SPY"], 0.5)
        self.assertAlmostEqual(sum(output[dates[0]].values()), 1.0)


if __name__ == "__main__":
    unittest.main()
