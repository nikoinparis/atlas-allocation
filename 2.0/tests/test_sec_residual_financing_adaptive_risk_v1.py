import numpy as np
import pandas as pd

from scripts.run_sec_residual_financing_adaptive_risk_v1 import (
    adaptive_multipliers,
    apply_exposure,
    cap_standalone_risk_contributions,
    shock_table,
)


LEVERAGE_RULES = {
    "minimum": 1.0, "middle": 1.125, "maximum": 1.25,
    "minimum_history_weeks": 4, "volatility_lookback_weeks": 2,
    "short_trend_weeks": 2, "long_trend_weeks": 4,
    "drawdown_lookback_weeks": 4, "maximum_volatility_for_high": 10.0,
    "maximum_volatility_for_middle": 10.0, "minimum_short_trend": 0.0,
    "minimum_long_trend": 0.0, "minimum_drawdown_for_high": -1.0,
    "minimum_drawdown_for_middle": -1.0, "signal_lag_weeks": 1,
}

MARGIN_RULES = {
    "broker_maintenance_equity_ratio": 0.4,
    "internal_safety_equity_ratio": 0.5,
    "forced_deleverage_target": 1.0,
    "forced_deleverage_cost_bps": 50,
    "one_week_asset_shocks": [-0.2, -0.6],
}


def test_adaptive_multiplier_has_no_same_week_lookahead():
    index = pd.date_range("2025-01-03", periods=8, freq="W-FRI", tz="UTC")
    base = pd.Series([0.02] * 8, index=index)
    changed = base.copy(); changed.iloc[-1] = -0.9
    original_signal = adaptive_multipliers(base, LEVERAGE_RULES)
    changed_signal = adaptive_multipliers(changed, LEVERAGE_RULES)
    assert original_signal.iloc[-1] == changed_signal.iloc[-1]


def test_financing_is_charged_only_on_borrowed_fraction():
    index = pd.date_range("2025-01-03", periods=2, freq="W-FRI", tz="UTC")
    returns = pd.Series([0.01, 0.01], index=index)
    exposure = pd.Series([1.25, 1.25], index=index)
    path, audit = apply_exposure(returns, exposure, 0.052, 0.0, MARGIN_RULES)
    np.testing.assert_allclose(path, 1.25 * returns - 0.25 * 0.001)
    np.testing.assert_allclose(audit.borrowed_fraction, 0.25)


def test_safety_breach_forces_next_week_to_one_x():
    index = pd.date_range("2025-01-03", periods=2, freq="W-FRI", tz="UTC")
    returns = pd.Series([-0.6, 0.01], index=index)
    exposure = pd.Series([1.25, 1.25], index=index)
    _, audit = apply_exposure(returns, exposure, 0.08, 0.0, MARGIN_RULES)
    assert bool(audit.internal_safety_breach.iloc[0])
    assert audit.actual_multiplier.iloc[1] == 1.0
    assert bool(audit.forced_deleverage.iloc[1])


def test_risk_contribution_cap_uses_only_prior_history():
    dates = pd.date_range("2025-01-03", periods=20, freq="W-FRI", tz="UTC")
    weekly = pd.DataFrame({"a": [0.08, -0.08] * 10, "b": [0.01, -0.01] * 10, "c": [0.02, -0.02] * 10}, index=dates)
    weights = pd.DataFrame({"decision_at": [dates[-1]] * 3, "cik10": ["a", "b", "c"], "weight": [1 / 3] * 3})
    rules = {"lookback_weeks": 13, "minimum_history_weeks": 8, "maximum_standalone_volatility_contribution_share": 0.5, "maximum_iterations": 100}
    capped, diagnostic = cap_standalone_risk_contributions(weights, weekly, rules)
    assert np.isclose(capped.weight.sum(), 1.0)
    assert capped.set_index("cik10").weight["a"] < 1 / 3
    assert diagnostic.maximum_risk_contribution_share.iloc[0] <= 0.5 + 1e-6


def test_margin_shock_table_flags_sixty_percent_loss():
    shocks = shock_table(1.25, 0.08, MARGIN_RULES).set_index("asset_shock")
    assert not bool(shocks.loc[-0.2, "internal_safety_breach"])
    assert bool(shocks.loc[-0.6, "internal_safety_breach"])
