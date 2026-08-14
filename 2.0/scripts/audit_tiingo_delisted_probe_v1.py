#!/usr/bin/env python3
"""Re-audit all cached Tiingo candidates with strict identity and price timing gates."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.tiingo_delisted import issuer_name_match, issuer_name_score

CACHE = ROOT / "data/tiingo_delisted_price_probe_cache_v1"
IDENTITY = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
OUTPUT = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1"


def main() -> int:
    rows = []
    for path in sorted(CACHE.glob("*/result.json")):
        result = json.loads(path.read_text())
        first_eligible = pd.to_datetime(result.get("first_eligible_decision"), utc=True, errors="coerce")
        last_eligible = pd.to_datetime(result.get("last_eligible_decision"), utc=True, errors="coerce")
        first_price = pd.to_datetime(result.get("first_price_date"), utc=True, errors="coerce")
        last_price = pd.to_datetime(result.get("last_price_date"), utc=True, errors="coerce")
        strict_name = issuer_name_match(result.get("sec_company_name"), result.get("provider_name"))
        covers_first = bool(pd.notna(first_price) and pd.notna(first_eligible) and first_price <= first_eligible + pd.Timedelta(days=10))
        covers_last = bool(pd.notna(last_price) and pd.notna(last_eligible) and last_price >= last_eligible)
        if not strict_name:
            audit_status = "rejected_name_mismatch_or_ticker_reuse"
        elif not covers_first:
            audit_status = "rejected_missing_start_of_eligibility"
        elif int(result.get("price_rows") or 0) < 2:
            audit_status = "rejected_insufficient_prices"
        elif not covers_last:
            audit_status = "validated_early_delisting_needs_terminal_audit"
        else:
            audit_status = "validated_history_through_last_decision"
        rows.append({
            **result,
            "strict_issuer_name_score": issuer_name_score(result.get("sec_company_name"), result.get("provider_name")),
            "strict_issuer_name_match": strict_name,
            "covers_first_eligible_decision": covers_first,
            "covers_last_eligible_decision": covers_last,
            "audit_status": audit_status,
        })
    audit = pd.DataFrame(rows)
    membership = pd.read_csv(IDENTITY, dtype={"cik10": str}, parse_dates=["decision_at"])
    if not audit.empty:
        valid_statuses = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
        valid_ciks = set(audit.loc[audit["audit_status"].isin(valid_statuses), "cik10"])
        audited_ciks = set(audit["cik10"])
    else:
        valid_ciks, audited_ciks = set(), set()
    audited_membership = membership[membership["cik10"].isin(audited_ciks)].copy()
    audited_membership["strict_tiingo_history_valid"] = audited_membership["cik10"].isin(valid_ciks)
    decision = audited_membership.groupby("decision_at", as_index=False).agg(
        audited_members=("cik10", "nunique"),
        valid_members=("strict_tiingo_history_valid", "sum"),
    )
    decision["validated_rate_within_audited_batch"] = decision["valid_members"] / decision["audited_members"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUTPUT / "candidate_audit.csv", index=False)
    decision.to_csv(OUTPUT / "batch_coverage_by_decision.csv", index=False)
    counts = audit["audit_status"].value_counts().to_dict() if not audit.empty else {}
    valid_statuses = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
    valid = int(audit["audit_status"].isin(valid_statuses).sum()) if not audit.empty else 0
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "cached_candidates": int(len(audit)),
        "identity_and_start_validated_histories": valid,
        "identity_and_start_validation_rate": float(valid / len(audit)) if len(audit) else 0.0,
        "early_delistings_requiring_terminal_audit": int((audit["audit_status"] == "validated_early_delisting_needs_terminal_audit").sum()) if not audit.empty else 0,
        "status_counts": {str(key): int(value) for key, value in counts.items()},
        "token_persisted": False,
        "additional_api_requests_used": 0,
        "strategy_testing_authorized": False,
        "next_gate": "continue free-tier batches, then audit full decision-date coverage and terminal delisting outcomes",
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = f"""# Tiingo authenticated delisted-price probe v1

The first authenticated batch cached **{len(audit)}** histories. After requiring a meaningful issuer-name token match and prices at the first SEC eligibility decision, **{valid}** histories passed ({result['identity_and_start_validation_rate']:.1%}). Histories ending before the filing-staleness window are retained as probable early delistings, shorten tradable membership, and require a separate terminal-outcome audit. Rejected histories remain explicit and are not substituted with similarly named or recycled tickers.

This batch validates the source direction, not the full research panel. More rate-limited batches and a terminal delisting-outcome audit are required before a fundamental strategy test can run.
"""
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
