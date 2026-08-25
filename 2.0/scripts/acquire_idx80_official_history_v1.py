#!/usr/bin/env python3
"""Acquire and parse the IDX-hosted IDX80 review archive currently available."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.idx80_history import (  # noqa: E402
    idx80_workbook_from_zip,
    parse_idx80_workbook,
)


OUTPUT_ROOT = ROOT / "data" / "indonesia_idx80_history_vintages"
API = "https://www.idx.id/primary/NewsAnnouncement/GetAllAnnouncement"
TARGET_START = "2019-02-01"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def fetch(url: str) -> tuple[bytes, dict[str, object]]:
    safe_url = quote(url.replace("www.idx.co.id", "www.idx.id"), safe=":/?=&%")
    request = Request(
        safe_url,
        headers={
            "User-Agent": "PortfolioOptimizerResearch/2.0",
            "Accept": "application/json, application/pdf, application/zip, */*",
            "Referer": "https://www.idx.id/id/berita/pengumuman",
        },
    )
    observed_at = datetime.now(timezone.utc).isoformat()
    with urlopen(request, timeout=90) as response:
        payload = response.read()
        return payload, {
            "url": safe_url,
            "observed_at_utc": observed_at,
            "http_status": getattr(response, "status", 200),
            "content_type": response.headers.get("Content-Type", ""),
            "bytes": len(payload),
            "sha256": sha256_bytes(payload),
        }


def announcement_payload() -> tuple[bytes, dict[str, object]]:
    query = urlencode(
        {"keywords": "IDX80", "pageNumber": 1, "pageSize": 100, "lang": "id"}
    )
    return fetch(f"{API}?{query}")


def review_announcements(payload: bytes) -> list[dict[str, object]]:
    response = json.loads(payload)
    rows = []
    for item in response["Items"]:
        published = pd.Timestamp(item["PublishDate"])
        if not item["Title"].strip().lower().startswith("evaluasi indeks"):
            continue
        if published.month not in {1, 4, 7, 10}:
            continue
        zip_files = [
            value for value in item["Attachments"] if value["OriginalFilename"].lower().endswith(".zip")
        ]
        pdf_files = [
            value for value in item["Attachments"] if value["OriginalFilename"].lower().endswith(".pdf")
        ]
        if len(zip_files) != 1:
            raise ValueError(f"review attachment set is incomplete: {item['AnnouncementNo']}")
        rows.append({**item, "zip": zip_files[0], "pdf": pdf_files[0] if pdf_files else None})
    return sorted(rows, key=lambda value: value["PublishDate"])


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vintage_id = f"{stamp}-idx80-official-history-v1"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_ROOT / vintage_id
    with tempfile.TemporaryDirectory(prefix=f".{vintage_id}-", dir=OUTPUT_ROOT) as temporary:
        staging = Path(temporary)
        raw = staging / "raw"
        raw.mkdir()
        api_payload, api_observation = announcement_payload()
        (raw / "announcement_search.json").write_bytes(api_payload)
        announcements = review_announcements(api_payload)
        membership_rows: list[dict[str, object]] = []
        source_rows: list[dict[str, object]] = [
            {"source_id": "idx-announcement-search", "source_type": "api", **api_observation}
        ]
        periods: list[dict[str, object]] = []
        for sequence, item in enumerate(announcements, start=1):
            announcement_id = item["AnnouncementNo"].replace("/", "_").replace(" ", "")
            zip_payload, zip_observation = fetch(item["zip"]["FullSavePath"])
            zip_name = f"{sequence:02d}-{announcement_id}.zip"
            (raw / zip_name).write_bytes(zip_payload)
            workbook_name, workbook_payload = idx80_workbook_from_zip(zip_payload)
            try:
                parsed = parse_idx80_workbook(workbook_payload)
            except ValueError as error:
                raise ValueError(f"{item['AnnouncementNo']}: {error}") from error
            workbook_file = f"{sequence:02d}-idx80.xlsx"
            (raw / workbook_file).write_bytes(workbook_payload)
            published_local = pd.Timestamp(item["PublishDate"]).tz_localize("Asia/Jakarta")
            available_at = published_local.tz_convert("UTC").isoformat()
            source_id = f"idx:{item['AnnouncementNo']}"
            for ticker in parsed["tickers"]:
                membership_rows.append(
                    {
                        "ticker": ticker,
                        "vendor_ticker": f"{ticker}.JK",
                        "universe": "IDX80",
                        "effective_from": parsed["effective_from"],
                        "effective_to": parsed["effective_to"],
                        "available_at": available_at,
                        "source_id": source_id,
                        "official_source": True,
                        "point_in_time_membership": True,
                    }
                )
            source_rows.append(
                {
                    "source_id": source_id,
                    "source_type": "review_zip",
                    "announcement_number": item["AnnouncementNo"],
                    "publish_date_local": item["PublishDate"],
                    "stored_file": f"raw/{zip_name}",
                    **zip_observation,
                }
            )
            if item["pdf"] is not None:
                pdf_payload, pdf_observation = fetch(item["pdf"]["FullSavePath"])
                pdf_name = f"{sequence:02d}-{announcement_id}.pdf"
                (raw / pdf_name).write_bytes(pdf_payload)
                source_rows.append(
                    {
                        "source_id": source_id,
                        "source_type": "announcement_pdf",
                        "announcement_number": item["AnnouncementNo"],
                        "publish_date_local": item["PublishDate"],
                        "stored_file": f"raw/{pdf_name}",
                        **pdf_observation,
                    }
                )
            periods.append(
                {
                    "source_id": source_id,
                    "announcement_number": item["AnnouncementNo"],
                    "published_local": item["PublishDate"],
                    "available_at_utc": available_at,
                    "effective_from": parsed["effective_from"],
                    "effective_to": parsed["effective_to"],
                    "declared_effective_to": parsed["effective_to"],
                    "member_count": len(parsed["tickers"]),
                    "workbook_in_zip": workbook_name,
                    "stored_workbook": f"raw/{workbook_file}",
                    "workbook_sha256": sha256_bytes(workbook_payload),
                }
            )

        membership = pd.DataFrame(membership_rows).sort_values(["effective_from", "ticker"])
        period_frame = pd.DataFrame(periods).sort_values("effective_from")
        next_starts = period_frame["effective_from"].shift(-1)
        period_frame.loc[next_starts.notna(), "effective_to"] = next_starts[next_starts.notna()]
        normalized_ends = dict(zip(period_frame["effective_from"], period_frame["effective_to"]))
        membership["effective_to"] = membership["effective_from"].map(normalized_ends)
        if membership.duplicated(["effective_from", "ticker"]).any():
            raise ValueError("duplicate membership rows")
        if not (membership.groupby("effective_from").size() == 80).all():
            raise ValueError("every official IDX80 period must contain 80 names")
        starts = pd.to_datetime(period_frame["effective_from"])
        ends = pd.to_datetime(period_frame["effective_to"])
        gaps = starts.iloc[1:].reset_index(drop=True) - ends.iloc[:-1].reset_index(drop=True)
        if (gaps != pd.Timedelta(0)).any():
            details = period_frame[["effective_from", "effective_to"]].to_dict("records")
            raise ValueError(
                f"official IDX80 review periods overlap or contain a trading-date gap: {details}"
            )

        membership.to_csv(staging / "idx80_membership.csv", index=False)
        period_frame.to_csv(staging / "review_periods.csv", index=False)
        pd.DataFrame(source_rows).to_csv(staging / "source_index.csv", index=False)
        coverage_from = str(period_frame["effective_from"].min())
        coverage_to = str(period_frame["effective_to"].max())
        report = f"""# IDX80 Official Membership Archive v1

