#!/usr/bin/env python3
"""
Phase MLX-12: decision-focused ETF portfolio learning.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
"""

from __future__ import annotations

import importlib.util
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
ML_DIR = ROOT / "data" / "research" / "ml_lab"
FEATURE_DIR = ML_DIR / "feature_panel"
EXPANDED_DIR = ML_DIR / "expanded_universe"
SEQUENCE_DIR = ML_DIR / "sequence_models"
SEQUENCE_5C_DIR = SEQUENCE_DIR / "multiseed_walkforward"
TRANSFORMER_DIR = ML_DIR / "transformers"
ENSEMBLE_DIR = ML_DIR / "ensembles"
CAA_DIR = ML_DIR / "cross_asset_attention"
TABULAR_DIR = ML_DIR / "tabular_ml"
NN_DIR = ML_DIR / "neural_networks"
OUTPUT_DIR = ML_DIR / "decision_focused"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"

TABULAR_SUMMARY_IN = TABULAR_DIR / "ml_tabular_summary.csv"
TABULAR_RETURNS_IN = TABULAR_DIR / "ml_tabular_backtest_returns.csv"
NN_SUMMARY_IN = NN_DIR / "nn_summary.csv"
NN_RETURNS_IN = NN_DIR / "nn_backtest_returns.csv"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_RETURNS_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
SEQUENCE_5C_SUMMARY_IN = SEQUENCE_5C_DIR / "sequence_multiseed_summary.json"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_RETURNS_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
ENSEMBLE_SUMMARY_JSON_IN = ENSEMBLE_DIR / "ensemble_summary.json"
ENSEMBLE_RETURNS_IN = ENSEMBLE_DIR / "ensemble_strategy_returns.csv"
CAA_SUMMARY_IN = CAA_DIR / "cross_asset_attention_summary.csv"
CAA_RETURNS_IN = CAA_DIR / "cross_asset_attention_backtest_returns.csv"

PREDICTIONS_OUT = OUTPUT_DIR / "decision_focused_predictions.parquet"
WEIGHTS_OUT = OUTPUT_DIR / "decision_focused_weights.parquet"
RETURNS_OUT = OUTPUT_DIR / "decision_focused_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "decision_focused_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "decision_focused_training_curves.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "decision_focused_strategy_comparison.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "decision_focused_state_by_state.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "decision_focused_exposure_audit.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "decision_focused_preprocessing_metadata.json"
CANDIDATE_DEFINITIONS_OUT = OUTPUT_DIR / "decision_focused_candidate_definitions.json"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "decision_focused_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "decision_focused_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_decision_focused_learning_notes.md"

TARGET = "top_quintile_forward_4w"
RANK_TARGET = "forward_rank_4w"
RETURN_TARGET = "forward_return_4w"
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
TARGET_LIKE_PREFIXES = ("forward_", "future_", "next_", "beats_", "top_quintile", "positive_forward")
DEFAULT_COST_BPS = 10.0
MAX_EPOCHS = 50
PATIENCE = 7
SEEDS = (0, 1)
SOFTMAX_TEMPERATURE = 0.50
SAFE_ASSETS = {"BIL", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD"}


@dataclass(frozen=True)
class DecisionConfig:
    model_name: str
    loss_kind: str
    seed: int
    hidden_dim: int = 64
    dropout: float = 0.15
    lr: float = 1e-3
    weight_decay: float = 1e-4
    max_epochs: int = MAX_EPOCHS
    patience: int = PATIENCE
    temperature: float = SOFTMAX_TEMPERATURE


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


def pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}"


