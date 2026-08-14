#!/usr/bin/env python3
"""Save a diverse, provisional shortlist from Research Laboratory Batch 01."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD = ROOT / "evidence/research_lab_batch_01/leaderboard.csv"
RESULT = ROOT / "evidence/research_lab_batch_01/result.json"
OUTPUT = ROOT / "research_registry/strategy_candidates.json"


QUALIFICATION_RULES = {
    "retrospective_2016_2020_min_sharpe": 0.40,
    "retrospective_2021_present_min_sharpe": 0.80,
    "each_retrospective_period_max_drawdown_floor": -0.30,
    "unpriced_exposure_events_required": 0,
    "fully_invested_required": True,
    "diversity_rule": "highest development-selection score per signal recipe",
    "additional_entries": "exact frozen v4 and each distinct walk-forward-selected configuration",
}
MISSING_GATES = [
    "parameter_neighborhood_stability",
    "25_50_100bps_cost_stress",
    "point_in_time_market_regime_stability",
    "multiple_testing_adjustment",
    "strategy_ensemble_interaction",
    "52_week_untouched_forward_record",
    "survivorship_safe_historical_universe",
]


def load_rows() -> list[dict[str, str]]:
    with LEADERBOARD.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def qualifies(row: dict[str, str]) -> bool:
    return (
        float(row["oos_2016_2020_sharpe_zero_rf"]) >= 0.40
        and float(row["oos_2021_present_sharpe_zero_rf"]) >= 0.80
        and float(row["oos_2016_2020_max_drawdown"]) >= -0.30
        and float(row["oos_2021_present_max_drawdown"]) >= -0.30
        and int(row["unpriced_exposure_events"]) == 0
        and row["fully_invested_pass"].lower() == "true"
    )


def compact(row: dict[str, str], reasons: list[str]) -> dict[str, object]:
    return {
        "candidate_id": f"candidate-{row['experiment_id'][4:]}",
        "experiment_id": row["experiment_id"],
        "status": "provisional_not_approved",
        "selection_reasons": reasons,
        "recipe_name": row["recipe_name"],
        "configuration": {
            "signals": row["signals"].split("+"),
            "smoothing_weeks": int(row["smoothing_weeks"]),
            "portfolio_method": row["portfolio_method"],
            "top_n": int(row["top_n"]),
            "minimum_signal": 0.05,
            "cost_bps": float(row["cost_bps"]),
        },
        "evidence": {
            "development_rank": int(row["development_rank"]),
            "development_annual_return": float(row["development_annual_return"]),
            "development_sharpe": float(row["development_sharpe_zero_rf"]),
            "retrospective_2016_2020_annual_return": float(row["oos_2016_2020_annual_return"]),
            "retrospective_2016_2020_sharpe": float(row["oos_2016_2020_sharpe_zero_rf"]),
            "retrospective_2021_present_annual_return": float(row["oos_2021_present_annual_return"]),
            "retrospective_2021_present_sharpe": float(row["oos_2021_present_sharpe_zero_rf"]),
            "full_annual_return": float(row["full_annual_return"]),
            "full_sharpe": float(row["full_sharpe_zero_rf"]),
            "full_max_drawdown": float(row["full_max_drawdown"]),
        },
        "passed_gates": [
            "point_in_time_signal_lag",
            "next_week_return_realization",
            "10bps_turnover_cost",
            "accounting_reconciliation",
            "two_retrospective_period_thresholds",
        ],
        "missing_gates": list(MISSING_GATES),
        "final": False,
        "approved_for_live_trading": False,
    }


def build() -> dict[str, object]:
    rows = load_rows()
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    selected: dict[str, tuple[dict[str, str], list[str]]] = {}
    for row in rows:
        if qualifies(row) and row["recipe_name"] not in {
            item[0]["recipe_name"] for item in selected.values()
        }:
            selected[row["experiment_id"]] = (row, ["best_qualifying_configuration_for_signal_recipe"])

    v4 = result["v4_benchmark"]
    v4_row = next(row for row in rows if row["experiment_id"] == v4["experiment_id"])
    selected.setdefault(v4_row["experiment_id"], (v4_row, []))[1].append("exact_frozen_v4_benchmark")

    for fold in result["retrospective_walk_forward"]["folds"]:
        experiment = str(fold["selected_experiment_id"])
        row = next(item for item in rows if item["experiment_id"] == experiment)
        selected.setdefault(experiment, (row, []))[1].append(
            f"selected_using_training_window_{fold['train_start']}_to_{fold['train_end']}"
        )

    candidates = [compact(row, reasons) for row, reasons in selected.values()]
    candidates.sort(key=lambda item: (int(item["evidence"]["development_rank"]), item["candidate_id"]))
    return {
        "registry_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_batch": "research_lab_batch_01",
        "source_snapshot_id": result["source_snapshot_id"],
        "purpose": "Track promising strategies without representing any as final, production-ready, or expected to make money.",
        "qualification_rules_fixed_before_robustness_batch_02": QUALIFICATION_RULES,
        "candidate_count": len(candidates),
        "candidate_status_definitions": {
            "provisional_not_approved": "Saved for further testing only.",
            "provisional_robust": "Passed the currently implemented retrospective robustness gates; still not final.",
            "provisional_fragile": "Failed at least one current robustness gate; retained for diagnosis.",
        },
        "candidates": candidates,
    }


def main() -> int:
    payload = build()
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_count": payload["candidate_count"],
        "candidate_ids": [item["candidate_id"] for item in payload["candidates"]],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
