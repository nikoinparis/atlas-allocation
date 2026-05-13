#!/usr/bin/env python3
"""
Phase MLX-4: neural-network models for the experimental hard-ML lab.

Research-only. This script reads MLX feature/target panels, trains small MLPs
with train-only preprocessing statistics, writes only under data/research/ml_lab,
and does not modify production pins, dashboard code, strategy logic, or candidates.
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
TABULAR_DIR = ROOT / "data" / "research" / "ml_lab" / "tabular_ml"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "neural_networks"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"

PREDICTIONS_OUT = OUTPUT_DIR / "nn_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "nn_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "nn_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "nn_training_curves.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "nn_preprocessing_metadata.json"
SKIPPED_MODELS_OUT = OUTPUT_DIR / "nn_skipped_models.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_neural_network_notes.md"

TABULAR_SUMMARY_IN = TABULAR_DIR / "ml_tabular_summary.csv"
TABULAR_RETURNS_IN = TABULAR_DIR / "ml_tabular_backtest_returns.csv"

TARGET_COLUMNS = {
    "forward_return_4w",
    "forward_return_13w",
    "forward_rank_4w",
    "forward_rank_13w",
    "beats_SPY_4w",
    "beats_BIL_4w",
    "positive_forward_4w",
    "top_quintile_forward_4w",
}

DEFAULT_COST_BPS = 10.0
RANDOM_STATE = 42
MAX_EPOCHS = 40
PATIENCE = 6
BATCH_SIZE = 4096
EXTREME_MISSINGNESS_THRESHOLD = 0.95


@dataclass(frozen=True)
class NNConfig:
    model_name: str
    target: str
    task: str
    hidden_dims: tuple[int, ...]
    dropout: float
    loss: str
    max_epochs: int = MAX_EPOCHS
    patience: int = PATIENCE


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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_mlx3_helpers() -> Any:
    path = ROOT / "scripts" / "ml_lab" / "02_run_tabular_ml_models.py"
    spec = importlib.util.spec_from_file_location("mlx3_tabular_helpers", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load MLX-3 helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not FEATURES_IN.exists() or not TARGETS_IN.exists():
        missing = [str(p) for p in [FEATURES_IN, TARGETS_IN] if not p.exists()]
        raise FileNotFoundError(f"Required MLX-2 input(s) missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    return features.sort_values(["Date", "ticker"]).reset_index(drop=True), targets.sort_values(["Date", "ticker"]).reset_index(drop=True)


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    required_ids = {"Date", "ticker"}
    if not required_ids.issubset(features.columns) or not required_ids.issubset(targets.columns):
        raise ValueError("Feature and target panels must both include Date and ticker identifiers.")
    feature_keys = features[["Date", "ticker"]].reset_index(drop=True)
    target_keys = targets[["Date", "ticker"]].reset_index(drop=True)
    if len(feature_keys) != len(target_keys) or not feature_keys.equals(target_keys):
        raise ValueError("Feature rows do not align with target rows on Date/ticker.")
    leaked_targets = sorted(TARGET_COLUMNS & set(features.columns))
    if leaked_targets:
        raise ValueError(f"Target columns are present in neural-network features: {leaked_targets}")
    suspicious = []
    for col in features.columns:
        lower = col.lower()
        if col in {"Date", "ticker", "target_vol_multiplier"}:
            continue
        if (
            lower.startswith("forward_")
            or lower.startswith("future_")
            or lower.startswith("next_")
            or lower.startswith("beats_")
            or lower.startswith("top_quintile")
            or lower.startswith("positive_forward")
            or lower.endswith("_label")
        ):
            suspicious.append(col)
    if suspicious:
        raise ValueError(f"Target-like leakage columns found in features: {suspicious}")


def split_name_for_dates(dates: pd.Series) -> pd.Series:
    split = pd.Series("unassigned", index=dates.index, dtype="object")
    split.loc[dates <= pd.Timestamp("2017-12-31")] = "train"
    split.loc[(dates >= pd.Timestamp("2018-01-01")) & (dates <= pd.Timestamp("2019-12-31"))] = "validation"
    split.loc[dates >= pd.Timestamp("2020-01-01")] = "holdout"
    return split


def prepare_features(features: pd.DataFrame, split: pd.Series) -> dict[str, Any]:
    identifier_cols = {"Date", "ticker"}
    numeric_cols = [
        col
        for col in features.columns
        if col not in identifier_cols and pd.api.types.is_numeric_dtype(features[col])
    ]
    x_raw = features[numeric_cols].replace([np.inf, -np.inf], np.nan)
    train_mask = split.eq("train")
    train_missing = x_raw.loc[train_mask].isna().mean()
    dropped = train_missing[train_missing > EXTREME_MISSINGNESS_THRESHOLD].index.tolist()
    kept_cols = [col for col in numeric_cols if col not in dropped]
    x_raw = x_raw[kept_cols]
    medians = x_raw.loc[train_mask].median(numeric_only=True).fillna(0.0)
    x_filled = x_raw.fillna(medians).fillna(0.0)
    means = x_filled.loc[train_mask].mean(numeric_only=True)
    stds = x_filled.loc[train_mask].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    x_standardized = ((x_filled - means) / stds).astype("float32")
    return {
        "numeric_feature_cols_original": numeric_cols,
        "numeric_feature_cols": kept_cols,
        "dropped_features_extreme_missingness": dropped,
        "train_missing_rate": train_missing.to_dict(),
        "median_fill_values": medians.to_dict(),
        "standardization_means": means.to_dict(),
        "standardization_stds": stds.to_dict(),
        "x_standardized": x_standardized,
    }


def torch_status() -> dict[str, Any]:
    spec = importlib.util.find_spec("torch")
    status: dict[str, Any] = {"available": bool(spec), "version": None, "cuda_available": False, "mps_available": False}
    if not spec:
        return status
    try:
        import torch
    except Exception as exc:
        status["available"] = False
        status["import_error"] = f"{type(exc).__name__}: {exc}"
        return status
    status["version"] = torch.__version__
    status["cuda_available"] = bool(torch.cuda.is_available())
    status["mps_available"] = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    return status


def set_torch_seeds(torch: Any) -> None:
    random.seed(RANDOM_STATE)
    np.random.seed(RANDOM_STATE)
    torch.manual_seed(RANDOM_STATE)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(RANDOM_STATE)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


def make_model(torch: Any, input_dim: int, hidden_dims: tuple[int, ...], dropout: float) -> Any:
    layers: list[Any] = []
    prev = input_dim
    for dim in hidden_dims:
        layers.append(torch.nn.Linear(prev, dim))
        layers.append(torch.nn.ReLU())
        layers.append(torch.nn.Dropout(dropout))
        prev = dim
    layers.append(torch.nn.Linear(prev, 1))
    return torch.nn.Sequential(*layers)


def make_loader(torch: Any, x: np.ndarray, y: np.ndarray, shuffle: bool) -> Any:
    dataset = torch.utils.data.TensorDataset(
        torch.from_numpy(x.astype("float32", copy=False)),
        torch.from_numpy(y.astype("float32", copy=False)).reshape(-1, 1),
    )
    return torch.utils.data.DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=shuffle)


def train_one_model(
    torch: Any,
    config: NNConfig,
    x: pd.DataFrame,
    y: pd.Series,
    split: pd.Series,
    device: str,
    warnings_list: list[str],
) -> tuple[Any | None, pd.DataFrame, dict[str, Any], np.ndarray | None]:
    train_mask = split.eq("train") & y.notna()
    val_mask = split.eq("validation") & y.notna()
    if train_mask.sum() < 1000 or val_mask.sum() < 100:
        warn(f"Skipping {config.model_name}: insufficient train/validation target rows.", warnings_list)
        return None, pd.DataFrame(), {"reason": "insufficient train/validation target rows"}, None

    y_train_raw = y.loc[train_mask].astype("float32")
    y_val_raw = y.loc[val_mask].astype("float32")
    target_transform: dict[str, Any] = {"type": "none"}

    if config.task == "regression":
        target_mean = float(y_train_raw.mean())
        target_std = float(y_train_raw.std(ddof=0) or 1.0)
        if target_std == 0.0 or not np.isfinite(target_std):
            target_std = 1.0
        y_train = ((y_train_raw - target_mean) / target_std).to_numpy(dtype="float32")
        y_val = ((y_val_raw - target_mean) / target_std).to_numpy(dtype="float32")
        target_transform = {"type": "standardized_regression_target", "mean": target_mean, "std": target_std}
    else:
        y_train = y_train_raw.to_numpy(dtype="float32")
        y_val = y_val_raw.to_numpy(dtype="float32")
        positives = float(y_train.sum())
        negatives = float(len(y_train) - positives)
        pos_weight_value = negatives / positives if positives > 0 else 1.0
        target_transform = {"type": "binary_classification", "positive_rate_train": positives / max(1.0, len(y_train)), "pos_weight": pos_weight_value}

    x_train = x.loc[train_mask].to_numpy(dtype="float32")
    x_val = x.loc[val_mask].to_numpy(dtype="float32")
    train_loader = make_loader(torch, x_train, y_train, shuffle=True)
    val_loader = make_loader(torch, x_val, y_val, shuffle=False)

    model = make_model(torch, x.shape[1], config.hidden_dims, config.dropout).to(device)
    if config.task == "classification":
        pos_weight = torch.tensor([float(target_transform["pos_weight"])], dtype=torch.float32, device=device)
        loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    elif config.loss == "huber":
        loss_fn = torch.nn.SmoothL1Loss()
    else:
        loss_fn = torch.nn.MSELoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    best_loss = float("inf")
    best_epoch = 0
    best_state = None
    stale_epochs = 0
    curve_rows: list[dict[str, Any]] = []

    for epoch in range(1, config.max_epochs + 1):
        model.train()
        train_losses: list[float] = []
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            optimizer.step()
            train_losses.append(float(loss.detach().cpu().item()))

        model.eval()
        val_losses: list[float] = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                val_loss = loss_fn(model(xb), yb)
                val_losses.append(float(val_loss.detach().cpu().item()))

        train_loss = float(np.mean(train_losses)) if train_losses else np.nan
        val_loss = float(np.mean(val_losses)) if val_losses else np.nan
        improved = val_loss < best_loss - 1e-6
        if improved:
            best_loss = val_loss
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
        curve_rows.append(
            {
                "model_name": config.model_name,
                "target": config.target,
                "task": config.task,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": val_loss,
                "best_epoch_so_far": best_epoch,
                "early_stop_triggered": False,
            }
        )
        if stale_epochs >= config.patience:
            curve_rows[-1]["early_stop_triggered"] = True
            break

    if best_state is not None:
        model.load_state_dict(best_state)
    meta = {
        "model_name": config.model_name,
        "target": config.target,
        "task": config.task,
        "hidden_dims": list(config.hidden_dims),
        "dropout": config.dropout,
        "loss": config.loss,
        "max_epochs": config.max_epochs,
        "patience": config.patience,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "epochs_run": len(curve_rows),
        "target_transform": target_transform,
    }
    return model, pd.DataFrame(curve_rows), meta, None


def predict_model(torch: Any, model: Any, config: NNConfig, x: pd.DataFrame, device: str, target_transform: dict[str, Any]) -> np.ndarray:
    model.eval()
    scores: list[np.ndarray] = []
    arr = x.to_numpy(dtype="float32")
    with torch.no_grad():
        for start in range(0, len(arr), BATCH_SIZE * 4):
            xb = torch.from_numpy(arr[start : start + BATCH_SIZE * 4]).to(device)
            raw = model(xb).detach().cpu().numpy().reshape(-1)
            if config.task == "classification":
                raw = 1.0 / (1.0 + np.exp(-raw))
            elif target_transform.get("type") == "standardized_regression_target":
                raw = raw * float(target_transform["std"]) + float(target_transform["mean"])
            scores.append(raw.astype("float64"))
    return np.concatenate(scores)


def empty_outputs(torch_meta: dict[str, Any], skipped: list[dict[str, str]], warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=["Date", "ticker", "split", "model_name", "target", "task", "score", "actual_target"]).to_parquet(PREDICTIONS_OUT, index=False)
    pd.DataFrame().to_csv(BACKTEST_RETURNS_OUT, index=False)
    pd.DataFrame().to_csv(SUMMARY_OUT, index=False)
    pd.DataFrame(columns=["model_name", "target", "epoch", "train_loss", "validation_loss"]).to_csv(TRAINING_CURVES_OUT, index=False)
    SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2) + "\n", encoding="utf-8")
    PREPROCESSING_METADATA_OUT.write_text(
        json.dumps(
            {
                "phase": "MLX-4 neural networks",
                "production_valid": False,
                "research_only": True,
                "torch": torch_meta,
                "models_run": [],
                "models_skipped": skipped,
                "warnings": warnings_list,
            },
            indent=2,
            default=json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def append_mlx3_best_baseline(mlx3: Any, all_returns: list[pd.DataFrame], summary_rows: list[dict[str, Any]], warnings_list: list[str]) -> dict[str, Any]:
    if not TABULAR_SUMMARY_IN.exists() or not TABULAR_RETURNS_IN.exists():
        warn("Optional MLX-3 tabular summary/returns missing; MLX-3 best baseline comparison skipped.", warnings_list)
        return {"loaded": False, "reason": "missing MLX-3 summary or returns"}
    tab_summary = pd.read_csv(TABULAR_SUMMARY_IN)
    holdout_models = tab_summary[(tab_summary["split"].eq("holdout")) & (tab_summary["strategy_type"].eq("model"))].copy()
    holdout_models = holdout_models[pd.to_numeric(holdout_models["sharpe"], errors="coerce").notna()]
    if holdout_models.empty:
        warn("MLX-3 summary has no holdout model rows; MLX-3 best baseline skipped.", warnings_list)
        return {"loaded": False, "reason": "no holdout model rows"}
    best = holdout_models.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
    best_strategy = str(best["strategy_name"])
    returns = pd.read_csv(TABULAR_RETURNS_IN, parse_dates=["Date"])
    rows = returns[returns["strategy_name"].eq(best_strategy)].copy()
    if rows.empty:
        warn(f"MLX-3 returns file did not contain best strategy {best_strategy}; skipped.", warnings_list)
        return {"loaded": False, "reason": "best strategy not in returns", "strategy_name": best_strategy}
    path = rows.set_index("Date")[["gross_return", "net_return", "turnover", "cost", "holdings_count"]].sort_index()
    mlx3.append_strategy_results(
        all_returns,
        summary_rows,
        path,
        strategy_name=f"mlx3_best_tabular__{best_strategy}",
        strategy_type="mlx3_tabular_baseline",
        split_values=("train", "validation", "holdout"),
        cost_bps=DEFAULT_COST_BPS,
    )
    return {
        "loaded": True,
        "strategy_name": best_strategy,
        "holdout_sharpe": float(best["sharpe"]),
        "holdout_annual_return": float(best["annual_return"]),
    }


def best_row(summary: pd.DataFrame, split: str, strategy_types: tuple[str, ...], metric: str = "sharpe", ascending: bool = False) -> dict[str, Any] | None:
    if summary.empty:
        return None
    subset = summary[summary["split"].eq(split) & summary["strategy_type"].isin(strategy_types)].copy()
    subset = subset[pd.to_numeric(subset[metric], errors="coerce").notna()]
    if subset.empty:
        return None
    return subset.sort_values([metric, "annual_return"], ascending=[ascending, False]).iloc[0].to_dict()


def compare_holdout(summary: pd.DataFrame) -> dict[str, Any]:
    nn = summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model"))].copy()
    if nn.empty:
        return {}
    best_nn = pd.to_numeric(nn["sharpe"], errors="coerce").max()

    def max_sharpe(mask: pd.Series) -> float:
        sub = summary[summary["split"].eq("holdout") & mask].copy()
        return float(pd.to_numeric(sub["sharpe"], errors="coerce").max()) if not sub.empty else np.nan

    out = {
        "best_nn_holdout_sharpe": float(best_nn),
        "mlx3_best_tabular_holdout_sharpe": max_sharpe(summary["strategy_type"].eq("mlx3_tabular_baseline")),
        "simple_momentum_holdout_sharpe": max_sharpe(summary["strategy_type"].eq("baseline_momentum")),
        "spy_holdout_sharpe": max_sharpe(summary["strategy_name"].eq("baseline_spy_buy_hold")),
        "sixty_forty_holdout_sharpe": max_sharpe(summary["strategy_name"].eq("baseline_60_40_spy_ief_or_agg")),
        "production_holdout_sharpe": max_sharpe(summary["strategy_name"].eq("project_current_production_or_rollback_phase2b")),
        "shadow_holdout_sharpe": max_sharpe(summary["strategy_name"].eq("project_official_shadow_phase2b_combo_abc")),
    }
    out["beats_mlx3_tabular_by_sharpe"] = bool(pd.notna(out["mlx3_best_tabular_holdout_sharpe"]) and best_nn > out["mlx3_best_tabular_holdout_sharpe"])
    out["beats_simple_momentum_by_sharpe"] = bool(pd.notna(out["simple_momentum_holdout_sharpe"]) and best_nn > out["simple_momentum_holdout_sharpe"])
    out["beats_spy_by_sharpe"] = bool(pd.notna(out["spy_holdout_sharpe"]) and best_nn > out["spy_holdout_sharpe"])
    out["beats_60_40_by_sharpe"] = bool(pd.notna(out["sixty_forty_holdout_sharpe"]) and best_nn > out["sixty_forty_holdout_sharpe"])
    out["beats_production_by_sharpe"] = bool(pd.notna(out["production_holdout_sharpe"]) and best_nn > out["production_holdout_sharpe"])
    out["beats_shadow_by_sharpe"] = bool(pd.notna(out["shadow_holdout_sharpe"]) and best_nn > out["shadow_holdout_sharpe"])
    return out


def fmt_metric(value: Any, pct: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}" if pct else f"{float(value):.3f}"


def fmt_strategy(row: dict[str, Any] | None) -> str:
    if not row:
        return "not available"
    return f"{row.get('strategy_name')} (Sharpe {fmt_metric(row.get('sharpe'))}, annual return {fmt_metric(row.get('annual_return'), pct=True)})"


def write_notes(
    torch_meta: dict[str, Any],
    device: str,
    models_run: list[str],
    skipped: list[dict[str, str]],
    summary: pd.DataFrame,
    comparisons: dict[str, Any],
    warnings_list: list[str],
) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    best_validation = best_row(summary, "validation", ("model",))
    best_holdout = best_row(summary, "holdout", ("model",))
    best_holdout_return = best_row(summary, "holdout", ("model",), metric="annual_return")
    best_drawdown = best_row(summary, "holdout", ("model",), metric="max_drawdown", ascending=False)
    model_lines = "\n".join(f"- {m}" for m in models_run) or "- None"
    skipped_lines = "\n".join(f"- {s['model_name']}: {s['reason']}" for s in skipped) or "- None"
    warning_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"
    NOTES_OUT.write_text(
        f"""# Phase MLX Neural Network Notes

