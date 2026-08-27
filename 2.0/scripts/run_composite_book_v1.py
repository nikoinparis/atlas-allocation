#!/usr/bin/env python3
"""Put the three surviving results together and see whether they add up.

Nothing new is searched here. Step 203 said stop selecting, Steps 200 and 201
found an independent sleeve, Step 198 found a drawdown rule that works on the
book's own path. Each was measured alone. This measures them together, which is
the only question that decides whether any of it improves the portfolio.

The drawdown threshold is copied from Step 198 unchanged and the trend sleeve is
taken at its lowest leverage setting, because that is the only point on the grid
that is not itself a decision.
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

CONFIG = ROOT / "config/composite_book_v1.json"
OUTPUT = ROOT / "evidence/composite_book_v1"


def metrics(net: pd.Series, periods: int = 52) -> dict:
    v = net.dropna()
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    rolling = w / w.shift(periods) - 1.0
    return {
        "weeks": int(len(v)),
        "cagr": float(w.iloc[-1] ** (periods / len(v)) - 1),
        "volatility": float(sd * math.sqrt(periods)),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float(rolling.min()) if rolling.notna().any() else float("nan"),
    }


def trend_weekly(prices: pd.DataFrame) -> pd.Series:
    """Step 201 sleeve, lowest leverage setting, rebuilt here rather than cached."""
    returns = prices.pct_change()
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    month_ends = pd.DatetimeIndex(
        [d for d in prices.index.to_series().groupby(prices.index.to_period("M")).last()]
    )
    for decision in month_ends:
        history = prices.loc[:decision]
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
        execute = prices.index.searchsorted(decision) + 1
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
        w = w * min(1.0, 0.10 / book_vol)
        for asset, value in w.items():
            weights.iloc[execute:, weights.columns.get_loc(asset)] = value
    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    gross = (weights.shift(1) * returns).sum(axis=1)
    idle = (1.0 - weights.sum(axis=1)).clip(lower=0.0)
    cash = returns["BIL"].fillna(0.0) if "BIL" in returns else 0.0
    daily = (gross + idle.shift(1).fillna(0.0) * cash - turnover * 10.0 / 1e4).dropna()
    return (1 + daily).resample("W-FRI").prod() - 1


def apply_drawdown_overlay(net: pd.Series, trigger: float, gated: float, cost_bps: float) -> pd.Series:
    """React to the book's own path: exposure is decided from realised wealth only."""
    exposure, wealth, peak = [], 1.0, 1.0
    previous = 1.0
    out = []
    for value in net:
        drawdown = wealth / peak - 1.0
        current = gated if drawdown <= -trigger else 1.0
        realised = value * current - abs(current - previous) * cost_bps / 1e4
        out.append(realised)
        exposure.append(current)
        previous = current
        wealth *= 1 + realised
        peak = max(peak, wealth)
    return pd.Series(out, index=net.index)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    dashboard = json.loads((ROOT / config["strategy_source"]).read_text())
    books = {}
    for entry in dashboard["strategies"]:
        frame = pd.DataFrame(entry["records"])
        frame["date"] = pd.to_datetime(frame["date"])
        books[entry["strategy"]["shortName"]] = frame.set_index("date")["netReturn"].astype(float)
    equity = pd.DataFrame(books)
    equity.index = equity.index.tz_localize(None) if equity.index.tz else equity.index

    raw = pd.read_csv(ROOT / config["price_source"], parse_dates=["observation_date"])
    prices = raw.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    trend = trend_weekly(prices)
    trend.index = trend.index.tz_localize(None) if trend.index.tz else trend.index

    equity_composite = equity.dropna().mean(axis=1)
    joined = pd.DataFrame({"equity": equity_composite}).join(trend.rename("trend"), how="inner").dropna()

    overlay = spec["drawdown_overlay"]
    cost = spec["cost_bps_per_unit_turnover"]

    results = {}
    for weight in spec["sleeve_weights"]:
        blend = weight["equity"] * joined["equity"] + weight["trend"] * joined["trend"]
        gated = apply_drawdown_overlay(blend, overlay["trigger_drawdown"], overlay["exposure_when_triggered"], cost)
        results[weight["name"]] = {
            "equity_weight": weight["equity"],
            "trend_weight": weight["trend"],
            "without_overlay": metrics(blend),
            "with_overlay": metrics(gated),
        }

    window = joined.index
    references = {
        f"single_book::{name}": metrics(series.reindex(window).dropna())
        for name, series in books.items()
    }
    references["trend_sleeve_alone"] = metrics(joined["trend"])
    references["best_single_book_by_sharpe"] = max(
        ((k, v) for k, v in references.items() if k.startswith("single_book")),
        key=lambda kv: kv[1]["sharpe"],
    )[0]

    ledger = TrialLedger(ROOT / "data/trial_ledger_v1/trials.jsonl")
    registered = 0
    if ledger.count(family="composite_book") == 0:
        registered = ledger.append([
            Trial("composite_book", config["experiment"], f"{name}::{variant}",
                  "sharpe_and_max_drawdown", config["strategy_source"],
                  outcome="reported_not_selected", metric=float(entry[variant]["sharpe"]))
            for name, entry in results.items()
            for variant in ("without_overlay", "with_overlay")
        ])

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "common_window": {"weeks": int(len(joined)), "first": str(window[0].date()), "last": str(window[-1].date())},
        "blends": results,
        "references": references,
        "trials_registered": registered,
        "trial_ledger_total": ledger.count(),
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"common window: {len(joined)} weeks, {window[0].date()} to {window[-1].date()}\n")
    print(f"{'blend':22s}{'overlay':>9s}{'CAGR':>10s}{'vol':>8s}{'Sharpe':>8s}{'maxDD':>9s}{'worst1Y':>10s}")
    for name, entry in results.items():
        for variant, label in (("without_overlay", "no"), ("with_overlay", "yes")):
            m = entry[variant]
            print(f"{name:22s}{label:>9s}{m['cagr']*100:9.2f}%{m['volatility']*100:7.1f}%"
                  f"{m['sharpe']:8.2f}{m['max_drawdown']*100:8.2f}%{m['worst_rolling_1y']*100:9.2f}%")
    print(f"\n{'reference':22s}{'':>9s}{'CAGR':>10s}{'vol':>8s}{'Sharpe':>8s}{'maxDD':>9s}{'worst1Y':>10s}")
    for name, m in references.items():
        if not isinstance(m, dict):
            continue
        print(f"{name[:22]:22s}{'':>9s}{m['cagr']*100:9.2f}%{m['volatility']*100:7.1f}%"
              f"{m['sharpe']:8.2f}{m['max_drawdown']*100:8.2f}%{m['worst_rolling_1y']*100:9.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
