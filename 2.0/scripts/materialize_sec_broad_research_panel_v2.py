#!/usr/bin/env python3
"""Gate-locked materializer for the authenticated broad SEC research panel."""

from __future__ import annotations

import argparse
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

# `data/sec_broad_research_panel_v2/manifest.json` is pinned by
# config/forward/sec_residual_controlled_sleeve_forward_v1.json. Rewriting it
# changes its hash, and the residual sleeve recorder then refuses to run at all:
# a newer panel would silently destroy the forward clock it was built to feed.
# A new quarterly vintage therefore has to be materialized somewhere else, so
# the output is a parameter and the default is the existing sealed path.
PINNED_BY_FORWARD_PROTOCOL = "data/sec_broad_research_panel_v2/manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def input_state(gate: dict, frozen_matches: bool, input_manifest_exists: bool) -> str:
    if not frozen_matches: return "blocked_frozen_protocol_mismatch"
    if not bool(gate.get("strategy_testing_authorized", False)): return "blocked_broad_research_gate"
    if not input_manifest_exists: return "authorized_waiting_for_causal_input_manifest"
    return "authorized_ready_to_materialize"


def verify_manifest(directory: Path, manifest: dict) -> bool:
    return all((directory / name).exists() and sha256(directory / name) == digest for name, digest in manifest.get("artifact_sha256", {}).items())


def refuse_to_break_the_pin(output: Path) -> None:
    protocol = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
    if not protocol.exists():
        return
    pinned = json.loads(protocol.read_text()).get("pinned_files_sha256", {})
    manifest = output / "manifest.json"
    if not manifest.exists():
        return
    relative = str(manifest.relative_to(ROOT))
    if relative in pinned and sha256(manifest) == pinned[relative]:
        raise RuntimeError(
            f"{relative} is pinned by sec_residual_controlled_sleeve_forward_v1 and already matches "
            f"that pin; materializing over it would void the forward clock. Pass --output-root with "
            f"a new vintage directory instead."
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default=str(OUTPUT),
                        help="panel vintage directory; defaults to the sealed v2 path")
    parser.add_argument("--status-root", default=str(STATUS))
    parser.add_argument("--experiment", default="sec_broad_research_panel_v2")
    parser.add_argument("--input-root", default=str(INPUT))
    parser.add_argument("--membership", default=str(MEMBERSHIP))
    args = parser.parse_args()
    inputs, membership_path = Path(args.input_root).resolve(), Path(args.membership).resolve()
    output, status_root = Path(args.output_root).resolve(), Path(args.status_root).resolve()
    refuse_to_break_the_pin(output)
    gate = json.loads(GATE.read_text())
    frozen_matches = CONFIG.exists() and FROZEN.exists() and sha256(CONFIG) == sha256(FROZEN)
    source_manifest_path = inputs / "manifest.json"
    state = input_state(gate, frozen_matches, source_manifest_path.exists())
    status = {"experiment": args.experiment + "_materialization", "created_at_utc": datetime.now(timezone.utc).isoformat(), "status": state, "frozen_protocol_matches": frozen_matches, "research_gate_open": bool(gate.get("strategy_testing_authorized", False)), "input_manifest_exists": source_manifest_path.exists(), "real_panel_written": False, "performance_evaluated": False, "strategy_promotion_authorized": False, "live_trading_enabled": False}
    status_root.mkdir(parents=True, exist_ok=True)
    if state != "authorized_ready_to_materialize":
        (status_root / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
        print(json.dumps(status, indent=2, sort_keys=True)); return 0
    source_manifest = json.loads(source_manifest_path.read_text())
    if not verify_manifest(inputs, source_manifest): raise RuntimeError("causal input manifest hash mismatch")
    features = pd.read_csv(inputs / "causal_features.csv.gz", dtype={"cik10": str})
    prices = pd.read_csv(inputs / "weekly_adjusted_prices.csv.gz", index_col=0)
    membership = pd.read_csv(membership_path, dtype={"cik10": str})
    panel, weekly_returns = materialize_panel(membership, features, prices, target_horizon_weeks=13, execution_delay_weeks=1)
    audit = validate_materialized_panel(panel)
    output.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output / "panel.csv.gz", index=False, compression="gzip")
    weekly_returns.to_csv(output / "weekly_returns.csv.gz", compression="gzip")
    benchmarks = inputs / "benchmark_weekly_returns.csv.gz"
    if not benchmarks.exists(): raise RuntimeError("benchmark returns required by frozen protocol")
    (output / "benchmark_weekly_returns.csv.gz").write_bytes(benchmarks.read_bytes())
    manifest = {"experiment": args.experiment, "created_at_utc": datetime.now(timezone.utc).isoformat(), "point_in_time_audit": audit, "source_manifest_sha256": sha256(source_manifest_path), "membership_sha256": sha256(membership_path), "artifact_sha256": {name: sha256(output / name) for name in ["panel.csv.gz", "weekly_returns.csv.gz", "benchmark_weekly_returns.csv.gz"]}, "performance_evaluated": False, "strategy_promotion_authorized": False, "live_trading_enabled": False}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    status.update({"status": "materialized_hash_verified_panel", "real_panel_written": True, "output_manifest_sha256": sha256(output / "manifest.json")})
    (status_root / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps(status, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
