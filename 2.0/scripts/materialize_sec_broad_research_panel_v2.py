#!/usr/bin/env python3
"""Gate-locked materializer for the authenticated broad SEC research panel."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.sec_broad_panel_v2 import materialize_panel, validate_materialized_panel

CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
FROZEN = ROOT / "evidence/sec_return_improvement_program_v1/frozen_config.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_v2/recent_membership_readiness.csv"
INPUT = ROOT / "data/sec_broad_panel_inputs_v2"
OUTPUT = ROOT / "data/sec_broad_research_panel_v2"
STATUS = ROOT / "evidence/sec_broad_panel_materialization_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_state(gate: dict, frozen_matches: bool, input_manifest_exists: bool) -> str:
    if not frozen_matches: return "blocked_frozen_protocol_mismatch"
    if not bool(gate.get("strategy_testing_authorized", False)): return "blocked_broad_research_gate"
    if not input_manifest_exists: return "authorized_waiting_for_causal_input_manifest"
    return "authorized_ready_to_materialize"


def verify_manifest(directory: Path, manifest: dict) -> bool:
    return all((directory / name).exists() and sha256(directory / name) == digest for name, digest in manifest.get("artifact_sha256", {}).items())


def main() -> int:
    gate = json.loads(GATE.read_text())
    frozen_matches = CONFIG.exists() and FROZEN.exists() and sha256(CONFIG) == sha256(FROZEN)
    source_manifest_path = INPUT / "manifest.json"
    state = input_state(gate, frozen_matches, source_manifest_path.exists())
    status = {"experiment": "sec_broad_panel_materialization_v2", "created_at_utc": datetime.now(timezone.utc).isoformat(), "status": state, "frozen_protocol_matches": frozen_matches, "research_gate_open": bool(gate.get("strategy_testing_authorized", False)), "input_manifest_exists": source_manifest_path.exists(), "real_panel_written": False, "performance_evaluated": False, "strategy_promotion_authorized": False, "live_trading_enabled": False}
    STATUS.mkdir(parents=True, exist_ok=True)
    if state != "authorized_ready_to_materialize":
        (STATUS / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
        print(json.dumps(status, indent=2, sort_keys=True)); return 0
    source_manifest = json.loads(source_manifest_path.read_text())
    if not verify_manifest(INPUT, source_manifest): raise RuntimeError("causal input manifest hash mismatch")
    features = pd.read_csv(INPUT / "causal_features.csv.gz", dtype={"cik10": str})
    prices = pd.read_csv(INPUT / "weekly_adjusted_prices.csv.gz", index_col=0)
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    panel, weekly_returns = materialize_panel(membership, features, prices, target_horizon_weeks=13, execution_delay_weeks=1)
    audit = validate_materialized_panel(panel)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    panel.to_csv(OUTPUT / "panel.csv.gz", index=False, compression="gzip")
    weekly_returns.to_csv(OUTPUT / "weekly_returns.csv.gz", compression="gzip")
    benchmarks = INPUT / "benchmark_weekly_returns.csv.gz"
    if not benchmarks.exists(): raise RuntimeError("benchmark returns required by frozen protocol")
    (OUTPUT / "benchmark_weekly_returns.csv.gz").write_bytes(benchmarks.read_bytes())
    manifest = {"experiment": "sec_broad_research_panel_v2", "created_at_utc": datetime.now(timezone.utc).isoformat(), "point_in_time_audit": audit, "source_manifest_sha256": sha256(source_manifest_path), "membership_sha256": sha256(MEMBERSHIP), "artifact_sha256": {name: sha256(OUTPUT / name) for name in ["panel.csv.gz", "weekly_returns.csv.gz", "benchmark_weekly_returns.csv.gz"]}, "performance_evaluated": False, "strategy_promotion_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    status.update({"status": "materialized_hash_verified_panel", "real_panel_written": True, "output_manifest_sha256": sha256(OUTPUT / "manifest.json")})
    (STATUS / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps(status, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
