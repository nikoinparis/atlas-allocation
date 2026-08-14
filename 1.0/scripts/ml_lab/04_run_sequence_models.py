#!/usr/bin/env python3
"""
Phase MLX-5: sequence models plus defensive overlays for the ML research lab.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
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
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
NN_DIR = ROOT / "data" / "research" / "ml_lab" / "neural_networks"
TABULAR_DIR = ROOT / "data" / "research" / "ml_lab" / "tabular_ml"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "sequence_models"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
NN_SUMMARY_IN = NN_DIR / "nn_summary.csv"
NN_RETURNS_IN = NN_DIR / "nn_backtest_returns.csv"
TABULAR_SUMMARY_IN = TABULAR_DIR / "ml_tabular_summary.csv"
TABULAR_RETURNS_IN = TABULAR_DIR / "ml_tabular_backtest_returns.csv"

PREDICTIONS_OUT = OUTPUT_DIR / "sequence_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "sequence_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "sequence_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "sequence_training_curves.csv"
OVERLAY_SUMMARY_OUT = OUTPUT_DIR / "sequence_overlay_summary.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "sequence_preprocessing_metadata.json"
SKIPPED_MODELS_OUT = OUTPUT_DIR / "sequence_skipped_models.json"
PROJECT_STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "sequence_project_strategy_comparison.csv"
COMPARISON_TABLE_OUT = OUTPUT_DIR / "sequence_comparison_table.csv"
NOTES_OUT = DOCS_DIR / "phase_mlx_sequence_model_notes.md"

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

RANDOM_STATE = 42
SEQ_LEN = 26
BATCH_SIZE = 2048
MAX_EPOCHS = 30
PATIENCE = 5
DEFAULT_COST_BPS = 10.0
EXTREME_MISSINGNESS_THRESHOLD = 0.95
HOLDOUT_START = pd.Timestamp("2020-01-03")
HOLDOUT_END = pd.Timestamp("2026-05-08")


@dataclass(frozen=True)
class SequenceConfig:
    model_name: str
    target: str
    model_type: str
    hidden_size: int
    dropout: float
    seq_len: int = SEQ_LEN
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


def torch_status() -> dict[str, Any]:
    spec = importlib.util.find_spec("torch")
    status: dict[str, Any] = {"available": bool(spec), "version": None, "cuda_available": False, "mps_available": False}
    if not spec:
        return status
    try:
        import torch
    except Exception as exc:
        return {"available": False, "version": None, "import_error": f"{type(exc).__name__}: {exc}"}
    status["version"] = torch.__version__
    status["cuda_available"] = bool(torch.cuda.is_available())
    status["mps_available"] = bool(hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
    return status


def set_seeds(torch: Any) -> None:
    random.seed(RANDOM_STATE)
    np.random.seed(RANDOM_STATE)
    torch.manual_seed(RANDOM_STATE)
    torch.set_num_threads(max(1, min(4, os.cpu_count() or 1)))


def load_panel_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.index.name = "Date"
    return df


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not FEATURES_IN.exists() or not TARGETS_IN.exists():
        missing = [str(p) for p in [FEATURES_IN, TARGETS_IN] if not p.exists()]
        raise FileNotFoundError(f"Required MLX feature/target inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    weekly_returns = load_panel_csv(WEEKLY_RETURNS_IN) if WEEKLY_RETURNS_IN.exists() else pd.DataFrame()
    return features, targets, weekly_returns


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    required = {"Date", "ticker"}
    if not required.issubset(features.columns) or not required.issubset(targets.columns):
        raise ValueError("features and targets must include Date and ticker identifiers")
    if not features[["Date", "ticker"]].reset_index(drop=True).equals(targets[["Date", "ticker"]].reset_index(drop=True)):
        raise ValueError("feature rows do not align with target rows")
    leaked = sorted(TARGET_COLUMNS & set(features.columns))
    if leaked:
        raise ValueError(f"target columns found in features: {leaked}")
    suspicious = []
    for col in features.columns:
        lower = col.lower()
        if col in {"Date", "ticker", "target_vol_multiplier"}:
            continue
        if lower.startswith(("forward_", "future_", "next_", "beats_", "top_quintile", "positive_forward")) or lower.endswith("_label"):
            suspicious.append(col)
    if suspicious:
        raise ValueError(f"target-like feature columns found: {suspicious}")


def split_name_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(pd.to_datetime(dates), index=getattr(dates, "index", None))
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
    return out


def prepare_features(features: pd.DataFrame, split: pd.Series) -> dict[str, Any]:
    numeric_cols = [c for c in features.columns if c not in {"Date", "ticker"} and pd.api.types.is_numeric_dtype(features[c])]
    raw = features[numeric_cols].replace([np.inf, -np.inf], np.nan)
    train_mask = split.eq("train")
    train_missing = raw.loc[train_mask].isna().mean()
    dropped = train_missing[train_missing > EXTREME_MISSINGNESS_THRESHOLD].index.tolist()
    kept = [c for c in numeric_cols if c not in dropped]
    raw = raw[kept]
    medians = raw.loc[train_mask].median(numeric_only=True).fillna(0.0)
    filled = raw.fillna(medians).fillna(0.0)
    means = filled.loc[train_mask].mean(numeric_only=True)
    stds = filled.loc[train_mask].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    standardized = ((filled - means) / stds).astype("float32")
    return {
        "numeric_feature_cols_original": numeric_cols,
        "numeric_feature_cols": kept,
        "dropped_features_extreme_missingness": dropped,
        "x": standardized.to_numpy(dtype="float32"),
        "median_fill_values": medians.to_dict(),
        "standardization_means": means.to_dict(),
        "standardization_stds": stds.to_dict(),
        "train_missing_rate": train_missing.to_dict(),
    }


def valid_sequence_end_indices(features: pd.DataFrame, seq_len: int) -> np.ndarray:
    indices: list[int] = []
    for _, group in features.groupby("ticker", sort=False):
        idx = group.index.to_numpy()
        if len(idx) < seq_len:
            continue
        indices.extend(idx[seq_len - 1 :].tolist())
    return np.asarray(indices, dtype=np.int64)


class SequenceDataset:
    def __init__(self, torch: Any, x: np.ndarray, end_indices: np.ndarray, y: np.ndarray, seq_len: int):
        self.torch = torch
        self.x = x
        self.end_indices = end_indices.astype(np.int64)
        self.y = y.astype("float32")
        self.seq_len = seq_len

    def __len__(self) -> int:
        return len(self.end_indices)

    def __getitem__(self, i: int) -> tuple[Any, Any]:
        end = int(self.end_indices[i])
        seq = self.x[end - self.seq_len + 1 : end + 1]
        return self.torch.from_numpy(seq), self.torch.tensor([self.y[i]], dtype=self.torch.float32)


class PredictSequenceDataset:
    def __init__(self, torch: Any, x: np.ndarray, end_indices: np.ndarray, seq_len: int):
        self.torch = torch
        self.x = x
        self.end_indices = end_indices.astype(np.int64)
        self.seq_len = seq_len

    def __len__(self) -> int:
        return len(self.end_indices)

    def __getitem__(self, i: int) -> Any:
        end = int(self.end_indices[i])
        return self.torch.from_numpy(self.x[end - self.seq_len + 1 : end + 1])


class RecurrentClassifier:
    def __init__(self, torch: Any, kind: str, input_dim: int, hidden_size: int, dropout: float):
        super().__init__()
        self.torch = torch
        nn = torch.nn
        rnn_cls = nn.LSTM if kind == "lstm" else nn.GRU
        self.net = rnn_cls(input_dim, hidden_size, batch_first=True)
        self.dropout = nn.Dropout(dropout)
        self.head = nn.Linear(hidden_size, 1)

    def parameters(self) -> Any:
        return list(self.net.parameters()) + list(self.dropout.parameters()) + list(self.head.parameters())

    def to(self, device: str) -> "RecurrentClassifier":
        self.net.to(device); self.dropout.to(device); self.head.to(device)
        return self

    def train(self) -> None:
        self.net.train(); self.dropout.train(); self.head.train()

    def eval(self) -> None:
        self.net.eval(); self.dropout.eval(); self.head.eval()

    def state_dict(self) -> dict[str, Any]:
        return {"net": self.net.state_dict(), "head": self.head.state_dict()}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.net.load_state_dict(state["net"]); self.head.load_state_dict(state["head"])

    def __call__(self, x: Any) -> Any:
        out, _ = self.net(x)
        return self.head(self.dropout(out[:, -1, :]))


class TemporalCNNClassifier:
    def __init__(self, torch: Any, input_dim: int, hidden_size: int, dropout: float):
        super().__init__()
        nn = torch.nn
        self.model = nn.Sequential(
            nn.Conv1d(input_dim, hidden_size, kernel_size=3, padding=2, dilation=1),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=4, dilation=2),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.head = nn.Linear(hidden_size, 1)

    def parameters(self) -> Any:
        return list(self.model.parameters()) + list(self.head.parameters())

    def to(self, device: str) -> "TemporalCNNClassifier":
        self.model.to(device); self.head.to(device)
        return self

    def train(self) -> None:
        self.model.train(); self.head.train()

    def eval(self) -> None:
        self.model.eval(); self.head.eval()

    def state_dict(self) -> dict[str, Any]:
        return {"model": self.model.state_dict(), "head": self.head.state_dict()}

    def load_state_dict(self, state: dict[str, Any]) -> None:
        self.model.load_state_dict(state["model"]); self.head.load_state_dict(state["head"])

    def __call__(self, x: Any) -> Any:
        z = x.transpose(1, 2)
        out = self.model(z)
        return self.head(out[:, :, -1])


def make_model(torch: Any, config: SequenceConfig, input_dim: int) -> Any:
    if config.model_type in {"lstm", "gru"}:
        return RecurrentClassifier(torch, config.model_type, input_dim, config.hidden_size, config.dropout)
    if config.model_type == "tcn":
        return TemporalCNNClassifier(torch, input_dim, config.hidden_size, config.dropout)
    raise ValueError(f"Unknown model type: {config.model_type}")


def train_sequence_model(
    torch: Any,
    config: SequenceConfig,
    x: np.ndarray,
    targets: pd.Series,
    split: pd.Series,
    all_end_indices: np.ndarray,
    device: str,
    warnings_list: list[str],
) -> tuple[Any | None, pd.DataFrame, dict[str, Any]]:
    y_all = pd.to_numeric(targets, errors="coerce")
    train_idx = all_end_indices[(split.iloc[all_end_indices].to_numpy() == "train") & y_all.iloc[all_end_indices].notna().to_numpy()]
    val_idx = all_end_indices[(split.iloc[all_end_indices].to_numpy() == "validation") & y_all.iloc[all_end_indices].notna().to_numpy()]
    if len(train_idx) < 1000 or len(val_idx) < 100:
        return None, pd.DataFrame(), {"reason": "insufficient train/validation sequence rows"}
    y_train = y_all.iloc[train_idx].astype("float32").to_numpy()
    y_val = y_all.iloc[val_idx].astype("float32").to_numpy()
    pos = float(y_train.sum())
    neg = float(len(y_train) - pos)
    pos_weight = neg / pos if pos > 0 else 1.0

    train_loader = torch.utils.data.DataLoader(SequenceDataset(torch, x, train_idx, y_train, config.seq_len), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = torch.utils.data.DataLoader(SequenceDataset(torch, x, val_idx, y_val, config.seq_len), batch_size=BATCH_SIZE, shuffle=False)
    model = make_model(torch, config, x.shape[1]).to(device)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)

    best_loss = float("inf")
    best_epoch = 0
    best_state = None
    stale = 0
    rows: list[dict[str, Any]] = []
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        train_losses: list[float] = []
        for xb, yb in train_loader:
            xb = xb.to(device); yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            train_losses.append(float(loss.detach().cpu().item()))
        model.eval()
        val_losses: list[float] = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device); yb = yb.to(device)
                val_losses.append(float(loss_fn(model(xb), yb).detach().cpu().item()))
        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses))
        if val_loss < best_loss - 1e-6:
            best_loss = val_loss
            best_epoch = epoch
            best_state = {k: {kk: vv.detach().cpu().clone() for kk, vv in v.items()} for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        rows.append({
            "model_name": config.model_name,
            "target": config.target,
            "model_type": config.model_type,
            "sequence_length": config.seq_len,
            "epoch": epoch,
            "train_loss": train_loss,
            "validation_loss": val_loss,
            "best_epoch_so_far": best_epoch,
            "early_stop_triggered": False,
        })
        if stale >= config.patience:
            rows[-1]["early_stop_triggered"] = True
            break
    if best_state is not None:
        model.load_state_dict(best_state)
    meta = {
        "model_name": config.model_name,
        "target": config.target,
        "model_type": config.model_type,
        "sequence_length": config.seq_len,
        "hidden_size": config.hidden_size,
        "dropout": config.dropout,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "epochs_run": len(rows),
        "positive_rate_train": pos / max(1, len(y_train)),
        "pos_weight": pos_weight,
        "train_sequences": int(len(train_idx)),
        "validation_sequences": int(len(val_idx)),
    }
    return model, pd.DataFrame(rows), meta


def predict_sequence_model(torch: Any, model: Any, x: np.ndarray, end_indices: np.ndarray, seq_len: int, device: str) -> np.ndarray:
    loader = torch.utils.data.DataLoader(PredictSequenceDataset(torch, x, end_indices, seq_len), batch_size=BATCH_SIZE * 2, shuffle=False)
    model.eval()
    out: list[np.ndarray] = []
    with torch.no_grad():
        for xb in loader:
            raw = model(xb.to(device)).detach().cpu().numpy().reshape(-1)
            out.append((1.0 / (1.0 + np.exp(-raw))).astype("float64"))
    return np.concatenate(out)


def next_week_return_panel(features: pd.DataFrame) -> pd.DataFrame:
    tmp = features[["Date", "ticker", "trailing_return_1w"]].sort_values(["ticker", "Date"]).copy()
    tmp["next_week_return"] = tmp.groupby("ticker")["trailing_return_1w"].shift(-1)
    return tmp.pivot(index="Date", columns="ticker", values="next_week_return").sort_index()


def matrix_by_date(features: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in features.columns:
        return pd.DataFrame()
    return features.pivot(index="Date", columns="ticker", values=column).sort_index()


def infer_market_state_by_date(features: pd.DataFrame) -> pd.Series:
    state_cols = [c for c in features.columns if c.startswith("market_state_")]
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    if not state_cols:
        return pd.Series("unknown", index=dates)
    state = features[["Date"] + state_cols].drop_duplicates("Date").set_index("Date").reindex(dates)
    labels = state[state_cols].idxmax(axis=1).str.replace("market_state_", "", regex=False)
    labels[state[state_cols].sum(axis=1).fillna(0.0).eq(0.0)] = "unknown"
    return labels.fillna("unknown")


def weights_from_scores(score_table: pd.DataFrame, dates: pd.DatetimeIndex, tickers: list[str], top_n: int, weighting: str, next_returns: pd.DataFrame, vol_panel: pd.DataFrame) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        available = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        eligible = group[["ticker", "score"]].dropna()
        eligible = eligible[eligible["ticker"].map(available.notna()).fillna(False)]
        if eligible.empty:
            continue
        chosen = eligible.sort_values("score", ascending=False).head(top_n)["ticker"].tolist()
        if not chosen:
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
    return weights


def add_bil_fallback(weights: pd.DataFrame, exposure: pd.Series, bil: str = "BIL") -> pd.DataFrame:
    exposure = exposure.reindex(weights.index).fillna(1.0).clip(0.0, 1.0)
    out = weights.mul(exposure, axis=0)
    if bil in out.columns:
        out[bil] = out[bil] + (1.0 - exposure)
    return out


def overlay_weights(wrapper: str, raw_weights: pd.DataFrame, next_returns: pd.DataFrame, state: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "regime_gate":
        mapping = {"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}
        exposure = state.reindex(dates).map(mapping).fillna(0.70)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "bil_fallback":
        mapping = {"stressed_panic": 0.25, "neutral_mixed": 0.75}
        exposure = state.reindex(dates).map(mapping).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    raw_gross = raw_weights.mul(next_returns.reindex(index=dates, columns=raw_weights.columns).fillna(0.0)).sum(axis=1)
    if wrapper == "vol_target":
        ann_vol = raw_gross.shift(1).rolling(13, min_periods=6).std() * math.sqrt(52.0)
        exposure = (0.10 / ann_vol.replace(0.0, np.nan)).clip(0.0, 1.0).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "drawdown_kill_switch":
        wealth = (1.0 + raw_gross.shift(1).fillna(0.0)).cumprod()
        peak = wealth.cummax()
        dd = wealth / peak - 1.0
        values: list[float] = []
        prev = 1.0
        for value in dd.reindex(dates).fillna(0.0):
            if value <= -0.15:
                exp = 0.25
            elif value <= -0.10:
                exp = 0.50
            elif value >= -0.03:
                exp = min(1.0, prev + 0.10)
            else:
                exp = prev
            values.append(exp)
            prev = exp
        exposure = pd.Series(values, index=dates)
        return add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"unknown wrapper {wrapper}")


def compute_path(weights: pd.DataFrame, next_returns: pd.DataFrame, cost_bps: float, exposure: pd.Series | None = None) -> pd.DataFrame:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (cost_bps / 10000.0)
    net = gross - cost
    out = pd.DataFrame({
        "gross_return": gross,
        "net_return": net,
        "turnover": turnover,
        "cost": cost,
        "holdings_count": weights.gt(0.0).sum(axis=1),
        "bil_weight": weights.get("BIL", pd.Series(0.0, index=weights.index)),
        "spy_weight": weights.get("SPY", pd.Series(0.0, index=weights.index)),
    }, index=weights.index)
    out["ml_exposure"] = exposure.reindex(weights.index).fillna(1.0) if exposure is not None else 1.0
    offensive = [c for c in weights.columns if c not in {"BIL", "SHY", "IEF", "TLT", "TIP", "GLD", "IAU", "LQD", "HYG", "MBB", "AGG", "BND"}]
    out["offensive_weight"] = weights.reindex(columns=offensive).sum(axis=1) if offensive else 0.0
    return out


def max_drawdown(returns: pd.Series) -> float:
    r = returns.dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {"annual_return": np.nan, "annual_volatility": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "calmar": np.nan, "cvar_5": np.nan, "average_turnover": np.nan, "annual_cost_drag": np.nan, "average_bil_weight": np.nan, "average_spy_weight": np.nan, "average_offensive_weight": np.nan, "average_ml_exposure": np.nan, "active_weeks": 0}
    wealth = (1.0 + r).cumprod()
    ann_ret = float(wealth.iloc[-1] ** (52.0 / len(r)) - 1.0) if wealth.iloc[-1] > 0 else np.nan
    ann_vol = float(r.std(ddof=0) * math.sqrt(52.0))
    sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else np.nan
    mdd = max_drawdown(r)
    q5 = r.quantile(0.05)
    return {
        "annual_return": ann_ret,
        "annual_volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "calmar": float(ann_ret / abs(mdd)) if pd.notna(mdd) and mdd < 0 else np.nan,
        "cvar_5": float(r[r <= q5].mean()) if pd.notna(q5) else np.nan,
        "average_turnover": float(path.get("turnover", pd.Series(dtype=float)).reindex(r.index).mean()),
        "annual_cost_drag": float(path.get("cost", pd.Series(dtype=float)).reindex(r.index).mean() * 52.0),
        "average_bil_weight": float(path.get("bil_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_spy_weight": float(path.get("spy_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_offensive_weight": float(path.get("offensive_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_ml_exposure": float(path.get("ml_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_number_of_etfs_held": float(path.get("holdings_count", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def append_results(all_returns: list[pd.DataFrame], summary_rows: list[dict[str, Any]], path: pd.DataFrame, strategy_name: str, strategy_type: str, model_name: str = "", target: str = "", top_n: Any = np.nan, weighting: str = "", wrapper: str = "") -> None:
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_name_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    dated["strategy_type"] = strategy_type
    dated["model_name"] = model_name
    dated["target"] = target
    dated["top_n"] = top_n
    dated["weighting"] = weighting
    dated["wrapper"] = wrapper
    dated["cost_bps"] = DEFAULT_COST_BPS
    all_returns.append(dated.reset_index(drop=True))
    for split in ("train", "validation", "holdout"):
        metrics = calc_metrics(dated[dated["split"].eq(split)])
        metrics.update({"strategy_name": strategy_name, "strategy_type": strategy_type, "model_name": model_name, "target": target, "top_n": top_n, "weighting": weighting, "wrapper": wrapper, "split": split, "cost_bps": DEFAULT_COST_BPS})
        summary_rows.append(metrics)


def static_baseline_weights(name: str, dates: pd.DatetimeIndex, tickers: list[str], next_returns: pd.DataFrame) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=dates, columns=tickers)
    if name == "baseline_spy_buy_hold" and "SPY" in tickers:
        w["SPY"] = next_returns["SPY"].notna().astype(float)
    elif name == "baseline_60_40_spy_ief_or_agg":
        bond = "IEF" if "IEF" in tickers else "AGG" if "AGG" in tickers else None
        if "SPY" in tickers and bond:
            w["SPY"] = 0.60 * next_returns["SPY"].notna().astype(float)
            w[bond] = 0.40 * next_returns[bond].notna().astype(float)
    elif name == "baseline_equal_weight_all_etfs":
        eligible = next_returns.reindex(index=dates, columns=tickers).notna()
        w = eligible.astype(float).div(eligible.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    return w


def run_backtests(features: pd.DataFrame, predictions: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    tickers = sorted(features["ticker"].unique())
    next_returns = next_week_return_panel(features).reindex(index=dates, columns=tickers)
    vol_panel = matrix_by_date(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = matrix_by_date(features, "realized_vol_26w")
    state = infer_market_state_by_date(features)
    wrappers = ["raw_ml", "regime_gate", "bil_fallback", "vol_target", "drawdown_kill_switch"]
    all_returns: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    for model_name, group in predictions.groupby("model_name", sort=True):
        target = str(group["target"].iloc[0])
        for top_n in (3, 5, 10):
            for weighting in ("equal_weight", "inverse_vol"):
                raw = weights_from_scores(group, dates, tickers, top_n, weighting, next_returns, vol_panel)
                for wrapper in wrappers:
                    wrapped, exposure = overlay_weights(wrapper, raw, next_returns, state)
                    path = compute_path(wrapped, next_returns, DEFAULT_COST_BPS, exposure)
                    strategy = f"{model_name}__top{top_n}__{weighting}__{wrapper}"
                    append_results(all_returns, summary_rows, path, strategy, "model", model_name, target, top_n, weighting, wrapper)

    for baseline in ("baseline_spy_buy_hold", "baseline_60_40_spy_ief_or_agg", "baseline_equal_weight_all_etfs"):
        w = static_baseline_weights(baseline, dates, tickers, next_returns)
        if w.sum(axis=1).sum() > 0:
            append_results(all_returns, summary_rows, compute_path(w, next_returns, DEFAULT_COST_BPS), baseline, "baseline")
        else:
            warn(f"Baseline {baseline} could not be built.", warnings_list)

    momentum_col = "momentum_12_1" if "momentum_12_1" in features.columns else "trailing_return_26w"
    score = features[["Date", "ticker", momentum_col]].rename(columns={momentum_col: "score"})
    for top_n in (3, 5, 10):
        for weighting in ("equal_weight", "inverse_vol"):
            w = weights_from_scores(score, dates, tickers, top_n, weighting, next_returns, vol_panel)
            append_results(all_returns, summary_rows, compute_path(w, next_returns, DEFAULT_COST_BPS), f"baseline_top_momentum_{momentum_col}__top{top_n}__{weighting}", "baseline_momentum", top_n=top_n, weighting=weighting)

    returns_df = pd.concat(all_returns, ignore_index=True) if all_returns else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    overlay_summary = summary[summary["strategy_type"].eq("model")].copy()
    return returns_df, summary, overlay_summary


def read_project_return_file(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    if "net_return" not in df.columns and "gross_return" in df.columns:
        df["net_return"] = df["gross_return"]
    if "gross_return" not in df.columns and "net_return" in df.columns:
        df["gross_return"] = df["net_return"]
    for col in ["turnover", "cost", "holdings_count", "bil_weight", "spy_weight", "offensive_weight", "ml_exposure"]:
        if col not in df.columns:
            df[col] = np.nan
    return df[["gross_return", "net_return", "turnover", "cost", "holdings_count", "bil_weight", "spy_weight", "offensive_weight", "ml_exposure"]]


def matching_weights_path(return_path: Path) -> Path | None:
    candidates = []
    name = return_path.name
    if "portfolio_version_returns_" in name:
        candidates.append(return_path.with_name(name.replace("portfolio_version_returns_", "portfolio_version_weights_")))
    if "_returns" in name:
        candidates.append(return_path.with_name(name.replace("_returns", "_weights")))
    for path in candidates:
        if path.exists():
            return path
    return None


def load_weight_exposures(path: Path | None, holdout_index: pd.Index) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"average_bil_weight": np.nan, "average_spy_weight": np.nan, "average_offensive_weight": np.nan}
    try:
        w = pd.read_csv(path)
        date_col = "Date" if "Date" in w.columns else w.columns[0]
        w[date_col] = pd.to_datetime(w[date_col], errors="coerce")
        w = w.dropna(subset=[date_col]).set_index(date_col).sort_index()
        for col in w.columns:
            w[col] = pd.to_numeric(w[col], errors="coerce")
        h = w.reindex(holdout_index).dropna(how="all")
        offensive = [c for c in h.columns if c not in {"BIL", "SHY", "IEF", "TLT", "TIP", "GLD", "IAU", "LQD", "HYG", "MBB", "AGG", "BND"}]
        return {
            "average_bil_weight": float(h["BIL"].mean()) if "BIL" in h else np.nan,
            "average_spy_weight": float(h["SPY"].mean()) if "SPY" in h else np.nan,
            "average_offensive_weight": float(h[offensive].sum(axis=1).mean()) if offensive else np.nan,
        }
    except Exception:
        return {"average_bil_weight": np.nan, "average_spy_weight": np.nan, "average_offensive_weight": np.nan}


def discover_project_strategy_files() -> dict[str, Path]:
    roots = [ROOT / "data" / "05_layer3_portfolio_construction", ROOT / "data" / "research"]
    out: dict[str, Path] = {}
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*.csv"):
            lower = path.name.lower()
            if "returns" not in lower:
                continue
            if "portfolio_version_returns_" in lower or "sleeve_returns" in lower:
                name = path.stem.replace("portfolio_version_returns_", "project_")
                out.setdefault(name, path)
    known = {
        "current_production_improved_phase2b_regime_confidence_boost": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
        "official_shadow_improved_phase2b_combo_abc": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_combo_abc.csv",
        "latest_candidate_improved_phaseggg_confirmed_only_robust_offense": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
        "phase7_stretch_target": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase7_stretch_target.csv",
    }
    for name, path in known.items():
        if path.exists():
            out[name] = path
    return out


def project_strategy_comparison(warnings_list: list[str]) -> pd.DataFrame:
    files = discover_project_strategy_files()
    if not files:
        warn("No project strategy return files found for comparison.", warnings_list)
        return pd.DataFrame()
    rows = []
    for name, path in sorted(files.items()):
        try:
            p = read_project_return_file(path)
            hold = p.loc[(p.index >= HOLDOUT_START) & (p.index <= HOLDOUT_END)]
            metrics = calc_metrics(hold)
            weights = load_weight_exposures(matching_weights_path(path), hold.index)
            metrics.update(weights)
            metrics.update({"comparison_name": name, "source_path": str(path.relative_to(ROOT)), "category": classify_project_strategy(name)})
            rows.append(metrics)
        except Exception as exc:
            warn(f"Could not read project strategy {path}: {exc}", warnings_list)
    return pd.DataFrame(rows).sort_values(["sharpe", "annual_return"], ascending=[False, False]).reset_index(drop=True)


def classify_project_strategy(name: str) -> str:
    lower = name.lower()
    if "phase2b_regime_confidence_boost" in lower:
        return "current_production"
    if "phase2b_combo_abc" in lower:
        return "official_shadow"
    if "phaseggg_confirmed_only_robust_offense" in lower:
        return "latest_candidate"
    if "phase4b" in lower:
        return "phase4b"
    if "phase6" in lower:
        return "phase6"
    if "phase7" in lower:
        return "phase7"
    return "project_strategy"


def append_external_baseline_from_returns(summary_rows: list[dict[str, Any]], returns_rows: list[pd.DataFrame], file_path: Path, name: str, strategy_type: str, warnings_list: list[str]) -> None:
    if not file_path.exists():
        warn(f"Optional comparison returns missing: {file_path}", warnings_list)
        return
    try:
        df = pd.read_csv(file_path, parse_dates=["Date"])
        if "strategy_name" in df.columns:
            if strategy_type == "mlx4_baseline":
                sub = pd.read_csv(NN_SUMMARY_IN)
                best = sub[(sub["split"].eq("holdout")) & (sub["strategy_type"].eq("model"))].sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
                df = df[df["strategy_name"].eq(best)]
            elif strategy_type == "mlx3_baseline":
                sub = pd.read_csv(TABULAR_SUMMARY_IN)
                best = sub[(sub["split"].eq("holdout")) & (sub["strategy_type"].eq("model"))].sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
                df = df[df["strategy_name"].eq(best)]
        path = df.set_index("Date")[["gross_return", "net_return", "turnover", "cost", "holdings_count"]].sort_index()
        for col in ["bil_weight", "spy_weight", "offensive_weight", "ml_exposure"]:
            path[col] = df.set_index("Date")[col] if col in df.columns else np.nan
        append_results(returns_rows, summary_rows, path, name, strategy_type)
    except Exception as exc:
        warn(f"Could not load external baseline {file_path}: {exc}", warnings_list)


def best_row(summary: pd.DataFrame, split: str, strategy_types: tuple[str, ...], metric: str = "sharpe", ascending: bool = False) -> dict[str, Any] | None:
    sub = summary[summary["split"].eq(split) & summary["strategy_type"].isin(strategy_types)].copy()
    sub = sub[pd.to_numeric(sub[metric], errors="coerce").notna()]
    if sub.empty:
        return None
    return sub.sort_values([metric, "annual_return"], ascending=[ascending, False]).iloc[0].to_dict()


def build_comparison_table(summary: pd.DataFrame, project: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    specs = [
        ("Best raw sequence model", summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model")) & (summary["wrapper"].eq("raw_ml"))]),
        ("Best defensive-overlay sequence model", summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model")) & (~summary["wrapper"].eq("raw_ml"))]),
        ("MLX-4 best MLP", summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("mlx4_baseline"))]),
        ("MLX-3 best tabular ML", summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("mlx3_baseline"))]),
        ("Simple momentum baseline", summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("baseline_momentum"))]),
        ("SPY", summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq("baseline_spy_buy_hold"))]),
        ("60/40", summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq("baseline_60_40_spy_ief_or_agg"))]),
    ]
    for label, sub in specs:
        if not sub.empty:
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict()
            row["comparison_label"] = label
            rows.append(row)
    if not project.empty:
        for label, category in [("Current production", "current_production"), ("Official shadow", "official_shadow"), ("Phase 4B best", "phase4b"), ("Phase 6 best", "phase6"), ("Phase 7 stretch/best", "phase7")]:
            sub = project[project["category"].eq(category)]
            if not sub.empty:
                row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict()
                row["comparison_label"] = label
                row["strategy_name"] = row.get("comparison_name")
                row["split"] = "holdout"
                rows.append(row)
    return pd.DataFrame(rows)


def compare_holdout(summary: pd.DataFrame, project: pd.DataFrame) -> dict[str, Any]:
    models = summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model"))]
    if models.empty:
        return {}
    best_any = float(models["sharpe"].max())
    best_raw = models[models["wrapper"].eq("raw_ml")]
    best_overlay = models[~models["wrapper"].eq("raw_ml")]
    best_raw_sharpe = float(best_raw["sharpe"].max()) if not best_raw.empty else np.nan
    best_overlay_sharpe = float(best_overlay["sharpe"].max()) if not best_overlay.empty else np.nan
    best_raw_dd = float(best_raw.sort_values("sharpe", ascending=False).iloc[0]["max_drawdown"]) if not best_raw.empty else np.nan
    best_overlay_dd = float(best_overlay.sort_values("sharpe", ascending=False).iloc[0]["max_drawdown"]) if not best_overlay.empty else np.nan

    def s(strategy_type: str | None = None, strategy_name: str | None = None) -> float:
        sub = summary[summary["split"].eq("holdout")]
        if strategy_type:
            sub = sub[sub["strategy_type"].eq(strategy_type)]
        if strategy_name:
            sub = sub[sub["strategy_name"].eq(strategy_name)]
        return float(sub["sharpe"].max()) if not sub.empty else np.nan

    prod = project[project["category"].eq("current_production")]
    shadow = project[project["category"].eq("official_shadow")]
    prod_best = prod.sort_values("sharpe", ascending=False).iloc[0].to_dict() if not prod.empty else {}
    shadow_best = shadow.sort_values("sharpe", ascending=False).iloc[0].to_dict() if not shadow.empty else {}
    best_ann = models.sort_values("annual_return", ascending=False).iloc[0]
    best_risk = models.sort_values("sharpe", ascending=False).iloc[0]
    return {
        "best_sequence_holdout_sharpe": best_any,
        "best_raw_sequence_holdout_sharpe": best_raw_sharpe,
        "best_overlay_sequence_holdout_sharpe": best_overlay_sharpe,
        "mlx4_best_holdout_sharpe": s("mlx4_baseline"),
        "mlx3_best_holdout_sharpe": s("mlx3_baseline"),
        "simple_momentum_holdout_sharpe": s("baseline_momentum"),
        "spy_holdout_sharpe": s(strategy_name="baseline_spy_buy_hold"),
        "sixty_forty_holdout_sharpe": s(strategy_name="baseline_60_40_spy_ief_or_agg"),
        "production_holdout_sharpe": prod_best.get("sharpe", np.nan),
        "shadow_holdout_sharpe": shadow_best.get("sharpe", np.nan),
        "any_sequence_beats_production_sharpe": bool(pd.notna(prod_best.get("sharpe", np.nan)) and best_any > prod_best.get("sharpe")),
        "any_sequence_beats_shadow_sharpe": bool(pd.notna(shadow_best.get("sharpe", np.nan)) and best_any > shadow_best.get("sharpe")),
        "any_sequence_beats_production_annual_return": bool(pd.notna(prod_best.get("annual_return", np.nan)) and float(best_ann["annual_return"]) > prod_best.get("annual_return")),
        "any_sequence_beats_production_after_drawdown_cvar": bool(pd.notna(prod_best.get("max_drawdown", np.nan)) and float(best_risk["sharpe"]) > prod_best.get("sharpe", np.inf) and float(best_risk["max_drawdown"]) >= prod_best.get("max_drawdown", -np.inf) and float(best_risk["cvar_5"]) >= prod_best.get("cvar_5", -np.inf)),
        "overlay_improved_sharpe_vs_raw": bool(pd.notna(best_overlay_sharpe) and pd.notna(best_raw_sharpe) and best_overlay_sharpe > best_raw_sharpe),
        "overlay_improved_drawdown_vs_raw": bool(pd.notna(best_overlay_dd) and pd.notna(best_raw_dd) and best_overlay_dd > best_raw_dd),
    }


def fmt(value: Any, pct: bool = False) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}" if pct else f"{float(value):.3f}"


def markdown_table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "No comparison table available."
    sub = df[[c for c in cols if c in df.columns]].copy()
    for col in ["annual_return", "annual_volatility", "sharpe", "max_drawdown", "calmar", "cvar_5"]:
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce").map(lambda x: "n/a" if pd.isna(x) else f"{x:.3f}")
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def write_notes(torch_meta: dict[str, Any], device: str, sequence_lengths: list[int], models_run: list[str], skipped: list[dict[str, str]], summary: pd.DataFrame, project: pd.DataFrame, comparison: pd.DataFrame, comparisons: dict[str, Any], warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    best_raw = best_row(summary[summary["wrapper"].eq("raw_ml")], "holdout", ("model",))
    best_overlay = best_row(summary[~summary["wrapper"].eq("raw_ml")], "holdout", ("model",))
    best_any = best_row(summary, "holdout", ("model",))
    best_ann = best_row(summary, "holdout", ("model",), metric="annual_return")
    best_dd = best_row(summary, "holdout", ("model",), metric="max_drawdown", ascending=False)
    model_lines = "\n".join(f"- {m}" for m in models_run) or "- None"
    skip_lines = "\n".join(f"- {s['model_name']}: {s['reason']}" for s in skipped) or "- None"
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"
    cmp_cols = ["comparison_label", "strategy_name", "annual_return", "sharpe", "max_drawdown", "calmar", "cvar_5"]
    cmp_md = markdown_table(comparison, cmp_cols)
    NOTES_OUT.write_text(f"""# Phase MLX Sequence Model Notes

