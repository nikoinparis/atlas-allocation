#!/usr/bin/env python3
"""Evaluate buffered holdings and persistent, cost-aware ML activation."""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_cross_sectional_factor_baseline_batch_16 as batch16
from scripts import run_ml_confidence_overlay_batch_18 as batch18
from scripts import run_ml_strong_confidence_overlay_batch_19 as batch19
from scripts import run_robust_cross_sectional_ml_batch_17 as batch17
from src.systematic_trader.cross_sectional_factors import capped_inverse_volatility_weights
from src.systematic_trader.data_vintage import parse_utc, sha256
from src.systematic_trader.ml_confidence import (
    apply_weight_turnover_buffer,
    buffered_membership,
    causal_strong_weight,
    guarded_weight,
    persistent_cost_aware_weight,
)
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

PROGRAM = ROOT / "config/ml_cost_aware_persistent_overlay_v1.json"
OUTPUT = ROOT / "evidence/ml_cost_aware_persistent_overlay_batch_20"
COSTS = (10.0, 50.0, 100.0)
VARIANTS = (
    "core_only", "batch19_strong_guarded", "buffered_strong_guarded",
    "persistent_unbuffered_guarded", "persistent_cost_aware_buffered_guarded",
)
BOOTSTRAP_SAMPLES = 20_000


def buffered_histories(
    predictions: list[dict[str, str]], dataset: list[dict[str, str]],
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]]]:
    volatility = {(row["decision_date"], row["asset"]): float(row["volatility_26w"]) for row in dataset}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in predictions:
        grouped[row["decision_date"]].append(row)
    histories: dict[str, dict[str, float]] = {}
    audit_rows = []
    previous_weights: dict[str, float] = {}
    for decision in sorted(grouped):
        scores = {row["asset"]: float(row["prediction_real"]) for row in grouped[decision]}
        selected, membership = buffered_membership(list(previous_weights), scores)
        target = capped_inverse_volatility_weights(
            selected, {asset: volatility[(decision, asset)] for asset in selected}, 0.35,
        )
        applied, weight_audit = apply_weight_turnover_buffer(previous_weights, target, 0.10)
        histories[decision] = applied
        for asset, weight in sorted(applied.items()):
            audit_rows.append({
                "decision_date": decision, "asset": asset, "prediction": scores[asset], "weight": weight,
                **membership, **weight_audit,
            })
        previous_weights = applied
    return histories, audit_rows


def realized_values(periods: list[dict[str, object]], decision: str) -> list[float]:
    return [float(row["net_return"]) for row in periods if str(row["realization_date"]) <= decision]


def excess_values(
    ml_periods: list[dict[str, object]], core_periods: list[dict[str, object]], decision: str,
) -> list[float]:
    core = {str(row["realization_date"]): float(row["net_return"]) for row in core_periods}
    return [
        float(row["net_return"]) - core[str(row["realization_date"])]
        for row in ml_periods
        if str(row["realization_date"]) <= decision and str(row["realization_date"]) in core
    ]


