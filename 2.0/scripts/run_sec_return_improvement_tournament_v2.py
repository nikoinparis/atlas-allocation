#!/usr/bin/env python3
"""Final gate-, protocol-, panel-, and execution-seal-locked tournament entry point."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.sec_broad_panel_v2 import validate_materialized_panel
from systematic_trader.sec_real_tournament_v2 import evaluate

CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
FROZEN = ROOT / "evidence/sec_return_improvement_program_v1/frozen_config.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
PANEL = ROOT / "data/sec_broad_research_panel_v2"
SEAL = ROOT / "evidence/sec_return_improvement_tournament_v2/execution_seal.json"
OUTPUT = ROOT / "evidence/sec_return_improvement_tournament_v2"


def sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def authorization_state(gate: dict, frozen_matches: bool, panel_exists: bool, seal_exists: bool) -> str:
    if not frozen_matches: return "blocked_frozen_protocol_mismatch"
    if not bool(gate.get("strategy_testing_authorized", False)): return "blocked_broad_research_gate"
    if not panel_exists: return "authorized_waiting_for_hash_verified_panel"
    if not seal_exists: return "authorized_waiting_for_execution_seal"
    return "authorized_ready_for_one_shot_tournament"


def verify_named_hashes(directory: Path, values: dict[str, str]) -> bool:
    return all((directory / name).exists() and sha256(directory / name) == digest for name, digest in values.items())


def main() -> int:
    gate = json.loads(GATE.read_text())
    frozen_matches = CONFIG.exists() and FROZEN.exists() and sha256(CONFIG) == sha256(FROZEN)
    manifest_path = PANEL / "manifest.json"
    state = authorization_state(gate, frozen_matches, manifest_path.exists(), SEAL.exists())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    status = {"experiment": "sec_return_improvement_tournament_v2", "created_at_utc": datetime.now(timezone.utc).isoformat(), "status": state, "research_gate_open": bool(gate.get("strategy_testing_authorized", False)), "performance_evaluated": False, "strategy_promotion_authorized": False, "live_trading_enabled": False}
    if state != "authorized_ready_for_one_shot_tournament":
        (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n"); print(json.dumps(status, indent=2, sort_keys=True)); return 0
    manifest = json.loads(manifest_path.read_text())
    if not verify_named_hashes(PANEL, manifest["artifact_sha256"]): raise RuntimeError("broad panel artifact hash mismatch")
    seal = json.loads(SEAL.read_text())
    if not verify_named_hashes(ROOT, seal["sealed_sha256"]): raise RuntimeError("execution seal mismatch")
    if (OUTPUT / "final_result.json").exists(): raise RuntimeError("one-shot tournament already evaluated")
    config = json.loads(CONFIG.read_text())
    panel = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    validate_materialized_panel(panel)
    weekly = pd.read_csv(PANEL / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    benchmarks = pd.read_csv(PANEL / "benchmark_weekly_returns.csv.gz", index_col=0, parse_dates=True)
    benchmarks.index = pd.to_datetime(benchmarks.index, utc=True)
    if set(config["benchmark_candidates"]) - set(benchmarks): raise RuntimeError("frozen benchmark return columns missing")
    screens, ml_rows = [], []
    for benchmark in config["benchmark_candidates"]:
        screen, ml = evaluate(panel, weekly, benchmarks[benchmark], config)
        screen.insert(1, "benchmark", benchmark); screens.append(screen)
        ml.insert(0, "benchmark", benchmark); ml_rows.append(ml)
    screening = pd.concat(screens, ignore_index=True)
    screening["passes_frozen_gates"] = (screening.recent_cagr_improvement_vs_control >= config["tournament"]["minimum_recent_cagr_improvement"]) & (screening.full_cagr_improvement_vs_control >= config["tournament"]["minimum_full_cagr_improvement"]) & (screening.minimum_rolling_outperformance_share >= config["tournament"]["minimum_rolling_outperformance_share"]) & (screening.familywise_adjusted_probability_positive >= config["tournament"]["minimum_bootstrap_probability_positive"]) & (screening.maximum_positive_issuer_share <= config["tournament"]["maximum_single_issuer_positive_return_share"]) & (screening.recent_max_drawdown >= config["tournament"]["maximum_recent_drawdown"])
    family_pass = screening.groupby("family").passes_frozen_gates.all()
    qualified = sorted(family_pass[family_pass].index)
    screening.to_csv(OUTPUT / "screening.csv", index=False)
    pd.concat(ml_rows, ignore_index=True).to_csv(OUTPUT / "nested_ml_audit.csv", index=False)
    result = {**status, "status": "one_shot_tournament_complete", "performance_evaluated": True, "qualified_families": qualified, "winner_selected": qualified[0] if len(qualified) == 1 else None, "manual_review_required": len(qualified) != 1, "artifact_sha256": {"screening": sha256(OUTPUT / "screening.csv"), "nested_ml_audit": sha256(OUTPUT / "nested_ml_audit.csv")}}
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True)); return 0


if __name__ == "__main__": raise SystemExit(main())