## Research-Only Warning

Phase MLX-5 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Sequence models are models that read ordered history rather than a single row. Here, each sample is the past {sequence_lengths[0]} weekly feature observations for one ETF, and the model predicts whether that ETF will be a top-quintile forward performer.

An LSTM is a recurrent neural network designed to remember useful information across time while forgetting less useful information. A GRU is a simpler recurrent model with fewer gates, often faster and more compact. A Temporal CNN applies convolution filters across time windows, looking for local temporal patterns such as acceleration, reversal, or volatility bursts.

Time-window models might help financial prediction because ETF leadership can depend on paths: trend persistence, volatility compression, drawdown recovery, and regime transitions. They might overfit because financial samples are noisy, regimes change, the validation window is short, and many model/overlay choices create data-mining risk.

This project uses sequence models to rank ETFs weekly. The models are tested as offensive ETF selectors, not as replacements for the core production portfolio.

## Defensive Overlay Explanation

Raw ML can have attractive returns but high drawdown because it stays exposed when model confidence is wrong or when market-wide stress dominates cross-sectional signals. The core regime engine can act as a risk filter by reducing ML exposure in stressed states.

BIL fallback sends unused exposure to the Treasury-bill proxy. Volatility targeting scales the ML sleeve toward a 10% annualized volatility target. The drawdown kill switch cuts exposure after the ML sleeve itself enters a drawdown. These wrappers test whether ML is more credible as an offensive sleeve inside a defensive framework than as a standalone production replacement.

