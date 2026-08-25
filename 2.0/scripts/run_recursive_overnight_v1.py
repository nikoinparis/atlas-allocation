#!/usr/bin/env python3
"""Run one bounded recursive loop on the SPY overnight hypothesis family."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.systematic_trader.idea_challengers import DailyBar, overnight_decomposition
from src.systematic_trader.recursive_research import (
    HypothesisSpec, PromotionPolicy, RecursiveResearchEngine, ResearchBoundaries,
    TrialLedger, write_frozen_hypothesis,
)


OUTPUT = ROOT / "evidence" / "recursive_overnight_v1"
LEDGER = OUTPUT / "trial_ledger.jsonl"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_prices() -> tuple[str, list[DailyBar]]:
    manifests = []
    for path in (ROOT / "data" / "vintages").glob("*/manifest.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        if "prices.csv" in item.get("files", {}):
            manifests.append((item["observed_at_utc"], item["snapshot_id"], path.parent / "payload" / "prices.csv"))
    if not manifests:
        raise RuntimeError("no price snapshot")
    _, snapshot, path = max(manifests)
    bars = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] == "SPY" and all(row.get(key) for key in ("open", "high", "low", "close", "adjusted_close")):
                bars.append(DailyBar(row["observation_date"], float(row["open"]), float(row["high"]),
                                     float(row["low"]), float(row["close"]), float(row["adjusted_close"])))
    return str(snapshot), sorted(bars, key=lambda bar: bar.date)


def spec(snapshot: str, condition: str) -> HypothesisSpec:
    return HypothesisSpec(
        name=f"SPY overnight: {condition}",
        thesis="A close-to-next-open position has positive net return after a frozen 10 bps round-trip cost",
        metric_family="timing", signal_definition="buy at adjusted close and sell at next adjusted open",
        universe="SPY", rebalance_frequency="daily", data_snapshot_id=snapshot,
        code_version=sha(ROOT / "src" / "systematic_trader" / "idea_challengers.py")[:16],
        parameters={"condition": condition, "round_trip_cost_bps": 10}, expected_direction=1,
    )


def main() -> None:
    if LEDGER.exists():
        ledger = TrialLedger(LEDGER)
        if not ledger.verify():
            raise RuntimeError("existing recursive ledger failed integrity verification")
        print(json.dumps({"status": "already_complete", "trials": len(ledger.entries()), "ledger_verified": True}, indent=2))
        return
    snapshot, bars = latest_prices()
    raw = overnight_decomposition(bars, round_trip_cost_bps=10)
    # The decision is made at the prior close.  For an overnight row dated D,
    # only the close-to-close return ending on D-1 is eligible as a condition.
    previous_close_return: dict[str, float] = {}
    for earlier, previous, current in zip(bars, bars[1:], bars[2:]):
        previous_close_return[current.date] = previous.adjusted_close / earlier.adjusted_close - 1.0

    boundaries = ResearchBoundaries(
        "2006-01-01", "2014-12-31", "2015-01-01", "2020-12-31",
        "2021-01-01", "2026-08-21",
    )
    by_condition = ["all_nights", "after_negative_day", "after_positive_day"]

    def rows_for(candidate: HypothesisSpec, split: str):
        start = getattr(boundaries, f"{split}_start")
        end = getattr(boundaries, f"{split}_end")
        condition = str(candidate.parameters["condition"])
        rows = []
        for row in raw:
            day = str(row["date"])
            if not start <= day <= end:
                continue
            prior = previous_close_return.get(day, 0.0)
            active = condition == "all_nights" or (condition == "after_negative_day" and prior < 0) or (condition == "after_positive_day" and prior > 0)
            rows.append({"date": day, "net_return": float(row["overnight_net"]) if active else 0.0})
        return rows

    def development(candidate, split):
        return rows_for(candidate, split)

    def locked(candidate):
        return rows_for(candidate, "locked_test")

    def proposer(feedback):
        current = str(feedback.train.metrics and feedback.hypothesis_id)
        del current  # feedback controls whether another predeclared family member is attempted.
        attempted = feedback.trial_number
        return spec(snapshot, by_condition[attempted]) if attempted < len(by_condition) else None

    OUTPUT.mkdir(parents=True, exist_ok=True)
    initial = spec(snapshot, by_condition[0])
    write_frozen_hypothesis(initial, OUTPUT / "initial_hypothesis.json")
    engine = RecursiveResearchEngine(
        boundaries=boundaries,
        policy=PromotionPolicy(
            minimum_train_observations=1500, minimum_validation_observations=1000,
            minimum_locked_observations=1000, minimum_train_primary=0.25,
            minimum_validation_primary=0.0, maximum_validation_degradation=0.75,
            minimum_timing_sharpe=0.5, maximum_timing_drawdown=-0.30,
        ), ledger=TrialLedger(LEDGER), periods_per_year=252,
    )
    outcomes = engine.run(initial=initial, development_evaluator=development,
                          locked_evaluator=locked, proposer=proposer, max_trials=3)
    summary = {
        "program": "recursive_overnight_v1", "snapshot": snapshot,
        "predeclared_candidates": by_condition, "cost_bps_round_trip": 10,
        "ledger_verified": TrialLedger(LEDGER).verify(),
        "locked_test_opened": any(item["locked_test"] is not None for item in outcomes),
        "outcomes": [{"trial_id": item["trial_id"], "name": item["hypothesis"]["spec"]["name"],
                      "status": item["status"], "diagnosis": item["diagnosis"],
                      "train_sharpe": item["train"]["primary_metric"],
                      "validation_sharpe": item["validation"]["primary_metric"],
                      "locked_test": item["locked_test"]} for item in outcomes],
        "claim": "A rejected recursive family is retained; the unopened lockbox was not used as feedback.",
    }
    (OUTPUT / "result.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
