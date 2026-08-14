"""Point-in-time mean-reversion, defensive, and distribution-yield signals."""

from __future__ import annotations

import csv
import math
import statistics
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from .raw_signals import (
    Panel,
    empty_panel,
    panel_score,
    rolling_mean,
    rolling_std,
    shift_panel,
    trailing_return,
)
from .weekly_data import friday_label


def negate(panel: Panel, dates: list[str], assets: list[str]) -> Panel:
    result = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            value = panel[day][asset]
            result[day][asset] = -float(value) if value is not None else None
    return result


def moving_average_reversal(prices: Panel, dates: list[str], assets: list[str], window: int = 13) -> Panel:
    average = rolling_mean(prices, dates, assets, window=window, min_periods=max(4, window // 2))
    raw = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            price, mean = prices[day][asset], average[day][asset]
            if price is not None and mean not in (None, 0.0):
                raw[day][asset] = -(float(price) / float(mean) - 1.0)
    return raw


def rsi_reversal(weekly_log_returns: Panel, dates: list[str], assets: list[str], window: int = 13) -> Panel:
    result = empty_panel(dates, assets)
    for index, day in enumerate(dates):
        recent = dates[max(0, index - window + 1) : index + 1]
        for asset in assets:
            values = [weekly_log_returns[item][asset] for item in recent]
            valid = [float(value) for value in values if value is not None]
            if len(valid) < max(4, window // 2):
                continue
            average_gain = statistics.fmean(max(value, 0.0) for value in valid)
            average_loss = statistics.fmean(max(-value, 0.0) for value in valid)
            if average_loss <= 1e-15:
                rsi = 100.0
            else:
                rsi = 100.0 - 100.0 / (1.0 + average_gain / average_loss)
            result[day][asset] = -rsi
    return result


def drawdown_resilience(prices: Panel, dates: list[str], assets: list[str], window: int = 26) -> Panel:
    result = empty_panel(dates, assets)
    for index, day in enumerate(dates):
        recent = dates[max(0, index - window + 1) : index + 1]
        for asset in assets:
            current = prices[day][asset]
            valid = [float(prices[item][asset]) for item in recent if prices[item][asset] is not None]
            if current is not None and len(valid) >= window // 2 and max(valid) > 0.0:
                result[day][asset] = float(current) / max(valid) - 1.0
    return result


def weekly_close_prices(
    prices_path: Path, *, dates: list[str], assets: list[str]
) -> Panel:
    allowed_dates = set(dates)
    allowed_assets = set(assets)
    selected: dict[tuple[str, str], tuple[date, float]] = {}
    with prices_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            asset = row["ticker"]
            if asset not in allowed_assets:
                continue
            observed = date.fromisoformat(row["observation_date"])
            week = friday_label(observed).isoformat()
            if week not in allowed_dates:
                continue
            value = float(row["close"])
            if math.isfinite(value) and value > 0.0:
                key = (week, asset)
                if key not in selected or observed > selected[key][0]:
                    selected[key] = (observed, value)
    return {
        day: {asset: selected.get((day, asset), (None, None))[1] for asset in assets}
        for day in dates
    }


def trailing_distribution_yield(
    *, actions_path: Path, dates: list[str], assets: list[str], close_prices: Panel, lookback_days: int = 365
) -> Panel:
    events: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with actions_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] in assets and row["action_type"] == "cash_distribution":
                amount = float(row["amount"])
                if math.isfinite(amount) and amount >= 0.0:
                    events[row["ticker"]].append((date.fromisoformat(row["event_date"]), amount))
    result = empty_panel(dates, assets)
    for day_text in dates:
        day = date.fromisoformat(day_text)
        start = day - timedelta(days=lookback_days)
        for asset in assets:
            price = close_prices[day_text][asset]
            if price is None:
                continue
            history = [(event_day, amount) for event_day, amount in events[asset] if start < event_day <= day]
            if history:
                result[day_text][asset] = sum(amount for _, amount in history) / float(price)
    return result


def reconstruct_non_momentum_signals(
    *, dates: list[str], assets: list[str], prices: Panel, weekly_log_returns: Panel,
    prices_path: Path, actions_path: Path,
) -> tuple[dict[str, Panel], dict[str, Panel], dict[str, object]]:
    components: dict[str, Panel] = {}

    reversal_4w = negate(trailing_return(prices, dates, assets, lookback=4, skip=0), dates, assets)
    components["reversal_4w_observed"] = reversal_4w
    components["reversal_4w_score_observed"] = panel_score(reversal_4w, dates, assets)

    ma_reversal = moving_average_reversal(prices, dates, assets)
    components["ma_reversal_observed"] = ma_reversal
    components["ma_reversal_score_observed"] = panel_score(ma_reversal, dates, assets)

    rsi = rsi_reversal(weekly_log_returns, dates, assets)
    components["rsi_reversal_observed"] = rsi
    components["rsi_reversal_score_observed"] = panel_score(rsi, dates, assets)

    volatility = rolling_std(weekly_log_returns, dates, assets, window=26, min_periods=13)
    low_volatility = negate(volatility, dates, assets)
    components["low_volatility_observed"] = low_volatility
    components["low_volatility_score_observed"] = panel_score(low_volatility, dates, assets)

    resilience = drawdown_resilience(prices, dates, assets)
    components["drawdown_resilience_observed"] = resilience
    components["drawdown_resilience_score_observed"] = panel_score(resilience, dates, assets)

    absolute_return_26w = trailing_return(prices, dates, assets, lookback=26, skip=0)
    defensive_quality = empty_panel(dates, assets)
    for day in dates:
        for asset in assets:
            low_vol = components["low_volatility_score_observed"][day][asset]
            resilient = components["drawdown_resilience_score_observed"][day][asset]
            trend = absolute_return_26w[day][asset]
            if low_vol is not None and resilient is not None and trend is not None:
                defensive_quality[day][asset] = (
                    (float(low_vol) + float(resilient)) / 2.0 if float(trend) > 0.0 else -1.0
                )
    components["defensive_quality_gated_observed"] = defensive_quality

    close_prices = weekly_close_prices(prices_path, dates=dates, assets=assets)
    distribution_yield = trailing_distribution_yield(
        actions_path=actions_path, dates=dates, assets=assets, close_prices=close_prices
    )
    components["distribution_yield_observed"] = distribution_yield
    components["distribution_yield_score_observed"] = panel_score(distribution_yield, dates, assets)

    observed_scores = {
        "reversal_4w": components["reversal_4w_score_observed"],
        "ma_reversal": components["ma_reversal_score_observed"],
        "rsi_reversal": components["rsi_reversal_score_observed"],
        "low_volatility": components["low_volatility_score_observed"],
        "drawdown_resilience": components["drawdown_resilience_score_observed"],
        "defensive_quality_gated": components["defensive_quality_gated_observed"],
        "distribution_yield": components["distribution_yield_score_observed"],
    }
    tradable = {name: shift_panel(panel, dates, assets) for name, panel in observed_scores.items()}
    with actions_path.open(encoding="utf-8", newline="") as handle:
        distribution_events_used = sum(
            1 for row in csv.DictReader(handle)
            if row["ticker"] in assets and row["action_type"] == "cash_distribution"
        )
    audit = {
        "signal_lag_weeks": 1,
        "distribution_events_used": distribution_events_used,
        "distribution_history_knowledge_limitation": (
            "event dates are used causally, but the free Yahoo action history was acquired as one current vintage "
            "and is not a historically archived point-in-time feed"
        ),
    }
    return tradable, components, audit
