"""Causal helpers for the official-Treasury term-structure challenger."""

from __future__ import annotations

import math
import statistics
import xml.etree.ElementTree as ET
from bisect import bisect_right
from datetime import date, timedelta


MATURITY_FIELDS = {
    "1Y": "BC_1YEAR",
    "2Y": "BC_2YEAR",
    "7Y": "BC_7YEAR",
    "10Y": "BC_10YEAR",
    "20Y": "BC_20YEAR",
}
ASSETS = ("SHY", "IEF", "TLT")


def parse_treasury_xml(payload: bytes) -> list[dict[str, float | str]]:
    """Parse Treasury's Atom XML feed into unique, date-sorted curve rows."""
    root = ET.fromstring(payload)
    namespace = {
        "atom": "http://www.w3.org/2005/Atom",
        "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
    }
    by_date: dict[str, dict[str, float | str]] = {}
    for properties in root.findall("atom:entry/atom:content/m:properties", namespace):
        raw_date = properties.find("d:NEW_DATE", namespace)
        if raw_date is None or not raw_date.text:
            continue
        day = raw_date.text[:10]
        row: dict[str, float | str] = {"observation_date": day}
        complete = True
        for label, field in MATURITY_FIELDS.items():
            node = properties.find(f"d:{field}", namespace)
            if node is None or not node.text:
                complete = False
                break
            value = float(node.text)
            if not math.isfinite(value):
                complete = False
                break
            row[label] = value
        if complete:
            by_date[day] = row
    return [by_date[day] for day in sorted(by_date)]


def latest_curve_with_full_week_lag(
    curves: list[dict[str, float | str]], decision_date: str
) -> dict[str, float | str] | None:
    """Return the last curve dated no later than seven days before decision."""
    days = [str(row["observation_date"]) for row in curves]
    cutoff = (date.fromisoformat(decision_date) - timedelta(days=7)).isoformat()
    index = bisect_right(days, cutoff) - 1
    return curves[index] if index >= 0 else None


def carry_roll_scores(curve: dict[str, float | str]) -> dict[str, float]:
    """Fixed ex-ante yield-plus-roll-down proxies, in annual percentage points."""
    y1, y2 = float(curve["1Y"]), float(curve["2Y"])
    y7, y10, y20 = float(curve["7Y"]), float(curve["10Y"]), float(curve["20Y"])
    return {
        "SHY": y2 + 1.9 * (y2 - y1),
        "IEF": y10 + 7.5 * (y10 - y7),
        "TLT": y20 + 15.0 * (y20 - y10),
    }


def target_weights(method: str, curve: dict[str, float | str]) -> dict[str, float]:
    if method == "equal_weight":
        return {asset: 1.0 / len(ASSETS) for asset in ASSETS}
    if method == "carry_roll":
        scores = carry_roll_scores(curve)
        selected = max(ASSETS, key=lambda asset: (scores[asset], asset))
        return {asset: float(asset == selected) for asset in ASSETS}
    if method == "slope_regime":
        selected = "TLT" if float(curve["10Y"]) > float(curve["2Y"]) else "SHY"
        return {asset: float(asset == selected) for asset in ASSETS}
    raise ValueError(f"unknown term-structure method: {method}")


def monthly_rebalance(day: str, previous_day: str | None) -> bool:
    return previous_day is None or day[:7] != previous_day[:7]


def correlation(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation requires equal series with at least two observations")
    left_mean, right_mean = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    denominator = math.sqrt(
        sum((x - left_mean) ** 2 for x in left) * sum((y - right_mean) ** 2 for y in right)
    )
    return numerator / denominator if denominator else 0.0
