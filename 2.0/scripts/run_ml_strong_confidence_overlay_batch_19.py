#!/usr/bin/env python3
"""Evaluate the predeclared strong-confidence-only ML overlay."""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_cross_sectional_factor_baseline_batch_16 as batch16
from scripts import run_ml_confidence_overlay_batch_18 as batch18
from scripts import run_robust_cross_sectional_ml_batch_17 as batch17
from src.systematic_trader.data_vintage import parse_utc, sha256
from src.systematic_trader.ml_confidence import causal_strong_weight, guarded_weight
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

PROGRAM = ROOT / "config/ml_strong_confidence_overlay_v2.json"
OUTPUT = ROOT / "evidence/ml_strong_confidence_overlay_batch_19"
COSTS = (10.0, 50.0, 100.0)
VARIANTS = (
    "core_only", "constant_20", "constant_30", "batch18_confidence_guarded",
    "strong_confidence_unguarded", "strong_confidence_guarded", "extreme_only",
)
BOOTSTRAP_SAMPLES = 20_000


def strong_decisions(
    base: list[dict[str, object]], ml_periods_10: list[dict[str, object]],
) -> list[dict[str, object]]:
    realized = sorted((str(row["realization_date"]), float(row["net_return"])) for row in ml_periods_10)
    prior_scores: list[float] = []
    output = []
    for row in base:
        decision = str(row["decision_date"])
        score = float(row["raw_confidence"])
        desired, thresholds = causal_strong_weight(score, prior_scores)
        available = [value for day, value in realized if day <= decision]
        guarded, risk = guarded_weight(desired, available)
        output.append({
            **row,
            "strong_threshold_p80": thresholds["p80"],
            "strong_threshold_p95": thresholds["p95"],
            "strong_desired_weight": desired,
            "strong_guarded_weight": guarded,
            "strong_volatility_cap_active": risk["volatility_cap_active"],
            "strong_drawdown_stop_active": risk["drawdown_stop_active"],
        })
        prior_scores.append(score)
    return output


def weights(decisions: list[dict[str, object]], variant: str) -> dict[str, float]:
    if variant == "core_only":
        return {str(row["decision_date"]): 0.0 for row in decisions}
    if variant == "constant_20":
        return {str(row["decision_date"]): 0.20 for row in decisions}
    if variant == "constant_30":
        return {str(row["decision_date"]): 0.30 for row in decisions}
    field = {
        "batch18_confidence_guarded": "guarded_weight",
        "strong_confidence_unguarded": "strong_desired_weight",
        "strong_confidence_guarded": "strong_guarded_weight",
        "extreme_only": "extreme_only_weight",
    }[variant]
    return {str(row["decision_date"]): float(row[field]) for row in decisions}


def combine(
    winner_periods: list[dict[str, object]], ml_periods: list[dict[str, object]],
    decisions: list[dict[str, object]], variant: str, cost_bps: float,
) -> list[dict[str, object]]:
    winner = {str(row["realization_date"]): row for row in winner_periods}
    ml = {str(row["realization_date"]): row for row in ml_periods}
    history = weights(decisions, variant)
    decision_dates = sorted(history)
    pointer = -1
    active_weight = 0.0
    previous_weight = 0.0
    output = []
    for realization in sorted(set(winner) & set(ml)):
        ml_row = ml[realization]
        weekly_decision = str(ml_row["decision_date"])
        while pointer + 1 < len(decision_dates) and decision_dates[pointer + 1] <= weekly_decision:
            pointer += 1
            active_weight = history[decision_dates[pointer]]
        if pointer < 0:
            continue
        allocation_turnover = abs(active_weight - previous_weight)
        allocation_cost = allocation_turnover * cost_bps / 10_000.0
        core_return = float(winner[realization]["net_return"])
        ml_return = float(ml_row["net_return"])
        output.append({
            "variant": variant, "cost_bps": cost_bps, "decision_date": weekly_decision,
            "realization_date": realization, "ml_weight": active_weight,
            "winner_net_return": core_return, "ml_net_return": ml_return,
            "allocation_turnover": allocation_turnover, "allocation_cost": allocation_cost,
            "net_return": (1.0 - active_weight) * core_return + active_weight * ml_return - allocation_cost,
        })
        previous_weight = active_weight
    return output


