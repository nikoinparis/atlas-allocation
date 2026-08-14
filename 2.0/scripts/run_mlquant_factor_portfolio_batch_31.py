#!/usr/bin/env python3
"""Run the predeclared weekly portfolio test for two qualified mlquant factors."""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import random
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_monte_carlo_risk_batch_28 import reconstruct_frozen_periods, verify_frozen_files
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.factor_portfolio_protocol import CASH, drift_aware_path, target_weights

PROGRAM = ROOT / "config/mlquant_factor_portfolio_program_v1.json"
OUTPUT = ROOT / "evidence/mlquant_factor_portfolio_batch_31"
IMAGE = "localhost/po2-mlquant-batch29:latest"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_inputs() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ("qualified_factor_panel.csv", "input_metadata.json"):
        path = OUTPUT / name
        if path.exists():
            path.unlink()
    subprocess.run([
        "podman", "run", "--rm", "-v", f"{ROOT}:/project:ro", "-v", f"{OUTPUT}:/output:rw",
        IMAGE, "python", "/project/scripts/export_mlquant_portfolio_inputs_batch_31.py",
        "--program", "/project/config/mlquant_factor_portfolio_program_v1.json", "--output", "/output",
    ], check=True, cwd=ROOT)


def load_factor_panel(program: dict[str, object]):
    rows = read_csv(OUTPUT / "qualified_factor_panel.csv")
    factors = list(program["factors"]["names"])
    dates = sorted({row["date"] for row in rows})
    assets = list(program["data"]["assets"])
    close: dict[str, dict[str, float | None]] = {day: {} for day in dates}
    scores: dict[str, dict[str, float]] = {day: {} for day in dates}
    for row in rows:
        day, asset = row["date"], row["ticker"]
        close[day][asset] = float(row["adjusted_close"]) if row["adjusted_close"] else None
        if row["joint_valid"].lower() == "true":
            values = [float(row[name]) * float(program["factors"]["directions"][name]) for name in factors]
            if all(math.isfinite(value) for value in values):
                scores[day][asset] = statistics.fmean(values)
    volatility: dict[str, dict[str, float]] = {day: {} for day in dates}
    histories: dict[str, list[float]] = {asset: [] for asset in assets}
    previous: dict[str, float | None] = {asset: None for asset in assets}
    for day in dates:
        for asset in assets:
            price = close[day].get(asset)
            if price is not None and previous[asset] is not None:
                histories[asset].append(price / float(previous[asset]) - 1.0)
            if price is not None:
                previous[asset] = price
            recent = histories[asset][-20:]
            if len(recent) == 20 and statistics.stdev(recent) > 0.0:
                volatility[day][asset] = statistics.stdev(recent)
    return dates, assets, close, scores, volatility


def asof(day: str, dates: list[str]) -> str | None:
    index = bisect.bisect_right(dates, day) - 1
    return dates[index] if index >= 0 else None


def weekly_returns(weekly_dates: list[str], daily_dates: list[str], assets: list[str], close):
    asset_dates = {
        asset: [day for day in daily_dates if close[day].get(asset) is not None]
        for asset in assets
    }
    prices: dict[str, dict[str, float | None]] = {}
    for day in weekly_dates:
        prices[day] = {}
        for asset in assets:
            source = asof(day, asset_dates[asset])
            prices[day][asset] = close[source][asset] if source else None
    result: dict[str, dict[str, float | None]] = {}
    for index, day in enumerate(weekly_dates):
        result[day] = {}
        if index == 0:
            result[day] = {asset: None for asset in assets}
            continue
        previous = weekly_dates[index - 1]
        for asset in assets:
            left, right = prices[previous][asset], prices[day][asset]
            result[day][asset] = right / left - 1.0 if left and right else None
    return result


def weight_history(
    weekly_dates, daily_dates, assets, scores, volatility, *, candidate, lag_weeks,
    inverted=False, permutation=None,
):
    history = {}
    for index, decision in enumerate(weekly_dates):
        if index < lag_weeks:
            history[decision] = {CASH: 1.0}
            continue
        signal_decision = weekly_dates[index - lag_weeks]
        source = asof(signal_decision, daily_dates)
        raw_scores = dict(scores[source]) if source else {}
        raw_volatility = dict(volatility[source]) if source else {}
        if permutation is not None:
            raw_scores = {
                asset: raw_scores[permutation[asset]]
                for asset in assets
                if permutation[asset] in raw_scores and asset in raw_volatility
            }
        history[decision] = target_weights(
            raw_scores, raw_volatility, candidate=candidate, top_n=5,
            maximum_weight=0.30, inverted=inverted,
        )
    return history


def metrics(rows, start="0000-00-00", end="9999-99-99"):
    chosen = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in chosen]).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in chosen) * 52.0
    result["mean_invested_weight"] = statistics.fmean(float(row.get("invested_weight", 1.0)) for row in chosen)
    return result


