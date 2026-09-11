#!/usr/bin/env python3
"""Acquire US daily volume so VWAP is computable on the wide panel.

The weekly price panel carries prices without volume, which is the only reason
VWAP had never been tested on US data in 307 steps. This fetches daily close and
volume for the panel's issuers, mapped through SEC's own company_tickers.json at
98% coverage.

Declared in config/vwap_wide_universe_registry_v1.json before it ran.

Two things this cannot fix and records instead of hiding. SEC's map is of CURRENT
tickers, so an issuer that delisted or changed symbol gets no volume and the
tested subset tilts toward survivors; the overlap is measured and written to the
result rather than assumed small. And Yahoo's daily volume is not always split-
consistent with its adjusted close, so the build that consumes this must check
rather than trust.
"""

from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/us_daily_volume_v1"
EVIDENCE = ROOT / "evidence/vwap_wide_universe_v1"
PANEL = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
TICKER_MAP = ROOT / "data/us_daily_volume_v1/cik_ticker_map.csv"
BATCH = 120
START, END = "2011-01-01", "2026-09-12"


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if not TICKER_MAP.is_file():
        print(f"missing {TICKER_MAP}; write the cik10,ticker map there first")
        return 1
    mapping = pd.read_csv(TICKER_MAP, dtype=str).dropna()
    panel = pd.read_csv(PANEL, nrows=1)
    names = {str(c) for c in panel.columns[1:]}
    mapping = mapping[mapping.cik10.isin(names)].drop_duplicates("cik10")
    tickers = sorted(set(mapping.ticker))
    print(f"panel issuers: {len(names)}   mapped tickers: {len(tickers)}")

    close_path, volume_path = OUTPUT / "daily_close.csv.gz", OUTPUT / "daily_volume.csv.gz"
    closes, volumes, failed = [], [], 0
    for i in range(0, len(tickers), BATCH):
        chunk = tickers[i:i + BATCH]
        try:
            data = yf.download(chunk, start=START, end=END, interval="1d",
                               progress=False, auto_adjust=False, threads=True)
        except Exception:                            # noqa: BLE001
            failed += len(chunk)
            continue
        if isinstance(data.columns, pd.MultiIndex):
            c = data["Close"] if "Close" in data.columns.get_level_values(0) else None
            v = data["Volume"] if "Volume" in data.columns.get_level_values(0) else None
        else:
            c = data[["Close"]].rename(columns={"Close": chunk[0]})
            v = data[["Volume"]].rename(columns={"Volume": chunk[0]})
        if c is not None:
            closes.append(c)
        if v is not None:
            volumes.append(v)
        print(f"  {i + len(chunk)}/{len(tickers)}", flush=True)
        time.sleep(1.0)

    close = pd.concat(closes, axis=1) if closes else pd.DataFrame()
    volume = pd.concat(volumes, axis=1) if volumes else pd.DataFrame()
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]

    # Rename to cik10 so everything downstream joins on the project's own key.
    back = dict(zip(mapping.ticker, mapping.cik10))
    close.columns = [back.get(c, c) for c in close.columns]
    volume.columns = [back.get(c, c) for c in volume.columns]
    close.to_csv(close_path, compression="gzip")
    volume.to_csv(volume_path, compression="gzip")

    usable = [c for c in volume.columns if volume[c].notna().sum() > 500]
    result = {
        "panel_issuers": len(names), "tickers_requested": len(tickers),
        "columns_returned": int(volume.shape[1]),
        "issuers_with_over_500_volume_days": len(usable),
        "survivorship_overlap": len(usable) / len(names),
        "days": int(volume.shape[0]),
        "first_day": str(volume.index.min())[:10], "last_day": str(volume.index.max())[:10],
        "batches_failed": failed,
        "caveat": ("SEC's map is of CURRENT tickers, so delisted or renamed issuers get no "
                   "volume and the tested subset tilts toward survivors"),
        "live_trading_enabled": False,
    }
    (EVIDENCE / "volume_acquisition.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
