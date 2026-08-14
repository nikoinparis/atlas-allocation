#!/usr/bin/env python3
"""Measure candidate dependence, netted ensembles, and search-adjusted evidence."""

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
from src.systematic_trader.ensemble import (
    average_holdings_overlap,
    block_bootstrap_positive_mean_pvalue,
    combine_weight_histories,
    correlation,
    correlation_clusters,
    effective_independent_count,
    expected_maximum_sharpe,
    greedy_low_correlation_selection,
)
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.point_in_time import compute_path
from src.systematic_trader.portfolio_construction import PortfolioSpec
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import StrategySpec, run_experiment, summarize_periods
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/ensemble_dependence_batch_03"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
CORRELATION_CLUSTER_THRESHOLD = 0.90
MULTIPLE_TEST_TRIALS = 288
BOOTSTRAP_SAMPLES = 25000
BOOTSTRAP_BLOCK_WEEKS = 13
FROZEN_V4_EXPERIMENT = "exp-fc7248702f02b421"


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def make_spec(candidate: dict[str, object]) -> StrategySpec:
    config = candidate["configuration"]
    return StrategySpec(
        signals=tuple(config["signals"]), smoothing_weeks=int(config["smoothing_weeks"]),
        portfolio=PortfolioSpec(
            method=str(config["portfolio_method"]), top_n=int(config["top_n"]),
            min_signal=float(config["minimum_signal"]),
        ), cost_bps=float(config["cost_bps"]),
    )


def matrix_rows(matrix: dict[str, dict[str, float]]) -> list[dict[str, object]]:
    names = list(matrix)
    return [{"candidate_id": name, **matrix[name]} for name in names]


def ensemble_result(
    *, name: str, coefficients: dict[str, float], dates: list[str], histories, simple_returns
) -> tuple[dict[str, object], list[dict[str, object]]]:
    weights = combine_weight_histories(dates, histories, coefficients)
    periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=10.0)
    recent = [row for row in periods if str(row["realization_date"]) >= "2021-01-01"]
    return {
        "ensemble_name": name,
        "member_count": len(coefficients),
        "members": "+".join(coefficients),
        "coefficients": json.dumps(coefficients, sort_keys=True),
        **{f"full_{key}": value for key, value in summarize_periods(periods).items()},
        **{f"recent_{key}": value for key, value in summarize_periods(recent).items()},
        "unpriced_exposure_events": accounting["unpriced_exposure_events"],
        "fully_invested_pass": accounting["fully_invested_pass"],
    }, periods


