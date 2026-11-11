import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("banded", ROOT / "scripts/record_banded_spy_gld_shy_forward_v1.py")
banded = importlib.util.module_from_spec(spec)
spec.loader.exec_module(banded)

THIRDS = {"SPY": 1 / 3, "GLD": 1 / 3, "SHY": 1 / 3}


def test_small_move_holds_drifted_weights_without_trading():
    weights, drifted, rebalanced, turnover = banded.band_step(THIRDS, {"SPY": 0.03, "GLD": -0.01, "SHY": 0.0}, THIRDS, 0.05)
    assert not rebalanced and turnover == 0.0
    assert weights == drifted
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["SPY"] > 1 / 3 > weights["GLD"]


def test_breach_resets_to_thirds_and_counts_both_sides():
    weights, drifted, rebalanced, turnover = banded.band_step(THIRDS, {"SPY": 0.30, "GLD": 0.0, "SHY": 0.0}, THIRDS, 0.05)
    assert rebalanced
    assert weights == THIRDS
    assert drifted["SPY"] == pytest.approx(1.3 / 3.3)
    assert turnover == pytest.approx(sum(abs(1 / 3 - v) for v in drifted.values()))


def test_drift_accumulates_until_the_band_is_crossed():
    held, rebalances = dict(THIRDS), 0
    for _ in range(12):
        held, _, rebalanced, _ = banded.band_step(held, {"SPY": 0.02, "GLD": 0.0, "SHY": 0.0}, THIRDS, 0.05)
        rebalances += rebalanced
    assert rebalances == 1


def test_protocol_matches_the_registered_band_and_cannot_execute():
    protocol = json.loads((ROOT / "config/forward/banded_spy_gld_shy_v1.json").read_text())
    assert protocol["rule"]["band"] == 0.05
    assert protocol["cadence"]["first_eligible_decision_date"] == "2026-11-13"
    assert protocol["live_trading_enabled"] is False and protocol["execution_enabled"] is False
