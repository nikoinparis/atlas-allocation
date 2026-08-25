#!/usr/bin/env python3
"""Normalize downloaded official IDX instance.zip filings into auditable CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.idx_fundamentals import normalize_xbrl_archive


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path, help="CSV with ticker, file_path, source_url, published_at")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    source_rows: list[dict[str, object]] = []
    fact_rows: list[dict[str, object]] = []
    issue_rows: list[dict[str, object]] = []
    with args.manifest.open(encoding="utf-8", newline="") as handle:
        filings = list(csv.DictReader(handle))
    for sequence, filing in enumerate(filings, start=1):
        source_id = filing.get("source_id") or f"IDX-FILING-{sequence:06d}"
        path = Path(filing["file_path"])
        if not path.is_absolute():
            path = (args.manifest.parent / path).resolve()
        source_row = {
            "source_id": source_id,
            "ticker": filing.get("ticker", ""),
            "source_name": "Indonesia Stock Exchange financial statement",
            "source_type": "official_xbrl_filing",
            "period": filing.get("period", ""),
            "as_of_date": filing.get("period_end", ""),
            "available_at": filing.get("published_at", ""),
            "retrieved_at": retrieved_at,
            "location": filing.get("source_url", ""),
            "local_file": str(path),
            "source_rank": "primary_official",
            "freshness": "historical_as_filed",
            "sha256": _sha256(path) if path.exists() else "",
            "notes": "",
        }
        source_rows.append(source_row)
        if not filing.get("published_at"):
            issue_rows.append({"source_id": source_id, "ticker": filing.get("ticker", ""), "severity": "blocker", "issue": "missing_required_source: publication timestamp"})
            continue
        if not path.exists():
            issue_rows.append({"source_id": source_id, "ticker": filing.get("ticker", ""), "severity": "blocker", "issue": "missing_required_source: local XBRL archive"})
            continue
        try:
            rows = normalize_xbrl_archive(
                path,
                ticker=filing.get("ticker", ""),
                source_id=source_id,
                source_location=filing.get("source_url", ""),
                retrieved_at=retrieved_at,
                available_at=filing["published_at"],
            )
            fact_rows.extend(rows)
            if not any(row["canonical_concept"] for row in rows):
                issue_rows.append({"source_id": source_id, "ticker": filing.get("ticker", ""), "severity": "warning", "issue": "no predeclared canonical concepts mapped"})
        except Exception as error:
            issue_rows.append({"source_id": source_id, "ticker": filing.get("ticker", ""), "severity": "blocker", "issue": f"XBRL parse failed: {type(error).__name__}: {error}"})
    source_fields = ["source_id", "ticker", "source_name", "source_type", "period", "as_of_date", "available_at", "retrieved_at", "location", "local_file", "source_rank", "freshness", "sha256", "notes"]
    fact_fields = ["ticker", "source_id", "source_name", "source_location", "retrieved_at", "available_at", "evidence_label", "confidence", "concept_namespace", "original_concept", "canonical_concept", "context_id", "entity_identifier", "period_start", "period_end", "period_type", "dimension_count", "consolidated_candidate", "unit_id", "unit", "decimals", "scale", "reported_value"]
    issue_fields = ["source_id", "ticker", "severity", "issue"]
    _write_csv(args.output_dir / "Source_Index.csv", source_rows, source_fields)
    _write_csv(args.output_dir / "Normalized_Financials_Long.csv", fact_rows, fact_fields)
    _write_csv(args.output_dir / "Normalization_Issues.csv", issue_rows, issue_fields)
    summary = {
        "created_at_utc": retrieved_at,
        "filings": len(filings),
        "normalized_facts": len(fact_rows),
        "canonical_facts": sum(bool(row["canonical_concept"]) for row in fact_rows),
        "issues": len(issue_rows),
        "blocking_issues": sum(row["severity"] == "blocker" for row in issue_rows),
        "research_only": True,
    }
    (args.output_dir / "normalization_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
