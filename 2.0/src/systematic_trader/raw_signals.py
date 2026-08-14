"""Independent standard-library reconstruction of the five trend signals."""

from __future__ import annotations

import math
import statistics
from typing import Callable


Panel = dict[str, dict[str, float | None]]


def empty_panel(dates: list[str], assets: list[str]) -> Panel:
    return {day: {asset: None for asset in assets} for day in dates}


def shift_panel(panel: Panel, dates: list[str], assets: list[str], periods: int = 1) -> Panel:
    result = empty_panel(dates, assets)
    for index in range(periods, len(dates)):
        result[dates[index]] = dict(panel[dates[index - periods]])
    return result


def trailing_return(prices: Panel, dates: list[str], assets: list[str], lookback: int, skip: int) -> Panel:
    result = empty_panel(dates, assets)
    for index, day in enumerate(dates):
        if index < lookback:
            continue
        numerator_day = dates[index - skip]
        denominator_day = dates[index - lookback]
        for asset in assets:
            numerator = prices[numerator_day][asset]
            denominator = prices[denominator_day][asset]
            if numerator is not None and denominator not in (None, 0.0):
                result[day][asset] = numerator / denominator - 1.0
    return result


def rolling_stat(
    panel: Panel,
    dates: list[str],
    assets: list[str],
    *,
    window: int,
    min_periods: int,
    statistic: Callable[[list[float]], float],
) -> Panel:
    result = empty_panel(dates, assets)
    for index, day in enumerate(dates):
        recent = dates[max(0, index - window + 1) : index + 1]
        for asset in assets:
            values = [panel[item][asset] for item in recent if panel[item][asset] is not None]
            if len(values) >= min_periods:
                result[day][asset] = statistic([float(value) for value in values])
    return result


def rolling_mean(panel: Panel, dates: list[str], assets: list[str], window: int, min_periods: int) -> Panel:
    return rolling_stat(panel, dates, assets, window=window, min_periods=min_periods, statistic=statistics.fmean)


