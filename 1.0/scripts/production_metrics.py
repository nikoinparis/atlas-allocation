"""Canonical production metrics for reports and validation gates.

Metric convention:
    * ``cagr`` is the geometric annual growth rate of weekly net returns.
    * ``ann_return`` is kept as an alias for ``cagr`` because existing
      production summaries used that name for geometric annual return.
    * ``arithmetic_ann_return`` is reported separately as weekly mean * 52.
    * ``ann_vol`` uses sample weekly volatility with ``ddof=1`` annualized by
      sqrt(52).  This matches the promoted registry Sharpe.
    * ``sharpe`` is ``cagr / ann_vol`` with zero risk-free rate.
    * ``var_5`` and ``cvar_5`` are weekly tail metrics on the provided return
      window.  ``cvar_5`` is the mean of returns at or below the 5th percentile.
    * Turnover is canonical one-way turnover if supplied.

The module intentionally exposes arithmetic alternatives where old helper code
used different formulas, so reports can compare conventions without silently
changing history.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from production_config import (
    CANONICAL_VOL_DDOF,
    OFFICIAL_HOLDOUT_START,
    WEEKS_PER_YEAR,
)
from production_costs import summarize_costs


OFFENSE_ASSETS = {
    "SPY",
    "QQQ",
    "IWM",
    "EFA",
    "EEM",
    "VWO",
    "VEA",
    "EWJ",
    "VNQ",
    "HYG",
    "XLY",
    "XLK",
    "XLF",
    "XLI",
    "XLB",
    "XLE",
    "VTV",
    "VUG",
}
DEFENSE_ASSETS = {"BIL", "SHY", "IEF", "TLT", "LQD", "MBB", "TIP", "GLD", "IAU", "UUP", "XLP", "XLU", "XLV"}
EQUITY_ASSETS = {"SPY", "QQQ", "IWM", "EFA", "EEM", "VWO", "VEA", "EWJ", "VNQ", "XLY", "XLK", "XLF", "XLI", "XLB", "XLE", "VTV", "VUG"}


def clean_returns(returns: pd.Series) -> pd.Series:
    """Return numeric returns with missing values removed."""

    return pd.to_numeric(pd.Series(returns), errors="coerce").dropna()


def cagr(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute geometric annual growth rate from periodic returns."""

    ret = clean_returns(returns)
    if len(ret) < 2:
        return np.nan
    growth = float((1.0 + ret).prod())
    years = len(ret) / float(periods_per_year)
    return growth ** (1.0 / years) - 1.0 if years > 0 and growth > 0 else np.nan


