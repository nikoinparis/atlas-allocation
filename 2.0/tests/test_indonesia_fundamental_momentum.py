from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "indonesia_fundamental_momentum_runner",
    ROOT / "scripts/run_indonesia_fundamental_momentum_v1.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _row(snapshot: str, available: str, fs_date: str, sales: float, profit: float) -> dict[str, object]:
    return {
        "ticker": "TEST",
        "sector": "Test Sector",
        "snapshot_date": pd.Timestamp(snapshot),
        "available_at": pd.Timestamp(available, tz="UTC"),
        "fs_date": fs_date,
        "sales_b_idr": sales,
        "profit_owners_b_idr": profit,
        "assets_b_idr": 100.0,
        "liabilities_b_idr": 40.0,
        "roe_pct": 12.0,
    }


def test_yoy_same_fs_period_ignores_adjacent_mismatched_quarter() -> None:
    panel = pd.DataFrame(
        [
            _row("2022-03-31", "2022-04-01", "Mar 2022", 100.0, 10.0),
            _row("2022-06-30", "2022-07-01", "Jun 2022", 180.0, 18.0),
            _row("2023-03-31", "2023-04-01", "Mar 2023", 125.0, 15.0),
        ]
    )

    result = MODULE.fundamental_snapshot(
        panel,
        pd.Timestamp("2023-05-01", tz="UTC"),
        ["TEST"],
        growth_method="yoy_same_fs_period",
    )

    assert result.iloc[0]["revenue_growth"] == 0.25
    assert result.iloc[0]["profit_growth"] == 0.5


def test_yoy_same_fs_period_requires_exact_prior_year() -> None:
    panel = pd.DataFrame(
        [
            _row("2022-06-30", "2022-07-01", "Jun 2022", 100.0, 10.0),
            _row("2023-03-31", "2023-04-01", "Mar 2023", 125.0, 15.0),
        ]
    )

    result = MODULE.fundamental_snapshot(
        panel,
        pd.Timestamp("2023-05-01", tz="UTC"),
        ["TEST"],
        growth_method="yoy_same_fs_period",
    )

    assert result.empty
