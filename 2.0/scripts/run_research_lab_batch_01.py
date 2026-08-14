#!/usr/bin/env python3
"""Run the first standardized signal and portfolio-construction research batch."""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.evaluation import benchmark_regression, performance_metrics
from src.systematic_trader.portfolio_construction import PortfolioSpec, SUPPORTED_METHODS
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import (
    StrategySpec,
    retrospective_walk_forward,
    run_experiment,
    selection_score,
)
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
OUTPUT = ROOT / "evidence/research_lab_batch_01"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
SIGNAL_RECIPES = {
    "xsmom_only": ("xsmom_global",),
    "multi_momentum_only": ("multi_mom_invvol",),
    "time_series_momentum_only": ("tsmom_vol_scaled",),
    "trend_clarity_only": ("trend_clarity_momentum",),
    "moving_average_only": ("moving_average_distance",),
    "momentum_core": ("xsmom_global", "multi_mom_invvol", "tsmom_vol_scaled"),
    "trend_confirmation": ("trend_clarity_momentum", "moving_average_distance"),
    "all_five_v4": (
        "xsmom_global", "multi_mom_invvol", "tsmom_vol_scaled",
        "trend_clarity_momentum", "moving_average_distance",
    ),
}
FOLDS = [
    {
        "train_start": "2006-01-01", "train_end": "2015-12-31",
        "evaluation_start": "2016-01-01", "evaluation_end": "2020-12-31",
    },
    {
        "train_start": "2011-01-01", "train_end": "2020-12-31",
        "evaluation_start": "2021-01-01", "evaluation_end": "9999-12-31",
    },
]
REFERENCE_PATTERNS = [
    {
        "project": "vectorbt",
        "url": "https://github.com/polakowo/vectorbt",
        "pattern_used": "evaluate many parameter combinations through one consistent vector-style research path",
        "code_copied": False,
    },
    {
        "project": "pysystemtrade",
        "url": "https://github.com/robcarver17/pysystemtrade",
        "pattern_used": "separate forecasting rules from position sizing and portfolio construction",
        "code_copied": False,
    },
    {
        "project": "skfolio",
        "url": "https://github.com/skfolio/skfolio",
        "pattern_used": "treat portfolio optimization like model selection with chronological evaluation",
        "code_copied": False,
    },
    {
        "project": "Riskfolio-Lib",
        "url": "https://github.com/dcajasn/Riskfolio-Lib",
        "pattern_used": "compare multiple risk-aware allocation objectives rather than assuming one weighting rule",
        "code_copied": False,
    },
    {
        "project": "Manifold-BT",
        "url": "https://github.com/manifoldbt/manifoldbt",
        "pattern_used": "make costs, look-ahead control, walk-forward testing, and parameter sweeps first-class evidence",
        "code_copied": False,
    },
]


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    if not candidates:
        raise ValueError("no free provider snapshot exists")
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def specification_grid() -> list[tuple[str, StrategySpec]]:
    result: list[tuple[str, StrategySpec]] = []
    for recipe_name, signals in SIGNAL_RECIPES.items():
        for smoothing in (1, 4, 8):
            for top_n in (2, 4, 6):
                for method in SUPPORTED_METHODS:
                    result.append((recipe_name, StrategySpec(
                        signals=signals,
                        smoothing_weeks=smoothing,
                        portfolio=PortfolioSpec(
                            method=method,
                            top_n=top_n,
                            min_signal=0.05,
                            maximum_asset_weight=1.0,
                        ),
                        cost_bps=10.0,
                    )))
    return result


def flatten_metrics(prefix: str, metrics: dict[str, object]) -> dict[str, object]:
    keys = (
        "observations", "annual_return", "annual_volatility", "sharpe_zero_rf",
        "sortino_zero_target", "max_drawdown", "calmar", "average_annual_turnover", "total_cost",
    )
    return {f"{prefix}_{key}": metrics.get(key) for key in keys}


