#!/usr/bin/env python3
"""Seal the immutable inputs for the v2 cross-strategy residual allocator.

The seal is written before the experiment runs and verified by the runner. Any
edit to the config, the runner, the dashboard export, or the frozen sector map
after sealing invalidates the run rather than silently changing the result.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_cross_strategy_residual_allocator_v2"
INPUTS = [
    ROOT / "config/sec_cross_strategy_residual_allocator_v2.json",
    ROOT / "dashboard/public/return-first-dashboard.json",
    ROOT / "data/cross_strategy_concentration_map_v1/sector_map.csv",
    ROOT / "data/cross_strategy_concentration_map_v1/manifest.json",
    ROOT / "scripts/run_sec_cross_strategy_residual_allocator_v2.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / "final_result.json").exists():
        print(json.dumps({"status": "blocked_one_shot_already_complete"}, indent=2))
        return 0
    missing = [str(path.relative_to(ROOT)) for path in INPUTS if not path.exists()]
    if missing:
        print(json.dumps({"status": "blocked_missing_input", "missing": missing}, indent=2))
        return 1
    payload = {
        "experiment_id": "sec-cross-strategy-residual-allocator-v2",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "sealed_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in INPUTS},
        "one_shot": True,
        "financing_deferred_until_unlevered_promoted": True,
        "live_trading_enabled": False,
    }
    (OUTPUT / "execution_seal.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
