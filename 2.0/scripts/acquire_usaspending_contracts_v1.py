#!/usr/bin/env python3
"""Acquire quarterly federal contract obligations by recipient from USASpending.gov.

For config/federal_contracts_registry_v1.json. Free and keyless. Top 1,000
contract recipients per calendar quarter by action date, then each recipient's
parent from the recipient profile. Cached per request so a rerun resumes.
"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/usaspending_contracts_v1"
CACHE = OUTPUT / "cache"
API = "https://api.usaspending.gov/api/v2"
PAGES = 10
FIRST_YEAR = 2012


def fetch(url: str, body: dict | None, cache: Path) -> dict:
    if cache.is_file():
        return json.loads(cache.read_text())
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read())
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(payload))
            return payload
        except Exception as error:                            # noqa: BLE001
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def quarters() -> list[tuple[str, str, str]]:
    out = []
    today = date.today()
    for year in range(FIRST_YEAR, today.year + 1):
        for q, (start, end) in enumerate((("01-01", "03-31"), ("04-01", "06-30"),
                                          ("07-01", "09-30"), ("10-01", "12-31")), 1):
            if date.fromisoformat(f"{year}-{end}") >= today:
                continue
            out.append((f"{year}Q{q}", f"{year}-{start}", f"{year}-{end}"))
    return out


def quarter_rows(label: str, start: str, end: str) -> list[dict]:
    rows = []
    for page in range(1, PAGES + 1):
        body = {"filters": {"time_period": [{"start_date": start, "end_date": end}],
                            "award_type_codes": ["A", "B", "C", "D"]},
                "category": "recipient", "spending_level": "transactions",
                "limit": 100, "page": page}
        payload = fetch(f"{API}/search/spending_by_category/recipient/", body,
                        CACHE / "quarters" / f"{label}_p{page}.json")
        for r in payload.get("results", []):
            rows.append({"quarter": label, "recipient_id": r.get("recipient_id"),
                         "name": r.get("name"), "uei": r.get("uei"), "amount": r.get("amount")})
        if not payload.get("page_metadata", {}).get("hasNext"):
            break
    return rows


def parent(recipient_id: str) -> dict:
    if not recipient_id:
        return {}
    try:
        p = fetch(f"{API}/recipient/{recipient_id}/", None, CACHE / "recipients" / f"{recipient_id}.json")
    except Exception:                                          # noqa: BLE001
        return {"recipient_id": recipient_id, "parent_name": None}
    return {"recipient_id": recipient_id, "parent_name": p.get("parent_name") or p.get("name"),
            "parent_uei": p.get("parent_uei"), "recipient_level": p.get("recipient_level")}


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for chunk in pool.map(lambda q: quarter_rows(*q), quarters()):
            rows.extend(chunk)
    frame = pd.DataFrame(rows)
    print(f"quarter rows: {len(frame):,}, quarters {frame.quarter.nunique()}, "
          f"recipients {frame.recipient_id.nunique():,}")
    ids = sorted(frame.recipient_id.dropna().unique())
    with ThreadPoolExecutor(max_workers=8) as pool:
        parents = pd.DataFrame([p for p in pool.map(parent, ids) if p])
    frame = frame.merge(parents, on="recipient_id", how="left")
    frame.to_csv(OUTPUT / "quarterly_recipient_obligations.csv.gz", index=False)
    (OUTPUT / "manifest.json").write_text(json.dumps({
        "source": API, "award_type_codes": ["A", "B", "C", "D"], "spending_level": "transactions",
        "recipients_per_quarter": PAGES * 100, "quarters": int(frame.quarter.nunique()),
        "rows": int(len(frame)), "unique_recipients": len(ids),
        "parents_resolved": int(parents.parent_name.notna().sum()),
        "acquired_on": date.today().isoformat(),
        "parent_mapping_is_current_not_point_in_time": True,
    }, indent=2) + "\n")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
