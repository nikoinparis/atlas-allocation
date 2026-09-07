#!/usr/bin/env python3
"""Extend the cached Form 4 bulk data back to 2011 so "routine" can be defined.

The existing vintage holds 2023Q1-2026Q2. The routine rule declared in
config/form4_opportunistic_registry_v1.json needs three prior calendar years of
an insider's history before it can classify anything, so on 14 quarters it could
only classify trades in the final year -- which is not a test, it is an anecdote.

Reaching back to 2011 also buys something this project badly needs and has never
had: a test window that is not 2023-2026. Every strategy on the dashboard was
selected on that window and none has out-of-sample evidence. Here the longer
window is forced by the method rather than chosen after seeing results, which is
the only circumstance in which a longer window costs nothing in selection.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/sec_form4_history_v1"
EVIDENCE = ROOT / "evidence/form4_opportunistic_v1"
BASE = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
AGENT = "Portfolio Optimizer Research nicholasturangan@gmail.com"
PAUSE = 0.6


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    quarters = [f"{y}q{q}" for y in range(2011, 2023) for q in (1, 2, 3, 4)]
    fetched = cached = failed = 0
    problems: list[str] = []
    for quarter in quarters:
        target = CACHE / f"{quarter}_form345.zip"
        if target.exists() and target.stat().st_size > 10_000:
            cached += 1
            continue
        request = urllib.request.Request(BASE.format(q=quarter), headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
            if len(body) < 10_000:
                problems.append(f"{quarter}:short({len(body)})")
                failed += 1
            else:
                target.write_bytes(body)
                fetched += 1
        except urllib.error.HTTPError as error:
            problems.append(f"{quarter}:HTTP{error.code}")
            failed += 1
        except Exception as error:                   # noqa: BLE001
            problems.append(f"{quarter}:{type(error).__name__}")
            failed += 1
        time.sleep(PAUSE)

    files = sorted(CACHE.glob("*_form345.zip"))
    total = sum(f.stat().st_size for f in files)
    result = {
        "quarters_requested": len(quarters),
        "fetched_this_run": fetched, "already_cached": cached, "failed": failed,
        "files_on_disk": len(files),
        "megabytes_on_disk": round(total / 1e6, 1),
        "first": files[0].stem if files else None,
        "last": files[-1].stem if files else None,
        "problems": problems[:20],
        "token_persisted": False, "live_trading_enabled": False,
    }
    (EVIDENCE / "acquisition_history.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if failed <= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
