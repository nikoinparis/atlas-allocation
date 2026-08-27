#!/usr/bin/env python3
"""Build the immutable 10-K text acquisition queue; never substitute metadata for text."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP = ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz"
CACHES = [ROOT / "data/sec_historical_identity_cache", ROOT / "data/sec_broad_identity_cache_v2"]
OUTPUT = ROOT / "evidence/sec_language_change_readiness_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_from_submission(path: Path, cik10: str) -> list[dict]:
    try:
        with gzip.open(path, "rt") as handle:
            document = json.load(handle)
    except Exception:
        return []
    recent = document.get("filings", {}).get("recent", {})
    count = len(recent.get("accessionNumber", []))
    rows = []
    for index in range(count):
        form = str(recent.get("form", [None] * count)[index])
        if form != "10-K":
            continue
        filing_date = recent.get("filingDate", [None] * count)[index]
        if not filing_date or not ("2018-01-01" <= filing_date < "2026-04-01"):
            continue
        rows.append({
            "cik10": cik10,
            "accession": recent.get("accessionNumber", [None] * count)[index],
            "filing_date": filing_date,
            "report_date": recent.get("reportDate", [None] * count)[index],
            "primary_document": recent.get("primaryDocument", [None] * count)[index],
            "form": form,
        })
    return rows


def main() -> int:
    members = set(pd.read_csv(MEMBERSHIP, usecols=["cik10"], dtype={"cik10": str}).cik10)
    rows, source_hashes = [], {}
    for cik10 in sorted(members):
        candidates = [cache / f"submissions_{cik10}.gz" for cache in CACHES]
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        if path is not None:
            source_hashes[str(path.relative_to(ROOT))] = sha256(path)
            rows.extend(rows_from_submission(path, cik10))
    queue = pd.DataFrame(rows)
    if not queue.empty:
        queue["filing_date"] = pd.to_datetime(queue.filing_date)
        queue = queue.sort_values(["cik10", "filing_date"])
        queue["prior_accession"] = queue.groupby("cik10").accession.shift(1)
        queue["prior_filing_date"] = queue.groupby("cik10").filing_date.shift(1)
        queue["has_year_over_year_pair"] = queue.prior_accession.notna()
        queue["archive_url"] = queue.apply(
            lambda row: f"https://www.sec.gov/Archives/edgar/data/{int(row.cik10)}/{str(row.accession).replace('-', '')}/{row.primary_document}", axis=1)
    local_documents = list(ROOT.glob("data/**/*.htm")) + list(ROOT.glob("data/**/*.html"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    queue.to_csv(OUTPUT / "filing_text_acquisition_queue.csv", index=False)
    result = {
        "experiment": "sec_language_change_readiness_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "membership_sha256": sha256(MEMBERSHIP),
        "submissions_sources": len(source_hashes),
        "ten_k_filings_queued": int(len(queue)),
        "issuers_with_year_over_year_pairs": int(queue.loc[queue.has_year_over_year_pair, "cik10"].nunique()) if not queue.empty else 0,
        "local_filing_body_documents": len(local_documents),
        "status": "blocked_filing_body_text_not_acquired" if not local_documents else "source_documents_present_requires_hash_audit",
        "performance_evaluated": False,
        "reason": "Submissions metadata proves filing dates and accession identities but contains no filing language. Treating metadata as text would fabricate the Lazy Prices signal.",
        "required_next_step": "Acquire and hash the queued primary documents under SEC fair-access rules, parse stable sections, then compare each filing only with the issuer's prior filing.",
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "source_hashes.json").write_text(json.dumps(source_hashes, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC language-change readiness v1\n\n"
        f"The point-in-time queue contains **{len(queue):,}** 10-K filings and "
        f"**{result['issuers_with_year_over_year_pairs']:,}** issuers with at least one prior-year comparison. "
        "The repository has no cached filing body text, so no language-change score or return was computed. "
        "This branch is source-blocked, not rejected.\n"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
