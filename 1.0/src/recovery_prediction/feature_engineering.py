"""Causal feature panel for Recovery Prediction Research.

The panel is weekly because the production baseline and market-state artifacts
are weekly. Day-based concepts from the research brief are approximated with
weekly windows: 20/40/60 trading days map to 4/8/12 weeks.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .signal_families import FAMILY_SCORE_COLUMNS

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
WEEKLY_PRICES_PATH = DATA / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE_PATH = DATA / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
VIX_PATH = DATA / "01_data_hub" / "vix_term_structure.csv"
BASELINE_PIN = "improved_frontier_phase5_fragility_guard"
BASELINE_WEIGHTS_PATH = DATA / "05_layer3_portfolio_construction" / f"portfolio_version_weights_{BASELINE_PIN}.csv"
BASELINE_RETURNS_PATH = DATA / "05_layer3_portfolio_construction" / f"portfolio_version_returns_{BASELINE_PIN}.csv"

TARGET_TICKERS = ["SPY", "QQQ"]
RISKY_ETFS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "VUG", "VTV", "XLK", "XLY", "XLI", "XLF", "XLB", "XLE", "VNQ"]
DEFENSIVE_ETFS = ["BIL", "SHY", "IEF", "TLT", "LQD", "MBB", "GLD", "IAU", "XLU", "XLP"]
SECTOR_ETFS = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]


def read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Date" not in df.columns and df.columns[0].startswith("Unnamed"):
        df = df.rename(columns={df.columns[0]: "Date"})
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    try:
        df[date_col] = df[date_col].dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def load_weekly_prices() -> pd.DataFrame:
    return read_dated(WEEKLY_PRICES_PATH).apply(pd.to_numeric, errors="coerce")


def load_market_states() -> pd.DataFrame:
    return read_dated(MARKET_STATE_PATH)


def load_baseline_returns() -> pd.DataFrame:
    return read_dated(BASELINE_RETURNS_PATH)


def load_baseline_weights() -> pd.DataFrame:
    return read_dated(BASELINE_WEIGHTS_PATH).apply(pd.to_numeric, errors="coerce").fillna(0.0)


def build_feature_panel(lag_weeks: int = 1) -> pd.DataFrame:
    """Return a causal feature panel with one row per Date/ticker."""

    prices = load_weekly_prices()
    states = load_market_states()
    weights = load_baseline_weights()
    vix = read_dated(VIX_PATH)
    all_idx = prices.index.intersection(states.index)
    prices = prices.reindex(all_idx)
    states = states.reindex(all_idx)
    weights = weights.reindex(all_idx).fillna(0.0)
    vix = vix.reindex(all_idx)

    market = _build_market_features(prices, states, vix)
    panel_parts = []
    for ticker in TARGET_TICKERS:
        ticker_features = _ticker_features(prices, weights, ticker)
        df = ticker_features.join(market, how="left")
        df["ticker"] = ticker
        panel_parts.append(df)

    panel = pd.concat(panel_parts).sort_index()
    panel.index.name = "Date"
    panel = panel.reset_index()
    numeric_cols = panel.select_dtypes(include=[np.number]).columns.tolist()
    # All numeric features are lagged by ticker before any predictive scoring.
    panel[numeric_cols] = panel.groupby("ticker", group_keys=False)[numeric_cols].shift(lag_weeks)
    panel["feature_lag_weeks"] = lag_weeks
    panel = _add_family_scores(panel)
    return panel


def _ticker_features(prices: pd.DataFrame, weights: pd.DataFrame, ticker: str) -> pd.DataFrame:
    px = prices[ticker]
    ret = px.pct_change()
    out = pd.DataFrame(index=prices.index)
    out["price"] = px
    for w in (1, 2, 4, 8, 12, 13, 26):
        out[f"ret_{w}w"] = px.pct_change(w)
    for w in (13, 26, 52):
        out[f"drawdown_{w}w_high"] = px / px.rolling(w).max() - 1.0
    for w in (4, 8, 12):
        low = px.rolling(w).min()
        out[f"distance_from_{w}w_low"] = px / low - 1.0
        out[f"weeks_since_{w}w_low"] = _weeks_since_min(px, w)
    out["decline_speed_4w"] = -out["ret_4w"].clip(upper=0) / 4.0
    for w in (4, 8, 12):
        out[f"down_weeks_{w}w"] = (ret < 0).rolling(w).sum()
    ma4 = px.rolling(4).mean()
    ma8 = px.rolling(8).mean()
    ma10 = px.rolling(10).mean()
    ma12 = px.rolling(12).mean()
    out["oversold_score"] = (1.0 - px / ma12).clip(lower=0)
    out["recovery_from_recent_low"] = out["distance_from_8w_low"]
    out["reclaim_ma4"] = (px > ma4).astype(float)
    out["reclaim_ma8"] = (px > ma8).astype(float)
    out["bounce_strength_4w"] = out["ret_4w"].clip(lower=0)
    out["drawdown_depth_x_reclaim"] = (-out["drawdown_26w_high"].clip(upper=0)) * out["reclaim_ma8"]
    out["negative_1w"] = (-out["ret_1w"]).clip(lower=0)
    out["negative_2w"] = (-out["ret_2w"]).clip(lower=0)
    out["negative_4w"] = (-out["ret_4w"]).clip(lower=0)
    out["one_month_reversal_score"] = out["negative_4w"] * out["reclaim_ma4"]
    out["medium_momentum_8w"] = out["ret_8w"]
    out["medium_momentum_12w"] = out["ret_12w"]
    out["medium_momentum_26w"] = out["ret_26w"]
    out["momentum_positive_pullback"] = (out["ret_12w"] > 0).astype(float) * out["negative_2w"]
    out["momentum_negative_bounce"] = (out["ret_12w"] < 0).astype(float) * out["ret_2w"].clip(lower=0)
    out["drawdown_high_accel_positive"] = (-out["drawdown_26w_high"].clip(upper=0)) * (out["ret_4w"] - out["ret_4w"].shift(4)).clip(lower=0)
    out["trend_negative_breadth_improving"] = (out["ret_12w"] < 0).astype(float)
    out["trend_positive_vol_fading"] = (out["ret_12w"] > 0).astype(float)
    out["baseline_weight"] = weights.get(ticker, pd.Series(0.0, index=prices.index))
    out["baseline_weight_change_4w"] = out["baseline_weight"] - out["baseline_weight"].shift(4)
    out["realized_vol_13w"] = np.log(px / px.shift(1)).rolling(13).std(ddof=1) * np.sqrt(52.0)
    out["realized_vol_pct"] = _rolling_rank(out["realized_vol_13w"], 52)
    out["realized_vol_change_4w"] = out["realized_vol_13w"] / out["realized_vol_13w"].shift(4) - 1.0
    return out


def _build_market_features(prices: pd.DataFrame, states: pd.DataFrame, vix: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=prices.index)
    out["market_state"] = states["market_state"].astype(str)
    out["risk_state"] = states.get("risk_state", "").astype(str)
    out["market_drawdown"] = pd.to_numeric(states.get("market_drawdown"), errors="coerce")
    out["recent_stress_26w"] = pd.to_numeric(states.get("recent_stress_26w"), errors="coerce")
    for col in ("breadth_sma_43", "breadth_26w_mom", "breadth_13w_mom", "breadth_change_4w"):
        out[col] = pd.to_numeric(states.get(col), errors="coerce")

    risky = [c for c in RISKY_ETFS if c in prices.columns]
    defensive = [c for c in DEFENSIVE_ETFS if c in prices.columns]
    sectors = [c for c in SECTOR_ETFS if c in prices.columns]
    out["risky_pct_above_4w_ma"] = _pct_above_ma(prices[risky], 4)
    out["risky_pct_above_10w_ma"] = _pct_above_ma(prices[risky], 10)
    out["risky_pct_positive_4w"] = (prices[risky].pct_change(4) > 0).mean(axis=1)
    out["risky_pct_positive_8w"] = (prices[risky].pct_change(8) > 0).mean(axis=1)
    out["breadth_improvement_1w"] = out["risky_pct_above_4w_ma"] - out["risky_pct_above_4w_ma"].shift(1)
    out["breadth_improvement_2w"] = out["risky_pct_above_4w_ma"] - out["risky_pct_above_4w_ma"].shift(2)
    out["breadth_improvement_4w"] = out["risky_pct_above_4w_ma"] - out["risky_pct_above_4w_ma"].shift(4)
    out["sector_pct_above_10w_ma"] = _pct_above_ma(prices[sectors], 10)
    out["risk_vs_defensive_breadth"] = out["risky_pct_above_10w_ma"] - _pct_above_ma(prices[defensive], 10)
    out["breadth_thrust_flag"] = ((out["risky_pct_above_4w_ma"] > 0.70) & (out["breadth_improvement_4w"] > 0.25)).astype(float)
    out["breadth_acceleration"] = out["breadth_improvement_2w"] - out["breadth_improvement_4w"].shift(2)

    hyg_lqd = prices["HYG"] / prices["LQD"]
    hyg_shy = prices["HYG"] / prices["SHY"]
    out["hyg_lqd_ret_4w"] = hyg_lqd.pct_change(4)
    out["hyg_lqd_trend_8w"] = hyg_lqd / hyg_lqd.rolling(8).mean() - 1.0
    out["hyg_lqd_ma_slope_4w"] = hyg_lqd.rolling(8).mean() / hyg_lqd.rolling(8).mean().shift(4) - 1.0
    out["hyg_shy_mom_4w"] = hyg_shy.pct_change(4)
    out["credit_improvement_flag"] = ((out["hyg_lqd_ret_4w"] > 0) & (out["hyg_shy_mom_4w"] > 0)).astype(float)
    out["credit_deterioration_flag"] = (out["hyg_lqd_ret_4w"] < -0.015).astype(float)
    out["credit_acceleration"] = out["hyg_lqd_ret_4w"] - out["hyg_lqd_ret_4w"].shift(4)

    out["vix"] = pd.to_numeric(vix.get("VIX"), errors="coerce")
    out["vix3m"] = pd.to_numeric(vix.get("VIX3M"), errors="coerce")
    out["vix_percentile"] = _rolling_rank(out["vix"], 52)
    out["vix_change_1w"] = out["vix"].pct_change(1)
    out["vix_change_2w"] = out["vix"].pct_change(2)
    out["vix_change_4w"] = out["vix"].pct_change(4)
    out["vix_drawdown_from_13w_high"] = out["vix"] / out["vix"].rolling(13).max() - 1.0
    out["vix_spike_fading_flag"] = ((out["vix_percentile"].shift(4) > 0.75) & (out["vix_change_4w"] < -0.10)).astype(float)
    out["vix_ratio"] = out["vix"] / out["vix3m"]
    out["vix_term_structure_ok"] = ((out["vix_ratio"] <= 1.0) | out["vix_ratio"].isna()).astype(float)
    out["vol_normalization_flag"] = ((out["vix_percentile"] < 0.70) & (out["vix_change_4w"] < 0)).astype(float)
    out["too_late_after_vol_collapse_flag"] = ((out["vix_percentile"] < 0.35) & (out["risky_pct_positive_4w"] > 0.70)).astype(float)
    return out


def _add_family_scores(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel.copy()
    state_non_panic = (~p["market_state"].astype(str).eq("stressed_panic")).astype(float)
    drawdown_depth = (-p["drawdown_26w_high"].clip(upper=0) / 0.20).clip(0, 1)
    rec = (p["recovery_from_recent_low"] / 0.08).clip(0, 1)
    reclaim = p[["reclaim_ma4", "reclaim_ma8"]].mean(axis=1)
    p["score_drawdown_reversal"] = _mean([drawdown_depth, rec, reclaim, (p["drawdown_depth_x_reclaim"] / 0.08).clip(0, 1)])

    p["score_short_horizon_reversal"] = _mean([
        (p["negative_1w"] / 0.03).clip(0, 1),
        (p["negative_2w"] / 0.05).clip(0, 1),
        (p["negative_4w"] / 0.08).clip(0, 1),
        p["reclaim_ma4"] * state_non_panic,
        p["credit_improvement_flag"],
    ])

    p["score_breadth_thrust"] = _mean([
        p["risky_pct_above_4w_ma"],
        p["risky_pct_above_10w_ma"],
        p["risky_pct_positive_4w"],
        p["risky_pct_positive_8w"],
        (p["breadth_improvement_4w"] / 0.30).clip(0, 1),
        p["breadth_thrust_flag"],
        ((p["risk_vs_defensive_breadth"] + 1.0) / 2.0).clip(0, 1),
    ])

    p["score_credit_improvement"] = _mean([
        (p["hyg_lqd_ret_4w"] / 0.03).clip(0, 1),
        ((p["hyg_lqd_trend_8w"] + 0.02) / 0.05).clip(0, 1),
        (p["hyg_lqd_ma_slope_4w"] / 0.02).clip(0, 1),
        (p["hyg_shy_mom_4w"] / 0.03).clip(0, 1),
        p["credit_improvement_flag"],
        1.0 - p["credit_deterioration_flag"].fillna(0),
    ])

    p["score_volatility_normalization"] = _mean([
        (1.0 - p["vix_percentile"]).clip(0, 1),
        (-p["vix_change_4w"] / 0.20).clip(0, 1),
        (-p["vix_drawdown_from_13w_high"] / 0.30).clip(0, 1),
        p["vix_spike_fading_flag"],
        (1.0 - p["realized_vol_pct"]).clip(0, 1),
        (-p["realized_vol_change_4w"] / 0.25).clip(0, 1),
        p["vix_term_structure_ok"],
        p["vol_normalization_flag"],
        1.0 - p["too_late_after_vol_collapse_flag"].fillna(0),
    ])

    p["trend_negative_breadth_improving"] = p["trend_negative_breadth_improving"] * (p["breadth_improvement_4w"] > 0).astype(float)
    p["trend_positive_vol_fading"] = p["trend_positive_vol_fading"] * p["vol_normalization_flag"]
    p["score_momentum_reversal_interaction"] = _mean([
        ((p["medium_momentum_12w"] + 0.10) / 0.25).clip(0, 1),
        (p["momentum_positive_pullback"] / 0.04).clip(0, 1),
        (p["momentum_negative_bounce"] / 0.04).clip(0, 1),
        (p["drawdown_high_accel_positive"] / 0.02).clip(0, 1),
        p["trend_negative_breadth_improving"],
        p["trend_positive_vol_fading"],
        _mean([p["score_drawdown_reversal"], p["score_breadth_thrust"], p["score_credit_improvement"], p["score_volatility_normalization"]]),
    ])

    p["score_equal_weight_composite"] = p[FAMILY_SCORE_COLUMNS].mean(axis=1)
    p["score_and_gated_composite"] = p[["score_drawdown_reversal", "score_credit_improvement", "score_volatility_normalization"]].min(axis=1)
    p["score_or_composite"] = p[FAMILY_SCORE_COLUMNS].max(axis=1)
    p["score_regime_gated_composite"] = p["score_equal_weight_composite"] * ((p["recent_stress_26w"] > 0) | (p["market_drawdown"] < -0.05)).astype(float)
    return p


def _weeks_since_min(s: pd.Series, window: int) -> pd.Series:
    def inner(arr: np.ndarray) -> float:
        if np.all(np.isnan(arr)):
            return np.nan
        return float(len(arr) - 1 - int(np.nanargmin(arr)))

    return s.rolling(window, min_periods=3).apply(inner, raw=True)


def _rolling_rank(s: pd.Series, window: int) -> pd.Series:
    def rank(arr: np.ndarray) -> float:
        cur = arr[-1]
        if np.isnan(cur):
            return np.nan
        valid = arr[~np.isnan(arr)]
        return float((valid <= cur).mean()) if len(valid) > 1 else np.nan

    return s.rolling(window, min_periods=12).apply(rank, raw=True)


def _pct_above_ma(df: pd.DataFrame, window: int) -> pd.Series:
    if df.empty:
        return pd.Series(np.nan, index=df.index)
    return (df > df.rolling(window).mean()).mean(axis=1)


def _mean(parts: list[pd.Series]) -> pd.Series:
    frame = pd.concat(parts, axis=1)
    return frame.mean(axis=1, skipna=True).fillna(0.0).clip(0, 1)

