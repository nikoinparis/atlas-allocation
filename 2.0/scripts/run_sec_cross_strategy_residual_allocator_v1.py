#!/usr/bin/env python3
"""Purged walk-forward test of a capped cross-strategy residual allocator.

This is a one-shot, research-only experiment. It reconstructs unfinanced source
returns from the immutable dashboard export, chooses one predeclared rule without
using the locked replay, and applies realistic outer reallocation costs.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_cross_strategy_residual_allocator_v1.json"
SOURCE = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/sec_cross_strategy_residual_allocator_v1"
SEAL = OUTPUT / "execution_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def statistics(returns: pd.Series, periods: int = 52) -> dict[str, float | int | str]:
    values = returns.dropna().astype(float)
    wealth = (1.0 + values).cumprod()
    years = len(values) / periods
    standard_deviation = values.std(ddof=1)
    return {
        "observations": int(len(values)),
        "start": str(values.index.min().date()),
        "end": str(values.index.max().date()),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(values.mean() / standard_deviation * math.sqrt(periods)) if standard_deviation else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "ending_value_10000": float(wealth.iloc[-1] * 10000.0),
    }


def weekly_from_daily(series: pd.Series) -> pd.Series:
    return (1.0 + series).resample("W-FRI").prod() - 1.0


def reconstruct_sources(document: dict, config: dict) -> pd.DataFrame:
    by_id = {item["strategy"]["id"]: item for item in document["strategies"]}
    base_item = by_id[config["base_strategy_id"]]
    sleeve_item = by_id[config["sleeve_strategy_id"]]

    base_display = pd.Series(
        {pd.Timestamp(row["date"]): float(row["netReturn"]) for row in base_item["records"]}, name="base_display"
    ).sort_index()
    base_rule = config["base_source_reconstruction"]
    base = (base_display + (base_rule["display_gross"] - 1.0) * base_rule["annual_financing_rate"] / base_rule["periods_per_year"]) / base_rule["display_gross"]

    sleeve_daily_display = pd.Series(
        {pd.Timestamp(row["date"]): float(row["netReturn"]) for row in sleeve_item["dailyRecords"]}, name="sleeve_display"
    ).sort_index()
    sleeve_rule = config["sleeve_source_reconstruction"]
    financing = (sleeve_rule["display_gross"] - 1.0) * sleeve_rule["annual_financing_rate"] / sleeve_rule["periods_per_year"]
    sleeve_daily = (sleeve_daily_display + financing) / sleeve_rule["display_gross"]
    if len(sleeve_daily):
        sleeve_daily.iloc[0] += ((sleeve_rule["display_gross"] - 1.0) * sleeve_rule["initial_exposure_change_cost_bps"] / 10000.0) / sleeve_rule["display_gross"]
    sleeve = weekly_from_daily(sleeve_daily)

    common = pd.concat([base.rename("base"), sleeve.rename("sleeve")], axis=1).dropna()
    if len(common) < 130:
        raise RuntimeError("insufficient common history for frozen split")
    return common


def causal_signals(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    signal = config["signal"]
    lagged = frame.shift(1)
    lookback = signal["beta_correlation_lookback_weeks"]
    minimum = signal["minimum_history_weeks"]
    covariance = lagged.sleeve.rolling(lookback, min_periods=minimum).cov(lagged.base)
    variance = lagged.base.rolling(lookback, min_periods=minimum).var().replace(0.0, np.nan)
    beta = covariance / variance
    correlation = lagged.sleeve.rolling(lookback, min_periods=minimum).corr(lagged.base)
    residual = lagged.sleeve - beta * lagged.base
    short_momentum = (1.0 + residual).rolling(signal["short_residual_momentum_weeks"], min_periods=signal["short_residual_momentum_weeks"]).apply(np.prod, raw=True) - 1.0
    long_momentum = (1.0 + residual).rolling(signal["long_residual_momentum_weeks"], min_periods=signal["long_residual_momentum_weeks"]).apply(np.prod, raw=True) - 1.0
    sleeve_momentum = (1.0 + lagged.sleeve).rolling(signal["short_residual_momentum_weeks"], min_periods=signal["short_residual_momentum_weeks"]).apply(np.prod, raw=True) - 1.0
    residual_mean = residual.rolling(signal["long_residual_momentum_weeks"], min_periods=signal["long_residual_momentum_weeks"]).mean()
    residual_std = residual.rolling(signal["long_residual_momentum_weeks"], min_periods=signal["long_residual_momentum_weeks"]).std(ddof=1).replace(0.0, np.nan)
    information_ratio = residual_mean / residual_std * math.sqrt(52)
    gate = (short_momentum > 0.0) & (long_momentum > 0.0) & (sleeve_momentum > 0.0) & (correlation <= signal["maximum_correlation"])
    return pd.DataFrame({
        "beta": beta, "correlation": correlation, "residual_short_momentum": short_momentum,
        "residual_long_momentum": long_momentum, "sleeve_momentum": sleeve_momentum,
        "residual_information_ratio": information_ratio, "gate": gate.fillna(False),
    }, index=frame.index)


def target_weights(signals: pd.DataFrame, rule: str, cap: float, config: dict) -> pd.Series:
    if rule == "static":
        return pd.Series(cap, index=signals.index, name="target_weight")
    if rule == "gated":
        return signals.gate.astype(float).mul(cap).rename("target_weight")
    if rule == "covariance_scaled":
        scale = (signals.residual_information_ratio / config["signal"]["maximum_residual_information_ratio"]).clip(0.0, 1.0).fillna(0.0)
        return signals.gate.astype(float).mul(scale).mul(cap).rename("target_weight")
    raise ValueError(f"unknown rule: {rule}")


def apply_allocator(frame: pd.DataFrame, targets: pd.Series, cost_bps: float, delay: int = 0, positive_retention: float = 1.0, shock: float = 0.0) -> pd.DataFrame:
    weight = targets.shift(delay).fillna(0.0).clip(0.0, 1.0)
    sleeve_increment = frame.sleeve - frame.base
    if positive_retention != 1.0:
        sleeve_increment = sleeve_increment.where(sleeve_increment <= 0.0, sleeve_increment * positive_retention)
    if shock:
        shock_index = sleeve_increment.index[len(sleeve_increment) // 2]
        sleeve_increment = sleeve_increment.copy()
        sleeve_increment.loc[shock_index] += shock
    turnover = weight.diff().abs().fillna(weight.abs())
    cost = turnover * cost_bps / 10000.0
    net = frame.base + weight * sleeve_increment - cost
    return pd.DataFrame({"base_return": frame.base, "sleeve_return": frame.sleeve, "target_weight": weight, "turnover": turnover, "outer_cost": cost, "net_return": net}, index=frame.index)


def expanding_folds(development_length: int, config: dict) -> list[tuple[int, int]]:
    selection = config["selection"]
    start = selection["minimum_training_weeks"] + selection["purge_weeks"]
    folds = []
    while start + selection["validation_weeks"] <= development_length:
        folds.append((start, start + selection["validation_weeks"]))
        start += selection["step_weeks"]
    if not folds:
        raise RuntimeError("no purged walk-forward validation fold")
    return folds


def candidate_name(rule: str, cap: float) -> str:
    return f"{rule}__cap_{int(round(cap * 100)):02d}pct"


def objective(metrics: dict, config: dict) -> float:
    selection = config["selection"]
    return float(metrics["cagr"] + selection["objective_sharpe_weight"] * metrics["sharpe"] - selection["objective_drawdown_penalty"] * abs(metrics["max_drawdown"]))


def paired_block_probability(selected: pd.Series, base: pd.Series, simulations: int, block: int, seed: int) -> float:
    difference = (selected - base).to_numpy()
    count = len(difference)
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, count - block + 1))
    wins = 0
    for _ in range(simulations):
        chunks = []
        while sum(len(chunk) for chunk in chunks) < count:
            start = int(rng.choice(starts))
            chunks.append(difference[start:start + block])
        sample = np.concatenate(chunks)[:count]
        wins += float(np.prod(1.0 + sample) > 1.0)
    return wins / simulations


def main() -> int:
    config = json.loads(CONFIG.read_text())
    seal = json.loads(SEAL.read_text()) if SEAL.exists() else {}
    sealed = seal.get("sealed_sha256", {})
    seal_valid = bool(sealed) and all((ROOT / path).exists() and sha256(ROOT / path) == digest for path, digest in sealed.items())
    final_path = OUTPUT / "final_result.json"
    if not seal_valid or final_path.exists():
        print(json.dumps({"status": "blocked_execution_seal" if not seal_valid else "blocked_one_shot_already_complete", "live_trading_enabled": False}, indent=2))
        return 0

    frame = reconstruct_sources(json.loads(SOURCE.read_text()), config)
    signals = causal_signals(frame, config)
    candidates = {
        candidate_name(rule, cap): (rule, cap, target_weights(signals, rule, cap, config))
        for rule in config["candidate_rules"] for cap in config["candidate_caps"]
    }
    locked_weeks = config["selection"]["locked_replay_weeks"]
    purge_weeks = config["selection"]["purge_weeks"]
    locked_start = len(frame) - locked_weeks
    development_end = locked_start - purge_weeks
    development = frame.iloc[:development_end]
    folds = expanding_folds(len(development), config)

    fold_rows = []
    scores = []
    for name, (rule, cap, targets) in candidates.items():
        candidate_scores = []
        valid_risk = True
        for fold_number, (start, end) in enumerate(folds, 1):
            path = apply_allocator(frame, targets, config["outer_reallocation_cost_bps"]).iloc[start:end]
            result = statistics(path.net_return)
            score = objective(result, config)
            valid_risk &= result["max_drawdown"] >= config["selection"]["minimum_validation_max_drawdown"]
            candidate_scores.append(score)
            fold_rows.append({"candidate": name, "rule": rule, "cap": cap, "fold": fold_number, "validation_start": result["start"], "validation_end": result["end"], "objective": score, **result})
        scores.append({"candidate": name, "rule": rule, "cap": cap, "mean_validation_objective": float(np.mean(candidate_scores)), "minimum_validation_objective": float(np.min(candidate_scores)), "risk_gate_passed": bool(valid_risk)})
    score_frame = pd.DataFrame(scores).sort_values(["risk_gate_passed", "mean_validation_objective"], ascending=[False, False])
    eligible = score_frame[score_frame.risk_gate_passed]
    chosen_row = (eligible if not eligible.empty else score_frame).iloc[0]
    chosen = chosen_row.candidate
    rule, cap, targets = candidates[chosen]

    base_locked = frame.base.iloc[locked_start:]
    headline_path = apply_allocator(frame, targets, config["outer_reallocation_cost_bps"]).iloc[locked_start:]
    base_metrics = statistics(base_locked)
    headline_metrics = statistics(headline_path.net_return)
    stress_paths = {
        "double_outer_cost": apply_allocator(frame, targets, config["stress"]["double_cost_bps"]).iloc[locked_start:],
        **{f"delay_{delay}_weeks": apply_allocator(frame, targets, config["outer_reallocation_cost_bps"], delay=delay).iloc[locked_start:] for delay in config["stress"]["delay_weeks"]},
        "positive_increment_decay": apply_allocator(frame, targets, config["outer_reallocation_cost_bps"], positive_retention=config["stress"]["positive_increment_retention"]).iloc[locked_start:],
        "sleeve_shock": apply_allocator(frame, targets, config["outer_reallocation_cost_bps"], shock=config["stress"]["sleeve_shock"]).iloc[locked_start:],
    }
    stress_metrics = {name: statistics(path.net_return) for name, path in stress_paths.items()}
    bootstrap = {
        str(block): paired_block_probability(headline_path.net_return, base_locked, config["stress"]["bootstrap_simulations"], block, config["stress"]["bootstrap_seed"] + block)
        for block in config["stress"]["bootstrap_blocks"]
    }
    familywise_threshold = 1.0 - config["stress"]["familywise_alpha"] / len(candidates)
    gates = {
        "locked_cagr_improvement": headline_metrics["cagr"] - base_metrics["cagr"] >= config["promotion_gates"]["minimum_locked_cagr_improvement"],
        "locked_sharpe": headline_metrics["sharpe"] - base_metrics["sharpe"] >= config["promotion_gates"]["minimum_locked_sharpe_delta"],
        "locked_drawdown": headline_metrics["max_drawdown"] >= base_metrics["max_drawdown"] - config["promotion_gates"]["maximum_drawdown_deterioration"],
        "double_cost_improvement": stress_metrics["double_outer_cost"]["cagr"] > base_metrics["cagr"],
        "delay_improvement": all(stress_metrics[f"delay_{delay}_weeks"]["cagr"] > base_metrics["cagr"] for delay in config["stress"]["delay_weeks"]),
        "familywise_bootstrap": all(probability >= familywise_threshold for probability in bootstrap.values()),
        "source_research_gate": bool(config["source_research_gate_passed"]),
    }
    promoted = all(gates.values())

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(fold_rows).to_csv(OUTPUT / "purged_walk_forward_folds.csv", index=False)
    score_frame.to_csv(OUTPUT / "candidate_selection.csv", index=False)
    pd.concat([frame, signals, headline_path.add_prefix("selected_")], axis=1).rename_axis("Date").to_csv(OUTPUT / "selected_path.csv")
    pd.DataFrame([{"stress": name, **metrics} for name, metrics in stress_metrics.items()]).to_csv(OUTPUT / "locked_stress_results.csv", index=False)
    result = {
        "experiment_id": config["experiment_id"],
        "status": "completed_research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen_config_sha256": sha256(CONFIG),
        "frozen_source_sha256": sha256(SOURCE),
        "selection_protocol": {"candidate_count": len(candidates), "fold_count": len(folds), "development_weeks": len(development), "purge_weeks": purge_weeks, "locked_replay_weeks": locked_weeks, "locked_replay_selection_contaminated_by_prior_hypothesis": True},
        "selected_candidate": {"name": chosen, "rule": rule, "cap": float(cap), "mean_validation_objective": float(chosen_row.mean_validation_objective)},
        "locked_replay": {"base": base_metrics, "selected": headline_metrics, "cagr_improvement": headline_metrics["cagr"] - base_metrics["cagr"], "sharpe_improvement": headline_metrics["sharpe"] - base_metrics["sharpe"]},
        "stresses": stress_metrics,
        "paired_moving_block_probability_of_outperformance": bootstrap,
        "familywise_probability_threshold": familywise_threshold,
        "promotion_gates": gates,
        "promoted": promoted,
        "conclusion": "eligible_for_forward_challenger" if promoted else "diagnostic_only_not_a_replacement",
        "source_research_gate_reason": config["source_research_gate_reason"],
        "financing_used": False,
        "live_trading_enabled": False,
    }
    final_path.write_text(json.dumps(result, indent=2) + "\n")
    artifact_names = ["purged_walk_forward_folds.csv", "candidate_selection.csv", "selected_path.csv", "locked_stress_results.csv", "final_result.json"]
    manifest = {"generated_at": datetime.now(timezone.utc).isoformat(), "artifacts": {name: sha256(OUTPUT / name) for name in artifact_names}, "live_trading_enabled": False}
    (OUTPUT / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
