#!/usr/bin/env python3
"""Is crypto the domain change that adds a third independent return source?

The owner's reasoning is sound and worth stating: 1.0 produced a mediocre
strategy on ETFs, 2.0 produced a better one on SEC single names, and the step
between them was a change of *data domain*, not a better signal. Every one of the
twelve families closed since has been a new signal on the same domain. Crypto is
the largest domain change still available for free.

Declared before running, and the declarations are in the file rather than a
separate registry because there are only two of them:

  baseline    equal-weight buy-and-hold across the universe
  strategy    top 5 of 20 by 12-week momentum, weekly rebalance, 50bps

Gates are Step 277's: absolute correlation below 0.30 against BOTH existing legs,
AND standalone Sharpe at or above 1.0. Both required. Breadth without skill pays
nothing -- XLE cleared orthogonality and bought 0.021 of Sharpe.

**This test is survivorship-contaminated and the contamination is not fixable
with free data.** The universe is twenty coins that are alive today, tested
backward. Coins that died are absent entirely, which is exactly the "present-day
ticker list filtered backward" CLAUDE.md rule 4 forbids, and the bias runs
upward. A NEGATIVE result here is therefore trustworthy and a POSITIVE one is
not: the honest reading of a pass would be "not established", not "found". That
asymmetry is declared here, before the numbers, so it cannot be forgotten after.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "evidence/crypto_cross_sectional_v1"
VALUATION = ROOT / "evidence/valuation_revival_v1/path__breadth20__50bps.csv"
GROWTH = ROOT / "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv"
UNIVERSE = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "ADA-USD", "AVAX-USD", "LINK-USD",
            "DOT-USD", "LTC-USD", "BCH-USD", "DOGE-USD", "TRX-USD", "XLM-USD", "ATOM-USD",
            "ETC-USD", "XMR-USD", "ALGO-USD", "VET-USD", "FIL-USD", "HBAR-USD"]
LOOKBACK, BREADTH, COST_BPS = 12, 5, 50.0


def load_leg(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
    frame = frame.dropna(subset=[column]).set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def metrics(returns: pd.Series) -> dict[str, float]:
    years = len(returns) / 52.0
    total = float((1.0 + returns).prod())
    cagr = total ** (1.0 / years) - 1.0 if total > 0 and years > 0 else float("nan")
    vol = float(returns.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + returns).cumprod()
    return {"cagr": cagr, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "volatility": vol, "max_drawdown": float((curve / curve.cummax() - 1.0).min())}


def main() -> int:
    daily = yf.download(UNIVERSE, start="2019-01-01", end="2026-09-06",
                        interval="1d", progress=False, auto_adjust=True)
    close = daily["Close"] if isinstance(daily.columns, pd.MultiIndex) else daily
    close.index = pd.to_datetime(close.index, utc=True)
    weekly = close.resample("W-FRI").last()
    returns = (weekly / weekly.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 2.0)

    correlation = returns.corr()
    values = np.linalg.eigvalsh(correlation.fillna(0.0).values)
    values = values[values > 0]
    effective = float(values.sum() ** 2 / (values ** 2).sum())

    baseline = returns.mean(axis=1)

    # Momentum measured over the LOOKBACK weeks ending at the decision week, used
    # for the following week. No same-week information enters the decision.
    momentum = (weekly / weekly.shift(LOOKBACK) - 1.0)
    holdings = pd.Series(0.0, index=returns.columns, dtype=float)
    rows = []
    for i, week in enumerate(returns.index):
        if i == 0:
            continue
        previous = returns.index[i - 1]
        signal = momentum.loc[previous].dropna()
        cost = 0.0
        if len(signal) >= BREADTH:
            names = list(signal.nlargest(BREADTH).index)
            target = pd.Series(0.0, index=returns.columns, dtype=float)
            target[names] = 1.0 / BREADTH
            cost = float((target - holdings).abs().sum()) / 2.0 * COST_BPS / 10_000.0
            holdings = target
        row = returns.loc[week].fillna(0.0)
        rows.append((week, float((holdings * row).sum()) - cost))
        grown = holdings * (1.0 + row)
        total = grown.sum()
        if total > 0:
            holdings = grown / total
    strategy = pd.Series(dict(rows)).sort_index()

    valuation, growth = load_leg(VALUATION), load_leg(GROWTH)
    results = {}
    for label, series in (("baseline_equal_weight", baseline), ("momentum_top5", strategy)):
        joined = pd.concat({"x": series, "v": valuation, "g": growth}, axis=1).dropna()
        cv, cg = float(joined.x.corr(joined.v)), float(joined.x.corr(joined.g))
        m = metrics(joined.x)
        gate_1 = bool(abs(cv) < 0.30 and abs(cg) < 0.30)
        gate_2 = bool(m["sharpe"] >= 1.0)
        results[label] = {**m, "correlation_vs_valuation": cv, "correlation_vs_growth": cg,
                          "gate_1_orthogonality": gate_1, "gate_2_standalone_skill": gate_2,
                          "both_gates": gate_1 and gate_2, "weeks": len(joined)}

    print(f"universe {len(UNIVERSE)} coins, {weekly.shape[0]} Friday weeks "
          f"({weekly.index.min().date()} -> {weekly.index.max().date()})")
    print(f"mean pairwise correlation among coins {np.nanmean(correlation.values[~np.eye(len(correlation), dtype=bool)]):+.3f}")
    print(f"EFFECTIVE INDEPENDENT COINS {effective:.2f} of {len(UNIVERSE)}\n")
    for label, r in results.items():
        print(f"{label}")
        print(f"  CAGR {r['cagr']:8.2%}  Sharpe {r['sharpe']:6.3f}  vol {r['volatility']:5.1%}  "
              f"maxDD {r['max_drawdown']:7.2%}   ({r['weeks']} common weeks)")
        print(f"  corr vs valuation {r['correlation_vs_valuation']:+.3f}  vs growth {r['correlation_vs_growth']:+.3f}")
        print(f"  gate 1 orthogonality {'PASS' if r['gate_1_orthogonality'] else 'FAIL'}   "
              f"gate 2 skill {'PASS' if r['gate_2_standalone_skill'] else 'FAIL'}")
    passed = [k for k, v in results.items() if v["both_gates"]]
    print(f"\nVERDICT: {'PASSES BOTH GATES -- and see the survivorship warning' if passed else 'CLOSED -- neither configuration clears both gates'}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    strategy.rename_axis("Date").to_frame("net_return").to_csv(OUTPUT / "path__momentum_top5__50bps.csv")
    (OUTPUT / "result.json").write_text(json.dumps({
        "universe": UNIVERSE, "lookback_weeks": LOOKBACK, "breadth": BREADTH,
        "cost_bps": COST_BPS, "configurations_declared": 2,
        "effective_independent_coins": effective,
        "mean_pairwise_correlation": float(np.nanmean(
            correlation.values[~np.eye(len(correlation), dtype=bool)])),
        "results": results, "configurations_passing_both_gates": passed,
        "survivorship_contaminated": True,
        "survivorship_note": ("Universe is twenty coins alive today, tested backward. Dead coins "
                              "are absent. The bias runs upward, so a negative result is "
                              "trustworthy and a positive one is not established."),
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
