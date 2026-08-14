"""Deterministic Monte Carlo risk tools for weekly portfolio returns."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence


def quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0.0 <= probability <= 1.0:
        raise ValueError("nonempty values and probability in [0, 1] required")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def path_statistics(returns: Sequence[float], *, recovery_start: int | None = None) -> dict[str, float | bool]:
    if not returns or any(float(value) <= -1.0 for value in returns):
        raise ValueError("valid nonempty simple-return path required")
    wealth = peak = 1.0
    maximum_drawdown = 0.0
    recovered = False
    for index, value in enumerate(returns):
        wealth *= 1.0 + float(value)
        peak = max(peak, wealth)
        maximum_drawdown = min(maximum_drawdown, wealth / peak - 1.0)
        if recovery_start is not None and index >= recovery_start and wealth >= 1.0:
            recovered = True
    return {
        "terminal_return": wealth - 1.0,
        "annual_return": wealth ** (52.0 / len(returns)) - 1.0,
        "max_drawdown": maximum_drawdown,
        "recovered_initial_wealth": recovered,
    }


def worst_compounded_block(values: Sequence[float], block_weeks: int) -> tuple[int, list[float], float]:
    observations = [float(value) for value in values]
    if block_weeks < 1 or len(observations) < block_weeks:
        raise ValueError("block must fit observations")
    candidates = []
    for start in range(len(observations) - block_weeks + 1):
        block = observations[start : start + block_weeks]
        compounded = math.prod(1.0 + value for value in block) - 1.0
        candidates.append((compounded, start, block))
    compounded, start, block = min(candidates)
    return start, block, compounded


def _sample_blocks(generator: random.Random, values: list[float], weeks: int, block_weeks: int) -> list[float]:
    result: list[float] = []
    while len(result) < weeks:
        start = generator.randrange(len(values))
        result.extend(values[(start + offset) % len(values)] for offset in range(block_weeks))
    return result[:weeks]


def simulate_paths(
    values: Sequence[float], *, weeks: int, paths: int, method: str, seed: int,
    block_weeks: int = 13, mean_haircut_fraction: float = 0.5,
    forced_initial_block: Sequence[float] | None = None,
) -> list[dict[str, float | bool]]:
    observations = [float(value) for value in values]
    if len(observations) < 2 or weeks < 1 or paths < 1 or any(value <= -1.0 for value in observations):
        raise ValueError("invalid simulation inputs")
    if method not in {"source_gaussian_gbm", "iid_empirical", "moving_block_13w", "moving_block_13w_mean_haircut", "forced_worst_13w_then_blocks"}:
        raise ValueError("unknown simulation method")
    if forced_initial_block is not None and any(float(value) <= -1.0 for value in forced_initial_block):
        raise ValueError("invalid forced block")
    generator = random.Random(seed)
    log_returns = [math.log1p(value) for value in observations]
    log_mean, log_variance = statistics.fmean(log_returns), statistics.variance(log_returns)
    gaussian_drift, log_std = log_mean - log_variance / 2.0, math.sqrt(log_variance)
    haircut = max(statistics.fmean(observations), 0.0) * mean_haircut_fraction
    summaries = []
    for _ in range(paths):
        recovery_start = None
        if method == "source_gaussian_gbm":
            sampled = [math.expm1(gaussian_drift + log_std * generator.gauss(0.0, 1.0)) for _ in range(weeks)]
        elif method == "iid_empirical":
            sampled = [observations[generator.randrange(len(observations))] for _ in range(weeks)]
        else:
            sampled = _sample_blocks(generator, observations, weeks, block_weeks)
            if method == "moving_block_13w_mean_haircut":
                sampled = [max(-0.999999, value - haircut) for value in sampled]
            elif method == "forced_worst_13w_then_blocks":
                forced = [float(value) for value in forced_initial_block or []]
                if not forced:
                    raise ValueError("forced crash method requires initial block")
                sampled = (forced + sampled)[:weeks]
                recovery_start = len(forced) - 1
        summaries.append(path_statistics(sampled, recovery_start=recovery_start))
    return summaries


def summarize_simulations(rows: Sequence[dict[str, float | bool]]) -> dict[str, float | int]:
    if not rows:
        raise ValueError("simulation rows required")
    terminal = [float(row["terminal_return"]) for row in rows]
    drawdowns = [float(row["max_drawdown"]) for row in rows]
    annual = [float(row["annual_return"]) for row in rows]
    tail_cutoff = quantile(terminal, 0.05)
    return {
        "paths": len(rows),
        "terminal_return_p01": quantile(terminal, 0.01),
        "terminal_return_p05": tail_cutoff,
        "terminal_return_p50": quantile(terminal, 0.50),
        "terminal_return_p95": quantile(terminal, 0.95),
        "terminal_return_p99": quantile(terminal, 0.99),
        "terminal_return_expected_shortfall_5pct": statistics.fmean(value for value in terminal if value <= tail_cutoff),
        "annual_return_p05": quantile(annual, 0.05),
        "annual_return_p50": quantile(annual, 0.50),
        "max_drawdown_p01": quantile(drawdowns, 0.01),
        "max_drawdown_p05": quantile(drawdowns, 0.05),
        "max_drawdown_p50": quantile(drawdowns, 0.50),
        "probability_terminal_loss": sum(value < 0.0 for value in terminal) / len(rows),
        "probability_terminal_loss_20pct": sum(value <= -0.20 for value in terminal) / len(rows),
        "probability_terminal_loss_50pct": sum(value <= -0.50 for value in terminal) / len(rows),
        "probability_drawdown_20pct": sum(value <= -0.20 for value in drawdowns) / len(rows),
        "probability_drawdown_30pct": sum(value <= -0.30 for value in drawdowns) / len(rows),
        "probability_drawdown_40pct": sum(value <= -0.40 for value in drawdowns) / len(rows),
        "probability_drawdown_50pct": sum(value <= -0.50 for value in drawdowns) / len(rows),
        "probability_recover_initial_wealth": sum(bool(row["recovered_initial_wealth"]) for row in rows) / len(rows),
    }


def source_best_fit_direction(
    training_returns: Sequence[float], test_returns: Sequence[float], *, simulations: int, seed: int,
) -> dict[str, float | int | bool]:
    training = [float(value) for value in training_returns]
    test = [float(value) for value in test_returns]
    if len(training) < 2 or not test or simulations < 1:
        raise ValueError("training, test, and simulations required")
    logs = [math.log1p(value) for value in training]
    variance = statistics.variance(logs)
    drift, volatility = statistics.fmean(logs) - variance / 2.0, math.sqrt(variance)
    actual = [1.0]
    for value in training:
        actual.append(actual[-1] * (1.0 + value))
    generator = random.Random(seed)
    best_error = math.inf
    best_path: list[float] = []
    for _ in range(simulations):
        path = [1.0]
        for _ in range(len(training) + len(test)):
            path.append(path[-1] * math.exp(drift + volatility * generator.gauss(0.0, 1.0)))
        error = math.sqrt(statistics.fmean((path[index] - actual[index]) ** 2 for index in range(len(actual))))
        if error < best_error:
            best_error, best_path = error, path
    predicted = best_path[-1] / best_path[len(training)] - 1.0
    realized = math.prod(1.0 + value for value in test) - 1.0
    return {
        "simulations": simulations, "training_weeks": len(training), "forecast_weeks": len(test),
        "training_fit_rmse": best_error, "predicted_return": predicted, "realized_return": realized,
        "direction_correct": (predicted >= 0.0) == (realized >= 0.0),
    }


def wilson_lower(successes: int, observations: int, z: float = 1.959963984540054) -> float:
    if observations < 1 or not 0 <= successes <= observations:
        raise ValueError("valid binomial counts required")
    proportion = successes / observations
    denominator = 1.0 + z * z / observations
    center = proportion + z * z / (2.0 * observations)
    margin = z * math.sqrt(proportion * (1.0 - proportion) / observations + z * z / (4.0 * observations * observations))
    return (center - margin) / denominator
