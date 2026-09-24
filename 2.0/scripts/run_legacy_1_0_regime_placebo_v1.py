"""S17 — does the 1.0 regime thesis carry information, or is it tuned noise?

Step 318 falsified 1.0's *allocator* from its own recorded output: 0 of 32 variants beat HRP
by the 0.05 Sharpe their own reports require. That did NOT test the regime classifier, which is
a separate claim -- the calls could carry real macro information that the allocator wastes.

THE TEST THAT DECIDES, DECLARED BEFORE IT RUNS. Feed the same allocator randomised regime
labels. If performance does not collapse, the regime calls carry no information and 32 phases
were tuning an allocator on noise.

  BAR: the real-label Sharpe must exceed the 95th percentile of the shuffled-label
  distribution. Anything less is consistent with the labels being decorative.

WHY THE SHUFFLE IS BLOCKED, NOT IID. Regime labels are highly persistent -- stress lasts
months. An iid shuffle destroys that persistence and produces a placebo that trades far more
often than the real thing, which would make the real labels look good for a reason that has
nothing to do with information. The shuffle here preserves the observed run-length structure by
permuting whole regime episodes, so the placebo has the same number and length of episodes as
the original and differs only in WHEN they occur. That is the honest null.

WHAT THIS IS NOT. It is not a reproduction of 1.0. `1.0/data/` does not exist and was never
committed, so none of 1.0's 32 benchmarks, 35 realism audits or 3 classifier versions can be
re-executed -- `build_macro_regime_classifier_v3.py` itself dies on a missing
`01_data_hub/weekly_prices.csv`. This is a RECONSTRUCTION of the documented design on public
data, testing the thesis rather than reproducing the numbers.

TWO DELIBERATE DEPARTURES, declared so they are not later mistaken for bugs.
  1. Market-observable inputs only (VIX, HYG/LQD, SPY drawdown, realised correlation). V3's
     growth factor uses FRED INDPRO, which is REVISED -- using today's vintage for a 2008
     decision is lookahead. Market data is not revised, so this is the causally safe subset,
     and it is exactly what V3 itself calls the `financial_conditions_proxy`.
  2. Expanding-window z-scores, never full-sample. A full-sample z-score would leak the
     future into every historical decision.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

START, END = "2005-01-01", "2026-04-10"
OFFENSE, DEFENSE = "SPY", "TLT"
N_PLACEBO = 2000
SEED = 20260924
OUT = Path(__file__).resolve().parents[1] / "evidence/legacy_1_0_regime_placebo_v1"


def fetch() -> pd.DataFrame:
    tickers = ["SPY", "TLT", "HYG", "LQD", "^VIX"]
    raw = yf.download(tickers, start=START, end=END, interval="1wk",
                      auto_adjust=True, progress=False, threads=False)
    close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw
    return close.dropna(how="all").ffill()


def expanding_z(series: pd.Series, minimum: int = 104) -> pd.Series:
    """Causal z-score: at each week, standardise against history up to and including it."""
    mean = series.expanding(min_periods=minimum).mean()
    std = series.expanding(min_periods=minimum).std()
    return ((series - mean) / std.replace(0, np.nan))


def build_stress(prices: pd.DataFrame) -> pd.Series:
    """V3's financial_conditions_proxy, market-observable components only, causally scored."""
    spy, vix = prices["SPY"], prices["^VIX"]
    credit = prices["HYG"] / prices["LQD"]           # risk appetite; falls when credit stresses
    drawdown = spy / spy.cummax() - 1.0              # peak-to-current, causal by construction
    returns = spy.pct_change()
    realised_vol = returns.rolling(13).std()

    parts = pd.DataFrame({
        "vix": expanding_z(vix),
        "credit": -expanding_z(credit.pct_change(13)),
        "drawdown": -expanding_z(drawdown),
        "vol": expanding_z(realised_vol),
    })
    return parts.mean(axis=1, skipna=True)


def episodes(labels: pd.Series) -> list[tuple[bool, int]]:
    """Compress a boolean series to (value, run_length) episodes."""
    out, current, length = [], labels.iloc[0], 0
    for value in labels:
        if value == current:
            length += 1
        else:
            out.append((current, length)); current, length = value, 1
    out.append((current, length))
    return out


def rebuild(eps: list[tuple[bool, int]], index: pd.Index) -> pd.Series:
    values = np.concatenate([np.full(n, v) for v, n in eps])[:len(index)]
    return pd.Series(values, index=index, dtype=bool)


