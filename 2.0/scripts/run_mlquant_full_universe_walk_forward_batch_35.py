#!/usr/bin/env python3
"""Run the predeclared full-universe Batch 35 confirmation."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_mlquant_walk_forward_feature_batch_34 as engine

OUTPUT = ROOT / "evidence/mlquant_full_universe_walk_forward_batch_35"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    engine.PROGRAM = ROOT / "config/mlquant_full_universe_walk_forward_confirmation_v1.json"
    engine.INPUT = OUTPUT / "matched_augmented_factor_dataset.csv"
    engine.AUDIT = OUTPUT / "dataset_audit.json"
    engine.OUTPUT = OUTPUT
    engine.main()
    report = OUTPUT / "report.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace(
            "# Walk-forward ML repository-feature ablation — Batch 34",
            "# Full-universe walk-forward ML repository-feature confirmation — Batch 35",
        ),
        encoding="utf-8",
    )
    result = json.loads((OUTPUT / "result.json").read_text(encoding="utf-8"))
    result["final_confirmation"] = True
    result["track_closed_historically"] = not (
        result["gates"]["rank_ic"] and result["gates"]["portfolio_10bps"]
    )
    result["track_decision"] = (
        "continue_to_independent_structural_evidence"
        if not result["track_closed_historically"]
        else "close_as_historically_promising_but_unproven_without_further_same-history_tuning"
    )
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes_path = OUTPUT / "artifact_hashes.json"
    hashes = json.loads(hashes_path.read_text(encoding="utf-8"))
    hashes["factor_export_metadata.json"] = sha256(OUTPUT / "factor_export_metadata.json")
    hashes["full_universe_factor_panel.csv"] = sha256(OUTPUT / "full_universe_factor_panel.csv")
    hashes["result.json"] = sha256(OUTPUT / "result.json")
    hashes["report.md"] = sha256(report)
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
