from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_sec_cross_component_overlap_budget_v1.py"
SPEC = importlib.util.spec_from_file_location("cross_component_overlap", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def score_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "cik10": [str(value) for value in range(1, 9)],
            "sector": ["tech", "tech", "tech", "finance", "finance", "health", "health", "energy"],
            "score": [8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
        }
    )


class CrossComponentOverlapBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads((ROOT / "config/sec_cross_component_overlap_budget_v1.json").read_text())

    def test_zero_overlap_excludes_every_reference_name(self) -> None:
        selected = module.select_ranked(
            score_frame(), breadth=4, sector_cap=0.75,
            first_names={"1", "4", "6"}, maximum_overlap=0,
        )
        self.assertTrue(set(selected.cik10).isdisjoint({"1", "4", "6"}))
        self.assertEqual(len(selected), 4)

    def test_overlap_and_sector_limits_both_bind(self) -> None:
        selected = module.select_ranked(
            score_frame(), breadth=4, sector_cap=0.50,
            first_names={"1", "2", "4", "6"}, maximum_overlap=1,
        )
        self.assertLessEqual(len(set(selected.cik10) & {"1", "2", "4", "6"}), 1)
        self.assertLessEqual(int(selected.sector.value_counts().max()), 2)

    def test_rank_selection_is_deterministic(self) -> None:
        frame = score_frame()
        expected = module.select_ranked(frame, 4, 0.75, {"1", "4"}, 1)
        shuffled = module.select_ranked(frame.sample(frac=1.0, random_state=17), 4, 0.75, {"1", "4"}, 1)
        self.assertEqual(list(expected.cik10), list(shuffled.cik10))

    def test_frozen_control_and_challenger_count_are_consistent(self) -> None:
        candidates = [
            (order, overlap)
            for order in self.config["selection_orders"]
            for overlap in self.config["maximum_overlap_counts"]
            if not (order == "balance_first" and int(overlap) == 20)
        ]
        self.assertIn(("cash_first", 20), candidates)
        self.assertEqual(self.config["control"], "cash_first_overlap20")
        self.assertEqual(len(candidates) - 1, int(self.config["multiple_testing"]["challenger_count"]))

    def test_config_is_generic_research_only(self) -> None:
        text = json.dumps(self.config).lower()
        self.assertNotIn("micron", text)
        self.assertNotIn('"mu"', text)
        self.assertFalse(bool(self.config["strategy_promotion_authorized"]))
        self.assertFalse(bool(self.config["live_trading_enabled"]))


if __name__ == "__main__":
    unittest.main()
