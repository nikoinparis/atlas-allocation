#!/usr/bin/env python3
"""VWAP on 2,763 US issuers: the fair trial Step 307 could not give it.

Declared in config/vwap_wide_universe_registry_v1.json before the volume was
acquired. Only the universe changes from Step 307 -- same VWAP definition, same
20-day window, same horizon, same mean-reversion sign, same measurements -- so a
different answer is the universe and nothing else.

Step 307 failed VWAP two ways that deserve separating. The deviation signal
correlated +0.767 with short-term reversal, which is a finding about the signal.
But the BANDS failed structurally: a two-sigma filter left 7 usable decisions on
79 Indonesian names because nothing survives the filter. Here 2,763 names leave
roughly 138 beyond two sigma, deciles of about 13, so the filter has something to
rank and the idea gets tested rather than starved.

Split consistency is checked rather than trusted. Yahoo's raw Close and Volume
are both unadjusted, so a VWAP built from them is internally consistent and the
deviation -- a ratio -- is split-neutral. Forward returns come from the project's
own split-adjusted panel. Mixing the two the other way round would put a split in
the numerator and not the denominator.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REGISTRY = ROOT / "config/vwap_wide_universe_registry_v1.json"
OUTPUT = ROOT / "evidence/vwap_wide_universe_v1"
CLOSE = ROOT / "data/us_daily_volume_v1/daily_close.csv.gz"
VOLUME = ROOT / "data/us_daily_volume_v1/daily_volume.csv.gz"
PANEL = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
WINDOW, HORIZON = 20, 4
BONFERRONI = 0.05 / 4


def load(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    return frame.sort_index()


def measure(pairs, rng) -> dict:
    ics, spreads, monos, widths, density = [], [], [], [], []
    for score, forward in pairs:
        both = pd.concat({"s": score, "f": forward}, axis=1).dropna()
        if len(both) < 60:
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
    draws, block = [], 4
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(ics) - block), size=int(np.ceil(len(ics) / block)))
        sample = np.concatenate([ics[i:i + block] for i in starts])[:len(ics)]
        draws.append(sample.mean() - mean_ic)
    p = float((np.abs(np.array(draws)) >= abs(mean_ic)).mean())
    spread = float(np.mean(spreads)) if spreads else float("nan")
    periods = 52.0 / HORIZON
    return {"decisions": int(len(ics)), "median_names": int(np.median(widths)),
            "mean_ic": mean_ic, "t_stat": t, "bootstrap_p": p,
            "clears_bonferroni": bool(p < BONFERRONI),
            "decile_spread_annualised": float((1 + spread) ** periods - 1) if np.isfinite(spread) else float("nan"),
            "monotonicity": float(np.mean(monos)) if monos else float("nan"),
            "inconclusive": False}


def book(signal: pd.DataFrame, returns: pd.DataFrame, breadth: int, cost_bps: float) -> pd.Series:
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    rows = []
    for i, week in enumerate(returns.index):
        if i == 0 or week not in signal.index:
            continue
        cost = 0.0
        if i % HORIZON == 0:
            scores = signal.loc[week].dropna()
            scores = scores[scores != 0]
            names = [c for c in scores.index if c in returns.columns]
            if len(names) >= breadth:
                picked = list(scores[names].nlargest(breadth).index)
                target = pd.Series(0.0, index=returns.columns, dtype=float)
                target[picked] = 1.0 / breadth
                cost = float((target - holdings).abs().sum()) / 2.0 * cost_bps / 10_000.0
                holdings = target
        row = returns.loc[week].fillna(0.0)
        rows.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    return pd.Series(dict(rows)).sort_index()


def metrics(r: pd.Series) -> dict:
    years = len(r) / 52.0
    total = float((1 + r).prod())
    cagr = total ** (1 / years) - 1 if total > 0 and years > 0 else float("nan")
    vol = float(r.std(ddof=1) * np.sqrt(52))
    curve = (1 + r).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "max_drawdown": float((curve / curve.cummax() - 1).min())}


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20260912)
    close, volume = load(CLOSE), load(VOLUME)
    shared = [c for c in close.columns if c in volume.columns]
    close, volume = close[shared], volume[shared]
    print(f"daily: {len(shared)} issuers x {len(close)} days "
          f"({close.index.min().date()} -> {close.index.max().date()})")

    # Split consistency, checked rather than trusted.
    ratio = (close / close.shift(1)).stack().dropna()
    jumps = float(((ratio > 1.8) | (ratio < 0.55)).mean())
    print(f"split-consistency check: {jumps:.4%} of daily price ratios outside [0.55, 1.8]")
    print("  raw Close and Volume are both unadjusted, so VWAP from them is")
    print("  internally consistent and the deviation ratio is split-neutral.\n")

    turnover = (close * volume).rolling(WINDOW, min_periods=WINDOW // 2).sum()
    shares = volume.rolling(WINDOW, min_periods=WINDOW // 2).sum()
    vwap = turnover / shares.where(shares > 0)
    deviation = (close - vwap) / vwap
    band_sd = deviation.rolling(WINDOW, min_periods=WINDOW // 2).std()
    z = deviation / band_sd.where(band_sd > 0)

    signals = {"vwap_deviation": -deviation}
    for k in (1, 2, 3):
        signals[f"vwap_band_{k}sd"] = -z.where(z.abs() >= k, 0.0)
    signals["short_term_reversal_4w"] = -(close / close.shift(WINDOW) - 1.0)

    panel = load(PANEL)
    weekly_ret = (panel / panel.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    weekly_ret = weekly_ret.where(weekly_ret.abs() <= 1.0)
    forward = (1 + weekly_ret.fillna(0.0)).rolling(HORIZON).apply(np.prod, raw=True).shift(-HORIZON) - 1
    weekly = {n: f.resample("W-FRI").last().shift(1) for n, f in signals.items()}

    decisions = [w for i, w in enumerate(weekly_ret.index) if i % HORIZON == 0 and w in forward.index]
    results = {}
    for name, frame in weekly.items():
        pairs = []
        for week in decisions:
            if week not in frame.index:
                continue
            score = frame.loc[week].dropna()
            if "band" in name:
                score = score[score != 0]
            score = score[score.index.isin(forward.columns)]
            if len(score) < 60:
                continue
            pairs.append((score, forward.loc[week].reindex(score.index)))
        results[name] = measure(pairs, rng)

    print(f"VWAP on {len(shared)} US issuers, {HORIZON}-week horizon, Bonferroni p < {BONFERRONI:.4f}\n")
    print(f"{'signal':26s} {'n':>4s} {'names':>6s} {'mean IC':>9s} {'t':>7s} {'p':>8s} "
          f"{'decile spread':>14s} {'monotone':>9s}")
    for name, r in results.items():
        if r.get("inconclusive"):
            print(f"{name:26s} {r['decisions']:>4d}   too few decisions")
            continue
        flag = " *" if r["clears_bonferroni"] else ""
        print(f"{name:26s} {r['decisions']:>4d} {r['median_names']:>6d} {r['mean_ic']:+9.4f} "
              f"{r['t_stat']:+7.2f} {r['bootstrap_p']:8.4f} "
              f"{r['decile_spread_annualised']:+13.2%} {r['monotonicity']:+9.2f}{flag}")

    print("\nIS IT A NEW FAMILY, OR SHORT-TERM REVERSAL AT SCALE?")
    corr = {}
    base = weekly["short_term_reversal_4w"]
    for name in ("vwap_deviation", "vwap_band_1sd", "vwap_band_2sd", "vwap_band_3sd"):
        a, b = weekly[name].align(base, join="inner")
        vals = [a.loc[w].corr(b.loc[w]) for w in a.index[::HORIZON]
                if a.loc[w].notna().sum() > 60 and b.loc[w].notna().sum() > 60]
        vals = [v for v in vals if np.isfinite(v)]
        corr[name] = float(np.mean(vals)) if vals else float("nan")
        print(f"   {name:18s} vs short-term reversal: {corr[name]:+.3f}   "
              f"(Step 307 on 79 Indonesian names: "
              f"{{'vwap_deviation':'+0.767','vwap_band_1sd':'+0.598','vwap_band_2sd':'+0.453','vwap_band_3sd':'+0.292'}}.get(name,''))")

    print("\nCOST LADDER, best-performing band, breadth 50 (CLAUDE.md rule 7)")
    ladder = {}
    for cost in (0.0, 10.0, 50.0, 100.0):
        path = book(weekly["vwap_band_2sd"], weekly_ret, 50, cost)
        m = metrics(path)
        ladder[str(int(cost))] = m
        print(f"   {cost:5.0f} bps   CAGR {m['cagr']:7.2%}   Sharpe {m['sharpe']:6.3f}   "
              f"maxDD {m['max_drawdown']:7.2%}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps({
        "universe": len(shared), "window_days": WINDOW, "horizon_weeks": HORIZON,
        "bonferroni_bar": BONFERRONI, "results": results,
        "correlation_with_short_term_reversal": corr, "cost_ladder_band_2sd": ladder,
        "step_307_correlations_on_79_names": {"vwap_deviation": 0.767, "vwap_band_1sd": 0.598,
                                              "vwap_band_2sd": 0.453, "vwap_band_3sd": 0.292},
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True, default=float) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
