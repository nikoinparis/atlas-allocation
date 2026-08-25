#!/usr/bin/env python3
"""Acquire a frozen Yahoo research cache for the official IDX80 history union."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP_ROOT = ROOT / "data" / "indonesia_idx80_history_vintages"
OUTPUT_ROOT = ROOT / "data" / "indonesia_idx80_history_price_vintages"
IMAGE = "localhost/po2-yfinance:1.5.2-v1"
BENCHMARKS = ("^JKSE", "^JKLQ45")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    membership_vintage = (MEMBERSHIP_ROOT / "LATEST").read_text(encoding="utf-8").strip()
    membership_dir = MEMBERSHIP_ROOT / membership_vintage
    membership_manifest = json.loads((membership_dir / "manifest.json").read_text(encoding="utf-8"))
    if not membership_manifest["claims"]["point_in_time_for_covered_period"]:
        raise ValueError("membership vintage is not point-in-time for its covered period")
    membership = pd.read_csv(membership_dir / "idx80_membership.csv")
    tickers = sorted(set(membership["ticker"]))
    symbols = [*BENCHMARKS, *(f"{ticker}.JK" for ticker in tickers)]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    vintage_id = f"{stamp}-idx80-history-prices-v1"
    destination = OUTPUT_ROOT / vintage_id
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="idx80-history-prices-", dir=ROOT / "data") as temporary:
        export = Path(temporary) / "export"
        export.mkdir()
        command = [
            "podman",
            "run",
            "--rm",
            "-v",
            f"{export.resolve()}:/export:Z",
            IMAGE,
            "--symbols",
            ",".join(symbols),
            "--period",
            "5y",
            "--output",
            "/export",
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        metadata_path = export / "acquisition_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if completed.returncode != 0 or metadata.get("status") != "complete":
            raise RuntimeError(
                f"IDX80 union price acquisition failed: {completed.stdout} {completed.stderr} "
                f"{metadata.get('errors')}"
            )
        destination.mkdir()
        for path in export.iterdir():
            shutil.copy2(path, destination / path.name)
    shutil.copy2(membership_dir / "idx80_membership.csv", destination / "idx80_membership.csv")
    files = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(destination.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "vintage_id": vintage_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "research-only prices for official IDX80 2024-2026 membership union",
        "membership_vintage": membership_vintage,
        "membership_manifest_sha256": sha256(membership_dir / "manifest.json"),
        "provider": "Yahoo Finance via pinned yfinance 1.5.2 container",
        "provider_terms": "Research/personal-use cache; Yahoo terms and yfinance warnings apply; no redistribution right is asserted.",
        "symbols_requested": len(symbols),
        "idx80_union_tickers": len(tickers),
        "price_rows": metadata["price_rows"],
        "action_rows": metadata["action_rows"],
        "observed_at_utc": metadata["observed_at_utc"],
        "claims": {
            "membership_official_for_covered_period": True,
            "price_vendor_revision_frozen": True,
            "licensed_for_redistribution": False,
            "delisting_complete": False,
            "target_history_complete_from_2019": False,
            "performance_claim_authorized": False,
            "live_trading_enabled": False,
        },
        "files": files,
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT_ROOT / "LATEST").write_text(vintage_id + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
