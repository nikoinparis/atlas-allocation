#!/usr/bin/env python3
"""Build a point-in-time technology/energy filer roster from SEC FSDS archives."""

from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_historical_universe import (
    attach_current_tickers,
    build_membership,
    normalize_submissions,
    quarter_decisions,
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "config/sec_historical_filer_universe_v1.json"))
    parser.add_argument("--output-root", default=str(ROOT / "data/sec_historical_universe_vintages"))
    parser.add_argument("--cache-root", default=str(ROOT / "data/sec_fsds_sub_cache"))
    parser.add_argument("--start", default=None, help="Optional YYYYQn override")
    parser.add_argument("--end", default=None, help="Optional YYYYQn override")
    return parser.parse_args()


def archive_range(start: str, end: str) -> list[tuple[int, int]]:
    sy, sq = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    values = [(year, quarter) for year in range(sy, ey + 1) for quarter in range(1, 5)]
    return [(year, quarter) for year, quarter in values if (year, quarter) >= (sy, sq) and (year, quarter) <= (ey, eq)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_user_agent() -> str:
    value = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in value or len(value) < 12:
        raise RuntimeError("SEC_USER_AGENT must identify the research project and a real contact")
    return value


def fetch_archive(year: int, quarter: int, config: dict, cache: Path, user_agent: str) -> dict:
    key = f"{year}q{quarter}"
    sub_path = cache / f"{key}.sub.txt.gz"
    meta_path = cache / f"{key}.json"
    if sub_path.exists() and meta_path.exists():
        return json.loads(meta_path.read_text())
    url = config["archive_url_template"].format(year=year, quarter=quarter)
    cache.mkdir(parents=True, exist_ok=True)
    error: Exception | None = None
    for attempt in range(4):
        temp_name: str | None = None
        try:
            request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
            started = time.monotonic()
            with urllib.request.urlopen(request, timeout=int(config["request_timeout_seconds"])) as response:
                with tempfile.NamedTemporaryFile(prefix=f"{key}-", suffix=".zip", delete=False, dir=cache) as temp:
                    temp_name = temp.name
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        temp.write(chunk)
                    status = int(response.status)
            temp_path = Path(temp_name)
            zip_hash = sha256_file(temp_path)
            zip_bytes = temp_path.stat().st_size
            with zipfile.ZipFile(temp_path) as archive:
                member = next(name for name in archive.namelist() if name.lower().endswith("sub.txt"))
                sub_bytes = archive.read(member)
            with sub_path.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
                    compressed.write(sub_bytes)
            temp_path.unlink()
            metadata = {
                "source_quarter": key.upper(),
                "url": url,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "http_status": status,
                "zip_bytes": zip_bytes,
                "zip_sha256": zip_hash,
                "sub_bytes": len(sub_bytes),
                "sub_sha256": hashlib.sha256(sub_bytes).hexdigest(),
                "cached_sub_file": str(sub_path.resolve()),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
            meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
            return metadata
        except Exception as exc:
            error = exc
            if temp_name and Path(temp_name).exists():
                Path(temp_name).unlink()
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to acquire {key} from {url}: {error}")


def fetch_json(url: str, cache_path: Path, user_agent: str, timeout: int) -> tuple[dict, dict]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
        if (response.headers.get("Content-Encoding") or "").lower() == "gzip" or payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
        status = int(response.status)
    cache_path.write_bytes(payload)
    metadata = {
        "url": url,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "http_status": status,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "cache_file": str(cache_path.resolve()),
    }
    return json.loads(payload), metadata


def read_sub(cache: Path, metadata: dict) -> pd.DataFrame:
    path = Path(metadata["cached_sub_file"])
    frame = pd.read_csv(path, sep="\t", dtype=str, low_memory=False)
    frame["source_quarter"] = metadata["source_quarter"]
    return frame


def mapping_frame(payload: dict) -> pd.DataFrame:
    if "fields" in payload and "data" in payload:
        return pd.DataFrame(payload["data"], columns=payload["fields"])
    return pd.DataFrame(payload.values()).rename(columns={"cik_str": "cik", "title": "name"})


def main() -> int:
    args = arguments()
    config_path = Path(args.config).resolve()
    config = json.loads(config_path.read_text())
    start = args.start or config["archive_start"]
    end = args.end or config["archive_end"]
    quarters = archive_range(start, end)
    cache = Path(args.cache_root).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    user_agent = require_user_agent()

    metadata: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(config["download_workers"])) as pool:
        futures = {pool.submit(fetch_archive, year, quarter, config, cache, user_agent): (year, quarter) for year, quarter in quarters}
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            metadata.append(row)
            print(f"ready {row['source_quarter']} ({row['zip_bytes'] / 1_000_000:.1f} MB source)", flush=True)
    metadata.sort(key=lambda row: row["source_quarter"])

    normalized: list[pd.DataFrame] = []
    for row in metadata:
        normalized.append(normalize_submissions(
            read_sub(cache, row), config["sic_groups"], config["accepted_forms"], config["accepted_filer_statuses"]
        ))
    submissions = pd.concat(normalized, ignore_index=True).drop_duplicates("adsh", keep="last")
    submissions = submissions.sort_values(["available_at", "adsh"]).reset_index(drop=True)
    decisions = quarter_decisions(f"{start[:4]}-01-01", pd.Period(end, freq="Q").end_time.normalize())
    membership = build_membership(submissions, decisions, int(config["membership_staleness_days"]))

    ticker_cache = cache / "company_tickers_exchange.json"
    ticker_payload, ticker_meta = fetch_json(
        config["current_ticker_mapping_url"], ticker_cache, user_agent, int(config["request_timeout_seconds"])
    )
    membership, identities = attach_current_tickers(membership, mapping_frame(ticker_payload))
    coverage = membership.groupby(["decision_at", "sector"], as_index=False).agg(
        members=("cik10", "nunique"),
        current_ticker_matches=("identity_status", lambda values: int((values == "current_ticker_available").sum())),
        former_or_unmapped=("identity_status", lambda values: int((values == "former_or_unmapped").sum())),
    )
    coverage["current_ticker_coverage"] = coverage["current_ticker_matches"] / coverage["members"]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(args.output_root).resolve() / f"{stamp}-sec-historical-filers-v1"
    output.mkdir(parents=True, exist_ok=False)
    submissions.to_csv(output / "qualifying_submissions.csv", index=False)
    membership.to_csv(output / "quarterly_membership.csv", index=False)
    identities.to_csv(output / "cik_identity_coverage.csv", index=False)
    coverage.to_csv(output / "coverage_by_decision.csv", index=False)
    pd.DataFrame(metadata).to_csv(output / "source_archives.csv", index=False)
    ticker_meta["source_quarter"] = "CURRENT_TICKER_MAPPING"
    pd.DataFrame([ticker_meta]).to_csv(output / "ticker_mapping_source.csv", index=False)

    latest = membership[membership["decision_at"] == membership["decision_at"].max()]
    former = identities[identities["identity_status"] == "former_or_unmapped"]
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(config_path),
        "archive_start": start,
        "archive_end": end,
        "archives": len(metadata),
        "source_zip_bytes": int(sum(row["zip_bytes"] for row in metadata)),
        "qualifying_submission_rows": int(len(submissions)),
        "unique_historical_ciks": int(submissions["cik10"].nunique()),
        "membership_rows": int(len(membership)),
        "decisions": int(membership["decision_at"].nunique()),
        "latest_members": int(latest["cik10"].nunique()),
        "historical_ciks_without_current_ticker": int(former["cik10"].nunique()),
        "historical_cik_current_ticker_coverage": float(identities["has_current_sec_ticker"].mean()),
        "strict_point_in_time_membership": True,
        "historical_ticker_mapping_complete": False,
        "delisting_returns_complete": False,
        "strategy_testing_authorized": False,
        "limitations": config["limitations"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
