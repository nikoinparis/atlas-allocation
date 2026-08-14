#!/usr/bin/env python3
"""Stress provisional strategies across parameters, costs, and market regimes."""

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
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.portfolio_construction import PortfolioSpec
from src.systematic_trader.raw_signals import reconstruct_five_signals
from src.systematic_trader.research_lab import StrategySpec, run_experiment
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices, weekly_log_returns


STORE_ROOT = ROOT / "data/vintages"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
LEADERBOARD_PATH = ROOT / "evidence/research_lab_batch_01/leaderboard.csv"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
OUTPUT = ROOT / "evidence/robustness_batch_02"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]
COSTS_BPS = (10.0, 25.0, 50.0, 100.0)
ROBUSTNESS_RULES = {
    "neighborhood": {
        "same_signal_recipe_and_portfolio_method": True,
        "smoothing_weeks": [1, 4, 8],
        "top_n": [2, 4, 6],
        "minimum_median_2016_2020_sharpe": 0.35,
        "minimum_median_2021_present_sharpe": 0.75,
        "minimum_positive_return_neighbors_each_period": 7,
        "maximum_allowed_neighbor_drawdown": -0.35,
    },
    "cost_stress": {
        "maximum_cost_bps": 100.0,
        "minimum_annual_return_at_maximum_cost": 0.0,
        "minimum_sharpe_at_maximum_cost": 0.25,
    },
    "regime": {
        "definition": "point-in-time trailing 26-week SPY return and volatility at decision date",
        "risk_off": "trailing SPY return <= 0",
        "high_vol_risk_on": "trailing SPY return > 0 and annualized volatility >= 20%",
        "calm_risk_on": "trailing SPY return > 0 and annualized volatility < 20%",
        "minimum_observations_per_scored_regime": 52,
        "minimum_annual_return_per_scored_regime": -0.02,
    },
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def latest_free_manifest(store: SnapshotStore) -> dict[str, object]:
    candidates = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    return max(candidates, key=lambda item: parse_utc(str(item["observed_at_utc"])))


def candidate_spec(candidate: dict[str, object]) -> StrategySpec:
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
    )


def regime_labels(dates: list[str], simple_returns) -> dict[str, str]:
    labels: dict[str, str] = {}
    for index, day in enumerate(dates):
        recent_days = dates[max(0, index - 25) : index + 1]
        values = [simple_returns[item].get("SPY") for item in recent_days]
        valid = [float(value) for value in values if value is not None]
        if len(valid) < 26:
            continue
        trailing = math.prod(1.0 + value for value in valid) - 1.0
        volatility = statistics.stdev(valid) * math.sqrt(52.0)
        if trailing <= 0.0:
            labels[day] = "risk_off"
        elif volatility >= 0.20:
            labels[day] = "high_vol_risk_on"
        else:
            labels[day] = "calm_risk_on"
    return labels


def neighborhood_evidence(candidate: dict[str, object], rows: list[dict[str, str]]) -> dict[str, object]:
    config = candidate["configuration"]
    neighbors = [row for row in rows if (
        row["recipe_name"] == candidate["recipe_name"]
        and row["portfolio_method"] == config["portfolio_method"]
        and int(row["smoothing_weeks"]) in (1, 4, 8)
        and int(row["top_n"]) in (2, 4, 6)
    )]
    sharpe_early = [float(row["oos_2016_2020_sharpe_zero_rf"]) for row in neighbors]
    sharpe_recent = [float(row["oos_2021_present_sharpe_zero_rf"]) for row in neighbors]
    return_early = [float(row["oos_2016_2020_annual_return"]) for row in neighbors]
    return_recent = [float(row["oos_2021_present_annual_return"]) for row in neighbors]
    drawdowns = [
        float(row[key])
        for row in neighbors
        for key in ("oos_2016_2020_max_drawdown", "oos_2021_present_max_drawdown")
    ]
    passed = (
        len(neighbors) == 9
        and statistics.median(sharpe_early) >= 0.35
        and statistics.median(sharpe_recent) >= 0.75
        and sum(value > 0.0 for value in return_early) >= 7
        and sum(value > 0.0 for value in return_recent) >= 7
        and min(drawdowns) >= -0.35
    )
    return {
        "candidate_id": candidate["candidate_id"],
        "neighbor_count": len(neighbors),
        "median_2016_2020_sharpe": statistics.median(sharpe_early),
        "median_2021_present_sharpe": statistics.median(sharpe_recent),
        "positive_return_neighbors_2016_2020": sum(value > 0.0 for value in return_early),
        "positive_return_neighbors_2021_present": sum(value > 0.0 for value in return_recent),
        "worst_neighbor_drawdown": min(drawdowns),
        "pass": passed,
    }


def cost_evidence(candidate_id: str, periods: list[dict[str, object]]) -> tuple[list[dict[str, object]], bool]:
    rows = []
    for cost_bps in COSTS_BPS:
        returns = [
            float(row["gross_return"]) - float(row["turnover"]) * cost_bps / 10_000.0
            for row in periods
        ]
        metrics = performance_metrics(returns).to_dict()
        rows.append({"candidate_id": candidate_id, "cost_bps": cost_bps, **metrics})
    maximum = rows[-1]
    passed = maximum["annual_return"] > 0.0 and maximum["sharpe_zero_rf"] >= 0.25
    return rows, passed


