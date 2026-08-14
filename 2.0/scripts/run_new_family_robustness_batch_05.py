#!/usr/bin/env python3
"""Apply common robustness gates to Batch 04's three family leaders."""

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
    block_bootstrap_positive_mean_pvalue,
    combine_weight_histories,
    expected_maximum_sharpe,
)
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.non_momentum_signals import reconstruct_non_momentum_signals
from src.systematic_trader.point_in_time import compute_path
from src.systematic_trader.portfolio_construction import PortfolioSpec
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import StrategySpec, run_experiment, summarize_periods
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
BATCH04_RESULT = ROOT / "evidence/new_families_batch_04/result.json"
BATCH04_LEADERBOARD = ROOT / "evidence/new_families_batch_04/leaderboard.csv"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/new_family_robustness_batch_05"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
COSTS_BPS = (10.0, 25.0, 50.0, 100.0)
TOTAL_SEARCH_TRIALS = 576
BOOTSTRAP_SAMPLES = 50_000
BOOTSTRAP_BLOCK_WEEKS = 13
RULES = {
    "neighborhood": {
        "same_recipe_method_and_frequency": True,
        "smoothing_weeks": [1, 2, 4],
        "top_n": [2, 4, 6],
        "minimum_median_2016_2020_sharpe": 0.25,
        "minimum_median_2021_present_sharpe": 0.50,
        "minimum_positive_return_neighbors_each_period": 7,
        "maximum_allowed_neighbor_drawdown": -0.40,
    },
    "cost": {"maximum_bps": 100.0, "minimum_annual_return": 0.0, "minimum_sharpe": 0.20},
    "regime": {
        "risk_off": "trailing 26-week SPY return <= 0",
        "high_vol_risk_on": "positive trailing return and annualized volatility >= 20%",
        "calm_risk_on": "positive trailing return and annualized volatility < 20%",
        "minimum_observations": 52,
        "minimum_annual_return": -0.02,
    },
    "multiple_testing": {
        "trials": TOTAL_SEARCH_TRIALS,
        "bootstrap_samples": BOOTSTRAP_SAMPLES,
        "block_weeks": BOOTSTRAP_BLOCK_WEEKS,
        "maximum_adjusted_pvalue": 0.05,
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
        rebalance_frequency=str(config.get("rebalance_frequency", "monthly")),
    )


def regime_labels(dates: list[str], simple_returns) -> dict[str, str]:
    labels = {}
    for index, day in enumerate(dates):
        recent = dates[max(0, index - 25) : index + 1]
        values = [simple_returns[item].get("SPY") for item in recent]
        valid = [float(value) for value in values if value is not None]
        if len(valid) < 26:
            continue
        trailing = math.prod(1.0 + value for value in valid) - 1.0
        volatility = statistics.stdev(valid) * math.sqrt(52.0)
        labels[day] = (
            "risk_off" if trailing <= 0.0
            else "high_vol_risk_on" if volatility >= 0.20
            else "calm_risk_on"
        )
    return labels


def neighborhood(candidate: dict[str, object], leaderboard: list[dict[str, str]]) -> dict[str, object]:
    config = candidate["configuration"]
    rows = [row for row in leaderboard if (
        row["recipe_name"] == candidate["recipe_name"]
        and row["portfolio_method"] == config["portfolio_method"]
        and row["rebalance_frequency"] == config["rebalance_frequency"]
        and int(row["smoothing_weeks"]) in (1, 2, 4)
        and int(row["top_n"]) in (2, 4, 6)
    )]
    early_sharpe = [float(row["oos_2016_2020_sharpe"]) for row in rows]
    recent_sharpe = [float(row["oos_2021_present_sharpe"]) for row in rows]
    early_return = [float(row["oos_2016_2020_annual_return"]) for row in rows]
    recent_return = [float(row["oos_2021_present_annual_return"]) for row in rows]
    drawdowns = [
        float(row[key]) for row in rows
        for key in ("oos_2016_2020_max_drawdown", "oos_2021_present_max_drawdown")
    ]
    passed = (
        len(rows) == 9
        and statistics.median(early_sharpe) >= 0.25
        and statistics.median(recent_sharpe) >= 0.50
        and sum(value > 0.0 for value in early_return) >= 7
        and sum(value > 0.0 for value in recent_return) >= 7
        and min(drawdowns) >= -0.40
    )
    return {
        "candidate_id": candidate["candidate_id"], "neighbor_count": len(rows),
        "median_2016_2020_sharpe": statistics.median(early_sharpe),
        "median_2021_present_sharpe": statistics.median(recent_sharpe),
        "positive_neighbors_2016_2020": sum(value > 0.0 for value in early_return),
        "positive_neighbors_2021_present": sum(value > 0.0 for value in recent_return),
        "worst_neighbor_drawdown": min(drawdowns), "pass": passed,
    }


def cost_rows(candidate_id: str, periods: list[dict[str, object]]) -> tuple[list[dict[str, object]], bool]:
    rows = []
    for bps in COSTS_BPS:
        values = [
            float(row["gross_return"]) - float(row["turnover"]) * bps / 10_000.0
            for row in periods
        ]
        rows.append({"candidate_id": candidate_id, "cost_bps": bps, **performance_metrics(values).to_dict()})
    maximum = rows[-1]
    return rows, bool(maximum["annual_return"] > 0.0 and maximum["sharpe_zero_rf"] >= 0.20)


def regime_rows(candidate_id: str, periods: list[dict[str, object]], labels) -> tuple[list[dict[str, object]], bool]:
    grouped = {name: [] for name in ("risk_off", "high_vol_risk_on", "calm_risk_on")}
    for row in periods:
        label = labels.get(str(row["decision_date"]))
        if label:
            grouped[label].append(float(row["net_return"]))
    rows = []
    passes = []
    for label, values in grouped.items():
        metrics = performance_metrics(values).to_dict() if values else {"observations": 0}
        scored = len(values) >= 52
        passed = not scored or float(metrics["annual_return"]) >= -0.02
        passes.append(passed)
        rows.append({"candidate_id": candidate_id, "regime": label, "scored": scored, "pass": passed, **metrics})
    return rows, all(passes)


def build() -> tuple[dict[str, object], dict[str, object], dict[str, list[dict[str, object]]]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    leaderboard = read_csv(BATCH04_LEADERBOARD)
    new_candidates = [
        item for item in registry["candidates"] if item.get("source_batch") == "new_families_batch_04"
    ]
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
    signals, _, _ = reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    labels = regime_labels(dates, simple_returns)
    expected_best = expected_maximum_sharpe(
        trials=TOTAL_SEARCH_TRIALS, observations=len(dates) - 1
    )
    runs = {}
    summaries = []
    neighborhoods = []
    costs = []
    regimes = []
    multiplicity = []

    for candidate in new_candidates:
        candidate_id = str(candidate["candidate_id"])
        run = run_experiment(
            spec=make_spec(candidate), snapshot_id=snapshot_id, dates=dates, assets=RISK_ASSETS,
            strategy_panels=signals, prices=prices, simple_returns=simple_returns,
        )
        runs[candidate_id] = run
        neighbor = neighborhood(candidate, leaderboard)
        cost_table, cost_pass = cost_rows(candidate_id, run["periods"])
        regime_table, regime_pass = regime_rows(candidate_id, run["periods"], labels)
        values = [float(row["net_return"]) for row in run["periods"]]
        seed = int(hashlib.sha256(candidate_id.encode()).hexdigest()[:8], 16)
        raw_p = block_bootstrap_positive_mean_pvalue(
            values, seed=seed, samples=BOOTSTRAP_SAMPLES, block_size=BOOTSTRAP_BLOCK_WEEKS
        )
        adjusted_p = min(1.0, raw_p * TOTAL_SEARCH_TRIALS)
        observed_sharpe = performance_metrics(values).sharpe_zero_rf
        multiple_pass = adjusted_p < 0.05 and observed_sharpe > expected_best
        multi = {
            "candidate_id": candidate_id, "observed_annualized_sharpe": observed_sharpe,
            "expected_best_zero_alpha_sharpe_across_576_trials": expected_best,
            "block_bootstrap_pvalue": raw_p, "bonferroni_576_pvalue": adjusted_p,
            "bootstrap_samples": BOOTSTRAP_SAMPLES, "block_weeks": BOOTSTRAP_BLOCK_WEEKS,
            "pass": multiple_pass,
        }
        robust = bool(neighbor["pass"] and cost_pass and regime_pass and multiple_pass)
        summary = {
            "candidate_id": candidate_id, "experiment_id": candidate["experiment_id"],
            "family": candidate["family"], "neighborhood_pass": neighbor["pass"],
            "cost_100bps_pass": cost_pass, "regime_pass": regime_pass,
            "multiple_testing_576_pass": multiple_pass, "robustness_pass": robust,
        }
        summaries.append(summary)
        neighborhoods.append(neighbor)
        costs.extend(cost_table)
        regimes.extend(regime_table)
        multiplicity.append(multi)

        if robust and candidate["family"] == "carry_proxy":
            candidate["status"] = "provisional_robust_research_only"
        elif robust:
            candidate["status"] = "provisional_robust_new_family"
        else:
            candidate["status"] = "provisional_fragile"
        candidate["new_family_robustness_batch_05"] = summary
        for gate, passed in (
            ("parameter_neighborhood_stability", neighbor["pass"]),
            ("100bps_cost_stress", cost_pass),
            ("point_in_time_market_regime_stability", regime_pass),
            ("multiple_testing_adjustment_across_batch_04", multiple_pass),
        ):
            if passed and gate not in candidate["passed_gates"]:
                candidate["passed_gates"].append(gate)
            if passed and gate in candidate["missing_gates"]:
                candidate["missing_gates"].remove(gate)

    trend_candidate = next(
        item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421"
    )
    trend_signals, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )
    trend_run = run_experiment(
        spec=make_spec(trend_candidate), snapshot_id=snapshot_id, dates=dates, assets=RISK_ASSETS,
        strategy_panels=trend_signals, prices=prices, simple_returns=simple_returns,
    )
    histories = {"trend_v4": trend_run["weights"], **{
        str(candidate["family"]): runs[str(candidate["candidate_id"])]["weights"]
        for candidate in new_candidates
        if next(row for row in summaries if row["candidate_id"] == candidate["candidate_id"])["robustness_pass"]
    }}
    ensemble_definitions = {"trend_v4": {"trend_v4": 1.0}}
    robust_families = [name for name in histories if name != "trend_v4"]
    if "defensive" in robust_families:
        ensemble_definitions["trend_plus_robust_defensive"] = {"trend_v4": 0.5, "defensive": 0.5}
    if robust_families:
        members = ["trend_v4", *sorted(robust_families)]
        ensemble_definitions["equal_robust_multi_family_research"] = {
            name: 1.0 / len(members) for name in members
        }
    ensemble_rows = []
    for name, coefficients in ensemble_definitions.items():
        weights = combine_weight_histories(dates, histories, coefficients)
        periods, accounting = compute_path(dates, weights, simple_returns, cost_bps=10.0)
        ensemble_rows.append({
            "ensemble_name": name, "coefficients": json.dumps(coefficients, sort_keys=True),
            **summarize_periods(periods), "unpriced_exposure_events": accounting["unpriced_exposure_events"],
            "fully_invested_pass": accounting["fully_invested_pass"], "untouched_holdout": False,
        })

    robust_by_id = {row["candidate_id"]: row["robustness_pass"] for row in summaries}
    for candidate in new_candidates:
        if robust_by_id[str(candidate["candidate_id"])]:
            if "multi_family_ensemble_interaction" in candidate["missing_gates"]:
                candidate["missing_gates"].remove("multi_family_ensemble_interaction")
            if "multi_family_ensemble_interaction_evaluated" not in candidate["passed_gates"]:
                candidate["passed_gates"].append("multi_family_ensemble_interaction_evaluated")

    registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    registry["latest_evidence_batch"] = "new_family_robustness_batch_05"
    registry["candidate_status_definitions"].update({
        "provisional_robust_new_family": "Passed Batch 05 retrospective gates; untouched validation still missing.",
        "provisional_robust_research_only": "Passed statistical gates but has a source-data limitation that blocks stronger use.",
    })
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "new_family_robustness_batch_05", "source_snapshot_id": snapshot_id,
        "candidate_count": len(new_candidates), "rules_fixed_before_results": RULES,
        "robust_count": sum(row["robustness_pass"] for row in summaries),
        "fragile_count": sum(not row["robustness_pass"] for row in summaries),
        "candidate_summaries": summaries,
        "expected_best_zero_alpha_sharpe_across_576_trials": expected_best,
        "limitations": [
            "All evidence is retrospective and no candidate has 52 untouched forward weeks.",
            "Carry remains research-only even if statistical gates pass because its distribution history is not archived point-in-time data.",
            "The ensemble is a diagnostic designed after viewing the history, not a frozen promotion candidate.",
            "Bonferroni correction is conservative but does not repair survivorship bias or data revisions.",
        ],
    }
    return result, registry, {
        "candidate_summary.csv": summaries, "neighborhoods.csv": neighborhoods,
        "cost_stress.csv": costs, "regimes.csv": regimes,
        "multiple_testing.csv": multiplicity, "robust_ensemble_diagnostics.csv": ensemble_rows,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_report(result: dict[str, object], tables: dict[str, list[dict[str, object]]]) -> str:
    lines = [
        "# New-Family Robustness — Batch 05", "",
        f"The three Batch 04 family leaders were tested across parameter neighborhoods, costs through 100 bps, causal market regimes, and a 50,000-sample correction for all {TOTAL_SEARCH_TRIALS} strategies searched so far.", "",
        f"- Provisionally robust: **{result['robust_count']}**.",
        f"- Provisionally fragile: **{result['fragile_count']}**.", "",
        "## Candidate decisions", "",
    ]
    for row in result["candidate_summaries"]:
        lines.append(
            f"- **{row['family']}** `{row['candidate_id']}`: **{'robust' if row['robustness_pass'] else 'fragile'}** "
            f"(neighborhood {'pass' if row['neighborhood_pass'] else 'fail'}, "
            f"100 bps {'pass' if row['cost_100bps_pass'] else 'fail'}, "
            f"regime {'pass' if row['regime_pass'] else 'fail'}, "
            f"multiple testing {'pass' if row['multiple_testing_576_pass'] else 'fail'})."
        )
    lines.extend(["", "## Robust-family ensemble diagnostics", ""])
    for row in tables["robust_ensemble_diagnostics.csv"]:
        lines.append(
            f"- **{row['ensemble_name']}**: annual return **{float(row['annual_return']) * 100:.2f}%**, "
            f"Sharpe **{float(row['sharpe_zero_rf']):.3f}**, drawdown **{float(row['max_drawdown']) * 100:.2f}%**, "
            f"annual turnover **{float(row['average_annual_turnover']):.2f}**."
        )
    lines.extend([
        "", "Carry cannot advance beyond research-only status from the current Yahoo action history, regardless of its statistical result. All ensemble numbers remain retrospective diagnostics.", "",
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
        "robust_count": result["robust_count"], "fragile_count": result["fragile_count"],
        "candidate_summaries": result["candidate_summaries"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
