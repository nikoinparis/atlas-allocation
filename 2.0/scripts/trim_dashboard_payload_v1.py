#!/usr/bin/env python3
"""Shrink the dashboard payload without changing anything the dashboard shows.

return-first-dashboard.json was 184MB, of which roughly 90% is `assetPrices` --
per-symbol daily price history used by the stock-chart drill-down and the
attribution panel. Two things in there are never displayed:

  symbols never held   The sector ensemble carries 260 symbols and holds 114.
                       51% of its price rows are for names no record ever holds,
                       so no chart can reach them.

  history before the   Every series starts 1993-01-29. The residual composite's
  strategy starts      own window starts 2022-12-02, so thirty years of it sit
                       behind the earliest date any chart can select.

Both are dropped. A lead buffer before the first record is kept so charts have
context to the left of the opening position, and every symbol that is ever held
keeps every row inside its strategy's window.

This is a size fix, not an edit to the record: no return, weight, holding or
metric is touched, and re-running scripts/build_*.py regenerates the full file
if it is ever needed.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dashboard/public/return-first-dashboard.json"
LEAD_DAYS = 400          # chart context to the left of the first position


def main() -> int:
    if not TARGET.is_file():
        print(f"missing {TARGET}")
        return 1
    before = TARGET.stat().st_size
    payload = json.loads(TARGET.read_text())

    report = []
    for entry in payload["strategies"]:
        name = entry["strategy"]["id"]
        prices = entry.get("assetPrices", {})
        if not prices:
            continue
        held = {h["symbol"] for r in entry.get("records", []) for h in r.get("holdings", [])}
        held |= {h["symbol"] for r in entry.get("dailyRecords", []) for h in r.get("holdings", [])}
        dates = [r["date"] for r in entry.get("records", [])] or \
                [r["date"] for r in entry.get("dailyRecords", [])]
        if not dates:
            continue
        floor = str(date.fromisoformat(min(dates)) - timedelta(days=LEAD_DAYS))
        rows_before = sum(len(v) for v in prices.values())
        trimmed = {
            symbol: [row for row in series if row["date"] >= floor]
            for symbol, series in prices.items() if symbol in held
        }
        trimmed = {k: v for k, v in trimmed.items() if v}
        entry["assetPrices"] = trimmed
        rows_after = sum(len(v) for v in trimmed.values())
        report.append((name, len(prices), len(trimmed), rows_before, rows_after, floor))

    backup = TARGET.with_suffix(".json.full")
    if not backup.exists():
        shutil.copy2(TARGET, backup)
    TARGET.write_text(json.dumps(payload, separators=(",", ":")))
    after = TARGET.stat().st_size

    print(f"{'strategy':44s} {'symbols':>16s} {'price rows':>22s}  kept from")
    for name, s0, s1, r0, r1, floor in report:
        print(f"{name:44s} {s0:>7d} -> {s1:<6d} {r0:>10,} -> {r1:<9,}  {floor}")
    print(f"\n{before/1048576:.1f} MB -> {after/1048576:.1f} MB "
          f"({(1 - after/before):.0%} smaller)")
    print(f"untrimmed copy left beside it as {backup.name} (gitignored)")
    print("no return, weight, holding or metric was altered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
