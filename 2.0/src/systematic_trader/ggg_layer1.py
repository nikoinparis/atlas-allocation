"""Platform-owned reconstruction of the Layer 1 inputs consumed by causal GGG."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Layer1Bundle:
    panels: dict[str, pd.DataFrame]
    regime_features: pd.DataFrame
    source_status: dict[str, str]


def _numeric(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.apply(pd.to_numeric, errors="coerce").sort_index()


def panel_score(panel: pd.DataFrame) -> pd.DataFrame:
    def score(row: pd.Series) -> pd.Series:
        valid = row.dropna()
        result = pd.Series(np.nan, index=row.index, dtype=float)
        if valid.empty:
            return result
        if len(valid) == 1:
            result.loc[valid.index] = 0.0
            return result
        lower, upper = valid.quantile(0.05), valid.quantile(0.95)
        clipped = valid.clip(lower=lower, upper=upper)
        ranks = clipped.rank(method="average")
        result.loc[valid.index] = (ranks - 1.0) / (len(valid) - 1.0) * 2.0 - 1.0
        return result
    return panel.apply(score, axis=1)


def _trailing_return(prices: pd.DataFrame, lookback: int, skip: int = 0) -> pd.DataFrame:
    return prices.shift(skip).div(prices.shift(lookback)) - 1.0


def _rolling_beta(asset_returns: pd.DataFrame, market: pd.Series, window: int, minimum: int) -> pd.DataFrame:
    variance = market.rolling(window, min_periods=minimum).var()
    return pd.DataFrame({asset: asset_returns[asset].rolling(window, min_periods=minimum).cov(market).div(variance) for asset in asset_returns}, index=asset_returns.index)


def _residual_momentum(log_returns: pd.DataFrame, market: pd.Series) -> pd.DataFrame:
    beta = _rolling_beta(log_returns, market, 52, 26)
    alpha = log_returns.rolling(52, min_periods=26).mean().sub(beta.mul(market.rolling(52, min_periods=26).mean(), axis=0), axis=0)
    expected = alpha.shift(1).add(beta.shift(1).mul(market, axis=0), axis=0)
    residual = log_returns - expected
    formation = residual.shift(4).rolling(48, min_periods=24).sum()
    return panel_score(np.expm1(formation)).shift(1)


def _quality(prices: pd.DataFrame, log_returns: pd.DataFrame) -> pd.DataFrame:
    simple = prices.pct_change(fill_method=None).where(log_returns.notna())
    realized_vol = log_returns.rolling(26, min_periods=13).std() * np.sqrt(52.0)
    downside = simple.clip(upper=0.0).rolling(26, min_periods=13).std() * np.sqrt(52.0)
    rolling_high = prices.rolling(52, min_periods=26).max()
    drawdown = prices.div(rolling_high) - 1.0
    frequency = drawdown.lt(-0.05).rolling(52, min_periods=26).mean()
    severity = drawdown.clip(upper=0.0).abs().rolling(52, min_periods=26).mean()
    observed = (
        panel_score(-realized_vol) + panel_score(-downside)
        + panel_score(-frequency) + panel_score(-severity)
    ) / 4.0
    return observed.shift(1)


def _value(prices: pd.DataFrame) -> pd.DataFrame:
    mean = prices.rolling(260, min_periods=104).mean()
    gap = mean.div(prices) - 1.0
    price_z = (prices - mean).div(prices.rolling(260, min_periods=104).std() + 1e-12)
    return ((panel_score(gap) + panel_score(-price_z)) / 2.0).shift(1)


def _bab(daily_log_returns: pd.DataFrame, weekly_index: pd.DatetimeIndex, columns: list[str], market: str) -> pd.DataFrame:
    daily = _numeric(daily_log_returns).reindex(columns=columns)
    simple = np.expm1(daily)
    beta = _rolling_beta(simple, simple[market], 126, 63)
    weekly_beta = beta.resample("W-FRI").last().reindex(weekly_index)
    return panel_score(-weekly_beta).shift(1)


def _carry(actions: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    if actions is None or actions.empty:
        return pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    frame = actions.copy()
    date_column = next((name for name in ("Date", "date", "event_date") if name in frame), None)
    ticker_column = next((name for name in ("ticker", "Ticker") if name in frame), None)
    value_column = next((name for name in ("distribution", "dividend", "dividends", "amount") if name in frame), None)
    if not date_column or not ticker_column or not value_column:
        raise ValueError("distribution actions require date, ticker, and amount fields")
    if "action_type" in frame:
        frame = frame.loc[frame["action_type"].eq("cash_distribution")]
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
    frame = frame.dropna(subset=[date_column, ticker_column, value_column])
    pivot = frame.pivot_table(index=date_column, columns=ticker_column, values=value_column, aggfunc="sum").sort_index()
    weekly = pivot.resample("W-FRI").sum().reindex(prices.index, fill_value=0.0)
    yield_panel = weekly.rolling(52, min_periods=4).sum().div(prices.reindex(columns=weekly.columns)).reindex(columns=prices.columns)
    return panel_score(yield_panel).shift(2)


def _rolling_z(series: pd.Series) -> pd.Series:
    mean = series.rolling(104, min_periods=52).mean()
    std = series.rolling(104, min_periods=52).std()
    return (series - mean) / (std + 1e-12)


def build_regime_features(
    index: pd.DatetimeIndex,
    *,
    vix_term: pd.DataFrame | None,
    macro_weekly: pd.DataFrame | None,
    google_trends: pd.DataFrame | None,
) -> tuple[pd.DataFrame, str]:
    if vix_term is None or vix_term.empty:
        return pd.DataFrame(index=index), "blocked_missing_vix_term_structure"
    vix = _numeric(vix_term).reindex(index).ffill()
    macro = pd.DataFrame(index=index) if macro_weekly is None else _numeric(macro_weekly).reindex(index).ffill()
    google = pd.DataFrame(index=index) if google_trends is None else _numeric(google_trends).reindex(index).ffill(limit=2)
    output = pd.DataFrame(index=index); components: list[str] = []
    if "VIX" in vix:
        output["vix_level_observed"] = vix["VIX"]
        output["vix_level_z_observed"] = _rolling_z(vix["VIX"])
        output["vix_level_z_tradable"] = output["vix_level_z_observed"].shift(1); components.append("vix_level_z_tradable")
    if "slope_1m_3m" in vix:
        output["vix_slope_1m_3m_observed"] = vix["slope_1m_3m"]
        output["vix_slope_risk_off_z_observed"] = -_rolling_z(vix["slope_1m_3m"])
        output["vix_slope_risk_off_z_tradable"] = output["vix_slope_risk_off_z_observed"].shift(1); components.append("vix_slope_risk_off_z_tradable")
        output["vix_contango_flag_observed"] = vix["slope_1m_3m"].gt(0).astype(float)
        output["vix_contango_flag_tradable"] = output["vix_contango_flag_observed"].shift(1)
    for raw, name, sign in (
        ("T10Y2Y", "yield_curve_risk_off_z_observed", -1.0),
        ("BAMLH0A0HYM2", "credit_spread_risk_off_z_observed", 1.0),
        ("NFCI", "nfci_risk_off_z_observed", 1.0),
        ("policy_minus_3m", "policy_minus_3m_risk_off_z_observed", 1.0),
        ("NAPM", "pmi_risk_off_z_observed", -1.0),
        ("DTWEXBGS", "dollar_risk_off_z_observed", 1.0),
    ):
        if raw in macro:
            output[name] = sign * _rolling_z(macro[raw]); tradable = name.replace("_observed", "_tradable")
            output[tradable] = output[name].shift(2); components.append(tradable)
    if "fear_composite_zscore" in google:
        output["google_fear_z_observed"] = google["fear_composite_zscore"]
    elif "fear_composite" in google:
        output["google_fear_z_observed"] = _rolling_z(google["fear_composite"])
    if "google_fear_z_observed" in output:
        output["google_fear_z_tradable"] = output["google_fear_z_observed"].shift(2); components.append("google_fear_z_tradable")
    output["macro_risk_score_tradable"] = output[components].mean(axis=1) if components else np.nan
    output["macro_regime_label_tradable"] = pd.cut(output["macro_risk_score_tradable"], [-np.inf, -0.5, 0.5, np.inf], labels=["risk_on", "neutral", "risk_off"]).astype("object")
    return output, "complete" if components else "blocked_no_regime_components"


def build_layer1_bundle(
    weekly_prices: pd.DataFrame,
    *,
    daily_log_returns: pd.DataFrame,
    distribution_actions: pd.DataFrame,
    market: str = "SPY",
    vix_term: pd.DataFrame | None = None,
    macro_weekly: pd.DataFrame | None = None,
    google_trends: pd.DataFrame | None = None,
) -> Layer1Bundle:
    prices = _numeric(weekly_prices)
    log_returns = np.log(prices.div(prices.shift(1)))
    momentum = _trailing_return(prices, 52, 4)
    components = {lookback: _trailing_return(prices, lookback, 4) for lookback in (13, 26, 39, 52)}
    component_vols = {lookback: frame.rolling(52, min_periods=26).std() for lookback, frame in components.items()}
    inverse = {lookback: 1.0 / vol.clip(lower=0.01) for lookback, vol in component_vols.items()}
    inverse_sum = sum(inverse.values())
    multi = sum(inverse[lookback] * components[lookback] for lookback in components) / inverse_sum
    panels = {
        "xsmom_global": panel_score(momentum).shift(1),
        "xsmom_raw_return_52_4w": momentum,
        "multi_mom_invvol": panel_score(multi).shift(1),
        "residual_momentum": _residual_momentum(log_returns, log_returns[market]),
        "reversal_4w_global": panel_score(-_trailing_return(prices, 4)).shift(1),
        "quality_proxy": _quality(prices, log_returns),
        "value_proxy": _value(prices),
        "bab_proxy": _bab(daily_log_returns, prices.index, list(prices.columns), market),
        "carry_proxy": _carry(distribution_actions, prices),
    }
    regime, regime_status = build_regime_features(prices.index, vix_term=vix_term, macro_weekly=macro_weekly, google_trends=google_trends)
    return Layer1Bundle(
        panels=panels,
        regime_features=regime,
        source_status={
            "price_signals": "complete", "daily_beta": "complete", "distribution_carry": "complete",
            "regime_features": regime_status,
        },
    )
