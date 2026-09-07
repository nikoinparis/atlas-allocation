#!/usr/bin/env python3
"""Fetch SEC Financial Statement Data Sets back to 2012 so one signal can be tested out of sample.

Every fundamental panel in this project starts 2023-01-01, which means every
dashboard strategy was selected on 2023-2026 and none can be tested before it.
That is a data limit rather than a choice, and Step 286 showed what the fix is
worth: a method that reaches back buys an out-of-sample window at no cost in
selection, because the window is forced by the data rather than chosen after
seeing results.

Rebuilding every signal to 2012 means redoing survivorship-safe universe
construction for eleven extra years and is not a small job. Rebuilding ONE is,
and the one worth it is earnings yield -- the valuation book that goes on a
forward clock on 2026-09-11 and is the growth-uncorrelated half of the frozen
50/50 blend. If it does not survive 2012-2022, the clock is measuring something
this project should already have doubted.

The cached data/sec_fsds_sub_cache holds only SUB tables. NUM is the one with the
actual reported numbers, and it only comes in the full quarterly zip.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/sec_fsds_history_v1"
EVIDENCE = ROOT / "evidence/valuation_out_of_sample_v1"
BASE = "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip"
AGENT = "Portfolio Optimizer Research nicholasturangan@gmail.com"
PAUSE = 0.7


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    quarters = [f"{y}q{q}" for y in range(2012, 2023) for q in (1, 2, 3, 4)]
    fetched = cached = failed = 0
    problems: list[str] = []
    for quarter in quarters:
        target = CACHE / f"{quarter}.zip"
        if target.exists() and target.stat().st_size > 100_000:
            cached += 1
            continue
        request = urllib.request.Request(BASE.format(q=quarter), headers={"User-Agent": AGENT})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                body = response.read()
            if len(body) < 100_000:
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

    files = sorted(CACHE.glob("*.zip"))
    result = {
        "quarters_requested": len(quarters), "fetched_this_run": fetched,
        "already_cached": cached, "failed": failed, "files_on_disk": len(files),
        "gigabytes_on_disk": round(sum(f.stat().st_size for f in files) / 1e9, 2),
        "first": files[0].stem if files else None, "last": files[-1].stem if files else None,
        "problems": problems[:20], "live_trading_enabled": False,
    }
    (EVIDENCE / "acquisition_fsds.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if failed <= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
