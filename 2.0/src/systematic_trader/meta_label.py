"""Causal secondary correctness model for fixed primary predictions."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LogisticModel:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def fit_logistic_correctness(
    features: Sequence[Sequence[float]], labels: Sequence[int], *,
    iterations: int = 400, learning_rate: float = 0.05, l2: float = 1.0,
) -> LogisticModel:
    rows = [[float(value) for value in row] for row in features]
    outcomes = [int(value) for value in labels]
    if len(rows) != len(outcomes) or len(rows) < 20 or not rows:
        raise ValueError("matching features and at least 20 labels are required")
    width = len(rows[0])
    if width < 1 or any(len(row) != width for row in rows) or any(value not in {0, 1} for value in outcomes):
        raise ValueError("rectangular features and binary labels required")
    means = [statistics.fmean(row[column] for row in rows) for column in range(width)]
    scales = []
    for column in range(width):
        values = [row[column] for row in rows]
        scales.append(max(statistics.pstdev(values), 1e-8))
    standardized = [[(row[column] - means[column]) / scales[column] for column in range(width)] for row in rows]
    coefficients = [0.0] * width
    base_rate = min(1.0 - 1e-6, max(1e-6, statistics.fmean(outcomes)))
    intercept = math.log(base_rate / (1.0 - base_rate))
    count = len(rows)
    for _ in range(iterations):
        probabilities = [_sigmoid(intercept + sum(weight * value for weight, value in zip(coefficients, row))) for row in standardized]
        intercept -= learning_rate * statistics.fmean(probability - label for probability, label in zip(probabilities, outcomes))
        for column in range(width):
            gradient = sum(
                (probability - label) * row[column]
                for probability, label, row in zip(probabilities, outcomes, standardized)
            ) / count + l2 * coefficients[column] / count
            coefficients[column] -= learning_rate * gradient
    return LogisticModel(tuple(means), tuple(scales), tuple(coefficients), intercept)


def correctness_probabilities(model: LogisticModel, features: Sequence[Sequence[float]]) -> list[float]:
    result = []
    for raw in features:
        if len(raw) != len(model.coefficients):
            raise ValueError("feature width differs from fitted model")
        row = [(float(value) - mean) / scale for value, mean, scale in zip(raw, model.means, model.scales)]
        result.append(_sigmoid(model.intercept + sum(weight * value for weight, value in zip(model.coefficients, row))))
    return result


def classification_metrics(labels: Sequence[int], selected: Sequence[bool]) -> dict[str, float | int]:
    outcomes = [int(value) for value in labels]
    decisions = [bool(value) for value in selected]
    if len(outcomes) != len(decisions) or not outcomes:
        raise ValueError("matching non-empty labels and decisions required")
    true_positive = sum(label == 1 and decision for label, decision in zip(outcomes, decisions))
    false_positive = sum(label == 0 and decision for label, decision in zip(outcomes, decisions))
    false_negative = sum(label == 1 and not decision for label, decision in zip(outcomes, decisions))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "observations": len(outcomes),
        "selected": sum(decisions),
        "coverage": sum(decisions) / len(outcomes),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "base_correctness_rate": statistics.fmean(outcomes),
    }
