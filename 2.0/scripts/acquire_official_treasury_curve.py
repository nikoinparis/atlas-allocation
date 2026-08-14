#!/usr/bin/env python3
"""Acquire and immutably register the free official U.S. Treasury curve."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.term_structure_challenger import parse_treasury_xml

BASE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
STORE = ROOT / "data/official_treasury_vintages"
OUTPUT = ROOT / "evidence/official_treasury_curve_acquisition"
USER_AGENT = "PortfolioOptimizerResearch/2.0 contact=local-research"


def fetch_year(year: int) -> tuple[int, bytes]:
    url = f"{BASE_URL}?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return year, response.read()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def acquire(start_year: int, end_year: int) -> dict[str, object]:
    observed_at = datetime.now(timezone.utc)
    years = list(range(start_year, end_year + 1))
    with ThreadPoolExecutor(max_workers=4) as executor:
        payloads = dict(executor.map(fetch_year, years))
    rows_by_date: dict[str, dict[str, float | str]] = {}
    for year in years:
        for row in parse_treasury_xml(payloads[year]):
            rows_by_date[str(row["observation_date"])] = row
    rows = [rows_by_date[day] for day in sorted(rows_by_date)]
    if not rows:
        raise RuntimeError("Treasury returned no complete curve rows")

    digest_basis = "".join(f"{year}:{sha256_bytes(payloads[year])}\n" for year in years).encode()
    digest = hashlib.sha256(digest_basis).hexdigest()
    snapshot_id = observed_at.strftime("%Y%m%dT%H%M%SZ") + "-" + digest[:16]
    destination = STORE / snapshot_id
    if destination.exists():
        raise RuntimeError(f"snapshot already exists: {snapshot_id}")
    with tempfile.TemporaryDirectory(dir=STORE.parent if STORE.parent.exists() else ROOT) as temporary:
        staging = Path(temporary) / snapshot_id
        raw = staging / "raw"
        raw.mkdir(parents=True)
        for year, payload in payloads.items():
            (raw / f"{year}.xml").write_bytes(payload)
        with (staging / "curve.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest = {
            "schema_version": 1,
            "snapshot_id": snapshot_id,
            "provider": "U.S. Department of the Treasury",
            "source_uri": BASE_URL,
            "observed_at_utc": observed_at.isoformat(),
            "coverage": {"start": rows[0]["observation_date"], "end": rows[-1]["observation_date"], "rows": len(rows)},
            "years_requested": years,
            "files_sha256": {f"raw/{year}.xml": sha256_bytes(payloads[year]) for year in years},
            "normalized_curve_sha256": hashlib.sha256((staging / "curve.csv").read_bytes()).hexdigest(),
            "cost": "free; no API key",
            "publication_lag_policy": "a curve may enter a decision only after a full seven-calendar-day lag",
            "revision_policy": "this local pull is immutable, but Treasury does not expose vintage-by-vintage revisions in this feed",
            "point_in_time_grade": "publication-date-causal_with_pre-acquisition_revision_caveat",
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        STORE.mkdir(parents=True, exist_ok=True)
        staging.rename(destination)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), **manifest}
    (OUTPUT / "latest_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2002)
    parser.add_argument("--end-year", type=int, default=datetime.now(timezone.utc).year)
    args = parser.parse_args()
    result = acquire(args.start_year, args.end_year)
    print(json.dumps({"snapshot_id": result["snapshot_id"], "coverage": result["coverage"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
