"""Causal long-only cross-asset trend helpers.

Signals are formed from completed weekly observations and weights are applied to the
following weekly return.  The module deliberately contains no parameter search or
candidate-selection logic.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
import pandas as pd


def _capped_inverse_volatility(volatility: pd.Series, cap: float) -> pd.Series:
    """Allocate inverse-volatility weights subject to a hard per-asset cap."""
    result = pd.Series(0.0, index=volatility.index, dtype=float)
    remaining = volatility.replace([np.inf, -np.inf], np.nan).dropna()
    remaining = remaining[remaining > 0.0]
    budget = 1.0
    while budget > 1e-12 and not remaining.empty:
        inverse = 1.0 / remaining
        proposal = budget * inverse / inverse.sum()
        room = cap - result.loc[remaining.index]
        allocation = pd.concat([proposal, room], axis=1).min(axis=1).clip(lower=0.0)
        result.loc[allocation.index] += allocation
        budget = 1.0 - float(result.sum())
        remaining = remaining.loc[(cap - result.loc[remaining.index]) > 1e-12]
    return result


def build_trend_weights(
    prices: pd.DataFrame,
    assets: Iterable[str],
    cash_asset: str,
    lookbacks: Iterable[int] = (13, 26, 52),
    volatility_lookback: int = 26,
    minimum_volatility_observations: int = 13,
    maximum_asset_weight: float = 0.20,
    rebalance_every_weeks: int = 4,
) -> pd.DataFrame:
    """Build causal decision-date weights from trailing prices only."""
    assets = list(assets)
    lookbacks = tuple(int(value) for value in lookbacks)
    required = assets + [cash_asset]
    missing = sorted(set(required) - set(prices.columns))
    if missing:
        raise ValueError(f"missing price columns: {missing}")
    if not 0.0 < maximum_asset_weight <= 1.0:
        raise ValueError("maximum_asset_weight must be in (0, 1]")
    if rebalance_every_weeks < 1:
        raise ValueError("rebalance_every_weeks must be positive")

    panel = prices.loc[:, required].sort_index().astype(float)
    weekly_returns = panel.pct_change(fill_method=None)
    volatility = weekly_returns[assets].rolling(
        volatility_lookback, min_periods=minimum_volatility_observations
    ).std(ddof=1) * math.sqrt(52.0)
    momentum = sum(
        (panel[assets] / panel[assets].shift(lookback) - 1.0 for lookback in lookbacks),
        start=pd.DataFrame(0.0, index=panel.index, columns=assets),
    ) / float(len(lookbacks))

    weights = pd.DataFrame(0.0, index=panel.index, columns=required)
    previous = pd.Series(0.0, index=required, dtype=float)
    previous[cash_asset] = 1.0
    first_eligible = max(max(lookbacks), minimum_volatility_observations)
    for position, date in enumerate(panel.index):
        should_rebalance = position >= first_eligible and (position - first_eligible) % rebalance_every_weeks == 0
        if should_rebalance:
            eligible = (momentum.loc[date] > 0.0) & volatility.loc[date].notna() & panel.loc[date, assets].notna()
            risk = _capped_inverse_volatility(volatility.loc[date, eligible], maximum_asset_weight)
            target = pd.Series(0.0, index=required, dtype=float)
            target.loc[risk.index] = risk
            target[cash_asset] = max(0.0, 1.0 - float(risk.sum()))
            previous = target
        weights.loc[date] = previous
    return weights


def apply_next_week_returns(
    prices: pd.DataFrame,
    weights: pd.DataFrame,
    cost_bps_one_way: float,
) -> pd.DataFrame:
    """Apply decision-date weights to the next observed weekly return."""
    aligned_prices = prices.reindex(index=weights.index, columns=weights.columns).astype(float)
    forward = aligned_prices.pct_change(fill_method=None).shift(-1)
    available = forward.notna()
    invested = weights.where(available, 0.0)
    missing_weight = 1.0 - invested.sum(axis=1)
    if "BIL" in invested.columns:
        invested.loc[:, "BIL"] += missing_weight
    gross_return = (invested * forward.fillna(0.0)).sum(axis=1)
    one_way_turnover = 0.5 * invested.diff().abs().sum(axis=1)
    one_way_turnover.iloc[0] = 0.0
    cost = one_way_turnover * float(cost_bps_one_way) / 10_000.0
    result = pd.DataFrame(
        {
            "gross_return": gross_return,
            "turnover": one_way_turnover,
            "cost": cost,
            "net_return": gross_return - cost,
        },
        index=weights.index,
    )
    return result.iloc[:-1]


def performance_metrics(returns: pd.Series) -> dict[str, float | int | str]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        raise ValueError("returns are empty")
    wealth = (1.0 + clean).cumprod()
    years = len(clean) / 52.0
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if wealth.iloc[-1] > 0.0 else float("nan")
    volatility = float(clean.std(ddof=1) * math.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    rolling = (1.0 + clean).rolling(52).apply(np.prod, raw=True) - 1.0
    downside = clean[clean < 0.0]
    cvar = float(downside.nsmallest(max(1, int(math.ceil(0.05 * len(clean))))).mean())
    return {
        "start": str(clean.index[0].date()),
        "end": str(clean.index[-1].date()),
        "weeks": int(len(clean)),
        "cagr": cagr,
        "annual_volatility": volatility,
        "sharpe_zero_rf": float(clean.mean() * 52.0 / volatility) if volatility > 0.0 else float("nan"),
        "max_drawdown": float(drawdown.min()),
        "calmar": cagr / abs(float(drawdown.min())) if drawdown.min() < 0.0 else float("nan"),
        "worst_rolling_52w": float(rolling.min()) if rolling.notna().any() else float("nan"),
        "cvar_5_weekly": cvar,
        "total_return": float(wealth.iloc[-1] - 1.0),
    }


def blend_returns(base: pd.Series, trend: pd.Series, trend_weight: float) -> pd.Series:
    if not 0.0 <= trend_weight <= 1.0:
        raise ValueError("trend_weight must be in [0, 1]")
    aligned = pd.concat([base.rename("base"), trend.rename("trend")], axis=1, join="inner").dropna()
    return (1.0 - trend_weight) * aligned["base"] + trend_weight * aligned["trend"]
