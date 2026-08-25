from __future__ import annotations

import pandas as pd

from scripts.run_idx80_survival_diagnostic_v1 import metrics, turnover


def test_turnover_includes_initial_cash_transition() -> None:
    assert turnover({"CASH_IDR": 1.0}, {"AAAA": 0.6, "BBBB": 0.4, "CASH_IDR": 0.0}) == 1.0
    assert turnover({"AAAA": 0.5, "BBBB": 0.5}, {"AAAA": 0.25, "BBBB": 0.75}) == 0.25


def test_metrics_have_expected_positive_path_and_drawdown() -> None:
    result = metrics(pd.Series([0.01, -0.02, 0.03]))
    assert result["cumulative_return"] > 0
    assert result["maximum_drawdown"] < 0
    assert result["daily_observations"] == 3
