#!/usr/bin/env python3
"""Adversarially validate the 28% breadth-confirmed return ceiling."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from scripts.run_independent_return_source_discovery_batch_63 import build_sources
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.return_confirmation import cross_asset_features

CONFIG_PATH = ROOT / "config/breadth_ceiling_adversarial_validation_batch_65.json"
BATCH63_CONFIG = ROOT / "config/independent_return_source_discovery_batch_63.json"
BUNDLE = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a"
CORE_PATH = ROOT / "evidence/aggressive_return_discovery_batch_62/selected_candidate_weights.csv"
OUTPUT = ROOT / "evidence/breadth_ceiling_adversarial_validation_batch_65"
FORWARD_CONFIG = ROOT / "config/forward/breadth_confirmed_trend_return_ceiling_v3.json"
FORWARD_STATUS = ROOT / "evidence/forward_breadth_confirmed_trend_return_ceiling_v3/status.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def monthly_decisions(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    month = index.to_period("M").astype(str).to_numpy()
    selected = np.zeros(len(index), dtype=bool)
    if len(index) > 1:
        selected[:-1] = month[:-1] != month[1:]
    if len(index):
        selected[0] = True
        selected[-1] = (index[-1] + pd.Timedelta(days=7)).month != index[-1].month
    return index[selected]


def dynamic_weights(core: pd.DataFrame, trend: pd.DataFrame, breadth: pd.Series, threshold: float, high: float, low: float) -> pd.DataFrame:
    decisions = monthly_decisions(core.index)
    decision_alpha = pd.Series(np.where(breadth.reindex(decisions) >= threshold, high, low), index=decisions, dtype=float)
    alpha = decision_alpha.reindex(core.index).ffill().fillna(low)
    columns = core.columns.union(trend.columns)
    result = core.reindex(columns=columns, fill_value=0.0).mul(1.0 - alpha, axis=0)
    result = result.add(trend.reindex(index=core.index, columns=columns, fill_value=0.0).mul(alpha, axis=0), fill_value=0.0)
    return result.div(result.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def fixed_weights(index: pd.DatetimeIndex, columns: pd.Index, allocation: dict[str, float]) -> pd.DataFrame:
    frame = pd.DataFrame(0.0, index=index, columns=columns)
    for asset, weight in allocation.items():
        if asset in frame:
            frame[asset] = float(weight)
    return frame


def ols_attribution(strategy: pd.Series, factors: pd.DataFrame) -> list[dict[str, object]]:
    aligned = pd.concat([strategy.rename("strategy"), factors], axis=1).dropna()
    rows = []
    for name in factors.columns:
        x = np.column_stack([np.ones(len(aligned)), aligned[[name]].to_numpy()])
        coefficients = np.linalg.lstsq(x, aligned.strategy.to_numpy(), rcond=None)[0]
        residual = aligned.strategy.to_numpy() - x @ coefficients
        rows.append({"model": name, "annual_alpha": float(coefficients[0] * 52.0), "r_squared": float(1.0 - np.var(residual) / np.var(aligned.strategy)), f"beta_{name}": float(coefficients[1])})
    x = np.column_stack([np.ones(len(aligned)), aligned[factors.columns].to_numpy()])
    coefficients = np.linalg.lstsq(x, aligned.strategy.to_numpy(), rcond=None)[0]
    residual = aligned.strategy.to_numpy() - x @ coefficients
    row = {"model": "multifactor", "annual_alpha": float(coefficients[0] * 52.0), "r_squared": float(1.0 - np.var(residual) / np.var(aligned.strategy))}
    row.update({f"beta_{name}": float(value) for name, value in zip(factors.columns, coefficients[1:])})
    rows.append(row)
    return rows


def rolling_selector(grid: dict[str, pd.DataFrame], prices: pd.DataFrame, cost: float, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    forward = next_week_returns(prices)
    paths = {name: portfolio_path(weights, forward.reindex(columns=weights.columns), cost) for name, weights in grid.items()}
    years = range(int(config["rolling_selection"]["first_test_year"]), prices.index.max().year + 1)
    output = pd.DataFrame(0.0, index=prices.index, columns=next(iter(grid.values())).columns)
    selections = []
    default = "t065_h100_l040"
    current = default
    for year in years:
        test = prices.index[prices.index.year == year]
        if not len(test): continue
        train_end = test[0] - pd.Timedelta(days=7)
        train_index = prices.loc[:train_end].tail(int(config["rolling_selection"]["training_weeks"])).index
        scores = []
        for name, path in paths.items():
            subset = path.reindex(train_index).dropna(subset=["net_return"])
            score = batch60.metrics(subset)["cagr"] if len(subset) >= 104 else -np.inf
            scores.append((score, name))
        current = max(scores, key=lambda item: (item[0], item[1]))[1] if scores else current
        output.loc[test] = grid[current].reindex(test).to_numpy()
        selections.append({"test_year": year, "training_start": str(train_index.min().date()) if len(train_index) else "", "training_end": str(train_index.max().date()) if len(train_index) else "", "selected": current, "training_cagr": max(scores)[0] if scores else np.nan})
    first = prices.index[prices.index.year >= int(config["rolling_selection"]["first_test_year"])]
    if len(first):
        output.loc[:first[0]] = grid[default].loc[:first[0]]
    output = output.replace(0.0, np.nan).ffill().fillna(grid[default])
    output = output.div(output.sum(axis=1), axis=0)
    return output, pd.DataFrame(selections)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    prices = read_dated_csv(BUNDLE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    core = read_dated_csv(CORE_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    b63 = json.loads(BATCH63_CONFIG.read_text())
    trend = build_sources(prices, b63)["trend_consistency_top3"]
    features = cross_asset_features(prices, b63["discovery_assets"])
    breadth = features.breadth_positive_13
    frozen = config["frozen_rule"]
    candidate = dynamic_weights(core, trend, breadth, frozen["breadth_threshold"], frozen["trend_weight_when_confirmed"], frozen["trend_weight_otherwise"])
    ceiling = mix([core, trend], [0.4, 0.6])

    grid = {}
    for threshold in config["neighborhood"]["breadth_thresholds"]:
        for high in config["neighborhood"]["confirmed_trend_weights"]:
            for low in config["neighborhood"]["otherwise_trend_weights"]:
                name = f"t{int(threshold*100):03d}_h{int(high*100):03d}_l{int(low*100):03d}"
                grid[name] = dynamic_weights(core, trend, breadth, threshold, high, low)

    paths = {}
    performance_rows = []
    all_weights = {"candidate": candidate, "comparison_ceiling": ceiling, **{f"neighbor::{name}": value for name, value in grid.items()}}
    benchmarks = {}
    for name, allocation in config["simple_benchmarks"].items():
        benchmarks[name] = fixed_weights(prices.index, prices.columns, allocation)
        all_weights[f"benchmark::{name}"] = benchmarks[name]
    for name, weights in all_weights.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][int(cost)] = path
            for window, subset in batch60.windows(path).items():
                performance_rows.append({"implementation": name, "cost_bps": cost, "window": window, **batch60.metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    def row(name: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.implementation == name) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    ceiling_recent = row("comparison_ceiling", "trailing_3y", 50)
    candidate_recent = row("candidate", "trailing_3y", 50)
    neighborhood_rows = []
    for name in grid:
        recent = row(f"neighbor::{name}", "trailing_3y", 50)
        neighborhood_rows.append({"configuration": name, "trailing_3y_cagr": recent.cagr, "cagr_vs_ceiling": recent.cagr - ceiling_recent.cagr, "sharpe": recent.sharpe_zero_rf, "drawdown": recent.max_drawdown, "beats_ceiling": recent.cagr > ceiling_recent.cagr})
    neighborhood = pd.DataFrame(neighborhood_rows).sort_values("trailing_3y_cagr", ascending=False)

    delay_rows = []
    for delay in config["additional_feature_delays_weeks"]:
        weights = dynamic_weights(core, trend, breadth.shift(int(delay)), frozen["breadth_threshold"], frozen["trend_weight_when_confirmed"], frozen["trend_weight_otherwise"])
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            recent = batch60.metrics(batch60.windows(path)["trailing_3y"])
            delay_rows.append({"additional_delay_weeks": delay, "cost_bps": cost, **recent, "cagr_vs_ceiling": recent["cagr"] - (ceiling_recent.cagr if cost == 50 else row("comparison_ceiling", "trailing_3y", cost).cagr)})
    delays = pd.DataFrame(delay_rows)

    rng = np.random.default_rng(int(config["placebo_seed"]))
    placebo_rows = []
    valid = breadth.dropna().to_numpy()
    valid_index = breadth.dropna().index
    for permutation in range(int(config["placebo_permutations"])):
        permuted = pd.Series(rng.permutation(valid), index=valid_index).reindex(prices.index)
        weights = dynamic_weights(core, trend, permuted, frozen["breadth_threshold"], frozen["trend_weight_when_confirmed"], frozen["trend_weight_otherwise"])
        recent = batch60.metrics(batch60.windows(portfolio_path(weights, forward.reindex(columns=weights.columns), 50))["trailing_3y"])
        placebo_rows.append({"permutation": permutation, "trailing_3y_cagr": recent["cagr"], "candidate_outperformed": candidate_recent.cagr > recent["cagr"]})
    placebos = pd.DataFrame(placebo_rows)
    placebo_percentile = float((placebos.trailing_3y_cagr < candidate_recent.cagr).mean())

    candidate_years = []
    for year in sorted(set(paths["candidate"][50].index.year)):
        c = paths["candidate"][50].loc[paths["candidate"][50].index.year == year]
        b = paths["comparison_ceiling"][50].loc[paths["comparison_ceiling"][50].index.year == year]
        if len(c) >= 26:
            candidate_years.append({"year": year, "candidate_cagr": batch60.metrics(c)["cagr"], "ceiling_cagr": batch60.metrics(b)["cagr"]})
    calendar = pd.DataFrame(candidate_years)
    recent_dates = paths["candidate"][50].loc[paths["candidate"][50].index >= pd.Timestamp(candidate_recent.start)].index
    recent_year_metrics = calendar[calendar.year.isin(sorted(set(recent_dates.year)))]
    strongest_year = int(recent_year_metrics.sort_values("candidate_cagr", ascending=False).iloc[0].year)
    keep = recent_dates[recent_dates.year != strongest_year]
    ex_candidate = batch60.metrics(paths["candidate"][50].reindex(keep))
    ex_ceiling = batch60.metrics(paths["comparison_ceiling"][50].reindex(keep))

    selector_weights, selections = rolling_selector(grid, prices, 50.0, config)
    selector_paths = {cost: portfolio_path(selector_weights, forward.reindex(columns=selector_weights.columns), float(cost)) for cost in config["cost_bps"]}
    selector_rows = []
    for cost, path in selector_paths.items():
        for window, subset in batch60.windows(path).items():
            selector_rows.append({"cost_bps": cost, "window": window, **batch60.metrics(subset)})
    selector_performance = pd.DataFrame(selector_rows)

    start_rows = []
    for start in config["start_date_sensitivity"]:
        for implementation in ("candidate", "comparison_ceiling"):
            values = paths[implementation][50].loc[pd.Timestamp(start):]
            start_rows.append({"start": start, "implementation": implementation, **batch60.metrics(values)})
    starts = pd.DataFrame(start_rows)

    factor_returns = pd.DataFrame({name: path[50].net_return for name, path in paths.items() if name in [f"benchmark::{x}" for x in ("SPY", "QQQ", "XLK", "XLE")]})
    factor_returns.columns = [name.split("::")[1] for name in factor_returns.columns]
    attribution = pd.DataFrame(ols_attribution(paths["candidate"][50].net_return, factor_returns))
    multifactor_alpha = float(attribution.loc[attribution.model == "multifactor", "annual_alpha"].iloc[0])

    best_benchmark = max((row(f"benchmark::{name}", "trailing_3y", 50) for name in config["simple_benchmarks"]), key=lambda item: item.cagr)
    selector_recent = selector_performance[(selector_performance.cost_bps == 50) & (selector_performance.window == "trailing_3y")].iloc[0]
    candidate200 = row("candidate", "trailing_3y", 200)
    rules = config["confirmation_gates"]
    gate_values = {
        "neighborhood": float(neighborhood.beats_ceiling.mean()) >= rules["minimum_neighborhood_share_beating_ceiling_recent_3y"],
        "delayed_features": float((delays[delays.cost_bps == 50].cagr_vs_ceiling > 0).mean()) >= rules["minimum_delay_share_beating_ceiling_recent_3y"],
        "excluded_best_year": ex_candidate["cagr"] - ex_ceiling["cagr"] >= rules["minimum_ex_best_year_cagr_advantage"],
        "placebo_percentile": placebo_percentile >= rules["minimum_placebo_percentile"],
        "rolling_selector": float(selector_recent.cagr - ceiling_recent.cagr) >= rules["minimum_rolling_selector_recent_3y_cagr_advantage"],
        "simple_benchmark": float(candidate_recent.cagr - best_benchmark.cagr) >= rules["minimum_candidate_recent_3y_cagr_advantage_over_best_simple_benchmark"],
        "multifactor_alpha": multifactor_alpha >= rules["minimum_multifactor_annual_alpha"],
        "cost_200bps_drawdown": abs(float(candidate200.max_drawdown)) <= rules["maximum_200bps_recent_3y_drawdown_magnitude"],
    }
    confirmed = all(gate_values.values())

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    neighborhood.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    delays.to_csv(OUTPUT / "feature_delays.csv", index=False)
    placebos.to_csv(OUTPUT / "placebo_breadth.csv", index=False)
    calendar.to_csv(OUTPUT / "calendar_years.csv", index=False)
    selections.to_csv(OUTPUT / "rolling_selector_choices.csv", index=False)
    selector_performance.to_csv(OUTPUT / "rolling_selector_performance.csv", index=False)
    starts.to_csv(OUTPUT / "start_date_sensitivity.csv", index=False)
    attribution.to_csv(OUTPUT / "factor_attribution.csv", index=False)
    candidate.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "current_holdings.csv")
    result = {
        "batch": 65, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "candidate": config["candidate"],
        "candidate_trailing_3y_50bps_cagr": float(candidate_recent.cagr), "comparison_trailing_3y_50bps_cagr": float(ceiling_recent.cagr),
        "neighborhood_configurations": len(neighborhood), "neighborhood_win_share": float(neighborhood.beats_ceiling.mean()),
        "delay_win_share": float((delays[delays.cost_bps == 50].cagr_vs_ceiling > 0).mean()),
        "excluded_strongest_recent_year": strongest_year, "ex_best_year_cagr_advantage": float(ex_candidate["cagr"] - ex_ceiling["cagr"]),
        "placebo_percentile": placebo_percentile, "rolling_selector_recent_3y_cagr": float(selector_recent.cagr),
        "best_simple_benchmark_recent_3y_cagr": float(best_benchmark.cagr), "candidate_advantage_over_best_simple_benchmark": float(candidate_recent.cagr - best_benchmark.cagr),
        "multifactor_annual_alpha": multifactor_alpha, "candidate_recent_3y_200bps_drawdown": float(candidate200.max_drawdown),
        "gates": gate_values, "adversarial_confirmation_pass": confirmed,
        "decision": "strengthen_breadth_ceiling_status" if confirmed else "retain_as_unconfirmed_aggressive_ceiling",
        "forward_protocol_frozen": True, "forward_clock_started": True, "forward_observed_weeks": 0,
        "live_trading_enabled": False, "leverage_used": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failed = [name for name, passed in gate_values.items() if not passed]
    (OUTPUT / "report.md").write_text(
        "# Batch 65 — adversarial validation of the breadth return ceiling\n\n"
        f"Adversarial confirmation pass: **{confirmed}**. Failed gates: `{', '.join(failed) if failed else 'none'}`.\n\n"
        f"The candidate retained `{candidate_recent.cagr:.2%}` trailing-three-year CAGR at 50 bps versus `{ceiling_recent.cagr:.2%}` for the prior ceiling. "
        f"It beat the prior ceiling in `{neighborhood.beats_ceiling.mean():.1%}` of 30 nearby configurations and `{(delays[delays.cost_bps == 50].cagr_vs_ceiling > 0).mean():.1%}` of delayed-feature tests.\n\n"
        f"After excluding its strongest recent calendar year ({strongest_year}), candidate-minus-ceiling CAGR was `{ex_candidate['cagr'] - ex_ceiling['cagr']:+.2%}`. "
        f"Its breadth rule ranked at the `{placebo_percentile:.1%}` percentile of 100 permuted breadth histories. The past-only rolling selector returned `{selector_recent.cagr:.2%}` over the trailing three years.\n\n"
        f"Decision: `{result['decision']}`. A 52-week forward protocol is frozen beginning with the first eligible 2026-08-14 decision; no live trading was enabled.\n"
    )

    protocol = {**config["forward_protocol"], "candidate": config["candidate"], "rule": config["frozen_rule"], "weights_artifact_sha256": sha256(OUTPUT / "current_holdings.csv"), "source_bundle": "ggg_causal_v2_027530550388432a"}
    FORWARD_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    protocol_text = json.dumps(protocol, indent=2, sort_keys=True) + "\n"
    if FORWARD_CONFIG.exists() and FORWARD_CONFIG.read_text() != protocol_text:
        raise RuntimeError("frozen forward protocol changed")
    if not FORWARD_CONFIG.exists(): FORWARD_CONFIG.write_text(protocol_text)
    status = {"protocol_id": protocol["protocol_id"], "status": "awaiting_first_eligible_realization", "observed_weeks": 0, "required_weeks": protocol["required_weeks"], "latest_decision_date": None, "latest_realization_date": None, "live_trading_enabled": False}
    FORWARD_STATUS.parent.mkdir(parents=True, exist_ok=True)
    if not FORWARD_STATUS.exists(): FORWARD_STATUS.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
