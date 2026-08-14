"""Signal engine for Recovery Options Overlay v3.

v3 is a focused follow-up to the standalone recovery options experiment. It
keeps the same proxy-only option-pricing caveats, but changes the trade design:

* outright calls only,
* smaller staged entries,
* no late entries after the rebound has mostly happened,
* add-ons only after recovery confirmation improves.

All signal inputs are lagged one week. The current regime label is still read by
the backtest at decision time, matching the v1/v2/recovery convention already in
this research namespace.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data

VIX_PATH = option_data.DATA / "01_data_hub" / "vix_term_structure.csv"

V3_UNDERLYINGS = ["SPY", "QQQ"]

RISK_ON_IMPROVING_STATES = {"recovery_fragile", "recovery_confirmed", "calm_trend"}
ADD_CONFIRM_STATES = {"recovery_confirmed", "calm_trend"}
DEFENSIVE_STATES = {"stressed_panic", "recovery_fragile"}
PANIC_STATE = "stressed_panic"

STATE_SCORE = {
    "stressed_panic": 0.0,
    "neutral_mixed": 1.0,
    "recovery_fragile": 2.0,
    "recovery_confirmed": 3.0,
    "calm_trend": 4.0,
}

LOOKBACK_DEFENSIVE_WEEKS = 26
DEFENSIVE_DRAWDOWN = -0.10
MIN_BASELINE_WEIGHT = 0.02

SURPLUS_MIN = 0.0025
SURPLUS_ADD_MIN = 0.005
SOFT_STAGE1_REQUIRED = 3
SOFT_STAGE2_REQUIRED = 4

# Late-entry filters. Weekly data approximates 20-40 trading days with 4-8 weeks.
MAX_RECOVERY_FROM_8W_LOW = 0.075
MAX_TRANSITION_AGE_WEEKS = 8
MAX_DIST_FAST_MA = 0.055
VIX_NORMALIZED_PCT = 0.35
REBOUND_AFTER_VIX_NORMALIZED = 0.05
MAX_BREAKEVEN_TO_REALIZED_MOVE = 1.25
VOL_SPIKE_RATIO = 1.65
VOL_PERCENTILE_OK = 0.85


def build_recovery_v3_signals(underlyings: list[str] | None = None, lag_weeks: int = 1) -> "V3SignalPanel":
    """Build causal per-underlying and market-level v3 signal features."""

    underlyings = underlyings or V3_UNDERLYINGS
    prices = option_data.load_weekly_prices(underlyings)

    ret_4w = prices.pct_change(4)
    ret_8w = prices.pct_change(8)
    ret_12w = prices.pct_change(12)
    accel_4w = ret_4w - ret_4w.shift(4)
    accel_8w = ret_8w - ret_8w.shift(8)

    ma_fast = prices.rolling(10).mean()
    ma_mid = prices.rolling(20).mean()
    ma_long = prices.rolling(40).mean()
    ma_fast_slope = ma_fast / ma_fast.shift(4) - 1.0
    ma_mid_slope = ma_mid / ma_mid.shift(4) - 1.0
    dist_fast_ma = prices / ma_fast - 1.0
    dist_mid_ma = prices / ma_mid - 1.0
    dist_long_ma = prices / ma_long - 1.0
    reclaim_fast = (prices > ma_fast).astype(float)
    reclaim_mid = (prices > ma_mid).astype(float)

    low_8w = prices.rolling(8).min()
    low_12w = prices.rolling(12).min()
    high_52w = prices.rolling(52).max()
    recovery_from_8w_low = prices / low_8w - 1.0
    recovery_from_12w_low = prices / low_12w - 1.0
    drawdown_from_52w_high = prices / high_52w - 1.0
    weeks_since_8w_low = _weeks_since_min(prices, 8)

    log_ret = np.log(prices / prices.shift(1))
    realized_vol = log_ret.rolling(13).std(ddof=1) * np.sqrt(52.0)
    realized_vol_pct = option_data.iv_percentile(realized_vol, lookback_weeks=52)
    vol_spike = (realized_vol / realized_vol.shift(4)).replace([np.inf, -np.inf], np.nan)

    # Drift is deliberately simple and visible. The option gate still asks the
    # priced structure whether this projected move clears breakeven.
    weekly_drift = ret_12w / 12.0

    per_ticker = {
        "ret_4w": ret_4w,
        "ret_8w": ret_8w,
        "ret_12w": ret_12w,
        "accel_4w": accel_4w,
        "accel_8w": accel_8w,
        "ma_fast_slope": ma_fast_slope,
        "ma_mid_slope": ma_mid_slope,
        "dist_fast_ma": dist_fast_ma,
        "dist_mid_ma": dist_mid_ma,
        "dist_long_ma": dist_long_ma,
        "reclaim_fast": reclaim_fast,
        "reclaim_mid": reclaim_mid,
        "recovery_from_8w_low": recovery_from_8w_low,
        "recovery_from_12w_low": recovery_from_12w_low,
        "drawdown_from_52w_high": drawdown_from_52w_high,
        "weeks_since_8w_low": weeks_since_8w_low,
        "realized_vol": realized_vol,
        "realized_vol_pct": realized_vol_pct,
        "vol_spike": vol_spike,
        "weekly_drift": weekly_drift,
    }
    per_ticker = {name: df.shift(lag_weeks) for name, df in per_ticker.items()}
    market = _build_market_features(lag_weeks)
    return V3SignalPanel(per_ticker=per_ticker, market=market, underlyings=underlyings)


def _build_market_features(lag_weeks: int) -> pd.DataFrame:
    states = option_data.load_market_states()
    out = pd.DataFrame(index=states.index)

    state = states["market_state"].astype(str)
    out["market_state"] = state
    out["state_score"] = state.map(STATE_SCORE).fillna(1.0)
    out["state_score_delta_4w"] = out["state_score"] - out["state_score"].shift(4)
    out["market_drawdown"] = pd.to_numeric(states.get("market_drawdown"), errors="coerce")

    was_defensive = pd.Series(False, index=state.index)
    deep_dd = pd.Series(False, index=state.index)
    for k in range(1, LOOKBACK_DEFENSIVE_WEEKS + 1):
        was_defensive = was_defensive | state.shift(k).isin(DEFENSIVE_STATES)
        deep_dd = deep_dd | (out["market_drawdown"].shift(k) <= DEFENSIVE_DRAWDOWN)
    out["recently_defensive"] = (was_defensive | deep_dd).astype(float)
    out["transition_flag"] = _transition_flag(state)
    out["transition_age_weeks"] = _transition_age(state)
    out["now_improving"] = state.isin(RISK_ON_IMPROVING_STATES).astype(float)
    out["not_panic"] = (state != PANIC_STATE).astype(float)

    vix = _load_vix().reindex(out.index)
    out["vix"] = vix["VIX"]
    out["vix3m"] = vix["VIX3M"]
    vix_pct = vix["VIX"].rolling(52, min_periods=12).apply(_rank, raw=True)
    out["vix_percentile"] = vix_pct
    out["vix_change_4w"] = vix["VIX"] / vix["VIX"].shift(4) - 1.0
    out["vix_available"] = vix["VIX"].notna().astype(float)

    elevated_recently = pd.Series(False, index=out.index)
    for k in range(1, 9):
        elevated_recently = elevated_recently | (vix_pct.shift(k) > 0.70)
    out["vix_normalizing"] = ((vix_pct < 0.70) & elevated_recently).astype(float)
    ratio = vix["VIX"] / vix["VIX3M"]
    out["vix_ratio"] = ratio
    out["vix_term_ok"] = ((ratio <= 1.0) | ratio.isna()).astype(float)

    credit = option_data.load_weekly_prices(["HYG", "LQD"]).reindex(out.index)
    cr = credit["HYG"] / credit["LQD"]
    out["credit_ratio_change_4w"] = cr / cr.shift(4) - 1.0
    out["credit_improvement"] = ((out["credit_ratio_change_4w"] > 0) & (credit["HYG"].pct_change(4) > 0)).astype(float)
    out["credit_deterioration"] = (out["credit_ratio_change_4w"] < -0.015).astype(float)
    out["credit_available"] = (credit["HYG"].notna() & credit["LQD"].notna()).astype(float)

    return out.shift(lag_weeks)


@dataclass
class V3SignalPanel:
    per_ticker: dict[str, pd.DataFrame]
    market: pd.DataFrame
    underlyings: list[str]

    def feature_row(self, date, ticker: str) -> dict:
        row: dict = {}
        for name, df in self.per_ticker.items():
            row[name] = _safe(df, date, ticker)
        for name in self.market.columns:
            row[name] = _safe_series(self.market[name], date)
        return row


@dataclass
class V3Decision:
    active: bool
    reasons_failed: list[str] = field(default_factory=list)
    late_entry_reasons: list[str] = field(default_factory=list)
    soft_score: int = 0
    expected_move: float = np.nan
    breakeven_move: float = np.nan
    surplus: float = np.nan
    required_to_realized: float = np.nan


def expected_forward_move(weekly_drift: float, holding_weeks: float) -> float:
    if weekly_drift is None or not np.isfinite(weekly_drift):
        return np.nan
    return float(weekly_drift) * float(holding_weeks)


def late_entry_reasons(features: dict, *, surplus: float, breakeven_move: float, holding_weeks: float) -> tuple[list[str], float]:
    """Return visible reasons a new entry/add-on is too late."""

    reasons: list[str] = []
    rec8 = features.get("recovery_from_8w_low")
    if _ge(rec8, MAX_RECOVERY_FROM_8W_LOW):
        reasons.append("rebound_already_extended")

    age = features.get("transition_age_weeks")
    if _ge(age, MAX_TRANSITION_AGE_WEEKS):
        reasons.append("transition_too_old")

    if not (np.isfinite(surplus) and surplus > SURPLUS_MIN):
        reasons.append("surplus_compressed")

    if _le(features.get("vix_percentile"), VIX_NORMALIZED_PCT) and _ge(rec8, REBOUND_AFTER_VIX_NORMALIZED):
        reasons.append("vix_normalized_after_rebound")

    if _ge(features.get("dist_fast_ma"), MAX_DIST_FAST_MA):
        reasons.append("price_too_extended_above_fast_ma")

    rv = features.get("realized_vol")
    expected_realized_move = np.nan
    if rv is not None and np.isfinite(rv) and rv > 0:
        expected_realized_move = float(rv) * np.sqrt(max(float(holding_weeks), 1.0) / 52.0)
        if np.isfinite(breakeven_move) and breakeven_move > MAX_BREAKEVEN_TO_REALIZED_MOVE * expected_realized_move:
            reasons.append("breakeven_too_large_vs_realized_vol")

    required_to_realized = breakeven_move / expected_realized_move if np.isfinite(expected_realized_move) and expected_realized_move > 0 else np.nan
    return reasons, required_to_realized


def evaluate_stage1_entry(
    features: dict,
    *,
    market_state: str,
    baseline_weight: float,
    baseline_weight_change_4w: float,
    breakeven_move: float,
    holding_weeks: float,
) -> V3Decision:
    """Pilot entry: early recovery, positive surplus, and not too late."""

    expected_move = expected_forward_move(features.get("weekly_drift"), holding_weeks)
    surplus = expected_move - breakeven_move if np.isfinite(expected_move) and np.isfinite(breakeven_move) else np.nan
    late_reasons, required_to_realized = late_entry_reasons(
        features, surplus=surplus, breakeven_move=breakeven_move, holding_weeks=holding_weeks
    )
    failed: list[str] = []

    if not (_ge(baseline_weight, MIN_BASELINE_WEIGHT) or _pos(baseline_weight_change_4w)):
        failed.append("baseline_weight_not_positive_or_rising")
    if market_state == PANIC_STATE:
        failed.append("panic_not_fading")
    if market_state not in RISK_ON_IMPROVING_STATES:
        failed.append("regime_not_improving")
    if not _pos(features.get("recently_defensive")):
        failed.append("not_recently_defensive")
    if not _pos(features.get("accel_4w")):
        failed.append("trend_acceleration_not_positive")
    if not (np.isfinite(surplus) and surplus > SURPLUS_MIN):
        failed.append("expected_move_surplus_not_positive")

    soft = {
        "transition_flag": _pos(features.get("transition_flag")),
        "ma_fast_slope": _pos(features.get("ma_fast_slope")),
        "reclaim_fast": _pos(features.get("reclaim_fast")),
        "vix_normalizing": _pos(features.get("vix_normalizing")) or not _pos(features.get("vix_available")),
        "credit_improvement": _pos(features.get("credit_improvement")) or not _pos(features.get("credit_available")),
        "vol_ok": _le(features.get("realized_vol_pct"), VOL_PERCENTILE_OK) and not _ge(features.get("vol_spike"), VOL_SPIKE_RATIO),
    }
    soft_score = int(sum(1 for ok in soft.values() if ok))
    if soft_score < SOFT_STAGE1_REQUIRED:
        failed.append(f"insufficient_stage1_confirmations({soft_score}/{SOFT_STAGE1_REQUIRED})")
    if late_reasons:
        failed.append("late_entry_blocked")

    return V3Decision(
        active=not failed,
        reasons_failed=failed,
        late_entry_reasons=late_reasons,
        soft_score=soft_score,
        expected_move=expected_move,
        breakeven_move=breakeven_move,
        surplus=surplus,
        required_to_realized=required_to_realized,
    )


def evaluate_stage2_addon(
    features: dict,
    *,
    market_state: str,
    breakeven_move: float,
    holding_weeks: float,
    weeks_since_pilot: int,
    max_add_window_weeks: int,
) -> V3Decision:
    """Add-on entry: confirmation improved and late-entry filters still pass."""

    expected_move = expected_forward_move(features.get("weekly_drift"), holding_weeks)
    surplus = expected_move - breakeven_move if np.isfinite(expected_move) and np.isfinite(breakeven_move) else np.nan
    late_reasons, required_to_realized = late_entry_reasons(
        features, surplus=surplus, breakeven_move=breakeven_move, holding_weeks=holding_weeks
    )
    failed: list[str] = []

    if weeks_since_pilot > max_add_window_weeks:
        failed.append("add_window_expired")
    if market_state not in RISK_ON_IMPROVING_STATES:
        failed.append("regime_not_confirming")
    if not (market_state in ADD_CONFIRM_STATES or _pos(features.get("state_score_delta_4w"))):
        failed.append("rerisk_confirmation_not_improved")
    if not (np.isfinite(surplus) and surplus > SURPLUS_ADD_MIN):
        failed.append("addon_surplus_not_positive")
    if _ge(features.get("vol_spike"), VOL_SPIKE_RATIO):
        failed.append("vol_spike")

    soft = {
        "credit_improvement": _pos(features.get("credit_improvement")) or not _pos(features.get("credit_available")),
        "vix_stable": _pos(features.get("vix_normalizing")) or _le(features.get("vix_percentile"), 0.70) or not _pos(features.get("vix_available")),
        "ma_fast_slope": _pos(features.get("ma_fast_slope")),
        "reclaim_mid": _pos(features.get("reclaim_mid")),
        "not_extended": not _ge(features.get("dist_fast_ma"), MAX_DIST_FAST_MA),
    }
    soft_score = int(sum(1 for ok in soft.values() if ok))
    if soft_score < SOFT_STAGE2_REQUIRED:
        failed.append(f"insufficient_stage2_confirmations({soft_score}/{SOFT_STAGE2_REQUIRED})")
    if late_reasons:
        failed.append("late_entry_blocked")

    return V3Decision(
        active=not failed,
        reasons_failed=failed,
        late_entry_reasons=late_reasons,
        soft_score=soft_score,
        expected_move=expected_move,
        breakeven_move=breakeven_move,
        surplus=surplus,
        required_to_realized=required_to_realized,
    )


def thesis_invalidation_reasons(features: dict, *, market_state: str, surplus: float) -> list[str]:
    reasons: list[str] = []
    if market_state == PANIC_STATE:
        reasons.append("panic_returned")
    if _pos(features.get("credit_deterioration")):
        reasons.append("credit_deteriorated")
    if not _pos(features.get("ma_fast_slope")) and not _pos(features.get("accel_4w")):
        reasons.append("trend_recovery_failed")
    if not _pos(features.get("reclaim_fast")):
        reasons.append("lost_recovery_ma")
    if np.isfinite(surplus) and surplus < -0.02:
        reasons.append("surplus_materially_negative")
    if _ge(features.get("vix_percentile"), 0.90) or _ge(features.get("vol_spike"), VOL_SPIKE_RATIO):
        reasons.append("vix_stress_returned")
    return reasons


def _transition_flag(state: pd.Series) -> pd.Series:
    recent_def = pd.Series(False, index=state.index)
    for k in range(1, 5):
        recent_def = recent_def | state.shift(k).isin(DEFENSIVE_STATES | {"neutral_mixed"})
    return (state.isin(RISK_ON_IMPROVING_STATES) & recent_def).astype(float)


def _transition_age(state: pd.Series) -> pd.Series:
    improving = state.isin(RISK_ON_IMPROVING_STATES)
    ages = []
    age = np.nan
    for ok in improving:
        if ok:
            age = 0.0 if not np.isfinite(age) else age + 1.0
        else:
            age = np.nan
        ages.append(age)
    return pd.Series(ages, index=state.index)


def _load_vix() -> pd.DataFrame:
    df = pd.read_csv(VIX_PATH)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    try:
        df["Date"] = df["Date"].dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return df.dropna(subset=["Date"]).set_index("Date")


def _weeks_since_min(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    def _wsm(arr: np.ndarray) -> float:
        if np.all(np.isnan(arr)):
            return np.nan
        idx = int(np.nanargmin(arr))
        return float(len(arr) - 1 - idx)

    return prices.rolling(window, min_periods=4).apply(_wsm, raw=True)


def _rank(window: np.ndarray) -> float:
    current = window[-1]
    if np.isnan(current):
        return np.nan
    valid = window[~np.isnan(window)]
    if len(valid) < 2:
        return np.nan
    return float((valid <= current).mean())


def _pos(x) -> bool:
    return x is not None and np.isfinite(x) and x > 0


def _ge(x, t) -> bool:
    return x is not None and np.isfinite(x) and x >= t


def _le(x, t) -> bool:
    return x is not None and np.isfinite(x) and x <= t


def _safe(df: pd.DataFrame, date, ticker: str, default: float = np.nan) -> float:
    try:
        val = df.loc[date, ticker]
    except (KeyError, IndexError):
        return default
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if np.isfinite(val) else default


def _safe_series(s: pd.Series, date, default=np.nan):
    try:
        val = s.loc[date]
    except (KeyError, IndexError):
        return default
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    if isinstance(val, str):
        return val
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if np.isfinite(val) else default
