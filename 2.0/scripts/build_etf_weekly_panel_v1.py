#!/usr/bin/env python3
"""Assemble a flat weekly ETF price panel from the vintage store.

Step 278 could not verify two dashboard strategies and could not touch a third,
because their books mix SEC equities with ETFs and every SEC panel here is keyed
by cik10 while ETF prices live only as daily rows inside dated vintage bundles.
That is a tooling gap, not a research finding, and it is why the dashboard's
headline strategy repriced at +0.493 with 45.6% of its weight unpriceable.

This flattens the vintage bundles into one weekly panel shaped like the SEC ones:
a Friday-indexed frame of adjusted closes, columns named by ticker.

**This panel is not point-in-time and must not be used as if it were.** The
bundles' own manifests declare `point_in_time_prices: false`,
`corporate_actions: false` and `vintage_revisions: false`. Every row is the
provider's *current* view of history as of the day it was pulled, so a split or
a restatement is reflected all the way back. It is fit for repricing a book we
already hold to check arithmetic, which is what Step 278 needed. It is not fit
for deciding what to hold, and any strategy work on it inherits a survivorship
and revision problem this project spent Steps 219-240 removing from the equity
panels.

Later vintages win on overlapping dates, and the manifest hash of every file
read is recorded so the panel can be traced back to the bundles it came from.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VINTAGES = ROOT / "data/vintages"
OUTPUT = ROOT / "data/etf_weekly_panel_v1"
EVIDENCE = ROOT / "evidence/etf_weekly_panel_v1"
KIND = "free_current_etf_research_bundle"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    bundles = []
    for directory in sorted(VINTAGES.iterdir()):
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("dataset_kind") != KIND:
            continue
        prices = directory / "payload/prices.csv"
        if not prices.is_file():
            continue
        declared = manifest.get("files", {}).get("prices.csv", {}).get("sha256")
        actual = file_sha256(prices)
        if declared and declared != actual:
            raise SystemExit(f"{directory.name}: prices.csv does not match its manifest hash")
        bundles.append({
            "directory": directory.name,
            "observed_at_utc": str(manifest.get("observed_at_utc", "")),
            "prices": prices,
            "prices_sha256": actual,
            "symbols": int(manifest.get("coverage", {}).get("symbols", 0)),
            "latest_observation_date": str(manifest.get("coverage", {}).get("latest_observation_date", "")),
            "claims": manifest.get("claims", {}),
        })
    if not bundles:
        raise SystemExit(f"no {KIND} bundles found under {VINTAGES}")

    bundles.sort(key=lambda b: b["observed_at_utc"])
    frames = []
    for bundle in bundles:
        frame = pd.read_csv(bundle["prices"],
                            usecols=["observation_date", "ticker", "adjusted_close"])
        frame["observation_date"] = pd.to_datetime(frame.observation_date, utc=True, errors="coerce")
        frame["adjusted_close"] = pd.to_numeric(frame.adjusted_close, errors="coerce")
        frame = frame.dropna(subset=["observation_date", "ticker", "adjusted_close"])
        frame["vintage"] = bundle["observed_at_utc"]
        frames.append(frame)
    daily = pd.concat(frames, ignore_index=True)

    # Later vintages win where two bundles cover the same day and ticker.
    daily = daily.sort_values("vintage").drop_duplicates(
        subset=["observation_date", "ticker"], keep="last")
    wide = daily.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()

    # Friday-stamped weekly closes, matching how every SEC panel here is indexed:
    # the last observation on or before each Friday, not the mean of the week.
    weekly = wide.resample("W-FRI").last()
    weekly = weekly.dropna(how="all")
    weekly.index.name = "Date"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / "weekly_adjusted_prices.csv.gz"
    weekly.to_csv(target, compression="gzip")

    coverage = weekly.notna().sum().sort_values()
    result = {
        "bundles_read": [
            {k: b[k] for k in ("directory", "observed_at_utc", "prices_sha256",
                               "symbols", "latest_observation_date")}
            for b in bundles
        ],
        "symbols": int(weekly.shape[1]),
        "weeks": int(weekly.shape[0]),
        "first_week": str(weekly.index.min().date()),
        "last_week": str(weekly.index.max().date()),
        "thinnest_symbols": {str(k): int(v) for k, v in coverage.head(5).items()},
        "output": str(target.relative_to(ROOT)),
        "output_sha256": file_sha256(target),
        "point_in_time": False,
        "survivorship_safe": False,
        "why_not": ("The source bundles declare point_in_time_prices false, corporate_actions "
                    "false and vintage_revisions false. Every row is the provider's current "
                    "view of history. Fit for repricing a book already chosen; not fit for "
                    "choosing one."),
        "declared_use": "verification of dashboard strategy arithmetic only (Step 278)",
    }
    (EVIDENCE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"{weekly.shape[1]} symbols x {weekly.shape[0]} weeks  "
          f"{result['first_week']} -> {result['last_week']}")
    print(f"bundles read: {len(bundles)}")
    print(f"thinnest coverage: {result['thinnest_symbols']}")
    print(f"written: {result['output']}")
    print("NOT point-in-time; verification use only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
