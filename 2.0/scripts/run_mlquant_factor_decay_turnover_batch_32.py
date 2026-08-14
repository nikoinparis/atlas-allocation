#!/usr/bin/env python3
"""Measure factor decay and test four predeclared low-turnover portfolios."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_mlquant_factor_portfolio_batch_31 as batch31
from scripts.run_monte_carlo_risk_batch_28 import reconstruct_frozen_periods, verify_frozen_files
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.factor_decay_turnover_protocol import buffered_membership, month_end_weekly_dates, ranked_assets
from src.systematic_trader.factor_ic_protocol import circular_block_bootstrap_means, quantile, summarize
from src.systematic_trader.factor_portfolio_protocol import CASH, drift_aware_path, target_weights

PROGRAM = ROOT / "config/mlquant_factor_decay_turnover_program_v1.json"
OUTPUT = ROOT / "evidence/mlquant_factor_decay_turnover_batch_32"
INPUT = ROOT / "evidence/mlquant_factor_portfolio_batch_31/qualified_factor_panel.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + end - 1) / 2.0 + 1.0
        for index in order[start:end]:
            result[index] = rank
        start = end
    return result


def spearman(left: list[float], right: list[float]) -> float | None:
    if len(left) < 5:
        return None
    x, y = average_ranks(left), average_ranks(right)
    mx, my = statistics.fmean(x), statistics.fmean(y)
    covariance = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    return covariance / math.sqrt(vx * vy) if vx > 0.0 and vy > 0.0 else None


def period(day: str, periods: dict[str, list[str]]) -> str | None:
    for name, (start, end) in periods.items():
        if start <= day <= end:
            return name
    return None


def decay_evidence(program, daily_dates, assets, close, scores):
    settings = program["decay_test"]
    daily_rows = []
    grouped: dict[tuple[int, str], list[float]] = {}
    for horizon in settings["forward_sessions"]:
        horizon = int(horizon)
        for index, day in enumerate(daily_dates[:-horizon]):
            later = daily_dates[index + horizon]
            left, right = [], []
            for asset in assets:
                score = scores[day].get(asset)
                start, end = close[day].get(asset), close[later].get(asset)
                if score is not None and start is not None and end is not None:
                    left.append(score)
                    right.append(end / start - 1.0)
            ic = spearman(left, right)
            if ic is not None:
                window = period(day, settings["periods"])
                if window:
                    grouped.setdefault((horizon, window), []).append(ic)
                daily_rows.append({"date": day, "forward_sessions": horizon, "rank_ic": ic, "assets": len(left)})
    development_means = {
        int(horizon): float(summarize(grouped[(int(horizon), "development")])["mean_ic"])
        for horizon in settings["forward_sessions"]
    }
    selected = min(development_means, key=lambda horizon: (-development_means[horizon], horizon))
    summary_rows = []
    for horizon in settings["forward_sessions"]:
        for window in settings["periods"]:
            summary_rows.append({"forward_sessions": horizon, "period": window, **summarize(grouped.get((int(horizon), window), [])), "selected_on_development": int(horizon) == selected})
    combined = grouped[(selected, "validation")] + grouped[(selected, "retrospective_test")]
    bootstrap = circular_block_bootstrap_means(
        combined, block_size=int(settings["bootstrap_block_sessions"]),
        replicates=int(settings["bootstrap_replicates"]), seed=int(settings["seed"]),
    )
    lower = quantile(bootstrap, float(settings["per_horizon_one_sided_alpha"]))
    selected_result = {
        "forward_sessions": selected,
        "development_mean_ic": development_means[selected],
        "validation_mean_ic": statistics.fmean(grouped[(selected, "validation")]),
        "retrospective_test_mean_ic": statistics.fmean(grouped[(selected, "retrospective_test")]),
        "combined_familywise_bootstrap_lower": lower,
    }
    selected_result["qualified"] = (
        selected_result["validation_mean_ic"] > 0.0
        and selected_result["retrospective_test_mean_ic"] > 0.0
        and lower > 0.0
    )
    return daily_rows, summary_rows, selected_result


def permuted_scores(raw, volatility, assets, permutation):
    return {
        asset: raw[permutation[asset]]
        for asset in assets if permutation[asset] in raw and asset in volatility
    }


def portfolio_history(
    weekly_dates, daily_dates, assets, scores, volatility, *, candidate, lag_weeks,
    inverted=False, permutation=None,
):
    monthly = candidate.startswith("monthly_")
    inverse = "inverse_volatility" in candidate
    construction = "inverse_volatility_top5" if inverse else "equal_weight_top5"
    month_ends = month_end_weekly_dates(weekly_dates[:-1])
    history: dict[str, dict[str, float] | None] = {}
    current_members: list[str] = []
    ages: dict[str, int] = {}
    initialized = False
    for index, decision in enumerate(weekly_dates):
        if index < lag_weeks:
            history[decision] = {CASH: 1.0} if not initialized else None
            initialized = True
            continue
        signal_day = batch31.asof(weekly_dates[index - lag_weeks], daily_dates)
        raw = dict(scores[signal_day]) if signal_day else {}
        vol = dict(volatility[signal_day]) if signal_day else {}
        if permutation is not None:
            raw = permuted_scores(raw, vol, assets, permutation)
        if monthly:
            if decision not in month_ends:
                history[decision] = None
                continue
            history[decision] = target_weights(
                raw, vol, candidate=construction, top_n=5, maximum_weight=0.30, inverted=inverted,
            )
            continue
        current_members, ages, changed = buffered_membership(
            current_members, ages, raw, top_n=5, minimum_age=4, entry_buffer=0.5, inverted=inverted,
        )
        refresh = changed or (inverse and decision in month_ends)
        if not refresh:
            history[decision] = None
            continue
        selected_scores = {asset: raw[asset] for asset in current_members if asset in raw}
        history[decision] = target_weights(
            selected_scores, vol, candidate=construction, top_n=5, maximum_weight=0.30,
        )
    return history


def main() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    if sha256(INPUT) != program["input"]["factor_panel_sha256"]:
        raise RuntimeError("qualified factor input changed")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frozen = verify_frozen_files()
    core, core_audit = reconstruct_frozen_periods()
    core = [{**row, "net_return": round(float(row["net_return"]), 12)} for row in core]
    core_audit["maximum_reconstruction_difference"] = round(float(core_audit["maximum_reconstruction_difference"]), 12)
    core_audit["baseline_metrics"] = {name: round(float(value), 12) for name, value in core_audit["baseline_metrics"].items()}
    weekly_dates = [str(core[0]["decision_date"])] + [str(row["realization_date"]) for row in core]
    daily_dates, assets, close, scores, volatility = batch31.load_factor_panel({
        "factors": {"names": program["input"]["factors"], "directions": {name: 1 for name in program["input"]["factors"]}},
        "data": {"assets": json.loads((ROOT / "config/mlquant_factor_portfolio_program_v1.json").read_text())["data"]["assets"]},
    })
    decay_daily, decay_summary, selected_horizon = decay_evidence(program, daily_dates, assets, close, scores)
    write_csv(OUTPUT / "daily_decay_ic.csv", decay_daily)
    write_csv(OUTPUT / "decay_summary.csv", decay_summary)
    weekly_returns = batch31.weekly_returns(weekly_dates, daily_dates, assets, close)
    randomizer = random.Random(int(program["controls"]["permutation_seed"]))
    shuffled = list(assets); randomizer.shuffle(shuffled)
    permutation = dict(zip(assets, shuffled))
    primary_cost = float(program["portfolio"]["primary_cost_bps"])
    costs = [float(value) for value in program["portfolio"]["costs_bps"]]
    results, scoreboard = [], []
    baseline_turnover = {"equal": 23.185865880092425, "inverse": 26.99271763536152}
    for number, candidate in enumerate(program["fixed_candidates"]):
        histories = {
            "primary": portfolio_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1),
            "stale": portfolio_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=2),
            "inverted": portfolio_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1, inverted=True),
            "permutation": portfolio_history(weekly_dates, daily_dates, assets, scores, volatility, candidate=candidate, lag_weeks=1, permutation=permutation),
        }
        runs, audits = {}, {}
        for variant, weights in histories.items():
            for cost in (costs if variant == "primary" else [primary_cost]):
                key = f"{variant}_{int(cost)}bps"
                runs[key], audits[key] = drift_aware_path(weekly_dates, weights, weekly_returns, cost_bps=cost)
        primary = runs["primary_50bps"]
        primary_metrics = batch31.metrics(primary)
        stress = batch31.metrics(runs["primary_100bps"])
        validation = batch31.metrics(primary, "2016-01-01", "2020-12-31")
        test = batch31.metrics(primary, "2021-01-01", "2026-08-07")
        controls = {name: batch31.metrics(runs[f"{name}_50bps"]) for name in ("stale", "inverted", "permutation")}
        blended = batch31.blend(core, primary, 50.0)
        blend_metrics = batch31.metrics(blended)
        core_metrics = batch31.metrics(core)
        paired = batch31.paired_bootstrap(
            [float(row["net_return"]) for row in blended], [float(row["net_return"]) for row in core],
            seed=int(program["comparison"]["seed"]) + number,
            samples=int(program["comparison"]["paired_bootstrap_samples"]),
            block_weeks=int(program["comparison"]["paired_bootstrap_block_weeks"]),
            alpha=float(program["comparison"]["per_candidate_one_sided_alpha"]),
        )
        family = "inverse" if "inverse" in candidate else "equal"
        gates = {
            "primary": primary_metrics["annual_return"] > 0.0 and primary_metrics["sharpe_zero_rf"] >= 0.5 and primary_metrics["max_drawdown"] >= -0.35,
            "stress": stress["annual_return"] > 0.0 and stress["sharpe_zero_rf"] > 0.0,
            "later_windows": validation["annual_return"] > 0.0 and test["annual_return"] > 0.0,
            "controls": all(primary_metrics["sharpe_zero_rf"] > row["sharpe_zero_rf"] for row in controls.values()),
            "turnover_improvement": primary_metrics["annual_turnover"] < baseline_turnover[family],
            "blend_point": blend_metrics["sharpe_zero_rf"] > core_metrics["sharpe_zero_rf"] and blend_metrics["max_drawdown"] >= core_metrics["max_drawdown"] - 0.02,
            "blend_familywise": paired["pass"],
            "accounting": all(a["unpriced_exposure_pass"] and a["fully_invested_including_cash_pass"] and a["cost_identity_pass"] for a in audits.values()),
            "survivorship_safe_universe": False,
            "untouched_forward_52w": False,
        }
        historical = all(value for key, value in gates.items() if key not in {"survivorship_safe_universe", "untouched_forward_52w"})
        result = {
            "candidate": candidate, "cost_10bps": batch31.metrics(runs["primary_10bps"]),
            "primary_50bps": primary_metrics, "stress_100bps": stress,
            "validation_2016_2020": validation, "retrospective_test_2021_present": test,
            "controls_50bps": controls, "blend_80_20": blend_metrics, "core_common": core_metrics,
            "paired_blend": paired, "accounting": audits, "gates": gates,
            "historical_gates_passed": historical, "promoted": all(gates.values()),
        }
        results.append(result)
        scoreboard.append({
            "candidate": candidate, "annual_return_10bps": result["cost_10bps"]["annual_return"],
            "annual_return_50bps": primary_metrics["annual_return"], "sharpe_50bps": primary_metrics["sharpe_zero_rf"],
            "max_drawdown_50bps": primary_metrics["max_drawdown"], "annual_turnover": primary_metrics["annual_turnover"],
            "annual_return_100bps": stress["annual_return"], "validation_return": validation["annual_return"],
            "test_return": test["annual_return"], "blend_sharpe": blend_metrics["sharpe_zero_rf"],
            "core_sharpe": core_metrics["sharpe_zero_rf"], "paired_lower": paired["one_sided_lower_sharpe_difference"],
            "historical_gates_passed": historical, "promoted": all(gates.values()),
        })
        write_csv(OUTPUT / f"{candidate}_primary_periods.csv", primary)
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    final = {
        "program": program["program"], "input_sha256": sha256(INPUT), "frozen_files": frozen,
        "core_reconstruction": core_audit, "selected_decay_horizon": selected_horizon,
        "asset_permutation": permutation, "candidates": results,
        "historical_challengers": [row["candidate"] for row in results if row["historical_gates_passed"]],
        "promoted_candidates": [row["candidate"] for row in results if row["promoted"]],
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(final, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Factor decay and turnover controls — Batch 32", "",
        f"Development selected a {selected_horizon['forward_sessions']}-session IC horizon. Validation IC was {selected_horizon['validation_mean_ic']:.4f}, test IC {selected_horizon['retrospective_test_mean_ic']:.4f}, and the familywise lower bound {selected_horizon['combined_familywise_bootstrap_lower']:.4f}.", "",
        "| Candidate | Return 10 bps | Return 50 bps | Sharpe | Drawdown | Turnover/year | Return 100 bps | Blend Sharpe | Core Sharpe | Historical gates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in scoreboard:
        lines.append(f"| {row['candidate']} | {float(row['annual_return_10bps']):.2%} | {float(row['annual_return_50bps']):.2%} | {float(row['sharpe_50bps']):.3f} | {float(row['max_drawdown_50bps']):.2%} | {float(row['annual_turnover']):.2f} | {float(row['annual_return_100bps']):.2%} | {float(row['blend_sharpe']):.3f} | {float(row['core_sharpe']):.3f} | {'pass' if row['historical_gates_passed'] else 'fail'} |")
    lines.extend(["", f"Historical challengers: {', '.join(final['historical_challengers']) if final['historical_challengers'] else 'none'}.",
        f"Promoted: {', '.join(final['promoted_candidates']) if final['promoted_candidates'] else 'none'}.", "", "Live trading remains disabled.", ""])
    (OUTPUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    artifacts = ["daily_decay_ic.csv", "decay_summary.csv", "scoreboard.csv", *[f"{name}_primary_periods.csv" for name in program["fixed_candidates"]], "result.json", "report.md"]
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps({name: sha256(OUTPUT / name) for name in artifacts}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
