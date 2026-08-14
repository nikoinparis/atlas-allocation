#!/usr/bin/env python3
"""Causal drawdown-optimizer comparison against the frozen Batch 06 portfolio."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from skfolio import RiskMeasure
from skfolio.optimization import MeanRisk, ObjectiveFunction

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.run_covariance_portfolios_batch_06 as batch6
from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.non_momentum_signals import reconstruct_non_momentum_signals
from src.systematic_trader.point_in_time import compute_path, monthly_rebalance_dates
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import period_slice, run_experiment, summarize_periods
from src.systematic_trader.strategy_allocation import cap_non_cash_weights, combine_dynamic_weight_histories
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns

PROGRAM_PATH = ROOT / "config/skfolio_drawdown_portfolio_experiment_v1.json"
OUTPUT = ROOT / "evidence/skfolio_drawdown_portfolios_batch_39"
METHODS = ("CDAR", "MAX_DRAWDOWN", "EDAR", "ULCER_INDEX")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = list(rows[0])
    for row in rows[1:]:
        fieldnames.extend(key for key in row if key not in fieldnames)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def exact_manifest(store: SnapshotStore, snapshot_id: str) -> dict[str, object]:
    return next(item for item in store.manifests() if str(item["snapshot_id"]) == snapshot_id)


def inputs(program: dict[str, object]):
    settings = program["data"]
    snapshot_id = str(settings["snapshot_id"])
    store = SnapshotStore(batch6.STORE_ROOT)
    manifest = exact_manifest(store, snapshot_id)
    payload = batch6.STORE_ROOT / snapshot_id / "payload"
    universe = sorted(json.loads(batch6.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = prepare_weekly_adjusted_prices(
        payload / "prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date.fromisoformat(str(settings["start_date"])),
        expected_symbols=universe,
    )
    log_returns = weekly_log_returns(dates, universe, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    trend_signals, _ = reconstruct_five_signals(
        dates=dates, assets=universe, prices=prices, weekly_log_returns=log_returns
    )
    non_momentum, _, _ = reconstruct_non_momentum_signals(
        dates=dates, assets=universe, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    registry = json.loads(batch6.REGISTRY_PATH.read_text(encoding="utf-8"))
    trend = next(item for item in registry["candidates"] if item["candidate_id"] == settings["constituent_candidates"][0])
    defensive = next(item for item in registry["candidates"] if item["candidate_id"] == settings["constituent_candidates"][1])
    runs = {
        "trend_v4": run_experiment(
            spec=batch6.make_spec(trend), snapshot_id=snapshot_id, dates=dates,
            assets=batch6.RISK_ASSETS, strategy_panels=trend_signals, prices=prices,
            simple_returns=simple_returns,
        ),
        "defensive": run_experiment(
            spec=batch6.make_spec(defensive), snapshot_id=snapshot_id, dates=dates,
            assets=batch6.RISK_ASSETS, strategy_panels=non_momentum, prices=prices,
            simple_returns=simple_returns,
        ),
    }
    return dates, simple_returns, {name: run["weights"] for name, run in runs.items()}, batch6.sleeve_return_panel(runs)


def optimize(panel: pd.DataFrame, method: str, minimum: float, maximum: float) -> np.ndarray:
    model = MeanRisk(
        objective_function=ObjectiveFunction.MINIMIZE_RISK,
        risk_measure=RiskMeasure[method],
        min_weights=minimum,
        max_weights=maximum,
        solver="CLARABEL",
    )
    model.fit(panel)
    return np.asarray(model.weights_, dtype=float)


def coefficients(dates, sleeve_returns, method, rules):
    rebalances = monthly_rebalance_dates(dates, include_sample_endpoint=False)
    lookback = int(rules["lookback_weeks"])
    minimum_observations = int(rules["minimum_observations"])
    lower = float(rules["minimum_sleeve_weight"])
    upper = float(rules["maximum_sleeve_weight"])
    current = {name: 0.5 for name in batch6.SLEEVES}
    all_weights = {}
    audit = []
    repeat_max = 0.0
    failures = 0
    for decision in dates:
        if decision in rebalances:
            known = [
                day for day in dates
                if day <= decision and all(day in sleeve_returns[name] for name in batch6.SLEEVES)
            ][-lookback:]
            fallback = len(known) < minimum_observations
            message = ""
            if not fallback:
                panel = pd.DataFrame({name: [sleeve_returns[name][day] for day in known] for name in batch6.SLEEVES}, index=known)
                try:
                    first = optimize(panel, method, lower, upper)
                    repeated = optimize(panel, method, lower, upper)
                    repeat_max = max(repeat_max, float(np.max(np.abs(first - repeated))))
                    if not np.isfinite(first).all() or abs(float(first.sum()) - 1.0) > 1e-8:
                        raise ValueError("invalid optimizer weights")
                    current = dict(zip(batch6.SLEEVES, map(float, first)))
                except Exception as exc:
                    fallback = True
                    failures += 1
                    current = {name: 0.5 for name in batch6.SLEEVES}
                    message = f"{type(exc).__name__}: {exc}"
            audit.append({
                "method": method, "decision_date": decision,
                "last_optimizer_observation": known[-1] if known else "",
                "observations": len(known), "fallback_equal_weight": fallback,
                "trend_v4_weight": current["trend_v4"], "defensive_weight": current["defensive"],
                "cash_weight": 1.0 - sum(current.values()), "optimizer_error": message,
                "causal_history_pass": not known or known[-1] <= decision,
            })
        all_weights[decision] = dict(current)
    return all_weights, audit, repeat_max, failures


def summarize(method, cost, periods, weights, coeffs):
    full = summarize_periods(periods)
    middle = summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31"))
    late = summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31"))
    return {
        "method": method, "cost_bps": cost, **full,
        "oos_2016_2020_annual_return": middle.get("annual_return", 0.0),
        "oos_2016_2020_sharpe": middle.get("sharpe_zero_rf", 0.0),
        "oos_2021_present_annual_return": late.get("annual_return", 0.0),
        "oos_2021_present_sharpe": late.get("sharpe_zero_rf", 0.0),
        "maximum_realized_asset_weight": max(value for row in weights.values() for asset, value in row.items() if asset != "cash::USD"),
        "maximum_sleeve_weight": max(max(row.values()) for row in coeffs.values()),
    }


def paired_bootstrap(challenger, benchmark, *, seed, samples, block_weeks, alpha):
    generator = random.Random(seed)
    length = len(challenger)
    values = []
    for _ in range(samples):
        indexes = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(block_weeks))
        indexes = indexes[:length]
        sharpes = []
        for panel in (challenger, benchmark):
            sample = [panel[index] for index in indexes]
            deviation = statistics.stdev(sample)
            sharpes.append(statistics.fmean(sample) / deviation * math.sqrt(52.0) if deviation else 0.0)
        values.append(sharpes[0] - sharpes[1])
    ordered = sorted(values)
    lower = ordered[math.floor(alpha * (samples - 1))]
    return {
        "observations": length, "samples": samples, "block_weeks": block_weeks,
        "one_sided_alpha": alpha, "mean_sharpe_difference": statistics.fmean(values),
        "one_sided_lower_sharpe_difference": lower, "pass": lower > 0.0,
    }


def report(result, scoreboard):
    rows = {(row["method"], float(row["cost_bps"])): row for row in scoreboard}
    benchmark = rows[("minimum_variance", 10.0)]
    primary = rows[("CDAR", 10.0)]
    lines = [
        "# skfolio drawdown portfolios — Batch 39", "",
        "Four drawdown objectives fixed before results were applied causally to the same two frozen sleeves and exact snapshot used by Batch 06. CDaR was the sole primary challenger; the other objectives could not replace it after observing performance.", "",
        "## 10-bps results", "",
    ]
    for method in ("minimum_variance", *METHODS):
        row = rows[(method, 10.0)]
        lines.append(f"- **{method}**: return **{float(row['annual_return'])*100:.2f}%**, Sharpe **{float(row['sharpe_zero_rf']):.3f}**, drawdown **{float(row['max_drawdown'])*100:.2f}%**, turnover **{float(row['average_annual_turnover']):.2f}**.")
    lines += ["", "## Decision", "", f"CDaR changed Sharpe by **{float(primary['sharpe_zero_rf'])-float(benchmark['sharpe_zero_rf']):.3f}** and drawdown by **{(abs(float(benchmark['max_drawdown']))-abs(float(primary['max_drawdown'])))*100:.2f} percentage points** versus the frozen benchmark. It passed **{sum(bool(v) for v in result['promotion_gates'].values())} of {len(result['promotion_gates'])}** gates; overall promotion: **{result['promoted']}**.", "", "These are retrospective results on a survivorship-prone free ETF universe. The frozen winner was not overwritten, and live trading remains disabled.", ""]
    return "\n".join(lines)


def main() -> int:
    program = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
    rules = program["portfolio_rules"]
    dates, simple_returns, histories, sleeve_returns = inputs(program)
    scoreboard = []
    return_rows = []
    audits = []
    periods_by_method_cost = {}
    diagnostics = {}

    baseline_coeffs, baseline_audit = batch6.build_coefficients(
        dates, sleeve_returns, method="minimum_variance",
        lookback=int(rules["lookback_weeks"]), shrinkage=batch6.PRIMARY_SHRINKAGE,
    )
    baseline_uncapped = combine_dynamic_weight_histories(dates, histories, baseline_coeffs)
    baseline_weights = cap_non_cash_weights(baseline_uncapped, maximum_asset_weight=float(rules["maximum_underlying_asset_weight"]))
    audits.extend(baseline_audit)
    coefficient_panels = {"minimum_variance": baseline_coeffs}
    weight_panels = {"minimum_variance": baseline_weights}
    for method in METHODS:
        coeffs, audit, repeat_max, failures = coefficients(dates, sleeve_returns, method, rules)
        uncapped = combine_dynamic_weight_histories(dates, histories, coeffs)
        weights = cap_non_cash_weights(uncapped, maximum_asset_weight=float(rules["maximum_underlying_asset_weight"]))
        coefficient_panels[method] = coeffs
        weight_panels[method] = weights
        audits.extend(audit)
        diagnostics[method] = {"repeat_maximum_absolute_weight_difference": repeat_max, "optimizer_failures": failures}

    for method in ("minimum_variance", *METHODS):
        for cost in map(float, rules["costs_bps"]):
            periods, accounting = compute_path(dates, weight_panels[method], simple_returns, cost_bps=cost)
            periods_by_method_cost[(method, cost)] = periods
            row = summarize(method, cost, periods, weight_panels[method], coefficient_panels[method])
            row.update(unpriced_exposure_events=accounting["unpriced_exposure_events"], fully_invested_pass=accounting["fully_invested_pass"])
            scoreboard.append(row)
            for period in periods:
                return_rows.append({"method": method, "cost_bps": cost, **period})

    prior = list(csv.DictReader((ROOT / "evidence/covariance_portfolios_batch_06/method_scoreboard.csv").open(encoding="utf-8")))
    matching = {}
    for cost in (10.0, 50.0):
        old = next(row for row in prior if row["method"] == "minimum_variance" and float(row["cost_bps"]) == cost)
        new = next(row for row in scoreboard if row["method"] == "minimum_variance" and float(row["cost_bps"]) == cost)
        matching[str(int(cost))] = max(abs(float(old[key]) - float(new[key])) for key in ("annual_return", "sharpe_zero_rf", "max_drawdown", "average_annual_turnover"))
    if max(matching.values()) > 1e-12:
        raise RuntimeError(f"frozen benchmark reconstruction mismatch: {matching}")

    uncertainty = program["uncertainty"]
    benchmark_values = [float(row["net_return"]) for row in periods_by_method_cost[("minimum_variance", 10.0)]]
    paired = {}
    for number, method in enumerate(METHODS):
        values = [float(row["net_return"]) for row in periods_by_method_cost[(method, 10.0)]]
        paired[method] = paired_bootstrap(
            values, benchmark_values, seed=int(uncertainty["seed_base"]) + number,
            samples=int(uncertainty["paired_circular_block_bootstrap_samples"]),
            block_weeks=int(uncertainty["block_weeks"]), alpha=float(uncertainty["familywise_one_sided_alpha"]),
        )

    lookup = {(row["method"], float(row["cost_bps"])): row for row in scoreboard}
    primary10, primary50, primary100 = (lookup[("CDAR", value)] for value in (10.0, 50.0, 100.0))
    benchmark10, benchmark50 = lookup[("minimum_variance", 10.0)], lookup[("minimum_variance", 50.0)]
    gates = {
        "all_decisions_causal": all(bool(row["causal_history_pass"]) for row in audits),
        "deterministic_repeat": diagnostics["CDAR"]["repeat_maximum_absolute_weight_difference"] <= 1e-8,
        "primary_10bps_sharpe": float(primary10["sharpe_zero_rf"]) >= float(benchmark10["sharpe_zero_rf"]),
        "primary_10bps_drawdown_improvement": abs(float(benchmark10["max_drawdown"])) - abs(float(primary10["max_drawdown"])) >= 0.02,
        "primary_50bps_sharpe": float(primary50["sharpe_zero_rf"]) >= float(benchmark50["sharpe_zero_rf"]),
        "primary_100bps_full_return": float(primary100["annual_return"]) > 0.0,
        "primary_100bps_2016_2020_return": float(primary100["oos_2016_2020_annual_return"]) > 0.0,
        "primary_100bps_2021_present_return": float(primary100["oos_2021_present_annual_return"]) > 0.0,
        "primary_turnover": float(primary10["average_annual_turnover"]) <= 1.5 * float(benchmark10["average_annual_turnover"]),
        "primary_familywise_paired_sharpe": bool(paired["CDAR"]["pass"]),
        "survivorship_safe": False,
        "untouched_forward_52_weeks": False,
    }
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM_PATH),
        "source_snapshot_id": program["data"]["snapshot_id"],
        "runtime": {
            "container_image": "localhost/po2-skfolio:0.20.1-native-core-batch37",
            "container_id": "92027e01782da34b066cc1c07ca97e1649a2d8d906eda9ec3ed9c5d35cbcfe1d",
            "container_size_bytes": 1560664897,
            "network_during_run": False,
        },
        "benchmark_reconstruction_maximum_differences": matching,
        "diagnostics": diagnostics, "paired_familywise_bootstrap": paired,
        "promotion_gates": gates, "promoted": all(gates.values()),
        "decision": "promoted_provisional" if all(gates.values()) else "not_promoted",
        "frozen_winner_overwritten": False, "live_trading_enabled": False,
        "limitations": ["retrospective research", "survivorship-prone free ETF universe", "only two qualified strategy sleeves", "no untouched 52-week forward record"]
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "portfolio_scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "weekly_returns.csv", return_rows)
    write_csv(OUTPUT / "allocation_history.csv", audits)
    write_csv(OUTPUT / "paired_bootstrap.csv", [{"method": method, **paired[method]} for method in METHODS])
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in ("portfolio_scoreboard.csv", "weekly_returns.csv", "allocation_history.csv", "paired_bootstrap.csv")}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result, scoreboard), encoding="utf-8")
    print(json.dumps({"primary": primary10, "benchmark": benchmark10, "gates": gates, "promoted": result["promoted"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
