#!/usr/bin/env python3
"""Frozen ensemble test for Batch 66's high-return candidates."""

from __future__ import annotations

import hashlib
import itertools
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from scripts.run_breadth_ceiling_adversarial_validation_batch_65 import ols_attribution
from scripts.run_exhaustive_return_first_discovery_batch_66 import metrics_for, static_weights
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.return_first_search import delay_weights

CONFIG_PATH = ROOT / "config/return_first_ensemble_batch_67.json"
OUTPUT = ROOT / "evidence/return_first_ensemble_batch_67"
BUNDLE = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a"


def load_components(prices: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    components = {}
    for name, path in config["components"].items():
        if path.startswith("static::"):
            components[name] = static_weights(prices, {path.split("::", 1)[1]: 1.0})
        else:
            components[name] = read_dated_csv(ROOT / path).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    diagnostic_path = next(iter(config["diagnostic_only_component"].values()))
    diagnostic = read_dated_csv(ROOT / diagnostic_path).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    return components, diagnostic


def grid_weights(names: list[str], increment: float, maximum: float, minimum_nonzero: int) -> list[dict[str, float]]:
    units = int(round(1.0 / increment))
    max_units = int(round(maximum / increment))
    rows = []
    for allocation in itertools.product(range(max_units + 1), repeat=len(names)):
        if sum(allocation) != units or sum(value > 0 for value in allocation) < minimum_nonzero:
            continue
        rows.append({name: value / units for name, value in zip(names, allocation)})
    return rows


def training_score(path: pd.DataFrame, end: pd.Timestamp) -> tuple[float, dict]:
    history = path.loc[:end]
    five = batch60.metrics(history.loc[history.index >= end - pd.DateOffset(years=5)])
    three = batch60.metrics(history.loc[history.index >= end - pd.DateOffset(years=3)])
    score = 0.60 * five["cagr"] + 0.30 * three["cagr"] + 0.10 * five["sharpe_zero_rf"]
    return float(score), {"training_5y_cagr": five["cagr"], "training_3y_cagr": three["cagr"], "training_5y_sharpe": five["sharpe_zero_rf"], "training_5y_drawdown": five["max_drawdown"]}


def excluded_best_year(candidate: pd.DataFrame, benchmarks: dict[str, pd.DataFrame], training_end: pd.Timestamp) -> tuple[int, dict[str, float]]:
    holdout = candidate.loc[candidate.index > training_end]
    full_years = [(batch60.metrics(group)["cagr"], int(year)) for year, group in holdout.groupby(holdout.index.year) if len(group) >= 40]
    strongest = max(full_years)[1]
    keep = holdout.index[holdout.index.year != strongest]
    candidate_cagr = batch60.metrics(candidate.reindex(keep))["cagr"]
    return strongest, {name: candidate_cagr - batch60.metrics(path.reindex(keep))["cagr"] for name, path in benchmarks.items()}


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    prices = read_dated_csv(BUNDLE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    training_end = pd.Timestamp(config["training_end"])
    components, hindsight = load_components(prices, config)
    repeated, repeated_hindsight = load_components(prices, config)
    deterministic = all(batch60.frame_hash(frame) == batch60.frame_hash(repeated[name]) for name, frame in components.items()) and batch60.frame_hash(hindsight) == batch60.frame_hash(repeated_hindsight)

    allocations = grid_weights(list(components), float(config["clean_grid"]["increment"]), float(config["clean_grid"]["maximum_single_component_weight"]), int(config["clean_grid"]["minimum_nonzero_components"]))
    candidates, rows = {}, []
    for index, allocation in enumerate(allocations):
        name = f"clean_{index:03d}"
        candidates[name] = mix(list(components.values()), list(allocation.values()))
        path = portfolio_path(candidates[name], forward.reindex(columns=candidates[name].columns), 50.0)
        score, detail = training_score(path, training_end)
        rows.append({"candidate": name, **allocation, "training_score": score, **detail})
    training = pd.DataFrame(rows).sort_values("training_score", ascending=False)
    selected = str(training.iloc[0].candidate)
    selected_weights = candidates[selected]

    clean_holdout_rows = []
    for name, weights in candidates.items():
        path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
        clean_holdout_rows.append({"candidate": name, **metrics_for(path, training_end)})
    clean_holdout = pd.DataFrame(clean_holdout_rows).sort_values("holdout_cagr", ascending=False)
    hindsight_clean_leader = str(clean_holdout.iloc[0].candidate)

    diagnostic_candidates = {}
    for base_label, base in (("training_selected", selected_weights), ("hindsight_clean_leader", candidates[hindsight_clean_leader])):
        for alpha in config["diagnostic_overlay_weights"]:
            name = f"diagnostic::{base_label}::hindsight52::{int(alpha * 100)}"
            diagnostic_candidates[name] = mix([base, hindsight], [1.0 - alpha, alpha])
    diagnostic_rows = []
    for name, weights in diagnostic_candidates.items():
        path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
        diagnostic_rows.append({"candidate": name, **metrics_for(path, training_end)})
    diagnostics = pd.DataFrame(diagnostic_rows).sort_values("holdout_cagr", ascending=False)

    benchmark_weights = {"xlk": components["xlk"], "breadth": components["breadth_ceiling"]}
    selected_paths = {cost: portfolio_path(selected_weights, forward.reindex(columns=selected_weights.columns), float(cost)) for cost in config["cost_bps"]}
    benchmark_paths = {name: {cost: portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost)) for cost in config["cost_bps"]} for name, weights in benchmark_weights.items()}
    selected_metrics = {cost: metrics_for(path, training_end) for cost, path in selected_paths.items()}
    benchmark_metrics = {name: {cost: metrics_for(path, training_end) for cost, path in paths.items()} for name, paths in benchmark_paths.items()}

    delay_rows = []
    for weeks in config["additional_execution_delays_weeks"]:
        weights = delay_weights(selected_weights, int(weeks))
        path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
        metric = metrics_for(path, training_end)
        delay_rows.append({"additional_delay_weeks": weeks, **metric, "beats_breadth": metric["holdout_cagr"] > benchmark_metrics["breadth"][50]["holdout_cagr"], "beats_xlk": metric["holdout_cagr"] > benchmark_metrics["xlk"][50]["holdout_cagr"]})
    delays = pd.DataFrame(delay_rows)

    strongest_year, ex_advantages = excluded_best_year(selected_paths[50], {name: paths[50] for name, paths in benchmark_paths.items()}, training_end)
    rolling_share, rolling_median, rolling_worst = rolling_win_share(selected_paths[50], benchmark_paths["xlk"][50])
    paired = selected_paths[50].loc[selected_paths[50].index > training_end, "net_return"] - benchmark_paths["xlk"][50].loc[benchmark_paths["xlk"][50].index > training_end, "net_return"]
    raw_p = batch60.paired_block_pvalue(paired.to_numpy(), samples=int(config["bootstrap_samples"]), block=int(config["bootstrap_block_weeks"]), seed=670001)
    adjusted_p = min(1.0, raw_p * len(allocations))

    factor_returns = {}
    for asset in ("SPY", "QQQ", "XLK", "XLE"):
        weights = static_weights(prices, {asset: 1.0})
        factor_returns[asset] = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0).net_return
    attribution = pd.DataFrame(ols_attribution(selected_paths[50].net_return, pd.DataFrame(factor_returns)))
    multifactor_alpha = float(attribution.loc[attribution.model == "multifactor", "annual_alpha"].iloc[0])

    component_return_paths = {}
    for name, weights in {**components, "hindsight_52pct": hindsight}.items():
        component_return_paths[name] = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0).net_return
    correlations = pd.DataFrame(component_return_paths).corr()

    rules = config["promotion_gates"]
    primary = selected_metrics[50]
    gates = {
        "return_target": primary["holdout_cagr"] >= rules["minimum_holdout_50bps_cagr"],
        "beat_xlk": primary["holdout_cagr"] - benchmark_metrics["xlk"][50]["holdout_cagr"] >= rules["minimum_advantage_over_xlk"],
        "beat_breadth": primary["holdout_cagr"] - benchmark_metrics["breadth"][50]["holdout_cagr"] >= rules["minimum_advantage_over_breadth"],
        "cost_100": selected_metrics[100]["holdout_cagr"] >= rules["minimum_holdout_100bps_cagr"],
        "cost_200": selected_metrics[200]["holdout_cagr"] >= rules["minimum_holdout_200bps_cagr"],
        "drawdown": abs(primary["holdout_drawdown"]) <= rules["maximum_holdout_drawdown_magnitude"],
        "delays": float(delays.beats_breadth.mean()) >= rules["minimum_delay_share_beating_breadth"],
        "excluded_best_year": ex_advantages["xlk"] >= rules["minimum_ex_best_year_advantage_over_xlk"],
        "rolling": rolling_share >= rules["minimum_rolling_3y_win_share_over_xlk"],
        "multifactor_alpha": multifactor_alpha >= rules["minimum_multifactor_annual_alpha"],
        "multiplicity": adjusted_p <= rules["maximum_adjusted_pvalue"],
    }
    qualified = all(gates.values())

    allocation = training.set_index("candidate").loc[selected, list(components)].to_dict()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    training.to_csv(OUTPUT / "training_rankings.csv", index=False)
    clean_holdout.to_csv(OUTPUT / "clean_grid_holdout_diagnostic.csv", index=False)
    diagnostics.to_csv(OUTPUT / "hindsight_52pct_overlay_diagnostic.csv", index=False)
    delays.to_csv(OUTPUT / "execution_delay_stress.csv", index=False)
    correlations.to_csv(OUTPUT / "component_correlations.csv")
    attribution.to_csv(OUTPUT / "factor_attribution.csv", index=False)
    pd.DataFrame([{"component": key, "weight": value} for key, value in allocation.items()]).to_csv(OUTPUT / "selected_component_weights.csv", index=False)
    selected_weights.rename_axis("Date").to_csv(OUTPUT / "selected_ensemble_weights.csv")
    selected_weights.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_current_holdings.csv")

    result = {
        "batch": 67, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "clean_grid_candidates": len(allocations),
        "diagnostic_hindsight_overlay_candidates": len(diagnostic_candidates), "deterministic": deterministic,
        "training_selected_candidate": selected, "training_selected_allocation": allocation,
        "training_selected_holdout_50bps_cagr": primary["holdout_cagr"], "training_selected_holdout_50bps_sharpe": primary["holdout_sharpe"],
        "training_selected_holdout_50bps_drawdown": primary["holdout_drawdown"], "training_selected_holdout_100bps_cagr": selected_metrics[100]["holdout_cagr"],
        "training_selected_holdout_200bps_cagr": selected_metrics[200]["holdout_cagr"], "training_selected_full_50bps_cagr": primary["full_cagr"],
        "training_selected_full_50bps_drawdown": primary["full_drawdown"], "xlk_holdout_50bps_cagr": benchmark_metrics["xlk"][50]["holdout_cagr"],
        "breadth_holdout_50bps_cagr": benchmark_metrics["breadth"][50]["holdout_cagr"], "delay_share_beating_breadth": float(delays.beats_breadth.mean()),
        "excluded_strongest_year": strongest_year, "ex_best_year_advantage_over_xlk": ex_advantages["xlk"], "ex_best_year_advantage_over_breadth": ex_advantages["breadth"],
        "rolling_3y_win_share_over_xlk": rolling_share, "rolling_median_advantage": rolling_median, "rolling_worst_advantage": rolling_worst,
        "raw_pvalue_vs_xlk": raw_p, "adjusted_pvalue_clean_grid": adjusted_p, "multifactor_annual_alpha": multifactor_alpha,
        "hindsight_clean_grid_leader": hindsight_clean_leader, "hindsight_clean_grid_leader_cagr": float(clean_holdout.iloc[0].holdout_cagr),
        "best_hindsight_52pct_overlay": str(diagnostics.iloc[0].candidate), "best_hindsight_52pct_overlay_cagr": float(diagnostics.iloc[0].holdout_cagr),
        "hindsight_52pct_overlays_promotion_eligible": False, "gates": gates, "qualified_replacement": qualified,
        "decision": "promote_provisional_ensemble_replacement" if qualified else "retain_components_and_do_not_promote_ensemble",
        "retrospective_research_only": True, "leverage_used": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failed = [name for name, passed in gates.items() if not passed]
    (OUTPUT / "report.md").write_text(
        "# Batch 67 — frozen return-first ensemble\n\n"
        f"The clean grid contained **{len(allocations)}** four-component allocations, all scored only through `{training_end.date()}`. The selected allocation was `{allocation}`.\n\n"
        f"It returned **{primary['holdout_cagr']:.2%}** at 50 bps, **{selected_metrics[100]['holdout_cagr']:.2%}** at 100 bps, and **{selected_metrics[200]['holdout_cagr']:.2%}** at 200 bps, with Sharpe **{primary['holdout_sharpe']:.3f}** and drawdown **{primary['holdout_drawdown']:.2%}**. XLK returned **{benchmark_metrics['xlk'][50]['holdout_cagr']:.2%}** and breadth returned **{benchmark_metrics['breadth'][50]['holdout_cagr']:.2%}**.\n\n"
        f"Qualified replacement: **{qualified}**. Failed gates: `{', '.join(failed) if failed else 'none'}`. The best diagnostic overlay containing the hindsight-selected 52.35% component reached **{diagnostics.iloc[0].holdout_cagr:.2%}**, but it was predeclared as ineligible for promotion.\n\n"
        f"Decision: `{result['decision']}`. No leverage or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if deterministic else 2


if __name__ == "__main__":
    raise SystemExit(main())
