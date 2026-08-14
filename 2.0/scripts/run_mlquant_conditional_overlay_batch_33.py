#!/usr/bin/env python3
"""Test confidence- and risk-gated allocations to the buffered factor sleeve."""

from __future__ import annotations

import bisect
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
from src.systematic_trader.conditional_overlay import overlay_path
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.factor_ic_protocol import quantile

PROGRAM = ROOT / "config/mlquant_conditional_overlay_program_v1.json"
OUTPUT = ROOT / "evidence/mlquant_conditional_overlay_batch_33"


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
        writer.writeheader(); writer.writerows(rows)


def matching_cost(rows: list[dict[str, object]], cost_bps: float) -> list[dict[str, object]]:
    result = []
    for row in rows:
        gross = round(float(row["gross_return"]), 12)
        turnover = round(float(row["turnover"]), 12)
        result.append({**row, "gross_return": gross, "turnover": turnover, "net_return": gross - turnover * cost_bps / 10_000.0})
    return result


def load_gate_inputs(path: Path):
    rows = read_csv(path)
    dates = sorted({row["date"] for row in rows})
    by_date: dict[str, dict[str, tuple[float, float, float]]] = {day: {} for day in dates}
    spy_close: dict[str, float] = {}
    for row in rows:
        if row["joint_valid"].lower() == "true":
            first, second = float(row["best_002"]), float(row["original_001"])
            by_date[row["date"]][row["ticker"]] = (first, second, (first + second) / 2.0)
        if row["ticker"] == "SPY" and row["adjusted_close"]:
            spy_close[row["date"]] = float(row["adjusted_close"])
    spy_dates = sorted(spy_close)
    spy_stats = {}
    returns = []
    for index, day in enumerate(spy_dates):
        if index:
            returns.append(spy_close[day] / spy_close[spy_dates[index - 1]] - 1.0)
        if index >= 199 and len(returns) >= 20:
            spy_stats[day] = {
                "above_200d_mean": spy_close[day] > statistics.fmean(spy_close[item] for item in spy_dates[index - 199:index + 1]),
                "volatility_20d": statistics.stdev(returns[-20:]),
            }
    return dates, by_date, spy_dates, spy_stats


def gate_history(program, weekly_dates, daily_dates, by_date, spy_dates, spy_stats):
    prior_strength, prior_volatility = [], []
    rows = []
    for index, decision in enumerate(weekly_dates[:-1]):
        signal_decision = weekly_dates[index - 1] if index else None
        source = batch31.asof(signal_decision, daily_dates) if signal_decision else None
        values = by_date[source] if source else {}
        selected = sorted(values, key=lambda asset: (-values[asset][2], asset))[:5]
        strength = statistics.fmean(values[asset][2] for asset in selected) if len(selected) == 5 else None
        agreement = sum(values[asset][0] > 0.0 and values[asset][1] > 0.0 for asset in selected)
        strength_threshold = quantile(prior_strength, 0.60) if len(prior_strength) >= 52 else None
        confidence = strength is not None and strength_threshold is not None and strength > strength_threshold and agreement >= 3
        spy_source = batch31.asof(source, spy_dates) if source else None
        current_volatility = spy_stats.get(spy_source, {}).get("volatility_20d")
        volatility_threshold = quantile(prior_volatility, 0.80) if len(prior_volatility) >= 52 else None
        risk = bool(
            spy_source and spy_stats.get(spy_source, {}).get("above_200d_mean", False)
            and current_volatility is not None and volatility_threshold is not None
            and current_volatility <= volatility_threshold
        )
        rows.append({
            "decision_date": decision, "factor_observation_date": source or "",
            "strength": "" if strength is None else strength,
            "prior_strength_p60": "" if strength_threshold is None else strength_threshold,
            "agreeing_assets": agreement, "confidence_gate": confidence,
            "spy_above_200d_mean": bool(spy_source and spy_stats.get(spy_source, {}).get("above_200d_mean", False)),
            "spy_volatility_20d": "" if current_volatility is None else current_volatility,
            "prior_volatility_p80": "" if volatility_threshold is None else volatility_threshold,
            "risk_gate": risk, "active": confidence and risk,
        })
        if strength is not None:
            prior_strength.append(strength)
        if current_volatility is not None:
            prior_volatility.append(float(current_volatility))
    return rows


