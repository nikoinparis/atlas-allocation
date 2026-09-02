#!/usr/bin/env python3
"""Time-series breakout across a multi-asset ETF universe, 1993-2026.

Every prior program here ranks instruments against each other and holds the best.
This asks each instrument independently whether it is breaking out, which is a
different mechanism, and it does so across bonds, gold, commodities and
international equity as well as US sectors.

Long only, no leverage, no financing. Unallocated capital sits in SHY and earns
its actual return. Four standard published parameterisations, declared in config
before running, with no grid search.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/multi_asset_breakout_v1.json"
CRITERIA = ROOT / "config/success_criteria_v1.json"
OUTPUT = ROOT / "evidence/multi_asset_breakout_v1"

REGIMES = {
    "dotcom": ("2000-03-01", "2002-10-31"),
    "gfc": ("2007-10-01", "2009-03-31"),
    "covid": ("2020-02-01", "2020-04-30"),
    "bear_2022": ("2022-01-01", "2022-12-31"),
}
MIN_BARS = 500


def load(config: dict):
    frame = pd.read_csv(ROOT / config["price_source"],
                        usecols=["observation_date", "ticker", "open", "high", "low", "close", "adjusted_close"])
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    wide = lambda col: frame.pivot_table(index="observation_date", columns="ticker", values=col).sort_index()
    # channel logic uses raw high/low; returns use adjusted closes
    return wide("high"), wide("low"), wide("close"), wide("adjusted_close")


def stats(r: pd.Series, periods: int = 252) -> dict:
    v = r.dropna()
    if len(v) < 10:
        return {"days": int(len(v)), "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "worst_rolling_252": 0.0}
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    roll = w / w.shift(periods) - 1.0
    return {
        "days": int(len(v)),
        "cagr": float(w.iloc[-1] ** (1 / years) - 1) if years > 0 else 0.0,
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_252": float(roll.min()) if roll.notna().any() else float("nan"),
    }


def backtest(signal: pd.DataFrame, adjusted: pd.DataFrame, cash: str, cost_bps: float, delay: int) -> pd.Series:
    returns = adjusted.pct_change().replace([np.inf, -np.inf], np.nan)
    active = signal.astype(float)
    count = active.sum(axis=1)
    weights = active.div(count.replace(0, np.nan), axis=0).fillna(0.0)
    if cash in returns.columns:
        weights[cash] = weights[cash].where(count > 0, 1.0)
        weights.loc[count == 0, cash] = 1.0
    held = weights.shift(delay).fillna(0.0)
    turnover = held.diff().abs().sum(axis=1).fillna(0.0) / 2.0
    gross = (held * returns[held.columns].fillna(0.0)).sum(axis=1)
    return gross - turnover * cost_bps / 10000.0


def main() -> int:
    config = json.loads(CONFIG.read_text())
    criteria = json.loads(CRITERIA.read_text())
    high, low, close, adjusted = load(config)
    rules = config["rules"]
    cash = "SHY"
    tradeable = close.notna().cumsum() >= MIN_BARS

    variants = {}

    for name, (enter, exit_) in {"donchian_20_10": (20, 10), "donchian_55_20": (55, 20),
                                 "donchian_100_50": (100, 50)}.items():
        upper = high.shift(1).rolling(enter).max()
        lower = low.shift(1).rolling(exit_).min()
        state = pd.DataFrame(False, index=close.index, columns=close.columns)
        prev = pd.Series(False, index=close.columns)
        for stamp in close.index:
            c, u, l = close.loc[stamp], upper.loc[stamp], lower.loc[stamp]
            now = prev.copy()
            now[(c > u) & u.notna()] = True
            now[(c < l) & l.notna()] = False
            now &= tradeable.loc[stamp]
            state.loc[stamp] = now
            prev = now
        variants[name] = state

    atr = (high - low).shift(1).rolling(20).mean()
    trigger = close.shift(1) + 0.5 * atr
    stop = close.shift(1) - 0.5 * atr
    state = pd.DataFrame(False, index=close.index, columns=close.columns)
    prev = pd.Series(False, index=close.columns)
    for stamp in close.index:
        c, t, s = close.loc[stamp], trigger.loc[stamp], stop.loc[stamp]
        now = prev.copy()
        now[(c > t) & t.notna()] = True
        now[(c < s) & s.notna()] = False
        now &= tradeable.loc[stamp]
        state.loc[stamp] = now
        prev = now
    variants["volatility_breakout"] = state

    spy = adjusted["SPY"].pct_change()
    results = {}
    for name, signal in variants.items():
        net = backtest(signal, adjusted, cash, rules["cost_bps_per_unit_turnover"], rules["execution_delay_days"])
        net = net.loc[net.first_valid_index():].dropna()
        entry = {"full_sample": stats(net), "exposure": float(signal.sum(axis=1).gt(0).mean())}
        for regime, (a, b) in REGIMES.items():
            sub, bench = net.loc[a:b], spy.loc[a:b].dropna()
            if len(sub) > 10:
                entry[regime] = {"strategy_total": float((1 + sub).prod() - 1),
                                 "spy_total": float((1 + bench).prod() - 1),
                                 "strategy_drawdown": stats(sub)["max_drawdown"],
                                 "spy_drawdown": stats(bench)["max_drawdown"]}
        results[name] = entry

    bench_full = stats(spy.dropna())
    tiers = criteria["proposed_tiers"]

    def tier_of(m):
        for label in ("excellent", "good", "minimum_viable"):
            t = tiers[label]
            if (m["cagr"] >= t["cagr"] and m["sharpe"] >= t["sharpe"]
                    and m["max_drawdown"] >= t["max_drawdown"]):
                return label
        return "below_minimum"

    for name, r in results.items():
        r["tier"] = tier_of(r["full_sample"])
        r["beats_spy_sharpe"] = bool(r["full_sample"]["sharpe"] > bench_full["sharpe"])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_spy_full_sample": bench_full,
        "variants": results,
        "graded_against": "config/success_criteria_v1.json (proposal, not yet accepted)",
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    b = bench_full
    print(f"SPY 1993-2026: CAGR {100*b['cagr']:.2f}%  Sharpe {b['sharpe']:.2f}  maxDD {100*b['max_drawdown']:.1f}%  worst yr {100*b['worst_rolling_252']:.1f}%\n")
    print(f"  {'variant':<22}{'CAGR':>8}{'Sharpe':>8}{'maxDD':>8}{'worst yr':>10}{'exposure':>10}{'tier':>16}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["full_sample"]["sharpe"]):
        m = r["full_sample"]
        print(f"  {name:<22}{100*m['cagr']:>7.2f}%{m['sharpe']:>8.2f}{100*m['max_drawdown']:>7.1f}%"
              f"{100*m['worst_rolling_252']:>9.1f}%{100*r['exposure']:>9.0f}%{r['tier']:>16}")
    print(f"\n  {'variant':<22}" + "".join(f"{k:>16}" for k in REGIMES))
    for name, r in results.items():
        cells = "".join(f"{100*r[k]['strategy_total']:>9.1f}% vs{100*r[k]['spy_total']:>5.0f}%" if k in r else f"{'-':>16}" for k in REGIMES)
        print(f"  {name:<22}{cells}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