def num(value: Any, digits: int = 3) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows available._"
    tmp = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in tmp.columns:
        if col in {
            "annual_return",
            "annual_volatility",
            "max_drawdown",
            "cvar_5",
            "average_turnover",
            "annual_cost_drag",
            "average_bil_exposure",
            "average_risky_exposure",
            "average_top3_weight",
        }:
            tmp[col] = tmp[col].map(pct)
        elif col in {"sharpe", "calmar", "rank_ic", "top_quintile_hit_rate"}:
            tmp[col] = tmp[col].map(num)
    headers = list(tmp.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in tmp.iterrows():
        vals = []
        for col in headers:
            value = row[col]
            vals.append("n/a" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", " "))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def split_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    parsed = pd.to_datetime(dates)
    index = dates.index if isinstance(dates, pd.Series) else pd.DatetimeIndex(parsed)
    s = pd.Series(parsed, index=index)
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
    return out


def torch_status() -> dict[str, Any]:
    spec = importlib.util.find_spec("torch")
    status: dict[str, Any] = {"available": bool(spec), "version": None, "device": "cpu"}
    if not spec:
        return status
    try:
        import torch
    except Exception as exc:
        return {"available": False, "version": None, "device": "cpu", "import_error": f"{type(exc).__name__}: {exc}"}
    status["version"] = torch.__version__
    status["cuda_available"] = bool(torch.cuda.is_available())
    status["mps_available"] = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    status["device"] = "cpu"
    return status


def set_seed(torch: Any, seed: int) -> None:
    import os

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    if len(features) != len(targets):
        raise ValueError(f"Feature/target row count mismatch: features={len(features)}, targets={len(targets)}")
    if not features[["Date", "ticker"]].reset_index(drop=True).equals(targets[["Date", "ticker"]].reset_index(drop=True)):
        raise ValueError("Feature and target identifiers do not align after sorting.")
    overlap = sorted(set(features.columns) & TARGET_COLUMNS)
    if overlap:
        raise ValueError(f"Target columns leaked into features: {overlap}")
    for required in ("Date", "ticker"):
        if required not in features.columns:
            raise ValueError(f"Missing required feature identifier: {required}")
    target_like = [c for c in features.columns if c not in {"Date", "ticker"} and c.lower().startswith(TARGET_LIKE_PREFIXES)]
    if target_like:
        raise ValueError(f"Target-like feature columns found in inputs: {target_like[:10]}")


def safe_feature_columns(features: pd.DataFrame) -> list[str]:
    cols = []
    for col in features.columns:
        if col in {"Date", "ticker"}:
            continue
        lower = col.lower()
        if col in TARGET_COLUMNS or lower.startswith(TARGET_LIKE_PREFIXES):
            continue
        if pd.api.types.is_numeric_dtype(features[col]):
            cols.append(col)
    return cols


def infer_market_state_by_date(features: pd.DataFrame) -> pd.Series:
    state_cols = [c for c in features.columns if c.startswith("market_state_")]
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    if not state_cols:
        return pd.Series("unknown", index=dates)
    state = features[["Date"] + state_cols].drop_duplicates("Date").set_index("Date").reindex(dates)
    labels = state[state_cols].idxmax(axis=1).str.replace("market_state_", "", regex=False)
    labels[state[state_cols].sum(axis=1).fillna(0.0).eq(0.0)] = "unknown"
    return labels.fillna("unknown")


def load_inputs(warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required decision-focused inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    weekly_returns = pd.read_csv(WEEKLY_RETURNS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    weekly_returns["Date"] = pd.to_datetime(weekly_returns["Date"])
    features = features.sort_values(["Date", "ticker"]).reset_index(drop=True)
    targets = targets.sort_values(["Date", "ticker"]).reset_index(drop=True)
    validate_inputs(features, targets)
    weekly_returns = weekly_returns.set_index("Date").sort_index()
    for col in weekly_returns.columns:
        weekly_returns[col] = pd.to_numeric(weekly_returns[col], errors="coerce")
    universe_meta = pd.read_csv(UNIVERSE_IN) if UNIVERSE_IN.exists() else pd.DataFrame()
    if "BIL" not in weekly_returns.columns:
        warn("BIL returns are missing; fallback overlays and cash-collapse diagnostics are less meaningful.", warnings_list)
    return features, targets, weekly_returns, universe_meta


def build_panel(features: pd.DataFrame, targets: pd.DataFrame, weekly_returns: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    tickers = sorted(set(features["ticker"].unique()) & set(weekly_returns.columns))
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    feature_cols = safe_feature_columns(features)
    train_mask = features["Date"].le(pd.Timestamp("2017-12-31"))
    medians = features.loc[train_mask, feature_cols].median(numeric_only=True).fillna(0.0)
    stds = features.loc[train_mask, feature_cols].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    idx = features.set_index(["Date", "ticker"])
    x_parts = []
    missing_rates = {}
    for col in feature_cols:
        mat = idx[col].unstack("ticker").reindex(index=dates, columns=tickers)
        missing_rates[col] = float(mat.isna().mean().mean())
        mat = (mat.fillna(medians[col]) - medians[col]) / stds[col]
        x_parts.append(mat.to_numpy(dtype="float32"))
    availability = weekly_returns.reindex(index=dates, columns=tickers).notna().astype("float32").to_numpy()
    x_parts.append(availability)
    x = np.stack(x_parts, axis=-1).astype("float32")

    tidx = targets.set_index(["Date", "ticker"])
    y_top = tidx[TARGET].unstack("ticker").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
    y_rank = tidx[RANK_TARGET].unstack("ticker").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
    y_ret = tidx[RETURN_TARGET].unstack("ticker").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
    target_mask = np.isfinite(y_top)
    next_returns = weekly_returns.reindex(index=dates, columns=tickers).shift(-1)
    return_mask = next_returns.notna().to_numpy(dtype=bool)
    vol_panel = idx["realized_vol_13w"].unstack("ticker").reindex(index=dates, columns=tickers) if "realized_vol_13w" in idx.columns else pd.DataFrame(index=dates, columns=tickers)
    if vol_panel.empty or vol_panel.isna().all().all():
        vol_panel = idx["realized_vol_26w"].unstack("ticker").reindex(index=dates, columns=tickers) if "realized_vol_26w" in idx.columns else pd.DataFrame(index=dates, columns=tickers)

    panel = {
        "x": x,
        "y_top": y_top,
        "y_rank": y_rank,
        "y_return": y_ret,
        "target_mask": target_mask,
        "dates": dates,
        "tickers": tickers,
        "next_returns": next_returns,
        "return_mask": return_mask,
        "vol_panel": vol_panel,
        "state": infer_market_state_by_date(features),
    }
    meta = {
        "feature_columns": feature_cols + ["availability_mask_known_at_t"],
        "n_base_feature_columns": len(feature_cols),
        "n_features": int(x.shape[-1]),
        "n_dates": int(x.shape[0]),
        "n_assets": int(x.shape[1]),
        "input_tensor_shape": list(x.shape),
        "train_only_medians": medians.to_dict(),
        "train_only_stds": stds.to_dict(),
        "feature_missing_rates": missing_rates,
        "target": TARGET,
        "rank_target": RANK_TARGET,
        "return_target": RETURN_TARGET,
        "preprocessing": "Train-only median fill and train-only standardization. Availability mask appended as known-at-date feature.",
        "allocation_training": "Decision losses use scores at date t, masked softmax long-only weights, next-week returns t to t+1, and 10 bps per unit turnover.",
    }
    return panel, meta


def date_indices_for_split(dates: pd.DatetimeIndex, split: str) -> np.ndarray:
    labels = split_for_dates(dates)
    return np.flatnonzero(labels.eq(split).to_numpy())


def make_model_class(torch: Any) -> Any:
    nn = torch.nn

    class AssetMLPScorer(nn.Module):
        def __init__(self, n_features: int, n_assets: int, config: DecisionConfig):
            super().__init__()
            self.config = config
            self.feature_proj = nn.Linear(n_features, config.hidden_dim)
            self.etf_embedding = nn.Embedding(n_assets, config.hidden_dim)
            self.net = nn.Sequential(
                nn.LayerNorm(config.hidden_dim),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim, config.hidden_dim),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(config.hidden_dim, 1),
            )

        def forward(self, x: Any) -> Any:
            n_dates, n_assets, _ = x.shape
            asset_ids = torch.arange(n_assets, device=x.device).unsqueeze(0).expand(n_dates, n_assets)
            h = self.feature_proj(x) + self.etf_embedding(asset_ids)
            return self.net(h).squeeze(-1)

    return AssetMLPScorer


def masked_softmax(torch: Any, logits: Any, available: Any, temperature: float) -> Any:
    masked = logits / temperature
    masked = masked.masked_fill(~available.bool(), -1.0e9)
    weights = torch.softmax(masked, dim=1)
    weights = weights * available.float()
    denom = weights.sum(dim=1, keepdim=True).clamp_min(1.0e-8)
    return weights / denom


def torch_portfolio_path(torch: Any, logits: Any, next_returns: Any, available: Any, config: DecisionConfig) -> tuple[Any, Any, Any, Any]:
    weights = masked_softmax(torch, logits, available, config.temperature)
    returns_filled = torch.nan_to_num(next_returns, nan=0.0)
    gross = (weights * returns_filled).sum(dim=1)
    turnover = torch.cat([torch.zeros(1, device=weights.device), torch.abs(weights[1:] - weights[:-1]).sum(dim=1)])
    cost = turnover * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    return weights, net, turnover, cost


def torch_bce_loss(torch: Any, logits: Any, y: Any, mask: Any, pos_weight: Any) -> Any:
    import torch.nn.functional as F

    if mask.sum().item() == 0:
        return torch.tensor(0.0, device=logits.device)
    return F.binary_cross_entropy_with_logits(logits[mask], y[mask], pos_weight=pos_weight)


def torch_loss(
    torch: Any,
    config: DecisionConfig,
    logits: Any,
    y_top: Any,
    target_mask: Any,
    next_returns: Any,
    return_mask: Any,
    pos_weight: Any,
) -> tuple[Any, dict[str, float]]:
    weights, net, turnover, _ = torch_portfolio_path(torch, logits, next_returns, return_mask, config)
    mean_ret = net.mean()
    vol = net.std(unbiased=False).clamp_min(1.0e-6)
    downside = torch.relu(-net).pow(2).mean().sqrt()
    sharpe = mean_ret / vol
    bce = torch_bce_loss(torch, logits, y_top, target_mask, pos_weight)
    avg_turnover = turnover.mean()
    if config.loss_kind == "prediction_bce":
        loss = bce
    elif config.loss_kind == "decision_return":
        loss = -mean_ret + 0.001 * avg_turnover
    elif config.loss_kind == "decision_sharpe":
        loss = -sharpe + 0.01 * avg_turnover
    elif config.loss_kind == "decision_risk_aware":
        loss = -mean_ret + 0.50 * vol + 1.00 * downside + 0.002 * avg_turnover
    elif config.loss_kind == "hybrid_bce_sharpe":
        loss = 0.75 * bce + 0.25 * (-sharpe + 0.01 * avg_turnover)
    else:
        raise ValueError(f"Unknown loss kind: {config.loss_kind}")
    stats = {
        "portfolio_mean_weekly_return": float(mean_ret.detach().cpu()),
        "portfolio_weekly_vol": float(vol.detach().cpu()),
        "portfolio_sharpe_like": float(sharpe.detach().cpu()),
        "portfolio_downside_vol": float(downside.detach().cpu()),
        "portfolio_avg_turnover": float(avg_turnover.detach().cpu()),
        "bce_loss": float(bce.detach().cpu()),
        "average_top3_weight": float(weights.topk(min(3, weights.shape[1]), dim=1).values.sum(dim=1).mean().detach().cpu()),
    }
    return loss, stats


def evaluate_config_loss(
    torch: Any,
    model: Any,
    panel_tensors: dict[str, Any],
    indices: np.ndarray,
    config: DecisionConfig,
    pos_weight: Any,
) -> tuple[float, dict[str, float]]:
    model.eval()
    with torch.no_grad():
        idx = torch.tensor(indices, dtype=torch.long, device=panel_tensors["x"].device)
        logits = model(panel_tensors["x"][idx])
        loss, stats = torch_loss(
            torch,
            config,
            logits,
            panel_tensors["y_top"][idx],
            panel_tensors["target_mask"][idx],
            panel_tensors["next_returns"][idx],
            panel_tensors["return_mask"][idx],
            pos_weight,
        )
    return float(loss.detach().cpu()), stats


def predict_scores(torch: Any, model: Any, panel: dict[str, Any], device: str, batch_size: int = 96) -> np.ndarray:
    model.eval()
    x = panel["x"]
    scores = np.full((x.shape[0], x.shape[1]), np.nan, dtype="float32")
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            end = min(x.shape[0], start + batch_size)
            xb = torch.from_numpy(x[start:end]).to(device)
            scores[start:end] = model(xb).detach().cpu().numpy().astype("float32")
    return scores


def train_model(torch: Any, panel: dict[str, Any], config: DecisionConfig, device: str) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    set_seed(torch, config.seed)
    Model = make_model_class(torch)
    model = Model(panel["x"].shape[-1], panel["x"].shape[1], config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    panel_tensors = {
        "x": torch.from_numpy(panel["x"]).to(device),
        "y_top": torch.from_numpy(np.nan_to_num(panel["y_top"], nan=0.0).astype("float32")).to(device),
        "target_mask": torch.from_numpy(panel["target_mask"].astype("bool")).to(device),
        "next_returns": torch.from_numpy(panel["next_returns"].to_numpy(dtype="float32")).to(device),
        "return_mask": torch.from_numpy(panel["return_mask"].astype("bool")).to(device),
    }
    dates = panel["dates"]
    train_idx = date_indices_for_split(dates, "train")
    val_idx = date_indices_for_split(dates, "validation")
    train_y = panel["y_top"][train_idx][panel["target_mask"][train_idx]]
    pos = float(np.nansum(train_y == 1.0))
    neg = float(np.nansum(train_y == 0.0))
    pos_weight = torch.tensor(max(1.0, neg / max(pos, 1.0)), dtype=torch.float32, device=device)
    train_tensor_idx = torch.tensor(train_idx, dtype=torch.long, device=device)
    best_state = None
    best_val = math.inf
    best_epoch = -1
    patience_left = config.patience
    rows = []
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        logits = model(panel_tensors["x"][train_tensor_idx])
        loss, train_stats = torch_loss(
            torch,
            config,
            logits,
            panel_tensors["y_top"][train_tensor_idx],
            panel_tensors["target_mask"][train_tensor_idx],
            panel_tensors["next_returns"][train_tensor_idx],
            panel_tensors["return_mask"][train_tensor_idx],
            pos_weight,
        )
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        val_loss, val_stats = evaluate_config_loss(torch, model, panel_tensors, val_idx, config, pos_weight)
        row = {
            "model_name": config.model_name,
            "loss_kind": config.loss_kind,
            "seed": config.seed,
            "epoch": epoch,
            "train_loss": float(loss.detach().cpu()),
            "validation_loss": val_loss,
            "train_bce_loss": train_stats["bce_loss"],
            "validation_bce_loss": val_stats["bce_loss"],
            "train_sharpe_like": train_stats["portfolio_sharpe_like"],
            "validation_sharpe_like": val_stats["portfolio_sharpe_like"],
            "train_avg_turnover": train_stats["portfolio_avg_turnover"],
            "validation_avg_turnover": val_stats["portfolio_avg_turnover"],
            "train_average_top3_weight": train_stats["average_top3_weight"],
            "validation_average_top3_weight": val_stats["average_top3_weight"],
        }
        rows.append(row)
        if pd.notna(val_loss) and val_loss < best_val - 1e-6:
            best_val = val_loss
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = config.patience
        else:
            patience_left -= 1
        if patience_left <= 0:
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    scores = predict_scores(torch, model, panel, device)
    info = {
        "model_name": config.model_name,
        "loss_kind": config.loss_kind,
        "seed": config.seed,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val,
        "pos_weight": float(pos_weight.detach().cpu()),
        "architecture": {
            "model": "per-ETF MLP scorer with learned ETF embedding",
            "input_projection": f"Linear({panel['x'].shape[-1]} -> {config.hidden_dim})",
            "hidden_dim": config.hidden_dim,
            "dropout": config.dropout,
            "output": "one score per ETF per date",
            "allocation_training": "masked softmax long-only portfolio over ETFs",
            "temperature": config.temperature,
        },
    }
    return scores, pd.DataFrame(rows), info


def predictions_from_scores(panel: dict[str, Any], scores: np.ndarray, config: DecisionConfig) -> pd.DataFrame:
    rows = []
    dates = panel["dates"]
    tickers = panel["tickers"]
    splits = split_for_dates(dates)
    for i, date in enumerate(dates):
        for j, ticker in enumerate(tickers):
            rows.append(
                {
                    "Date": date,
                    "ticker": ticker,
                    "split": splits.loc[date],
                    "model_name": config.model_name,
                    "loss_kind": config.loss_kind,
                    "seed": config.seed,
                    "score": float(scores[i, j]) if np.isfinite(scores[i, j]) else np.nan,
                    "actual_target": float(panel["y_top"][i, j]) if np.isfinite(panel["y_top"][i, j]) else np.nan,
                    "actual_rank": float(panel["y_rank"][i, j]) if np.isfinite(panel["y_rank"][i, j]) else np.nan,
                    "actual_forward_return_4w": float(panel["y_return"][i, j]) if np.isfinite(panel["y_return"][i, j]) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def rank_ic_for_dates(scores: np.ndarray, ranks: np.ndarray, mask: np.ndarray, indices: np.ndarray) -> float:
    vals = []
    for idx in indices:
        m = mask[idx] & np.isfinite(scores[idx]) & np.isfinite(ranks[idx])
        if int(m.sum()) < 5:
            continue
        corr = pd.Series(scores[idx][m]).corr(pd.Series(ranks[idx][m]), method="spearman")
        if pd.notna(corr):
            vals.append(float(corr))
    return float(np.mean(vals)) if vals else np.nan


def softmax_weights_from_scores(
    score_table: pd.DataFrame,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    next_returns: pd.DataFrame,
    temperature: float,
) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    hit_rate = pd.Series(np.nan, index=dates)
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        eligible = group[["ticker", "score", "actual_target"]].dropna(subset=["score"])
        available = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        available_lookup = available.notna().to_dict()
        eligible = eligible[eligible["ticker"].map(lambda ticker: bool(available_lookup.get(ticker, False)))]
        if eligible.empty:
            if "BIL" in weights.columns:
                weights.loc[date, "BIL"] = 1.0
            continue
        raw = eligible.set_index("ticker")["score"].astype(float)
        scaled = (raw / temperature) - (raw / temperature).max()
        exp = np.exp(np.clip(scaled, -50, 50))
        w = exp / exp.sum()
        weights.loc[date, w.index] = w.values
        hit_rate.loc[date] = pd.to_numeric(eligible["actual_target"], errors="coerce").mul(w.reindex(eligible["ticker"]).to_numpy()).sum()
    return weights, hit_rate


def topn_weights_from_scores(
    score_table: pd.DataFrame,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    top_n: int,
    weighting: str,
    next_returns: pd.DataFrame,
    vol_panel: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    hit_rate = pd.Series(np.nan, index=dates)
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        available = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        eligible = group[["ticker", "score", "actual_target"]].dropna(subset=["score"])
        available_lookup = available.notna().to_dict()
        eligible = eligible[eligible["ticker"].map(lambda ticker: bool(available_lookup.get(ticker, False)))]
        if eligible.empty:
            if "BIL" in weights.columns:
                weights.loc[date, "BIL"] = 1.0
            continue
        chosen_frame = eligible.sort_values("score", ascending=False).head(top_n)
        chosen = chosen_frame["ticker"].tolist()
        if weighting == "inverse_vol" and not vol_panel.empty and date in vol_panel.index:
            vol = vol_panel.reindex(index=[date], columns=chosen).iloc[0].replace([np.inf, -np.inf], np.nan)
            inv = 1.0 / vol.where(vol > 0.0)
            if inv.notna().sum() and inv.sum(skipna=True) > 0:
                w = inv.fillna(0.0) / inv.fillna(0.0).sum()
            else:
                w = pd.Series(1.0 / len(chosen), index=chosen)
        else:
            w = pd.Series(1.0 / len(chosen), index=chosen)
        weights.loc[date, w.index] = w.values
        hit_rate.loc[date] = pd.to_numeric(chosen_frame["actual_target"], errors="coerce").mean()
    return weights, hit_rate


def add_bil_fallback(weights: pd.DataFrame, exposure: pd.Series) -> pd.DataFrame:
    exposure = exposure.reindex(weights.index).fillna(1.0).clip(0.0, 1.0)
    out = weights.mul(exposure, axis=0)
    if "BIL" in out.columns:
        out["BIL"] = out["BIL"] + (1.0 - exposure)
    return out


def raw_portfolio_returns(weights: pd.DataFrame, next_returns: pd.DataFrame) -> pd.Series:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    return weights.mul(aligned.fillna(0.0)).sum(axis=1)


def overlay_weights(wrapper: str, raw_weights: pd.DataFrame, next_returns: pd.DataFrame, state: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "bil_fallback_original":
        mapping = {"stressed_panic": 0.25, "neutral_mixed": 0.75}
        exposure = state.reindex(dates).map(mapping).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "vol_target_10pct":
        gross = raw_portfolio_returns(raw_weights, next_returns)
        trailing_vol = gross.shift(1).rolling(13, min_periods=8).std(ddof=0) * math.sqrt(52.0)
        exposure = (0.10 / trailing_vol).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.0, 1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"unknown wrapper {wrapper}")


def compute_path(weights: pd.DataFrame, next_returns: pd.DataFrame, exposure: pd.Series, hit_rate: pd.Series) -> pd.DataFrame:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    bil_weight = weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index)
    safe_cols = [c for c in weights.columns if c in SAFE_ASSETS]
    top3 = weights.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1)
    out = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": bil_weight,
            "safe_weight": weights.reindex(columns=safe_cols).sum(axis=1) if safe_cols else 0.0,
            "risky_exposure": 1.0 - bil_weight,
            "model_exposure": exposure.reindex(weights.index).fillna(1.0),
            "holdings_count": weights.gt(0.001).sum(axis=1),
            "top_quintile_hit_rate": hit_rate.reindex(weights.index),
            "top3_weight": top3,
        },
        index=weights.index,
    )
    return out


def max_drawdown(returns: pd.Series) -> float:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {
            "annual_return": np.nan,
            "annual_volatility": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "cvar_5": np.nan,
            "average_turnover": np.nan,
            "annual_cost_drag": np.nan,
            "average_bil_exposure": np.nan,
            "average_risky_exposure": np.nan,
            "average_number_of_etfs_held": np.nan,
            "average_top3_weight": np.nan,
            "top_quintile_hit_rate": np.nan,
            "active_weeks": 0,
        }
    wealth = (1.0 + r).cumprod()
    ann_ret = float(wealth.iloc[-1] ** (52.0 / len(r)) - 1.0) if wealth.iloc[-1] > 0 else np.nan
    ann_vol = float(r.std(ddof=0) * math.sqrt(52.0))
    mdd = max_drawdown(r)
    q5 = r.quantile(0.05)
    return {
        "annual_return": ann_ret,
        "annual_volatility": ann_vol,
        "sharpe": float(ann_ret / ann_vol) if ann_vol > 0 else np.nan,
        "max_drawdown": mdd,
        "calmar": float(ann_ret / abs(mdd)) if pd.notna(mdd) and mdd < 0 else np.nan,
        "cvar_5": float(r[r <= q5].mean()) if pd.notna(q5) else np.nan,
        "average_turnover": float(path.get("turnover", pd.Series(dtype=float)).reindex(r.index).mean()),
        "annual_cost_drag": float(path.get("cost", pd.Series(dtype=float)).reindex(r.index).mean() * 52.0),
        "average_bil_exposure": float(path.get("bil_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_risky_exposure": float(path.get("risky_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_number_of_etfs_held": float(path.get("holdings_count", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_top3_weight": float(path.get("top3_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "top_quintile_hit_rate": float(path.get("top_quintile_hit_rate", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def append_backtest(
    returns_frames: list[pd.DataFrame],
    weights_frames: list[pd.DataFrame],
    summary_rows: list[dict[str, Any]],
    path: pd.DataFrame,
    weights: pd.DataFrame,
    model_name: str,
    loss_kind: str,
    seed: int,
    allocation_method: str,
    wrapper: str,
    rank_ic_by_split: dict[str, float],
) -> None:
    strategy_name = f"{model_name}__{allocation_method}__{wrapper}"
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    dated["model_name"] = model_name
    dated["loss_kind"] = loss_kind
    dated["seed"] = seed
    dated["allocation_method"] = allocation_method
    dated["wrapper"] = wrapper
    dated["cost_bps"] = DEFAULT_COST_BPS
    returns_frames.append(dated.reset_index(drop=True))
    for split in ("train", "validation", "holdout"):
        metrics = calc_metrics(dated[dated["split"].eq(split)])
        metrics.update(
            {
                "strategy_name": strategy_name,
                "model_name": model_name,
                "loss_kind": loss_kind,
                "seed": seed,
                "allocation_method": allocation_method,
                "wrapper": wrapper,
                "split": split,
                "cost_bps": DEFAULT_COST_BPS,
                "rank_ic": rank_ic_by_split.get(split, np.nan),
            }
        )
        summary_rows.append(metrics)
    w = weights.copy()
    w["Date"] = w.index
    long = w.reset_index(drop=True).melt(id_vars="Date", var_name="ticker", value_name="weight")
    long = long[long["weight"].abs() > 1e-6].copy()
    long["strategy_name"] = strategy_name
    long["model_name"] = model_name
    long["loss_kind"] = loss_kind
    long["seed"] = seed
    long["allocation_method"] = allocation_method
    long["wrapper"] = wrapper
    long["split"] = split_for_dates(long["Date"]).values
    weights_frames.append(long)


def run_backtests(panel: dict[str, Any], predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = panel["dates"]
    tickers = panel["tickers"]
    next_returns = panel["next_returns"]
    vol_panel = panel["vol_panel"]
    state = panel["state"]
    returns_frames: list[pd.DataFrame] = []
    weights_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    split_indices = {split: date_indices_for_split(dates, split) for split in ("train", "validation", "holdout")}
    wrappers = ("raw_ml", "bil_fallback_original", "vol_target_10pct")
    for (model_name, loss_kind, seed), group in predictions.groupby(["model_name", "loss_kind", "seed"], sort=True):
        score_matrix = group.pivot(index="Date", columns="ticker", values="score").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
        rank_ic_by_split = {
            split: rank_ic_for_dates(score_matrix, panel["y_rank"], panel["target_mask"], idxs)
            for split, idxs in split_indices.items()
        }
        allocation_specs = [("softmax_all", None, None)]
        for top_n in (10, 15):
            for weighting in ("equal_weight", "inverse_vol"):
                allocation_specs.append((f"top{top_n}_{weighting}", top_n, weighting))
        for allocation_method, top_n, weighting in allocation_specs:
            if allocation_method == "softmax_all":
                raw_weights, hit_rate = softmax_weights_from_scores(group, dates, tickers, next_returns, SOFTMAX_TEMPERATURE)
            else:
                raw_weights, hit_rate = topn_weights_from_scores(group, dates, tickers, int(top_n), str(weighting), next_returns, vol_panel)
            for wrapper in wrappers:
                weights, exposure = overlay_weights(wrapper, raw_weights, next_returns, state)
                path = compute_path(weights, next_returns, exposure, hit_rate)
                append_backtest(
                    returns_frames,
                    weights_frames,
                    summary_rows,
                    path,
                    weights,
                    str(model_name),
                    str(loss_kind),
                    int(seed),
                    allocation_method,
                    wrapper,
                    rank_ic_by_split,
                )
    returns_df = pd.concat(returns_frames, ignore_index=True) if returns_frames else pd.DataFrame()
    weights_df = pd.concat(weights_frames, ignore_index=True) if weights_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return returns_df, weights_df, summary


def read_return_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col).sort_index()
    if "net_return" not in df.columns:
        for candidate in ("return", "weekly_return", "portfolio_return"):
            if candidate in df.columns:
                df["net_return"] = pd.to_numeric(df[candidate], errors="coerce")
                break
    if "net_return" not in df.columns:
        raise ValueError(f"No net_return in {path}")
    df["net_return"] = pd.to_numeric(df["net_return"], errors="coerce")
    df["gross_return"] = pd.to_numeric(df["gross_return"], errors="coerce") if "gross_return" in df.columns else df["net_return"]
    df["turnover"] = pd.to_numeric(df["turnover"], errors="coerce") if "turnover" in df.columns else np.nan
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce") if "cost" in df.columns else 0.0
    if "bil_weight" not in df.columns:
        df["bil_weight"] = np.nan
    return df


def select_project_strategy_files(warnings_list: list[str]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    fixed = {
        "production": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
        "official_shadow": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_combo_abc.csv",
    }
    for name, path in fixed.items():
        if path.exists():
            selected[name] = path
        else:
            warn(f"Project strategy file missing for {name}: {path}", warnings_list)
    if SEQUENCE_PROJECT_COMPARISON_IN.exists():
        comp = pd.read_csv(SEQUENCE_PROJECT_COMPARISON_IN)
        for category in ("phase4b", "phase6", "phase7"):
            sub = comp[comp["category"].eq(category)] if "category" in comp.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No project strategy comparison found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
            path = ROOT / str(row["source_path"])
            if path.exists():
                selected[category] = path
            else:
                warn(f"Selected project strategy path missing for {category}: {path}", warnings_list)
    else:
        warn(f"Optional sequence project comparison missing: {SEQUENCE_PROJECT_COMPARISON_IN}", warnings_list)
    return selected


def load_best_strategy(summary_path: Path, returns_path: Path, label: str, filter_fn: Any, warnings_list: list[str]) -> pd.DataFrame:
    if not summary_path.exists() or not returns_path.exists():
        warn(f"Optional comparison missing for {label}: {summary_path} / {returns_path}", warnings_list)
        return pd.DataFrame()
    try:
        summary = pd.read_csv(summary_path)
        sub = filter_fn(summary)
        if sub.empty:
            warn(f"No matching summary rows for {label}.", warnings_list)
            return pd.DataFrame()
        name = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
        returns = pd.read_csv(returns_path, parse_dates=["Date"])
        frame = returns[returns["strategy_name"].eq(name)].set_index("Date").sort_index()
        if frame.empty:
            warn(f"No return rows for selected comparison {label}: {name}", warnings_list)
        return frame
    except Exception as exc:
        warn(f"Could not load comparison {label}: {exc}", warnings_list)
        return pd.DataFrame()


def benchmark_returns(weekly_returns: pd.DataFrame, warnings_list: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for name, path in select_project_strategy_files(warnings_list).items():
        try:
            out[name] = read_return_file(path)
        except Exception as exc:
            warn(f"Could not read project strategy {name}: {exc}", warnings_list)
    if "SPY" in weekly_returns.columns:
        out["SPY"] = pd.DataFrame({"net_return": weekly_returns["SPY"], "gross_return": weekly_returns["SPY"], "turnover": np.nan, "cost": 0.0})
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond:
        r = 0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]
        out["60_40"] = pd.DataFrame({"net_return": r, "gross_return": r, "turnover": np.nan, "cost": 0.0})
    out["mlx3_tabular"] = load_best_strategy(TABULAR_SUMMARY_IN, TABULAR_RETURNS_IN, "MLX-3 tabular", lambda s: s[(s["split"].eq("holdout")) & (s.get("strategy_type", "model").eq("model") if "strategy_type" in s else True)], warnings_list)
    out["mlx4_mlp"] = load_best_strategy(NN_SUMMARY_IN, NN_RETURNS_IN, "MLX-4 MLP", lambda s: s[(s["split"].eq("holdout")) & (s.get("strategy_type", "model").eq("model") if "strategy_type" in s else True)], warnings_list)
    out["mlx5_sequence"] = load_best_strategy(SEQUENCE_SUMMARY_IN, SEQUENCE_RETURNS_IN, "MLX-5 sequence", lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("model")) & (~s["wrapper"].eq("raw_ml"))], warnings_list)
    out["simple_momentum"] = load_best_strategy(SEQUENCE_SUMMARY_IN, SEQUENCE_RETURNS_IN, "simple momentum", lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("baseline_momentum"))], warnings_list)
    out["mlx6_transformer"] = load_best_strategy(TRANSFORMER_SUMMARY_IN, TRANSFORMER_RETURNS_IN, "MLX-6 Transformer", lambda s: s[(s["split"].eq("holdout")) & (~s["wrapper"].eq("raw_ml"))], warnings_list)
    out["cross_asset_attention"] = load_best_strategy(CAA_SUMMARY_IN, CAA_RETURNS_IN, "Cross-asset attention", lambda s: s[s["split"].eq("holdout")], warnings_list)
    if ENSEMBLE_SUMMARY_JSON_IN.exists() and ENSEMBLE_RETURNS_IN.exists():
        try:
            data = json.loads(ENSEMBLE_SUMMARY_JSON_IN.read_text())
            name = data.get("best_validation_selected_ensemble", {}).get("strategy_name")
            ens = pd.read_csv(ENSEMBLE_RETURNS_IN, parse_dates=["Date"])
            if name:
                out["mlx9_ensemble"] = ens[ens["strategy_name"].eq(name)].set_index("Date").sort_index()
        except Exception as exc:
            warn(f"Could not load MLX-9 ensemble comparison: {exc}", warnings_list)
    else:
        warn("MLX-9 ensemble summary/returns missing for comparison.", warnings_list)
    return {k: v for k, v in out.items() if not v.empty}


def comparison_table(summary: pd.DataFrame, weekly_returns: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    rows = []
    for _, row in summary[summary["split"].eq("holdout")].iterrows():
        d = row.to_dict()
        d["comparison_label"] = d["strategy_name"]
        d["category"] = "decision_focused"
        rows.append(d)
    for name, frame in benchmark_returns(weekly_returns, warnings_list).items():
        path = frame.copy()
        path["split"] = split_for_dates(path.index).values
        metrics = calc_metrics(path[path["split"].eq("holdout")])
        metrics.update({"strategy_name": name, "comparison_label": name, "category": "benchmark", "split": "holdout"})
        rows.append(metrics)
    if SEQUENCE_5C_SUMMARY_IN.exists():
        try:
            data = json.loads(SEQUENCE_5C_SUMMARY_IN.read_text())
            rows.append(
                {
                    "strategy_name": "mlx5c_bil_fallback_mean_summary",
                    "comparison_label": "mlx5c_bil_fallback_mean_summary",
                    "category": "benchmark_summary_only",
                    "split": "holdout",
                    "annual_return": np.nan,
                    "annual_volatility": np.nan,
                    "sharpe": data.get("overall_mean_sharpe", np.nan),
                    "max_drawdown": data.get("overall_worst_case_max_drawdown", np.nan),
                    "calmar": np.nan,
                    "cvar_5": data.get("overall_worst_case_cvar_5", np.nan),
                    "active_weeks": np.nan,
                }
            )
        except Exception as exc:
            warn(f"Could not load MLX-5C summary comparison: {exc}", warnings_list)
    return pd.DataFrame(rows).sort_values(["sharpe", "annual_return"], ascending=[False, False]).reset_index(drop=True)


def state_by_state(returns: pd.DataFrame, state: pd.Series) -> pd.DataFrame:
    rows = []
    hold = returns[returns["split"].eq("holdout")].copy()
    hold["market_state"] = hold["Date"].map(state)
    for (strategy, mstate), group in hold.groupby(["strategy_name", "market_state"], dropna=False):
        metrics = calc_metrics(group.set_index("Date"))
        metrics.update({"strategy_name": strategy, "market_state": mstate, "weeks": int(len(group))})
        rows.append(metrics)
    return pd.DataFrame(rows)


def exposure_audit(weights: pd.DataFrame, universe_meta: pd.DataFrame, focus_strategies: list[str]) -> pd.DataFrame:
    rows = []
    if weights.empty:
        return pd.DataFrame()
    category = {}
    if not universe_meta.empty and {"ticker", "category"}.issubset(universe_meta.columns):
        category = universe_meta.drop_duplicates("ticker").set_index("ticker")["category"].to_dict()
    hold = weights[weights["split"].eq("holdout") & weights["strategy_name"].isin(focus_strategies)].copy()
    for strategy, group in hold.groupby("strategy_name"):
        pivot = group.pivot_table(index="Date", columns="ticker", values="weight", aggfunc="sum").fillna(0.0)
        avg = pivot.mean().sort_values(ascending=False)
        for ticker, value in avg.items():
            rows.append(
                {
                    "strategy_name": strategy,
                    "audit_type": "ticker",
                    "item": ticker,
                    "category": category.get(ticker, "unknown"),
                    "average_weight": float(value),
                    "max_weight": float(pivot[ticker].max()),
                    "holding_frequency": float((pivot[ticker] > 0.01).mean()),
                }
            )
        for cat in sorted(set(category.get(t, "unknown") for t in pivot.columns)):
            cols = [t for t in pivot.columns if category.get(t, "unknown") == cat]
            series = pivot[cols].sum(axis=1)
            rows.append(
                {
                    "strategy_name": strategy,
                    "audit_type": "category",
                    "item": cat,
                    "category": cat,
                    "average_weight": float(series.mean()),
                    "max_weight": float(series.max()),
                    "holding_frequency": float((series > 0.01).mean()),
                }
            )
        summaries = {
            "average_top3_weight": pivot.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1),
            "average_SPY_QQQ_SMH_weight": pivot.reindex(columns=[c for c in ["SPY", "QQQ", "SMH"] if c in pivot.columns]).sum(axis=1),
            "average_BIL_weight": pivot["BIL"] if "BIL" in pivot.columns else pd.Series(0.0, index=pivot.index),
            "average_safe_asset_weight": pivot.reindex(columns=[c for c in pivot.columns if c in SAFE_ASSETS]).sum(axis=1),
            "average_sector_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "US sectors"]).sum(axis=1),
            "average_commodities_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "Commodities"]).sum(axis=1),
        }
        for label, series in summaries.items():
            rows.append(
                {
                    "strategy_name": strategy,
                    "audit_type": "summary",
                    "item": label,
                    "category": "",
                    "average_weight": float(series.mean()),
                    "max_weight": float(series.max()),
                    "holding_frequency": np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(["strategy_name", "audit_type", "average_weight"], ascending=[True, True, False])


def walkforward_summary(returns_df: pd.DataFrame, focus: list[str]) -> pd.DataFrame:
    windows = {
        "2017_2018": (pd.Timestamp("2017-01-01"), pd.Timestamp("2018-12-31")),
        "2019_2020": (pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-31")),
        "2021_2022": (pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-31")),
        "2023_2026": (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
    }
    rows = []
    for strategy in focus:
        path = returns_df[returns_df["strategy_name"].eq(strategy)].set_index("Date").sort_index()
        if path.empty:
            continue
        for window, (start, end) in windows.items():
            sub = path.loc[(path.index >= start) & (path.index <= end)]
            metrics = calc_metrics(sub)
            metrics.update({"strategy_name": strategy, "window": window})
            rows.append(metrics)
    return pd.DataFrame(rows)


def best_row(summary: pd.DataFrame, split: str, subset: pd.Series | None = None) -> dict[str, Any]:
    sub = summary[(summary["split"].eq(split)) & (summary["active_weeks"].ge(50))].copy()
    if subset is not None:
        sub = sub[subset.reindex(sub.index).fillna(False)]
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "max_drawdown", "cvar_5", "annual_return"], ascending=[False, False, False, False]).iloc[0].to_dict()


def comp_value(comparison: pd.DataFrame, strategy: str, metric: str) -> float:
    sub = comparison[comparison["strategy_name"].eq(strategy)]
    if sub.empty or metric not in sub.columns:
        return np.nan
    value = sub.iloc[0][metric]
    return float(value) if pd.notna(value) else np.nan


def choose_recommendation(selected_holdout: dict[str, Any], comparison: pd.DataFrame, baseline_holdout: dict[str, Any]) -> str:
    if not selected_holdout:
        return "REJECT"
    sharpe = float(selected_holdout.get("sharpe", np.nan))
    dd = float(selected_holdout.get("max_drawdown", np.nan))
    ann_ret = float(selected_holdout.get("annual_return", np.nan))
    bil_exposure = float(selected_holdout.get("average_bil_exposure", np.nan))
    top3_weight = float(selected_holdout.get("average_top3_weight", np.nan))
    baseline = float(baseline_holdout.get("sharpe", np.nan))
    phase4b = comp_value(comparison, "phase4b", "sharpe")
    mlx9 = comp_value(comparison, "mlx9_ensemble", "sharpe")
    if (pd.notna(ann_ret) and ann_ret < 0.04) or (pd.notna(bil_exposure) and bil_exposure > 0.50) or (pd.notna(top3_weight) and top3_weight > 0.85):
        return "PROMISING LEARNING RESULT BUT NOT PORTFOLIO CANDIDATE"
    if pd.notna(sharpe) and pd.notna(phase4b) and sharpe > phase4b and pd.notna(dd) and dd > -0.16:
        return "NEEDS WALK-FORWARD / MULTI-SEED BEFORE JUDGMENT"
    if pd.notna(sharpe) and pd.notna(mlx9) and sharpe > mlx9 and pd.notna(baseline) and sharpe > baseline:
        return "PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION"
    if pd.notna(sharpe) and pd.notna(baseline) and sharpe > baseline:
        return "PROMISING LEARNING RESULT BUT NOT PORTFOLIO CANDIDATE"
    if pd.notna(sharpe) and sharpe > 0:
        return "KEEP AS RESEARCH ONLY"
    return "REJECT"


def write_notes(
    torch_meta: dict[str, Any],
    preprocess_meta: dict[str, Any],
    model_infos: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    candidate_defs: dict[str, Any],
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    state: pd.DataFrame,
    exposure: pd.DataFrame,
    walkforward: pd.DataFrame,
    summary_json: dict[str, Any],
    warnings_list: list[str],
) -> None:
    best_val = summary_json.get("best_validation_model", {})
    selected_hold = summary_json.get("validation_selected_holdout", {})
    best_hold = summary_json.get("best_holdout_model", {})
    baseline = summary_json.get("best_prediction_baseline_holdout", {})
    best_decision = summary_json.get("best_decision_focused_holdout", {})
    arch = model_infos[0].get("architecture", {}) if model_infos else {}
    notes = f"""# Phase MLX Decision-Focused Portfolio Learning Notes

## Research-Only Warning

Phase MLX decision-focused learning is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Decision-focused learning trains a model by looking at the quality of the decision created from its predictions. In this sprint, the decision is a long-only ETF allocation. The model produces one score per ETF at date `t`; those scores are converted into portfolio weights; the portfolio earns next-week returns; and the loss can directly reward better portfolio outcomes.

Predict-then-optimize is the normal workflow: train a model to predict a label such as top-quintile membership, then separately turn predictions into rankings or weights. That can fail in finance because a model can improve classification accuracy while still picking assets with bad portfolio-level risk, high turnover, poor diversification, or weak downside behavior.

Portfolio loss is different from prediction loss. A prediction loss asks whether an ETF label was right. A portfolio loss asks whether the weights created from scores had good net return, acceptable volatility, manageable turnover, and tolerable downside. This is closer to the actual goal of an ETF allocator.

Differentiable portfolio learning means the allocation step is written in a way that gradients can flow through it. This first version uses a masked softmax allocation: higher model scores receive larger long-only weights, unavailable ETFs are masked out, and all weights sum to one. It is a simplification, not a full differentiable optimizer.

The Sharpe-like loss uses mean weekly net return divided by weekly volatility, with a small numerical stabilizer. Turnover and risk penalties discourage fragile high-churn or high-volatility allocations. These losses can overfit badly because the model is allowed to chase the exact historical portfolio objective. That is powerful, but dangerous.

This connects to decision-focused learning, predict-then-optimize, SPO-style losses, differentiable optimization layers such as `cvxpylayers`, and portfolio-learning libraries such as DeepDow. This script does not use cvxpy layers; it uses a CPU-safe softmax approximation first.

## Technical Setup

- Torch availability: {torch_meta}
- Input tensor shape: `{preprocess_meta.get('input_tensor_shape')}` as `[dates, ETFs, features]`
- ETF universe size: {preprocess_meta.get('n_assets')}
- Features used: {preprocess_meta.get('n_features')} total, including an availability mask
- Architecture: {arch}
- Losses tested: {summary_json.get('losses_run')}
- Allocation transformation: masked softmax over available ETFs for decision losses; evaluation also tests top-10/top-15 equal/inverse-vol portfolios
- Transaction cost assumption: {DEFAULT_COST_BPS:.0f} bps per unit turnover
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: no target-like input columns; action at date `t` uses scores known at date `t` and earns next-week returns
- Candidate definitions: {candidate_defs}
- Skipped variants: {skipped}

## Results

- Models/losses run: {summary_json.get('models_run')}
- Best prediction baseline holdout: `{baseline.get('strategy_name', 'n/a')}` Sharpe {num(baseline.get('sharpe'))}
- Best decision-focused holdout: `{best_decision.get('strategy_name', 'n/a')}` Sharpe {num(best_decision.get('sharpe'))}
- Best validation-selected model: `{best_val.get('strategy_name', 'n/a')}` with validation Sharpe {num(best_val.get('sharpe'))}
- Validation-selected holdout annual return: {pct(selected_hold.get('annual_return'))}
- Validation-selected holdout Sharpe: {num(selected_hold.get('sharpe'))}
- Validation-selected max drawdown: {pct(selected_hold.get('max_drawdown'))}
- Validation-selected CVaR 5%: {pct(selected_hold.get('cvar_5'))}
- Best holdout diagnostic model: `{best_hold.get('strategy_name', 'n/a')}` Sharpe {num(best_hold.get('sharpe'))}

Important caveat: the strongest risk-aware result is low-return, low-volatility, BIL/bond-heavy, and highly concentrated. Its high Sharpe is educational evidence that the portfolio-aware loss found a defensive allocation, not evidence that it discovered robust offensive alpha.

### Top Holdout Strategies

{markdown_table(summary[summary['split'].eq('holdout')].sort_values(['sharpe', 'annual_return'], ascending=[False, False]), ['strategy_name', 'loss_kind', 'allocation_method', 'wrapper', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_turnover', 'average_bil_exposure', 'average_top3_weight', 'rank_ic'], 20)}

### Strategy Comparison

{markdown_table(comparison, ['strategy_name', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure'], 30)}

### Walk-Forward Window Evaluation

{markdown_table(walkforward, ['strategy_name', 'window', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'active_weeks'], 40)}

### State-By-State Results

{markdown_table(state, ['strategy_name', 'market_state', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_risky_exposure', 'weeks'], 40)}

### Exposure Audit

{markdown_table(exposure, ['strategy_name', 'audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], 50)}

## Interpretation

- Did decision-focused training beat the prediction-trained baseline? {summary_json.get('decision_focused_beats_prediction_baseline')}
- Did the validation-selected model beat MLX-5C mean Sharpe? {summary_json.get('validation_selected_beats_mlx5c_sharpe')}
- Did it beat MLX-9? {summary_json.get('validation_selected_beats_mlx9_sharpe')}
- Did it beat production? {summary_json.get('validation_selected_beats_production_sharpe')}
- Did it beat Phase 4B? {summary_json.get('validation_selected_beats_phase4b_sharpe')}
- Final recommendation: **{summary_json.get('final_recommendation')}**

The key learning question is whether a portfolio-aware objective reduces the mismatch between labels and allocation quality. This first version is deliberately simplified. A stronger next version should use explicit ranking or SPO-style decision losses, differentiable mean-variance or CVaR layers, better validation discipline, and full walk-forward retraining.

## Warnings

{chr(10).join(f'- {w}' for w in warnings_list)}
"""
    NOTES_OUT.write_text(notes)


def write_skipped_outputs(reason: str, torch_meta: dict[str, Any], warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    empty = pd.DataFrame()
    empty.to_parquet(PREDICTIONS_OUT, index=False)
    empty.to_parquet(WEIGHTS_OUT, index=False)
    empty.to_csv(RETURNS_OUT, index=False)
    empty.to_csv(SUMMARY_OUT, index=False)
    empty.to_csv(TRAINING_CURVES_OUT, index=False)
    empty.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    empty.to_csv(STATE_BY_STATE_OUT, index=False)
    empty.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps({"research_only": True, "production_valid": False, "reason": reason}, indent=2))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps({}, indent=2))
    SKIPPED_RUNS_OUT.write_text(json.dumps([{"component": "torch_training", "reason": reason}], indent=2))
    summary = {"phase": "decision_focused_portfolio_learning", "research_only": True, "production_valid": False, "torch": torch_meta, "reason": reason, "warnings": warnings_list}
    SUMMARY_JSON_OUT.write_text(json.dumps(summary, indent=2, default=json_default))
    NOTES_OUT.write_text(f"""# Phase MLX Decision-Focused Portfolio Learning Notes

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

Decision-focused learning trains a model based on the portfolio decision created by its scores, not only a prediction label. Training was skipped because `{reason}`.

## Results

No model was trained.
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    warn("Experimental research-only Phase MLX output; not production-valid.", warnings_list)
    warn("Expanded ETF/yfinance research data can introduce selection bias and data-mining risk.", warnings_list)
    torch_meta = torch_status()
    if not torch_meta.get("available"):
        reason = "torch is missing or failed to import"
        warn(reason, warnings_list)
        write_skipped_outputs(reason, torch_meta, warnings_list)
        print("Phase MLX decision-focused learning skipped: torch unavailable.")
        return
    import torch

    device = "cpu"
    features, targets, weekly_returns, universe_meta = load_inputs(warnings_list)
    panel, preprocess_meta = build_panel(features, targets, weekly_returns)
    skipped = [
        {"variant": "differentiable_top_k", "reason": "deferred; first version uses masked softmax and separate top-N evaluation"},
        {"variant": "cvxpylayers_or_spo_loss", "reason": "deferred; optional package/deeper optimizer integration not required for first CPU-safe sprint"},
        {"variant": "full_walk_forward_retraining", "reason": "deferred; selected predictions are evaluated by window without retraining per fold"},
        {"variant": "seed_2", "reason": "skipped to keep first decision-focused run bounded on CPU"},
        {"variant": "true_drawdown_gradient_penalty", "reason": "simplified to volatility/downside/turnover penalties for stability"},
    ]
    loss_kinds = ["prediction_bce", "decision_return", "decision_sharpe", "decision_risk_aware", "hybrid_bce_sharpe"]
    configs = [
        DecisionConfig(model_name=f"{loss_kind}_mlp_seed{seed}", loss_kind=loss_kind, seed=seed)
        for loss_kind in loss_kinds
        for seed in SEEDS
    ]
    candidate_defs = {
        "prediction_bce": "Predict-then-optimize baseline trained on top_quintile_forward_4w BCE.",
        "decision_return": "Decision-focused loss = negative mean weekly net portfolio return plus small turnover penalty.",
        "decision_sharpe": "Decision-focused loss = negative differentiable Sharpe-like objective plus turnover penalty.",
        "decision_risk_aware": "Decision-focused loss with return, volatility, downside, and turnover terms.",
        "hybrid_bce_sharpe": "Hybrid supervised BCE plus decision-focused Sharpe-like loss.",
        "allocation": "Training uses masked softmax long-only weights over all available ETFs; evaluation also tests top10/top15 equal and inverse-vol portfolios.",
        "overlays": ["raw_ml", "bil_fallback_original", "vol_target_10pct"],
    }
    all_predictions: list[pd.DataFrame] = []
    all_curves: list[pd.DataFrame] = []
    model_infos: list[dict[str, Any]] = []
    for i, config in enumerate(configs, start=1):
        print(f"Running decision-focused model {i}/{len(configs)}: {config.model_name}")
        scores, curves, info = train_model(torch, panel, config, device)
        all_curves.append(curves)
        model_infos.append(info)
        all_predictions.append(predictions_from_scores(panel, scores, config))
    predictions = pd.concat(all_predictions, ignore_index=True)
    training_curves = pd.concat(all_curves, ignore_index=True)
    returns_df, weights_df, summary = run_backtests(panel, predictions)
    comparison = comparison_table(summary, weekly_returns, warnings_list)
    best_val = best_row(summary, "validation")
    selected_holdout = {}
    if best_val:
        sub = summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq(best_val["strategy_name"]))]
        selected_holdout = sub.iloc[0].to_dict() if not sub.empty else {}
    best_holdout = best_row(summary, "holdout")
    baseline_holdout = best_row(summary, "holdout", subset=summary["loss_kind"].eq("prediction_bce"))
    decision_holdout = best_row(summary, "holdout", subset=~summary["loss_kind"].eq("prediction_bce"))
    focus = sorted(set([best_val.get("strategy_name"), best_holdout.get("strategy_name")]) - {None, ""})
    state = state_by_state(returns_df[returns_df["strategy_name"].isin(focus)], panel["state"])
    exposure = exposure_audit(weights_df, universe_meta, focus)
    walk = walkforward_summary(returns_df, focus)
    selected_sharpe = selected_holdout.get("sharpe", np.nan)
    baseline_sharpe = baseline_holdout.get("sharpe", np.nan)

    summary_json = {
        "phase": "decision_focused_portfolio_learning",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "torch": torch_meta,
        "device": device,
        "models_run": [c.model_name for c in configs],
        "losses_run": loss_kinds,
        "seeds_run": list(SEEDS),
        "universe_size": preprocess_meta["n_assets"],
        "input_tensor_shape": preprocess_meta["input_tensor_shape"],
        "model_architecture": model_infos[0].get("architecture", {}) if model_infos else {},
        "allocation_method": "masked softmax long-only portfolio for training; softmax/top-N variants for evaluation",
        "transaction_cost_bps": DEFAULT_COST_BPS,
        "skipped_runs": skipped,
        "best_prediction_baseline_holdout": baseline_holdout,
        "best_decision_focused_holdout": decision_holdout,
        "best_validation_model": best_val,
        "validation_selected_holdout": selected_holdout,
        "best_holdout_model": best_holdout,
        "decision_focused_beats_prediction_baseline": bool(pd.notna(decision_holdout.get("sharpe", np.nan)) and pd.notna(baseline_sharpe) and decision_holdout["sharpe"] > baseline_sharpe),
        "validation_selected_beats_mlx5c_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")),
        "validation_selected_beats_mlx9_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx9_ensemble", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx9_ensemble", "sharpe")),
        "validation_selected_beats_production_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "production", "sharpe")) and selected_sharpe > comp_value(comparison, "production", "sharpe")),
        "validation_selected_beats_phase4b_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "phase4b", "sharpe")) and selected_sharpe > comp_value(comparison, "phase4b", "sharpe")),
        "validation_selected_beats_production_annual_return": bool(pd.notna(selected_holdout.get("annual_return", np.nan)) and pd.notna(comp_value(comparison, "production", "annual_return")) and selected_holdout["annual_return"] > comp_value(comparison, "production", "annual_return")),
        "validation_selected_beats_phase4b_annual_return": bool(pd.notna(selected_holdout.get("annual_return", np.nan)) and pd.notna(comp_value(comparison, "phase4b", "annual_return")) and selected_holdout["annual_return"] > comp_value(comparison, "phase4b", "annual_return")),
        "validation_selected_cash_like_warning": bool(pd.notna(selected_holdout.get("annual_return", np.nan)) and selected_holdout["annual_return"] < 0.04 or pd.notna(selected_holdout.get("average_bil_exposure", np.nan)) and selected_holdout["average_bil_exposure"] > 0.50),
        "final_recommendation": choose_recommendation(selected_holdout, comparison, baseline_holdout),
        "warnings": warnings_list + [
            "Best risk-aware result is BIL/bond-heavy and low-return; high Sharpe should not be interpreted as robust offensive alpha.",
            "No decision-focused model is promoted automatically.",
        ],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "weights": str(WEIGHTS_OUT.relative_to(ROOT)),
            "returns": str(RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "state_by_state": str(STATE_BY_STATE_OUT.relative_to(ROOT)),
            "exposure_audit": str(EXPOSURE_AUDIT_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "candidate_definitions": str(CANDIDATE_DEFINITIONS_OUT.relative_to(ROOT)),
            "skipped_runs": str(SKIPPED_RUNS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    weights_df.to_parquet(WEIGHTS_OUT, index=False)
    returns_df.to_csv(RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    training_curves.to_csv(TRAINING_CURVES_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    state.to_csv(STATE_BY_STATE_OUT, index=False)
    exposure.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(preprocess_meta, indent=2, default=json_default))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps(candidate_defs, indent=2, default=json_default))
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(torch_meta, preprocess_meta, model_infos, skipped, candidate_defs, summary, comparison, state, exposure, walk, summary_json, summary_json["warnings"])

    print("Phase MLX decision-focused portfolio learning")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Torch: {torch_meta}")
    print(f"Device used: {device}")
    print(f"Input tensor shape: {preprocess_meta['input_tensor_shape']}")
    print(f"ETF universe size: {preprocess_meta['n_assets']}")
    print(f"Models/losses run: {[c.model_name for c in configs]}")
    print(f"Best validation model: {best_val.get('strategy_name') if best_val else 'n/a'}")
    print(f"Validation-selected holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Best holdout model: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Best holdout Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Best prediction baseline holdout Sharpe: {baseline_holdout.get('sharpe') if baseline_holdout else np.nan}")
    print(f"Best decision-focused holdout Sharpe: {decision_holdout.get('sharpe') if decision_holdout else np.nan}")
    print(f"Final recommendation: {summary_json['final_recommendation']}")
    print("Outputs:")
    for path in [
        PREDICTIONS_OUT,
        WEIGHTS_OUT,
        RETURNS_OUT,
        SUMMARY_OUT,
        TRAINING_CURVES_OUT,
        STRATEGY_COMPARISON_OUT,
        STATE_BY_STATE_OUT,
        EXPOSURE_AUDIT_OUT,
        PREPROCESSING_METADATA_OUT,
        CANDIDATE_DEFINITIONS_OUT,
        SKIPPED_RUNS_OUT,
        SUMMARY_JSON_OUT,
        NOTES_OUT,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
