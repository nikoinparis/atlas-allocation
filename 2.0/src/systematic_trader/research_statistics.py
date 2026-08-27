"""Trial-aware statistics for systematic-research promotion gates.

These helpers are deterministic and dependency-free.  They are designed to
make data snooping visible; none of them converts retrospective evidence into
an untouched forward result.
"""

from __future__ import annotations

import itertools
import math
import random
import statistics
from collections.abc import Sequence
from statistics import NormalDist


def information_coefficient_ratio(
    values: Sequence[float], *, periods_per_year: int | None = None
) -> dict[str, float | int | None]:
    sample = [float(value) for value in values]
    if not sample or any(not math.isfinite(value) for value in sample):
        raise ValueError("finite IC observations are required")
    mean = statistics.fmean(sample)
    deviation = statistics.stdev(sample) if len(sample) > 1 else 0.0
    raw = mean / deviation if deviation > 0.0 else 0.0
    annualized = raw * math.sqrt(periods_per_year) if periods_per_year else None
    return {
        "observations": len(sample),
        "mean_ic": mean,
        "ic_std": deviation,
        "icir": raw,
        "annualized_icir": annualized,
        "periods_per_year": periods_per_year,
        "positive_rate": sum(value > 0.0 for value in sample) / len(sample),
    }


def sample_skewness(values: Sequence[float]) -> float:
    sample = [float(value) for value in values]
    if len(sample) < 3:
        return 0.0
    mean = statistics.fmean(sample)
    std = statistics.stdev(sample)
    if std == 0.0:
        return 0.0
    count = len(sample)
    return count / ((count - 1) * (count - 2)) * sum(((value - mean) / std) ** 3 for value in sample)


def sample_kurtosis(values: Sequence[float]) -> float:
    """Return bias-adjusted Pearson kurtosis (normal == 3)."""
    sample = [float(value) for value in values]
    if len(sample) < 4:
        return 3.0
    mean = statistics.fmean(sample)
    std = statistics.stdev(sample)
    if std == 0.0:
        return 3.0
    count = len(sample)
    fourth = sum(((value - mean) / std) ** 4 for value in sample)
    excess = (
        count * (count + 1) / ((count - 1) * (count - 2) * (count - 3)) * fourth
        - 3 * (count - 1) ** 2 / ((count - 2) * (count - 3))
    )
    return excess + 3.0


def annualized_sharpe(values: Sequence[float], *, periods_per_year: int = 52) -> float:
    sample = [float(value) for value in values]
    if len(sample) < 2:
        return 0.0
    deviation = statistics.stdev(sample)
    return statistics.fmean(sample) / deviation * math.sqrt(periods_per_year) if deviation > 0.0 else 0.0


def probabilistic_sharpe_ratio(
    values: Sequence[float], *, benchmark_sharpe: float = 0.0, periods_per_year: int = 52
) -> float:
    """Probability that the observed annualized Sharpe exceeds a benchmark.

    Implements the non-normal-return adjustment used by Bailey and Lopez de
    Prado.  The result is retrospective sampling evidence, not a forecast.
    """
    sample = [float(value) for value in values]
    if len(sample) < 3:
        raise ValueError("at least three returns are required")
    observed_annualized = annualized_sharpe(sample, periods_per_year=periods_per_year)
    # The finite-sample PSR correction is defined on the Sharpe ratio at the
    # observation frequency.  Accept annualized hurdles at the public API, but
    # convert both sides before applying the skew/kurtosis adjustment.  Using
    # an annualized Sharpe inside this denominator can saturate the probability
    # at one and effectively erase the multiple-testing penalty.
    scale = math.sqrt(periods_per_year)
    observed = observed_annualized / scale
    benchmark = benchmark_sharpe / scale
    skew = sample_skewness(sample)
    kurtosis = sample_kurtosis(sample)
    denominator_term = 1.0 - skew * observed + (kurtosis - 1.0) * observed * observed / 4.0
    if denominator_term <= 0.0:
        return 0.0 if observed <= benchmark else 1.0
    statistic = (observed - benchmark) * math.sqrt(len(sample) - 1) / math.sqrt(denominator_term)
    return NormalDist().cdf(statistic)


def expected_maximum_sharpe(*, trials: int, sharpe_std: float) -> float:
    if trials < 1 or sharpe_std < 0.0 or not math.isfinite(sharpe_std):
        raise ValueError("valid trial count and Sharpe standard deviation required")
    if trials == 1 or sharpe_std == 0.0:
        return 0.0
    normal = NormalDist()
    euler_gamma = 0.5772156649015329
    first = normal.inv_cdf(1.0 - 1.0 / trials)
    second = normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
    return sharpe_std * ((1.0 - euler_gamma) * first + euler_gamma * second)


