#!/usr/bin/env python3
"""Identify SEC-confirmed issuer terminations across the recent membership panel."""

from __future__ import annotations

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "evidence/tiingo_delisted_coverage_probe_v1/membership_inventory_coverage.csv"
SEC_CACHE = ROOT / "data/sec_historical_identity_cache"
OUTPUT = ROOT / "evidence/sec_terminal_membership_v1"
PERIODIC_FORMS = {"10-K", "10-Q", "20-F", "40-F"}
CORE_ITEMS = {"2.01", "3.01"}


def terminal_filing(cik10: str) -> dict | None:
    path = SEC_CACHE / f"submissions_{cik10}.gz"
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()))
    recent = payload.get("filings", {}).get("recent", {})
    filings = []
    for index, form in enumerate(recent.get("form", [])):
        try:
            filing_date = date.fromisoformat(recent.get("filingDate", [])[index])
        except (TypeError, ValueError, IndexError):
            continue
        filings.append({
            "form": form,
            "filing_date": filing_date,
            "accession": recent.get("accessionNumber", [])[index],
            "items": {item.strip() for item in str(recent.get("items", [])[index]).split(",")},
        })
    notices = [row for row in filings if row["form"] == "25-NSE"]
    periodic_dates = [row["filing_date"] for row in filings if row["form"] in PERIODIC_FORMS]
    candidates = []
    for row in filings:
        if row["form"] != "8-K" or not CORE_ITEMS.issubset(row["items"]):
            continue
        nearby = [notice for notice in notices if abs((notice["filing_date"] - row["filing_date"]).days) <= 10]
        if "5.01" not in row["items"] and not nearby:
            continue
        later_periodic = [date for date in periodic_dates if date > row["filing_date"]]
        if later_periodic:
            continue
        candidates.append({
            **row,
            "nearby_25_nse": bool(nearby),
            "notice_accessions": [notice["accession"] for notice in nearby],
        })
    return max(candidates, key=lambda row: row["filing_date"]) if candidates else None


def main() -> int:
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    company_by_cik = membership.groupby("cik10")["company_name_as_filed"].last().to_dict()
    rows = []
    for cik10 in sorted(company_by_cik):
        filing = terminal_filing(cik10)
        if filing is None:
            continue
        rows.append({
            "cik10": cik10,
            "company_name": company_by_cik[cik10],
            "sec_terminal_date": filing["filing_date"].isoformat(),
            "completion_accession": filing["accession"],
            "completion_items": "|".join(sorted(filing["items"])),
            "nearby_25_nse": filing["nearby_25_nse"],
            "notice_accessions": "|".join(filing["notice_accessions"]),
            "later_periodic_filing": False,
            "terminal_reason": "sec_confirmed_merger_or_acquisition_completion",
        })
    terminals = pd.DataFrame(rows)
    if not terminals.empty:
        terminals = terminals.sort_values(["sec_terminal_date", "cik10"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    terminals.to_csv(OUTPUT / "sec_terminal_membership.csv", index=False)
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "membership_ciks_audited": int(len(company_by_cik)),
        "sec_confirmed_terminal_ciks": int(len(terminals)),
        "rule": "8-K Items 2.01 and 3.01 plus Item 5.01 or nearby Form 25-NSE, with no later periodic filing",
        "strategy_testing_authorized": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC terminal membership audit v1\n\n"
        f"Audited **{len(company_by_cik)}** membership CIKs and found **{len(terminals)}** "
        "SEC-confirmed issuer terminations. A company is removed only after an 8-K with "
        "Items 2.01 and 3.01 plus Item 5.01 or a nearby Form 25-NSE, and only when no later "
        "10-K, 10-Q, 20-F, or 40-F exists.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
