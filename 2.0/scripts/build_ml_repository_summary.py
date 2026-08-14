#!/usr/bin/env python3
"""Combine ML repository execution with the common nested validation bar."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTION = ROOT / "evidence/challenger_program_v1/python_execution"
OUTPUT = ROOT / "evidence/ml_sandbox_batch_12/repository_summary.json"
INSTALLABLE = ("ast-0006", "ast-0076", "ast-0186")


def main() -> int:
    attempts = []
    for path in sorted(EXECUTION.glob("ast-*.json")):
        if not any(path.name.startswith(entry_id) for entry_id in INSTALLABLE):
            continue
        row = json.loads(path.read_text(encoding="utf-8"))
        attempts.append({
            "entry_id": row["entry_id"], "status": row["status"],
            "install_exit_code": row["install_exit_code"], "test_exit_code": row["test_exit_code"],
            "install_seconds": row["install_seconds"], "test_seconds": row["test_seconds"],
            "started_at": row["started_at"], "evidence_file": str(path.relative_to(ROOT)),
        })
    latest = {}
    for entry_id in INSTALLABLE:
        rows = [row for row in attempts if row["entry_id"] == entry_id]
        latest[entry_id] = max(rows, key=lambda row: row["started_at"]) if rows else None
    common = json.loads((ROOT / "evidence/ml_sandbox_batch_12/result.json").read_text(encoding="utf-8"))
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "track": "machine_learning_sandbox",
        "repository_attempts": attempts,
        "latest_attempt_by_repository": latest,
        "finclaw": {
            "entry_id": "ast-0011", "status": "blocked_source_quality_gate",
            "tracked_files": 6, "dependency_manifests": 0, "test_indicators": 0,
            "license": "MISSING",
            "decision": "do_not_execute_or_incorporate_until_packaging_tests_and_license_exist",
        },
        "common_nested_bar": {
            "outer_folds": common["outer_fold_count"], "test_observations": common["test_observations"],
            "hyperparameter_fits_including_shuffle": common["total_hyperparameter_fits_including_shuffle"],
            "ml_beats_baseline": common["ml_beats_baseline_sharpe_at_10bps"],
            "shuffle_control_pass": common["shuffle_control_is_not_better_than_real_model"],
        },
        "external_repository_alpha_accepted": False,
        "status": "repository_capability_review_complete_no_ml_promotion",
        "reason": "Framework installation or upstream tests cannot substitute for beating the same causal nested walk-forward portfolio baseline.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"latest_status": {key: value["status"] if value else "missing" for key, value in latest.items()}, "finclaw": result["finclaw"]["status"], "ml_promoted": False}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
