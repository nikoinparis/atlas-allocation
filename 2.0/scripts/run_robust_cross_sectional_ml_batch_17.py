#!/usr/bin/env python3
"""Orchestrate isolated nested ML, common portfolio accounting, and promotion gates."""

from __future__ import annotations

import csv
import argparse
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
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_cross_sectional_factor_baseline_batch_16 as batch16
from scripts.run_treasury_term_structure_batch_14 import frozen_winner_returns
from src.systematic_trader.cross_sectional_factors import capped_inverse_volatility_weights
from src.systematic_trader.data_vintage import SnapshotStore, parse_utc, sha256
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.ml_protocol import promotion_gates
from src.systematic_trader.term_structure_challenger import correlation
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

IMAGE = "localhost/po2-robust-ml:sklearn-1.9.0-v1"
PROGRAM = ROOT / "config/robust_cross_sectional_ml_v1.json"
INPUT = ROOT / "evidence/cross_sectional_factor_baseline_batch_16/factor_dataset.csv"
OUTPUT = ROOT / "evidence/robust_cross_sectional_ml_batch_17"
STORE = ROOT / "data/vintages"
UNIVERSE = ROOT / "config/free_etf_universe.json"
VARIANTS = ("real", "label_shuffle", "random_features", "stale_1m", "stale_3m")
COSTS = (10.0, 50.0, 100.0)
BOOTSTRAP_SAMPLES = 20_000
BOOTSTRAP_BLOCK_MONTHS = 3


def command(args: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(args[:4])}\n{result.stderr}\n{result.stdout}")
    return result


def image_metadata() -> dict[str, str]:
    result = command(["podman", "image", "inspect", IMAGE, "--format", "{{.Id}}|{{.Digest}}"])
    image_id, _, digest = result.stdout.strip().partition("|")
    return {"image": IMAGE, "image_id": image_id, "repo_digest": digest}


def run_isolated(destination: Path) -> None:
    name = "po2-robust-ml-" + uuid.uuid4().hex[:12]
    created = False
    try:
        command([
            "podman", "create", "--name", name, IMAGE,
            "--input", "/input.csv", "--config", "/config.json", "--output", "/output",
        ])
        created = True
        command(["podman", "cp", str(INPUT), f"{name}:/input.csv"])
        command(["podman", "cp", str(PROGRAM), f"{name}:/config.json"])
        start = command(["podman", "start", "--attach", name], capture=False, check=False)
        if start.returncode != 0:
            raise RuntimeError(f"isolated ML engine failed with exit code {start.returncode}")
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
        writer.writerows(rows)


