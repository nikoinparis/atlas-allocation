#!/usr/bin/env python3
"""Inventory the free-data work required before the broad SEC universe can be tested."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/sec_broad_universe_readiness_v2"
EXISTING = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
FACTS = ROOT / "data/sec_recent_companyfacts_cache_v1"
BATCHES = ROOT / "data/sec_broad_current_data_vintages"
RECOVERED_BATCHES = ROOT / "data/sec_broad_recovered_data_vintages"
MULTI_SYMBOL_BATCHES = ROOT / "data/sec_broad_multi_symbol_data_vintages"
TIINGO_KEYS = ROOT / "evidence/sec_broad_tiingo_audit_v2/validated_price_decision_keys.csv"
TERMINALS = ROOT / "evidence/sec_broad_terminal_membership_v2/sec_terminal_membership.csv"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", default="")
    return parser.parse_args()


def latest_broad_vintage() -> Path:
    values = sorted((ROOT / "data/sec_historical_universe_vintages").glob("*-sec-historical-filers-broad-v2"))
    if not values:
        raise RuntimeError("no broad-v2 SEC universe vintage found")
    return values[-1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    args = arguments()
    universe = Path(args.universe).resolve() if args.universe else latest_broad_vintage()
    membership = pd.read_csv(universe / "quarterly_membership.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    recent = membership[membership["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")].copy()
    terminal_removed_rows = 0
    if TERMINALS.exists():
        terminals = pd.read_csv(TERMINALS, dtype={"cik10": str})
        terminal_by_cik = {
            str(row.cik10).zfill(10): pd.Timestamp(row.sec_terminal_date, tz="UTC")
            for row in terminals.itertuples(index=False)
        }
        removed = recent.apply(
            lambda row: row["cik10"] in terminal_by_cik and row["decision_at"] > terminal_by_cik[row["cik10"]],
            axis=1,
        )
        terminal_removed_rows = int(removed.sum())
        recent = recent[~removed].copy()

    existing = pd.read_csv(EXISTING, dtype={"cik10": str}, parse_dates=["decision_at"])
    existing_keys = existing.loc[
        existing["execution_price_available"].astype(bool), ["decision_at", "cik10"]
    ].drop_duplicates().assign(existing_execution_price=True)
    if TIINGO_KEYS.exists():
        tiingo_keys = pd.read_csv(TIINGO_KEYS, dtype={"cik10": str}, parse_dates=["decision_at"])
        tiingo_keys["existing_execution_price"] = True
        existing_keys = pd.concat([existing_keys, tiingo_keys], ignore_index=True).drop_duplicates(["decision_at", "cik10"])
    recent = recent.merge(existing_keys, on=["decision_at", "cik10"], how="left")
    recent["existing_execution_price"] = recent["existing_execution_price"].fillna(False).astype(bool)

    batch_price_ciks: set[str] = set()
    attempted_price_ciks: set[str] = set()
    price_result_paths = [
        *sorted(BATCHES.glob("*/price_results.csv")),
        *sorted(RECOVERED_BATCHES.glob("*/price_results.csv")),
        *sorted(MULTI_SYMBOL_BATCHES.glob("*/price_results.csv")),
    ]
    for path in price_result_paths:
        frame = pd.read_csv(path, dtype={"cik10": str})
        attempted_price_ciks.update(frame["cik10"].astype(str))
        valid = frame["history_overlaps_eligible_interval"].astype(str).str.lower().eq("true")
        batch_price_ciks.update(frame.loc[valid, "cik10"].astype(str))
    recent["batch_price_available"] = recent["cik10"].isin(batch_price_ciks)
    recent["validated_price_available"] = recent["existing_execution_price"] | recent["batch_price_available"]
    recent["batch_price_attempted"] = recent["cik10"].isin(attempted_price_ciks)

    cached_facts = {
        path.stem.removeprefix("companyfacts_")
        for path in FACTS.glob("companyfacts_*.json")
    }
    recent["companyfacts_cached"] = recent["cik10"].isin(cached_facts)
    recent["single_current_ticker"] = (
        recent["current_tickers"].notna()
        & ~recent["current_tickers"].astype(str).str.contains("|", regex=False)
    )

    sector = recent.groupby("sector", as_index=False).agg(
        decision_rows=("cik10", "size"),
        unique_ciks=("cik10", "nunique"),
        validated_price_rows=("validated_price_available", "sum"),
        companyfacts_rows=("companyfacts_cached", "sum"),
        single_ticker_rows=("single_current_ticker", "sum"),
    )
    sector["validated_price_coverage"] = sector["validated_price_rows"] / sector["decision_rows"]
    sector["companyfacts_coverage"] = sector["companyfacts_rows"] / sector["decision_rows"]
    sector["single_ticker_coverage"] = sector["single_ticker_rows"] / sector["decision_rows"]

    issuers = recent.groupby("cik10", as_index=False).agg(
        company_name_as_filed=("company_name_as_filed", "last"),
        sector=("sector", "last"),
        current_tickers=("current_tickers", "last"),
        first_recent_decision=("decision_at", "min"),
        last_recent_decision=("decision_at", "max"),
        recent_decision_rows=("decision_at", "size"),
        validated_price_rows=("validated_price_available", "sum"),
        batch_price_attempted=("batch_price_attempted", "max"),
        companyfacts_cached=("companyfacts_cached", "max"),
        single_current_ticker=("single_current_ticker", "max"),
    )
    issuers["queue_status"] = "identity_recovery_required"
    issuers.loc[issuers["single_current_ticker"], "queue_status"] = "acquire_price_and_facts"
    issuers.loc[
        issuers["single_current_ticker"] & issuers["companyfacts_cached"], "queue_status"
    ] = "acquire_price_only"
    issuers.loc[
        (issuers["validated_price_rows"] == issuers["recent_decision_rows"]) & issuers["companyfacts_cached"],
        "queue_status",
    ] = "ready_validated_panel"
    issuers.loc[
        issuers["batch_price_attempted"] & (issuers["validated_price_rows"] < issuers["recent_decision_rows"]),
        "queue_status",
    ] = "identity_terminal_review_required"
    priority_order = {
        "acquire_price_only": 1,
        "acquire_price_and_facts": 2,
        "identity_recovery_required": 3,
        "identity_terminal_review_required": 3,
        "ready_validated_panel": 4,
    }
    issuers["priority"] = issuers["queue_status"].map(priority_order)
    issuers = issuers.sort_values(["priority", "sector", "last_recent_decision", "cik10"], ascending=[True, True, False, True])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    recent.to_csv(OUTPUT / "recent_membership_readiness.csv", index=False)
    sector.to_csv(OUTPUT / "sector_readiness.csv", index=False)
    issuers.to_csv(OUTPUT / "issuer_acquisition_queue.csv", index=False)
    counts = issuers["queue_status"].value_counts().to_dict()
    result = {
        "experiment": "sec_broad_universe_readiness_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "universe_vintage": universe.name,
        "recent_start": "2023-01-01",
        "recent_decisions": int(recent["decision_at"].nunique()),
        "recent_unique_ciks": int(recent["cik10"].nunique()),
        "sec_terminal_removed_decision_rows": terminal_removed_rows,
        "latest_members": int(recent.loc[recent["decision_at"].eq(recent["decision_at"].max()), "cik10"].nunique()),
        "validated_price_decision_coverage": float(recent["validated_price_available"].mean()),
        "new_batch_price_ciks": int(len(batch_price_ciks)),
        "attempted_batch_price_ciks": int(len(attempted_price_ciks)),
        "companyfacts_decision_coverage": float(recent["companyfacts_cached"].mean()),
        "single_current_ticker_decision_coverage": float(recent["single_current_ticker"].mean()),
        "issuer_queue_counts": {str(key): int(value) for key, value in counts.items()},
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
        "next_gate": "acquire and validate adjusted prices plus company facts, recover former identities, audit terminal outcomes, then require at least 95% decision-date coverage and missing-company stress tests",
        "artifact_sha256": {
            "recent_membership_readiness": sha256(OUTPUT / "recent_membership_readiness.csv"),
            "sector_readiness": sha256(OUTPUT / "sector_readiness.csv"),
            "issuer_acquisition_queue": sha256(OUTPUT / "issuer_acquisition_queue.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Broad SEC universe readiness v2\n\n"
        f"The point-in-time broad universe has **{result['recent_unique_ciks']:,}** unique companies from 2023 onward "
        f"and **{result['latest_members']:,}** at the latest decision. Existing validated price coverage spans "
        f"**{result['validated_price_decision_coverage']:.1%}** of company-decision rows; cached SEC company facts span "
        f"**{result['companyfacts_decision_coverage']:.1%}**.\n\n"
        "No broad-universe return test is authorized yet. The issuer queue prioritizes single-current-ticker companies, "
        "then explicitly routes former or ambiguous identities to recovery instead of dropping them.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
