#!/usr/bin/env python3
"""Audit decision-date coverage across Yahoo current/recovered and validated Tiingo."""

from __future__ import annotations

import argparse
import json
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
TIINGO_AUDIT = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1/candidate_audit.csv"
TERMINALS = ROOT / "evidence/tiingo_terminal_outcomes_v1/terminal_outcomes.csv"
SEC_TERMINALS = ROOT / "evidence/sec_terminal_membership_v1/sec_terminal_membership.csv"
RECOVERED_YAHOO_AUDIT = ROOT / "evidence/sec_recovered_price_probe_v1/recovered_symbol_price_audit.csv"
RECOVERED_YAHOO_RESULT = ROOT / "evidence/sec_recovered_price_probe_v1/result.json"
OUTPUT = ROOT / "evidence/combined_recent_price_panel_v1"


def current_yahoo_results() -> list[tuple[Path, pd.DataFrame]]:
    values = []
    for path in sorted((ROOT / "data/yahoo_recent_current_sec_price_vintages").glob("*/price_results.csv")):
        values.append((path.parent, pd.read_csv(path, dtype={"cik10": str})))
    return values


def read_dates(path: Path) -> list[pd.Timestamp]:
    frame = pd.read_csv(path, compression="gzip", usecols=[0])
    return sorted(pd.to_datetime(frame.iloc[:, 0], utc=True, errors="coerce").dropna().tolist())


