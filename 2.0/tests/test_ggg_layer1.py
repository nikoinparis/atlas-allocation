import numpy as np
import pandas as pd

from src.systematic_trader.ggg_layer1 import build_layer1_bundle, panel_score


def test_panel_score_is_bounded_and_centered_rank():
    frame = pd.DataFrame([[1.0, 2.0, 3.0]], columns=list("ABC"))
    result = panel_score(frame)
    assert result.iloc[0].tolist() == [-1.0, 0.0, 1.0]


def test_price_signals_are_prefix_invariant():
    dates = pd.date_range("2018-01-05", periods=300, freq="W-FRI")
    assets = ["SPY", "QQQ", "BIL", "TLT", "GLD"]
    prices = pd.DataFrame({asset: 100.0 * np.exp(np.linspace(0, 0.4 + i / 10, len(dates))) for i, asset in enumerate(assets)}, index=dates)
    daily_dates = pd.date_range(dates.min() - pd.Timedelta(days=200), dates.max(), freq="B")
    daily = pd.DataFrame(0.001, index=daily_dates, columns=assets)
    actions = pd.DataFrame({"event_date": [dates[100]], "ticker": ["SPY"], "action_type": ["cash_distribution"], "amount": [1.0]})
    original = build_layer1_bundle(prices, daily_log_returns=daily, distribution_actions=actions)
    shocked = prices.copy(); shocked.iloc[-1] *= 0.2
    alternative = build_layer1_bundle(shocked, daily_log_returns=daily, distribution_actions=actions)
    for name in original.panels:
        pd.testing.assert_frame_equal(original.panels[name].iloc[:-1], alternative.panels[name].iloc[:-1])


def test_missing_regime_inputs_fail_closed_in_status():
    dates = pd.date_range("2020-01-03", periods=60, freq="W-FRI")
    assets = ["SPY", "BIL"]
    prices = pd.DataFrame({"SPY": np.arange(100.0, 160.0), "BIL": np.arange(90.0, 150.0)}, index=dates)
    daily = pd.DataFrame(0.0, index=pd.date_range("2019-01-01", dates.max(), freq="B"), columns=assets)
    bundle = build_layer1_bundle(prices, daily_log_returns=daily, distribution_actions=pd.DataFrame())
    assert bundle.source_status["regime_features"].startswith("blocked_")