def cost_aware_decisions(
    base: list[dict[str, object]], buffered: dict[float, list[dict[str, object]]],
    original: dict[float, list[dict[str, object]]], core: dict[float, list[dict[str, object]]],
) -> list[dict[str, object]]:
    prior_scores: list[float] = []
    previous_strong: float | None = None
    output = []
    for row in base:
        decision = str(row["decision_date"])
        score = float(row["raw_confidence"])
        strong, thresholds = causal_strong_weight(score, prior_scores)
        buffered_candidate, buffered_cost = persistent_cost_aware_weight(
            strong, previous_strong, excess_values(buffered[100.0], core[100.0], decision),
        )
        original_candidate, original_cost = persistent_cost_aware_weight(
            strong, previous_strong, excess_values(original[100.0], core[100.0], decision),
        )
        buffered_strong_guarded, buffered_strong_risk = guarded_weight(
            strong, realized_values(buffered[10.0], decision),
        )
        buffered_primary, buffered_primary_risk = guarded_weight(
            buffered_candidate, realized_values(buffered[10.0], decision),
        )
        original_persistent, original_persistent_risk = guarded_weight(
            original_candidate, realized_values(original[10.0], decision),
        )
        output.append({
            **row,
            "strong_threshold_p80": thresholds["p80"], "strong_threshold_p95": thresholds["p95"],
            "strong_desired_weight": strong,
            "buffered_strong_guarded_weight": buffered_strong_guarded,
            "persistent_buffered_pre_risk_weight": buffered_candidate,
            "persistent_buffered_guarded_weight": buffered_primary,
            "persistent_unbuffered_guarded_weight": original_persistent,
            **{f"buffered_cost_{key}": value for key, value in buffered_cost.items()},
            **{f"unbuffered_cost_{key}": value for key, value in original_cost.items()},
            "buffered_strong_volatility_cap": buffered_strong_risk["volatility_cap_active"],
            "buffered_strong_drawdown_stop": buffered_strong_risk["drawdown_stop_active"],
            "primary_volatility_cap": buffered_primary_risk["volatility_cap_active"],
            "primary_drawdown_stop": buffered_primary_risk["drawdown_stop_active"],
            "unbuffered_persistent_volatility_cap": original_persistent_risk["volatility_cap_active"],
            "unbuffered_persistent_drawdown_stop": original_persistent_risk["drawdown_stop_active"],
        })
        previous_strong = strong
        prior_scores.append(score)
    return output


def variant_weights(
    decisions: list[dict[str, object]], batch19_decisions: list[dict[str, object]], variant: str,
) -> dict[str, float]:
    if variant == "core_only":
        return {str(row["decision_date"]): 0.0 for row in decisions}
    if variant == "batch19_strong_guarded":
        return {str(row["decision_date"]): float(row["strong_guarded_weight"]) for row in batch19_decisions}
    field = {
        "buffered_strong_guarded": "buffered_strong_guarded_weight",
        "persistent_unbuffered_guarded": "persistent_unbuffered_guarded_weight",
        "persistent_cost_aware_buffered_guarded": "persistent_buffered_guarded_weight",
    }[variant]
    return {str(row["decision_date"]): float(row[field]) for row in decisions}


def combine(
    core_periods: list[dict[str, object]], ml_periods: list[dict[str, object]],
    weights: dict[str, float], variant: str, cost_bps: float,
) -> list[dict[str, object]]:
    core = {str(row["realization_date"]): row for row in core_periods}
    ml = {str(row["realization_date"]): row for row in ml_periods}
    monthly = sorted(weights)
    pointer = -1
    active = previous = 0.0
    output = []
    for realization in sorted(set(core) & set(ml)):
        weekly_decision = str(ml[realization]["decision_date"])
        while pointer + 1 < len(monthly) and monthly[pointer + 1] <= weekly_decision:
            pointer += 1
            active = weights[monthly[pointer]]
        if pointer < 0:
            continue
        allocation_turnover = abs(active - previous)
        allocation_cost = allocation_turnover * cost_bps / 10_000.0
        core_return = float(core[realization]["net_return"])
        ml_return = float(ml[realization]["net_return"])
        output.append({
            "variant": variant, "cost_bps": cost_bps, "decision_date": weekly_decision,
            "realization_date": realization, "ml_weight": active,
            "winner_net_return": core_return, "ml_net_return": ml_return,
            "allocation_turnover": allocation_turnover, "allocation_cost": allocation_cost,
            "net_return": (1.0 - active) * core_return + active * ml_return - allocation_cost,
        })
        previous = active
    return output


