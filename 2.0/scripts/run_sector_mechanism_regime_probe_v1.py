#!/usr/bin/env python3
"""Does the sector-rotation engine survive regimes the strategies never saw?

The saved SEC strategies start in 2023 and their stock price panel starts
2022-12-02, so they cannot be pushed back through 2008 or 2020. Their engine can:
multi-horizon cross-sectional momentum, sector balance, volatility targeting,
costs and an execution delay, applied to 9 SPDR sector ETFs with history to 1998.

This measures the mechanism, not any saved strategy. It is a single frozen
configuration run once, with no parameter search.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sector_mechanism_regime_probe_v1.json"
OUTPUT = ROOT / "evidence/sector_mechanism_regime_probe_v1"


def weekly_prices(config: dict) -> pd.DataFrame:
    frame = pd.read_csv(ROOT / config["price_source"], usecols=["observation_date", "ticker", "adjusted_close"])
    frame["observation_date"] = pd.to_datetime(frame["observation_date"])
    wanted = set(config["sectors"]) | {config["benchmark"], config["cash_proxy"]}
    frame = frame[frame.ticker.isin(wanted)]
    wide = frame.pivot_table(index="observation_date", columns="ticker", values="adjusted_close")
    return wide.resample("W-FRI").last().dropna(how="all")


def statistics(returns: pd.Series, periods: int = 52) -> dict:
    values = returns.dropna().astype(float)
    if len(values) < 2:
        return {"weeks": int(len(values)), "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    wealth = (1.0 + values).cumprod()
    years = len(values) / periods
    deviation = values.std(ddof=1)
    return {
        "weeks": int(len(values)),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0,
        "sharpe": float(values.mean() / deviation * math.sqrt(periods)) if deviation else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
    }


def run_engine(prices: pd.DataFrame, config: dict) -> pd.DataFrame:
    engine = config["engine"]
    sectors = [s for s in config["sectors"] if s in prices.columns]
    cash = config["cash_proxy"]
    returns = prices.pct_change()

    # rank consensus across horizons, all strictly lagged
    ranks = []
    for horizon in engine["horizons_weeks"]:
        trailing = prices[sectors] / prices[sectors].shift(horizon) - 1.0
        ranks.append(trailing.rank(axis=1, ascending=True))
    consensus = sum(ranks) / len(ranks)

    # a sector must also have a positive average trailing return to be eligible
    average_trailing = sum(prices[sectors] / prices[sectors].shift(h) - 1.0 for h in engine["horizons_weeks"]) / len(engine["horizons_weeks"])

    top_n = int(engine["select_top_n"])
    target = pd.DataFrame(0.0, index=prices.index, columns=sectors + [cash])
    for stamp in prices.index:
        row = consensus.loc[stamp]
        if row.isna().all():
            target.loc[stamp, cash] = 1.0
            continue
        eligible = row.dropna()
        if engine["require_positive_consensus"]:
            positive = average_trailing.loc[stamp]
            eligible = eligible[[s for s in eligible.index if positive.get(s, np.nan) > 0.0]]
        if eligible.empty:
            target.loc[stamp, cash] = 1.0
            continue
        picks = eligible.nlargest(min(top_n, len(eligible))).index
        target.loc[stamp, picks] = 1.0 / len(picks)
        target.loc[stamp, cash] = 1.0 - target.loc[stamp, picks].sum()

    # volatility scaler on the unscaled sleeve, lagged
    sleeve_return = (target[sectors].shift(1) * returns[sectors]).sum(axis=1)
    realised = sleeve_return.rolling(engine["volatility_lookback_weeks"]).std(ddof=1) * math.sqrt(52)
    scaler = (engine["volatility_target_annual"] / realised).clip(upper=engine["scaler_maximum"]).shift(1).fillna(0.0)

    delay = int(engine["execution_delay_weeks"])
    held = target.shift(delay).fillna(0.0)
    scaled = held[sectors].mul(scaler, axis=0)
    scaled[cash] = 1.0 - scaled[sectors].sum(axis=1)

    turnover = scaled.diff().abs().sum(axis=1).fillna(0.0) / 2.0
    cost = turnover * engine["cost_bps_per_unit_turnover"] / 10000.0
    gross = (scaled * returns[scaled.columns]).sum(axis=1)
    net = gross - cost

    return pd.DataFrame({
        "gross": gross, "cost": cost, "net": net, "turnover": turnover,
        "scaler": scaler, "sector_weight": scaled[sectors].sum(axis=1),
        "benchmark": returns[config["benchmark"]],
    }).dropna(subset=["net"])


def main() -> int:
    config = json.loads(CONFIG.read_text())
    prices = weekly_prices(config)
    path = run_engine(prices, config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    path.to_csv(OUTPUT / "weekly_path.csv")

    rows = []
    for name, (start, end) in config["regimes"].items():
        window = path.loc[start:end]
        if window.empty:
            continue
        engine_stats = statistics(window.net)
        bench_stats = statistics(window.benchmark)
        rows.append({
            "regime": name, "start": start, "end": end, "weeks": engine_stats["weeks"],
            "engine_total": engine_stats["total_return"], "engine_cagr": engine_stats["cagr"],
            "engine_sharpe": engine_stats["sharpe"], "engine_drawdown": engine_stats["max_drawdown"],
            "spy_total": bench_stats["total_return"], "spy_cagr": bench_stats["cagr"],
            "spy_drawdown": bench_stats["max_drawdown"],
            "excess_total": engine_stats["total_return"] - bench_stats["total_return"],
            "average_sector_weight": float(window.sector_weight.mean()),
        })
    table = pd.DataFrame(rows)
    table.to_csv(OUTPUT / "regime_table.csv", index=False)

    full_engine = statistics(path.net)
    full_bench = statistics(path.benchmark)
    bears = [r for r in rows if r["regime"] in {"dotcom_crash", "global_financial_crisis", "covid_crash", "bear_2022"}]
    result = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "honest_scope": config["honest_scope"],
        "sample": {"start": str(path.index.min().date()), "end": str(path.index.max().date()), "weeks": int(len(path))},
        "full_sample": {"engine": full_engine, "benchmark": full_bench},
        "regimes": rows,
        "bear_summary": {
            "count": len(bears),
            "engine_beat_spy": int(sum(1 for r in bears if r["excess_total"] > 0)),
            "average_engine_drawdown": float(np.mean([r["engine_drawdown"] for r in bears])) if bears else 0.0,
            "average_spy_drawdown": float(np.mean([r["spy_drawdown"] for r in bears])) if bears else 0.0,
        },
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    print(f"sample {result['sample']['start']} to {result['sample']['end']}  ({result['sample']['weeks']} weeks)\n")
    print(f"  {'regime':<28}{'weeks':>6}{'engine':>11}{'SPY':>10}{'excess':>10}{'eng DD':>9}{'SPY DD':>9}{'exposure':>10}")
    for r in rows:
        print(f"  {r['regime']:<28}{r['weeks']:>6}{100*r['engine_total']:>10.1f}%{100*r['spy_total']:>9.1f}%"
              f"{100*r['excess_total']:>9.1f}%{100*r['engine_drawdown']:>8.1f}%{100*r['spy_drawdown']:>8.1f}%{100*r['average_sector_weight']:>9.0f}%")
    print(f"\n  FULL SAMPLE  engine {100*full_engine['cagr']:.2f}% CAGR, Sharpe {full_engine['sharpe']:.2f}, DD {100*full_engine['max_drawdown']:.1f}%")
    print(f"               SPY    {100*full_bench['cagr']:.2f}% CAGR, Sharpe {full_bench['sharpe']:.2f}, DD {100*full_bench['max_drawdown']:.1f}%")
    b = result["bear_summary"]
    print(f"\n  Bear regimes: engine beat SPY in {b['engine_beat_spy']} of {b['count']}; "
          f"avg engine DD {100*b['average_engine_drawdown']:.1f}% vs SPY {100*b['average_spy_drawdown']:.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
