#!/usr/bin/env python3
"""Evaluate literal and direction-corrected repository Heikin-Ashi rules."""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.heikin_ashi_protocol import capped_unit_weights, heikin_ashi_bars, update_state
from src.systematic_trader.oscillator_protocol import adjusted_bar, long_only_turnover
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/heikin_ashi_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_23/source_rule_review.json"
OUTPUT = ROOT / "evidence/heikin_ashi_batch_23"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
CORE_EVIDENCE = ROOT / "evidence/repository_oscillators_batch_22/blend_weekly_returns_50bps.csv"
TREND_EVIDENCE = ROOT / "evidence/strategy_rebuild_trend_quality/returns.csv"
CANDIDATES = ("source_exact", "direction_corrected")
VARIANTS = tuple(name for candidate in CANDIDATES for name in (candidate, f"{candidate}_stale_1d", f"{candidate}_stale_5d", f"{candidate}_random_matched"))
COSTS = (10.0, 50.0, 100.0)
PRIMARY_COST = 50.0
BOOTSTRAP_SAMPLES = 20_000


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: format(value, ".12g") if isinstance(value, float) else value for key, value in row.items()} for row in rows)


def load_bars(path: Path, assets: list[str], start: str) -> tuple[dict[str, list[dict[str, float | str]]], dict[str, object]]:
    result: dict[str, list[dict[str, float | str]]] = {asset: [] for asset in assets}
    rejected = 0
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] not in result or row["observation_date"] < start:
                continue
            try:
                bar = adjusted_bar(*(float(row[key]) for key in ("open", "high", "low", "close", "adjusted_close")))
            except ValueError:
                rejected += 1
                continue
            result[row["ticker"]].append({"date": row["observation_date"], **bar})
    for rows in result.values():
        rows.sort(key=lambda row: str(row["date"]))
    return result, {
        "assets": len(assets), "rows": sum(map(len, result.values())), "rejected_rows": rejected,
        "first_date": min(str(rows[0]["date"]) for rows in result.values()),
        "last_date": max(str(rows[-1]["date"]) for rows in result.values()),
        "split_safe_adjusted_ohlc": True,
    }


def build_states(bars: dict[str, list[dict[str, float | str]]]) -> tuple[dict[str, dict[str, int]], list[dict[str, object]]]:
    panels = {name: {} for name in VARIANTS if "random_matched" not in name}
    audit = []
    for asset, rows in bars.items():
        transformed = heikin_ashi_bars([{key: float(row[key]) for key in ("open", "high", "low", "close")} for row in rows])
        for candidate, corrected in (("source_exact", False), ("direction_corrected", True)):
            states = [0]
            events = ["initial"]
            for index in range(1, len(rows)):
                state, event = update_state(transformed[index - 1], transformed[index], states[-1], corrected=corrected)
                states.append(state)
                events.append(event)
            for index, row in enumerate(rows):
                key = f"{row['date']}|{asset}"
                panels[candidate][key] = states[index]
                for lag in (1, 5):
                    if index >= lag:
                        panels[f"{candidate}_stale_{lag}d"][key] = states[index - lag]
                audit.append({
                    "decision_date": row["date"], "asset": asset, "candidate": candidate,
                    "units": states[index], "event": events[index],
                    **{f"ha_{name}": transformed[index][name] for name in ("open", "high", "low", "close")},
                })
    return panels, audit


def random_matched_states(base: dict[str, int], eligible: list[str], day: str, candidate: str) -> dict[str, int]:
    values = [base[asset] for asset in eligible]
    random.Random(f"20260823:{candidate}:{day}").shuffle(values)
    return dict(zip(eligible, values))


def simulate_daily(
    variant: str, cost_bps: float, bars: dict[str, list[dict[str, float | str]]],
    panels: dict[str, dict[str, int]], assets: list[str],
) -> list[dict[str, object]]:
    price = {f"{row['date']}|{asset}": float(row["close"]) for asset, rows in bars.items() for row in rows}
    dates = sorted({str(row["date"]) for rows in bars.values() for row in rows})
    previous = capped_unit_weights({}, assets)
    candidate = next(name for name in CANDIDATES if variant.startswith(name))
    panel_name = candidate if variant.endswith("random_matched") else variant
    periods = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        eligible = [asset for asset in assets if f"{decision}|{asset}" in panels[panel_name] and f"{realization}|{asset}" in price]
        if not eligible:
            continue
        states = {asset: panels[panel_name][f"{decision}|{asset}"] for asset in eligible}
        if variant.endswith("random_matched"):
            states = random_matched_states(states, eligible, decision, candidate)
        target = capped_unit_weights(states, assets)
        turnover = long_only_turnover(previous, target)
        asset_returns = {asset: price[f"{realization}|{asset}"] / price[f"{decision}|{asset}"] - 1.0 for asset in eligible}
        gross = sum(target[asset] * asset_returns[asset] for asset in eligible)
        periods.append({
            "variant": variant, "decision_date": decision, "realization_date": realization,
            "cost_bps": cost_bps, "active_assets": sum(states[asset] > 0 for asset in eligible),
            "total_units": sum(states.values()), "invested_weight": 1.0 - target["cash::USD"],
            "turnover": turnover, "gross_return": gross, "cost": turnover * cost_bps / 10_000.0,
            "net_return": gross - turnover * cost_bps / 10_000.0,
        })
        previous = {asset: target[asset] * (1.0 + asset_returns.get(asset, 0.0)) / (1.0 + gross) for asset in assets}
        previous["cash::USD"] = target["cash::USD"] / (1.0 + gross)
    return periods


