"""Performance metrics for the options convexity research module.

These mirror the project's canonical conventions (see
``scripts/production_metrics.py``) so results are comparable:

  * Weekly periodicity, 52 weeks per year.
  * ``cagr`` is the geometric annual growth rate of weekly net returns.
  * ``ann_vol`` uses sample volatility (ddof=1) annualized by sqrt(52).
  * ``sharpe`` is ``cagr / ann_vol`` with a zero risk-free rate.
  * ``cvar_5`` is the mean of weekly returns at or below the 5th percentile.

The module is kept self-contained (no import of production code) so this
research experiment stays fully standalone, as required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS_PER_YEAR = 52
VOL_DDOF = 1


def _clean(returns: pd.Series) -> pd.Series:
    return pd.to_numeric(pd.Series(returns), errors="coerce").dropna()


def cagr(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    ret = _clean(returns)
    if len(ret) < 2:
        return np.nan
    growth = float((1.0 + ret).prod())
    years = len(ret) / float(ppy)
    return growth ** (1.0 / years) - 1.0 if years > 0 and growth > 0 else np.nan


def annualized_return(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    """Arithmetic annualized return (mean weekly return * 52)."""

    ret = _clean(returns)
    return float(ret.mean() * ppy) if len(ret) else np.nan


def annualized_vol(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    ret = _clean(returns)
    if len(ret) <= VOL_DDOF:
        return np.nan
    return float(ret.std(ddof=VOL_DDOF) * np.sqrt(ppy))


def sharpe(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    ar, av = cagr(returns, ppy), annualized_vol(returns, ppy)
    return float(ar / av) if np.isfinite(ar) and np.isfinite(av) and av > 0 else np.nan


def sortino(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    ret = _clean(returns)
    if len(ret) < 2:
        return np.nan
    downside = ret[ret < 0.0]
    if len(downside) <= VOL_DDOF:
        return np.nan
    dvol = float(downside.std(ddof=VOL_DDOF) * np.sqrt(ppy))
    ar = cagr(ret, ppy)
    return float(ar / dvol) if np.isfinite(ar) and dvol > 0 else np.nan


def max_drawdown(returns: pd.Series) -> float:
    ret = _clean(returns)
    if ret.empty:
        return np.nan
    wealth = (1.0 + ret).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calmar(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> float:
    ar, dd = cagr(returns, ppy), max_drawdown(returns)
    return float(ar / abs(dd)) if np.isfinite(ar) and np.isfinite(dd) and dd < 0 else np.nan


def var_cvar(returns: pd.Series, q: float = 0.05) -> tuple[float, float]:
    ret = _clean(returns)
    if len(ret) < 20:
        return np.nan, np.nan
    var = float(ret.quantile(q))
    tail = ret[ret <= var]
    return var, (float(tail.mean()) if len(tail) else np.nan)


def hit_rate(returns: pd.Series) -> float:
    ret = _clean(returns)
    return float((ret > 0.0).mean()) if len(ret) else np.nan


def summarize(returns: pd.Series, ppy: int = WEEKS_PER_YEAR) -> dict[str, float]:
    """Return the full canonical metric bundle for a weekly return series."""

    ret = _clean(returns)
    var_5, cvar_5 = var_cvar(ret)
    return {
        "cagr": cagr(ret, ppy),
        "ann_return": annualized_return(ret, ppy),
        "ann_vol": annualized_vol(ret, ppy),
        "sharpe": sharpe(ret, ppy),
        "sortino": sortino(ret, ppy),
        "max_drawdown": max_drawdown(ret),
        "calmar": calmar(ret, ppy),
        "var_5": var_5,
        "cvar_5": cvar_5,
        "hit_rate": hit_rate(ret),
        "n_weeks": int(len(ret)),
    }


def summarize_option_trades(trades: pd.DataFrame) -> dict[str, float]:
    """Summarize the per-trade economics of the options sleeve.

    ``trades`` is expected to have at least ``trade_return`` (option-only return
    = payoff/premium - 1) and ``premium_fraction`` (fraction of portfolio
    spent). Returns hit rate, average/median/worst trade returns, etc. Safe to
    call on an empty frame (returns NaNs / zeros).
    """

    if trades is None or trades.empty:
        return {
            "n_trades": 0,
            "option_hit_rate": np.nan,
            "avg_trade_return": np.nan,
            "median_trade_return": np.nan,
            "worst_trade_return": np.nan,
            "best_trade_return": np.nan,
            "avg_premium_fraction": np.nan,
        }

    tr = pd.to_numeric(trades["trade_return"], errors="coerce").dropna()
    return {
        "n_trades": int(len(tr)),
        "option_hit_rate": float((tr > 0.0).mean()) if len(tr) else np.nan,
        "avg_trade_return": float(tr.mean()) if len(tr) else np.nan,
        "median_trade_return": float(tr.median()) if len(tr) else np.nan,
        "worst_trade_return": float(tr.min()) if len(tr) else np.nan,
        "best_trade_return": float(tr.max()) if len(tr) else np.nan,
        "avg_premium_fraction": float(
            pd.to_numeric(trades.get("premium_fraction"), errors="coerce").mean()
        ),
    }
