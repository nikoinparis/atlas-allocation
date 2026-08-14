#!/usr/bin/env python3
"""Consolidate genuine third-sleeve evidence without relabeling weak ideas as winners."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/independent_sleeves_batch_10"
LEDGER = ROOT / "evidence/challenger_program_v1/trial_ledger.csv"


def main() -> int:
    batch04 = json.loads((ROOT / "evidence/new_families_batch_04/result.json").read_text(encoding="utf-8"))
    batch05 = json.loads((ROOT / "evidence/new_family_robustness_batch_05/result.json").read_text(encoding="utf-8"))
    robust = {row["family"]: row for row in batch05["candidate_summaries"]}
    leaders = {row["family"]: row for row in batch04["family_leaders"]}
    families = [
        {
            "family": "cross_sectional_value",
            "test_status": "blocked_data_gate",
            "configurations_tested": 0,
            "decision": "retain_in_backlog",
            "reason": "A genuine point-in-time value test requires historical fundamentals or valuation data; current free ETF prices cannot measure value without inventing a mislabeled proxy.",
        },
        {
            "family": "carry_or_roll_proxy",
            "test_status": "completed_failed_promotion",
            "configurations_tested": 36,
            "decision": "research_only",
            "reason": "Positive and cost-robust, but failed the 576-trial multiple-testing gate and current distributions are not archived point-in-time vintages.",
            "leader": leaders["carry_proxy"],
            "robustness": robust["carry_proxy"],
        },
        {
            "family": "short_term_reversal",
            "test_status": "completed_failed_promotion",
            "configurations_tested": 144,
            "decision": "do_not_add_to_portfolio",
            "reason": "The selected reversal family failed the 100 bps cost and 576-trial multiple-testing gates and had excessive turnover.",
            "leader": leaders["mean_reversion"],
            "robustness": robust["mean_reversion"],
        },
        {
            "family": "defensive_macro_regime",
            "test_status": "completed_not_independent",
            "configurations_tested": 108,
            "decision": "already_represented",
            "reason": "The defensive family passed robustness, but it is already the second frozen sleeve and therefore cannot honestly be counted as an independent third sleeve.",
            "leader": leaders["defensive"],
            "robustness": robust["defensive"],
        },
    ]
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 10,
        "track": "independent_strategy_sleeves",
        "prior_experiments_reconciled": batch04["experiment_count"],
        "multiple_testing_trial_count": batch05["rules_fixed_before_results"]["multiple_testing"]["trials"],
        "families": families,
        "independent_third_sleeve_promoted": False,
        "status": "completed_no_qualified_third_sleeve",
        "next_free_data_candidates": [
            "term-structure carry when a genuinely point-in-time free history is located",
            "cross-sectional value after a point-in-time fundamentals source passes licensing and vintage checks",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (OUTPUT / "family_decisions.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["family", "test_status", "configurations_tested", "decision", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row[key] for key in fields} for row in families])
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in families:
            writer.writerow([
                f"batch10-{row['family']}", 10, "independent_strategy_sleeves", "",
                row["family"], row["test_status"], row["decision"], row["reason"],
                "evidence/independent_sleeves_batch_10/result.json",
            ])
    print(json.dumps({"status": result["status"], "families": len(families)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