def metrics(rows, start="0000-00-00", end="9999-99-99"):
    chosen = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in chosen]).to_dict()
    result["annual_allocation_turnover"] = statistics.fmean(float(row.get("allocation_turnover", 0.0)) for row in chosen) * 52.0
    result["mean_factor_weight"] = statistics.fmean(float(row.get("factor_target_weight", 0.0)) for row in chosen)
    return result


def main() -> None:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    factor_path = ROOT / program["source_candidate"]["factor_panel"]
    periods_path = ROOT / program["source_candidate"]["periods"]
    if sha256(factor_path) != program["source_candidate"]["factor_panel_sha256"] or sha256(periods_path) != program["source_candidate"]["periods_sha256"]:
        raise RuntimeError("conditional-overlay input changed")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frozen = verify_frozen_files()
    core_raw, core_audit = reconstruct_frozen_periods()
    core_audit["maximum_reconstruction_difference"] = round(float(core_audit["maximum_reconstruction_difference"]), 12)
    core_audit["baseline_metrics"] = {name: round(float(value), 12) for name, value in core_audit["baseline_metrics"].items()}
    factor_raw = [{**row} for row in read_csv(periods_path)]
    if [row["realization_date"] for row in core_raw] != [row["realization_date"] for row in factor_raw]:
        raise RuntimeError("core and factor periods do not align")
    weekly_dates = [str(core_raw[0]["decision_date"])] + [str(row["realization_date"]) for row in core_raw]
    daily_dates, by_date, spy_dates, spy_stats = load_gate_inputs(factor_path)
    gate_rows = gate_history(program, weekly_dates, daily_dates, by_date, spy_dates, spy_stats)
    write_csv(OUTPUT / "gate_decisions.csv", gate_rows)
    confidence = [bool(row["confidence_gate"]) for row in gate_rows]
    risk = [bool(row["risk_gate"]) for row in gate_rows]
    active = [left and right for left, right in zip(confidence, risk)]
    shuffled_confidence = list(confidence)
    random.Random(int(program["controls"]["seed"])).shuffle(shuffled_confidence)
    states = {
        "conditional": active,
        "always_on": [True] * len(active),
        "shuffled_confidence": [left and right for left, right in zip(shuffled_confidence, risk)],
        "inverted_risk": [left and not right for left, right in zip(confidence, risk)],
    }
    costs = [float(value) for value in program["costs"]["basis_points"]]
    primary_cost = float(program["costs"]["primary_basis_points"])
    core_by_cost = {cost: matching_cost(core_raw, cost) for cost in costs}
    factor_by_cost = {cost: matching_cost(factor_raw, cost) for cost in costs}
    scoreboard, results = [], []
    for number, (candidate, cap) in enumerate(program["fixed_candidates"].items()):
        runs, audits = {}, {}
        for variant, state in states.items():
            for cost in (costs if variant == "conditional" else [primary_cost]):
                key = f"{variant}_{int(cost)}bps"
                runs[key], audits[key] = overlay_path(
                    core_by_cost[cost], factor_by_cost[cost], state,
                    maximum_factor_weight=float(cap), top_level_cost_bps=cost,
                )
        primary = metrics(runs["conditional_50bps"])
        stress = metrics(runs["conditional_100bps"])
        core50, core100 = metrics(core_by_cost[50.0]), metrics(core_by_cost[100.0])
        validation = metrics(runs["conditional_50bps"], *program["evaluation"]["later_windows"]["validation"])
        test = metrics(runs["conditional_50bps"], *program["evaluation"]["later_windows"]["retrospective_test"])
        core_validation = metrics(core_by_cost[50.0], *program["evaluation"]["later_windows"]["validation"])
        core_test = metrics(core_by_cost[50.0], *program["evaluation"]["later_windows"]["retrospective_test"])
        controls = {name: metrics(runs[f"{name}_50bps"]) for name in ("always_on", "shuffled_confidence", "inverted_risk")}
        paired = batch31.paired_bootstrap(
            [float(row["net_return"]) for row in runs["conditional_50bps"]],
            [float(row["net_return"]) for row in core_by_cost[50.0]],
            seed=int(program["evaluation"]["seed"]) + number,
            samples=int(program["evaluation"]["paired_bootstrap_samples"]),
            block_weeks=int(program["evaluation"]["block_weeks"]),
            alpha=float(program["evaluation"]["per_candidate_one_sided_alpha"]),
        )
        active_share = sum(active) / len(active)
        gates = {
            "primary": primary["annual_return"] > core50["annual_return"] and primary["sharpe_zero_rf"] > core50["sharpe_zero_rf"] and primary["max_drawdown"] >= core50["max_drawdown"],
            "stress": stress["annual_return"] >= core100["annual_return"] and stress["sharpe_zero_rf"] >= core100["sharpe_zero_rf"],
            "later_windows": validation["annual_return"] > core_validation["annual_return"] and test["annual_return"] > core_test["annual_return"],
            "controls": all(primary["sharpe_zero_rf"] > row["sharpe_zero_rf"] for row in controls.values()),
            "uncertainty": paired["pass"],
            "activation": float(program["evaluation"]["minimum_active_week_share"]) <= active_share <= float(program["evaluation"]["maximum_active_week_share"]),
            "accounting": all(audit["return_identity_pass"] for audit in audits.values()),
            "survivorship_safe_universe": False,
            "untouched_forward_52w": False,
        }
        historical = all(value for key, value in gates.items() if key not in {"survivorship_safe_universe", "untouched_forward_52w"})
        results.append({
            "candidate": candidate, "maximum_factor_weight": cap, "active_week_share": active_share,
            "cost_10bps": metrics(runs["conditional_10bps"]), "primary_50bps": primary,
            "stress_100bps": stress, "core_50bps": core50, "core_100bps": core100,
            "validation": validation, "core_validation": core_validation,
            "retrospective_test": test, "core_retrospective_test": core_test,
            "controls_50bps": controls, "paired_vs_core": paired, "accounting": audits,
            "gates": gates, "historical_gates_passed": historical, "promoted": all(gates.values()),
        })
        scoreboard.append({
            "candidate": candidate, "maximum_factor_weight": cap, "active_week_share": active_share,
            "annual_return_50bps": primary["annual_return"], "core_return_50bps": core50["annual_return"],
            "sharpe_50bps": primary["sharpe_zero_rf"], "core_sharpe_50bps": core50["sharpe_zero_rf"],
            "max_drawdown_50bps": primary["max_drawdown"], "core_max_drawdown_50bps": core50["max_drawdown"],
            "annual_return_100bps": stress["annual_return"], "core_return_100bps": core100["annual_return"],
            "paired_lower_sharpe_difference": paired["one_sided_lower_sharpe_difference"],
            "historical_gates_passed": historical, "promoted": all(gates.values()),
        })
        write_csv(OUTPUT / f"{candidate}_primary_periods.csv", runs["conditional_50bps"])
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    result = {
        "program": program["program"], "factor_panel_sha256": sha256(factor_path),
        "factor_periods_sha256": sha256(periods_path), "frozen_files": frozen,
        "core_reconstruction": core_audit,
        "gate_summary": {
            "weeks": len(active), "confidence_weeks": sum(confidence), "risk_weeks": sum(risk),
            "active_weeks": sum(active), "active_week_share": sum(active) / len(active),
        },
        "candidates": results,
        "historical_challengers": [row["candidate"] for row in results if row["historical_gates_passed"]],
        "promoted_candidates": [row["candidate"] for row in results if row["promoted"]],
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    lines = ["# Conditional mlquant factor overlay — Batch 33", "",
        f"The confidence and risk gates were jointly active in {sum(active)} of {len(active)} weeks ({sum(active)/len(active):.1%}).", "",
        "| Candidate | Return | Core return | Sharpe | Core Sharpe | Drawdown | Core drawdown | 100-bps return | Paired lower | Historical gates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in scoreboard:
        lines.append(f"| {row['candidate']} | {float(row['annual_return_50bps']):.2%} | {float(row['core_return_50bps']):.2%} | {float(row['sharpe_50bps']):.3f} | {float(row['core_sharpe_50bps']):.3f} | {float(row['max_drawdown_50bps']):.2%} | {float(row['core_max_drawdown_50bps']):.2%} | {float(row['annual_return_100bps']):.2%} | {float(row['paired_lower_sharpe_difference']):.3f} | {'pass' if row['historical_gates_passed'] else 'fail'} |")
    lines.extend(["", f"Historical challengers: {', '.join(result['historical_challengers']) if result['historical_challengers'] else 'none'}.",
        f"Promoted: {', '.join(result['promoted_candidates']) if result['promoted_candidates'] else 'none'}.", "", "Live trading remains disabled.", ""])
    (OUTPUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    artifacts = ["gate_decisions.csv", "scoreboard.csv", *[f"{name}_primary_periods.csv" for name in program["fixed_candidates"]], "result.json", "report.md"]
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps({name: sha256(OUTPUT / name) for name in artifacts}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
