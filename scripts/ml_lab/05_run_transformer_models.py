#!/usr/bin/env python3
"""
Phase MLX-6: small Transformer encoder ETF sequence models.

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
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
SEQUENCE_DIR = ROOT / "data" / "research" / "ml_lab" / "sequence_models"
MLX5C_DIR = SEQUENCE_DIR / "multiseed_walkforward"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "transformers"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
SEQUENCE_BACKTEST_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_COMPARISON_IN = SEQUENCE_DIR / "sequence_comparison_table.csv"
PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
MLX5C_SUMMARY_IN = MLX5C_DIR / "sequence_multiseed_summary.json"
MLX5C_METRICS_IN = MLX5C_DIR / "sequence_multiseed_run_metrics.csv"

PREDICTIONS_OUT = OUTPUT_DIR / "transformer_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "transformer_backtest_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "transformer_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "transformer_training_curves.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "transformer_strategy_comparison.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "transformer_preprocessing_metadata.json"
SKIPPED_MODELS_OUT = OUTPUT_DIR / "transformer_skipped_models.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "transformer_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_transformer_model_notes.md"

TARGET = "top_quintile_forward_4w"
SECONDARY_TARGET = "beats_SPY_4w"
DEFAULT_COST_BPS = 10.0
BATCH_SIZE = 4096
MAX_EPOCHS = 8
PATIENCE = 2
HOLDOUT_START = pd.Timestamp("2020-01-01")


@dataclass(frozen=True)
class TransformerConfig:
    model_name: str
    target: str
    sequence_length: int
    seed: int
    d_model: int = 32
    nhead: int = 4
    num_layers: int = 1
    dim_feedforward: int = 64
    dropout: float = 0.20
    pooling: str = "last"
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


def load_mlx5_module() -> Any:
    path = ROOT / "scripts" / "ml_lab" / "04_run_sequence_models.py"
    spec = importlib.util.spec_from_file_location("mlx5_sequence_models", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import MLX-5 helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def set_seed(torch: Any, seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, __import__("os").cpu_count() or 1)))


def load_inputs(mlx5: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-6 inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    mlx5.validate_inputs(features, targets)
    weekly_returns = mlx5.load_panel_csv(WEEKLY_RETURNS_IN)
    return features, targets, weekly_returns


def base_split(features: pd.DataFrame) -> pd.Series:
    dates = features["Date"]
    split = pd.Series("unassigned", index=features.index, dtype="object")
    split.loc[dates <= pd.Timestamp("2017-12-31")] = "train"
    split.loc[(dates >= pd.Timestamp("2018-01-01")) & (dates <= pd.Timestamp("2019-12-31"))] = "validation"
    split.loc[dates >= pd.Timestamp("2020-01-01")] = "holdout"
    return split


def split_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(pd.to_datetime(dates), index=getattr(dates, "index", None))
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
    return out


def make_context(mlx5: Any, features: pd.DataFrame) -> dict[str, Any]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    tickers = sorted(features["ticker"].unique())
    next_returns = mlx5.next_week_return_panel(features).reindex(index=dates, columns=tickers)
    vol_panel = mlx5.matrix_by_date(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = mlx5.matrix_by_date(features, "realized_vol_26w")
    state = mlx5.infer_market_state_by_date(features)
    return {"dates": dates, "tickers": tickers, "next_returns": next_returns, "vol_panel": vol_panel, "state": state}


class TransformerSequenceDataset:
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


class TransformerPredictDataset:
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


def make_transformer_class(torch: Any) -> Any:
    nn = torch.nn

    class SmallTransformerClassifier(nn.Module):
        def __init__(self, input_dim: int, config: TransformerConfig):
            super().__init__()
            self.config = config
            self.input_proj = nn.Linear(input_dim, config.d_model)
            self.pos_embedding = nn.Parameter(torch.zeros(1, config.sequence_length, config.d_model))
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=config.d_model,
                nhead=config.nhead,
                dim_feedforward=config.dim_feedforward,
                dropout=config.dropout,
                activation="gelu",
                batch_first=True,
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=config.num_layers)
            self.dropout = nn.Dropout(config.dropout)
            self.head = nn.Linear(config.d_model, 1)
            nn.init.normal_(self.pos_embedding, mean=0.0, std=0.02)

        def forward(self, x: Any) -> Any:
            z = self.input_proj(x) + self.pos_embedding[:, : x.shape[1], :]
            z = self.encoder(z)
            pooled = z.mean(dim=1) if self.config.pooling == "mean" else z[:, -1, :]
            return self.head(self.dropout(pooled))

    return SmallTransformerClassifier


def train_transformer(torch: Any, config: TransformerConfig, x: np.ndarray, target: pd.Series, split: pd.Series, all_end_indices: np.ndarray, device: str) -> tuple[Any | None, pd.DataFrame, dict[str, Any]]:
    y_all = pd.to_numeric(target, errors="coerce")
    train_idx = all_end_indices[(split.iloc[all_end_indices].to_numpy() == "train") & y_all.iloc[all_end_indices].notna().to_numpy()]
    val_idx = all_end_indices[(split.iloc[all_end_indices].to_numpy() == "validation") & y_all.iloc[all_end_indices].notna().to_numpy()]
    if len(train_idx) < 1000 or len(val_idx) < 100:
        return None, pd.DataFrame(), {"reason": "insufficient train/validation sequence rows"}
    y_train = y_all.iloc[train_idx].astype("float32").to_numpy()
    y_val = y_all.iloc[val_idx].astype("float32").to_numpy()
    pos = float(y_train.sum())
    neg = float(len(y_train) - pos)
    pos_weight = neg / pos if pos > 0 else 1.0

    set_seed(torch, config.seed)
    train_loader = torch.utils.data.DataLoader(TransformerSequenceDataset(torch, x, train_idx, y_train, config.sequence_length), batch_size=BATCH_SIZE, shuffle=True)
    val_loader = torch.utils.data.DataLoader(TransformerSequenceDataset(torch, x, val_idx, y_val, config.sequence_length), batch_size=BATCH_SIZE, shuffle=False)
    model_cls = make_transformer_class(torch)
    model = model_cls(x.shape[1], config).to(device)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], dtype=torch.float32, device=device))
    opt = torch.optim.AdamW(model.parameters(), lr=8e-4, weight_decay=1e-4)

    best_loss = float("inf")
    best_epoch = 0
    best_state = None
    stale = 0
    rows: list[dict[str, Any]] = []
    for epoch in range(1, config.max_epochs + 1):
        model.train()
        train_losses = []
        for xb, yb in train_loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            train_losses.append(float(loss.detach().cpu().item()))
        model.eval()
        val_losses = []
        with torch.no_grad():
            for xb, yb in val_loader:
                xb = xb.to(device)
                yb = yb.to(device)
                val_losses.append(float(loss_fn(model(xb), yb).detach().cpu().item()))
        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses))
        if val_loss < best_loss - 1e-6:
            best_loss = val_loss
            best_epoch = epoch
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
        rows.append({
            "model_name": config.model_name,
            "target": config.target,
            "sequence_length": config.sequence_length,
            "seed": config.seed,
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
        "sequence_length": config.sequence_length,
        "seed": config.seed,
        "d_model": config.d_model,
        "nhead": config.nhead,
        "num_layers": config.num_layers,
        "dim_feedforward": config.dim_feedforward,
        "dropout": config.dropout,
        "pooling": config.pooling,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "epochs_run": len(rows),
        "positive_rate_train": pos / max(1, len(y_train)),
        "pos_weight": pos_weight,
        "train_sequences": int(len(train_idx)),
        "validation_sequences": int(len(val_idx)),
    }
    return model, pd.DataFrame(rows), meta


def predict_transformer(torch: Any, model: Any, x: np.ndarray, end_indices: np.ndarray, seq_len: int, device: str) -> np.ndarray:
    loader = torch.utils.data.DataLoader(TransformerPredictDataset(torch, x, end_indices, seq_len), batch_size=BATCH_SIZE * 2, shuffle=False)
    model.eval()
    out: list[np.ndarray] = []
    with torch.no_grad():
        for xb in loader:
            raw = model(xb.to(device)).detach().cpu().numpy().reshape(-1)
            out.append((1.0 / (1.0 + np.exp(-raw))).astype("float64"))
    return np.concatenate(out)


def overlay_weights(mlx5: Any, wrapper: str, raw_weights: pd.DataFrame, context: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    state = context["state"].reindex(dates).fillna("unknown")
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "bil_fallback_original":
        exposure = state.map({"stressed_panic": 0.25, "neutral_mixed": 0.75}).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "regime_gate_original":
        exposure = state.map({"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}).fillna(0.70)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "vol_target_10pct":
        next_returns = context["next_returns"]
        raw_gross = raw_weights.mul(next_returns.reindex(index=dates, columns=raw_weights.columns).fillna(0.0)).sum(axis=1)
        ann_vol = raw_gross.shift(1).rolling(13, min_periods=6).std() * math.sqrt(52.0)
        exposure = (0.10 / ann_vol.replace(0.0, np.nan)).clip(0.0, 1.0).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"Unknown overlay wrapper: {wrapper}")


def run_backtests(mlx5: Any, features: pd.DataFrame, predictions: pd.DataFrame, context: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    wrappers = ["raw_ml", "bil_fallback_original", "regime_gate_original", "vol_target_10pct"]
    all_returns: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for model_name, group in predictions.groupby("model_name", sort=True):
        target = str(group["target"].iloc[0])
        seq_len = int(group["sequence_length"].iloc[0])
        seed = int(group["seed"].iloc[0])
        for top_n in (10, 15):
            raw = mlx5.weights_from_scores(group, context["dates"], context["tickers"], top_n, "inverse_vol", context["next_returns"], context["vol_panel"])
            for wrapper in wrappers:
                weights, exposure = overlay_weights(mlx5, wrapper, raw, context)
                path = mlx5.compute_path(weights, context["next_returns"], DEFAULT_COST_BPS, exposure)
                strategy = f"{model_name}__top{top_n}__inverse_vol__{wrapper}"
                dated = path.reset_index(names="Date")
                dated["split"] = split_for_dates(dated["Date"]).values
                dated["strategy_name"] = strategy
                dated["strategy_type"] = "transformer"
                dated["model_name"] = model_name
                dated["target"] = target
                dated["sequence_length"] = seq_len
                dated["seed"] = seed
                dated["top_n"] = top_n
                dated["weighting"] = "inverse_vol"
                dated["wrapper"] = wrapper
                dated["cost_bps"] = DEFAULT_COST_BPS
                all_returns.append(dated)
                for split_name in ("train", "validation", "holdout"):
                    metrics = mlx5.calc_metrics(dated[dated["split"].eq(split_name)])
                    metrics.update({
                        "strategy_name": strategy,
                        "strategy_type": "transformer",
                        "model_name": model_name,
                        "target": target,
                        "sequence_length": seq_len,
                        "seed": seed,
                        "top_n": top_n,
                        "weighting": "inverse_vol",
                        "wrapper": wrapper,
                        "split": split_name,
                        "cost_bps": DEFAULT_COST_BPS,
                    })
                    summary_rows.append(metrics)
    returns = pd.concat(all_returns, ignore_index=True) if all_returns else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return returns, summary


def add_baselines_and_comparisons(mlx5: Any, features: pd.DataFrame, context: dict[str, Any], transformer_summary: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    holdout_start = pd.Timestamp("2020-01-01")
    holdout_end = pd.Timestamp(features["Date"].max())
    dates = context["dates"][(context["dates"] >= holdout_start) & (context["dates"] <= holdout_end)]

    def add_row(label: str, category: str, metrics: dict[str, Any], source: str = "") -> None:
        metrics = dict(metrics)
        metrics.update({"comparison_label": label, "category": category, "source": source})
        rows.append(metrics)

    hold = transformer_summary[(transformer_summary["split"].eq("holdout")) & (transformer_summary["strategy_type"].eq("transformer"))].copy()
    if not hold.empty:
        raw = hold[hold["wrapper"].eq("raw_ml")].sort_values(["sharpe", "annual_return"], ascending=[False, False])
        overlay = hold[~hold["wrapper"].eq("raw_ml")].sort_values(["sharpe", "annual_return"], ascending=[False, False])
        if not raw.empty:
            add_row("Best raw Transformer", "transformer", raw.iloc[0].to_dict(), "transformer_summary")
        if not overlay.empty:
            add_row("Best overlay Transformer", "transformer", overlay.iloc[0].to_dict(), "transformer_summary")

    # Local baselines on the same 2020+ holdout.
    for baseline in ("baseline_spy_buy_hold", "baseline_60_40_spy_ief_or_agg"):
        w = mlx5.static_baseline_weights(baseline, dates, context["tickers"], context["next_returns"])
        metrics = mlx5.calc_metrics(mlx5.compute_path(w, context["next_returns"], DEFAULT_COST_BPS))
        add_row("SPY" if baseline == "baseline_spy_buy_hold" else "60/40", "baseline", metrics, "computed")
    momentum_col = "momentum_12_1" if "momentum_12_1" in features.columns else "trailing_return_26w"
    score = features[["Date", "ticker", momentum_col]].rename(columns={momentum_col: "score"})
    for top_n in (10, 15):
        w = mlx5.weights_from_scores(score, dates, context["tickers"], top_n, "inverse_vol", context["next_returns"], context["vol_panel"])
        metrics = mlx5.calc_metrics(mlx5.compute_path(w, context["next_returns"], DEFAULT_COST_BPS))
        add_row(f"Simple momentum top{top_n}", "baseline_momentum", metrics, "computed")

    if SEQUENCE_COMPARISON_IN.exists():
        comp = pd.read_csv(SEQUENCE_COMPARISON_IN)
        for label in ["Best defensive-overlay sequence model", "MLX-4 best MLP", "MLX-3 best tabular ML"]:
            sub = comp[comp["comparison_label"].eq(label)] if "comparison_label" in comp.columns else pd.DataFrame()
            if not sub.empty:
                row = sub.iloc[0].to_dict()
                add_row(label, "prior_mlx", row, str(SEQUENCE_COMPARISON_IN.relative_to(ROOT)))
    else:
        warn("MLX-5 sequence comparison table missing.", warnings_list)

    if PROJECT_COMPARISON_IN.exists():
        project = pd.read_csv(PROJECT_COMPARISON_IN)
        labels = {
            "current_production": "Current production",
            "official_shadow": "Official shadow",
            "phase4b": "Phase 4B best",
            "phase6": "Phase 6 best",
            "phase7": "Phase 7 stretch",
        }
        for category, label in labels.items():
            sub = project[project["category"].eq(category)] if "category" in project.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No project strategy comparison found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict()
            add_row(label, category, row, row.get("source_path", ""))
    else:
        warn("Project strategy comparison file missing.", warnings_list)

    if MLX5C_SUMMARY_IN.exists():
        mlx5c = json.loads(MLX5C_SUMMARY_IN.read_text())
        add_row("MLX-5C bil-fallback mean", "prior_mlx5c", {
            "annual_return": np.nan,
            "annual_volatility": np.nan,
            "sharpe": mlx5c.get("overall_mean_sharpe", np.nan),
            "max_drawdown": mlx5c.get("overall_worst_case_max_drawdown", np.nan),
            "calmar": np.nan,
            "cvar_5": mlx5c.get("overall_worst_case_cvar_5", np.nan),
            "average_turnover": np.nan,
            "annual_cost_drag": np.nan,
            "average_bil_weight": np.nan,
            "active_weeks": np.nan,
        }, str(MLX5C_SUMMARY_IN.relative_to(ROOT)))
    else:
        warn("MLX-5C summary missing; Transformer comparison to MLX-5C is incomplete.", warnings_list)

    return pd.DataFrame(rows)


def best_row(df: pd.DataFrame, split: str = "holdout", wrapper_filter: str | None = None, metric: str = "sharpe", ascending: bool = False) -> dict[str, Any] | None:
    sub = df[df["split"].eq(split)].copy() if "split" in df.columns else df.copy()
    if wrapper_filter == "raw":
        sub = sub[sub["wrapper"].eq("raw_ml")]
    elif wrapper_filter == "overlay":
        sub = sub[~sub["wrapper"].eq("raw_ml")]
    sub = sub[pd.to_numeric(sub[metric], errors="coerce").notna()]
    if sub.empty:
        return None
    return sub.sort_values([metric, "annual_return"], ascending=[ascending, False]).iloc[0].to_dict()


def pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}"


def num(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "No rows available."
    sub = df[[c for c in cols if c in df.columns]].head(max_rows).copy()
    pct_cols = [c for c in sub.columns if c in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "annual_cost_drag", "average_bil_weight"}]
    for col in pct_cols:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(pct)
    for col in [c for c in ["sharpe", "calmar"] if c in sub.columns]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(num)
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def choose_recommendation(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    best_overlay = best_row(summary, "holdout", "overlay")
    if best_overlay is None:
        return "REJECT"
    transformer_sharpe = float(best_overlay.get("sharpe", np.nan))
    mlx5c = comparison[comparison["comparison_label"].eq("MLX-5C bil-fallback mean")] if not comparison.empty else pd.DataFrame()
    mlx5c_sharpe = float(mlx5c.iloc[0]["sharpe"]) if not mlx5c.empty and pd.notna(mlx5c.iloc[0]["sharpe"]) else np.nan
    production = comparison[comparison["comparison_label"].eq("Current production")] if not comparison.empty else pd.DataFrame()
    production_sharpe = float(production.iloc[0]["sharpe"]) if not production.empty and pd.notna(production.iloc[0]["sharpe"]) else np.nan
    if pd.notna(mlx5c_sharpe) and transformer_sharpe > mlx5c_sharpe and pd.notna(production_sharpe) and transformer_sharpe > production_sharpe:
        return "PROCEED TO ENSEMBLE TESTING"
    if transformer_sharpe > 0.8:
        return "NEEDS MULTI-SEED / WALK-FORWARD BEFORE JUDGMENT"
    if transformer_sharpe > 0.4:
        return "KEEP AS RESEARCH ONLY"
    return "REJECT"


def write_notes(torch_meta: dict[str, Any], device: str, configs: list[TransformerConfig], skipped: list[dict[str, Any]], summary: pd.DataFrame, comparison: pd.DataFrame, metadata: dict[str, Any], warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    hold = summary[summary["split"].eq("holdout")].copy() if not summary.empty else pd.DataFrame()
    best_raw = best_row(summary, "holdout", "raw")
    best_overlay = best_row(summary, "holdout", "overlay")
    best_return = best_row(summary, "holdout", None, "annual_return")
    best_dd = best_row(summary, "holdout", None, "max_drawdown")
    model_lines = "\n".join(f"- `{c.model_name}`: seq={c.sequence_length}, seed={c.seed}, d_model={c.d_model}, heads={c.nhead}, layers={c.num_layers}" for c in configs) or "- None"
    skip_lines = "\n".join(f"- {s['model_name']}: {s['reason']}" for s in skipped) or "- None"
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"
    comp_sorted = comparison.sort_values(["sharpe", "annual_return"], ascending=[False, False]) if not comparison.empty and "sharpe" in comparison.columns else comparison
    hold_sorted = hold.sort_values(["sharpe", "annual_return"], ascending=[False, False]) if not hold.empty else hold

    NOTES_OUT.write_text(f"""# Phase MLX Transformer Model Notes

