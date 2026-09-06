#!/usr/bin/env python3
"""Repair the price panel at the source, rather than filtering returns at use time.

Step 239 measured the damage: one infinite weekly return and 211 above +100%,
sitting only in the benchmark side of every comparison this project makes.  The
temptation is to drop outlier returns wherever they appear.  That is wrong twice
over -- it hides the cause, and it silently changes the meaning of any pinned
artifact built on top.  The defect is in the prices, so it is fixed in the
prices, and the result is a new panel rather than an edit to an old one.

Three distinct defects, three distinct repairs:

  non-positive prices    A price of zero is not a price.  It produced the single
                         infinite return in both panels.  Set to missing.

  sub-investable prices  Below a dollar, a quoted return is mostly tick
                         quantization: 0.0003 to 0.0043 reads as +1,333% and is
                         not a return anybody could have earned.  These names are
                         also not institutionally investable.  Set to missing for
                         the weeks they are below the floor, which removes them
                         from the universe rather than inventing a return.

  interleaved identities A genuine split moves a price once.  A column that jumps
                         five-fold two or more times is two securities' prices in
                         one column -- CIK 0001655210 oscillates between $0.55 and
                         $17 for months.  The whole column is quarantined, because
                         there is no way to know which weeks belong to which
                         security and guessing would fabricate history.

Nothing here is authorised to trade.  No pinned artifact is modified: this writes
a new cleaned price file and leaves every existing panel exactly as it was.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

JUMP_RATIO = 5.0          # a weekly move this large is a corporate action, not a return
MAX_LEGITIMATE_JUMPS = 1  # one is a split; two or more is a corrupted series


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(prices: pd.DataFrame, floor: float) -> tuple[pd.DataFrame, dict[str, object]]:
    prices = prices.apply(pd.to_numeric, errors="coerce")
    report: dict[str, object] = {"input_cells": int(prices.notna().sum().sum()),
                                 "input_issuers": int(prices.shape[1])}

    non_positive = (prices <= 0)
    report["non_positive_cells_removed"] = int(non_positive.sum().sum())
    report["non_positive_issuers"] = sorted(prices.columns[non_positive.any()].astype(str))
    prices = prices.where(~non_positive)

    # Quarantine FIRST, on the prices as they arrived. Applying the floor before
    # this hides the evidence: it deletes the low side of an oscillating column,
    # the jumps vanish, and a column that is two securities interleaved sails
    # through looking clean. The first version of this script did exactly that
    # and quarantined nothing.
    log_prices = np.log(prices.where(prices > 0))
    jumps = (log_prices.diff().abs() > np.log(JUMP_RATIO)).sum()
    quarantined = sorted(jumps.index[jumps > MAX_LEGITIMATE_JUMPS].astype(str))
    report["jump_ratio"] = JUMP_RATIO
    report["max_legitimate_jumps"] = MAX_LEGITIMATE_JUMPS
    report["quarantined_issuers"] = quarantined
    report["quarantined_count"] = len(quarantined)
    report["single_jump_issuers_kept"] = sorted(jumps.index[jumps == 1].astype(str))
    prices = prices.drop(columns=quarantined)

    below = prices < floor
    report["price_floor"] = floor
    report["sub_floor_cells_removed"] = int(below.sum().sum())
    report["sub_floor_issuers_touched"] = int(below.any().sum())
    prices = prices.where(~below)

    report["output_cells"] = int(prices.notna().sum().sum())
    report["output_issuers"] = int(prices.shape[1])
    report["cells_removed_total"] = report["input_cells"] - report["output_cells"]
    report["share_of_cells_removed"] = round(
        report["cells_removed_total"] / max(1, report["input_cells"]), 6)
    return prices, report


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    returns = prices / prices.shift(1) - 1.0
    return returns.replace([np.inf, -np.inf], np.nan)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", default="data/sec_broad_panel_inputs_v3/weekly_adjusted_prices.csv.gz")
    parser.add_argument("--floor", type=float, default=1.00,
                        help="minimum investable weekly price; below this a name leaves the universe")
    parser.add_argument("--output", default="data/clean_corporate_action_prices_v1")
    args = parser.parse_args()

    source = ROOT / args.prices
    prices = pd.read_csv(source, index_col=0, parse_dates=True)
    cleaned, report = clean(prices, args.floor)

    before = weekly_returns(prices.apply(pd.to_numeric, errors="coerce"))
    after = weekly_returns(cleaned)
    for label, frame in (("before", before), ("after", after)):
        values = frame.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        report[f"{label}__infinite_returns"] = int(np.isinf(values).sum())
        report[f"{label}__returns_above_100pct"] = int((np.abs(finite) > 1.0).sum())
        report[f"{label}__worst_weekly_return"] = float(finite.max()) if finite.size else None
        equal_weight = frame.mean(axis=1, skipna=True)
        total = float((1.0 + equal_weight.fillna(0.0)).prod())
        years = len(equal_weight) / 52.0
        report[f"{label}__equal_weight_cagr"] = float(total ** (1.0 / years) - 1.0) if years else None
        recent = equal_weight.tail(52)
        report[f"{label}__equal_weight_recent_52w"] = float((1.0 + recent.fillna(0.0)).prod() - 1.0)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    price_path = out / "weekly_adjusted_prices_clean.csv.gz"
    cleaned.to_csv(price_path, compression="gzip")
    after.to_csv(out / "weekly_returns_clean.csv.gz", compression="gzip")

    manifest = {
        "experiment": "corporate_action_clean_prices_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_prices": args.prices,
        "source_sha256": sha256(source),
        "repairs": report,
        "artifact_sha256": {p.name: sha256(p) for p in sorted(out.glob("*.csv.gz"))},
        "modifies_existing_panels": False,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    printable = {k: v for k, v in report.items()
                 if not isinstance(v, list) or len(v) <= 12}
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
