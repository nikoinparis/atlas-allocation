"""Causal price-only signal families for independent return-source discovery."""

from __future__ import annotations

import numpy as np
import pandas as pd

CASH = "cash::USD"


def cross_sectional_score(frame: pd.DataFrame) -> pd.DataFrame:
    def score(row: pd.Series) -> pd.Series:
        valid = row.replace([np.inf, -np.inf], np.nan).dropna()
        output = pd.Series(np.nan, index=row.index, dtype=float)
        if not valid.empty:
            clipped = valid.clip(valid.quantile(0.05), valid.quantile(0.95))
            output.loc[valid.index] = clipped.rank(pct=True, method="average") * 2.0 - 1.0
        return output
    return frame.apply(score, axis=1)


def signal_families(prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return weekly signals delayed one complete observation before trading."""
    prices = prices.apply(pd.to_numeric, errors="coerce")
    returns = prices.pct_change(fill_method=None)
    r13 = prices.div(prices.shift(13)) - 1.0
    r26 = prices.div(prices.shift(26)) - 1.0
    r52_skip4 = prices.shift(4).div(prices.shift(52)) - 1.0
    vol13 = returns.rolling(13, min_periods=8).std(ddof=1) * np.sqrt(52.0)
    downside26 = returns.clip(upper=0.0).pow(2).rolling(26, min_periods=13).mean().pow(0.5) * np.sqrt(52.0)
    positive_share26 = returns.gt(0.0).rolling(26, min_periods=13).mean()
    multi = (
        cross_sectional_score(r13)
        + cross_sectional_score(r26)
        + cross_sectional_score(r52_skip4)
    ) / 3.0
    observed = {
        "breakout_52w": prices.div(prices.rolling(52, min_periods=26).max()) - 1.0,
        "momentum_acceleration": r13 - r52_skip4 / 4.0,
        "downside_adjusted_momentum": r52_skip4.div(downside26.replace(0.0, np.nan)),
        "trend_consistency": r52_skip4 * positive_share26,
        "reversal_4w": -(prices.div(prices.shift(4)) - 1.0),
        "risk_adjusted_13w": r13.div(vol13.replace(0.0, np.nan)),
        "multi_horizon_strength": multi,
    }
    return {name: cross_sectional_score(frame).shift(1) for name, frame in observed.items()}


def monthly_weights(
    signal: pd.DataFrame,
    prices: pd.DataFrame,
    universe: list[str],
    *,
    top_n: int,
    method: str = "score_inverse_volatility",
    minimum_score: float = 0.05,
) -> pd.DataFrame:
    """Build fully invested long-only weights on true calendar-final Fridays."""
    if method not in {"equal_weight", "score_inverse_volatility"}:
        raise ValueError("unsupported method")
    index = prices.index
    columns = list(dict.fromkeys([*prices.columns, CASH]))
    output = pd.DataFrame(0.0, index=index, columns=columns)
    ordinary = prices.pct_change(fill_method=None)
    vol = ordinary.rolling(26, min_periods=13).std(ddof=1)
    month = index.to_period("M")
    rebalance = pd.Series(False, index=index)
    if len(index) > 1:
        rebalance.iloc[:-1] = month[:-1].to_numpy() != month[1:].to_numpy()
    if len(index):
        rebalance.iloc[0] = True
        rebalance.iloc[-1] = (index[-1] + pd.Timedelta(days=7)).month != index[-1].month
    current = pd.Series(0.0, index=columns)
    current[CASH] = 1.0
    for date in index:
        if bool(rebalance.loc[date]):
            row = signal.reindex(index=[date], columns=universe).iloc[0]
            eligible = row[(row > minimum_score) & prices.loc[date, universe].notna()]
            selected = eligible.sort_values(ascending=False).head(top_n)
            current = pd.Series(0.0, index=columns)
            if len(selected):
                if method == "equal_weight":
                    raw = pd.Series(1.0, index=selected.index)
                else:
                    inv = 1.0 / vol.loc[date, selected.index].replace(0.0, np.nan)
                    raw = (selected - minimum_score).clip(lower=1e-12) * inv.fillna(1.0)
                risk_budget = len(selected) / top_n
                current.loc[raw.index] = raw / raw.sum() * risk_budget
            remainder = 1.0 - current.sum()
            destination = "BIL" if "BIL" in prices and pd.notna(prices.loc[date, "BIL"]) else CASH
            current[destination] += remainder
        output.loc[date] = current
    return output
