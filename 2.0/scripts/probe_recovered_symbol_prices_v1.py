#!/usr/bin/env python3
"""Freeze Yahoo histories for SEC-recovered former-company symbols, preserving failures."""

from __future__ import annotations

import gzip
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "evidence/sec_historical_identity_v1"
OUTPUT_ROOT = ROOT / "data/sec_recovered_price_probe_vintages"


def safe_name(symbol: str) -> str:
    return symbol.replace("/", "_").replace("\\", "_")


def main() -> int:
    identity = pd.read_csv(IDENTITY / "combined_identity_map.csv", dtype={"cik10": str})
    recovered = identity[
        identity["single_symbol_usable_for_price_probe"].astype(bool)
        & identity["symbol_source"].isin(["last_filing_inline_xbrl", "last_filing_instance_xbrl"])
    ].copy()
    symbols = sorted(recovered["candidate_symbols"].dropna().unique())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-recovered-yahoo-price-probe-v1"
    history_dir = output / "histories"
    history_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, symbol in enumerate(symbols, start=1):
        started = datetime.now(timezone.utc).isoformat()
        row = {"ticker": symbol, "started_at_utc": started, "status": "failed", "rows": 0}
        try:
            frame = yf.Ticker(symbol).history(
                period="max", interval="1d", auto_adjust=False, actions=True, repair=False
            )
            if frame.empty:
                raise RuntimeError("empty history")
            frame = frame.reset_index()
            date_column = "Date" if "Date" in frame.columns else frame.columns[0]
            frame[date_column] = pd.to_datetime(frame[date_column], utc=True, errors="coerce").dt.strftime("%Y-%m-%d")
            payload = frame.to_csv(index=False).encode("utf-8")
            destination = history_dir / f"{safe_name(symbol)}.csv.gz"
            destination.write_bytes(gzip.compress(payload, compresslevel=6, mtime=0))
            dates = pd.to_datetime(frame[date_column], errors="coerce")
            row.update({
                "status": "ok",
                "rows": int(len(frame)),
                "first_observed_date": dates.min().date().isoformat(),
                "last_observed_date": dates.max().date().isoformat(),
                "history_file": str(destination.relative_to(output)),
                "uncompressed_sha256": hashlib.sha256(payload).hexdigest(),
                "compressed_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                "error_type": None,
                "error_message": None,
            })
        except Exception as exc:
            row.update({
                "first_observed_date": None,
                "last_observed_date": None,
                "history_file": None,
                "uncompressed_sha256": None,
                "compressed_sha256": None,
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
            })
        row["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
        rows.append(row)
        if index % 25 == 0 or index == len(symbols):
            print(f"processed {index}/{len(symbols)}; prices found {sum(x['status'] == 'ok' for x in rows)}", flush=True)
    pulls = pd.DataFrame(rows).sort_values(["status", "ticker"]).reset_index(drop=True)
    pulls.to_csv(output / "price_probe_results.csv", index=False)
    ok = int((pulls["status"] == "ok").sum())
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "Yahoo Finance via pinned yfinance container",
        "yfinance_version": yf.__version__,
        "python_version": platform.python_version(),
        "scope": "usable single symbols recovered from former/unmapped SEC CIKs",
        "symbols_requested": int(len(symbols)),
        "symbols_with_history": ok,
        "symbols_failed": int(len(symbols) - ok),
        "raw_symbol_history_rate": float(ok / len(symbols)) if symbols else 0.0,
        "ticker_reuse_validated": False,
        "delisting_returns_complete": False,
        "strategy_testing_authorized": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