def build() -> dict[str, object]:
    store = SnapshotStore(STORE_ROOT)
    manifest = latest_free_manifest(store)
    snapshot_id = str(manifest["snapshot_id"])
    store.verify(snapshot_id)
    universe = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    all_assets = sorted(universe["symbols"])
    dates, prices, preparation = prepare_weekly_adjusted_prices(
        STORE_ROOT / snapshot_id / "payload/prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=datetime(2005, 1, 7).date(),
        expected_symbols=all_assets,
    )
    log_returns = weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {asset: math.expm1(value) if value is not None else None for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    panels, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )

    experiments: list[dict[str, object]] = []
    registry_rows: list[dict[str, object]] = []
    for recipe_name, spec in specification_grid():
        result = run_experiment(
            spec=spec,
            snapshot_id=snapshot_id,
            dates=dates,
            assets=RISK_ASSETS,
            strategy_panels=panels,
            prices=prices,
            simple_returns=simple_returns,
        )
        result.pop("weights")
        result["recipe_name"] = recipe_name
        experiments.append(result)
        registry_rows.append({
            "experiment_id": result["experiment_id"],
            "source_snapshot_id": snapshot_id,
            "recipe_name": recipe_name,
            "configuration": spec.to_dict(),
            "metrics": result["metrics"],
            "accounting": result["accounting"],
            "construction_audit": result["construction_audit"],
            "status": "retrospective_research_only",
            "untouched_holdout": False,
        })

    spy_by_date = {day: row["SPY"] for day, row in simple_returns.items() if row.get("SPY") is not None}
    leaderboard: list[dict[str, object]] = []
    for result in experiments:
        strategy = result["strategy"]
        portfolio = strategy["portfolio"]
        metrics = result["metrics"]
        periods = result["periods"]
        values = [float(row["net_return"]) for row in periods]
        benchmark = [float(spy_by_date[str(row["realization_date"])]) for row in periods]
        row = {
            "experiment_id": result["experiment_id"],
            "recipe_name": result["recipe_name"],
            "signals": "+".join(strategy["signals"]),
            "smoothing_weeks": strategy["smoothing_weeks"],
            "portfolio_method": portfolio["method"],
            "top_n": portfolio["top_n"],
            "cost_bps": strategy["cost_bps"],
            "development_selection_score": selection_score(metrics["development_2006_2015"]),
            **flatten_metrics("full", metrics["full_history"]),
            **flatten_metrics("development", metrics["development_2006_2015"]),
            **flatten_metrics("oos_2016_2020", metrics["retrospective_oos_2016_2020"]),
            **flatten_metrics("oos_2021_present", metrics["retrospective_oos_2021_present"]),
            **benchmark_regression(values, benchmark),
            "unpriced_exposure_events": result["accounting"]["unpriced_exposure_events"],
            "fully_invested_pass": result["accounting"]["fully_invested_pass"],
            "untouched_holdout": False,
        }
        leaderboard.append(row)
    leaderboard.sort(key=lambda row: (-float(row["development_selection_score"]), str(row["experiment_id"])))
    for rank, row in enumerate(leaderboard, 1):
        row["development_rank"] = rank

    selections, walk_forward_periods, walk_forward_metrics = retrospective_walk_forward(experiments, FOLDS)
    v4 = next(row for row in leaderboard if (
        row["recipe_name"] == "all_five_v4"
        and row["smoothing_weeks"] == 4
        and row["portfolio_method"] == "equal_weight"
        and row["top_n"] == 4
    ))
    best = leaderboard[0]
    spy_periods = [float(spy_by_date[day]) for day in sorted(spy_by_date) if "2016-01-01" <= day]
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "research_lab_batch_01",
        "source_snapshot_id": snapshot_id,
        "source_snapshot_observed_at_utc": manifest["observed_at_utc"],
        "market_data_through": dates[-1],
        "preparation": preparation,
        "experiment_count": len(experiments),
        "design": {
            "signal_recipes": {name: list(signals) for name, signals in SIGNAL_RECIPES.items()},
            "smoothing_weeks": [1, 4, 8],
            "top_n": [2, 4, 6],
            "portfolio_methods": list(SUPPORTED_METHODS),
            "cost_bps": 10.0,
            "decision_timing": "signals are lagged one week; monthly decisions; realization begins next week",
        },
        "reference_patterns": REFERENCE_PATTERNS,
        "best_by_development_only": best,
        "v4_benchmark": v4,
        "retrospective_walk_forward": {
            "folds": selections,
            "metrics": walk_forward_metrics,
            "periods": walk_forward_periods,
        },
        "spy_2016_present": performance_metrics(spy_periods).to_dict(),
        "limitations": [
            "All history through 2026-08-07 was visible when this batch was designed; no result is an untouched holdout.",
            "The current ETF list is not survivorship-safe historical membership.",
            "Testing 288 variants creates multiple-testing risk; rankings are hypotheses, not proof of future profitability.",
            "The walk-forward result uses chronological selection but remains retrospective research.",
            "Only weekly liquid-ETF long-only strategies and four allocation methods are covered in this first batch.",
        ],
        "registry_rows": registry_rows,
        "leaderboard": leaderboard,
    }


