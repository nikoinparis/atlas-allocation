#!/usr/bin/env python3
"""
Phase MLX-10: cross-asset attention ETF ranker.

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
TABULAR_DIR = ML_DIR / "tabular_ml"
NN_DIR = ML_DIR / "neural_networks"
OUTPUT_DIR = ML_DIR / "cross_asset_attention"
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

PREDICTIONS_OUT = OUTPUT_DIR / "cross_asset_attention_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "cross_asset_attention_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "cross_asset_attention_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "cross_asset_attention_training_curves.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "cross_asset_attention_strategy_comparison.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "cross_asset_attention_state_by_state.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "cross_asset_attention_exposure_audit.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "cross_asset_attention_preprocessing_metadata.json"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "cross_asset_attention_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "cross_asset_attention_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_cross_asset_attention_ranker_notes.md"

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
MAX_EPOCHS = 30
PATIENCE = 5
BATCH_SIZE_DATES = 32
SEEDS = (0, 1)
SAFE_ASSETS = {"BIL", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD"}


@dataclass(frozen=True)
class AttentionConfig:
    model_name: str
    seed: int
    d_model: int = 32
    nhead: int = 4
    num_layers: int = 1
    dim_feedforward: int = 64
    dropout: float = 0.20
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
        if col in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "average_turnover", "annual_cost_drag", "average_bil_exposure"}:
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


def load_inputs(warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required cross-asset attention inputs missing: {missing}")
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
        warn("BIL returns are missing; fallback overlays will be skipped or less meaningful.", warnings_list)
    return features, targets, weekly_returns, universe_meta


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


def build_tensor_panel(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    weekly_returns: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
    }
    return panel, meta


class CrossAssetDateDataset:
    def __init__(self, torch: Any, panel: dict[str, Any], date_indices: np.ndarray):
        self.torch = torch
        self.x = panel["x"]
        self.y = panel["y_top"]
        self.mask = panel["target_mask"]
        self.indices = date_indices.astype(np.int64)

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, i: int) -> tuple[Any, Any, Any, Any]:
        idx = int(self.indices[i])
        return (
            self.torch.from_numpy(self.x[idx]),
            self.torch.from_numpy(np.nan_to_num(self.y[idx], nan=0.0).astype("float32")),
            self.torch.from_numpy(self.mask[idx].astype("bool")),
            self.torch.tensor(idx, dtype=self.torch.long),
        )


def make_model_class(torch: Any) -> Any:
    nn = torch.nn

    class CrossAssetAttentionRanker(nn.Module):
        def __init__(self, n_features: int, n_assets: int, config: AttentionConfig):
            super().__init__()
            self.config = config
            self.feature_proj = nn.Linear(n_features, config.d_model)
            self.etf_embedding = nn.Embedding(n_assets, config.d_model)
            layer = nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=config.nhead,
                dim_feedforward=config.dim_feedforward,
                dropout=config.dropout,
                activation="gelu",
                batch_first=True,
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=config.num_layers)
            self.norm = nn.LayerNorm(config.d_model)
            self.head = nn.Linear(config.d_model, 1)

        def forward(self, x: Any) -> Any:
            batch, n_assets, _ = x.shape
            asset_ids = torch.arange(n_assets, device=x.device).unsqueeze(0).expand(batch, n_assets)
            h = self.feature_proj(x) + self.etf_embedding(asset_ids)
            h = self.encoder(h)
            h = self.norm(h)
            return self.head(h).squeeze(-1)

    return CrossAssetAttentionRanker


def date_indices_for_split(dates: pd.DatetimeIndex, split: str) -> np.ndarray:
    labels = split_for_dates(dates)
    return np.flatnonzero(labels.eq(split).to_numpy())


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


def top_quintile_hit_for_dates(scores: np.ndarray, y_top: np.ndarray, mask: np.ndarray, indices: np.ndarray, top_n: int = 10) -> float:
    vals = []
    for idx in indices:
        m = mask[idx] & np.isfinite(scores[idx])
        if int(m.sum()) < top_n:
            continue
        eligible = np.flatnonzero(m)
        chosen = eligible[np.argsort(scores[idx][eligible])[-top_n:]]
        hit = np.nanmean(y_top[idx][chosen])
        if np.isfinite(hit):
            vals.append(float(hit))
    return float(np.mean(vals)) if vals else np.nan


def evaluate_loss(torch: Any, model: Any, loader: Any, device: str, pos_weight: Any) -> float:
    import torch.nn.functional as F

    model.eval()
    losses = []
    with torch.no_grad():
        for xb, yb, mb, _ in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            mb = mb.to(device)
            logits = model(xb)
            if mb.sum().item() == 0:
                continue
            loss = F.binary_cross_entropy_with_logits(logits[mb], yb[mb], pos_weight=pos_weight)
            losses.append(float(loss.item()))
    return float(np.mean(losses)) if losses else np.nan


def predict_scores(torch: Any, model: Any, panel: dict[str, Any], device: str, batch_size: int = 64) -> np.ndarray:
    model.eval()
    x = panel["x"]
    scores = np.full((x.shape[0], x.shape[1]), np.nan, dtype="float32")
    with torch.no_grad():
        for start in range(0, x.shape[0], batch_size):
            end = min(x.shape[0], start + batch_size)
            xb = torch.from_numpy(x[start:end]).to(device)
            logits = model(xb).detach().cpu().numpy().astype("float32")
            scores[start:end] = logits
    return scores


def train_model(torch: Any, panel: dict[str, Any], config: AttentionConfig, device: str) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    set_seed(torch, config.seed)
    Dataset = CrossAssetDateDataset
    DataLoader = torch.utils.data.DataLoader
    Model = make_model_class(torch)
    dates = panel["dates"]
    train_idx = date_indices_for_split(dates, "train")
    val_idx = date_indices_for_split(dates, "validation")
    train_ds = Dataset(torch, panel, train_idx)
    val_ds = Dataset(torch, panel, val_idx)
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE_DATES, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE_DATES, shuffle=False)
    model = Model(panel["x"].shape[-1], panel["x"].shape[1], config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    valid_y = panel["y_top"][train_idx][panel["target_mask"][train_idx]]
    pos = float(np.nansum(valid_y == 1.0))
    neg = float(np.nansum(valid_y == 0.0))
    pos_weight_value = max(1.0, neg / max(pos, 1.0))
    pos_weight = torch.tensor(pos_weight_value, dtype=torch.float32, device=device)

    import torch.nn.functional as F

    best_state = None
    best_val = math.inf
    best_epoch = -1
    patience_left = config.patience
    rows = []
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        batch_losses = []
        for xb, yb, mb, _ in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            mb = mb.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(xb)
            if mb.sum().item() == 0:
                continue
            loss = F.binary_cross_entropy_with_logits(logits[mb], yb[mb], pos_weight=pos_weight)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            batch_losses.append(float(loss.item()))
        train_loss = float(np.mean(batch_losses)) if batch_losses else np.nan
        val_loss = evaluate_loss(torch, model, val_loader, device, pos_weight)
        scores = predict_scores(torch, model, panel, device, batch_size=128)
        val_rank_ic = rank_ic_for_dates(scores, panel["y_rank"], panel["target_mask"], val_idx)
        val_top_hit = top_quintile_hit_for_dates(scores, panel["y_top"], panel["target_mask"], val_idx, top_n=10)
        rows.append(
            {
                "model_name": config.model_name,
                "seed": config.seed,
                "epoch": epoch,
                "train_loss": train_loss,
                "validation_loss": val_loss,
                "validation_rank_ic": val_rank_ic,
                "validation_top10_top_quintile_hit_rate": val_top_hit,
            }
        )
        if pd.notna(val_loss) and val_loss < best_val - 1e-5:
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
    scores = predict_scores(torch, model, panel, device, batch_size=128)
    info = {
        "model_name": config.model_name,
        "seed": config.seed,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val,
        "pos_weight": pos_weight_value,
        "architecture": {
            "input_projection": f"Linear({panel['x'].shape[-1]} -> {config.d_model})",
            "etf_embedding": True,
            "attention_axis": "asset/cross-section dimension at one date",
            "d_model": config.d_model,
            "nhead": config.nhead,
            "num_layers": config.num_layers,
            "dim_feedforward": config.dim_feedforward,
            "dropout": config.dropout,
            "output": "one logit score per ETF per date",
        },
    }
    return scores, pd.DataFrame(rows), info


def predictions_from_scores(panel: dict[str, Any], scores: np.ndarray, config: AttentionConfig) -> pd.DataFrame:
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
                    "seed": config.seed,
                    "target": TARGET,
                    "loss_function": "BCEWithLogitsLoss",
                    "score": float(scores[i, j]) if np.isfinite(scores[i, j]) else np.nan,
                    "actual_target": float(panel["y_top"][i, j]) if np.isfinite(panel["y_top"][i, j]) else np.nan,
                    "actual_rank": float(panel["y_rank"][i, j]) if np.isfinite(panel["y_rank"][i, j]) else np.nan,
                    "actual_forward_return_4w": float(panel["y_return"][i, j]) if np.isfinite(panel["y_return"][i, j]) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def weights_from_scores(
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
    has_bil = "BIL" in tickers
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        available = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        eligible = group[["ticker", "score", "actual_target"]].dropna(subset=["score"])
        available_lookup = available.notna().to_dict()
        eligible = eligible[eligible["ticker"].map(lambda ticker: bool(available_lookup.get(ticker, False)))]
        if eligible.empty:
            if has_bil:
                weights.loc[date, "BIL"] = 1.0
            continue
        chosen_frame = eligible.sort_values("score", ascending=False).head(top_n)
        chosen = chosen_frame["ticker"].tolist()
        if not chosen:
            if has_bil:
                weights.loc[date, "BIL"] = 1.0
            continue
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


def overlay_weights(wrapper: str, raw_weights: pd.DataFrame, next_returns: pd.DataFrame, state: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "bil_fallback_original":
        mapping = {"stressed_panic": 0.25, "neutral_mixed": 0.75}
        exposure = state.reindex(dates).map(mapping).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "regime_gate_original":
        mapping = {"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}
        exposure = state.reindex(dates).map(mapping).fillna(0.70)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "defensive_first":
        mapping = {"calm_trend": 0.90, "recovery_confirmed": 0.90, "neutral_mixed": 0.55, "recovery_fragile": 0.50, "stressed_panic": 0.15}
        exposure = state.reindex(dates).map(mapping).fillna(0.60)
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
    out = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": bil_weight,
            "safe_weight": weights.reindex(columns=safe_cols).sum(axis=1) if safe_cols else 0.0,
            "ml_exposure": exposure.reindex(weights.index).fillna(1.0),
            "holdings_count": weights.gt(0.001).sum(axis=1),
            "top_quintile_hit_rate": hit_rate.reindex(weights.index),
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
            "average_ml_exposure": np.nan,
            "average_number_of_etfs_held": np.nan,
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
        "average_ml_exposure": float(path.get("ml_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_number_of_etfs_held": float(path.get("holdings_count", pd.Series(dtype=float)).reindex(r.index).mean()),
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
    seed: int,
    top_n: int,
    weighting: str,
    wrapper: str,
    rank_ic_by_split: dict[str, float],
) -> None:
    strategy_name = f"{model_name}__top{top_n}__{weighting}__{wrapper}"
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    dated["model_name"] = model_name
    dated["seed"] = seed
    dated["target"] = TARGET
    dated["loss_function"] = "BCEWithLogitsLoss"
    dated["top_n"] = top_n
    dated["weighting"] = weighting
    dated["wrapper"] = wrapper
    dated["cost_bps"] = DEFAULT_COST_BPS
    returns_frames.append(dated.reset_index(drop=True))
    for split in ("train", "validation", "holdout"):
        metrics = calc_metrics(dated[dated["split"].eq(split)])
        metrics.update(
            {
                "strategy_name": strategy_name,
                "model_name": model_name,
                "seed": seed,
                "target": TARGET,
                "loss_function": "BCEWithLogitsLoss",
                "top_n": top_n,
                "weighting": weighting,
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
    long = long[long["weight"].abs() > 1e-9].copy()
    long["strategy_name"] = strategy_name
    long["model_name"] = model_name
    long["seed"] = seed
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
    wrappers = ("raw_ml", "bil_fallback_original", "regime_gate_original", "defensive_first")
    for (model_name, seed), group in predictions.groupby(["model_name", "seed"], sort=True):
        group = group.copy()
        score_matrix = group.pivot(index="Date", columns="ticker", values="score").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
        split_indices = {split: date_indices_for_split(dates, split) for split in ("train", "validation", "holdout")}
        rank_ic_by_split = {
            split: rank_ic_for_dates(score_matrix, panel["y_rank"], panel["target_mask"], idxs)
            for split, idxs in split_indices.items()
        }
        for top_n in (5, 10, 15):
            for weighting in ("equal_weight", "inverse_vol"):
                raw_weights, hit_rate = weights_from_scores(group, dates, tickers, top_n, weighting, next_returns, vol_panel)
                for wrapper in wrappers:
                    weights, exposure = overlay_weights(wrapper, raw_weights, next_returns, state)
                    path = compute_path(weights, next_returns, exposure, hit_rate)
                    append_backtest(returns_frames, weights_frames, summary_rows, path, weights, str(model_name), int(seed), top_n, weighting, wrapper, rank_ic_by_split)
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
        d["category"] = "cross_asset_attention"
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


def best_row(summary: pd.DataFrame, split: str) -> dict[str, Any]:
    sub = summary[(summary["split"].eq(split)) & (summary["active_weeks"].ge(50))].copy()
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "max_drawdown", "cvar_5", "annual_return"], ascending=[False, False, False, False]).iloc[0].to_dict()


def comp_value(comparison: pd.DataFrame, strategy: str, metric: str) -> float:
    sub = comparison[comparison["strategy_name"].eq(strategy)]
    if sub.empty or metric not in sub.columns:
        return np.nan
    value = sub.iloc[0][metric]
    return float(value) if pd.notna(value) else np.nan


def choose_recommendation(selected_holdout: dict[str, Any], comparison: pd.DataFrame) -> str:
    if not selected_holdout:
        return "REJECT"
    sharpe = float(selected_holdout.get("sharpe", np.nan))
    dd = float(selected_holdout.get("max_drawdown", np.nan))
    prod = comp_value(comparison, "production", "sharpe")
    phase4b = comp_value(comparison, "phase4b", "sharpe")
    mlx9 = comp_value(comparison, "mlx9_ensemble", "sharpe")
    if pd.notna(sharpe) and pd.notna(phase4b) and sharpe > phase4b and pd.notna(dd) and dd > -0.16:
        return "NEEDS MULTI-SEED / WALK-FORWARD BEFORE JUDGMENT"
    if pd.notna(sharpe) and pd.notna(prod) and sharpe > prod and pd.notna(mlx9) and sharpe > mlx9:
        return "PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION"
    if pd.notna(sharpe) and sharpe > 0.7:
        return "KEEP AS ML SHADOW"
    if pd.notna(sharpe) and sharpe > 0:
        return "KEEP AS RESEARCH ONLY"
    return "REJECT"


def write_notes(
    torch_meta: dict[str, Any],
    preprocess_meta: dict[str, Any],
    model_infos: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
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
    arch = model_infos[0].get("architecture", {}) if model_infos else {}
    notes = f"""# Phase MLX Cross-Asset Attention Ranker Notes

