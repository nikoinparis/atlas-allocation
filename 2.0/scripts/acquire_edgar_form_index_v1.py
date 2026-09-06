#!/usr/bin/env python3
"""Acquire EDGAR quarterly form indexes, for the 13D/13G event study.

Queue item A4. The indexes are small -- about a megabyte a quarter -- and they
carry everything the event study needs: form type, company name, CIK and filing
date.

The identity trick that makes this cheap was verified before the registry was
written. Each 13D appears in the index twice, once under the filer's CIK and once
under the subject company's CIK, with the same accession. So matching index CIKs
against the panel roster isolates subject-company rows with no header fetching and
no name matching -- which avoids both three hours of requests and a name join of
the kind Steps 210 and 211 taught this project to distrust.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.sec.gov/Archives/edgar/full-index"


def contact() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if not value or "@" not in value:
        raise SystemExit("SEC_USER_AGENT must be set to a contact string containing an email address")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2013)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--output", default="data/edgar_form_index_v1")
    args = parser.parse_args()
    agent = contact()

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0
    for year in range(args.start_year, args.end_year + 1):
        for quarter in (1, 2, 3, 4):
            target = out / f"{year}q{quarter}_form.idx"
            if target.is_file() and target.stat().st_size > 10_000:
                skipped += 1
                continue
            url = f"{BASE}/{year}/QTR{quarter}/form.idx"
            try:
                request = urllib.request.Request(url, headers={"User-Agent": agent, "Host": "www.sec.gov"})
                with urllib.request.urlopen(request, timeout=120) as response:
                    payload = response.read()
            except Exception as error:  # noqa: BLE001 - future quarters legitimately 404
                failed += 1
                print(f"  {year}Q{quarter}: {type(error).__name__}", flush=True)
                time.sleep(0.5)
                continue
            target.write_bytes(payload)
            downloaded += 1
            print(f"  {year}Q{quarter}: {len(payload)/1e6:.1f} MB", flush=True)
            time.sleep(0.25)

    manifest = {"experiment": "edgar_form_index_v1",
                "completed_at_utc": datetime.now(timezone.utc).isoformat(),
                "downloaded": downloaded, "skipped": skipped, "failed_or_absent": failed,
                "files_on_disk": len(list(out.glob("*_form.idx"))),
                "note": "quarters after the present legitimately 404; that is not an error",
                "computes_no_signal": True, "live_trading_enabled": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