def blend(core, candidate, cost_bps):
    candidates = {str(row["realization_date"]): row for row in candidate}
    result = []
    prior_candidate_weight = 0.0
    for row in core:
        day = str(row["realization_date"])
        if day not in candidates:
            continue
        core_return = float(row["net_return"])
        candidate_return = float(candidates[day]["net_return"])
        gross = 0.8 * core_return + 0.2 * candidate_return
        turnover = abs(0.2 - prior_candidate_weight)
        net = gross - turnover * cost_bps / 10_000.0
        prior_candidate_weight = 0.2 * (1.0 + candidate_return) / (1.0 + gross)
        result.append({
            "decision_date": row["decision_date"], "realization_date": day,
            "net_return": net, "turnover": turnover, "invested_weight": 1.0,
        })
    return result


def paired_bootstrap(left, right, *, seed, samples, block_weeks, alpha):
    if len(left) != len(right) or not left:
        raise ValueError("paired observations required")
    generator = random.Random(seed)
    length = len(left)
    differences = []
    for _ in range(samples):
        indexes = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(block_weeks))
        indexes = indexes[:length]
        sharpes = []
        for panel in (left, right):
            sample = [panel[index] for index in indexes]
            deviation = statistics.stdev(sample)
            sharpes.append(statistics.fmean(sample) / deviation * math.sqrt(52.0) if deviation else 0.0)
        differences.append(sharpes[0] - sharpes[1])
    ordered = sorted(differences)
    lower = ordered[math.floor(alpha * (samples - 1))]
    return {
        "observations": length, "samples": samples, "block_weeks": block_weeks,
        "one_sided_alpha": alpha, "mean_sharpe_difference": statistics.fmean(differences),
        "one_sided_lower_sharpe_difference": lower, "pass": lower > 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-input", action="store_true")
    args = parser.parse_args()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    if not args.reuse_input:
        export_inputs()
    frozen_audit = verify_frozen_files()
    core_periods, core_audit = reconstruct_frozen_periods()
    core_periods = [
        {**row, "net_return": round(float(row["net_return"]), 12)}
        for row in core_periods
    ]
    core_audit["maximum_reconstruction_difference"] = round(
        float(core_audit["maximum_reconstruction_difference"]), 12
    )
    core_audit["baseline_metrics"] = {
        name: round(float(value), 12)
        for name, value in core_audit["baseline_metrics"].items()
    }
    weekly_dates = [str(core_periods[0]["decision_date"])] + [str(row["realization_date"]) for row in core_periods]
    daily_dates, assets, close, scores, volatility = load_factor_panel(program)
    returns = weekly_returns(weekly_dates, daily_dates, assets, close)
    randomizer = random.Random(int(program["controls"]["permutation_seed"]))
    shuffled = list(assets)
    randomizer.shuffle(shuffled)
    permutation = dict(zip(assets, shuffled))
    candidates = list(program["fixed_candidates"])
    costs = [float(value) for value in program["execution"]["costs_bps"]]
    primary_cost = float(program["execution"]["primary_cost_bps"])
    comparison = program["comparison"]
    scorecard = []
    result_candidates = []
    period_outputs = {}
    for candidate_number, candidate in enumerate(candidates):
        variant_weights = {
            "primary": weight_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1),
            "stale_1": weight_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=2),
            "stale_5": weight_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=6),
            "inverted": weight_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1, inverted=True),
            "asset_permutation": weight_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1, permutation=permutation),
        }
        runs = {}
        audits = {}
        for variant, weights in variant_weights.items():
            for cost in (costs if variant == "primary" else [primary_cost]):
                key = f"{variant}_{int(cost)}bps"
                runs[key], audits[key] = drift_aware_path(weekly_dates, weights, returns, cost_bps=cost)
        primary = runs[f"primary_{int(primary_cost)}bps"]
        primary_metrics = metrics(primary)
        stress_metrics = metrics(runs["primary_100bps"])
        validation_metrics = metrics(primary, *comparison["later_windows"]["validation"])
        test_metrics = metrics(primary, *comparison["later_windows"]["retrospective_test"])
        controls = {name: metrics(runs[f"{name}_{int(primary_cost)}bps"]) for name in ("stale_1", "stale_5", "inverted", "asset_permutation")}
        blended = blend(core_periods, primary, float(comparison["top_level_rebalance_cost_bps"]))
        blend_metrics = metrics(blended)
        core_common = metrics(core_periods)
        blend_values = [float(row["net_return"]) for row in blended]
        core_values = [float(row["net_return"]) for row in core_periods]
        paired = paired_bootstrap(
            blend_values, core_values, seed=2026083102 + candidate_number,
            samples=int(comparison["paired_bootstrap_samples"]),
            block_weeks=int(comparison["paired_bootstrap_block_weeks"]),
            alpha=float(comparison["per_candidate_one_sided_alpha"]),
        )
        gates = {
            "primary_performance": primary_metrics["annual_return"] > 0.0 and primary_metrics["sharpe_zero_rf"] >= 0.5 and primary_metrics["max_drawdown"] >= -0.35,
            "stress": stress_metrics["annual_return"] > 0.0 and stress_metrics["sharpe_zero_rf"] > 0.0,
            "later_windows": validation_metrics["annual_return"] > 0.0 and test_metrics["annual_return"] > 0.0,
            "controls": all(primary_metrics["sharpe_zero_rf"] > row["sharpe_zero_rf"] for row in controls.values()),
            "blend_point_estimate": blend_metrics["sharpe_zero_rf"] > core_common["sharpe_zero_rf"] and blend_metrics["max_drawdown"] >= core_common["max_drawdown"] - 0.02,
            "blend_familywise_paired": paired["pass"],
            "survivorship_safe_universe": False,
            "untouched_forward_52w": False,
            "accounting": all(audit["unpriced_exposure_pass"] and audit["fully_invested_including_cash_pass"] and audit["cost_identity_pass"] for audit in audits.values()),
        }
        historical_gates = all(value for key, value in gates.items() if key not in {"survivorship_safe_universe", "untouched_forward_52w"})
        promoted = all(gates.values())
        result_candidates.append({
            "candidate": candidate, "primary_50bps": primary_metrics,
            "cost_10bps": metrics(runs["primary_10bps"]), "stress_100bps": stress_metrics,
            "validation_2016_2020": validation_metrics, "retrospective_test_2021_present": test_metrics,
            "controls_50bps": controls, "core_common_50bps": core_common,
            "blend_80_20_50bps": blend_metrics, "paired_blend": paired,
            "accounting": audits, "gates": gates,
            "historical_gates_passed": historical_gates, "promoted": promoted,
        })
        scorecard.append({
            "candidate": candidate, "annual_return_50bps": primary_metrics["annual_return"],
            "sharpe_50bps": primary_metrics["sharpe_zero_rf"], "max_drawdown_50bps": primary_metrics["max_drawdown"],
            "annual_turnover": primary_metrics["annual_turnover"], "annual_return_100bps": stress_metrics["annual_return"],
            "validation_return": validation_metrics["annual_return"], "test_return": test_metrics["annual_return"],
            "blend_sharpe": blend_metrics["sharpe_zero_rf"], "core_sharpe": core_common["sharpe_zero_rf"],
            "paired_lower_sharpe_difference": paired["one_sided_lower_sharpe_difference"],
            "historical_gates_passed": historical_gates, "promoted": promoted,
        })
        period_outputs[candidate] = primary
    write_csv(OUTPUT / "scoreboard.csv", scorecard)
    for name, rows in period_outputs.items():
        write_csv(OUTPUT / f"{name}_primary_periods.csv", rows)
    metadata = json.loads((OUTPUT / "input_metadata.json").read_text(encoding="utf-8"))
    result = {
        "program": program["program"], "repository_commit": program["repository"]["commit"],
        "source_snapshot_id": program["data"]["snapshot_id"], "input_metadata": metadata,
        "frozen_files": frozen_audit, "core_reconstruction": core_audit,
        "asset_permutation": permutation, "candidates": result_candidates,
        "historical_challengers": [row["candidate"] for row in result_candidates if row["historical_gates_passed"]],
        "promoted_candidates": [row["candidate"] for row in result_candidates if row["promoted"]],
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = [
        "# Qualified mlquant factor portfolios — Batch 31", "",
        "Two constructions were fixed before returns were viewed. Signals are observed at a completed weekly close, entered at the following weekly close, and earn returns only after entry.", "",
        "| Candidate | Return (50 bps) | Sharpe | Drawdown | Turnover/year | Return (100 bps) | 80/20 blend Sharpe | Core Sharpe | Historical gates |", "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in scorecard:
        lines.append(
            f"| {row['candidate']} | {float(row['annual_return_50bps']):.2%} | {float(row['sharpe_50bps']):.3f} | {float(row['max_drawdown_50bps']):.2%} | "
            f"{float(row['annual_turnover']):.2f} | {float(row['annual_return_100bps']):.2%} | {float(row['blend_sharpe']):.3f} | {float(row['core_sharpe']):.3f} | {'pass' if row['historical_gates_passed'] else 'fail'} |"
        )
    lines.extend([
        "", f"Historical challengers: {', '.join(result['historical_challengers']) if result['historical_challengers'] else 'none'}.",
        f"Promoted candidates: {', '.join(result['promoted_candidates']) if result['promoted_candidates'] else 'none'}.", "",
        "Even a historical-gate pass remains research-only because the ETF universe is a survivor list and no new untouched 52-week record exists. Live trading remains disabled.", "",
    ])
    (OUTPUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    artifacts = ["qualified_factor_panel.csv", "input_metadata.json", "scoreboard.csv", "equal_weight_top5_primary_periods.csv", "inverse_volatility_top5_primary_periods.csv", "result.json", "report.md"]
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps({name: sha256(OUTPUT / name) for name in artifacts}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
