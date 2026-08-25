#!/usr/bin/env python3
"""Freeze the return-improvement tournament without evaluating performance."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader import sec_return_improvement as program


CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
OUTPUT = ROOT / "evidence/sec_return_improvement_program_v1"
MODULE = ROOT / "src/systematic_trader/sec_return_improvement.py"
TEST = ROOT / "tests/test_sec_return_improvement.py"
TOURNAMENT_TEST = ROOT / "tests/test_sec_return_improvement_tournament.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_config(config: dict) -> None:
    required_families = {"residual_momentum", "trend_quality", "quality_momentum", "event_conditioning"}
    if set(config["signal_families"]) != required_families:
        raise ValueError("the four predeclared signal families changed")
    if config.get("adaptive_concentration", {}).get("ticker_specific_caps_forbidden") is not True:
        raise ValueError("ticker-specific caps must remain forbidden")
    if int(config["tournament"]["familywise_trials"]) != 8:
        raise ValueError("familywise trial count must remain eight")
    if config.get("broad_performance_must_not_run_before_gate") is not True:
        raise ValueError("broad performance gate cannot be disabled")
    if config.get("live_trading_enabled") is not False:
        raise ValueError("live trading must remain disabled")


def main() -> int:
    config = json.loads(CONFIG.read_text())
    validate_config(config)
    gate = json.loads(GATE.read_text()) if GATE.exists() else {}
    authorized = bool(gate.get("strategy_testing_authorized", False))
    output_rows = [
        {
            "workstream": "residual_momentum",
            "implementation": "causal_sector_and_market_residual_price_rank",
            "required_sources": "validated_adjusted_prices|point_in_time_sector",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "sector residual adds no rolling return after costs",
        },
        {
            "workstream": "trend_quality",
            "implementation": "52_week_high|positive_week_consistency|multi_horizon_strength",
            "required_sources": "validated_adjusted_prices",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "breakout score is a single-period winner proxy",
        },
        {
            "workstream": "quality_momentum",
            "implementation": "sector_neutral_growth|profitability|accruals|asset_growth|dilution",
            "required_sources": "point_in_time_SEC_Company_Facts",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "feature availability or denominator quality is unstable",
        },
        {
            "workstream": "event_conditioning",
            "implementation": "strictly_delayed_earnings_8K_and_Form4_confirmation",
            "required_sources": "SEC_event_vintages|validated_adjusted_prices",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "event overlay fails one-week delay or severe-cost test",
        },
        {
            "workstream": "adaptive_concentration",
            "implementation": "generic_confidence_breadth_5_10_20|issuer_and_sector_caps",
            "required_sources": "component_scores|point_in_time_sector",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "top-five result depends on one issuer or one sector",
        },
        {
            "workstream": "confidence_weighted_ml",
            "implementation": "purged_embargoed_walk_forward_ridge_rank_ensemble",
            "required_sources": "all_causal_features|future_sector_relative_training_labels",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "nested out-of-sample rank IC or calibration is non-positive",
        },
        {
            "workstream": "holding_and_exit",
            "implementation": "minimum_hold|rank_decay_exit|max_age|entry_buffer",
            "required_sources": "causal_quarterly_scores",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "return gain disappears after turnover and delay stress",
        },
        {
            "workstream": "strategy_allocator",
            "implementation": "past_only_strength|dependence_penalty|sleeve_caps|explicit_cash",
            "required_sources": "fully_accounted_sleeve_return_histories",
            "engineering_ready": True,
            "broad_return_test_ready": authorized,
            "first_rejection": "allocator merely chases the latest selected winner",
        },
    ]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frozen_config = OUTPUT / "frozen_config.json"
    if frozen_config.exists() and sha256(CONFIG) != sha256(frozen_config):
        raise RuntimeError("the existing frozen protocol differs from the working config")
    if not frozen_config.exists():
        shutil.copyfile(CONFIG, frozen_config)
    inventory = pd.DataFrame(output_rows)
    inventory.to_csv(OUTPUT / "workstream_inventory.csv", index=False)
    event_files = sorted((ROOT / "data/sec_earnings_event_vintages").glob("*/earnings_8k_events.csv"))
    form4_manifests = sorted((ROOT / "data/sec_form4_bulk_vintages").glob("*/manifest.json"))
    source_readiness = pd.DataFrame([
        {
            "source": "broad_point_in_time_membership",
            "available": (ROOT / "evidence/sec_broad_universe_readiness_v2/recent_membership_readiness.csv").exists(),
            "coverage": 1.0,
            "gate_limited": False,
        },
        {
            "source": "validated_adjusted_prices",
            "available": gate.get("overall_price_coverage") is not None,
            "coverage": gate.get("overall_price_coverage"),
            "gate_limited": not authorized,
        },
        {
            "source": "point_in_time_companyfacts",
            "available": gate.get("overall_companyfacts_coverage") is not None,
            "coverage": gate.get("overall_companyfacts_coverage"),
            "gate_limited": not bool(gate.get("companyfacts_gate_passed", False)),
        },
        {
            "source": "earnings_8k_events",
            "available": bool(event_files),
            "coverage": None,
            "gate_limited": False,
        },
        {
            "source": "form4_bulk_events",
            "available": bool(form4_manifests),
            "coverage": None,
            "gate_limited": False,
        },
        {
            "source": "existing_accounted_strategy_paths",
            "available": (ROOT / "dashboard/public/return-first-dashboard.json").exists(),
            "coverage": None,
            "gate_limited": False,
        },
    ])
    source_readiness.to_csv(OUTPUT / "source_readiness.csv", index=False)
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_frozen": True,
        "workstreams": int(len(inventory)),
        "engineering_ready_workstreams": int(inventory.engineering_ready.sum()),
        "broad_strategy_testing_authorized": authorized,
        "performance_evaluated": False,
        "performance_metrics_written": False,
        "research_only": True,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
        "gate_snapshot": {
            "minimum_decision_price_coverage": gate.get("minimum_decision_price_coverage"),
            "overall_price_coverage": gate.get("overall_price_coverage"),
            "free_tiingo_pending_ciks": gate.get("free_tiingo_pending_ciks"),
            "terminal_outcome_gate_passed": gate.get("terminal_outcome_gate_passed"),
        },
        "artifact_sha256": {
            "frozen_config": sha256(frozen_config),
            "workstream_inventory": sha256(OUTPUT / "workstream_inventory.csv"),
            "implementation_module": sha256(MODULE),
            "implementation_tests": sha256(TEST),
            "tournament_guard_tests": sha256(TOURNAMENT_TEST),
            "source_readiness": sha256(OUTPUT / "source_readiness.csv"),
        },
        "module_exports_verified": all(
            hasattr(program, name)
            for name in [
                "residual_momentum_scores",
                "trend_quality_scores",
                "sector_neutral_quality_scores",
                "event_conditioned_scores",
                "adaptive_concentration_weights",
                "walk_forward_ridge_rank",
                "buffered_holding_selections",
                "causal_strategy_allocator",
            ]
        ),
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC return-improvement program v1\n\n"
        f"Frozen **{len(inventory)}** causal workstreams before broad performance evaluation. "
        f"All **{int(inventory.engineering_ready.sum())}** signal/construction interfaces are implemented. "
        f"Broad return testing is **{'authorized' if authorized else 'blocked'}** by the existing research gate. "
        "No performance metric was calculated, no candidate was selected, and live trading remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
