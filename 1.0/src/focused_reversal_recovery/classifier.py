"""Simple train-only classifiers for focused reversal labels.

The models are intentionally small and deterministic. They use focused reversal
features only, avoiding breadth/credit/volatility as primary alpha inputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HOLDOUT_START = pd.Timestamp("2024-04-19")

MODEL_NAMES = ["classifier_logistic_reversal", "classifier_ridge_reversal"]


FOCUSED_MODEL_COLUMNS = [
    "score_short_horizon_reversal",
    "score_drawdown_reversal",
    "score_momentum_reversal_interaction",
    "score_focused_reversal_composite",
    "score_short_reversal_only",
    "score_drawdown_recovery_only",
    "score_pullback_in_uptrend",
    "score_oversold_rebound_after_stress",
    "ret_1w",
    "ret_2w",
    "ret_4w",
    "ret_8w",
    "ret_12w",
    "ret_26w",
    "loss_magnitude_1w",
    "loss_magnitude_2w",
    "loss_magnitude_4w",
    "ret_1w_z_52",
    "ret_2w_z_52",
    "ret_4w_z_52",
    "short_term_oversold_score",
    "recent_loss_magnitude",
    "reversal_pressure_score",
    "drawdown_depth_13w",
    "drawdown_depth_26w",
    "drawdown_depth_52w",
    "recovery_from_4w_low",
    "recovery_from_8w_low",
    "weeks_since_8w_low",
    "selloff_speed_4w",
    "down_weeks_4w",
    "down_weeks_8w",
    "above_4w_ma",
    "above_8w_ma",
    "reclaim_4w_ma",
    "reclaim_8w_ma",
    "drawdown_depth_x_recovery_confirmation",
    "bounce_from_low_after_drawdown",
    "medium_momentum_8w",
    "medium_momentum_12w",
    "medium_momentum_26w",
    "medium_uptrend_flag",
    "medium_downtrend_flag",
    "uptrend_short_pullback",
    "downtrend_short_bounce",
    "trend_negative_recovery_acceleration",
    "trend_positive_short_oversold",
    "momentum_reversal_interaction_raw",
]


def run_classifiers(features: pd.DataFrame, targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    df["Date"] = pd.to_datetime(df["Date"])
    model_cols = [c for c in FOCUSED_MODEL_COLUMNS if c in df.columns]
    work = df.dropna(subset=model_cols + ["strong_bounce_label"]).copy()
    train = work[work["Date"] < HOLDOUT_START]
    holdout = work[work["Date"] >= HOLDOUT_START]
    if len(train) < 100:
        raise RuntimeError("Not enough train rows for focused reversal classifier research")

    x_train = train[model_cols].astype(float).values
    y_train = train["strong_bounce_label"].astype(float).values
    mean = np.nanmean(x_train, axis=0)
    std = np.nanstd(x_train, axis=0)
    std[std == 0] = 1.0
    x_train_z = (x_train - mean) / std

    weights = {
        "classifier_logistic_reversal": (_fit_logistic(x_train_z, y_train, l2=0.30), "logistic"),
        "classifier_ridge_reversal": (_fit_ridge(x_train_z, y_train, l2=3.0), "ridge"),
    }

    metric_rows = []
    pred_frames = []
    for model, (w, kind) in weights.items():
        train_probs = _predict(train[model_cols].astype(float).values, mean, std, w, kind)
        train_threshold = float(np.nanquantile(train_probs, 0.75))
        for window, sub in [("train", train), ("holdout", holdout), ("full", work)]:
            probs = _predict(sub[model_cols].astype(float).values, mean, std, w, kind)
            metric_rows.extend(_classification_metrics(sub, probs, model, window, train_threshold))

        full_probs = _predict(work[model_cols].astype(float).values, mean, std, w, kind)
        pf = work[
            [
                "Date",
                "ticker",
                "market_state",
                "filter_non_panic",
                "strong_bounce_label",
                "failed_bounce_label",
                "crash_continuation_label",
                "fwd_8w_return",
            ]
        ].copy()
        pf["model"] = model
        pf["prediction"] = full_probs
        pf["threshold"] = train_threshold
        pf["active"] = full_probs >= train_threshold
        pred_frames.append(pf)
        metric_rows.extend(_coefficient_rows(model, model_cols, w))

    return pd.DataFrame(metric_rows), pd.concat(pred_frames, ignore_index=True)


def _fit_logistic(x: np.ndarray, y: np.ndarray, l2: float, steps: int = 900, lr: float = 0.05) -> np.ndarray:
    x1 = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(x1.shape[1])
    for _ in range(steps):
        p = 1.0 / (1.0 + np.exp(-np.clip(x1 @ w, -30, 30)))
        grad = x1.T @ (p - y) / len(y)
        grad[1:] += l2 * w[1:] / len(y)
        w -= lr * grad
    return w


def _fit_ridge(x: np.ndarray, y: np.ndarray, l2: float) -> np.ndarray:
    x1 = np.column_stack([np.ones(len(x)), x])
    ident = np.eye(x1.shape[1])
    ident[0, 0] = 0.0
    return np.linalg.pinv(x1.T @ x1 + l2 * ident) @ x1.T @ y


def _predict(x: np.ndarray, mean: np.ndarray, std: np.ndarray, weights: np.ndarray, kind: str) -> np.ndarray:
    z = (x - mean) / std
    x1 = np.column_stack([np.ones(len(z)), z])
    raw = x1 @ weights
    if kind == "logistic":
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))
    return np.clip(raw, 0.0, 1.0)


def _classification_metrics(
    df: pd.DataFrame,
    probs: np.ndarray,
    model: str,
    window: str,
    threshold: float,
) -> list[dict]:
    y = df["strong_bounce_label"].astype(float).values
    if len(y) == 0:
        return []
    pred = probs >= threshold
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    precision = tp / (tp + fp) if (tp + fp) else np.nan
    recall = tp / (tp + fn) if (tp + fn) else np.nan
    fpr = fp / (fp + tn) if (fp + tn) else np.nan
    base = float(np.mean(y))
    brier = float(np.mean((probs - y) ** 2))
    risk_off = pd.to_numeric(df["filter_non_panic"], errors="coerce").fillna(1).values < 1
    risk_off_fp = float(((pred == 1) & (y == 0) & risk_off).sum() / max(risk_off.sum(), 1))
    active = df[pred]
    return [
        {"model": model, "window": window, "metric": "base_rate", "value": base},
        {"model": model, "window": window, "metric": "precision_top_quartile", "value": precision},
        {"model": model, "window": window, "metric": "recall_top_quartile", "value": recall},
        {"model": model, "window": window, "metric": "false_positive_rate", "value": fpr},
        {"model": model, "window": window, "metric": "risk_off_false_positive_rate", "value": risk_off_fp},
        {
            "model": model,
            "window": window,
            "metric": "failed_bounce_rate_top_quartile",
            "value": float(active["failed_bounce_label"].mean()) if len(active) else np.nan,
        },
        {
            "model": model,
            "window": window,
            "metric": "crash_continuation_rate_top_quartile",
            "value": float(active["crash_continuation_label"].mean()) if len(active) else np.nan,
        },
        {"model": model, "window": window, "metric": "brier_score", "value": brier},
        {"model": model, "window": window, "metric": "threshold", "value": threshold},
        {"model": model, "window": window, "metric": "n", "value": len(y)},
    ]


def _coefficient_rows(model: str, cols: list[str], weights: np.ndarray) -> list[dict]:
    rows = []
    for col, w in zip(["intercept"] + cols, weights):
        rows.append({"model": model, "window": "coefficient", "metric": col, "value": float(w)})
    return rows