## Research-Only Warning

Phase MLX cross-asset attention is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Cross-sectional prediction means ranking assets against each other at the same date. Instead of asking whether one ETF will go up in isolation, the model asks which ETFs look better than the rest of the ETF universe this week.

Cross-asset attention is a Transformer-style method where every ETF is treated as a token. Attention lets SPY, QQQ, TLT, GLD, sectors, international ETFs, commodities, and BIL interact at the same date. This differs from MLX-6, where the Transformer mainly processed one ETF's historical sequence. Here, the attention axis is the cross-section of ETFs at date `t`.

ETF allocation is naturally a ranking problem because the portfolio does not need perfect return forecasts for every ETF; it needs a useful ordering for top-N selection, sizing, and defensive overlay. Ranking jointly may help because relative relationships matter: bonds versus equities, growth versus value, commodities versus inflation-sensitive assets, and BIL versus risky assets.

This can overfit because ETF relationships change over time, the cross-section is small, and a Transformer can learn period-specific risk-on or tech momentum patterns. This sprint relates to research directions such as MASTER: Market-Guided Stock Transformer, self-attention for cross-sectional return forecasting, and learning-to-rank for asset selection.

## Technical Setup

- Torch availability: {torch_meta}
- Input tensor shape: `{preprocess_meta.get('input_tensor_shape')}` as `[dates, ETFs, features]`
- ETF universe size: {preprocess_meta.get('n_assets')}
- Features used: {preprocess_meta.get('n_features')} total, including an availability mask
- Target: `{preprocess_meta.get('target')}`
- Architecture: {arch}
- Loss function: `BCEWithLogitsLoss` for `top_quintile_forward_4w`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: no target-like input columns; action at date `t` uses scores known at date `t` and earns next-week returns
- Skipped variants: {skipped}

