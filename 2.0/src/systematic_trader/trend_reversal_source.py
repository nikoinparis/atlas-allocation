"""Monthly trend-qualified cross-sectional reversal source."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import CASH_PROXY, apply_etf_cap


@dataclass(frozen=True)
class ReversalSpec:
    reversal_lookback: int
    medium_trend_lookback: int
    sma_lookback: int
    top_n: int


def build_reversal_weights(prices: pd.DataFrame, assets: list[str], spec: ReversalSpec) -> pd.DataFrame:
    assets = [asset for asset in assets if asset in prices.columns and asset != CASH_PROXY]
    short_return = prices[assets].div(prices[assets].shift(spec.reversal_lookback)) - 1.0
    medium_return = prices[assets].div(prices[assets].shift(spec.medium_trend_lookback)) - 1.0
    sma = prices[assets].rolling(spec.sma_lookback, min_periods=spec.sma_lookback).mean()
    month = prices.index.to_period("M").astype(str).to_numpy()
    rebalance = np.ones(len(prices), dtype=bool)
    if len(prices) > 1:
        rebalance[:-1] = month[:-1] != month[1:]
    current = pd.Series(0.0, index=prices.columns)
    current.loc[CASH_PROXY] = 1.0
    rows: list[pd.Series] = []
    for location, date in enumerate(prices.index):
        if rebalance[location]:
            eligible = medium_return.loc[date].gt(0.0) & prices.loc[date, assets].gt(sma.loc[date])
            ranked = short_return.loc[date, eligible[eligible].index].dropna().sort_values(ascending=True)
            selected = ranked.head(spec.top_n).index.tolist()
            current = pd.Series(0.0, index=prices.columns)
            if selected:
                current.loc[selected] = 1.0 / len(selected)
            else:
                current.loc[CASH_PROXY] = 1.0
        row = current.copy()
        row.name = date
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=prices.columns).fillna(0.0)


def blend_with_ggg(baseline: pd.DataFrame, source: pd.DataFrame, weight: float) -> pd.DataFrame:
    rows: list[pd.Series] = []
    for date in baseline.index:
        mixed = (1.0 - weight) * baseline.loc[date] + weight * source.loc[date]
        capped = apply_etf_cap(mixed)
        capped.name = date
        rows.append(capped)
    return pd.DataFrame(rows).reindex(columns=baseline.columns).fillna(0.0)
