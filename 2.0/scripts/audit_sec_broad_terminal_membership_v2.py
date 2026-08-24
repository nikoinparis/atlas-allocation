#!/usr/bin/env python3
"""Find SEC-confirmed terminal mergers among broad recovered-identity issuers."""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import audit_sec_terminal_membership_v1 as legacy


CACHE = ROOT / "data/sec_broad_identity_cache_v2"
OUTPUT = ROOT / "evidence/sec_broad_terminal_membership_v2"


def immutable_membership() -> Path:
    vintages = sorted((ROOT / "data/sec_historical_universe_vintages").glob("*-sec-historical-filers-broad-v2"))
    if not vintages:
        raise RuntimeError("no immutable broad-v2 universe vintage found")
    return vintages[-1] / "quarterly_membership.csv"


def main() -> int:
    legacy.SEC_CACHE = CACHE
    membership = pd.read_csv(immutable_membership(), dtype={"cik10": str}, parse_dates=["decision_at"])
    membership = membership[membership["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")]
    company_by_cik = membership.groupby("cik10")["company_name_as_filed"].last().to_dict()
    cached_ciks = {path.stem.removeprefix("submissions_") for path in CACHE.glob("submissions_*.gz")}
    audited_ciks = sorted(set(company_by_cik) & cached_ciks)

    def audit_one(cik10: str) -> dict | None:
        filing = legacy.terminal_filing(cik10)
        if filing is None:
            return None
        return {
            "cik10": cik10,
            "company_name": company_by_cik[cik10],
            "sec_terminal_date": filing["filing_date"].isoformat(),
            "completion_accession": filing["accession"],
            "completion_items": "|".join(sorted(filing["items"])),
            "nearby_25_nse": filing["nearby_25_nse"],
            "notice_accessions": "|".join(filing["notice_accessions"]),
            "later_periodic_filing": False,
            "terminal_reason": filing.get("terminal_rule", "completion_8k"),
        }

    # The immutable cache can contain over a thousand independent compressed
    # submissions.  Parallel read/decompression keeps the audit practical on
    # cloud-backed filesystems without changing deterministic sorted output.
    with ThreadPoolExecutor(max_workers=16) as executor:
        rows = [row for row in executor.map(audit_one, audited_ciks) if row is not None]
    terminals = pd.DataFrame(rows)
    if not terminals.empty:
        terminals = terminals.sort_values(["sec_terminal_date", "cik10"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    terminals.to_csv(OUTPUT / "sec_terminal_membership.csv", index=False)
    result = {
        "experiment": "sec_broad_terminal_membership_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "membership_ciks": int(len(company_by_cik)),
        "cached_submission_ciks_audited": int(len(audited_ciks)),
        "sec_confirmed_terminal_ciks": int(len(terminals)),
        "rule": "completion 8-K, Form 25 plus Form 15, or strict bankruptcy-equity termination; no later economic reporting period",
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
