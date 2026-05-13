#!/usr/bin/env python3
"""
Phase MLX-3: run tabular ML models for the experimental hard-ML lab.

This is research-only infrastructure. It reads Phase MLX feature/target panels,
uses train-only preprocessing statistics, writes outputs under data/research/ml_lab,
and does not modify production pins, dashboard code, strategy logic, or candidates.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "tabular_ml"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"

PREDICTIONS_OUT = OUTPUT_DIR / "ml_tabular_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "ml_tabular_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "ml_tabular_summary.csv"
FEATURE_IMPORTANCE_OUT = OUTPUT_DIR / "ml_tabular_feature_importance.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "ml_tabular_preprocessing_metadata.json"
SKIPPED_MODELS_OUT = OUTPUT_DIR / "ml_tabular_skipped_models.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_tabular_ml_notes.md"

DEFAULT_COST_BPS = 10.0
RANDOM_STATE = 42
TOP_N_VALUES = (3, 5, 10)
CLASSIFICATION_TARGETS = ("top_quintile_forward_4w", "beats_SPY_4w", "positive_forward_4w")
REGRESSION_TARGETS = ("forward_return_4w",)
TARGET_COLUMNS = (
    "forward_return_4w",
    "forward_return_13w",
    "forward_rank_4w",
    "forward_rank_13w",
    "beats_SPY_4w",
    "beats_BIL_4w",
    "positive_forward_4w",
    "top_quintile_forward_4w",
)


@dataclass
class ModelSpec:
    model_key: str
    display_name: str
    task: str
    feature_view: str
    package: str
    estimator: Any


def warn(message: str, warnings_list: list[str]) -> None:
    warnings_list.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def compact_error(exc: Exception, max_len: int = 500) -> str:
    text = " ".join(str(exc).split())
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def split_name_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    date_series = pd.Series(pd.to_datetime(dates), index=getattr(dates, "index", None))
    split = pd.Series("unassigned", index=date_series.index, dtype="object")
    split.loc[date_series <= pd.Timestamp("2017-12-31")] = "train"
    split.loc[(date_series >= pd.Timestamp("2018-01-01")) & (date_series <= pd.Timestamp("2019-12-31"))] = "validation"
    split.loc[date_series >= pd.Timestamp("2020-01-01")] = "holdout"
    return split


def load_inputs(warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [str(path) for path in [FEATURES_IN, TARGETS_IN] if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-2 input(s) missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    if features.empty:
        warn("Feature panel is empty.", warnings_list)
    if targets.empty:
        warn("Target panel is empty.", warnings_list)
    return features, targets


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame, warnings_list: list[str]) -> None:
    required_ids = {"Date", "ticker"}
    missing_feature_ids = sorted(required_ids - set(features.columns))
    missing_target_ids = sorted(required_ids - set(targets.columns))
    if missing_feature_ids or missing_target_ids:
        raise ValueError(f"Missing identifiers. features={missing_feature_ids}, targets={missing_target_ids}")

    feature_keys = features[["Date", "ticker"]].sort_values(["Date", "ticker"]).reset_index(drop=True)
    target_keys = targets[["Date", "ticker"]].sort_values(["Date", "ticker"]).reset_index(drop=True)
    if len(feature_keys) != len(target_keys) or not feature_keys.equals(target_keys):
        raise ValueError("Feature rows do not align with target rows on Date/ticker.")

    leaked_targets = sorted(set(TARGET_COLUMNS) & set(features.columns))
    if leaked_targets:
        raise ValueError(f"Target columns are present in features: {leaked_targets}")

    suspicious = []
    for col in features.columns:
        lower = col.lower()
        if col in {"Date", "ticker", "target_vol_multiplier"}:
            continue
        if (
            lower.startswith("forward_")
            or lower.startswith("future_")
            or lower.startswith("next_")
            or "forward_return" in lower
            or "forward_rank" in lower
            or lower.startswith("beats_")
            or lower.startswith("top_quintile")
            or lower.startswith("positive_forward")
            or lower.endswith("_label")
        ):
            suspicious.append(col)
    if suspicious:
        raise ValueError(f"Obvious future/target leakage feature columns found: {suspicious}")


def build_model_specs(skipped: list[dict[str, str]]) -> list[ModelSpec]:
    try:
        from sklearn.ensemble import (
            GradientBoostingClassifier,
            GradientBoostingRegressor,
            RandomForestClassifier,
            RandomForestRegressor,
        )
        from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
    except ImportError as exc:
        raise ImportError("scikit-learn is required for MLX-3 tabular models and was not importable.") from exc

    specs: list[ModelSpec] = [
        ModelSpec("ridge_regression", "Ridge regression", "regression", "standardized", "sklearn", Ridge(alpha=10.0)),
        ModelSpec(
            "elasticnet_regression",
            "ElasticNet regression",
            "regression",
            "standardized",
            "sklearn",
            ElasticNet(alpha=0.0005, l1_ratio=0.20, max_iter=10000, random_state=RANDOM_STATE),
        ),
        ModelSpec(
            "random_forest_regressor",
            "Random Forest regressor",
            "regression",
            "filled",
            "sklearn",
            RandomForestRegressor(
                n_estimators=80,
                max_depth=7,
                min_samples_leaf=50,
                n_jobs=-1,
                random_state=RANDOM_STATE,
            ),
        ),
        ModelSpec(
            "gradient_boosting_regressor",
            "Gradient Boosting regressor",
            "regression",
            "filled",
            "sklearn",
            GradientBoostingRegressor(
                n_estimators=120,
                learning_rate=0.04,
                max_depth=2,
                subsample=0.80,
                random_state=RANDOM_STATE,
            ),
        ),
        ModelSpec(
            "logistic_regression",
            "Logistic Regression",
            "classification",
            "standardized",
            "sklearn",
            LogisticRegression(
                penalty="l2",
                C=0.50,
                max_iter=2000,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            ),
        ),
        ModelSpec(
            "random_forest_classifier",
            "Random Forest classifier",
            "classification",
            "filled",
            "sklearn",
            RandomForestClassifier(
                n_estimators=100,
                max_depth=7,
                min_samples_leaf=50,
                n_jobs=-1,
                class_weight="balanced_subsample",
                random_state=RANDOM_STATE,
            ),
        ),
        ModelSpec(
            "gradient_boosting_classifier",
            "Gradient Boosting classifier",
            "classification",
            "filled",
            "sklearn",
            GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.04,
                max_depth=2,
                subsample=0.80,
                random_state=RANDOM_STATE,
            ),
        ),
    ]

    if importlib.util.find_spec("xgboost") is None:
        for target in REGRESSION_TARGETS + CLASSIFICATION_TARGETS:
            skipped.append(
                {
                    "model_key": "xgboost",
                    "target": target,
                    "reason": "xgboost package is not installed; skipped without installing packages",
                }
            )
    else:
        try:
            from xgboost import XGBClassifier, XGBRegressor  # type: ignore
        except Exception as exc:
            reason = f"xgboost package was found but could not be imported/loaded: {type(exc).__name__}: {compact_error(exc)}"
            for target in REGRESSION_TARGETS + CLASSIFICATION_TARGETS:
                skipped.append({"model_key": "xgboost", "target": target, "reason": reason})
        else:
            specs.extend(
                [
                    ModelSpec(
                        "xgboost_regressor",
                        "XGBoost regressor",
                        "regression",
                        "filled",
                        "xgboost",
                        XGBRegressor(
                            n_estimators=160,
                            max_depth=3,
                            learning_rate=0.035,
                            subsample=0.80,
                            colsample_bytree=0.80,
                            objective="reg:squarederror",
                            random_state=RANDOM_STATE,
                            n_jobs=2,
                        ),
                    ),
                    ModelSpec(
                        "xgboost_classifier",
                        "XGBoost classifier",
                        "classification",
                        "filled",
                        "xgboost",
                        XGBClassifier(
                            n_estimators=160,
                            max_depth=3,
                            learning_rate=0.035,
                            subsample=0.80,
                            colsample_bytree=0.80,
                            eval_metric="logloss",
                            random_state=RANDOM_STATE,
                            n_jobs=2,
                        ),
                    ),
                ]
            )

    if importlib.util.find_spec("lightgbm") is None:
        for target in REGRESSION_TARGETS + CLASSIFICATION_TARGETS:
            skipped.append(
                {
                    "model_key": "lightgbm",
                    "target": target,
                    "reason": "lightgbm package is not installed; skipped without installing packages",
                }
            )
    else:
        try:
            from lightgbm import LGBMClassifier, LGBMRegressor  # type: ignore
        except Exception as exc:
            reason = f"lightgbm package was found but could not be imported/loaded: {type(exc).__name__}: {compact_error(exc)}"
            for target in REGRESSION_TARGETS + CLASSIFICATION_TARGETS:
                skipped.append({"model_key": "lightgbm", "target": target, "reason": reason})
        else:
            specs.extend(
                [
                    ModelSpec(
                        "lightgbm_regressor",
                        "LightGBM regressor",
                        "regression",
                        "filled",
                        "lightgbm",
                        LGBMRegressor(
                            n_estimators=160,
                            max_depth=4,
                            learning_rate=0.035,
                            subsample=0.80,
                            colsample_bytree=0.80,
                            random_state=RANDOM_STATE,
                            n_jobs=2,
                            verbose=-1,
                        ),
                    ),
                    ModelSpec(
                        "lightgbm_classifier",
                        "LightGBM classifier",
                        "classification",
                        "filled",
                        "lightgbm",
                        LGBMClassifier(
                            n_estimators=160,
                            max_depth=4,
                            learning_rate=0.035,
                            subsample=0.80,
                            colsample_bytree=0.80,
                            random_state=RANDOM_STATE,
                            n_jobs=2,
                            verbose=-1,
                        ),
                    ),
                ]
            )
    return specs


def prepare_feature_matrices(features: pd.DataFrame, split: pd.Series) -> dict[str, Any]:
    identifier_cols = ["Date", "ticker"]
    numeric_feature_cols = [
        col
        for col in features.columns
        if col not in identifier_cols and pd.api.types.is_numeric_dtype(features[col])
    ]
    excluded_cols = [col for col in features.columns if col not in identifier_cols + numeric_feature_cols]

    x_raw = features[numeric_feature_cols].replace([np.inf, -np.inf], np.nan)
    train_mask = split.eq("train")
    train_medians = x_raw.loc[train_mask].median(numeric_only=True).fillna(0.0)
    x_filled = x_raw.fillna(train_medians).fillna(0.0)
    train_means = x_filled.loc[train_mask].mean(numeric_only=True)
    train_stds = x_filled.loc[train_mask].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    x_standardized = (x_filled - train_means) / train_stds

    return {
        "numeric_feature_cols": numeric_feature_cols,
        "excluded_cols": excluded_cols,
        "x_filled": x_filled,
        "x_standardized": x_standardized,
        "train_medians": train_medians.to_dict(),
        "train_means": train_means.to_dict(),
        "train_stds": train_stds.to_dict(),
        "feature_missing_rate": x_raw.isna().mean().to_dict(),
    }


def prediction_score(estimator: Any, task: str, x: pd.DataFrame) -> np.ndarray:
    if task == "regression":
        return np.asarray(estimator.predict(x), dtype=float)
    if hasattr(estimator, "predict_proba"):
        proba = estimator.predict_proba(x)
        if proba.ndim == 2 and proba.shape[1] > 1:
            return np.asarray(proba[:, 1], dtype=float)
        return np.asarray(proba.ravel(), dtype=float)
    if hasattr(estimator, "decision_function"):
        raw = np.asarray(estimator.decision_function(x), dtype=float)
        return 1.0 / (1.0 + np.exp(-raw))
    return np.asarray(estimator.predict(x), dtype=float)


def collect_importance(estimator: Any, model_name: str, target: str, feature_cols: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if hasattr(estimator, "coef_"):
        coef = np.asarray(estimator.coef_)
        if coef.ndim > 1:
            coef = coef[0]
        for feature, value in zip(feature_cols, coef):
            rows.append(
                {
                    "model_name": model_name,
                    "target": target,
                    "feature": feature,
                    "importance": float(value),
                    "abs_importance": float(abs(value)),
                    "importance_type": "coefficient_standardized_features",
                }
            )
    elif hasattr(estimator, "feature_importances_"):
        for feature, value in zip(feature_cols, np.asarray(estimator.feature_importances_)):
            rows.append(
                {
                    "model_name": model_name,
                    "target": target,
                    "feature": feature,
                    "importance": float(value),
                    "abs_importance": float(abs(value)),
                    "importance_type": "feature_importance",
                }
            )
    return rows


def fit_models(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    split: pd.Series,
    prepared: dict[str, Any],
    warnings_list: list[str],
    skipped: list[dict[str, str]],
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    specs = build_model_specs(skipped)
    predictions: list[pd.DataFrame] = []
    importance_rows: list[dict[str, Any]] = []
    models_run: list[str] = []

    target_map: dict[str, tuple[str, ...]] = {
        "regression": REGRESSION_TARGETS,
        "classification": CLASSIFICATION_TARGETS,
    }
    x_lookup = {
        "filled": prepared["x_filled"],
        "standardized": prepared["x_standardized"],
    }
    ids = features[["Date", "ticker"]].copy()
    ids["split"] = split.values

    for spec in specs:
        for target in target_map[spec.task]:
            model_name = f"{spec.model_key}__{target}"
            if spec.task == "regression" and target not in REGRESSION_TARGETS:
                continue
            if spec.task == "classification" and target not in CLASSIFICATION_TARGETS:
                continue
            y = targets[target]
            train_mask = split.eq("train") & y.notna()
            if spec.task == "classification":
                y_train = y.loc[train_mask].astype(int)
                if y_train.nunique() < 2:
                    reason = "classification target has fewer than two classes in train split"
                    warn(f"Skipping {model_name}: {reason}", warnings_list)
                    skipped.append({"model_key": spec.model_key, "target": target, "reason": reason})
                    continue
            else:
                y_train = y.loc[train_mask].astype(float)
                if y_train.notna().sum() < 100:
                    reason = "regression target has fewer than 100 non-null train rows"
                    warn(f"Skipping {model_name}: {reason}", warnings_list)
                    skipped.append({"model_key": spec.model_key, "target": target, "reason": reason})
                    continue

            x_matrix = x_lookup[spec.feature_view]
            estimator = spec.estimator
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                estimator.fit(x_matrix.loc[train_mask], y_train)
                for item in caught:
                    warn(f"{model_name} fit warning: {item.message}", warnings_list)

            score = prediction_score(estimator, spec.task, x_matrix)
            pred = ids.copy()
            pred["model_name"] = model_name
            pred["model_key"] = spec.model_key
            pred["target"] = target
            pred["task"] = spec.task
            pred["score"] = score
            predictions.append(pred)
            importance_rows.extend(
                collect_importance(estimator, model_name, target, prepared["numeric_feature_cols"])
            )
            models_run.append(model_name)

    if not predictions:
        warn("No tabular models were run successfully.", warnings_list)
        return pd.DataFrame(columns=["Date", "ticker", "split", "model_name", "model_key", "target", "task", "score"]), pd.DataFrame(), models_run

    prediction_panel = pd.concat(predictions, ignore_index=True)
    importance = pd.DataFrame(importance_rows)
    if not importance.empty:
        importance = importance.sort_values(["model_name", "abs_importance"], ascending=[True, False])
    return prediction_panel, importance, models_run


def next_week_return_panel(features: pd.DataFrame) -> pd.DataFrame:
    tmp = features[["Date", "ticker", "trailing_return_1w"]].copy()
    tmp = tmp.sort_values(["ticker", "Date"])
    tmp["next_week_return"] = tmp.groupby("ticker")["trailing_return_1w"].shift(-1)
    return tmp.pivot(index="Date", columns="ticker", values="next_week_return").sort_index()


def feature_matrix_by_date(features: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in features.columns:
        return pd.DataFrame()
    return features.pivot(index="Date", columns="ticker", values=column).sort_index()


def weights_from_scores(
    score_table: pd.DataFrame,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    top_n: int,
    weighting: str,
    next_returns: pd.DataFrame,
    vol_panel: pd.DataFrame | None,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        available_returns = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        eligible = group[["ticker", "score"]].dropna()
        eligible = eligible[eligible["ticker"].map(available_returns.notna()).fillna(False)]
        if eligible.empty:
            continue
        chosen = eligible.sort_values("score", ascending=False).head(top_n)["ticker"].tolist()
        if not chosen:
            continue
        if weighting == "inverse_vol" and vol_panel is not None and not vol_panel.empty and date in vol_panel.index:
            vol = vol_panel.reindex(index=[date], columns=chosen).iloc[0].replace([np.inf, -np.inf], np.nan)
            inv = 1.0 / vol.where(vol > 0.0)
            if inv.notna().sum() > 0 and inv.sum(skipna=True) > 0:
                w = inv.fillna(0.0) / inv.fillna(0.0).sum()
            else:
                w = pd.Series(1.0 / len(chosen), index=chosen)
        else:
            w = pd.Series(1.0 / len(chosen), index=chosen)
        weights.loc[date, w.index] = w.values
    return weights


def weights_for_static_baseline(
    name: str,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    next_returns: pd.DataFrame,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    if name == "baseline_spy_buy_hold":
        if "SPY" in tickers:
            weights["SPY"] = next_returns["SPY"].notna().astype(float)
        return weights
    if name == "baseline_60_40_spy_ief_or_agg":
        bond = "IEF" if "IEF" in tickers else "AGG" if "AGG" in tickers else None
        if "SPY" in tickers and bond:
            weights["SPY"] = next_returns["SPY"].notna().astype(float) * 0.60
            weights[bond] = next_returns[bond].notna().astype(float) * 0.40
        return weights
    if name == "baseline_equal_weight_all_etfs":
        eligible = next_returns.notna().reindex(index=dates, columns=tickers).fillna(False)
        counts = eligible.sum(axis=1).replace(0, np.nan)
        weights = eligible.astype(float).div(counts, axis=0).fillna(0.0)
        return weights
    return weights


def compute_path(weights: pd.DataFrame, next_returns: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    aligned_returns = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned_returns.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (cost_bps / 10000.0)
    net = gross - cost
    holdings = weights.gt(0.0).sum(axis=1)
    return pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "holdings_count": holdings,
        },
        index=weights.index,
    )


def max_drawdown(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return np.nan
    wealth = (1.0 + clean).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return float(drawdown.min())


def calc_metrics(path: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if returns.empty:
        return {
            "annual_return": np.nan,
            "annual_volatility": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "cvar_5": np.nan,
            "average_turnover": np.nan,
            "annual_cost_drag": np.nan,
            "average_number_of_etfs_held": np.nan,
            "weeks": 0,
        }
    wealth = (1.0 + returns).cumprod()
    if wealth.iloc[-1] > 0:
        annual_return = float(wealth.iloc[-1] ** (52.0 / len(returns)) - 1.0)
    else:
        annual_return = np.nan
    annual_vol = float(returns.std(ddof=0) * math.sqrt(52.0))
    sharpe = float(annual_return / annual_vol) if annual_vol and annual_vol > 0 else np.nan
    mdd = max_drawdown(returns)
    calmar = float(annual_return / abs(mdd)) if pd.notna(mdd) and mdd < 0 else np.nan
    q5 = returns.quantile(0.05)
    cvar = float(returns[returns <= q5].mean()) if pd.notna(q5) else np.nan
    turnover = pd.to_numeric(path.get("turnover", pd.Series(dtype=float)), errors="coerce")
    cost = pd.to_numeric(path.get("cost", pd.Series(dtype=float)), errors="coerce")
    holdings = pd.to_numeric(path.get("holdings_count", pd.Series(dtype=float)), errors="coerce")
    return {
        "annual_return": annual_return,
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": calmar,
        "cvar_5": cvar,
        "average_turnover": float(turnover.reindex(returns.index).mean()) if not turnover.empty else np.nan,
        "annual_cost_drag": float(cost.reindex(returns.index).mean() * 52.0) if not cost.empty else np.nan,
        "average_number_of_etfs_held": float(holdings.reindex(returns.index).mean()) if not holdings.empty else np.nan,
        "weeks": int(len(returns)),
    }


def split_path(path: pd.DataFrame) -> pd.DataFrame:
    out = path.copy()
    out["Date"] = out.index
    out["split"] = split_name_for_dates(out["Date"]).values
    return out


def append_strategy_results(
    all_returns: list[pd.DataFrame],
    summary_rows: list[dict[str, Any]],
    path: pd.DataFrame,
    strategy_name: str,
    strategy_type: str,
    split_values: tuple[str, ...],
    model_name: str | None = None,
    target: str | None = None,
    top_n: int | None = None,
    weighting: str | None = None,
    cost_bps: float = DEFAULT_COST_BPS,
) -> None:
    dated = split_path(path)
    dated["strategy_name"] = strategy_name
    dated["strategy_type"] = strategy_type
    dated["model_name"] = model_name or ""
    dated["target"] = target or ""
    dated["top_n"] = top_n if top_n is not None else np.nan
    dated["weighting"] = weighting or ""
    dated["cost_bps"] = cost_bps
    all_returns.append(dated.reset_index(drop=True))

    for split_value in split_values:
        metrics = calc_metrics(dated.loc[dated["split"].eq(split_value)])
        metrics.update(
            {
                "strategy_name": strategy_name,
                "strategy_type": strategy_type,
                "model_name": model_name or "",
                "target": target or "",
                "top_n": top_n if top_n is not None else np.nan,
                "weighting": weighting or "",
                "split": split_value,
                "cost_bps": cost_bps,
            }
        )
        summary_rows.append(metrics)


def run_portfolio_simulations(
    features: pd.DataFrame,
    predictions: pd.DataFrame,
    warnings_list: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    tickers = sorted(features["ticker"].unique())
    split_values = ("train", "validation", "holdout")
    next_returns = next_week_return_panel(features).reindex(index=dates, columns=tickers)
    vol_panel = feature_matrix_by_date(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = feature_matrix_by_date(features, "realized_vol_26w")
    if vol_panel.empty:
        warn("No realized_vol_13w or realized_vol_26w found; inverse-vol portfolios will fall back to equal weight.", warnings_list)

    all_returns: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for model_name, group in predictions.groupby("model_name", sort=True):
        model_target = str(group["target"].iloc[0])
        for top_n in TOP_N_VALUES:
            for weighting in ("equal_weight", "inverse_vol"):
                weights = weights_from_scores(
                    group,
                    dates=dates,
                    tickers=tickers,
                    top_n=top_n,
                    weighting=weighting,
                    next_returns=next_returns,
                    vol_panel=vol_panel if not vol_panel.empty else None,
                )
                path = compute_path(weights, next_returns, DEFAULT_COST_BPS)
                strategy_name = f"{model_name}__top{top_n}__{weighting}"
                append_strategy_results(
                    all_returns,
                    summary_rows,
                    path,
                    strategy_name=strategy_name,
                    strategy_type="model",
                    split_values=split_values,
                    model_name=model_name,
                    target=model_target,
                    top_n=top_n,
                    weighting=weighting,
                )

    for baseline_name in (
        "baseline_spy_buy_hold",
        "baseline_60_40_spy_ief_or_agg",
        "baseline_equal_weight_all_etfs",
    ):
        weights = weights_for_static_baseline(baseline_name, dates, tickers, next_returns)
        if weights.sum(axis=1).sum() == 0:
            warn(f"Baseline {baseline_name} could not be built from available ETF returns.", warnings_list)
            continue
        path = compute_path(weights, next_returns, DEFAULT_COST_BPS)
        append_strategy_results(
            all_returns,
            summary_rows,
            path,
            strategy_name=baseline_name,
            strategy_type="baseline",
            split_values=split_values,
        )

    momentum_col = "momentum_12_1" if "momentum_12_1" in features.columns else "trailing_return_26w"
    if momentum_col in features.columns:
        score_table = features[["Date", "ticker", momentum_col]].rename(columns={momentum_col: "score"})
        for top_n in TOP_N_VALUES:
            for weighting in ("equal_weight", "inverse_vol"):
                weights = weights_from_scores(
                    score_table,
                    dates=dates,
                    tickers=tickers,
                    top_n=top_n,
                    weighting=weighting,
                    next_returns=next_returns,
                    vol_panel=vol_panel if not vol_panel.empty else None,
                )
                path = compute_path(weights, next_returns, DEFAULT_COST_BPS)
                strategy_name = f"baseline_top_momentum_{momentum_col}__top{top_n}__{weighting}"
                append_strategy_results(
                    all_returns,
                    summary_rows,
                    path,
                    strategy_name=strategy_name,
                    strategy_type="baseline_momentum",
                    split_values=split_values,
                    top_n=top_n,
                    weighting=weighting,
                )
    else:
        warn("No momentum_12_1 or trailing_return_26w column found; momentum baselines skipped.", warnings_list)

    external_meta = append_external_project_baselines(all_returns, summary_rows, split_values, warnings_list)
    returns_df = pd.concat(all_returns, ignore_index=True) if all_returns else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return returns_df, summary, external_meta


def read_project_return_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    if "net_return" not in df.columns and "gross_return" in df.columns:
        df["net_return"] = df["gross_return"]
    if "gross_return" not in df.columns and "net_return" in df.columns:
        df["gross_return"] = df["net_return"]
    if "turnover" not in df.columns:
        df["turnover"] = np.nan
    if "cost" not in df.columns:
        df["cost"] = np.nan
    if "holdings_count" not in df.columns:
        df["holdings_count"] = np.nan
    return df[["gross_return", "net_return", "turnover", "cost", "holdings_count"]]


def append_external_project_baselines(
    all_returns: list[pd.DataFrame],
    summary_rows: list[dict[str, Any]],
    split_values: tuple[str, ...],
    warnings_list: list[str],
) -> dict[str, Any]:
    candidates = {
        "project_current_production_or_rollback_phase2b": ROOT
        / "data"
        / "05_layer3_portfolio_construction"
        / "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
        "project_official_shadow_phase2b_combo_abc": ROOT
        / "data"
        / "05_layer3_portfolio_construction"
        / "portfolio_version_returns_improved_phase2b_combo_abc.csv",
        "project_production_candidate_ggg1": ROOT
        / "data"
        / "05_layer3_portfolio_construction"
        / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    }
    loaded: list[str] = []
    missing: list[str] = []
    for name, path in candidates.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            warn(f"Optional project baseline missing: {path}", warnings_list)
            continue
        try:
            path_df = read_project_return_file(path)
        except Exception as exc:
            missing.append(str(path.relative_to(ROOT)))
            warn(f"Optional project baseline unreadable: {path} ({exc})", warnings_list)
            continue
        append_strategy_results(
            all_returns,
            summary_rows,
            path_df,
            strategy_name=name,
            strategy_type="project_baseline",
            split_values=split_values,
            cost_bps=DEFAULT_COST_BPS,
        )
        loaded.append(str(path.relative_to(ROOT)))
    return {"loaded": loaded, "missing_or_unreadable": missing}


def best_row(summary: pd.DataFrame, split: str, strategy_types: tuple[str, ...]) -> dict[str, Any] | None:
    if summary.empty:
        return None
    subset = summary[summary["split"].eq(split) & summary["strategy_type"].isin(strategy_types)].copy()
    subset = subset[pd.to_numeric(subset["sharpe"], errors="coerce").notna()]
    if subset.empty:
        return None
    row = subset.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
    return row.to_dict()


def compare_holdout(summary: pd.DataFrame) -> dict[str, Any]:
    holdout_models = summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model"))].copy()
    comparisons: dict[str, Any] = {}
    if holdout_models.empty:
        return comparisons
    best_model_sharpe = pd.to_numeric(holdout_models["sharpe"], errors="coerce").max()

    def baseline_sharpe(strategy_filter: pd.Series) -> float:
        subset = summary[summary["split"].eq("holdout") & strategy_filter].copy()
        return float(pd.to_numeric(subset["sharpe"], errors="coerce").max()) if not subset.empty else np.nan

    momentum = baseline_sharpe(summary["strategy_type"].eq("baseline_momentum"))
    spy = baseline_sharpe(summary["strategy_name"].eq("baseline_spy_buy_hold"))
    balanced = baseline_sharpe(summary["strategy_name"].eq("baseline_60_40_spy_ief_or_agg"))
    production = baseline_sharpe(summary["strategy_name"].eq("project_current_production_or_rollback_phase2b"))
    shadow = baseline_sharpe(summary["strategy_name"].eq("project_official_shadow_phase2b_combo_abc"))

    comparisons["best_model_holdout_sharpe"] = float(best_model_sharpe)
    comparisons["best_momentum_holdout_sharpe"] = momentum
    comparisons["spy_holdout_sharpe"] = spy
    comparisons["sixty_forty_holdout_sharpe"] = balanced
    comparisons["production_holdout_sharpe"] = production
    comparisons["shadow_holdout_sharpe"] = shadow
    comparisons["any_model_beats_simple_momentum_holdout_by_sharpe"] = bool(pd.notna(momentum) and best_model_sharpe > momentum)
    comparisons["any_model_beats_spy_holdout_by_sharpe"] = bool(pd.notna(spy) and best_model_sharpe > spy)
    comparisons["any_model_beats_60_40_holdout_by_sharpe"] = bool(pd.notna(balanced) and best_model_sharpe > balanced)
    comparisons["any_model_beats_production_holdout_by_sharpe"] = bool(pd.notna(production) and best_model_sharpe > production)
    comparisons["any_model_beats_shadow_holdout_by_sharpe"] = bool(pd.notna(shadow) and best_model_sharpe > shadow)
    return comparisons


def write_notes(
    models_run: list[str],
    skipped: list[dict[str, str]],
    summary: pd.DataFrame,
    comparisons: dict[str, Any],
    warnings_list: list[str],
) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    best_train = best_row(summary, "train", ("model",))
    best_validation = best_row(summary, "validation", ("model",))
    best_holdout = best_row(summary, "holdout", ("model",))
    best_holdout_return = None
    holdout_models = summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model"))].copy()
    if not holdout_models.empty:
        best_holdout_return = holdout_models.sort_values("annual_return", ascending=False).iloc[0].to_dict()

    def fmt_row(row: dict[str, Any] | None) -> str:
        if not row:
            return "not available"
        return (
            f"{row.get('strategy_name')} "
            f"(Sharpe {row.get('sharpe'):.3f}, annual return {row.get('annual_return'):.3%})"
        )

    skipped_lines = "\n".join(
        f"- {item['model_key']} on {item['target']}: {item['reason']}" for item in skipped
    ) or "- None"
    model_lines = "\n".join(f"- {name}" for name in models_run) or "- None"
    warning_lines = "\n".join(f"- {message}" for message in warnings_list) or "- None"

    NOTES_OUT.write_text(
        f"""# Phase MLX Tabular ML Notes

