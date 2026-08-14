"""Track A tests for canonical production metrics and cost conventions."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from production_costs import (
    full_l1_turnover,
    one_way_turnover,
    portfolio_path,
    transaction_cost_from_turnover,
)
from production_metrics import (
    annualized_volatility,
    cagr,
    calmar_ratio,
    max_drawdown,
    metrics_from_series,
    var_cvar,
)


def assert_close(actual: float, expected: float, tol: float = 1e-12) -> None:
    if not math.isclose(float(actual), float(expected), rel_tol=tol, abs_tol=tol):
        raise AssertionError(f"{actual!r} != {expected!r}")


def test_turnover_and_cost_convention() -> None:
    idx = pd.date_range("2024-01-05", periods=4, freq="W-FRI")
    weights = pd.DataFrame(
        {
            "A": [1.0, 0.5, 0.5, 0.0],
            "B": [0.0, 0.5, 0.5, 1.0],
        },
        index=idx,
    )
    full = full_l1_turnover(weights)
    one_way = one_way_turnover(weights)
    expected_full = pd.Series([np.nan, 1.0, 0.0, 1.0], index=idx)
    expected_one_way = pd.Series([np.nan, 0.5, 0.0, 0.5], index=idx)
    pd.testing.assert_series_equal(full, expected_full)
    pd.testing.assert_series_equal(one_way, expected_one_way)

    cost = transaction_cost_from_turnover(one_way, cost_bps=10.0)
    expected_cost = pd.Series([0.0, 0.0005, 0.0, 0.0005], index=idx)
    pd.testing.assert_series_equal(cost, expected_cost)


def test_portfolio_path_uses_next_week_returns_and_one_way_cost() -> None:
    idx = pd.date_range("2024-01-05", periods=3, freq="W-FRI")
    weights = pd.DataFrame({"A": [1.0, 0.0, 0.0], "B": [0.0, 1.0, 1.0]}, index=idx)
    next_returns = pd.DataFrame({"A": [0.01, 0.02, 0.03], "B": [0.04, 0.05, 0.06]}, index=idx)
    path = portfolio_path(weights, next_returns, cost_bps=10.0)
    assert_close(path.loc[0, "gross_return"], 0.01)
    assert math.isnan(path.loc[0, "turnover"])
    assert_close(path.loc[0, "cost"], 0.0)
    assert_close(path.loc[1, "gross_return"], 0.05)
    assert_close(path.loc[1, "turnover"], 1.0)
    assert_close(path.loc[1, "cost"], 0.001)
    assert_close(path.loc[1, "net_return"], 0.049)


def test_metric_conventions_are_stable() -> None:
    idx = pd.date_range("2023-01-06", periods=52, freq="W-FRI")
    returns = pd.Series([0.01, -0.005] * 26, index=idx)
    expected_cagr = float((1.0 + returns).prod() ** (52 / len(returns)) - 1.0)
    expected_vol = float(returns.std(ddof=1) * np.sqrt(52))
    metrics = metrics_from_series(returns)
    assert_close(cagr(returns), expected_cagr)
    assert_close(annualized_volatility(returns), expected_vol)
    assert_close(metrics["ann_return"], expected_cagr)
    assert_close(metrics["ann_vol"], expected_vol)
    assert_close(metrics["sharpe"], expected_cagr / expected_vol)
    assert_close(max_drawdown(pd.Series([0.10, -0.20, 0.10])), -0.20)
    assert_close(calmar_ratio(returns), expected_cagr / abs(max_drawdown(returns)))


def test_weekly_var_cvar_convention() -> None:
    returns = pd.Series(np.linspace(-0.10, 0.10, 101))
    var_5, cvar_5 = var_cvar(returns, 0.05)
    assert_close(var_5, float(returns.quantile(0.05)))
    assert_close(cvar_5, float(returns[returns <= var_5].mean()))


def main() -> None:
    test_turnover_and_cost_convention()
    test_portfolio_path_uses_next_week_returns_and_one_way_cost()
    test_metric_conventions_are_stable()
    test_weekly_var_cvar_convention()
    print("production metrics/cost tests passed")


if __name__ == "__main__":
    main()
