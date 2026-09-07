#!/usr/bin/env python3
"""Flatten 62 quarters of SEC Form 4 into one table of open-market insider purchases.

Reads both caches -- data/sec_form4_history_v1 (2011Q1-2022Q4) and the existing
data/sec_form4_bulk_vintages (2023Q1-2026Q2) -- joins SUBMISSION, REPORTINGOWNER
and NONDERIV_TRANS, and keeps only genuine open-market buys: transaction code P
with an acquired/disposed code of A.

Two details that decide whether the result is causal:

The FILING date is kept alongside the transaction date and everything downstream
keys on the filing date, because that is when the market could have known. Form 4
is due within two business days but late filings exist and using the transaction
date would leak.

Purchases are counted by DISTINCT OWNER, not by filing. One officer splitting a
buy across five filings in a week is one insider buying, and counting filings
would let a single person look like a cluster -- which is precisely the
concentration failure Steps 125-126 died on.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [ROOT / "data/sec_form4_history_v1",
           ROOT / "data/sec_form4_bulk_vintages/20260815T005416Z-sec-form4-bulk-v1/raw"]
OUTPUT = ROOT / "data/form4_purchase_panel_v1"
EVIDENCE = ROOT / "evidence/form4_opportunistic_v1"


def read_member(archive: zipfile.ZipFile, name: str, columns: list[str]) -> pd.DataFrame:
    with archive.open(name) as handle:
        return pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"),
                           sep="\t", usecols=columns, low_memory=False)


def main() -> int:
    archives = sorted({p.name: p for source in SOURCES if source.is_dir()
                       for p in source.glob("*_form345.zip")}.items())
    if not archives:
        raise SystemExit("no form345 archives found")

    frames, skipped = [], []
    for name, path in archives:
        try:
            with zipfile.ZipFile(path) as archive:
                submission = read_member(archive, "SUBMISSION.tsv",
                    ["ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"])
                owners = read_member(archive, "REPORTINGOWNER.tsv",
                    ["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNER_RELATIONSHIP"])
                trans = read_member(archive, "NONDERIV_TRANS.tsv",
                    ["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE",
                     "TRANS_SHARES", "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"])
        except Exception as error:                   # noqa: BLE001
            skipped.append(f"{name}:{type(error).__name__}")
            continue

        trans = trans[(trans.TRANS_CODE.astype(str).str.strip() == "P")
                      & (trans.TRANS_ACQUIRED_DISP_CD.astype(str).str.strip() == "A")]
        if trans.empty:
            continue
        submission = submission[submission.DOCUMENT_TYPE.astype(str).str.strip().isin(["4", "4/A"])]
        merged = trans.merge(submission, on="ACCESSION_NUMBER", how="inner") \
                      .merge(owners, on="ACCESSION_NUMBER", how="inner")
        frames.append(merged)

    panel = pd.concat(frames, ignore_index=True)
    panel["filing_date"] = pd.to_datetime(panel.FILING_DATE, format="%d-%b-%Y",
                                          errors="coerce", utc=True)
    panel["trans_date"] = pd.to_datetime(panel.TRANS_DATE, format="%d-%b-%Y",
                                         errors="coerce", utc=True)
    panel = panel.dropna(subset=["filing_date", "trans_date", "ISSUERCIK", "RPTOWNERCIK"])

    # A filing that reports a transaction from before the issuer existed, or dated
    # after it was filed, is a data error rather than a signal.
    panel = panel[panel.trans_date <= panel.filing_date]

    panel["cik10"] = panel.ISSUERCIK.astype("int64").astype(str).str.zfill(10)
    panel["owner_cik"] = panel.RPTOWNERCIK.astype("int64").astype(str)
    panel["shares"] = pd.to_numeric(panel.TRANS_SHARES, errors="coerce")
    panel["price"] = pd.to_numeric(panel.TRANS_PRICEPERSHARE, errors="coerce")
    panel["relationship"] = panel.RPTOWNER_RELATIONSHIP.astype(str)
    panel["symbol"] = panel.ISSUERTRADINGSYMBOL.astype(str).str.upper()

    keep = ["filing_date", "trans_date", "cik10", "owner_cik", "symbol",
            "shares", "price", "relationship", "ACCESSION_NUMBER"]
    panel = panel[keep].rename(columns={"ACCESSION_NUMBER": "accession"})
    panel = panel.drop_duplicates(subset=["accession", "owner_cik", "trans_date", "shares"])
    panel = panel.sort_values(["filing_date", "cik10", "owner_cik"])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "insider_purchases.csv.gz"
    panel.to_csv(target, index=False, compression="gzip")

    lag = (panel.filing_date - panel.trans_date).dt.days
    result = {
        "archives_read": len(archives), "archives_skipped": skipped,
        "purchase_rows": int(len(panel)),
        "distinct_issuers": int(panel.cik10.nunique()),
        "distinct_owners": int(panel.owner_cik.nunique()),
        "first_filing": str(panel.filing_date.min().date()),
        "last_filing": str(panel.filing_date.max().date()),
        "filing_lag_days": {"median": float(lag.median()), "p90": float(lag.quantile(0.90)),
                            "over_10_days_share": float((lag > 10).mean())},
        "output": str(target.relative_to(ROOT)),
        "counted_by": "distinct owner, not by filing",
        "keyed_on": "filing date, not transaction date",
    }
    (EVIDENCE / "panel.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
