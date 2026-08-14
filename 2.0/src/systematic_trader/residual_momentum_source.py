"""Independent price-derived residual momentum source."""

from __future__ import annotations

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import CASH_PROXY


def _rank_score(row: pd.Series) -> pd.Series:
    valid = row.dropna()
    output = pd.Series(np.nan, index=row.index, dtype=float)
    if valid.empty:
        return output
    lower, upper = valid.quantile(0.05), valid.quantile(0.95)
    valid = valid.clip(lower, upper)
    if len(valid) == 1:
        output.loc[valid.index] = 0.0
    else:
        ranks = valid.rank(method="average")
        output.loc[valid.index] = ((ranks - 1.0) / (len(valid) - 1.0)) * 2.0 - 1.0
    return output


def residual_momentum_signal(prices: pd.DataFrame, market: str = "SPY") -> pd.DataFrame:
    log_returns = np.log(prices / prices.shift(1))
    market_returns = log_returns[market]
    market_variance = market_returns.rolling(52, min_periods=26).var()
    beta = pd.DataFrame({column: log_returns[column].rolling(52, min_periods=26).cov(market_returns).div(market_variance) for column in log_returns.columns})
    market_mean = market_returns.rolling(52, min_periods=26).mean()
    alpha = log_returns.rolling(52, min_periods=26).mean().sub(beta.mul(market_mean, axis=0), axis=0)
    expected = alpha.shift(1).add(beta.shift(1).mul(market_returns, axis=0), axis=0)
    residual = log_returns - expected
    formation = residual.shift(4).rolling(48, min_periods=24).sum()
    observed = np.expm1(formation)
    return observed.apply(_rank_score, axis=1).shift(1)


def top_five_weights(signal: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    for date in prices.index:
        eligible = signal.loc[date].drop(labels=[CASH_PROXY], errors="ignore").dropna()
        selected = eligible[eligible > 0.0].sort_values(ascending=False).head(5).index
        if len(selected):
            weights.loc[date, selected] = 1.0 / len(selected)
        else:
            weights.loc[date, CASH_PROXY] = 1.0
    return weights


def volatility_manage(weights: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    spy_vol = prices["SPY"].pct_change().rolling(13, min_periods=8).std(ddof=1) * np.sqrt(52.0)
    scale = pd.Series(0.8, index=prices.index)
    scale.loc[spy_vol <= 0.18] = 1.0
    scale.loc[(spy_vol > 0.18) & (spy_vol <= 0.25)] = 0.8
    scale.loc[spy_vol > 0.25] = 0.6
    risky = [column for column in weights.columns if column != CASH_PROXY]
    output = weights.copy()
    output[risky] = output[risky].mul(scale.fillna(0.8), axis=0)
    output[CASH_PROXY] = 1.0 - output[risky].sum(axis=1)
    return output
