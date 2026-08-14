"""Statistical validation helpers for research-only portfolio experiments.

The functions here are deliberately conservative. They are designed to make
frontier research harder to fool with lucky backtests, repeated trials, leakage,
or overlapping labels. DSR/PBO implementations are approximations unless a full
experiment log and CPCV design are supplied.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


WEEKS_PER_YEAR = 52
EULER_GAMMA = 0.5772156649015329


def normal_cdf(x: float) -> float:
    """Standard normal CDF without requiring scipy."""

    if not np.isfinite(x):
        return float("nan")
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def inverse_normal_cdf(p: float) -> float:
    """Acklam inverse normal approximation."""

    if p <= 0.0:
        return -np.inf
    if p >= 1.0:
        return np.inf
    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02, 1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02, 6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00, -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00, 3.754408661907416e00]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)


def clean_returns(returns: pd.Series) -> pd.Series:
    return pd.to_numeric(pd.Series(returns), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()


def annualized_return(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    ret = clean_returns(returns)
    if ret.empty:
        return float("nan")
    growth = float((1.0 + ret).prod())
    years = len(ret) / periods_per_year
    return growth ** (1.0 / years) - 1.0 if growth > 0 and years > 0 else float("nan")


def annualized_vol(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    ret = clean_returns(returns)
    return float(ret.std(ddof=0) * math.sqrt(periods_per_year)) if len(ret) > 1 else float("nan")


def sharpe_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    ann_ret = annualized_return(returns, periods_per_year)
    ann_vol = annualized_vol(returns, periods_per_year)
    return float(ann_ret / ann_vol) if np.isfinite(ann_ret) and ann_vol > 0 else float("nan")


def max_drawdown(returns: pd.Series) -> float:
    ret = clean_returns(returns)
    if ret.empty:
        return float("nan")
    wealth = (1.0 + ret).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar_5(returns: pd.Series) -> float:
    ret = clean_returns(returns)
    if len(ret) < 20:
        return float("nan")
    return float(ret[ret <= ret.quantile(0.05)].mean())


def calmar_ratio(returns: pd.Series, periods_per_year: int = WEEKS_PER_YEAR) -> float:
    ann_ret = annualized_return(returns, periods_per_year)
    mdd = max_drawdown(returns)
    return float(ann_ret / abs(mdd)) if np.isfinite(ann_ret) and mdd < 0 else float("nan")


def skewness(returns: pd.Series) -> float:
    ret = clean_returns(returns)
    return float(ret.skew()) if len(ret) >= 3 else float("nan")


def pearson_kurtosis(returns: pd.Series) -> float:
    ret = clean_returns(returns)
    return float(ret.kurtosis() + 3.0) if len(ret) >= 4 else float("nan")


def sharpe_variance_weekly(weekly_returns: pd.Series) -> float:
    """Approximate non-normal Sharpe variance term from Bailey/Lopez de Prado."""

    ret = clean_returns(weekly_returns)
    n = len(ret)
    if n < 5:
        return float("nan")
    sr = ret.mean() / ret.std(ddof=0) if ret.std(ddof=0) > 0 else float("nan")
    skew = skewness(ret)
    kurt = pearson_kurtosis(ret)
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    return float(max(denom, 1e-12) / (n - 1.0))


def probabilistic_sharpe_ratio(
    returns: pd.Series,
    benchmark_sharpe_annual: float = 0.0,
    periods_per_year: int = WEEKS_PER_YEAR,
) -> float:
    """Probability observed Sharpe exceeds a benchmark Sharpe.

    Uses the Bailey/Lopez de Prado PSR form with skew/kurtosis adjustment.
    The calculation is performed in weekly Sharpe units and the benchmark is
    converted from annualized Sharpe to weekly Sharpe.
    """

    ret = clean_returns(returns)
    n = len(ret)
    if n < 5 or ret.std(ddof=0) <= 0:
        return float("nan")
    sr = float(ret.mean() / ret.std(ddof=0))
    sr_benchmark = benchmark_sharpe_annual / math.sqrt(periods_per_year)
    var_sr = sharpe_variance_weekly(ret)
    if not np.isfinite(var_sr) or var_sr <= 0:
        return float("nan")
    z = (sr - sr_benchmark) / math.sqrt(var_sr)
    return float(normal_cdf(z))


def expected_max_sharpe_threshold(trial_count: int, returns: pd.Series) -> float:
    """Approximate selection-bias Sharpe threshold in annualized units."""

    ret = clean_returns(returns)
    if len(ret) < 5:
        return float("nan")
    n_trials = max(int(trial_count), 1)
    var_sr = sharpe_variance_weekly(ret)
    if not np.isfinite(var_sr):
        return float("nan")
    if n_trials <= 1:
        return 0.0
    z1 = inverse_normal_cdf(1.0 - 1.0 / n_trials)
    z2 = inverse_normal_cdf(1.0 - 1.0 / (n_trials * math.e))
    threshold_weekly = math.sqrt(var_sr) * ((1.0 - EULER_GAMMA) * z1 + EULER_GAMMA * z2)
    return float(threshold_weekly * math.sqrt(WEEKS_PER_YEAR))


def deflated_sharpe_ratio_proxy(
    returns: pd.Series,
    trial_count: int = 1,
    periods_per_year: int = WEEKS_PER_YEAR,
) -> float:
    """Approximate Deflated Sharpe Ratio probability.

    This proxy uses a non-normal Sharpe variance adjustment and an expected
    maximum Sharpe threshold based on the number of tested variants. It is not a
    full DSR unless the true number and dependence structure of all trials are
    known.
    """

    threshold = expected_max_sharpe_threshold(trial_count, returns)
    if not np.isfinite(threshold):
        return float("nan")
    return probabilistic_sharpe_ratio(returns, threshold, periods_per_year)


def multiple_testing_adjusted_support(psr: float, trial_count: int) -> float:
    """Bonferroni-style support adjustment from PSR."""

    if not np.isfinite(psr):
        return float("nan")
    p_value = max(0.0, 1.0 - psr)
    adjusted_p = min(1.0, p_value * max(int(trial_count), 1))
    return float(1.0 - adjusted_p)


def purged_embargoed_cv_splits(
    date_index: Sequence[pd.Timestamp],
    n_splits: int = 5,
    label_horizon_weeks: int = 4,
    embargo_weeks: int = 2,
) -> Iterator[Tuple[pd.Series, pd.Series]]:
    """Yield train/test masks with purging and embargo for overlapping labels."""

    idx = pd.Index(pd.to_datetime(date_index)).sort_values()
    n = len(idx)
    if n_splits < 2 or n < n_splits:
        raise ValueError("Need at least two splits and enough dates.")
    fold_sizes = np.full(n_splits, n // n_splits, dtype=int)
    fold_sizes[: n % n_splits] += 1
    start = 0
    for fold_size in fold_sizes:
        stop = start + int(fold_size)
        test_positions = np.arange(start, stop)
        train_mask = pd.Series(True, index=idx)
        test_mask = pd.Series(False, index=idx)
        test_mask.iloc[test_positions] = True
        train_mask.iloc[test_positions] = False
        purge_start = max(0, start - label_horizon_weeks + 1)
        train_mask.iloc[purge_start:start] = False
        embargo_stop = min(n, stop + embargo_weeks)
        train_mask.iloc[stop:embargo_stop] = False
        yield train_mask, test_mask
        start = stop


def rolling_origin_splits(
    date_index: Sequence[pd.Timestamp],
    min_train_weeks: int = 260,
    test_weeks: int = 52,
    step_weeks: int = 26,
) -> Iterator[Tuple[pd.Series, pd.Series]]:
    """Yield rolling-origin train/test masks."""

    idx = pd.Index(pd.to_datetime(date_index)).sort_values()
    n = len(idx)
    start = int(min_train_weeks)
    while start + test_weeks <= n:
        train_mask = pd.Series(False, index=idx)
        test_mask = pd.Series(False, index=idx)
        train_mask.iloc[:start] = True
        test_mask.iloc[start : start + test_weeks] = True
        yield train_mask, test_mask
        start += int(step_weeks)


def pbo_proxy(candidate_returns: Dict[str, pd.Series], n_splits: int = 6) -> Dict[str, float]:
    """Lightweight Probability of Backtest Overfitting proxy.

    For each subperiod, choose the top in-sample strategy and check whether its
    out-of-sample Sharpe falls below the median OOS Sharpe. This is not CPCV,
    but it captures the core "winner in-sample disappoints OOS" failure mode.
    """

    if len(candidate_returns) < 3:
        return {"pbo_proxy": float("nan"), "folds": 0.0, "candidate_count": float(len(candidate_returns))}
    frame = pd.DataFrame({k: clean_returns(v) for k, v in candidate_returns.items()}).dropna(how="all")
    frame = frame.fillna(0.0)
    frame = frame.sort_index()
    if frame.index.has_duplicates:
        frame = frame.groupby(level=0).mean()
    if len(frame) < n_splits * 20:
        return {"pbo_proxy": float("nan"), "folds": 0.0, "candidate_count": float(len(candidate_returns))}
    failures = 0
    folds = 0
    for train_mask, test_mask in purged_embargoed_cv_splits(frame.index, n_splits=n_splits, label_horizon_weeks=1, embargo_weeks=0):
        is_perf = frame.iloc[train_mask.to_numpy()].apply(sharpe_ratio)
        oos_perf = frame.iloc[test_mask.to_numpy()].apply(sharpe_ratio)
        if is_perf.dropna().empty or oos_perf.dropna().empty:
            continue
        top = str(is_perf.idxmax())
        median_oos = float(oos_perf.median())
        if float(oos_perf.get(top, np.nan)) < median_oos:
            failures += 1
        folds += 1
    return {
        "pbo_proxy": float(failures / folds) if folds else float("nan"),
        "folds": float(folds),
        "candidate_count": float(len(candidate_returns)),
    }


def drawdown_pain_score(returns: pd.Series) -> float:
    """Simple pain-to-payoff score: annual return divided by average drawdown."""

    ret = clean_returns(returns)
    if ret.empty:
        return float("nan")
    wealth = (1.0 + ret).cumprod()
    drawdown = (wealth / wealth.cummax() - 1.0).abs()
    avg_dd = float(drawdown.mean())
    ann_ret = annualized_return(ret)
    return float(ann_ret / avg_dd) if avg_dd > 0 and np.isfinite(ann_ret) else float("nan")


def strategy_validation_summary(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    turnover: Optional[pd.Series] = None,
    trial_count: int = 1,
) -> Dict[str, float]:
    """Compute a standardized validation summary for one strategy."""

    ret = clean_returns(returns)
    benchmark_sharpe = sharpe_ratio(benchmark_returns) if benchmark_returns is not None and len(clean_returns(benchmark_returns)) else 0.0
    psr = probabilistic_sharpe_ratio(ret, benchmark_sharpe)
    dsr = deflated_sharpe_ratio_proxy(ret, trial_count=trial_count)
    row = {
        "annual_return": annualized_return(ret),
        "annual_vol": annualized_vol(ret),
        "sharpe": sharpe_ratio(ret),
        "max_drawdown": max_drawdown(ret),
        "calmar": calmar_ratio(ret),
        "cvar_5": cvar_5(ret),
        "skew": skewness(ret),
        "kurtosis": pearson_kurtosis(ret),
        "psr": psr,
        "dsr_proxy": dsr,
        "multiple_testing_adjusted_support": multiple_testing_adjusted_support(psr, trial_count),
        "drawdown_pain_score": drawdown_pain_score(ret),
        "n_observations": float(len(ret)),
        "trial_count_used": float(max(int(trial_count), 1)),
    }
    if turnover is not None:
        t = pd.to_numeric(pd.Series(turnover), errors="coerce").dropna()
        row["avg_turnover"] = float(t.mean()) if len(t) else float("nan")
        row["turnover_warning"] = float(t.mean() > 0.15) if len(t) else float("nan")
    else:
        row["avg_turnover"] = float("nan")
        row["turnover_warning"] = float("nan")
    return row


def validation_verdict(row: pd.Series) -> str:
    """Classify statistical support conservatively."""

    n = float(row.get("n_observations", 0.0))
    psr = float(row.get("psr", np.nan))
    dsr = float(row.get("dsr_proxy", np.nan))
    pbo = float(row.get("pbo_proxy", np.nan))
    sharpe = float(row.get("sharpe", np.nan))
    if n < 156 or not np.isfinite(sharpe):
        return "insufficient_data"
    if np.isfinite(pbo) and pbo >= 0.50:
        return "overfit_risk"
    if np.isfinite(dsr) and dsr >= 0.95 and np.isfinite(psr) and psr >= 0.95:
        return "statistically_supported"
    if (np.isfinite(dsr) and dsr >= 0.80) or (np.isfinite(psr) and psr >= 0.90):
        return "promising_but_underpowered"
    if sharpe > 0:
        return "diagnostic_only"
    return "overfit_risk"


def sanity_check_cv() -> Dict[str, float]:
    """Minimal sanity checks for purged/embargoed CV masks."""

    idx = pd.date_range("2020-01-03", periods=120, freq="W-FRI")
    rows: List[Dict[str, float]] = []
    for train_mask, test_mask in purged_embargoed_cv_splits(idx, n_splits=4, label_horizon_weeks=4, embargo_weeks=2):
        rows.append(
            {
                "train_count": float(train_mask.sum()),
                "test_count": float(test_mask.sum()),
                "overlap": float((train_mask & test_mask).sum()),
            }
        )
    return {
        "folds": float(len(rows)),
        "max_train_test_overlap": float(max(r["overlap"] for r in rows)),
        "min_test_count": float(min(r["test_count"] for r in rows)),
    }


@dataclass
class ReturnFile:
    candidate: str
    source_file: str
    returns: pd.Series
    turnover: Optional[pd.Series] = None
