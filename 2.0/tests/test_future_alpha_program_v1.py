from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ohlcv_alpha", ROOT / "scripts/run_daily_ohlcv_alpha_zoo_v1.py")
ohlcv = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ohlcv)


def synthetic_prices(last_value: float = 200.0) -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=320, tz="UTC")
    close = np.linspace(100.0, last_value, len(dates))
    return pd.DataFrame({
        "Date": dates, "Open": close * 0.999, "High": close * 1.01,
        "Low": close * 0.99, "Close": close, "Adj Close": close,
        "Volume": np.linspace(1_000_000, 2_000_000, len(dates)),
    })


def test_feature_snapshot_never_uses_prices_after_decision() -> None:
    raw = synthetic_prices()
    decision = raw.Date.iloc[250]
    before = ohlcv.compute_features(raw, decision)
    altered = raw.copy()
    altered.loc[altered.Date > decision, ["Open", "High", "Low", "Close", "Adj Close", "Volume"]] = 1e12
    after = ohlcv.compute_features(altered, decision)
    assert before is not None and after is not None
    for key in before:
        assert np.isclose(before[key], after[key], equal_nan=True)


def test_sign_flip_probability_is_exact_and_symmetric() -> None:
    assert ohlcv.sign_flip_p([1.0, 1.0, 1.0, 1.0]) == ohlcv.sign_flip_p([-1.0, -1.0, -1.0, -1.0])
    assert ohlcv.sign_flip_p([1.0, -1.0, 1.0, -1.0]) == 1.0


def test_portfolio_cost_is_charged_only_on_turnover() -> None:
    dates = pd.to_datetime(["2025-01-03", "2025-01-10"], utc=True)
    weekly = pd.DataFrame({"A": [0.10, 0.10]}, index=dates)
    path = ohlcv.portfolio_path({dates[0]: {"A": 1.0}}, weekly, 100)
    assert np.isclose(path.iloc[0], 0.09)
    assert np.isclose(path.iloc[1], 0.10)
