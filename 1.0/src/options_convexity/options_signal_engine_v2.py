"""Options-specific signal engine for the v2 convexity research extension.

WHY v2 EXISTS
-------------
The v1 overlay used the *ETF allocation* signals ("should I hold more of this
ETF?") to decide when to buy options. That question is the wrong one for
options. An option only pays if the underlying moves *enough*, *soon enough*, to
overcome the premium, time decay and implied vol. So v2 builds signals that try
to answer the harder question:

    "Is this ETF likely to make a large enough move over the next 1-3 months to
     beat the call-spread breakeven, AND is now a cheap/accelerating moment to
     buy that convexity?"

Everything here is CAUSAL: every feature used at decision week ``t`` is lagged by
one week (``shift(1)``) so it only sees data through week ``t-1``. The only
week-``t`` value the backtest uses is the executable spot price, exactly as v1.

This module deliberately:
  * does NOT touch or import any production allocation logic,
  * does NOT modify the v1 files (it only imports their read-only helpers),
  * uses simple, documented, round-number thresholds (no ML, no aggressive
    tuning) so the activation logic is not overfit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data

# --------------------------------------------------------------------------
# v2 activation thresholds. Chosen as simple round numbers up front, NOT tuned
# to maximize the backtest. The DTE/structure/ablation SWEEPS (not these knobs)
# are how we explore the design space.
# --------------------------------------------------------------------------
RISK_ON_STATES = {"calm_trend", "recovery_confirmed"}
DEFENSIVE_STATES = {"stressed_panic", "recovery_fragile"}

MIN_BASELINE_WEIGHT = 0.02          # ETF must already be held by the baseline.
MAX_MARKET_DRAWDOWN = -0.10         # block if broad market deeper than -10%.
SURPLUS_MARGIN = 0.01               # expected move must beat breakeven by >=1%.
MAX_VOL_PERCENTILE = 0.70           # IV/realized-vol "not expensive" gate.
MAX_RV_VS_MEDIAN = 1.10             # realized vol not far above its own median.
DD_RECOVERY_MIN = 0.60             # "recovery strength" threshold (0..1).
VOL_SPIKE_RATIO = 1.50              # block if realized vol jumped 50% in 4 wks.

# Ablation levels (cumulative). The backtest runs each so we can SEE which
# filter actually adds value rather than asserting it.
ABLATION_LEVELS = {
    1: "bullish_only",
    2: "bullish_acceleration",
    3: "bullish_acceleration_breakeven",
    4: "bullish_acceleration_breakeven_iv",
    5: "bullish_acceleration_breakeven_iv_transition",
}


def build_v2_signals(
    underlyings: list[str] | None = None,
    lag_weeks: int = 1,
) -> "V2SignalPanel":
    """Build the full causal v2 signal panel for the eligible underlyings.

    Returns a :class:`V2SignalPanel` holding per-underlying feature frames
    (date x ticker) and market-level series. Every feature is lagged so it is
    strictly backward-looking at decision time.
    """

    underlyings = underlyings or option_data.ELIGIBLE_UNDERLYINGS
    prices = option_data.load_weekly_prices(underlyings)

    # ---- Multi-horizon trailing returns -----------------------------------
    ret_4w = prices.pct_change(4)
    ret_8w = prices.pct_change(8)
    ret_12w = prices.pct_change(12)

    # ---- Trend acceleration: is the recent 4w move faster than the prior 4w?
    accel_4w = ret_4w - ret_4w.shift(4)

    # ---- Moving-average slope (13w MA momentum) and distance from 40w MA ----
    ma_13 = prices.rolling(13).mean()
    ma_slope = ma_13 / ma_13.shift(4) - 1.0
    ma_40 = prices.rolling(40).mean()
    dist_from_ma = prices / ma_40 - 1.0

    # ---- Breakout score: z-score of price vs its short MA (positive = pushing
    #      to new local highs) -------------------------------------------------
    std_13 = prices.rolling(13).std(ddof=0)
    breakout_score = (prices - ma_13) / std_13.replace(0.0, np.nan)

    # ---- Drawdown-recovery score: where price sits in its trailing 52w range
    #      (0 = at the lows, 1 = at the highs => fully recovered) --------------
    roll_min = prices.rolling(52).min()
    roll_max = prices.rolling(52).max()
    dd_recovery = (prices - roll_min) / (roll_max - roll_min).replace(0.0, np.nan)

    # ---- Volatility features (realized-vol proxy for IV) -------------------
    log_ret = np.log(prices / prices.shift(1))
    realized_vol = log_ret.rolling(13).std(ddof=1) * np.sqrt(52.0)
    vol_percentile = option_data.iv_percentile(realized_vol, lookback_weeks=52)
    rv_vs_median = realized_vol / realized_vol.rolling(52).median()
    vol_spike = (realized_vol / realized_vol.shift(4)).fillna(1.0)

    # ---- Expected forward "drift" per week (momentum-persistence proxy) -----
    # Trailing 12-week average weekly return. Scaled to the option horizon in
    # the backtest. This is an APPROXIMATION of expected forward return; it is
    # NOT a forecast model, just a transparent persistence assumption.
    weekly_drift = ret_12w / 12.0

    # ---- Lag everything so decisions never peek at the current week ---------
    def lag(df: pd.DataFrame) -> pd.DataFrame:
        return df.shift(lag_weeks)

    per_ticker = {
        "ret_4w": lag(ret_4w),
        "ret_8w": lag(ret_8w),
        "ret_12w": lag(ret_12w),
        "accel_4w": lag(accel_4w),
        "ma_slope": lag(ma_slope),
        "dist_from_ma": lag(dist_from_ma),
        "breakout_score": lag(breakout_score),
        "dd_recovery": lag(dd_recovery),
        "vol_percentile": lag(vol_percentile),
        "rv_vs_median": lag(rv_vs_median),
        "vol_spike": lag(vol_spike),
        "realized_vol": lag(realized_vol),
        "weekly_drift": lag(weekly_drift),
    }

    # ---- Market-level features (credit + regime transition) ----------------
    market = _build_market_level_features(lag_weeks=lag_weeks)

    return V2SignalPanel(per_ticker=per_ticker, market=market, underlyings=underlyings)


def _build_market_level_features(lag_weeks: int = 1) -> pd.DataFrame:
    """Build market-wide credit-improvement and risk-on-transition flags.

    Credit improvement uses the HYG/LQD ratio (high-yield vs investment-grade):
    when high yield is outperforming and rising, credit conditions are easing,
    which historically confirms a risk-on environment. The regime transition
    flag fires when the market has recently moved OUT of a defensive state into
    a risk-on state (a "re-risking" moment).
    """

    prices = option_data.load_weekly_prices(["HYG", "LQD"])
    states = option_data.load_market_states()

    out = pd.DataFrame(index=prices.index)

    # Credit improvement: HYG/LQD ratio rising over 4 weeks AND HYG up 4w.
    if "HYG" in prices and "LQD" in prices:
        ratio = prices["HYG"] / prices["LQD"]
        hyg_4w = prices["HYG"].pct_change(4)
        out["credit_improvement"] = ((ratio > ratio.shift(4)) & (hyg_4w > 0)).astype(float)
        out["credit_available"] = 1.0
    else:
        out["credit_improvement"] = np.nan
        out["credit_available"] = 0.0

    # Defensive -> risk-on transition within the last 4 weeks.
    state = states["market_state"].astype(str).reindex(out.index)
    was_defensive = state.shift(1).isin(DEFENSIVE_STATES | {"neutral_mixed"})
    for k in range(2, 5):
        was_defensive = was_defensive | state.shift(k).isin(DEFENSIVE_STATES | {"neutral_mixed"})
    is_risk_on = state.isin(RISK_ON_STATES)
    out["risk_on_transition"] = (is_risk_on & was_defensive).astype(float)

    return out.shift(lag_weeks)


@dataclass
class V2SignalPanel:
    """Container for the causal v2 signal panel."""

    per_ticker: dict[str, pd.DataFrame]
    market: pd.DataFrame
    underlyings: list[str]

    def feature_row(self, date, ticker: str) -> dict[str, float]:
        """Return all feature values for one (date, ticker), NaN-safe."""

        row: dict[str, float] = {}
        for name, df in self.per_ticker.items():
            row[name] = _safe_lookup(df, date, ticker)
        for name in self.market.columns:
            row[name] = _safe_lookup_series(self.market[name], date)
        return row


def expected_forward_move(weekly_drift: float, horizon_weeks: float) -> float:
    """Project the trailing weekly drift over the option horizon.

    This is the v2 "expected forward return proxy" for the underlying over the
    life of the option. It is intentionally simple (momentum persistence). The
    point is to COMPARE it against the option's breakeven, not to be a precise
    forecast.
    """

    if weekly_drift is None or not np.isfinite(weekly_drift):
        return np.nan
    return float(weekly_drift) * float(horizon_weeks)


@dataclass
class V2EntryDecision:
    """Result of evaluating the v2 entry filters at a given ablation level."""

    active: bool
    level: int
    reasons_failed: list[str] = field(default_factory=list)
    expected_move: float = float("nan")
    breakeven_move: float = float("nan")
    surplus: float = float("nan")


def evaluate_v2_entry(
    features: dict[str, float],
    *,
    level: int,
    market_state: str,
    market_drawdown: float,
    baseline_weight: float,
    breakeven_move: float,
    horizon_weeks: float,
    iv_history_available: bool = True,
    margin: float = SURPLUS_MARGIN,
) -> V2EntryDecision:
    """Evaluate the cumulative v2 entry filters up to ``level`` (1..5).

    The filters build on each other:
      L1 bullish_only            : baseline holds it, regime risk-on, not in
                                   panic/stress/drawdown-defense.
      L2 + acceleration          : trend acceleration positive, MA sloping up,
                                   multi-horizon momentum positive, breakout,
                                   and NOT right after a vol spike.
      L3 + breakeven             : expected forward move beats the spread's
                                   breakeven move by the safety margin.
      L4 + IV/richness           : realized-vol percentile low and vol not far
                                   above its own median (options "not expensive").
      L5 + re-risking transition : recovery strength OR a defensive->risk-on
                                   transition, confirmed by improving credit.

    Returns a :class:`V2EntryDecision`. ``active`` is True only if every filter
    up to ``level`` passes.
    """

    failed: list[str] = []
    f = features

    expected_move = expected_forward_move(f.get("weekly_drift"), horizon_weeks)
    surplus = expected_move - breakeven_move if np.isfinite(expected_move) and np.isfinite(breakeven_move) else np.nan

    # ---- Level 1: bullish context (necessary, not sufficient) -------------
    if not (baseline_weight is not None and baseline_weight >= MIN_BASELINE_WEIGHT):
        failed.append("insufficient_baseline_weight")
    if market_state not in RISK_ON_STATES:
        failed.append("regime_not_risk_on")
    if market_state in DEFENSIVE_STATES:
        failed.append("defensive_state")
    if market_drawdown is not None and np.isfinite(market_drawdown) and market_drawdown < MAX_MARKET_DRAWDOWN:
        failed.append("market_in_drawdown")

    # ---- Level 2: acceleration / breakout strength ------------------------
    if level >= 2:
        if not _pos(f.get("accel_4w")):
            failed.append("no_acceleration")
        if not _pos(f.get("ma_slope")):
            failed.append("ma_not_rising")
        if not (_pos(f.get("ret_4w")) and _pos(f.get("ret_8w")) and _pos(f.get("ret_12w"))):
            failed.append("momentum_not_broad")
        if not _ge(f.get("breakout_score"), 0.0):
            failed.append("no_breakout")
        # Rule 11: do not chase right after a volatility spike.
        if _ge(f.get("vol_spike"), VOL_SPIKE_RATIO):
            failed.append("post_vol_spike")

    # ---- Level 3: breakeven-aware entry (the key options-specific test) ----
    if level >= 3:
        if not (np.isfinite(surplus) and surplus > margin):
            failed.append("expected_move_below_breakeven")

    # ---- Level 4: IV / richness filter ------------------------------------
    if level >= 4 and iv_history_available:
        if not _le(f.get("vol_percentile"), MAX_VOL_PERCENTILE):
            failed.append("iv_too_expensive")
        if not _le(f.get("rv_vs_median"), MAX_RV_VS_MEDIAN):
            failed.append("rv_above_median")

    # ---- Level 5: re-risking transition + credit confirmation -------------
    if level >= 5:
        recovery_ok = _ge(f.get("dd_recovery"), DD_RECOVERY_MIN) or _pos(f.get("risk_on_transition"))
        if not recovery_ok:
            failed.append("no_recovery_or_transition")
        # Credit confirmation only required when credit data is available.
        if f.get("credit_available", 0.0) >= 1.0 and not _pos(f.get("credit_improvement")):
            failed.append("credit_not_improving")

    return V2EntryDecision(
        active=len(failed) == 0,
        level=level,
        reasons_failed=failed,
        expected_move=expected_move,
        breakeven_move=breakeven_move,
        surplus=surplus,
    )


# --------------------------------------------------------------------------
# Small numeric helpers (kept explicit and readable on purpose).
# --------------------------------------------------------------------------
def _pos(x) -> bool:
    return x is not None and np.isfinite(x) and x > 0


def _ge(x, threshold) -> bool:
    return x is not None and np.isfinite(x) and x >= threshold


def _le(x, threshold) -> bool:
    return x is not None and np.isfinite(x) and x <= threshold


def _safe_lookup(df: pd.DataFrame, date, ticker: str, default: float = np.nan) -> float:
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


def _safe_lookup_series(s: pd.Series, date, default: float = np.nan) -> float:
    try:
        val = s.loc[date]
    except (KeyError, IndexError):
        return default
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if np.isfinite(val) else default