Phase MLX-3 is experimental, research-only, not production-valid, and high overfitting risk. No model in this folder is promoted automatically or suitable for live trading decisions.

## Data Source Warning

Inputs are `data/research/ml_lab/feature_panel/ml_feature_panel.parquet` and `data/research/ml_lab/feature_panel/ml_targets.parquet`, derived from the Phase MLX expanded ETF universe. The upstream ETF data is `yfinance` research data and the expanded universe introduces selection-bias and data-mining risk. Stock breadth prototype features, when present, are survivorship-biased research diagnostics.

## Split Definitions

- Train: dates through 2017-12-31
- Validation: 2018-01-01 through 2019-12-31
- Holdout: 2020-01-01 onward

Preprocessing medians, means, and standard deviations are fit on the train split only.

## Models Run

{model_lines}

## Models Skipped

{skipped_lines}

## Target Definitions

- Regression: `forward_return_4w`
- Classification: `top_quintile_forward_4w`, `beats_SPY_4w`, and auxiliary `positive_forward_4w`

Forward labels remain in the target parquet only and are not model features.

## Backtest Assumptions

Model scores are converted into weekly ETF rankings. Each week tests top 3, top 5, and top 10 equal-weight and inverse-volatility portfolios. Realized next-week returns are derived from `trailing_return_1w` shifted one week forward by ticker. Transaction costs use the project-style 10 bps per unit turnover assumption. This remains an approximate research simulation, not a production allocator.

