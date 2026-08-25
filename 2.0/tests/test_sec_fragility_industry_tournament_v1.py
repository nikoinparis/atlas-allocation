from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "fragility_tournament", ROOT / "scripts/run_sec_fragility_industry_tournament_v1.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def weekly_index(periods: int = 30) -> pd.DatetimeIndex:
    return pd.date_range("2025-01-03", periods=periods, freq="W-FRI", tz="UTC")


def test_apply_exposure_charges_financing_and_only_initial_change_cost() -> None:
    index = weekly_index(3)
    returns = pd.Series([0.01, 0.0, 0.0], index=index)
    path, audit = MODULE.apply_exposure(returns, 1.25, 0.08, 25)
    expected_first = 1.25 * 0.01 - 0.25 * 0.08 / 52.0 - 0.25 * 25 / 10000.0
    assert np.isclose(path.iloc[0], expected_first)
    assert np.isclose(audit.exposure_change_cost.iloc[1], 0.0)
    assert (audit.financing_cost > 0).all()


def test_causal_beta_does_not_change_when_current_return_changes() -> None:
    index = weekly_index(30)
    core = pd.Series(np.linspace(-0.02, 0.03, len(index)), index=index)
    source = 0.7 * core + 0.002
    original = MODULE.causal_beta(source, core)
    changed = source.copy()
    changed.iloc[-1] = 9.0
    mutated = MODULE.causal_beta(changed, core)
    assert np.isclose(original.iloc[-1], mutated.iloc[-1])


def test_accelerator_turns_off_without_changing_core() -> None:
    index = weekly_index(30)
    core = pd.Series(0.01, index=index)
    source = pd.Series(0.03, index=index)
    off = pd.Series(False, index=index)
    result, audit = MODULE.accelerator_return(core, source, 0.30, off)
    assert np.allclose(result, core)
    assert np.allclose(audit.source_weight, 0.0)


def test_industry_signal_uses_only_history_before_execution() -> None:
    index = weekly_index(40)
    columns = ["0000000001", "0000000002", "0000000003", "0000000004"]
    weekly = pd.DataFrame(
        {
            columns[0]: np.linspace(0.001, 0.02, len(index)),
            columns[1]: np.linspace(0.001, 0.018, len(index)),
            columns[2]: np.linspace(0.001, -0.01, len(index)),
            columns[3]: np.linspace(0.001, -0.012, len(index)),
        },
        index=index,
    )
    decision = index[-2] - pd.Timedelta(days=7)
    execution = index[-2]
    panel = pd.DataFrame(
        {
            "decision_at": [decision] * 4,
            "execution_at": [execution] * 4,
            "cik10": columns,
            "sector": ["technology", "technology", "energy", "energy"],
            "validated_price_available": [True] * 4,
            "quality_momentum": [1.0, 0.5, 1.0, 0.5],
            "event_score": [0.5] * 4,
        }
    )
    spec = {
        "lookback_weeks": 13,
        "skip_recent_weeks": 4,
        "reversal_penalty": 0.0,
        "top_sectors": 1,
        "names_per_sector": 1,
    }
    config = {
        "industry_beta_lookback_weeks": 26,
        "industry_beta_minimum_weeks": 13,
        "fundamental_score_weights": {"quality_momentum": 0.8, "event_score": 0.2},
    }
    before, _ = MODULE.industry_residual_weights(panel, weekly, spec, config)
    mutated = weekly.copy()
    mutated.loc[mutated.index >= execution, columns[2]] = 10.0
    after, _ = MODULE.industry_residual_weights(panel, mutated, spec, config)
    pd.testing.assert_frame_equal(before.reset_index(drop=True), after.reset_index(drop=True))
