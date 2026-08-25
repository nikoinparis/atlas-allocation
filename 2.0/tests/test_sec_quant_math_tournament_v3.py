from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from systematic_trader import sec_quant_math_tournament_v3 as quant

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/sec_quant_math_tournament_v3.json").read_text())
SPEC = importlib.util.spec_from_file_location("quant_runner_v3", ROOT / "scripts/run_sec_quant_math_tournament_v3.py")
runner = importlib.util.module_from_spec(SPEC); assert SPEC.loader is not None; SPEC.loader.exec_module(runner)


def fixture(seed: int = 17, weeks: int = 170, names: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-06", periods=weeks, freq="W-FRI", tz="UTC")
    ciks = [f"{index:010d}" for index in range(1, names + 1)]
    sectors = {cik: f"sector_{index % 5}" for index, cik in enumerate(ciks)}
    market = rng.normal(0.002, 0.02, weeks)
    latent = rng.normal(0, 1, names)
    returns = pd.DataFrame(index=dates, columns=ciks, dtype=float)
    for index, cik in enumerate(ciks):
        returns[cik] = market + 0.0015 * latent[index] + rng.normal(0, 0.035, weeks)
    rows = []
    for position in range(0, weeks - 13, 13):
        decision = dates[position]
        execution = dates[min(position + 1, weeks - 1)]
        label_end = dates[min(position + 13, weeks - 1)]
        for index, cik in enumerate(ciks):
            rows.append({
                "decision_at": decision, "execution_at": execution, "label_end_at": label_end,
                "available_at": decision - pd.Timedelta(days=1), "cik10": cik,
                "sector": sectors[cik], "validated_price_available": True,
                "quality_momentum": latent[index] + rng.normal(0, 0.1),
                "event_score": 0.5 + 0.1 * np.tanh(latent[index]),
            })
    return pd.DataFrame(rows), returns


class QuantMathTournamentV3Tests(unittest.TestCase):
    def test_robust_z_limits_single_extreme_observation(self) -> None:
        values = pd.Series([0.0, 0.1, -0.1, 0.2, 1_000_000.0])
        scores = quant.robust_z(values)
        self.assertTrue(np.isfinite(scores).all())
        self.assertLess(scores.max(), 1_000)

    def test_future_return_mutation_cannot_change_past_features(self) -> None:
        panel, returns = fixture()
        original = quant.build_monthly_feature_panel(panel, returns, CONFIG)
        cutoff = returns.index[110]
        changed = returns.copy()
        changed.loc[changed.index > cutoff] *= -7.0
        mutated = quant.build_monthly_feature_panel(panel, changed, CONFIG)
        quant.verify_prefix_causality(original, mutated, cutoff, [
            "residual_13", "residual_26", "residual_52", "momentum_acceleration",
            "trend_consistency", "downside_volatility", "quality_momentum", "event_score",
        ])

    def test_ridge_training_labels_end_before_test_decision(self) -> None:
        panel, returns = fixture(weeks=240)
        monthly = quant.build_monthly_feature_panel(panel, returns, CONFIG)
        _, audit = quant.build_signal_panel(monthly, CONFIG)
        self.assertFalse(audit.empty)
        self.assertTrue((pd.to_datetime(audit.train_end, utc=True) < pd.to_datetime(audit.decision_at, utc=True)).all())

    def test_all_predeclared_base_candidates_are_built(self) -> None:
        panel, returns = fixture(weeks=240)
        monthly = quant.build_monthly_feature_panel(panel, returns, CONFIG)
        signals, _ = quant.build_signal_panel(monthly, CONFIG)
        targets = quant.build_base_targets(signals, returns, CONFIG)
        self.assertEqual(len(targets), CONFIG["candidate_accounting"]["base_candidates"])
        for target in targets.values():
            self.assertLessEqual(target.groupby("decision_at").weight.max().max(), CONFIG["constraints"]["maximum_issuer_weight"] + 1e-9)

    def test_volatility_exposure_uses_only_lagged_returns(self) -> None:
        index = pd.date_range("2024-01-05", periods=60, freq="W-FRI", tz="UTC")
        base = pd.Series(np.linspace(-0.02, 0.03, len(index)), index=index)
        rule = next(item for item in CONFIG["exposure_rules"] if item["kind"] == "volatility_target")
        original = quant.exposure_series(base, rule)
        changed = base.copy(); changed.iloc[40] = 0.90
        altered = quant.exposure_series(changed, rule)
        self.assertEqual(original.iloc[40], altered.iloc[40])

    def test_authorization_fails_closed(self) -> None:
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": False}, True, True, False), "blocked_research_gate")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, False, True, False), "blocked_panel_hashes")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, True, False, False), "blocked_execution_seal")
        self.assertEqual(runner.authorization_state({"strategy_testing_authorized": True}, True, True, True), "blocked_one_shot_already_complete")


if __name__ == "__main__":
    unittest.main()
