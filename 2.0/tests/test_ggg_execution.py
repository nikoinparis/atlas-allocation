import pandas as pd

from src.systematic_trader.ggg_execution import asset_deadband, band_execution, scheduled_execution, volatility_adaptive_band


def targets():
    dates = pd.date_range("2024-01-05", periods=8, freq="W-FRI")
    return pd.DataFrame({"SPY": [0.5, 0.51, 0.7, 0.69, 0.3, 0.31, 0.6, 0.61], "BIL": [0.5, 0.49, 0.3, 0.31, 0.7, 0.69, 0.4, 0.39]}, index=dates)


def assert_valid(frame):
    assert frame.sum(axis=1).sub(1.0).abs().max() < 1e-10
    assert frame.min().min() >= 0.0


def test_scheduled_and_emergency_execution_are_valid():
    source = targets()
    for result in (
        scheduled_execution(source, cadence_weeks=2),
        scheduled_execution(source, monthly=True),
        scheduled_execution(source, monthly=True, emergency_turnover=0.15, emergency_cash_change=0.10),
    ):
        assert_valid(result)


def test_asset_and_asymmetric_bands_are_valid():
    source = targets()
    assert_valid(asset_deadband(source, 0.01))
    assert_valid(band_execution(source, entry_band=0.025, exit_band=0.005))


def test_adaptive_rule_is_prefix_invariant_to_future_price_shock():
    source = targets()
    prices = pd.DataFrame({"SPY": [100.0 + i for i in range(len(source))]}, index=source.index)
    original = volatility_adaptive_band(source, prices, calm_band=0.025, stress_band=0.005, spy_volatility_threshold=0.20, lookback_weeks=3)
    shocked = prices.copy(); shocked.iloc[-1, 0] *= 0.1
    alternative = volatility_adaptive_band(source, shocked, calm_band=0.025, stress_band=0.005, spy_volatility_threshold=0.20, lookback_weeks=3)
    pd.testing.assert_frame_equal(original.iloc[:-1], alternative.iloc[:-1])
