#!/usr/bin/env python3
"""Join 13F issuers to this project's cik10 universe, and measure whether it worked.

13F identifies issuers by CUSIP. This project's universe is keyed by cik10. There
is no free official crosswalk between them, so the join goes through issuer names,
and a name join is exactly the kind of thing that quietly half-works. Steps 210
and 211 found a present-day ticker file silently rewriting universe history; the
lesson taken from that was that identity joins here get measured rather than
assumed.

So this produces a map and a match rate, and the registry declared in advance that
below 50% of panel issuers matched the graph is too sparse to trust and the
experiment stops.

No signal is computed here.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / "data/sec_13f_datasets_v1"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"

SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "PLC",
    "LP", "LLC", "LLP", "NV", "SA", "AG", "SE", "ADR", "ADS", "CL", "CLASS", "COM", "COMMON",
    "STOCK", "SHS", "SHARES", "HOLDINGS", "HOLDING", "GROUP", "THE", "NEW", "TR", "TRUST",
    "PARTNERS", "PARTNERSHIP", "USA", "US", "AMERICA", "AMERICAN", "INTERNATIONAL", "INTL",
}
PUNCT = re.compile(r"[^A-Z0-9 ]+")
SPACES = re.compile(r"\s+")


def normalise(name: object) -> str:
    text = PUNCT.sub(" ", str(name).upper())
    words = [w for w in SPACES.sub(" ", text).strip().split() if w not in SUFFIXES]
    return " ".join(words)


def read_member(archive: zipfile.ZipFile, member: str, usecols: list[str]) -> pd.DataFrame:
    with archive.open(member) as handle:
        return pd.read_csv(io.TextIOWrapper(handle, encoding="utf-8", errors="ignore"),
                           sep="\t", usecols=usecols, low_memory=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/institutional_linkage_v1")
    args = parser.parse_args()

    archives = sorted(ARCHIVES.glob("*.zip"))
    if not archives:
        raise SystemExit("no 13F archives on disk")

    names: dict[str, Counter] = {}
    holdings_rows = []
    for path in archives:
        with zipfile.ZipFile(path) as archive:
            members = set(archive.namelist())
            if "INFOTABLE.tsv" not in members or "SUBMISSION.tsv" not in members:
                continue
            submissions = read_member(archive, "SUBMISSION.tsv",
                                      ["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE",
                                       "CIK", "PERIODOFREPORT"])
            submissions = submissions[submissions.SUBMISSIONTYPE.astype(str).str.startswith("13F-HR")]
            info = read_member(archive, "INFOTABLE.tsv",
                               ["ACCESSION_NUMBER", "NAMEOFISSUER", "CUSIP", "VALUE", "PUTCALL"])
            info = info[info.PUTCALL.isna()]           # options are not holdings of the stock
            info["CUSIP"] = info.CUSIP.astype(str).str.upper().str.strip()
            for cusip, issuer in zip(info.CUSIP, info.NAMEOFISSUER):
                names.setdefault(cusip, Counter())[normalise(issuer)] += 1
            merged = info.merge(submissions[["ACCESSION_NUMBER", "FILING_DATE", "CIK", "PERIODOFREPORT"]],
                                on="ACCESSION_NUMBER", how="inner")
            holdings_rows.append(merged[["CIK", "CUSIP", "FILING_DATE", "PERIODOFREPORT", "VALUE"]])
        print(f"  read {path.name}", flush=True)

    holdings = pd.concat(holdings_rows, ignore_index=True)
    holdings["FILING_DATE"] = pd.to_datetime(holdings.FILING_DATE, format="%d-%b-%Y", errors="coerce")
    holdings["PERIODOFREPORT"] = pd.to_datetime(holdings.PERIODOFREPORT, format="%d-%b-%Y", errors="coerce")
    holdings = holdings.dropna(subset=["FILING_DATE", "CUSIP", "CIK"])

    cusip_name = pd.DataFrame(
        [{"cusip": c, "issuer_name": counter.most_common(1)[0][0]} for c, counter in names.items()])

    members = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    members["normalised"] = members.company_name_as_filed.map(normalise)
    roster = members.drop_duplicates("cik10")[["cik10", "normalised"]]
    unique_roster = roster.groupby("normalised").cik10.nunique()
    unambiguous = set(unique_roster[unique_roster == 1].index)
    lookup = roster[roster.normalised.isin(unambiguous)].drop_duplicates("normalised")

    mapped = cusip_name.merge(lookup, left_on="issuer_name", right_on="normalised", how="inner")
    matched_ciks = set(mapped.cik10)
    panel_ciks = set(members.cik10)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    mapped[["cusip", "issuer_name", "cik10"]].to_csv(out / "cusip_to_cik10.csv", index=False)
    holdings.to_parquet(out / "holdings.parquet", index=False)

    result = {
        "experiment": "institutional_linkage_identity_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "archives_read": len(archives),
        "holding_rows": int(len(holdings)),
        "distinct_managers": int(holdings.CIK.nunique()),
        "distinct_cusips": int(holdings.CUSIP.nunique()),
        "filing_date_range": [str(holdings.FILING_DATE.min().date()), str(holdings.FILING_DATE.max().date())],
        "identity": {
            "cusips_with_a_name": int(len(cusip_name)),
            "roster_names_unambiguous": int(len(lookup)),
            "cusips_matched_to_cik10": int(len(mapped)),
            "panel_issuers": len(panel_ciks),
            "panel_issuers_matched": len(matched_ciks & panel_ciks),
            "panel_match_rate": round(len(matched_ciks & panel_ciks) / max(1, len(panel_ciks)), 4),
        },
        "gate": "declared in advance: below 0.50 panel match rate the graph is too sparse and this stops",
        "computes_no_signal": True,
        "live_trading_enabled": False,
    }
    result["gate_passed"] = bool(result["identity"]["panel_match_rate"] >= 0.50)
    (out / "identity_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
