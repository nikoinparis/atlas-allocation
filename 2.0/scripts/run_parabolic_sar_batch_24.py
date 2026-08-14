#!/usr/bin/env python3
"""Run fixed, causal repository Parabolic SAR candidates and controls."""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_heikin_ashi_batch_23 as batch23
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.oscillator_protocol import capped_equal_weights, long_only_turnover
from src.systematic_trader.parabolic_sar_protocol import repository_parabolic_sar
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/parabolic_sar_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_24/source_rule_review.json"
OUTPUT = ROOT / "evidence/parabolic_sar_batch_24"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
CANDIDATES = ("source_default", "source_equity_step")
CONTROL_SUFFIXES = ("stale_1d", "stale_5d", "inverted", "asset_permuted")
VARIANTS = tuple(name for candidate in CANDIDATES for name in (candidate, *(f"{candidate}_{suffix}" for suffix in CONTROL_SUFFIXES)))
COSTS = (10.0, 50.0, 100.0)
PRIMARY_COST = 50.0


def candidate_parameters(program: dict[str, object], candidate: str) -> dict[str, float]:
    row = program["fixed_candidates"][candidate]
    return {"initial_af": float(row["initial_af"]), "step_af": float(row["step_af"]), "maximum_af": float(row["maximum_af"])}


def build_positions(
    bars: dict[str, list[dict[str, float | str]]], assets: list[str], program: dict[str, object],
) -> tuple[dict[str, dict[str, bool]], list[dict[str, object]], dict[str, str]]:
    panels = {name: {} for name in VARIANTS if not name.endswith("asset_permuted")}
    audit = []
    for asset, rows in bars.items():
        inputs = [{key: float(row[key]) for key in ("high", "low", "close")} for row in rows]
        for candidate in CANDIDATES:
            states = repository_parabolic_sar(inputs, **candidate_parameters(program, candidate))
            for index in range(1, len(rows)):
                key = f"{rows[index]['date']}|{asset}"
                position = bool(states[index]["long"])
                panels[candidate][key] = position
                panels[f"{candidate}_inverted"][key] = not position
                for lag in (1, 5):
                    if index - lag >= 1:
                        panels[f"{candidate}_stale_{lag}d"][key] = bool(states[index - lag]["long"])
                audit.append({
                    "decision_date": rows[index]["date"], "asset": asset, "candidate": candidate,
                    "long": int(position), "trend": states[index]["trend"], "sar": states[index]["sar"],
                    "real_sar": states[index]["real_sar"], "extreme_point": states[index]["ep"],
                    "acceleration_factor": states[index]["af"], "adjusted_close": rows[index]["close"],
                })
    donors = list(assets)
    random.Random(20260824).shuffle(donors)
    permutation = dict(zip(assets, donors))
    all_dates = sorted({key.split("|", 1)[0] for key in panels[CANDIDATES[0]]})
    for candidate in CANDIDATES:
        target = panels[f"{candidate}_asset_permuted"] = {}
        source = panels[candidate]
        for day in all_dates:
            for asset, donor in permutation.items():
                donor_key = f"{day}|{donor}"
                if donor_key in source:
                    target[f"{day}|{asset}"] = source[donor_key]
    return panels, audit, permutation