def calibration(decisions: list[dict[str, object]]) -> dict[str, object]:
    eligible = [row for row in decisions if int(row["prior_confidence_observations"]) >= 24]

    def difference(rows: list[dict[str, object]]) -> float | None:
        active = [float(row["future_rank_ic_evaluation_only"]) for row in rows if float(row["persistent_buffered_pre_risk_weight"]) > 0.0]
        inactive = [float(row["future_rank_ic_evaluation_only"]) for row in rows if float(row["persistent_buffered_pre_risk_weight"]) == 0.0]
        return statistics.fmean(active) - statistics.fmean(inactive) if active and inactive else None

    point = difference(eligible)
    if point is None:
        raise RuntimeError("cost-aware calibration has an empty group")
    generator = random.Random(20260820)
    samples = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(eligible):
            start = generator.randrange(len(eligible))
            sample.extend(eligible[(start + offset) % len(eligible)] for offset in range(3))
        value = difference(sample[:len(eligible)])
        if value is not None:
            samples.append(value)
    lower = sorted(samples)[math.floor(0.05 * (len(samples) - 1))]
    active = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["persistent_buffered_pre_risk_weight"]) > 0.0]
    inactive = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["persistent_buffered_pre_risk_weight"]) == 0.0]
    return {
        "eligible_months": len(eligible), "active_months": len(active), "inactive_months": len(inactive),
        "active_mean_future_rank_ic": statistics.fmean(active),
        "inactive_mean_future_rank_ic": statistics.fmean(inactive),
        "active_minus_inactive_rank_ic": point,
        "bootstrap_samples": len(samples), "block_months": 3,
        "one_sided_95pct_lower_difference": lower, "pass": point > 0.0 and lower > 0.0,
    }