def rolling_std(panel: Panel, dates: list[str], assets: list[str], window: int, min_periods: int) -> Panel:
    return rolling_stat(panel, dates, assets, window=window, min_periods=min_periods, statistic=statistics.stdev)


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def average_ranks(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average = ((index + 1) + end) / 2.0
        for position in range(index, end):
            ranks[ordered[position][0]] = average
        index = end
    return ranks


def panel_rank(panel: Panel, dates: list[str], assets: list[str]) -> Panel:
    result = empty_panel(dates, assets)
    for day in dates:
        valid = {asset: float(panel[day][asset]) for asset in assets if panel[day][asset] is not None}
        result[day].update(average_ranks(valid))
    return result


def panel_score(panel: Panel, dates: list[str], assets: list[str]) -> Panel:
    result = empty_panel(dates, assets)
    for day in dates:
        valid = {asset: float(panel[day][asset]) for asset in assets if panel[day][asset] is not None}
        if not valid:
            continue
        lower = percentile(list(valid.values()), 0.05)
        upper = percentile(list(valid.values()), 0.95)
        clipped = {asset: min(max(value, lower), upper) for asset, value in valid.items()}
        ranks = average_ranks(clipped)
        if len(clipped) == 1:
            result[day][next(iter(clipped))] = 0.0
        else:
            for asset, rank in ranks.items():
                result[day][asset] = ((rank - 1.0) / (len(clipped) - 1.0)) * 2.0 - 1.0
    return result


def multiply(left: Panel, right: Panel, dates: list[str], assets: list[str]) -> Panel:
    result = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            a, b = left[day][asset], right[day][asset]
            if a is not None and b is not None:
                result[day][asset] = a * b
    return result


def ratio_minus_one(left: Panel, right: Panel, dates: list[str], assets: list[str]) -> Panel:
    result = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            a, b = left[day][asset], right[day][asset]
            if a is not None and b not in (None, 0.0):
                result[day][asset] = a / b - 1.0
    return result


def rolling_trend_r2(log_prices: Panel, dates: list[str], assets: list[str], window: int, min_periods: int) -> Panel:
    def calculate(values: list[float]) -> float:
        count = len(values)
        x = [float(index) for index in range(count)]
        mean_x = statistics.fmean(x)
        mean_y = statistics.fmean(values)
        centered_x = [value - mean_x for value in x]
        centered_y = [value - mean_y for value in values]
        denominator = math.sqrt(sum(value * value for value in centered_x) * sum(value * value for value in centered_y))
        if denominator <= 0.0:
            return math.nan
        correlation = sum(a * b for a, b in zip(centered_x, centered_y)) / denominator
        return correlation * correlation

    result = rolling_stat(log_prices, dates, assets, window=window, min_periods=min_periods, statistic=calculate)
    for day in dates:
        for asset in assets:
            if result[day][asset] is not None and not math.isfinite(float(result[day][asset])):
                result[day][asset] = None
    return result


def reconstruct_five_signals(
    *, dates: list[str], assets: list[str], prices: Panel, weekly_log_returns: Panel
) -> tuple[dict[str, Panel], dict[str, Panel]]:
    components: dict[str, Panel] = {}

    momentum_52_4 = trailing_return(prices, dates, assets, 52, 4)
    components["xsmom_raw_return_52_4w"] = momentum_52_4
    components["xsmom_raw_rank"] = panel_rank(momentum_52_4, dates, assets)
    components["xsmom_score_observed"] = panel_score(momentum_52_4, dates, assets)
    components["xsmom_score_tradable"] = shift_panel(components["xsmom_score_observed"], dates, assets)

    annual_vol = rolling_std(weekly_log_returns, dates, assets, window=26, min_periods=13)
    for day in dates:
        for asset in assets:
            if annual_vol[day][asset] is not None:
                annual_vol[day][asset] = float(annual_vol[day][asset]) * math.sqrt(52.0)
    scaled = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            raw, vol = momentum_52_4[day][asset], annual_vol[day][asset]
            if raw is not None and vol not in (None, 0.0):
                scaled[day][asset] = raw / vol
    components["raw_tsmom_52_4w"] = momentum_52_4
    components["realized_vol_ann_26w"] = annual_vol
    components["tsmom_vol_scaled_observed"] = scaled
    components["tsmom_score_observed"] = panel_score(scaled, dates, assets)
    components["tsmom_vol_scaled_tradable"] = shift_panel(scaled, dates, assets)
    components["tsmom_score_tradable"] = shift_panel(components["tsmom_score_observed"], dates, assets)

    momentum_components = {
        f"mom_{lookback}_4w": trailing_return(prices, dates, assets, lookback, 4)
        for lookback in (13, 26, 39, 52)
    }
    components.update(momentum_components)
    equal = empty_panel(dates, assets)
    inverse = empty_panel(dates, assets)
    component_vols = {
        name: rolling_std(panel, dates, assets, window=52, min_periods=26)
        for name, panel in momentum_components.items()
    }
    for day in dates:
        for asset in assets:
            values = [panel[day][asset] for panel in momentum_components.values()]
            if all(value is not None for value in values):
                equal[day][asset] = sum(float(value) for value in values) / 4.0
            vols = [panel[day][asset] for panel in component_vols.values()]
            if all(value is not None for value in values) and all(value is not None for value in vols):
                inverse_weights = [1.0 / max(float(value), 0.01) for value in vols]
                inverse[day][asset] = sum(weight * float(value) for weight, value in zip(inverse_weights, values)) / sum(inverse_weights)
    components["multi_mom_equal_observed"] = equal
    components["multi_mom_equal_score_observed"] = panel_score(equal, dates, assets)
    components["multi_mom_equal_score_tradable"] = shift_panel(components["multi_mom_equal_score_observed"], dates, assets)
    components["multi_mom_invvol_observed"] = inverse
    components["multi_mom_invvol_score_observed"] = panel_score(inverse, dates, assets)
    components["multi_mom_invvol_score_tradable"] = shift_panel(components["multi_mom_invvol_score_observed"], dates, assets)

    log_prices = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            price = prices[day][asset]
            if price is not None and price > 0.0:
                log_prices[day][asset] = math.log(price)
    clarity = rolling_trend_r2(log_prices, dates, assets, window=52, min_periods=39)
    clarity_raw = multiply(momentum_52_4, clarity, dates, assets)
    components["trend_clarity_r2_observed"] = clarity
    components["trend_clarity_momentum_raw_observed"] = clarity_raw
    components["trend_clarity_momentum_raw_tradable"] = shift_panel(clarity_raw, dates, assets)
    components["trend_clarity_momentum_score_observed"] = panel_score(clarity_raw, dates, assets)
    components["trend_clarity_momentum_score_tradable"] = shift_panel(components["trend_clarity_momentum_score_observed"], dates, assets)

    ma_short = rolling_mean(prices, dates, assets, window=13, min_periods=8)
    ma_long = rolling_mean(prices, dates, assets, window=52, min_periods=26)
    distance = ratio_minus_one(ma_short, ma_long, dates, assets)
    components["ma_13w_observed"] = ma_short
    components["ma_52w_observed"] = ma_long
    components["moving_average_distance_observed"] = distance
    components["moving_average_distance_tradable"] = shift_panel(distance, dates, assets)
    components["moving_average_distance_score_observed"] = panel_score(distance, dates, assets)
    components["moving_average_distance_score_tradable"] = shift_panel(components["moving_average_distance_score_observed"], dates, assets)

    strategy_panels = {
        "xsmom_global": components["xsmom_score_tradable"],
        "multi_mom_invvol": components["multi_mom_invvol_score_tradable"],
        "tsmom_vol_scaled": components["tsmom_score_tradable"],
        "trend_clarity_momentum": components["trend_clarity_momentum_score_tradable"],
        "moving_average_distance": components["moving_average_distance_score_tradable"],
    }
    return strategy_panels, components
