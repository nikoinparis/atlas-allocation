"""Revision and freshness diagnostics for normalized price snapshots."""

from __future__ import annotations

import csv
import math
from datetime import date, datetime
from pathlib import Path

from .data_vintage import DataVintageError, SnapshotStore, parse_utc


def _price_rows(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {(row["observation_date"], row["security_id"]): row for row in csv.DictReader(handle)}


def compare_price_files(old_path: Path, new_path: Path, tolerance: float = 1e-10) -> dict[str, object]:
    old = _price_rows(old_path)
    new = _price_rows(new_path)
    common = set(old) & set(new)
    revised = []
    relative_thresholds = (1e-8, 1e-7, 1e-6, 1e-5, 1e-4, 1e-3)
    magnitude = {
        field: {
            "exact_change_count": 0,
            "maximum_absolute_difference": 0.0,
            "maximum_relative_difference": 0.0,
            "relative_change_counts": {f"over_{threshold:g}": 0 for threshold in relative_thresholds},
        }
        for field in ("adjusted_close", "close")
    }
    for key in sorted(common):
        changes = {}
        for field in ("adjusted_close", "close"):
            old_raw, new_raw = old[key].get(field, ""), new[key].get(field, "")
            if old_raw == "" or new_raw == "":
                if old_raw != new_raw:
                    changes[field] = {"old": old_raw, "new": new_raw}
                continue
            old_value, new_value = float(old_raw), float(new_raw)
            scale = max(1.0, abs(old_value), abs(new_value))
            absolute = abs(new_value - old_value)
            relative = absolute / max(abs(old_value), abs(new_value), 1e-300)
            if absolute > 0.0:
                magnitude[field]["exact_change_count"] += 1
            magnitude[field]["maximum_absolute_difference"] = max(
                magnitude[field]["maximum_absolute_difference"], absolute
            )
            magnitude[field]["maximum_relative_difference"] = max(
                magnitude[field]["maximum_relative_difference"], relative
            )
            for threshold in relative_thresholds:
                magnitude[field]["relative_change_counts"][f"over_{threshold:g}"] += relative > threshold
            if not math.isclose(old_value, new_value, rel_tol=tolerance, abs_tol=tolerance * scale):
                changes[field] = {"old": old_value, "new": new_value, "difference": new_value - old_value}
        if changes:
            revised.append({"observation_date": key[0], "security_id": key[1], "changes": changes})
    for summary in magnitude.values():
        summary["exact_change_share"] = summary["exact_change_count"] / len(common) if common else 0.0
        summary["relative_change_shares"] = {
            key: count / len(common) if common else 0.0
            for key, count in summary["relative_change_counts"].items()
        }
    return {
        "old_rows": len(old),
        "new_rows": len(new),
        "common_rows": len(common),
        "new_keys": len(set(new) - set(old)),
        "disappeared_keys": len(set(old) - set(new)),
        "revised_rows": len(revised),
        "revised_row_share": len(revised) / len(common) if common else 0.0,
        "magnitude_by_field": magnitude,
        "economically_material_relative_threshold": 1e-4,
        "economically_material_adjusted_close_rows": magnitude["adjusted_close"]["relative_change_counts"]["over_0.0001"],
        "sample_revisions": revised[:20],
    }


def compare_snapshots(store: SnapshotStore, old_snapshot_id: str, new_snapshot_id: str) -> dict[str, object]:
    old_manifest = next(item for item in store.manifests() if item["snapshot_id"] == old_snapshot_id)
    new_manifest = next(item for item in store.manifests() if item["snapshot_id"] == new_snapshot_id)
    if parse_utc(str(new_manifest["observed_at_utc"])) <= parse_utc(str(old_manifest["observed_at_utc"])):
        raise DataVintageError("new snapshot must have a later observation timestamp")
    store.verify(old_snapshot_id)
    store.verify(new_snapshot_id)
    comparison = compare_price_files(
        store.root / old_snapshot_id / "payload/prices.csv",
        store.root / new_snapshot_id / "payload/prices.csv",
    )
    comparison.update({"old_snapshot_id": old_snapshot_id, "new_snapshot_id": new_snapshot_id})
    return comparison


def snapshot_freshness(prices_path: Path, observed_at_utc: str, expected_symbols: set[str]) -> dict[str, object]:
    rows = _price_rows(prices_path)
    if not rows:
        raise DataVintageError("price snapshot is empty")
    latest_by_symbol: dict[str, date] = {}
    for (day, _), row in rows.items():
        ticker = row["ticker"]
        parsed = date.fromisoformat(day)
        latest_by_symbol[ticker] = max(latest_by_symbol.get(ticker, parsed), parsed)
    observed_date = parse_utc(observed_at_utc).date()
    stale_days = {ticker: (observed_date - latest).days for ticker, latest in latest_by_symbol.items()}
    missing = sorted(expected_symbols - set(latest_by_symbol))
    return {
        "expected_symbols": len(expected_symbols),
        "observed_symbols": len(latest_by_symbol),
        "missing_symbols": missing,
        "latest_observation_date": max(latest_by_symbol.values()).isoformat(),
        "maximum_calendar_staleness_days": max(stale_days.values()),
        "symbols_staler_than_7_days": sorted(ticker for ticker, days in stale_days.items() if days > 7),
        "freshness_pass": not missing and all(days <= 7 for days in stale_days.values()),
    }