## Results

- Models run: {summary_json.get('models_run')}
- Best validation model: `{best_val.get('strategy_name', 'n/a')}` with validation Sharpe {num(best_val.get('sharpe'))}
- Validation-selected holdout Sharpe: {num(selected_hold.get('sharpe'))}
- Validation-selected holdout annual return: {pct(selected_hold.get('annual_return'))}
- Validation-selected max drawdown: {pct(selected_hold.get('max_drawdown'))}
- Validation-selected CVaR 5%: {pct(selected_hold.get('cvar_5'))}
- Best holdout model: `{best_hold.get('strategy_name', 'n/a')}` with holdout Sharpe {num(best_hold.get('sharpe'))}

### Top Holdout Strategies

{markdown_table(summary[summary['split'].eq('holdout')].sort_values(['sharpe', 'annual_return'], ascending=[False, False]), ['strategy_name', 'seed', 'top_n', 'weighting', 'wrapper', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_turnover', 'average_bil_exposure', 'rank_ic', 'top_quintile_hit_rate'], 15)}

### Strategy Comparison

{markdown_table(comparison, ['strategy_name', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure'], 25)}

### Walk-Forward Window Evaluation

{markdown_table(walkforward, ['strategy_name', 'window', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'active_weeks'], 40)}

### State-By-State Results

{markdown_table(state, ['strategy_name', 'market_state', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_ml_exposure', 'weeks'], 40)}

### Exposure / Ranking Diagnostics

{markdown_table(exposure, ['strategy_name', 'audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], 40)}

Attention weights were not extracted in this first CPU-bounded implementation. The diagnostics instead audit scores indirectly through top holdings, category exposures, BIL exposure, SPY/QQQ/SMH concentration, state-by-state behavior, rank IC, and top-quintile hit rate.

## Interpretation

- Did cross-asset attention beat MLX-5C mean Sharpe? {summary_json.get('validation_selected_beats_mlx5c_sharpe')}
- Did it beat MLX-6 Transformer? {summary_json.get('validation_selected_beats_mlx6_sharpe')}
- Did it beat MLX-9 ensemble? {summary_json.get('validation_selected_beats_mlx9_sharpe')}
- Did it beat production? {summary_json.get('validation_selected_beats_production_sharpe')}
- Did it beat Phase 4B? {summary_json.get('validation_selected_beats_phase4b_sharpe')}
- Final recommendation: **{summary_json.get('final_recommendation')}**

The first version answers whether cross-sectional attention is promising enough for deeper work. A better version should add explicit pairwise/listwise ranking loss, extract attention maps, run full walk-forward retraining, test more seeds, and eventually move to PIT stock data.

## Warnings

{chr(10).join(f'- {w}' for w in warnings_list)}
"""
    NOTES_OUT.write_text(notes)


def write_skipped_outputs(reason: str, torch_meta: dict[str, Any], warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    empty = pd.DataFrame()
    empty.to_parquet(PREDICTIONS_OUT, index=False)
    empty.to_csv(BACKTEST_RETURNS_OUT, index=False)
    empty.to_csv(SUMMARY_OUT, index=False)
    empty.to_csv(TRAINING_CURVES_OUT, index=False)
    empty.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    empty.to_csv(STATE_BY_STATE_OUT, index=False)
    empty.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps({"research_only": True, "production_valid": False, "reason": reason}, indent=2))
    SKIPPED_RUNS_OUT.write_text(json.dumps([{"component": "torch_training", "reason": reason}], indent=2))
    summary = {"phase": "cross_asset_attention", "research_only": True, "production_valid": False, "torch": torch_meta, "reason": reason, "warnings": warnings_list}
    SUMMARY_JSON_OUT.write_text(json.dumps(summary, indent=2, default=json_default))
    NOTES_OUT.write_text(f"""# Phase MLX Cross-Asset Attention Ranker Notes

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

Cross-asset attention would treat ETFs as tokens at the same date and let them interact through Transformer attention. Training was skipped because `{reason}`.

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
        print("Phase MLX cross-asset attention skipped: torch unavailable.")
        return
    import torch

    device = "cpu"
    features, targets, weekly_returns, universe_meta = load_inputs(warnings_list)
    panel, preprocess_meta = build_tensor_panel(features, targets, weekly_returns)
    skipped = [
        {"variant": "pairwise_ranking_loss", "reason": "deferred in first CPU-bounded version; BCE top-quintile loss used first"},
        {"variant": "listwise_ranking_loss", "reason": "deferred in first CPU-bounded version; explicit date-grouped ranking loss is next upgrade"},
        {"variant": "seed_2", "reason": "skipped to keep first cross-asset attention run bounded on CPU"},
        {"variant": "attention_weight_extraction", "reason": "PyTorch TransformerEncoder does not expose attention maps directly in this simple implementation"},
        {"variant": "full_walk_forward_retraining", "reason": "deferred; selected predictions are evaluated by window without retraining per fold"},
    ]
    configs = [
        AttentionConfig(model_name=f"cross_asset_attention_ranker_seed{seed}", seed=seed)
        for seed in SEEDS
    ]
    all_predictions: list[pd.DataFrame] = []
    all_curves: list[pd.DataFrame] = []
    model_infos: list[dict[str, Any]] = []
    for i, config in enumerate(configs, start=1):
        print(f"Running cross-asset attention model {i}/{len(configs)}: {config.model_name}")
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
    focus = sorted(set([best_val.get("strategy_name"), best_holdout.get("strategy_name")]) - {None, ""})
    state = state_by_state(returns_df[returns_df["strategy_name"].isin(focus)], panel["state"])
    exposure = exposure_audit(weights_df, universe_meta, focus)
    walk = walkforward_summary(returns_df, focus)

    selected_sharpe = selected_holdout.get("sharpe", np.nan)
    summary_json = {
        "phase": "cross_asset_attention_ranker",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "torch": torch_meta,
        "device": device,
        "models_run": [c.model_name for c in configs],
        "seeds_run": list(SEEDS),
        "model_architecture": model_infos[0].get("architecture", {}) if model_infos else {},
        "input_tensor_shape": preprocess_meta["input_tensor_shape"],
        "etf_universe_size": preprocess_meta["n_assets"],
        "loss_function": "BCEWithLogitsLoss for top_quintile_forward_4w",
        "skipped_runs": skipped,
        "best_validation_model": best_val,
        "validation_selected_holdout": selected_holdout,
        "best_holdout_model": best_holdout,
        "validation_selected_beats_mlx5c_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")),
        "validation_selected_beats_mlx6_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx6_transformer", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx6_transformer", "sharpe")),
        "validation_selected_beats_mlx9_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx9_ensemble", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx9_ensemble", "sharpe")),
        "validation_selected_beats_production_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "production", "sharpe")) and selected_sharpe > comp_value(comparison, "production", "sharpe")),
        "validation_selected_beats_phase4b_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "phase4b", "sharpe")) and selected_sharpe > comp_value(comparison, "phase4b", "sharpe")),
        "final_recommendation": choose_recommendation(selected_holdout, comparison),
        "warnings": warnings_list + ["No cross-asset attention model is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "state_by_state": str(STATE_BY_STATE_OUT.relative_to(ROOT)),
            "exposure_audit": str(EXPOSURE_AUDIT_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "skipped_runs": str(SKIPPED_RUNS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    returns_df.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    training_curves.to_csv(TRAINING_CURVES_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    state.to_csv(STATE_BY_STATE_OUT, index=False)
    exposure.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(preprocess_meta, indent=2, default=json_default))
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(torch_meta, preprocess_meta, model_infos, skipped, summary, comparison, state, exposure, walk, summary_json, summary_json["warnings"])

    print("Phase MLX cross-asset attention ranker")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Torch: {torch_meta}")
    print(f"Device used: {device}")
    print(f"Input tensor shape: {preprocess_meta['input_tensor_shape']}")
    print(f"ETF universe size: {preprocess_meta['n_assets']}")
    print(f"Models run: {[c.model_name for c in configs]}")
    print(f"Best validation model: {best_val.get('strategy_name') if best_val else 'n/a'}")
    print(f"Validation-selected holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Best holdout model: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Best holdout Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Final recommendation: {summary_json['final_recommendation']}")
    print("Outputs:")
    for path in [PREDICTIONS_OUT, BACKTEST_RETURNS_OUT, SUMMARY_OUT, TRAINING_CURVES_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, EXPOSURE_AUDIT_OUT, PREPROCESSING_METADATA_OUT, SKIPPED_RUNS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
