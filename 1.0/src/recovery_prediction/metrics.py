"""Metrics for standalone recovery prediction research."""

from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS_PER_YEAR = 52


def clean(s: pd.Series) -> pd.Series:
    return pd.to_numeric(pd.Series(s), errors="coerce").dropna()


def cagr(returns: pd.Series) -> float:
    r = clean(returns)
    if len(r) < 2:
        return np.nan
    growth = float((1.0 + r).prod())
    years = len(r) / WEEKS_PER_YEAR
    return growth ** (1.0 / years) - 1.0 if years > 0 and growth > 0 else np.nan


def ann_return(returns: pd.Series) -> float:
    r = clean(returns)
    return float(r.mean() * WEEKS_PER_YEAR) if len(r) else np.nan


def ann_vol(returns: pd.Series) -> float:
    r = clean(returns)
    return float(r.std(ddof=1) * np.sqrt(WEEKS_PER_YEAR)) if len(r) > 1 else np.nan


def sharpe(returns: pd.Series) -> float:
    cg, vol = cagr(returns), ann_vol(returns)
    return float(cg / vol) if np.isfinite(cg) and np.isfinite(vol) and vol > 0 else np.nan


def sortino(returns: pd.Series) -> float:
    r = clean(returns)
    down = r[r < 0]
    if len(down) <= 1:
        return np.nan
    dvol = float(down.std(ddof=1) * np.sqrt(WEEKS_PER_YEAR))
    cg = cagr(r)
    return float(cg / dvol) if np.isfinite(cg) and dvol > 0 else np.nan


def max_drawdown(returns: pd.Series) -> float:
    r = clean(returns)
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calmar(returns: pd.Series) -> float:
    cg, dd = cagr(returns), max_drawdown(returns)
    return float(cg / abs(dd)) if np.isfinite(cg) and np.isfinite(dd) and dd < 0 else np.nan


def cvar(returns: pd.Series, q: float = 0.05) -> float:
    r = clean(returns)
    if len(r) < 20:
        return np.nan
    var = float(r.quantile(q))
    tail = r[r <= var]
    return float(tail.mean()) if len(tail) else np.nan


def capture(strategy: pd.Series, baseline: pd.Series, upside: bool) -> float:
    s, b = clean(strategy), clean(baseline)
    idx = s.index.intersection(b.index)
    s, b = s.reindex(idx), b.reindex(idx)
    mask = b > 0 if upside else b < 0
    if mask.sum() < 5 or b[mask].mean() == 0:
        return np.nan
    return float(s[mask].mean() / b[mask].mean())


def summarize(returns: pd.Series, baseline: pd.Series | None = None) -> dict[str, float]:
    out = {
        "cagr": cagr(returns),
        "ann_return": ann_return(returns),
        "ann_vol": ann_vol(returns),
        "sharpe": sharpe(returns),
        "sortino": sortino(returns),
        "max_drawdown": max_drawdown(returns),
        "calmar": calmar(returns),
        "cvar_5": cvar(returns, 0.05),
        "cvar_1": cvar(returns, 0.01),
        "n_weeks": int(len(clean(returns))),
    }
    if baseline is not None:
        out["upside_capture"] = capture(returns, baseline, True)
        out["downside_capture"] = capture(returns, baseline, False)
    return out


def hit_rate(x: pd.Series) -> float:
    r = clean(x)
    return float((r > 0).mean()) if len(r) else np.nan


def rank_ic(signal: pd.Series, target: pd.Series) -> float:
    df = pd.DataFrame({"signal": signal, "target": target}).dropna()
    if len(df) < 20 or df["signal"].nunique() < 3 or df["target"].nunique() < 3:
        return np.nan
    return float(df["signal"].rank().corr(df["target"].rank()))

