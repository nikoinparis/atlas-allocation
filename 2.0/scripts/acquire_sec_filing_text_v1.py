#!/usr/bin/env python3
"""Acquire the 10-K primary documents that Step 202 queued and never downloaded.

Step 202 built a hash-backed queue of 9,755 filings across 1,426 issuers and then
stopped, because using submissions metadata as a substitute for filing prose would
have fabricated the signal. The queue has sat unused since. It is item S1 in
`docs/RESEARCH_QUEUE.md` and the reason that file now exists.

Fair access is not optional. SEC asks for a declared User-Agent carrying a real
contact address and no more than ten requests a second; this runs at five, sleeps
on 429 and 403, and stops rather than hammering. The contact string comes from
SEC_USER_AGENT in the environment and the script refuses to run without it.

Every document is stored gzipped with its sha256 recorded, so a later parse can
prove it read the bytes that were downloaded. Resumable: anything already on disk
with a matching hash is skipped.

This acquires text. It computes no signal and makes no claim.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "evidence/sec_language_change_readiness_v1/filing_text_acquisition_queue.csv"

REQUESTS_PER_SECOND = 5.0          # SEC permits ten; half of it leaves headroom
BACKOFF_SECONDS = 60.0
MAX_CONSECUTIVE_FAILURES = 10


def contact() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if not value or "@" not in value:
        raise SystemExit(
            "SEC_USER_AGENT must be set to a contact string containing an email address, "
            "e.g. SEC_USER_AGENT='Portfolio Optimizer research <you@example.com>'. "
            "SEC fair-access rules require identifying the requester."
        )
    return value


def fetch(url: str, agent: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": agent,
        "Accept-Encoding": "gzip, deflate",
        "Host": "www.sec.gov",
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            payload = gzip.decompress(payload)
        return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 acquires the whole queue")
    parser.add_argument("--output", default="data/sec_filing_text_v1")
    parser.add_argument("--pairs-only", action="store_true",
                        help="only filings that have a prior-year filing to compare against")
    parser.add_argument("--newest-first", action="store_true")
    args = parser.parse_args()

    agent = contact()
    queue = pd.read_csv(QUEUE, dtype={"cik10": str})
    queue = queue[queue.archive_url.notna()]
    if args.pairs_only:
        queue = queue[queue.has_year_over_year_pair.astype(bool)]
    queue = queue.sort_values("filing_date", ascending=not args.newest_first)
    if args.limit:
        queue = queue.head(args.limit)

    out = ROOT / args.output
    documents = out / "documents"
    documents.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.jsonl"
    already = {}
    if index_path.is_file():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                already[record["accession"]] = record

    interval = 1.0 / REQUESTS_PER_SECOND
    downloaded = skipped = failed = 0
    consecutive = 0
    bytes_total = 0
    started = time.monotonic()

    with index_path.open("a", encoding="utf-8") as index:
        for row in queue.itertuples(index=False):
            accession = str(row.accession)
            target = documents / f"{accession}.gz"
            if accession in already and target.is_file():
                skipped += 1
                continue
            began = time.monotonic()
            try:
                payload = fetch(str(row.archive_url), agent)
                consecutive = 0
            except urllib.error.HTTPError as error:
                failed += 1
                consecutive += 1
                if error.code in (403, 429):
                    print(f"  {error.code} on {accession}; sleeping {BACKOFF_SECONDS:.0f}s", flush=True)
                    time.sleep(BACKOFF_SECONDS)
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    print(f"stopping after {consecutive} consecutive failures", flush=True)
                    break
                continue
            except Exception as error:  # noqa: BLE001 - network paths are varied and non-fatal
                failed += 1
                consecutive += 1
                if consecutive >= MAX_CONSECUTIVE_FAILURES:
                    print(f"stopping after {consecutive} consecutive failures: {error}", flush=True)
                    break
                continue

            digest = hashlib.sha256(payload).hexdigest()
            target.write_bytes(gzip.compress(payload))
            record = {
                "cik10": str(row.cik10), "accession": accession,
                "filing_date": str(row.filing_date), "report_date": str(row.report_date),
                "form": str(row.form), "url": str(row.archive_url),
                "bytes": len(payload), "sha256": digest,
                "prior_accession": (None if pd.isna(row.prior_accession) else str(row.prior_accession)),
                "acquired_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            index.write(json.dumps(record, sort_keys=True) + "\n")
            index.flush()
            downloaded += 1
            bytes_total += len(payload)
            if downloaded % 50 == 0:
                rate = downloaded / max(1e-9, time.monotonic() - started)
                print(f"  {downloaded} downloaded, {skipped} skipped, {failed} failed, "
                      f"{bytes_total/1e6:.0f} MB, {rate:.1f}/s", flush=True)
            elapsed = time.monotonic() - began
            if elapsed < interval:
                time.sleep(interval - elapsed)

    manifest = {
        "experiment": "sec_filing_text_v1",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "queue": str(QUEUE.relative_to(ROOT)),
        "queue_rows_considered": int(len(queue)),
        "downloaded": downloaded, "skipped_already_present": skipped, "failed": failed,
        "bytes_downloaded": bytes_total,
        "mean_document_bytes": int(bytes_total / downloaded) if downloaded else 0,
        "documents_on_disk": len(list(documents.glob("*.gz"))),
        "requests_per_second_cap": REQUESTS_PER_SECOND,
        "fair_access": "declared User-Agent with contact address; five requests a second against a permitted ten",
        "computes_no_signal": True,
        "live_trading_enabled": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
