#!/usr/bin/env python3
"""Test mean-reversion, defensive, and distribution-yield carry families."""

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

from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.ensemble import combine_weight_histories, correlation
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.non_momentum_signals import reconstruct_non_momentum_signals
from src.systematic_trader.portfolio_construction import PortfolioSpec, SUPPORTED_METHODS
from src.systematic_trader.point_in_time import compute_path
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import StrategySpec, run_experiment, selection_score, summarize_periods
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/new_families_batch_04"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
RECIPES = {
    "reversal_4w": {"family": "mean_reversion", "signals": ("reversal_4w",), "frequency": "weekly"},
    "ma_reversal": {"family": "mean_reversion", "signals": ("ma_reversal",), "frequency": "weekly"},
    "rsi_reversal": {"family": "mean_reversion", "signals": ("rsi_reversal",), "frequency": "weekly"},
    "mean_reversion_composite": {
        "family": "mean_reversion", "signals": ("reversal_4w", "ma_reversal", "rsi_reversal"), "frequency": "weekly"
    },
    "low_volatility": {"family": "defensive", "signals": ("low_volatility",), "frequency": "monthly"},
    "drawdown_resilience": {"family": "defensive", "signals": ("drawdown_resilience",), "frequency": "monthly"},
    "defensive_quality_gated": {
        "family": "defensive", "signals": ("defensive_quality_gated",), "frequency": "monthly"
    },
    "distribution_yield": {"family": "carry_proxy", "signals": ("distribution_yield",), "frequency": "monthly"},
}
REFERENCE_PATTERNS = [
    {
        "project": "quant-trading",
        "url": "https://github.com/je-suis-tm/quant-trading",
        "pattern_used": "treat RSI, pair, and other mean-reversion rules as hypotheses requiring common backtest controls",
        "code_copied": False,
    },
    {
        "project": "PythonTradingFramework",
        "url": "https://github.com/JustinGuese/python_tradingbot_framework",
        "pattern_used": "expose technical signals such as RSI through a repeatable parameter-testing interface",
        "code_copied": False,
    },
    {
        "project": "pysystemtrade",
        "url": "https://github.com/robcarver17/pysystemtrade",
        "pattern_used": "keep forecast logic, position sizing, and portfolio aggregation separate",
        "code_copied": False,
    },
]


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def specifications() -> list[tuple[str, str, StrategySpec]]:
    result = []
    for recipe_name, recipe in RECIPES.items():
        for smoothing in (1, 2, 4):
            for top_n in (2, 4, 6):
                for method in SUPPORTED_METHODS:
                    result.append((recipe_name, str(recipe["family"]), StrategySpec(
                        signals=tuple(recipe["signals"]), smoothing_weeks=smoothing,
                        portfolio=PortfolioSpec(method=method, top_n=top_n, min_signal=0.05),
                        cost_bps=10.0, rebalance_frequency=str(recipe["frequency"]),
                    )))
    return result


def metrics_row(recipe_name: str, family: str, run: dict[str, object]) -> dict[str, object]:
    strategy = run["strategy"]
    portfolio = strategy["portfolio"]
    metrics = run["metrics"]
    stressed = [
        float(row["gross_return"]) - float(row["turnover"]) * 50.0 / 10_000.0
        for row in run["periods"]
    ]
    stress = performance_metrics(stressed).to_dict()
    return {
        "experiment_id": run["experiment_id"],
        "family": family,
        "recipe_name": recipe_name,
        "signals": "+".join(strategy["signals"]),
        "rebalance_frequency": strategy.get("rebalance_frequency", "monthly"),
        "smoothing_weeks": strategy["smoothing_weeks"],
        "portfolio_method": portfolio["method"],
        "top_n": portfolio["top_n"],
        "development_selection_score": selection_score(metrics["development_2006_2015"]),
        "development_annual_return": metrics["development_2006_2015"]["annual_return"],
        "development_sharpe": metrics["development_2006_2015"]["sharpe_zero_rf"],
        "development_max_drawdown": metrics["development_2006_2015"]["max_drawdown"],
        "oos_2016_2020_annual_return": metrics["retrospective_oos_2016_2020"]["annual_return"],
        "oos_2016_2020_sharpe": metrics["retrospective_oos_2016_2020"]["sharpe_zero_rf"],
        "oos_2016_2020_max_drawdown": metrics["retrospective_oos_2016_2020"]["max_drawdown"],
        "oos_2021_present_annual_return": metrics["retrospective_oos_2021_present"]["annual_return"],
        "oos_2021_present_sharpe": metrics["retrospective_oos_2021_present"]["sharpe_zero_rf"],
        "oos_2021_present_max_drawdown": metrics["retrospective_oos_2021_present"]["max_drawdown"],
        "full_annual_return": metrics["full_history"]["annual_return"],
        "full_sharpe": metrics["full_history"]["sharpe_zero_rf"],
        "full_max_drawdown": metrics["full_history"]["max_drawdown"],
        "full_annual_turnover": metrics["full_history"]["average_annual_turnover"],
        "stress_50bps_annual_return": stress["annual_return"],
        "stress_50bps_sharpe": stress["sharpe_zero_rf"],
        "unpriced_exposure_events": run["accounting"]["unpriced_exposure_events"],
        "fully_invested_pass": run["accounting"]["fully_invested_pass"],
        "untouched_holdout": False,
    }


