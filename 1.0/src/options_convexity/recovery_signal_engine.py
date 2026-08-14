"""Recovery / regime-transition signal engine.

The central hypothesis of this experiment: long-premium upside options are only
worth their volatility-risk-premium cost during RARE defensive-to-risk-on
recovery transitions - panic rebounds where price is re-accelerating AND
volatility is normalizing AND the expected move clears the option's breakeven.

This engine builds those signals (all CAUSAL / lagged one week) and evaluates a
grouped activation gate. Thresholds are coarse and kept visible in the config
block - deliberately not tuned to make the backtest pass.

Reads (read-only): weekly prices (SPY/QQQ + HYG/LQD), the market-state history,
and the VIX term-structure file. Never writes; never touches production or v1/v2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data

ROOT = option_data.ROOT
VIX_PATH = option_data.DATA / "01_data_hub" / "vix_term_structure.csv"

# Underlyings for THIS experiment (best option liquidity). The engine is written
# generically so future versions could add more, but v0 is SPY/QQQ only.
RECOVERY_UNDERLYINGS = ["SPY", "QQQ"]

# Regime state groupings.
RISK_ON_IMPROVING_STATES = {"recovery_fragile", "recovery_confirmed", "calm_trend"}
DEFENSIVE_STATES = {"stressed_panic", "recovery_fragile"}
PANIC_STATE = "stressed_panic"

# ---------------------- coarse activation thresholds ----------------------
LOOKBACK_DEFENSIVE_WEEKS = 26      # "recently defensive" window.
DEFENSIVE_DRAWDOWN = -0.10         # market drawdown that counts as stress.
MIN_RECOVERY_FROM_LOW = 0.05       # price must be >=5% off its recent low...
MAX_RECOVERY_FROM_LOW = 0.40       # ...but not already fully run (avoid late entry).
RECOVERY_LOW_WINDOW = 26           # window for the recent low.
HIGH_WINDOW = 52                   # window for the recent high (drawdown-from-high).
MIN_BASELINE_WEIGHT = 0.02

VOL_PERCENTILE_CALM = 0.85         # IV/realized-vol "not extremely expensive".
VOL_SPIKE_RATIO = 1.75             # realized vol exploding => block.
SOFT_GATES_REQUIRED = 4            # need >=4 of the soft confirmation gates.

SURPLUS_MARGIN = 0.01              # expected move must beat breakeven by >=1%.


def build_recovery_signals(underlyings: list[str] | None = None, lag_weeks: int = 1) -> "RecoverySignalPanel":
    """Build the full causal recovery signal panel."""

    underlyings = underlyings or RECOVERY_UNDERLYINGS
    prices = option_data.load_weekly_prices(underlyings)

    # ---- Per-underlying price/trend/recovery features ---------------------
    ret_4w = prices.pct_change(4)
    ret_8w = prices.pct_change(8)
    ret_12w = prices.pct_change(12)
    accel_4w = ret_4w - ret_4w.shift(4)
    accel_8w = ret_8w - ret_8w.shift(8)

    ma_fast = prices.rolling(10).mean()
    ma_slope = ma_fast / ma_fast.shift(4) - 1.0
    ma_mid = prices.rolling(20).mean()
    ma_long = prices.rolling(40).mean()
    dist_from_ma = prices / ma_long - 1.0
    reclaim_flag = (prices > ma_mid).astype(float)  # reclaimed the 20w MA.

    roll_high = prices.rolling(HIGH_WINDOW).max()
    roll_low = prices.rolling(RECOVERY_LOW_WINDOW).min()
    drawdown_from_high = prices / roll_high - 1.0
    recovery_from_low = prices / roll_low - 1.0

    # Weeks since the recent low (a young recovery is preferred over an old one).
    days_since_low = _weeks_since_min(prices, RECOVERY_LOW_WINDOW) * 7.0

    weekly_drift = ret_12w / 12.0  # expected-forward-move proxy input.

    log_ret = np.log(prices / prices.shift(1))
    realized_vol = log_ret.rolling(13).std(ddof=1) * np.sqrt(52.0)
    realized_vol_pct = option_data.iv_percentile(realized_vol, lookback_weeks=52)
    vol_spike = (realized_vol / realized_vol.shift(4)).replace([np.inf, -np.inf], np.nan)

    per_ticker = {
        "ret_4w": ret_4w, "ret_8w": ret_8w, "ret_12w": ret_12w,
        "accel_4w": accel_4w, "accel_8w": accel_8w,
        "ma_slope": ma_slope, "dist_from_ma": dist_from_ma, "reclaim_flag": reclaim_flag,
        "drawdown_from_high": drawdown_from_high, "recovery_from_low": recovery_from_low,
        "days_since_low": days_since_low, "weekly_drift": weekly_drift,
        "realized_vol": realized_vol, "realized_vol_pct": realized_vol_pct, "vol_spike": vol_spike,
    }
    per_ticker = {k: v.shift(lag_weeks) for k, v in per_ticker.items()}

    market = _build_market_features(lag_weeks)

    return RecoverySignalPanel(per_ticker=per_ticker, market=market, underlyings=underlyings)


def _build_market_features(lag_weeks: int = 1) -> pd.DataFrame:
    """Build market-level regime / VIX / credit recovery features (causal)."""

    states = option_data.load_market_states()
    out = pd.DataFrame(index=states.index)

    state = states["market_state"].astype(str)
    out["market_state"] = state
    mdd = pd.to_numeric(states.get("market_drawdown"), errors="coerce")
    out["market_drawdown"] = mdd

    # "Recently defensive": in the last N weeks the market was in a defensive
    # state OR experienced a meaningful drawdown.
    was_defensive = pd.Series(False, index=state.index)
    deep_dd = pd.Series(False, index=state.index)
    for k in range(1, LOOKBACK_DEFENSIVE_WEEKS + 1):
        was_defensive = was_defensive | state.shift(k).isin(DEFENSIVE_STATES)
        deep_dd = deep_dd | (mdd.shift(k) <= DEFENSIVE_DRAWDOWN)
    out["recently_defensive"] = (was_defensive | deep_dd).astype(float)

    out["now_improving"] = state.isin(RISK_ON_IMPROVING_STATES).astype(float)
    out["not_panic"] = (state != PANIC_STATE).astype(float)

    # Defensive -> risk-on transition: improving now, defensive in last 4 weeks.
    recent_def = pd.Series(False, index=state.index)
    for k in range(1, 5):
        recent_def = recent_def | state.shift(k).isin(DEFENSIVE_STATES | {"neutral_mixed"})
    out["transition_flag"] = (state.isin(RISK_ON_IMPROVING_STATES) & recent_def).astype(float)

    # ---- VIX features -----------------------------------------------------
    vix = _load_vix().reindex(out.index)
    out["vix"] = vix["VIX"]
    vix_pct = vix["VIX"].rolling(52, min_periods=12).apply(_rank, raw=True)
    out["vix_percentile"] = vix_pct
    # VIX normalizing: percentile has come down from an elevated reading.
    elevated_recently = pd.Series(False, index=out.index)
    for k in range(1, 9):
        elevated_recently = elevated_recently | (vix_pct.shift(k) > 0.70)
    out["vix_normalizing"] = ((vix_pct < 0.70) & elevated_recently).astype(float)
    # VIX term structure: ratio<1 is contango (calm); normalizing = flipped from
    # backwardation (>1) to contango within the last 4 weeks.
    ratio = vix["VIX"] / vix["VIX3M"]
    out["vix_ratio"] = ratio
    flipped = pd.Series(False, index=out.index)
    for k in range(1, 5):
        flipped = flipped | (ratio.shift(k) > 1.0)
    out["vix_term_normalizing"] = ((ratio <= 1.0) & flipped).astype(float)
    out["vix_available"] = vix["VIX3M"].notna().astype(float)

    # ---- Credit (HYG/LQD) -------------------------------------------------
    credit = option_data.load_weekly_prices(["HYG", "LQD"]).reindex(out.index)
    cr = credit["HYG"] / credit["LQD"]
    hyg_4w = credit["HYG"].pct_change(4)
    out["credit_improvement"] = ((cr > cr.shift(4)) & (hyg_4w > 0)).astype(float)
    out["credit_available"] = (credit["HYG"].notna() & credit["LQD"].notna()).astype(float)

    return out.shift(lag_weeks)


@dataclass
class RecoverySignalPanel:
    per_ticker: dict[str, pd.DataFrame]
    market: pd.DataFrame
    underlyings: list[str]

    def feature_row(self, date, ticker: str) -> dict[str, float]:
        row: dict[str, float] = {}
        for name, df in self.per_ticker.items():
            row[name] = _safe(df, date, ticker)
        for name in self.market.columns:
            row[name] = _safe_series(self.market[name], date)
        return row


def expected_forward_move(weekly_drift: float, horizon_weeks: float) -> float:
    """Project trailing weekly drift over the option HOLDING horizon (proxy)."""

    if weekly_drift is None or not np.isfinite(weekly_drift):
        return np.nan
    return float(weekly_drift) * float(horizon_weeks)


@dataclass
class RecoveryDecision:
    active: bool
    reasons_failed: list[str] = field(default_factory=list)
    soft_score: int = 0
    expected_move: float = float("nan")
    breakeven_move: float = float("nan")
    surplus: float = float("nan")


# Gate-group flags let the runner ABLATE individual ideas (surplus, vol,
# transition, recovery) to answer "did this filter improve selection?".
DEFAULT_GATE_FLAGS = {"surplus": True, "vol": True, "transition": True, "recovery": True}


def evaluate_recovery_entry(
    features: dict,
    *,
    market_state: str,
    baseline_weight: float,
    breakeven_move: float,
    horizon_weeks: float,
    holding_weeks: float,
    gate_flags: dict | None = None,
    margin: float = SURPLUS_MARGIN,
    cost_buffer: float = 0.0,
) -> RecoveryDecision:
    """Evaluate the recovery activation gate.

    HARD gates (must all pass): baseline weight, not panic, recently defensive,
    regime now improving, trend re-acceleration, and (if enabled) the expected-
    move surplus. SOFT gates (need >= ``SOFT_GATES_REQUIRED``): transition flag,
    MA slope, reclaim, recovery-from-low in range, VIX normalizing, VIX term
    normalizing, credit improving, realized vol not exploding.
    """

    flags = {**DEFAULT_GATE_FLAGS, **(gate_flags or {})}
    f = features
    failed: list[str] = []

    expected_move = expected_forward_move(f.get("weekly_drift"), holding_weeks)
    surplus = (expected_move - breakeven_move - cost_buffer) if (np.isfinite(expected_move) and np.isfinite(breakeven_move)) else np.nan

    # ----- HARD gates ------------------------------------------------------
    if not _ge(baseline_weight, MIN_BASELINE_WEIGHT):
        failed.append("insufficient_baseline_weight")
    if market_state == PANIC_STATE:
        failed.append("confirmed_panic")
    if not _pos(f.get("recently_defensive")):
        failed.append("not_recently_defensive")
    # Use the current-week regime state for the "now improving" check (matches
    # how v1/v2 read the state at decision time); ``recently_defensive`` above is
    # inherently backward-looking and stays on the lagged panel.
    if market_state not in RISK_ON_IMPROVING_STATES:
        failed.append("regime_not_improving")
    if not _pos(f.get("accel_4w")):
        failed.append("no_trend_reacceleration")
    if flags["surplus"]:
        if not (np.isfinite(surplus) and surplus > margin):
            failed.append("expected_move_below_breakeven")

    # ----- SOFT confirmation gates ----------------------------------------
    soft = {}
    soft["transition_flag"] = _pos(f.get("transition_flag")) if flags["transition"] else True
    rec = f.get("recovery_from_low")
    soft["recovery_from_low"] = (
        (rec is not None and np.isfinite(rec) and MIN_RECOVERY_FROM_LOW <= rec <= MAX_RECOVERY_FROM_LOW)
        if flags["recovery"] else True
    )
    soft["ma_slope_positive"] = _pos(f.get("ma_slope"))
    soft["reclaimed_ma"] = _pos(f.get("reclaim_flag"))
    if flags["vol"]:
        soft["vix_normalizing"] = _pos(f.get("vix_normalizing")) or not _pos(f.get("vix_available"))
        soft["vix_term_normalizing"] = _pos(f.get("vix_term_normalizing")) or not _pos(f.get("vix_available"))
        soft["realized_vol_calm"] = _le(f.get("realized_vol_pct"), VOL_PERCENTILE_CALM) and not _ge(f.get("vol_spike"), VOL_SPIKE_RATIO)
    soft["credit_improving"] = _pos(f.get("credit_improvement")) or not _pos(f.get("credit_available"))

    soft_score = int(sum(1 for v in soft.values() if v))
    if soft_score < SOFT_GATES_REQUIRED:
        failed.append(f"insufficient_soft_confirmations({soft_score}/{SOFT_GATES_REQUIRED})")

    # Always block if vol is exploding, even via the soft path (safety).
    if flags["vol"] and _ge(f.get("vol_spike"), VOL_SPIKE_RATIO):
        failed.append("vol_exploding")

    return RecoveryDecision(
        active=len(failed) == 0,
        reasons_failed=failed,
        soft_score=soft_score,
        expected_move=expected_move,
        breakeven_move=breakeven_move,
        surplus=surplus,
    )


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _load_vix() -> pd.DataFrame:
    df = pd.read_csv(VIX_PATH)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    try:
        df["Date"] = df["Date"].dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return df.dropna(subset=["Date"]).set_index("Date")


def _weeks_since_min(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    """For each column, weeks since the rolling-``window`` minimum."""

    def _wsm(arr: np.ndarray) -> float:
        if np.all(np.isnan(arr)):
            return np.nan
        # position of min within the window; distance from the end (now).
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