def arithmetic_annual_return(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute arithmetic annualized return, ``mean(period return) * periods``."""

    ret = clean_returns(returns)
    return float(ret.mean() * periods_per_year) if len(ret) else np.nan


def annualized_volatility(
    returns: pd.Series,
    periods_per_year: int = WEEKS_PER_YEAR,
    ddof: int = CANONICAL_VOL_DDOF,
) -> float:
    """Compute annualized sample volatility."""

    ret = clean_returns(returns)
    if len(ret) <= ddof:
        return np.nan
    return float(ret.std(ddof=ddof) * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute canonical zero-risk-free Sharpe as CAGR divided by volatility."""

    ar = cagr(returns, periods_per_year)
    av = annualized_volatility(returns, periods_per_year)
    return float(ar / av) if np.isfinite(ar) and np.isfinite(av) and av > 0 else np.nan


def arithmetic_sharpe_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute zero-risk-free Sharpe using arithmetic annualized return."""

    ar = arithmetic_annual_return(returns, periods_per_year)
    av = annualized_volatility(returns, periods_per_year)
    return float(ar / av) if np.isfinite(ar) and np.isfinite(av) and av > 0 else np.nan


def sortino_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute zero-target Sortino using annualized downside deviation."""

    ret = clean_returns(returns)
    if len(ret) < 2:
        return np.nan
    downside = ret[ret < 0.0]
    if len(downside) <= CANONICAL_VOL_DDOF:
        return np.nan
    downside_vol = float(downside.std(ddof=CANONICAL_VOL_DDOF) * np.sqrt(periods_per_year))
    ar = cagr(ret, periods_per_year)
    return float(ar / downside_vol) if np.isfinite(ar) and downside_vol > 0 else np.nan


def max_drawdown(returns: pd.Series) -> float:
    """Compute maximum drawdown from periodic returns."""

    ret = clean_returns(returns)
    if ret.empty:
        return np.nan
    wealth = (1.0 + ret).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calmar_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    """Compute CAGR divided by absolute max drawdown."""

    ar = cagr(returns, periods_per_year)
    dd = max_drawdown(returns)
    return float(ar / abs(dd)) if np.isfinite(ar) and np.isfinite(dd) and dd < 0 else np.nan


def var_cvar(returns: pd.Series, q: float = 0.05) -> tuple[float, float]:
    """Compute weekly VaR and CVaR at quantile ``q``."""

    ret = clean_returns(returns)
    if len(ret) < 20:
        return np.nan, np.nan
    var = float(ret.quantile(q))
    tail = ret[ret <= var]
    cvar = float(tail.mean()) if len(tail) else np.nan
    return var, cvar


def hit_rate(returns: pd.Series) -> float:
    """Share of non-missing periods with positive returns."""

    ret = clean_returns(returns)
    return float((ret > 0.0).mean()) if len(ret) else np.nan


def exposure_summary(weights: pd.DataFrame | None) -> dict[str, float]:
    """Compute production exposure summaries from ETF weights when available."""

    if weights is None or weights.empty:
        return {
            "avg_BIL": np.nan,
            "avg_cash": np.nan,
            "avg_SPY": np.nan,
            "avg_offense": np.nan,
            "avg_defense": np.nan,
            "avg_equity": np.nan,
            "max_single_etf_weight": np.nan,
        }
    w = weights.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    offense_cols = [c for c in w.columns if c in OFFENSE_ASSETS]
    defense_cols = [c for c in w.columns if c in DEFENSE_ASSETS]
    equity_cols = [c for c in w.columns if c in EQUITY_ASSETS]
    cash_cols = [c for c in w.columns if c in {"BIL", "cash", "CASH"}]
    return {
        "avg_BIL": float(w["BIL"].mean()) if "BIL" in w.columns else np.nan,
        "avg_cash": float(w[cash_cols].sum(axis=1).mean()) if cash_cols else np.nan,
        "avg_SPY": float(w["SPY"].mean()) if "SPY" in w.columns else np.nan,
        "avg_offense": float(w[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan,
        "avg_defense": float(w[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan,
        "avg_equity": float(w[equity_cols].sum(axis=1).mean()) if equity_cols else np.nan,
        "max_single_etf_weight": float(w.max(axis=1).max()),
    }


def metrics_from_series(
    returns: pd.Series,
    turnover: pd.Series | None = None,
    cost: pd.Series | None = None,
    weights: pd.DataFrame | None = None,
    *,
    periods_per_year: int = WEEKS_PER_YEAR,
) -> dict[str, float]:
    """Compute canonical production metrics from a return series."""

    ret = clean_returns(returns)
    var_5, cvar_5 = var_cvar(ret)
    metrics = {
        "ann_return": cagr(ret, periods_per_year),
        "cagr": cagr(ret, periods_per_year),
        "arithmetic_ann_return": arithmetic_annual_return(ret, periods_per_year),
        "ann_vol": annualized_volatility(ret, periods_per_year),
        "sharpe": sharpe_ratio(ret, periods_per_year),
        "arithmetic_sharpe": arithmetic_sharpe_ratio(ret, periods_per_year),
        "sortino": sortino_ratio(ret, periods_per_year),
        "max_drawdown": max_drawdown(ret),
        "calmar": calmar_ratio(ret, periods_per_year),
        "var_5": var_5,
        "cvar_5": cvar_5,
        "hit_rate": hit_rate(ret),
        "n_weeks": int(len(ret)),
    }
    if turnover is not None or cost is not None:
        path = pd.DataFrame(
            {
                "turnover": pd.Series(turnover, dtype=float) if turnover is not None else pd.Series(dtype=float),
                "cost": pd.Series(cost, dtype=float) if cost is not None else pd.Series(dtype=float),
            }
        )
        metrics.update(summarize_costs(path, periods_per_year))
        metrics["avg_turnover"] = metrics["avg_weekly_turnover"]
        metrics["cost_drag"] = metrics["total_cost"]
    else:
        metrics.update(
            {
                "avg_weekly_turnover": np.nan,
                "annualized_turnover": np.nan,
                "total_cost": np.nan,
                "avg_weekly_cost": np.nan,
                "annualized_cost": np.nan,
                "avg_turnover": np.nan,
                "cost_drag": np.nan,
            }
        )
    metrics.update(exposure_summary(weights))
    return metrics


def metrics_from_path(
    path: pd.DataFrame,
    *,
    weights: pd.DataFrame | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
) -> dict[str, float]:
    """Compute canonical metrics from a saved production path DataFrame."""

    df = path.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
        df = df.dropna(subset=["Date"]).sort_values("Date")
        if start is not None:
            df = df[df["Date"] >= pd.Timestamp(start)]
        if end is not None:
            df = df[df["Date"] <= pd.Timestamp(end)]
    return metrics_from_series(
        df.get("net_return", pd.Series(dtype=float)),
        df.get("turnover"),
        df.get("cost"),
        weights,
    )


def holdout_metrics_from_path(
    path: pd.DataFrame,
    *,
    weights: pd.DataFrame | None = None,
    holdout_start: pd.Timestamp = OFFICIAL_HOLDOUT_START,
) -> dict[str, float]:
    """Compute canonical metrics from the official holdout window."""

    return metrics_from_path(path, weights=weights, start=holdout_start)


def rolling_origin_metrics(
    returns: pd.Series,
    *,
    test_window: int = 104,
    step: int = 52,
    min_train: int = 260,
) -> pd.DataFrame:
    """Compute simple rolling-origin test-window metrics when enough data exists."""

    ret = clean_returns(returns).sort_index()
    rows: list[dict[str, float | int | str]] = []
    if len(ret) < min_train + test_window:
        return pd.DataFrame(rows)
    start = min_train
    fold = 0
    while start + test_window <= len(ret):
        fold += 1
        test = ret.iloc[start : start + test_window]
        row = metrics_from_series(test)
        row.update(
            {
                "fold": fold,
                "test_start": str(test.index.min().date()) if hasattr(test.index.min(), "date") else str(test.index.min()),
                "test_end": str(test.index.max().date()) if hasattr(test.index.max(), "date") else str(test.index.max()),
            }
        )
        rows.append(row)
        start += step
    return pd.DataFrame(rows)


def prefixed_metrics(prefix: str, metrics: dict[str, float]) -> dict[str, float]:
    """Return metrics with a prefix for comparison tables."""

    return {f"{prefix}_{key}": value for key, value in metrics.items()}
