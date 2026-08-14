"""Prepare completed Friday data from normalized immutable daily snapshots."""

from __future__ import annotations

import csv
import math
from datetime import date, timedelta
from pathlib import Path

from .data_vintage import DataVintageError


Panel = dict[str, dict[str, float | None]]


def friday_label(day: date) -> date:
    return day + timedelta(days=(4 - day.weekday()) % 7)


def prepare_weekly_adjusted_prices(
    prices_path: Path,
    *,
    observed_at_date: date,
    start_date: date,
    expected_symbols: list[str],
) -> tuple[list[str], Panel, dict[str, object]]:
    selected: dict[tuple[date, str], tuple[date, float]] = {}
    with prices_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = row["ticker"]
            if ticker not in expected_symbols:
                continue
            observation = date.fromisoformat(row["observation_date"])
            week = friday_label(observation)
            if week < start_date or week > observed_at_date:
                continue
            value = float(row["adjusted_close"])
            if not math.isfinite(value) or value <= 0.0:
                raise DataVintageError(f"invalid adjusted price for {ticker} on {observation}")
            key = (week, ticker)
            if key not in selected or observation > selected[key][0]:
                selected[key] = (observation, value)

    if not selected:
        raise DataVintageError("no completed weekly prices were prepared")
    first_week = min(week for week, _ in selected)
    last_week = max(week for week, _ in selected)
    dates = []
    current = first_week
    while current <= last_week:
        dates.append(current.isoformat())
        current += timedelta(days=7)
    panel: Panel = {
        day: {
            ticker: selected.get((date.fromisoformat(day), ticker), (None, None))[1]
            for ticker in expected_symbols
        }
        for day in dates
    }
    missing_cells = sum(value is None for row in panel.values() for value in row.values())
    return dates, panel, {
        "weekly_start": dates[0],
        "weekly_end": dates[-1],
        "completed_weeks": len(dates),
        "symbols": len(expected_symbols),
        "missing_cells": missing_cells,
        "source_daily_rows_selected": len(selected),
        "friday_label_uses_last_available_observation": True,
    }


def weekly_log_returns(dates: list[str], assets: list[str], prices: Panel) -> Panel:
    result: Panel = {day: {asset: None for asset in assets} for day in dates}
    for index in range(1, len(dates)):
        day, previous = dates[index], dates[index - 1]
        for asset in assets:
            current_price, previous_price = prices[day][asset], prices[previous][asset]
            if current_price is not None and previous_price is not None and previous_price > 0.0:
                result[day][asset] = math.log(current_price / previous_price)
    return result
