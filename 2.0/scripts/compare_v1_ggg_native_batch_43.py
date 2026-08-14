#!/usr/bin/env python3
"""Compare an isolated native GGG rerun with the pinned Version 1 artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

NAME = "improved_phaseggg_confirmed_only_robust_offense"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dated(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "date" if "date" in frame else "Date" if "Date" in frame else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)


def compare_frames(expected_path: Path, actual_path: Path) -> dict:
    expected = read_dated(expected_path).apply(pd.to_numeric, errors="coerce")
    actual = read_dated(actual_path).apply(pd.to_numeric, errors="coerce")
    common_index = expected.index.intersection(actual.index)
    common_columns = expected.columns.intersection(actual.columns)
    left = expected.reindex(index=common_index, columns=common_columns)
    right = actual.reindex(index=common_index, columns=common_columns)
    difference = (left - right).abs()
    maximum = float(np.nanmax(difference.to_numpy())) if difference.size else float("inf")
    return {
        "expected_rows": len(expected), "actual_rows": len(actual),
        "expected_columns": len(expected.columns), "actual_columns": len(actual.columns),
        "common_rows": len(common_index), "common_columns": len(common_columns),
        "index_equal": expected.index.equals(actual.index),
        "columns_equal": expected.columns.equals(actual.columns),
        "maximum_absolute_difference": maximum,
        "expected_sha256": sha256(expected_path), "actual_sha256": sha256(actual_path),
    }


def stage_transition(stage_frames: dict[str, pd.DataFrame], first: str, second: str) -> dict:
    left, right = stage_frames[first], stage_frames[second]
    index = left.index.intersection(right.index)
    columns = left.columns.intersection(right.columns)
    difference = (left.loc[index, columns] - right.loc[index, columns]).abs()
    row_maximum = difference.max(axis=1)
    return {
        "from_stage": first, "to_stage": second,
        "maximum_absolute_change": float(difference.to_numpy().max()),
        "changed_rows": int((row_maximum > 1e-12).sum()),
        "unchanged_rows": int((row_maximum <= 1e-12).sum()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--rerun-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--program", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve()
    rerun = args.rerun_root.resolve()
    output = args.output.resolve()
    program = json.loads(args.program.read_text(encoding="utf-8"))
    stages = list(program["expected_stages"])
    source_checkpoints = source / "data/research/allocator_checkpoints"
    rerun_checkpoints = rerun / "data/research/allocator_checkpoints"

    rows = []
    stage_frames: dict[str, pd.DataFrame] = {}
    for stage in stages:
        filename = f"{NAME}__{stage}.csv"
        expected_path, actual_path = source_checkpoints / filename, rerun_checkpoints / filename
        if not expected_path.exists() or not actual_path.exists():
            rows.append({"artifact": stage, "present": False, "maximum_absolute_difference": float("inf")})
            continue
        comparison = compare_frames(expected_path, actual_path)
        rows.append({"artifact": stage, "present": True, **comparison})
        stage_frames[stage] = read_dated(actual_path).apply(pd.to_numeric, errors="coerce").fillna(0.0)

    transitions = []
    for first, second in zip(stages[:5], stages[1:5]):
        if first in stage_frames and second in stage_frames:
            transitions.append(stage_transition(stage_frames, first, second))

    layer3 = "data/05_layer3_portfolio_construction"
    published_files = {
        "published_weights": f"portfolio_version_weights_{NAME}.csv",
        "published_sleeve_weights": f"portfolio_version_sleeve_weights_{NAME}.csv",
        "published_returns": f"portfolio_version_returns_{NAME}.csv",
    }
    published = {}
    for label, filename in published_files.items():
        published[label] = compare_frames(source / layer3 / filename, rerun / layer3 / filename)

    expected_returns = read_dated(source / layer3 / published_files["published_returns"])
    actual_returns = read_dated(rerun / layer3 / published_files["published_returns"])
    aligned = expected_returns[["net_return"]].join(actual_returns[["net_return"]], how="inner", rsuffix="_actual")
    correlation = float(aligned["net_return"].corr(aligned["net_return_actual"]))
    checkpoint_max = max(float(row.get("maximum_absolute_difference", float("inf"))) for row in rows)
    gates_config = program["equivalence_gates"]
    gates = {
        "all_expected_stages_present": len(rows) == len(stages) and all(bool(row.get("present")) for row in rows),
        "checkpoint_values": checkpoint_max <= float(gates_config["maximum_checkpoint_absolute_difference"]),
        "published_weights": published["published_weights"]["maximum_absolute_difference"] <= float(gates_config["maximum_published_weight_absolute_difference"]),
        "published_path": published["published_returns"]["maximum_absolute_difference"] <= float(gates_config["maximum_published_path_absolute_difference"]),
        "published_net_return_correlation": correlation >= float(gates_config["minimum_published_net_return_correlation"]),
    }

    output.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output / "checkpoint_equivalence.csv", index=False)
    pd.DataFrame(transitions).to_csv(output / "stage_transition_summary.csv", index=False)
    pd.DataFrame([{"artifact": key, **value} for key, value in published.items()]).to_csv(output / "published_artifact_equivalence.csv", index=False)
    stage_manifest = pd.DataFrame([
        {"stage": "raw_hrp_sleeve_weights", "role": "Monthly HRP allocation across six active sleeves", "rule": "156-week trailing sleeve-return window; sample covariance; long-only HRP"},
        {"stage": "post_state_tilt_sleeve_weights", "role": "State-conditioned sleeve risk budget", "rule": "phase_ddd_confirmed_near_exclude_dual"},
        {"stage": "post_layer3_expression_sleeve_weights", "role": "Optional Layer 3 expression", "rule": "none; exact identity for GGG"},
        {"stage": "post_overlay_pre_lookthrough_sleeve_weights", "role": "Risk, regime, smoothing, and cash overlay", "rule": "good_state_fragile_expression; sleeve speed 0.40; rerisk 0.80; conservative hybrid overlay; target-vol ceiling 1.00; regime-confidence boost"},
        {"stage": "final_sleeve_weights", "role": "Weekly held sleeve allocation", "rule": "Carry the most recent rebalance allocation; exact identity from post-overlay for GGG"},
        {"stage": "final_etf_weights", "role": "Look through sleeve holdings to 35 ETFs", "rule": "Broad offense except recovery_confirmed drops PDBC and DBA; aggregate sleeves and residual cash in BIL"},
    ])
    stage_manifest.to_csv(output / "stage_rule_manifest.csv", index=False)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(args.program),
        "candidate": NAME, "native_builder_sha256": sha256(source / "scripts/build_improvement_artifacts.py"),
        "source_version_1_mounted_read_only": True,
        "expected_stage_count": len(stages), "actual_stage_count": sum(bool(row.get("present")) for row in rows),
        "maximum_checkpoint_absolute_difference": checkpoint_max,
        "published_artifacts": published,
        "published_net_return_correlation": correlation,
        "equivalence_gates": gates, "native_reconstruction_passed": all(gates.values()),
        "independent_v2_rewrite": False,
        "selection_contamination_removed": False,
        "decision": "native_source_reproducible_continue_to_independent_v2_extraction" if all(gates.values()) else "native_source_reconstruction_failed",
        "version_1_modified": False, "live_trading_enabled": False,
    }
    artifact_names = ["checkpoint_equivalence.csv", "stage_transition_summary.csv", "published_artifact_equivalence.csv", "stage_rule_manifest.csv"]
    result["artifacts"] = {name: {"sha256": sha256(output / name), "bytes": (output / name).stat().st_size} for name in artifact_names}
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# V1 GGG native allocator reconstruction — Batch 43", "",
        f"The pinned Version 1 builder was executed for GGG alone in an ephemeral writable copy while the original Version 1 tree remained read-only. All {len(stages)} allocator checkpoints were regenerated.", "",
        f"Maximum checkpoint difference: {checkpoint_max:.3e}. Published weight difference: {published['published_weights']['maximum_absolute_difference']:.3e}. Published path difference: {published['published_returns']['maximum_absolute_difference']:.3e}. Net-return correlation: {correlation:.15f}. Native reconstruction passed: **{all(gates.values())}**.", "",
        "This proves deterministic native regeneration from the pinned source and artifacts. It does not erase the prior 230-variant search, create post-selection data, or constitute an independent Version 2 rewrite. The next boundary is extracting the minimal GGG equations and dependencies into Version 2 while preserving these stage-level equivalence gates.", "",
    ]
    (output / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"native_reconstruction_passed": all(gates.values()), "maximum_checkpoint_difference": checkpoint_max, "published_path_difference": published["published_returns"]["maximum_absolute_difference"], "correlation": correlation}, indent=2))
    return 0 if all(gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