def annual_turnover(periods: list[dict[str, object]]) -> float:
    return statistics.fmean(float(row["turnover"]) for row in periods) * 52.0


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
    original_histories, _ = batch17.prediction_histories(predictions, dataset, "real")
    buffered_weights, holding_audit = buffered_histories(predictions, dataset)
    first_prediction = min(row["decision_date"] for row in predictions)
    original = {
        cost: [row for row in batch16.simulate(dates, assets, prices, original_histories, cost) if str(row["decision_date"]) >= first_prediction]
        for cost in COSTS
    }
    buffered = {
        cost: [row for row in batch16.simulate(dates, assets, prices, buffered_weights, cost) if str(row["decision_date"]) >= first_prediction]
        for cost in COSTS
    }
    core = {cost: batch18.frozen_winner_periods(cost) for cost in COSTS}
    base_buffered = batch18.confidence_decisions(predictions, buffered[10.0])
    decisions = cost_aware_decisions(base_buffered, buffered, original, core)
    base_original = batch18.confidence_decisions(predictions, original[10.0])
    batch19_decisions = batch19.strong_decisions(base_original, original[10.0])

    tables = {}
    scoreboard = []
    for variant in VARIANTS:
        ml_source = original if variant in {"batch19_strong_guarded", "persistent_unbuffered_guarded"} else buffered
        history = variant_weights(decisions, batch19_decisions, variant)
        for cost in COSTS:
            periods = combine(core[cost], ml_source[cost], history, variant, cost)
            tables[(variant, cost)] = periods
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in batch18.metrics(periods).items()},
                **{f"oos_2016_2020_{key}": value for key, value in batch18.metrics(periods, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in batch18.metrics(periods, "2021-01-01").items()},
            })

    def score(variant: str, cost: float) -> dict[str, object]:
        return next(row for row in scoreboard if row["variant"] == variant and row["cost_bps"] == cost)

    primary_10, primary_100 = score("persistent_cost_aware_buffered_guarded", 10.0), score("persistent_cost_aware_buffered_guarded", 100.0)
    core_10, core_100 = score("core_only", 10.0), score("core_only", 100.0)
    batch19_10 = score("batch19_strong_guarded", 10.0)
    paired = batch17.paired_bootstrap_advantage(
        [float(row["net_return"]) for row in tables[("persistent_cost_aware_buffered_guarded", 10.0)]],
        [float(row["net_return"]) for row in tables[("core_only", 10.0)]], seed=20260820,
    )
    confidence = calibration(decisions)
    turnover = {
        "original_ml": annual_turnover(original[10.0]),
        "buffered_ml": annual_turnover(buffered[10.0]),
        "batch19_allocation": float(batch19_10["full_annual_allocation_turnover"]),
        "primary_allocation": float(primary_10["full_annual_allocation_turnover"]),
    }
    gates = {
        "annual_return_10bps": float(primary_10["full_annual_return"]) > float(core_10["full_annual_return"]),
        "sharpe_10bps": float(primary_10["full_sharpe_zero_rf"]) > float(core_10["full_sharpe_zero_rf"]),
        "maximum_drawdown_10bps": float(primary_10["full_max_drawdown"]) >= float(core_10["full_max_drawdown"]) - float(program["floating_point_comparison_tolerance"]),
        "paired_sharpe_10bps": bool(paired["sharpe_advantage_statistically_positive"]),
        "paired_annual_return_10bps": bool(paired["annual_return_advantage_statistically_positive"]),
        "annual_return_100bps": float(primary_100["full_annual_return"]) > float(core_100["full_annual_return"]),
        "sharpe_100bps": float(primary_100["full_sharpe_zero_rf"]) > float(core_100["full_sharpe_zero_rf"]),
        "later_windows_100bps": float(primary_100["oos_2016_2020_annual_return"]) > 0.0 and float(primary_100["oos_2021_present_annual_return"]) > 0.0,
        "ml_turnover_reduced": turnover["buffered_ml"] < turnover["original_ml"],
        "allocation_turnover_not_increased": turnover["primary_allocation"] <= turnover["batch19_allocation"],
        "confidence_calibration_bootstrap": bool(confidence["pass"]),
        "survivorship_safe": False, "untouched_forward_52w": False,
    }
    gates["all"] = all(gates.values())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 20,
        "track": "cost_aware_persistent_ml_overlay", "program_sha256": sha256(PROGRAM),
        "source_prediction_projection_sha256": projected, "prediction_projection_unchanged": True,
        "hypothesis_is_retrospective_followup": True, "turnover_evidence": turnover,
        "confidence_calibration": confidence, "paired_bootstrap_10bps": paired,
        "promotion_gates": gates, "promoted": gates["all"], "live_trading_approved": False,
        "limitations": [
            "Cost-aware persistence was designed after inspecting Batch 19 and is retrospective.",
            "Trailing realized excess is a noisy estimate of future net benefit.",
            "The ETF universe remains survivorship-prone.",
            "Final promotion requires untouched forward evidence under a newly frozen version.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    batch18.write_csv(OUTPUT / "holding_buffer_audit.csv", holding_audit)
    batch18.write_csv(OUTPUT / "cost_aware_decisions.csv", decisions)
    batch18.write_csv(OUTPUT / "portfolio_scoreboard.csv", scoreboard)
    batch18.write_csv(OUTPUT / "primary_returns_10bps.csv", tables[("persistent_cost_aware_buffered_guarded", 10.0)])
    report = "\n".join([
        "# Cost-Aware Persistent ML Overlay — Batch 20", "",
        f"The primary portfolio returned **{float(primary_10['full_annual_return']) * 100:.2f}%** with **{float(primary_10['full_sharpe_zero_rf']):.3f}** Sharpe and **{float(primary_10['full_max_drawdown']) * 100:.2f}%** maximum drawdown at 10 bps.", "",
        f"The core returned **{float(core_10['full_annual_return']) * 100:.2f}%** with **{float(core_10['full_sharpe_zero_rf']):.3f}** Sharpe. Batch 19 returned **{float(batch19_10['full_annual_return']) * 100:.2f}%** with **{float(batch19_10['full_sharpe_zero_rf']):.3f}** Sharpe.", "",
        f"At 100 bps the primary returned **{float(primary_100['full_annual_return']) * 100:.2f}%** versus core **{float(core_100['full_annual_return']) * 100:.2f}%**.", "",
        f"ML annual turnover changed from **{turnover['original_ml']:.2f}** to **{turnover['buffered_ml']:.2f}**; overlay allocation turnover changed from Batch 19 **{turnover['batch19_allocation']:.2f}** to **{turnover['primary_allocation']:.2f}**.", "",
        f"Paired Sharpe lower bound: **{float(paired['one_sided_95pct_lower_sharpe_difference']):.3f}**. Paired annual-return lower bound: **{float(paired['one_sided_95pct_lower_annual_return_difference']) * 100:.3f}%**.", "",
        f"Promotion: **{gates['all']}**. Live execution remains disabled.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name != "result.json"}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"primary_10": primary_10, "core_10": core_10, "batch19_10": batch19_10, "primary_100": primary_100, "core_100": core_100, "turnover": turnover, "confidence": confidence, "paired": paired, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