def build() -> tuple[dict[str, object], dict[str, object], dict[str, list[dict[str, object]]]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    store = SnapshotStore(STORE_ROOT)
    manifest = latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    all_assets = sorted(universe["symbols"])
    dates, prices, _ = prepare_weekly_adjusted_prices(
        STORE_ROOT / snapshot_id / "payload/prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=all_assets,
    )
    log_returns = weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    panels, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )

    runs: dict[str, dict[str, object]] = {}
    histories = {}
    returns = {}
    recent_returns = {}
    candidate_by_id = {}
    for candidate in registry["candidates"]:
        candidate_id = str(candidate["candidate_id"])
        candidate_by_id[candidate_id] = candidate
        run = run_experiment(
            spec=make_spec(candidate), snapshot_id=snapshot_id, dates=dates,
            assets=RISK_ASSETS, strategy_panels=panels, prices=prices, simple_returns=simple_returns,
        )
        runs[candidate_id] = run
        histories[candidate_id] = run["weights"]
        returns[candidate_id] = [float(row["net_return"]) for row in run["periods"]]
        recent_returns[candidate_id] = [
            float(row["net_return"]) for row in run["periods"]
            if str(row["realization_date"]) >= "2021-01-01"
        ]

    names = sorted(runs)
    full_matrix = {left: {right: correlation(returns[left], returns[right]) for right in names} for left in names}
    recent_matrix = {
        left: {right: correlation(recent_returns[left], recent_returns[right]) for right in names}
        for left in names
    }
    overlap_rows = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap_rows.append({
                "candidate_left": left,
                "candidate_right": right,
                "full_return_correlation": full_matrix[left][right],
                "recent_return_correlation": recent_matrix[left][right],
                "average_weight_overlap": average_holdings_overlap(dates, histories[left], histories[right]),
            })

    clusters = correlation_clusters(names, full_matrix, CORRELATION_CLUSTER_THRESHOLD)
    cluster_by_name = {
        name: cluster_index + 1 for cluster_index, cluster in enumerate(clusters) for name in cluster
    }
    v4_candidate = next(
        candidate["candidate_id"] for candidate in registry["candidates"]
        if candidate["experiment_id"] == FROZEN_V4_EXPERIMENT
    )
    greedy = greedy_low_correlation_selection(names, full_matrix, start=v4_candidate, count=4)
    equal_coefficients = {name: 1.0 / len(names) for name in names}
    cluster_coefficients = {
        name: 1.0 / len(clusters) / len(clusters[cluster_by_name[name] - 1]) for name in names
    }
    greedy_coefficients = {name: 1.0 / len(greedy) for name in greedy}
    v4_coefficients = {v4_candidate: 1.0}
    ensembles = []
    ensemble_periods = {}
    for ensemble_name, coefficients in (
        ("frozen_v4", v4_coefficients),
        ("equal_all_candidates", equal_coefficients),
        ("correlation_cluster_balanced", cluster_coefficients),
        ("greedy_four_from_v4", greedy_coefficients),
    ):
        row, periods = ensemble_result(
            name=ensemble_name, coefficients=coefficients, dates=dates,
            histories=histories, simple_returns=simple_returns,
        )
        ensembles.append(row)
        ensemble_periods[ensemble_name] = periods

    equal_metrics = next(row for row in ensembles if row["ensemble_name"] == "equal_all_candidates")
    marginal_rows = []
    for excluded in names:
        remaining = [name for name in names if name != excluded]
        row, _ = ensemble_result(
            name=f"equal_without_{excluded}", coefficients={name: 1.0 / len(remaining) for name in remaining},
            dates=dates, histories=histories, simple_returns=simple_returns,
        )
        marginal_rows.append({
            "candidate_id": excluded,
            "all_candidate_sharpe": equal_metrics["full_sharpe_zero_rf"],
            "without_candidate_sharpe": row["full_sharpe_zero_rf"],
            "sharpe_contribution": float(equal_metrics["full_sharpe_zero_rf"]) - float(row["full_sharpe_zero_rf"]),
            "all_candidate_annual_return": equal_metrics["full_annual_return"],
            "without_candidate_annual_return": row["full_annual_return"],
            "annual_return_contribution": float(equal_metrics["full_annual_return"]) - float(row["full_annual_return"]),
            "all_candidate_max_drawdown": equal_metrics["full_max_drawdown"],
            "without_candidate_max_drawdown": row["full_max_drawdown"],
        })

    multiplicity_rows = []
    expected_best = expected_maximum_sharpe(
        trials=MULTIPLE_TEST_TRIALS, observations=len(next(iter(returns.values())))
    )
    for candidate_id in names:
        values = returns[candidate_id]
        seed = int(hashlib.sha256(candidate_id.encode()).hexdigest()[:8], 16)
        raw_p = block_bootstrap_positive_mean_pvalue(
            values, seed=seed, samples=BOOTSTRAP_SAMPLES, block_size=BOOTSTRAP_BLOCK_WEEKS
        )
        bonferroni = min(1.0, raw_p * MULTIPLE_TEST_TRIALS)
        observed_sharpe = performance_metrics(values).sharpe_zero_rf
        passed = bonferroni < 0.05 and observed_sharpe > expected_best
        multiplicity_rows.append({
            "candidate_id": candidate_id,
            "observed_annualized_sharpe": observed_sharpe,
            "expected_best_zero_alpha_sharpe_across_288_trials": expected_best,
            "block_bootstrap_one_sided_pvalue": raw_p,
            "bonferroni_288_pvalue": bonferroni,
            "multiple_testing_gate_pass": passed,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "block_weeks": BOOTSTRAP_BLOCK_WEEKS,
        })

    overlap_by_candidate = {
        name: [
            float(row["average_weight_overlap"]) for row in overlap_rows
            if name in (row["candidate_left"], row["candidate_right"])
        ] for name in names
    }
    multiplicity_by_id = {row["candidate_id"]: row for row in multiplicity_rows}
    marginal_by_id = {row["candidate_id"]: row for row in marginal_rows}
    for candidate_id, candidate in candidate_by_id.items():
        peers = [full_matrix[candidate_id][other] for other in names if other != candidate_id]
        dependence = {
            "correlation_cluster": cluster_by_name[candidate_id],
            "average_peer_correlation": statistics.fmean(peers),
            "maximum_peer_correlation": max(peers),
            "average_holdings_overlap": statistics.fmean(overlap_by_candidate[candidate_id]),
            "sharpe_contribution_to_equal_candidate_ensemble": marginal_by_id[candidate_id]["sharpe_contribution"],
            "multiple_testing_gate_pass": multiplicity_by_id[candidate_id]["multiple_testing_gate_pass"],
        }
        candidate["ensemble_dependence_batch_03"] = dependence
        if "strategy_ensemble_interaction" in candidate["missing_gates"]:
            candidate["missing_gates"].remove("strategy_ensemble_interaction")
        if "strategy_ensemble_interaction_evaluated" not in candidate["passed_gates"]:
            candidate["passed_gates"].append("strategy_ensemble_interaction_evaluated")
        if dependence["multiple_testing_gate_pass"]:
            if "multiple_testing_adjustment" in candidate["missing_gates"]:
                candidate["missing_gates"].remove("multiple_testing_adjustment")
            candidate["passed_gates"].append("multiple_testing_adjustment")

    registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    registry["latest_evidence_batch"] = "ensemble_dependence_batch_03"
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "ensemble_dependence_batch_03",
        "source_snapshot_id": snapshot_id,
        "candidate_count": len(names),
        "pair_count": len(overlap_rows),
        "full_correlation_range": {
            "minimum": min(float(row["full_return_correlation"]) for row in overlap_rows),
            "maximum": max(float(row["full_return_correlation"]) for row in overlap_rows),
            "median": statistics.median(float(row["full_return_correlation"]) for row in overlap_rows),
        },
        "average_holdings_overlap": statistics.fmean(float(row["average_weight_overlap"]) for row in overlap_rows),
        "effective_independent_strategy_count": effective_independent_count(full_matrix),
        "correlation_cluster_threshold": CORRELATION_CLUSTER_THRESHOLD,
        "correlation_clusters": clusters,
        "greedy_four_members": greedy,
        "multiple_testing": {
            "original_experiment_search_count": MULTIPLE_TEST_TRIALS,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "block_weeks": BOOTSTRAP_BLOCK_WEEKS,
            "expected_best_zero_alpha_sharpe": expected_best,
            "candidate_pass_count": sum(row["multiple_testing_gate_pass"] for row in multiplicity_rows),
        },
        "limitations": [
            "Ensembles were designed after viewing the same history and are retrospective research only.",
            "The sleeve-level candidates share data, assets, and signal ancestry; correlation estimates can change.",
            "Bonferroni correction treats 288 tests conservatively; block bootstrap p-values have finite-sample resolution.",
            "Netted portfolio turnover is modeled, but tax, capacity, and market-impact effects are not.",
            "No result satisfies the 52-week untouched-forward gate.",
        ],
    }
    return result, registry, {
        "full_return_correlation.csv": matrix_rows(full_matrix),
        "recent_return_correlation.csv": matrix_rows(recent_matrix),
        "pairwise_dependence.csv": overlap_rows,
        "ensemble_scoreboard.csv": ensembles,
        "marginal_contribution.csv": marginal_rows,
        "multiple_testing.csv": multiplicity_rows,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_report(result: dict[str, object], tables: dict[str, list[dict[str, object]]]) -> str:
    ensembles = tables["ensemble_scoreboard.csv"]
    multiplicity = result["multiple_testing"]
    lines = [
        "# Ensemble and Dependence Batch 03", "",
        f"The ten provisional candidates represent approximately **{result['effective_independent_strategy_count']:.2f}** independent return streams by the correlation participation ratio.", "",
        "## Dependence", "",
        f"- Pairwise full-history return correlations range from **{result['full_correlation_range']['minimum']:.3f}** to **{result['full_correlation_range']['maximum']:.3f}**; median **{result['full_correlation_range']['median']:.3f}**.",
        f"- Average historical holdings overlap is **{result['average_holdings_overlap'] * 100:.1f}%**.",
        f"- At correlation ≥ {result['correlation_cluster_threshold']:.2f}, the candidates form **{len(result['correlation_clusters'])}** connected clusters.", "",
        "## Netted portfolio ensembles", "",
    ]
    for row in ensembles:
        lines.append(
            f"- **{row['ensemble_name']}**: annual return {float(row['full_annual_return']) * 100:.2f}%, "
            f"Sharpe {float(row['full_sharpe_zero_rf']):.3f}, drawdown {float(row['full_max_drawdown']) * 100:.2f}%, "
            f"annual turnover {float(row['full_average_annual_turnover']):.2f}."
        )
    lines.extend([
        "", "## Multiple-testing correction", "",
        f"The original search contained **{multiplicity['original_experiment_search_count']}** strategies. Under independent zero-alpha Gaussian trials, the expected best Sharpe is approximately **{multiplicity['expected_best_zero_alpha_sharpe']:.3f}**. Serial-dependence-aware 13-week block-bootstrap p-values were Bonferroni-adjusted across all 288 trials.", "",
        f"Candidates passing the declared multiple-testing gate: **{multiplicity['candidate_pass_count']} of {result['candidate_count']}**.", "",
        "## Interpretation", "",
        "The ensemble comparison uses netted target weights and therefore does not double-charge turnover shared across sleeves. However, every ensemble was designed after observing this history. It is evidence about redundancy and portfolio mechanics, not an untouched performance claim.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    result, registry, tables = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        write_csv(OUTPUT / name, rows)
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in tables
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(make_report(result, tables), encoding="utf-8")
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "effective_independent_strategy_count": result["effective_independent_strategy_count"],
        "correlation_clusters": result["correlation_clusters"],
        "multiple_testing": result["multiple_testing"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
