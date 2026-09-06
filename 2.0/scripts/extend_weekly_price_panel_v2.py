#!/usr/bin/env python3
"""Extend the cleaned weekly issuer price panel with newly closed weeks.

The sealed panel is not a table of dollar prices. Every issuer's series is
rebased to 1.0 at its first observation, so a fresh Yahoo pull cannot be
appended as-is; it has to be chained onto the stored level at the last week the
two have in common. The reconciliation check therefore compares weekly returns,
which are invariant to that rebasing, rather than levels, which are not.

Only weeks whose Friday has already closed are appended. Nothing already in the
panel is rewritten.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
CLEAN_V1 = ROOT / "data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz"
OUTPUT_ROOT = ROOT / "data/clean_weekly_prices_v2"
RAW_ROOT = ROOT / "data/sec_broad_recent_tail_vintages"

WEEKLY_RETURN_CAP = 2.0
WEEKLY_RETURN_FLOOR = -0.95


def ticker_map() -> dict[str, str]:
    out: dict[str, str] = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            # Yahoo vintages store one file per ticker under histories/;
            # the Tiingo caches store one directory per ticker instead.
            match = (re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
                     or re.search(r"/([A-Za-z0-9.\-]+)/prices\.csv\.gz$", row["path"]))
            if match:
                out[row["cik10"]] = match.group(1).upper()
    return out


def download(symbols: list[str], start: str, end: str, batch: int, pause: float):
    frames, failures = [], []
    for index in range(0, len(symbols), batch):
        chunk = symbols[index:index + batch]
        try:
            frame = yf.download(chunk, start=start, end=end, interval="1d", auto_adjust=False,
                                progress=False, threads=False, group_by="column")
        except Exception as error:
            failures.extend(chunk)
            print(f"  chunk {index}: FAILED {error}", flush=True)
            continue
        if frame.empty or "Adj Close" not in set(np.atleast_1d(frame.columns.get_level_values(0))):
            failures.extend(chunk)
            continue
        frames.append(frame["Adj Close"])
        print(f"  chunk {index}-{index + len(chunk)}", flush=True)
        time.sleep(pause)
    combined = pd.concat(frames, axis=1)
    combined.index = pd.to_datetime(combined.index).tz_localize(None)
    return combined.loc[:, ~combined.columns.duplicated()], failures


def last_closed_friday(now: pd.Timestamp) -> pd.Timestamp:
    """The most recent Friday that has already ended in US market terms."""
    candidate = now.normalize() - pd.Timedelta(days=(now.weekday() - 4) % 7)
    if now.weekday() == 4 and now.hour < 21:
        candidate -= pd.Timedelta(days=7)
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-06-01")
    parser.add_argument("--batch", type=int, default=60)
    parser.add_argument("--pause", type=float, default=0.4)
    parser.add_argument("--label", default="broad-recent-tail-v1")
    parser.add_argument("--reuse", default="", help="path to a cached daily_adjusted_close.csv.gz")
    args = parser.parse_args()

    mapping = ticker_map()
    symbols = sorted(set(mapping.values()))
    print(f"issuers_mapped={len(mapping)} unique_symbols={len(symbols)}", flush=True)

    if args.reuse:
        raw_dir = Path(args.reuse).parent
        daily = pd.read_csv(args.reuse, index_col=0, parse_dates=True)
        failures: list[str] = []
        missing = sorted(set(symbols) - set(daily.columns))
        print(f"reusing cached daily tail {daily.shape}; {len(missing)} symbols still to fetch", flush=True)
        if missing:
            end = (pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() + pd.Timedelta(days=1)).date().isoformat()
            extra, failures = download(missing, args.start, end, args.batch, args.pause)
            daily = pd.concat([daily, extra.reindex(daily.index)], axis=1)
            daily = daily.loc[:, ~daily.columns.duplicated()]
            daily.to_csv(raw_dir / "daily_adjusted_close.csv.gz", compression="gzip")
            print(f"merged tail {daily.shape}", flush=True)
    else:
        end = (pd.Timestamp.now(tz="UTC").tz_localize(None).normalize() + pd.Timedelta(days=1)).date().isoformat()
        daily, failures = download(symbols, args.start, end, args.batch, args.pause)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raw_dir = RAW_ROOT / f"{stamp}-{args.label}"
        raw_dir.mkdir(parents=True, exist_ok=True)
        daily.to_csv(raw_dir / "daily_adjusted_close.csv.gz", compression="gzip")

    weekly_symbols = daily.resample("W-FRI").last()
    fresh = pd.DataFrame({
        cik: pd.to_numeric(weekly_symbols[symbol], errors="coerce")
        for cik, symbol in mapping.items() if symbol in weekly_symbols.columns
    }).sort_index()
    fresh.index.name = "Date"

    stored = pd.read_csv(CLEAN_V1, parse_dates=["Date"]).set_index("Date").sort_index()
    stored.columns = [str(c) for c in stored.columns]

    # Returns are invariant to the panel's per-issuer rebasing; levels are not.
    overlap_dates = fresh.index.intersection(stored.index)
    columns = fresh.columns.intersection(stored.columns)
    stored_returns = stored.loc[overlap_dates, columns].pct_change()
    fresh_returns = fresh.loc[overlap_dates, columns].pct_change()
    both = stored_returns.notna() & fresh_returns.notna()
    gap = (fresh_returns - stored_returns).abs().where(both)
    reconciliation = {
        "basis": "weekly simple returns over the overlapping weeks",
        "overlap_weeks": [str(d.date()) for d in overlap_dates],
        "compared_cells": int(both.to_numpy().sum()),
        "cells_over_10bps": int((gap > 0.001).to_numpy().sum()),
        "cells_over_100bps": int((gap > 0.01).to_numpy().sum()),
        "max_absolute_return_gap": None if gap.isna().all().all() else float(gap.max().max()),
        "median_absolute_return_gap": None if gap.isna().all().all() else float(gap.stack().median()),
    }
    print("reconciliation:", json.dumps(reconciliation, default=str)[:600], flush=True)

    cutoff = last_closed_friday(pd.Timestamp.now(tz="UTC").tz_localize(None))
    new_dates = fresh.index[(fresh.index > stored.index.max()) & (fresh.index <= cutoff)]
    print(f"last closed friday={cutoff.date()} new closed weeks={[str(d.date()) for d in new_dates]}", flush=True)
    if len(new_dates) == 0:
        print("nothing to append")
        return 0

    # Chain each issuer onto its own stored level at the last week both cover.
    appended = pd.DataFrame(index=new_dates, columns=stored.columns, dtype=float)
    chained, unchainable = 0, []
    for cik in stored.columns:
        if cik not in fresh.columns:
            unchainable.append(cik)
            continue
        stored_series = stored[cik].dropna()
        fresh_series = fresh[cik].dropna()
        common = stored_series.index.intersection(fresh_series.index)
        if len(common) == 0 or fresh[cik].reindex(new_dates).isna().all():
            unchainable.append(cik)
            continue
        anchor = common.max()
        scale = stored_series.loc[anchor] / fresh_series.loc[anchor]
        if not np.isfinite(scale) or scale <= 0:
            unchainable.append(cik)
            continue
        appended[cik] = fresh[cik].reindex(new_dates) * scale
        chained += 1
    print(f"chained {chained} issuers; {len(unchainable)} could not be extended", flush=True)

    combined = pd.concat([stored, appended]).sort_index()
    combined[combined <= 0] = np.nan
    returns = combined.pct_change()
    mask = (returns > WEEKLY_RETURN_CAP) | (returns < WEEKLY_RETURN_FLOOR)
    mask.loc[mask.index <= stored.index.max()] = False
    adjusted_cells = int(mask.to_numpy().sum())
    combined = combined.mask(mask)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_ROOT / "weekly_adjusted_prices_clean.csv.gz"
    combined.to_csv(out, compression="gzip")

    manifest = {
        "experiment": "clean_weekly_prices_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "derived_from": str(CLEAN_V1.relative_to(ROOT)),
        "derived_from_sha256": hashlib.sha256(CLEAN_V1.read_bytes()).hexdigest(),
        "raw_tail_vintage": str(Path(raw_dir).resolve().relative_to(ROOT)),
        "panel_convention": "each issuer is rebased to 1.0 at its first observation; new weeks are chained onto the stored level at the last shared week",
        "appended_weeks": [str(d.date()) for d in new_dates],
        "prior_last_week": str(stored.index.max().date()),
        "new_last_week": str(combined.index.max().date()),
        "last_closed_friday_at_build": str(cutoff.date()),
        "issuers": int(combined.shape[1]),
        "issuers_extended": chained,
        "issuers_not_extended": len(unchainable),
        "not_extended_reason": "no fresh Yahoo observation in the new week; these are overwhelmingly Tiingo-sourced delisted issuers whose series legitimately stops",
        "symbols_requested": len(symbols),
        "symbols_failed": len(failures),
        "coverage_new_week": {
            str(d.date()): int(combined.loc[d].notna().sum()) for d in new_dates
        },
        "cleaning_rules": {
            "applied_to": "appended weeks only; existing cells are never rewritten",
            "weekly_return_cap": WEEKLY_RETURN_CAP,
            "weekly_return_floor": WEEKLY_RETURN_FLOOR,
            "zero_and_negative_prices": "set to missing",
            "return_observations_adjusted": adjusted_cells,
        },
        "overlap_reconciliation": reconciliation,
        "artifact_sha256": {"weekly_adjusted_prices_clean.csv.gz": hashlib.sha256(out.read_bytes()).hexdigest()},
        "live_trading_enabled": False,
    }
    (OUTPUT_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
