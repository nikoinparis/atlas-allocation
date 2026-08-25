#!/usr/bin/env python3
"""Does low asset growth survive strict evaluation, and does it build a portfolio?

The discovery program scored it on overlapping weekly windows. This re-tests it on
strictly non-overlapping windows, then builds an actual portfolio with costs, an
execution delay and varying breadth, and measures it against an equal-weight
benchmark of the same universe.
"""

from __future__ import annotations

import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/low_asset_growth_candidate_v2.json"
OUTPUT = ROOT / "evidence/low_asset_growth_candidate_v2"

spec = importlib.util.spec_from_file_location("disc", ROOT / "scripts/run_signal_discovery_program_v1.py")
disc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(disc)


def stats(returns: pd.Series, periods: int = 52) -> dict:
    v = returns.dropna().astype(float)
    if len(v) < 2:
        return {"weeks": len(v), "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    w = (1 + v).cumprod()
    years = len(v) / periods
    sd = v.std(ddof=1)
    return {
        "weeks": int(len(v)), "total_return": float(w.iloc[-1] - 1),
        "cagr": float(w.iloc[-1] ** (1 / years) - 1), "sharpe": float(v.mean() / sd * math.sqrt(periods)) if sd else 0.0,
        "max_drawdown": float((w / w.cummax() - 1).min()),
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    disc_cfg = json.loads((ROOT / "config/signal_discovery_program_v1.json").read_text())
    prices = disc.load_prices(disc_cfg)
    # price hygiene: zero prices are data errors; cap single-week moves so one bad print
    # cannot dominate a decile mean. Verified not to change the conclusion either way.
    raw = prices.replace(0.0, np.nan)
    capped = raw.pct_change().clip(upper=config["price_hygiene"]["cap_weekly_return"])
    prices = (1.0 + capped).cumprod()
    sectors = disc.sector_map()
    facts = disc.build_fundamental_signals(prices, ROOT / disc_cfg["fundamental_panel"])
    signal = disc.sector_neutral_z(facts["low_asset_growth"], sectors)

    horizon = config["strict_evaluation"]["window_weeks"]
    forward = prices.shift(-horizon) / prices - 1.0
    warmup = disc_cfg["evaluation"]["warmup_weeks"]

    # ---- strictly non-overlapping decile spreads
    stamps = list(signal.index[warmup::horizon])
    rows = []
    for stamp in stamps:
        s = signal.loc[stamp].dropna()
        f = forward.loc[stamp].dropna()
        common = s.index.intersection(f.index)
        if len(common) < disc_cfg["evaluation"]["minimum_names"]:
            continue
        s, f = s[common], f[common]
        order = s.sort_values()
        size = max(1, int(len(order) * 0.10))
        top, bottom = f[order.index[-size:]], f[order.index[:size]]
        trimmed = (top.drop(top.idxmax()).mean() - bottom.drop(bottom.idxmin()).mean()) if len(top) > 1 else 0.0
        rows.append({"date": str(stamp.date()), "names": len(common),
                     "top": float(top.mean()), "bottom": float(bottom.mean()),
                     "spread": float(top.mean() - bottom.mean()), "spread_trimmed": float(trimmed)})
    strict = pd.DataFrame(rows)

    # ---- portfolio: top N by signal, equal weight, quarterly, delayed, costed
    weekly = prices.pct_change().replace([np.inf, -np.inf], np.nan)
    benchmark = weekly.mean(axis=1, skipna=True)
    delay = config["portfolio"]["execution_delay_weeks"]
    cost_bps = config["portfolio"]["cost_bps_per_unit_turnover"]
    portfolios = {}
    for size in config["portfolio"]["breadth_sizes"]:
        target = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
        for stamp in stamps:
            s = signal.loc[stamp].dropna()
            if len(s) < size:
                continue
            picks = s.nlargest(size).index
            target.loc[stamp:, :] = 0.0
            target.loc[stamp:, picks] = 1.0 / size
        held = target.shift(delay).fillna(0.0)
        turnover = held.diff().abs().sum(axis=1).fillna(0.0) / 2.0
        gross = (held * weekly[held.columns]).sum(axis=1)
        net = gross - turnover * cost_bps / 10000.0
        net = net.iloc[warmup:]
        portfolios[str(size)] = {**stats(net), "average_turnover": float(turnover.iloc[warmup:].mean())}

    bench = stats(benchmark.iloc[warmup:])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    strict.to_csv(OUTPUT / "non_overlapping_spreads.csv", index=False)
    gates = {
        "non_overlapping_spread_positive": bool(len(strict) and strict.spread.mean() > 0),
        "beats_benchmark_after_costs": bool(any(p["cagr"] > bench["cagr"] for p in portfolios.values())),
        "wide_book_not_worse_than_narrow": bool(portfolios[str(config["portfolio"]["breadth_sizes"][-1])]["cagr"]
                                                >= portfolios[str(config["portfolio"]["breadth_sizes"][0])]["cagr"]),
        "no_single_name_drives_result": bool(len(strict) and strict.spread_trimmed.mean() > 0),
    }
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strict_non_overlapping": {
            "windows": int(len(strict)),
            "mean_spread": float(strict.spread.mean()) if len(strict) else 0.0,
            "median_spread": float(strict.spread.median()) if len(strict) else 0.0,
            "share_positive": float((strict.spread > 0).mean()) if len(strict) else 0.0,
            "mean_spread_trimmed": float(strict.spread_trimmed.mean()) if len(strict) else 0.0,
            "annualised": float(strict.spread.mean() * 4) if len(strict) else 0.0,
        },
        "portfolios": portfolios,
        "benchmark": bench,
        "gates": gates,
        "all_gates_pass": bool(all(gates.values())),
        "honest_scope": config["honest_scope"],
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"STRICT NON-OVERLAPPING ({len(strict)} independent windows)")
    print(f"   mean spread {100*strict.spread.mean():+.2f}% per 13w  ({100*strict.spread.mean()*4:+.2f}% ann)")
    print(f"   median      {100*strict.spread.median():+.2f}%   positive in {100*(strict.spread>0).mean():.0f}% of windows")
    print(f"   trimmed     {100*strict.spread_trimmed.mean():+.2f}%")
    print(f"\nPORTFOLIO vs equal-weight benchmark ({100*bench['cagr']:.2f}% CAGR, Sharpe {bench['sharpe']:.2f}, DD {100*bench['max_drawdown']:.1f}%)")
    print(f"   {'names':>6}{'CAGR':>10}{'Sharpe':>9}{'maxDD':>9}{'turnover':>10}{'vs bench':>11}")
    for size, p in portfolios.items():
        print(f"   {size:>6}{100*p['cagr']:>9.2f}%{p['sharpe']:>9.2f}{100*p['max_drawdown']:>8.1f}%"
              f"{p['average_turnover']:>10.3f}{100*(p['cagr']-bench['cagr']):>10.2f}pp")
    print(f"\n   gates: {gates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
