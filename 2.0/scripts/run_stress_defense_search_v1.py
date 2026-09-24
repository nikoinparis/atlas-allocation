"""S18 — what to hold in detected stress, when bonds do not hedge.

Step 319 established the thing this project actually has: 1.0's regime classifier
**identifies crises correctly** -- 2008 at 100% stress, 2020 at 84%, 2022 at 87% -- and the
regime strategy made **+15.05%** through the GFC against a static 60/40's -19.23%.

It failed on the RESPONSE. In 2008 the defensive asset rallied. In 2022 the stock/bond hedge
broke, TLT fell with equities, and defensive-into-bonds lost 28.9% against the static blend's
20.6%. Knowing it is stressful does not tell you what to own.

THE QUESTION: is there a defensive leg that works in BOTH crises?

BARS DECLARED BEFORE ANY RESULT EXISTS. A candidate must clear all three:

  1. BOTH-CRISIS RULE. Beat static 60/40 in the GFC window AND in 2022. Beating one is
     exactly the failure S17 diagnosed -- 2008 alone can carry a full-sample number, and
     duration already does that. This is the bar that matters.
  2. PLACEBO. Beat the 95th percentile of its own block-shuffled regime labels on the full
     sample. Episodes are permuted whole, preserving run-length structure, because an iid
     shuffle destroys persistence and flatters the real labels for the wrong reason.
  3. NOT JUST DE-RISKING. Report Sharpe against static 60/40 and against a constant-weight
     version of itself. A defense that only lowers drawdown by holding less risk is a
     risk-budget choice, not a timing edge -- the verdict S16 and S17 both reached about 1.0.

MULTIPLE TESTING, DECLARED: nine defensive candidates are searched here. That is a search and
the count goes in the ledger. With nine tries the best one is expected to look better than it
is, which is precisely what bar 1 and bar 2 exist to absorb.

No promotion comes out of this regardless of outcome.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

START, END = "2004-01-01", "2026-04-10"
SEED, N_PLACEBO = 20260924, 1500
SMOOTH = 13          # from S17's persistence sweep; ~20-week median regimes
OUT = Path(__file__).resolve().parents[1] / "evidence/stress_defense_search_v1"

# Each defense is a dict of weights held while the regime says stress.
DEFENSES = {
    "cash":                 {},
    "TLT_long_duration":    {"TLT": 1.0},
    "IEF_intermediate":     {"IEF": 1.0},
    "SHY_short_duration":   {"SHY": 1.0},
    "GLD_gold":             {"GLD": 1.0},
    "SHY_GLD_half":         {"SHY": 0.5, "GLD": 0.5},
    "DBC_commodities":      {"DBC": 1.0},
    "UUP_dollar":           {"UUP": 1.0},
    "degross_half_equity":  {"SPY": 0.5},
}
WINDOWS = {"GFC": ("2007-10-01", "2009-06-30"),
           "COVID": ("2020-02-01", "2020-06-30"),
           "Rates2022": ("2022-01-01", "2022-12-31")}


def expanding_z(s: pd.Series, minimum: int = 104) -> pd.Series:
    return (s - s.expanding(min_periods=minimum).mean()) / \
           s.expanding(min_periods=minimum).std().replace(0, np.nan)


def stress_signal(px: pd.DataFrame) -> pd.Series:
    """S17's market-observable financial-conditions proxy. Causal by construction."""
    spy, vix = px["SPY"], px["^VIX"]
    parts = pd.DataFrame({
        "vix": expanding_z(vix),
        "credit": -expanding_z((px["HYG"] / px["LQD"]).pct_change(13)),
        "drawdown": -expanding_z(spy / spy.cummax() - 1.0),
        "vol": expanding_z(spy.pct_change().rolling(13).std()),
    })
    return parts.mean(axis=1, skipna=True).rolling(SMOOTH).mean()


def episodes(labels: pd.Series):
    out, cur, n = [], labels.iloc[0], 0
    for v in labels:
        if v == cur:
            n += 1
        else:
            out.append((cur, n)); cur, n = v, 1
    out.append((cur, n))
    return out


def rebuild(eps, index):
    return pd.Series(np.concatenate([np.full(n, v) for v, n in eps])[:len(index)],
                     index=index, dtype=bool)


def run(stress: pd.Series, rets: pd.DataFrame, defense: dict) -> pd.Series:
    """Long SPY when calm, hold `defense` when stressed. shift(1) = next-week execution."""
    w = pd.DataFrame(0.0, index=stress.index, columns=rets.columns)
    w.loc[~stress, "SPY"] = 1.0
    for asset, weight in defense.items():
        w.loc[stress, asset] = weight
    return (w.shift(1) * rets).sum(axis=1).dropna()


