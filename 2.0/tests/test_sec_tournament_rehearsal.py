from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from systematic_trader import sec_tournament_rehearsal as subject


ROOT = Path(__file__).resolve().parents[1]


class SECTournamentRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.panel, cls.returns = subject.synthetic_panel(17, 30, 234, 13)

    def test_synthetic_panel_is_deterministic_and_point_in_time(self) -> None:
        repeated, _ = subject.synthetic_panel(17, 30, 234, 13)
        self.assertEqual(subject.frame_sha256(self.panel), subject.frame_sha256(repeated))
        audit = subject.validate_point_in_time_panel(self.panel, 13, 13)
        self.assertTrue(audit["prefix_causal"])
        self.assertEqual(audit["required_purge_decisions"], 1)

    def test_future_available_feature_is_rejected(self) -> None:
        changed = self.panel.copy()
        changed.loc[changed.index[0], "available_at"] = changed.loc[changed.index[0], "decision_at"] + pd.Timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "available after decision"):
            subject.validate_point_in_time_panel(changed, 13, 13)

    def test_target_horizon_must_fit_purge_interval(self) -> None:
        with self.assertRaisesRegex(ValueError, "purge is insufficient"):
            subject.validate_point_in_time_panel(self.panel, 14, 13)

    def test_nested_ml_does_not_use_outer_test_targets(self) -> None:
        features = ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]
        original = subject.nested_ridge_predictions(self.panel, features, [0.1, 1.0, 10.0], 8)
        changed = self.panel.copy()
        last = changed.decision_at.max()
        changed.loc[changed.decision_at == last, "future_sector_relative_return"] = 999.0
        altered = subject.nested_ridge_predictions(changed, features, [0.1, 1.0, 10.0], 8)
        columns = ["decision_at", "cik10", "score", "selected_alpha", "train_end"]
        pd.testing.assert_frame_equal(original[columns], altered[columns])
        self.assertTrue((original.train_end < original.decision_at).all())
        self.assertTrue(set(original.selected_alpha).issubset({0.1, 1.0, 10.0}))

    def test_weights_respect_issuer_and_sector_caps(self) -> None:
        frame = self.panel[["decision_at", "cik10", "sector", "quality_momentum"]].rename(columns={"quality_momentum": "score"})
        weights = subject.top_weights(frame, 10, 0.15, 0.4)
        self.assertLessEqual(float(weights.weight.max()), 0.15)
        merged = weights.merge(self.panel[["decision_at", "cik10", "sector"]], on=["decision_at", "cik10"])
        self.assertLessEqual(float(merged.groupby(["decision_at", "sector"]).weight.sum().max()), 0.4 + 1e-12)

    def test_cost_delay_and_missing_stresses_execute(self) -> None:
        decision = self.panel.decision_at.min()
        weights = pd.DataFrame({"decision_at": [decision], "cik10": [self.returns.columns[0]], "weight": [1.0]})
        base, _ = subject.portfolio_path(weights, self.returns, 50)
        severe, _ = subject.portfolio_path(weights, self.returns, 200)
        delayed, _ = subject.portfolio_path(weights, self.returns, 50, 2)
        missing = self.returns.copy(); missing.iloc[:, 0] = np.nan
        adverse, _ = subject.portfolio_path(weights, missing, 50, 0, "adverse_total_loss")
        self.assertLess(float(severe.sum()), float(base.sum()))
        self.assertFalse(base.equals(delayed))
        self.assertLess(float(adverse.sum()), float(base.sum()))

    def test_config_is_synthetic_research_only(self) -> None:
        config = json.loads((ROOT / "config/sec_return_tournament_synthetic_rehearsal_v1.json").read_text())
        self.assertTrue(config["synthetic_only"])
        self.assertFalse(config["strategy_promotion_authorized"])
        self.assertFalse(config["live_trading_enabled"])
        self.assertEqual(config["familywise_trials"], 8)

    def test_seal_covers_contract_engine_runner_and_tests(self) -> None:
        source = (ROOT / "scripts/seal_sec_return_tournament_rehearsal_v1.py").read_text()
        for required in ["sec_return_tournament_synthetic_rehearsal_v1.json", "sec_broad_research_panel_v1.schema.json", "sec_tournament_rehearsal.py", "run_sec_return_tournament_synthetic_rehearsal_v1.py", "test_sec_tournament_rehearsal.py"]:
            self.assertIn(required, source)
        self.assertIn('"real_execution_authorized": False', source)
        self.assertIn('"live_trading_enabled": False', source)


if __name__ == "__main__":
    unittest.main()
