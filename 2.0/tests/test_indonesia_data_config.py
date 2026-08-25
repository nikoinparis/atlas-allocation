import json
from pathlib import Path

from scripts.acquire_indonesia_current_pilot import validate_config


ROOT = Path(__file__).resolve().parents[1]


def test_current_indonesia_universe_snapshot_has_expected_nesting_and_is_non_backtestable():
    config = json.loads(
        (ROOT / "config/indonesia_current_universes_2026-08-03.json").read_text()
    )
    validate_config(config)
    universes = config["universes"]
    assert len(universes["IDX80"]) == 80
    assert len(universes["LQ45"]) == 45
    assert len(universes["IDX30"]) == 30
    assert set(universes["IDX30"]) < set(universes["LQ45"]) < set(universes["IDX80"])
    assert config["historical_membership"] is False
    assert config["backtest_membership_authorized"] is False
