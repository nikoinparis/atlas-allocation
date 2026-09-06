#!/usr/bin/env python3
"""Salvage the breakout work as a regime filter rather than a strategy.

Standalone breakout loses to buy-and-hold even at 5bps. But the signal carries
information in aggregate: when few instruments across a diversified ETF universe
are in breakout, the market is not trending. This tests whether that breadth
reading, used only to scale exposure, improves the distribution of strategies
that already exist.

The overlay never selects anything. It only decides how much to hold.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ETF = ROOT / "data/vintages/20260812T035702Z-0c1bf62d74413e2a/payload/prices.csv"
CLEAN = ROOT / "data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/breakout_regime_overlay_v1"

ENTER, EXIT = 100, 50           # the lowest-turnover, most stable variant
RISK_OFF_SCALE = 0.5
BREADTH_FLOOR = 0.40


def stats(r: pd.Series, periods: int = 52) -> dict:
    v = r.dropna()
    if len(v) < 10:
        return {}
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    roll = w / w.shift(periods) - 1.0
    return {"cagr": float(w.iloc[-1] ** (1 / years) - 1),
            "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
            "max_drawdown": float((w / w.cummax() - 1).min()),
            "worst_rolling": float(roll.min()) if roll.notna().any() else float("nan")}


def breakout_breadth() -> pd.Series:
    frame = pd.read_csv(ETF, usecols=["observation_date", "ticker", "high", "low", "close"])
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    wide = lambda c: frame.pivot_table(index="observation_date", columns="ticker", values=c).sort_index()
    high, low, close = wide("high"), wide("low"), wide("close")
    upper = high.shift(1).rolling(ENTER).max()
    lower = low.shift(1).rolling(EXIT).min()
    state = pd.DataFrame(False, index=close.index, columns=close.columns)
    prev = pd.Series(False, index=close.columns)
    for stamp in close.index:
        c, u, l = close.loc[stamp], upper.loc[stamp], lower.loc[stamp]
        now = prev.copy()
        now[(c > u) & u.notna()] = True
        now[(c < l) & l.notna()] = False
        state.loc[stamp] = now
        prev = now
    live = close.notna()
    breadth = state.where(live).sum(axis=1) / live.sum(axis=1).replace(0, np.nan)
    return breadth.resample("W-FRI").last()


def main() -> int:
    breadth = breakout_breadth()

    prices = pd.read_csv(CLEAN, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan)
    live = prices.notna()
    weights = live.div(live.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    held = weights.shift(1).fillna(0.0)
    turn = held.diff().abs().sum(axis=1).fillna(0.0) / 2.0
    universe = ((held * returns.fillna(0.0)).sum(axis=1) - turn * 50 / 10000.0).iloc[52:]

    document = json.loads(DASHBOARD.read_text())
    series = {"equal_weight_universe": universe}
    for item in document["strategies"]:
        idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in item["records"]])
        gross = pd.Series([float(r["grossReturn"]) for r in item["records"]], index=idx)
        exposure = max(1.0, max(sum(abs(h["weight"]) for h in r["holdings"]
                                    if not h["symbol"].startswith("cash")) for r in item["records"]))
        series[item["strategy"]["shortName"]] = gross / exposure   # pure cash

    rows = []
    for name, base in series.items():
        aligned = breadth.reindex(base.index).ffill().shift(1)      # lagged: causal
        scale = pd.Series(np.where(aligned < BREADTH_FLOOR, RISK_OFF_SCALE, 1.0), index=base.index)
        overlaid = base * scale
        b, o = stats(base), stats(overlaid)
        if not b or not o:
            continue
        rows.append({
            "series": name, "weeks": int(len(base)),
            "base_cagr": b["cagr"], "overlay_cagr": o["cagr"],
            "base_sharpe": b["sharpe"], "overlay_sharpe": o["sharpe"],
            "base_drawdown": b["max_drawdown"], "overlay_drawdown": o["max_drawdown"],
            "base_worst_rolling": b["worst_rolling"], "overlay_worst_rolling": o["worst_rolling"],
            "share_risk_off": float((scale < 1.0).mean()),
            "sharpe_improved": bool(o["sharpe"] > b["sharpe"]),
            "drawdown_improved": bool(o["max_drawdown"] > b["max_drawdown"]),
        })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "overlay_comparison.csv", index=False)
    helped = [r["series"] for r in rows if r["sharpe_improved"] and r["drawdown_improved"]]
    payload = {
        "experiment_id": "breakout-regime-overlay-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "signal": f"cross-sectional breakout breadth, Donchian {ENTER}/{EXIT}, lagged one week",
        "rule": f"scale exposure to {RISK_OFF_SCALE} when fewer than {int(100*BREADTH_FLOOR)}% of ETFs are in breakout",
        "results": rows,
        "improved_both_sharpe_and_drawdown": helped,
        "caveat": ("The overlay is applied to strategy return series, which is valid for a risk scaler "
                   "but assumes exposure can be reduced without changing what is held. Thresholds were "
                   "declared before running and not swept."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"breakout breadth as a risk-off filter (Donchian {ENTER}/{EXIT}, lagged)")
    print(f"scale to {RISK_OFF_SCALE:.0%} when under {BREADTH_FLOOR:.0%} of ETFs are breaking out\n")
    print(f"  {'series':<26}{'CAGR':>18}{'Sharpe':>16}{'maxDD':>18}{'risk-off':>10}")
    for r in rows:
        print(f"  {r['series']:<26}{100*r['base_cagr']:>8.1f}%->{100*r['overlay_cagr']:>7.1f}%"
              f"{r['base_sharpe']:>8.2f}->{r['overlay_sharpe']:>6.2f}"
              f"{100*r['base_drawdown']:>9.1f}%->{100*r['overlay_drawdown']:>7.1f}%{100*r['share_risk_off']:>9.0f}%")
    print(f"\n  improved BOTH Sharpe and drawdown: {helped if helped else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
