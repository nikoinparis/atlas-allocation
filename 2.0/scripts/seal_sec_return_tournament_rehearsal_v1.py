#!/usr/bin/env python3
"""Create or verify the immutable synthetic tournament rehearsal seal."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_return_tournament_synthetic_rehearsal_v1"
SEAL = OUTPUT / "seal.json"
FILES = [
    ROOT / "config/sec_return_tournament_synthetic_rehearsal_v1.json",
    ROOT / "schemas/sec_broad_research_panel_v1.schema.json",
    ROOT / "src/systematic_trader/sec_tournament_rehearsal.py",
    ROOT / "scripts/run_sec_return_tournament_synthetic_rehearsal_v1.py",
    ROOT / "tests/test_sec_tournament_rehearsal.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in FILES}


def main() -> int:
    current = current_hashes()
    if SEAL.exists():
        prior = json.loads(SEAL.read_text())
        if prior["sealed_sha256"] != current:
            raise RuntimeError("synthetic rehearsal seal mismatch; create a versioned protocol instead of mutating v1")
        print(json.dumps({"seal_verified": True, "sealed_files": len(current)}, indent=2))
        return 0
    gate = json.loads((ROOT / "evidence/sec_broad_research_gate_v2/result.json").read_text())
    seal = {"experiment": "sec_return_tournament_synthetic_rehearsal_v1", "sealed_at_utc": datetime.now(timezone.utc).isoformat(), "rehearsal_contract_sealed": True, "real_research_gate_open_at_seal": bool(gate.get("strategy_testing_authorized", False)), "real_performance_evaluated": False, "real_execution_authorized": False, "strategy_promotion_authorized": False, "live_trading_enabled": False, "sealed_sha256": current}
    SEAL.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n")
    print(json.dumps(seal, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
