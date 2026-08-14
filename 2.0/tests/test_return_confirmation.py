import numpy as np
import pandas as pd

from systematic_trader.return_confirmation import cross_asset_features, expanding_ridge_predictions, four_week_labels


def fixture(rows=420):
    index = pd.date_range("2015-01-02", periods=rows, freq="W-FRI")
    x = np.arange(rows, dtype=float)
    names = ["SPY", "QQQ", "IWM", "HYG", "TLT", "PDBC", "GLD", "UUP", "XLE", "XLK"]
    return pd.DataFrame({name: 100 * np.exp((0.0005 + i * 0.0001) * x + 0.02 * np.sin(x / (5 + i))) for i, name in enumerate(names)}, index=index)


def test_cross_asset_features_are_prefix_invariant():
    full = fixture()
    cutoff = full.index[-20]
    expected = cross_asset_features(full, list(full.columns)).loc[:cutoff]
    actual = cross_asset_features(full.loc[:cutoff], list(full.columns))
    pd.testing.assert_frame_equal(expected, actual)


def test_expanding_ridge_strictly_embargoes_four_week_labels():
    prices = fixture()
    features = cross_asset_features(prices, list(prices.columns))
    month = prices.index.to_period("M").astype(str).to_numpy()
    decisions = prices.index[np.r_[month[:-1] != month[1:], True]]
    excess = pd.Series(np.sin(np.arange(len(prices)) / 9) / 100, index=prices.index)
    labels = four_week_labels(excess, decisions)
    _, audit = expanding_ridge_predictions(features, labels, decisions, penalty=1.0, minimum_training=24)
    predicted = audit[audit.predicted]
    assert len(predicted)
    assert predicted.embargo_pass.all()
    assert (pd.to_datetime(predicted.maximum_label_end) < predicted.index).all()


def test_predictions_are_prefix_invariant():
    prices = fixture()
    cutoff = prices.index[-25]
    full_features = cross_asset_features(prices, list(prices.columns))
    month = prices.index.to_period("M").astype(str).to_numpy()
    decisions = prices.index[np.r_[month[:-1] != month[1:], True]]
    excess = pd.Series(np.sin(np.arange(len(prices)) / 9) / 100, index=prices.index)
    labels = four_week_labels(excess, decisions)
    full, _ = expanding_ridge_predictions(full_features, labels, decisions, penalty=1.0, minimum_training=24)
    prefix_prices = prices.loc[:cutoff]
    prefix_features = cross_asset_features(prefix_prices, list(prices.columns))
    prefix_decisions = decisions[decisions <= cutoff]
    prefix_labels = four_week_labels(excess.loc[:cutoff], prefix_decisions)
    prefix, _ = expanding_ridge_predictions(prefix_features, prefix_labels, prefix_decisions, penalty=1.0, minimum_training=24)
    pd.testing.assert_series_equal(full.loc[:cutoff], prefix)
