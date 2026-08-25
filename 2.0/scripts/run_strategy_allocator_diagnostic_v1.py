#!/usr/bin/env python3
"""Run one frozen, retrospective strategy-allocation diagnostic."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_return_improvement import CASH, causal_strategy_allocator


CONFIG = ROOT / "config/sec_return_improvement_program_v1.json"
FROZEN = ROOT / "evidence/sec_return_improvement_program_v1/frozen_config.json"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/strategy_allocator_diagnostic_v1"
SLEEVES = {
    "etf_incumbent": "candidate-return-first-60-40-forward-v1",
    "growth_top5": "sec-growth-survivorship-aware-v1",
    "dynamic_breadth20": "sec-cash-conversion-breadth20-dynamic-v1",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(returns: pd.Series) -> dict[str, float | int | str]:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    wealth = (1.0 + values).cumprod()
    years = len(values) / 52.0
    annual = float(values.mean() * 52.0)
    volatility = float(values.std(ddof=1) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": int(len(values)),
        "start": str(values.index.min().date()),
        "end": str(values.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe_zero_rf": annual / volatility if volatility else 0.0,
        "max_drawdown": float(drawdown.min()),
    }


def main() -> int:
    if not FROZEN.exists() or sha256(CONFIG) != sha256(FROZEN):
        raise RuntimeError("return-improvement protocol is not frozen or its config changed")
    config = json.loads(FROZEN.read_text())["strategy_allocator"]
    dashboard = json.loads(DASHBOARD.read_text())
    by_id = {item["strategy"]["id"]: item for item in dashboard["strategies"]}
    series = {}
    for name, strategy_id in SLEEVES.items():
        records = by_id[strategy_id]["records"]
        series[name] = pd.Series(
            [float(row["netReturn"]) for row in records],
            index=pd.to_datetime([row["date"] for row in records]),
            name=name,
        )
    returns = pd.concat(series, axis=1).dropna()
    weights = causal_strategy_allocator(
        returns,
        lookback_weeks=int(config["lookback_weeks"]),
        minimum_history_weeks=int(config["minimum_history_weeks"]),
        momentum_lookbacks_weeks=config["momentum_lookbacks_weeks"],
        maximum_sleeve_weight=float(config["maximum_sleeve_weight"]),
        minimum_active_sleeve_weight=float(config["minimum_active_sleeve_weight"]),
        independence_penalty=float(config["independence_penalty"]),
    )
    sleeve_weights = weights.drop(columns=[CASH])
    turnover = sleeve_weights.diff().abs().sum(axis=1).mul(0.5)
    if len(turnover):
        turnover.iloc[0] = sleeve_weights.iloc[0].abs().sum() * 0.5
    active_dates = sleeve_weights.index[sleeve_weights.sum(axis=1) > 0.0]
    if active_dates.empty:
        raise RuntimeError("the causal allocator never became eligible")
    evaluation_start = active_dates[0]
    allocator_cost_bps = 50.0
    dynamic_return = (sleeve_weights * returns).sum(axis=1) - turnover * allocator_cost_bps / 10000.0
    equal_weights = pd.DataFrame(1.0 / len(SLEEVES), index=returns.index, columns=returns.columns)
    equal_turnover = pd.Series(0.0, index=returns.index)
    equal_turnover.loc[evaluation_start] = 0.5
    equal_return = (equal_weights * returns).sum(axis=1) - equal_turnover * allocator_cost_bps / 10000.0
    metric_rows = [
        {"candidate": "causal_allocator", **metrics(dynamic_return.loc[evaluation_start:])},
        {"candidate": "static_equal_weight", **metrics(equal_return.loc[evaluation_start:])},
        *({"candidate": name, **metrics(returns.loc[evaluation_start:, name])} for name in returns),
    ]
    performance = pd.DataFrame(metric_rows).sort_values("cagr", ascending=False)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    weights.rename_axis("date").to_csv(OUTPUT / "causal_weights.csv")
    pd.DataFrame({"net_return": dynamic_return, "turnover": turnover}).rename_axis("date").to_csv(
        OUTPUT / "allocator_path.csv"
    )
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    dynamic = performance[performance.candidate == "causal_allocator"].iloc[0]
    equal = performance[performance.candidate == "static_equal_weight"].iloc[0]
    best_sleeve = performance[performance.candidate.isin(SLEEVES)].iloc[0]
    result = {
        "experiment": "strategy_allocator_diagnostic_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "sleeves": SLEEVES,
        "allocator_cost_bps": allocator_cost_bps,
        "evaluation_start_after_warmup": str(evaluation_start.date()),
        "dynamic_cagr": float(dynamic.cagr),
        "dynamic_sharpe": float(dynamic.sharpe_zero_rf),
        "dynamic_max_drawdown": float(dynamic.max_drawdown),
        "equal_weight_cagr": float(equal.cagr),
        "best_sleeve": str(best_sleeve.candidate),
        "best_sleeve_cagr": float(best_sleeve.cagr),
        "dynamic_beats_equal_weight": bool(dynamic.cagr > equal.cagr),
        "dynamic_beats_best_sleeve": bool(dynamic.cagr > best_sleeve.cagr),
        "retrospective_selection_contaminated": True,
        "broad_research_gate_used": False,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "weights": sha256(OUTPUT / "causal_weights.csv"),
            "path": sha256(OUTPUT / "allocator_path.csv"),
            "performance": sha256(OUTPUT / "performance.csv"),
            "frozen_config": sha256(FROZEN),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Strategy allocator diagnostic v1\n\n"
        f"The single predeclared causal allocator produced **{dynamic.cagr:.2%}** CAGR, "
        f"**{dynamic.sharpe_zero_rf:.3f}** Sharpe, and **{dynamic.max_drawdown:.2%}** drawdown "
        f"over the common retrospective window, after an additional {allocator_cost_bps:.0f}-bps "
        f"allocation-turnover charge. Static equal weight returned **{equal.cagr:.2%}**; the best "
        f"standalone sleeve was `{best_sleeve.candidate}` at **{best_sleeve.cagr:.2%}**.\n\n"
        "This is a diagnostic on already selected strategies, not untouched evidence. It cannot "
        "promote or replace a strategy and does not enable live trading.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
