import pandas as pd

import scripts.run_sec_multi_horizon_activation_ensemble_v1 as subject


def test_activation_votes_are_strictly_lagged():
    index = pd.date_range("2026-01-02", periods=8, freq="W-FRI")
    returns = pd.DataFrame({"leader": [0.0] * 8, "cash_conversion": [0.01] * 8}, index=index)
    original = subject.activation_votes(returns, [3])
    changed = returns.copy()
    changed.iloc[-1, 1] = -0.9
    revised = subject.activation_votes(changed, [3])
    pd.testing.assert_series_equal(original.iloc[-1], revised.iloc[-1])


def test_vote_threshold_and_proportional_sizing():
    index = pd.date_range("2026-01-02", periods=5, freq="W-FRI")
    returns = pd.DataFrame({"leader": [0.0] * 5, "cash_conversion": [0.1, -0.2, 0.1, 0.1, 0.1]}, index=index)
    breadth = pd.Series(True, index=index)
    target, panel = subject.ensemble_target(returns, breadth, [1, 2], 1, "proportional")
    assert (target.cash_conversion >= 0).all()
    assert (target.cash_conversion <= 0.8).all()
    assert panel.vote_count.equals(panel[["vote_1w", "vote_2w"]].sum(axis=1))
