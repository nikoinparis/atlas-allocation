#!/usr/bin/env python3
"""Join full-universe repository factors onto the frozen Batch 16 ML rows."""

from __future__ import annotations

import bisect
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "config/mlquant_full_universe_walk_forward_confirmation_v1.json"
OUTPUT = ROOT / "evidence/mlquant_full_universe_walk_forward_batch_35"


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
    source = program["source"]
    base_path = ROOT / source["base_dataset"]
    factor_path = ROOT / source["factor_panel"]
    export_metadata = json.loads((OUTPUT / "factor_export_metadata.json").read_text(encoding="utf-8"))
    if sha256(base_path) != source["base_dataset_sha256"]:
        raise RuntimeError("pinned base dataset changed")
    if sha256(factor_path) != export_metadata["factor_panel_sha256"]:
        raise RuntimeError("factor panel differs from its generation record")
    factors: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for row in read_csv(factor_path):
        if row["joint_valid"].lower() == "true":
            factors[row["ticker"]].append((row["date"], float(row["best_002"]), float(row["original_001"])))
    factor_dates = {asset: [row[0] for row in values] for asset, values in factors.items()}
    base_rows = read_csv(base_path)
    output_rows = []
    dropped = 0
    timing_violations = 0
    factor_lags = []
    for row in base_rows:
        asset, cutoff = row["asset"], row["feature_asof_date"]
        dates = factor_dates.get(asset, [])
        index = bisect.bisect_right(dates, cutoff) - 1
        if index < 0:
            dropped += 1
            continue
        factor_date, best, original = factors[asset][index]
        timing_violations += int(factor_date > cutoff)
        joined = dict(row)
        joined.update({"mlquant_factor_asof_date": factor_date, "mlquant_best_002": best, "mlquant_original_001": original})
        output_rows.append(joined)
    if timing_violations:
        raise RuntimeError("repository factor timing violation")
    if not output_rows:
        raise RuntimeError("no matched rows")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = OUTPUT / "matched_augmented_factor_dataset.csv"
    with dataset.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    counts = {}
    for row in output_rows:
        counts[row["decision_date"]] = counts.get(row["decision_date"], 0) + 1
    audit = {
        "program_sha256": sha256(PROGRAM),
        "base_dataset_sha256": sha256(base_path),
        "factor_panel_sha256": sha256(factor_path),
        "output_dataset_sha256": sha256(dataset),
        "base_rows": len(base_rows),
        "matched_rows": len(output_rows),
        "dropped_rows": dropped,
        "matched_assets": len({row["asset"] for row in output_rows}),
        "timing_violations": timing_violations,
        "first_decision": min(row["decision_date"] for row in output_rows),
        "last_decision": max(row["decision_date"] for row in output_rows),
        "minimum_assets_per_decision": min(counts.values()),
    }
    (OUTPUT / "dataset_audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
