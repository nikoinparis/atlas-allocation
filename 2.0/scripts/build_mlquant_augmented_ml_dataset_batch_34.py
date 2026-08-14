#!/usr/bin/env python3
"""Join qualified repository factors onto the frozen Batch 16 ML rows."""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "config/mlquant_walk_forward_feature_program_v1.json"
OUTPUT = ROOT / "evidence/mlquant_walk_forward_feature_batch_34"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    base_path = ROOT / program["source"]["base_dataset"]
    factor_path = ROOT / program["source"]["factor_panel"]
    if sha256(base_path) != program["source"]["base_dataset_sha256"] or sha256(factor_path) != program["source"]["factor_panel_sha256"]:
        raise RuntimeError("pinned dataset input changed")
    factors: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for row in read_csv(factor_path):
        if row["joint_valid"].lower() == "true":
            factors[row["ticker"]].append((row["date"], float(row["best_002"]), float(row["original_001"])))
    factor_dates = {asset: [row[0] for row in values] for asset, values in factors.items()}
    output_rows = []
    dropped = 0
    timing_violations = 0
    maximum_factor_lag_days = 0
    for row in read_csv(base_path):
        asset, cutoff = row["asset"], row["feature_asof_date"]
        dates = factor_dates.get(asset, [])
        index = bisect.bisect_right(dates, cutoff) - 1
        if index < 0:
            dropped += 1
            continue
        factor_date, best, original = factors[asset][index]
        timing_violations += factor_date > cutoff
        joined = dict(row)
        joined.update({
            "mlquant_factor_asof_date": factor_date,
            "mlquant_best_002": best,
            "mlquant_original_001": original,
        })
        output_rows.append(joined)
    if timing_violations:
        raise RuntimeError("repository factor timing violation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = OUTPUT / "matched_augmented_factor_dataset.csv"
    with dataset.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader(); writer.writerows(output_rows)
    audit = {
        "program_sha256": sha256(PROGRAM), "base_dataset_sha256": sha256(base_path),
        "factor_panel_sha256": sha256(factor_path), "output_dataset_sha256": sha256(dataset),
        "base_rows": len(read_csv(base_path)), "matched_rows": len(output_rows), "dropped_rows": dropped,
        "timing_violations": timing_violations,
        "first_decision": min(row["decision_date"] for row in output_rows),
        "last_decision": max(row["decision_date"] for row in output_rows),
        "minimum_assets_per_decision": min(
            sum(other["decision_date"] == day for other in output_rows)
            for day in {row["decision_date"] for row in output_rows}
        ),
    }
    (OUTPUT / "dataset_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