def simulate_daily(
    variant: str, cost_bps: float, bars: dict[str, list[dict[str, float | str]]],
    panels: dict[str, dict[str, bool]], assets: list[str],
) -> list[dict[str, object]]:
    price = {f"{row['date']}|{asset}": float(row["close"]) for asset, rows in bars.items() for row in rows}
    dates = sorted({str(row["date"]) for rows in bars.values() for row in rows})
    previous = capped_equal_weights([], assets)
    periods = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        eligible = [
            asset for asset in assets
            if f"{decision}|{asset}" in panels[variant]
            and f"{decision}|{asset}" in price
            and f"{realization}|{asset}" in price
        ]
        if not eligible:
            continue
        active = [asset for asset in eligible if panels[variant][f"{decision}|{asset}"]]
        target = capped_equal_weights(active, assets)
        turnover = long_only_turnover(previous, target)
        asset_returns = {asset: price[f"{realization}|{asset}"] / price[f"{decision}|{asset}"] - 1.0 for asset in eligible}
        gross = sum(target[asset] * asset_returns[asset] for asset in eligible)
        periods.append({
            "variant": variant, "decision_date": decision, "realization_date": realization,
            "cost_bps": cost_bps, "active_assets": len(active), "invested_weight": 1.0 - target["cash::USD"],
            "turnover": turnover, "gross_return": gross, "cost": turnover * cost_bps / 10_000.0,
            "net_return": gross - turnover * cost_bps / 10_000.0,
        })
        previous = {asset: target[asset] * (1.0 + asset_returns.get(asset, 0.0)) / (1.0 + gross) for asset in assets}
        previous["cash::USD"] = target["cash::USD"] / (1.0 + gross)
    return periods


