#!/usr/bin/env python3
"""Is buying the whole universe equally the best thing measured here?

Step 193 found the equal-weight panel returning 22.21% at Sharpe 1.28, better
risk-adjusted than any saved strategy on pure cash. It has no selection story,
which is exactly why it deserves a test: nothing in this project has demonstrated
an ability to select, and Step 190 showed breadth captures the skew.

Run on the cleaned price panel, with costs, an execution delay, and variants that
remove the untradeable names the integrity audit found.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz"
OUTPUT = ROOT / "evidence/equal_weight_universe_candidate_v1"

COST_BPS = 50.0
DELAY = 1
STALE_RUN = 8

SAVED_PURE_CASH = {
    "Growth / Micron": 1.5572, "Sector Ensemble": 1.2420, "Fragile 1.35x (unlevered)": 1.1412,
    "Residual 1.25x (unlevered)": 1.1260, "Daily-Audited": 0.9268, "ETF Incumbent": 0.7031,
}


def stats(r: pd.Series, periods: int = 52) -> dict:
    v = r.dropna().astype(float)
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    return {
        "weeks": int(len(v)), "cagr": float(w.iloc[-1] ** (1 / years) - 1),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_week": float(v.min()), "best_week": float(v.max()),
    }


def stale_mask(prices: pd.DataFrame, run: int) -> pd.Series:
    flags = {}
    for column in prices.columns:
        s = prices[column].dropna()
        if len(s) < run:
            flags[column] = True
            continue
        same = s.diff().eq(0.0)
        longest = current = 0
        for f in same:
            current = current + 1 if f else 0
            longest = max(longest, current)
        flags[column] = longest >= run
    return pd.Series(flags)


def book(prices: pd.DataFrame, columns, label: str) -> dict:
    sub = prices[list(columns)]
    returns = sub.pct_change().replace([np.inf, -np.inf], np.nan)
    live = sub.notna()
    weights = live.div(live.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    held = weights.shift(DELAY).fillna(0.0)
    turnover = held.diff().abs().sum(axis=1).fillna(0.0) / 2.0
    gross = (held * returns.fillna(0.0)).sum(axis=1)
    net = gross - turnover * COST_BPS / 10000.0
    net = net.iloc[52:]
    return {"label": label, "names": int(len(columns)),
            **stats(net), "average_turnover": float(turnover.iloc[52:].mean())}


def main() -> int:
    prices = pd.read_csv(CLEAN, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    stale = stale_mask(prices, STALE_RUN)
    tradeable = [c for c in prices.columns if not stale[c]]

    # a liquidity-ish proxy: exclude names whose price never exceeds $1
    penny = [c for c in tradeable if prices[c].max() < 1.0]
    liquid = [c for c in tradeable if c not in penny]

    variants = [
        book(prices, prices.columns, "all issuers"),
        book(prices, tradeable, "excluding stale (8+ identical weeks)"),
        book(prices, liquid, "excluding stale and sub-$1 names"),
    ]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(variants).to_csv(OUTPUT / "variants.csv", index=False)
    best = max(variants, key=lambda v: v["sharpe"])
    payload = {
        "experiment_id": "equal-weight-universe-candidate-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "price_source": str(CLEAN.relative_to(ROOT)),
        "cost_bps": COST_BPS, "execution_delay_weeks": DELAY,
        "variants": variants,
        "best_by_sharpe": best["label"],
        "saved_strategies_pure_cash_trailing": SAVED_PURE_CASH,
        "beats_every_saved_strategy_on_sharpe": None,
        "caveat": ("Same 2023-2026 bull window as everything else, and no forward evidence. "
                   "It also has no selection story at all, which is simultaneously its "
                   "weakness as a thesis and the reason it is hard to overfit."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"  {'variant':<40}{'names':>7}{'CAGR':>10}{'Sharpe':>9}{'maxDD':>9}{'turnover':>10}")
    for v in variants:
        print(f"  {v['label']:<40}{v['names']:>7}{100*v['cagr']:>9.2f}%{v['sharpe']:>9.2f}"
              f"{100*v['max_drawdown']:>8.1f}%{v['average_turnover']:>10.4f}")
    print(f"\n  best by Sharpe: {best['label']}  ({best['sharpe']:.2f})")
    print(f"\n  saved strategies, pure-cash trailing 52w CAGR (Sharpe not comparable window):")
    for k, v in sorted(SAVED_PURE_CASH.items(), key=lambda kv: -kv[1]):
        print(f"     {k:<32}{100*v:>8.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
