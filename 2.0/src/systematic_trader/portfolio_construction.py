"""Point-in-time portfolio construction methods for the research laboratory."""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass

from .point_in_time import CASH_ASSET, monthly_rebalance_dates


Panel = dict[str, dict[str, float | None]]


@dataclass(frozen=True)
class PortfolioSpec:
    method: str
    top_n: int
    min_signal: float
    defensive_asset: str = "BIL"
    volatility_lookback_weeks: int = 26
    volatility_min_weeks: int = 13
    maximum_asset_weight: float = 1.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


SUPPORTED_METHODS = (
    "equal_weight",
    "score_weighted",
    "inverse_volatility",
    "score_inverse_volatility",
)


def _trailing_volatility(
    *, day_index: int, dates: list[str], asset: str, returns: Panel, lookback: int, minimum: int
) -> float | None:
    recent = dates[max(0, day_index - lookback + 1) : day_index + 1]
    values = [returns[day][asset] for day in recent if returns.get(day, {}).get(asset) is not None]
    if len(values) < minimum:
        return None
    volatility = statistics.stdev(float(value) for value in values)
    return volatility if math.isfinite(volatility) and volatility > 1e-12 else None


def _capped_normalize(
    raw: dict[str, float], maximum: float, *, total_weight: float = 1.0
) -> tuple[dict[str, float], float]:
    if not raw or maximum <= 0.0 or maximum > 1.0:
        if not raw:
            return {}, total_weight
        raise ValueError("maximum_asset_weight must be in (0, 1]")
    if not 0.0 <= total_weight <= 1.0:
        raise ValueError("total_weight must be in [0, 1]")
    if any(not math.isfinite(value) or value <= 0.0 for value in raw.values()):
        raise ValueError("raw allocation values must be finite and positive")
    remaining = total_weight
    active = dict(raw)
    result = {asset: 0.0 for asset in raw}
    while active and remaining > 1e-15:
        scale = remaining / sum(active.values())
        capped = [asset for asset, value in active.items() if value * scale > maximum]
        if not capped:
            for asset, value in active.items():
                result[asset] = value * scale
            remaining = 0.0
            break
        for asset in capped:
            result[asset] = maximum
            remaining -= maximum
            del active[asset]
        if remaining <= 1e-15:
            active.clear()
    return result, max(0.0, remaining)


def build_portfolio_weights(
    *,
    dates: list[str],
    assets: list[str],
    scores: Panel,
    prices: Panel,
    simple_returns: Panel,
    spec: PortfolioSpec,
    include_sample_endpoint_rebalance: bool = False,
    rebalance_frequency: str = "monthly",
) -> tuple[dict[str, dict[str, float]], set[str], dict[str, int | float]]:
    """Build long-only weights using information available at each decision date."""
    if spec.method not in SUPPORTED_METHODS:
        raise ValueError(f"unsupported portfolio method: {spec.method}")
    if spec.top_n <= 0:
        raise ValueError("top_n must be positive")

    if rebalance_frequency == "monthly":
        rebalance_dates = monthly_rebalance_dates(
            dates, include_sample_endpoint=include_sample_endpoint_rebalance
        )
    elif rebalance_frequency == "weekly":
        rebalance_dates = set(dates)
    else:
        raise ValueError(f"unsupported rebalance frequency: {rebalance_frequency}")
    columns = list(dict.fromkeys([*assets, spec.defensive_asset, CASH_ASSET]))
    current = {asset: 0.0 for asset in columns}
    result: dict[str, dict[str, float]] = {}
    asset_order = {asset: index for index, asset in enumerate(assets)}
    fallback_rebalances = 0
    defensive_rebalances = 0

    for index, decision in enumerate(dates):
        if decision in rebalance_dates:
            current = {asset: 0.0 for asset in columns}
            candidates = [
                (float(score), asset)
                for asset, score in scores.get(decision, {}).items()
                if asset in asset_order
                and score is not None
                and float(score) > spec.min_signal
                and prices.get(decision, {}).get(asset) is not None
            ]
            candidates.sort(key=lambda item: (-item[0], asset_order[item[1]]))
            selected = candidates[: spec.top_n]
            raw: dict[str, float] = {}
            rebalance_used_fallback = False
            for score, asset in selected:
                volatility = _trailing_volatility(
                    day_index=index,
                    dates=dates,
                    asset=asset,
                    returns=simple_returns,
                    lookback=spec.volatility_lookback_weeks,
                    minimum=spec.volatility_min_weeks,
                )
                if spec.method == "equal_weight":
                    raw[asset] = 1.0
                elif spec.method == "score_weighted":
                    raw[asset] = max(score - spec.min_signal, 1e-12)
                elif spec.method == "inverse_volatility":
                    raw[asset] = 1.0 / volatility if volatility is not None else 1.0
                    rebalance_used_fallback = rebalance_used_fallback or volatility is None
                else:
                    raw[asset] = (
                        max(score - spec.min_signal, 1e-12) / volatility
                        if volatility is not None
                        else max(score - spec.min_signal, 1e-12)
                    )
                    rebalance_used_fallback = rebalance_used_fallback or volatility is None

            if rebalance_used_fallback:
                fallback_rebalances += 1
            risk_budget = len(selected) / spec.top_n
            allocated, _ = _capped_normalize(
                raw, spec.maximum_asset_weight, total_weight=risk_budget
            )
            current.update(allocated)
            remainder = 1.0 - sum(allocated.values())
            if remainder > 1e-12:
                destination = (
                    spec.defensive_asset
                    if prices.get(decision, {}).get(spec.defensive_asset) is not None
                    else CASH_ASSET
                )
                current[destination] += remainder
                defensive_rebalances += 1
        result[decision] = dict(current)

    return result, rebalance_dates, {
        "rebalance_count": len(rebalance_dates),
        "volatility_fallback_rebalances": fallback_rebalances,
        "defensive_rebalances": defensive_rebalances,
    }
