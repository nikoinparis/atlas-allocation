"""Simple deterministic classifiers for strong recovery labels."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signal_families import FAMILY_SCORE_COLUMNS

HOLDOUT_START = pd.Timestamp("2024-04-19")


def run_classifiers(features: pd.DataFrame, targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train simple train-only models and return metrics plus predictions."""

    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    df["Date"] = pd.to_datetime(df["Date"])
    model_cols = FAMILY_SCORE_COLUMNS + [
        "score_equal_weight_composite",
        "score_and_gated_composite",
        "score_regime_gated_composite",
        "baseline_weight",
        "market_drawdown",
        "recent_stress_26w",
    ]
    model_cols = [c for c in model_cols if c in df.columns]
    work = df.dropna(subset=model_cols + ["strong_recovery_label"]).copy()
    train = work[work["Date"] < HOLDOUT_START]
    holdout = work[work["Date"] >= HOLDOUT_START]
    if len(train) < 100:
        raise RuntimeError("Not enough train rows for classifier research")

    x_train = train[model_cols].astype(float).values
    y_train = train["strong_recovery_label"].astype(float).values
    mean = np.nanmean(x_train, axis=0)
    std = np.nanstd(x_train, axis=0)
    std[std == 0] = 1.0
    x_train_z = (x_train - mean) / std

    logistic_w = _fit_logistic(x_train_z, y_train, l2=0.25)
    ridge_w = _fit_ridge(x_train_z, y_train, l2=2.0)

    pred_frames = []
    metric_rows = []
    for name, weights, kind in [
        ("logistic_l2", logistic_w, "logistic"),
        ("ridge_probability", ridge_w, "ridge"),
    ]:
        for window, sub in [("train", train), ("holdout", holdout), ("full", work)]:
            probs = _predict(sub[model_cols].astype(float).values, mean, std, weights, kind)
            metric_rows.extend(_classification_metrics(sub, probs, name, window))
        full_probs = _predict(work[model_cols].astype(float).values, mean, std, weights, kind)
        pf = work[["Date", "ticker", "market_state", "strong_recovery_label", "fake_bounce_label", "fwd_8w_return"]].copy()
        pf["model"] = name
        pf["prediction"] = full_probs
        pf["active"] = full_probs >= np.nanquantile(full_probs[work["Date"] < HOLDOUT_START], 0.75)
        pred_frames.append(pf)
        metric_rows.extend(_coefficient_rows(name, model_cols, weights))

    predictions = pd.concat(pred_frames, ignore_index=True)
    return pd.DataFrame(metric_rows), predictions


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
    ident[0, 0] = 0
    return np.linalg.pinv(x1.T @ x1 + l2 * ident) @ x1.T @ y


def _predict(x: np.ndarray, mean: np.ndarray, std: np.ndarray, weights: np.ndarray, kind: str) -> np.ndarray:
    z = (x - mean) / std
    x1 = np.column_stack([np.ones(len(z)), z])
    raw = x1 @ weights
    if kind == "logistic":
        return 1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30)))
    return np.clip(raw, 0.0, 1.0)


def _classification_metrics(df: pd.DataFrame, probs: np.ndarray, model: str, window: str) -> list[dict]:
    y = df["strong_recovery_label"].astype(float).values
    if len(y) == 0:
        return []
    threshold = np.nanquantile(probs, 0.75)
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
    risk_off = df["market_state"].astype(str).eq("stressed_panic").values
    risk_off_fp = float(((pred == 1) & (y == 0) & risk_off).sum() / max(risk_off.sum(), 1))
    return [
        {"model": model, "window": window, "metric": "base_rate", "value": base},
        {"model": model, "window": window, "metric": "precision_top_quartile", "value": precision},
        {"model": model, "window": window, "metric": "recall_top_quartile", "value": recall},
        {"model": model, "window": window, "metric": "false_positive_rate", "value": fpr},
        {"model": model, "window": window, "metric": "risk_off_false_positive_rate", "value": risk_off_fp},
        {"model": model, "window": window, "metric": "brier_score", "value": brier},
        {"model": model, "window": window, "metric": "n", "value": len(y)},
    ]


def _coefficient_rows(model: str, cols: list[str], weights: np.ndarray) -> list[dict]:
    rows = []
    for col, w in zip(["intercept"] + cols, weights):
        rows.append({"model": model, "window": "coefficient", "metric": col, "value": float(w)})
    return rows