def regime_evidence(
    candidate_id: str, periods: list[dict[str, object]], labels: dict[str, str]
) -> tuple[list[dict[str, object]], bool]:
    grouped: dict[str, list[float]] = {name: [] for name in ("risk_off", "high_vol_risk_on", "calm_risk_on")}
    for row in periods:
        label = labels.get(str(row["decision_date"]))
        if label:
            grouped[label].append(float(row["net_return"]))
    rows = []
    scored_passes = []
    for label, returns in grouped.items():
        metrics = performance_metrics(returns).to_dict() if returns else {"observations": 0}
        scored = len(returns) >= 52
        passed = not scored or float(metrics["annual_return"]) >= -0.02
        scored_passes.append(passed)
        rows.append({
            "candidate_id": candidate_id,
            "regime": label,
            "scored": scored,
            "pass": passed,
            **metrics,
        })
    return rows, all(scored_passes)


def build() -> tuple[dict[str, object], dict[str, object], dict[str, list[dict[str, object]]]]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    leaderboard = read_csv(LEADERBOARD_PATH)
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
    labels = regime_labels(dates, simple_returns)
    summaries = []
    neighborhood_rows = []
    cost_rows = []
    regime_rows = []

    for candidate in registry["candidates"]:
        run = run_experiment(
            spec=candidate_spec(candidate), snapshot_id=snapshot_id, dates=dates,
            assets=RISK_ASSETS, strategy_panels=panels, prices=prices, simple_returns=simple_returns,
        )
        neighborhood = neighborhood_evidence(candidate, leaderboard)
        costs, cost_pass = cost_evidence(candidate["candidate_id"], run["periods"])
        regimes, regime_pass = regime_evidence(candidate["candidate_id"], run["periods"], labels)
        overall = bool(neighborhood["pass"] and cost_pass and regime_pass)
        summary = {
            "candidate_id": candidate["candidate_id"],
            "experiment_id": candidate["experiment_id"],
            "neighborhood_pass": neighborhood["pass"],
            "cost_stress_pass": cost_pass,
            "regime_pass": regime_pass,
            "robustness_pass": overall,
        }
        summaries.append(summary)
        neighborhood_rows.append(neighborhood)
        cost_rows.extend(costs)
        regime_rows.extend(regimes)

        candidate["status"] = "provisional_robust" if overall else "provisional_fragile"
        candidate["robustness_batch_02"] = summary
        for gate, passed in (
            ("parameter_neighborhood_stability", neighborhood["pass"]),
            ("25_50_100bps_cost_stress", cost_pass),
            ("point_in_time_market_regime_stability", regime_pass),
        ):
            if passed and gate not in candidate["passed_gates"]:
                candidate["passed_gates"].append(gate)
            if passed and gate in candidate["missing_gates"]:
                candidate["missing_gates"].remove(gate)

    registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    registry["latest_evidence_batch"] = "robustness_batch_02"
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "robustness_batch_02",
        "source_snapshot_id": snapshot_id,
        "candidate_count": len(summaries),
        "rules_fixed_before_results": ROBUSTNESS_RULES,
        "robust_count": sum(row["robustness_pass"] for row in summaries),
        "fragile_count": sum(not row["robustness_pass"] for row in summaries),
        "candidate_summaries": summaries,
        "limitations": [
            "All robustness results are retrospective and share the visible Batch 01 history.",
            "Parameter neighborhoods reduce single-point sensitivity but do not remove multiple-testing bias.",
            "The three SPY-defined regimes are simple fixed diagnostics, not an optimized regime model.",
            "Survivorship-safe historical membership and 52 untouched weeks remain unavailable.",
        ],
    }
    return result, registry, {
        "neighborhoods.csv": neighborhood_rows,
        "cost_stress.csv": cost_rows,
        "regimes.csv": regime_rows,
        "candidate_summary.csv": summaries,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def report(result: dict[str, object]) -> str:
    lines = [
        "# Robustness Batch 02", "",
        f"All **{result['candidate_count']}** provisional strategies were tested against predeclared parameter-neighborhood, 25–100 bps cost, and point-in-time market-regime rules.", "",
        f"- Provisionally robust: **{result['robust_count']}**.",
        f"- Provisionally fragile: **{result['fragile_count']}**.", "",
        "## Candidate decisions", "",
    ]
    for row in result["candidate_summaries"]:
        lines.append(
            f"- `{row['candidate_id']}`: **{'robust' if row['robustness_pass'] else 'fragile'}** "
            f"(neighborhood {'pass' if row['neighborhood_pass'] else 'fail'}, "
            f"cost {'pass' if row['cost_stress_pass'] else 'fail'}, "
            f"regime {'pass' if row['regime_pass'] else 'fail'})."
        )
    lines.extend([
        "", "## Meaning", "",
        "A robust label means only that the candidate passed these three retrospective gates. It remains non-final, cannot trade, and still requires multiple-testing analysis, ensemble interaction checks, and at least 52 untouched forward weeks.", "",
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
    (OUTPUT / "report.md").write_text(report(result), encoding="utf-8")
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "candidate_count": result["candidate_count"],
        "robust_count": result["robust_count"],
        "fragile_count": result["fragile_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