## Research-Only Warning

Phase MLX-4 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed by this work.

## Educational Explanation

A neural network is a flexible function approximator: it learns many small weights that transform inputs into predictions. In this lab, the inputs are date × ETF features such as momentum, volatility, drawdown, regime scores, and breadth diagnostics.

An MLP, or multilayer perceptron, is the simplest common neural-network architecture. It stacks fully connected linear layers with nonlinear activation functions. Here, each ETF-date row is passed through hidden layers and the model outputs either a probability or a predicted forward return.

Dropout randomly turns off a fraction of hidden units during training. That forces the network not to rely too heavily on one pathway and can reduce overfitting, though it does not eliminate data-mining risk.

Early stopping watches validation loss and stops training when the model stops improving. It is a guardrail against training until the network memorizes the training split.

Train, validation, and holdout mean three chronological data blocks. Train data fits preprocessing and model weights. Validation data chooses when to stop training. Holdout data is kept out of fitting and is the main research check.

Neural networks might help this ETF project if there are nonlinear interactions between trend, volatility, cross-sectional strength, market regime, and breadth. They might overfit because the ETF universe is expanded, signals are noisy, validation windows are short, and many model/portfolio choices create multiple-testing risk.

This project uses neural networks only to rank ETFs each week. The highest-scoring ETFs are tested in simple top-N portfolios; no neural-network output is promoted automatically.