def candidate_entry(
    leader: dict[str, object], run: dict[str, object], v4_returns: list[float], correlation_to_v4: float
) -> dict[str, object]:
    qualifies = (
        float(leader["oos_2016_2020_annual_return"]) > 0.0
        and float(leader["oos_2021_present_annual_return"]) > 0.0
        and float(leader["oos_2016_2020_sharpe"]) > 0.0
        and float(leader["oos_2021_present_sharpe"]) > 0.0
        and float(leader["stress_50bps_annual_return"]) > 0.0
        and float(leader["full_max_drawdown"]) >= -0.40
        and int(leader["unpriced_exposure_events"]) == 0
    )
    strategy = run["strategy"]
    missing = [
        "parameter_neighborhood_stability",
        "100bps_cost_stress",
        "point_in_time_market_regime_stability",
        "multiple_testing_adjustment_across_batch_04",
        "multi_family_ensemble_interaction",
        "52_week_untouched_forward_record",
        "survivorship_safe_historical_universe",
    ]
    if leader["family"] == "carry_proxy":
        missing.append("archived_point_in_time_distribution_history")
    return {
        "candidate_id": f"candidate-{str(leader['experiment_id'])[4:]}",
        "experiment_id": leader["experiment_id"],
        "source_batch": "new_families_batch_04",
        "family": leader["family"],
        "recipe_name": leader["recipe_name"],
        "status": "provisional_new_family" if qualifies else "provisional_fragile",
        "selection_reasons": ["highest_development_selection_score_in_new_strategy_family"],
        "configuration": {
            "signals": strategy["signals"],
            "smoothing_weeks": strategy["smoothing_weeks"],
            "portfolio_method": strategy["portfolio"]["method"],
            "top_n": strategy["portfolio"]["top_n"],
            "minimum_signal": strategy["portfolio"]["min_signal"],
            "cost_bps": strategy["cost_bps"],
            "rebalance_frequency": strategy.get("rebalance_frequency", "monthly"),
        },
        "evidence": {
            key: leader[key] for key in leader if key not in {
                "signals", "fully_invested_pass", "untouched_holdout"
            }
        } | {"full_return_correlation_to_frozen_v4": correlation_to_v4},
        "passed_gates": [
            "point_in_time_formula_ordering",
            "one_week_signal_lag",
            "next_week_return_realization",
            "10bps_turnover_cost",
            "50bps_cost_diagnostic",
            "accounting_reconciliation",
        ],
        "missing_gates": missing,
        "final": False,
        "approved_for_live_trading": False,
    }


