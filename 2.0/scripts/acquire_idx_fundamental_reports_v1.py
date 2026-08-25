#!/usr/bin/env python3
"""Acquire official IDX XBRL filings with point-in-time publication metadata.

The script deliberately requests a whole reporting period, then filters locally to
the IDX80 membership archive. This avoids the one-request-per-company pattern that
quickly triggers IDX rate limits. Authentication cookies must come from an isolated
IDX session (for example, ``idxlens auth``); personal browser state is not used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://www.idx.co.id/primary/ListedCompany/GetFinancialReport"
ORIGIN = "https://www.idx.co.id"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
MAX_ATTACHMENT_BYTES = 50 * 1024 * 1024


def _cookies(path: Path) -> str:
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("cookie file is empty")
    return "; ".join(f"{entry['name']}={entry['value']}" for entry in entries)


def _request(url: str, cookie_header: str, *, retries: int, pause_seconds: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{ORIGIN}/",
            "Cookie": cookie_header,
        },
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = response.read(MAX_ATTACHMENT_BYTES + 1)
                if len(payload) > MAX_ATTACHMENT_BYTES:
                    raise ValueError("IDX attachment exceeded safety size limit")
                time.sleep(pause_seconds)
                return payload
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == retries:
                raise
            retry_after = error.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else min(60.0, 5.0 * (2**attempt))
            time.sleep(delay)
    raise RuntimeError("unreachable retry state")


def _members(path: Path, current_only: bool) -> set[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if current_only:
        latest = max(row["effective_from"] for row in rows)
        rows = [row for row in rows if row["effective_from"] == latest]
    return {row["ticker"] for row in rows}


def _listing_url(year: int, period: str, index_from: int, page_size: int) -> str:
    params = {
        "indexFrom": index_from,
        "pageSize": page_size,
        "year": year,
        "reportType": "rdf",
        "EmitenType": "s",
        "periode": period,
        "kodeEmiten": "",
        "SortColumn": "KodeEmiten",
        "SortOrder": "asc",
    }
    return ENDPOINT + "?" + urllib.parse.urlencode(params)


def _all_results(
    year: int,
    period: str,
    cookie_header: str,
    *,
    retries: int,
    pause_seconds: float,
) -> list[dict[str, object]]:
    page_size = 2000
    index_from = 1
    results: list[dict[str, object]] = []
    while True:
        payload = _request(
            _listing_url(year, period, index_from, page_size),
            cookie_header,
            retries=retries,
            pause_seconds=pause_seconds,
        )
        response = json.loads(payload)
        batch = response.get("Results") or []
        results.extend(batch)
        total = int(response.get("ResultCount") or len(results))
        if not batch or len(results) >= total:
            return results
        index_from += page_size


def _preferred_attachment(result: dict[str, object]) -> dict[str, object] | None:
    attachments = result.get("Attachments") or []
    for attachment in attachments:
        if str(attachment.get("File_Name", "")).lower() == "instance.zip":
            return attachment
    return None


def _safe_source_url(file_path: str) -> str:
    decoded = urllib.parse.unquote(file_path)
    if not decoded.startswith("/Portals/0/StaticData/ListedCompanies/"):
        raise ValueError(f"unexpected IDX attachment path: {file_path}")
    return ORIGIN + urllib.parse.quote(decoded, safe="/:_%")


def _source_id(ticker: str, year: int, period: str, published_at: str) -> str:
    key = f"{ticker}|{year}|{period}|{published_at}".encode()
    return "IDX-FILING-" + hashlib.sha256(key).hexdigest()[:16].upper()


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie-file", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/indonesia_fundamental_idx_vintages")
    parser.add_argument("--years", default="2022,2023,2024,2025")
    parser.add_argument("--periods", default="audit")
    parser.add_argument("--current-only", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=5)
    args = parser.parse_args()
    years = [int(value) for value in args.years.split(",") if value]
    periods = [value.strip() for value in args.periods.split(",") if value.strip()]
    tickers = _members(args.membership, args.current_only)
    cookie_header = _cookies(args.cookie_file)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output_root / f"{stamp}-idx-fundamentals-v1"
    raw = output / "raw"
    raw.mkdir(parents=True)
    manifest_rows: list[dict[str, object]] = []
    listing_counts: dict[str, int] = {}
    for year in years:
        for period in periods:
            results = _all_results(
                year,
                period,
                cookie_header,
                retries=args.retries,
                pause_seconds=args.pause_seconds,
            )
            listing_counts[f"{year}:{period}"] = len(results)
            for result in results:
                ticker = str(result.get("KodeEmiten", "")).upper()
                if ticker not in tickers:
                    continue
                attachment = _preferred_attachment(result)
                published_at = str(result.get("File_Modified") or "")
                if not attachment:
                    manifest_rows.append(
                        {
                            "ticker": ticker,
                            "year": year,
                            "period": period,
                            "published_at": published_at,
                            "status": "missing_required_source",
                            "error": "instance.zip not supplied",
                        }
                    )
                    continue
                source_url = _safe_source_url(str(attachment.get("File_Path", "")))
                destination = raw / ticker / str(year) / period / "instance.zip"
                destination.parent.mkdir(parents=True, exist_ok=True)
                try:
                    payload = _request(
                        source_url,
                        cookie_header,
                        retries=args.retries,
                        pause_seconds=args.pause_seconds,
                    )
                    destination.write_bytes(payload)
                    relative = destination.relative_to(output)
                    status, error = "downloaded", ""
                    digest = hashlib.sha256(payload).hexdigest()
                except Exception as exc:
                    relative, digest = "", ""
                    status, error = "download_failed", f"{type(exc).__name__}: {exc}"
                manifest_rows.append(
                    {
                        "source_id": _source_id(ticker, year, period, published_at),
                        "ticker": ticker,
                        "year": year,
                        "period": period,
                        "period_end": "",
                        "published_at": published_at,
                        "source_url": source_url,
                        "file_path": str(relative),
                        "sha256": digest,
                        "status": status,
                        "error": error,
                    }
                )
    fields = ["source_id", "ticker", "year", "period", "period_end", "published_at", "source_url", "file_path", "sha256", "status", "error"]
    _write_csv(output / "report_manifest.csv", manifest_rows, fields)
    shutil.copy2(args.membership, output / "idx80_membership.csv")
    summary = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": ENDPOINT,
        "research_only": True,
        "membership_scope": "current IDX80" if args.current_only else "historical IDX80 union",
        "tickers_in_scope": len(tickers),
        "years": years,
        "periods": periods,
        "listing_counts": listing_counts,
        "manifest_rows": len(manifest_rows),
        "downloaded": sum(row.get("status") == "downloaded" for row in manifest_rows),
        "failed": sum(row.get("status") != "downloaded" for row in manifest_rows),
        "performance_claim_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if summary["downloaded"]:
        (args.output_root / "LATEST").write_text(output.name + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
