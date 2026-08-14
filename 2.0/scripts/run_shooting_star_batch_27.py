#!/usr/bin/env python3
"""Run predeclared causal Shooting Star candidates and falsification controls."""

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
from src.systematic_trader.shooting_star_protocol import shooting_star_short_states
from src.systematic_trader.term_structure_challenger import correlation

PROGRAM = ROOT / "config/shooting_star_program_v1.json"
SOURCE_REVIEW = ROOT / "evidence/quant_trading_repository_batch_27/source_rule_review.json"
OUTPUT = ROOT / "evidence/shooting_star_batch_27"
INVENTORY = ROOT / "evidence/quant_trading_repository_batch_21/strategy_inventory.csv"
CANDIDATES = ("source_causal_confirmed", "normalized_confirmed", "normalized_unconfirmed")
CONTROL_SUFFIXES = ("stale_1d", "stale_5d", "inverted", "asset_permuted")
VARIANTS = tuple(name for candidate in CANDIDATES for name in (candidate, *(f"{candidate}_{suffix}" for suffix in CONTROL_SUFFIXES)))
SCENARIOS = ((10.0, .03, "low_10bps_borrow3"), (50.0, .03, "primary_50bps_borrow3"), (100.0, .08, "stress_100bps_borrow8"))
PRIMARY = "primary_50bps_borrow3"
STRESS = "stress_100bps_borrow8"


def build_states(bars, assets):
    panels = {name: {} for name in VARIANTS if not name.endswith("asset_permuted")}
    audit = []
    definitions = {
        "source_causal_confirmed": ("source_signed_expanding", True),
        "normalized_confirmed": ("normalized_absolute_expanding", True),
        "normalized_unconfirmed": ("normalized_absolute_expanding", False),
    }
    for asset, rows in bars.items():
        inputs = [{key: float(row[key]) for key in ("open", "high", "low", "close")} for row in rows]
        for candidate, (body_mode, confirmed) in definitions.items():
            states, events, star_indices, diagnostics = shooting_star_short_states(
                inputs, body_mode=body_mode, require_confirmation=confirmed,
            )
            for index in range(2, len(rows)):
                key = f"{rows[index]['date']}|{asset}"
                state = int(states[index])
                panels[candidate][key] = state
                panels[f"{candidate}_inverted"][key] = -state
                for lag in (1, 5):
                    if index - lag >= 2:
                        panels[f"{candidate}_stale_{lag}d"][key] = int(states[index - lag])
                detail = diagnostics[index]
                audit.append({
                    "decision_date": rows[index]["date"], "asset": asset, "candidate": candidate,
                    "state": state, "event": events[index], "star_index": "" if star_indices[index] is None else star_indices[index],
                    "condition_count": detail["condition_count"], "body": detail["body"],
                    "body_observation": detail["body_observation"], "body_reference": detail["body_reference"],
                    "lower_wick": detail["lower_wick"], "upper_wick": detail["upper_wick"],
                    "adjusted_close": rows[index]["close"],
                })
    donors = list(assets)
    random.Random(20260827).shuffle(donors)
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


def signed_target(states, assets, cap=.2):
    active = [asset for asset in assets if states.get(asset, 0)]
    magnitude = min(cap, 1.0 / len(active)) if active else 0.0
    weights = {asset: magnitude * int(states.get(asset, 0)) for asset in assets}
    weights["cash::USD"] = 1.0 - sum(weights.values())
    return weights


def simulate_daily(variant, cost_bps, borrow, bars, panels, assets):
    prices = {f"{row['date']}|{asset}": float(row["close"]) for asset, rows in bars.items() for row in rows}
    dates = sorted({str(row["date"]) for rows in bars.values() for row in rows})
    previous = signed_target({}, assets)
    periods = []
    for index in range(len(dates) - 1):
        decision, realization = dates[index], dates[index + 1]
        eligible = [asset for asset in assets if f"{decision}|{asset}" in panels[variant] and f"{decision}|{asset}" in prices and f"{realization}|{asset}" in prices]
        if not eligible:
            continue
        states = {asset: int(panels[variant][f"{decision}|{asset}"]) for asset in eligible}
        target = signed_target(states, assets)
        turnover = sum(abs(target[asset] - previous[asset]) for asset in assets)
        returns = {asset: prices[f"{realization}|{asset}"] / prices[f"{decision}|{asset}"] - 1.0 for asset in eligible}
        gross = sum(target[asset] * returns[asset] for asset in eligible)
        short_exposure = sum(max(-target[asset], 0.0) for asset in assets)
        trading_cost = turnover * cost_bps / 10_000.0
        borrow_cost = short_exposure * borrow / 252.0
        periods.append({
            "variant": variant, "decision_date": decision, "realization_date": realization,
            "cost_bps": cost_bps, "annual_borrow_fee": borrow,
            "long_exposure": sum(max(target[asset], 0.0) for asset in assets),
            "short_exposure": short_exposure, "invested_weight": sum(abs(target[asset]) for asset in assets),
            "turnover": turnover, "gross_return": gross, "trading_cost": trading_cost,
            "borrow_cost": borrow_cost, "net_return": gross - trading_cost - borrow_cost,
        })
        denominator = 1.0 + gross
        previous = {asset: target[asset] * (1.0 + returns.get(asset, 0.0)) / denominator for asset in assets}
        previous["cash::USD"] = target["cash::USD"] / denominator
    return periods


