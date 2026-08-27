#!/usr/bin/env python3
"""Does picking the best book beat holding all of them?

Step 196 diagnosed the project's central problem as selection: candidates chosen
because they performed well in the window they are then measured on. Step 202 put
a number on it. This tests the cheapest structural defence, which is to stop
picking.

The rule under test uses only trailing information at each decision, charges for
switching, and sweeps k without selecting a value. Three controls bracket it: an
oracle that cannot be implemented, equal weighting, and random choice.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/bagged_selection_v1.json"
OUTPUT = ROOT / "evidence/bagged_selection_v1"


def metrics(net: pd.Series, periods: int = 52) -> dict:
    v = net.dropna()
    w = (1 + v).cumprod()
    sd = v.std(ddof=1)
    return {
        "weeks": int(len(v)),
        "cagr": float(w.iloc[-1] ** (periods / len(v)) - 1),
        "volatility": float(sd * math.sqrt(periods)),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
    }


def run_rule(returns: pd.DataFrame, k: int, lookback: int, burn_in: int, cost_bps: float) -> pd.Series:
    dates = returns.index
    held = pd.Series(0.0, index=returns.columns)
    out = {}
    for position in range(burn_in, len(dates)):
        decision = dates[position]
        # Strictly-prior information only.
        window = returns.iloc[position - lookback:position]
        score = (1 + window).prod() - 1
        chosen = score.nlargest(k).index
        target = pd.Series(0.0, index=returns.columns)
        target[chosen] = 1.0 / k
        turnover = float((target - held).abs().sum())
        realised = float((target * returns.loc[decision].fillna(0.0)).sum())
        out[decision] = realised - turnover * cost_bps / 1e4
        held = target
    return pd.Series(out).sort_index()


def main() -> int:
    config = json.loads(CONFIG.read_text())
    spec = config["declared_before_running"]

    dashboard = json.loads((ROOT / config["strategy_source"]).read_text())
    books = {}
    for entry in dashboard["strategies"]:
        frame = pd.DataFrame(entry["records"])
        frame["date"] = pd.to_datetime(frame["date"])
        books[entry["strategy"]["shortName"]] = frame.set_index("date")["netReturn"].astype(float)
    returns = pd.DataFrame(books).dropna()
    returns.index = returns.index.tz_localize(None) if returns.index.tz else returns.index

    burn_in, cost = spec["burn_in_weeks"], spec["switching_cost_bps"]
    evaluated = returns.index[burn_in:]

    results = {}
    for lookback in spec["lookback_weeks"]:
        for k in spec["k_values"]:
            series = run_rule(returns, k, lookback, burn_in, cost)
            results[f"top{k}_lookback{lookback}w"] = {"k": k, "lookback_weeks": lookback, **metrics(series)}

    controls = {}
    full_sample_best = ((1 + returns).prod() - 1).idxmax()
    controls["oracle_best"] = {"book": full_sample_best, **metrics(returns.loc[evaluated, full_sample_best])}
    controls["equal_weight_all"] = metrics(returns.loc[evaluated].mean(axis=1))

    rng = np.random.default_rng(12345)
    draws = []
    for _ in range(500):
        picks = rng.integers(0, returns.shape[1], size=len(evaluated))
        series = pd.Series(
            [returns.loc[d].iloc[p] for d, p in zip(evaluated, picks)], index=evaluated
        )
        draws.append(metrics(series))
    controls["random_pick"] = {
        "draws": len(draws),
        "median_cagr": float(np.median([d["cagr"] for d in draws])),
        "median_sharpe": float(np.median([d["sharpe"] for d in draws])),
        "median_max_drawdown": float(np.median([d["max_drawdown"] for d in draws])),
        "cagr_5th_percentile": float(np.percentile([d["cagr"] for d in draws], 5)),
        "cagr_95th_percentile": float(np.percentile([d["cagr"] for d in draws], 95)),
    }

    by_k = {}
    for k in spec["k_values"]:
        entries = [v for v in results.values() if v["k"] == k]
        by_k[str(k)] = {
            "mean_sharpe_across_lookbacks": float(np.mean([e["sharpe"] for e in entries])),
            "mean_cagr_across_lookbacks": float(np.mean([e["cagr"] for e in entries])),
            "mean_max_drawdown_across_lookbacks": float(np.mean([e["max_drawdown"] for e in entries])),
        }

    result = {
        "experiment": config["experiment"],
        "status": config["status"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "common_window": {
            "weeks_total": int(len(returns)),
            "weeks_evaluated": int(len(evaluated)),
            "first": str(evaluated[0].date()),
            "last": str(evaluated[-1].date()),
        },
        "candidates": list(returns.columns),
        "rules": results,
        "summary_by_k": by_k,
        "controls": controls,
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2) + "\n")

    print(f"common window: {result['common_window']['weeks_evaluated']} weeks evaluated "
          f"({result['common_window']['first']} to {result['common_window']['last']})\n")
    print(f"{'rule':28s}{'CAGR':>9s}{'Sharpe':>8s}{'maxDD':>9s}")
    for name, entry in results.items():
        print(f"{name:28s}{entry['cagr']*100:8.2f}%{entry['sharpe']:8.2f}{entry['max_drawdown']*100:8.2f}%")
    print()
    print(f"{'mean across lookbacks':28s}{'CAGR':>9s}{'Sharpe':>8s}{'maxDD':>9s}")
    for k, entry in by_k.items():
        print(f"  hold top {k:22s}{entry['mean_cagr_across_lookbacks']*100:8.2f}%"
              f"{entry['mean_sharpe_across_lookbacks']:8.2f}{entry['mean_max_drawdown_across_lookbacks']*100:8.2f}%")
    print()
    print(f"{'control: oracle best':28s}{controls['oracle_best']['cagr']*100:8.2f}%"
          f"{controls['oracle_best']['sharpe']:8.2f}{controls['oracle_best']['max_drawdown']*100:8.2f}%"
          f"   ({controls['oracle_best']['book']})")
    print(f"{'control: equal weight all':28s}{controls['equal_weight_all']['cagr']*100:8.2f}%"
          f"{controls['equal_weight_all']['sharpe']:8.2f}{controls['equal_weight_all']['max_drawdown']*100:8.2f}%")
    print(f"{'control: random pick (median)':28s}{controls['random_pick']['median_cagr']*100:8.2f}%"
          f"{controls['random_pick']['median_sharpe']:8.2f}{controls['random_pick']['median_max_drawdown']*100:8.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