## Research-Only Warning

Phase MLX-6 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

A Transformer is a neural network architecture that reads a sequence and uses attention to decide which past time steps matter most. Attention means the model can learn relationships between different weeks in the lookback window instead of only reading the sequence from left to right. Positional encoding gives the model a sense of order, so week 1 and week 26 are not treated as interchangeable.

Transformers might help ETF time-series ranking because they can look across the whole recent path for trend, volatility, recovery, or regime-transition patterns. They may overfit financial data because the signal-to-noise ratio is low, markets change, and attention layers can learn accidental historical quirks. In this project, the Transformer scores each ETF-date row, ETFs are ranked weekly by score, and defensive overlays such as BIL fallback, regime gates, and volatility targeting reduce exposure when risk conditions look unfavorable.

## Technical Setup

- Torch available: {torch_meta.get('available')} / version: {torch_meta.get('version')}
- Device used: `{device}`
- Sequence lengths tested: {metadata.get('sequence_lengths_tested')}
- Seeds tested: {metadata.get('seeds_tested')}
- Features: numeric MLX-2 features only; `Date` and `ticker` are identifiers.
- Target: `{TARGET}`
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architecture: input projection to d_model=32, learned positional embeddings, 1-layer TransformerEncoder, 4 attention heads, feedforward size 64, dropout 0.20, final-step pooling, one-logit classifier.
- Loss: `BCEWithLogitsLoss` with train-set positive-class weighting.
- Early stopping: validation loss only.
- Preprocessing: train-only median fill and train-only standardization.
- Leakage controls: targets are excluded from features, forward returns are targets only, and validation/holdout are never used for preprocessing statistics or model fitting.