def build() -> tuple[dict[str, object], dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    store = SnapshotStore(STORE_ROOT)
    manifest = latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    payload = STORE_ROOT / snapshot_id / "payload"
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    all_assets = sorted(universe["symbols"])
    dates, prices, preparation = prepare_weekly_adjusted_prices(
        payload / "prices.csv", observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2005, 1, 7), expected_symbols=all_assets,
    )
    log_returns = weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    signals, _, signal_audit = reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )

    runs = {}
    leaderboard = []
    experiment_rows = []
    for recipe_name, family, spec in specifications():
        run = run_experiment(
            spec=spec, snapshot_id=snapshot_id, dates=dates, assets=RISK_ASSETS,
            strategy_panels=signals, prices=prices, simple_returns=simple_returns,
        )
        runs[str(run["experiment_id"])] = run
        row = metrics_row(recipe_name, family, run)
        leaderboard.append(row)
        experiment_rows.append({
            "experiment_id": run["experiment_id"], "source_snapshot_id": snapshot_id,
            "family": family, "recipe_name": recipe_name, "strategy": run["strategy"],
            "metrics": run["metrics"], "accounting": run["accounting"],
            "status": "retrospective_research_only", "untouched_holdout": False,
        })
    leaderboard.sort(key=lambda row: (-float(row["development_selection_score"]), str(row["experiment_id"])))
    for rank, row in enumerate(leaderboard, 1):
        row["overall_development_rank"] = rank

    family_leaders = {}
    for row in leaderboard:
        family_leaders.setdefault(str(row["family"]), row)

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    v4 = next(item for item in registry["candidates"] if item["experiment_id"] == "exp-fc7248702f02b421")
    trend_signals, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )
    v4_config = v4["configuration"]
    v4_run = run_experiment(
        spec=StrategySpec(
            signals=tuple(v4_config["signals"]), smoothing_weeks=int(v4_config["smoothing_weeks"]),
            portfolio=PortfolioSpec(
                method=str(v4_config["portfolio_method"]), top_n=int(v4_config["top_n"]),
                min_signal=float(v4_config["minimum_signal"]),
            ), cost_bps=float(v4_config["cost_bps"]),
        ), snapshot_id=snapshot_id, dates=dates, assets=RISK_ASSETS,
        strategy_panels=trend_signals, prices=prices, simple_returns=simple_returns,
    )
    v4_returns = [float(row["net_return"]) for row in v4_run["periods"]]
    leader_summaries = []
    existing = {item["experiment_id"]: item for item in registry["candidates"]}
    for family, leader in sorted(family_leaders.items()):
        run = runs[str(leader["experiment_id"])]
        values = [float(row["net_return"]) for row in run["periods"]]
        corr = correlation(values, v4_returns)
        entry = candidate_entry(leader, run, v4_returns, corr)
        existing[entry["experiment_id"]] = entry
        leader_summaries.append({
            **leader,
            "full_return_correlation_to_frozen_v4": corr,
            "saved_candidate_status": entry["status"],
        })

    family_runs = {"trend_v4": v4_run, **{
        family: runs[str(leader["experiment_id"])] for family, leader in family_leaders.items()
    }}
    family_names = list(family_runs)
    family_correlation_rows = []
    for left_index, left in enumerate(family_names):
        left_returns = [float(row["net_return"]) for row in family_runs[left]["periods"]]
        for right in family_names[left_index + 1 :]:
            right_returns = [float(row["net_return"]) for row in family_runs[right]["periods"]]
            family_correlation_rows.append({
                "family_left": left, "family_right": right,
                "full_return_correlation": correlation(left_returns, right_returns),
            })

    family_histories = {name: run["weights"] for name, run in family_runs.items()}
    ensemble_definitions = {
        "trend_v4": {"trend_v4": 1.0},
        "trend_plus_defensive": {"trend_v4": 0.5, "defensive": 0.5},
        "trend_defensive_carry": {"trend_v4": 1 / 3, "defensive": 1 / 3, "carry_proxy": 1 / 3},
        "all_four_families": {name: 0.25 for name in family_names},
    }
    ensemble_rows = []
    for ensemble_name, coefficients in ensemble_definitions.items():
        combined = combine_weight_histories(dates, family_histories, coefficients)
        periods, accounting = compute_path(dates, combined, simple_returns, cost_bps=10.0)
        recent = [row for row in periods if str(row["realization_date"]) >= "2021-01-01"]
        ensemble_rows.append({
            "ensemble_name": ensemble_name,
            "coefficients": json.dumps(coefficients, sort_keys=True),
            **{f"full_{key}": value for key, value in summarize_periods(periods).items()},
            **{f"recent_{key}": value for key, value in summarize_periods(recent).items()},
            "unpriced_exposure_events": accounting["unpriced_exposure_events"],
            "fully_invested_pass": accounting["fully_invested_pass"],
            "untouched_holdout": False,
        })
    registry["registry_version"] = 2
    registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    registry["latest_evidence_batch"] = "new_families_batch_04"
    registry["candidate_status_definitions"]["provisional_new_family"] = (
        "Leading configuration from a newly tested family; basic retrospective gates passed, deeper gates pending."
    )
    registry["candidates"] = sorted(existing.values(), key=lambda item: (str(item.get("family", "trend_momentum")), item["candidate_id"]))
    registry["candidate_count"] = len(registry["candidates"])

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "new_families_batch_04",
        "source_snapshot_id": snapshot_id,
        "market_data_through": dates[-1],
        "preparation": preparation,
        "experiment_count": len(leaderboard),
        "family_count": len(family_leaders),
        "design": {
            "recipes": RECIPES, "smoothing_weeks": [1, 2, 4], "top_n": [2, 4, 6],
            "portfolio_methods": list(SUPPORTED_METHODS), "cost_bps": 10.0,
        },
        "signal_audit": signal_audit,
        "family_leaders": leader_summaries,
        "family_pairwise_correlation": family_correlation_rows,
        "multi_family_ensemble_diagnostics": ensemble_rows,
        "reference_patterns": REFERENCE_PATTERNS,
        "limitations": [
            "All results are retrospective and the 2026 design can see the complete historical sample.",
            "The current ETF universe is not survivorship-safe.",
            "Cash-distribution events are ordered by event date but came from one current vintage, not archived historical vintages.",
            "Weekly mean reversion has materially higher turnover and must survive cost stress before promotion.",
            "Selecting family leaders from 288 new configurations creates a new multiple-testing obligation.",
        ],
    }
    return result, registry, leaderboard, experiment_rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def report(result: dict[str, object]) -> str:
    lines = [
        "# New Strategy Families — Batch 04", "",
        f"**{result['experiment_count']}** configurations tested mean reversion, defensive selection, and a distribution-yield carry proxy on immutable snapshot `{result['source_snapshot_id']}`.", "",
        "## Development-selected family leaders", "",
    ]
    for row in result["family_leaders"]:
        lines.extend([
            f"### {str(row['family']).replace('_', ' ').title()}", "",
            f"- Experiment: `{row['experiment_id']}`; recipe **{row['recipe_name']}**.",
            f"- Configuration: {row['rebalance_frequency']}, {row['portfolio_method']}, top {row['top_n']}, smoothing {row['smoothing_weeks']} weeks.",
            f"- Development: return **{pct(row['development_annual_return'])}**, Sharpe **{float(row['development_sharpe']):.3f}**, drawdown **{pct(row['development_max_drawdown'])}**.",
            f"- Retrospective 2016–2020: return **{pct(row['oos_2016_2020_annual_return'])}**, Sharpe **{float(row['oos_2016_2020_sharpe']):.3f}**.",
            f"- Retrospective 2021–present: return **{pct(row['oos_2021_present_annual_return'])}**, Sharpe **{float(row['oos_2021_present_sharpe']):.3f}**.",
            f"- 50 bps full-history stress: return **{pct(row['stress_50bps_annual_return'])}**, Sharpe **{float(row['stress_50bps_sharpe']):.3f}**.",
            f"- Correlation to frozen v4: **{float(row['full_return_correlation_to_frozen_v4']):.3f}**.",
            f"- Registry status: **{row['saved_candidate_status']}**.", "",
        ])
    lines.extend(["## Multi-family ensemble diagnostics", ""])
    for row in result["multi_family_ensemble_diagnostics"]:
        lines.append(
            f"- **{row['ensemble_name']}**: return **{pct(row['full_annual_return'])}**, "
            f"Sharpe **{float(row['full_sharpe_zero_rf']):.3f}**, "
            f"drawdown **{pct(row['full_max_drawdown'])}**, annual turnover **{float(row['full_average_annual_turnover']):.2f}**."
        )
    lines.extend([
        "", "These combinations net target weights before charging turnover, but they were designed after viewing the history and are not promotion candidates.", "",
        "## Carry-data limitation", "",
        "The carry proxy uses trailing cash distributions divided by unadjusted close and lags the cross-sectional signal one week. Event dates are causal, but Yahoo's entire action history was obtained in the current 2026 snapshot. The carry candidate therefore cannot pass the archived point-in-time distribution gate from this source.", "",
        "## Interpretation", "",
        "Family leaders were selected only from the development period and then displayed on later retrospective periods. They are saved for further testing, not promoted. Batch 04 adds another 288-way search, so robustness, dependence, and multiple-testing correction must be run before combining any leader with the trend sleeve.", "",
    ])
    return "\n".join(lines)


def main() -> int:
    result, registry, leaderboard, experiments = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "leaderboard.csv", leaderboard)
    write_csv(OUTPUT / "family_pairwise_correlation.csv", result["family_pairwise_correlation"])
    write_csv(OUTPUT / "multi_family_ensemble_diagnostics.csv", result["multi_family_ensemble_diagnostics"])
    (OUTPUT / "experiments.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in experiments), encoding="utf-8"
    )
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in (
            "leaderboard.csv", "experiments.jsonl", "family_pairwise_correlation.csv",
            "multi_family_ensemble_diagnostics.csv",
        )
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "experiment_count": result["experiment_count"],
        "family_leaders": result["family_leaders"],
        "registry_candidate_count": registry["candidate_count"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
