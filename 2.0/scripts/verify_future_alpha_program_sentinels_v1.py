#!/usr/bin/env python3
"""Prove that the future-alpha program did not alter protected forward evidence."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "evidence/pre_future_alpha_program_manifest_v1/manifest.json"
OUTPUT = ROOT / "evidence/future_alpha_program_sentinel_verification_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    frozen = json.loads(FROZEN.read_text())
    rows = []
    for relative, expected in frozen["protected_forward_sentinels"].items():
        path = ROOT / relative
        actual_exists = path.exists()
        actual_hash = sha256(path) if actual_exists else None
        rows.append({"path": relative, "expected_exists": expected["exists"], "actual_exists": actual_exists,
                     "expected_sha256": expected["sha256"], "actual_sha256": actual_hash,
                     "matches": actual_exists == expected["exists"] and actual_hash == expected["sha256"]})
    result = {
        "experiment": "future_alpha_program_sentinel_verification_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protected_files": len(rows),
        "all_match": all(row["matches"] for row in rows),
        "failures": [row["path"] for row in rows if not row["matches"]],
        "rows": rows,
        "forward_evidence_mutated": not all(row["matches"] for row in rows),
        "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: result[key] for key in ["protected_files", "all_match", "failures", "forward_evidence_mutated", "live_trading_enabled"]}, indent=2))
    return 0 if result["all_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
