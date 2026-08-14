#!/usr/bin/env python3
"""Freeze the exact Batch 67 60/40 diagnostic blend for forward observation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.run_aggressive_return_discovery_batch_62 import mix
from scripts.run_exhaustive_return_first_discovery_batch_66 import metrics_for
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv

BASE_PATH = ROOT / "evidence/return_first_ensemble_batch_67/selected_ensemble_weights.csv"
HINDSIGHT_PATH = ROOT / "evidence/exhaustive_return_first_discovery_batch_66/retrospective_ceiling_weights.csv"
PRICE_PATH = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
OUTPUT = ROOT / "evidence/forward_return_first_60_40_blend_v1"


def main() -> int:
    prices = read_dated_csv(PRICE_PATH).apply(pd.to_numeric, errors="coerce")
    base = read_dated_csv(BASE_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    hindsight = read_dated_csv(HINDSIGHT_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    weights = mix([base, hindsight], [0.60, 0.40])
    repeated = mix([base, hindsight], [0.60, 0.40])
    if not weights.equals(repeated):
        raise RuntimeError("non-deterministic blend")
    if float((weights.sum(axis=1) - 1.0).abs().max()) > 1e-12:
        raise RuntimeError("weights do not sum to one")

    forward = next_week_returns(prices)
    path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
    metrics = metrics_for(path, pd.Timestamp("2023-08-04"))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    weights.rename_axis("Date").to_csv(OUTPUT / "frozen_weights.csv")
    weights.iloc[-1].loc[lambda values: values > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "current_holdings.csv")
    result = {
        "candidate": "candidate-return-first-60-40-forward-v1",
        "base_weight": 0.60,
        "hindsight_ceiling_weight": 0.40,
        "holdout_50bps_cagr": metrics["holdout_cagr"],
        "holdout_50bps_sharpe": metrics["holdout_sharpe"],
        "holdout_50bps_drawdown": metrics["holdout_drawdown"],
        "full_50bps_cagr": metrics["full_cagr"],
        "full_50bps_drawdown": metrics["full_drawdown"],
        "deterministic": True,
        "weights_sum_to_one": True,
        "retrospective_research_only": True,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