def pct(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def make_report(result: dict[str, object]) -> str:
    best = result["best_by_development_only"]
    v4 = result["v4_benchmark"]
    wf = result["retrospective_walk_forward"]
    selected_lines = [
        f"- {fold['evaluation_start']} to {fold['evaluation_end']}: `{fold['selected_experiment_id']}`; "
        f"evaluation Sharpe {float(fold['evaluation_metrics']['sharpe_zero_rf']):.3f}, "
        f"annual return {pct(fold['evaluation_metrics']['annual_return'])}."
        for fold in wf["folds"]
    ]
    source_lines = [
        f"- [{item['project']}]({item['url']}): {item['pattern_used']}; no source code copied."
        for item in result["reference_patterns"]
    ]
    return "\n".join([
        "# Research Laboratory — Batch 01", "",
        f"**{result['experiment_count']}** standardized trend/momentum and portfolio-construction experiments were run on immutable snapshot `{result['source_snapshot_id']}` through {result['market_data_through']}.", "",
        "## What was tested", "",
        "Eight signal recipes × three smoothing windows × three portfolio sizes × four allocation methods. Every experiment used lagged signals, calendar-causal monthly decisions, next-week return realization, and 10 bps turnover costs.", "",
        "## Development-selected leader", "",
        f"- Experiment: `{best['experiment_id']}`.",
        f"- Recipe / construction: **{best['recipe_name']} / {best['portfolio_method']}**, top {best['top_n']}, smoothing {best['smoothing_weeks']} weeks.",
        f"- Development (2006–2015): annual return **{pct(best['development_annual_return'])}**, Sharpe **{float(best['development_sharpe_zero_rf']):.3f}**, drawdown **{pct(best['development_max_drawdown'])}**.",
        f"- Retrospective 2016–2020: annual return **{pct(best['oos_2016_2020_annual_return'])}**, Sharpe **{float(best['oos_2016_2020_sharpe_zero_rf']):.3f}**, drawdown **{pct(best['oos_2016_2020_max_drawdown'])}**.",
        f"- Retrospective 2021–present: annual return **{pct(best['oos_2021_present_annual_return'])}**, Sharpe **{float(best['oos_2021_present_sharpe_zero_rf']):.3f}**, drawdown **{pct(best['oos_2021_present_max_drawdown'])}**.", "",
        "## Frozen-v4 benchmark row", "",
        f"The exact all-five, four-week smoothing, top-four equal-weight configuration is `{v4['experiment_id']}`. Full-history annual return is **{pct(v4['full_annual_return'])}**, Sharpe **{float(v4['full_sharpe_zero_rf']):.3f}**, and maximum drawdown **{pct(v4['full_max_drawdown'])}**.", "",
        "## Retrospective walk-forward", "",
        *selected_lines, "",
        f"The stitched evaluation path has annual return **{pct(wf['metrics']['annual_return'])}**, Sharpe **{float(wf['metrics']['sharpe_zero_rf']):.3f}**, and maximum drawdown **{pct(wf['metrics']['max_drawdown'])}**. Selection used only each fold's earlier training window, but this is still retrospective—not untouched—evidence.", "",
        "## Ideas taken from the awesome repository", "",
        *source_lines, "",
        "## Interpretation", "",
        "This batch is a research funnel, not a money-making claim. The 288-way comparison raises false-discovery risk, and the free ETF universe lacks point-in-time membership. Candidates must survive parameter-neighborhood, cost, regime, and future untouched tests before promotion.", "",
    ])


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    result = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    registry = result.pop("registry_rows")
    leaderboard = result.pop("leaderboard")
    periods = result["retrospective_walk_forward"].pop("periods")
    (OUTPUT / "experiments.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in registry), encoding="utf-8"
    )
    write_csv(OUTPUT / "leaderboard.csv", leaderboard)
    write_csv(OUTPUT / "walk_forward_returns.csv", periods)
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in ("experiments.jsonl", "leaderboard.csv", "walk_forward_returns.csv")
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "report.md").write_text(make_report(result), encoding="utf-8")
    print(json.dumps({
        "experiment_count": result["experiment_count"],
        "best": result["best_by_development_only"],
        "v4": result["v4_benchmark"],
        "walk_forward": result["retrospective_walk_forward"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
