import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChallengerResearchProtocolTests(unittest.TestCase):
    def test_ml_protocol_is_nested_and_has_negative_control(self):
        config = json.loads((ROOT / "config/ml_sandbox_v1.json").read_text())
        self.assertEqual(config["inner_selection"]["method"], "time_ordered_walk_forward_only")
        self.assertGreaterEqual(config["inner_selection"]["embargo_weeks"], 1)
        self.assertIn("label_shuffle_negative_control", config["mandatory_controls"])
        self.assertEqual(config["promotion_requires"]["untouched_forward_weeks"], 52)

    def test_portfolio_comparison_has_common_constraints(self):
        config = json.loads((ROOT / "config/portfolio_library_comparison_v1.json").read_text())
        self.assertEqual(len(config["repositories"]), 4)
        self.assertTrue(config["constraints"]["long_only"])
        self.assertTrue(config["constraints"]["fully_invested"])
        self.assertLessEqual(config["constraints"]["maximum_asset_weight"], 0.35)


if __name__ == "__main__":
    unittest.main()
