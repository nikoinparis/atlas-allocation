#!/usr/bin/env python3
"""Test all fixed threshold and pattern strategies present in the RSI source."""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_heikin_ashi_batch_23 as batch23
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.rsi_pattern_protocol import head_shoulders_short_states, repository_rsi, threshold_states
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/rsi_pattern_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_26/source_rule_review.json"
OUTPUT = ROOT / "evidence/rsi_pattern_batch_26"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
CANDIDATES = ("threshold_long_short", "threshold_long_only", "head_shoulders_source_price", "head_shoulders_rsi_corrected")
CONTROL_SUFFIXES = ("stale_1d", "stale_5d", "inverted", "asset_permuted")
VARIANTS = tuple(name for candidate in CANDIDATES for name in (candidate, *(f"{candidate}_{suffix}" for suffix in CONTROL_SUFFIXES)))
SCENARIOS = ((10.0, .03, "low_10bps_borrow3"), (50.0, .03, "primary_50bps_borrow3"), (100.0, .08, "stress_100bps_borrow8"))
PRIMARY = "primary_50bps_borrow3"
STRESS = "stress_100bps_borrow8"


def build_states(
    bars: dict[str, list[dict[str, float | str]]], assets: list[str], program: dict[str, object],
) -> tuple[dict[str, dict[str, int]], list[dict[str, object]], dict[str, str]]:
    panels = {name: {} for name in VARIANTS if not name.endswith("asset_permuted")}
    audit = []
    for asset, rows in bars.items():
        prices = [float(row["close"]) for row in rows]
        rsi = repository_rsi(prices, lag=14)
        definitions = {
            "threshold_long_short": (threshold_states(rsi, long_only=False), None, None),
            "threshold_long_only": (threshold_states(rsi, long_only=True), None, None),
        }
        for candidate, use_rsi in (("head_shoulders_source_price", False), ("head_shoulders_rsi_corrected", True)):
            states, events, coordinates = head_shoulders_short_states(prices, rsi, use_rsi_nodes=use_rsi)
            definitions[candidate] = (states, events, coordinates)
        for candidate, (states, events, coordinates) in definitions.items():
            previous = 0
            for index in range(14, len(rows)):
                key = f"{rows[index]['date']}|{asset}"
                state = int(states[index])
                panels[candidate][key] = state
                panels[f"{candidate}_inverted"][key] = -state
                for lag in (1, 5):
                    if index - lag >= 14:
                        panels[f"{candidate}_stale_{lag}d"][key] = int(states[index - lag])
                if events is None:
                    event = "hold"
                    if state != previous:
                        event = "switch" if state and previous else ("entry" if state else "exit")
                else:
                    event = events[index]
                audit.append({
                    "decision_date": rows[index]["date"], "asset": asset, "candidate": candidate,
                    "state": state, "event": event, "rsi": "" if rsi[index] is None else rsi[index],
                    "coordinates": "" if coordinates is None or coordinates[index] is None else ",".join(map(str, coordinates[index])),
                    "adjusted_close": prices[index],
                })
                previous = state
    donors = list(assets)
    random.Random(20260826).shuffle(donors)
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


def signed_target(states: dict[str, int], assets: list[str], cap: float = .2) -> dict[str, float]:
    active = [asset for asset in assets if states.get(asset, 0)]
    magnitude = min(cap, 1.0 / len(active)) if active else 0.0
    weights = {asset: magnitude * states.get(asset, 0) for asset in assets}
    weights["cash::USD"] = 1.0 - sum(weights.values())
    return weights


