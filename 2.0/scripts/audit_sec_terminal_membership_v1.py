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
DEREGISTRATION_FORMS = {"15-12G", "15-12G/A", "15-12B", "15-12B/A"}
DELISTING_FORMS = {"25", "25-NSE"}
BANKRUPTCY_TERMINAL_ITEMS = {"2.05", "2.06", "3.01"}
BANKRUPTCY_DELISTING_WINDOW_DAYS = 90


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
        try:
            report_date = date.fromisoformat(recent.get("reportDate", [])[index])
        except (TypeError, ValueError, IndexError):
            report_date = None
        filings.append({
            "form": form,
            "filing_date": filing_date,
            "report_date": report_date,
            "accession": recent.get("accessionNumber", [])[index],
            "items": {item.strip() for item in str(recent.get("items", [])[index]).split(",")},
        })
    notices = [row for row in filings if row["form"] in DELISTING_FORMS]
    deregistrations = [row for row in filings if row["form"] in DEREGISTRATION_FORMS]
    periodic_rows = [row for row in filings if row["form"] in PERIODIC_FORMS]

    def has_later_periodic(terminal_date: date) -> bool:
        """Use the period covered, not a delayed filing date, as economic evidence."""
        return any(
            (row["report_date"] or row["filing_date"]) > terminal_date
            for row in periodic_rows
        )

    candidates = []
    for row in filings:
        if row["form"] != "8-K" or not CORE_ITEMS.issubset(row["items"]):
            continue
        nearby = [notice for notice in notices if abs((notice["filing_date"] - row["filing_date"]).days) <= 10]
        if "5.01" not in row["items"] and not nearby:
            continue
        if has_later_periodic(row["filing_date"]):
            continue
        candidates.append({
            **row,
            "nearby_25_nse": bool(nearby),
            "notice_accessions": [notice["accession"] for notice in nearby],
            "terminal_rule": "completion_8k",
        })
    # A Form 25 followed closely by a Form 15, with no later periodic filing,
    # independently confirms that the public equity registration ended. This
    # catches cash acquisitions and liquidations whose closing 8-K does not use
    # the exact merger item combination above, while excluding issuers that
    # continue to file periodic reports after a symbol transition.
    for notice in notices:
        nearby_dereg = [
            row for row in deregistrations
            if 0 <= (row["filing_date"] - notice["filing_date"]).days <= 45
        ]
        if not nearby_dereg:
            continue
        terminal_date = max([notice["filing_date"], *[row["filing_date"] for row in nearby_dereg]])
        if has_later_periodic(terminal_date):
            continue
        candidates.append({
            **notice,
            "filing_date": notice["filing_date"],
            "nearby_25_nse": True,
            "notice_accessions": [notice["accession"]],
            "terminal_rule": "form25_plus_form15_no_later_periodic",
        })

    # Bankruptcy can end the investable common equity before a Form 15 is filed.
    # Require Item 1.03 plus either a nearby exchange delisting notice or at
    # least two corroborating shutdown/delisting items, and reject the signal if
    # the issuer subsequently reports a later economic period. This is narrow
    # enough to avoid treating every Chapter 11 filing as an immediate terminal.
    for row in filings:
        if row["form"] != "8-K" or "1.03" not in row["items"]:
            continue
        nearby = [
            notice for notice in notices
            # A national-exchange suspension can precede a restructuring
            # filing.  One calendar quarter captures the same continuous
            # distress episode without treating old, unrelated delistings as
            # bankruptcy corroboration.
            if abs((notice["filing_date"] - row["filing_date"]).days)
            <= BANKRUPTCY_DELISTING_WINDOW_DAYS
        ]
        corroborating_items = row["items"] & BANKRUPTCY_TERMINAL_ITEMS
        if not nearby and len(corroborating_items) < 2:
            continue
        if has_later_periodic(row["filing_date"]):
            continue
        candidates.append({
            **row,
            "nearby_25_nse": bool(nearby),
            "notice_accessions": [notice["accession"] for notice in nearby],
            "terminal_rule": "bankruptcy_equity_termination",
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
            "terminal_reason": filing.get("terminal_rule", "completion_8k"),
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
        "rule": "completion 8-K, Form 25 plus Form 15, or strict bankruptcy-equity termination; no later economic reporting period",
        "strategy_testing_authorized": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC terminal membership audit v1\n\n"
        f"Audited **{len(company_by_cik)}** membership CIKs and found **{len(terminals)}** "
        "SEC-confirmed issuer terminations. Removal requires a qualifying completion, "
        "deregistration, or strictly corroborated bankruptcy event, with no later economic "
        "reporting period in a 10-K, 10-Q, 20-F, or 40-F.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
