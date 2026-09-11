#!/usr/bin/env python3
"""Does anything have cross-sectional content in Indonesian equities?

Declared in config/indonesia_monotonicity_registry_v1.json. A diagnostic.

Step 301's argument: an edge at this scale lives where institutional capacity
constraints bite, and all nineteen closed families were tested on the most
arbitraged cross-section on earth. Indonesia is the one market already on disk
that fits the other description.

The earlier Indonesia closure is worth reading precisely. It said the programme
was "rejected or inconclusive because local inactive/delisted history, benchmark,
cost, and forward gates remain open" -- a closure on DATA GATES, not a measured
null. Cross-sectional skill was never tested here. This tests it.

Point-in-time throughout: membership carries effective_from, effective_to and
available_at, and a name enters a decision's universe only if the roster said so
as of that date. The extended roster holds 157 tickers against an 80-name index,
so names that LEFT are present -- the survivorship problem the earlier closure
named is at least partly addressed, though an issuer that left AND lost price
coverage is still invisible and that absence is not random.
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

REGISTRY = ROOT / "config/indonesia_monotonicity_registry_v1.json"
OUTPUT = ROOT / "evidence/indonesia_monotonicity_v1"
MEMBERSHIP = "data/indonesia_idx80_extended_history_vintages/**/idx80_membership.csv"
PRICES = "data/indonesia_idx80_extended_price_vintages/**/prices.csv"
HORIZON = 4
BONFERRONI = 0.05 / 4


def load_prices() -> pd.DataFrame:
    files = [f for f in glob.glob(str(ROOT / PRICES), recursive=True) if os.path.getsize(f) > 5000]
    frames = [pd.read_csv(f, usecols=["observation_date", "ticker", "close"]) for f in files]
    daily = pd.concat(frames, ignore_index=True)
    daily["observation_date"] = pd.to_datetime(daily.observation_date, utc=True, errors="coerce")
    daily["close"] = pd.to_numeric(daily.close, errors="coerce")
    daily = daily.dropna().drop_duplicates(["observation_date", "ticker"], keep="last")
    wide = daily.pivot(index="observation_date", columns="ticker", values="close").sort_index()
    return wide.resample("W-FRI").last()


def load_membership() -> pd.DataFrame:
    files = glob.glob(str(ROOT / MEMBERSHIP), recursive=True)
    frame = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    for column in ("effective_from", "effective_to", "available_at"):
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame.dropna(subset=["vendor_ticker", "effective_from"])


def members_at(membership: pd.DataFrame, when: pd.Timestamp) -> list[str]:
    """Point in time: in the index on this date, and the roster was published by then.

    Returns vendor_ticker, not ticker. The roster carries both -- `AALI` and
    `AALI.JK` -- and the price panel is keyed on the vendor form. Joining on
    `ticker` overlaps zero of 157 names and every decision silently drops, which
    reads as "no data" rather than as a broken join. It is the same class of
    mistake as the Step 291 date offset: a key that looks right, matches nothing,
    and produces a confident empty answer.
    """
    live = membership[(membership.effective_from <= when)
                      & ((membership.effective_to.isna()) | (membership.effective_to > when))
                      & ((membership.available_at.isna()) | (membership.available_at <= when))]
    return sorted(set(live.vendor_ticker.astype(str)))


def build_signals(weekly: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = (weekly / weekly.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    signals: dict[str, pd.DataFrame] = {}
    # 52-week return excluding the most recent 4, the protocol's primary signal
    signals["momentum_12_1"] = (weekly.shift(4) / weekly.shift(52) - 1.0)
    signals["low_volatility_26w"] = -returns.rolling(26, min_periods=13).std()
    signals["short_term_reversal_4w"] = -(weekly / weekly.shift(4) - 1.0)
    signals["size_proxy"] = -weekly.rolling(52, min_periods=26).median()
    # Nothing may use the decision week's own price move.
    return {name: frame.shift(1) for name, frame in signals.items()}


def measure(pairs: list[tuple[pd.Series, pd.Series]], rng) -> dict:
    ics, spreads, monos, widths = [], [], [], []
    for score, forward in pairs:
        both = pd.concat({"s": score, "f": forward}, axis=1).dropna()
        if len(both) < 30:
            continue
        widths.append(len(both))
        ics.append(float(both.s.rank().corr(both.f.rank())))
        try:
            decile = pd.qcut(both.s.rank(method="first"), 10, labels=False, duplicates="drop")
        except ValueError:
            continue
        means = both.f.groupby(decile).mean()
        if len(means) < 10:
            continue
        spreads.append(float(means.iloc[-1] - means.iloc[0]))
        monos.append(float(pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman")))
    ics = np.array([x for x in ics if np.isfinite(x)])
    if len(ics) < 20:
        return {"decisions": int(len(ics)), "inconclusive": True}
    mean_ic = float(ics.mean())
    t = float(mean_ic / (ics.std(ddof=1) / np.sqrt(len(ics)))) if ics.std(ddof=1) > 0 else float("nan")
    block, draws = 4, []
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean())
    periods = 52.0 / HORIZON
    spread = float(np.mean(spreads)) if spreads else float("nan")
    return {"decisions": int(len(ics)), "median_names": int(np.median(widths)),
            "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p,
            "clears_bonferroni": bool(p < BONFERRONI),
            "decile_spread_annualised": float((1 + spread) ** periods - 1) if np.isfinite(spread) else float("nan"),
            "monotonicity": float(np.mean(monos)) if monos else float("nan"),
            "deciles_interpretable": True, "inconclusive": False}


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20260911)
    weekly = load_prices()
    membership = load_membership()
    returns = (weekly / weekly.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    forward = (1.0 + returns.fillna(0.0)).rolling(HORIZON).apply(np.prod, raw=True).shift(-HORIZON) - 1.0
    signals = build_signals(weekly)

    print(f"prices: {weekly.shape[1]} tickers x {weekly.shape[0]} weeks "
          f"({weekly.index.min().date()} -> {weekly.index.max().date()})")
    print(f"membership: {membership.vendor_ticker.nunique()} distinct tickers, "
          f"{membership.effective_from.min().date()} -> {membership.effective_from.max().date()}")

    # Monthly decisions: every fourth Friday the roster and a forward return both exist.
    decisions = [w for i, w in enumerate(weekly.index) if i % 4 == 0
                 and w >= pd.Timestamp("2019-03-01", tz="UTC") and w in forward.index]
    print(f"candidate monthly decisions: {len(decisions)}\n")

    results = {}
    for name, frame in signals.items():
        pairs = []
        for week in decisions:
            live = members_at(membership, week)
            live = [t for t in live if t in frame.columns]
            if len(live) < 30:
                continue
            score = frame.loc[week, live].dropna()
            fwd = forward.loc[week, live].dropna()
            if len(score) < 30:
                continue
            pairs.append((score, fwd.reindex(score.index)))
        results[name] = measure(pairs, rng)

    print(f"Indonesia IDX80, {HORIZON}-week horizon, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'signal':26s} {'n':>4s} {'names':>6s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:26s} {r['decisions']:>4d}   too few decisions to measure")
            continue
        flag = " *" if r["clears_bonferroni"] else ""
        print(f"{name:26s} {r['decisions']:>4d} {r['median_names']:>6d} {r['mean_ic']:+9.4f} "
              f"{r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    usable = {k: v for k, v in results.items() if not v.get("inconclusive")}
    clearing = [k for k, v in usable.items() if v["clears_bonferroni"]]
    monotone = [k for k, v in usable.items() if abs(v["monotonicity"]) > 0.5]
    print(f"\nsignals measured: {len(usable)} of {len(results)}")
    print(f"clearing Bonferroni {BONFERRONI:.4f}: {len(clearing)}" + (f" -- {clearing}" if clearing else ""))
    print(f"monotonicity above 0.5: {len(monotone)}" + (f" -- {monotone}" if monotone else ""))
    print("\nUS comparison, Steps 296-300: nought of 27 signals ordered their deciles,")
    print("monotonicity within 0.17 of zero for every one.")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "monotonicity.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "market": "Indonesia IDX80", "horizon_weeks": HORIZON, "bonferroni_bar": BONFERRONI,
        "results": results, "clearing_bonferroni": clearing, "monotonic_above_half": monotone,
        "point_in_time_membership": True,
        "survivorship_note": ("roster holds 157 tickers against an 80-name index so exits are "
                              "present; an issuer that left AND lost price coverage is still "
                              "invisible and that absence is not random"),
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
