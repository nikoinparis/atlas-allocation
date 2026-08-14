#!/usr/bin/env python3
"""Measure whether recovered Yahoo histories actually cover SEC membership decisions."""

from __future__ import annotations

import gzip
import json
from bisect import bisect_left
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "evidence/sec_historical_identity_v1"
OUTPUT = ROOT / "evidence/sec_recovered_price_probe_v1"


def latest(pattern: str) -> Path:
    return sorted(ROOT.glob(pattern))[-1]


def main() -> int:
    price = latest("data/sec_recovered_price_probe_vintages/*/manifest.json").parent
    pulls = pd.read_csv(price / "price_probe_results.csv")
    identities = pd.read_csv(IDENTITY / "combined_identity_map.csv", dtype={"cik10": str})
    membership = pd.read_csv(IDENTITY / "membership_with_candidate_symbols.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    recovered = identities[
        identities["single_symbol_usable_for_price_probe"].astype(bool)
        & identities["symbol_source"].isin(["last_filing_inline_xbrl", "last_filing_instance_xbrl"])
    ][["cik10", "candidate_symbols", "company_name_as_filed", "sector", "symbol_source"]]
    audit = recovered.merge(pulls, left_on="candidate_symbols", right_on="ticker", how="left")
    intervals = membership.groupby("cik10", as_index=False).agg(
        first_eligible_decision=("decision_at", "min"), last_eligible_decision=("decision_at", "max")
    )
    audit = audit.merge(intervals, on="cik10", how="left")
    audit["first_observed_date"] = pd.to_datetime(audit["first_observed_date"], utc=True, errors="coerce")
    audit["last_observed_date"] = pd.to_datetime(audit["last_observed_date"], utc=True, errors="coerce")
    audit["history_overlaps_eligible_interval"] = (
        audit["status"].eq("ok")
        & (audit["first_observed_date"] <= audit["last_eligible_decision"] + pd.Timedelta(days=10))
        & (audit["last_observed_date"] >= audit["first_eligible_decision"] - pd.Timedelta(days=10))
    )
    audit["issuer_period_probe_status"] = "no_free_history"
    audit.loc[audit["status"].eq("ok") & ~audit["history_overlaps_eligible_interval"], "issuer_period_probe_status"] = "history_outside_eligible_period_possible_ticker_reuse"
    audit.loc[audit["history_overlaps_eligible_interval"], "issuer_period_probe_status"] = "history_overlaps_eligible_period"

    dates_by_symbol: dict[str, list[pd.Timestamp]] = {}
    for row in pulls[pulls["status"] == "ok"].itertuples(index=False):
        path = price / row.history_file
        frame = pd.read_csv(path, compression="gzip", usecols=[0])
        values = sorted(pd.to_datetime(frame.iloc[:, 0], utc=True, errors="coerce").dropna().tolist())
        dates_by_symbol[row.ticker] = values

    def has_execution_price(row: pd.Series) -> bool:
        dates = dates_by_symbol.get(str(row["candidate_symbols"]), [])
        if not dates:
            return False
        decision = row["decision_at"]
        index = bisect_left(dates, decision)
        return index < len(dates) and dates[index] <= decision + pd.Timedelta(days=10)

    recovered_membership = membership[membership["symbol_source"].isin(["last_filing_inline_xbrl", "last_filing_instance_xbrl"])].copy()
    recovered_membership["free_execution_price_available"] = recovered_membership.apply(has_execution_price, axis=1)
    by_decision = membership.groupby("decision_at", as_index=False).agg(members=("cik10", "nunique"))
    current = membership[membership["symbol_source"] == "current_sec_mapping"].groupby("decision_at")["cik10"].nunique()
    recovered_ok = recovered_membership[recovered_membership["free_execution_price_available"]].groupby("decision_at")["cik10"].nunique()
    by_decision["current_mapping_unprobed"] = by_decision["decision_at"].map(current).fillna(0).astype(int)
    by_decision["recovered_with_execution_price"] = by_decision["decision_at"].map(recovered_ok).fillna(0).astype(int)
    by_decision["optimistic_coverage_if_all_current_symbols_work"] = (
        by_decision["current_mapping_unprobed"] + by_decision["recovered_with_execution_price"]
    ) / by_decision["members"]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUTPUT / "recovered_symbol_price_audit.csv", index=False)
    recovered_membership.to_csv(OUTPUT / "recovered_membership_price_coverage.csv", index=False)
    by_decision.to_csv(OUTPUT / "coverage_upper_bound_by_decision.csv", index=False)
    status_counts = audit["issuer_period_probe_status"].value_counts().to_dict()
    recent = by_decision[by_decision["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")]
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "price_vintage": str(price),
        "recovered_symbols_requested": int(len(audit)),
        "raw_histories_returned": int(audit["status"].eq("ok").sum()),
        "histories_overlapping_issuer_eligible_period": int(audit["history_overlaps_eligible_interval"].sum()),
        "raw_history_rate": float(audit["status"].eq("ok").mean()),
        "issuer_period_overlap_rate": float(audit["history_overlaps_eligible_interval"].mean()),
        "status_counts": {str(key): int(value) for key, value in status_counts.items()},
        "recent_optimistic_coverage_min": float(recent["optimistic_coverage_if_all_current_symbols_work"].min()),
        "latest_optimistic_coverage": float(by_decision.iloc[-1]["optimistic_coverage_if_all_current_symbols_work"]),
        "interpretation": "upper bound assumes every current SEC symbol has valid historical prices; those symbols have not yet been probed",
        "strategy_testing_authorized": False,
        "blocker": "free Yahoo coverage of recovered former/delisted symbols is insufficient and delisting returns are absent",
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = f"""# Recovered-symbol free-price probe v1

Yahoo returned histories for **{result['raw_histories_returned']} of {result['recovered_symbols_requested']}** usable SEC-recovered former-company symbols ({result['raw_history_rate']:.1%}). Only **{result['histories_overlapping_issuer_eligible_period']}** histories overlap the corresponding issuer's eligible SEC period ({result['issuer_period_overlap_rate']:.1%}); non-overlapping histories are treated as possible ticker reuse, not valid observations.

Even under the optimistic assumption that every current SEC ticker has valid history, total universe coverage falls as low as **{result['recent_optimistic_coverage_min']:.1%}** from 2023 onward. Yahoo also supplies no complete delisting-return table. A survivorship-safe strategy backtest is therefore blocked; failed symbols must not be silently deleted.
"""
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