## Baseline Comparison

Baselines include SPY buy-and-hold, 60/40 SPY/IEF or SPY/AGG, equal-weight all available ETFs, top momentum ETFs using `momentum_12_1`, inverse-vol top momentum, and available project production/shadow/candidate return files.

## Best Models

- Best train model by Sharpe: {fmt_row(best_train)}
- Best validation model by Sharpe: {fmt_row(best_validation)}
- Best holdout model by Sharpe: {fmt_row(best_holdout)}
- Best holdout model by annual return: {fmt_row(best_holdout_return)}

## Holdout Read

- Any model beats simple momentum on holdout by Sharpe: {comparisons.get('any_model_beats_simple_momentum_holdout_by_sharpe')}
- Any model beats SPY on holdout by Sharpe: {comparisons.get('any_model_beats_spy_holdout_by_sharpe')}
- Any model beats 60/40 on holdout by Sharpe: {comparisons.get('any_model_beats_60_40_holdout_by_sharpe')}
- Any model beats production on holdout by Sharpe: {comparisons.get('any_model_beats_production_holdout_by_sharpe')}
- Any model beats official shadow on holdout by Sharpe: {comparisons.get('any_model_beats_shadow_holdout_by_sharpe')}

## Warnings

{warning_lines}

## Interpretation

