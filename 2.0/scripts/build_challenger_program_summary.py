#!/usr/bin/env python3
"""Build the final truthful Batch 08–13 cross-track decision."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/challenger_program_v1/result.json"


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> int:
    portfolio_registry = load("research_registry/portfolio_candidates.json")
    candidate = portfolio_registry["candidates"][0]
    buffering = load("evidence/trade_buffering_batch_08/result.json")
    fragility = load("evidence/fragility_guard_batch_09/result.json")
    sleeves = load("evidence/independent_sleeves_batch_10/result.json")
    libraries = load("evidence/portfolio_libraries_batch_11/result.json")
    ml = load("evidence/ml_sandbox_batch_12/result.json")
    ml_repos = load("evidence/ml_sandbox_batch_12/repository_summary.json")
    vectorbt = load("evidence/vectorbt_equivalence_batch_13/result.json")
    source = load("evidence/challenger_program_v1/source_smoke/summary.json")
    with (ROOT / "evidence/challenger_program_v1/trial_ledger.csv").open(newline="", encoding="utf-8") as handle:
        ledger_rows = list(csv.DictReader(handle))
    baseline = candidate["evidence"]
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": "challenger_program_v1_batches_08_13",
        "pinned_repositories": source["total"],
        "pinned_source_gate_passed": source["passed"],
        "logged_trial_rows": len(ledger_rows),
        "frozen_baseline_modified": False,
        "current_winning_strategy": {
            "name": "covariance_minimum_variance_v1",
            "status": candidate["status"], "final": candidate["final"],
            "annual_return_10bps": baseline["annual_return"],
            "sharpe_10bps": baseline["sharpe_zero_rf"],
            "max_drawdown_10bps": baseline["max_drawdown"],
            "annual_turnover": baseline["average_annual_turnover"],
            "forward_weeks_observed": candidate["forward_clock"]["observed_weeks"],
            "forward_weeks_required": candidate["forward_clock"]["required_weeks"],
        },
        "track_decisions": {
            "trade_buffering": {
                "selected_configuration": buffering["selected_at_10_bps"]["configuration_id"],
                "decision": "retain_as_high_cost_execution_challenger_not_winner",
            },
            "fragility_guard": {
                "selected_configuration": fragility["selected_at_10_bps"]["configuration_id"],
                "decision": "did_not_transfer_to_2_0_baseline_remains_winner",
            },
            "independent_strategy_sleeves": {
                "third_sleeve_promoted": sleeves["independent_third_sleeve_promoted"],
                "decision": sleeves["status"],
            },
            "portfolio_libraries": {
                "latest_capability_status": {key: value["status"] for key, value in libraries["latest_attempt_by_repository"].items()},
                "decision": libraries["status"],
            },
            "machine_learning": {
                "ml_beats_baseline": ml["ml_beats_baseline_sharpe_at_10bps"],
                "external_alpha_accepted": ml_repos["external_repository_alpha_accepted"],
                "decision": ml_repos["status"],
            },
            "vectorbt": {
                "probe_status": vectorbt["status"],
                "indicator_equivalence_pass": vectorbt["probe"].get("indicator_equivalence_pass", False),
                "decision": vectorbt["decision"],
            },
        },
        "program_outcome": "all_six_tracks_attempted_no_new_winner",
        "promotion": False,
        "live_trading_approved": False,
        "reason": "No challenger produced sufficiently stronger causal after-cost evidence than frozen v1; forward evidence remains 0 of 52 weeks.",
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"outcome": result["program_outcome"], "logged_trial_rows": len(ledger_rows), "current_winner": result["current_winning_strategy"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
