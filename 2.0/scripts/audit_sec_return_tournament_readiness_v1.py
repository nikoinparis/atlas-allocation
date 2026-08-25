#!/usr/bin/env python3
"""Audit tournament engineering readiness without loading prices or calculating returns."""

from __future__ import annotations

import hashlib
import importlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
FROZEN = ROOT / "evidence/sec_return_improvement_program_v1/frozen_config.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
OUTPUT = ROOT / "evidence/sec_return_tournament_readiness_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_artifacts(result_path: Path) -> dict[str, bool]:
    result = json.loads(result_path.read_text())
    directory = result_path.parent
    files = [path for path in directory.iterdir() if path.is_file() and path != result_path]
    return {
        label: any(sha256(path) == expected for path in files)
        for label, expected in result.get("artifact_sha256", {}).items()
    }


def main() -> int:
    gate = json.loads(GATE.read_text())
    module = importlib.import_module("systematic_trader.sec_return_improvement")
    required_functions = [
        "residual_momentum_scores", "trend_quality_scores", "sector_neutral_quality_scores",
        "event_conditioned_scores", "adaptive_breadth", "adaptive_concentration_weights",
        "walk_forward_ridge_rank", "buffered_holding_selections", "causal_strategy_allocator",
    ]
    function_checks = {name: callable(getattr(module, name, None)) for name in required_functions}
    source_results = [
        ROOT / "evidence/sec_broad_tiingo_audit_v2/result.json",
        ROOT / "evidence/sec_broad_universe_readiness_v2/result.json",
        GATE,
    ]
    source_hash_checks = {str(path.relative_to(ROOT)): verified_artifacts(path) for path in source_results}
    config_matches = sha256(CONFIG) == sha256(FROZEN)
    panel_manifest = ROOT / "data/sec_broad_research_panel_v1/manifest.json"
    gate_open = bool(gate.get("strategy_testing_authorized", False))
    result = {
        "experiment": "sec_return_tournament_readiness_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_protocol_matches": config_matches,
        "signal_primitive_checks": function_checks,
        "all_signal_primitives_present": all(function_checks.values()),
        "source_artifact_hash_checks": source_hash_checks,
        "all_source_artifact_hashes_verified": all(all(checks.values()) for checks in source_hash_checks.values()),
        "research_gate_open": gate_open,
        "panel_manifest_exists": panel_manifest.exists(),
        "tournament_execution_ready": bool(config_matches and all(function_checks.values()) and
                                             all(all(x.values()) for x in source_hash_checks.values()) and
                                             gate_open and panel_manifest.exists()),
        "next_engineering_dependency": "materialize_hash_verified_broad_panel_after_gate" if not gate_open else
                                       "materialize_hash_verified_broad_panel" if not panel_manifest.exists() else
                                       "implement_and_run_frozen_eight_family_evaluator",
        "performance_evaluated": False,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC return tournament readiness v1\n\n"
        f"Frozen protocol: **{'PASS' if config_matches else 'FAIL'}**. Source hashes: "
        f"**{'PASS' if result['all_source_artifact_hashes_verified'] else 'FAIL'}**. Signal primitives: "
        f"**{'PASS' if result['all_signal_primitives_present'] else 'FAIL'}**. Research gate: "
        f"**{'OPEN' if gate_open else 'CLOSED'}**. No performance was calculated.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
