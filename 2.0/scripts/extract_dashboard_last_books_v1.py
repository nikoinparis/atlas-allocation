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

def main() -> int:
    """Read the payload whole. It used to be a 193MB pretty-printed file sliced by line;
    since 2026-10-06 the builder writes compact JSON of ~18MB, which line slicing cannot parse."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    meta: list[dict] = []
    for entry in json.loads(SNAPSHOT.read_text())["strategies"]:
        strategy_id = entry["strategy"]["id"]
        record = entry["records"][-1]
        meta.append({
            "strategy_id": strategy_id,
            "last_record_date": record["date"],
            "wealth": record.get("wealth"),
            "names": len([h for h in record["holdings"] if not str(h["symbol"]).startswith("cash")]),
            "gross_exposure": sum(abs(float(h["weight"])) for h in record["holdings"]
                                  if not str(h["symbol"]).startswith("cash")),
        })
        for holding in record["holdings"]:
            rows.append({"strategy_id": strategy_id, "as_of": record["date"],
                         "symbol": holding["symbol"], "weight": holding["weight"]})
        print(f"{strategy_id}: last record {record['date']}, {len(record['holdings'])} lines", flush=True)

    pd.DataFrame(rows).to_csv(OUTPUT / "last_books.csv", index=False)
    pd.DataFrame(meta).to_csv(OUTPUT / "last_book_summary.csv", index=False)
    print(pd.DataFrame(meta).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