## Models Run

{model_lines}

## Models Skipped

{skip_lines}

## Holdout Results

{markdown_table(hold_sorted, ['strategy_name', 'sequence_length', 'seed', 'top_n', 'wrapper', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_weight'], max_rows=16)}

## Best Results

- Best raw Transformer: `{best_raw.get('strategy_name') if best_raw else 'n/a'}` with Sharpe {num(best_raw.get('sharpe') if best_raw else np.nan)}.
- Best overlay Transformer: `{best_overlay.get('strategy_name') if best_overlay else 'n/a'}` with Sharpe {num(best_overlay.get('sharpe') if best_overlay else np.nan)}.
- Best holdout annual return: `{best_return.get('strategy_name') if best_return else 'n/a'}` at {pct(best_return.get('annual_return') if best_return else np.nan)}.
- Best drawdown: `{best_dd.get('strategy_name') if best_dd else 'n/a'}` with max drawdown {pct(best_dd.get('max_drawdown') if best_dd else np.nan)}.

## Comparison Table

{markdown_table(comp_sorted, ['comparison_label', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_weight'], max_rows=24)}

## Interpretation

The Transformer should be judged against the simpler MLX-5/5C sequence models, not just against SPY or a single holdout period. If the Transformer does not clearly beat MLX-5C or Phase 4B, it should remain research-only or wait for ensemble testing rather than becoming an ML shadow. Defensive overlays are useful only if they improve Sharpe or reduce drawdown without making the model a disguised cash/BIL strategy.

Final recommendation: **{metadata.get('final_recommendation')}**

## Warnings

{warn_lines}
""")


def empty_outputs(reason: str, warnings_list: list[str], torch_meta: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame().to_parquet(PREDICTIONS_OUT, index=False)
    pd.DataFrame().to_csv(BACKTEST_RETURNS_OUT, index=False)
    pd.DataFrame().to_csv(SUMMARY_OUT, index=False)
    pd.DataFrame().to_csv(TRAINING_CURVES_OUT, index=False)
    pd.DataFrame().to_csv(STRATEGY_COMPARISON_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps({"research_only": True, "production_valid": False, "torch": torch_meta, "reason": reason, "warnings": warnings_list}, indent=2, default=json_default))
    SKIPPED_MODELS_OUT.write_text(json.dumps([{"model_name": "transformer", "reason": reason}], indent=2) + "\n")
    SUMMARY_JSON_OUT.write_text(json.dumps({"research_only": True, "production_valid": False, "reason": reason}, indent=2))
    NOTES_OUT.write_text(f"""# Phase MLX Transformer Model Notes

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

A Transformer uses attention over a sequence. Training was skipped because {reason}.
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    torch_meta = torch_status()
    if not torch_meta.get("available"):
        warn("torch is missing; skipping Transformer training.", warnings_list)
        empty_outputs("torch missing", warnings_list, torch_meta)
        return
    import torch

    mlx5 = load_mlx5_module()
    features, targets, weekly_returns = load_inputs(mlx5)
    if "BIL" not in weekly_returns.columns:
        warn("BIL returns are missing; BIL fallback overlays may be incomplete.", warnings_list)
    split = base_split(features)
    prepared = mlx5.prepare_features(features, split)
    context = make_context(mlx5, features)
    ids = features[["Date", "ticker"]].copy()
    x = prepared["x"]
    device = "cpu"

    configs = [
        TransformerConfig("transformer_encoder_top_quintile_forward_4w_seq13_seed0", TARGET, 13, 0),
        TransformerConfig("transformer_encoder_top_quintile_forward_4w_seq26_seed0", TARGET, 26, 0),
    ]
    skipped = [
        {"model_name": "transformer_encoder_top_quintile_forward_4w_seq52_seed0", "reason": "skipped 52-week Transformer for bounded CPU runtime"},
        {"model_name": "transformer_encoder_top_quintile_forward_4w_seq26_seed1", "reason": "skipped additional Transformer seed for bounded CPU runtime"},
        {"model_name": "transformer_encoder_top_quintile_forward_4w_seq26_seed2", "reason": "skipped additional Transformer seed for bounded CPU runtime"},
        {"model_name": "transformer_encoder_beats_SPY_4w_seq26_seed0", "reason": "skipped secondary beats_SPY target for bounded CPU runtime"},
        {"model_name": "transformer_walk_forward_retraining", "reason": "deferred full Transformer walk-forward retraining; use MLX-5C walk-forward sequence results for robustness context"},
        {"model_name": "transformer_equal_weight_portfolios", "reason": "skipped optional equal-weight portfolios to keep MLX-6 bounded"},
    ]

    pred_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    training_meta: list[dict[str, Any]] = []
    for i, config in enumerate(configs, start=1):
        print(f"Running MLX-6 Transformer {i}/{len(configs)}: seq={config.sequence_length} seed={config.seed}", flush=True)
        all_end_indices = mlx5.valid_sequence_end_indices(features, config.sequence_length)
        model, curves, meta = train_transformer(torch, config, x, targets[config.target], split, all_end_indices, device)
        if model is None:
            skipped.append({"model_name": config.model_name, "reason": meta.get("reason", "training skipped")})
            continue
        scores = predict_transformer(torch, model, x, all_end_indices, config.sequence_length, device)
        pred = ids.iloc[all_end_indices].copy()
        pred["split"] = split.iloc[all_end_indices].values
        pred["model_name"] = config.model_name
        pred["target"] = config.target
        pred["sequence_length"] = config.sequence_length
        pred["seed"] = config.seed
        pred["score"] = scores
        pred["actual_target"] = targets[config.target].iloc[all_end_indices].values
        pred_frames.append(pred)
        curve_frames.append(curves)
        training_meta.append(meta)

    predictions = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    backtest_returns, summary = run_backtests(mlx5, features, predictions, context) if not predictions.empty else (pd.DataFrame(), pd.DataFrame())
    comparison = add_baselines_and_comparisons(mlx5, features, context, summary, warnings_list)
    recommendation = choose_recommendation(summary, comparison)

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    backtest_returns.to_csv(BACKTEST_RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    curves.to_csv(TRAINING_CURVES_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    SKIPPED_MODELS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default) + "\n")

    best_raw = best_row(summary, "holdout", "raw")
    best_overlay = best_row(summary, "holdout", "overlay")
    best_return = best_row(summary, "holdout", None, "annual_return")
    best_dd = best_row(summary, "holdout", None, "max_drawdown")
    metadata = {
        "phase": "MLX-6 Transformer encoder models",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "torch": torch_meta,
        "device_used": device,
        "architecture": {"d_model": 32, "nhead": 4, "num_layers": 1, "dim_feedforward": 64, "dropout": 0.20, "pooling": "last"},
        "sequence_lengths_tested": sorted(predictions["sequence_length"].dropna().astype(int).unique().tolist()) if not predictions.empty else [],
        "seeds_tested": sorted(predictions["seed"].dropna().astype(int).unique().tolist()) if not predictions.empty else [],
        "targets_tested": sorted(predictions["target"].dropna().unique().tolist()) if not predictions.empty else [],
        "overlays_tested": ["raw_ml", "bil_fallback_original", "regime_gate_original", "vol_target_10pct"],
        "models_run": [c.model_name for c in configs if c.model_name in set(predictions.get("model_name", pd.Series(dtype=str)).unique())],
        "models_skipped": skipped,
        "training_metadata": training_meta,
        "feature_panel_shape": list(features.shape),
        "target_shape": list(targets.shape),
        "weekly_returns_shape": list(weekly_returns.shape),
        "numeric_feature_count_original": len(prepared["numeric_feature_cols_original"]),
        "numeric_feature_count_used": len(prepared["numeric_feature_cols"]),
        "dropped_features_extreme_missingness": prepared["dropped_features_extreme_missingness"],
        "train_only_preprocessing": {
            "median_fill_values": prepared["median_fill_values"],
            "standardization_means": prepared["standardization_means"],
            "standardization_stds": prepared["standardization_stds"],
            "train_missing_rate": prepared["train_missing_rate"],
        },
        "best_raw_transformer": best_raw,
        "best_overlay_transformer": best_overlay,
        "best_holdout_annual_return": best_return,
        "best_holdout_max_drawdown": best_dd,
        "final_recommendation": recommendation,
        "warnings": warnings_list + ["Experimental research-only Phase MLX output; not production-valid.", "No Transformer model is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "preprocessing_metadata": str(PREPROCESSING_METADATA_OUT.relative_to(ROOT)),
            "skipped_models": str(SKIPPED_MODELS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(metadata, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps({
        "phase": metadata["phase"],
        "research_only": True,
        "production_valid": False,
        "best_raw_transformer": best_raw,
        "best_overlay_transformer": best_overlay,
        "best_holdout_annual_return": best_return,
        "best_holdout_max_drawdown": best_dd,
        "final_recommendation": recommendation,
        "warnings": metadata["warnings"],
    }, indent=2, default=json_default))
    write_notes(torch_meta, device, configs, skipped, summary, comparison, metadata, metadata["warnings"])

    print("Phase MLX-6 Transformer encoder models")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Torch available: {torch_meta.get('available')} version={torch_meta.get('version')}")
    print(f"Device used: {device}")
    print("Architecture: d_model=32, nhead=4, layers=1, feedforward=64, dropout=0.20, pooling=last")
    print(f"Sequence lengths tested: {metadata['sequence_lengths_tested']}")
    print(f"Seeds tested: {metadata['seeds_tested']}")
    print(f"Overlays tested: {metadata['overlays_tested']}")
    print(f"Best raw Transformer: {best_raw.get('strategy_name') if best_raw else 'n/a'}")
    print(f"Best overlay Transformer: {best_overlay.get('strategy_name') if best_overlay else 'n/a'}")
    print(f"Best holdout Sharpe: {best_overlay.get('sharpe') if best_overlay else np.nan}")
    print(f"Best holdout annual return: {best_return.get('annual_return') if best_return else np.nan}")
    print(f"Best max drawdown: {best_dd.get('max_drawdown') if best_dd else np.nan}")
    print(f"Final recommendation: {recommendation}")
    print("Outputs:")
    for path in [PREDICTIONS_OUT, BACKTEST_RETURNS_OUT, SUMMARY_OUT, TRAINING_CURVES_OUT, STRATEGY_COMPARISON_OUT, PREPROCESSING_METADATA_OUT, SKIPPED_MODELS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
