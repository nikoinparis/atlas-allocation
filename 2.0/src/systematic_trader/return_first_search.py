"""Causal return-first signals and selectors for the Batch 66 search."""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from .independent_return_sources import cross_sectional_score, monthly_weights


def _rolling_trend_quality(prices: pd.DataFrame, window: int) -> pd.DataFrame:
    log_prices = np.log(prices.where(prices > 0.0))

    def quality(values: np.ndarray) -> float:
        if np.isnan(values).any() or len(values) < window:
            return np.nan
        x = np.arange(len(values), dtype=float)
        x -= x.mean()
        y = values - values.mean()
        denominator = float(np.dot(x, x))
        variance = float(np.dot(y, y))
        if denominator <= 0.0 or variance <= 0.0:
            return 0.0
        slope = float(np.dot(x, y) / denominator)
        fitted = slope * x
        r_squared = float(np.dot(fitted, fitted) / variance)
        return slope * 52.0 * max(0.0, min(1.0, r_squared))

    return log_prices.rolling(window, min_periods=window).apply(quality, raw=True)


def advanced_signal_families(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return twelve distinct price-only ranking signals with a one-week lag."""
    prices = prices.apply(pd.to_numeric, errors="coerce")
    returns = prices.pct_change(fill_method=None)
    r4 = prices.div(prices.shift(4)) - 1.0
    r13 = prices.div(prices.shift(13)) - 1.0
    r26 = prices.div(prices.shift(26)) - 1.0
    r52 = prices.shift(4).div(prices.shift(52)) - 1.0
    vol13 = returns.rolling(13, min_periods=8).std(ddof=1)
    vol26 = returns.rolling(26, min_periods=13).std(ddof=1)
    vol52 = returns.rolling(52, min_periods=26).std(ddof=1)
    negative26 = returns.clip(upper=0.0).abs().rolling(26, min_periods=13).sum()
    negative52 = returns.clip(upper=0.0).abs().rolling(52, min_periods=26).sum()
    positive52 = returns.clip(lower=0.0).rolling(52, min_periods=26).sum()
    high52 = prices.rolling(52, min_periods=26).max()
    drawdown52 = prices.div(high52) - 1.0

    ranks = [cross_sectional_score(frame) for frame in (r4, r13, r26, r52)]
    rank_cube = np.stack([frame.to_numpy(dtype=float) for frame in ranks], axis=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        rank_mean_values = np.nanmean(rank_cube, axis=0)
        rank_std_values = np.nanstd(rank_cube, axis=0)
    rank_mean = pd.DataFrame(rank_mean_values, index=prices.index, columns=prices.columns)
    rank_std = pd.DataFrame(rank_std_values, index=prices.index, columns=prices.columns)
    consensus = rank_mean
    persistence = rank_mean - 0.5 * rank_std

    observed = {
        "trend_quality_26": _rolling_trend_quality(prices, 26),
        "trend_quality_52": _rolling_trend_quality(prices, 52),
        "leadership_persistence": r52 * (1.0 - rank_std.clip(0.0, 1.0)),
        "gain_to_pain_26": r26.div(negative26.replace(0.0, np.nan)),
        "gain_to_pain_52": r52.div(negative52.replace(0.0, np.nan)),
        "downside_efficiency_52": (positive52 - negative52).div(negative52.replace(0.0, np.nan)),
        "low_vol_momentum_26": r26.div(vol26.replace(0.0, np.nan)),
        "high_proximity_strength": r13 + prices.div(high52) - 1.0,
        "volatility_breakout": r13.div(vol52.replace(0.0, np.nan)) * vol13.div(vol52.replace(0.0, np.nan)),
        "drawdown_recovery": r13 + 0.5 * drawdown52,
        "rank_consensus": consensus,
        "persistent_consensus": persistence,
    }
    return {
        name: cross_sectional_score(frame.replace([np.inf, -np.inf], np.nan)).shift(1)
        for name, frame in observed.items()
    }


def build_advanced_sources(
    prices: pd.DataFrame,
    *,
    families: list[str],
    universe: list[str],
    top_ns: list[int],
    methods: list[str],
    minimum_score: float,
) -> dict[str, pd.DataFrame]:
    panels = advanced_signal_families(prices)
    sources: dict[str, pd.DataFrame] = {}
    for family in families:
        for top_n in top_ns:
            for method in methods:
                short_method = "equal" if method == "equal_weight" else "score_invvol"
                name = f"{family}__top{top_n}__{short_method}"
                sources[name] = monthly_weights(
                    panels[family], prices, universe, top_n=top_n, method=method,
                    minimum_score=minimum_score,
                )
    return sources


def regime_source_alphas(prices: pd.DataFrame, universe: list[str]) -> dict[str, pd.Series]:
    """Source weights for four rules that switch away from an XLK core."""
    r13 = prices.div(prices.shift(13)) - 1.0
    r26 = prices.div(prices.shift(26)) - 1.0
    returns = prices.pct_change(fill_method=None)
    spy_vol = returns["SPY"].rolling(13, min_periods=8).std(ddof=1) * np.sqrt(52.0)
    available = [asset for asset in universe if asset in prices]
    breadth = r13[available].gt(0.0).mean(axis=1)
    dispersion = r13[available].std(axis=1)
    dispersion_threshold = dispersion.expanding(min_periods=104).median().shift(1)
    vol_threshold = spy_vol.expanding(min_periods=104).quantile(0.60).shift(1)
    observed = {
        "tech_leadership": np.where((r26["XLK"] > r26["SPY"]) & (r26["XLK"] > 0.0), 0.25, 1.0),
        "broad_risk_on": np.where(breadth >= 0.65, 1.0, 0.25),
        "high_dispersion": np.where(dispersion >= dispersion_threshold, 1.0, 0.25),
        "low_volatility_risk_on": np.where((r26["SPY"] > 0.0) & (spy_vol <= vol_threshold), 0.25, 1.0),
    }
    return {
        name: pd.Series(values, index=prices.index, dtype=float).shift(1).fillna(0.25)
        for name, values in observed.items()
    }


def delay_weights(weights: pd.DataFrame, weeks: int, cash_asset: str = "BIL") -> pd.DataFrame:
    delayed = weights.shift(weeks).fillna(0.0)
    empty = delayed.sum(axis=1) <= 1e-12
    if cash_asset in delayed:
        delayed.loc[empty, cash_asset] = 1.0
    return delayed