Treat any validation or holdout win as a hypothesis, not evidence of deployability. The search space includes many ETFs, targets, model classes, feature transforms, and portfolio construction choices, so overfitting and multiple-testing risk are high. MLX-3 is useful as ML/AI/data-science infrastructure and as a disciplined research benchmark, not as a production strategy.
""",
        encoding="utf-8",
    )


def main() -> int:
    warnings_list: list[str] = []
    skipped: list[dict[str, str]] = []
    print("Phase MLX-3 tabular ML model runner")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")

    features, targets = load_inputs(warnings_list)
    validate_inputs(features, targets, warnings_list)

    features = features.sort_values(["Date", "ticker"]).reset_index(drop=True)
    targets = targets.sort_values(["Date", "ticker"]).reset_index(drop=True)
    split = split_name_for_dates(features["Date"])

    prepared = prepare_feature_matrices(features, split)
    predictions, feature_importance, models_run = fit_models(
        features, targets, split, prepared, warnings_list, skipped
    )
    backtest_returns, summary, external_meta = run_portfolio_simulations(features, predictions, warnings_list)
    comparisons = compare_holdout(summary)
    write_notes(models_run, skipped, summary, comparisons, warnings_list)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    backtest_returns.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    if feature_importance.empty:
        feature_importance = pd.DataFrame(
            columns=["model_name", "target", "feature", "importance", "abs_importance", "importance_type"]
        )
    feature_importance.to_csv(FEATURE_IMPORTANCE_OUT, index=False)
    SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default) + "\n", encoding="utf-8")

    split_ranges = {}
    for name in ("train", "validation", "holdout"):
        date_values = features.loc[split.eq(name), "Date"]
        split_ranges[name] = {
            "start": date_values.min().date().isoformat() if not date_values.empty else None,
            "end": date_values.max().date().isoformat() if not date_values.empty else None,
            "rows": int(split.eq(name).sum()),
            "dates": int(date_values.nunique()),
        }

    preprocessing_metadata = {
        "phase": "MLX-3 tabular ML models",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "no_live_trading_decisions": True,
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_existing_candidates_replaced": True,
        "inputs": {
            "features": str(FEATURES_IN.relative_to(ROOT)),
            "targets": str(TARGETS_IN.relative_to(ROOT)),
        },
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "feature_importance": str(FEATURE_IMPORTANCE_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "skipped_models": str(SKIPPED_MODELS_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
        "split_ranges": split_ranges,
        "feature_panel_shape": list(features.shape),
        "target_shape": list(targets.shape),
        "number_of_etfs": int(features["ticker"].nunique()),
        "number_of_dates": int(features["Date"].nunique()),
        "numeric_feature_count": len(prepared["numeric_feature_cols"]),
        "numeric_features": prepared["numeric_feature_cols"],
        "excluded_non_numeric_columns": prepared["excluded_cols"],
        "train_only_preprocessing": {
            "median_fill_values": prepared["train_medians"],
            "standardization_means": prepared["train_means"],
            "standardization_stds": prepared["train_stds"],
            "feature_missing_rate": prepared["feature_missing_rate"],
        },
        "models_run": models_run,
        "models_skipped": skipped,
        "cost_assumption": {
            "cost_bps_per_unit_turnover": DEFAULT_COST_BPS,
            "source": "Project convention found in Layer 2A/Layer 3 notebooks: DEFAULT_COST_BPS = 10",
        },
        "backtest_return_construction": (
            "Realized next-week ETF returns are derived from trailing_return_1w shifted one week forward by ticker."
        ),
        "external_project_baselines": external_meta,
        "holdout_comparisons": comparisons,
        "warnings": warnings_list
        + [
            "Experimental research-only Phase MLX output; not production-valid.",
            "No model is promoted automatically.",
            "Expanded ETF model testing has high overfitting, selection-bias, and data-mining risk.",
        ],
    }
    PREPROCESSING_METADATA_OUT.write_text(
        json.dumps(preprocessing_metadata, indent=2, default=json_default) + "\n",
        encoding="utf-8",
    )

    best_validation = best_row(summary, "validation", ("model",))
    best_holdout = best_row(summary, "holdout", ("model",))
    print(f"Models run: {len(models_run)}")
    print(f"Models skipped: {len(skipped)}")
    print(f"Predictions shape: {predictions.shape}")
    print(f"Backtest returns shape: {backtest_returns.shape}")
    print(f"Summary shape: {summary.shape}")
    print(f"Best validation model: {best_validation.get('strategy_name') if best_validation else 'none'}")
    print(f"Best holdout model: {best_holdout.get('strategy_name') if best_holdout else 'none'}")
    print(f"Best holdout Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Best holdout annual return: {best_holdout.get('annual_return') if best_holdout else np.nan}")
    print("Outputs:")
    for path in preprocessing_metadata["outputs"].values():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
