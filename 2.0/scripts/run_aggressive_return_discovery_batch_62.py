#!/usr/bin/env python3
"""Aggressive, unlevered return discovery around the causal GGG+xsmom engine."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.portfolio_construction import PortfolioSpec
from systematic_trader.raw_signals import reconstruct_five_signals
from systematic_trader.research_lab import StrategySpec, run_experiment
from systematic_trader.residual_momentum_source import residual_momentum_signal, top_five_weights
from systematic_trader.weekly_data import weekly_log_returns

CONFIG_PATH = ROOT / "config/aggressive_return_discovery_batch_62.json"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
OUTPUT = ROOT / "evidence/aggressive_return_discovery_batch_62"
LEADER_WEIGHTS = ROOT / "evidence/ggg_xsmom_deep_validation_batch_61/selected_variant_weights.csv"


def mix(histories: list[pd.DataFrame], coefficients: list[float]) -> pd.DataFrame:
    index = histories[0].index
    columns = histories[0].columns
    for frame in histories[1:]:
        columns = columns.union(frame.columns)
    result = pd.DataFrame(0.0, index=index, columns=columns)
    for frame, coefficient in zip(histories, coefficients):
        result = result.add(frame.reindex(index=index, columns=columns, fill_value=0.0) * float(coefficient), fill_value=0.0)
    return result.div(result.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def build_signal_sources(prices: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    dates, all_assets, price_panel = batch60.to_panel(prices)
    log_returns = weekly_log_returns(dates, all_assets, price_panel)
    simple_returns = {
        day: {asset: None if value is None else math.expm1(value) for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    signals, _ = reconstruct_five_signals(dates=dates, assets=all_assets, prices=price_panel, weekly_log_returns=log_returns)

    def run_source(name: str, assets: list[str], top_n: int, method: str) -> pd.DataFrame:
        spec = StrategySpec(
            signals=("xsmom_global",), smoothing_weeks=1,
            portfolio=PortfolioSpec(method=method, top_n=top_n, min_signal=0.05),
            cost_bps=0.0, rebalance_frequency="monthly",
        )
        result = run_experiment(
            spec=spec, snapshot_id=f"batch62::{name}", dates=dates, assets=assets,
            strategy_panels=signals, prices=price_panel, simple_returns=simple_returns,
        )
        frame = pd.DataFrame.from_dict(result["weights"], orient="index").fillna(0.0)
        frame.index = pd.to_datetime(frame.index)
        return frame.reindex(prices.index).fillna(0.0)

    sources = {
        "global_xsmom": run_source("global_xsmom", config["risk_assets"], 6, "score_inverse_volatility")
    }
    for spec in config["concentrated_global_specs"]:
        sources[spec["name"]] = run_source(spec["name"], config["risk_assets"], int(spec["top_n"]), spec["method"])
    for spec in config["sector_specs"]:
        sources[spec["name"]] = run_source(spec["name"], config["sector_assets"], int(spec["top_n"]), spec["method"])
    residual = top_five_weights(residual_momentum_signal(prices), prices)
    sources["residual_top5"] = residual.reindex(index=prices.index).fillna(0.0)
    return sources


def build_candidates(ggg: pd.DataFrame, leader: pd.DataFrame, sources: dict[str, pd.DataFrame], config: dict) -> dict[str, pd.DataFrame]:
    result = {"current_return_leader": leader}
    for alpha in config["global_xsmom_weights"]:
        result[f"global_xsmom_{int(alpha * 100):02d}"] = mix([ggg, sources["global_xsmom"]], [1.0 - alpha, alpha])
    for spec in config["concentrated_global_specs"]:
        for alpha in config["concentrated_blend_weights"]:
            result[f"{spec['name']}_{int(alpha * 100):02d}"] = mix([ggg, sources[spec["name"]]], [1.0 - alpha, alpha])
    for spec in config["sector_specs"]:
        for alpha in config["sector_blend_weights"]:
            result[f"{spec['name']}_{int(alpha * 100):02d}"] = mix([leader, sources[spec["name"]]], [1.0 - alpha, alpha])
    sector = sources[config["three_way_sector_source"]]
    for index, spec in enumerate(config["three_way_weights"], 1):
        result[f"three_way_{index}"] = mix([ggg, sources["global_xsmom"], sector], [spec["ggg"], spec["global_xsmom"], spec["sector_xsmom"]])
    for alpha in config["residual_blend_weights"]:
        result[f"leader_residual_{int(alpha * 100):02d}"] = mix([leader, sources["residual_top5"]], [1.0 - alpha, alpha])
    return result


def rolling_win_share(candidate: pd.DataFrame, leader: pd.DataFrame, width: int = 156, step: int = 13) -> tuple[float, float, float]:
    differences = []
    starts = list(range(0, len(candidate) - width + 1, step))
    final = len(candidate) - width
    if final not in starts: starts.append(final)
    for start in starts:
        c = batch60.metrics(candidate.iloc[start:start + width])["cagr"]
        b = batch60.metrics(leader.iloc[start:start + width])["cagr"]
        differences.append(c - b)
    return float(np.mean(np.array(differences) > 0.0)), float(np.median(differences)), float(np.min(differences))


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    bundle = ROOT / "data/ggg_vintages" / config["baseline_bundle_id"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    ggg = run_from_artifacts(bundle, causal_training=True, legacy_terminal_rebalance=False).stages["final_etf_weights"]
    leader = read_dated_csv(LEADER_WEIGHTS).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    sources = build_signal_sources(prices, config)
    repeated_sources = build_signal_sources(prices, config)
    deterministic = all(batch60.frame_hash(frame) == batch60.frame_hash(repeated_sources[name]) for name, frame in sources.items())
    candidates = build_candidates(ggg, leader, sources, config)
    expected_trials = len(config["global_xsmom_weights"]) + len(config["concentrated_global_specs"]) * len(config["concentrated_blend_weights"]) + len(config["sector_specs"]) * len(config["sector_blend_weights"]) + len(config["three_way_weights"]) + len(config["residual_blend_weights"])
    if len(candidates) - 1 != expected_trials:
        raise RuntimeError("candidate budget mismatch")

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix_sources = build_signal_sources(prices.loc[:cutoff], config)
        for name, full in sources.items():
            expected = full.loc[:cutoff]
            actual = prefix_sources[name].reindex_like(expected)
            difference = float((expected - actual).abs().max().max())
            prefix_rows.append({"source": name, "cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)

    performance_rows, paths = [], {}
    for name, weights in candidates.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][int(cost)] = path
            for window, subset in batch60.windows(path).items():
                performance_rows.append({"candidate": name, "cost_bps": cost, "window": window, **batch60.metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    def row(name: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.candidate == name) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    leader_recent = row("current_return_leader", "trailing_3y", 50)
    gates = config["qualification_gates"]
    qualification_rows = []
    for name in candidates:
        if name == "current_return_leader": continue
        r1, r2, r3 = row(name, "trailing_1y", 50), row(name, "trailing_2y", 50), row(name, "trailing_3y", 50)
        r100, full = row(name, "trailing_3y", 100), row(name, "full", 50)
        win_share, median_rolling, worst_rolling = rolling_win_share(paths[name][50], paths["current_return_leader"][50])
        paired = paths[name][50].loc[r3.start:r3.end, "net_return"] - paths["current_return_leader"][50].loc[r3.start:r3.end, "net_return"]
        raw_p = batch60.paired_block_pvalue(
            paired.to_numpy(), samples=int(config["bootstrap_samples"]), block=int(config["bootstrap_block_weeks"]),
            seed=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16),
        )
        adjusted = min(1.0, raw_p * expected_trials)
        checks = {
            "one_year_return": r1.cagr >= gates["minimum_trailing_1y_cagr"],
            "two_year_return": r2.cagr >= gates["minimum_trailing_2y_cagr"],
            "three_year_return": r3.cagr >= gates["minimum_trailing_3y_cagr"],
            "cost_stress": r100.cagr >= gates["minimum_trailing_3y_100bps_cagr"],
            "recent_drawdown": abs(r3.max_drawdown) <= gates["maximum_recent_3y_drawdown_magnitude"],
            "full_drawdown": abs(full.max_drawdown) <= gates["maximum_full_drawdown_magnitude"],
            "full_return": full.cagr >= gates["minimum_full_cagr"],
            "rolling_win_share": win_share >= gates["minimum_rolling_3y_win_share_vs_current_leader"],
            "adjusted_pvalue": adjusted <= gates["maximum_adjusted_pvalue_vs_current_leader"],
        }
        qualification_rows.append({
            "candidate": name, "trailing_1y_cagr": r1.cagr, "trailing_2y_cagr": r2.cagr,
            "trailing_3y_cagr": r3.cagr, "trailing_3y_cagr_vs_leader": r3.cagr - leader_recent.cagr,
            "trailing_3y_sharpe": r3.sharpe_zero_rf, "trailing_3y_drawdown": r3.max_drawdown,
            "trailing_3y_100bps_cagr": r100.cagr, "full_cagr": full.cagr, "full_drawdown": full.max_drawdown,
            "rolling_3y_win_share_vs_leader": win_share, "rolling_median_cagr_difference": median_rolling,
            "rolling_worst_cagr_difference": worst_rolling, "raw_pvalue": raw_p,
            f"adjusted_pvalue_{expected_trials}_trials": adjusted,
            **{f"gate_{key}": value for key, value in checks.items()}, "qualified": all(checks.values()),
        })
    qualification = pd.DataFrame(qualification_rows).sort_values(["qualified", "trailing_3y_cagr"], ascending=False)
    passing = qualification[qualification.qualified]
    selected = str(passing.iloc[0].candidate) if len(passing) else None
    point_best = str(qualification.iloc[0].candidate)
    saved = selected or point_best

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    prefixes.to_csv(OUTPUT / "source_prefix_invariance.csv", index=False)
    source_hashes = pd.DataFrame([{"source": name, "hash": batch60.frame_hash(frame), "repeated_hash": batch60.frame_hash(repeated_sources[name]), "deterministic": batch60.frame_hash(frame) == batch60.frame_hash(repeated_sources[name])} for name, frame in sources.items()])
    source_hashes.to_csv(OUTPUT / "source_determinism.csv", index=False)
    selected_weights = candidates[saved].copy(); selected_weights.index.name = "Date"
    selected_weights.to_csv(OUTPUT / "selected_candidate_weights.csv")
    selected_weights.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_candidate_current_holdings.csv")
    best = qualification.iloc[0]
    result = {
        "batch": 62, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_trials": expected_trials, "deterministic": deterministic,
        "prefix_invariance_pass": bool(prefixes.prefix_pass.all()),
        "maximum_prefix_weight_difference": float(prefixes.maximum_weight_difference.max()),
        "current_leader_trailing_3y_50bps_cagr": float(leader_recent.cagr),
        "qualified_candidate_count": len(passing), "selected_candidate": selected,
        "research_ceiling_candidate": point_best,
        "best_point_candidate": point_best, "best_point_trailing_1y_50bps_cagr": float(best.trailing_1y_cagr),
        "best_point_trailing_2y_50bps_cagr": float(best.trailing_2y_cagr),
        "best_point_trailing_3y_50bps_cagr": float(best.trailing_3y_cagr),
        "best_point_trailing_3y_50bps_sharpe": float(best.trailing_3y_sharpe),
        "best_point_trailing_3y_50bps_drawdown": float(best.trailing_3y_drawdown),
        "best_point_full_drawdown": float(best.full_drawdown),
        "decision": "save_aggressive_return_leader" if selected else "save_unqualified_aggressive_return_ceiling_for_confirmation",
        "retrospective_research_only": True, "leverage_used": False,
        "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Batch 62 — aggressive return discovery\n\n"
        f"Evaluated {expected_trials} unlevered return-expansion candidates. Deterministic: **{deterministic}**. "
        f"All {len(prefixes)} source-prefix checks passed: **{bool(prefixes.prefix_pass.all())}**.\n\n"
        f"Current leader trailing-three-year 50-bps CAGR was `{leader_recent.cagr:.2%}`. "
        f"Best point candidate `{point_best}` produced one/two/three-year CAGR of `{best.trailing_1y_cagr:.2%}` / `{best.trailing_2y_cagr:.2%}` / `{best.trailing_3y_cagr:.2%}`, "
        f"Sharpe `{best.trailing_3y_sharpe:.3f}`, recent drawdown `{best.trailing_3y_drawdown:.2%}`, and full drawdown `{best.full_drawdown:.2%}`.\n\n"
        f"Candidates passing every aggressive return gate: **{len(passing)}**. Selected: `{selected}`. "
        f"Research ceiling retained even if unqualified: `{point_best}`. "
        f"Decision: `{result['decision']}`. Drawdown limits were intentionally relaxed, but timing, costs, rolling consistency, and multiplicity controls were not.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if deterministic and bool(prefixes.prefix_pass.all()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
