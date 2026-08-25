#!/usr/bin/env python3
"""Comparable real-world survival diagnostics for every saved dashboard strategy."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/dashboard_strategy_survival_lab_v3.json"
SOURCE = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/dashboard_strategy_survival_lab_v3"
PUBLIC_OUTPUT = ROOT / "dashboard/public/strategy-survival.json"
SEAL = OUTPUT / "execution_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def statistics(returns: np.ndarray, periods: int = 52) -> dict[str, float | int]:
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if not len(clean):
        return {"observations": 0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    wealth = np.cumprod(1.0 + clean)
    years = len(clean) / periods
    volatility = float(np.std(clean, ddof=1)) if len(clean) > 1 else 0.0
    return {
        "observations": int(len(clean)),
        "cagr": float(wealth[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(np.mean(clean) / volatility * np.sqrt(periods)) if volatility else 0.0,
        "max_drawdown": float(np.min(wealth / np.maximum.accumulate(wealth) - 1.0)),
        "total_return": float(wealth[-1] - 1.0),
    }


def rolling_year_metrics(returns: np.ndarray, window: int) -> dict[str, float | int]:
    clean = np.asarray(returns, dtype=float)
    if len(clean) < window:
        result = statistics(clean)
        return {"windows": 1, "worst_return": result["total_return"], "median_return": result["total_return"], "positive_rate": float(result["total_return"] > 0)}
    values = np.array([np.prod(1.0 + clean[start:start + window]) - 1.0 for start in range(len(clean) - window + 1)])
    return {
        "windows": int(len(values)),
        "worst_return": float(np.min(values)),
        "median_return": float(np.median(values)),
        "positive_rate": float(np.mean(values > 0.0)),
    }


def moving_block_paths(returns: np.ndarray, simulations: int, horizon: int, block: int, seed: int) -> np.ndarray:
    clean = np.asarray(returns, dtype=float)
    if not len(clean):
        return np.zeros((simulations, horizon), dtype=float)
    rng = np.random.default_rng(seed)
    blocks_needed = int(np.ceil(horizon / block))
    maximum_start = max(len(clean) - block, 0)
    starts = rng.integers(0, maximum_start + 1, size=(simulations, blocks_needed))
    paths = np.empty((simulations, blocks_needed * block), dtype=float)
    offsets = np.arange(block)
    for column in range(blocks_needed):
        indices = np.minimum(starts[:, column, None] + offsets, len(clean) - 1)
        paths[:, column * block:(column + 1) * block] = clean[indices]
    return paths[:, :horizon]


def histogram(values: np.ndarray, bins: int = 44) -> dict[str, list[float]]:
    """Bin an outcome distribution for display. Edges are returned, not midpoints."""
    counts, edges = np.histogram(values, bins=bins)
    return {
        "edges": [round(float(v), 5) for v in edges],
        "counts": [int(v) for v in counts],
    }


def curve_bands(wealth: np.ndarray) -> dict[str, list[float]]:
    """Percentile fan of the simulated wealth curves, week by week."""
    quantiles = {"p05": 0.05, "p25": 0.25, "p50": 0.50, "p75": 0.75, "p95": 0.95}
    bands = {name: [round(float(v), 5) for v in np.quantile(wealth, q, axis=0)]
             for name, q in quantiles.items()}
    bands["week"] = [int(i + 1) for i in range(wealth.shape[1])]
    return bands


def sample_curves(wealth: np.ndarray, count: int, seed: int) -> list[list[float]]:
    """A deterministic handful of individual paths, so the fan has visible texture."""
    rng = np.random.default_rng(seed)
    picks = rng.choice(len(wealth), size=min(count, len(wealth)), replace=False)
    return [[round(float(v), 4) for v in wealth[i]] for i in sorted(picks)]


def monte_carlo_summary(paths: np.ndarray, distributions: bool = False, seed: int = 0) -> dict:
    wealth = np.cumprod(1.0 + paths, axis=1)
    total = wealth[:, -1] - 1.0
    drawdowns = wealth / np.maximum.accumulate(wealth, axis=1) - 1.0
    worst_drawdown = np.min(drawdowns, axis=1)
    extra: dict = {}
    if distributions:
        extra = {
            "return_histogram": histogram(total),
            "drawdown_histogram": histogram(worst_drawdown),
            "curve_bands": curve_bands(wealth),
            "sample_curves": sample_curves(wealth, 24, seed),
            "quartiles": {
                "p25_return": float(np.quantile(total, 0.25)),
                "p75_return": float(np.quantile(total, 0.75)),
                "p01_return": float(np.quantile(total, 0.01)),
                "p99_return": float(np.quantile(total, 0.99)),
                "worst_return": float(np.min(total)),
                "best_return": float(np.max(total)),
                "mean_return": float(np.mean(total)),
                "probability_of_20pct_capital_loss": float(np.mean(total <= -0.20)),
                "probability_of_beating_10pct": float(np.mean(total >= 0.10)),
            },
        }
    return {**extra, 
        "simulations": int(len(paths)),
        "median_return": float(np.median(total)),
        "p05_return": float(np.quantile(total, 0.05)),
        "p95_return": float(np.quantile(total, 0.95)),
        "probability_of_profit": float(np.mean(total > 0.0)),
        "probability_of_50pct_capital_loss": float(np.mean(total <= -0.50)),
        "probability_drawdown_over_30pct": float(np.mean(worst_drawdown <= -0.30)),
        "median_max_drawdown": float(np.median(worst_drawdown)),
        "p05_max_drawdown": float(np.quantile(worst_drawdown, 0.05)),
    }


def strategy_arrays(payload: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    records = payload["records"]
    returns = np.array([float(row.get("netReturn") or 0.0) for row in records], dtype=float)
    turnover = np.array([float(row.get("turnover") or 0.0) for row in records], dtype=float)
    costs = np.array([float(row.get("cost") or 0.0) for row in records], dtype=float)
    borrowed = []
    concentration = []
    for row in records:
        holdings = row.get("holdings") or []
        cash = sum(float(item.get("weight") or 0.0) for item in holdings if item.get("symbol") == "cash::USD")
        borrowed.append(max(0.0, -cash))
        positive = [float(item.get("weight") or 0.0) for item in holdings if item.get("symbol") != "cash::USD" and float(item.get("weight") or 0.0) > 0.0]
        concentration.append(max(positive, default=0.0))
    return returns, turnover, costs, np.array([borrowed, concentration], dtype=float)


def score_strategy(full: dict, rolling: dict, stresses: dict, monte: dict, concentration: float, config: dict, forward_weeks: int) -> tuple[int, list[dict], str, str]:
    weights = config["historical_resilience_score"]
    tests = [
        {"id": "full_drawdown", "label": "Full-history drawdown", "passed": full["max_drawdown"] > config["stress_tests"]["drawdown_failure_threshold"], "value": full["max_drawdown"], "threshold": config["stress_tests"]["drawdown_failure_threshold"], "points": weights["full_drawdown_points"]},
        {"id": "rolling_year", "label": "Worst rolling year", "passed": rolling["worst_return"] > 0.0, "value": rolling["worst_return"], "threshold": 0.0, "points": weights["positive_worst_rolling_year_points"]},
        {"id": "double_cost", "label": "Doubled trading cost", "passed": stresses["double_cost"]["cagr"] > 0.0, "value": stresses["double_cost"]["cagr"], "threshold": 0.0, "points": weights["double_cost_positive_points"]},
        {"id": "signal_decay", "label": "25% positive-signal decay", "passed": stresses["signal_decay"]["cagr"] > 0.0, "value": stresses["signal_decay"]["cagr"], "threshold": 0.0, "points": weights["signal_decay_positive_points"]},
        {"id": "monte_profit", "label": "Monte Carlo profit probability", "passed": monte["probability_of_profit"] >= weights["profit_probability_threshold"], "value": monte["probability_of_profit"], "threshold": weights["profit_probability_threshold"], "points": weights["monte_carlo_profit_probability_points"]},
        {"id": "monte_drawdown", "label": "Monte Carlo drawdown control", "passed": monte["probability_drawdown_over_30pct"] <= weights["drawdown_probability_threshold"], "value": monte["probability_drawdown_over_30pct"], "threshold": weights["drawdown_probability_threshold"], "points": weights["monte_carlo_drawdown_points"]},
        {"id": "concentration", "label": "Single-position concentration", "passed": concentration <= config["stress_tests"]["concentration_threshold"], "value": concentration, "threshold": config["stress_tests"]["concentration_threshold"], "points": weights["concentration_points"]},
    ]
    score = int(sum(test["points"] for test in tests if test["passed"]))
    for test in tests:
        test["status"] = "pass" if test["passed"] else "fail"
    if score >= config["interpretation"]["historically_resilient_minimum_score"]:
        historical_grade = "historically_resilient"
    elif score >= config["interpretation"]["mixed_minimum_score"]:
        historical_grade = "mixed_evidence"
    else:
        historical_grade = "historically_fragile"
    live_verdict = "forward_validation_complete" if forward_weeks >= config["interpretation"]["live_proof_required_forward_weeks"] else "not_proven_live"
    return score, tests, historical_grade, live_verdict


def main() -> int:
    config = json.loads(CONFIG.read_text())
    seal = json.loads(SEAL.read_text()) if SEAL.exists() else {}
    sealed = seal.get("sealed_sha256", {})
    seal_valid = bool(sealed) and all((ROOT / name).exists() and sha256(ROOT / name) == digest for name, digest in sealed.items())
    final = OUTPUT / "final_result.json"
    if not seal_valid or final.exists():
        print(json.dumps({"status": "blocked_execution_seal" if not seal_valid else "blocked_one_shot_already_complete", "live_trading_enabled": False}, indent=2))
        return 0

    bundle = json.loads(SOURCE.read_text())
    period = int(config["annualization_periods"])
    stress = config["stress_tests"]
    monte_cfg = config["monte_carlo"]
    strategies = []
    comparison_rows = []
    for ordinal, payload in enumerate(bundle["strategies"]):
        strategy = payload["strategy"]
        returns, turnover, recorded_costs, arrays = strategy_arrays(payload)
        borrowed, concentration = arrays
        full = statistics(returns, period)
        recent = statistics(returns[-52:], period)
        rolling = rolling_year_metrics(returns, int(stress["rolling_window_weeks"]))

        estimated_cost = np.where(recorded_costs > 0.0, recorded_costs, turnover * float(strategy["disclosures"]["costBps"]) / 10000.0)
        double_cost_returns = returns - estimated_cost * float(stress["additional_cost_multiplier"])
        financing_returns = returns - borrowed * float(stress["additional_financing_rate"]) / period
        signal_decay_returns = np.where(returns > 0.0, returns * float(stress["positive_return_retention"]), returns)
        crash_returns = returns[-int(stress["crash_evaluation_window_weeks"]):].copy()
        crash_index = min(int(stress["crash_insertion_week"]), max(len(crash_returns) - 1, 0))
        if len(crash_returns):
            crash_returns[crash_index] = min(crash_returns[crash_index], float(stress["crash_week_return"]))
        stresses = {
            "double_cost": statistics(double_cost_returns, period),
            "financing_plus_300bps": statistics(financing_returns, period),
            "signal_decay": statistics(signal_decay_returns, period),
            "one_off_20pct_crash": statistics(crash_returns, period),
        }

        block_summaries = {}
        for block in monte_cfg["block_lengths"]:
            block_seed = int(monte_cfg["seed"]) + ordinal * 100 + int(block)
            paths = moving_block_paths(returns, int(monte_cfg["simulations"]), int(monte_cfg["horizon_weeks"]), int(block), block_seed)
            is_primary = int(block) == int(monte_cfg["primary_block_length"])
            block_summaries[str(block)] = monte_carlo_summary(paths, distributions=is_primary, seed=block_seed)
        primary_monte = block_summaries[str(monte_cfg["primary_block_length"])]
        maximum_concentration = float(np.max(concentration)) if len(concentration) else 0.0
        average_concentration = float(np.mean(concentration)) if len(concentration) else 0.0
        forward_weeks = int(strategy["forward"].get("observedWeeks") or 0)
        score, tests, grade, live_verdict = score_strategy(full, rolling, stresses, primary_monte, maximum_concentration, config, forward_weeks)
        failed = [test["label"] for test in tests if not test["passed"]]
        validation_values = [value for value in payload.get("validation", {}).values() if isinstance(value, bool)]
        research_gate = {
            "status": "passed" if validation_values and all(validation_values) else "failed" if validation_values else "not_exposed_in_dashboard",
            "boolean_checks": len(validation_values),
            "checks_passed": int(sum(validation_values)),
            "source_validation": payload.get("validation", {}),
        }
        result = {
            "id": strategy["id"],
            "name": strategy["name"],
            "short_name": strategy["shortName"],
            "as_of": strategy["asOf"],
            "observations": int(len(returns)),
            "start": payload["records"][0]["date"],
            "end": payload["records"][-1]["date"],
            "historical_resilience_score": score,
            "historical_grade": grade,
            "live_verdict": live_verdict,
            "research_evidence_gate": research_gate,
            "plain_english_verdict": "Historically survived the frozen stress suite, but is not proven live." if grade == "historically_resilient" else "Some historical stresses failed; treat as fragile research, not a live-ready strategy.",
            "binding_failures": failed,
            "historical": {"full": full, "trailing_52w": recent, "rolling_52w": rolling},
            "weekly_returns": [{"date": row["date"], "net": round(float(row.get("netReturn") or 0.0), 6),
                                 "wealth": round(float(row.get("wealth") or 0.0), 6),
                                 "drawdown": round(float(row.get("drawdown") or 0.0), 6)}
                                for row in payload["records"]],
            "stress_tests": stresses,
            "monte_carlo": {"method": "moving-block bootstrap of native weekly net returns", "block_summaries": block_summaries, "primary_block_weeks": monte_cfg["primary_block_length"]},
            "concentration": {"maximum_single_position_weight": maximum_concentration, "average_largest_position_weight": average_concentration, "average_borrowed_exposure": float(np.mean(borrowed)) if len(borrowed) else 0.0},
            "test_results": tests,
            "forward_evidence": {"observed_weeks": forward_weeks, "required_weeks": int(strategy["forward"].get("requiredWeeks") or 52), "status": strategy["forward"].get("status"), "passed": forward_weeks >= config["interpretation"]["live_proof_required_forward_weeks"]},
            "readiness": {"execution_enabled": False, "live_trading_enabled": False, "missing_real_world_inputs": config["known_missing_real_world_inputs"]},
        }
        strategies.append(result)
        comparison_rows.append({
            "id": strategy["id"], "name": strategy["shortName"], "score": score, "grade": grade,
            "recent_cagr": recent["cagr"], "full_cagr": full["cagr"], "full_drawdown": full["max_drawdown"],
            "worst_rolling_year": rolling["worst_return"], "double_cost_cagr": stresses["double_cost"]["cagr"],
            "signal_decay_cagr": stresses["signal_decay"]["cagr"], "crash_cagr": stresses["one_off_20pct_crash"]["cagr"],
            "monte_profit_probability": primary_monte["probability_of_profit"], "monte_30pct_drawdown_probability": primary_monte["probability_drawdown_over_30pct"],
            "maximum_concentration": maximum_concentration, "forward_weeks": forward_weeks, "live_verdict": live_verdict,
        })

    comparison = sorted(comparison_rows, key=lambda row: (-row["score"], -row["monte_profit_probability"], -row["recent_cagr"]))
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dashboard_sha256": sha256(SOURCE),
        "methodology": {
            "frequency": config["native_frequency"],
            "monte_carlo": config["monte_carlo"],
            "stress_tests": config["stress_tests"],
            "selection_warning": config["selection_warning"],
            "interpretation": "Historical resilience is a diagnostic grade, not a forecast or live-trading authorization.",
        },
        "comparison": comparison,
        "strategies": strategies,
        "leader": comparison[0] if comparison else None,
        "all_strategies_not_proven_live": all(item["live_verdict"] == "not_proven_live" for item in strategies),
        "known_missing_real_world_inputs": config["known_missing_real_world_inputs"],
        "strategy_replacement_authorized": False,
        "execution_enabled": False,
        "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    final.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    PUBLIC_OUTPUT.write_text(json.dumps(result, separators=(",", ":"), sort_keys=True, allow_nan=False))
    pd.DataFrame(comparison).to_csv(OUTPUT / "strategy_comparison.csv", index=False)
    artifact_hashes = {
        "final_result.json": sha256(final),
        "strategy_comparison.csv": sha256(OUTPUT / "strategy_comparison.csv"),
        "dashboard/public/strategy-survival.json": sha256(PUBLIC_OUTPUT),
    }
    manifest = {
        "experiment": config["experiment"], "created_at_utc": result["created_at_utc"],
        "source_dashboard_sha256": result["source_dashboard_sha256"], "artifact_sha256": artifact_hashes,
        "execution_enabled": False, "live_trading_enabled": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "complete", "strategies": len(strategies), "leader": result["leader"], "all_strategies_not_proven_live": result["all_strategies_not_proven_live"], "artifact_sha256": artifact_hashes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