def deflated_sharpe_ratio(
    selected_returns: Sequence[float], *, trial_sharpes: Sequence[float], periods_per_year: int = 52
) -> dict[str, float | int]:
    trials = [float(value) for value in trial_sharpes]
    if not trials or any(not math.isfinite(value) for value in trials):
        raise ValueError("finite trial Sharpe values are required")
    trial_std = statistics.stdev(trials) if len(trials) > 1 else 0.0
    hurdle = expected_maximum_sharpe(trials=len(trials), sharpe_std=trial_std)
    return {
        "trials": len(trials),
        "selected_sharpe": annualized_sharpe(selected_returns, periods_per_year=periods_per_year),
        "trial_sharpe_std": trial_std,
        "expected_maximum_sharpe_hurdle": hurdle,
        "deflated_sharpe_probability": probabilistic_sharpe_ratio(
            selected_returns, benchmark_sharpe=hurdle, periods_per_year=periods_per_year
        ),
    }


def _fold_indices(observations: int, folds: int) -> list[list[int]]:
    if folds < 2 or folds % 2 or observations < folds:
        raise ValueError("CSCV requires an even fold count that fits the observations")
    result = [[] for _ in range(folds)]
    for index in range(observations):
        result[min(index * folds // observations, folds - 1)].append(index)
    return result


def probability_of_backtest_overfitting(
    trial_returns: Sequence[Sequence[float]], *, folds: int = 8, periods_per_year: int = 52
) -> dict[str, float | int | list[float]]:
    """Combinatorially symmetric cross-validation PBO estimate.

    Input shape is trials x chronological return observations.  Each split
    selects the best in-sample trial, then records its out-of-sample rank.
    """
    matrix = [[float(value) for value in trial] for trial in trial_returns]
    if len(matrix) < 2 or not matrix[0]:
        raise ValueError("at least two nonempty trials are required")
    observations = len(matrix[0])
    if any(len(trial) != observations for trial in matrix):
        raise ValueError("trial return lengths must match")
    fold_map = _fold_indices(observations, folds)
    logits: list[float] = []
    splits = 0
    for in_fold_ids in itertools.combinations(range(folds), folds // 2):
        if 0 not in in_fold_ids:
            continue  # symmetric complements would duplicate each split
        in_set = set(in_fold_ids)
        in_indices = [idx for fid, group in enumerate(fold_map) if fid in in_set for idx in group]
        out_indices = [idx for fid, group in enumerate(fold_map) if fid not in in_set for idx in group]
        in_scores = [annualized_sharpe([trial[idx] for idx in in_indices], periods_per_year=periods_per_year) for trial in matrix]
        selected = max(range(len(matrix)), key=lambda idx: (in_scores[idx], -idx))
        out_scores = [annualized_sharpe([trial[idx] for idx in out_indices], periods_per_year=periods_per_year) for trial in matrix]
        ordered = sorted(range(len(matrix)), key=lambda idx: (out_scores[idx], -idx))
        rank = ordered.index(selected) + 1
        relative_rank = (rank - 0.5) / len(matrix)
        logits.append(math.log(relative_rank / (1.0 - relative_rank)))
        splits += 1
    return {
        "trials": len(matrix),
        "observations": observations,
        "folds": folds,
        "splits": splits,
        "pbo": sum(value <= 0.0 for value in logits) / len(logits),
        "rank_logits": logits,
    }


def white_reality_check_pvalue(
    return_differentials: Sequence[Sequence[float]], *, block_size: int = 13,
    replicates: int = 2000, seed: int = 0,
) -> dict[str, float | int]:
    """Block-bootstrap White Reality Check for the best mean differential."""
    matrix = [[float(value) for value in trial] for trial in return_differentials]
    if not matrix or not matrix[0] or any(len(trial) != len(matrix[0]) for trial in matrix):
        raise ValueError("equal-length differential series are required")
    if block_size < 1 or replicates < 1:
        raise ValueError("positive block size and replicates are required")
    observations = len(matrix[0])
    means = [statistics.fmean(trial) for trial in matrix]
    observed = max(means)
    centered = [[value - mean for value in trial] for trial, mean in zip(matrix, means)]
    generator = random.Random(seed)
    exceed = 0
    for _ in range(replicates):
        indices: list[int] = []
        while len(indices) < observations:
            start = generator.randrange(observations)
            indices.extend((start + offset) % observations for offset in range(block_size))
        indices = indices[:observations]
        bootstrap_max = max(statistics.fmean(trial[idx] for idx in indices) for trial in centered)
        exceed += bootstrap_max >= observed
    return {
        "trials": len(matrix),
        "observations": observations,
        "block_size": block_size,
        "replicates": replicates,
        "observed_best_mean": observed,
        "pvalue": (exceed + 1) / (replicates + 1),
    }
