#!/usr/bin/env python3
"""Build a point-in-time IDX80 fundamental panel from archived IDX ratio tables."""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLUMNS = [
    "row_number", "sector", "sub_industry_code", "sub_industry", "ticker",
    "stock_name", "sharia", "fs_date", "fiscal_year_end", "fs_type",
    "auditor_opinion", "assets_b_idr", "liabilities_b_idr", "equity_b_idr",
    "sales_b_idr", "ebt_b_idr", "profit_period_b_idr", "profit_owners_b_idr",
    "eps_idr", "book_value_idr", "pe_ratio", "price_to_book", "debt_to_equity",
    "roa_pct", "roe_pct", "net_profit_margin_pct",
]
NUMERIC = COLUMNS[11:]


def _number(value: str) -> float | None:
    clean = value.replace(",", "").strip()
    if clean in {"", "-", "N/A", "n/a"}:
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def _membership(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _active(rows: list[dict[str, str]], date: str) -> set[str]:
    return {
        row["ticker"]
        for row in rows
        if row["effective_from"] <= date <= row["effective_to"]
    }


def _write(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshots", type=Path)
    parser.add_argument("membership", type=Path)
    parser.add_argument("--start-year", type=int, default=2021)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/indonesia_fundamental_ratio_vintages")
    args = parser.parse_args()
    members = _membership(args.membership)
    union = {row["ticker"] for row in members}
    panel: list[dict[str, object]] = []
    coverage: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    accepted_files: list[Path] = []
    for path in sorted(args.snapshots.glob("????-??.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        year, month = int(payload["snapshot_year"]), int(payload["snapshot_month"])
        if year < args.start_year:
            continue
        last_day = calendar.monthrange(year, month)[1]
        snapshot_date = f"{year:04d}-{month:02d}-{last_day:02d}"
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        available_at = f"{next_year:04d}-{next_month:02d}-01T00:00:00+07:00"
        active = _active(members, snapshot_date)
        rows_by_ticker: dict[str, dict[str, object]] = {}
        for values in payload.get("rows", []):
            if len(values) < len(COLUMNS):
                continue
            row = dict(zip(COLUMNS, values[: len(COLUMNS)]))
            ticker = str(row["ticker"]).upper()
            if ticker not in union:
                continue
            for column in NUMERIC:
                row[column] = _number(str(row[column]))
            row.update(
                {
                    "snapshot_date": snapshot_date,
                    "available_at": available_at,
                    "source_id": f"IDX-RATIO-{year:04d}{month:02d}",
                    "source_url": payload["source_url"],
                    "evidence_label": "fact_provider_standardized",
                    "confidence": "high",
                    "research_only": True,
                }
            )
            rows_by_ticker[ticker] = row
        panel.extend(rows_by_ticker.values())
        covered = active & set(rows_by_ticker)
        coverage.append(
            {
                "snapshot_date": snapshot_date,
                "available_at": available_at,
                "active_idx80_members": len(active),
                "covered_members": len(covered),
                "coverage_ratio": len(covered) / len(active) if active else 0.0,
                "missing_tickers": "|".join(sorted(active - set(rows_by_ticker))),
                "raw_idx_rows": len(payload.get("rows", [])),
                "failed_pages": "|".join(map(str, payload.get("failed_pages", []))),
            }
        )
        sources.append(
            {
                "source_id": f"IDX-RATIO-{year:04d}{month:02d}",
                "source_name": payload["heading"],
                "source_type": "official_idx_digital_statistic",
                "as_of_date": snapshot_date,
                "available_at": available_at,
                "retrieved_at": payload["observed_at_utc"],
                "location": payload["source_url"],
                "source_rank": "primary_official",
                "freshness": "historical_month_end_snapshot",
                "notes": "Eligibility delayed to the next month; no period-end look-ahead.",
            }
        )
        accepted_files.append(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output_root / f"{stamp}-idx-ratio-panel-v1"
    output.mkdir(parents=True)
    raw = output / "raw"
    raw.mkdir()
    for path in accepted_files:
        shutil.copy2(path, raw / path.name)
    panel_fields = ["snapshot_date", "available_at", "source_id", *COLUMNS[1:], "source_url", "evidence_label", "confidence", "research_only"]
    _write(output / "financial_ratio_panel.csv", sorted(panel, key=lambda row: (str(row["snapshot_date"]), str(row["ticker"]))), panel_fields)
    _write(output / "coverage.csv", coverage, list(coverage[0]) if coverage else [])
    _write(output / "Source_Index.csv", sources, list(sources[0]) if sources else [])
    shutil.copy2(args.membership, output / "idx80_membership.csv")
    file_hashes = {}
    for path in output.rglob("*"):
        if path.is_file():
            file_hashes[str(path.relative_to(output))] = hashlib.sha256(path.read_bytes()).hexdigest()
    summary = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "official IDX Digital Statistic — Financial Data and Ratio",
        "snapshot_count": len(coverage),
        "panel_rows": len(panel),
        "minimum_idx80_coverage": min((row["coverage_ratio"] for row in coverage), default=0.0),
        "maximum_idx80_coverage": max((row["coverage_ratio"] for row in coverage), default=0.0),
        "data_start": min((row["snapshot_date"] for row in coverage), default=None),
        "data_end": max((row["snapshot_date"] for row in coverage), default=None),
        "research_only": True,
        "performance_claim_authorized": False,
        "files": file_hashes,
    }
    (output / "manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "LATEST").write_text(output.name + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