def latest_free_manifest() -> dict[str, object]:
    items = [item for item in SnapshotStore(STORE).manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    return max(items, key=lambda item: str(item["observed_at_utc"]))


def prediction_histories(
    prediction_rows: list[dict[str, str]], dataset_rows: list[dict[str, str]], variant: str,
) -> tuple[dict[str, dict[str, float]], list[dict[str, object]]]:
    volatility = {(row["decision_date"], row["asset"]): float(row["volatility_26w"]) for row in dataset_rows}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in prediction_rows:
        grouped[row["decision_date"]].append(row)
    histories = {}
    holdings = []
    field = f"prediction_{variant}"
    for decision in sorted(grouped):
        rows = grouped[decision]
        selected = sorted(rows, key=lambda row: (float(row[field]), row["asset"]), reverse=True)[:5]
        assets = [row["asset"] for row in selected]
        weights = capped_inverse_volatility_weights(
            assets, {asset: volatility[(decision, asset)] for asset in assets}, 0.35
        )
        histories[decision] = weights
        scores = {row["asset"]: float(row[field]) for row in selected}
        for asset in assets:
            holdings.append({
                "variant": variant, "decision_date": decision, "asset": asset,
                "prediction": scores[asset], "weight": weights[asset],
            })
    return histories, holdings


def metrics(periods: list[dict[str, object]], start: str = "0000", end: str = "9999") -> dict[str, float | int]:
    selected = [row for row in periods if start <= str(row["realization_date"]) <= end]
    result = performance_metrics([float(row["net_return"]) for row in selected]).to_dict()
    result["annual_turnover"] = statistics.fmean(float(row["turnover"]) for row in selected) * 52.0
    return result


def monthly_ics(predictions: list[dict[str, str]], variant: str) -> list[dict[str, object]]:
    field = f"prediction_{variant}"
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in predictions:
        grouped[row["decision_date"]].append(row)
    result = []
    for decision in sorted(grouped):
        rows = grouped[decision]
        prediction = [float(row[field]) for row in rows]
        target = [float(row["target_rank"]) for row in rows]
        result.append({
            "variant": variant, "decision_date": decision, "assets": len(rows),
            "rank_ic": correlation(prediction, target) if statistics.pstdev(prediction) > 1e-15 else 0.0,
        })
    return result


def bootstrap_ic(rows: list[dict[str, object]], alpha: float) -> dict[str, float | int | bool]:
    values = [float(row["rank_ic"]) for row in rows]
    generator = random.Random(20260809)
    means = []
    for _ in range(BOOTSTRAP_SAMPLES):
        sample = []
        while len(sample) < len(values):
            start = generator.randrange(len(values))
            sample.extend(values[(start + offset) % len(values)] for offset in range(BOOTSTRAP_BLOCK_MONTHS))
        means.append(statistics.fmean(sample[:len(values)]))
    ordered = sorted(means)
    lower = ordered[math.floor(alpha * (len(ordered) - 1))]
    return {
        "months": len(values), "mean_rank_ic": statistics.fmean(values),
        "positive_month_share": sum(value > 0.0 for value in values) / len(values),
        "bootstrap_samples": BOOTSTRAP_SAMPLES, "block_months": BOOTSTRAP_BLOCK_MONTHS,
        "one_sided_alpha": alpha, "lower_mean_rank_ic": lower, "pass": lower > 0.0,
    }


def winner_common_metrics(winner: dict[str, float], start: str, end: str = "9999") -> dict[str, float | int]:
    values = [value for day, value in sorted(winner.items()) if start <= day <= end]
    return performance_metrics(values).to_dict()


def paired_bootstrap_advantage(
    challenger: list[float], benchmark: list[float], *, seed: int, samples: int = 20_000, block_weeks: int = 13,
) -> dict[str, float | int | bool]:
    if len(challenger) != len(benchmark) or not challenger:
        raise ValueError("paired bootstrap requires equal non-empty returns")
    generator = random.Random(seed)
    sharpe_differences = []
    return_differences = []
    length = len(challenger)
    for _ in range(samples):
        indexes = []
        while len(indexes) < length:
            start = generator.randrange(length)
            indexes.extend((start + offset) % length for offset in range(block_weeks))
        indexes = indexes[:length]
        left = [challenger[index] for index in indexes]
        right = [benchmark[index] for index in indexes]
        left_metrics = performance_metrics(left)
        right_metrics = performance_metrics(right)
        sharpe_differences.append(left_metrics.sharpe_zero_rf - right_metrics.sharpe_zero_rf)
        return_differences.append(left_metrics.annual_return - right_metrics.annual_return)
    lower_index = math.floor(0.05 * (samples - 1))
    sharpe_ordered = sorted(sharpe_differences)
    return_ordered = sorted(return_differences)
    return {
        "observations": length, "samples": samples, "block_weeks": block_weeks,
        "mean_sharpe_difference": statistics.fmean(sharpe_differences),
        "one_sided_95pct_lower_sharpe_difference": sharpe_ordered[lower_index],
        "mean_annual_return_difference": statistics.fmean(return_differences),
        "one_sided_95pct_lower_annual_return_difference": return_ordered[lower_index],
        "sharpe_advantage_statistically_positive": sharpe_ordered[lower_index] > 0.0,
        "annual_return_advantage_statistically_positive": return_ordered[lower_index] > 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-engine-output", action="store_true")
    args = parser.parse_args()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    if not INPUT.is_file():
        raise RuntimeError("Batch 16 factor dataset is missing")
    with tempfile.TemporaryDirectory() as temporary:
        engine_output = Path(temporary) / "engine"
        if args.reuse_engine_output:
            engine_output.mkdir(parents=True)
            for name in ("metadata.json", "predictions.csv", "inner_search_trials.csv", "outer_folds.csv"):
                shutil.copyfile(OUTPUT / name, engine_output / name)
        else:
            run_isolated(engine_output)
        metadata = json.loads((engine_output / "metadata.json").read_text(encoding="utf-8"))
        predictions = read_csv(engine_output / "predictions.csv")
        folds = read_csv(engine_output / "outer_folds.csv")
        if not predictions or not all(row["embargo_pass"].lower() == "true" for row in folds):
            raise RuntimeError("ML output is empty or an outer-fold embargo failed")

        dataset_rows = read_csv(INPUT)
        manifest = latest_free_manifest()
        snapshot_id = str(manifest["snapshot_id"])
        assets = sorted(json.loads(UNIVERSE.read_text(encoding="utf-8"))["symbols"])
        dates, prices, weekly_audit = prepare_weekly_adjusted_prices(
            STORE / snapshot_id / "payload/prices.csv",
            observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
            start_date=date(2004, 1, 2), expected_symbols=assets,
        )
        first_prediction = min(row["decision_date"] for row in predictions)
        period_tables = {}
        holdings_rows = []
        score_rows = []
        for variant in VARIANTS:
            histories, holdings = prediction_histories(predictions, dataset_rows, variant)
            holdings_rows.extend(holdings)
            for cost in COSTS:
                periods = batch16.simulate(dates, assets, prices, histories, cost)
                periods = [row for row in periods if str(row["decision_date"]) >= first_prediction]
                period_tables[(variant, cost)] = periods
                score_rows.append({
                    "variant": variant, "cost_bps": cost,
                    **{f"full_{key}": value for key, value in metrics(periods).items()},
                    **{f"oos_2016_2020_{key}": value for key, value in metrics(periods, "2016-01-01", "2020-12-31").items()},
                    **{f"oos_2021_present_{key}": value for key, value in metrics(periods, "2021-01-01").items()},
                })

        # Recompute the locked fixed baseline under the exact ML common period.
        _, by_decision, _ = batch16.build_dataset(dates, assets, prices)
        fixed_histories, _, _ = batch16.decision_weights(by_decision, json.loads(batch16.PROGRAM.read_text(encoding="utf-8")))
        for cost in COSTS:
            periods = [row for row in batch16.simulate(dates, assets, prices, fixed_histories, cost) if str(row["decision_date"]) >= first_prediction]
            period_tables[("fixed_factor_baseline", cost)] = periods
            score_rows.append({
                "variant": "fixed_factor_baseline", "cost_bps": cost,
                **{f"full_{key}": value for key, value in metrics(periods).items()},
                **{f"oos_2016_2020_{key}": value for key, value in metrics(periods, "2016-01-01", "2020-12-31").items()},
                **{f"oos_2021_present_{key}": value for key, value in metrics(periods, "2021-01-01").items()},
            })

        winner = frozen_winner_returns()
        winner_metrics = winner_common_metrics(winner, first_prediction)
        real_periods = period_tables[("real", 10.0)]
        common = [(float(row["net_return"]), winner[str(row["realization_date"])]) for row in real_periods if str(row["realization_date"]) in winner]
        dependence = correlation([value[0] for value in common], [value[1] for value in common])
        fixed_by_date = {str(row["realization_date"]): float(row["net_return"]) for row in period_tables[("fixed_factor_baseline", 10.0)]}
        common_fixed = [
            (float(row["net_return"]), fixed_by_date[str(row["realization_date"])])
            for row in real_periods if str(row["realization_date"]) in fixed_by_date
        ]
        paired_uncertainty = {
            "versus_frozen_winner": paired_bootstrap_advantage(
                [value[0] for value in common], [value[1] for value in common], seed=20260817,
            ),
            "versus_fixed_factor": paired_bootstrap_advantage(
                [value[0] for value in common_fixed], [value[1] for value in common_fixed], seed=20260818,
            ),
        }
        ic_rows = {variant: monthly_ics(predictions, variant) for variant in VARIANTS}
        ic_evidence = {
            variant: bootstrap_ic(rows, 0.05 / 3.0 if variant == "real" else 0.05)
            for variant, rows in ic_rows.items()
        }
        real_10 = next(row for row in score_rows if row["variant"] == "real" and row["cost_bps"] == 10.0)
        real_100 = next(row for row in score_rows if row["variant"] == "real" and row["cost_bps"] == 100.0)
        fixed_10 = next(row for row in score_rows if row["variant"] == "fixed_factor_baseline" and row["cost_bps"] == 10.0)
        shuffle_10 = next(row for row in score_rows if row["variant"] == "label_shuffle" and row["cost_bps"] == 10.0)
        random_10 = next(row for row in score_rows if row["variant"] == "random_features" and row["cost_bps"] == 10.0)
        controls_pass = (
            float(ic_evidence["real"]["mean_rank_ic"]) > max(float(ic_evidence[name]["mean_rank_ic"]) for name in ("label_shuffle", "random_features"))
            and float(real_10["full_sharpe_zero_rf"]) > max(float(shuffle_10["full_sharpe_zero_rf"]), float(random_10["full_sharpe_zero_rf"]))
        )
        positive_fold_share = sum(float(row["real_mean_rank_ic"]) > 0.0 for row in folds) / len(folds)
        gates = promotion_gates(
            rank_ic_pass=bool(ic_evidence["real"]["pass"]),
            beats_fixed=float(real_10["full_sharpe_zero_rf"]) > float(fixed_10["full_sharpe_zero_rf"]),
            beats_winner=float(real_10["full_sharpe_zero_rf"]) > float(winner_metrics["sharpe_zero_rf"]),
            drawdown_pass=float(real_10["full_max_drawdown"]) >= float(winner_metrics["max_drawdown"]),
            later_cost_pass=float(real_100["oos_2016_2020_annual_return"]) > 0.0 and float(real_100["oos_2021_present_annual_return"]) > 0.0,
            dependence_pass=abs(dependence) <= 0.75,
            controls_pass=controls_pass,
            fold_stability_pass=positive_fold_share >= 0.60,
            survivorship_safe=False, forward_weeks=0,
        )
        result = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "batch": 17, "track": "robust_cross_sectional_ml",
            "program_sha256": sha256(PROGRAM), "input_dataset_sha256": sha256(INPUT),
            "implementation_sha256": {
                "container_engine": sha256(ROOT / "containers/robust_cross_sectional_ml.py"),
                "containerfile": sha256(ROOT / "config/images/robust-ml-sklearn-1.9.Containerfile"),
                "requirements_lock": sha256(ROOT / "config/robust_ml_requirements.lock"),
                "host_orchestrator": sha256(ROOT / "scripts/run_robust_cross_sectional_ml_batch_17.py"),
                "promotion_protocol": sha256(ROOT / "src/systematic_trader/ml_protocol.py"),
            },
            "source_snapshot_id": snapshot_id, "image": image_metadata(),
            "engine_metadata": metadata, "weekly_data_audit": weekly_audit,
            "first_out_of_fold_decision": first_prediction,
            "rank_ic_evidence": ic_evidence,
            "positive_outer_fold_rank_ic_share": positive_fold_share,
            "correlation_to_frozen_winner_10bps": dependence,
            "correlation_observations": len(common),
            "frozen_winner_common_period_metrics_10bps": winner_metrics,
            "paired_bootstrap_advantage_10bps": paired_uncertainty,
            "negative_controls_pass": controls_pass,
            "promotion_gates": gates,
            "promoted": gates["all"], "live_trading_approved": False,
            "limitations": [
                "Outer predictions are chronological and embargoed but remain retrospective because the overall program was designed after the history existed.",
                "The current ETF universe is survivorship-prone and not a historical membership database.",
                "The free adjusted-price snapshot may contain pre-acquisition revisions.",
                "Thousands of fits increase search power and therefore require the nested folds and adjusted uncertainty gate; computation alone is not evidence of alpha.",
            ],
        }
        OUTPUT.mkdir(parents=True, exist_ok=True)
        for path in engine_output.iterdir():
            shutil.copyfile(path, OUTPUT / path.name)
        write_csv(OUTPUT / "portfolio_scoreboard.csv", score_rows)
        write_csv(OUTPUT / "holdings.csv", holdings_rows)
        write_csv(OUTPUT / "monthly_rank_ic.csv", [row for variant in VARIANTS for row in ic_rows[variant]])
        write_csv(OUTPUT / "real_returns_10bps.csv", real_periods)
        report = "\n".join([
            "# Robust Cross-Sectional ML — Batch 17", "",
            f"The isolated engine completed **{metadata['model_fit_count']:,} model fits** across **{metadata['outer_folds']} embargoed outer folds**, three model families, five seeds, and four adversarial/staleness controls.", "",
            f"Real ML at 10 bps: **{float(real_10['full_annual_return']) * 100:.2f}%** annual return, **{float(real_10['full_sharpe_zero_rf']):.3f}** Sharpe, **{float(real_10['full_max_drawdown']) * 100:.2f}%** maximum drawdown, and **{float(real_10['full_annual_turnover']):.2f}** annual turnover.", "",
            f"Fixed factor common-period Sharpe: **{float(fixed_10['full_sharpe_zero_rf']):.3f}**. Frozen winner common-period Sharpe: **{float(winner_metrics['sharpe_zero_rf']):.3f}**.", "",
            f"ML maximum drawdown: **{float(real_10['full_max_drawdown']) * 100:.2f}%** versus frozen winner **{float(winner_metrics['max_drawdown']) * 100:.2f}%**; safety gate passed: **{gates['maximum_drawdown']}**.", "",
            f"Paired-bootstrap Sharpe advantage over the winner was statistically positive: **{paired_uncertainty['versus_frozen_winner']['sharpe_advantage_statistically_positive']}**; lower Sharpe-difference bound **{float(paired_uncertainty['versus_frozen_winner']['one_sided_95pct_lower_sharpe_difference']):.3f}**.", "",
            f"Adjusted mean rank IC: **{float(ic_evidence['real']['mean_rank_ic']):.4f}**; lower bound **{float(ic_evidence['real']['lower_mean_rank_ic']):.4f}**; gate passed: **{ic_evidence['real']['pass']}**.", "",
            f"Correlation to frozen winner: **{dependence:.3f}**. Positive outer-fold rank-IC share: **{positive_fold_share * 100:.1f}%**. Negative controls passed: **{controls_pass}**.", "",
            f"Promotion: **{gates['all']}**. Failed gates remain explicit in `result.json`; no execution or live trading was enabled.", "",
        ])
        (OUTPUT / "report.md").write_text(report, encoding="utf-8")
        result["artifacts"] = {
            path.name: {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in OUTPUT.iterdir() if path.is_file() and path.name != "result.json"
        }
        (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "model_fits": metadata["model_fit_count"], "outer_folds": metadata["outer_folds"],
            "annual_return_10bps": real_10["full_annual_return"], "sharpe_10bps": real_10["full_sharpe_zero_rf"],
            "max_drawdown_10bps": real_10["full_max_drawdown"], "adjusted_rank_ic_pass": ic_evidence["real"]["pass"],
            "correlation_to_winner": dependence, "negative_controls_pass": controls_pass,
            "promotion": gates["all"],
        }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