def simulate_daily(
    variant: str, cost_bps: float, borrow: float, bars: dict[str, list[dict[str, float | str]]],
    panels: dict[str, dict[str, int]], assets: list[str],
) -> list[dict[str, object]]:
    prices = {f"{row['date']}|{asset}": float(row["close"]) for asset, rows in bars.items() for row in rows}
    dates = sorted({str(row["date"]) for rows in bars.values() for row in rows})
    previous = signed_target({}, assets)
    periods = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        eligible = [asset for asset in assets if f"{decision}|{asset}" in panels[variant] and f"{decision}|{asset}" in prices and f"{realization}|{asset}" in prices]
        if not eligible:
            continue
        states = {asset: panels[variant][f"{decision}|{asset}"] for asset in eligible}
        target = signed_target(states, assets)
        turnover = sum(abs(target[asset] - previous[asset]) for asset in assets)
        returns = {asset: prices[f"{realization}|{asset}"] / prices[f"{decision}|{asset}"] - 1.0 for asset in eligible}
        gross = sum(target[asset] * returns[asset] for asset in eligible)
        short_exposure = sum(max(-target[asset], 0.0) for asset in assets)
        trading_cost, borrow_cost = turnover * cost_bps / 10_000.0, short_exposure * borrow / 252.0
        periods.append({
            "variant": variant, "decision_date": decision, "realization_date": realization,
            "cost_bps": cost_bps, "annual_borrow_fee": borrow,
            "long_exposure": sum(max(target[asset], 0.0) for asset in assets), "short_exposure": short_exposure,
            "invested_weight": sum(abs(target[asset]) for asset in assets), "turnover": turnover,
            "gross_return": gross, "trading_cost": trading_cost, "borrow_cost": borrow_cost,
            "net_return": gross - trading_cost - borrow_cost,
        })
        previous = {asset: target[asset] * (1.0 + returns.get(asset, 0.0)) / (1.0 + gross) for asset in assets}
        previous["cash::USD"] = target["cash::USD"] / (1.0 + gross)
    return periods


