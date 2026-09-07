#!/usr/bin/env python3
"""Fetch FINRA consolidated daily short-sale volume files and cache them.

Free, published by the venue, one file per trading day. The monthly archive path
returns AccessDenied so the daily files are fetched individually, cached on disk,
and never re-fetched. Polite rate limiting and an identifying user agent; the
contact address is the owner's, authorised for this use only.

The signal built from these is declared in config/finra_short_volume_registry_v1.json
before any of it was downloaded.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/finra_short_volume_v1/daily"
EVIDENCE = ROOT / "evidence/finra_short_volume_v1"
BASE = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{stamp}.txt"
AGENT = "Portfolio Optimizer Research nicholasturangan@gmail.com"
START, END = date(2023, 1, 3), date(2026, 9, 4)
PAUSE = 0.35


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    fetched = cached = missing = failed = 0
    absent: list[str] = []

    day = START
    while day <= END:
        if day.weekday() >= 5:                      # no consolidated file on weekends
            day += timedelta(days=1)
            continue
        stamp = day.strftime("%Y%m%d")
        target = CACHE / f"{stamp}.txt"
        if target.exists() and target.stat().st_size > 0:
            cached += 1
            day += timedelta(days=1)
            continue
        request = urllib.request.Request(BASE.format(stamp=stamp), headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace")
            # A holiday returns a short body or an error document rather than a 404.
            if not body.startswith("Date|Symbol|"):
                missing += 1
                absent.append(stamp)
            else:
                target.write_text(body, encoding="utf-8")
                fetched += 1
        except urllib.error.HTTPError as error:
            # FINRA answers a day with no file with 403, not 404. Treating 403 as a
            # failure made a complete download report 37 failures and exit non-zero;
            # every one of them is a US market holiday (MLK, Presidents, Good Friday,
            # Memorial, Juneteenth, July 4, Labor, Thanksgiving, Christmas, New Year).
            if error.code in (403, 404):
                missing += 1
                absent.append(stamp)
            else:
                failed += 1
                absent.append(f"{stamp}:HTTP{error.code}")
        except Exception as error:                   # noqa: BLE001
            failed += 1
            absent.append(f"{stamp}:{type(error).__name__}")
        time.sleep(PAUSE)
        day += timedelta(days=1)

    files = sorted(CACHE.glob("*.txt"))
    result = {
        "experiment": "finra_short_volume_v1",
        "window": [str(START), str(END)],
        "files_on_disk": len(files),
        "fetched_this_run": fetched,
        "already_cached": cached,
        "no_file_published": missing,
        "failed": failed,
        "first_file": files[0].stem if files else None,
        "last_file": files[-1].stem if files else None,
        "absent_sample": absent[:20],
        "token_persisted": False,
        "live_trading_enabled": False,
    }
    (EVIDENCE / "acquisition.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in
        ("files_on_disk", "fetched_this_run", "already_cached", "no_file_published",
         "failed", "first_file", "last_file")}, indent=2, sort_keys=True))
    return 0 if failed < 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
