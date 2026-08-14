#!/usr/bin/env python3
"""Run a matched walk-forward ML ablation with two repository factors."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_cross_sectional_factor_baseline_batch_16 as batch16
from scripts import run_robust_cross_sectional_ml_batch_17 as batch17
from scripts.run_monte_carlo_risk_batch_28 import verify_frozen_files
from src.systematic_trader.data_vintage import parse_utc, sha256 as project_sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.term_structure_challenger import correlation
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

PROGRAM = ROOT / "config/mlquant_walk_forward_feature_program_v1.json"
BASE_ENGINE_CONFIG = ROOT / "config/robust_cross_sectional_ml_v1.json"
INPUT = ROOT / "evidence/mlquant_walk_forward_feature_batch_34/matched_augmented_factor_dataset.csv"
AUDIT = ROOT / "evidence/mlquant_walk_forward_feature_batch_34/dataset_audit.json"
OUTPUT = ROOT / "evidence/mlquant_walk_forward_feature_batch_34"
IMAGE = "localhost/po2-robust-ml:sklearn-1.9.0-mlquant-v2"


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
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def command(args: list[str], *, capture=True, check=True):
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args[:4])}\n{result.stderr}\n{result.stdout}")
    return result


def run_engine(config_path: Path, destination: Path) -> None:
    name = "po2-mlquant-wf-" + uuid.uuid4().hex[:12]
    try:
        command(["podman", "create", "--name", name, IMAGE, "--input", "/input.csv", "--config", "/config.json", "--output", "/output"])
        command(["podman", "cp", str(INPUT), f"{name}:/input.csv"])
        command(["podman", "cp", str(config_path), f"{name}:/config.json"])
        result = command(["podman", "start", "--attach", name], capture=False, check=False)
        if result.returncode:
            raise RuntimeError(f"ML engine failed with exit code {result.returncode}")
        destination.mkdir(parents=True, exist_ok=True)
        command(["podman", "cp", f"{name}:/output/.", str(destination)])
    finally:
        command(["podman", "rm", "--force", name], check=False)


def make_engine_configs(program: dict[str, object]) -> dict[str, Path]:
    base = json.loads(BASE_ENGINE_CONFIG.read_text(encoding="utf-8"))
    paths = {}
    for name, features in program["feature_sets"].items():
        config = {**base, "program": f"{program['program']}_{name}", "features": features, "input_dataset": str(INPUT.relative_to(ROOT))}
        path = OUTPUT / f"engine_config_{name}.json"
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        paths[name] = path
    return paths


def metrics(periods, start="0000", end="9999"):
    chosen = [row for row in periods if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in chosen]).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in chosen) * 52.0
    return result


def bootstrap_ic(rows, *, seed, samples, block_months, alpha):
    values = [float(row["rank_ic"]) for row in rows]
    generator = random.Random(seed)
    means = []
    for _ in range(samples):
        indexes = []
        while len(indexes) < len(values):
            start = generator.randrange(len(values))
            indexes.extend((start + offset) % len(values) for offset in range(block_months))
        means.append(statistics.fmean(values[index] for index in indexes[:len(values)]))
    ordered = sorted(means)
    lower = ordered[math.floor(alpha * (samples - 1))]
    return {"months": len(values), "mean_rank_ic": statistics.fmean(values), "positive_month_share": sum(value > 0 for value in values) / len(values), "lower_mean_rank_ic": lower, "pass": lower > 0.0}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--reuse-engines", action="store_true"); args = parser.parse_args()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if sha256(INPUT) != audit["output_dataset_sha256"]:
        raise RuntimeError("matched ML dataset changed")
    frozen = verify_frozen_files()
    configs = make_engine_configs(program)
    engine_dirs = {name: OUTPUT / f"engine_{name}" for name in program["feature_sets"]}
    if not args.reuse_engines:
        for directory in engine_dirs.values():
            if directory.exists(): shutil.rmtree(directory)
        for name in program["feature_sets"]:
            run_engine(configs[name], engine_dirs[name])
    engine_metadata, predictions, folds = {}, {}, {}
    for name, directory in engine_dirs.items():
        engine_metadata[name] = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        predictions[name] = read_csv(directory / "predictions.csv")
        folds[name] = read_csv(directory / "outer_folds.csv")
        if engine_metadata[name]["features"] != program["feature_sets"][name]:
            raise RuntimeError(f"{name} engine used unexpected features")
        if not all(row["embargo_pass"].lower() == "true" for row in folds[name]):
            raise RuntimeError(f"{name} embargo failure")
    dataset = read_csv(INPUT)
    manifest = batch17.latest_free_manifest()
    snapshot_id = str(manifest["snapshot_id"])
    assets = sorted(json.loads(batch17.UNIVERSE.read_text(encoding="utf-8"))["symbols"])
    dates, prices, weekly_audit = prepare_weekly_adjusted_prices(
        batch17.STORE / snapshot_id / "payload/prices.csv", observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=date(2004, 1, 2), expected_symbols=assets,
    )
    first_prediction = min(row["decision_date"] for row in predictions["matched_baseline"])
    period_tables, score_rows = {}, []
    variants = ("real", "label_shuffle", "random_features", "stale_1m", "stale_3m")
    for engine_name in program["feature_sets"]:
        for variant in variants:
            histories, _ = batch17.prediction_histories(predictions[engine_name], dataset, variant)
            for cost in (10.0, 50.0, 100.0):
                periods = [row for row in batch16.simulate(dates, assets, prices, histories, cost) if str(row["decision_date"]) >= first_prediction]
                period_tables[(engine_name, variant, cost)] = periods
                score_rows.append({
                    "engine": engine_name, "variant": variant, "cost_bps": cost,
                    **{f"full_{key}": value for key, value in metrics(periods).items()},
                    **{f"validation_{key}": value for key, value in metrics(periods, "2016-01-01", "2020-12-31").items()},
                    **{f"test_{key}": value for key, value in metrics(periods, "2021-01-01").items()},
                })
    ic_rows = {}
    for engine_name in program["feature_sets"]:
        for variant in variants:
            ic_rows[(engine_name, variant)] = [
                {**row, "engine": engine_name}
                for row in batch17.monthly_ics(predictions[engine_name], variant)
            ]
    settings = program["evaluation"]
    ic_evidence = {
        f"{engine}_{variant}": bootstrap_ic(
            ic_rows[(engine, variant)], seed=2026083400 + index,
            samples=int(settings["rank_ic_bootstrap_samples"]), block_months=int(settings["rank_ic_block_months"]), alpha=float(settings["one_sided_alpha"]),
        )
        for index, (engine, variant) in enumerate(ic_rows)
    }
    primary = {}
    for engine in program["feature_sets"]:
        primary[engine] = {
            cost: next(row for row in score_rows if row["engine"] == engine and row["variant"] == "real" and row["cost_bps"] == cost)
            for cost in (10.0, 50.0, 100.0)
        }
    paired = {
        cost: batch17.paired_bootstrap_advantage(
            [float(row["net_return"]) for row in period_tables[("mlquant_augmented", "real", cost)]],
            [float(row["net_return"]) for row in period_tables[("matched_baseline", "real", cost)]],
            seed=2026083410 + int(cost), samples=int(settings["paired_bootstrap_samples"]), block_weeks=int(settings["paired_bootstrap_block_weeks"]),
        ) for cost in (10.0, 50.0)
    }
    augmented_ic = ic_evidence["mlquant_augmented_real"]
    baseline_ic = ic_evidence["matched_baseline_real"]
    augmented10, augmented50, augmented100 = primary["mlquant_augmented"][10.0], primary["mlquant_augmented"][50.0], primary["mlquant_augmented"][100.0]
    baseline10, baseline50, baseline100 = primary["matched_baseline"][10.0], primary["matched_baseline"][50.0], primary["matched_baseline"][100.0]
    shuffle10 = next(row for row in score_rows if row["engine"] == "mlquant_augmented" and row["variant"] == "label_shuffle" and row["cost_bps"] == 10.0)
    random10 = next(row for row in score_rows if row["engine"] == "mlquant_augmented" and row["variant"] == "random_features" and row["cost_bps"] == 10.0)
    controls = augmented_ic["mean_rank_ic"] > max(ic_evidence["mlquant_augmented_label_shuffle"]["mean_rank_ic"], ic_evidence["mlquant_augmented_random_features"]["mean_rank_ic"]) and float(augmented10["full_sharpe_zero_rf"]) > max(float(shuffle10["full_sharpe_zero_rf"]), float(random10["full_sharpe_zero_rf"]))
    positive_fold_share = sum(float(row["real_mean_rank_ic"]) > 0.0 for row in folds["mlquant_augmented"]) / len(folds["mlquant_augmented"])
    gates = {
        "embargo": all(row["embargo_pass"].lower() == "true" for rows in folds.values() for row in rows),
        "rank_ic": augmented_ic["pass"] and augmented_ic["mean_rank_ic"] > baseline_ic["mean_rank_ic"],
        "portfolio_10bps": float(augmented10["full_sharpe_zero_rf"]) > float(baseline10["full_sharpe_zero_rf"]) and paired[10.0]["sharpe_advantage_statistically_positive"],
        "portfolio_50bps": float(augmented50["full_sharpe_zero_rf"]) > float(baseline50["full_sharpe_zero_rf"]),
        "drawdown": float(augmented10["full_max_drawdown"]) >= float(baseline10["full_max_drawdown"]) - 0.02,
        "stress": float(augmented100["validation_annual_return"]) > 0.0 and float(augmented100["test_annual_return"]) > 0.0 and float(augmented100["full_sharpe_zero_rf"]) >= float(baseline100["full_sharpe_zero_rf"]),
        "controls": controls, "fold_stability": positive_fold_share >= 0.60,
        "survivorship_safe_universe": False, "untouched_forward_52w": False,
    }
    historical = all(value for key, value in gates.items() if key not in {"survivorship_safe_universe", "untouched_forward_52w"})
    image = command(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Size}}"]).stdout.strip().split("|")
    result = {
        "program": program["program"], "program_sha256": sha256(PROGRAM), "dataset_audit": audit,
        "matched_dataset_sha256": sha256(INPUT), "source_snapshot_id": snapshot_id,
        "image": {"name": IMAGE, "id": image[0], "size_bytes": int(image[1])},
        "engine_metadata": engine_metadata, "weekly_data_audit": weekly_audit,
        "first_out_of_fold_decision": first_prediction, "rank_ic_evidence": ic_evidence,
        "positive_augmented_outer_fold_share": positive_fold_share,
        "primary_scorecards": primary, "paired_augmented_vs_baseline": {str(key): value for key, value in paired.items()},
        "negative_controls_pass": controls, "gates": gates,
        "historical_gates_passed": historical, "promoted": all(gates.values()),
        "frozen_files": frozen, "live_trading_enabled": False,
    }
    write_csv(OUTPUT / "portfolio_scoreboard.csv", score_rows)
    write_csv(OUTPUT / "monthly_rank_ic.csv", [row for values in ic_rows.values() for row in values])
    write_csv(OUTPUT / "augmented_real_returns_10bps.csv", period_tables[("mlquant_augmented", "real", 10.0)])
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Walk-forward ML repository-feature ablation — Batch 34", "",
        f"Both engines used {audit['matched_rows']:,} identical asset-month rows and {engine_metadata['mlquant_augmented']['outer_folds']} embargoed outer folds.", "",
        "| Model | Features | Mean rank IC | Return 10 bps | Sharpe 10 bps | Drawdown 10 bps | Sharpe 50 bps | Sharpe 100 bps |", "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name in program["feature_sets"]:
        row10, row50, row100 = primary[name][10.0], primary[name][50.0], primary[name][100.0]
        lines.append(f"| {name} | {len(program['feature_sets'][name])} | {float(ic_evidence[name + '_real']['mean_rank_ic']):.4f} | {float(row10['full_annual_return']):.2%} | {float(row10['full_sharpe_zero_rf']):.3f} | {float(row10['full_max_drawdown']):.2%} | {float(row50['full_sharpe_zero_rf']):.3f} | {float(row100['full_sharpe_zero_rf']):.3f} |")
    lines.extend(["", f"Paired 10-bps Sharpe lower difference: {float(paired[10.0]['one_sided_95pct_lower_sharpe_difference']):.3f}.",
        f"Historical gates passed: {historical}. Promoted: {all(gates.values())}.", "", "Live trading remains disabled.", ""])
    (OUTPUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    artifact_paths = [AUDIT, INPUT, *configs.values(), OUTPUT / "portfolio_scoreboard.csv", OUTPUT / "monthly_rank_ic.csv", OUTPUT / "augmented_real_returns_10bps.csv", OUTPUT / "result.json", OUTPUT / "report.md"]
    for directory in engine_dirs.values(): artifact_paths.extend(sorted(path for path in directory.iterdir() if path.is_file()))
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps({str(path.relative_to(OUTPUT)): sha256(path) for path in artifact_paths}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
