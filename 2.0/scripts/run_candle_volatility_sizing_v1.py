#!/usr/bin/env python3
"""We only ever looked at where each day ended.

Every strategy here estimates volatility from closing prices, which throws away
the open, high and low that are sitting in the same file. Range-based estimators
use the whole bar and are several times more efficient for the same window. Since
the trend sleeve sizes by inverse volatility, a steadier volatility reading is a
free improvement to the portfolio if it survives measurement.

One correctness trap is handled explicitly: the vintage stores raw bars next to an
adjusted close, and the adjustment factor runs from 0.55 to 1.00 on SPY. Raw highs
and lows must be scaled before use or every estimate is quietly wrong.
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

CONFIG = ROOT / "config/candle_volatility_sizing_v1.json"
OUTPUT = ROOT / "evidence/candle_volatility_sizing_v1"
TRADING_DAYS = 252


def load_adjusted_bars(path: Path) -> dict[str, pd.DataFrame]:
    raw = pd.read_csv(path, parse_dates=["observation_date"])
    # Scale raw bars onto the adjusted-close basis so splits and dividends do not
    # manufacture ranges that never happened.
    factor = raw["adjusted_close"] / raw["close"]
    for column in ("open", "high", "low", "close"):
        raw[column] = raw[column] * factor
    return {
        column: raw.pivot_table(index="observation_date", columns="ticker", values=column).sort_index()
        for column in ("open", "high", "low", "close")
    }


def realised_volatility(bars: dict[str, pd.DataFrame], estimator: str, window: int) -> pd.DataFrame:
    open_, high, low, close = bars["open"], bars["high"], bars["low"], bars["close"]
    previous_close = close.shift(1)

    if estimator == "close_to_close":
        return np.log(close / previous_close).rolling(window).std(ddof=1) * math.sqrt(TRADING_DAYS)

    if estimator == "parkinson":
        term = np.log(high / low) ** 2 / (4 * math.log(2))
        return np.sqrt(term.rolling(window).mean() * TRADING_DAYS)

    if estimator == "garman_klass":
        term = 0.5 * np.log(high / low) ** 2 - (2 * math.log(2) - 1) * np.log(close / open_) ** 2
        return np.sqrt(term.rolling(window).mean().clip(lower=0) * TRADING_DAYS)

    if estimator == "rogers_satchell":
        term = (np.log(high / close) * np.log(high / open_)
                + np.log(low / close) * np.log(low / open_))
        return np.sqrt(term.rolling(window).mean().clip(lower=0) * TRADING_DAYS)

    if estimator == "yang_zhang":
        overnight = np.log(open_ / previous_close)
        open_to_close = np.log(close / open_)
        rogers = (np.log(high / close) * np.log(high / open_)
                  + np.log(low / close) * np.log(low / open_))
        v_overnight = overnight.rolling(window).var(ddof=1)
        v_open_close = open_to_close.rolling(window).var(ddof=1)
        v_rogers = rogers.rolling(window).mean()
        k = 0.34 / (1.34 + (window + 1) / (window - 1))
        total = v_overnight + k * v_open_close + (1 - k) * v_rogers
        return np.sqrt(total.clip(lower=0) * TRADING_DAYS)

    raise ValueError(f"unknown estimator {estimator}")


def metrics(net: pd.Series, turnover: pd.Series) -> dict:
    v = net.dropna()
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    rolling = w / w.shift(TRADING_DAYS) - 1.0
    return {
        "observations": int(len(v)),
        "cagr": float(w.iloc[-1] ** (TRADING_DAYS / len(v)) - 1),
        "sharpe": float(v.mean() / sd * math.sqrt(TRADING_DAYS)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float(rolling.min()) if rolling.notna().any() else float("nan"),
        "annual_turnover": float(turnover.reindex(v.index).fillna(0.0).sum() / (len(v) / TRADING_DAYS)),
    }


def trend_book(bars: dict[str, pd.DataFrame], vol: pd.DataFrame, window_start: str):
    close = bars["close"]
    returns = close.pct_change()
    weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    month_ends = pd.DatetimeIndex(
        [d for d in close.index.to_series().groupby(close.index.to_period("M")).last()]
    )
    for decision in month_ends:
        history = close.loc[:decision]
        if len(history) < 300:
            continue
        available = history.columns[history.tail(252).notna().sum() >= 240]
        if len(available) < 4:
            continue
        score = pd.Series(0.0, index=available)
        for lookback in (63, 126, 252):
            if len(history) <= lookback:
                continue
            score += np.sign((history[available].iloc[-1] / history[available].iloc[-1 - lookback] - 1).fillna(0.0))
        score /= 3
        held = score[score > 0]
        execute = close.index.searchsorted(decision) + 1
        if execute >= len(close.index):
            continue
        weights.iloc[execute:, :] = 0.0
        if held.empty:
            continue
        estimate = vol.loc[:decision].iloc[-1].reindex(held.index)
        estimate = estimate.replace(0.0, np.nan)
        estimate = estimate.fillna(estimate.median() if estimate.notna().any() else 0.2)
        w = held.abs() / estimate
        w /= w.sum()
        cov = returns[held.index].loc[:decision].tail(252).cov() * TRADING_DAYS
        book_vol = float(np.sqrt(max(w.values @ cov.values @ w.values, 1e-8)))
        w = w * min(1.0, 0.10 / book_vol)
        for asset, value in w.items():
            weights.iloc[execute:, weights.columns.get_loc(asset)] = value

    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    gross = (weights.shift(1) * returns).sum(axis=1)
    idle = (1.0 - weights.sum(axis=1)).clip(lower=0.0)
    cash = returns["BIL"].fillna(0.0) if "BIL" in returns else 0.0
    net = (gross + idle.shift(1).fillna(0.0) * cash - turnover * 10.0 / 1e4).dropna()
    return net.loc[window_start:], turnover.loc[window_start:]


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]
    bars = load_adjusted_bars(ROOT / config["price_source"])
    window = spec["estimation_window_days"]

    estimates = {e["name"]: realised_volatility(bars, e["name"], window)
                 for e in spec["estimators"]}

    # How steady is each estimator's own reading of the same volatility?
    steadiness = {}
    for name, frame in estimates.items():
        changes = frame.diff().abs()
        steadiness[name] = {
            "mean_level": float(frame.stack().mean()),
            "mean_absolute_daily_change": float(changes.stack().mean()),
            "noise_ratio": float(changes.stack().mean() / frame.stack().mean()),
        }
    baseline_noise = steadiness["close_to_close"]["noise_ratio"]
    for name in steadiness:
        steadiness[name]["noise_versus_close_to_close"] = (
            steadiness[name]["noise_ratio"] / baseline_noise
        )

    results = {}
    for window_name, start in spec["windows"].items():
        results[window_name] = {}
        for name, frame in estimates.items():
            net, turnover = trend_book(bars, frame, start)
            results[window_name][name] = metrics(net, turnover)

    ledger = TrialLedger(ROOT / "data/trial_ledger_v1/trials.jsonl")
    registered = 0
    if ledger.count(family="candle_volatility") == 0:
        registered = ledger.append([
            Trial("candle_volatility", config["experiment"], f"{w}::{n}", "sharpe",
                  config["price_source"], outcome="reported_not_selected",
                  metric=float(results[w][n]["sharpe"]))
            for w in results for n in results[w]
        ])

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "estimator_steadiness": steadiness,
        "sleeve_results": results,
        "trials_registered": registered,
        "trial_ledger_total": ledger.count(),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print("estimator steadiness (lower noise ratio = steadier reading of the same volatility)")
    print(f"  {'estimator':18s}{'mean vol':>10s}{'noise ratio':>13s}{'vs close':>10s}")
    for name, s in steadiness.items():
        print(f"  {name:18s}{s['mean_level']*100:9.2f}%{s['noise_ratio']:13.4f}{s['noise_versus_close_to_close']:10.2f}x")
    for window_name, entries in results.items():
        print(f"\n--- trend sleeve, window {window_name} ---")
        print(f"  {'estimator':18s}{'CAGR':>9s}{'Sharpe':>8s}{'maxDD':>9s}{'worst1Y':>10s}{'turnover':>10s}")
        for name, m in entries.items():
            print(f"  {name:18s}{m['cagr']*100:8.2f}%{m['sharpe']:8.2f}{m['max_drawdown']*100:8.2f}%"
                  f"{m['worst_rolling_1y']*100:9.2f}%{m['annual_turnover']:10.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