def confidence_calibration(decisions: list[dict[str, object]]) -> dict[str, object]:
    eligible = [row for row in decisions if int(row["prior_confidence_observations"]) >= 24]

    def difference(rows: list[dict[str, object]]) -> float | None:
        active = [float(row["future_rank_ic_evaluation_only"]) for row in rows if float(row["strong_desired_weight"]) > 0.0]
        inactive = [float(row["future_rank_ic_evaluation_only"]) for row in rows if float(row["strong_desired_weight"]) == 0.0]
        return statistics.fmean(active) - statistics.fmean(inactive) if active and inactive else None

    point = difference(eligible)
    if point is None:
        raise RuntimeError("confidence calibration has an empty group")
    generator = random.Random(20260819)
    bootstrapped = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(eligible):
            start = generator.randrange(len(eligible))
            sample.extend(eligible[(start + offset) % len(eligible)] for offset in range(3))
        value = difference(sample[:len(eligible)])
        if value is not None:
            bootstrapped.append(value)
    ordered = sorted(bootstrapped)
    lower = ordered[math.floor(0.05 * (len(ordered) - 1))]
    active = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["strong_desired_weight"]) > 0.0]
    inactive = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["strong_desired_weight"]) == 0.0]
    extreme = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["strong_desired_weight"]) == 0.30]
    return {
        "eligible_months": len(eligible), "active_months": len(active), "inactive_months": len(inactive),
        "active_mean_future_rank_ic": statistics.fmean(active),
        "inactive_mean_future_rank_ic": statistics.fmean(inactive),
        "extreme_mean_future_rank_ic": statistics.fmean(extreme),
        "active_minus_inactive_rank_ic": point,
        "bootstrap_samples": len(bootstrapped), "block_months": 3,
        "one_sided_95pct_lower_difference": lower,
        "pass": point > 0.0 and lower > 0.0,
    }


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    predictions = batch18.read_csv(batch18.PREDICTIONS)
    projected = batch18.projection_hash(predictions)
    if projected != str(program["source_prediction_projection_sha256"]):
        raise RuntimeError("source prediction projection changed")
    dataset = batch18.read_csv(batch18.DATASET)
    manifest = batch17.latest_free_manifest()
    snapshot_id = str(manifest["snapshot_id"])
    assets = sorted(json.loads(batch17.UNIVERSE.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = prepare_weekly_adjusted_prices(
        batch17.STORE / snapshot_id / "payload/prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2004, 1, 2), expected_symbols=assets,
    )
    histories, _ = batch17.prediction_histories(predictions, dataset, "real")
    first_prediction = min(row["decision_date"] for row in predictions)
    ml_periods = {
        cost: [row for row in batch16.simulate(dates, assets, prices, histories, cost) if str(row["decision_date"]) >= first_prediction]
        for cost in COSTS
    }
    base_decisions = batch18.confidence_decisions(predictions, ml_periods[10.0])
    decisions = strong_decisions(base_decisions, ml_periods[10.0])
    winner_periods = {cost: batch18.frozen_winner_periods(cost) for cost in COSTS}
    tables = {}
    scoreboard = []
    for variant in VARIANTS:
        for cost in COSTS:
            periods = combine(winner_periods[cost], ml_periods[cost], decisions, variant, cost)
            tables[(variant, cost)] = periods
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in batch18.metrics(periods).items()},
                **{f"oos_2016_2020_{key}": value for key, value in batch18.metrics(periods, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in batch18.metrics(periods, "2021-01-01").items()},
            })

    def score(variant: str, cost: float) -> dict[str, object]:
        return next(row for row in scoreboard if row["variant"] == variant and row["cost_bps"] == cost)

    primary_10, primary_100 = score("strong_confidence_guarded", 10.0), score("strong_confidence_guarded", 100.0)
    core_10, core_100 = score("core_only", 10.0), score("core_only", 100.0)
    paired = batch17.paired_bootstrap_advantage(
        [float(row["net_return"]) for row in tables[("strong_confidence_guarded", 10.0)]],
        [float(row["net_return"]) for row in tables[("core_only", 10.0)]], seed=20260819,
    )
    calibration = confidence_calibration(decisions)
    gates = {
        "annual_return_10bps": float(primary_10["full_annual_return"]) > float(core_10["full_annual_return"]),
        "sharpe_10bps": float(primary_10["full_sharpe_zero_rf"]) > float(core_10["full_sharpe_zero_rf"]),
        "maximum_drawdown_10bps": float(primary_10["full_max_drawdown"]) >= float(core_10["full_max_drawdown"]),
        "paired_sharpe_10bps": bool(paired["sharpe_advantage_statistically_positive"]),
        "paired_annual_return_10bps": bool(paired["annual_return_advantage_statistically_positive"]),
        "annual_return_100bps": float(primary_100["full_annual_return"]) > float(core_100["full_annual_return"]),
        "sharpe_100bps": float(primary_100["full_sharpe_zero_rf"]) > float(core_100["full_sharpe_zero_rf"]),
        "later_windows_100bps": float(primary_100["oos_2016_2020_annual_return"]) > 0.0 and float(primary_100["oos_2021_present_annual_return"]) > 0.0,
        "confidence_calibration_bootstrap": bool(calibration["pass"]),
        "survivorship_safe": False, "untouched_forward_52w": False,
    }
    gates["all"] = all(gates.values())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 19,
        "track": "strong_confidence_only_ml_overlay", "program_sha256": sha256(PROGRAM),
        "source_prediction_projection_sha256": projected, "prediction_projection_unchanged": True,
        "hypothesis_is_retrospective_followup": True,
        "confidence_calibration": calibration, "paired_bootstrap_10bps": paired,
        "promotion_gates": gates, "promoted": gates["all"], "live_trading_approved": False,
        "limitations": [
            "The strong-only hypothesis was motivated by Batch 18 and therefore reuses history already inspected.",
            "The ETF universe remains survivorship-prone.",
            "Consensus can be confidently wrong and is not a probability of profit.",
            "Final promotion requires 52 untouched forward weeks under a new frozen version.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    batch18.write_csv(OUTPUT / "strong_confidence_decisions.csv", decisions)
    batch18.write_csv(OUTPUT / "portfolio_scoreboard.csv", scoreboard)
    batch18.write_csv(OUTPUT / "primary_returns_10bps.csv", tables[("strong_confidence_guarded", 10.0)])
    report = "\n".join([
        "# Strong-Confidence-Only ML Overlay — Batch 19", "",
        f"The guarded strong-only overlay produced **{float(primary_10['full_annual_return']) * 100:.2f}%** annual return, **{float(primary_10['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(primary_10['full_max_drawdown']) * 100:.2f}%** maximum drawdown at 10 bps.", "",
        f"The frozen core produced **{float(core_10['full_annual_return']) * 100:.2f}%**, **{float(core_10['full_sharpe_zero_rf']):.3f}**, and **{float(core_10['full_max_drawdown']) * 100:.2f}%** over identical dates.", "",
        f"At 100 bps the strong overlay returned **{float(primary_100['full_annual_return']) * 100:.2f}%** versus core **{float(core_100['full_annual_return']) * 100:.2f}%**.", "",
        f"Active-minus-inactive future rank IC was **{float(calibration['active_minus_inactive_rank_ic']):.4f}** with one-sided block-bootstrap lower bound **{float(calibration['one_sided_95pct_lower_difference']):.4f}**.", "",
        f"The paired Sharpe lower bound was **{float(paired['one_sided_95pct_lower_sharpe_difference']):.3f}** and annual-return lower bound **{float(paired['one_sided_95pct_lower_annual_return_difference']) * 100:.3f}%**.", "",
        f"Promotion: **{gates['all']}**. This is a retrospective follow-up and live execution remains disabled.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name != "result.json"}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"primary_10": primary_10, "core_10": core_10, "primary_100": primary_100, "core_100": core_100, "calibration": calibration, "paired": paired, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
