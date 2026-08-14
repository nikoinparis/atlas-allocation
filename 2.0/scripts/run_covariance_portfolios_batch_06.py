#!/usr/bin/env python3
"""Compare causal covariance-aware allocation across robust strategy families."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.ensemble import correlation
from src.systematic_trader.non_momentum_signals import reconstruct_non_momentum_signals
from src.systematic_trader.point_in_time import compute_path, monthly_rebalance_dates
from src.systematic_trader.portfolio_construction import PortfolioSpec
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import (
    StrategySpec,
    period_slice,
    run_experiment,
    selection_score,
    summarize_periods,
)
from src.systematic_trader.strategy_allocation import (
    allocate_two_sleeves,
    cap_non_cash_weights,
    combine_dynamic_weight_histories,
    portfolio_variance,
    shrunk_covariance,
)
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
PORTFOLIO_REGISTRY_PATH = ROOT / "research_registry/portfolio_candidates.json"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/covariance_portfolios_batch_06"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
SLEEVES = ("trend_v4", "defensive")
PRIMARY_LOOKBACK = 104
MINIMUM_OBSERVATIONS = 52
PRIMARY_SHRINKAGE = 0.25
MAXIMUM_SLEEVE_WEIGHT = 0.80
MAXIMUM_UNDERLYING_ASSET_WEIGHT = 0.35
VOLATILITY_TARGET = 0.10
METHODS = (
    "equal_weight",
    "inverse_volatility",
    "minimum_variance",
    "maximum_diversification",
    "hrp_two_sleeve",
    "equal_weight_vol_target_10",
)
RULES = {
    "decision_frequency": "monthly",
    "covariance_lookback_weeks": PRIMARY_LOOKBACK,
    "minimum_observations": MINIMUM_OBSERVATIONS,
    "diagonal_shrinkage": PRIMARY_SHRINKAGE,
    "maximum_sleeve_weight": MAXIMUM_SLEEVE_WEIGHT,
    "maximum_underlying_asset_weight": MAXIMUM_UNDERLYING_ASSET_WEIGHT,
    "volatility_target": VOLATILITY_TARGET,
    "maximum_leverage": 1.0,
    "costs_bps": [10.0, 50.0],
    "sensitivity_lookbacks": [52, 104, 156],
    "sensitivity_shrinkage": [0.0, 0.25, 0.5],
}


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def make_spec(candidate: dict[str, object]) -> StrategySpec:
    config = candidate["configuration"]
    return StrategySpec(
        signals=tuple(config["signals"]),
        smoothing_weeks=int(config["smoothing_weeks"]),
        portfolio=PortfolioSpec(
            method=str(config["portfolio_method"]),
            top_n=int(config["top_n"]),
            min_signal=float(config["minimum_signal"]),
        ),
        cost_bps=float(config["cost_bps"]),
        rebalance_frequency=str(config.get("rebalance_frequency", "monthly")),
    )


def sleeve_return_panel(runs: dict[str, dict[str, object]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {name: {} for name in runs}
    for name, run in runs.items():
        for row in run["periods"]:
            result[name][str(row["realization_date"])] = float(row["net_return"])
    return result


def build_coefficients(
    dates: list[str],
    sleeve_returns: dict[str, dict[str, float]],
    *,
    method: str,
    lookback: int,
    shrinkage: float,
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]]]:
    rebalance_dates = monthly_rebalance_dates(dates, include_sample_endpoint=False)
    current = {name: 0.5 for name in SLEEVES}
    coefficients: dict[str, dict[str, float]] = {}
    audit: list[dict[str, object]] = []
    for decision in dates:
        if decision in rebalance_dates:
            known_dates = [
                day for day in dates
                if day <= decision and all(day in sleeve_returns[name] for name in SLEEVES)
            ][-lookback:]
            fallback = len(known_dates) < MINIMUM_OBSERVATIONS
            covariance = None
            estimated_volatility = None
            if not fallback:
                observations = {
                    name: [sleeve_returns[name][day] for day in known_dates] for name in SLEEVES
                }
                covariance = shrunk_covariance(observations, diagonal_shrinkage=shrinkage)
                base_method = "equal_weight" if method == "equal_weight_vol_target_10" else method
                current = allocate_two_sleeves(
                    base_method, covariance, maximum_weight=MAXIMUM_SLEEVE_WEIGHT
                )
                variance = max(0.0, portfolio_variance(current, covariance))
                estimated_volatility = math.sqrt(variance * 52.0)
                if method == "equal_weight_vol_target_10":
                    exposure = min(1.0, VOLATILITY_TARGET / estimated_volatility) if estimated_volatility > 0 else 1.0
                    current = {name: value * exposure for name, value in current.items()}
            audit.append({
                "method": method,
                "decision_date": decision,
                "last_covariance_observation": known_dates[-1] if known_dates else "",
                "observations": len(known_dates),
                "fallback_equal_weight": fallback,
                "trend_v4_weight": current["trend_v4"],
                "defensive_weight": current["defensive"],
                "cash_weight": 1.0 - sum(current.values()),
                "estimated_annual_volatility": estimated_volatility if estimated_volatility is not None else "",
                "trend_variance": covariance["trend_v4"]["trend_v4"] if covariance else "",
                "defensive_variance": covariance["defensive"]["defensive"] if covariance else "",
                "cross_covariance": covariance["trend_v4"]["defensive"] if covariance else "",
                "causal_history_pass": not known_dates or known_dates[-1] <= decision,
            })
        coefficients[decision] = dict(current)
    return coefficients, audit


def evaluate_method(
    dates: list[str], histories: dict[str, dict[str, dict[str, float]]],
    sleeve_returns: dict[str, dict[str, float]], simple_returns: dict[str, dict[str, float | None]],
    *, method: str, lookback: int,
    shrinkage: float, cost_bps: float,
) -> tuple[dict[str, object], list[dict[str, float | str]], list[dict[str, object]], dict[str, object]]:
    coefficients, audit = build_coefficients(
        dates, sleeve_returns, method=method, lookback=lookback, shrinkage=shrinkage
    )
    uncapped_weights = combine_dynamic_weight_histories(dates, histories, coefficients)
    weights = cap_non_cash_weights(
        uncapped_weights, maximum_asset_weight=MAXIMUM_UNDERLYING_ASSET_WEIGHT
    )
    periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=cost_bps)
    summary = {
        "method": method,
        "lookback_weeks": lookback,
        "diagonal_shrinkage": shrinkage,
        "cost_bps": cost_bps,
        **summarize_periods(periods),
        "development_sharpe": summarize_periods(period_slice(periods, "2006-01-01", "2015-12-31")).get("sharpe_zero_rf", 0.0),
        "oos_2016_2020_annual_return": summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31")).get("annual_return", 0.0),
        "oos_2016_2020_sharpe": summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31")).get("sharpe_zero_rf", 0.0),
        "oos_2021_present_annual_return": summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31")).get("annual_return", 0.0),
        "oos_2021_present_sharpe": summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31")).get("sharpe_zero_rf", 0.0),
        "maximum_realized_asset_weight": max(
            value for row in weights.values() for asset, value in row.items()
            if asset != "cash::USD"
        ),
        "maximum_sleeve_weight": max(max(row.values()) for row in coefficients.values()),
        "minimum_total_sleeve_exposure": min(sum(row.values()) for row in coefficients.values()),
        "unpriced_exposure_events": accounting["unpriced_exposure_events"],
        "fully_invested_pass": accounting["fully_invested_pass"],
    }
    return summary, periods, audit, accounting


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_report(result: dict[str, object], scoreboard: list[dict[str, object]]) -> str:
    primary = [row for row in scoreboard if float(row["cost_bps"]) == 10.0]
    lines = [
        "# Covariance-Aware Portfolios — Batch 06", "",
        "Frozen trend v4 and the Batch 05 robust defensive sleeve were combined using only covariance observations available by each monthly decision date. All combined target weights were accounted together so overlapping trades were netted before costs. Each sleeve was capped at 80%, each underlying non-cash asset at 35%, and cap excess was held in explicit cash.", "",
        "## Primary 104-week, 25% diagonal-shrinkage comparison", "",
    ]
    for row in primary:
        lines.append(
            f"- **{row['method']}**: annual return **{float(row['annual_return']) * 100:.2f}%**, "
            f"Sharpe **{float(row['sharpe_zero_rf']):.3f}**, drawdown **{float(row['max_drawdown']) * 100:.2f}%**, "
            f"turnover **{float(row['average_annual_turnover']):.2f}**."
        )
    chosen = result["development_selected_method"]
    lines.extend([
        "", "## Decision", "",
        f"The method selected using only the 2006–2015 development score was **{chosen}**. Its later-period results remain retrospective out-of-sample diagnostics, because Batch 06 itself was designed after the complete history was available.", "",
        "With two sleeves, maximum diversification is mathematically equivalent to inverse-volatility weighting, while two-sleeve HRP has no meaningful hierarchy to discover. Duplicate return histories are explicitly reported rather than counted as independent methods.", "",
        "No portfolio in this batch is final or approved for live trading. The free ETF universe remains survivorship-prone and the 52-week untouched forward clock is incomplete.", "",
    ])
    return "\n".join(lines)


def build() -> tuple[dict[str, object], dict[str, list[dict[str, object]]], dict[str, object]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    trend_candidate = next(item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    defensive_candidate = next(item for item in registry["candidates"] if item.get("family") == "defensive")
    if defensive_candidate["status"] != "provisional_robust_new_family":
        raise ValueError("Batch 06 requires the Batch 05 robust defensive candidate")

    store = SnapshotStore(STORE_ROOT)
    manifest = latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    payload = STORE_ROOT / snapshot_id / "payload"
    all_assets = sorted(json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, _ = prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=all_assets,
    )
    log_returns = weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    trend_signals, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )
    non_momentum, _, _ = reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    runs = {
        "trend_v4": run_experiment(
            spec=make_spec(trend_candidate), snapshot_id=snapshot_id, dates=dates,
            assets=RISK_ASSETS, strategy_panels=trend_signals, prices=prices,
            simple_returns=simple_returns,
        ),
        "defensive": run_experiment(
            spec=make_spec(defensive_candidate), snapshot_id=snapshot_id, dates=dates,
            assets=RISK_ASSETS, strategy_panels=non_momentum, prices=prices,
            simple_returns=simple_returns,
        ),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = sleeve_return_panel(runs)

    scoreboard: list[dict[str, object]] = []
    allocation_history: list[dict[str, object]] = []
    primary_periods: dict[str, list[dict[str, float | str]]] = {}
    for method in METHODS:
        for cost_bps in (10.0, 50.0):
            row, periods, audit, _ = evaluate_method(
                dates, histories, sleeve_returns, simple_returns, method=method,
                lookback=PRIMARY_LOOKBACK, shrinkage=PRIMARY_SHRINKAGE, cost_bps=cost_bps,
            )
            scoreboard.append(row)
            if cost_bps == 10.0:
                primary_periods[method] = periods
                allocation_history.extend(audit)

    sensitivity: list[dict[str, object]] = []
    for method in METHODS[1:]:
        for lookback in (52, 104, 156):
            for shrinkage in (0.0, 0.25, 0.5):
                row, _, _, _ = evaluate_method(
                    dates, histories, sleeve_returns, simple_returns, method=method,
                    lookback=lookback, shrinkage=shrinkage, cost_bps=10.0,
                )
                sensitivity.append(row)

    correlations: list[dict[str, object]] = []
    for left in METHODS:
        left_values = [float(row["net_return"]) for row in primary_periods[left]]
        for right in METHODS:
            right_values = [float(row["net_return"]) for row in primary_periods[right]]
            correlations.append({"left_method": left, "right_method": right, "return_correlation": correlation(left_values, right_values)})

    primary = [row for row in scoreboard if float(row["cost_bps"]) == 10.0]
    selected = max(primary, key=lambda row: (
        selection_score(summarize_periods(period_slice(primary_periods[str(row["method"])], "2006-01-01", "2015-12-31"))),
        str(row["method"]),
    ))
    selected_method = str(selected["method"])
    duplicate_pairs = [
        {"left": row["left_method"], "right": row["right_method"], "correlation": row["return_correlation"]}
        for row in correlations
        if str(row["left_method"]) < str(row["right_method"])
        and float(row["return_correlation"]) >= 0.999999
    ]
    candidate = {
        "portfolio_candidate_id": "portfolio-" + hashlib.sha256(
            f"{snapshot_id}|{selected_method}|{PRIMARY_LOOKBACK}|{PRIMARY_SHRINKAGE}".encode()
        ).hexdigest()[:16],
        "status": "provisional_portfolio_research",
        "final": False,
        "approved_for_live_trading": False,
        "selection_window": "2006-01-01 through 2015-12-31",
        "selection_method": "highest development selection score among six predeclared methods",
        "method": selected_method,
        "source_snapshot_id": snapshot_id,
        "constituent_candidates": [trend_candidate["candidate_id"], defensive_candidate["candidate_id"]],
        "configuration": RULES,
        "evidence": selected,
        "missing_gates": [
            "52_week_untouched_forward_record",
            "survivorship_safe_historical_universe",
            "multi_vintage_parameter_stability",
        ],
    }
    portfolio_registry = {
        "schema_version": 1,
        "last_updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": 1,
        "candidates": [candidate],
    }
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "covariance_portfolios_batch_06",
        "source_snapshot_id": snapshot_id,
        "rules_fixed_before_results": RULES,
        "methods_tested": list(METHODS),
        "primary_method_count": len(METHODS),
        "sensitivity_configuration_count": len(sensitivity),
        "development_selected_method": selected_method,
        "development_selected_candidate_id": candidate["portfolio_candidate_id"],
        "duplicate_primary_method_pairs": duplicate_pairs,
        "limitations": [
            "All results are retrospective; no Batch 06 method has an untouched 52-week forward record.",
            "Only two robust strategy families are available, so HRP cannot form a meaningful hierarchy.",
            "The free ETF universe is not survivorship-safe.",
            "Covariance shrinkage and lookbacks reduce but cannot eliminate estimation error.",
            "Volatility targeting is unlevered and holds residual exposure in explicit cash.",
        ],
    }
    tables = {
        "method_scoreboard.csv": scoreboard,
        "allocation_history.csv": allocation_history,
        "estimation_sensitivity.csv": sensitivity,
        "method_return_correlations.csv": correlations,
    }
    return result, tables, portfolio_registry


def main() -> int:
    result, tables, portfolio_registry = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        write_csv(OUTPUT / name, rows)
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in tables
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(make_report(result, tables["method_scoreboard.csv"]), encoding="utf-8")
    PORTFOLIO_REGISTRY_PATH.write_text(json.dumps(portfolio_registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "development_selected_method": result["development_selected_method"],
        "duplicate_primary_method_pairs": result["duplicate_primary_method_pairs"],
        "primary_results": [row for row in tables["method_scoreboard.csv"] if row["cost_bps"] == 10.0],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
