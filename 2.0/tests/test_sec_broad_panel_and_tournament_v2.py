from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from systematic_trader import sec_broad_panel_v2 as panel_module
from systematic_trader import sec_real_tournament_v2 as tournament
from systematic_trader import sec_tournament_rehearsal as fixture

ROOT = Path(__file__).resolve().parents[1]
RUNNER_SPEC = importlib.util.spec_from_file_location("real_runner", ROOT / "scripts/run_sec_return_improvement_tournament_v2.py")
runner = importlib.util.module_from_spec(RUNNER_SPEC); assert RUNNER_SPEC.loader is not None; RUNNER_SPEC.loader.exec_module(runner)
MATERIALIZER_SPEC = importlib.util.spec_from_file_location("materializer", ROOT / "scripts/materialize_sec_broad_research_panel_v2.py")
materializer = importlib.util.module_from_spec(MATERIALIZER_SPEC); assert MATERIALIZER_SPEC.loader is not None; MATERIALIZER_SPEC.loader.exec_module(materializer)


class BroadPanelAndTournamentV2Tests(unittest.TestCase):
    @classmethod
    def sources(cls):
        raw, returns = fixture.synthetic_panel(23, 48, 260, 13)
        membership = raw[["decision_at", "available_at", "cik10", "sector"]].copy()
        membership["validated_price_available"] = True
        features = raw[["decision_at", "available_at", "cik10", "residual_momentum", "trend_quality", "quality_momentum", "event_score"]].copy()
        prices = 100 * (1 + returns).cumprod()
        return raw, membership, features, prices

    def test_materializer_enforces_delay_and_explicit_missing_policy(self) -> None:
        _, membership, features, prices = self.sources()
        first_key = membership.index[0]
        membership.loc[first_key, "validated_price_available"] = False
        panel, weekly = panel_module.materialize_panel(membership, features, prices)
        audit = panel_module.validate_materialized_panel(panel)
        self.assertTrue(audit["causal_timestamps"])
        self.assertTrue((pd.to_datetime(panel.execution_at) >= pd.to_datetime(panel.decision_at) + pd.Timedelta(weeks=1)).all())
        missing = panel[(panel.decision_at == membership.loc[first_key, "decision_at"]) & (panel.cik10 == membership.loc[first_key, "cik10"])]
        self.assertEqual(missing.iloc[0].missing_price_policy, "base_cash_adverse_total_loss")
        self.assertTrue(pd.isna(missing.iloc[0].price_at_execution))
        self.assertEqual(list(weekly.columns), sorted(weekly.columns))

    def test_late_feature_is_rejected(self) -> None:
        _, membership, features, prices = self.sources()
        features.loc[features.index[0], "available_at"] = features.loc[features.index[0], "decision_at"] + pd.Timedelta(days=1)
        with self.assertRaisesRegex(ValueError, "after its decision"):
            panel_module.materialize_panel(membership, features, prices)

    def test_future_price_mutation_does_not_change_completed_labels(self) -> None:
        _, membership, features, prices = self.sources()
        original, _ = panel_module.materialize_panel(membership, features, prices)
        cutoff = prices.index[-30]
        changed_prices = prices.copy(); changed_prices.loc[changed_prices.index > cutoff] *= 9
        altered, _ = panel_module.materialize_panel(membership, features, changed_prices)
        keep = pd.to_datetime(original.label_end_at) <= cutoff
        columns = ["decision_at", "cik10", "price_at_execution", "future_sector_relative_return"]
        pd.testing.assert_frame_equal(original.loc[keep, columns].reset_index(drop=True), altered.loc[keep, columns].reset_index(drop=True))

    def test_fixture_evaluator_exercises_all_eight_families(self) -> None:
        _, membership, features, prices = self.sources()
        panel, weekly = panel_module.materialize_panel(membership, features, prices)
        config = json.loads((ROOT / "config/sec_return_improvement_program_v1.json").read_text())
        control = weekly.mean(axis=1, skipna=True)
        screen, ml = tournament.evaluate(panel, weekly, control, config)
        self.assertEqual(len(screen), 8)
        self.assertEqual(set(screen.family), {"residual_momentum", "trend_quality", "quality_momentum", "event_conditioning", "adaptive_concentration", "confidence_weighted_ml", "holding_and_exit", "strategy_allocator"})
        self.assertFalse(ml.empty)
        self.assertTrue((ml.train_end < ml.decision_at).all())

    def test_family_builder_normalizes_serialized_timestamps_before_merges(self) -> None:
        _, membership, features, prices = self.sources()
        panel, _ = panel_module.materialize_panel(membership, features, prices)
        panel["decision_at"] = panel.decision_at.astype(str)
        panel["execution_at"] = panel.execution_at.astype(str)
        config = json.loads((ROOT / "config/sec_return_improvement_program_v1.json").read_text())

        weights, _ = tournament.build_family_weights(panel, config)

        self.assertEqual(set(weights), {"residual_momentum", "trend_quality", "quality_momentum", "event_conditioning", "adaptive_concentration", "confidence_weighted_ml", "holding_and_exit"})
        self.assertTrue(all(isinstance(frame.decision_at.dtype, pd.DatetimeTZDtype) for frame in weights.values()))

    def test_guards_prioritize_protocol_then_gate_then_panel_then_seal(self) -> None:
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, False, True, True), "blocked_frozen_protocol_mismatch")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": False}, True, True, True), "blocked_broad_research_gate")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, True, False, True), "authorized_waiting_for_hash_verified_panel")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, True, True, False), "authorized_waiting_for_execution_seal")

    def test_materializer_guard_blocks_before_input_discovery(self) -> None:
        self.assertEqual(materializer.input_state({"strategy_testing_authorized": False}, True, True), "blocked_broad_research_gate")

    def test_manifest_hash_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary); artifact = directory / "x.csv"; artifact.write_text("x\n1\n")
            manifest = {"artifact_sha256": {"x.csv": materializer.sha256(artifact)}}
            self.assertTrue(materializer.verify_manifest(directory, manifest))
            artifact.write_text("x\n2\n")
            self.assertFalse(materializer.verify_manifest(directory, manifest))


if __name__ == "__main__": unittest.main()
