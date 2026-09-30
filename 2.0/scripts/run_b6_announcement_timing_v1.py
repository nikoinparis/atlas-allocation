#!/usr/bin/env python3
"""B6 announcement-timing test, 2011-2018 -- coverage gate only (Step 329).

The test itself is not run. This script checks, before anything else, whether the
SEC 8-K Item 2.02 dates on disk cover the point-in-time tech-and-energy universe
over 2012-2018. It writes the coverage table and refuses to go further if the
share of members with a dated announcement falls below the gate.

No returns are read. No signal is built.
"""

from __future__ import annotations

import collections
import glob
import gzip
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/sec_historical_identity_cache"
MEMBERSHIP = ROOT / "data/sec_historical_universe_vintages/20260905T055015Z-sec-historical-filers-v1/quarterly_membership.csv"
VINTAGE = ROOT / "data/sec_earnings_event_vintages/20260821T035516Z-sec-earnings-8k-v1/manifest.json"
OUT = ROOT / "evidence/b6_announcement_timing_v1"
# An expected-date signal needs a prior dated announcement for nearly every member.
COVERAGE_GATE = 0.80


def cached_item_202_events() -> tuple[dict[str, set[str]], dict[str, int], int, int]:
    """Item 2.02 8-K filers per year from every cached SEC submissions payload."""
    payloads: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
    for path in glob.glob(str(CACHE / "submissions_*.gz")):
        key = os.path.basename(path)[:-3]
        payloads[key.split("_")[1]].append((key, json.loads(gzip.decompress(Path(path).read_bytes()))))
    filers: dict[str, set[str]] = collections.defaultdict(set)
    events: dict[str, int] = collections.Counter()
    unfetched_pages = 0
    for cik, items in payloads.items():
        fetched = {key for key, _ in items}
        for _, payload in items:
            recent = payload.get("filings", {}).get("recent", payload)
            for spec in payload.get("filings", {}).get("files", []) if "filings" in payload else []:
                if f"submissions_{cik}_{spec['name'][:-5]}" not in fetched and str(spec.get("filingTo", "")) >= "2011":
                    unfetched_pages += 1
            for form, item, filed in zip(recent.get("form", []), recent.get("items", []), recent.get("filingDate", [])):
                if form in {"8-K", "8-K/A"} and "2.02" in str(item) and "2011" <= filed[:4] <= "2018":
                    filers[filed[:4]].add(cik)
                    events[filed[:4]] += 1
    return filers, events, len(payloads), unfetched_pages


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    vintage = json.loads(VINTAGE.read_text())
    filers, events, cached_issuers, unfetched = cached_item_202_events()
    members = pd.read_csv(MEMBERSHIP, usecols=["decision_at", "cik10"], dtype={"cik10": str})
    members["year"] = members["decision_at"].str[:4]
    rows = []
    for year in map(str, range(2012, 2019)):
        roster = set(members.loc[members["year"] == year, "cik10"])
        covered = roster & filers[year]
        rows.append({"year": year, "pit_members": len(roster), "members_with_item_202_event": len(covered),
                     "coverage_share": round(len(covered) / len(roster), 4), "cached_item_202_events_all_issuers": events[year]})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "coverage_2012_2018.csv", index=False)
    window_ciks = set(members.loc[members["year"] <= "2018", "cik10"])
    cached_ciks = {os.path.basename(p)[:-3].split("_")[1] for p in glob.glob(str(CACHE / "submissions_*.gz"))}
    result = {
        "step": 329,
        "gate": "8-K Item 2.02 coverage of the point-in-time tech-and-energy universe, 2012-2018",
        "coverage_gate": COVERAGE_GATE,
        "normalized_8k_vintage_event_start": vintage["event_start_date"],
        "normalized_8k_vintage_events_before_2019": 0,
        "cached_submission_issuers": cached_issuers,
        "pit_unique_ciks_2012_2018": len(window_ciks),
        "pit_ciks_with_any_cached_submissions": len(window_ciks & cached_ciks),
        "unfetched_history_pages_overlapping_2011_onward": unfetched,
        "min_year_coverage": float(table["coverage_share"].min()),
        "max_year_coverage": float(table["coverage_share"].max()),
        "passes": bool(table["coverage_share"].min() >= COVERAGE_GATE),
        "returns_read": False,
        "signal_built": False,
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(table.to_string(index=False))
    print(json.dumps(result, indent=2))
    if not result["passes"]:
        print("STOP: coverage below gate; the B6 test is not run.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
