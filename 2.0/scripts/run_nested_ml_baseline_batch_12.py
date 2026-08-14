#!/usr/bin/env python3
"""Run a common nested walk-forward ML bar before accepting external ML claims."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_trade_buffering_batch_08 import build_inputs
from src.systematic_trader.nested_ml_challenger import nested_walk_forward
from src.systematic_trader.point_in_time import CASH_ASSET, compute_path
from src.systematic_trader.research_lab import summarize_periods


OUTPUT = ROOT / "evidence/ml_sandbox_batch_12"
LEDGER = ROOT / "evidence/challenger_program_v1/trial_ledger.csv"
COSTS = (10.0, 25.0, 50.0, 100.0)


def trailing_return(dates, prices, index, asset, weeks):
    if index < weeks:
        return 0.0
    current = prices.get(dates[index], {}).get(asset)
    prior = prices.get(dates[index - weeks], {}).get(asset)
    return current / prior - 1.0 if current is not None and prior not in (None, 0.0) else 0.0


def dataset(dates, prices):
    decision_dates = dates[:-1]
    features = []
    labels = []
    risk_assets = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG"]
    for index, decision in enumerate(decision_dates):
        breadth_values = [trailing_return(dates, prices, index, asset, 13) for asset in risk_assets]
        features.append([
            trailing_return(dates, prices, index, "SPY", 1),
            trailing_return(dates, prices, index, "SPY", 4),
            trailing_return(dates, prices, index, "SPY", 13),
            trailing_return(dates, prices, index, "SPY", 26),
            sum(value > 0.0 for value in breadth_values) / len(breadth_values),
        ])
        current = prices.get(decision, {}).get("SPY")
        future = prices.get(dates[index + 1], {}).get("SPY")
        labels.append(future / current - 1.0 if current not in (None, 0.0) and future is not None else 0.0)
    return decision_dates, features, labels


def overlay(targets, predictions):
    result = {}
    risk_off_count = 0
    for decision, row in targets.items():
        if decision not in predictions or predictions[decision] >= 0.0:
            result[decision] = dict(row)
            continue
        risk_off_count += 1
        scaled = {asset: weight * 0.5 for asset, weight in row.items() if asset != CASH_ASSET}
        scaled[CASH_ASSET] = 1.0 - sum(scaled.values())
        result[decision] = scaled
    return result, risk_off_count


def main() -> int:
    snapshot_id, dates, targets, simple_returns, prices = build_inputs()
    decision_dates, features, labels = dataset(dates, prices)
    real_predictions, real_folds = nested_walk_forward(decision_dates, features, labels)
    shuffled_predictions, shuffled_folds = nested_walk_forward(decision_dates, features, labels, shuffle=True)
    variants = {"baseline": ({}, targets), "nested_ridge": (real_predictions, overlay(targets, real_predictions)[0]), "label_shuffle": (shuffled_predictions, overlay(targets, shuffled_predictions)[0])}
    rows = []
    eligible_dates = set(real_predictions)
    for name, (predictions, weights) in variants.items():
        for cost_bps in COSTS:
            periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=cost_bps)
            test_periods = [row for row in periods if row["decision_date"] in eligible_dates]
            rows.append({
                "variant": name, "cost_bps": cost_bps, **summarize_periods(test_periods),
                "risk_off_decisions": sum(value < 0.0 for value in predictions.values()),
                "fully_invested_pass": accounting["fully_invested_pass"],
                "unpriced_exposure_events": accounting["unpriced_exposure_events"],
            })
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "scoreboard.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    with (OUTPUT / "outer_folds.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(real_folds[0])); writer.writeheader(); writer.writerows(real_folds + shuffled_folds)
    at_10 = {row["variant"]: row for row in rows if row["cost_bps"] == 10.0}
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 12,
        "track": "machine_learning_sandbox", "source_snapshot_id": snapshot_id,
        "outer_fold_count": len(real_folds), "inner_trials_per_fold": 3,
        "total_hyperparameter_fits_including_shuffle": len(real_folds) * 3 * 2,
        "test_observations": len(real_predictions), "scoreboard_at_10_bps": at_10,
        "ml_beats_baseline_sharpe_at_10bps": at_10["nested_ridge"]["sharpe_zero_rf"] > at_10["baseline"]["sharpe_zero_rf"],
        "shuffle_control_is_not_better_than_real_model": at_10["label_shuffle"]["sharpe_zero_rf"] <= at_10["nested_ridge"]["sharpe_zero_rf"],
        "status": "common_ml_bar_complete_external_systems_pending_capability",
        "limitations": [
            "This is an auditable linear baseline, not a claim that any external ML repository is profitable.",
            "The ETF universe remains survivorship-prone and there is no untouched 52-week forward record.",
            "External systems must beat this bar under the same folds; their published examples are not accepted as evidence."
        ],
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in rows:
            writer.writerow([f"batch12-{row['variant']}-{row['cost_bps']:.0f}",12,"machine_learning_sandbox","",row["variant"],"completed","retain_for_comparison","nested outer test only","evidence/ml_sandbox_batch_12/scoreboard.csv"])
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
