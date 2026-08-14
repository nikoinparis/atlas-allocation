#!/usr/bin/env python3
"""Export the two qualified repository factors for the Batch 31 portfolio test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, "/project")

from mlquant.features import compute_legacy_set
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
    factor_program = json.loads(Path("/project/config/mlquant_etf_factor_ic_program_v1.json").read_text(encoding="utf-8"))
    prices = Path("/project") / factor_program["source_snapshot"]["prices"]
    panel, _ = load_panel(prices, program["data"]["assets"])
    names = tuple(program["factors"]["names"])
    factors, joint_mask, returned = compute_legacy_set(panel, names=names)
    if returned != list(names):
        raise RuntimeError("unexpected factor order")
    values = factors.detach().cpu().numpy().astype(np.float64)
    valid = joint_mask.detach().cpu().numpy()
    close = panel.close.detach().cpu().numpy().astype(np.float64)
    dates = panel.dates.astype("datetime64[D]").astype(str)
    stocks = [str(value) for value in panel.stocks]
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "qualified_factor_panel.csv"
    with output.open("w", encoding="utf-8", newline="") as handle:
        columns = ["date", "ticker", "adjusted_close", "joint_valid", *names]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for t, day in enumerate(dates):
            if day < program["data"]["start_date"] or day > program["data"]["end_date"]:
                continue
            for n, ticker in enumerate(stocks):
                row = {
                    "date": day,
                    "ticker": ticker,
                    "adjusted_close": close[t, n] if close[t, n] > 0.0 else "",
                    "joint_valid": bool(valid[t, n]),
                }
                row.update({name: values[t, n, index] for index, name in enumerate(names)})
                writer.writerow(row)
    metadata = {
        "repository_commit": program["repository"]["commit"],
        "program_sha256": sha256(args.program),
        "factor_program_sha256": sha256(Path("/project/config/mlquant_etf_factor_ic_program_v1.json")),
        "prices_sha256": sha256(prices),
        "rows": sum(program["data"]["start_date"] <= day <= program["data"]["end_date"] for day in dates) * len(stocks),
        "factors": list(names),
        "first_date": max(program["data"]["start_date"], str(dates[0])),
        "last_date": min(program["data"]["end_date"], str(dates[-1])),
    }
    (args.output / "input_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
