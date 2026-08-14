"""Small, dependency-free helpers for point-in-time portfolio reconstruction."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


CASH_ASSET = "cash::USD"


@dataclass(frozen=True)
class SignalSpec:
    name: str
    file_name: str
    observed_column: str
    tradable_column: str


def optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite numeric input")
    return parsed


def read_wide_panel(path: Path, *, log_returns: bool = False) -> tuple[list[str], list[str], dict[str, dict[str, float | None]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assets = [column for column in (reader.fieldnames or []) if column != "Date"]
        rows: dict[str, dict[str, float | None]] = {}
        for row in reader:
            values: dict[str, float | None] = {}
            for asset in assets:
                value = optional_float(row.get(asset))
                values[asset] = math.expm1(value) if log_returns and value is not None else value
            rows[row["Date"]] = values
    return list(rows), assets, rows


def read_signal_panel(path: Path, spec: SignalSpec) -> tuple[dict[str, dict[str, float | None]], dict[str, int | float]]:
    observed_by_asset: dict[str, list[tuple[str, float | None, float | None]]] = defaultdict(list)
    panel: dict[str, dict[str, float | None]] = defaultdict(dict)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            decision = row["Date"]
            asset = row["Ticker"]
            observed = optional_float(row.get(spec.observed_column))
            tradable = optional_float(row.get(spec.tradable_column))
            observed_by_asset[asset].append((decision, observed, tradable))
            panel[decision][asset] = tradable

    comparisons = 0
    mismatches = 0
    max_error = 0.0
    missingness_mismatches = 0
    for rows in observed_by_asset.values():
        rows.sort(key=lambda item: item[0])
        previous: float | None = None
        for _, observed, tradable in rows:
            if previous is None or tradable is None:
                if previous is not tradable:
                    missingness_mismatches += 1
            else:
                comparisons += 1
                error = abs(previous - tradable)
                max_error = max(max_error, error)
                mismatches += error > 1e-12
            previous = observed
    return dict(panel), {
        "numeric_comparisons": comparisons,
        "numeric_mismatches": mismatches,
        "missingness_mismatches": missingness_mismatches,
        "max_lag_error": max_error,
        "lag_one_reconciliation_pass": mismatches == 0 and missingness_mismatches == 0,
    }


def combine_and_smooth(
    dates: list[str], assets: list[str], panels: list[dict[str, dict[str, float | None]]], window: int
) -> dict[str, dict[str, float | None]]:
    raw: dict[str, dict[str, float | None]] = {}
    for decision in dates:
        raw[decision] = {}
        for asset in assets:
            values = [panel.get(decision, {}).get(asset) for panel in panels]
            available = [value for value in values if value is not None]
            raw[decision][asset] = sum(available) / len(available) if available else None

    smoothed: dict[str, dict[str, float | None]] = {}
    for index, decision in enumerate(dates):
        smoothed[decision] = {}
        recent_dates = dates[max(0, index - window + 1) : index + 1]
        for asset in assets:
            available = [raw[item][asset] for item in recent_dates if raw[item][asset] is not None]
            smoothed[decision][asset] = sum(available) / len(available) if available else None
    return smoothed


def monthly_rebalance_dates(dates: list[str], *, include_sample_endpoint: bool = True) -> set[str]:
    result: set[str] = set()
    for index, decision in enumerate(dates):
        current = date.fromisoformat(decision)
        if index == 0:
            result.add(decision)
        elif index < len(dates) - 1 and date.fromisoformat(dates[index + 1]).month != current.month:
            result.add(decision)
        elif index == len(dates) - 1 and (
            include_sample_endpoint or (current + timedelta(days=7)).month != current.month
        ):
            result.add(decision)
    return result


def build_monthly_top_n_weights(
    *,
    dates: list[str],
    assets: list[str],
    scores: dict[str, dict[str, float | None]],
    prices: dict[str, dict[str, float | None]],
    top_n: int,
    min_signal: float,
    defensive_asset: str,
    include_sample_endpoint_rebalance: bool = True,
) -> tuple[dict[str, dict[str, float]], set[str]]:
    rebalance_dates = monthly_rebalance_dates(
        dates, include_sample_endpoint=include_sample_endpoint_rebalance
    )
    columns = assets + [defensive_asset, CASH_ASSET]
    current = {asset: 0.0 for asset in columns}
    result: dict[str, dict[str, float]] = {}
    asset_order = {asset: index for index, asset in enumerate(assets)}
    for decision in dates:
        if decision in rebalance_dates:
            current = {asset: 0.0 for asset in columns}
            candidates = [
                (float(score), asset)
                for asset, score in scores[decision].items()
                if score is not None
                and score > min_signal
                and prices.get(decision, {}).get(asset) is not None
            ]
            candidates.sort(key=lambda item: (-item[0], asset_order[item[1]]))
            selected = candidates[:top_n]
            for _, asset in selected:
                current[asset] = 1.0 / top_n
            remainder = 1.0 - len(selected) / top_n
            if remainder > 0.0:
                destination = (
                    defensive_asset
                    if prices.get(decision, {}).get(defensive_asset) is not None
                    else CASH_ASSET
                )
                current[destination] = remainder
        result[decision] = dict(current)
    return result, rebalance_dates


def compute_path(
    dates: list[str],
    weights: dict[str, dict[str, float]],
    simple_returns: dict[str, dict[str, float | None]],
    *,
    cost_bps: float,
) -> tuple[list[dict[str, float | str]], dict[str, int | float | bool]]:
    periods: list[dict[str, float | str]] = []
    previous: dict[str, float] | None = None
    wealth = 1.0
    peak = 1.0
    unpriced_events = 0
    max_weight_sum_error = 0.0
    max_cost_error = 0.0
    for index, decision in enumerate(dates[:-1]):
        realization = dates[index + 1]
        row = weights[decision]
        max_weight_sum_error = max(max_weight_sum_error, abs(sum(row.values()) - 1.0))
        gross = 0.0
        for asset, weight in row.items():
            if asset == CASH_ASSET:
                asset_return = 0.0
            else:
                asset_return = simple_returns.get(realization, {}).get(asset)
                if asset_return is None:
                    if abs(weight) > 1e-12:
                        unpriced_events += 1
                    asset_return = 0.0
            gross += weight * asset_return
        turnover = 0.0 if previous is None else 0.5 * sum(
            abs(row.get(asset, 0.0) - previous.get(asset, 0.0)) for asset in set(row) | set(previous)
        )
        cost = turnover * cost_bps / 10_000.0
        net = gross - cost
        max_cost_error = max(max_cost_error, abs(net - (gross - cost)))
        wealth *= 1.0 + net
        peak = max(peak, wealth)
        periods.append({
            "decision_date": decision,
            "realization_date": realization,
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": wealth / peak - 1.0,
        })
        previous = row
    return periods, {
        "periods": len(periods),
        "unpriced_exposure_events": unpriced_events,
        "unpriced_exposure_pass": unpriced_events == 0,
        "max_weight_sum_error": max_weight_sum_error,
        "fully_invested_pass": max_weight_sum_error <= 1e-12,
        "max_cost_identity_error": max_cost_error,
        "cost_identity_pass": max_cost_error <= 1e-15,
    }