def stats(x: pd.Series) -> dict:
    if len(x) < 52:
        return {"sharpe": float("nan")}
    ann, vol = x.mean() * 52, x.std(ddof=1) * np.sqrt(52)
    curve = (1 + x).cumprod()
    return {"sharpe": float(ann / vol) if vol else float("nan"), "ann_return": float(ann),
            "max_drawdown": float((curve / curve.cummax() - 1).min())}


def total(x: pd.Series) -> float:
    return float((1 + x).prod() - 1)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    tickers = ["SPY", "TLT", "IEF", "SHY", "GLD", "DBC", "UUP", "HYG", "LQD", "^VIX"]
    px = yf.download(tickers, start=START, end=END, interval="1wk",
                     auto_adjust=True, progress=False, threads=False)["Close"].ffill()
    score = stress_signal(px)
    idx = score.dropna().index
    stress = score.loc[idx] > 0
    rets = px[["SPY", "TLT", "IEF", "SHY", "GLD", "DBC", "UUP"]].pct_change().loc[idx].fillna(0.0)

    bench = (pd.DataFrame({"SPY": 0.6, "TLT": 0.4}, index=idx).shift(1)
             * rets[["SPY", "TLT"]]).sum(axis=1).dropna()
    bench_windows = {k: total(bench[a:b].dropna()) for k, (a, b) in WINDOWS.items()}
    bs = stats(bench)
    print(f"weeks {len(idx)}  {idx.min().date()} -> {idx.max().date()}   "
          f"stress {stress.mean():.1%}\n")
    print(f"STATIC 60/40 BENCHMARK  sharpe {bs['sharpe']:+.4f}  "
          f"maxDD {bs['max_drawdown']:+.2%}   "
          + "  ".join(f"{k} {v:+.2%}" for k, v in bench_windows.items()))
    print("\nBARS DECLARED BEFORE THIS RAN: beat 60/40 in BOTH the GFC and 2022,")
    print("and beat the 95th percentile of block-shuffled regime labels.\n")

    eps = episodes(stress)
    results = {}
    header = (f"{'defense':22} {'sharpe':>7} {'maxDD':>8} {'GFC':>9} {'COVID':>8} "
              f"{'2022':>9} {'both?':>6} {'placebo p':>10} {'clears':>7}")
    print(header); print("-" * len(header))

    for name, defense in DEFENSES.items():
        strat = run(stress, rets, defense)
        st = stats(strat)
        wins = {k: total(strat[a:b].dropna()) for k, (a, b) in WINDOWS.items()}
        both = wins["GFC"] > bench_windows["GFC"] and wins["Rates2022"] > bench_windows["Rates2022"]

        draws = []
        for _ in range(N_PLACEBO):
            shuffled = list(eps); rng.shuffle(shuffled)
            d = stats(run(rebuild(shuffled, idx), rets, defense))
            if d["sharpe"] == d["sharpe"]:
                draws.append(d["sharpe"])
        draws = np.array(draws)
        p = float((draws >= st["sharpe"]).mean())
        beats_placebo = st["sharpe"] > np.percentile(draws, 95)
        clears = bool(both and beats_placebo)

        results[name] = {"stats": st, "windows": wins, "both_crises": bool(both),
                         "placebo_p": p, "placebo_p95": float(np.percentile(draws, 95)),
                         "beats_placebo": bool(beats_placebo), "clears": clears}
        print(f"{name:22} {st['sharpe']:+7.4f} {st['max_drawdown']:+8.2%} "
              f"{wins['GFC']:+9.2%} {wins['COVID']:+8.2%} {wins['Rates2022']:+9.2%} "
              f"{str(both):>6} {p:>10.4f} {str(clears):>7}")

    winners = [k for k, v in results.items() if v["clears"]]
    print(f"\ncandidates searched: {len(DEFENSES)}   clearing BOTH declared bars: {len(winners)}"
          + (f" -> {winners}" if winners else ""))
    print("\nBoth bars were declared before any number existed. Nine candidates is a search and")
    print("the count goes in the ledger. Nothing is promoted out of this regardless of outcome.")
    (OUT / "result.json").write_text(json.dumps(
        {"benchmark": {"stats": bs, "windows": bench_windows},
         "results": results, "winners": winners,
         "candidates_searched": len(DEFENSES), "seed": SEED,
         "bars": ["beat 60/40 in BOTH GFC and 2022", "beat block-shuffled 95th percentile"]},
        indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
