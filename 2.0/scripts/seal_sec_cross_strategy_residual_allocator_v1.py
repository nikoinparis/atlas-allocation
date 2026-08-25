#!/usr/bin/env python3
"""Seal immutable inputs for the cross-strategy residual allocator."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_cross_strategy_residual_allocator_v1"
INPUTS = [
    ROOT / "config/sec_cross_strategy_residual_allocator_v1.json",
    ROOT / "dashboard/public/return-first-dashboard.json",
    ROOT / "scripts/run_sec_cross_strategy_residual_allocator_v1.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    final = OUTPUT / "final_result.json"
    if final.exists():
        print(json.dumps({"status": "blocked_one_shot_already_complete"}, indent=2))
        return 0
    payload = {
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "sealed_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in INPUTS},
        "one_shot": True,
        "live_trading_enabled": False,
    }
    (OUTPUT / "execution_seal.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
