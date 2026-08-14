#!/usr/bin/env python3
"""Acquire a frozen free adjusted-price panel for the SEC engineering pilot."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_fundamental_pilot_v1.json"
OUTPUT_ROOT = ROOT / "data/sec_pilot_price_vintages"
IMAGE = "localhost/po2-yfinance:1.5.2-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    config = json.loads(CONFIG.read_text())
    tickers = sorted({ticker for group in config["pilot_universe"].values() for ticker in group} | {"SPY", "XLK", "XLE"})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-sec-pilot-prices"
    with tempfile.TemporaryDirectory() as temporary:
        export = Path(temporary) / "export"
        export.mkdir()
        command = [
            "podman", "run", "--rm", "-v", f"{export}:/export:Z", IMAGE,
            "--symbols", ",".join(tickers), "--period", "max", "--output", "/export",
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(f"price acquisition failed: {completed.stdout} {completed.stderr}")
        metadata = json.loads((export / "acquisition_metadata.json").read_text())
        if metadata.get("status") != "complete":
            raise RuntimeError(str(metadata.get("errors")))
        output.mkdir(parents=True)
        for path in export.iterdir():
            shutil.copy2(path, output / path.name)
    files = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in sorted(output.iterdir()) if path.is_file()}
    manifest = {
        "vintage_id": output.name, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance via pinned yfinance 1.5.2 container", "symbols": tickers,
        "symbol_count": len(tickers), "price_rows": metadata["price_rows"], "observed_at_utc": metadata["observed_at_utc"],
        "files": files, "claims": {"point_in_time_universe": False, "delisting_complete": False, "revision_complete": False},
        "purpose": "non-promotable SEC fundamental pilot diagnostic", "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
