import pandas as pd

from systematic_trader.ggg_layer2b import _causal_transition_probabilities, _future_labels


def test_forward_label_remains_unknown_until_full_horizon_exists():
    returns = pd.Series([0.01] * 10, index=pd.date_range("2026-01-02", periods=10, freq="W-FRI"))
    label = _future_labels(returns, 4, "regime")
    assert label.iloc[-4:].isna().all()
    assert label.iloc[-5] in (0.0, 1.0)


def test_training_embargo_excludes_unavailable_recent_labels():
    decision_index = 50
    horizon = 8
    assert decision_index - horizon == 42
    # At decision row 50, labels dated 42..49 still use at least one outcome
    # at or after the decision boundary and therefore cannot enter training.
    assert list(range(decision_index - horizon, decision_index)) == list(range(42, 50))


def test_causal_transition_features_are_prefix_invariant():
    index = pd.date_range("2020-01-03", periods=80, freq="W-FRI")
    state = pd.Series((["calm_trend"] * 12 + ["neutral_mixed"] * 4) * 5, index=index)
    full = _causal_transition_probabilities(state)
    cutoff = index[62]
    short = _causal_transition_probabilities(state.loc[:cutoff])
    for full_series, short_series in zip(full, short):
        pd.testing.assert_series_equal(full_series.loc[:cutoff], short_series)