This archive contains {len(period_frame)} consecutive official IDX80 review
periods, covering {coverage_from} through {coverage_to} (exclusive end).
Every period contains exactly 80 securities and retains its IDX announcement,
ZIP attachment, original IDX80 workbook, publication timestamp, and hash.

The intended strategy test starts at {TARGET_START}. The official archive
currently exposed by the IDX announcement API begins at {coverage_from}, so
the period {TARGET_START} through {coverage_from} remains missing. This dataset
must not be described as complete 2019–2026 history and does not by itself
authorize performance claims.
"""
        (staging / "README.md").write_text(report, encoding="utf-8")
        files = {
            str(path.relative_to(staging)): {"bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(staging.rglob("*"))
            if path.is_file() and path.name != "manifest.json"
        }
        manifest = {
            "vintage_id": vintage_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "point-in-time official IDX80 membership reconstruction",
            "provider": "Indonesia Stock Exchange announcement API and attachments",
            "provider_terms": "Research use only; IDX site terms apply; no commercial redistribution right asserted.",
            "target_start": TARGET_START,
            "coverage_from": coverage_from,
            "coverage_to_exclusive": coverage_to,
            "review_periods": len(period_frame),
            "membership_rows": len(membership),
            "unique_tickers": membership["ticker"].nunique(),
            "claims": {
                "official_source": True,
                "point_in_time_for_covered_period": True,
                "target_history_complete": coverage_from <= TARGET_START,
                "survivorship_safe_for_covered_membership": True,
                "price_history_complete": False,
                "delisting_complete": False,
                "performance_claim_authorized": False,
                "live_trading_enabled": False,
            },
            "files": files,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.copytree(staging, destination)
    (OUTPUT_ROOT / "LATEST").write_text(vintage_id + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