def project_path(value: object) -> Path:
    path = Path(str(value))
    # Vintages written in different containers root at /project or /workspace/2.0.
    for prefix in ("/project/", "/workspace/2.0/"):
        if str(path).startswith(prefix):
            return ROOT / path.relative_to(prefix)
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recent-start", default="2023-01-01")
    parser.add_argument("--output-root", default=str(OUTPUT))
    args = parser.parse_args()
    output = Path(args.output_root).resolve()
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    membership = membership[membership["decision_at"] >= pd.Timestamp(args.recent_start, tz="UTC")].copy()

    source_by_cik: dict[str, dict] = {}
    for vintage, results in current_yahoo_results():
        for row in results[results["status"] == "ok"].to_dict("records"):
            source_by_cik[str(row["cik10"])] = {
                "price_source": "yahoo_current_sec",
                "price_file": vintage / row["history_file"],
                "ticker_used": row["yahoo_symbol"],
            }

    recovered_result = json.loads(RECOVERED_YAHOO_RESULT.read_text())
    recovered_root = project_path(recovered_result["price_vintage"])
    recovered = pd.read_csv(RECOVERED_YAHOO_AUDIT, dtype={"cik10": str})
    recovered = recovered[recovered["history_overlaps_eligible_interval"].astype(bool)]
    for row in recovered.to_dict("records"):
        source_by_cik.setdefault(str(row["cik10"]), {
            "price_source": "yahoo_recovered_former",
            "price_file": recovered_root / row["history_file"],
            "ticker_used": row["candidate_symbols"],
        })

    tiingo = pd.read_csv(TIINGO_AUDIT, dtype={"cik10": str})
    valid_statuses = {"validated_history_through_last_decision", "validated_early_delisting_needs_terminal_audit"}
    for row in tiingo[tiingo["audit_status"].isin(valid_statuses)].to_dict("records"):
        source_by_cik[str(row["cik10"])] = {
            "price_source": "tiingo_identity_validated",
            "price_file": project_path(row["price_file"]),
            "ticker_used": row["tiingo_symbol"],
        }

    dates_by_cik = {cik: read_dates(spec["price_file"]) for cik, spec in source_by_cik.items()}
    terminals = pd.read_csv(TERMINALS, dtype={"cik10": str}) if TERMINALS.exists() else pd.DataFrame()
    merger_end = {
        str(row["cik10"]): pd.Timestamp(row["last_price_date"], tz="UTC")
        for row in terminals.to_dict("records")
        if row.get("terminal_reason") == "merger_or_acquisition_completion"
    }
    if SEC_TERMINALS.exists():
        sec_terminals = pd.read_csv(SEC_TERMINALS, dtype={"cik10": str})
        for row in sec_terminals.to_dict("records"):
            cik = str(row["cik10"])
            terminal = pd.Timestamp(row["sec_terminal_date"], tz="UTC")
            merger_end[cik] = min(terminal, merger_end.get(cik, terminal))

    def classify(row: pd.Series) -> pd.Series:
        cik = str(row["cik10"])
        decision = row["decision_at"]
        terminal = merger_end.get(cik)
        if terminal is not None and terminal < decision:
            return pd.Series({
                "tradable_member": False, "execution_price_available": False,
                "panel_status": "removed_after_sec_confirmed_acquisition",
                "price_source": source_by_cik.get(cik, {}).get("price_source"),
                "ticker_used": source_by_cik.get(cik, {}).get("ticker_used"),
            })
        dates = dates_by_cik.get(cik, [])
        available = False
        if dates:
            index = bisect_left(dates, decision)
            available = index < len(dates) and dates[index] <= decision + pd.Timedelta(days=10)
        source = source_by_cik.get(cik, {})
        return pd.Series({
            "tradable_member": True,
            "execution_price_available": available,
            "panel_status": "execution_price_available" if available else "missing_validated_execution_price",
            "price_source": source.get("price_source"),
            "ticker_used": source.get("ticker_used"),
        })

    classified = membership.join(membership.apply(classify, axis=1))
    tradable = classified[classified["tradable_member"]].copy()
    coverage = tradable.groupby("decision_at", as_index=False).agg(
        tradable_members=("cik10", "nunique"),
        covered_members=("execution_price_available", "sum"),
    )
    coverage["missing_members"] = coverage["tradable_members"] - coverage["covered_members"]
    coverage["execution_price_coverage"] = coverage["covered_members"] / coverage["tradable_members"]
    source_coverage = (
        tradable[tradable["execution_price_available"]]
        .groupby(["decision_at", "price_source"], as_index=False)["cik10"].nunique()
        .rename(columns={"cik10": "covered_members"})
    )

    output.mkdir(parents=True, exist_ok=True)
    classified.to_csv(output / "classified_membership.csv", index=False)
    coverage.to_csv(output / "coverage_by_decision.csv", index=False)
    source_coverage.to_csv(output / "coverage_by_source.csv", index=False)
    missing = tradable[~tradable["execution_price_available"]]
    missing.to_csv(output / "missing_membership.csv", index=False)
    minimum_coverage = float(coverage["execution_price_coverage"].min())
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "recent_decisions": int(coverage["decision_at"].nunique()),
        "unique_members": int(membership["cik10"].nunique()),
        "unique_ciks_with_price_source": int(len(source_by_cik)),
        "current_yahoo_ciks": int(sum(spec["price_source"] == "yahoo_current_sec" for spec in source_by_cik.values())),
        "recovered_yahoo_ciks": int(sum(spec["price_source"] == "yahoo_recovered_former" for spec in source_by_cik.values())),
        "validated_tiingo_ciks": int(sum(spec["price_source"] == "tiingo_identity_validated" for spec in source_by_cik.values())),
        "sec_confirmed_acquisition_terminations": int(len(merger_end)),
        "minimum_decision_coverage": minimum_coverage,
        "median_decision_coverage": float(coverage["execution_price_coverage"].median()),
        "latest_decision_coverage": float(coverage.iloc[-1]["execution_price_coverage"]),
        "missing_company_decision_rows": int(len(missing)),
        "observed_coverage_gate_passed": minimum_coverage >= 0.95,
        "strategy_testing_authorized": False,
        "authorization_gate": "complete remaining recent-priority Tiingo batches, then require >=95% coverage at every recent decision plus missing-company adverse sensitivity",
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (output / "report.md").write_text(
        f"# Combined recent price-panel audit v1\n\nThe current panel combines **{result['current_yahoo_ciks']}** current-company Yahoo histories, **{result['recovered_yahoo_ciks']}** issuer-period-valid recovered Yahoo histories, and **{result['validated_tiingo_ciks']}** identity-validated Tiingo histories. SEC-confirmed acquisitions remove **{result['sec_confirmed_acquisition_terminations']}** companies after their final trading dates.\n\nDecision-date coverage is currently {result['minimum_decision_coverage']:.1%} at its minimum, {result['median_decision_coverage']:.1%} at the median, and {result['latest_decision_coverage']:.1%} at the latest decision. Missing companies remain explicit. Strategy testing is blocked until all recent-priority Tiingo batches finish and every recent decision reaches the declared 95% gate with an adverse missing-company sensitivity.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