def update_inventory() -> None:
    rows = batch23.read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "8":
            row.update(status="tested_batch_24", reason="Default and equity acceleration variants tested causally with costs controls and blends", next_action="Follow Batch 24 gate decision")
    batch23.write_csv(INVENTORY, rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot = str(program["data"]["snapshot_id"])
    assets = list(program["data"]["assets"])
    bars, data_audit = batch23.load_bars(ROOT / f"data/vintages/{snapshot}/payload/prices.csv", assets, str(program["data"]["start_date"]))
    panels, signal_audit, permutation = build_positions(bars, assets, program)
    core = batch23.core_periods()
    trend = batch23.trend_periods(PRIMARY_COST)
    weekly_tables = {}
    primary_daily = {}
    scoreboard = []
    for variant in VARIANTS:
        for cost in COSTS:
            daily = simulate_daily(variant, cost, bars, panels, assets)
            weekly = batch23.aggregate_weekly(daily, core)
            weekly_tables[(variant, cost)] = weekly
            if variant in CANDIDATES and cost == PRIMARY_COST:
                primary_daily[variant] = daily
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in batch23.metrics(weekly).items()},
                **{f"oos_2016_2020_{key}": value for key, value in batch23.metrics(weekly, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in batch23.metrics(weekly, "2021-01-01").items()},
            })
    core_metrics = performance_metrics([float(row["net_return"]) for row in core]).to_dict()
    evaluations, blends = {}, {}
    for number, candidate in enumerate(CANDIDATES):
        primary = next(row for row in scoreboard if row["variant"] == candidate and row["cost_bps"] == PRIMARY_COST)
        stress = next(row for row in scoreboard if row["variant"] == candidate and row["cost_bps"] == 100.0)
        controls = [next(row for row in scoreboard if row["variant"] == f"{candidate}_{suffix}" and row["cost_bps"] == PRIMARY_COST) for suffix in CONTROL_SUFFIXES]
        weekly = weekly_tables[(candidate, PRIMARY_COST)]
        candidate_core, common_core = batch23.aligned(weekly, core)
        candidate_trend, common_trend = batch23.aligned(weekly, trend)
        blend_rows = batch23.blend(core, weekly, PRIMARY_COST)
        blend_values, blend_core = batch23.aligned(blend_rows, core)
        blend_metrics = performance_metrics(blend_values).to_dict()
        paired = batch23.paired_bootstrap(blend_values, blend_core, 20260825 + number, alpha=0.025)
        gates = {
            "primary_performance": float(primary["full_annual_return"]) > 0.0 and float(primary["full_sharpe_zero_rf"]) > 0.5 and float(primary["full_max_drawdown"]) >= -0.25,
            "stress": float(stress["full_annual_return"]) > 0.0 and float(stress["oos_2016_2020_annual_return"]) > 0.0 and float(stress["oos_2021_present_annual_return"]) > 0.0,
            "controls": float(primary["full_sharpe_zero_rf"]) > max(float(row["full_sharpe_zero_rf"]) for row in controls),
            "dependence_core": abs(correlation(candidate_core, common_core)) <= 0.80,
            "dependence_trend": abs(correlation(candidate_trend, common_trend)) <= 0.80,
            "blend_point": float(blend_metrics["sharpe_zero_rf"]) > float(core_metrics["sharpe_zero_rf"]) and float(blend_metrics["max_drawdown"]) >= float(core_metrics["max_drawdown"]),
            "blend_familywise_paired": bool(paired["pass"]),
            "survivorship_safe": False, "untouched_forward_52w": False,
        }
        gates["all"] = all(gates.values())
        evaluations[candidate] = {
            "primary_50bps": primary, "stress_100bps": stress,
            "correlation_to_core": correlation(candidate_core, common_core),
            "correlation_to_trend": correlation(candidate_trend, common_trend),
            "blend_metrics": blend_metrics, "paired_blend": paired, "gates": gates,
        }
        blends[candidate] = blend_rows
    OUTPUT.mkdir(parents=True, exist_ok=True)
    batch23.write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    batch23.write_csv(OUTPUT / "signal_audit.csv", signal_audit)
    for candidate in CANDIDATES:
        batch23.write_csv(OUTPUT / f"{candidate}_daily_50bps.csv", primary_daily[candidate])
        batch23.write_csv(OUTPUT / f"{candidate}_weekly_50bps.csv", weekly_tables[(candidate, PRIMARY_COST)])
        batch23.write_csv(OUTPUT / f"{candidate}_blend_50bps.csv", blends[candidate])
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 24,
        "track": "quant_trading_repository_parabolic_sar", "program_sha256": sha256(PROGRAM),
        "source_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "core_evidence_sha256": sha256(batch23.CORE_EVIDENCE), "trend_evidence_sha256": sha256(batch23.TREND_EVIDENCE),
        "data_audit": data_audit, "asset_permutation_control": permutation,
        "core_common_metrics_50bps": core_metrics, "candidate_evaluations": evaluations,
        "promoted": any(bool(evaluations[name]["gates"]["all"]) for name in CANDIDATES),
        "live_trading_approved": False,
        "limitations": [
            "The current free ETF list is survivorship-prone and not historical membership data.",
            "Adjusted daily OHLC cannot reproduce intraday stop crossing order or executable spread.",
            "The equity 0.01 interpretation resolves an ambiguous source comment and is not claimed as uniquely canonical.",
            "The repository recursion is preserved even where its initialization differs from standard descriptions.",
            "The snapshot can contain vendor revisions made before acquisition; all results are retrospective."
        ],
    }
    report = ["# Repository Parabolic SAR — Batch 24", ""]
    for candidate in CANDIDATES:
        item = evaluations[candidate]
        row, stress = item["primary_50bps"], item["stress_100bps"]
        report.extend([
            f"## {candidate.replace('_', ' ').title()}", "",
            f"At 50 bps: **{float(row['full_annual_return']) * 100:.2f}%** annual return, **{float(row['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(row['full_max_drawdown']) * 100:.2f}%** drawdown, and **{float(row['full_annual_turnover']):.2f}** annual turnover.", "",
            f"At 100 bps: **{float(stress['full_annual_return']) * 100:.2f}%**. Core/trend correlations: **{item['correlation_to_core']:.3f}/{item['correlation_to_trend']:.3f}**. Blend Sharpe: **{float(item['blend_metrics']['sharpe_zero_rf']):.3f}** versus core **{float(core_metrics['sharpe_zero_rf']):.3f}**. Promotion: **{item['gates']['all']}**.", "",
        ])
    report.extend(["Both acceleration variants and all controls were fixed before results. No source code execution, tuning, paid data, or live trading was used.", ""])
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps(evaluations, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
