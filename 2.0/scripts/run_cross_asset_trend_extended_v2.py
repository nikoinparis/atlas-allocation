#!/usr/bin/env python3
"""Push the sleeve back to 1993 and find out what the volatility target is doing.

Step 200 started in 2007 because that is when the bond, commodity, FX and
international sleeves all exist. Running back to 1993 is worth doing anyway, but
only if the shrinking universe is reported rather than averaged away: before 2007
this is progressively just an equity book, and a pre-2007 number compared against
a post-2007 number measures the opportunity set as much as the rule.

Three variants separate the rule from its sizing: unconditional targeting,
conditional targeting that only intervenes when realised volatility is high, and
no targeting at all as the control.

Still a probe. No point on the leverage grid is selected.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/cross_asset_trend_extended_v2.json"
OUTPUT = ROOT / "evidence/cross_asset_trend_extended_v2"


def metrics(net: pd.Series, turnover: pd.Series | None = None, periods: int = 252) -> dict:
    v = net.dropna()
    if len(v) < periods:
        return {"observations": int(len(v)), "insufficient": True}
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    rolling = w / w.shift(periods) - 1.0
    out = {
        "observations": int(len(v)),
        "cagr": float(w.iloc[-1] ** (periods / len(v)) - 1),
        "volatility": float(sd * math.sqrt(periods)),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_1y": float(rolling.min()) if rolling.notna().any() else float("nan"),
    }
    if turnover is not None:
        t = turnover.reindex(v.index).fillna(0.0)
        out["annual_turnover"] = float(t.sum() / (len(v) / periods))
    return out


def build(prices: pd.DataFrame, spec: dict, vol_target: float, max_leverage: float, variant: str):
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

        if variant == "no_vol_target":
            scale = min(max_leverage, 1.0)
        elif variant == "conditional":
            # Intervene only when realised volatility is above target; leave a
            # quiet book alone rather than levering it up every month.
            scale = min(max_leverage, vol_target / book_vol) if book_vol > vol_target else min(max_leverage, 1.0)
        else:
            scale = min(max_leverage, vol_target / book_vol)
        w = w * scale
        for asset, value in w.items():
            weights.iloc[execute:, weights.columns.get_loc(asset)] = value

    turnover = weights.diff().abs().sum(axis=1).fillna(0.0)
    gross = (weights.shift(1) * returns).sum(axis=1)
    idle = (1.0 - weights.sum(axis=1)).clip(lower=0.0)
    cash = returns[spec["cash_asset"]].fillna(0.0) if spec["cash_asset"] in returns else 0.0
    net = (gross + idle.shift(1).fillna(0.0) * cash - turnover * spec["cost_bps_per_unit_turnover"] / 1e4)
    return net.dropna(), turnover


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    raw = pd.read_csv(ROOT / config["price_source"], parse_dates=["observation_date"])
    prices = raw.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()

    # How many assets does the rule actually have to choose from, over time?
    coverage = {}
    for year in range(1994, 2027):
        stamp = pd.Timestamp(f"{year}-06-30")
        if stamp > prices.index[-1]:
            continue
        window = prices.loc[:stamp].tail(252)
        coverage[str(year)] = int((window.notna().sum() >= 240).sum())

    results: dict[str, dict] = {}
    for variant in ("unconditional", "conditional", "no_vol_target"):
        for vol_target, max_leverage in spec["leverage_grid"]:
            net, turnover = build(prices, spec, vol_target, max_leverage, variant)
            key = f"{variant}_vt{int(vol_target * 100)}_lev{max_leverage}"
            results[key] = {
                "variant": variant, "vol_target": vol_target, "max_leverage": max_leverage,
                "windows": {
                    name: metrics(net.loc[start:], turnover.loc[start:])
                    for name, start in spec["windows"].items()
                },
            }
            if variant == "no_vol_target":
                break  # the control has no target to sweep

    benchmarks = {}
    for name, start in spec["windows"].items():
        benchmarks[name] = {
            "SPY_buy_and_hold": metrics(prices["SPY"].pct_change().loc[start:]),
            "sixty_forty_SPY_IEF": metrics(
                (0.6 * prices["SPY"].pct_change() + 0.4 * prices["IEF"].pct_change()).loc[start:]
            ),
        }

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "assets_available_by_year": coverage,
        "variants": results,
        "benchmarks_by_window": benchmarks,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print("assets available:", {k: v for k, v in coverage.items() if k in ("1994", "1999", "2003", "2007", "2015", "2026")})
    print()
    for window in spec["windows"]:
        print(f"--- window {window} (from {spec['windows'][window]}) ---")
        b = benchmarks[window]["SPY_buy_and_hold"]
        if not b.get("insufficient"):
            print(f"  {'SPY buy and hold':40s} CAGR {b['cagr']*100:7.2f}%  Sh {b['sharpe']:5.2f}  maxDD {b['max_drawdown']*100:7.2f}%")
        for key, entry in results.items():
            m = entry["windows"][window]
            if m.get("insufficient"):
                continue
            print(f"  {key:40s} CAGR {m['cagr']*100:7.2f}%  Sh {m['sharpe']:5.2f}  "
                  f"maxDD {m['max_drawdown']*100:7.2f}%  turn {m.get('annual_turnover', float('nan')):5.2f}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
