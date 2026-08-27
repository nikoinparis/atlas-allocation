"""Dependence, ensemble, and multiple-testing helpers for strategy research."""

from __future__ import annotations

import math
import random
import statistics
from statistics import NormalDist


def correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation requires equal series with at least two values")
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
    denominator = math.sqrt(
        sum((a - mean_left) ** 2 for a in left) * sum((b - mean_right) ** 2 for b in right)
    )
    return numerator / denominator if denominator > 0.0 else 0.0


def weighted_holdings_overlap(left: dict[str, float], right: dict[str, float]) -> float:
    """Intersection of two long-only, fully invested portfolios in [0, 1]."""
    assets = set(left) | set(right)
    if any(left.get(asset, 0.0) < 0.0 or right.get(asset, 0.0) < 0.0 for asset in assets):
        raise ValueError("holdings overlap only supports long-only weights")
    return sum(min(left.get(asset, 0.0), right.get(asset, 0.0)) for asset in assets)


def average_holdings_overlap(
    dates: list[str], left: dict[str, dict[str, float]], right: dict[str, dict[str, float]]
) -> float:
    common = [day for day in dates if day in left and day in right]
    if not common:
        raise ValueError("weight histories do not overlap")
    return statistics.fmean(weighted_holdings_overlap(left[day], right[day]) for day in common)


def correlation_clusters(
    names: list[str], matrix: dict[str, dict[str, float]], threshold: float
) -> list[list[str]]:
    """Connected components where any pairwise correlation meets the threshold."""
    remaining = set(names)
    clusters: list[list[str]] = []
    while remaining:
        seed = min(remaining)
        stack = [seed]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            for other in remaining:
                if other not in component and matrix[current][other] >= threshold:
                    stack.append(other)
        remaining -= component
        clusters.append(sorted(component))
    return sorted(clusters, key=lambda cluster: (cluster[0], len(cluster)))


def combine_weight_histories(
    dates: list[str], histories: dict[str, dict[str, dict[str, float]]], coefficients: dict[str, float]
) -> dict[str, dict[str, float]]:
    if abs(sum(coefficients.values()) - 1.0) > 1e-12 or any(value < 0.0 for value in coefficients.values()):
        raise ValueError("ensemble coefficients must be nonnegative and sum to one")
    if set(coefficients) - set(histories):
        raise ValueError("coefficient references an unknown strategy")
    result: dict[str, dict[str, float]] = {}
    for day in dates:
        assets = set().union(*(histories[name][day] for name in coefficients))
        result[day] = {
            asset: sum(coefficients[name] * histories[name][day].get(asset, 0.0) for name in coefficients)
            for asset in assets
        }
    return result


def greedy_low_correlation_selection(
    names: list[str], matrix: dict[str, dict[str, float]], *, start: str, count: int
) -> list[str]:
    if start not in names or not 1 <= count <= len(names):
        raise ValueError("invalid greedy selection request")
    selected = [start]
    while len(selected) < count:
        remaining = [name for name in names if name not in selected]
        chosen = min(
            remaining,
            key=lambda name: (statistics.fmean(matrix[name][item] for item in selected), name),
        )
        selected.append(chosen)
    return selected


def effective_independent_count(matrix: dict[str, dict[str, float]]) -> float:
    """Participation-ratio estimate using trace(C)^2 / trace(C^2)."""
    names = list(matrix)
    trace = sum(matrix[name][name] for name in names)
    trace_square = sum(matrix[left][right] ** 2 for left in names for right in names)
    return trace * trace / trace_square if trace_square > 0.0 else 0.0


def marginal_effective_breadth(
    candidate: str, matrix: dict[str, dict[str, float]]
) -> float:
    """Return the candidate's participation-ratio breadth contribution.

    The comparison is deliberately made against the complete peer set.  A
    candidate that is merely another highly correlated variant can therefore
    have a contribution close to zero (or even negative), regardless of its
    standalone Sharpe ratio.
    """
    if candidate not in matrix:
        raise ValueError("candidate is absent from the correlation matrix")
    names = list(matrix)
    if any(set(matrix[name]) != set(names) for name in names):
        raise ValueError("correlation matrix must be square and complete")
    if len(names) == 1:
        return effective_independent_count(matrix)
    without = {
        left: {right: matrix[left][right] for right in names if right != candidate}
        for left in names
        if left != candidate
    }
    return effective_independent_count(matrix) - effective_independent_count(without)


