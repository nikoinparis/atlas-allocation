#!/usr/bin/env python3
"""Export the two qualified mlquant factors across the full frozen ETF universe."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from mlquant.features import compute_legacy_set

sys.path.insert(0, "/project")
from scripts.export_mlquant_factors_batch_30 import load_panel


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    program = json.loads(args.program.read_text(encoding="utf-8"))
    source = program["source"]
    universe_path = Path("/project") / source["universe_file"]
    if sha256(universe_path) != source["universe_file_sha256"]:
        raise RuntimeError("frozen universe changed")
    universe = sorted(json.loads(universe_path.read_text(encoding="utf-8"))["symbols"])
    prices = Path("/project") / source["prices"]
    panel, coverage = load_panel(prices, universe)
    names = tuple(source["qualified_factors"])
    factor_values, factor_mask, returned = compute_legacy_set(panel, names=names)
    if returned != list(names):
        raise RuntimeError("repository returned factors in an unexpected order")
    values = factor_values.detach().cpu().numpy().astype(np.float64)
    valid = factor_mask.detach().cpu().numpy()
    close = panel.close.detach().cpu().numpy().astype(np.float64)
    dates = panel.dates.astype("datetime64[D]").astype(str)
    args.output.mkdir(parents=True, exist_ok=True)
    factor_path = args.output / "full_universe_factor_panel.csv"
    with factor_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "ticker", "adjusted_close", "joint_valid", *names])
        writer.writeheader()
        for t, day in enumerate(dates):
            for n, ticker in enumerate(universe):
                writer.writerow({
                    "date": day,
                    "ticker": ticker,
                    "adjusted_close": close[t, n],
                    "joint_valid": bool(valid[t, n]),
                    names[0]: values[t, n, 0],
                    names[1]: values[t, n, 1],
                })
    metadata = {
        "program_sha256": sha256(args.program),
        "prices_sha256": sha256(prices),
        "universe_sha256": sha256(universe_path),
        "factor_panel_sha256": sha256(factor_path),
        "panel_dates": panel.n_dates,
        "panel_assets": panel.n_stocks,
        "universe": universe,
        "selected_factors": list(names),
        "joint_valid_cells": int(valid.sum()),
        "coverage": coverage,
    }
    (args.output / "factor_export_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
