import pandas as pd

import scripts.run_sec_cluster_aware_cash_sleeve_v1 as subject


def test_cap_weights_preserves_sum_and_limit():
    actual = subject.cap_weights(pd.Series({"a": 0.8, "b": 0.1, "c": 0.1}), 0.4)
    assert abs(actual.sum() - 1.0) < 1e-12
    assert actual.max() <= 0.4 + 1e-12


def test_risk_history_cannot_see_rebalance_week():
    index = pd.date_range("2026-01-02", periods=8, freq="W-FRI")
    prices = pd.DataFrame({"a": range(10, 18), "b": range(20, 28)}, index=index, dtype=float)
    cohorts = pd.DataFrame({
        "decision_at": [index[5], index[5]], "cik10": ["a", "b"],
        "company_name_as_filed": ["A", "B"], "sector": ["x", "y"], "score": [1.0, 0.5],
    })
    targets, _ = subject.build_weighted_targets(cohorts, prices, index, "inverse_volatility", 3, 1.0, 2.0)
    changed = prices.copy()
    changed.loc[index[5]:, "a"] = 9999.0
    repeated, _ = subject.build_weighted_targets(cohorts, changed, index, "inverse_volatility", 3, 1.0, 2.0)
    assert targets == repeated


def test_equal_weights_are_exact_control_weights():
    index = pd.date_range("2026-01-02", periods=4, freq="W-FRI")
    prices = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 3, 4, 5]}, index=index)
    cohorts = pd.DataFrame({
        "decision_at": [index[1], index[1]], "cik10": ["a", "b"],
        "company_name_as_filed": ["A", "B"], "sector": ["x", "y"], "score": [1.0, 0.5],
    })
    targets, _ = subject.build_weighted_targets(cohorts, prices, index, "equal", 26, 0.0, 1.0)
    assert list(targets.values())[0] == {"a": 0.5, "b": 0.5}
