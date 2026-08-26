#!/usr/bin/env python3
"""What is the best portfolio obtainable with no selection skill?

Every prior program in this project varied which names to hold. The decile study
showed that space is empty here. This holds selection constant at "everything
priced" and varies only construction, which Step 190 showed moves the entire
outcome distribution rather than just its variance.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/portfolio_construction_tournament_v1.json"
OUTPUT = ROOT / "evidence/portfolio_construction_tournament_v1"


def metrics(net: pd.Series, turnover: pd.Series, periods: int = 52) -> dict:
    v = net.dropna()
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    rolling = w / w.shift(52) - 1.0
    return {
        "weeks": int(len(v)),
        "cagr": float(w.iloc[-1] ** (1 / years) - 1),
        "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
        "worst_rolling_52w": float(rolling.min()) if rolling.notna().any() else float("nan"),
        "fifth_percentile_52w": float(rolling.quantile(0.05)) if rolling.notna().any() else float("nan"),
        "average_turnover": float(turnover.mean()),
    }


def run(weights: pd.DataFrame, returns: pd.DataFrame, delay: int, cost_bps: float, warmup: int) -> dict:
    held = weights.shift(delay).fillna(0.0)
    turnover = held.diff().abs().sum(axis=1).fillna(0.0) / 2.0
    gross = (held * returns.fillna(0.0)).sum(axis=1)
    net = (gross - turnover * cost_bps / 10000.0).iloc[warmup:]
    return metrics(net, turnover.iloc[warmup:])


def main() -> int:
    config = json.loads(CONFIG.read_text())
    ev = config["evaluation"]
    prices = pd.read_csv(ROOT / ev["price_source"], index_col=0)
    prices.index = pd.to_datetime(prices.index)
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan)
    live = prices.notna()
    vol = returns.rolling(52, min_periods=40).std(ddof=1).shift(1)
    volrank = vol.rank(axis=1, pct=True)
    delay, cost, warmup = ev["execution_delay_weeks"], ev["cost_bps_per_unit_turnover"], ev["warmup_weeks"]

    def normalise(mask_or_weights: pd.DataFrame) -> pd.DataFrame:
        return mask_or_weights.div(mask_or_weights.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    equal = normalise(live.astype(float))
    results = {}

    results["equal_weight"] = run(equal, returns, delay, cost, warmup)

    inv_vol = normalise((1.0 / vol.replace(0, np.nan)).where(live).fillna(0.0))
    results["inverse_volatility"] = run(inv_vol, returns, delay, cost, warmup)

    inv_var = normalise((1.0 / vol.replace(0, np.nan) ** 2).where(live).fillna(0.0))
    results["inverse_variance"] = run(inv_var, returns, delay, cost, warmup)

    base_gross = (equal.shift(delay).fillna(0.0) * returns.fillna(0.0)).sum(axis=1)
    realised = base_gross.rolling(26).std(ddof=1) * math.sqrt(52)
    scaler = (0.15 / realised).clip(upper=1.0).shift(1).fillna(0.0)
    results["volatility_targeted"] = run(equal.mul(scaler, axis=0), returns, delay, cost, warmup)

    wealth = (1 + base_gross.fillna(0.0)).cumprod()
    underwater = wealth / wealth.cummax() - 1.0
    dd_scaler = pd.Series(np.where(underwater.shift(1) < -0.08, 0.5, 1.0), index=equal.index)
    results["drawdown_controlled"] = run(equal.mul(dd_scaler, axis=0), returns, delay, cost, warmup)

    results["exclude_top_vol_decile"] = run(normalise(live.astype(float).where(volrank <= 0.90, 0.0)),
                                            returns, delay, cost, warmup)
    results["exclude_bottom_vol_decile"] = run(normalise(live.astype(float).where(volrank >= 0.10, 0.0)),
                                               returns, delay, cost, warmup)

    capped = equal.clip(upper=0.01)
    results["capped_equal_weight"] = run(normalise(capped), returns, delay, cost, warmup)

    base = results["equal_weight"]
    for name, r in results.items():
        r["cagr_vs_baseline"] = r["cagr"] - base["cagr"]
        r["drawdown_vs_baseline"] = r["max_drawdown"] - base["max_drawdown"]
        r["beats_baseline_on_both"] = bool(r["cagr"] > base["cagr"] and r["max_drawdown"] > base["max_drawdown"])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).T.to_csv(OUTPUT / "construction_variants.csv")
    winners = [n for n, r in results.items() if r["beats_baseline_on_both"] and n != "equal_weight"]
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "variants": results,
        "baseline": "equal_weight",
        "variants_beating_baseline_on_return_and_drawdown": winners,
        "caveat": ("One 2023-2026 window, no forward evidence, and no selection skill assumed anywhere. "
                   "These are structural rules with nothing fitted, which limits overfitting but does not "
                   "remove regime dependence."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"  {'construction':<28}{'CAGR':>9}{'Sharpe':>8}{'maxDD':>9}{'worst 52w':>11}{'5th pct 52w':>13}{'turnover':>10}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["sharpe"]):
        mark = " *" if r["beats_baseline_on_both"] and name != "equal_weight" else ("  <- baseline" if name == "equal_weight" else "")
        print(f"  {name:<28}{100*r['cagr']:>8.2f}%{r['sharpe']:>8.2f}{100*r['max_drawdown']:>8.1f}%"
              f"{100*r['worst_rolling_52w']:>10.1f}%{100*r['fifth_percentile_52w']:>12.1f}%{r['average_turnover']:>10.4f}{mark}")
    print(f"\n  beating the baseline on BOTH return and drawdown: {winners if winners else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
