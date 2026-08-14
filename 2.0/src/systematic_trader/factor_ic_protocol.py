"""Pure-Python statistics for the predeclared factor rank-IC protocol."""

from __future__ import annotations

import math
import random
import statistics


def quantile(values: list[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires observations")
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def circular_block_bootstrap_means(
    values: list[float], *, block_size: int, replicates: int, seed: int
) -> list[float]:
    """Bootstrap a mean with fixed-length circular blocks."""
    if not values:
        raise ValueError("bootstrap requires observations")
    if block_size <= 0 or replicates <= 0:
        raise ValueError("block_size and replicates must be positive")
    sample = [float(value) for value in values]
    if not all(math.isfinite(value) for value in sample):
        raise ValueError("bootstrap values must be finite")
    count = len(sample)
    blocks = math.ceil(count / block_size)
    randomizer = random.Random(seed)
    means = []
    for _ in range(replicates):
        total = 0.0
        used = 0
        for _block in range(blocks):
            take = min(block_size, count - used)
            start = randomizer.randrange(count)
            total += sum(sample[(start + offset) % count] for offset in range(take))
            used += take
        means.append(total / count)
    return means


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"observations": 0, "mean_ic": math.nan, "median_ic": math.nan, "ic_std": math.nan, "positive_rate": math.nan}
    return {
        "observations": len(values),
        "mean_ic": statistics.fmean(values),
        "median_ic": statistics.median(values),
        "ic_std": statistics.stdev(values) if len(values) > 1 else 0.0,
        "positive_rate": sum(value > 0.0 for value in values) / len(values),
    }

