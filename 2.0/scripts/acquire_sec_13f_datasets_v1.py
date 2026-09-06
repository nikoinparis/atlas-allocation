#!/usr/bin/env python3
"""Acquire the SEC Form 13F structured data sets.

Queue item A0. The URLs are scraped from the official index page rather than
constructed, because the naming convention changed in 2024 from `2023q4_form13f`
to `01dec2024-28feb2025_form13f` and a constructed pattern silently 404s on
everything after that boundary -- which a probe confirmed before this was written.

SEC fair access applies as it did for the filing text: a declared User-Agent with
a contact address, well under the permitted rate, hashes recorded, resumable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
BASE = "https://www.sec.gov"
PAUSE_SECONDS = 1.0


def contact() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if not value or "@" not in value:
        raise SystemExit("SEC_USER_AGENT must be set to a contact string containing an email address")
    return value


def get(url: str, agent: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Host": "www.sec.gov"})
    with urllib.request.urlopen(request, timeout=180) as response:
        return response.read()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/sec_13f_datasets_v1")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    agent = contact()

    page = get(INDEX, agent).decode("utf-8", "ignore")
    links = sorted(set(re.findall(r'href="(/files/structureddata/data/form-13f-data-sets/[^"]+\.zip)"', page)))
    if args.limit:
        links = links[-args.limit:]

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    index_path = out / "index.jsonl"
    already = set()
    if index_path.is_file():
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                already.add(json.loads(line)["name"])

    downloaded = skipped = failed = 0
    total_bytes = 0
    with index_path.open("a", encoding="utf-8") as index:
        for link in links:
            name = link.rsplit("/", 1)[-1]
            target = out / name
            if name in already and target.is_file():
                skipped += 1
                continue
            try:
                payload = get(BASE + link, agent)
            except Exception as error:  # noqa: BLE001
                print(f"  failed {name}: {type(error).__name__}", flush=True)
                failed += 1
                time.sleep(PAUSE_SECONDS * 5)
                continue
            target.write_bytes(payload)
            record = {"name": name, "url": BASE + link, "bytes": len(payload),
                      "sha256": hashlib.sha256(payload).hexdigest(),
                      "acquired_at_utc": datetime.now(timezone.utc).isoformat()}
            index.write(json.dumps(record, sort_keys=True) + "\n")
            index.flush()
            downloaded += 1
            total_bytes += len(payload)
            print(f"  {name} {len(payload)/1e6:.0f} MB  ({downloaded}/{len(links)})", flush=True)
            time.sleep(PAUSE_SECONDS)

    manifest = {"experiment": "sec_13f_datasets_v1",
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "index_page": INDEX, "files_listed": len(links),
                "downloaded": downloaded, "skipped": skipped, "failed": failed,
                "bytes_downloaded": total_bytes,
                "files_on_disk": len(list(out.glob("*.zip"))),
                "url_pattern_note": "scraped, not constructed; naming changed in 2024",
                "computes_no_signal": True, "live_trading_enabled": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
