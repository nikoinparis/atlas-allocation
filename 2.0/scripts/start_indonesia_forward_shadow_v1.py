#!/usr/bin/env python3
"""Freeze the first Indonesia research target into a forward-only ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REHEARSAL_ROOT = ROOT / "evidence" / "indonesia_current_rehearsal_v1"
OUTPUT = ROOT / "data" / "indonesia_forward_shadow_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    run_id = (REHEARSAL_ROOT / "LATEST").read_text(encoding="utf-8").strip()
    source = REHEARSAL_ROOT / run_id
    source_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if any(
        source_manifest["claims"][name]
        for name in ("historical_backtest", "investment_recommendation", "execution_authorized")
    ):
        raise ValueError("source rehearsal is not a research-only snapshot")
    target = pd.read_csv(source / "research_target.csv")
    decision_id = "IDN-SHADOW-2026-08-22-001"
    decisions = target.copy()
    decisions.insert(0, "decision_id", decision_id)
    decisions["decision_at"] = source_manifest["decision_at"]
    decisions["effective_session"] = "2026-08-24"
    decisions["source_rehearsal"] = run_id
    decisions["status"] = "frozen_awaiting_first_forward_observation"
    decisions["execution_authorized"] = False
    decisions["research_only"] = True

    OUTPUT.mkdir(parents=True, exist_ok=True)
    decisions_path = OUTPUT / "decisions.csv"
    if decisions_path.exists():
        existing = pd.read_csv(decisions_path)
        if decision_id in set(existing["decision_id"]):
            raise FileExistsError(f"forward decision already frozen: {decision_id}")
        decisions = pd.concat([existing, decisions], ignore_index=True)
    decisions.to_csv(decisions_path, index=False)
    observations_path = OUTPUT / "observations.csv"
    if not observations_path.exists():
        pd.DataFrame(
            columns=[
                "decision_id",
                "observation_date",
                "knowledge_at_utc",
                "ticker",
                "adjusted_close",
                "source_id",
                "recorded_at_utc",
            ]
        ).to_csv(observations_path, index=False)
    readme = """# Indonesia Forward Shadow v1

Forward-only research ledger. Decisions are immutable after their timestamp.
Future observations may be appended only when acquired; no historical price is
allowed to masquerade as forward evidence. This ledger does not authorize a
broker order, recommendation, or performance claim.
"""
    (OUTPUT / "README.md").write_text(readme, encoding="utf-8")
    manifest = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "untouched forward evidence for Indonesia research sleeve",
        "source_rehearsal": run_id,
        "source_manifest_sha256": sha256(source / "manifest.json"),
        "decision_ids": sorted(set(decisions["decision_id"])),
        "observation_rows": sum(1 for _ in observations_path.open(encoding="utf-8")) - 1,
        "claims": {
            "forward_only": True,
            "returns_calculated": False,
            "performance_claim_authorized": False,
            "investment_recommendation": False,
            "execution_authorized": False,
        },
        "files": {
            name: {"bytes": (OUTPUT / name).stat().st_size, "sha256": sha256(OUTPUT / name)}
            for name in ("decisions.csv", "observations.csv", "README.md")
        },
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
