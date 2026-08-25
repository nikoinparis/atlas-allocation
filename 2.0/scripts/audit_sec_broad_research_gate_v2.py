#!/usr/bin/env python3
"""Authorize broad research only after coverage and adverse-missing-data gates pass."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_broad_missing_company_gate_v2.json"
READINESS = ROOT / "evidence/sec_broad_universe_readiness_v2/recent_membership_readiness.csv"
TIINGO_AUDIT = ROOT / "evidence/sec_broad_tiingo_audit_v2/candidate_audit.csv"
CANDIDATE_FILES = [
    ROOT / "evidence/sec_broad_tiingo_queue_v2/candidates.csv",
    ROOT / "evidence/sec_broad_tiingo_multi_symbol_supplement_v2/candidates.csv",
]
OUTPUT = ROOT / "evidence/sec_broad_research_gate_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    config = json.loads(CONFIG.read_text())
    readiness = pd.read_csv(READINESS, dtype={"cik10": str}, parse_dates=["decision_at"])
    candidates = pd.concat(
        [pd.read_csv(path, dtype={"cik10": str}) for path in CANDIDATE_FILES if path.exists()],
        ignore_index=True,
    ).drop_duplicates("cik10")
    audit = pd.read_csv(TIINGO_AUDIT, dtype={"cik10": str}) if TIINGO_AUDIT.exists() else pd.DataFrame()
    audited_ciks = set(audit["cik10"].str.zfill(10)) if not audit.empty else set()
    candidate_ciks = set(candidates["cik10"].str.zfill(10))
    pending_ciks = candidate_ciks - audited_ciks

    by_decision = readiness.groupby("decision_at", as_index=False).agg(
        company_rows=("cik10", "size"),
        validated_price_rows=("validated_price_available", "sum"),
        companyfacts_rows=("companyfacts_cached", "sum"),
    )
    by_decision["validated_price_coverage"] = by_decision["validated_price_rows"] / by_decision["company_rows"]
    by_decision["companyfacts_coverage"] = by_decision["companyfacts_rows"] / by_decision["company_rows"]
    minimum_price = float(by_decision["validated_price_coverage"].min())
    minimum_facts = float(by_decision["companyfacts_coverage"].min())
    unresolved_terminal = int(
        audit["audit_status"].eq("validated_early_delisting_needs_terminal_audit").sum()
    ) if not audit.empty else 0
    price_gate = minimum_price >= float(config["minimum_price_coverage_each_decision"])
    facts_gate = minimum_facts >= float(config["minimum_companyfacts_coverage"])
    provider_gate = not pending_ciks
    terminal_gate = unresolved_terminal == 0
    policy_gate = (
        config.get("base_selected_missing_company_treatment") == "hold_intended_weight_in_cash_for_holding_period"
        and float(config.get("adverse_selected_missing_company_return")) == -1.0
    )
    authorized = bool(price_gate and facts_gate and provider_gate and terminal_gate and policy_gate)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    by_decision.to_csv(OUTPUT / "decision_coverage.csv", index=False)
    pd.DataFrame({"cik10": sorted(pending_ciks)}).to_csv(OUTPUT / "pending_tiingo_ciks.csv", index=False)
    missing = readiness[~readiness["validated_price_available"].astype(bool)].copy()
    missing["base_treatment"] = config["base_selected_missing_company_treatment"]
    missing["adverse_selected_return"] = float(config["adverse_selected_missing_company_return"])
    missing.to_csv(OUTPUT / "missing_company_policy.csv", index=False)
    result = {
        "experiment": "sec_broad_research_gate_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "minimum_decision_price_coverage": minimum_price,
        "minimum_decision_companyfacts_coverage": minimum_facts,
        "overall_price_coverage": float(readiness["validated_price_available"].mean()),
        "overall_companyfacts_coverage": float(readiness["companyfacts_cached"].mean()),
        "free_tiingo_candidate_ciks": int(len(candidate_ciks)),
        "free_tiingo_audited_ciks": int(len(candidate_ciks & audited_ciks)),
        "free_tiingo_pending_ciks": int(len(pending_ciks)),
        "unconfirmed_early_delistings": unresolved_terminal,
        "missing_company_decision_rows_tagged": int(len(missing)),
        "price_coverage_gate_passed": price_gate,
        "companyfacts_gate_passed": facts_gate,
        "free_provider_queue_gate_passed": provider_gate,
        "terminal_outcome_gate_passed": terminal_gate,
        "missing_company_policy_gate_passed": policy_gate,
        "strategy_testing_authorized": authorized,
        "authorization_scope": config["authorization_scope"],
        "live_trading_enabled": False,
        "artifact_sha256": {
            "decision_coverage": sha256(OUTPUT / "decision_coverage.csv"),
            "pending_tiingo_ciks": sha256(OUTPUT / "pending_tiingo_ciks.csv"),
            "missing_company_policy": sha256(OUTPUT / "missing_company_policy.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Broad research gate v2\n\n"
        f"Minimum decision-level price coverage is **{minimum_price:.2%}** and Company Facts coverage is "
        f"**{minimum_facts:.2%}**. The authenticated free-provider queue has **{len(pending_ciks):,}** "
        f"candidates remaining. Missing selections are held as cash in the base case and assigned a total "
        f"loss in the adverse case. Research strategy testing is **{'authorized' if authorized else 'blocked'}**; "
        "live trading remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
