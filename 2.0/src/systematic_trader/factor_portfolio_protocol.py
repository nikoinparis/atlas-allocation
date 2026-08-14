"""Portfolio construction and drift-aware accounting for qualified factors."""

from __future__ import annotations

import math


CASH = "cash::USD"


def cap_and_normalize(raw: dict[str, float], maximum: float) -> dict[str, float]:
    """Normalize positive weights while iteratively enforcing an upper cap."""
    if maximum <= 0.0 or maximum > 1.0:
        raise ValueError("maximum must be in (0, 1]")
    positive = {name: float(value) for name, value in raw.items() if value > 0.0 and math.isfinite(value)}
    if not positive:
        return {}
    if len(positive) * maximum < 1.0 - 1e-12:
        raise ValueError("cap is infeasible for the number of assets")
    remaining = set(positive)
    result = {name: 0.0 for name in positive}
    residual = 1.0
    while remaining:
        denominator = sum(positive[name] for name in remaining)
        proposed = {name: residual * positive[name] / denominator for name in remaining}
        capped = [name for name, value in proposed.items() if value > maximum + 1e-15]
        if not capped:
            result.update(proposed)
            break
        for name in capped:
            result[name] = maximum
            residual -= maximum
            remaining.remove(name)
    return result


def target_weights(
    scores: dict[str, float], volatility: dict[str, float], *, candidate: str,
    top_n: int, maximum_weight: float, inverted: bool = False,
) -> dict[str, float]:
    eligible = [(score, asset) for asset, score in scores.items() if math.isfinite(score)]
    eligible.sort(key=lambda row: (row[0] if inverted else -row[0], row[1]))
    selected = [asset for _, asset in eligible[:top_n]]
    if len(selected) < top_n:
        return {CASH: 1.0}
    if candidate == "equal_weight_top5":
        risky = {asset: 1.0 / top_n for asset in selected}
    elif candidate == "inverse_volatility_top5":
        inverse = {
            asset: 1.0 / volatility[asset]
            for asset in selected
            if asset in volatility and math.isfinite(volatility[asset]) and volatility[asset] > 0.0
        }
        if len(inverse) < top_n:
            return {CASH: 1.0}
        risky = cap_and_normalize(inverse, maximum_weight)
    else:
        raise ValueError(f"unknown candidate: {candidate}")
    result = dict(risky)
    result[CASH] = max(0.0, 1.0 - sum(risky.values()))
    return result


def drift_aware_path(
    dates: list[str], weights: dict[str, dict[str, float] | None],
    returns: dict[str, dict[str, float | None]], *, cost_bps: float,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    previous_drifted = {CASH: 1.0}
    periods = []
    unpriced = 0
    maximum_sum_error = 0.0
    maximum_cost_error = 0.0
    for index, decision in enumerate(dates[:-1]):
        realization = dates[index + 1]
        requested = weights[decision]
        target = previous_drifted if requested is None else requested
        maximum_sum_error = max(maximum_sum_error, abs(sum(target.values()) - 1.0))
        names = set(target) | set(previous_drifted)
        turnover = 0.0 if requested is None else 0.5 * sum(
            abs(target.get(name, 0.0) - previous_drifted.get(name, 0.0)) for name in names
        )
        gross = 0.0
        asset_returns: dict[str, float] = {}
        for asset, weight in target.items():
            if asset == CASH:
                value = 0.0
            else:
                observed = returns.get(realization, {}).get(asset)
                if observed is None:
                    unpriced += abs(weight) > 1e-12
                    value = 0.0
                else:
                    value = float(observed)
            asset_returns[asset] = value
            gross += weight * value
        cost = turnover * cost_bps / 10_000.0
        net = gross - cost
        maximum_cost_error = max(maximum_cost_error, abs(net - (gross - cost)))
        denominator = 1.0 + gross
        previous_drifted = {
            asset: weight * (1.0 + asset_returns[asset]) / denominator
            for asset, weight in target.items()
        }
        periods.append({
            "decision_date": decision, "realization_date": realization,
            "gross_return": gross, "net_return": net, "turnover": turnover,
            "cost": cost, "invested_weight": 1.0 - target.get(CASH, 0.0),
        })
    return periods, {
        "periods": len(periods), "unpriced_exposure_events": unpriced,
        "unpriced_exposure_pass": unpriced == 0,
        "maximum_weight_sum_error": maximum_sum_error,
        "fully_invested_including_cash_pass": maximum_sum_error <= 1e-12,
        "maximum_cost_identity_error": maximum_cost_error,
        "cost_identity_pass": maximum_cost_error <= 1e-15,
    }
