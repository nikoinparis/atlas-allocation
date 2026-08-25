import json
import unittest

import pandas as pd

import scripts.run_sec_multisignal_company_rank_v1 as subject


class MultiSignalRankTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(subject.CONFIG.read_text())

    def test_predeclared_grid_has_unique_ensemble_names(self):
        specs = subject.ensemble_specs(self.config)

        self.assertEqual(len(specs), 27)
        self.assertEqual(len({spec["name"] for spec in specs}), 27)
        self.assertEqual(
            len(specs) * len(self.config["form4_feature_weights"]) * len(self.config["sector_caps"]),
            108,
        )

    def test_blend_uses_neutral_value_for_missing_secondary(self):
        panel = pd.DataFrame(
            {
                "decision_at": pd.to_datetime(["2026-01-01", "2026-01-01"], utc=True),
                "cik10": ["1", "2"],
                "company_name_as_filed": ["A", "B"],
                "sector": ["technology", "energy"],
                "cash_conversion": [0.8, 0.6],
                "balance_sheet_quality": [1.0, float("nan")],
            }
        )
        spec = {"families": ["balance_sheet_quality"], "secondary_total": 0.2}

        blended = subject.blended_scores(panel, spec)

        self.assertAlmostEqual(float(blended.iloc[0].score), 0.84)
        self.assertAlmostEqual(float(blended.iloc[1].score), 0.58)


if __name__ == "__main__":
    unittest.main()
