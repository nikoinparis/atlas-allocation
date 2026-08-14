import numpy as np
import pandas as pd

from systematic_trader.independent_return_sources import monthly_weights, signal_families


def prices(rows=140):
    index = pd.date_range("2020-01-03", periods=rows, freq="W-FRI")
    x = np.arange(rows, dtype=float)
    return pd.DataFrame({
        "SPY": 100.0 * np.exp(0.002 * x),
        "QQQ": 100.0 * np.exp(0.003 * x + 0.01 * np.sin(x / 5)),
        "IWM": 100.0 * np.exp(0.001 * x + 0.02 * np.cos(x / 7)),
        "BIL": 100.0 * np.exp(0.0002 * x),
    }, index=index)


def test_signals_and_weights_are_prefix_invariant():
    full = prices()
    cutoff = full.index[-9]
    full_signals = signal_families(full)
    prefix_signals = signal_families(full.loc[:cutoff])
    for name in full_signals:
        pd.testing.assert_frame_equal(full_signals[name].loc[:cutoff], prefix_signals[name])
        expected = monthly_weights(full_signals[name], full, ["SPY", "QQQ", "IWM"], top_n=2).loc[:cutoff]
        actual = monthly_weights(prefix_signals[name], full.loc[:cutoff], ["SPY", "QQQ", "IWM"], top_n=2)
        pd.testing.assert_frame_equal(expected, actual)


def test_final_incomplete_month_is_not_rebalanced():
    full = prices(139)
    signals = signal_families(full)["breakout_52w"]
    weights = monthly_weights(signals, full, ["SPY", "QQQ", "IWM"], top_n=2)
    if (full.index[-1] + pd.Timedelta(days=7)).month == full.index[-1].month:
        pd.testing.assert_series_equal(weights.iloc[-1], weights.iloc[-2], check_names=False)


def test_weights_are_long_only_and_fully_invested():
    full = prices()
    for signal in signal_families(full).values():
        weights = monthly_weights(signal, full, ["SPY", "QQQ", "IWM"], top_n=3)
        assert (weights >= -1e-14).all().all()
        assert np.allclose(weights.sum(axis=1), 1.0)
