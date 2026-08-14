import pandas as pd

from src.systematic_trader.ggg_return_expansion import breadth_risk_on, redeploy_cash, turnover_transform


def test_breadth_signal_does_not_change_when_future_prices_change():
    dates = pd.date_range("2020-01-03", periods=60, freq="W-FRI")
    prices = pd.DataFrame({"SPY": range(100, 160), "QQQ": range(200, 260), "IWM": range(80, 140)}, index=dates, dtype=float)
    original = breadth_risk_on(prices, ["SPY", "QQQ", "IWM"], 0.66)
    shocked = prices.copy()
    shocked.iloc[-1] *= 0.1
    alternative = breadth_risk_on(shocked, ["SPY", "QQQ", "IWM"], 0.66)
    pd.testing.assert_series_equal(original.iloc[:-1], alternative.iloc[:-1])


def test_cash_redeployment_preserves_long_only_unit_sum():
    dates = pd.date_range("2024-01-05", periods=2, freq="W-FRI")
    weights = pd.DataFrame({"SPY": [0.4, 0.2], "QQQ": [0.2, 0.3], "BIL": [0.4, 0.5]}, index=dates)
    result = redeploy_cash(weights, pd.Series([True, False], index=dates), 0.5)
    assert abs(float(result.iloc[0].sum()) - 1.0) < 1e-12
    assert result.iloc[0]["BIL"] == 0.2
    pd.testing.assert_series_equal(result.iloc[1], weights.iloc[1])


def test_turnover_transforms_preserve_unit_sum_and_long_only():
    dates = pd.date_range("2024-01-05", periods=3, freq="W-FRI")
    weights = pd.DataFrame({"SPY": [0.5, 0.7, 0.2], "BIL": [0.5, 0.3, 0.8]}, index=dates)
    for kind, value in (("turnover_band", 0.01), ("minimum_total_change", 0.25), ("stagger", 0.5)):
        result = turnover_transform(weights, kind, value)
        assert result.sum(axis=1).sub(1.0).abs().max() < 1e-12
        assert result.min().min() >= 0.0
