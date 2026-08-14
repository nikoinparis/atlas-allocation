#!/usr/bin/env python3
"""Test fixed saved strategies as small additions to the causal GGG benchmark."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.portfolio_construction import PortfolioSpec
from systematic_trader.raw_signals import reconstruct_five_signals
from systematic_trader.research_lab import StrategySpec, run_experiment
from systematic_trader.weekly_data import weekly_log_returns

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/ggg_saved_strategy_improvement_batch_60.json"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
OUTPUT = ROOT / "evidence/ggg_saved_strategy_improvement_batch_60"
RISK_ASSETS = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "DBA", "TLT"]


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def to_panel(frame: pd.DataFrame) -> tuple[list[str], list[str], dict[str, dict[str, float | None]]]:
    dates = [str(day.date()) for day in frame.index]
    assets = list(frame.columns)
    panel = {
        str(day.date()): {
            asset: None if pd.isna(value) else float(value)
            for asset, value in row.items()
        }
        for day, row in frame.iterrows()
    }
    return dates, assets, panel


def candidate_spec(candidate: dict) -> StrategySpec:
    cfg = candidate["configuration"]
    return StrategySpec(
        signals=tuple(cfg["signals"]),
        smoothing_weeks=int(cfg["smoothing_weeks"]),
        portfolio=PortfolioSpec(
            method=str(cfg["portfolio_method"]),
            top_n=int(cfg["top_n"]),
            min_signal=float(cfg["minimum_signal"]),
        ),
        cost_bps=0.0,
        rebalance_frequency=str(cfg.get("rebalance_frequency", "monthly")),
    )


def build_candidate_weights(prices: pd.DataFrame, candidates: list[dict]) -> dict[str, pd.DataFrame]:
    dates, all_assets, price_panel = to_panel(prices)
    log_returns = weekly_log_returns(dates, all_assets, price_panel)
    simple_returns = {
        day: {asset: None if value is None else math.expm1(value) for asset, value in row.items()}
        for day, row in log_returns.items()
    }
    signals, _ = reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=price_panel, weekly_log_returns=log_returns
    )
    results = {}
    for candidate in candidates:
        candidate_id = str(candidate["candidate_id"])
        run = run_experiment(
            spec=candidate_spec(candidate), snapshot_id="ggg_causal_v2_027530550388432a",
            dates=dates, assets=RISK_ASSETS, strategy_panels=signals,
            prices=price_panel, simple_returns=simple_returns,
        )
        weights = pd.DataFrame.from_dict(run["weights"], orient="index").fillna(0.0)
        weights.index = pd.to_datetime(weights.index)
        results[candidate_id] = weights.reindex(prices.index).fillna(0.0)
    return results


def blended_weights(baseline: pd.DataFrame, challenger: pd.DataFrame, alpha: float) -> pd.DataFrame:
    columns = baseline.columns.union(challenger.columns)
    left = baseline.reindex(columns=columns, fill_value=0.0)
    right = challenger.reindex(index=baseline.index, columns=columns, fill_value=0.0)
    result = (1.0 - alpha) * left + alpha * right
    sums = result.sum(axis=1).replace(0.0, np.nan)
    return result.div(sums, axis=0).fillna(0.0)


def metrics(path: pd.DataFrame) -> dict:
    returns = pd.to_numeric(path["net_return"], errors="coerce").dropna()
    turnover = pd.to_numeric(path["turnover"], errors="coerce").reindex(returns.index)
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    annual = float(returns.mean() * 52.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    downside = float(np.sqrt(returns.clip(upper=0.0).pow(2).mean()) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe_zero_rf": annual / volatility if volatility else 0.0,
        "sortino_zero_target": annual / downside if downside else 0.0,
        "max_drawdown": float(drawdown.min()),
        "annual_one_way_turnover": float(turnover.mean() * 52.0),
    }


def windows(path: pd.DataFrame) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full": path,
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_3y": path.loc[path.index >= end - pd.DateOffset(years=3)],
        "post_2024": path.loc[path.index >= pd.Timestamp("2024-01-05")],
    }


def paired_block_pvalue(differences: np.ndarray, *, samples: int, block: int, seed: int) -> float:
    """One-sided circular block bootstrap p-value after centering at zero effect."""
    values = np.asarray(differences, dtype=float)
    observed = float(values.mean())
    centered = values - observed
    rng = np.random.default_rng(seed)
    nonpositive = 0
    blocks_needed = math.ceil(len(values) / block)
    offsets = np.arange(block)
    for _ in range(samples):
        starts = rng.integers(0, len(values), size=blocks_needed)
        indices = ((starts[:, None] + offsets[None, :]) % len(values)).ravel()[:len(values)]
        nonpositive += float(centered[indices].mean()) >= observed
    return (nonpositive + 1.0) / (samples + 1.0)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    registry = json.loads(REGISTRY_PATH.read_text())
    by_id = {row["candidate_id"]: row for row in registry["candidates"]}
    candidates = [by_id[item] for item in config["candidate_ids"]]
    bundle = ROOT / "data/ggg_vintages" / config["baseline_bundle_id"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    baseline = run_from_artifacts(bundle, causal_training=True, legacy_terminal_rebalance=False)
    baseline_weights = baseline.stages["final_etf_weights"]

    candidate_weights = build_candidate_weights(prices, candidates)
    repeated = build_candidate_weights(prices, candidates)
    deterministic = all(frame_hash(candidate_weights[key]) == frame_hash(repeated[key]) for key in candidate_weights)

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix = build_candidate_weights(prices.loc[:cutoff], candidates)
        for candidate_id, full in candidate_weights.items():
            expected = full.loc[:cutoff]
            actual = prefix[candidate_id].reindex_like(expected)
            difference = float((expected - actual).abs().max().max())
            prefix_rows.append({"candidate_id": candidate_id, "cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)

    paths: dict[str, dict[int, pd.DataFrame]] = {"baseline": {}}
    weights_by_name = {"baseline": baseline_weights}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        weights_by_name[f"standalone::{candidate_id}"] = candidate_weights[candidate_id]
        for alpha in config["candidate_allocation_weights"]:
            weights_by_name[f"blend::{candidate_id}::{alpha:.1f}"] = blended_weights(baseline_weights, candidate_weights[candidate_id], float(alpha))

    rows = []
    for name, weights in weights_by_name.items():
        paths[name] = {}
        for cost in config["stress_cost_bps"] + [config["primary_cost_bps"]]:
            cost = int(cost)
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][cost] = path
            for window, subset in windows(path).items():
                kind, candidate_id, alpha = ("baseline", "", 0.0) if name == "baseline" else (
                    ("standalone", name.split("::")[1], 1.0) if name.startswith("standalone")
                    else ("blend", name.split("::")[1], float(name.split("::")[2]))
                )
                rows.append({"implementation": name, "kind": kind, "candidate_id": candidate_id, "candidate_weight": alpha, "cost_bps": cost, "window": window, **metrics(subset)})
    performance = pd.DataFrame(rows).drop_duplicates(subset=["implementation", "cost_bps", "window"])

    primary_cost = int(config["primary_cost_bps"])
    primary_window = config["primary_window"]
    base_primary = performance[(performance.implementation == "baseline") & (performance.cost_bps == primary_cost) & (performance.window == primary_window)].iloc[0]
    base_full = performance[(performance.implementation == "baseline") & (performance.cost_bps == primary_cost) & (performance.window == "full")].iloc[0]
    comparisons = []
    trial_names = [name for name in weights_by_name if name.startswith("blend::")]
    for name in trial_names:
        row = performance[(performance.implementation == name) & (performance.cost_bps == primary_cost) & (performance.window == primary_window)].iloc[0]
        full = performance[(performance.implementation == name) & (performance.cost_bps == primary_cost) & (performance.window == "full")].iloc[0]
        paired = paths[name][primary_cost].loc[row.start:row.end, "net_return"] - paths["baseline"][primary_cost].loc[row.start:row.end, "net_return"]
        # Static positive blend sizes scale the same candidate-minus-baseline
        # return stream. Use one candidate-level seed so numerical Monte Carlo
        # noise cannot make an alpha pass while the identical hypothesis at a
        # different size fails.
        candidate_id = name.split("::")[1]
        raw_p = paired_block_pvalue(
            paired.to_numpy(), samples=int(config["bootstrap_samples"]),
            block=int(config["bootstrap_block_weeks"]),
            seed=int(hashlib.sha256(candidate_id.encode()).hexdigest()[:8], 16),
        )
        adjusted_p = min(1.0, raw_p * int(config["multiple_testing_trials"]))
        gates = {
            "cagr_improvement": float(row.cagr - base_primary.cagr) >= float(config["minimum_primary_cagr_improvement"]),
            "sharpe_guard": float(row.sharpe_zero_rf - base_primary.sharpe_zero_rf) >= float(config["minimum_primary_sharpe_improvement"]),
            "drawdown_guard": float(row.max_drawdown - base_primary.max_drawdown) >= -float(config["maximum_drawdown_deterioration"]),
            "full_history_guard": float(full.cagr - base_full.cagr) >= -float(config["maximum_full_history_cagr_sacrifice"]),
            "multiplicity_adjusted_pvalue": adjusted_p <= float(config["maximum_adjusted_pvalue"]),
        }
        comparisons.append({
            "implementation": name, "candidate_id": name.split("::")[1], "candidate_weight": float(name.split("::")[2]),
            "recent_3y_cagr": float(row.cagr), "recent_3y_cagr_improvement": float(row.cagr - base_primary.cagr),
            "recent_3y_sharpe": float(row.sharpe_zero_rf), "recent_3y_sharpe_improvement": float(row.sharpe_zero_rf - base_primary.sharpe_zero_rf),
            "recent_3y_max_drawdown": float(row.max_drawdown), "full_cagr_improvement": float(full.cagr - base_full.cagr),
            "raw_pvalue": raw_p, "adjusted_pvalue_24_trials": adjusted_p, **{f"gate_{key}": value for key, value in gates.items()},
            "all_promotion_gates": all(gates.values()),
        })
    comparison = pd.DataFrame(comparisons).sort_values(["recent_3y_cagr_improvement", "recent_3y_sharpe_improvement"], ascending=False)
    best = comparison.iloc[0]
    promoted = comparison[comparison.all_promotion_gates]
    provisional = promoted.iloc[0] if len(promoted) else None

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    comparison.to_csv(OUTPUT / "blend_comparison.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    candidate_weights[best.candidate_id].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "best_candidate_current_holdings.csv")
    weights_by_name[best.implementation].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "best_blend_current_holdings.csv")
    if provisional is not None:
        weights_by_name[provisional.implementation].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "provisional_challenger_current_holdings.csv")
    result = {
        "batch": 60, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_bundle_id": config["baseline_bundle_id"], "candidate_count": len(candidates), "blend_trial_count": len(trial_names),
        "deterministic": deterministic, "prefix_invariance_pass": bool(prefixes.prefix_pass.all()),
        "maximum_prefix_weight_difference": float(prefixes.maximum_weight_difference.max()),
        "baseline_recent_3y_50bps_cagr": float(base_primary.cagr), "baseline_recent_3y_50bps_sharpe": float(base_primary.sharpe_zero_rf),
        "best_implementation": str(best.implementation), "best_recent_3y_50bps_cagr": float(best.recent_3y_cagr),
        "best_recent_3y_50bps_cagr_improvement": float(best.recent_3y_cagr_improvement),
        "best_recent_3y_50bps_sharpe": float(best.recent_3y_sharpe), "best_adjusted_pvalue": float(best.adjusted_pvalue_24_trials),
        "promoted_candidate_count": len(promoted),
        "provisional_challenger": str(provisional.implementation) if provisional is not None else None,
        "decision": "save_provisional_challenger_for_deeper_validation" if len(promoted) else "retain_causal_ggg_baseline_and_continue_research",
        "retrospective_selection_only": True, "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Batch 60 — saved-strategy additions to causal GGG\n\n"
        f"Tested {len(candidates)} previously saved robust definitions at 10%, 20%, and 30% allocations ({len(trial_names)} blend trials). "
        f"All candidate rebuilds were deterministic: **{deterministic}**. All {len(prefixes)} prefix checks passed: **{bool(prefixes.prefix_pass.all())}**.\n\n"
        f"At 50 bps over the trailing three years, baseline CAGR/Sharpe were `{base_primary.cagr:.2%}` / `{base_primary.sharpe_zero_rf:.3f}`. "
        f"The best point estimate was `{best.implementation}` at `{best.recent_3y_cagr:.2%}` / `{best.recent_3y_sharpe:.3f}`, a CAGR change of `{best.recent_3y_cagr_improvement:+.2%}`. "
        f"Its 24-trial adjusted paired-bootstrap p-value was `{best.adjusted_pvalue_24_trials:.4f}`.\n\n"
        f"Blends passing the first screening gates: **{len(promoted)}**. Provisional challenger: `{result['provisional_challenger']}`. "
        f"Decision: `{result['decision']}`. These are retrospective comparisons on already observed history, not guarantees or untouched forward evidence.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if deterministic and bool(prefixes.prefix_pass.all()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
