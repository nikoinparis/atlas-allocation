#!/usr/bin/env python3
"""Recreate unreadable cloud-placeholder price inputs in an audited repair vintage."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/daily_audit_price_source_repairs_v1"

YAHOO = {
    "0000788965": "HNRG",
    "0000927003": "AEIS",
    "0000945983": "CLMB",
    "0001039399": "FORM",
    "0001124804": "MDRX",
    "0001361113": "VRNS",
    "0001463101": "ENPH",
    "0001520006": "MTDR",
    "0001650372": "TEAM",
    "0001653482": "GTLB",
    "0001679268": "TUSK",
    "0001694028": "LBRT",
    "0001713445": "RDDT",
    "0001713683": "ZS",
    "0001855747": "BLND",
}

TIINGO = {
    "0001701732": ("ALTR", "2019-04-01", "2026-04-11"),
    "0001827075": ("CVT", "2022-04-01", "2024-07-11"),
    "0001863105": ("ESMT", "2023-04-01", "2025-01-11"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_gzip_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = frame.to_csv(index=False).encode()
    with gzip.GzipFile(filename=str(path), mode="wb", mtime=0) as handle:
        handle.write(payload)


def yahoo_rows() -> list[dict]:
    rows = []
    for cik, ticker in YAHOO.items():
        frame = yf.Ticker(ticker).history(
            start="2018-01-01",
            end="2026-08-12",
            auto_adjust=False,
            actions=True,
            repair=False,
        )
        if frame.empty:
            raise RuntimeError(f"Yahoo returned no rows for {ticker}")
        frame = frame.reset_index()
        frame["Date"] = pd.to_datetime(frame["Date"], utc=True).dt.tz_localize(None).dt.strftime("%Y-%m-%d")
        required = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
        for column in required:
            if column not in frame:
                frame[column] = 0.0
        path = OUTPUT / "yahoo" / f"{ticker}.csv.gz"
        write_gzip_csv(frame[required], path)
        rows.append({"cik10": cik, "ticker": ticker, "source": "yahoo_repair_v1", "price_file": str(path.relative_to(ROOT)), "rows": len(frame), "first_date": frame.Date.min(), "last_date": frame.Date.max(), "sha256": sha256(path)})
    return rows


def tiingo_rows(token: str) -> list[dict]:
    rows = []
    headers = {"Authorization": f"Token {token}"}
    for cik, (ticker, start, end) in TIINGO.items():
        url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices"
        response = requests.get(url, headers=headers, params={"startDate": start, "endDate": end, "resampleFreq": "daily"}, timeout=60)
        response.raise_for_status()
        frame = pd.DataFrame(response.json())
        if frame.empty:
            raise RuntimeError(f"Tiingo returned no rows for {ticker}")
        path = OUTPUT / "tiingo" / ticker / "prices.csv.gz"
        write_gzip_csv(frame, path)
        rows.append({"cik10": cik, "ticker": ticker, "source": "tiingo_repair_v1", "price_file": str(path.relative_to(ROOT)), "rows": len(frame), "first_date": str(pd.to_datetime(frame.date).min().date()), "last_date": str(pd.to_datetime(frame.date).max().date()), "sha256": sha256(path)})
    return rows


def main() -> int:
    token = os.environ.get("TIINGO_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TIINGO_API_TOKEN is required for the three delisted repair sources")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = yahoo_rows() + tiingo_rows(token)
    manifest = pd.DataFrame(rows).sort_values("cik10")
    manifest.to_csv(OUTPUT / "manifest.csv", index=False)
    result = {
        "experiment": "daily_audit_price_source_repairs_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": len(manifest),
        "yahoo_sources": len(YAHOO),
        "tiingo_sources": len(TIINGO),
        "all_files_hashed": bool(manifest.sha256.str.len().eq(64).all()),
        "purpose": "replace unreadable iCloud placeholders without mutating the original frozen evidence",
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