def update_inventory() -> None:
    rows = batch23.read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "10":
            row.update(status="tested_batch_26", reason="Threshold and literal/corrected head-shoulders RSI families tested with causal costs borrow controls and blends", next_action="Follow Batch 26 gate decision")
    batch23.write_csv(INVENTORY, rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot, assets = str(program["data"]["snapshot_id"]), list(program["data"]["assets"])
    bars, data_audit = batch23.load_bars(ROOT / f"data/vintages/{snapshot}/payload/prices.csv", assets, str(program["data"]["start_date"]))
    panels, signal_audit, permutation = build_states(bars, assets, program)
    core, trend = batch23.core_periods(), batch23.trend_periods(50.0)
    weekly_tables, primary_daily, scoreboard = {}, {}, []
    for variant in VARIANTS:
        for cost, borrow, scenario in SCENARIOS:
            daily = simulate_daily(variant, cost, borrow, bars, panels, assets)
            weekly = batch23.aggregate_weekly(daily, core)
            weekly_tables[(variant, scenario)] = weekly
            if variant in CANDIDATES and scenario == PRIMARY:
                primary_daily[variant] = daily
            scoreboard.append({
                "variant": variant, "scenario": scenario, "cost_bps": cost, "annual_borrow_fee": borrow,
                **{f"full_{key}": value for key, value in batch23.metrics(weekly).items()},
                **{f"oos_2016_2020_{key}": value for key, value in batch23.metrics(weekly, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in batch23.metrics(weekly, "2021-01-01").items()},
            })
    evaluations, blends = {}, {}
    for number, candidate in enumerate(CANDIDATES):
        primary = next(row for row in scoreboard if row["variant"] == candidate and row["scenario"] == PRIMARY)
        stress = next(row for row in scoreboard if row["variant"] == candidate and row["scenario"] == STRESS)
        controls = [next(row for row in scoreboard if row["variant"] == f"{candidate}_{suffix}" and row["scenario"] == PRIMARY) for suffix in CONTROL_SUFFIXES]
        weekly = weekly_tables[(candidate, PRIMARY)]
        candidate_core, common_core = batch23.aligned(weekly, core)
        candidate_trend, common_trend = batch23.aligned(weekly, trend)
        core_metrics = performance_metrics(common_core).to_dict()
        blend_rows = batch23.blend(core, weekly, 50.0)
        blend_values, blend_core = batch23.aligned(blend_rows, core)
        blend_metrics = performance_metrics(blend_values).to_dict()
        paired = batch23.paired_bootstrap(blend_values, blend_core, 20260830 + number, alpha=.0125)
        entries = sum(row["candidate"] == candidate and row["event"] in {"entry", "switch", "short_entry"} for row in signal_audit)
        later_exposure = {
            "2016_2020": any("2016-01-01" <= str(row["realization_date"]) <= "2020-12-31" and float(row["invested_weight"]) > 0 for row in primary_daily[candidate]),
            "2021_present": any(str(row["realization_date"]) >= "2021-01-01" and float(row["invested_weight"]) > 0 for row in primary_daily[candidate]),
        }
        gates = {
            "signal_coverage": entries >= 20 and all(later_exposure.values()),
            "primary_performance": float(primary["full_annual_return"]) > 0 and float(primary["full_sharpe_zero_rf"]) > .5 and float(primary["full_max_drawdown"]) >= -.25,
            "stress": float(stress["full_annual_return"]) > 0 and float(stress["oos_2016_2020_annual_return"]) > 0 and float(stress["oos_2021_present_annual_return"]) > 0,
            "controls": float(primary["full_sharpe_zero_rf"]) > max(float(row["full_sharpe_zero_rf"]) for row in controls),
            "dependence_core": abs(correlation(candidate_core, common_core)) <= .8,
            "dependence_trend": abs(correlation(candidate_trend, common_trend)) <= .8,
            "blend_point": float(blend_metrics["sharpe_zero_rf"]) > float(core_metrics["sharpe_zero_rf"]) and float(blend_metrics["max_drawdown"]) >= float(core_metrics["max_drawdown"]),
            "blend_familywise_paired": bool(paired["pass"]), "survivorship_safe": False, "untouched_forward_52w": False,
        }
        gates["all"] = all(gates.values())
        evaluations[candidate] = {
            "entries": entries, "later_exposure": later_exposure, "primary_50bps_borrow3": primary,
            "stress_100bps_borrow8": stress, "common_core_metrics": core_metrics,
            "correlation_to_core": correlation(candidate_core, common_core), "correlation_to_trend": correlation(candidate_trend, common_trend),
            "blend_metrics": blend_metrics, "paired_blend": paired, "gates": gates,
        }
        blends[candidate] = blend_rows
    OUTPUT.mkdir(parents=True, exist_ok=True)
    batch23.write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    batch23.write_csv(OUTPUT / "signal_audit.csv", signal_audit)
    for candidate in CANDIDATES:
        batch23.write_csv(OUTPUT / f"{candidate}_daily_primary.csv", primary_daily[candidate])
        batch23.write_csv(OUTPUT / f"{candidate}_weekly_primary.csv", weekly_tables[(candidate, PRIMARY)])
        batch23.write_csv(OUTPUT / f"{candidate}_blend_primary.csv", blends[candidate])
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 26, "track": "quant_trading_repository_rsi",
        "program_sha256": sha256(PROGRAM), "source_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "core_evidence_sha256": sha256(batch23.CORE_EVIDENCE), "trend_evidence_sha256": sha256(batch23.TREND_EVIDENCE),
        "data_audit": data_audit, "asset_permutation_control": permutation, "candidate_evaluations": evaluations,
        "promoted": any(bool(evaluations[name]["gates"]["all"]) for name in CANDIDATES), "live_trading_approved": False,
        "limitations": [
            "The current ETF universe is survivorship-prone and the free snapshot can contain pre-acquisition revisions.",
            "Short availability, forced buy-ins, dividends on borrowed shares, and nonlinear market impact are not fully modeled.",
            "The corrected RSI-pattern candidate repairs the source's stated intent and is not its executed main strategy.",
            "Daily closes cannot reproduce intraday threshold crossings or executable spreads.",
            "All evidence is retrospective and no result is approved for live trading."
        ],
    }
    report = ["# Repository RSI Strategies — Batch 26", ""]
    for candidate in CANDIDATES:
        item, row, stress = evaluations[candidate], evaluations[candidate]["primary_50bps_borrow3"], evaluations[candidate]["stress_100bps_borrow8"]
        report.extend([
            f"## {candidate.replace('_', ' ').title()}", "",
            f"Entries: **{item['entries']}**. Primary: **{float(row['full_annual_return']) * 100:.2f}%** annual return, **{float(row['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(row['full_max_drawdown']) * 100:.2f}%** drawdown, **{float(row['full_annual_turnover']):.2f}** turnover.", "",
            f"Stress return: **{float(stress['full_annual_return']) * 100:.2f}%**. Core/trend correlation: **{item['correlation_to_core']:.3f}/{item['correlation_to_trend']:.3f}**. Blend Sharpe: **{float(item['blend_metrics']['sharpe_zero_rf']):.3f}** versus core **{float(item['common_core_metrics']['sharpe_zero_rf']):.3f}**. Promotion: **{item['gates']['all']}**.", "",
        ])
    report.extend(["All four candidates and their familywise gates were fixed before results. No RSI or pattern threshold was tuned.", ""])
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps(evaluations, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
