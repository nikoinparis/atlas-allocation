#!/usr/bin/env python3
"""Orchestrate isolated ETF-pairs research, costs, controls, and portfolio evidence."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ml_confidence_overlay_batch_18 as batch18
from scripts import run_robust_cross_sectional_ml_batch_17 as batch17
from src.systematic_trader.data_vintage import sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.pair_protocol import frictional_pair_return
from src.systematic_trader.term_structure_challenger import correlation

IMAGE = "localhost/po2-etf-pairs:statsmodels-0.14.6-v1"
PROGRAM = ROOT / "config/etf_pairs_program_v1.json"
UNIVERSE = ROOT / "config/free_etf_universe.json"
SNAPSHOT = "20260809T002313Z-0d8632e2cf759918"
PRICES = ROOT / f"data/vintages/{SNAPSHOT}/payload/prices.csv"
OUTPUT = ROOT / "evidence/etf_pairs_batch_21"
VARIANTS = ("real", "inverted", "random_pairs", "stale_5d")
SCENARIOS = ((10.0, 0.03, "10bps_borrow3"), (50.0, 0.03, "50bps_borrow3"), (100.0, 0.03, "100bps_borrow3"), (100.0, 0.08, "100bps_borrow8"))
BOOTSTRAP_SAMPLES = 20_000


def command(args: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args[:4])}\n{result.stderr}\n{result.stdout}")
    return result


def run_isolated(destination: Path) -> None:
    name = "po2-etf-pairs-" + uuid.uuid4().hex[:12]
    created = False
    try:
        command(["podman", "create", "--name", name, IMAGE, "--prices", "/prices.csv", "--universe", "/universe.json", "--config", "/config.json", "--output", "/output"])
        created = True
        command(["podman", "cp", str(PRICES), f"{name}:/prices.csv"])
        command(["podman", "cp", str(UNIVERSE), f"{name}:/universe.json"])
        command(["podman", "cp", str(PROGRAM), f"{name}:/config.json"])
        started = command(["podman", "start", "--attach", name], capture=False, check=False)
        if started.returncode != 0:
            raise RuntimeError(f"isolated pairs engine failed with exit code {started.returncode}")
        destination.mkdir(parents=True, exist_ok=True)
        command(["podman", "cp", f"{name}:/output/.", str(destination)])
    finally:
        if created:
            command(["podman", "rm", "--force", name], check=False)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: format(value, ".9g") if isinstance(value, float) else value for key, value in row.items()} for row in rows)


def net_daily(rows: list[dict[str, str]], cost_bps: float, borrow: float) -> list[dict[str, object]]:
    return [{
        **row, "cost_bps": cost_bps, "annual_borrow_fee": borrow,
        "trading_cost": float(row["turnover"]) * cost_bps / 10_000.0,
        "borrow_cost": float(row["short_exposure"]) * borrow / 252.0,
        "net_return": frictional_pair_return(
            float(row["gross_return"]), float(row["turnover"]), float(row["short_exposure"]),
            cost_bps=cost_bps, annual_borrow_fee=borrow,
        ),
    } for row in rows]


def metric_dict(rows: list[dict[str, object]], periods_per_year: int, start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [row for row in rows if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in selected], periods_per_year=periods_per_year).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in selected) * periods_per_year
    result["mean_short_exposure"] = statistics.fmean(float(row["short_exposure"]) for row in selected)
    return result


def weekly_pairs(daily: list[dict[str, object]], core_periods: list[dict[str, object]]) -> list[dict[str, object]]:
    result = []
    for core in core_periods:
        start, end = str(core["decision_date"]), str(core["realization_date"])
        selected = [row for row in daily if start < str(row["realization_date"]) <= end]
        if not selected:
            continue
        result.append({
            "decision_date": start, "realization_date": end,
            "net_return": math.prod(1.0 + float(row["net_return"]) for row in selected) - 1.0,
            "turnover": sum(float(row["turnover"]) for row in selected),
            "short_exposure": statistics.fmean(float(row["short_exposure"]) for row in selected),
            "daily_observations": len(selected),
        })
    return result


def bootstrap_return_lower(values: list[float], seed: int) -> dict[str, float | int | bool]:
    generator = random.Random(seed)
    annual = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            sample.extend(values[(start + offset) % len(values)] for offset in range(13))
        sample = sample[:len(values)]
        annual.append(math.prod(1.0 + value for value in sample) ** (52.0 / len(sample)) - 1.0)
    lower = sorted(annual)[math.floor(0.05 * (len(annual) - 1))]
    return {"samples": BOOTSTRAP_SAMPLES, "block_weeks": 13, "one_sided_95pct_lower_annual_return": lower, "pass": lower > 0.0}


def blend(core_periods: list[dict[str, object]], pair_periods: list[dict[str, object]], cost_bps: float) -> list[dict[str, object]]:
    pairs = {str(row["realization_date"]): row for row in pair_periods}
    rows = []
    first = True
    for core in core_periods:
        day = str(core["realization_date"])
        if day not in pairs:
            continue
        core_return, pair_return = float(core["net_return"]), float(pairs[day]["net_return"])
        gross = 0.8 * core_return + 0.2 * pair_return
        drifted_pair = 0.2 * (1.0 + pair_return) / (1.0 + gross)
        allocation_turnover = 0.2 if first else abs(drifted_pair - 0.2)
        first = False
        rows.append({
            "decision_date": core["decision_date"], "realization_date": day,
            "core_return": core_return, "pair_return": pair_return,
            "allocation_turnover": allocation_turnover,
            "turnover": allocation_turnover,
            "short_exposure": 0.2 * float(pairs[day]["short_exposure"]),
            "net_return": gross - allocation_turnover * cost_bps / 10_000.0,
        })
    return rows


def image_metadata() -> dict[str, str]:
    result = command(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Digest}}"])
    image_id, _, digest = result.stdout.strip().partition("|")
    return {"image": IMAGE, "image_id": image_id, "repo_digest": digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-engine-output", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temporary:
        engine = Path(temporary) / "engine"
        if args.reuse_engine_output:
            engine.mkdir(parents=True)
            for name in ("daily_periods.csv", "selected_pairs.csv", "formation_audit.csv", "metadata.json"):
                shutil.copyfile(OUTPUT / name, engine / name)
        else:
            run_isolated(engine)
        metadata = json.loads((engine / "metadata.json").read_text(encoding="utf-8"))
        all_daily = read_csv(engine / "daily_periods.csv")
        grouped = {variant: [row for row in all_daily if row["variant"] == variant] for variant in VARIANTS}
        if any(not rows for rows in grouped.values()):
            raise RuntimeError("one or more pair variants produced no daily periods")
        core_by_cost = {cost: batch18.frozen_winner_periods(cost) for cost in (10.0, 50.0, 100.0)}
        scoreboard = []
        daily_tables = {}
        weekly_tables = {}
        for variant in VARIANTS:
            for cost, borrow, scenario in SCENARIOS:
                daily = net_daily(grouped[variant], cost, borrow)
                daily_tables[(variant, scenario)] = daily
                weekly = weekly_pairs(daily, core_by_cost[cost])
                weekly_tables[(variant, scenario)] = weekly
                scoreboard.append({
                    "variant": variant, "scenario": scenario, "cost_bps": cost, "annual_borrow_fee": borrow,
                    **{f"full_{key}": value for key, value in metric_dict(weekly, 52).items()},
                    **{f"oos_2016_2020_{key}": value for key, value in metric_dict(weekly, 52, "2016-01-01", "2020-12-31").items()},
                    **{f"oos_2021_present_{key}": value for key, value in metric_dict(weekly, 52, "2021-01-01").items()},
                })
        primary = next(row for row in scoreboard if row["variant"] == "real" and row["scenario"] == "50bps_borrow3")
        stress = next(row for row in scoreboard if row["variant"] == "real" and row["scenario"] == "100bps_borrow8")
        controls = {variant: next(row for row in scoreboard if row["variant"] == variant and row["scenario"] == "50bps_borrow3") for variant in VARIANTS if variant != "real"}
        primary_weekly = weekly_tables[("real", "50bps_borrow3")]
        pair_by_date = {str(row["realization_date"]): float(row["net_return"]) for row in primary_weekly}
        core_50 = core_by_cost[50.0]
        common_core = [row for row in core_50 if str(row["realization_date"]) in pair_by_date]
        core_values = [float(row["net_return"]) for row in common_core]
        pair_values = [pair_by_date[str(row["realization_date"])] for row in common_core]
        dependence = correlation(pair_values, core_values)
        blend_rows = blend(common_core, primary_weekly, 50.0)
        core_common_metrics = performance_metrics(core_values).to_dict()
        blend_metrics = metric_dict(blend_rows, 52)
        paired_blend = batch17.paired_bootstrap_advantage(
            [float(row["net_return"]) for row in blend_rows], core_values, seed=20260821,
        )
        pair_bootstrap = bootstrap_return_lower(pair_values, 20260821)
        gates = {
            "pair_annual_return": float(primary["full_annual_return"]) > 0.0,
            "pair_sharpe": float(primary["full_sharpe_zero_rf"]) > 0.5,
            "pair_maximum_drawdown": float(primary["full_max_drawdown"]) >= -0.20,
            "pair_bootstrap_annual_return": bool(pair_bootstrap["pass"]),
            "later_windows": float(primary["oos_2016_2020_annual_return"]) > 0.0 and float(primary["oos_2021_present_annual_return"]) > 0.0,
            "stress": float(stress["full_annual_return"]) > 0.0,
            "controls": float(primary["full_sharpe_zero_rf"]) > max(float(row["full_sharpe_zero_rf"]) for row in controls.values()),
            "dependence": abs(dependence) <= 0.30,
            "blend_point": float(blend_metrics["sharpe_zero_rf"]) > float(core_common_metrics["sharpe_zero_rf"]) and float(blend_metrics["max_drawdown"]) >= float(core_common_metrics["max_drawdown"]) - 1e-12,
            "blend_paired_sharpe": bool(paired_blend["sharpe_advantage_statistically_positive"]),
            "survivorship_safe": False, "untouched_forward_52w": False,
        }
        gates["all"] = all(gates.values())
        result = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 21,
            "track": "quant_trading_repository_etf_pairs", "program_sha256": sha256(PROGRAM),
            "source_snapshot_id": SNAPSHOT, "source_snapshot_manifest_sha256": sha256(ROOT / f"data/vintages/{SNAPSHOT}/manifest.json"),
            "image": image_metadata(), "engine_metadata": metadata,
            "pair_bootstrap_primary": pair_bootstrap, "weekly_correlation_to_frozen_core": dependence,
            "common_core_metrics_50bps": core_common_metrics, "blend_metrics_50bps": blend_metrics,
            "paired_blend_advantage_50bps": paired_blend, "promotion_gates": gates,
            "promoted": gates["all"], "live_trading_approved": False,
            "limitations": [
                "The current ETF universe is survivorship-prone and is not historical membership data.",
                "Historical short availability is unknown; borrow fees are modeled but forced buy-ins are not.",
                "Adjusted-close data cannot reproduce intraday fills, spreads, or locate failures.",
                "Repeated quarterly cointegration searches remain retrospective despite causal formation windows.",
            ],
        }
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for path in engine.iterdir():
            shutil.copyfile(path, OUTPUT / path.name)
        write_csv(OUTPUT / "scoreboard.csv", scoreboard)
        write_csv(OUTPUT / "primary_weekly_returns.csv", primary_weekly)
        write_csv(OUTPUT / "blend_weekly_returns.csv", blend_rows)
        report = "\n".join([
            "# ETF Pair Trading — Batch 21", "",
            f"The real pair sleeve at 50 bps plus 3% annual borrow returned **{float(primary['full_annual_return']) * 100:.2f}%** annually with **{float(primary['full_sharpe_zero_rf']):.3f}** Sharpe and **{float(primary['full_max_drawdown']) * 100:.2f}%** maximum drawdown.", "",
            f"The 100 bps plus 8% borrow stress returned **{float(stress['full_annual_return']) * 100:.2f}%** annually. Weekly correlation to the frozen core was **{dependence:.3f}**.", "",
            f"The 80/20 core-pair blend Sharpe was **{float(blend_metrics['sharpe_zero_rf']):.3f}** versus common-period core **{float(core_common_metrics['sharpe_zero_rf']):.3f}**; paired Sharpe lower bound **{float(paired_blend['one_sided_95pct_lower_sharpe_difference']):.3f}**.", "",
            f"The pair annual-return bootstrap lower bound was **{float(pair_bootstrap['one_sided_95pct_lower_annual_return']) * 100:.2f}%**. Promotion: **{gates['all']}**.", "",
            "The repository source was not executed. Its pair concept was rebuilt independently with causal formation, next-day realization, borrow fees, negative controls, and broken-relationship exits.", "",
        ])
        (OUTPUT / "report.md").write_text(report, encoding="utf-8")
        result["artifacts"] = {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in OUTPUT.iterdir() if path.is_file() and path.name != "result.json"}
        (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"primary": primary, "stress": stress, "controls": controls, "correlation": dependence, "blend": blend_metrics, "pair_bootstrap": pair_bootstrap, "paired_blend": paired_blend, "gates": gates}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
