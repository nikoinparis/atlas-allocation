import pandas as pd

import scripts.run_sec_independent_market_regime_activation_v1 as subject


def test_regime_target_market_only_uses_threshold():
    index = pd.date_range("2026-01-02", periods=3, freq="W-FRI")
    features = pd.DataFrame({
        "market_trend": [1, 1, 0], "low_volatility": [1, 0, 0],
        "credit_strong": [1, 1, 0], "vix_contango": [1, 1, 1],
        "breadth_strong": [1, 0, 0], "risk_on_score": [5, 3, 1],
    }, index=index).astype({c: bool for c in ["market_trend", "low_volatility", "credit_strong", "vix_contango", "breadth_strong"]})
    target, panel = subject.regime_target(
        pd.Series(False, index=index), features, pd.Series(True, index=index), 3, "market_only"
    )
    assert target.cash_conversion.tolist() == [0.8, 0.8, 0.0]
    assert panel.risk_on_score.tolist() == [5, 3, 1]


def test_signal_delay_shifts_market_and_base_state():
    index = pd.date_range("2026-01-02", periods=3, freq="W-FRI")
    columns = ["market_trend", "low_volatility", "credit_strong", "vix_contango", "breadth_strong"]
    features = pd.DataFrame(False, index=index, columns=columns)
    features.loc[index[0], columns] = True
    features["risk_on_score"] = features[columns].sum(axis=1)
    base = pd.Series([True, False, False], index=index)
    target, _ = subject.regime_target(base, features, pd.Series(True, index=index), 5, "union", delay=1)
    assert target.cash_conversion.tolist() == [0.0, 0.8, 0.0]