## Technical Setup

- Torch available: {torch_meta.get('available')} / version: {torch_meta.get('version')}
- Device used: `{device}`
- Input features: numeric MLX-2 features only; `Date` and `ticker` are identifiers, not model inputs.
- Targets: `top_quintile_forward_4w`, `beats_SPY_4w`, and `forward_return_4w`.
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architecture: small MLPs with ReLU activations and dropout, plus one deeper dropout MLP.
- Loss functions: BCEWithLogitsLoss for classifiers and SmoothL1/Huber loss for regression.
- Preprocessing: train-only medians for missing values and train-only mean/std standardization.
- Leakage controls: no `forward_*`, `beats_*`, `top_quintile_*`, or other target-like columns are used as input features; validation and holdout are not used for preprocessing or fitting model weights.

## Results

Models run:

{model_lines}

Models skipped:

{skipped_lines}

- Best validation model: {fmt_strategy(best_validation)}
- Best holdout model: {fmt_strategy(best_holdout)}
- Best holdout annual return model: {fmt_strategy(best_holdout_return)}
- Best holdout drawdown model: {fmt_strategy(best_drawdown)}
- Best holdout Sharpe: {fmt_metric(best_holdout.get('sharpe') if best_holdout else np.nan)}
- Best holdout annual return: {fmt_metric(best_holdout_return.get('annual_return') if best_holdout_return else np.nan, pct=True)}

