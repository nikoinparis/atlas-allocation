"""Causal allocation across already-accounted strategy sleeves."""

from __future__ import annotations

import math
import statistics

from .point_in_time import CASH_ASSET


def shrunk_covariance(
    observations: dict[str, list[float]], *, diagonal_shrinkage: float
) -> dict[str, dict[str, float]]:
    """Sample covariance shrunk toward its diagonal, using aligned observations."""
    names = list(observations)
    if len(names) < 2 or not 0.0 <= diagonal_shrinkage <= 1.0:
        raise ValueError("need at least two sleeves and shrinkage in [0, 1]")
    lengths = {len(observations[name]) for name in names}
    if len(lengths) != 1 or min(lengths) < 2:
        raise ValueError("sleeve observations must be aligned with at least two rows")
    means = {name: statistics.fmean(observations[name]) for name in names}
    result: dict[str, dict[str, float]] = {}
    denominator = next(iter(lengths)) - 1
    for left in names:
        result[left] = {}
        for right in names:
            raw = sum(
                (a - means[left]) * (b - means[right])
                for a, b in zip(observations[left], observations[right])
            ) / denominator
            result[left][right] = (
                raw if left == right else raw * (1.0 - diagonal_shrinkage)
            )
    return result


def portfolio_variance(weights: dict[str, float], covariance: dict[str, dict[str, float]]) -> float:
    return sum(
        weights[left] * weights[right] * covariance[left][right]
        for left in weights for right in weights
    )


def _bounded_two_sleeve(first_weight: float, names: list[str], maximum_weight: float) -> dict[str, float]:
    if len(names) != 2 or not 0.5 <= maximum_weight <= 1.0:
        raise ValueError("two sleeves and a maximum weight in [0.5, 1] are required")
    lower = 1.0 - maximum_weight
    first_weight = min(maximum_weight, max(lower, first_weight))
    return {names[0]: first_weight, names[1]: 1.0 - first_weight}


def allocate_two_sleeves(
    method: str,
    covariance: dict[str, dict[str, float]],
    *,
    maximum_weight: float = 0.80,
) -> dict[str, float]:
    """Long-only allocation for the two surviving strategy sleeves."""
    names = list(covariance)
    if len(names) != 2:
        raise ValueError("Batch 06 allocators require exactly two sleeves")
    first, second = names
    var_first = max(0.0, covariance[first][first])
    var_second = max(0.0, covariance[second][second])
    covar = covariance[first][second]
    if method == "equal_weight":
        first_weight = 0.5
    elif method in {"inverse_volatility", "maximum_diversification"}:
        vol_first = math.sqrt(var_first)
        vol_second = math.sqrt(var_second)
        first_weight = vol_second / (vol_first + vol_second) if vol_first + vol_second > 0 else 0.5
    elif method == "minimum_variance":
        denominator = var_first + var_second - 2.0 * covar
        first_weight = (var_second - covar) / denominator if denominator > 1e-18 else 0.5
    elif method == "hrp_two_sleeve":
        inverse_first = 1.0 / var_first if var_first > 1e-18 else 0.0
        inverse_second = 1.0 / var_second if var_second > 1e-18 else 0.0
        first_weight = inverse_first / (inverse_first + inverse_second) if inverse_first + inverse_second > 0 else 0.5
    else:
        raise ValueError(f"unsupported strategy allocation method: {method}")
    return _bounded_two_sleeve(first_weight, names, maximum_weight)


def safe_allocate_two_sleeves(
    method: str,
    covariance: dict[str, dict[str, float]],
    *,
    sleeve_names: tuple[str, str],
    maximum_weight: float = 0.80,
) -> tuple[dict[str, float], str | None]:
    """Allocate or deterministically fall back to equal weight on invalid estimates."""
    fallback = {sleeve_names[0]: 0.5, sleeve_names[1]: 0.5}
    try:
        if set(covariance) != set(sleeve_names):
            raise ValueError("covariance sleeve mismatch")
        values = [covariance[left][right] for left in sleeve_names for right in sleeve_names]
        if any(not math.isfinite(value) for value in values):
            raise ValueError("non-finite covariance")
        if any(covariance[name][name] < 0.0 for name in sleeve_names):
            raise ValueError("negative variance")
        weights = allocate_two_sleeves(method, covariance, maximum_weight=maximum_weight)
        if any(not math.isfinite(value) for value in weights.values()):
            raise ValueError("non-finite allocation")
        return weights, None
    except (KeyError, ValueError, ZeroDivisionError) as error:
        return fallback, str(error)


def combine_dynamic_weight_histories(
    dates: list[str],
    histories: dict[str, dict[str, dict[str, float]]],
    coefficients: dict[str, dict[str, float]],
) -> dict[str, dict[str, float]]:
    """Combine dated sleeve weights, allowing unlevered residual cash."""
    result: dict[str, dict[str, float]] = {}
    for day in dates:
        row_coefficients = coefficients[day]
        if set(row_coefficients) - set(histories):
            raise ValueError("coefficient references an unknown sleeve")
        exposure = sum(row_coefficients.values())
        if exposure < -1e-12 or exposure > 1.0 + 1e-12 or any(value < 0.0 for value in row_coefficients.values()):
            raise ValueError("dynamic coefficients must be nonnegative and sum to at most one")
        assets = set().union(*(histories[name][day] for name in row_coefficients))
        combined = {
            asset: sum(
                row_coefficients[name] * histories[name][day].get(asset, 0.0)
                for name in row_coefficients
            )
            for asset in assets
        }
        combined[CASH_ASSET] = combined.get(CASH_ASSET, 0.0) + max(0.0, 1.0 - exposure)
        result[day] = combined
    return result


def cap_non_cash_weights(
    histories: dict[str, dict[str, float]], *, maximum_asset_weight: float
) -> dict[str, dict[str, float]]:
    """Move non-cash concentration above a fixed cap into explicit cash."""
    if not 0.0 < maximum_asset_weight <= 1.0:
        raise ValueError("maximum_asset_weight must be in (0, 1]")
    result: dict[str, dict[str, float]] = {}
    for day, row in histories.items():
        capped: dict[str, float] = {}
        excess = 0.0
        for asset, weight in row.items():
            if asset == CASH_ASSET:
                capped[asset] = weight
            else:
                capped[asset] = min(weight, maximum_asset_weight)
                excess += max(0.0, weight - maximum_asset_weight)
        capped[CASH_ASSET] = capped.get(CASH_ASSET, 0.0) + excess
        result[day] = capped
    return result