def core_periods() -> list[dict[str, object]]:
    return [{
        "decision_date": row["decision_date"], "realization_date": row["realization_date"],
        "net_return": float(row["core_return"]),
    } for row in read_csv(CORE_EVIDENCE)]


def trend_periods(cost_bps: float) -> list[dict[str, object]]:
    return [{
        "decision_date": row["decision_date"], "realization_date": row["realization_date"],
        "net_return": float(row["gross_return"]) - float(row["turnover"]) * cost_bps / 10_000.0,
    } for row in read_csv(TREND_EVIDENCE)]


def aggregate_weekly(daily: list[dict[str, object]], reference: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for week in reference:
        start, end = str(week["decision_date"]), str(week["realization_date"])
        selected = [row for row in daily if start < str(row["realization_date"]) <= end]
        if selected:
            result.append({
                "decision_date": start, "realization_date": end,
                "net_return": math.prod(1.0 + float(row["net_return"]) for row in selected) - 1.0,
                "turnover": sum(float(row["turnover"]) for row in selected),
                "mean_invested_weight": statistics.fmean(float(row["invested_weight"]) for row in selected),
                "daily_observations": len(selected),
            })
    return result


def metrics(rows: list[dict[str, object]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    chosen = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in chosen]).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in chosen) * 52.0
    result["mean_invested_weight"] = statistics.fmean(float(row["mean_invested_weight"]) for row in chosen)
    return result


def aligned(left: list[dict[str, object]], right: list[dict[str, object]]) -> tuple[list[float], list[float]]:
    panel = {str(row["realization_date"]): float(row["net_return"]) for row in right}
    pairs = [(float(row["net_return"]), panel[str(row["realization_date"])]) for row in left if str(row["realization_date"]) in panel]
    return [row[0] for row in pairs], [row[1] for row in pairs]


def blend(core: list[dict[str, object]], challenger: list[dict[str, object]], cost_bps: float) -> list[dict[str, object]]:
    panel = {str(row["realization_date"]): row for row in challenger}
    result, first = [], True
    for row in core:
        day = str(row["realization_date"])
        if day not in panel:
            continue
        core_return, candidate_return = float(row["net_return"]), float(panel[day]["net_return"])
        gross = 0.8 * core_return + 0.2 * candidate_return
        drifted = 0.2 * (1.0 + candidate_return) / (1.0 + gross)
        turnover = 0.2 if first else abs(drifted - 0.2)
        first = False
        result.append({
            "decision_date": row["decision_date"], "realization_date": day,
            "core_return": core_return, "candidate_return": candidate_return,
            "turnover": turnover, "mean_invested_weight": 1.0,
            "net_return": gross - turnover * cost_bps / 10_000.0,
        })
    return result


def paired_bootstrap(left: list[float], right: list[float], seed: int, alpha: float = 0.025) -> dict[str, object]:
    generator = random.Random(seed)
    length = len(left)
    differences = []
    for _ in range(BOOTSTRAP_SAMPLES):
        indexes = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(13))
        indexes = indexes[:length]
        sums = [sum(panel[index] for index in indexes) for panel in (left, right)]
        squares = [sum(panel[index] ** 2 for index in indexes) for panel in (left, right)]
        deviations = [math.sqrt(max(0.0, (square - total * total / length) / (length - 1))) for total, square in zip(sums, squares)]
        sharpes = [total / length / deviation * math.sqrt(52.0) if deviation else 0.0 for total, deviation in zip(sums, deviations)]
        differences.append(sharpes[0] - sharpes[1])
    ordered = sorted(differences)
    lower = ordered[math.floor(alpha * (len(ordered) - 1))]
    return {
        "observations": length, "samples": BOOTSTRAP_SAMPLES, "block_weeks": 13,
        "one_sided_alpha": alpha, "mean_sharpe_difference": statistics.fmean(differences),
        "one_sided_lower_sharpe_difference": lower, "pass": lower > 0.0,
    }


