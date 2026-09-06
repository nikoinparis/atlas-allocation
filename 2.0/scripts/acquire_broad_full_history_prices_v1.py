#!/usr/bin/env python3
"""Pull full Yahoo history for the broad research universe, back to 2011.

The broad weekly panel begins 2022-12-02 in every version, because it was built
for the recent window and never extended backwards. That is why the residual
momentum sleeve -- the leg that beat its universe by 47 points in Step 224 and
carried the composite in Step 225 -- cannot be tested before 2023 at all, while
the leg that already fails in sample can be.

This pulls the whole history in one pass rather than chaining onto the existing
panel, so there is no rebasing to reconcile: the daily closes are the closes. The
overlap against the existing panel is compared on weekly returns afterwards,
which is the invariant that survives the existing panel's rebasing.

Survivorship is the obvious risk and is measured rather than assumed. Roughly a
third of this universe is Tiingo-sourced delisted names that Yahoo will not
return, and the manifest records exactly which symbols came back empty so the
gap is visible to whatever consumes this.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v3/price_source_inventory.csv"
OUTPUT_ROOT = ROOT / "data/broad_full_history_price_vintages"


def symbol_of(path: str) -> str | None:
    match = (re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", path)
             or re.search(r"/([A-Za-z0-9.\-]+)/prices\.csv\.gz$", path))
    return match.group(1).upper() if match else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2011-01-01")
    parser.add_argument("--batch", type=int, default=80)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--label", default="broad-full-history-v1")
    args = parser.parse_args()

    inventory = pd.read_csv(INVENTORY, dtype={"cik10": str})
    inventory["symbol"] = inventory.path.map(symbol_of)
    inventory = inventory.dropna(subset=["symbol"]).drop_duplicates("cik10")
    by_symbol = dict(zip(inventory.symbol, inventory.cik10))
    symbols = sorted(by_symbol)
    print(f"requesting full history from {args.start} for {len(symbols)} symbols", flush=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-{args.label}"
    (output / "histories").mkdir(parents=True, exist_ok=False)

    end = (pd.Timestamp.utcnow().tz_localize(None) + pd.Timedelta(days=1)).date().isoformat()
    returned, empty = [], []
    for offset in range(0, len(symbols), args.batch):
        chunk = symbols[offset:offset + args.batch]
        try:
            frame = yf.download(chunk, start=args.start, end=end, interval="1d", auto_adjust=False,
                                progress=False, threads=False, group_by="column")
        except Exception as error:
            print(f"  batch {offset} failed: {error}", flush=True)
            empty.extend(chunk)
            continue
        adjusted = frame["Adj Close"] if "Adj Close" in frame else pd.DataFrame()
        if isinstance(adjusted, pd.Series):
            adjusted = adjusted.to_frame(chunk[0])
        for symbol in chunk:
            series = adjusted[symbol].dropna() if symbol in adjusted else pd.Series(dtype=float)
            if series.empty:
                empty.append(symbol)
                continue
            series.rename("adjusted_close").rename_axis("date").to_csv(
                output / "histories" / f"{symbol}.csv.gz", compression="gzip")
            returned.append({"symbol": symbol, "cik10": by_symbol[symbol], "rows": int(len(series)),
                             "first": str(series.index[0].date()), "last": str(series.index[-1].date())})
        print(f"  {min(offset + args.batch, len(symbols))}/{len(symbols)}"
              f"  returned={len(returned)} empty={len(empty)}", flush=True)
        time.sleep(args.pause)

    catalogue = pd.DataFrame(returned)
    catalogue.to_csv(output / "history_catalogue.csv", index=False)
    first_years = catalogue["first"].str[:4].value_counts().sort_index().to_dict() if len(catalogue) else {}
    manifest = {
        "experiment": "broad_full_history_price_vintages",
        "vintage_id": output.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "requested_start": args.start,
        "symbols_requested": len(symbols),
        "symbols_returned": len(returned),
        "symbols_empty": len(empty),
        "return_rate": round(len(returned) / max(len(symbols), 1), 4),
        "first_observation_year_distribution": first_years,
        "empty_symbols": sorted(empty),
        "survivorship_note": ("symbols returning nothing are overwhelmingly delisted issuers Yahoo no longer "
                              "serves. They are listed in full so any panel built on this can account for "
                              "them explicitly rather than silently omitting them."),
        "provider": "Yahoo Finance via yfinance",
        "live_trading_enabled": False,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "empty_symbols"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
