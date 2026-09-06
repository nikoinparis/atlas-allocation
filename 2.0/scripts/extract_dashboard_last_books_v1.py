#!/usr/bin/env python3
"""Pull each dashboard strategy's final decided book out of the 193MB snapshot.

The snapshot is pretty-printed, so the last weekly record of each strategy can be
sliced by line without holding the whole document in memory. This writes one small
CSV of final holdings per strategy, which is what the mark-to-market step needs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/dashboard_last_books_v1"

RECORD_OPEN = "        {"
RECORD_DATE = '          "date": "'
STRATEGY_ID = '        "id": "'
RECORDS_OPEN = '      "records": ['
SECTION_CLOSE = '      ],'


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    meta: list[dict] = []

    current_id: str | None = None
    in_records = False
    record_start: int | None = None
    last_start: int | None = None
    last_date: str | None = None
    boundaries: list[tuple[str, int, str]] = []

    with SNAPSHOT.open() as handle:
        for number, line in enumerate(handle, 1):
            text = line.rstrip("\n")
            if text.startswith(STRATEGY_ID):
                if current_id and last_start:
                    boundaries.append((current_id, last_start, last_date))
                current_id = text.split('"')[3]
                last_start = last_date = record_start = None
                in_records = False
            elif text == RECORDS_OPEN:
                in_records = True
            elif text == SECTION_CLOSE:
                in_records = False
            elif in_records and text == RECORD_OPEN:
                record_start = number
            elif in_records and text.startswith(RECORD_DATE) and record_start:
                last_start, last_date = record_start, text.split('"')[3]
    if current_id and last_start:
        boundaries.append((current_id, last_start, last_date))

    lines = None
    for strategy_id, start, date in boundaries:
        # Re-read only the slice this record occupies.
        collected: list[str] = []
        depth = 0
        with SNAPSHOT.open() as handle:
            for number, line in enumerate(handle, 1):
                if number < start:
                    continue
                collected.append(line)
                depth += line.count("{") - line.count("}")
                if depth == 0:
                    break
        blob = "".join(collected).rstrip().rstrip(",")
        record = json.loads(blob)
        meta.append({
            "strategy_id": strategy_id,
            "last_record_date": record["date"],
            "wealth": record.get("wealth"),
            "names": len([h for h in record["holdings"] if not str(h["symbol"]).startswith("cash")]),
            "gross_exposure": sum(abs(float(h["weight"])) for h in record["holdings"]
                                  if not str(h["symbol"]).startswith("cash")),
        })
        for holding in record["holdings"]:
            rows.append({
                "strategy_id": strategy_id,
                "as_of": record["date"],
                "symbol": holding["symbol"],
                "weight": holding["weight"],
            })
        print(f"{strategy_id}: last record {record['date']}, {len(record['holdings'])} lines", flush=True)

    pd.DataFrame(rows).to_csv(OUTPUT / "last_books.csv", index=False)
    pd.DataFrame(meta).to_csv(OUTPUT / "last_book_summary.csv", index=False)
    print(pd.DataFrame(meta).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
