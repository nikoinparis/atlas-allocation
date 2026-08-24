#!/usr/bin/env python3
"""Create or verify the pre-result execution seal for the real tournament v2."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_return_improvement_tournament_v2"
SEAL = OUTPUT / "execution_seal.json"
FILES = [
    ROOT / "config/sec_return_improvement_program_v1.json",
    ROOT / "config/sec_broad_missing_company_gate_v2.json",
    ROOT / "schemas/sec_broad_research_panel_v2.schema.json",
    ROOT / "src/systematic_trader/sec_return_improvement.py",
    ROOT / "src/systematic_trader/sec_tournament_rehearsal.py",
    ROOT / "src/systematic_trader/sec_broad_panel_v2.py",
    ROOT / "src/systematic_trader/sec_real_tournament_v2.py",
    ROOT / "scripts/materialize_sec_broad_research_panel_v2.py",
    ROOT / "scripts/run_sec_return_improvement_tournament_v2.py",
    ROOT / "scripts/seal_sec_return_improvement_tournament_v2.py",
    ROOT / "tests/test_sec_broad_panel_and_tournament_v2.py",
    ROOT / "tests/test_sec_return_improvement.py",
]


def sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    current = {str(path.relative_to(ROOT)): sha256(path) for path in FILES}
    if SEAL.exists():
        prior = json.loads(SEAL.read_text())
        if prior["sealed_sha256"] != current:
            final_result = OUTPUT / "final_result.json"
            repair_requested = "--repair-before-result" in sys.argv
            if final_result.exists() or not repair_requested:
                raise RuntimeError("real tournament execution seal mismatch; use a new version after results")
            result = {
                **prior,
                "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
                "sealed_sha256": current,
                "pre_result_repair": True,
                "pre_result_repair_reason": "missing-score buffered-holding crash before performance output",
                "prior_execution_seal_sha256": sha256(SEAL),
                "performance_evaluated_at_seal": False,
            }
            SEAL.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        print(json.dumps({"execution_seal_verified": True, "sealed_files": len(current)}, indent=2)); return 0
    gate = json.loads((ROOT / "evidence/sec_broad_research_gate_v2/result.json").read_text())
    if bool(gate.get("strategy_testing_authorized", False)):
        raise RuntimeError("execution code must be sealed before the broad research gate opens")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {"experiment": "sec_return_improvement_tournament_v2", "sealed_at_utc": datetime.now(timezone.utc).isoformat(), "pre_result_execution_seal": True, "research_gate_open_at_seal": False, "performance_evaluated_at_seal": False, "one_shot_execution": True, "strategy_promotion_authorized": False, "live_trading_enabled": False, "sealed_sha256": current}
    SEAL.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
