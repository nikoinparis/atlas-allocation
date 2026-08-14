#!/usr/bin/env python3
"""Measure authenticated Tiingo rescue progress over recent SEC decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
CANDIDATES = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/yahoo_failures_tiingo_candidates.csv"
AUDIT = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1/candidate_audit.csv"
OUTPUT = ROOT / "evidence/tiingo_recent_rescue_progress_v1"


def main() -> int:
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    candidates = pd.read_csv(CANDIDATES, dtype={"cik10": str})
    audit = pd.read_csv(AUDIT, dtype={"cik10": str})
    recent = membership[membership["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")].copy()
    priority_ciks = set(candidates.loc[candidates["inventory_interval_overlap"].astype(bool), "cik10"])
    recent_priority_ciks = priority_ciks & set(recent["cik10"])
    valid_statuses = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
    valid_ciks = set(audit.loc[audit["audit_status"].isin(valid_statuses), "cik10"])
    rejected_ciks = set(audit.loc[~audit["audit_status"].isin(valid_statuses), "cik10"])
    recent_priority = recent[recent["cik10"].isin(recent_priority_ciks)].copy()
    recent_priority["authenticated_tiingo_valid"] = recent_priority["cik10"].isin(valid_ciks)
    by_decision = recent_priority.groupby("decision_at", as_index=False).agg(
        priority_gap_members=("cik10", "nunique"),
        authenticated_rescued_members=("authenticated_tiingo_valid", "sum"),
    )
    by_decision["priority_gap_rescue_rate"] = by_decision["authenticated_rescued_members"] / by_decision["priority_gap_members"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    by_decision.to_csv(OUTPUT / "rescue_by_decision.csv", index=False)
    affected_rows = recent_priority[recent_priority["authenticated_tiingo_valid"]]
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "authenticated_candidates_audited": int(len(audit)),
        "authenticated_valid_ciks": int(len(valid_ciks)),
        "authenticated_rejected_ciks": int(len(rejected_ciks)),
        "recent_priority_ciks_total": int(len(recent_priority_ciks)),
        "recent_priority_ciks_validated": int(len(valid_ciks & recent_priority_ciks)),
        "recent_priority_ciks_remaining": int(len(recent_priority_ciks - valid_ciks - rejected_ciks)),
        "recent_company_decision_gaps_total": int(len(recent_priority)),
        "recent_company_decision_gaps_rescued": int(len(affected_rows)),
        "recent_company_decision_rescue_rate": float(len(affected_rows) / len(recent_priority)) if len(recent_priority) else 0.0,
        "strategy_testing_authorized": False,
        "next_gate": "complete remaining recent-priority Tiingo batches and rebuild the combined Yahoo/Tiingo price panel",
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# Tiingo recent rescue progress v1\n\nTwo authenticated batches audited **{len(audit)}** candidates and validated **{len(valid_ciks)}** identities. Of the **{len(recent_priority_ciks)}** Tiingo candidates affecting decisions from 2023 onward, **{len(valid_ciks & recent_priority_ciks)}** are now validated and **{len(recent_priority_ciks - valid_ciks - rejected_ciks)}** remain untested. The validated histories restore **{len(affected_rows):,} of {len(recent_priority):,}** affected company-decision observations ({result['recent_company_decision_rescue_rate']:.1%}). Strategy testing remains blocked until the remaining recent-priority batches and combined-panel audit finish.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
