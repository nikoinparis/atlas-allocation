#!/usr/bin/env python3
"""Build compact, hashed historical fixtures without modifying Portfolio Optimizer 1.0."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "1.0/data/01_data_hub/daily_prices.csv"
METADATA_SOURCE = ROOT.parent / "1.0/data/01_data_hub/yahoo_metadata_snapshot.csv"
OUTPUT = ROOT / "evidence/historical_validation/fixtures/equity_daily_adjusted_close.csv"
PROVENANCE = ROOT / "evidence/historical_validation/fixtures/provenance.json"
SYMBOLS = ("SPY", "TLT", "GLD")
START = "2006-01-01"
END = "2026-04-14"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> dict[str, object]:
    if not SOURCE.exists() or not METADATA_SOURCE.exists():
        raise FileNotFoundError("Portfolio Optimizer 1.0 data hub is required to build the fixture")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    selected: list[dict[str, str]] = []
    with SOURCE.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        missing = [name for name in ("Date", *SYMBOLS) if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing required columns: {missing}")
        for row in reader:
            if START <= row["Date"] <= END:
                compact = {name: row[name] for name in ("Date", *SYMBOLS)}
                if not all(compact[name] for name in SYMBOLS):
                    raise ValueError(f"missing selected price on {row['Date']}")
                selected.append(compact)
    if not selected:
        raise ValueError("selected fixture is empty")

    with OUTPUT.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=["Date", *SYMBOLS], lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected)

    metadata: dict[str, dict[str, str]] = {}
    with METADATA_SOURCE.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("ticker") in SYMBOLS:
                metadata[row["ticker"]] = {
                    "pull_timestamp_utc": row.get("pull_timestamp_utc", ""),
                    "long_name": row.get("longName", ""),
                    "currency": row.get("currency", ""),
                    "asset_class": row.get("asset_class", ""),
                    "description": row.get("description", ""),
                }

    record: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": str(OUTPUT.relative_to(ROOT)),
        "fixture_sha256": sha256(OUTPUT),
        "rows": len(selected),
        "first_date": selected[0]["Date"],
        "last_date": selected[-1]["Date"],
        "symbols": list(SYMBOLS),
        "source": str(SOURCE.relative_to(ROOT.parent)),
        "source_sha256": sha256(SOURCE),
        "metadata_source": str(METADATA_SOURCE.relative_to(ROOT.parent)),
        "metadata_source_sha256": sha256(METADATA_SOURCE),
        "source_metadata": metadata,
        "data_semantics": "Yahoo-derived daily adjusted close snapshot inherited read-only from Portfolio Optimizer 1.0",
        "known_limits": [
            "Adjusted close has no open/high/low or quote information and cannot validate intraday execution.",
            "The present-day three-ETF selection is not point-in-time universe membership and is subject to selection/survivorship bias.",
            "The upstream vendor snapshot can be revised; hashes pin exactly what this run used.",
        ],
    }
    PROVENANCE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