Comparisons by holdout Sharpe:

- Beats MLX-3 best tabular model: {comparisons.get('beats_mlx3_tabular_by_sharpe')}
- Beats simple momentum: {comparisons.get('beats_simple_momentum_by_sharpe')}
- Beats SPY: {comparisons.get('beats_spy_by_sharpe')}
- Beats 60/40: {comparisons.get('beats_60_40_by_sharpe')}
- Beats production: {comparisons.get('beats_production_by_sharpe')}
- Beats official shadow: {comparisons.get('beats_shadow_by_sharpe')}

## Interpretation

Neural networks are useful infrastructure here, but the bar is not whether one backtest looks clever. The key question is whether the model beats simple, robust baselines on holdout without suspicious train/validation behavior. Any promising result remains research-only or ML shadow at most until it survives harsher walk-forward testing, turnover realism, regime slicing, and human review.

Warnings:

{warning_lines}
""",
        encoding="utf-8",
    )


def main() -> int:
    warnings_list: list[str] = []
    skipped: list[dict[str, str]] = []
    print("Phase MLX-4 neural-network model runner")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")

    torch_meta = torch_status()
    features, targets = load_inputs()
    validate_inputs(features, targets)
    split = split_name_for_dates(features["Date"])
    split_ranges = {
        name: {
            "start": features.loc[split.eq(name), "Date"].min().date().isoformat(),
            "end": features.loc[split.eq(name), "Date"].max().date().isoformat(),
            "rows": int(split.eq(name).sum()),
            "dates": int(features.loc[split.eq(name), "Date"].nunique()),
        }
        for name in ("train", "validation", "holdout")
    }

    configs = [
        NNConfig("mlp_classifier_top_quintile_forward_4w", "top_quintile_forward_4w", "classification", (128, 64), 0.20, "bce"),
        NNConfig("mlp_classifier_beats_SPY_4w", "beats_SPY_4w", "classification", (128, 64), 0.20, "bce"),
        NNConfig("mlp_regressor_forward_return_4w", "forward_return_4w", "regression", (128, 64), 0.20, "huber"),
        NNConfig("deep_dropout_mlp_classifier_top_quintile_forward_4w", "top_quintile_forward_4w", "classification", (256, 128, 64), 0.35, "bce", max_epochs=35, patience=6),
    ]
    skipped.append(
        {
            "model_name": "autoencoder_feature_compression_mlp",
            "reason": "Skipped in MLX-4 sprint to keep runtime and complexity bounded; candidate for later representation-learning phase.",
        }
    )

    if not torch_meta.get("available"):
        for config in configs:
            skipped.append({"model_name": config.model_name, "reason": "torch is missing or failed to import; neural-network training skipped."})
        empty_outputs(torch_meta, skipped, warnings_list)
        write_notes(torch_meta, "none", [], skipped, pd.DataFrame(), {}, warnings_list)
        return 0

    import torch

    set_torch_seeds(torch)
    device = "cpu"
    prepared = prepare_features(features, split)
    x = prepared["x_standardized"]
    ids = features[["Date", "ticker"]].copy()
    ids["split"] = split.values

    prediction_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    training_meta: list[dict[str, Any]] = []
    models_run: list[str] = []

    for config in configs:
        model, curves, meta, _ = train_one_model(torch, config, x, targets[config.target], split, device, warnings_list)
        if model is None:
            skipped.append({"model_name": config.model_name, "reason": meta.get("reason", "training failed or skipped")})
            continue
        scores = predict_model(torch, model, config, x, device, meta["target_transform"])
        pred = ids.copy()
        pred["model_name"] = config.model_name
        pred["target"] = config.target
        pred["task"] = config.task
        pred["score"] = scores
        pred["actual_target"] = targets[config.target].values
        prediction_frames.append(pred)
        curve_frames.append(curves)
        training_meta.append(meta)
        models_run.append(config.model_name)

    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame(columns=["Date", "ticker", "split", "model_name", "target", "task", "score", "actual_target"])
    curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame(columns=["model_name", "target", "task", "epoch", "train_loss", "validation_loss"])

    mlx3 = load_mlx3_helpers()
    backtest_returns, summary, external_meta = mlx3.run_portfolio_simulations(features, predictions, warnings_list)
    all_returns = [backtest_returns] if not backtest_returns.empty else []
    summary_rows = summary.to_dict("records") if not summary.empty else []
    mlx3_best_meta = append_mlx3_best_baseline(mlx3, all_returns, summary_rows, warnings_list)
    backtest_returns = pd.concat(all_returns, ignore_index=True) if all_returns else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    comparisons = compare_holdout(summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    backtest_returns.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    curves.to_csv(TRAINING_CURVES_OUT, index=False)
    SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default) + "\n", encoding="utf-8")

    metadata = {
        "phase": "MLX-4 neural network models",
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
        "torch": torch_meta,
        "device_used": device,
        "mps_available_but_not_used": bool(torch_meta.get("mps_available") and device != "mps"),
        "inputs": {"features": str(FEATURES_IN.relative_to(ROOT)), "targets": str(TARGETS_IN.relative_to(ROOT))},
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "skipped_models": str(SKIPPED_MODELS_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
        "split_ranges": split_ranges,
        "feature_panel_shape": list(features.shape),
        "target_shape": list(targets.shape),
        "numeric_feature_count_original": len(prepared["numeric_feature_cols_original"]),
        "numeric_feature_count_used": len(prepared["numeric_feature_cols"]),
        "numeric_features_used": prepared["numeric_feature_cols"],
        "dropped_features_extreme_missingness": prepared["dropped_features_extreme_missingness"],
        "extreme_missingness_threshold": EXTREME_MISSINGNESS_THRESHOLD,
        "train_only_preprocessing": {
            "median_fill_values": prepared["median_fill_values"],
            "standardization_means": prepared["standardization_means"],
            "standardization_stds": prepared["standardization_stds"],
            "train_missing_rate": prepared["train_missing_rate"],
        },
        "models_run": models_run,
        "models_skipped": skipped,
        "training_metadata": training_meta,
        "cost_assumption": {"cost_bps_per_unit_turnover": DEFAULT_COST_BPS},
        "backtest_return_construction": "Realized next-week ETF returns are derived from trailing_return_1w shifted one week forward by ticker.",
        "external_project_baselines": external_meta,
        "mlx3_best_tabular_baseline": mlx3_best_meta,
        "holdout_comparisons": comparisons,
        "warnings": warnings_list
        + [
            "Experimental research-only Phase MLX output; not production-valid.",
            "No neural-network model is promoted automatically.",
            "Expanded ETF neural-network testing has high overfitting, selection-bias, and data-mining risk.",
        ],
    }
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(metadata, indent=2, default=json_default) + "\n", encoding="utf-8")
    write_notes(torch_meta, device, models_run, skipped, summary, comparisons, warnings_list)

    best_validation = best_row(summary, "validation", ("model",))
    best_holdout = best_row(summary, "holdout", ("model",))
    print(f"Torch available: {torch_meta.get('available')} version={torch_meta.get('version')}")
    print(f"Device used: {device}")
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
    for path in metadata["outputs"].values():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
