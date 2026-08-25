#!/usr/bin/env python3
"""Acquire and normalize complete SEC 8-K Item 2.02 history for the stock universe."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_earnings_8k_acquisition_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
DEFAULT_CACHE = ROOT / "data/sec_historical_identity_cache"
DEFAULT_OUTPUT = ROOT / "data/sec_earnings_event_vintages"


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-issuers", type=int, default=None)
    return parser.parse_args()


def universe() -> list[dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with SCORES.open() as handle:
        for row in csv.DictReader(handle):
            if row["family"] != "cash_conversion":
                continue
            rows[row["cik10"]] = {
                "cik10": row["cik10"],
                "company_name_as_filed": row["company_name_as_filed"],
                "sector": row["sector"],
            }
    return [rows[cik] for cik in sorted(rows)]


class Fetcher:
    def __init__(self, cache: Path, user_agent: str, minimum_interval: float, timeout: int, attempts: int):
        self.cache = cache
        self.user_agent = user_agent
        self.minimum_interval = minimum_interval
        self.timeout = timeout
        self.attempts = attempts
        self.last_request = 0.0
        cache.mkdir(parents=True, exist_ok=True)

    def json(self, url: str, key: str) -> tuple[dict, dict, bool]:
        body_path = self.cache / f"{key}.gz"
        meta_path = self.cache / f"{key}.json"
        if body_path.exists() and meta_path.exists():
            raw = gzip.decompress(body_path.read_bytes())
            meta = json.loads(meta_path.read_text())
            if hashlib.sha256(raw).hexdigest() != meta.get("sha256"):
                raise RuntimeError(f"cached hash mismatch: {key}")
            return json.loads(raw), meta, True
        error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                remaining = self.minimum_interval - (time.monotonic() - self.last_request)
                if remaining > 0:
                    time.sleep(remaining)
                request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json", "Accept-Encoding": "gzip"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                    if (response.headers.get("Content-Encoding") or "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
                        raw = gzip.decompress(raw)
                    status = int(response.status)
                self.last_request = time.monotonic()
                meta = {
                    "url": url,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "http_status": status,
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "cache_key": key,
                }
                body_path.write_bytes(gzip.compress(raw, compresslevel=6, mtime=0))
                meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
                return json.loads(raw), meta, False
            except Exception as exc:
                error = exc
                self.last_request = time.monotonic()
                time.sleep(2 ** attempt)
        raise RuntimeError(f"failed {url}: {error}")


def overlapping_history_files(payload: dict, start_date: str) -> list[str]:
    names = []
    for spec in payload.get("filings", {}).get("files", []):
        filing_from = str(spec.get("filingFrom") or "")
        filing_to = str(spec.get("filingTo") or "")
        if filing_to and filing_to < start_date:
            continue
        if filing_from and filing_from > datetime.now(timezone.utc).date().isoformat():
            continue
        if spec.get("name"):
            names.append(str(spec["name"]))
    return sorted(set(names))


def columnar_rows(payload: dict) -> list[dict]:
    source = payload.get("filings", {}).get("recent", payload)
    keys = ["accessionNumber", "filingDate", "reportDate", "acceptanceDateTime", "form", "items", "primaryDocument"]
    length = len(source.get("form", []))
    return [{key: source.get(key, [None] * length)[index] if index < len(source.get(key, [])) else None for key in keys} for index in range(length)]


def earnings_events(cik: dict[str, str], payloads: list[tuple[str, dict]], start_date: str) -> list[dict]:
    events: dict[str, dict] = {}
    for source_file, payload in payloads:
        for row in columnar_rows(payload):
            if row.get("form") not in {"8-K", "8-K/A"}:
                continue
            items = {value.strip() for value in str(row.get("items") or "").split(",")}
            if "2.02" not in items or str(row.get("filingDate") or "") < start_date:
                continue
            accession = str(row.get("accessionNumber") or "")
            accepted = str(row.get("acceptanceDateTime") or "")
            availability_source = "acceptance_datetime"
            if not accepted:
                filed = datetime.fromisoformat(str(row["filingDate"]))
                accepted = (filed + timedelta(days=1)).replace(tzinfo=timezone.utc).isoformat()
                availability_source = "filing_date_plus_one_day"
            events[accession] = {
                **cik,
                "accession": accession,
                "form": row.get("form"),
                "filing_date": row.get("filingDate"),
                "report_date": row.get("reportDate"),
                "available_at": accepted,
                "availability_source": availability_source,
                "items": "|".join(sorted(items)),
                "primary_document": row.get("primaryDocument"),
                "source_file": source_file,
            }
    return list(events.values())


def main() -> int:
    args = arguments()
    config = json.loads(CONFIG.read_text())
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact email is required")
    targets = universe()
    if args.max_issuers is not None:
        targets = targets[: max(0, int(args.max_issuers))]
    fetcher = Fetcher(Path(args.cache_root).resolve(), user_agent, float(config["minimum_seconds_between_requests"]), int(config["request_timeout_seconds"]), int(config["maximum_attempts"]))
    status_rows, event_rows, source_rows = [], [], []
    for number, issuer in enumerate(targets, start=1):
        cik = issuer["cik10"]
        histories_expected = 0
        histories_loaded = 0
        cache_hits = 0
        try:
            main_payload, metadata, cached = fetcher.json(config["source_endpoint"].format(cik10=cik), f"submissions_{cik}")
            source_rows.append({"cik10": cik, "source_file": "main", **metadata})
            cache_hits += int(cached)
            payloads = [("main", main_payload)]
            filenames = overlapping_history_files(main_payload, str(config["event_start_date"]))
            histories_expected = len(filenames)
            for filename in filenames:
                payload, metadata, cached = fetcher.json(config["historical_source_endpoint"].format(filename=filename), f"submissions_{cik}_{filename.removesuffix('.json')}")
                payloads.append((filename, payload))
                source_rows.append({"cik10": cik, "source_file": filename, **metadata})
                histories_loaded += 1
                cache_hits += int(cached)
            events = earnings_events(issuer, payloads, str(config["event_start_date"]))
            event_rows.extend(events)
            status_rows.append({**issuer, "status": "complete", "historical_files_expected": histories_expected, "historical_files_loaded": histories_loaded, "earnings_events": len(events), "cache_hits": cache_hits})
        except Exception as exc:
            status_rows.append({**issuer, "status": f"failed:{type(exc).__name__}", "historical_files_expected": histories_expected, "historical_files_loaded": histories_loaded, "earnings_events": 0, "cache_hits": cache_hits})
        if number % 25 == 0 or number == len(targets):
            complete = sum(row["status"] == "complete" for row in status_rows)
            print(f"processed {number}/{len(targets)} issuers; complete {complete}; events {len(event_rows)}", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root).resolve() / f"{stamp}-sec-earnings-8k-v1"
    output.mkdir(parents=True, exist_ok=False)
    status_rows.sort(key=lambda row: row["cik10"])
    event_rows.sort(key=lambda row: (row["available_at"], row["cik10"], row["accession"]))
    source_rows.sort(key=lambda row: (row["cik10"], row["source_file"]))
    for filename, rows in [("issuer_status.csv", status_rows), ("earnings_8k_events.csv", event_rows), ("source_manifest.csv", source_rows)]:
        if rows:
            with (output / filename).open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader(); writer.writerows(rows)
        else:
            (output / filename).write_text("")
    complete = sum(row["status"] == "complete" for row in status_rows)
    complete_share = complete / len(status_rows) if status_rows else 0.0
    fallback_count = sum(row["availability_source"] != "acceptance_datetime" for row in event_rows)
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "event_start_date": config["event_start_date"],
        "target_issuers": len(status_rows),
        "complete_issuers": complete,
        "complete_issuer_share": complete_share,
        "failed_issuers": len(status_rows) - complete,
        "item_202_events": len(event_rows),
        "issuers_with_item_202_events": len({row["cik10"] for row in event_rows}),
        "acceptance_datetime_events": len(event_rows) - fallback_count,
        "conservative_filing_plus_one_day_events": fallback_count,
        "source_files": len(source_rows),
        "source_manifest_sha256": hashlib.sha256((output / "source_manifest.csv").read_bytes()).hexdigest(),
        "event_file_sha256": hashlib.sha256((output / "earnings_8k_events.csv").read_bytes()).hexdigest(),
        "minimum_complete_issuer_share_for_research": config["minimum_complete_issuer_share_for_research"],
        "research_testing_authorized": complete_share >= float(config["minimum_complete_issuer_share_for_research"]) and len(status_rows) == len(universe()),
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if not manifest["failed_issuers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
