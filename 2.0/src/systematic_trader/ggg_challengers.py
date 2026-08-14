"""Causal, bounded ETF overlays for the frozen GGG research benchmark."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import CASH_PROXY, apply_etf_cap


@dataclass(frozen=True)
class ChallengerSpec:
    momentum_strength: float
    cash_redeploy_fraction: float


def trailing_signals(prices: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    momentum = prices.div(prices.shift(26)) - 1.0
    trend = prices.gt(prices.rolling(43, min_periods=43).mean())
    return momentum, trend


def row_zscore(row: pd.Series) -> pd.Series:
    valid = row.replace([np.inf, -np.inf], np.nan).dropna()
    result = pd.Series(0.0, index=row.index)
    if len(valid) > 1 and float(valid.std(ddof=1)) > 0:
        result.loc[valid.index] = ((valid - valid.mean()) / valid.std(ddof=1)).clip(-2.0, 2.0)
    return result


def apply_challenger(
    baseline_weights: pd.DataFrame,
    prices: pd.DataFrame,
    spec: ChallengerSpec,
) -> pd.DataFrame:
    """Transform date-t weights using information observable by date t."""
    prices = prices.reindex(index=baseline_weights.index, columns=baseline_weights.columns)
    momentum, trend = trailing_signals(prices)
    rows: list[pd.Series] = []
    risky_columns = [column for column in baseline_weights.columns if column != CASH_PROXY]
    for date in baseline_weights.index:
        row = baseline_weights.loc[date].fillna(0.0).copy()
        if spec.momentum_strength > 0:
            score = row_zscore(momentum.loc[date, risky_columns])
            multiplier = np.exp(spec.momentum_strength * score)
            row.loc[risky_columns] = row.loc[risky_columns] * multiplier
            total = float(row.sum())
            if total > 0:
                row = row / total
        if spec.cash_redeploy_fraction > 0 and {"SPY", "QQQ", CASH_PROXY}.issubset(row.index):
            risk_on = bool(
                momentum.loc[date, "SPY"] > 0
                and momentum.loc[date, "QQQ"] > 0
                and trend.loc[date, "SPY"]
                and trend.loc[date, "QQQ"]
            )
            if risk_on:
                amount = float(row[CASH_PROXY]) * spec.cash_redeploy_fraction
                row[CASH_PROXY] -= amount
                row["SPY"] += amount / 2.0
                row["QQQ"] += amount / 2.0
        row = apply_etf_cap(row)
        row.name = date
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=baseline_weights.columns).fillna(0.0)
