import unittest

import pandas as pd

import scripts.run_sec_form4_rank_feature_v1 as subject


class SectorCappedSelectionTests(unittest.TestCase):
    def test_selection_respects_breadth_and_sector_cap(self):
        frame = pd.DataFrame(
            {
                "cik10": ["1", "2", "3", "4", "5", "6"],
                "sector": ["technology", "technology", "technology", "energy", "energy", "healthcare"],
                "adjusted_score": [1.00, 0.99, 0.98, 0.97, 0.96, 0.95],
            }
        )

        selected = subject.select_sector_capped(frame, breadth=4, sector_cap=0.50)

        self.assertEqual(len(selected), 4)
        self.assertLessEqual(int(selected.sector.value_counts().max()), 2)
        self.assertEqual(set(selected.cik10), {"1", "2", "4", "5"})

    def test_selection_returns_empty_when_constraints_are_impossible(self):
        frame = pd.DataFrame(
            {
                "cik10": ["1", "2", "3"],
                "sector": ["technology", "technology", "technology"],
                "adjusted_score": [1.00, 0.99, 0.98],
            }
        )

        selected = subject.select_sector_capped(frame, breadth=3, sector_cap=0.50)

        self.assertTrue(selected.empty)


if __name__ == "__main__":
    unittest.main()
