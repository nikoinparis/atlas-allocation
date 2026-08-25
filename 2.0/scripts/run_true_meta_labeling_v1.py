#!/usr/bin/env python3
"""Test a true secondary correctness label before any portfolio pass-through."""

from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.meta_label import (  # noqa: E402
    classification_metrics,
    correctness_probabilities,
    fit_logistic_correctness,
)


CONFIG = ROOT / "config/true_meta_labeling_v1.json"
OUTPUT = ROOT / "evidence/true_meta_labeling_v1"


def _features(row: dict[str, str]) -> list[float]:
    prediction = float(row["prediction_real"])
    return [
        abs(prediction),
        1.0 if prediction >= 0.0 else -1.0,
        float(row["prediction_member_std_real"]),
        float(row["prediction_family_std_real"]),
        float(row["prediction_sign_agreement_real"]),
    ]


def _label(row: dict[str, str]) -> int:
    return int(float(row["prediction_real"]) * float(row["target_rank"]) > 0.0)


def build() -> tuple[dict[str, object], list[dict[str, object]]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = ROOT / str(config["prediction_source"])
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    start_year = int(config["outer_test_start_year"])
    threshold = float(config["selection_probability_threshold"])
    embargo = timedelta(days=int(config["embargo_days"]))
    predictions: list[dict[str, object]] = []
    folds: list[dict[str, object]] = []
    for year in sorted({int(row["outer_year"]) for row in rows if int(row["outer_year"]) >= start_year}):
        test_start = date(year, 1, 1)
        cutoff = test_start - embargo
        train = [row for row in rows if date.fromisoformat(row["label_end_date"]) <= cutoff]
        test = [row for row in rows if int(row["outer_year"]) == year]
        train_features = [_features(row) for row in train]
        train_labels = [_label(row) for row in train]
        test_features = [_features(row) for row in test]
        test_labels = [_label(row) for row in test]
        model = fit_logistic_correctness(train_features, train_labels)
        real_probabilities = correctness_probabilities(model, test_features)
        generator = random.Random(10_000 + year)
        shuffled = list(train_labels)
        generator.shuffle(shuffled)
        shuffled_model = fit_logistic_correctness(train_features, shuffled)
        shuffled_probabilities = correctness_probabilities(shuffled_model, test_features)
        random_train = [[generator.gauss(0.0, 1.0) for _ in range(5)] for _ in train]
        random_test = [[generator.gauss(0.0, 1.0) for _ in range(5)] for _ in test]
        random_model = fit_logistic_correctness(random_train, train_labels)
        random_probabilities = correctness_probabilities(random_model, random_test)
        fold_real = classification_metrics(test_labels, [value >= threshold for value in real_probabilities])
        folds.append({
            "outer_year": year,
            "train_rows": len(train),
            "test_rows": len(test),
            "maximum_training_label_end_date": max(row["label_end_date"] for row in train),
            "embargo_pass": max(date.fromisoformat(row["label_end_date"]) for row in train) <= cutoff,
            **fold_real,
        })
        for row, label, real, shuffle, random_probability in zip(
            test, test_labels, real_probabilities, shuffled_probabilities, random_probabilities
        ):
            predictions.append({
                "outer_year": year,
                "decision_date": row["decision_date"],
                "label_end_date": row["label_end_date"],
                "asset": row["asset"],
                "primary_correct": label,
                "meta_probability": real,
                "selected": real >= threshold,
                "label_shuffle_probability": shuffle,
                "random_feature_probability": random_probability,
            })
    labels = [int(row["primary_correct"]) for row in predictions]
    real = classification_metrics(labels, [bool(row["selected"]) for row in predictions])
    take_all = classification_metrics(labels, [True] * len(labels))
    shuffle = classification_metrics(
        labels, [float(row["label_shuffle_probability"]) >= threshold for row in predictions]
    )
    random_control = classification_metrics(
        labels, [float(row["random_feature_probability"]) >= threshold for row in predictions]
    )
    precision_improvement = float(real["precision"]) - float(take_all["precision"])
    control_best = max(float(shuffle["precision"]), float(random_control["precision"]))
    gate = (
        precision_improvement >= float(config["minimum_precision_improvement"])
        and float(real["coverage"]) >= float(config["minimum_coverage"])
        and float(real["precision"]) - control_best >= float(config["negative_control_precision_margin"])
        and all(bool(fold["embargo_pass"]) for fold in folds)
    )
    result = {
        "program": config["program"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "secondary_label_is_primary_correctness": True,
        "directional_alpha_retrained": False,
        "outer_fold_count": len(folds),
        "folds": folds,
        "take_all_primary": take_all,
        "true_meta_label": real,
        "deterministic_label_shuffle": shuffle,
        "deterministic_random_features": random_control,
        "precision_improvement": precision_improvement,
        "classification_gate_pass": gate,
        "portfolio_backtest_run": False,
        "portfolio_backtest_block_reason": (
            "classification_gate_failed" if not gate else "requires_separately_predeclared_pass_through_after_classification_result"
        ),
        "promotion_authorized": False,
        "live_trading_enabled": False,
        "verdict": "CLASSIFICATION_PASS_RESEARCH_ONLY" if gate else "REJECTED_CLASSIFICATION_GATE",
        "limitations": [
            "The primary ETF ML model was itself rejected and is used only to distinguish true meta-labeling from prior confidence overlays.",
            "No return was optimized and no portfolio backtest is run unless the classification gate passes.",
            "All history is retrospectively visible to the project owner; this is not untouched forward evidence.",
        ],
    }
    return result, predictions


def main() -> int:
    result, predictions = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(predictions[0]))
        writer.writeheader()
        writer.writerows(predictions)
    result["predictions_sha256"] = hashlib.sha256((OUTPUT / "predictions.csv").read_bytes()).hexdigest()
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = (
        "# True Meta-Labeling V1\n\n"
        f"Verdict: **{result['verdict']}**. Out-of-sample precision changed from "
        f"{result['take_all_primary']['precision']:.3f} to {result['true_meta_label']['precision']:.3f}; "
        f"coverage was {result['true_meta_label']['coverage']:.3f} and F1 was {result['true_meta_label']['f1']:.3f}.\n\n"
        "The secondary label is primary-model correctness. No directional model was retrained and no return was used as the fitting objective.\n"
    )
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "verdict", "take_all_primary", "true_meta_label", "deterministic_label_shuffle",
        "deterministic_random_features", "classification_gate_pass", "portfolio_backtest_run",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