def breadth_admission_gate(
    *,
    candidate: str,
    matrix: dict[str, dict[str, float]],
    holdings_overlap_by_peer: dict[str, float],
    minimum_rounded_contribution: float = 0.01,
    contribution_decimals: int = 2,
) -> dict[str, object]:
    """Fail-closed breadth gate for a proposed strategy candidate.

    Holdings overlap is mandatory because return correlation alone can look
    low over a short or unusual regime.  This gate does not claim alpha; it
    only decides whether a candidate contributes measurable diversification.
    """
    if candidate not in matrix:
        raise ValueError("candidate is absent from the correlation matrix")
    peers = [name for name in matrix if name != candidate]
    if not peers:
        raise ValueError("breadth admission requires at least one incumbent peer")
    if set(holdings_overlap_by_peer) != set(peers):
        raise ValueError("holdings overlap is required for every incumbent peer")
    overlaps = [float(holdings_overlap_by_peer[name]) for name in peers]
    if any(not 0.0 <= value <= 1.0 for value in overlaps):
        raise ValueError("holdings overlap must be in [0, 1]")
    correlations = [float(matrix[candidate][name]) for name in peers]
    contribution = marginal_effective_breadth(candidate, matrix)
    rounded = round(contribution, contribution_decimals)
    passed = rounded >= minimum_rounded_contribution
    return {
        "candidate": candidate,
        "incumbent_count": len(peers),
        "effective_breadth_with_candidate": effective_independent_count(matrix),
        "marginal_effective_breadth": contribution,
        "rounded_marginal_effective_breadth": rounded,
        "minimum_rounded_contribution": minimum_rounded_contribution,
        "average_peer_correlation": statistics.fmean(correlations),
        "maximum_absolute_peer_correlation": max(abs(value) for value in correlations),
        "average_holdings_overlap": statistics.fmean(overlaps),
        "maximum_holdings_overlap": max(overlaps),
        "breadth_gate_pass": passed,
        "performance_promotion_authorized": False,
    }


def fundamental_law_decomposition(
    *,
    information_coefficient: float,
    effective_breadth: float,
    transfer_coefficient: float = 1.0,
    realized_information_ratio: float | None = None,
) -> dict[str, float | None]:
    """Report an explicit IC/breadth/implementation-efficiency decomposition.

    This is a measurement helper, not a performance estimator.  Callers must
    supply an out-of-sample IC and should omit realized IR when it is not
    available on a matching horizon.
    """
    ic = float(information_coefficient)
    breadth = float(effective_breadth)
    transfer = float(transfer_coefficient)
    if not -1.0 <= ic <= 1.0:
        raise ValueError("information coefficient must be in [-1, 1]")
    if breadth < 0.0:
        raise ValueError("effective breadth must be nonnegative")
    if not 0.0 <= transfer <= 1.0:
        raise ValueError("transfer coefficient must be in [0, 1]")
    theoretical = ic * math.sqrt(breadth)
    implementable = theoretical * transfer
    realized = None if realized_information_ratio is None else float(realized_information_ratio)
    efficiency = None
    if realized is not None and implementable != 0.0:
        efficiency = realized / implementable
    return {
        "information_coefficient": ic,
        "effective_breadth": breadth,
        "transfer_coefficient": transfer,
        "theoretical_information_ratio": theoretical,
        "implementable_information_ratio": implementable,
        "realized_information_ratio": realized,
        "realized_to_implementable_efficiency": efficiency,
    }


def block_bootstrap_positive_mean_pvalue(
    returns: list[float], *, seed: int, samples: int = 2000, block_size: int = 13
) -> float:
    """One-sided centered-null p-value with circular, serial-dependence blocks."""
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    observed = statistics.fmean(returns)
    centered = [value - observed for value in returns]
    generator = random.Random(seed)
    exceedances = 0
    for _ in range(samples):
        total = 0.0
        count = 0
        while count < len(centered):
            start = generator.randrange(len(centered))
            take = min(block_size, len(centered) - count)
            total += sum(centered[(start + offset) % len(centered)] for offset in range(take))
            count += take
        exceedances += total / len(centered) >= observed
    return (exceedances + 1.0) / (samples + 1.0)


def expected_maximum_sharpe(*, trials: int, observations: int, periods_per_year: int = 52) -> float:
    """Expected best annualized Sharpe from independent zero-alpha Gaussian trials."""
    if trials <= 1 or observations <= 1:
        return 0.0
    normal = NormalDist()
    gamma = 0.5772156649015329
    first = normal.inv_cdf(1.0 - 1.0 / trials)
    second = normal.inv_cdf(1.0 - 1.0 / (trials * math.e))
    return ((1.0 - gamma) * first + gamma * second) * math.sqrt(periods_per_year / (observations - 1))
