#!/usr/bin/env python3
"""Summarize every portfolio-library attempt and choose no strategy winner."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "evidence/portfolio_libraries_batch_11/capability_probes"
OUTPUT = ROOT / "evidence/portfolio_libraries_batch_11/result.json"
ENTRY_IDS = ("ast-0183", "ast-0184", "ast-0185", "ast-0187")


def main() -> int:
    attempts = []
    for path in sorted(PROBES.glob("ast-*.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        row = {key: value for key, value in row.items() if key not in {"install_log", "probe_log"}}
        row["evidence_file"] = str(path.relative_to(ROOT))
        attempts.append(row)
    latest = {}
    for entry_id in ENTRY_IDS:
        rows = [row for row in attempts if row["entry_id"] == entry_id]
        latest[entry_id] = max(rows, key=lambda row: str(row["started_at"])) if rows else None
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 11,
        "track": "portfolio_libraries",
        "attempt_count": len(attempts),
        "all_attempts": attempts,
        "latest_attempt_by_repository": latest,
        "identical_synthetic_return_panel": True,
        "common_constraints": {"long_only": True, "fully_invested": True, "maximum_asset_weight": 0.35},
        "strategy_alpha_claim": False,
        "portfolio_winner_selected": False,
        "decisions": {
            "ast-0183": "sandbox_reference_only_gpl",
            "ast-0184": "eligible_research_library_after_minimal_install",
            "ast-0185": "eligible_only_if_explicit_bounds_are_enforced_and_rechecked",
            "ast-0187": "eligible_research_library_with_pinned_dependencies; HRP compatibility issue remains",
        },
        "status": "capability_comparison_complete_no_baseline_replacement",
        "reason": "Library agreement and capability are engineering evidence; they do not create an independent return source or justify changing frozen v1.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"attempt_count": len(attempts), "latest_status": {key: value["status"] if value else "missing" for key, value in latest.items()}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