## Technical Setup

- Torch available: {torch_meta.get('available')} / version: {torch_meta.get('version')}
- Device used: `{device}`
- Input sequence length: {sequence_lengths}
- Features: numeric MLX-2 features only; `Date` and `ticker` are identifiers.
- Main target: `top_quintile_forward_4w`
- Secondary target: `beats_SPY_4w`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architectures: small LSTM, GRU, Temporal CNN, and optional GRU for `beats_SPY_4w`.
- Loss: BCEWithLogitsLoss.
- Preprocessing: train-only median fill and train-only mean/std standardization.
- Leakage controls: no target-like `forward_*`, `beats_*`, or `top_quintile_*` input columns; validation and holdout do not fit preprocessing or model weights.

## Results

Models run:

{model_lines}

Models skipped:

{skip_lines}

- Best raw sequence model: {best_raw.get('strategy_name') if best_raw else 'n/a'} / Sharpe {fmt(best_raw.get('sharpe') if best_raw else np.nan)}
- Best defensive-overlay sequence model: {best_overlay.get('strategy_name') if best_overlay else 'n/a'} / Sharpe {fmt(best_overlay.get('sharpe') if best_overlay else np.nan)}
- Best holdout Sharpe: {fmt(best_any.get('sharpe') if best_any else np.nan)}
- Best holdout annual return: {fmt(best_ann.get('annual_return') if best_ann else np.nan, pct=True)}
- Best holdout max drawdown: {fmt(best_dd.get('max_drawdown') if best_dd else np.nan, pct=True)}
- Comparison vs MLX-4 best: beats by Sharpe = {comparisons.get('best_sequence_holdout_sharpe', np.nan) > comparisons.get('mlx4_best_holdout_sharpe', np.inf)}
- Comparison vs simple momentum: beats by Sharpe = {comparisons.get('best_sequence_holdout_sharpe', np.nan) > comparisons.get('simple_momentum_holdout_sharpe', np.inf)}
- Comparison vs production: beats by Sharpe = {comparisons.get('any_sequence_beats_production_sharpe')}
- Comparison vs official shadow: beats by Sharpe = {comparisons.get('any_sequence_beats_shadow_sharpe')}
- Overlays improve drawdown vs raw: {comparisons.get('overlay_improved_drawdown_vs_raw')}
- Overlays improve Sharpe vs raw: {comparisons.get('overlay_improved_sharpe_vs_raw')}

