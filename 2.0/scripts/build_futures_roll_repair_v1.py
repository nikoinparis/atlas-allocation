#!/usr/bin/env python3
"""Repair roll discontinuities in unadjusted front-month futures series.

Step 248 could not tell whether futures trend's significantly negative
short-horizon IC was mean reversion or an artifact of rolling through contango.
This is the repair that separates them, and the point of the exercise is that it
must be chosen without looking at the answer it is meant to inform.

The problem: Yahoo's `=F` symbols are front-month continuous and unadjusted, so
the price jumps from the expiring contract to the next one and that jump enters
as a return. Without contract-level data the exact roll dates are unknowable, so
the roll cannot be adjusted away; it can only be detected and excluded.

The method: a roll gap is a discontinuity in an otherwise continuous series, so
flag weeks whose return exceeds k robust standard deviations of that instrument's
own recent history and set them to missing. Missing, not zero -- a fabricated flat
week is the mistake Step 236 refused to make on the equity side.

The robust scale matters. A plain standard deviation is inflated by the very
outliers being detected, so a 2,938% week raises the threshold enough to hide
itself. This uses the median absolute deviation over a trailing window, which
outliers cannot move.

**k is chosen on a golden master, not on the outcome.** Nine futures have an ETF
proxy tracking the same underlying -- ES/SPY, GC/GLD, CL/USO and so on -- and a
good repair must raise the correlation between the future and its proxy. The
sweep is scored on that and on nothing else. The IC measurement this feeds is not
consulted.

Nothing here is authorised to trade, and no existing panel is modified.
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

FUTURES = "evidence/futures_data_scoping_v1/probe_prices.csv.gz"
ETF = "data/derived/20260808T212827Z-de103c2e063d6c4a/weekly_prices.csv"

# Established broken in Step 247: a +903.8% day and 179% annualised volatility is
# a contract or quotation change, not a market, and no threshold repairs that.
EXCLUDE = ["6J=F"]

PROXIES = {"ES=F": "SPY", "NQ=F": "QQQ", "RTY=F": "IWM", "ZB=F": "TLT", "ZN=F": "IEF",
           "GC=F": "GLD", "SI=F": "SLV", "CL=F": "USO", "ZC=F": "DBA"}

ROBUST_WINDOW_WEEKS = 104
MAD_TO_SIGMA = 1.4826


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    weekly = prices.resample("W-FRI").last()
    return (weekly / weekly.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def robust_sigma(returns: pd.DataFrame) -> pd.DataFrame:
    """Trailing MAD-based scale. Outliers cannot inflate a median."""
    median = returns.rolling(ROBUST_WINDOW_WEEKS, min_periods=26).median()
    deviation = (returns - median).abs()
    return deviation.rolling(ROBUST_WINDOW_WEEKS, min_periods=26).median() * MAD_TO_SIGMA


def repair(returns: pd.DataFrame, k: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    sigma = robust_sigma(returns)
    median = returns.rolling(ROBUST_WINDOW_WEEKS, min_periods=26).median()
    flagged = (returns - median).abs() > (k * sigma)
    flagged = flagged & sigma.notna() & returns.notna()
    return returns.where(~flagged), flagged


def proxy_agreement(returns: pd.DataFrame, etf_returns: pd.DataFrame) -> dict[str, float]:
    """The golden master: does the repaired future track the thing it should?"""
    scores = {}
    for future, proxy in PROXIES.items():
        if future not in returns.columns or proxy not in etf_returns.columns:
            continue
        joined = pd.concat([returns[future].rename("f"), etf_returns[proxy].rename("e")],
                           axis=1).dropna().loc["2005-01-01":]
        if len(joined) < 100:
            continue
        scores[future] = float(joined.f.corr(joined.e))
    return scores


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k-sweep", default="4,6,8,10")
    parser.add_argument("--output", default="data/futures_roll_repaired_v1")
    args = parser.parse_args()

    prices = pd.read_csv(ROOT / FUTURES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices = prices.drop(columns=[c for c in EXCLUDE if c in prices.columns])
    returns = weekly_returns(prices).loc["2005-01-01":]

    etf_prices = pd.read_csv(ROOT / ETF, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    etf_returns = weekly_returns(etf_prices)

    baseline = proxy_agreement(returns, etf_returns)
    sweep = []
    for k in [float(v) for v in args.k_sweep.split(",")]:
        repaired, flagged = repair(returns, k)
        scores = proxy_agreement(repaired, etf_returns)
        common = sorted(set(baseline) & set(scores))
        sweep.append({
            "k": k,
            "cells_flagged": int(flagged.sum().sum()),
            "share_of_cells_flagged": float(flagged.sum().sum() / returns.notna().sum().sum()),
            "instruments_touched": int((flagged.sum() > 0).sum()),
            "worst_surviving_weekly_return": float(np.nanmax(np.abs(repaired.to_numpy()))),
            "mean_proxy_correlation": float(np.mean([scores[c] for c in common])),
            "mean_proxy_improvement": float(np.mean([scores[c] - baseline[c] for c in common])),
            "proxies_improved": int(sum(1 for c in common if scores[c] > baseline[c])),
            "proxies_compared": len(common),
            "per_proxy": {c: round(scores[c] - baseline[c], 5) for c in common},
        })

    # Selected on proxy agreement alone. The IC measurement is not consulted.
    best = max(sweep, key=lambda row: (row["mean_proxy_improvement"], -row["k"]))
    repaired, flagged = repair(returns, best["k"])

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    repaired.to_csv(out / "weekly_returns_repaired.csv.gz", compression="gzip")
    flagged.to_csv(out / "flagged_weeks.csv.gz", compression="gzip")

    manifest = {
        "experiment": "futures_roll_repair_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": FUTURES,
        "source_sha256": sha256(ROOT / FUTURES),
        "excluded_instruments": EXCLUDE,
        "method": {
            "detector": f"|r - trailing median| > k x {MAD_TO_SIGMA} x trailing MAD",
            "window_weeks": ROBUST_WINDOW_WEEKS,
            "treatment": "flagged returns set to missing, never to zero",
            "why_not_adjusted": "roll dates are unknowable without contract-level data, so gaps can be excluded but not adjusted away",
        },
        "k_selected": best["k"],
        "k_selected_on": "mean improvement in correlation against nine ETF proxies; the IC measurement was not consulted",
        "sweep": sweep,
        "baseline_proxy_correlations": {k: round(v, 5) for k, v in baseline.items()},
        "artifact_sha256": {p.name: sha256(p) for p in sorted(out.glob("*.csv.gz"))},
        "modifies_existing_panels": False,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    print(f"{'k':>5}{'flagged':>9}{'share':>9}{'instr':>7}{'worst left':>12}{'mean corr':>11}{'improve':>10}{'better':>8}")
    for row in sweep:
        print(f"{row['k']:>5.0f}{row['cells_flagged']:>9}{row['share_of_cells_flagged']:>9.4f}"
              f"{row['instruments_touched']:>7}{row['worst_surviving_weekly_return']*100:>11.1f}%"
              f"{row['mean_proxy_correlation']:>11.4f}{row['mean_proxy_improvement']:>+10.5f}"
              f"{row['proxies_improved']:>4}/{row['proxies_compared']}")
    print(f"\nbaseline mean proxy correlation: {np.mean(list(baseline.values())):.4f}")
    print(f"selected k = {best['k']:.0f} on proxy agreement alone")
    print("per-proxy improvement at the selected k:")
    for name, delta in sorted(best["per_proxy"].items(), key=lambda kv: -kv[1]):
        print(f"    {name:<8}{delta:+.5f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
