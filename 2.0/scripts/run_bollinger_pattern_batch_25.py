#!/usr/bin/env python3
"""Test literal and scale-normalized repository Bollinger bottom-W rules."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_heikin_ashi_batch_23 as batch23
from scripts import run_parabolic_sar_batch_24 as batch24
from src.systematic_trader.bollinger_pattern_protocol import bottom_w_positions
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/bollinger_pattern_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_25/source_rule_review.json"
OUTPUT = ROOT / "evidence/bollinger_pattern_batch_25"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
CANDIDATES = ("source_literal_fx_units", "scale_normalized")
CONTROL_SUFFIXES = ("stale_1d", "stale_5d", "inverted", "asset_permuted")
VARIANTS = tuple(name for candidate in CANDIDATES for name in (candidate, *(f"{candidate}_{suffix}" for suffix in CONTROL_SUFFIXES)))
COSTS = (10.0, 50.0, 100.0)
PRIMARY_COST = 50.0


def build_positions(
    bars: dict[str, list[dict[str, float | str]]], assets: list[str], program: dict[str, object],
) -> tuple[dict[str, dict[str, bool]], list[dict[str, object]], dict[str, str]]:
    panels = {name: {} for name in VARIANTS if not name.endswith("asset_permuted")}
    audit = []
    for asset, rows in bars.items():
        prices = [float(row["close"]) for row in rows]
        for candidate in CANDIDATES:
            rule = program["fixed_candidates"][candidate]
            positions, events, coordinates = bottom_w_positions(
                prices, period=int(program["fixed_indicator"]["pattern_lookback_days"]),
                alpha=float(rule["alpha"]), beta=float(rule["beta"]),
                normalized=candidate == "scale_normalized",
            )
            for index in range(75, len(rows)):
                key = f"{rows[index]['date']}|{asset}"
                panels[candidate][key] = positions[index]
                panels[f"{candidate}_inverted"][key] = not positions[index]
                for lag in (1, 5):
                    if index - lag >= 75:
                        panels[f"{candidate}_stale_{lag}d"][key] = positions[index - lag]
                audit.append({
                    "decision_date": rows[index]["date"], "asset": asset, "candidate": candidate,
                    "long": int(positions[index]), "event": events[index],
                    "coordinates": "" if coordinates[index] is None else ",".join(map(str, coordinates[index])),
                    "adjusted_close": prices[index],
                })
    donors = list(assets)
    random.Random(20260825).shuffle(donors)
    permutation = dict(zip(assets, donors))
    dates = sorted({key.split("|", 1)[0] for key in panels[CANDIDATES[0]]})
    for candidate in CANDIDATES:
        target = panels[f"{candidate}_asset_permuted"] = {}
        source = panels[candidate]
        for day in dates:
            for asset, donor in permutation.items():
                donor_key = f"{day}|{donor}"
                if donor_key in source:
                    target[f"{day}|{asset}"] = source[donor_key]
    return panels, audit, permutation


def update_inventory() -> None:
    rows = batch23.read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "9":
            row.update(status="tested_batch_25", reason="Literal FX-unit and dimensionless bottom-W rules tested causally with coverage costs controls and blends", next_action="Follow Batch 25 gate decision")
    batch23.write_csv(INVENTORY, rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot = str(program["data"]["snapshot_id"])
    assets = list(program["data"]["assets"])
    bars, data_audit = batch23.load_bars(ROOT / f"data/vintages/{snapshot}/payload/prices.csv", assets, str(program["data"]["start_date"]))
    panels, signal_audit, permutation = build_positions(bars, assets, program)
    core, trend = batch23.core_periods(), batch23.trend_periods(PRIMARY_COST)
    weekly_tables, primary_daily, scoreboard = {}, {}, []
    for variant in VARIANTS:
        for cost in COSTS:
            daily = batch24.simulate_daily(variant, cost, bars, panels, assets)
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
        common_core_metrics = performance_metrics(common_core).to_dict()
        candidate_trend, common_trend = batch23.aligned(weekly, trend)
        blend_rows = batch23.blend(core, weekly, PRIMARY_COST)
        blend_values, blend_core = batch23.aligned(blend_rows, core)
        blend_metrics = performance_metrics(blend_values).to_dict()
        paired = batch23.paired_bootstrap(blend_values, blend_core, 20260827 + number, alpha=0.025)
        entries = sum(row["candidate"] == candidate and row["event"] == "entry" for row in signal_audit)
        later_exposure = {
            "2016_2020": any("2016-01-01" <= str(row["realization_date"]) <= "2020-12-31" and float(row["invested_weight"]) > 0 for row in primary_daily[candidate]),
            "2021_present": any(str(row["realization_date"]) >= "2021-01-01" and float(row["invested_weight"]) > 0 for row in primary_daily[candidate]),
        }
        gates = {
            "signal_coverage": entries >= 20 and all(later_exposure.values()),
            "primary_performance": float(primary["full_annual_return"]) > 0 and float(primary["full_sharpe_zero_rf"]) > 0.5 and float(primary["full_max_drawdown"]) >= -0.25,
            "stress": float(stress["full_annual_return"]) > 0 and float(stress["oos_2016_2020_annual_return"]) > 0 and float(stress["oos_2021_present_annual_return"]) > 0,
            "controls": float(primary["full_sharpe_zero_rf"]) > max(float(row["full_sharpe_zero_rf"]) for row in controls),
            "dependence_core": abs(correlation(candidate_core, common_core)) <= 0.80,
            "dependence_trend": abs(correlation(candidate_trend, common_trend)) <= 0.80,
            "blend_point": float(blend_metrics["sharpe_zero_rf"]) > float(common_core_metrics["sharpe_zero_rf"]) and float(blend_metrics["max_drawdown"]) >= float(common_core_metrics["max_drawdown"]),
            "blend_familywise_paired": bool(paired["pass"]),
            "survivorship_safe": False, "untouched_forward_52w": False,
        }
        gates["all"] = all(gates.values())
        evaluations[candidate] = {
            "entries": entries, "later_exposure": later_exposure, "primary_50bps": primary, "stress_100bps": stress,
            "common_core_metrics": common_core_metrics,
            "correlation_to_core": correlation(candidate_core, common_core), "correlation_to_trend": correlation(candidate_trend, common_trend),
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
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 25,
        "track": "quant_trading_repository_bollinger_bottom_w", "program_sha256": sha256(PROGRAM),
        "source_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "core_evidence_sha256": sha256(batch23.CORE_EVIDENCE), "trend_evidence_sha256": sha256(batch23.TREND_EVIDENCE),
        "data_audit": data_audit, "asset_permutation_control": permutation, "core_common_metrics_50bps": core_metrics,
        "candidate_evaluations": evaluations, "promoted": any(bool(evaluations[name]["gates"]["all"]) for name in CANDIDATES),
        "live_trading_approved": False,
        "limitations": [
            "The current ETF list is survivorship-prone and the snapshot can contain pre-acquisition revisions.",
            "The literal candidate intentionally retains GBP/USD absolute units and may produce no portable ETF signal.",
            "The normalized candidate is a fixed dimensional repair, not a parameter search or claim of canonical Bollinger practice.",
            "Daily adjusted closes cannot model intraday pattern confirmation or executable spreads.",
            "All evidence is retrospective and no result is approved for live trading."
        ],
    }
    report = ["# Repository Bollinger Bottom-W Pattern — Batch 25", ""]
    for candidate in CANDIDATES:
        item, row, stress = evaluations[candidate], evaluations[candidate]["primary_50bps"], evaluations[candidate]["stress_100bps"]
        report.extend([
            f"## {candidate.replace('_', ' ').title()}", "",
            f"Entries: **{item['entries']}**. At 50 bps: **{float(row['full_annual_return']) * 100:.2f}%** annual return, **{float(row['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(row['full_max_drawdown']) * 100:.2f}%** drawdown, **{float(row['full_annual_turnover']):.2f}** turnover.", "",
            f"At 100 bps: **{float(stress['full_annual_return']) * 100:.2f}%**. Core/trend correlations: **{item['correlation_to_core']:.3f}/{item['correlation_to_trend']:.3f}**. Blend Sharpe: **{float(item['blend_metrics']['sharpe_zero_rf']):.3f}** versus common-period core **{float(item['common_core_metrics']['sharpe_zero_rf']):.3f}**. Promotion: **{item['gates']['all']}**.", "",
        ])
    report.extend(["Both scale interpretations and all gates were fixed before results. No tolerance was widened after observing coverage.", ""])
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps(evaluations, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