def accounting_audit(rows):
    return {
        "rows": len(rows),
        "maximum_identity_error": max((abs(float(row["gross_return"]) - float(row["trading_cost"]) - float(row["borrow_cost"]) - float(row["net_return"])) for row in rows), default=0.0),
        "maximum_turnover": max((float(row["turnover"]) for row in rows), default=0.0),
        "maximum_long_exposure": max((float(row["long_exposure"]) for row in rows), default=0.0),
        "maximum_short_exposure": max((float(row["short_exposure"]) for row in rows), default=0.0),
        "maximum_gross_exposure": max((float(row["invested_weight"]) for row in rows), default=0.0),
    }


def update_inventory():
    rows = batch23.read_csv(INVENTORY)
    for row in rows:
        if row["number"] == "17":
            row.update(status="tested_batch_27", reason="Literal-causal and normalized confirmed/unconfirmed Shooting Star variants tested with costs borrow controls and blends", next_action="Follow Batch 27 gate decision")
    batch23.write_csv(INVENTORY, rows)


def main():
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    snapshot, assets = str(program["data"]["snapshot_id"]), list(program["data"]["assets"])
    bars, data_audit = batch23.load_bars(ROOT / f"data/vintages/{snapshot}/payload/prices.csv", assets, str(program["data"]["start_date"]))
    panels, signal_audit, permutation = build_states(bars, assets)
    core, trend = batch23.core_periods(), batch23.trend_periods(50.0)
    weekly_tables, primary_daily, scoreboard, audits = {}, {}, [], {}
    for variant in VARIANTS:
        for cost, borrow, scenario in SCENARIOS:
            daily = simulate_daily(variant, cost, borrow, bars, panels, assets)
            audit = accounting_audit(daily)
            if audit["maximum_identity_error"] > 1e-12 or audit["maximum_gross_exposure"] > 1.0 + 1e-12:
                raise RuntimeError(f"accounting invariant failed for {variant} {scenario}")
            weekly = batch23.aggregate_weekly(daily, core)
            weekly_tables[(variant, scenario)] = weekly
            audits[f"{variant}|{scenario}"] = audit
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
        paired = batch23.paired_bootstrap(blend_values, blend_core, 20260840 + number, alpha=1.0 / 60.0)
        entries = sum(row["candidate"] == candidate and str(row["event"]).startswith("short_entry") for row in signal_audit)
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
            "stress_100bps_borrow8": stress, "controls_primary": controls, "common_core_metrics": core_metrics,
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
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 27, "track": "quant_trading_repository_shooting_star",
        "program_sha256": sha256(PROGRAM), "source_review_sha256": sha256(SOURCE_REVIEW), "source_snapshot_id": snapshot,
        "core_evidence_sha256": sha256(batch23.CORE_EVIDENCE), "trend_evidence_sha256": sha256(batch23.TREND_EVIDENCE),
        "data_audit": data_audit, "asset_permutation_control": permutation, "accounting_audits": audits,
        "candidate_evaluations": evaluations, "promoted": any(bool(evaluations[name]["gates"]["all"]) for name in CANDIDATES),
        "live_trading_approved": False,
        "limitations": [
            "The free ETF universe is survivorship-prone and the snapshot can contain pre-acquisition vendor revisions.",
            "Adjusted daily OHLC cannot reproduce intraday stop ordering, executable spreads, or gaps inside a bar.",
            "Borrow availability, forced buy-ins, dividends on borrowed shares, and nonlinear market impact are not fully modeled.",
            "The expanding body references are causal repairs; the repository's biased full-sample statistic is intentionally not evaluated for promotion.",
            "All evidence is retrospective and no result is approved for live trading."
        ],
    }
    report = ["# Repository Shooting Star — Batch 27", ""]
    for candidate in CANDIDATES:
        item, row, stress = evaluations[candidate], evaluations[candidate]["primary_50bps_borrow3"], evaluations[candidate]["stress_100bps_borrow8"]
        report.extend([
            f"## {candidate.replace('_', ' ').title()}", "",
            f"Entries: **{item['entries']}**. Primary: **{float(row['full_annual_return']) * 100:.2f}%** annual return, **{float(row['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(row['full_max_drawdown']) * 100:.2f}%** drawdown, and **{float(row['full_annual_turnover']):.2f}** turnover.", "",
            f"Stress return: **{float(stress['full_annual_return']) * 100:.2f}%**. Core/trend correlation: **{item['correlation_to_core']:.3f}/{item['correlation_to_trend']:.3f}**. Blend Sharpe: **{float(item['blend_metrics']['sharpe_zero_rf']):.3f}** versus core **{float(item['common_core_metrics']['sharpe_zero_rf']):.3f}**. Promotion: **{item['gates']['all']}**.", "",
        ])
    report.extend(["All candidates, causal repairs, costs, controls, and familywise gates were fixed before results. The source's lookahead return was not computed.", ""])
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name not in {"result.json", "determinism_check.json"}}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    update_inventory()
    print(json.dumps(evaluations, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
