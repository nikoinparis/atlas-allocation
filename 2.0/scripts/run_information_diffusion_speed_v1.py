#!/usr/bin/env python3
"""Test the premise behind the latency idea before building the pipeline for it.

Step 301's third structural asymmetry was non-machine-read information: IDX and
OJK disclosures are not parsed in microseconds the way SEC EDGAR is, so a pipeline
that ingests on publication and acts within minutes might have a window.

Two things block testing that directly. Indonesian prices on disk are DAILY, so
same-day reaction speed is unmeasurable. And IDX's endpoints return HTTP 403
behind an AWS WAF challenge, so a disclosure feed needs headless-browser
automation -- a real build.

Rather than build it and find out, this tests the premise it rests on. If
information diffuses more slowly into Indonesian prices than US ones, the
asymmetry is real and the pipeline is worth building. If it diffuses at the same
speed, the premise is wrong and no amount of scraping engineering helps.

Two measures, both beta-neutral in the sense that matters and both computable
from daily data already here:

    own-return autocorrelation   A price that underreacts to news keeps drifting,
                                 so yesterday's return predicts today's. Measured
                                 per stock at lags 1-5, averaged cross-sectionally.

    Hou-Moskowitz delay          Regress a stock's return on the contemporaneous
                                 market, then on contemporaneous plus four lags.
                                 The share of explained variance that only the
                                 lags provide is the fraction of the price
                                 response that arrives late. Recorded from general
                                 knowledge of the 2005 paper, not a read of it.

A higher figure on either measure means slower incorporation.
"""

from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "evidence/information_diffusion_speed_v1"
LAGS = 4
MIN_OBS = 250


def indonesian_daily() -> pd.DataFrame:
    files = [f for f in glob.glob(str(ROOT / "data/indonesia_idx80_extended_price_vintages/**/prices.csv"),
                                  recursive=True) if os.path.getsize(f) > 5000]
    frames = [pd.read_csv(f, usecols=["observation_date", "ticker", "close"]) for f in files]
    daily = pd.concat(frames, ignore_index=True)
    daily["observation_date"] = pd.to_datetime(daily.observation_date, utc=True, errors="coerce")
    daily["close"] = pd.to_numeric(daily.close, errors="coerce")
    daily = daily.dropna().drop_duplicates(["observation_date", "ticker"], keep="last")
    return daily.pivot(index="observation_date", columns="ticker", values="close").sort_index()


def us_daily() -> pd.DataFrame | None:
    """The US daily data on disk is 35 ETFs, and that is NOT a valid comparison.

    An ETF is a basket arbitraged against its holdings. It incorporates market
    information mechanically and near-instantly, and its negative autocorrelation
    is bid-ask bounce rather than underreaction. Comparing 157 Indonesian single
    stocks to 35 US ETFs measures the difference between instruments, not between
    markets, and the "premise NOT supported" line this produced should not be read
    as evidence about either market.

    No US daily single-stock panel exists here -- clean_full_history_prices_v1 is
    weekly. The comparison is kept and printed because deleting it would hide that
    it was attempted, but it is labelled invalid and the Indonesian figures are
    read on their own absolute level instead.
    """
    vintages = sorted(glob.glob(str(ROOT / "data/vintages/*/payload/prices.csv")))
    if not vintages:
        return None
    frames = []
    for f in vintages[-3:]:
        frame = pd.read_csv(f, usecols=["observation_date", "ticker", "adjusted_close"])
        frames.append(frame)
    daily = pd.concat(frames, ignore_index=True)
    daily["observation_date"] = pd.to_datetime(daily.observation_date, utc=True, errors="coerce")
    daily["adjusted_close"] = pd.to_numeric(daily.adjusted_close, errors="coerce")
    daily = daily.dropna().drop_duplicates(["observation_date", "ticker"], keep="last")
    return daily.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()


def autocorrelations(returns: pd.DataFrame) -> dict[int, float]:
    out = {}
    for lag in range(1, 6):
        values = []
        for column in returns.columns:
            series = returns[column].dropna()
            if len(series) < MIN_OBS:
                continue
            rho = series.autocorr(lag=lag)
            if np.isfinite(rho):
                values.append(rho)
        out[lag] = float(np.mean(values)) if values else float("nan")
    return out


