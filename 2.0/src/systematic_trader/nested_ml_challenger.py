"""Small auditable nested walk-forward ridge baseline for the ML track."""

from __future__ import annotations

import math
import random


def solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [matrix[row][:] + [vector[row]] for row in range(size)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        if abs(divisor) < 1e-12:
            divisor = 1e-12
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [left - factor * right for left, right in zip(augmented[row], augmented[column], strict=True)]
    return [augmented[row][-1] for row in range(size)]


def fit_ridge(features: list[list[float]], labels: list[float], penalty: float):
    columns = len(features[0])
    means = [sum(row[col] for row in features) / len(features) for col in range(columns)]
    scales = []
    for col in range(columns):
        variance = sum((row[col] - means[col]) ** 2 for row in features) / max(1, len(features) - 1)
        scales.append(math.sqrt(variance) if variance > 1e-16 else 1.0)
    normalized = [[(row[col] - means[col]) / scales[col] for col in range(columns)] for row in features]
    label_mean = sum(labels) / len(labels)
    centered = [value - label_mean for value in labels]
    gram = [[sum(row[a] * row[b] for row in normalized) for b in range(columns)] for a in range(columns)]
    for col in range(columns):
        gram[col][col] += penalty
    rhs = [sum(row[col] * label for row, label in zip(normalized, centered, strict=True)) for col in range(columns)]
    coefficients = solve_linear(gram, rhs)
    return {"means": means, "scales": scales, "label_mean": label_mean, "coefficients": coefficients}


def predict(model: dict[str, object], row: list[float]) -> float:
    means = model["means"]; scales = model["scales"]; coefficients = model["coefficients"]
    return float(model["label_mean"]) + sum(
        float(coef) * (value - float(mean)) / float(scale)
        for coef, value, mean, scale in zip(coefficients, row, means, scales, strict=True)
    )


def nested_walk_forward(
    dates: list[str], features: list[list[float]], labels: list[float],
    *, minimum_training: int = 260, test_weeks: int = 52,
    penalties: tuple[float, ...] = (0.01, 0.1, 1.0), shuffle: bool = False,
) -> tuple[dict[str, float], list[dict[str, object]]]:
    predictions: dict[str, float] = {}
    folds = []
    fold = 0
    for test_start in range(minimum_training, len(labels), test_weeks):
        train_end = test_start - 1  # one-row embargo; train labels end before the test decision
        if train_end < 104:
            continue
        validation_start = train_end - 52
        inner_train_end = validation_start - 1
        train_labels = labels[:inner_train_end]
        if shuffle:
            train_labels = train_labels[:]
            random.Random(20260809 + fold).shuffle(train_labels)
        scores = []
        for penalty in penalties:
            model = fit_ridge(features[:inner_train_end], train_labels, penalty)
            errors = [
                (predict(model, features[index]) - labels[index]) ** 2
                for index in range(validation_start, train_end)
            ]
            scores.append((sum(errors) / len(errors), penalty))
        chosen = min(scores)[1]
        outer_labels = labels[:train_end]
        if shuffle:
            outer_labels = outer_labels[:]
            random.Random(20260809 + fold).shuffle(outer_labels)
        model = fit_ridge(features[:train_end], outer_labels, chosen)
        end = min(len(labels), test_start + test_weeks)
        for index in range(test_start, end):
            predictions[dates[index]] = predict(model, features[index])
        folds.append({
            "fold": fold, "train_decision_end": dates[train_end - 1],
            "test_decision_start": dates[test_start], "test_decision_end": dates[end - 1],
            "chosen_penalty": chosen, "inner_trials": len(penalties), "shuffle": shuffle,
            "causal_embargo_pass": train_end - 1 < test_start,
        })
        fold += 1
    return predictions, folds
