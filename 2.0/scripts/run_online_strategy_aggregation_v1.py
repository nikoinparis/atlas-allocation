#!/usr/bin/env python3
"""Causal shadow allocator across the six saved dashboard strategies."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "dashboard/public/return-first-dashboard.json"
CONFIG = ROOT / "config/future_alpha_program_v1.json"
OUTPUT = ROOT / "evidence/online_strategy_aggregation_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(path: pd.Series) -> dict[str, float]:
    path = path.dropna()
    wealth = (1 + path).cumprod()
    years = len(path) / 52
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1) if years > 0 and wealth.iloc[-1] > 0 else np.nan
    vol = float(path.std(ddof=1) * math.sqrt(52))
    drawdown = wealth / wealth.cummax() - 1
    return {"weeks": len(path), "cagr": cagr, "sharpe_zero_rf": float(path.mean() * 52 / vol) if vol else np.nan, "max_drawdown": float(drawdown.min()), "total_return": float(wealth.iloc[-1] - 1)}


def main() -> int:
    payload = json.loads(SOURCE.read_text())
    config = json.loads(CONFIG.read_text())
    series = {}
    for item in payload["strategies"]:
        identity = item["strategy"]["id"]
        rows = pd.DataFrame(item["records"])
        rows["date"] = pd.to_datetime(rows.date, utc=True)
        series[identity] = rows.set_index("date").netReturn.astype(float)
    returns = pd.concat(series, axis=1).sort_index()
    common = returns.dropna()
    if len(common) < 52:
        raise RuntimeError("online allocator requires at least 52 common weeks")

    minimum = float(next(branch for branch in config["branches"] if branch["id"] == "online_strategy_aggregation")["minimum_weight"])
    learning_rates = next(branch for branch in config["branches"] if branch["id"] == "online_strategy_aggregation")["learning_rates"]
    result_rows, paths, scorecard = [], {}, {}
    for eta in learning_rates:
        prior = pd.Series(1 / common.shape[1], index=common.columns)
        output = []
        for date, realised in common.iterrows():
            history = common.loc[common.index < date].tail(26)
            if len(history) >= 13:
                mean = history.mean() * 52
                risk = history.std(ddof=1) * math.sqrt(52)
                utility = mean / risk.replace(0, np.nan)
                utility = utility.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(-3, 3)
                raw = np.exp(float(eta) * utility)
                target = raw / raw.sum()
                target = minimum + (1 - minimum * len(target)) * target
                target = target / target.sum()
            else:
                target = prior
            output.append(float((target * realised).sum()))
            result_rows.extend({"date": date, "learning_rate": eta, "strategy": name, "weight": float(weight)} for name, weight in target.items())
            prior = target
        path = pd.Series(output, index=common.index)
        paths[f"eta_{eta}"] = path
        scorecard[f"eta_{eta}"] = metrics(path)

    equal = common.mean(axis=1)
    paths["equal_weight"] = equal
    scorecard["equal_weight"] = metrics(equal)
    for name in common:
        scorecard[f"component_{name}"] = metrics(common[name])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(result_rows).to_csv(OUTPUT / "weights.csv", index=False)
    pd.DataFrame(paths).to_csv(OUTPUT / "weekly_paths.csv")
    best_eta = max((name for name in scorecard if name.startswith("eta_")), key=lambda name: scorecard[name]["cagr"])
    result = {
        "experiment": "online_strategy_aggregation_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sha256(SOURCE), "config_sha256": sha256(CONFIG), "common_weeks": len(common),
        "causal": True, "uses_current_week_to_set_current_weight": False,
        "scorecard": scorecard, "best_retrospective_learning_rate": best_eta,
        "interpretation": "shadow diagnostic only; saved component paths were selected in-sample and holdings-level allocator costs are not reconstructed",
        "forward_status": "eligible_for_preregistered_shadow_observation_only",
        "strategy_promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Online strategy aggregation v1\n\n"
        "Weights are set from the prior 26 weeks only and applied to the next observed return. "
        "This is a shadow allocator diagnostic, not clean out-of-sample evidence: its six inputs were already selected by this project, and exact holdings-level allocator costs were not reconstructed.\n"
    )
    print(json.dumps({"best_retrospective_learning_rate": best_eta, "scorecard": scorecard, "live_trading_enabled": False}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
