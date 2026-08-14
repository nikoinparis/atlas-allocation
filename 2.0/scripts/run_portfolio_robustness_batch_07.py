#!/usr/bin/env python3
"""Adversarial robustness audit for the Batch 06 minimum-variance portfolio."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_covariance_portfolios_batch_06 as batch06
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.point_in_time import compute_path, monthly_rebalance_dates
from src.systematic_trader.research_lab import summarize_periods
from src.systematic_trader.strategy_allocation import (
    cap_non_cash_weights,
    combine_dynamic_weight_histories,
    safe_allocate_two_sleeves,
    shrunk_covariance,
)


OUTPUT = ROOT / "evidence/portfolio_robustness_batch_07"
PORTFOLIO_REGISTRY_PATH = ROOT / "research_registry/portfolio_candidates.json"
MANIFEST_PATH = ROOT / "config/portfolios/covariance_minimum_variance_v1.json"
BOOTSTRAP_SAMPLES = 20_000
BLOCK_WEEKS = 13
ROLLING_WEEKS = 156
ROLLING_STEP_WEEKS = 52
STRESS_COST_BPS = 50.0
RULES = {
    "rolling_windows": {
        "window_weeks": ROLLING_WEEKS,
        "step_weeks": ROLLING_STEP_WEEKS,
        "minimum_positive_return_fraction": 0.80,
        "minimum_positive_sharpe_fraction": 0.75,
        "minimum_median_sharpe": 0.40,
        "maximum_allowed_drawdown": -0.35,
    },
    "bootstrap": {
        "samples": BOOTSTRAP_SAMPLES,
        "block_weeks": BLOCK_WEEKS,
        "confidence": 0.95,
        "minimum_return_lower_bound": 0.0,
        "minimum_sharpe_lower_bound": 0.0,
        "maximum_drawdown_lower_bound": -0.40,
    },
    "input_stress": {
        "delays_weeks": [1, 4, 13],
        "synthetic_revision_bps": 5.0,
        "rounded_decimal_places": 4,
        "missing_every_nth_observation": 10,
        "minimum_annual_return": 0.0,
        "minimum_sharpe": 0.50,
        "maximum_allowed_drawdown": -0.30,
    },
    "allocator_fallback": "equal weight on malformed or non-finite covariance",
    "cost_bps": STRESS_COST_BPS,
}


def quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def lightweight_metrics(values: list[float]) -> tuple[float, float, float, float]:
    annual_return = math.prod(1.0 + value for value in values) ** (52.0 / len(values)) - 1.0
    volatility = statistics.stdev(values) * math.sqrt(52.0)
    sharpe = statistics.fmean(values) / statistics.stdev(values) * math.sqrt(52.0) if volatility > 0 else 0.0
    wealth = 1.0
    peak = 1.0
    drawdown = 0.0
    for value in values:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1.0)
    return annual_return, sharpe, drawdown, volatility


def transformed_observations(
    known_dates: list[str], sleeve_returns: dict[str, dict[str, float]], scenario: str
) -> tuple[list[str], dict[str, list[float]]]:
    selected = list(known_dates)
    if scenario == "missing_every_10th":
        selected = [day for index, day in enumerate(selected) if (index + 1) % 10 != 0]
    observations: dict[str, list[float]] = {}
    for name in batch06.SLEEVES:
        values = [sleeve_returns[name][day] for day in selected]
        if scenario == "rounded_4dp":
            values = [round(value, 4) for value in values]
        elif scenario == "synthetic_revision_5bps":
            revised = []
            for day, value in zip(selected, values):
                sign = 1.0 if int(hashlib.sha256(f"{day}|{name}".encode()).hexdigest()[-1], 16) % 2 else -1.0
                revised.append(value + sign * 5.0 / 10_000.0)
            values = revised
        observations[name] = values
    return selected, observations


def stress_coefficients(
    dates: list[str], sleeve_returns: dict[str, dict[str, float]], *, scenario: str, delay_weeks: int
) -> tuple[dict[str, dict[str, float]], dict[str, int]]:
    rebalances = monthly_rebalance_dates(dates, include_sample_endpoint=False)
    current = {name: 0.5 for name in batch06.SLEEVES}
    result: dict[str, dict[str, float]] = {}
    fallback_counts = {"insufficient_history": 0, "invalid_covariance": 0}
    date_index = {day: index for index, day in enumerate(dates)}
    for decision in dates:
        if decision in rebalances:
            cutoff_index = max(0, date_index[decision] - delay_weeks)
            cutoff = dates[cutoff_index]
            known = [
                day for day in dates if day <= cutoff
                and all(day in sleeve_returns[name] for name in batch06.SLEEVES)
            ][-batch06.PRIMARY_LOOKBACK:]
            selected, observations = transformed_observations(known, sleeve_returns, scenario)
            if len(selected) < batch06.MINIMUM_OBSERVATIONS:
                current = {name: 0.5 for name in batch06.SLEEVES}
                fallback_counts["insufficient_history"] += 1
            else:
                covariance = shrunk_covariance(
                    observations, diagonal_shrinkage=batch06.PRIMARY_SHRINKAGE
                )
                current, reason = safe_allocate_two_sleeves(
                    "minimum_variance", covariance, sleeve_names=batch06.SLEEVES,
                    maximum_weight=batch06.MAXIMUM_SLEEVE_WEIGHT,
                )
                fallback_counts["invalid_covariance"] += reason is not None
        result[decision] = dict(current)
    return result, fallback_counts


def evaluate_scenario(
    dates, histories, sleeve_returns, simple_returns, *, name: str, delay_weeks: int = 0
):
    coefficients, fallback_counts = stress_coefficients(
        dates, sleeve_returns, scenario=name, delay_weeks=delay_weeks
    )
    weights = cap_non_cash_weights(
        combine_dynamic_weight_histories(dates, histories, coefficients),
        maximum_asset_weight=batch06.MAXIMUM_UNDERLYING_ASSET_WEIGHT,
    )
    periods, accounting = compute_path(
        dates, weights, simple_returns, cost_bps=STRESS_COST_BPS
    )
    metrics = summarize_periods(periods)
    passed = (
        float(metrics["annual_return"]) > RULES["input_stress"]["minimum_annual_return"]
        and float(metrics["sharpe_zero_rf"]) >= RULES["input_stress"]["minimum_sharpe"]
        and float(metrics["max_drawdown"]) >= RULES["input_stress"]["maximum_allowed_drawdown"]
        and accounting["fully_invested_pass"] and accounting["unpriced_exposure_pass"]
    )
    return {
        "scenario": name, "delay_weeks": delay_weeks, **metrics,
        **fallback_counts, "fully_invested_pass": accounting["fully_invested_pass"],
        "unpriced_exposure_events": accounting["unpriced_exposure_events"], "pass": passed,
    }, periods


def rolling_rows(periods: list[dict[str, float | str]]) -> tuple[list[dict[str, object]], bool]:
    rows = []
    starts = list(range(0, len(periods) - ROLLING_WEEKS + 1, ROLLING_STEP_WEEKS))
    final_start = len(periods) - ROLLING_WEEKS
    if final_start not in starts:
        starts.append(final_start)
    for start in starts:
        window = periods[start : start + ROLLING_WEEKS]
        rows.append({
            "start": window[0]["realization_date"], "end": window[-1]["realization_date"],
            **summarize_periods(window),
        })
    positive_return_fraction = sum(float(row["annual_return"]) > 0.0 for row in rows) / len(rows)
    positive_sharpe_fraction = sum(float(row["sharpe_zero_rf"]) > 0.0 for row in rows) / len(rows)
    passed = (
        positive_return_fraction >= RULES["rolling_windows"]["minimum_positive_return_fraction"]
        and positive_sharpe_fraction >= RULES["rolling_windows"]["minimum_positive_sharpe_fraction"]
        and statistics.median(float(row["sharpe_zero_rf"]) for row in rows) >= RULES["rolling_windows"]["minimum_median_sharpe"]
        and min(float(row["max_drawdown"]) for row in rows) >= RULES["rolling_windows"]["maximum_allowed_drawdown"]
    )
    return rows, passed


def bootstrap_rows(
    selected_periods: list[dict[str, float | str]], equal_periods: list[dict[str, float | str]]
) -> tuple[list[dict[str, object]], bool]:
    selected = [float(row["net_return"]) for row in selected_periods]
    equal = [float(row["net_return"]) for row in equal_periods]
    generator = random.Random(20260808)
    annual_returns, sharpes, drawdowns, volatility_differences = [], [], [], []
    length = len(selected)
    for _ in range(BOOTSTRAP_SAMPLES):
        indexes: list[int] = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(BLOCK_WEEKS))
        indexes = indexes[:length]
        selected_sample = [selected[index] for index in indexes]
        equal_sample = [equal[index] for index in indexes]
        annual_return, sharpe, drawdown, volatility = lightweight_metrics(selected_sample)
        _, _, _, equal_volatility = lightweight_metrics(equal_sample)
        annual_returns.append(annual_return)
        sharpes.append(sharpe)
        drawdowns.append(drawdown)
        volatility_differences.append(volatility - equal_volatility)
    rows = [
        {"metric": "annual_return", "lower_2_5": quantile(annual_returns, 0.025), "median": quantile(annual_returns, 0.5), "upper_97_5": quantile(annual_returns, 0.975)},
        {"metric": "sharpe", "lower_2_5": quantile(sharpes, 0.025), "median": quantile(sharpes, 0.5), "upper_97_5": quantile(sharpes, 0.975)},
        {"metric": "max_drawdown", "lower_2_5": quantile(drawdowns, 0.025), "median": quantile(drawdowns, 0.5), "upper_97_5": quantile(drawdowns, 0.975)},
        {"metric": "annual_volatility_difference_vs_equal", "lower_2_5": quantile(volatility_differences, 0.025), "median": quantile(volatility_differences, 0.5), "upper_97_5": quantile(volatility_differences, 0.975)},
    ]
    by_metric = {row["metric"]: row for row in rows}
    passed = (
        float(by_metric["annual_return"]["lower_2_5"]) > RULES["bootstrap"]["minimum_return_lower_bound"]
        and float(by_metric["sharpe"]["lower_2_5"]) > RULES["bootstrap"]["minimum_sharpe_lower_bound"]
        and float(by_metric["max_drawdown"]["lower_2_5"]) >= RULES["bootstrap"]["maximum_drawdown_lower_bound"]
    )
    return rows, passed


def failure_rows() -> tuple[list[dict[str, object]], bool]:
    cases = {
        "non_finite": {"trend_v4": {"trend_v4": float("nan"), "defensive": 0.0}, "defensive": {"trend_v4": 0.0, "defensive": 0.1}},
        "negative_variance": {"trend_v4": {"trend_v4": -0.1, "defensive": 0.0}, "defensive": {"trend_v4": 0.0, "defensive": 0.1}},
        "missing_sleeve": {"trend_v4": {"trend_v4": 0.1}},
        "zero_variance": {"trend_v4": {"trend_v4": 0.0, "defensive": 0.0}, "defensive": {"trend_v4": 0.0, "defensive": 0.0}},
    }
    rows = []
    for name, covariance in cases.items():
        weights, reason = safe_allocate_two_sleeves(
            "minimum_variance", covariance, sleeve_names=batch06.SLEEVES,
            maximum_weight=batch06.MAXIMUM_SLEEVE_WEIGHT,
        )
        expected_fallback = name != "zero_variance"
        passed = weights == {"trend_v4": 0.5, "defensive": 0.5} and bool(reason) == expected_fallback
        rows.append({
            "case": name, "trend_v4_weight": weights["trend_v4"],
            "defensive_weight": weights["defensive"], "fallback_reason": reason or "",
            "expected_fallback": expected_fallback, "pass": passed,
        })
    return rows, all(row["pass"] for row in rows)


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_report(result, input_rows, rolling, bootstrap):
    baseline = next(row for row in input_rows if row["scenario"] == "baseline")
    by_metric = {row["metric"]: row for row in bootstrap}
    return "\n".join([
        "# Portfolio Robustness — Batch 07", "",
        "The Batch 06 development-selected minimum-variance portfolio was stressed at 50 bps using rolling windows, serial block bootstrap, stale and synthetically revised covariance observations, missing estimator inputs, and malformed covariance fallbacks.", "",
        f"- Overall robustness gate: **{'PASS' if result['robustness_pass'] else 'FAIL'}**.",
        f"- Baseline at 50 bps: **{float(baseline['annual_return']) * 100:.2f}%** annual return, **{float(baseline['sharpe_zero_rf']):.3f}** Sharpe, **{float(baseline['max_drawdown']) * 100:.2f}%** drawdown.",
        f"- Rolling 3-year windows: **{len(rolling)}** evaluated; worst drawdown **{min(float(row['max_drawdown']) for row in rolling) * 100:.2f}%**.",
        f"- Bootstrap 95% annual-return interval: **{float(by_metric['annual_return']['lower_2_5']) * 100:.2f}% to {float(by_metric['annual_return']['upper_97_5']) * 100:.2f}%**.",
        f"- Bootstrap 95% Sharpe interval: **{float(by_metric['sharpe']['lower_2_5']):.3f} to {float(by_metric['sharpe']['upper_97_5']):.3f}**.", "",
        "Passing this batch freezes the rules for forward observation; it does not make the portfolio final, survivorship-safe, or approved for real money.", "",
    ])


def build():
    portfolio_registry = json.loads(PORTFOLIO_REGISTRY_PATH.read_text(encoding="utf-8"))
    candidate = portfolio_registry["candidates"][0]
    if candidate["method"] != "minimum_variance":
        raise ValueError("Batch 07 requires the Batch 06 minimum-variance selection")

    strategy_registry = json.loads(batch06.REGISTRY_PATH.read_text(encoding="utf-8"))
    trend = next(item for item in strategy_registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    defensive = next(item for item in strategy_registry["candidates"] if item.get("family") == "defensive")
    store = batch06.SnapshotStore(batch06.STORE_ROOT)
    manifest = batch06.latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    payload = batch06.STORE_ROOT / snapshot_id / "payload"
    all_assets = sorted(json.loads(batch06.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = batch06.prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=batch06.parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=batch06.date(2005, 1, 7), expected_symbols=all_assets,
    )
    log_returns = batch06.weekly_log_returns(dates, all_assets, prices)
    simple_returns = {day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()} for day, row in log_returns.items()}
    trend_signals, _ = batch06.reconstruct_five_signals(dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns)
    non_momentum, _, _ = batch06.reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    runs = {
        "trend_v4": batch06.run_experiment(spec=batch06.make_spec(trend), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=trend_signals, prices=prices, simple_returns=simple_returns),
        "defensive": batch06.run_experiment(spec=batch06.make_spec(defensive), snapshot_id=snapshot_id, dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=non_momentum, prices=prices, simple_returns=simple_returns),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = batch06.sleeve_return_panel(runs)

    scenarios = [("baseline", 0), ("baseline", 1), ("baseline", 4), ("baseline", 13), ("rounded_4dp", 0), ("synthetic_revision_5bps", 0), ("missing_every_10th", 0)]
    input_rows, scenario_periods = [], {}
    for scenario, delay in scenarios:
        label = scenario if delay == 0 else f"delay_{delay}_weeks"
        row, periods = evaluate_scenario(
            dates, histories, sleeve_returns, simple_returns, name=scenario, delay_weeks=delay
        )
        row["scenario"] = label
        input_rows.append(row)
        scenario_periods[label] = periods
    input_pass = all(row["pass"] for row in input_rows)
    rolling, rolling_pass = rolling_rows(scenario_periods["baseline"])

    _, equal_periods, _, _ = batch06.evaluate_method(
        dates, histories, sleeve_returns, simple_returns, method="equal_weight",
        lookback=batch06.PRIMARY_LOOKBACK, shrinkage=batch06.PRIMARY_SHRINKAGE,
        cost_bps=STRESS_COST_BPS,
    )
    bootstrap, bootstrap_pass = bootstrap_rows(scenario_periods["baseline"], equal_periods)
    failures, failure_pass = failure_rows()
    robust = rolling_pass and bootstrap_pass and input_pass and failure_pass

    candidate["portfolio_robustness_batch_07"] = {
        "rolling_windows_pass": rolling_pass,
        "bootstrap_uncertainty_pass": bootstrap_pass,
        "input_stress_pass": input_pass,
        "allocator_failure_pass": failure_pass,
        "robustness_pass": robust,
    }
    candidate["status"] = "frozen_forward_candidate" if robust else "provisional_portfolio_fragile"
    passed_gates = candidate.setdefault("passed_gates", [])
    for gate, passed in (
        ("rolling_subperiod_stability", rolling_pass),
        ("block_bootstrap_uncertainty", bootstrap_pass),
        ("delayed_and_synthetic_revision_covariance_stability", input_pass),
        ("allocator_failure_fallback", failure_pass),
    ):
        if passed and gate not in passed_gates:
            passed_gates.append(gate)
    if robust:
        MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
        frozen_at = datetime.now(timezone.utc).isoformat()
        frozen_manifest = {
            "schema_version": 1,
            "portfolio_version": "covariance_minimum_variance_v1",
            "status": "frozen_forward_candidate",
            "frozen_at_utc": frozen_at,
            "source_snapshot_id": snapshot_id,
            "source_data_through": dates[-1],
            "first_eligible_untouched_decision_date": "2026-08-14",
            "method": "minimum_variance",
            "constituent_candidates": candidate["constituent_candidates"],
            "configuration": candidate["configuration"],
            "code_sha256": {
                "strategy_allocation.py": sha256(ROOT / "src/systematic_trader/strategy_allocation.py"),
                "batch_06_runner.py": sha256(ROOT / "scripts/run_covariance_portfolios_batch_06.py"),
                "batch_07_runner.py": sha256(ROOT / "scripts/run_portfolio_robustness_batch_07.py"),
            },
            "final": False,
            "approved_for_live_trading": False,
            "required_untouched_weeks": 52,
        }
        MANIFEST_PATH.write_text(json.dumps(frozen_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        candidate["frozen_manifest"] = str(MANIFEST_PATH.relative_to(ROOT))
        candidate["forward_clock"] = {
            "first_eligible_decision_date": "2026-08-14", "required_weeks": 52,
            "observed_weeks": 0,
        }
    portfolio_registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    PORTFOLIO_REGISTRY_PATH.write_text(json.dumps(portfolio_registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "portfolio_robustness_batch_07", "source_snapshot_id": snapshot_id,
        "portfolio_candidate_id": candidate["portfolio_candidate_id"],
        "rules_fixed_before_results": RULES,
        "rolling_windows_pass": rolling_pass, "bootstrap_uncertainty_pass": bootstrap_pass,
        "input_stress_pass": input_pass, "allocator_failure_pass": failure_pass,
        "robustness_pass": robust,
        "frozen_manifest": str(MANIFEST_PATH.relative_to(ROOT)) if robust else None,
        "limitations": [
            "The frozen clock starts only after all data used in design; it currently has zero untouched observations.",
            "Synthetic revisions are stress tests, not substitutes for a second real immutable data vintage.",
            "The ETF universe remains survivorship-prone.",
            "Bootstrap intervals describe historical sampling uncertainty, not guaranteed future bounds.",
        ],
    }
    return result, {
        "rolling_windows.csv": rolling, "bootstrap_uncertainty.csv": bootstrap,
        "input_stress.csv": input_rows, "allocator_failures.csv": failures,
    }, portfolio_registry


def main():
    result, tables, _ = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        write_csv(OUTPUT / name, rows)
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in tables}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(make_report(result, tables["input_stress.csv"], tables["rolling_windows.csv"], tables["bootstrap_uncertainty.csv"]), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("rolling_windows_pass", "bootstrap_uncertainty_pass", "input_stress_pass", "allocator_failure_pass", "robustness_pass", "frozen_manifest")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
