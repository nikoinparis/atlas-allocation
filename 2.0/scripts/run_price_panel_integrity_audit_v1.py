#!/usr/bin/env python3
"""Audit the sealed weekly price panel, and emit a cleaned derivative.

Step 193 found 52 zero prices and an infinite weekly return sitting inside the
panel that every strategy and every backtest in this project is built on. This
enumerates the defects, measures how far they reach, and writes a cleaned copy.

The sealed panel is never modified. It is hashed in the panel-inputs manifest,
which chains to a file the forward protocol pins, so a cleaned derivative is the
only safe form this correction can take.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEALED = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/price_panel_integrity_audit_v1"
CLEAN = ROOT / "data/clean_weekly_prices_v1"

CAP_WEEKLY_RETURN = 2.0     # +200% in one week
FLOOR_WEEKLY_RETURN = -0.95 # -95% in one week
STALE_RUN_WEEKS = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    prices = pd.read_csv(SEALED, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    returns = prices.pct_change()

    findings = {}

    zero_mask = (prices == 0.0)
    findings["zero_prices"] = {
        "count": int(zero_mask.to_numpy().sum()),
        "issuers_affected": int(zero_mask.any().sum()),
        "note": "A zero price is a data error, not a trade. It makes the next return infinite.",
    }
    negative = (prices < 0.0)
    findings["negative_prices"] = {"count": int(negative.to_numpy().sum())}

    infinite = np.isinf(returns.to_numpy())
    findings["infinite_returns"] = {
        "count": int(infinite.sum()),
        "note": "Every one is produced by a zero price in the prior week.",
    }

    finite = returns.replace([np.inf, -np.inf], np.nan)
    findings["extreme_returns"] = {
        "above_plus_200pct": int((finite > CAP_WEEKLY_RETURN).to_numpy().sum()),
        "above_plus_1000pct": int((finite > 10.0).to_numpy().sum()),
        "below_minus_95pct": int((finite < FLOOR_WEEKLY_RETURN).to_numpy().sum()),
        "largest_weekly_gain": float(finite.max().max()),
        "largest_weekly_loss": float(finite.min().min()),
    }

    # stale runs: identical price for many consecutive weeks means no real trading
    stale_total, stale_issuers = 0, 0
    for column in prices.columns:
        series = prices[column].dropna()
        if len(series) < STALE_RUN_WEEKS:
            continue
        same = series.diff().eq(0.0)
        run, longest = 0, 0
        for flag in same:
            run = run + 1 if flag else 0
            longest = max(longest, run)
        if longest >= STALE_RUN_WEEKS:
            stale_issuers += 1
            stale_total += longest
    findings["stale_price_runs"] = {
        "issuers_with_run_of_8_or_more_identical_weeks": stale_issuers,
        "note": "A frozen price is usually a delisted or untraded name still being carried in the panel.",
    }

    # resurrections: a name that goes missing and comes back
    present = prices.notna()
    resurrected = 0
    for column in prices.columns:
        p = present[column].to_numpy()
        idx = np.flatnonzero(p)
        if len(idx) > 1 and (np.diff(idx) > 1).any():
            resurrected += 1
    findings["gapped_coverage"] = {
        "issuers_with_internal_gaps": int(resurrected),
        "note": "Prices that disappear and return. Legitimate for halted names, but a source of fake returns across the gap.",
    }

    findings["coverage"] = {
        "weeks": int(len(prices)),
        "issuers": int(prices.shape[1]),
        "median_issuers_priced_per_week": int(present.sum(axis=1).median()),
        "start": str(prices.index.min().date()),
        "end": str(prices.index.max().date()),
    }

    # ---- cleaned derivative
    clean_prices = prices.replace(0.0, np.nan).mask(prices < 0.0)
    clean_returns = clean_prices.pct_change().replace([np.inf, -np.inf], np.nan)
    capped = clean_returns.clip(lower=FLOOR_WEEKLY_RETURN, upper=CAP_WEEKLY_RETURN)
    # NaN != NaN is True in pandas, so compare only where both sides are present
    both = capped.notna() & clean_returns.notna()
    adjustments = int(((capped != clean_returns) & both).to_numpy().sum())
    rebuilt = (1.0 + capped.fillna(0.0)).cumprod()
    rebuilt = rebuilt.where(clean_prices.notna())

    CLEAN.mkdir(parents=True, exist_ok=True)
    clean_path = CLEAN / "weekly_adjusted_prices_clean.csv.gz"
    rebuilt.to_csv(clean_path, compression="gzip")

    manifest = {
        "experiment": "clean_weekly_prices_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "derived_from": "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz",
        "source_sha256": sha256(SEALED),
        "source_unmodified": True,
        "cleaning_rules": {
            "zero_and_negative_prices": "set to missing",
            "weekly_return_cap": CAP_WEEKLY_RETURN,
            "weekly_return_floor": FLOOR_WEEKLY_RETURN,
            "return_observations_adjusted": adjustments,
        },
        "artifact_sha256": {"weekly_adjusted_prices_clean.csv.gz": sha256(clean_path)},
        "note": ("The sealed panel is hashed in the panel-inputs manifest, which chains to a file the "
                 "forward protocol pins. It is therefore never edited; this is a derivative for future work."),
        "live_trading_enabled": False,
    }
    (CLEAN / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": "price-panel-integrity-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sealed_source_sha256": sha256(SEALED),
        "sealed_source_modified": False,
        "findings": findings,
        "cleaned_output": str(clean_path.relative_to(ROOT)),
        "return_observations_adjusted": adjustments,
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"panel: {findings['coverage']['issuers']} issuers x {findings['coverage']['weeks']} weeks "
          f"({findings['coverage']['start']} to {findings['coverage']['end']})\n")
    print(f"  zero prices                  {findings['zero_prices']['count']:>6}  across {findings['zero_prices']['issuers_affected']} issuers")
    print(f"  negative prices              {findings['negative_prices']['count']:>6}")
    print(f"  infinite returns             {findings['infinite_returns']['count']:>6}")
    print(f"  weekly returns > +200%       {findings['extreme_returns']['above_plus_200pct']:>6}")
    print(f"  weekly returns > +1000%      {findings['extreme_returns']['above_plus_1000pct']:>6}")
    print(f"  weekly returns < -95%        {findings['extreme_returns']['below_minus_95pct']:>6}")
    print(f"  largest single week          {findings['extreme_returns']['largest_weekly_gain']:>6,.0f}x")
    print(f"  issuers with 8+ stale weeks  {findings['stale_price_runs']['issuers_with_run_of_8_or_more_identical_weeks']:>6}")
    print(f"  issuers with coverage gaps   {findings['gapped_coverage']['issuers_with_internal_gaps']:>6}")
    print(f"\n  return observations adjusted in the cleaned copy: {adjustments}")
    print(f"  sealed source left untouched: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
