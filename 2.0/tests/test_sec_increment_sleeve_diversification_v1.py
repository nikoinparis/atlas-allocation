import pandas as pd

import scripts.run_sec_increment_sleeve_diversification_v1 as subject


def test_routed_target_preserves_base_and_routes_only_increment():
    index = pd.date_range("2026-01-02", periods=2, freq="W-FRI")
    base = pd.DataFrame({"leader": [0.5, 1.0], "cash_conversion": [0.5, 0.0]}, index=index)
    route = pd.DataFrame({"cash_conversion": [0.5, 0.5], "profitability": [0.5, 0.5]}, index=index)
    target = subject.routed_target(base, pd.Series([0.2, 0.0], index=index), route)
    assert target.loc[index[0]].round(12).to_dict() == {"leader": 0.3, "cash_conversion": 0.6, "profitability": 0.1}
    assert target.loc[index[1]].to_dict() == {"leader": 1.0, "cash_conversion": 0.0, "profitability": 0.0}


def test_inverse_volatility_route_is_strictly_lagged_and_sums_to_one():
    index = pd.date_range("2026-01-02", periods=5, freq="W-FRI")
    returns = pd.DataFrame({"a": [0.01, 0.02, -0.01, 0.04, 9.0], "b": [0.02, -0.01, 0.03, 0.01, -9.0]}, index=index)
    route = subject.causal_inverse_vol_route(returns, ["a", "b"], 0.25, 3)
    changed = returns.copy()
    changed.loc[index[-1], ["a", "b"]] = [-99.0, 99.0]
    repeated = subject.causal_inverse_vol_route(changed, ["a", "b"], 0.25, 3)
    pd.testing.assert_series_equal(route.loc[index[-1]], repeated.loc[index[-1]])
    assert route.sum(axis=1).round(12).eq(1.0).all()


def test_actual_increment_never_changes_base_without_raw_increment():
    index = pd.date_range("2026-01-02", periods=4, freq="W-FRI")
    base = pd.DataFrame({"leader": [0.5] * 4, "cash_conversion": [0.5] * 4}, index=index)
    actual = subject.actual_increment(base, pd.Series(0.0, index=index))
    assert actual.eq(0.0).all()


def test_fixed_route_is_ticker_agnostic_and_sums_to_one():
    index = pd.date_range("2026-01-02", periods=3, freq="W-FRI")
    route = subject.fixed_route(index, ["profitability", "shareholder_discipline"], 0.5)
    assert route.sum(axis=1).round(12).eq(1.0).all()
    assert route.iloc[0].to_dict() == {
        "cash_conversion": 0.5,
        "profitability": 0.25,
        "shareholder_discipline": 0.25,
    }
