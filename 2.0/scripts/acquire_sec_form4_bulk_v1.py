#!/usr/bin/env python3
"""Acquire an immutable, hash-audited SEC Forms 3/4/5 bulk-data vintage."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_form4_bulk_acquisition_v1.json"
VINTAGES = ROOT / "data/sec_form4_bulk_vintages"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    config = json.loads(CONFIG.read_text())
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent:
        raise RuntimeError("SEC_USER_AGENT with a real contact address is required")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-sec-form4-bulk-v1"
    target = VINTAGES / run_id
    if target.exists():
        raise FileExistsError(target)
    rows = []
    with tempfile.TemporaryDirectory(prefix="sec-form4-") as temporary:
        staging = Path(temporary) / run_id
        raw = staging / "raw"
        extracted = staging / "extracted"
        raw.mkdir(parents=True)
        extracted.mkdir(parents=True)
        for quarter in config["quarters"]:
            url = config.get("url_overrides", {}).get(
                quarter, config["standard_url_template"].format(quarter=quarter)
            )
            archive = raw / f"{quarter}_form345.zip"
            request = urllib.request.Request(url, headers={"User-Agent": user_agent})
            observed_at = datetime.now(timezone.utc).isoformat()
            with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as output:
                shutil.copyfileobj(response, output)
            with zipfile.ZipFile(archive) as bundle:
                names = set(bundle.namelist())
                missing = sorted(set(config["required_tables"]) - names)
                if missing:
                    raise RuntimeError(f"{quarter} is missing required tables: {missing}")
                quarter_dir = extracted / quarter
                quarter_dir.mkdir()
                for name in config["required_tables"]:
                    bundle.extract(name, quarter_dir)
            rows.append({
                "quarter": quarter,
                "url": url,
                "observed_at_utc": observed_at,
                "archive": str(archive.relative_to(staging)),
                "bytes": archive.stat().st_size,
                "sha256": sha256(archive),
            })
            print(f"acquired {quarter}: {archive.stat().st_size:,} bytes", flush=True)
        manifest = {
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "SEC Insider Transactions Data Sets",
            "source_page": "https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets",
            "archives": rows,
            "required_tables": config["required_tables"],
            "contact_persisted": False,
            "immutable_vintage": True,
            "strategy_testing_authorized": False,
            "live_trading_enabled": False,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        VINTAGES.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staging), str(target))
    latest = VINTAGES / "LATEST"
    latest.write_text(run_id + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
