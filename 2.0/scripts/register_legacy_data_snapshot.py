#!/usr/bin/env python3
"""Quarantine the 1.0 data hub in the immutable 2.0 vintage store."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import DataVintageError, SnapshotStore, sha256

SOURCE = ROOT.parent / "1.0/data/01_data_hub"
STORE_ROOT = ROOT / "data/vintages"
OUTPUT = ROOT / "evidence/data_vintage_store"
OBSERVED_AT = "2026-04-15T08:19:54.115905+00:00"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_derived_files(directory: Path) -> dict[str, Path]:
    prices = read_csv(SOURCE / "weekly_prices.csv")
    metadata = {row["ticker"]: row for row in read_csv(SOURCE / "universe_metadata.csv")}
    yahoo = {row["ticker"]: row for row in read_csv(SOURCE / "yahoo_metadata_snapshot.csv")}
    assets = [column for column in prices[0] if column != "Date"]
    security_rows = []
    membership_rows = []
    for ticker in assets:
        observed_dates = [row["Date"] for row in prices if row[ticker]]
        meta = metadata.get(ticker, {})
        info = yahoo.get(ticker, {})
        security_rows.append({
            "security_id": f"legacy-yahoo:{ticker}",
            "permanent_id_source": "synthetic_ticker_id_not_permanent",
            "ticker": ticker,
            "name": info.get("longName") or meta.get("description") or ticker,
            "exchange": "",
            "first_observed_date": min(observed_dates) if observed_dates else "",
            "last_observed_date": max(observed_dates) if observed_dates else "",
            "delisting_date": "",
            "knowledge_at_utc": OBSERVED_AT,
            "point_in_time_identity": "false",
        })
        membership_rows.append({
            "security_id": f"legacy-yahoo:{ticker}",
            "ticker": ticker,
            "universe": "portfolio_optimizer_1.0_current_etf_universe",
            "effective_from": "",
            "effective_to": "",
            "knowledge_at_utc": OBSERVED_AT,
            "source_revision": "legacy-import",
            "point_in_time_membership": "false",
            "selection_method": "current researched universe backfilled over history",
        })
    security_path = directory / "security_master.csv"
    membership_path = directory / "universe_membership.csv"
    write_csv(security_path, list(security_rows[0]), security_rows)
    write_csv(membership_path, list(membership_rows[0]), membership_rows)

    actions = []
    for row in read_csv(SOURCE / "etf_distribution_history.csv"):
        actions.append({
            "security_id": f"legacy-yahoo:{row['ticker']}",
            "ticker": row["ticker"],
            "event_date": row["Date"],
            "action_type": "cash_distribution",
            "amount": row["distribution"],
            "knowledge_at_utc": row["pull_timestamp_utc"],
            "source_revision": "yfinance.dividends_pull_2026-04-15",
            "source": row["source"],
        })
    actions_path = directory / "corporate_actions.csv"
    action_fields = ["security_id", "ticker", "event_date", "action_type", "amount", "knowledge_at_utc", "source_revision", "source"]
    write_csv(actions_path, action_fields, actions)
    delistings_path = directory / "delistings.csv"
    write_csv(
        delistings_path,
        ["security_id", "ticker", "delisting_date", "delisting_return", "reason", "knowledge_at_utc", "source_revision"],
        [],
    )
    return {
        "security_master.csv": security_path,
        "universe_membership.csv": membership_path,
        "corporate_actions.csv": actions_path,
        "delistings.csv": delistings_path,
    }


def build() -> dict[str, object]:
    store = SnapshotStore(STORE_ROOT)
    with tempfile.TemporaryDirectory() as temporary_name:
        derived = build_derived_files(Path(temporary_name))
        source_files = {
            "legacy_weekly_prices.csv": SOURCE / "weekly_prices.csv",
            "legacy_weekly_returns.csv": SOURCE / "weekly_returns.csv",
            "legacy_universe.json": SOURCE / "universe.json",
            "legacy_universe_metadata.csv": SOURCE / "universe_metadata.csv",
            "legacy_yahoo_metadata_snapshot.csv": SOURCE / "yahoo_metadata_snapshot.csv",
            "legacy_distribution_history.csv": SOURCE / "etf_distribution_history.csv",
            **derived,
        }
        descriptor = {
            "provider": "legacy_yahoo_via_yfinance",
            "dataset_kind": "legacy_etf_research_bundle",
            "observed_at_utc": OBSERVED_AT,
            "observed_at_basis": "conservative maximum pull_timestamp_utc in companion Yahoo metadata snapshot",
            "source_uri": "legacy://1.0/data/01_data_hub",
            "source_license": "Yahoo Finance/yfinance research cache; provider terms apply; not a licensed point-in-time feed",
            "revision_policy": "unknown; adjusted history may be revised retroactively",
            "publication_lag_policy": "unknown; strict store availability begins only at observed_at_utc",
            "coverage": {"weekly_start": "2005-01-07", "weekly_end": "2026-04-10", "etf_count": 35},
            "claims": {
                "point_in_time_prices": False,
                "point_in_time_universe": False,
                "permanent_security_ids": False,
                "corporate_actions": False,
                "delistings": False,
                "vintage_revisions": False,
            },
            "notes": [
                "The historical rows were learned in 2026 and cannot pass strict as-of gates for earlier simulations.",
                "Ticker-derived IDs are not permanent security identifiers.",
                "The universe is a current researched ETF list backfilled through history.",
                "Distribution events are cached, but split and delisting coverage is not proven.",
            ],
        }
        manifest = store.ingest(source_files, descriptor)

    historical_rejection = False
    production_claim_rejection = False
    try:
        store.select("2005-01-07T23:59:59+00:00")
    except DataVintageError:
        historical_rejection = True
    try:
        store.select("2026-08-08T23:59:59+00:00", required_claims=(
            "point_in_time_prices", "point_in_time_universe", "permanent_security_ids", "corporate_actions", "delistings"
        ))
    except DataVintageError:
        production_claim_rejection = True
    current_selection = store.select("2026-08-08T23:59:59+00:00")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_manifest": str(current_selection.manifest_path.resolve()),
        "snapshot_integrity_pass": store.verify(str(manifest["snapshot_id"])),
        "historical_lookahead_rejection_pass": historical_rejection,
        "production_claim_rejection_pass": production_claim_rejection,
        "historical_simulation_grade": manifest["historical_simulation_grade"],
        "claims": manifest["claims"],
        "source_hashes": {
            path.name: sha256(path) for path in [
                SOURCE / "weekly_prices.csv", SOURCE / "weekly_returns.csv", SOURCE / "universe.json",
                SOURCE / "universe_metadata.csv", SOURCE / "yahoo_metadata_snapshot.csv", SOURCE / "etf_distribution_history.csv",
            ]
        },
        "next_required_bundle": [
            "licensed or otherwise verified permanent security identifiers",
            "point-in-time universe membership with knowledge timestamps",
            "prices for active and delisted securities",
            "split, distribution, merger, and delisting events with revision identifiers",
            "multiple retained vintages so revisions can be detected",
        ],
    }


def report(result: dict[str, object]) -> str:
    return "\n".join([
        "# Versioned Data Store — Initial Snapshot", "",
        f"Snapshot: `{result['snapshot_id']}`", "",
        "The existing 1.0 ETF data is now stored as an immutable, hashed snapshot. It is deliberately labeled research-only and is unavailable to strict historical as-of queries before its April 2026 observation timestamp.", "",
        "## Enforced results", "",
        f"- File-integrity verification: **{'pass' if result['snapshot_integrity_pass'] else 'fail'}**.",
        f"- Attempted 2005 access rejected as future knowledge: **{'pass' if result['historical_lookahead_rejection_pass'] else 'fail'}**.",
        f"- Attempted production-grade selection rejected: **{'pass' if result['production_claim_rejection_pass'] else 'fail'}**.",
        f"- Historical simulation grade: **{result['historical_simulation_grade']}**.", "",
        "## Why this snapshot is not point-in-time", "",
        "The adjusted history was downloaded in 2026, its earlier vendor revisions are unavailable, the ETF list was selected with hindsight, ticker-derived identifiers are not permanent IDs, and complete split/delisting coverage is not proven. The store records those facts instead of allowing the data to satisfy production gates.", "",
        "## What the next vendor export must contain", "",
        *[f"- {item}." for item in result["next_required_bundle"]], "",
        "The ingestion command and schemas are ready for that export. Each future pull creates a new content-addressed snapshot; existing snapshots are never overwritten.", "",
    ])


def main() -> int:
    result = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
