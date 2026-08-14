"""Causal feature panel for Focused Reversal Recovery Research.

The experiment uses weekly observations because the baseline strategy and
market-state artifacts are weekly. Day-based concepts in the prompt are mapped
to weekly approximations: 20/40/60 trading days become 4/8/12 weeks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

WEEKLY_PRICES_PATH = DATA / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE_PATH = DATA / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
VIX_PATH = DATA / "01_data_hub" / "vix_term_structure.csv"
BASELINE_PIN = "improved_frontier_phase5_fragility_guard"
BASELINE_WEIGHTS_PATH = DATA / "05_layer3_portfolio_construction" / f"portfolio_version_weights_{BASELINE_PIN}.csv"
BASELINE_RETURNS_PATH = DATA / "05_layer3_portfolio_construction" / f"portfolio_version_returns_{BASELINE_PIN}.csv"

TARGET_TICKERS = ["SPY", "QQQ"]
RISK_ASSET_BASKET = ["SPY", "QQQ", "IWM", "EFA", "EEM", "VUG", "VTV", "XLK", "XLY", "XLI", "XLF"]


def read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" not in df.columns and df.columns[0].startswith("Unnamed"):
        df = df.rename(columns={df.columns[0]: "Date"})
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    try:
        df[date_col] = df[date_col].dt.tz_localize(None)
    except (AttributeError, TypeError):
        pass
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def load_weekly_prices() -> pd.DataFrame:
    return read_dated(WEEKLY_PRICES_PATH).apply(pd.to_numeric, errors="coerce")


def load_market_states() -> pd.DataFrame:
    return read_dated(MARKET_STATE_PATH)


def load_vix() -> pd.DataFrame:
    return read_dated(VIX_PATH).apply(pd.to_numeric, errors="coerce")


def load_baseline_returns() -> pd.DataFrame:
    return read_dated(BASELINE_RETURNS_PATH)


def load_baseline_weights() -> pd.DataFrame:
    return read_dated(BASELINE_WEIGHTS_PATH).apply(pd.to_numeric, errors="coerce").fillna(0.0)


def build_feature_panel(lag_weeks: int = 1) -> pd.DataFrame:
    """Build one row per Date/ticker with all predictive inputs lagged."""

    from .regime_filters import add_regime_filters
    from .reversal_signals import add_reversal_signals

    prices = load_weekly_prices()
    states = load_market_states()
    vix = load_vix()
    weights = load_baseline_weights()

    all_idx = prices.index.intersection(states.index)
    prices = prices.reindex(all_idx)
    states = states.reindex(all_idx)
    vix = vix.reindex(all_idx)
    weights = weights.reindex(all_idx).fillna(0.0)

    market = _market_features(prices, states, vix)
    parts = []
    for ticker in TARGET_TICKERS:
        ticker_features = _ticker_features(prices, weights, ticker)
        df = ticker_features.join(market, how="left")
        df["ticker"] = ticker
        parts.append(df)

    panel = pd.concat(parts).sort_index()
    panel.index.name = "Date"
    panel = panel.reset_index()

    feature_cols = [c for c in panel.columns if c not in {"Date", "ticker"}]
    panel[feature_cols] = panel.groupby("ticker", group_keys=False)[feature_cols].shift(lag_weeks)
    panel["feature_lag_weeks"] = lag_weeks

    panel = add_regime_filters(panel)
    panel = add_reversal_signals(panel)
    return panel


def _ticker_features(prices: pd.DataFrame, weights: pd.DataFrame, ticker: str) -> pd.DataFrame:
    px = prices[ticker]
    ret_1w = px.pct_change()
    out = pd.DataFrame(index=prices.index)
    out["price"] = px

    for w in (1, 2, 4, 8, 12, 13, 26, 52):
        out[f"ret_{w}w"] = px.pct_change(w)

    for w in (1, 2, 4):
        out[f"negative_{w}w_return_flag"] = (out[f"ret_{w}w"] < 0).astype(float)
        out[f"loss_magnitude_{w}w"] = (-out[f"ret_{w}w"]).clip(lower=0)
        out[f"ret_{w}w_z_52"] = _rolling_z(out[f"ret_{w}w"], 52)

    out["short_term_oversold_score"] = _mean(
        [
            (out["loss_magnitude_1w"] / 0.03).clip(0, 1),
            (out["loss_magnitude_2w"] / 0.05).clip(0, 1),
            (out["loss_magnitude_4w"] / 0.08).clip(0, 1),
            (-out["ret_1w_z_52"] / 1.5).clip(0, 1),
            (-out["ret_2w_z_52"] / 1.5).clip(0, 1),
            (-out["ret_4w_z_52"] / 1.5).clip(0, 1),
        ]
    )
    out["recent_loss_magnitude"] = out[["loss_magnitude_1w", "loss_magnitude_2w", "loss_magnitude_4w"]].max(axis=1)

    for w in (13, 26, 52):
        out[f"drawdown_{w}w_high"] = px / px.rolling(w).max() - 1.0
        out[f"drawdown_depth_{w}w"] = (-out[f"drawdown_{w}w_high"]).clip(lower=0)

    for w in (4, 8, 12):
        low = px.rolling(w).min()
        out[f"distance_from_{w}w_low"] = px / low - 1.0
        out[f"recovery_from_{w}w_low"] = out[f"distance_from_{w}w_low"].clip(lower=0)
        out[f"weeks_since_{w}w_low"] = _weeks_since_min(px, w)
        out[f"down_weeks_{w}w"] = (ret_1w < 0).rolling(w).sum()

    out["selloff_speed_4w"] = out["loss_magnitude_4w"] / 4.0
    out["selloff_speed_8w"] = (-out["ret_8w"]).clip(lower=0) / 8.0
    out["bounce_strength_1w"] = out["ret_1w"].clip(lower=0)
    out["bounce_strength_2w"] = out["ret_2w"].clip(lower=0)
    out["bounce_strength_4w"] = out["ret_4w"].clip(lower=0)

    for w in (4, 8, 12):
        ma = px.rolling(w).mean()
        out[f"above_{w}w_ma"] = (px > ma).astype(float)
        out[f"reclaim_{w}w_ma"] = ((px > ma) & (px.shift(1) <= ma.shift(1))).astype(float)

    out["drawdown_depth_x_recovery_confirmation"] = out["drawdown_depth_26w"] * _mean(
        [
            (out["recovery_from_8w_low"] / 0.06).clip(0, 1),
            out["above_4w_ma"],
            out["above_8w_ma"],
        ]
    )
    out["bounce_from_low_after_drawdown"] = out["drawdown_depth_13w"] * out["recovery_from_8w_low"]

    out["medium_momentum_8w"] = out["ret_8w"]
    out["medium_momentum_12w"] = out["ret_12w"]
    out["medium_momentum_26w"] = out["ret_26w"]
    out["medium_uptrend_flag"] = ((out["ret_12w"] > 0) & (out["ret_26w"] > -0.05)).astype(float)
    out["medium_downtrend_flag"] = ((out["ret_12w"] < 0) & (out["ret_26w"] < 0)).astype(float)
    out["uptrend_short_pullback"] = out["medium_uptrend_flag"] * out["loss_magnitude_2w"]
    out["downtrend_short_bounce"] = out["medium_downtrend_flag"] * out["bounce_strength_2w"]
    out["trend_negative_recovery_acceleration"] = out["medium_downtrend_flag"] * (
        out["ret_4w"] - out["ret_4w"].shift(4)
    ).clip(lower=0)
    out["trend_positive_short_oversold"] = out["medium_uptrend_flag"] * out["short_term_oversold_score"]
    out["momentum_reversal_interaction_raw"] = _mean(
        [
            (out["uptrend_short_pullback"] / 0.04).clip(0, 1),
            (out["downtrend_short_bounce"] / 0.04).clip(0, 1),
            (out["trend_negative_recovery_acceleration"] / 0.06).clip(0, 1),
            out["trend_positive_short_oversold"],
        ]
    )
    out["momentum_reversal_state"] = np.select(
        [
            (out["medium_downtrend_flag"] == 1) & (out["ret_2w"] < 0),
            (out["short_term_oversold_score"] > 0.55) & (out["bounce_strength_1w"] > 0),
            (out["medium_uptrend_flag"] == 1) & (out["loss_magnitude_2w"] > 0),
            (out["bounce_strength_2w"] > 0) & (out["ret_8w"] < -0.03),
        ],
        ["continuation_bearish", "oversold_rebound", "pullback_in_uptrend", "failed_bounce_setup"],
        default="neutral",
    )

    out["baseline_weight"] = weights.get(ticker, pd.Series(0.0, index=prices.index))
    out["baseline_weight_change_4w"] = out["baseline_weight"] - out["baseline_weight"].shift(4)
    out["realized_vol_13w"] = np.log(px / px.shift(1)).rolling(13).std(ddof=1) * np.sqrt(52.0)
    out["realized_vol_pct_52w"] = _rolling_rank(out["realized_vol_13w"], 52)
    out["realized_vol_change_4w"] = out["realized_vol_13w"] / out["realized_vol_13w"].shift(4) - 1.0
    return out


def _market_features(prices: pd.DataFrame, states: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=prices.index)
    out["market_state"] = states.get("market_state", "").astype(str)
    out["market_state_stable"] = states.get("market_state_stable", "").astype(str)
    out["risk_state"] = states.get("risk_state", "").astype(str)
    out["signal_environment"] = states.get("signal_environment", "").astype(str)
    out["risk_regime_score"] = pd.to_numeric(states.get("risk_regime_score"), errors="coerce")
    out["market_drawdown"] = pd.to_numeric(states.get("market_drawdown"), errors="coerce")
    out["market_trend_positive"] = pd.to_numeric(states.get("market_trend_positive"), errors="coerce")
    out["recent_stress_26w"] = pd.to_numeric(states.get("recent_stress_26w"), errors="coerce")
    out["transition_good_state_prob"] = pd.to_numeric(states.get("transition_good_state_prob"), errors="coerce")
    out["transition_non_stress_prob"] = pd.to_numeric(states.get("transition_non_stress_prob"), errors="coerce")

    basket = [c for c in RISK_ASSET_BASKET if c in prices.columns]
    if basket:
        basket_px = prices[basket]
        out["risk_basket_ret_1w"] = basket_px.pct_change(1).mean(axis=1)
        out["risk_basket_ret_4w"] = basket_px.pct_change(4).mean(axis=1)
        out["risk_basket_pct_positive_4w"] = (basket_px.pct_change(4) > 0).mean(axis=1)
    else:
        out["risk_basket_ret_1w"] = np.nan
        out["risk_basket_ret_4w"] = np.nan
        out["risk_basket_pct_positive_4w"] = np.nan

    if {"HYG", "LQD"}.issubset(prices.columns):
        hyg_lqd = prices["HYG"] / prices["LQD"]
        out["credit_hyg_lqd_ret_4w"] = hyg_lqd.pct_change(4)
        out["credit_hyg_lqd_trend_8w"] = hyg_lqd / hyg_lqd.rolling(8).mean() - 1.0
        out["credit_hyg_lqd_ma_slope_4w"] = hyg_lqd.rolling(8).mean() / hyg_lqd.rolling(8).mean().shift(4) - 1.0
    else:
        out["credit_hyg_lqd_ret_4w"] = np.nan
        out["credit_hyg_lqd_trend_8w"] = np.nan
        out["credit_hyg_lqd_ma_slope_4w"] = np.nan

    out["vix"] = pd.to_numeric(vix.get("VIX"), errors="coerce")
    out["vix3m"] = pd.to_numeric(vix.get("VIX3M"), errors="coerce")
    out["vix_percentile_52w"] = _rolling_rank(out["vix"], 52)
    out["vix_change_1w"] = out["vix"].pct_change(1)
    out["vix_change_2w"] = out["vix"].pct_change(2)
    out["vix_change_4w"] = out["vix"].pct_change(4)
    out["vix_ratio"] = out["vix"] / out["vix3m"]
    out["vix_fading_from_13w_high"] = out["vix"] / out["vix"].rolling(13).max() - 1.0
    return out


def _rolling_z(s: pd.Series, window: int) -> pd.Series:
    mean = s.rolling(window, min_periods=max(12, window // 4)).mean()
    std = s.rolling(window, min_periods=max(12, window // 4)).std(ddof=1)
    return (s - mean) / std.replace(0.0, np.nan)


def _rolling_rank(s: pd.Series, window: int) -> pd.Series:
    def rank(arr: np.ndarray) -> float:
        cur = arr[-1]
        if np.isnan(cur):
            return np.nan
        valid = arr[~np.isnan(arr)]
        return float((valid <= cur).mean()) if len(valid) > 1 else np.nan

    return s.rolling(window, min_periods=max(12, window // 4)).apply(rank, raw=True)


def _weeks_since_min(s: pd.Series, window: int) -> pd.Series:
    def inner(arr: np.ndarray) -> float:
        if np.all(np.isnan(arr)):
            return np.nan
        return float(len(arr) - 1 - int(np.nanargmin(arr)))

    return s.rolling(window, min_periods=3).apply(inner, raw=True)


def _mean(parts: list[pd.Series]) -> pd.Series:
    frame = pd.concat(parts, axis=1)
    return frame.mean(axis=1, skipna=True).fillna(0.0).clip(0, 1)

