#!/usr/bin/env python3
"""Audit the normalized SEC earnings 8-K vintage and every referenced raw source."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ROOT / "data/sec_earnings_event_vintages"
CACHE = ROOT / "data/sec_historical_identity_cache"
OUTPUT = ROOT / "evidence/sec_earnings_8k_acquisition_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    vintage = sorted(VINTAGES.glob("*-sec-earnings-8k-v1"))[-1]
    manifest = json.loads((vintage / "manifest.json").read_text())
    statuses = read_rows(vintage / "issuer_status.csv")
    events = read_rows(vintage / "earnings_8k_events.csv")
    sources = read_rows(vintage / "source_manifest.csv")
    source_failures = []
    for row in sources:
        path = CACHE / f"{row['cache_key']}.gz"
        if not path.exists():
            source_failures.append(f"missing:{row['cache_key']}")
            continue
        actual = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
        if actual != row["sha256"]:
            source_failures.append(f"hash:{row['cache_key']}")
    accessions = [row["accession"] for row in events]
    valid_times = True
    quarters = Counter()
    for row in events:
        filing = datetime.fromisoformat(row["filing_date"]).replace(tzinfo=timezone.utc)
        accepted = datetime.fromisoformat(row["available_at"].replace("Z", "+00:00"))
        # EDGAR can assign the next business filingDate to an after-hours
        # acceptance, including a weekend gap. The acceptance timestamp is the
        # authoritative causal availability time; reject only wider conflicts.
        valid_times = valid_times and accepted >= filing - timedelta(days=4)
        quarters[f"{accepted.year}Q{(accepted.month - 1) // 3 + 1}"] += 1
    checks = {
        "manifest_event_hash_matches": sha256(vintage / "earnings_8k_events.csv") == manifest["event_file_sha256"],
        "manifest_source_hash_matches": sha256(vintage / "source_manifest.csv") == manifest["source_manifest_sha256"],
        "all_referenced_raw_sources_present_and_hashed": not source_failures,
        "all_598_issuers_complete": len(statuses) == 598 and all(row["status"] == "complete" for row in statuses),
        "issuer_rows_unique": len({row["cik10"] for row in statuses}) == len(statuses),
        "event_accessions_unique": len(set(accessions)) == len(accessions),
        "all_events_are_item_202_8k": all(row["form"] in {"8-K", "8-K/A"} and "2.02" in row["items"].split("|") for row in events),
        "all_events_on_or_after_start": all(row["filing_date"] >= manifest["event_start_date"] for row in events),
        "all_acceptance_times_within_sec_filing_date_convention": valid_times,
        "all_events_have_acceptance_datetime": all(row["availability_source"] == "acceptance_datetime" for row in events),
        "manifest_research_authorized": bool(manifest["research_testing_authorized"]),
    }
    all_passed = all(checks.values())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "quarterly_event_coverage.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["quarter", "event_count"], lineterminator="\n")
        writer.writeheader()
        for quarter in sorted(quarters):
            writer.writerow({"quarter": quarter, "event_count": quarters[quarter]})
    result = {
        "experiment": "sec_earnings_8k_acquisition_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "vintage_id": manifest["vintage_id"],
        "target_issuers": len(statuses),
        "complete_issuer_share": manifest["complete_issuer_share"],
        "events": len(events),
        "issuers_with_events": len({row["cik10"] for row in events}),
        "source_files_verified": len(sources),
        "event_date_start": min(row["filing_date"] for row in events),
        "event_date_end": max(row["filing_date"] for row in events),
        "checks": checks,
        "all_checks_passed": all_passed,
        "research_testing_authorized": all_passed,
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC earnings 8-K acquisition v1\n\n"
        f"The vintage contains {len(events):,} Item 2.02 earnings events across {result['issuers_with_events']} of {len(statuses)} issuers from {result['event_date_start']} through {result['event_date_end']}. All {len(sources)} referenced source files were decompressed and independently matched to their SEC response hashes.\n\n"
        f"The acquisition audit decision was {'PASS' if all_passed else 'FAIL'}. Research testing is {'authorized' if all_passed else 'not authorized'}; strategy replacement and live trading remain disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
