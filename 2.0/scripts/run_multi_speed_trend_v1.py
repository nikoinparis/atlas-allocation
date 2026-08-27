#!/usr/bin/env python3
"""Three speeds held together, rather than three speeds blended into one number.

The incumbent sleeve averages three lookbacks into a single score and trades one
book. A signal average can sit at zero while its components disagree, which takes
the book to cash exactly when the speeds are most informative about each other.
Managed-futures programmes instead run several speeds as separate books and hold
all of them.

That is the same argument Step 203 made one level up, applied one level down: hold
the set rather than choosing within it. Every speed on the ladder is held, so
nothing here is selected on performance.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.trial_ledger import Trial, TrialLedger  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
from run_candle_volatility_sizing_v1 import load_adjusted_bars, realised_volatility  # noqa: E402

CONFIG = ROOT / "config/multi_speed_trend_v1.json"
OUTPUT = ROOT / "evidence/multi_speed_trend_v1"
TRADING_DAYS = 252


def metrics(net: pd.Series, turnover: pd.Series | None = None) -> dict:
    v = net.dropna()
    if len(v) < 200:
        return {"observations": int(len(v)), "insufficient": True}
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    rolling = w / w.shift(TRADING_DAYS) - 1.0
    out = {
        "observations": int(len(v)),
        "cagr": float(w.iloc[-1] ** (TRADING_DAYS / len(v)) - 1),
        "sharpe": float(v.mean() / sd * math.sqrt(TRADING_DAYS)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float(rolling.min()) if rolling.notna().any() else float("nan"),
    }
    if turnover is not None:
        out["annual_turnover"] = float(turnover.reindex(v.index).fillna(0.0).sum() / (len(v) / TRADING_DAYS))
    return out


def build_weights(bars, vol, lookbacks):
    close = bars["close"]
    returns = close.pct_change()
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    month_ends = pd.DatetimeIndex(
        [d for d in close.index.to_series().groupby(close.index.to_period("M")).last()]
    )
    need = max(lookbacks) + 60
    for decision in month_ends:
        history = close.loc[:decision]
        if len(history) < max(300, need):
            continue
        available = history.columns[history.tail(252).notna().sum() >= 240]
        if len(available) < 4:
            continue
        score = pd.Series(0.0, index=available)
        used = 0
        for lookback in lookbacks:
            if len(history) <= lookback:
                continue
            score += np.sign((history[available].iloc[-1] / history[available].iloc[-1 - lookback] - 1).fillna(0.0))
            used += 1
        if not used:
            continue
        score /= used
        held = score[score > 0]
        execute = close.index.searchsorted(decision) + 1
        if execute >= len(close.index):
            continue
        weights.iloc[execute:, :] = 0.0
        if held.empty:
            continue
        estimate = vol.loc[:decision].iloc[-1].reindex(held.index).replace(0.0, np.nan)
        estimate = estimate.fillna(estimate.median() if estimate.notna().any() else 0.2)
        w = held.abs() / estimate
        w /= w.sum()
        cov = returns[held.index].loc[:decision].tail(252).cov() * TRADING_DAYS
        book_vol = float(np.sqrt(max(w.values @ cov.values @ w.values, 1e-8)))
        w = w * min(1.0, 0.10 / book_vol)
        for asset, value in w.items():
            weights.iloc[execute:, weights.columns.get_loc(asset)] = value
    return weights


def realise(weights: pd.DataFrame, bars, cost_bps: float):
    returns = bars["close"].pct_change()
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    gross = (weights.shift(1) * returns).sum(axis=1)
    idle = (1.0 - weights.sum(axis=1)).clip(lower=0.0)
    cash = returns["BIL"].fillna(0.0) if "BIL" in returns else 0.0
    return (gross + idle.shift(1).fillna(0.0) * cash - turnover * cost_bps / 1e4).dropna(), turnover


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]
    bars = load_adjusted_bars(ROOT / config["price_source"])
    vol = realised_volatility(bars, spec["volatility_estimator"], 126)
    cost = spec["cost_bps_per_unit_turnover"]

    ladder = {s["name"]: s["lookbacks_days"] for s in spec["speed_ladder"]}
    speed_weights = {name: build_weights(bars, vol, lookbacks) for name, lookbacks in ladder.items()}

    rules = {}
    rules["signal_average_medium_only"] = realise(speed_weights["medium"], bars, cost)
    all_nine = sorted({lb for lookbacks in ladder.values() for lb in lookbacks})
    rules["signal_average_all_nine"] = realise(build_weights(bars, vol, all_nine), bars, cost)
    blended = sum(speed_weights.values()) / len(speed_weights)
    rules["book_average_three_speeds"] = realise(blended, bars, cost)
    for name, weights in speed_weights.items():
        rules[f"single_speed_{name}"] = realise(weights, bars, cost)

    results = {}
    for window_name, start in spec["windows"].items():
        results[window_name] = {
            name: metrics(net.loc[start:], turnover.loc[start:])
            for name, (net, turnover) in rules.items()
        }

    ledger = TrialLedger(ROOT / "data/trial_ledger_v1/trials.jsonl")
    registered = 0
    if ledger.count(family="multi_speed_trend") == 0:
        registered = ledger.append([
            Trial("multi_speed_trend", config["experiment"], f"{w}::{n}", "sharpe",
                  config["price_source"], outcome="reported_not_selected",
                  metric=float(m.get("sharpe", 0.0)))
            for w, entries in results.items() for n, m in entries.items()
        ])

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "results_by_window": results,
        "trials_registered": registered,
        "trial_ledger_total": ledger.count(),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    for window_name, entries in results.items():
        print(f"\n--- {window_name} ---")
        print(f"  {'rule':30s}{'CAGR':>9s}{'Sharpe':>8s}{'maxDD':>9s}{'worst1Y':>10s}{'turnover':>10s}")
        for name, m in entries.items():
            if m.get("insufficient"):
                print(f"  {name:30s}  (too short)")
                continue
            print(f"  {name:30s}{m['cagr']*100:8.2f}%{m['sharpe']:8.2f}{m['max_drawdown']*100:8.2f}%"
                  f"{m['worst_rolling_1y']*100:9.2f}%{m.get('annual_turnover', 0):10.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