## Holdout Comparison Table

{cmp_md}

## Explicit Answers

1. Any sequence model beats current production on holdout Sharpe: {comparisons.get('any_sequence_beats_production_sharpe')}
2. Any sequence model beats official shadow on holdout Sharpe: {comparisons.get('any_sequence_beats_shadow_sharpe')}
3. Any sequence model beats production on annual return: {comparisons.get('any_sequence_beats_production_annual_return')}
4. Any sequence model beats production after considering max drawdown and CVaR: {comparisons.get('any_sequence_beats_production_after_drawdown_cvar')}
5. Defensive overlay makes ML more comparable to production risk: {comparisons.get('overlay_improved_drawdown_vs_raw')}
6. Standalone or offensive sleeve: research-only offensive sleeve candidate at most; not a production replacement.

## Interpretation

Sequence models test a richer time-history hypothesis than row-wise MLPs. The important question is not whether a single variant wins one holdout screen, but whether the result remains stable across stricter walk-forward tests and whether overlays reduce risk enough to resemble the core project. Anything promising remains ML shadow / research-only until it survives that process.

Warnings:

{warn_lines}
""", encoding="utf-8")


def main() -> int:
    warnings_list: list[str] = []
    skipped: list[dict[str, str]] = []
    print("Phase MLX-5 sequence model runner")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    torch_meta = torch_status()
    features, targets, weekly_returns = load_inputs()
    validate_inputs(features, targets)
    split = split_name_for_dates(features["Date"])
    split_ranges = {
        name: {"start": features.loc[split.eq(name), "Date"].min().date().isoformat(), "end": features.loc[split.eq(name), "Date"].max().date().isoformat(), "rows": int(split.eq(name).sum()), "dates": int(features.loc[split.eq(name), "Date"].nunique())}
        for name in ("train", "validation", "holdout")
    }
    configs = [
        SequenceConfig("lstm_classifier_top_quintile_forward_4w_seq26", "top_quintile_forward_4w", "lstm", 48, 0.20),
        SequenceConfig("gru_classifier_top_quintile_forward_4w_seq26", "top_quintile_forward_4w", "gru", 48, 0.20),
        SequenceConfig("temporal_cnn_classifier_top_quintile_forward_4w_seq26", "top_quintile_forward_4w", "tcn", 48, 0.20),
        SequenceConfig("gru_classifier_beats_SPY_4w_seq26", "beats_SPY_4w", "gru", 48, 0.20, max_epochs=25, patience=5),
    ]
    if not torch_meta.get("available"):
        for config in configs:
            skipped.append({"model_name": config.model_name, "reason": "torch missing or failed to import"})
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        pd.DataFrame().to_parquet(PREDICTIONS_OUT)
        pd.DataFrame().to_csv(BACKTEST_RETURNS_OUT, index=False)
        pd.DataFrame().to_csv(SUMMARY_OUT, index=False)
        pd.DataFrame().to_csv(TRAINING_CURVES_OUT, index=False)
        pd.DataFrame().to_csv(OVERLAY_SUMMARY_OUT, index=False)
        SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2) + "\n")
        PREPROCESSING_METADATA_OUT.write_text(json.dumps({"torch": torch_meta, "models_skipped": skipped}, indent=2) + "\n")
        write_notes(torch_meta, "none", [SEQ_LEN], [], skipped, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {}, warnings_list)
        return 0

    import torch
    set_seeds(torch)
    device = "cpu"
    prepared = prepare_features(features, split)
    all_end_indices = valid_sequence_end_indices(features, SEQ_LEN)
    ids = features[["Date", "ticker"]].copy()
    x = prepared["x"]

    pred_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    training_meta: list[dict[str, Any]] = []
    models_run: list[str] = []
    for config in configs:
        model, curves, meta = train_sequence_model(torch, config, x, targets[config.target], split, all_end_indices, device, warnings_list)
        if model is None:
            skipped.append({"model_name": config.model_name, "reason": meta.get("reason", "training skipped")})
            continue
        scores = predict_sequence_model(torch, model, x, all_end_indices, config.seq_len, device)
        pred = ids.iloc[all_end_indices].copy()
        pred["split"] = split.iloc[all_end_indices].values
        pred["model_name"] = config.model_name
        pred["target"] = config.target
        pred["score"] = scores
        pred["actual_target"] = targets[config.target].iloc[all_end_indices].values
        pred_frames.append(pred)
        curve_frames.append(curves)
        training_meta.append(meta)
        models_run.append(config.model_name)

    predictions = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    backtest_returns, summary, overlay_summary = run_backtests(features, predictions, warnings_list)
    returns_parts = [backtest_returns] if not backtest_returns.empty else []
    summary_rows = summary.to_dict("records") if not summary.empty else []
    append_external_baseline_from_returns(summary_rows, returns_parts, NN_RETURNS_IN, "mlx4_best_mlp", "mlx4_baseline", warnings_list)
    append_external_baseline_from_returns(summary_rows, returns_parts, TABULAR_RETURNS_IN, "mlx3_best_tabular_ml", "mlx3_baseline", warnings_list)
    backtest_returns = pd.concat(returns_parts, ignore_index=True) if returns_parts else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    project_comp = project_strategy_comparison(warnings_list)
    comparison = build_comparison_table(summary, project_comp)
    comparisons = compare_holdout(summary, project_comp)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    backtest_returns.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    curves.to_csv(TRAINING_CURVES_OUT, index=False)
    overlay_summary.to_csv(OVERLAY_SUMMARY_OUT, index=False)
    project_comp.to_csv(PROJECT_STRATEGY_COMPARISON_OUT, index=False)
    comparison.to_csv(COMPARISON_TABLE_OUT, index=False)
    SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default) + "\n", encoding="utf-8")
    metadata = {
        "phase": "MLX-5 sequence models",
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
        "sequence_lengths_used": [SEQ_LEN],
        "split_ranges": split_ranges,
        "inputs": {"features": str(FEATURES_IN.relative_to(ROOT)), "targets": str(TARGETS_IN.relative_to(ROOT)), "weekly_returns": str(WEEKLY_RETURNS_IN.relative_to(ROOT))},
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "overlay_summary": str(OVERLAY_SUMMARY_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "skipped_models": str(SKIPPED_MODELS_OUT.relative_to(ROOT)),
            "project_strategy_comparison": str(PROJECT_STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "comparison_table": str(COMPARISON_TABLE_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
        "feature_panel_shape": list(features.shape),
        "target_shape": list(targets.shape),
        "weekly_returns_shape": list(weekly_returns.shape),
        "models_run": models_run,
        "models_skipped": skipped,
        "training_metadata": training_meta,
        "numeric_feature_count_original": len(prepared["numeric_feature_cols_original"]),
        "numeric_feature_count_used": len(prepared["numeric_feature_cols"]),
        "dropped_features_extreme_missingness": prepared["dropped_features_extreme_missingness"],
        "train_only_preprocessing": {
            "median_fill_values": prepared["median_fill_values"],
            "standardization_means": prepared["standardization_means"],
            "standardization_stds": prepared["standardization_stds"],
            "train_missing_rate": prepared["train_missing_rate"],
        },
        "defensive_overlays_tested": ["raw_ml", "regime_gate", "bil_fallback", "vol_target", "drawdown_kill_switch"],
        "holdout_comparisons": comparisons,
        "warnings": warnings_list + ["Experimental research-only Phase MLX output; not production-valid.", "No sequence model is promoted automatically."],
    }
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(metadata, indent=2, default=json_default) + "\n", encoding="utf-8")
    write_notes(torch_meta, device, [SEQ_LEN], models_run, skipped, summary, project_comp, comparison, comparisons, warnings_list)

    best_raw = best_row(summary[summary["wrapper"].eq("raw_ml")], "holdout", ("model",))
    best_overlay = best_row(summary[~summary["wrapper"].eq("raw_ml")], "holdout", ("model",))
    best_any = best_row(summary, "holdout", ("model",))
    best_ann = best_row(summary, "holdout", ("model",), metric="annual_return")
    best_dd = best_row(summary, "holdout", ("model",), metric="max_drawdown", ascending=False)
    print(f"Torch available: {torch_meta.get('available')} version={torch_meta.get('version')}")
    print(f"Device used: {device}")
    print(f"Sequence lengths used: {[SEQ_LEN]}")
    print(f"Models run: {len(models_run)}")
    print(f"Models skipped: {len(skipped)}")
    print(f"Defensive overlays tested: raw_ml, regime_gate, bil_fallback, vol_target, drawdown_kill_switch")
    print(f"Best raw sequence model: {best_raw.get('strategy_name') if best_raw else 'none'}")
    print(f"Best overlay sequence model: {best_overlay.get('strategy_name') if best_overlay else 'none'}")
    print(f"Best holdout Sharpe: {best_any.get('sharpe') if best_any else np.nan}")
    print(f"Best holdout annual return: {best_ann.get('annual_return') if best_ann else np.nan}")
    print(f"Best holdout max drawdown: {best_dd.get('max_drawdown') if best_dd else np.nan}")
    print("Outputs:")
    for path in metadata["outputs"].values():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