def update_inventory() -> None:
    rows = read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "3":
            row.update(status="tested_batch_23", reason="Literal and direction-corrected fixed rules tested with causal OHLC costs controls and blends", next_action="Follow Batch 23 gate decision")
    write_csv(INVENTORY, rows)


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot = str(program["data"]["snapshot_id"])
    assets = list(program["data"]["assets"])
    bars, data_audit = load_bars(ROOT / f"data/vintages/{snapshot}/payload/prices.csv", assets, str(program["data"]["start_date"]))
    panels, signal_audit = build_states(bars)
    core = core_periods()
    trend = trend_periods(PRIMARY_COST)
    weekly_tables = {}
    daily_primary = {}
    scoreboard = []
    for variant in VARIANTS:
        for cost in COSTS:
            daily = simulate_daily(variant, cost, bars, panels, assets)
            weekly = aggregate_weekly(daily, core)
            weekly_tables[(variant, cost)] = weekly
            if variant in CANDIDATES and cost == PRIMARY_COST:
                daily_primary[variant] = daily
            scoreboard.append({
                "variant": variant, "cost_bps": cost,
                **{f"full_{key}": value for key, value in metrics(weekly).items()},
                **{f"oos_2016_2020_{key}": value for key, value in metrics(weekly, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in metrics(weekly, "2021-01-01").items()},
            })
    core_values = [float(row["net_return"]) for row in core]
    core_metrics = performance_metrics(core_values).to_dict()
    evaluations = {}
    blends = {}
    for number, candidate in enumerate(CANDIDATES):
        primary = next(row for row in scoreboard if row["variant"] == candidate and row["cost_bps"] == PRIMARY_COST)
        stress = next(row for row in scoreboard if row["variant"] == candidate and row["cost_bps"] == 100.0)
        controls = [next(row for row in scoreboard if row["variant"] == f"{candidate}_{suffix}" and row["cost_bps"] == PRIMARY_COST) for suffix in ("stale_1d", "stale_5d", "random_matched")]
        weekly = weekly_tables[(candidate, PRIMARY_COST)]
        candidate_core, common_core = aligned(weekly, core)
        candidate_trend, common_trend = aligned(weekly, trend)
        blend_rows = blend(core, weekly, PRIMARY_COST)
        blend_values, blend_core = aligned(blend_rows, core)
        blend_metrics = performance_metrics(blend_values).to_dict()
        paired = paired_bootstrap(blend_values, blend_core, 20260823 + number, alpha=0.025)
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
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "signal_audit.csv", signal_audit)
    for candidate in CANDIDATES:
        write_csv(OUTPUT / f"{candidate}_daily_50bps.csv", daily_primary[candidate])
        write_csv(OUTPUT / f"{candidate}_weekly_50bps.csv", weekly_tables[(candidate, PRIMARY_COST)])
        write_csv(OUTPUT / f"{candidate}_blend_50bps.csv", blends[candidate])
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 23,
        "track": "quant_trading_repository_heikin_ashi", "program_sha256": sha256(PROGRAM),
        "source_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "core_evidence_sha256": sha256(CORE_EVIDENCE), "trend_evidence_sha256": sha256(TREND_EVIDENCE),
        "data_audit": data_audit, "core_common_metrics_50bps": core_metrics,
        "candidate_evaluations": evaluations,
        "promoted": any(bool(evaluations[name]["gates"]["all"]) for name in CANDIDATES),
        "live_trading_approved": False,
        "limitations": [
            "The free current ETF list is survivorship-prone and not historical membership data.",
            "Adjusted OHLC cannot reproduce intraday fills, spreads, or gaps between signal observation and executable orders.",
            "The direction-corrected rule is an interpretation, not the repository's literal claimed-long implementation.",
            "The snapshot can contain vendor revisions made before acquisition; all results are retrospective."
        ],
    }
    report_lines = ["# Repository Heikin-Ashi — Batch 23", ""]
    for candidate in CANDIDATES:
        item = evaluations[candidate]
        row, stress = item["primary_50bps"], item["stress_100bps"]
        report_lines.extend([
            f"## {candidate.replace('_', ' ').title()}", "",
            f"At 50 bps: **{float(row['full_annual_return']) * 100:.2f}%** annual return, **{float(row['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(row['full_max_drawdown']) * 100:.2f}%** drawdown, and **{float(row['full_annual_turnover']):.2f}** annual turnover.", "",
            f"At 100 bps: **{float(stress['full_annual_return']) * 100:.2f}%** annual return. Correlation to core/trend: **{item['correlation_to_core']:.3f} / {item['correlation_to_trend']:.3f}**. Blend Sharpe: **{float(item['blend_metrics']['sharpe_zero_rf']):.3f}** versus core **{float(core_metrics['sharpe_zero_rf']):.3f}**. Promotion: **{item['gates']['all']}**.", "",
        ])
    report_lines.extend(["The repository direction and corrected interpretation were fixed before results. No tuning, live execution, or paid data was used.", ""])
    (OUTPUT / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps({name: evaluations[name] for name in CANDIDATES}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
