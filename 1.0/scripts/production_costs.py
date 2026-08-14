"""Canonical turnover and transaction-cost logic for production artifacts.

Convention:
    * Turnover is one-way turnover, also called half-turnover:
      ``0.5 * sum(abs(current_weight - prior_weight))``.
    * The first row has undefined turnover because there is no prior production
      portfolio in the saved path.  Cost fills that first row to zero.
    * Cost is a decimal return drag: ``one_way_turnover * cost_bps / 10000``.
    * The default production assumption is 10 bps per unit of one-way turnover.
    * Saved production paths use Friday-close decision weights applied to
      next-week close-to-close returns from weekly prices
      (``prices.pct_change().shift(-1)``).

These conventions reproduce the promoted Track A artifact and are intentionally
not an execution-quality broker cost model.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from production_config import DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER


def full_l1_turnover(weights: pd.DataFrame) -> pd.Series:
    """Return full L1 turnover, ``sum(abs(delta weight))``."""

    w = weights.sort_index().apply(pd.to_numeric, errors="coerce").fillna(0.0)
    turnover = w.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    return turnover


def one_way_turnover(weights: pd.DataFrame) -> pd.Series:
    """Return canonical one-way turnover, ``0.5 * full_l1_turnover``."""

    return 0.5 * full_l1_turnover(weights)


def transaction_cost_from_turnover(
    turnover: pd.Series,
    cost_bps: float = DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
) -> pd.Series:
    """Convert one-way turnover into decimal return drag."""

    return pd.to_numeric(turnover, errors="coerce").fillna(0.0) * (float(cost_bps) / 10000.0)


def next_week_returns_from_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute production next-week close-to-close returns from weekly prices."""

    return prices.sort_index().apply(pd.to_numeric, errors="coerce").pct_change().shift(-1)


def portfolio_path(
    weights: pd.DataFrame,
    next_week_returns: pd.DataFrame,
    cost_bps: float = DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
) -> pd.DataFrame:
    """Recompute the production portfolio path from weights and forward returns."""

    common = weights.index.intersection(next_week_returns.index)
    cols = [c for c in weights.columns if c in next_week_returns.columns]
    w = weights.reindex(index=common, columns=cols).fillna(0.0)
    r = next_week_returns.reindex(index=common, columns=cols).fillna(0.0)
    gross = (w * r).sum(axis=1)
    turnover = one_way_turnover(w)
    cost = transaction_cost_from_turnover(turnover, cost_bps)
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame(
        {
            "Date": common,
            "gross_return": gross.values,
            "net_return": net.values,
            "turnover": turnover.values,
            "cost": cost.values,
            "wealth": wealth.values,
            "drawdown": drawdown.values,
        }
    )


def cost_sensitivity_paths(
    weights: pd.DataFrame,
    next_week_returns: pd.DataFrame,
    *,
    multipliers: Iterable[float] = (1.0, 2.0, 3.0),
    base_cost_bps: float = DEFAULT_COST_BPS_PER_ONE_WAY_TURNOVER,
) -> dict[float, pd.DataFrame]:
    """Return production paths at cost multipliers such as 1x, 2x, and 3x."""

    return {
        float(multiplier): portfolio_path(weights, next_week_returns, base_cost_bps * float(multiplier))
        for multiplier in multipliers
    }


def summarize_costs(path: pd.DataFrame, weeks_per_year: int = 52) -> dict[str, float]:
    """Summarize canonical turnover and cost fields from a production path."""

    turnover = pd.to_numeric(path.get("turnover", pd.Series(dtype=float)), errors="coerce")
    cost = pd.to_numeric(path.get("cost", pd.Series(dtype=float)), errors="coerce")
    return {
        "avg_weekly_turnover": float(turnover.mean()) if len(turnover) else np.nan,
        "annualized_turnover": float(turnover.mean() * weeks_per_year) if len(turnover) else np.nan,
        "total_cost": float(cost.sum()) if len(cost) else np.nan,
        "avg_weekly_cost": float(cost.mean()) if len(cost) else np.nan,
        "annualized_cost": float(cost.mean() * weeks_per_year) if len(cost) else np.nan,
    }
