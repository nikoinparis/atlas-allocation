#!/usr/bin/env python3
"""Execute pinned mlquant factors against the immutable ETF snapshot.

This file is intentionally run inside the qualified Podman image. It produces
factor diagnostics and daily rank-IC observations; it does not trade or select
factors.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch

from mlquant.data import Panel
from mlquant.features import LEGACY_REGISTRY, compute_legacy_set


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        ranks[order[start:end]] = (start + end - 1) / 2.0 + 1.0
        start = end
    return ranks


def spearman(values: np.ndarray, returns: np.ndarray, valid: np.ndarray, minimum: int) -> tuple[float, int]:
    keep = valid & np.isfinite(values) & np.isfinite(returns)
    count = int(keep.sum())
    if count < minimum:
        return math.nan, count
    x = average_ranks(values[keep])
    y = average_ranks(returns[keep])
    if np.std(x) == 0.0 or np.std(y) == 0.0:
        return math.nan, count
    return float(np.corrcoef(x, y)[0, 1]), count


def load_panel(path: Path, universe: list[str]) -> tuple[Panel, list[dict[str, object]]]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] in universe:
                rows.append(row)
    dates = sorted({row["observation_date"] for row in rows})
    date_index = {value: index for index, value in enumerate(dates)}
    asset_index = {value: index for index, value in enumerate(universe)}
    shape = (len(dates), len(universe))
    arrays = {name: np.zeros(shape, dtype=np.float32) for name in ("open", "high", "low", "close", "volume", "vwap")}
    mask = np.zeros(shape, dtype=bool)

    for row in rows:
        t, n = date_index[row["observation_date"]], asset_index[row["ticker"]]
        try:
            raw_close = float(row["close"])
            adjusted_close = float(row["adjusted_close"])
            ratio = adjusted_close / raw_close
            adjusted_open = float(row["open"]) * ratio
            adjusted_high = float(row["high"]) * ratio
            adjusted_low = float(row["low"]) * ratio
            volume = float(row["volume"])
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        values = (adjusted_open, adjusted_high, adjusted_low, adjusted_close, volume)
        valid = (
            all(math.isfinite(value) for value in values)
            and min(adjusted_open, adjusted_high, adjusted_low, adjusted_close) > 0.0
            and volume >= 0.0
            and adjusted_high >= max(adjusted_open, adjusted_low, adjusted_close)
            and adjusted_low <= min(adjusted_open, adjusted_high, adjusted_close)
        )
        if not valid:
            continue
        arrays["open"][t, n] = adjusted_open
        arrays["high"][t, n] = adjusted_high
        arrays["low"][t, n] = adjusted_low
        arrays["close"][t, n] = adjusted_close
        arrays["volume"][t, n] = volume
        arrays["vwap"][t, n] = (adjusted_high + adjusted_low + adjusted_close) / 3.0
        mask[t, n] = True

    fields = {name: torch.from_numpy(values) for name, values in arrays.items()}
    panel = Panel.from_tensors(
        dates=np.asarray(dates, dtype="datetime64[D]"),
        stocks=np.asarray(universe),
        fields=fields,
        mask=torch.from_numpy(mask),
    )
    panel.assert_consistent()
    coverage = []
    for index, ticker in enumerate(universe):
        valid_dates = np.flatnonzero(mask[:, index])
        coverage.append({
            "ticker": ticker,
            "observations": int(valid_dates.size),
            "first_date": dates[int(valid_dates[0])] if valid_dates.size else "",
            "last_date": dates[int(valid_dates[-1])] if valid_dates.size else "",
            "panel_date_coverage": float(valid_dates.size / len(dates)),
        })
    return panel, coverage


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"no rows for {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    program = json.loads(args.program.read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)

    prices = Path("/project") / program["source_snapshot"]["prices"]
    panel, coverage = load_panel(prices, program["universe"])
    write_csv(args.output / "asset_coverage.csv", coverage)

    all_audit = []
    for name in sorted(LEGACY_REGISTRY):
        try:
            values, valid = LEGACY_REGISTRY[name](panel)
            finite = torch.isfinite(values)
            usable = valid & finite
            all_audit.append({
                "factor": name,
                "status": "pass",
                "valid_cells": int(usable.sum().item()),
                "valid_dates_minimum_5_assets": int((usable.sum(dim=1) >= 5).sum().item()),
                "nonfinite_valid_cells": int((valid & ~finite).sum().item()),
                "error": "",
            })
        except Exception as exc:
            all_audit.append({
                "factor": name, "status": "fail", "valid_cells": 0,
                "valid_dates_minimum_5_assets": 0, "nonfinite_valid_cells": 0,
                "error": f"{type(exc).__name__}: {exc}",
            })
    write_csv(args.output / "all_factor_audit.csv", all_audit)

    names = tuple(program["source_preselected_factors"])
    factor_values, factor_mask, returned_names = compute_legacy_set(panel, names=names)
    if returned_names != list(names):
        raise RuntimeError("repository returned factors in an unexpected order")
    values = factor_values.detach().cpu().numpy().astype(np.float64)
    joint_mask = factor_mask.detach().cpu().numpy()
    close = panel.close.detach().cpu().numpy().astype(np.float64)
    tradable = panel.mask.detach().cpu().numpy()
    forward = np.zeros_like(close)
    np.divide(close[1:], close[:-1], out=forward[:-1], where=close[:-1] > 0.0)
    forward[:-1] -= 1.0
    forward[:-1][~(tradable[:-1] & tradable[1:])] = 0.0
    forward_mask = np.zeros_like(tradable)
    forward_mask[:-1] = tradable[:-1] & tradable[1:]

    rng = np.random.default_rng(int(program["controls"]["permutation_seed"]))
    asset_permutation = rng.permutation(panel.n_stocks)
    return_permutation = rng.permutation(panel.n_stocks)
    minimum = int(program["target"]["minimum_assets_per_date"])
    dates = panel.dates.astype("datetime64[D]").astype(str)
    daily_rows: list[dict[str, object]] = []
    for t, day in enumerate(dates):
        for factor_index, name in enumerate(names):
            base_valid = joint_mask[t] & forward_mask[t]
            variants: list[tuple[str, np.ndarray, np.ndarray, np.ndarray]] = [
                ("primary", values[t, :, factor_index], forward[t], base_valid),
                ("inverted", -values[t, :, factor_index], forward[t], base_valid),
                (
                    "asset_permutation", values[t, asset_permutation, factor_index], forward[t],
                    joint_mask[t, asset_permutation] & forward_mask[t],
                ),
                (
                    "return_permutation", values[t, :, factor_index], forward[t, return_permutation],
                    joint_mask[t] & forward_mask[t, return_permutation],
                ),
            ]
            for lag in program["controls"]["stale_sessions"]:
                lag = int(lag)
                if t >= lag:
                    variants.append((
                        f"stale_{lag}", values[t - lag, :, factor_index], forward[t],
                        joint_mask[t - lag] & forward_mask[t],
                    ))
                else:
                    variants.append((f"stale_{lag}", values[t, :, factor_index], forward[t], np.zeros(panel.n_stocks, dtype=bool)))
            for variant, factor_row, return_row, valid_row in variants:
                ic, asset_count = spearman(factor_row, return_row, valid_row, minimum)
                daily_rows.append({
                    "date": day, "factor": name, "variant": variant,
                    "rank_ic": "" if math.isnan(ic) else ic, "assets": asset_count,
                })
    write_csv(args.output / "daily_rank_ic.csv", daily_rows)
    metadata = {
        "program_sha256": sha256(args.program),
        "prices_sha256": sha256(prices),
        "panel_dates": panel.n_dates,
        "panel_assets": panel.n_stocks,
        "first_date": str(dates[0]),
        "last_date": str(dates[-1]),
        "registered_factor_count": len(LEGACY_REGISTRY),
        "selected_factors": list(names),
        "asset_permutation": asset_permutation.tolist(),
        "return_permutation": return_permutation.tolist(),
        "torch_version": torch.__version__,
    }
    (args.output / "export_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
