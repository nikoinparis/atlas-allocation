#!/usr/bin/env python3
"""Pinned-container engine for nested cross-sectional ML research."""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import platform
from collections import defaultdict
from pathlib import Path

import numpy as np
import scipy
import sklearn
from scipy.stats import rankdata
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNet, Ridge
from sklearn.preprocessing import StandardScaler


FEATURES = (
    "momentum_4w", "momentum_13w", "momentum_26w", "momentum_52w_skip_4w",
    "moving_average_distance_13w", "moving_average_distance_26w",
    "volatility_13w", "volatility_26w", "downside_volatility_26w",
    "drawdown_26w", "positive_week_share_26w",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def centered_ranks(values: np.ndarray) -> np.ndarray:
    if len(values) <= 1:
        return np.zeros(len(values), dtype=float)
    return (rankdata(values, method="average") - 1.0) / (len(values) - 1.0) - 0.5


def prepare(rows: list[dict[str, str]]):
    raw_x = np.asarray([[float(row[name]) for name in FEATURES] for row in rows], dtype=float)
    raw_y = np.asarray([float(row["forward_4w_relative_return"]) for row in rows], dtype=float)
    x = np.empty_like(raw_x)
    y = np.empty_like(raw_y)
    by_decision: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        by_decision[row["decision_date"]].append(index)
    for indexes in by_decision.values():
        positions = np.asarray(indexes, dtype=int)
        for column in range(raw_x.shape[1]):
            x[positions, column] = centered_ranks(raw_x[positions, column])
        y[positions] = centered_ranks(raw_y[positions])
    date_counts = {day: len(indexes) for day, indexes in by_decision.items()}
    sample_weight = np.asarray([1.0 / date_counts[row["decision_date"]] for row in rows])
    return x, y, sample_weight, by_decision


def config_id(family: str, params: dict[str, object]) -> str:
    payload = json.dumps({"family": family, "params": params}, sort_keys=True, separators=(",", ":"))
    return family + "-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def configurations(config: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    families = config["model_families"]
    ridge = [{"alpha": value} for value in families["ridge"]["alpha"]]
    elastic = [
        {"alpha": alpha, "l1_ratio": ratio}
        for alpha, ratio in itertools.product(
            families["elastic_net"]["alpha"], families["elastic_net"]["l1_ratio"]
        )
    ]
    hist_keys = ("learning_rate", "max_iter", "max_leaf_nodes", "l2_regularization", "min_samples_leaf")
    hist = [
        dict(zip(hist_keys, values))
        for values in itertools.product(*(families["hist_gradient_boosting"][key] for key in hist_keys))
    ]
    return {"ridge": ridge, "elastic_net": elastic, "hist_gradient_boosting": hist}


def make_model(family: str, params: dict[str, object], seed: int):
    if family == "ridge":
        return Ridge(alpha=float(params["alpha"]))
    if family == "elastic_net":
        return ElasticNet(
            alpha=float(params["alpha"]), l1_ratio=float(params["l1_ratio"]),
            max_iter=10_000, tol=1e-6, selection="cyclic", random_state=seed,
        )
    if family == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(
            learning_rate=float(params["learning_rate"]), max_iter=int(params["max_iter"]),
            max_leaf_nodes=int(params["max_leaf_nodes"]),
            l2_regularization=float(params["l2_regularization"]),
            min_samples_leaf=int(params["min_samples_leaf"]), random_state=seed,
            early_stopping=False,
        )
    raise ValueError(f"unknown family {family}")


def fit_predict(
    family: str, params: dict[str, object], seed: int,
    x_train: np.ndarray, y_train: np.ndarray, weights: np.ndarray, x_test: np.ndarray,
) -> np.ndarray:
    scaler = StandardScaler()
    train = scaler.fit_transform(x_train)
    test = scaler.transform(x_test)
    model = make_model(family, params, seed)
    model.fit(train, y_train, sample_weight=weights)
    return model.predict(test)


def monthly_rank_ics(
    rows: list[dict[str, str]], global_indexes: list[int], predictions: np.ndarray, y: np.ndarray
) -> list[float]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for position, global_index in enumerate(global_indexes):
        grouped[rows[global_index]["decision_date"]].append(position)
    result = []
    for positions in grouped.values():
        pred = centered_ranks(predictions[np.asarray(positions)])
        actual = y[np.asarray([global_indexes[position] for position in positions])]
        if np.std(pred) <= 1e-15 or np.std(actual) <= 1e-15:
            result.append(0.0)
        else:
            result.append(float(np.corrcoef(pred, actual)[0, 1]))
    return result


def top_five_turnover(rows: list[dict[str, str]], global_indexes: list[int], predictions: np.ndarray) -> float:
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for position, global_index in enumerate(global_indexes):
        grouped[rows[global_index]["decision_date"]].append((rows[global_index]["asset"], float(predictions[position])))
    previous: set[str] | None = None
    values = []
    for day in sorted(grouped):
        current = {asset for asset, _ in sorted(grouped[day], key=lambda item: (item[1], item[0]), reverse=True)[:5]}
        if previous is not None:
            values.append(1.0 - len(current & previous) / 5.0)
        previous = current
    return float(np.mean(values)) if values else 0.0


def eligible_before(rows: list[dict[str, str]], test_start: str) -> list[int]:
    return [
        index for index, row in enumerate(rows)
        if row["decision_date"] < test_start and row["label_end_date"] < test_start
    ]


def year_indexes(rows: list[dict[str, str]], year: int) -> list[int]:
    prefix = str(year) + "-"
    return [index for index, row in enumerate(rows) if row["decision_date"].startswith(prefix)]


def randomized_labels(
    y_values: np.ndarray, rows: list[dict[str, str]], indexes: list[int], seed: int
) -> np.ndarray:
    result = y_values[np.asarray(indexes)].copy()
    rng = np.random.default_rng(seed)
    grouped: dict[str, list[int]] = defaultdict(list)
    for position, global_index in enumerate(indexes):
        grouped[rows[global_index]["decision_date"]].append(position)
    for positions in grouped.values():
        shuffled = result[np.asarray(positions)].copy()
        rng.shuffle(shuffled)
        result[np.asarray(positions)] = shuffled
    return result


def randomized_features(
    x_values: np.ndarray, rows: list[dict[str, str]], indexes: list[int], seed: int
) -> np.ndarray:
    result = x_values[np.asarray(indexes)].copy()
    rng = np.random.default_rng(seed)
    grouped: dict[str, list[int]] = defaultdict(list)
    for position, global_index in enumerate(indexes):
        grouped[rows[global_index]["decision_date"]].append(position)
    for positions in grouped.values():
        positions_array = np.asarray(positions)
        for column in range(result.shape[1]):
            shuffled = result[positions_array, column].copy()
            rng.shuffle(shuffled)
            result[positions_array, column] = shuffled
    return result


def stale_features(
    x_values: np.ndarray, rows: list[dict[str, str]], indexes: list[int], months: int
) -> tuple[np.ndarray, int]:
    decisions = sorted({row["decision_date"] for row in rows})
    decision_position = {day: index for index, day in enumerate(decisions)}
    lookup = {(row["decision_date"], row["asset"]): index for index, row in enumerate(rows)}
    result = []
    fallbacks = 0
    for global_index in indexes:
        row = rows[global_index]
        position = decision_position[row["decision_date"]] - months
        stale_index = lookup.get((decisions[position], row["asset"])) if position >= 0 else None
        if stale_index is None:
            stale_index = global_index
            fallbacks += 1
        result.append(x_values[stale_index])
    return np.asarray(result), fallbacks


def capped_family_weights(scores: dict[str, float], maximum: float = 0.6) -> dict[str, float]:
    positive = {family: max(score, 0.0) for family, score in scores.items()}
    if sum(positive.values()) <= 1e-15:
        result = {family: 1.0 / len(scores) for family in scores}
    else:
        result = {family: value / sum(positive.values()) for family, value in positive.items()}
    for _ in range(len(result)):
        excess = sum(max(0.0, value - maximum) for value in result.values())
        if excess <= 1e-12:
            break
        uncapped = [family for family, value in result.items() if value < maximum - 1e-12]
        for family in result:
            result[family] = min(result[family], maximum)
        basis = sum(result[family] for family in uncapped)
        if basis <= 1e-15:
            for family in uncapped:
                result[family] += excess / len(uncapped)
        else:
            for family in uncapped:
                result[family] += excess * result[family] / basis
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    rows = read_csv(Path(args.input))
    x, y, sample_weight, _ = prepare(rows)
    family_configs = configurations(config)
    seeds = [int(seed) for seed in config["ensemble"]["seeds"]]
    first_year = int(config["outer_walk_forward"]["first_test_year"])
    outer_years = sorted({int(row["decision_date"][:4]) for row in rows if int(row["decision_date"][:4]) >= first_year})
    trials: list[dict[str, object]] = []
    predictions_rows: list[dict[str, object]] = []
    fold_rows: list[dict[str, object]] = []
    fit_count = 0
    stale_fallbacks = {"one_month": 0, "three_month": 0}

    for outer_year in outer_years:
        test_start = f"{outer_year}-01-01"
        test_indexes = year_indexes(rows, outer_year)
        train_indexes = eligible_before(rows, test_start)
        if len({rows[index]["decision_date"] for index in train_indexes}) < 60 or not test_indexes:
            continue
        best_by_family: dict[str, tuple[dict[str, object], float]] = {}
        for family, configs in family_configs.items():
            for params in configs:
                fold_ics, fold_turnovers = [], []
                for validation_year in range(outer_year - 3, outer_year):
                    validation_start = f"{validation_year}-01-01"
                    inner_train = eligible_before(rows, validation_start)
                    validation = year_indexes(rows, validation_year)
                    if len({rows[index]["decision_date"] for index in inner_train}) < 36 or not validation:
                        continue
                    pred = fit_predict(
                        family, params, 17, x[np.asarray(inner_train)], y[np.asarray(inner_train)],
                        sample_weight[np.asarray(inner_train)], x[np.asarray(validation)],
                    )
                    fit_count += 1
                    fold_ics.extend(monthly_rank_ics(rows, validation, pred, y))
                    fold_turnovers.append(top_five_turnover(rows, validation, pred))
                mean_ic = float(np.mean(fold_ics)) if fold_ics else -1.0
                turnover = float(np.mean(fold_turnovers)) if fold_turnovers else 1.0
                score = mean_ic - 0.01 * turnover
                trial = {
                    "outer_year": outer_year, "family": family,
                    "config_id": config_id(family, params), "parameters": json.dumps(params, sort_keys=True),
                    "inner_months": len(fold_ics), "inner_mean_rank_ic": mean_ic,
                    "inner_top5_turnover_proxy": turnover, "selection_score": score,
                }
                trials.append(trial)
                if family not in best_by_family or (score, trial["config_id"]) > (
                    best_by_family[family][1], config_id(family, best_by_family[family][0])
                ):
                    best_by_family[family] = (params, score)

        family_weights = capped_family_weights({family: value[1] for family, value in best_by_family.items()})
        variant_by_family: dict[str, dict[str, np.ndarray]] = {}
        real_members_by_family: dict[str, list[np.ndarray]] = {}
        stale_one, fallback_one = stale_features(x, rows, test_indexes, 1)
        stale_three, fallback_three = stale_features(x, rows, test_indexes, 3)
        stale_fallbacks["one_month"] += fallback_one
        stale_fallbacks["three_month"] += fallback_three
        for family, (params, _) in best_by_family.items():
            per_variant: dict[str, list[np.ndarray]] = defaultdict(list)
            for seed in seeds:
                real = fit_predict(
                    family, params, seed, x[np.asarray(train_indexes)], y[np.asarray(train_indexes)],
                    sample_weight[np.asarray(train_indexes)], x[np.asarray(test_indexes)],
                )
                fit_count += 1
                shuffled_y = randomized_labels(y, rows, train_indexes, seed + outer_year * 1000)
                shuffle = fit_predict(
                    family, params, seed, x[np.asarray(train_indexes)], shuffled_y,
                    sample_weight[np.asarray(train_indexes)], x[np.asarray(test_indexes)],
                )
                fit_count += 1
                random_train = randomized_features(x, rows, train_indexes, seed + outer_year * 2000)
                random_test = randomized_features(x, rows, test_indexes, seed + outer_year * 3000)
                random_pred = fit_predict(
                    family, params, seed, random_train, y[np.asarray(train_indexes)],
                    sample_weight[np.asarray(train_indexes)], random_test,
                )
                fit_count += 1
                # The real model is also challenged with stale current inputs.
                scaler = StandardScaler().fit(x[np.asarray(train_indexes)])
                model = make_model(family, params, seed)
                model.fit(
                    scaler.transform(x[np.asarray(train_indexes)]), y[np.asarray(train_indexes)],
                    sample_weight=sample_weight[np.asarray(train_indexes)],
                )
                fit_count += 1
                per_variant["real"].append(real)
                per_variant["label_shuffle"].append(shuffle)
                per_variant["random_features"].append(random_pred)
                per_variant["stale_1m"].append(model.predict(scaler.transform(stale_one)))
                per_variant["stale_3m"].append(model.predict(scaler.transform(stale_three)))
            variant_by_family[family] = {
                variant: np.mean(np.vstack(values), axis=0) for variant, values in per_variant.items()
            }
            real_members_by_family[family] = list(per_variant["real"])

        variants = ("real", "label_shuffle", "random_features", "stale_1m", "stale_3m")
        ensemble = {
            variant: sum(family_weights[family] * variant_by_family[family][variant] for family in family_weights)
            for variant in variants
        }
        real_member_stack = np.vstack([
            prediction for family in family_weights for prediction in real_members_by_family[family]
        ])
        real_family_stack = np.vstack([variant_by_family[family]["real"] for family in family_weights])
        ensemble_sign = np.sign(ensemble["real"])
        sign_agreement = np.mean(np.sign(real_member_stack) == ensemble_sign[np.newaxis, :], axis=0)
        member_std = np.std(real_member_stack, axis=0)
        family_std = np.std(real_family_stack, axis=0)
        real_ics = monthly_rank_ics(rows, test_indexes, ensemble["real"], y)
        fold_rows.append({
            "outer_year": outer_year,
            "test_start": test_start,
            "maximum_training_decision_date": max(rows[index]["decision_date"] for index in train_indexes),
            "maximum_training_label_end_date": max(rows[index]["label_end_date"] for index in train_indexes),
            "embargo_pass": max(rows[index]["label_end_date"] for index in train_indexes) < test_start,
            "train_rows": len(train_indexes), "test_rows": len(test_indexes),
            "test_months": len({rows[index]["decision_date"] for index in test_indexes}),
            "real_mean_rank_ic": float(np.mean(real_ics)),
            "real_positive_month_share": sum(value > 0.0 for value in real_ics) / len(real_ics),
            "family_weights": json.dumps(family_weights, sort_keys=True),
            "selected_configs": json.dumps({family: config_id(family, params) for family, (params, _) in best_by_family.items()}, sort_keys=True),
        })
        for position, global_index in enumerate(test_indexes):
            predictions_rows.append({
                "outer_year": outer_year,
                "decision_date": rows[global_index]["decision_date"],
                "label_end_date": rows[global_index]["label_end_date"],
                "asset": rows[global_index]["asset"],
                "target_rank": y[global_index],
                **{f"prediction_{variant}": ensemble[variant][position] for variant in variants},
                "prediction_member_std_real": member_std[position],
                "prediction_family_std_real": family_std[position],
                "prediction_sign_agreement_real": sign_agreement[position],
            })
        print(json.dumps({"outer_year_complete": outer_year, "fits": fit_count, "real_mean_rank_ic": fold_rows[-1]["real_mean_rank_ic"]}), flush=True)

    write_csv(output / "predictions.csv", predictions_rows)
    write_csv(output / "inner_search_trials.csv", trials)
    write_csv(output / "outer_folds.csv", fold_rows)
    metadata = {
        "engine": "robust_cross_sectional_ml_container_v1",
        "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__, "scikit_learn": sklearn.__version__,
        "rows": len(rows), "features": list(FEATURES),
        "outer_folds": len(fold_rows), "inner_trial_rows": len(trials),
        "model_fit_count": fit_count, "seeds": seeds,
        "real_diagnostic_member_count": len(seeds) * len(family_configs),
        "variants": ["real", "label_shuffle", "random_features", "stale_1m", "stale_3m"],
        "stale_feature_fallbacks": stale_fallbacks,
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
