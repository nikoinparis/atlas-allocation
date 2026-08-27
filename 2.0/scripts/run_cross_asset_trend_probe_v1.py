#!/usr/bin/env python3
"""Is there a second bet on disk already?

Step 186 ran the 35-ETF vintage as a cross-sectional sector rotation and found it
worthless over 33 years. That is one way to use the panel. This is the other one:
long-only time-series momentum across bonds, commodities, FX, international and
equity, which is a different mechanism with a different literature behind it.

The question is not whether it out-returns the SEC books. It is whether it is
independent of them, because the project's binding constraint since Batch 03 has
been an effective breadth near 1.15, and no re-weighting of the momentum and
cash-conversion family has moved it.

Every parameter is declared in the config before running. This is a probe, not a
candidate: nothing here starts a forward clock or promotes anything.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/cross_asset_trend_probe_v1.json"
OUTPUT = ROOT / "evidence/cross_asset_trend_probe_v1"


def metrics(net: pd.Series, periods: int = 252) -> dict:
    v = net.dropna()
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    rolling = w / w.shift(periods) - 1.0
    return {
        "observations": int(len(v)),
        "cagr": float(w.iloc[-1] ** (1 / years) - 1),
        "volatility": float(sd * math.sqrt(periods)),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float(rolling.min()) if rolling.notna().any() else float("nan"),
    }


def trend_book(prices: pd.DataFrame, spec: dict, vol_target: float, max_leverage: float) -> pd.Series:
    returns = prices.pct_change()
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    month_ends = pd.DatetimeIndex(
        [d for d in prices.index.to_series().groupby(prices.index.to_period("M")).last()]
    )
    for decision in month_ends:
        history = prices.loc[:decision]
        if len(history) < spec["minimum_history_days"]:
            continue
        available = history.columns[history.tail(252).notna().sum() >= 240]
        if len(available) < spec["minimum_assets_held"]:
            continue
        score = pd.Series(0.0, index=available)
        for lookback in spec["lookbacks_trading_days"]:
            if len(history) <= lookback:
                continue
            change = history[available].iloc[-1] / history[available].iloc[-1 - lookback] - 1.0
            score += np.sign(change.fillna(0.0))
        score /= len(spec["lookbacks_trading_days"])
        held = score[score > 0]
        execute = prices.index.searchsorted(decision) + spec["execution_delay_days"]
        if execute >= len(prices.index):
            continue
        weights.iloc[execute:, :] = 0.0
        if held.empty:
            continue
        vol = (returns[available].loc[:decision].tail(126).std(ddof=1) * math.sqrt(252)).reindex(held.index)
        vol = vol.replace(0.0, np.nan).fillna(vol.median())
        w = held.abs() / vol
        w /= w.sum()
        cov = returns[held.index].loc[:decision].tail(252).cov() * 252
        book_vol = float(np.sqrt(max(w.values @ cov.values @ w.values, 1e-8)))
        w = w * min(max_leverage, vol_target / book_vol)
        for asset, value in w.items():
            weights.iloc[execute:, weights.columns.get_loc(asset)] = value

    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    gross = (weights.shift(1) * returns).sum(axis=1)
    idle = (1.0 - weights.sum(axis=1)).clip(lower=0.0)
    cash = returns[spec["cash_asset"]].fillna(0.0) if spec["cash_asset"] in returns else 0.0
    return (gross + idle.shift(1).fillna(0.0) * cash - turnover * spec["cost_bps_per_unit_turnover"] / 1e4).dropna()


def effective_bets(frame: pd.DataFrame) -> float:
    corr = frame.corr().values
    eigenvalues = np.linalg.eigvalsh(corr)
    eigenvalues = eigenvalues[eigenvalues > 1e-10]
    share = eigenvalues / eigenvalues.sum()
    return float(np.exp(-(share * np.log(share)).sum()))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    raw = pd.read_csv(ROOT / config["price_source"], parse_dates=["observation_date"])
    prices = raw.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    start = spec["evaluation_start"]

    grid = {}
    for vol_target, max_leverage in ((0.10, 1.0), (0.15, 1.5), (0.20, 2.0), (0.25, 2.5)):
        net = trend_book(prices, spec, vol_target, max_leverage).loc[start:]
        grid[f"vol_target_{int(vol_target * 100)}_leverage_cap_{max_leverage}"] = {
            **metrics(net),
            "vol_target": vol_target,
            "max_leverage": max_leverage,
        }

    benchmarks = {
        "SPY_buy_and_hold": metrics(prices["SPY"].pct_change().loc[start:]),
        "sixty_forty_SPY_IEF": metrics(
            (0.6 * prices["SPY"].pct_change() + 0.4 * prices["IEF"].pct_change()).loc[start:]
        ),
    }

    reference = trend_book(prices, spec, 0.20, 2.0).loc[start:]
    weekly_trend = (1 + reference).resample("W-FRI").prod() - 1

    dashboard = json.loads((ROOT / config["strategy_source"]).read_text())
    books = {}
    for entry in dashboard["strategies"]:
        record = pd.DataFrame(entry["records"])
        record["date"] = pd.to_datetime(record["date"])
        books[entry["strategy"]["shortName"]] = record.set_index("date")["netReturn"].astype(float)
    equity = pd.DataFrame(books)
    equity.index = equity.index.tz_localize(None) if equity.index.tz else equity.index
    weekly_trend.index = weekly_trend.index.tz_localize(None) if weekly_trend.index.tz else weekly_trend.index

    joined = equity.join(weekly_trend.rename("cross_asset_trend"), how="inner")
    correlations = joined.corr()["cross_asset_trend"].drop("cross_asset_trend")

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_start": start,
        "leverage_grid": grid,
        "benchmarks": benchmarks,
        "regime_returns": {},
        "correlation_to_saved_strategies": {k: float(v) for k, v in correlations.items()},
        "effective_independent_bets": {
            "equity_books_only": effective_bets(joined.drop(columns=["cross_asset_trend"]).dropna(how="all")),
            "with_cross_asset_trend": effective_bets(joined.dropna(how="all")),
        },
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }

    for label, (lo, hi) in {
        "dotcom_2000_2002": ("2000-01-01", "2003-01-01"),
        "gfc_2007_2009": ("2007-10-01", "2009-04-01"),
        "covid_2020": ("2020-02-01", "2020-05-01"),
        "bear_2022": ("2022-01-01", "2023-01-01"),
        "recent_2023_2026": ("2023-01-01", "2026-08-14"),
    }.items():
        window = reference.loc[lo:hi]
        spy_window = prices["SPY"].pct_change().loc[lo:hi]
        if len(window) > 20:
            result["regime_returns"][label] = {
                "cross_asset_trend": float((1 + window).prod() - 1),
                "spy": float((1 + spy_window.dropna()).prod() - 1),
            }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