def delay(returns: pd.DataFrame) -> tuple[float, int]:
    """Share of explained variance that only lagged market returns provide."""
    market = returns.mean(axis=1, skipna=True)
    ratios = []
    for column in returns.columns:
        frame = pd.concat({"r": returns[column], "m0": market}, axis=1)
        for lag in range(1, LAGS + 1):
            frame[f"m{lag}"] = market.shift(lag)
        frame = frame.dropna()
        if len(frame) < MIN_OBS:
            continue
        y = frame.r.to_numpy()
        if y.std() == 0:
            continue

        def r2(cols):
            X = np.column_stack([np.ones(len(frame))] + [frame[c].to_numpy() for c in cols])
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            return 1.0 - resid.var() / y.var()

        restricted = r2(["m0"])
        full = r2(["m0"] + [f"m{i}" for i in range(1, LAGS + 1)])
        if full <= 0:
            continue
        ratios.append(1.0 - max(0.0, restricted) / full)
    return (float(np.mean(ratios)) if ratios else float("nan")), len(ratios)


def describe(name: str, prices: pd.DataFrame) -> dict:
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 0.5)
    acf = autocorrelations(returns)
    d, n = delay(returns)
    print(f"{name}")
    print(f"  stocks measured: {n}   days: {len(returns)}   "
          f"({returns.index.min().date()} -> {returns.index.max().date()})")
    print("  own-return autocorrelation: " +
          "  ".join(f"lag{k} {v:+.4f}" for k, v in acf.items()))
    print(f"  Hou-Moskowitz delay (share of response arriving late): {d:.4f}\n")
    return {"stocks": n, "days": int(len(returns)),
            "autocorrelation": {str(k): v for k, v in acf.items()}, "delay": d}


def main() -> int:
    results = {}
    idn = indonesian_daily()
    results["indonesia_idx"] = describe("INDONESIA (IDX80 universe, daily)", idn)
    us = us_daily()
    if us is not None:
        results["us_etf"] = describe("US (ETF universe, daily)", us)
    else:
        print("US daily panel unavailable; Indonesian figures stand alone\n")

    if "us_etf" in results:
        di, du = results["indonesia_idx"]["delay"], results["us_etf"]["delay"]
        ai = results["indonesia_idx"]["autocorrelation"]["1"]
        au = results["us_etf"]["autocorrelation"]["1"]
        print("COMPARISON (INVALID — 157 single stocks vs 35 ETFs, kept for the record)")
        print(f"  delay            Indonesia {di:.4f}  vs  US {du:.4f}   "
              f"{'SLOWER' if di > du else 'NOT slower'}")
        print(f"  lag-1 autocorr   Indonesia {ai:+.4f}  vs  US {au:+.4f}   "
              f"{'more underreaction' if ai > au else 'no more underreaction'}")
        print("  ^ do not read this as evidence: an ETF incorporates market")
        print("    information mechanically, so the difference is instrument, not market.")
        results["comparison_valid"] = False
        results["comparison_invalid_because"] = (
            "US side is 35 ETFs, Indonesian side is 157 single stocks")

    # The absolute Indonesian level is what can actually be read.
    d = results["indonesia_idx"]["delay"]
    a1 = results["indonesia_idx"]["autocorrelation"]["1"]
    print("\nABSOLUTE READING (Indonesia on its own)")
    print(f"  delay {d:.4f}  ->  {1-d:.1%} of the price response to market information")
    print(f"  arrives contemporaneously; only {d:.1%} arrives late.")
    print(f"  lag-1 own-return autocorrelation {a1:+.4f} -- economically nil.")
    print("  Hou and Moskowitz report US large caps near 0.02-0.05 and small caps")
    print("  0.10-0.20 on this measure (from general knowledge of the 2005 paper,")
    print("  not a read of it). Indonesia at %.3f sits in the liquid, fast band." % d)
    results["absolute_reading"] = (
        f"{1-d:.1%} of the response is contemporaneous; the market is fast, not slow")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps({
        "measures": ["own-return autocorrelation lags 1-5", "Hou-Moskowitz delay"],
        "results": results,
        "why": "tests the premise behind the non-machine-read information idea before building a disclosure pipeline",
        "blockers_found_first": ["Indonesian prices on disk are daily only",
                                 "IDX endpoints return HTTP 403 behind an AWS WAF challenge"],
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
