#!/usr/bin/env python3
"""Is VWAP deviation a new signal, or short-term reversal wearing a different name?

The owner asked whether VWAP and standard-deviation-band strategies had been
tried. The record says almost: VWAP appears once in 306 steps, and only to note
that the free ETF snapshot HAD no VWAP so a typical-price proxy was substituted.
Bollinger bands were rejected in Step 49 for zero signal coverage. So VWAP-band
strategies are genuinely untested here.

They are only computable where volume exists, and the US weekly panel carries
prices without volume. The Indonesian daily panel carries volume, so that is
where this runs.

Two questions, and the second matters more than the first:

    does it order its deciles?   the standard screen, density guard on
    is it a new signal at all?   VWAP deviation is (price - volume-weighted
                                 average price) / price. Price above its own
                                 recent VWAP means recent buying, which is what
                                 a positive trailing return means. If the two
                                 correlate highly, a VWAP band is a repackaging
                                 of short-term reversal -- closed in Step 250 on
                                 bid-ask bounce and again in Step 302 at
                                 monotonicity +0.01 -- and no amount of band
                                 tuning changes that.

Bands at 1, 2 and 3 standard deviations are reported, because that is the form
the question was asked in and the answer should address it directly.
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
sys.path.insert(0, str(ROOT / "scripts"))
import run_indonesia_monotonicity_v1 as idn

OUTPUT = ROOT / "evidence/vwap_signal_v1"
HORIZON = 4
WINDOW = 20          # trading days over which VWAP and its dispersion are formed
BONFERRONI = 0.05 / 5


def load_daily() -> tuple[pd.DataFrame, pd.DataFrame]:
    files = [f for f in glob.glob(str(ROOT / "data/indonesia_idx80_extended_price_vintages/**/prices.csv"),
                                  recursive=True) if os.path.getsize(f) > 5000]
    frames = [pd.read_csv(f, usecols=["observation_date", "ticker", "close", "volume"]) for f in files]
    daily = pd.concat(frames, ignore_index=True)
    daily["observation_date"] = pd.to_datetime(daily.observation_date, utc=True, errors="coerce")
    for c in ("close", "volume"):
        daily[c] = pd.to_numeric(daily[c], errors="coerce")
    daily = daily.dropna().drop_duplicates(["observation_date", "ticker"], keep="last")
    close = daily.pivot(index="observation_date", columns="ticker", values="close").sort_index()
    volume = daily.pivot(index="observation_date", columns="ticker", values="volume").sort_index()
    return close, volume


def main() -> int:
    rng = np.random.default_rng(20260911)
    close, volume = load_daily()
    print(f"daily panel: {close.shape[1]} tickers x {close.shape[0]} days "
          f"({close.index.min().date()} -> {close.index.max().date()})")
    print(f"volume present in {(volume > 0).sum().sum() / volume.size:.1%} of cells\n")

    # Rolling VWAP over WINDOW days, and the dispersion of price around it.
    turnover = (close * volume).rolling(WINDOW, min_periods=WINDOW // 2).sum()
    shares = volume.rolling(WINDOW, min_periods=WINDOW // 2).sum()
    vwap = turnover / shares.where(shares > 0)
    deviation = (close - vwap) / vwap
    band_sd = deviation.rolling(WINDOW, min_periods=WINDOW // 2).std()

    signals: dict[str, pd.DataFrame] = {}
    # Mean-reversion convention throughout: a stock far ABOVE its VWAP is expected
    # to fall, so the signal is the negative of the deviation.
    signals["vwap_deviation"] = -deviation
    for k in (1, 2, 3):
        # Band signal: how many standard deviations beyond the k-sigma band, zero inside.
        z = deviation / band_sd.where(band_sd > 0)
        signals[f"vwap_band_{k}sd"] = -z.where(z.abs() >= k, 0.0)
    signals["short_term_reversal_4w"] = -(close / close.shift(20) - 1.0)

    weekly_close = close.resample("W-FRI").last()
    returns = (weekly_close / weekly_close.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    forward = (1.0 + returns.fillna(0.0)).rolling(HORIZON).apply(np.prod, raw=True).shift(-HORIZON) - 1.0
    membership = idn.load_membership()

    weekly_signals = {n: f.resample("W-FRI").last().shift(1) for n, f in signals.items()}
    decisions = [w for i, w in enumerate(weekly_close.index) if i % 4 == 0
                 and w >= pd.Timestamp("2019-03-01", tz="UTC") and w in forward.index]

    results = {}
    for name, frame in weekly_signals.items():
        pairs = []
        for week in decisions:
            live = [t for t in idn.members_at(membership, week) if t in frame.columns]
            if len(live) < 30:
                continue
            score = frame.loc[week, live].dropna()
            score = score[score != 0] if "band" in name else score
            if len(score) < 30:
                continue
            pairs.append((score, forward.loc[week, live].reindex(score.index)))
        results[name] = idn.measure(pairs, rng)

    print(f"VWAP signals on Indonesian daily data, {HORIZON}-week horizon, "
          f"Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'signal':26s} {'n':>4s} {'names':>6s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:26s} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["bootstrap_p"] < BONFERRONI else ""
        print(f"{name:26s} {r['decisions']:>4d} {r['median_names']:>6d} {r['mean_ic']:+9.4f} "
              f"{r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    # The question that decides whether this is a new family at all.
    print("\nIS VWAP DEVIATION A NEW SIGNAL, OR SHORT-TERM REVERSAL RELABELLED?")
    corr = {}
    base = weekly_signals["short_term_reversal_4w"]
    for name in ("vwap_deviation", "vwap_band_1sd", "vwap_band_2sd", "vwap_band_3sd"):
        a, b = weekly_signals[name].align(base, join="inner")
        per_week = [a.loc[w].corr(b.loc[w]) for w in a.index[::4]
                    if a.loc[w].notna().sum() > 30 and b.loc[w].notna().sum() > 30]
        per_week = [x for x in per_week if np.isfinite(x)]
        corr[name] = float(np.mean(per_week)) if per_week else float("nan")
        print(f"   cross-sectional correlation, {name:18s} vs short-term reversal: {corr[name]:+.3f}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps({
        "market": "Indonesia IDX80 daily (the only panel here carrying volume)",
        "window_days": WINDOW, "horizon_weeks": HORIZON, "bonferroni_bar": BONFERRONI,
        "results": results, "correlation_with_short_term_reversal": corr,
        "why_this_market": "the US weekly panel carries prices without volume, so VWAP is not computable there",
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
