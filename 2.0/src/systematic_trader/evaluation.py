"""Platform-owned performance metrics for bias-aware strategy evaluation."""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import asdict, dataclass
from typing import Sequence


PERIODS_PER_YEAR = 52


@dataclass(frozen=True)
class PerformanceMetrics:
    observations: int
    years: float
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_zero_rf: float
    sortino_zero_target: float
    max_drawdown: float
    max_drawdown_duration_weeks: int
    calmar: float
    cvar_5_weekly: float
    positive_week_share: float
    worst_week: float
    best_week: float

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


def _finite_returns(returns: Sequence[float]) -> list[float]:
    values = [float(value) for value in returns]
    if not values:
        raise ValueError("at least one return is required")
    if any(not math.isfinite(value) or value <= -1.0 for value in values):
        raise ValueError("returns must be finite and greater than -100%")
    return values


def wealth_path(returns: Sequence[float]) -> list[float]:
    values = _finite_returns(returns)
    wealth = 1.0
    result: list[float] = []
    for value in values:
        wealth *= 1.0 + value
        result.append(wealth)
    return result


def drawdown_statistics(returns: Sequence[float]) -> tuple[float, int]:
    path = wealth_path(returns)
    peak = path[0]
    maximum = 0.0
    duration = 0
    maximum_duration = 0
    for wealth in path:
        peak = max(peak, wealth)
        drawdown = wealth / peak - 1.0
        maximum = min(maximum, drawdown)
        if drawdown < 0.0:
            duration += 1
            maximum_duration = max(maximum_duration, duration)
        else:
            duration = 0
    return maximum, maximum_duration


def performance_metrics(returns: Sequence[float], periods_per_year: int = PERIODS_PER_YEAR) -> PerformanceMetrics:
    values = _finite_returns(returns)
    observations = len(values)
    years = observations / periods_per_year
    path = wealth_path(values)
    total_return = path[-1] - 1.0
    annual_return = path[-1] ** (periods_per_year / observations) - 1.0
    mean = statistics.fmean(values)
    volatility = statistics.stdev(values) if observations > 1 else 0.0
    annual_volatility = volatility * math.sqrt(periods_per_year)
    sharpe = mean / volatility * math.sqrt(periods_per_year) if volatility > 0.0 else 0.0
    downside = [min(value, 0.0) for value in values]
    downside_deviation = math.sqrt(statistics.fmean(value * value for value in downside))
    sortino = mean / downside_deviation * math.sqrt(periods_per_year) if downside_deviation > 0.0 else 0.0
    maximum_drawdown, drawdown_duration = drawdown_statistics(values)
    calmar = annual_return / abs(maximum_drawdown) if maximum_drawdown < 0.0 else 0.0
    tail_count = max(1, math.ceil(observations * 0.05))
    cvar = statistics.fmean(sorted(values)[:tail_count])
    return PerformanceMetrics(
        observations=observations,
        years=years,
        total_return=total_return,
        annual_return=annual_return,
        annual_volatility=annual_volatility,
        sharpe_zero_rf=sharpe,
        sortino_zero_target=sortino,
        max_drawdown=maximum_drawdown,
        max_drawdown_duration_weeks=drawdown_duration,
        calmar=calmar,
        cvar_5_weekly=cvar,
        positive_week_share=sum(value > 0.0 for value in values) / observations,
        worst_week=min(values),
        best_week=max(values),
    )


def benchmark_regression(returns: Sequence[float], benchmark: Sequence[float]) -> dict[str, float]:
    values = _finite_returns(returns)
    reference = _finite_returns(benchmark)
    if len(values) != len(reference):
        raise ValueError("strategy and benchmark must have equal observations")
    mean_strategy = statistics.fmean(values)
    mean_benchmark = statistics.fmean(reference)
    variance = sum((value - mean_benchmark) ** 2 for value in reference) / len(reference)
    covariance = sum(
        (strategy - mean_strategy) * (market - mean_benchmark)
        for strategy, market in zip(values, reference)
    ) / len(values)
    beta = covariance / variance if variance > 0.0 else 0.0
    alpha = (mean_strategy - beta * mean_benchmark) * PERIODS_PER_YEAR
    active = [strategy - market for strategy, market in zip(values, reference)]
    tracking_error = statistics.stdev(active) * math.sqrt(PERIODS_PER_YEAR) if len(active) > 1 else 0.0
    information_ratio = (
        statistics.fmean(active) / statistics.stdev(active) * math.sqrt(PERIODS_PER_YEAR)
        if len(active) > 1 and statistics.stdev(active) > 0.0
        else 0.0
    )
    return {
        "beta_to_spy": beta,
        "annual_alpha_zero_rf": alpha,
        "annual_tracking_error": tracking_error,
        "information_ratio": information_ratio,
    }


def rolling_window_summary(
    returns: Sequence[float], benchmark: Sequence[float], window: int = 156
) -> dict[str, float | int]:
    values = _finite_returns(returns)
    reference = _finite_returns(benchmark)
    if len(values) != len(reference):
        raise ValueError("strategy and benchmark must have equal observations")
    if len(values) < window:
        return {"rolling_windows": 0, "worst_3y_sharpe": 0.0, "positive_3y_sharpe_share": 0.0, "spy_win_3y_share": 0.0}
    sharpes: list[float] = []
    wins = 0
    for end in range(window, len(values) + 1):
        strategy_window = values[end - window : end]
        benchmark_window = reference[end - window : end]
        metric = performance_metrics(strategy_window)
        sharpes.append(metric.sharpe_zero_rf)
        strategy_wealth = wealth_path(strategy_window)[-1]
        benchmark_wealth = wealth_path(benchmark_window)[-1]
        wins += strategy_wealth > benchmark_wealth
    return {
        "rolling_windows": len(sharpes),
        "worst_3y_sharpe": min(sharpes),
        "positive_3y_sharpe_share": sum(value > 0.0 for value in sharpes) / len(sharpes),
        "spy_win_3y_share": wins / len(sharpes),
    }


def block_bootstrap_intervals(
    returns: Sequence[float], *, seed: int, samples: int = 500, block_size: int = 13
) -> dict[str, float | int]:
    values = _finite_returns(returns)
    generator = random.Random(seed)
    annual_returns: list[float] = []
    sharpes: list[float] = []
    for _ in range(samples):
        sample: list[float] = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            block = [values[(start + offset) % len(values)] for offset in range(block_size)]
            sample.extend(block)
        metric = performance_metrics(sample[: len(values)])
        annual_returns.append(metric.annual_return)
        sharpes.append(metric.sharpe_zero_rf)

    def percentile(items: list[float], probability: float) -> float:
        ordered = sorted(items)
        position = probability * (len(ordered) - 1)
        lower = math.floor(position)
        upper = math.ceil(position)
        if lower == upper:
            return ordered[lower]
        weight = position - lower
        return ordered[lower] * (1.0 - weight) + ordered[upper] * weight

    return {
        "bootstrap_samples": samples,
        "bootstrap_block_weeks": block_size,
        "annual_return_ci_low": percentile(annual_returns, 0.025),
        "annual_return_ci_high": percentile(annual_returns, 0.975),
        "sharpe_ci_low": percentile(sharpes, 0.025),
        "sharpe_ci_high": percentile(sharpes, 0.975),
    }
