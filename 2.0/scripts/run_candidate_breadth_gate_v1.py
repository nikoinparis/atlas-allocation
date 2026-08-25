#!/usr/bin/env python3
"""Run the mandatory breadth gate for one candidate against all incumbents."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.ensemble import (  # noqa: E402
    breadth_admission_gate,
    correlation,
    fundamental_law_decomposition,
    weighted_holdings_overlap,
)


def _resolved(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _load_returns(path: Path, *, date_column: str, return_column: str) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or date_column not in rows[0] or return_column not in rows[0]:
        raise ValueError(f"invalid return file schema: {path}")
    result: dict[str, float] = {}
    for row in rows:
        day = str(row[date_column])
        if day in result:
            raise ValueError(f"duplicate return date {day} in {path}")
        result[day] = float(row[return_column])
    return result


def _load_holdings(path: Path, *, date_column: str, asset_column: str, weight_column: str) -> dict[str, dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or not {date_column, asset_column, weight_column}.issubset(rows[0]):
        raise ValueError(f"invalid holdings file schema: {path}")
    result: dict[str, dict[str, float]] = {}
    for row in rows:
        day, asset, weight = str(row[date_column]), str(row[asset_column]), float(row[weight_column])
        if asset in result.setdefault(day, {}):
            raise ValueError(f"duplicate holding {day}/{asset} in {path}")
        result[day][asset] = weight
    return result


def build(manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    members = [manifest["candidate"], *manifest["incumbents"]]
    names = [str(item["name"]) for item in members]
    if len(set(names)) != len(names) or not manifest["incumbents"]:
        raise ValueError("one unique candidate and at least one unique incumbent are required")
    returns = {
        str(item["name"]): _load_returns(
            _resolved(base, str(item["returns_csv"])),
            date_column=str(item.get("return_date_column", "realization_date")),
            return_column=str(item.get("return_column", "net_return")),
        )
        for item in members
    }
    common_return_dates = sorted(set.intersection(*(set(values) for values in returns.values())))
    minimum = int(manifest.get("minimum_common_return_observations", 52))
    if len(common_return_dates) < minimum:
        raise ValueError(f"only {len(common_return_dates)} common returns; {minimum} required")
    matrix = {
        left: {
            right: correlation(
                [returns[left][day] for day in common_return_dates],
                [returns[right][day] for day in common_return_dates],
            )
            for right in names
        }
        for left in names
    }
    holdings = {
        str(item["name"]): _load_holdings(
            _resolved(base, str(item["holdings_csv"])),
            date_column=str(item.get("holdings_date_column", "decision_date")),
            asset_column=str(item.get("asset_column", "asset")),
            weight_column=str(item.get("weight_column", "weight")),
        )
        for item in members
    }
    candidate = str(manifest["candidate"]["name"])
    overlap_by_peer: dict[str, float] = {}
    overlap_observations: dict[str, int] = {}
    for peer in names:
        if peer == candidate:
            continue
        dates = sorted(set(holdings[candidate]) & set(holdings[peer]))
        if not dates:
            raise ValueError(f"no common holdings dates for {candidate} and {peer}")
        overlap_by_peer[peer] = sum(
            weighted_holdings_overlap(holdings[candidate][day], holdings[peer][day])
            for day in dates
        ) / len(dates)
        overlap_observations[peer] = len(dates)
    gate = breadth_admission_gate(
        candidate=candidate,
        matrix=matrix,
        holdings_overlap_by_peer=overlap_by_peer,
        minimum_rounded_contribution=float(
            manifest.get("minimum_rounded_marginal_effective_breadth", 0.01)
        ),
        contribution_decimals=int(manifest.get("marginal_contribution_rounding_decimals", 2)),
    )
    decomposition = None
    if "information_coefficient" in manifest:
        decomposition = fundamental_law_decomposition(
            information_coefficient=float(manifest["information_coefficient"]),
            effective_breadth=float(gate["effective_breadth_with_candidate"]),
            transfer_coefficient=float(manifest.get("transfer_coefficient", 1.0)),
            realized_information_ratio=(
                None
                if "realized_information_ratio" not in manifest
                else float(manifest["realized_information_ratio"])
            ),
        )
    return {
        "program": "candidate_breadth_gate_v1",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "candidate": candidate,
        "incumbents": names[1:],
        "common_return_start": common_return_dates[0],
        "common_return_end": common_return_dates[-1],
        "common_return_observations": len(common_return_dates),
        "pairwise_return_correlation": matrix,
        "candidate_holdings_overlap_by_peer": overlap_by_peer,
        "holdings_overlap_observations_by_peer": overlap_observations,
        "breadth_gate": gate,
        "fundamental_law_decomposition": decomposition,
        "strategy_edge_proven": False,
        "live_trading_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("breadth evidence is immutable; choose a new output path")
    result = build(args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["breadth_gate"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
