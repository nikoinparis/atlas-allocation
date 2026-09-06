#!/usr/bin/env python3
"""Build a broad weekly issuer panel from 2011, and check it against the sealed one.

The existing broad panel starts 2022-12-02 and stores each issuer rebased to 1.0 at
its first observation. This builds an independent panel from raw adjusted closes
over the full history, so nothing is chained and no rebasing has to be unwound.

Because the two are built from different sources by different routes, their overlap
is a real check rather than a formality. Levels are not comparable -- one is rebased
and one is not -- so the comparison is on weekly returns, which are invariant to
rebasing. A large disagreement there would mean one of the two panels is wrong, and
that is worth knowing before anything is backtested on either.

Cleaning matches the sealed panel exactly: non-positive prices become missing, and
weekly returns outside [-0.95, 2.0] are treated as data errors rather than events.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ROOT / "data/broad_full_history_price_vintages"
SEALED = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
OUTPUT = ROOT / "data/broad_full_history_panel_v1"
RETURN_CAP, RETURN_FLOOR = 2.0, -0.95


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vintage", default="")
    args = parser.parse_args()
    vintage = Path(args.vintage) if args.vintage else sorted(VINTAGES.glob("*-broad-full-history-v1"))[-1]
    catalogue = pd.read_csv(vintage / "history_catalogue.csv", dtype={"cik10": str})
    print(f"vintage {vintage.name}: {len(catalogue)} histories", flush=True)

    series = {}
    for row in catalogue.itertuples(index=False):
        path = vintage / "histories" / f"{row.symbol}.csv.gz"
        if not path.exists():
            continue
        frame = pd.read_csv(path, index_col=0)
        frame.index = pd.to_datetime(frame.index, utc=True, errors="coerce").tz_localize(None)
        values = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
        values = values.where(values > 0)
        series[row.cik10] = values.dropna()
    print(f"parsed {len(series)} issuer histories", flush=True)

    daily = pd.DataFrame(series)
    weekly = daily.resample("W-FRI").last()
    returns = weekly.pct_change()
    # Implausible weekly moves are masked in the return series only. The level series is
    # left as reported: a level is a fact about a price, while a return outside
    # [-0.95, 2.0] is almost always a split or a data error rather than an event.
    bad = (returns > RETURN_CAP) | (returns < RETURN_FLOOR)
    adjusted = int(bad.sum().sum())
    returns = returns.mask(bad)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    weekly.rename_axis("Date").to_csv(OUTPUT / "weekly_adjusted_prices.csv.gz", compression="gzip")
    returns.rename_axis("Date").to_csv(OUTPUT / "weekly_returns.csv.gz", compression="gzip")

    sealed = pd.read_csv(SEALED, index_col=0)
    sealed.index = pd.to_datetime(sealed.index)
    sealed_returns = sealed.pct_change()
    shared_dates = returns.index.intersection(sealed_returns.index)
    shared_ciks = [c for c in returns.columns if c in sealed_returns.columns]
    a = returns.loc[shared_dates, shared_ciks]
    b = sealed_returns.loc[shared_dates, shared_ciks]
    gap = (a - b).abs()
    compared = int(gap.notna().sum().sum())
    reconciliation = {
        "basis": "weekly simple returns, invariant to the sealed panel's rebasing",
        "overlap_weeks": int(len(shared_dates)),
        "shared_issuers": int(len(shared_ciks)),
        "compared_cells": compared,
        "median_absolute_gap": float(np.nanmedian(gap.values)) if compared else None,
        "cells_over_10bps": int((gap > 0.001).sum().sum()),
        "cells_over_100bps": int((gap > 0.01).sum().sum()),
        "share_over_100bps": round(float((gap > 0.01).sum().sum()) / max(compared, 1), 6),
    }

    manifest = {
        "experiment": "broad_full_history_panel_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_vintage": vintage.name,
        "issuers": int(weekly.shape[1]),
        "weeks": int(weekly.shape[0]),
        "first_week": str(weekly.index[0].date()),
        "last_week": str(weekly.index[-1].date()),
        "cleaning_rules": {"non_positive_prices": "set to missing",
                           "weekly_return_cap": RETURN_CAP, "weekly_return_floor": RETURN_FLOOR,
                           "return_observations_masked": adjusted},
        "coverage_by_year": {str(y): int(weekly.loc[str(y)].notna().any().sum())
                             for y in range(weekly.index[0].year, weekly.index[-1].year + 1)},
        "reconciliation_against_sealed_panel": reconciliation,
        "artifact_sha256": {n: sha256(OUTPUT / n) for n in
                            ["weekly_adjusted_prices.csv.gz", "weekly_returns.csv.gz"]},
        "live_trading_enabled": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in manifest.items() if k != "artifact_sha256"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
