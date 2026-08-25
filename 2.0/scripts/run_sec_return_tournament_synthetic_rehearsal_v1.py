#!/usr/bin/env python3
"""Run all eight frozen workstream shapes on deterministic synthetic data only."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader import sec_return_improvement as primitives
from systematic_trader import sec_tournament_rehearsal as rehearsal

CONFIG = ROOT / "config/sec_return_tournament_synthetic_rehearsal_v1.json"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
OUTPUT = ROOT / "evidence/sec_return_tournament_synthetic_rehearsal_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def score_frame(panel: pd.DataFrame, column: str) -> pd.DataFrame:
    return panel[["decision_at", "cik10", "sector", column]].rename(columns={column: "score"})


def main() -> int:
    config = json.loads(CONFIG.read_text())
    if not config.get("synthetic_only") or config.get("live_trading_enabled") is not False:
        raise RuntimeError("rehearsal must remain synthetic-only with live trading disabled")
    panel, returns = rehearsal.synthetic_panel(config["seed"], config["assets"], config["weekly_periods"], config["decision_interval_weeks"])
    contract = rehearsal.validate_point_in_time_panel(panel, config["target_horizon_weeks"], config["decision_interval_weeks"])
    features = ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]
    families = {
        "residual_momentum": score_frame(panel, "residual_momentum"),
        "trend_quality": score_frame(panel, "trend_quality"),
        "quality_momentum": score_frame(panel, "quality_momentum"),
    }
    event = panel.copy()
    event["score"] = 0.8 * event.quality_momentum + 0.2 * (event.event_score - 0.5) * 2
    families["event_conditioning"] = event[["decision_at", "cik10", "sector", "score"]]
    adaptive = panel.copy()
    adaptive["score"] = adaptive.groupby("decision_at")[features[:3]].rank(pct=True).mean(axis=1)
    families["adaptive_concentration"] = adaptive[["decision_at", "cik10", "sector", "score"]]
    ml = rehearsal.nested_ridge_predictions(panel, features, [0.1, 1.0, 10.0])
    ml = ml.merge(panel[["decision_at", "cik10", "sector"]], on=["decision_at", "cik10"], how="left")
    families["confidence_weighted_ml"] = ml[["decision_at", "cik10", "sector", "score"]]
    buffered = primitives.buffered_holding_selections(score_frame(panel, "quality_momentum"), breadth=config["breadth"], entry_rank_buffer=5, exit_rank_multiple=2.0, minimum_holding_decisions=2, maximum_holding_decisions=8)
    buffered = buffered.merge(panel[["decision_at", "cik10", "sector"]], on=["decision_at", "cik10"], how="left").rename(columns={"intended_weight": "weight"})
    weights = {name: rehearsal.top_weights(frame, config["breadth"], config["issuer_cap"], config["sector_cap"]) for name, frame in families.items()}
    weights["holding_and_exit"] = buffered[["decision_at", "cik10", "weight"]]
    control_weights = pd.DataFrame([{"decision_at": panel.decision_at.min(), "cik10": cik, "weight": 1 / config["assets"]} for cik in returns.columns])
    control, _ = rehearsal.portfolio_path(control_weights, returns, 50)
    base_paths, contributions = {}, {}
    for name, target in weights.items():
        base_paths[name], contributions[name] = rehearsal.portfolio_path(target, returns, 50)
    sleeve_frame = pd.DataFrame({name: base_paths[name] for name in ["residual_momentum", "trend_quality", "quality_momentum", "event_conditioning"]})
    allocator_weights = primitives.causal_strategy_allocator(sleeve_frame, lookback_weeks=52, minimum_history_weeks=26, momentum_lookbacks_weeks=[13, 26], maximum_sleeve_weight=0.6, minimum_active_sleeve_weight=0.1, independence_penalty=0.5)
    allocator_path = (allocator_weights[sleeve_frame.columns] * sleeve_frame).sum(axis=1)
    allocator_path -= allocator_weights[sleeve_frame.columns].diff().abs().sum(axis=1).fillna(0) * 50 / 10000
    base_paths["strategy_allocator"] = allocator_path
    rows = []
    missing_returns = returns.copy()
    missing_returns.iloc[::19, ::11] = np.nan
    sectors = panel.drop_duplicates("cik10").set_index("cik10").sector.to_dict()
    for family, path in base_paths.items():
        base_metric = rehearsal.metrics(path)
        if family == "strategy_allocator":
            stress_cost = base_metric; delay_worst = base_metric; missing_worst = base_metric
            issuer_share = 0.0; sector_ablated = base_metric["cagr"]
        else:
            stress_cost = rehearsal.metrics(rehearsal.portfolio_path(weights[family], returns, 200)[0])
            delay_worst = min((rehearsal.metrics(rehearsal.portfolio_path(weights[family], returns, 50, delay)[0]) for delay in [1, 2]), key=lambda x: x["cagr"])
            missing_worst = rehearsal.metrics(rehearsal.portfolio_path(weights[family], missing_returns, 50, 0, "adverse_total_loss")[0])
            positive = contributions[family].sum().clip(lower=0)
            issuer_share = float(positive.max() / positive.sum()) if positive.sum() else 0.0
            worst_sector = max(set(sectors.values()), key=lambda sector: float(positive[[c for c in positive.index if sectors[c] == sector]].sum()))
            removed = path - contributions[family][[c for c in contributions[family] if sectors[c] == worst_sector]].sum(axis=1)
            sector_ablated = rehearsal.metrics(removed)["cagr"]
        rolling = {str(window): rehearsal.rolling_share(path, control, window)[0] for window in config["rolling_windows_weeks"]}
        bootstrap = {str(block): rehearsal.bootstrap_probability(path - control, block, config["bootstrap_draws"], config["seed"]) for block in config["bootstrap_blocks_weeks"]}
        rows.append({"family": family, **base_metric, "severe_cost_cagr": stress_cost["cagr"], "worst_delay_cagr": delay_worst["cagr"], "adverse_missing_cagr": missing_worst["cagr"], "maximum_positive_issuer_share": issuer_share, "worst_sector_removed_cagr": sector_ablated, "rolling_26w_share": rolling["26"], "rolling_52w_share": rolling["52"], "bootstrap_4w_probability": bootstrap["4"], "bootstrap_13w_probability": bootstrap["13"]})
    results = pd.DataFrame(rows).sort_values("family")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    panel.head(500).to_csv(OUTPUT / "synthetic_panel_sample.csv", index=False)
    results.to_csv(OUTPUT / "family_rehearsal.csv", index=False)
    ml[["decision_at", "cik10", "selected_alpha", "train_end"]].to_csv(OUTPUT / "nested_ml_audit.csv", index=False)
    gate = json.loads(GATE.read_text())
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "synthetic_only": True, "point_in_time_contract": contract, "families_exercised": int(len(results)), "nested_ml_folds": int(ml.decision_at.nunique()), "real_research_gate_open": bool(gate.get("strategy_testing_authorized", False)), "real_performance_evaluated": False, "synthetic_winner_is_not_a_strategy_candidate": True, "sealed_for_real_run": False, "strategy_promotion_authorized": False, "live_trading_enabled": False, "artifact_sha256": {"config": sha256(CONFIG), "panel_sample": sha256(OUTPUT / "synthetic_panel_sample.csv"), "family_rehearsal": sha256(OUTPUT / "family_rehearsal.csv"), "nested_ml_audit": sha256(OUTPUT / "nested_ml_audit.csv")}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# Synthetic SEC tournament rehearsal v1\n\nAll eight workstream shapes completed on deterministic synthetic data. These values have no investment meaning. No real broad-universe performance was evaluated, no winner was promoted, and live trading remains disabled.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
