#!/usr/bin/env python3
"""A32 input: daily adjusted high, low and close for every price-panel symbol (Yahoo via yfinance), for
Abdi-Ranaldo (2017) spread estimates. Stored as gzip CSVs with a sha256 manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
OUTPUT = ROOT / "data/daily_ohlc_v1"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False).drop_duplicates("cik10")
    symbols = list(cat.symbol)
    frames = {"High": [], "Low": [], "Close": []}
    for i in range(0, len(symbols), 100):
        chunk = symbols[i:i + 100]
        d = yf.download(chunk, start="2011-01-01", end="2026-10-17", auto_adjust=True, progress=False, threads=True)
        for field in frames:
            frames[field].append(d[field])
        print(f"  {min(i + 100, len(symbols))}/{len(symbols)}", flush=True)
    sym_to_cik = dict(zip(cat.symbol, cat.cik10))
    manifest = {}
    for field, parts in frames.items():
        df = pd.concat(parts, axis=1)
        df.columns = [sym_to_cik.get(c, c) for c in df.columns]
        path = OUTPUT / f"daily_{field.lower()}.csv.gz"
        df.to_csv(path)
        manifest[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUTPUT / "manifest.json").write_text(json.dumps({"symbols": len(symbols), "sha256": manifest}, indent=2) + "\n")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
