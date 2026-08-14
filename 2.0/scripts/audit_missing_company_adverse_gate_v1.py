#!/usr/bin/env python3
"""Authorize research only when coverage and explicit missing-company stress gates pass."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config/missing_company_adverse_gate_v1.json").read_text())
COMBINED = ROOT / "evidence/combined_recent_price_panel_v1"
RESCUE = ROOT / "evidence/tiingo_recent_rescue_progress_v1/result.json"
TERMINALS = ROOT / "evidence/tiingo_terminal_outcomes_v1/result.json"
OUTPUT = ROOT / "evidence/missing_company_adverse_gate_v1"


def main() -> int:
    combined = json.loads((COMBINED / "result.json").read_text())
    rescue = json.loads(RESCUE.read_text())
    terminals = json.loads(TERMINALS.read_text())
    missing = pd.read_csv(COMBINED / "missing_membership.csv", dtype={"cik10": str})
    policy = missing[["decision_at", "cik10", "company_name_as_filed", "sector", "candidate_symbols"]].copy()
    policy["base_treatment"] = CONFIG["base_selected_missing_company_treatment"]
    policy["base_period_return"] = 0.0
    policy["adverse_treatment"] = "apply_minus_100_percent_to_intended_weight_for_holding_period"
    policy["adverse_period_return"] = float(CONFIG["adverse_selected_missing_company_return"])
    policy["renormalize_into_survivors"] = bool(CONFIG["renormalize_missing_weight_into_survivors"])

    coverage_pass = float(combined["minimum_decision_coverage"]) >= float(CONFIG["minimum_observed_coverage_every_decision"])
    priority_pass = int(rescue["recent_priority_ciks_remaining"]) == 0
    terminal_unresolved = int(terminals["early_delistings"]) - int(terminals["known_terminal_reasons"])
    terminal_pass = terminal_unresolved == 0
    policy_pass = len(policy) == int(combined["missing_company_decision_rows"]) and not policy.isna().any(axis=None)
    authorized = bool(coverage_pass and priority_pass and terminal_pass and policy_pass)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    policy.to_csv(OUTPUT / "missing_company_scenario_policy.csv", index=False)
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "minimum_observed_coverage": float(combined["minimum_decision_coverage"]),
        "minimum_observed_coverage_required": float(CONFIG["minimum_observed_coverage_every_decision"]),
        "coverage_gate_passed": coverage_pass,
        "recent_priority_ciks_remaining": int(rescue["recent_priority_ciks_remaining"]),
        "priority_resolution_gate_passed": priority_pass,
        "unresolved_terminal_outcomes": terminal_unresolved,
        "terminal_outcome_gate_passed": terminal_pass,
        "missing_company_decision_rows_tagged": int(len(policy)),
        "missing_company_policy_gate_passed": policy_pass,
        "base_treatment": CONFIG["base_selected_missing_company_treatment"],
        "adverse_selected_missing_company_return": float(CONFIG["adverse_selected_missing_company_return"]),
        "renormalize_missing_weight_into_survivors": bool(CONFIG["renormalize_missing_weight_into_survivors"]),
        "strategy_testing_authorized": authorized,
        "authorization_scope": "research backtests only, with both base and adverse missing-company scenarios required",
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Missing-company adverse gate v1\n\n"
        f"Minimum observed decision coverage is **{result['minimum_observed_coverage']:.2%}** "
        f"against a **{result['minimum_observed_coverage_required']:.0%}** requirement. "
        f"All priority CIKs are resolved, unresolved terminal outcomes are **{terminal_unresolved}**, "
        f"and **{len(policy)}** missing company-decision rows have explicit base and adverse policies.\n\n"
        "A selected missing company keeps its intended weight in cash in the base scenario and loses "
        "100% of that intended weight in the adverse scenario. Missing weight is never redistributed "
        "to surviving winners. Research strategy testing is "
        f"**{'authorized' if authorized else 'blocked'}**; live trading remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if authorized else 2


if __name__ == "__main__":
    raise SystemExit(main())
