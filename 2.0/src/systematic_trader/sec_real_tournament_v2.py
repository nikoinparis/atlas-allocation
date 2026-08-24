"""Eight-family evaluator shared by fixture tests and the gate-locked real runner."""

from __future__ import annotations

import numpy as np
import pandas as pd

from systematic_trader import sec_return_improvement as primitives
from systematic_trader import sec_tournament_rehearsal as engine

FEATURES = ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]


def _score(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    return panel[["decision_at", "execution_at", "cik10", "sector", column]].rename(columns={column: "score"})


def _execution_weights(scores: pd.DataFrame, breadth: int, issuer_cap: float, sector_cap: float) -> pd.DataFrame:
    weights = engine.top_weights(scores, breadth, issuer_cap, sector_cap)
    executions = scores[["decision_at", "execution_at"]].drop_duplicates()
    return weights.merge(executions, on="decision_at", validate="many_to_one").drop(columns="decision_at").rename(columns={"execution_at": "decision_at"})


def build_family_weights(panel: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    panel = panel.copy()
    panel["decision_at"] = pd.to_datetime(panel["decision_at"], utc=True)
    panel["execution_at"] = pd.to_datetime(panel["execution_at"], utc=True)
    families = {
        "residual_momentum": _score(panel, "residual_momentum"),
        "trend_quality": _score(panel, "trend_quality"),
        "quality_momentum": _score(panel, "quality_momentum"),
    }
    event = panel.copy()
    event["score"] = 0.8 * event.quality_momentum + 0.2 * (event.event_score - 0.5) * 2.0
    families["event_conditioning"] = event[["decision_at", "execution_at", "cik10", "sector", "score"]]
    adaptive = panel.copy()
    adaptive["score"] = adaptive.groupby("decision_at")[FEATURES[:3]].rank(pct=True).mean(axis=1)
    families["adaptive_concentration"] = adaptive[["decision_at", "execution_at", "cik10", "sector", "score"]]
    ml = engine.nested_ridge_predictions(panel, FEATURES, config["ml_ranking"]["ridge_alphas"], config["ml_ranking"]["minimum_training_decisions"])
    ml = ml.merge(panel[["decision_at", "execution_at", "cik10", "sector"]], on=["decision_at", "cik10"], how="left", validate="many_to_one")
    families["confidence_weighted_ml"] = ml[["decision_at", "execution_at", "cik10", "sector", "score"]]
    breadth = max(config["adaptive_concentration"]["breadth_tiers"])
    weights = {name: _execution_weights(frame, breadth, config["adaptive_concentration"]["maximum_issuer_weight"], config["adaptive_concentration"]["maximum_sector_weight"]) for name, frame in families.items()}
    buffered = primitives.buffered_holding_selections(_score(panel, "quality_momentum").drop(columns=["execution_at", "sector"]), breadth=breadth, entry_rank_buffer=max(config["holding_and_exit"]["entry_rank_buffer"]), exit_rank_multiple=max(config["holding_and_exit"]["exit_rank_multiple"]), minimum_holding_decisions=max(config["holding_and_exit"]["minimum_holding_decisions"]), maximum_holding_decisions=max(config["holding_and_exit"]["maximum_holding_decisions"]))
    execution = panel[["decision_at", "execution_at"]].drop_duplicates()
    weights["holding_and_exit"] = buffered.merge(execution, on="decision_at", validate="many_to_one")[["execution_at", "cik10", "intended_weight"]].rename(columns={"execution_at": "decision_at", "intended_weight": "weight"})
    return weights, ml


def evaluate(panel: pd.DataFrame, weekly_returns: pd.DataFrame, control: pd.Series, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights, ml = build_family_weights(panel, config)
    costs = config["tournament"]["primary_cost_bps"]
    paths, contributions = {}, {}
    for name, target in weights.items():
        paths[name], contributions[name] = engine.portfolio_path(target, weekly_returns, costs)
    sleeves = pd.DataFrame({name: paths[name] for name in ["residual_momentum", "trend_quality", "quality_momentum", "event_conditioning"]})
    alloc = config["strategy_allocator"]
    allocator_weights = primitives.causal_strategy_allocator(sleeves, lookback_weeks=alloc["lookback_weeks"], minimum_history_weeks=alloc["minimum_history_weeks"], momentum_lookbacks_weeks=alloc["momentum_lookbacks_weeks"], maximum_sleeve_weight=alloc["maximum_sleeve_weight"], minimum_active_sleeve_weight=alloc["minimum_active_sleeve_weight"], independence_penalty=alloc["independence_penalty"])
    def allocate(sleeve_paths: pd.DataFrame, allocation_cost: int) -> tuple[pd.Series, pd.DataFrame]:
        allocation = primitives.causal_strategy_allocator(sleeve_paths, lookback_weeks=alloc["lookback_weeks"], minimum_history_weeks=alloc["minimum_history_weeks"], momentum_lookbacks_weeks=alloc["momentum_lookbacks_weeks"], maximum_sleeve_weight=alloc["maximum_sleeve_weight"], minimum_active_sleeve_weight=alloc["minimum_active_sleeve_weight"], independence_penalty=alloc["independence_penalty"])
        result = (allocation[sleeve_paths.columns] * sleeve_paths).sum(axis=1)
        result -= allocation[sleeve_paths.columns].diff().abs().sum(axis=1).fillna(0) * allocation_cost / 10000
        return result, allocation
    allocator, allocator_weights = allocate(sleeves, costs)
    paths["strategy_allocator"] = allocator
    allocator_contribution = sum(contributions[name].mul(allocator_weights[name], axis=0) for name in sleeves.columns)
    contributions["strategy_allocator"] = allocator_contribution
    aligned_control = control.reindex(weekly_returns.index).fillna(0.0)
    sectors = panel.drop_duplicates("cik10").set_index("cik10").sector.to_dict()
    rows = []
    for family, path in paths.items():
        base = engine.metrics(path)
        recent = engine.metrics(path.tail(52))
        if family == "strategy_allocator":
            severe_paths = pd.DataFrame({name: engine.portfolio_path(weights[name], weekly_returns, max(config["tournament"]["cost_stress_bps"]))[0] for name in sleeves.columns})
            severe_cagr = engine.metrics(allocate(severe_paths, max(config["tournament"]["cost_stress_bps"]))[0].tail(52))["cagr"]
            delayed_values = []
            for delay in [1, 2]:
                delayed_paths = pd.DataFrame({name: engine.portfolio_path(weights[name], weekly_returns, costs, delay)[0] for name in sleeves.columns})
                delayed_values.append(engine.metrics(allocate(delayed_paths, costs)[0].tail(52))["cagr"])
            delay_cagr = min(delayed_values)
            adverse_paths = pd.DataFrame({name: engine.portfolio_path(weights[name], weekly_returns, costs, 0, "adverse_total_loss")[0] for name in sleeves.columns})
            adverse_cagr = engine.metrics(allocate(adverse_paths, costs)[0].tail(52))["cagr"]
        else:
            severe_cagr = min(engine.metrics(engine.portfolio_path(weights[family], weekly_returns, cost)[0].tail(52))["cagr"] for cost in config["tournament"]["cost_stress_bps"])
            delay_cagr = min(engine.metrics(engine.portfolio_path(weights[family], weekly_returns, costs, delay)[0].tail(52))["cagr"] for delay in [1, 2])
            adverse_cagr = engine.metrics(engine.portfolio_path(weights[family], weekly_returns, costs, 0, "adverse_total_loss")[0].tail(52))["cagr"]
        positive = contributions[family].sum().clip(lower=0)
        issuer_share = float(positive.max() / positive.sum()) if positive.sum() else 0.0
        sector_totals = {sector: float(positive[[c for c in positive.index if sectors.get(c) == sector]].sum()) for sector in set(sectors.values())}
        worst_sector = max(sector_totals, key=sector_totals.get)
        removed = path - contributions[family][[c for c in contributions[family] if sectors.get(c) == worst_sector]].sum(axis=1)
        sector_removed = engine.metrics(removed.tail(52))["cagr"]
        rolling = {window: engine.rolling_share(path, aligned_control, window)[0] for window in config["tournament"]["rolling_comparison_weeks"]}
        raw_bootstrap = min(engine.bootstrap_probability(path - aligned_control, block, config["tournament"]["bootstrap_draws"], config["tournament"]["bootstrap_seed"]) for block in config["tournament"]["bootstrap_blocks_weeks"])
        adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw_bootstrap) * config["tournament"]["familywise_trials"]))
        control_metric = engine.metrics(aligned_control)
        control_recent = engine.metrics(aligned_control.tail(52))
        rows.append({"family": family, "full_cagr": base["cagr"], "full_sharpe": base["sharpe"], "full_max_drawdown": base["max_drawdown"], "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_max_drawdown": recent["max_drawdown"], "recent_cagr_improvement_vs_control": recent["cagr"] - control_recent["cagr"], "full_cagr_improvement_vs_control": base["cagr"] - control_metric["cagr"], "severe_cost_recent_cagr": severe_cagr, "worst_delay_recent_cagr": delay_cagr, "adverse_missing_recent_cagr": adverse_cagr, "maximum_positive_issuer_share": issuer_share, "worst_sector_removed_recent_cagr": sector_removed, "minimum_rolling_outperformance_share": min(rolling.values()), "raw_bootstrap_probability_positive": raw_bootstrap, "familywise_adjusted_probability_positive": adjusted})
    return pd.DataFrame(rows).sort_values("family").reset_index(drop=True), ml
