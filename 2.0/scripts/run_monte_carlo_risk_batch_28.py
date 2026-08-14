#!/usr/bin/env python3
"""Run predeclared Monte Carlo risk validation on the frozen portfolio."""

from __future__ import annotations

import csv
import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_covariance_portfolios_batch_06 as batch06
from scripts import run_portfolio_robustness_batch_07 as batch07
from src.systematic_trader.data_vintage import parse_utc, sha256
from src.systematic_trader.monte_carlo_risk import (
    path_statistics,
    quantile,
    simulate_paths,
    source_best_fit_direction,
    summarize_simulations,
    wilson_lower,
    worst_compounded_block,
)

PROGRAM = ROOT / "config/monte_carlo_risk_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_28/source_rule_review.json"
METHODOLOGICAL_AMENDMENT = ROOT / "evidence/monte_carlo_risk_batch_28/post_result_methodological_amendment.json"
PORTFOLIO_MANIFEST = ROOT / "config/portfolios/covariance_minimum_variance_v1.json"
FORWARD_PROTOCOL = ROOT / "config/forward/covariance_minimum_variance_v1.json"
OUTPUT = ROOT / "evidence/monte_carlo_risk_batch_28"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
BASELINE_EVIDENCE = ROOT / "evidence/portfolio_robustness_batch_07/input_stress.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"no rows for {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_frozen_files() -> dict[str, object]:
    forward = json.loads(FORWARD_PROTOCOL.read_text(encoding="utf-8"))
    checks = dict(forward["pinned_files_sha256"])
    portfolio = json.loads(PORTFOLIO_MANIFEST.read_text(encoding="utf-8"))
    checks["scripts/run_portfolio_robustness_batch_07.py"] = portfolio["code_sha256"]["batch_07_runner.py"]
    mismatches = []
    for name, expected in checks.items():
        actual = sha256(ROOT / name)
        if actual != expected:
            mismatches.append({"file": name, "expected": expected, "actual": actual})
    if mismatches:
        raise RuntimeError(f"frozen inputs changed: {mismatches}")
    return {"files_checked": len(checks), "intact": True, "mismatches": []}


def reconstruct_frozen_periods() -> tuple[list[dict[str, float | str]], dict[str, object]]:
    portfolio = json.loads(PORTFOLIO_MANIFEST.read_text(encoding="utf-8"))
    snapshot_id = str(portfolio["source_snapshot_id"])
    snapshot_manifest = json.loads((batch06.STORE_ROOT / snapshot_id / "manifest.json").read_text(encoding="utf-8"))
    payload = batch06.STORE_ROOT / snapshot_id / "payload"
    registry = json.loads(batch06.REGISTRY_PATH.read_text(encoding="utf-8"))
    constituent_ids = set(portfolio["constituent_candidates"])
    trend = next(item for item in registry["candidates"] if item["candidate_id"] in constituent_ids and item.get("family") != "defensive")
    defensive = next(item for item in registry["candidates"] if item["candidate_id"] in constituent_ids and item.get("family") == "defensive")
    all_assets = sorted(json.loads(batch06.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = batch06.prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(snapshot_manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=all_assets,
    )
    log_returns = batch06.weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    trend_signals, _ = batch06.reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
    )
    non_momentum, _, _ = batch06.reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    runs = {
        "trend_v4": batch06.run_experiment(
            spec=batch06.make_spec(trend), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS,
            strategy_panels=trend_signals, prices=prices, simple_returns=simple_returns,
        ),
        "defensive": batch06.run_experiment(
            spec=batch06.make_spec(defensive), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS,
            strategy_panels=non_momentum, prices=prices, simple_returns=simple_returns,
        ),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = batch06.sleeve_return_panel(runs)
    summary, periods = batch07.evaluate_scenario(
        dates, histories, sleeve_returns, simple_returns, name="baseline", delay_weeks=0,
    )
    expected = next(row for row in read_csv(BASELINE_EVIDENCE) if row["scenario"] == "baseline")
    fields = ("annual_return", "sharpe_zero_rf", "max_drawdown", "annual_volatility")
    differences = {field: abs(float(summary[field]) - float(expected[field])) for field in fields}
    if max(differences.values()) > 1e-12:
        raise RuntimeError(f"frozen baseline reconstruction mismatch: {differences}")
    audit = {
        "source_snapshot_id": snapshot_id, "observations": len(periods),
        "first_realization_date": periods[0]["realization_date"], "last_realization_date": periods[-1]["realization_date"],
        "baseline_metrics": {field: float(summary[field]) for field in fields},
        "maximum_reconstruction_difference": max(differences.values()), "exact_reconstruction_pass": True,
    }
    return periods, audit


def historical_metrics(values: list[float]) -> dict[str, float | int]:
    row = path_statistics(values)
    volatility = statistics.stdev(values) * math.sqrt(52.0)
    sharpe = statistics.fmean(values) / statistics.stdev(values) * math.sqrt(52.0)
    return {
        "observations": len(values), "annual_return": row["annual_return"],
        "annual_volatility": volatility, "sharpe_zero_rf": sharpe,
        "max_drawdown": row["max_drawdown"], "total_return": row["terminal_return"],
    }


def production_simulations(values: list[float], program: dict[str, object], worst_block: list[float]) -> list[dict[str, object]]:
    settings = program["production_simulation"]
    methods = ["source_gaussian_gbm", "iid_empirical", "moving_block_13w", "moving_block_13w_mean_haircut"]
    rows = []
    for method_number, method in enumerate(methods):
        for horizon in settings["horizons_weeks"]:
            simulations = simulate_paths(
                values, weeks=int(horizon), paths=int(settings["paths_per_method_horizon"]), method=method,
                seed=int(settings["seed"]) + method_number * 10_000 + int(horizon), block_weeks=13,
            )
            rows.append({"method": method, "horizon_weeks": horizon, **summarize_simulations(simulations)})
    horizon = 260
    simulations = simulate_paths(
        values, weeks=horizon, paths=int(settings["paths_per_method_horizon"]), method="forced_worst_13w_then_blocks",
        seed=int(settings["seed"]) + 90_000 + horizon, block_weeks=13, forced_initial_block=worst_block,
    )
    rows.append({"method": "forced_worst_13w_then_blocks", "horizon_weeks": horizon, **summarize_simulations(simulations)})
    return rows


def rolling_calibration(values: list[float], dates: list[str], program: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, float | int | bool]]:
    settings = program["rolling_calibration"]
    minimum, horizon, step = int(settings["minimum_training_weeks"]), int(settings["forecast_weeks"]), int(settings["step_weeks"])
    rows = []
    for origin_number, origin in enumerate(range(minimum, len(values) - horizon + 1, step)):
        simulations = simulate_paths(
            values[:origin], weeks=horizon, paths=int(settings["paths_per_origin"]), method="moving_block_13w",
            seed=int(settings["seed"]) + origin_number, block_weeks=13,
        )
        terminal = [float(row["terminal_return"]) for row in simulations]
        drawdowns = [float(row["max_drawdown"]) for row in simulations]
        actual = path_statistics(values[origin : origin + horizon])
        terminal_low, terminal_high = quantile(terminal, .05), quantile(terminal, .95)
        drawdown_low, drawdown_high = quantile(drawdowns, .05), quantile(drawdowns, .95)
        rows.append({
            "origin_date": dates[origin - 1], "realization_end_date": dates[origin + horizon - 1],
            "training_weeks": origin, "forecast_weeks": horizon,
            "terminal_p05": terminal_low, "terminal_p50": quantile(terminal, .50), "terminal_p95": terminal_high,
            "actual_terminal_return": actual["terminal_return"],
            "terminal_90pct_covered": terminal_low <= float(actual["terminal_return"]) <= terminal_high,
            "drawdown_p05": drawdown_low, "drawdown_p50": quantile(drawdowns, .50), "drawdown_p95": drawdown_high,
            "actual_max_drawdown": actual["max_drawdown"],
            "drawdown_90pct_covered": drawdown_low <= float(actual["max_drawdown"]) <= drawdown_high,
            "predicted_probability_loss": sum(value < 0.0 for value in terminal) / len(terminal),
            "actual_loss": float(actual["terminal_return"]) < 0.0,
        })
    terminal_coverage = sum(bool(row["terminal_90pct_covered"]) for row in rows) / len(rows)
    drawdown_coverage = sum(bool(row["drawdown_90pct_covered"]) for row in rows) / len(rows)
    thresholds = program["risk_thresholds"]["calibration"]
    summary = {
        "origins": len(rows), "terminal_90pct_coverage": terminal_coverage,
        "drawdown_90pct_coverage": drawdown_coverage,
        "pass": terminal_coverage >= float(thresholds["minimum_terminal_90pct_coverage"]) and drawdown_coverage >= float(thresholds["minimum_drawdown_90pct_coverage"]),
    }
    return rows, summary


def source_diagnostic(values: list[float], dates: list[str], program: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], bool]:
    settings = program["source_best_fit_diagnostic"]
    minimum, horizon, step = int(settings["minimum_training_weeks"]), int(settings["forecast_weeks"]), int(settings["step_weeks"])
    rows = []
    for count_number, simulations in enumerate(settings["simulation_counts"]):
        for origin_number, origin in enumerate(range(minimum, len(values) - horizon + 1, step)):
            result = source_best_fit_direction(
                values[:origin], values[origin : origin + horizon], simulations=int(simulations),
                seed=int(settings["seed"]) + count_number * 10_000 + origin_number,
            )
            rows.append({"origin_date": dates[origin - 1], "realization_end_date": dates[origin + horizon - 1], **result})
    summaries = []
    for simulations in settings["simulation_counts"]:
        chosen = [row for row in rows if int(row["simulations"]) == int(simulations)]
        successes = sum(bool(row["direction_correct"]) for row in chosen)
        positive_realizations = sum(float(row["realized_return"]) >= 0.0 for row in chosen)
        accuracy = successes / len(chosen)
        majority_accuracy = max(positive_realizations, len(chosen) - positive_realizations) / len(chosen)
        lower = wilson_lower(successes, len(chosen))
        absolute_gate = accuracy >= float(settings["edge_claim_requires_accuracy"]) and lower > float(settings["edge_claim_requires_wilson_lower_bound"])
        summaries.append({
            "simulations": simulations, "origins": len(chosen), "correct": successes,
            "direction_accuracy": accuracy, "wilson_95pct_lower": lower,
            "positive_realizations": positive_realizations,
            "majority_direction_accuracy": majority_accuracy,
            "excess_accuracy_vs_majority": accuracy - majority_accuracy,
            "predeclared_absolute_edge_gate": absolute_gate,
            "edge_gate": absolute_gate and accuracy > majority_accuracy,
        })
    primary = next(row for row in summaries if int(row["simulations"]) == int(settings["primary_simulation_count"]))
    return rows, summaries, bool(primary["edge_gate"])


def safety_gates(path_rows: list[dict[str, object]], calibration: dict[str, object], program: dict[str, object]) -> dict[str, bool]:
    by_key = {(row["method"], int(row["horizon_weeks"])): row for row in path_rows}
    block = by_key[("moving_block_13w", 260)]
    haircut = by_key[("moving_block_13w_mean_haircut", 260)]
    crash = by_key[("forced_worst_13w_then_blocks", 260)]
    thresholds = program["risk_thresholds"]
    gates = {
        "moving_block_5y": float(block["probability_terminal_loss"]) <= float(thresholds["moving_block_5y"]["maximum_probability_terminal_loss"]) and float(block["probability_drawdown_30pct"]) <= float(thresholds["moving_block_5y"]["maximum_probability_drawdown_30pct"]) and float(block["terminal_return_p05"]) >= float(thresholds["moving_block_5y"]["minimum_terminal_return_5pct"]),
        "mean_haircut_5y": float(haircut["probability_terminal_loss"]) <= float(thresholds["mean_haircut_5y"]["maximum_probability_terminal_loss"]) and float(haircut["probability_drawdown_40pct"]) <= float(thresholds["mean_haircut_5y"]["maximum_probability_drawdown_40pct"]) and float(haircut["terminal_return_p05"]) >= float(thresholds["mean_haircut_5y"]["minimum_terminal_return_5pct"]),
        "forced_crash_5y": float(crash["probability_recover_initial_wealth"]) >= float(thresholds["forced_crash_5y"]["minimum_probability_recover_initial_wealth"]) and float(crash["probability_terminal_loss"]) <= float(thresholds["forced_crash_5y"]["maximum_probability_terminal_loss"]),
        "rolling_calibration": bool(calibration["pass"]),
    }
    gates["all"] = all(gates.values())
    return gates


def update_inventory() -> None:
    rows = read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "11":
            row.update(status="tested_batch_28", reason="Source Gaussian and best-fit diagnostics plus empirical block haircut forced-crash and rolling calibration risk tests completed", next_action="Use as risk evidence only; never as an alpha or live-trading approval")
    write_csv(INVENTORY, rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    frozen_audit = verify_frozen_files()
    periods, reconstruction = reconstruct_frozen_periods()
    values = [round(float(row["net_return"]), 12) for row in periods]
    dates = [str(row["realization_date"]) for row in periods]
    worst_start, worst_block, worst_return = worst_compounded_block(values, 13)
    path_rows = production_simulations(values, program, worst_block)
    calibration_rows, calibration_summary = rolling_calibration(values, dates, program)
    diagnostic_rows, diagnostic_summary, source_edge = source_diagnostic(values, dates, program)
    gates = safety_gates(path_rows, calibration_summary, program)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    historical_rows = [{"decision_date": row["decision_date"], "realization_date": row["realization_date"], "net_return": value} for row, value in zip(periods, values)]
    write_csv(OUTPUT / "frozen_weekly_returns_50bps.csv", historical_rows)
    write_csv(OUTPUT / "path_risk_summary.csv", path_rows)
    write_csv(OUTPUT / "rolling_calibration.csv", calibration_rows)
    write_csv(OUTPUT / "source_best_fit_direction.csv", diagnostic_rows)
    write_csv(OUTPUT / "source_best_fit_summary.csv", diagnostic_summary)
    by_key = {(row["method"], int(row["horizon_weeks"])): row for row in path_rows}
    block = by_key[("moving_block_13w", 260)]
    haircut = by_key[("moving_block_13w_mean_haircut", 260)]
    crash = by_key[("forced_worst_13w_then_blocks", 260)]
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 28,
        "track": "frozen_portfolio_monte_carlo_risk", "program_sha256": sha256(PROGRAM),
        "source_review_sha256": sha256(SOURCE_REVIEW), "portfolio_manifest_sha256": sha256(PORTFOLIO_MANIFEST),
        "post_result_methodological_amendment_sha256": sha256(METHODOLOGICAL_AMENDMENT),
        "forward_protocol_sha256": sha256(FORWARD_PROTOCOL), "frozen_file_audit": frozen_audit,
        "reconstruction_audit": reconstruction, "historical_metrics": historical_metrics(values),
        "worst_historical_13w": {
            "start_index": worst_start, "start_date": dates[worst_start], "end_date": dates[worst_start + 12],
            "compounded_return": worst_return,
        },
        "path_risk": path_rows, "rolling_calibration": calibration_summary,
        "source_best_fit_summary": diagnostic_summary, "source_forecast_edge": source_edge,
        "safety_gates": gates, "risk_validation_pass": bool(gates["all"]),
        "portfolio_promoted": False, "live_trading_approved": False, "execution_enabled": False,
        "limitations": [
            "All simulated distributions are conditional on one survivorship-prone retrospective ETF history.",
            "Block sampling preserves short historical sequences but cannot generate unprecedented market structure or liquidity failure.",
            "The forced crash repeats the worst observed 13-week portfolio block; a future crisis can be deeper, longer, or operationally different.",
            "Return haircuts are scenarios, not estimated probabilities, and thresholds express risk tolerance rather than guarantees.",
            "Monte Carlo evidence does not advance the untouched 52-week forward clock or approve real-money execution."
        ],
    }
    report = [
        "# Frozen Portfolio Monte Carlo Risk — Batch 28", "",
        "This batch uses the repository's Gaussian Monte Carlo and best-fit path as diagnostics, then adds empirical and serial block models for risk estimation. No simulated path changes the portfolio or creates an alpha signal.", "",
        f"Historical reconstruction: **{float(result['historical_metrics']['annual_return']) * 100:.2f}%** annual return, **{float(result['historical_metrics']['sharpe_zero_rf']):.3f}** Sharpe, and **{float(result['historical_metrics']['max_drawdown']) * 100:.2f}%** drawdown across **{result['historical_metrics']['observations']}** weeks.", "",
        f"Five-year 13-week block model: **{float(block['probability_terminal_loss']) * 100:.1f}%** probability of ending below starting wealth, **{float(block['probability_drawdown_30pct']) * 100:.1f}%** probability of a 30% drawdown, and **{float(block['terminal_return_p05']) * 100:.1f}%** fifth-percentile terminal return.", "",
        f"Five-year positive-mean haircut: **{float(haircut['probability_terminal_loss']) * 100:.1f}%** probability of ending below starting wealth and **{float(haircut['terminal_return_p05']) * 100:.1f}%** fifth-percentile terminal return.", "",
        f"Forced worst historical 13-week block ({result['worst_historical_13w']['start_date']} to {result['worst_historical_13w']['end_date']}, **{float(worst_return) * 100:.1f}%**): **{float(crash['probability_recover_initial_wealth']) * 100:.1f}%** recovered starting wealth within five years; **{float(crash['probability_terminal_loss']) * 100:.1f}%** ended below it.", "",
        f"Rolling past-only 90% calibration coverage: terminal return **{float(calibration_summary['terminal_90pct_coverage']) * 100:.1f}%**, maximum drawdown **{float(calibration_summary['drawdown_90pct_coverage']) * 100:.1f}%**, across **{calibration_summary['origins']}** annual origins.", "",
        f"Predeclared risk-validation gate: **{'PASS' if result['risk_validation_pass'] else 'FAIL'}**. Source best-fit forecasting edge: **{source_edge}**. Portfolio promotion/live approval: **False/False**.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps({
        "historical_metrics": result["historical_metrics"], "worst_historical_13w": result["worst_historical_13w"],
        "moving_block_5y": block, "mean_haircut_5y": haircut, "forced_crash_5y": crash,
        "rolling_calibration": calibration_summary, "source_best_fit_summary": diagnostic_summary,
        "safety_gates": gates,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
