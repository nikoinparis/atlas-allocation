#!/usr/bin/env python3
"""Evaluate causally tiered ML confidence as a capped overlay on the frozen core."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_cross_sectional_factor_baseline_batch_16 as batch16
from scripts import run_robust_cross_sectional_ml_batch_17 as batch17
from scripts import run_treasury_term_structure_batch_14 as batch14
from src.systematic_trader.data_vintage import parse_utc, sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.ml_confidence import causal_weight, guarded_weight, raw_confidence
from src.systematic_trader.term_structure_challenger import correlation
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

PROGRAM = ROOT / "config/ml_confidence_overlay_v1.json"
PREDICTIONS = ROOT / "evidence/robust_cross_sectional_ml_batch_17/predictions.csv"
DATASET = ROOT / "evidence/cross_sectional_factor_baseline_batch_16/factor_dataset.csv"
OUTPUT = ROOT / "evidence/ml_confidence_overlay_batch_18"
PROJECTION_COLUMNS = (
    "outer_year", "decision_date", "label_end_date", "asset", "target_rank", "prediction_real",
    "prediction_label_shuffle", "prediction_random_features", "prediction_stale_1m", "prediction_stale_3m",
)
VARIANTS = ("core_only", "constant_10", "constant_20", "constant_30", "confidence_tiered_unguarded", "confidence_tiered_guarded", "extreme_only")
COSTS = (10.0, 50.0, 100.0)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: format(value, ".9g") if isinstance(value, float) else value for key, value in row.items()} for row in rows)


def projection_hash(rows: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(("\x1f".join(row[column] for column in PROJECTION_COLUMNS) + "\n").encode())
    return digest.hexdigest()


def frozen_winner_periods(cost_bps: float) -> list[dict[str, object]]:
    batch06 = batch14.batch06
    frozen = json.loads((ROOT / "config/portfolios/covariance_minimum_variance_v1.json").read_text(encoding="utf-8"))
    snapshot_id = str(frozen["source_snapshot_id"])
    payload = batch14.ETF_STORE / snapshot_id / "payload"
    assets = sorted(json.loads(batch06.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    manifest = json.loads((batch14.ETF_STORE / snapshot_id / "manifest.json").read_text(encoding="utf-8"))
    dates, prices, _ = batch06.prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=assets,
    )
    logs = batch06.weekly_log_returns(dates, assets, prices)
    simple = {day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()} for day, row in logs.items()}
    registry = json.loads(batch06.REGISTRY_PATH.read_text(encoding="utf-8"))
    trend = next(item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    defensive = next(item for item in registry["candidates"] if item.get("family") == "defensive")
    trend_signals, _ = batch06.reconstruct_five_signals(dates=dates, assets=assets, prices=prices, weekly_log_returns=logs)
    non_momentum, _, _ = batch06.reconstruct_non_momentum_signals(
        dates=dates, assets=assets, prices=prices, weekly_log_returns=logs,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    runs = {
        "trend_v4": batch06.run_experiment(spec=batch06.make_spec(trend), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=trend_signals, prices=prices, simple_returns=simple),
        "defensive": batch06.run_experiment(spec=batch06.make_spec(defensive), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=non_momentum, prices=prices, simple_returns=simple),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = batch06.sleeve_return_panel(runs)
    _, periods, _, _ = batch06.evaluate_method(
        dates, histories, sleeve_returns, simple, method="minimum_variance",
        lookback=batch06.PRIMARY_LOOKBACK, shrinkage=batch06.PRIMARY_SHRINKAGE, cost_bps=cost_bps,
    )
    return periods


def confidence_decisions(predictions: list[dict[str, str]], ml_periods_10: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in predictions:
        grouped[row["decision_date"]].append(row)
    future_ic = {str(row["decision_date"]): float(row["rank_ic"]) for row in batch17.monthly_ics(predictions, "real")}
    realized = sorted((str(row["realization_date"]), float(row["net_return"])) for row in ml_periods_10)
    prior_scores: list[float] = []
    decisions: list[dict[str, object]] = []
    for decision in sorted(grouped):
        ranked = sorted(grouped[decision], key=lambda row: (float(row["prediction_real"]), row["asset"]), reverse=True)
        selected, comparison = ranked[:5], ranked[5:10]
        audit = raw_confidence(
            [float(row["prediction_real"]) for row in selected],
            [float(row["prediction_real"]) for row in comparison],
            [float(row["prediction_sign_agreement_real"]) for row in selected],
            [float(row["prediction_member_std_real"]) for row in selected],
            [float(row["prediction_family_std_real"]) for row in selected],
        )
        desired, thresholds = causal_weight(float(audit["raw_confidence"]), prior_scores)
        available_returns = [value for day, value in realized if day <= decision]
        guarded, risk = guarded_weight(desired, available_returns)
        extreme = 0.30 if thresholds["p95"] is not None and float(audit["raw_confidence"]) >= float(thresholds["p95"]) else 0.0
        decisions.append({
            "decision_date": decision, **audit, "prior_confidence_observations": len(prior_scores),
            **{f"threshold_{key}": value for key, value in thresholds.items()},
            "desired_weight": desired, "guarded_weight": guarded, "extreme_only_weight": extreme,
            **risk, "future_rank_ic_evaluation_only": future_ic[decision],
        })
        prior_scores.append(float(audit["raw_confidence"]))
    return decisions


def weight_history(decisions: list[dict[str, object]], variant: str) -> dict[str, float]:
    if variant == "core_only":
        return {str(row["decision_date"]): 0.0 for row in decisions}
    if variant.startswith("constant_"):
        value = float(variant.split("_")[1]) / 100.0
        return {str(row["decision_date"]): value for row in decisions}
    field = {
        "confidence_tiered_unguarded": "desired_weight",
        "confidence_tiered_guarded": "guarded_weight",
        "extreme_only": "extreme_only_weight",
    }[variant]
    return {str(row["decision_date"]): float(row[field]) for row in decisions}


def combine(
    winner_periods: list[dict[str, object]], ml_periods: list[dict[str, object]],
    decisions: list[dict[str, object]], variant: str, cost_bps: float,
) -> list[dict[str, object]]:
    winner = {str(row["realization_date"]): row for row in winner_periods}
    ml = {str(row["realization_date"]): row for row in ml_periods}
    weights = weight_history(decisions, variant)
    decision_dates = sorted(weights)
    current_weight = 0.0
    output = []
    for realization in sorted(set(winner) & set(ml)):
        ml_row = ml[realization]
        weekly_decision = str(ml_row["decision_date"])
        eligible = [day for day in decision_dates if day <= weekly_decision]
        if not eligible:
            continue
        target_weight = weights[eligible[-1]]
        allocation_turnover = abs(target_weight - current_weight)
        extra_cost = allocation_turnover * cost_bps / 10_000.0
        winner_return = float(winner[realization]["net_return"])
        ml_return = float(ml_row["net_return"])
        combined_return = (1.0 - target_weight) * winner_return + target_weight * ml_return - extra_cost
        output.append({
            "variant": variant, "cost_bps": cost_bps, "decision_date": weekly_decision,
            "realization_date": realization, "ml_weight": target_weight,
            "winner_net_return": winner_return, "ml_net_return": ml_return,
            "allocation_turnover": allocation_turnover, "allocation_cost": extra_cost,
            "net_return": combined_return,
        })
        current_weight = target_weight
    return output


def metrics(rows: list[dict[str, object]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in selected]).to_dict()
    result["annual_allocation_turnover"] = statistics.fmean(float(row["allocation_turnover"]) for row in selected) * 52.0
    result["mean_ml_weight"] = statistics.fmean(float(row["ml_weight"]) for row in selected)
    return result


def calibration(decisions: list[dict[str, object]]) -> dict[str, object]:
    eligible = [row for row in decisions if int(row["prior_confidence_observations"]) >= 24]
    active = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["desired_weight"]) > 0.0]
    inactive = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if float(row["desired_weight"]) == 0.0]
    by_weight = {}
    for weight in (0.0, 0.1, 0.2, 0.3):
        values = [float(row["future_rank_ic_evaluation_only"]) for row in eligible if abs(float(row["desired_weight"]) - weight) < 1e-12]
        by_weight[str(weight)] = {"months": len(values), "mean_future_rank_ic": statistics.fmean(values) if values else None}
    active_mean = statistics.fmean(active)
    inactive_mean = statistics.fmean(inactive)
    return {
        "eligible_months": len(eligible), "active_months": len(active), "inactive_months": len(inactive),
        "active_mean_future_rank_ic": active_mean, "inactive_mean_future_rank_ic": inactive_mean,
        "by_desired_weight": by_weight,
        "pass": active_mean > inactive_mean and active_mean > 0.0,
    }


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    predictions = read_csv(PREDICTIONS)
    projected = projection_hash(predictions)
    expected = str(program["source_prediction_projection_sha256_before_diagnostics"])
    if projected != expected:
        raise RuntimeError(f"original prediction projection changed: {projected} != {expected}")
    required = {"prediction_member_std_real", "prediction_family_std_real", "prediction_sign_agreement_real"}
    if not predictions or not required.issubset(predictions[0]):
        raise RuntimeError("confidence diagnostics are absent from canonical predictions")

    dataset = read_csv(DATASET)
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
    decisions = confidence_decisions(predictions, ml_periods[10.0])
    winner_periods = {cost: frozen_winner_periods(cost) for cost in COSTS}
    all_periods: dict[tuple[str, float], list[dict[str, object]]] = {}
    scoreboard = []
    for variant in VARIANTS:
        for cost in COSTS:
            periods = combine(winner_periods[cost], ml_periods[cost], decisions, variant, cost)
            all_periods[(variant, cost)] = periods
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in metrics(periods).items()},
                **{f"oos_2016_2020_{key}": value for key, value in metrics(periods, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in metrics(periods, "2021-01-01").items()},
            })
    primary = next(row for row in scoreboard if row["variant"] == "confidence_tiered_guarded" and row["cost_bps"] == 10.0)
    primary_100 = next(row for row in scoreboard if row["variant"] == "confidence_tiered_guarded" and row["cost_bps"] == 100.0)
    core = next(row for row in scoreboard if row["variant"] == "core_only" and row["cost_bps"] == 10.0)
    primary_periods = all_periods[("confidence_tiered_guarded", 10.0)]
    core_periods = all_periods[("core_only", 10.0)]
    paired = batch17.paired_bootstrap_advantage(
        [float(row["net_return"]) for row in primary_periods],
        [float(row["net_return"]) for row in core_periods], seed=20260818,
    )
    calibration_result = calibration(decisions)
    gates = {
        "annual_return": float(primary["full_annual_return"]) > float(core["full_annual_return"]),
        "sharpe": float(primary["full_sharpe_zero_rf"]) > float(core["full_sharpe_zero_rf"]),
        "maximum_drawdown": float(primary["full_max_drawdown"]) >= float(core["full_max_drawdown"]),
        "paired_sharpe": bool(paired["sharpe_advantage_statistically_positive"]),
        "later_cost": float(primary_100["oos_2016_2020_annual_return"]) > 0.0 and float(primary_100["oos_2021_present_annual_return"]) > 0.0,
        "confidence_calibration": bool(calibration_result["pass"]),
        "survivorship_safe": False, "untouched_forward_52w": False,
    }
    gates["all"] = all(gates.values())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 18,
        "track": "causal_ml_confidence_overlay", "program_sha256": sha256(PROGRAM),
        "source_prediction_projection_sha256": projected,
        "prediction_projection_unchanged": projected == expected,
        "confidence_calibration": calibration_result, "paired_bootstrap_10bps": paired,
        "promotion_gates": gates, "promoted": gates["all"], "live_trading_approved": False,
        "limitations": [
            "Confidence is model consensus, not probability of profit and can be jointly wrong.",
            "The ETF universe remains survivorship-prone and the experiment remains retrospective.",
            "The primary rule was predeclared, but 52 untouched forward weeks are still required.",
            "Sleeve costs are retained independently and cross-sleeve trade netting is not assumed.",
        ],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "confidence_decisions.csv", decisions)
    write_csv(OUTPUT / "portfolio_scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "primary_returns_10bps.csv", primary_periods)
    report = "\n".join([
        "# Causal ML Confidence Overlay — Batch 18", "",
        f"The primary guarded confidence overlay produced **{float(primary['full_annual_return']) * 100:.2f}%** annual return, **{float(primary['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(primary['full_max_drawdown']) * 100:.2f}%** maximum drawdown at 10 bps.", "",
        f"The frozen core over the same dates produced **{float(core['full_annual_return']) * 100:.2f}%** annual return, **{float(core['full_sharpe_zero_rf']):.3f}** Sharpe, and **{float(core['full_max_drawdown']) * 100:.2f}%** maximum drawdown.", "",
        f"High-confidence calibration passed: **{calibration_result['pass']}**. Its active-month future rank IC was **{float(calibration_result['active_mean_future_rank_ic']):.4f}** versus **{float(calibration_result['inactive_mean_future_rank_ic']):.4f}** when inactive.", "",
        f"The paired-bootstrap lower Sharpe-difference bound was **{float(paired['one_sided_95pct_lower_sharpe_difference']):.3f}**; statistically positive: **{paired['sharpe_advantage_statistically_positive']}**.", "",
        f"Promotion: **{gates['all']}**. The frozen winner was not changed and live execution remains disabled.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name != "result.json"}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"primary": primary, "core": core, "calibration": calibration_result, "paired": paired, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
