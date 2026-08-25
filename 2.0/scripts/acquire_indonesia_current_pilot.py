#!/usr/bin/env python3
"""Freeze a research-only current Indonesian universe and five-year price pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/indonesia_current_universes_2026-08-03.json"
OUTPUT_ROOT = ROOT / "data/indonesia_equity_vintages"
IMAGE = "localhost/po2-yfinance:1.5.2-v1"
BENCHMARK_SYMBOLS = ("^JKSE", "^JKLQ45")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_config(config: dict[str, object]) -> None:
    universes = config["universes"]
    expected = {"IDX80": 80, "LQ45": 45, "IDX30": 30}
    for universe, count in expected.items():
        members = universes[universe]
        if len(members) != count or len(set(members)) != count:
            raise ValueError(f"{universe} must contain {count} unique members")
        if any(len(ticker) != 4 or ticker != ticker.upper() for ticker in members):
            raise ValueError(f"{universe} contains an invalid IDX code")
    if not set(universes["IDX30"]).issubset(universes["LQ45"]):
        raise ValueError("IDX30 current snapshot must be a subset of LQ45")
    if not set(universes["LQ45"]).issubset(universes["IDX80"]):
        raise ValueError("LQ45 current snapshot must be a subset of IDX80")
    if config.get("historical_membership") or config.get("backtest_membership_authorized"):
        raise ValueError("current snapshot cannot authorize historical membership or backtests")


def observe_source(url: str) -> dict[str, object]:
    observed = datetime.now(timezone.utc).isoformat()
    try:
        request = Request(url, headers={"User-Agent": "PortfolioOptimizerResearch/2.0"})
        with urlopen(request, timeout=60) as response:
            payload = response.read()
            return {
                "observed_at_utc": observed,
                "http_status": getattr(response, "status", 200),
                "bytes_observed": len(payload),
                "sha256_observed_content": hashlib.sha256(payload).hexdigest(),
                "content_type": response.headers.get("Content-Type", ""),
                "observation_status": "ok",
            }
    except Exception as error:
        return {
            "observed_at_utc": observed,
            "observation_status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
        }


def write_membership(path: Path, config: dict[str, object], available_at: str) -> int:
    fields = [
        "ticker",
        "vendor_ticker",
        "universe",
        "effective_from",
        "effective_to",
        "available_at",
        "source_id",
        "point_in_time_membership",
        "backtest_authorized",
    ]
    count = 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for universe in ("IDX80", "LQ45", "IDX30"):
            for ticker in config["universes"][universe]:
                writer.writerow(
                    {
                        "ticker": ticker,
                        "vendor_ticker": f"{ticker}.JK",
                        "universe": universe,
                        "effective_from": config["effective_from"],
                        "effective_to": config["effective_to_exclusive"],
                        "available_at": available_at,
                        "source_id": config["snapshot_id"],
                        "point_in_time_membership": "false",
                        "backtest_authorized": "false",
                    }
                )
                count += 1
    return count


def write_source_index(path: Path, config: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for source in config["sources"]:
        rows.append({**source, **observe_source(source["url"])})
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    validate_config(config)
    tickers = sorted(config["universes"]["IDX80"])
    yahoo_symbols = [*BENCHMARK_SYMBOLS, *(f"{ticker}.JK" for ticker in tickers)]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-indonesia-current-pilot-v1"
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="indonesia-acquire-", dir=ROOT / "data") as temporary:
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
            ",".join(yahoo_symbols),
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
                f"Indonesia price acquisition failed: {completed.stdout} {completed.stderr} "
                f"{metadata.get('errors')}"
            )
        output.mkdir()
        for path in export.iterdir():
            if path.name != "universe_membership.csv":
                shutil.copy2(path, output / path.name)

    observed_at = str(metadata["observed_at_utc"])
    membership_rows = write_membership(output / "universe_membership.csv", config, observed_at)
    source_observations = write_source_index(output / "source_index.csv", config)
    shutil.copy2(CONFIG, output / "universe_config.json")

    files = {
        path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "research-only current Indonesian liquid-equity data pilot",
        "notice": config["notice"],
        "universe_status": config["status"],
        "provider": "Yahoo Finance via pinned yfinance 1.5.2 container",
        "provider_terms": "Research/personal-use cache; Yahoo terms and yfinance warnings apply; no redistribution right is asserted.",
        "currency": "IDR",
        "current_universe_counts": {name: len(values) for name, values in config["universes"].items()},
        "membership_rows": membership_rows,
        "price_symbols_requested": len(yahoo_symbols),
        "price_rows": metadata["price_rows"],
        "action_rows": metadata["action_rows"],
        "observed_at_utc": observed_at,
        "source_observation_failures": sum(
            row.get("observation_status") != "ok" for row in source_observations
        ),
        "claims": {
            "current_period_snapshot": True,
            "official_constituent_file_validated": False,
            "point_in_time_historical_membership": False,
            "survivorship_safe": False,
            "delisting_complete": False,
            "licensed_for_redistribution": False,
            "backtest_authorized": False,
            "performance_claim_authorized": False,
            "live_trading_enabled": False,
        },
        "benchmarks_available": ["^JKSE", "^JKLQ45"],
        "benchmarks_missing": ["IDX80", "IDX30"],
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT_ROOT / "LATEST").write_text(output.name + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
