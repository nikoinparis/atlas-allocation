#!/usr/bin/env python3
"""Create or verify the v3 pre-performance execution seal."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_quant_math_tournament_v3"
SEAL = OUTPUT / "execution_seal.json"
FILES = [
    ROOT / "config/sec_quant_math_tournament_v3.json",
    ROOT / "src/systematic_trader/sec_quant_math_tournament_v3.py",
    ROOT / "scripts/run_sec_quant_math_tournament_v3.py",
    ROOT / "scripts/seal_sec_quant_math_tournament_v3.py",
    ROOT / "tests/test_sec_quant_math_tournament_v3.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    current = {str(path.relative_to(ROOT)): sha256(path) for path in FILES}
    final = OUTPUT / "final_result.json"
    if SEAL.exists():
        prior = json.loads(SEAL.read_text())
        if prior.get("sealed_sha256") != current:
            raise RuntimeError("v3 execution seal mismatch; create a new tournament version")
        print(json.dumps({"execution_seal_verified": True, "sealed_files": len(current)}, indent=2))
        return 0
    if final.exists():
        raise RuntimeError("cannot seal after performance evaluation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {
        "experiment": "sec_quant_math_tournament_v3",
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "pre_result_execution_seal": True,
        "performance_evaluated_at_seal": False,
        "one_shot_execution": True,
        "selection_contaminated_by_prior_project_results": True,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
        "sealed_sha256": current,
    }
    SEAL.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