def backtest(stress: pd.Series, forward: pd.DataFrame) -> dict:
    """Allocate to DEFENSE in stress, OFFENSE otherwise. Strictly next-week execution."""
    weights = pd.DataFrame(0.0, index=stress.index, columns=[OFFENSE, DEFENSE])
    weights.loc[~stress, OFFENSE] = 1.0
    weights.loc[stress, DEFENSE] = 1.0
    strategy = (weights.shift(1) * forward).sum(axis=1).dropna()   # shift(1) = no same-bar fill
    if len(strategy) < 52:
        return {"sharpe": float("nan")}
    ann = strategy.mean() * 52
    vol = strategy.std(ddof=1) * np.sqrt(52)
    curve = (1 + strategy).cumprod()
    return {"sharpe": float(ann / vol) if vol > 0 else float("nan"),
            "ann_return": float(ann), "ann_vol": float(vol),
            "max_drawdown": float((curve / curve.cummax() - 1).min()),
            "turnover": float(weights.diff().abs().sum(axis=1).mean() / 2),
            "weeks": int(len(strategy))}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    prices = fetch()
    returns = prices[[OFFENSE, DEFENSE]].pct_change()
    stress_score = build_stress(prices)
    usable = stress_score.dropna().index
    stress = (stress_score.loc[usable] > 0)
    returns = returns.loc[usable]

    print(f"weeks: {len(usable)}  {usable.min().date()} -> {usable.max().date()}")
    print(f"stress weeks: {int(stress.sum())} ({stress.mean():.1%})\n")

    eps = episodes(stress)
    print(f"regime episodes: {len(eps)}  median length {np.median([n for _, n in eps]):.0f}w\n")

    real = backtest(stress, returns)
    print("=== REAL regime labels ===")
    for k, v in real.items():
        print(f"  {k:14} {v:.4f}" if isinstance(v, float) else f"  {k:14} {v}")

    # --- benchmarks that do not use the labels at all -------------------------------
    bench = {}
    for name, w in {"always_SPY": {OFFENSE: 1.0, DEFENSE: 0.0},
                    "always_TLT": {OFFENSE: 0.0, DEFENSE: 1.0},
                    "static_60_40": {OFFENSE: 0.6, DEFENSE: 0.4}}.items():
        flat = pd.DataFrame([w] * len(usable), index=usable)
        s = (flat.shift(1) * returns).sum(axis=1).dropna()
        ann, vol = s.mean() * 52, s.std(ddof=1) * np.sqrt(52)
        curve = (1 + s).cumprod()
        bench[name] = {"sharpe": float(ann / vol), "ann_return": float(ann),
                       "max_drawdown": float((curve / curve.cummax() - 1).min())}
    print("\n=== benchmarks that ignore the regime entirely ===")
    for k, v in bench.items():
        print(f"  {k:14} sharpe {v['sharpe']:+.4f}  return {v['ann_return']:+.4f}  "
              f"maxDD {v['max_drawdown']:+.4f}")

    # --- the placebo ----------------------------------------------------------------
    print(f"\n=== PLACEBO: {N_PLACEBO} block-shuffled label sets ===", flush=True)
    draws = []
    for i in range(N_PLACEBO):
        shuffled = list(eps)
        rng.shuffle(shuffled)
        result = backtest(rebuild(shuffled, usable), returns)
        if result["sharpe"] == result["sharpe"]:
            draws.append(result["sharpe"])
    draws = np.array(draws)
    pct95 = float(np.percentile(draws, 95))
    p_value = float((draws >= real["sharpe"]).mean())

    print(f"  shuffled Sharpe: mean {draws.mean():+.4f}  sd {draws.std(ddof=1):.4f}")
    print(f"                   5th {np.percentile(draws,5):+.4f}   median "
          f"{np.median(draws):+.4f}   95th {pct95:+.4f}   max {draws.max():+.4f}")
    print(f"\n  REAL labels:     {real['sharpe']:+.4f}")
    print(f"  bar declared before the run: must exceed the 95th percentile "
          f"({pct95:+.4f})")
    print(f"  empirical p-value: {p_value:.4f}  "
          f"({int((draws >= real['sharpe']).sum())} of {len(draws)} shuffles did as well)")

    verdict = ("REGIME CALLS CARRY INFORMATION -- real labels beat the shuffled 95th percentile"
               if real["sharpe"] > pct95 else
               "REFUTED -- randomised labels do as well. The regime calls carry no information "
               "the allocator can use, and 32 phases were tuning on noise.")
    print(f"\n  VERDICT: {verdict}")

    (OUT / "result.json").write_text(json.dumps({
        "real": real, "benchmarks": bench,
        "placebo": {"n": len(draws), "mean": float(draws.mean()),
                    "sd": float(draws.std(ddof=1)), "p95": pct95,
                    "max": float(draws.max()), "p_value": p_value},
        "verdict": verdict, "seed": SEED,
        "bar_declared_before_run": "real Sharpe must exceed shuffled 95th percentile",
    }, indent=2))
    print(f"\nwritten: {OUT / 'result.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
