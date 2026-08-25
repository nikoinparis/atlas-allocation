#!/usr/bin/env python3
"""Freeze and normalize Telkom University SRIL/WSKT research price files."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data" / "indonesia_idx80_inactive_price_supplement_vintages"
DOWNLOADS = Path.home() / "Downloads"
SOURCES = {
    "SRIL.JK": {
        "filename": "SRIL.JK.csv",
        "md5": "3b21910602b9ae3278f7a9bb14421d79",
        "persistent_id": "doi:10.34820/FK2/0YDDJS/SIQEMG",
        "unf": "UNF:6:XYpqroZcI9nz4MsVkJHjhA==",
        "suspension_date": "2021-05-18",
    },
    "WSKT.JK": {
        "filename": "WSKT.JK.csv",
        "md5": "55729f846b376c14bda3ac4a3e1585b4",
        "persistent_id": "doi:10.34820/FK2/0YDDJS/DFHMCN",
        "unf": "UNF:6:NVy15wnURwk3vTCBcgXMrA==",
        "suspension_date": "2023-05-08",
    },
}
DATASET_DOI = "doi:10.34820/FK2/0YDDJS"
DATASET_URL = "https://dataverse.telkomuniversity.ac.id/dataset.xhtml?persistentId=doi%3A10.34820%2FFK2%2F0YDDJS"


def digest(path: Path, algorithm: str = "sha256") -> str:
    value = hashlib.new(algorithm)
    value.update(path.read_bytes())
    return value.hexdigest()


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vintage_id = f"{stamp}-idx80-inactive-price-supplement-v1"
    destination = OUTPUT_ROOT / vintage_id
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    frames: list[pd.DataFrame] = []
    source_rows: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="idx80-inactive-supplement-", dir=ROOT / "data") as temporary:
        staging = Path(temporary)
        raw = staging / "raw"
        raw.mkdir()
        for ticker, source in SOURCES.items():
            incoming = DOWNLOADS / str(source["filename"])
            if not incoming.exists():
                raise FileNotFoundError(incoming)
            if digest(incoming, "md5") != source["md5"]:
                raise ValueError(f"MD5 mismatch for {incoming}")
            frozen = raw / str(source["filename"])
            shutil.copy2(incoming, frozen)
            frame = pd.read_csv(frozen)
            frame = frame.rename(
                columns={
                    "Date": "observation_date", "Open": "open", "High": "high", "Low": "low",
                    "Close": "close", "Adj Close": "adjusted_close", "Volume": "volume"
                }
            )
            frame.insert(1, "security_id", f"telkom-dataverse:{ticker}")
            frame.insert(2, "ticker", ticker)
            frame["knowledge_at_utc"] = "2023-10-02T00:00:00+00:00"
            frame["source_revision"] = f"telkom-dataverse-v1:{source['persistent_id']}"
            frames.append(frame)
            positive_volume = frame[pd.to_numeric(frame["volume"], errors="coerce") > 0]
            source_rows.append(
                {
                    "ticker": ticker,
                    "persistent_id": source["persistent_id"],
                    "unf": source["unf"],
                    "md5": source["md5"],
                    "rows": len(frame),
                    "first_date": frame["observation_date"].min(),
                    "last_date": frame["observation_date"].max(),
                    "last_positive_volume_date": positive_volume["observation_date"].max(),
                    "suspension_date": source["suspension_date"],
                }
            )
        normalized = pd.concat(frames, ignore_index=True).sort_values(["ticker", "observation_date"])
        normalized.to_csv(staging / "prices.csv", index=False)
        pd.DataFrame(source_rows).to_csv(staging / "source_manifest.csv", index=False)
        files = {}
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                files[str(path.relative_to(staging))] = {
                    "bytes": path.stat().st_size,
                    "sha256": digest(path),
                }
        manifest = {
            "vintage_id": vintage_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "purpose": "research-only inactive-security price supplement for IDX80 diagnostic",
            "dataset_doi": DATASET_DOI,
            "dataset_url": DATASET_URL,
            "citation": "Fahrudin, Tora (2023), Dataset Harga Saham-Saham LQ45 Periode 2019 s/d 2023, Telkom University Dataverse, V1.",
            "normalized_rows": len(normalized),
            "tickers": sorted(SOURCES),
            "claims": {
                "independent_from_yahoo": True,
                "provider_vintage_frozen": True,
                "point_in_time_price_vintage": False,
                "complete_delisting_returns": False,
                "licensed_for_redistribution": False,
                "research_only": True,
            },
            "files": files,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        shutil.copytree(staging, destination)
    (OUTPUT_ROOT / "LATEST").write_text(vintage_id + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
