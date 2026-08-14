#!/usr/bin/env python3
"""
Phase MLX-12B: benchmark-relative decision-focused ETF learning.

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
DECISION_DIR = ML_DIR / "decision_focused"
TRIPLE_DIR = ML_DIR / "triple_barrier_meta"
OUTPUT_DIR = ML_DIR / "decision_focused_benchmark_relative"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"

SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_RETURNS_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
SEQUENCE_5C_SUMMARY_IN = SEQUENCE_5C_DIR / "sequence_multiseed_summary.json"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_RETURNS_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
ENSEMBLE_SUMMARY_JSON_IN = ENSEMBLE_DIR / "ensemble_summary.json"
ENSEMBLE_RETURNS_IN = ENSEMBLE_DIR / "ensemble_strategy_returns.csv"
DECISION_SUMMARY_JSON_IN = DECISION_DIR / "decision_focused_summary.json"
DECISION_RETURNS_IN = DECISION_DIR / "decision_focused_returns.csv"
TRIPLE_SUMMARY_JSON_IN = TRIPLE_DIR / "triple_barrier_summary.json"
TRIPLE_RETURNS_IN = TRIPLE_DIR / "triple_barrier_strategy_returns.csv"
TRIPLE_LABELS_IN = TRIPLE_DIR / "triple_barrier_labels.parquet"

PREDICTIONS_OUT = OUTPUT_DIR / "benchmark_relative_predictions.parquet"
WEIGHTS_OUT = OUTPUT_DIR / "benchmark_relative_weights.parquet"
RETURNS_OUT = OUTPUT_DIR / "benchmark_relative_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "benchmark_relative_summary.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "benchmark_relative_training_curves.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "benchmark_relative_strategy_comparison.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "benchmark_relative_state_by_state.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "benchmark_relative_exposure_audit.csv"
WALKFORWARD_OUT = OUTPUT_DIR / "benchmark_relative_walkforward_summary.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "benchmark_relative_preprocessing_metadata.json"
CANDIDATE_DEFINITIONS_OUT = OUTPUT_DIR / "benchmark_relative_candidate_definitions.json"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "benchmark_relative_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "benchmark_relative_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_12b_benchmark_relative_decision_focused_learning_notes.md"

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
MAX_EPOCHS = 20
PATIENCE = 4
SEEDS = (0, 1)
SOFTMAX_TEMPERATURE = 0.50
SAFE_ASSETS = {"BIL", "SHV", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD", "MUB", "STIP", "VGSH", "VGIT"}


@dataclass(frozen=True)
class BenchConfig:
    model_name: str
    loss_kind: str
    benchmark_name: str
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
            "average_safe_exposure",
            "average_risky_exposure",
            "average_benchmark_excess_return",
            "tracking_error",
            "average_top3_weight",
        }:
            tmp[col] = tmp[col].map(pct)
        elif col in {"sharpe", "calmar", "information_ratio", "rank_ic", "top_quintile_hit_rate"}:
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
        raise FileNotFoundError(f"Required MLX-12B inputs missing: {missing}")
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
        warn("BIL returns are missing; BIL fallback overlays will be skipped or less meaningful.", warnings_list)
    return features, targets, weekly_returns, universe_meta


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
        warn("Sequence project strategy comparison missing; Phase 4B/6/7 comparisons may be skipped.", warnings_list)
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


def load_strategy_returns(weekly_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    frames: dict[str, pd.Series] = {}
    sources: dict[str, str] = {}
    for name, path in select_project_strategy_files(warnings_list).items():
        try:
            frame = read_return_file(path)
            frames[name] = frame["net_return"].rename(name)
            sources[name] = str(path.relative_to(ROOT))
        except Exception as exc:
            warn(f"Could not read project strategy {name}: {exc}", warnings_list)
    if "SPY" in weekly_returns.columns:
        frames["SPY"] = weekly_returns["SPY"].rename("SPY")
    if "BIL" in weekly_returns.columns:
        frames["BIL"] = weekly_returns["BIL"].rename("BIL")
    else:
        frames["BIL"] = pd.Series(0.0, index=weekly_returns.index, name="BIL")
        warn("BIL was not available in weekly returns; using 0 return cash proxy for overlay accounting.", warnings_list)
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond:
        frames["60_40"] = (0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]).rename("60_40")
    if SEQUENCE_SUMMARY_IN.exists() and SEQUENCE_RETURNS_IN.exists():
        seq = load_best_strategy(SEQUENCE_SUMMARY_IN, SEQUENCE_RETURNS_IN, "MLX-5 sequence", lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("model")) & (~s["wrapper"].eq("raw_ml"))], warnings_list)
        if not seq.empty:
            frames["mlx5_sequence"] = seq["net_return"].rename("mlx5_sequence")
        mom = load_best_strategy(SEQUENCE_SUMMARY_IN, SEQUENCE_RETURNS_IN, "simple momentum", lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("baseline_momentum"))], warnings_list)
        if not mom.empty:
            frames["simple_momentum"] = mom["net_return"].rename("simple_momentum")
    if TRANSFORMER_SUMMARY_IN.exists() and TRANSFORMER_RETURNS_IN.exists():
        tr = load_best_strategy(TRANSFORMER_SUMMARY_IN, TRANSFORMER_RETURNS_IN, "MLX-6 Transformer", lambda s: s[(s["split"].eq("holdout")) & (~s["wrapper"].eq("raw_ml"))], warnings_list)
        if not tr.empty:
            frames["mlx6_transformer"] = tr["net_return"].rename("mlx6_transformer")
    if ENSEMBLE_SUMMARY_JSON_IN.exists() and ENSEMBLE_RETURNS_IN.exists():
        try:
            data = json.loads(ENSEMBLE_SUMMARY_JSON_IN.read_text())
            name = data.get("best_validation_selected_ensemble", {}).get("strategy_name")
            ens = pd.read_csv(ENSEMBLE_RETURNS_IN, parse_dates=["Date"])
            if name:
                sub = ens[ens["strategy_name"].eq(name)].set_index("Date").sort_index()
                if not sub.empty:
                    frames["mlx9_ensemble"] = sub["net_return"].rename("mlx9_ensemble")
        except Exception as exc:
            warn(f"Could not load MLX-9 ensemble comparison: {exc}", warnings_list)
    if DECISION_SUMMARY_JSON_IN.exists() and DECISION_RETURNS_IN.exists():
        try:
            data = json.loads(DECISION_SUMMARY_JSON_IN.read_text())
            name = data.get("best_validation_model", {}).get("strategy_name")
            dec = pd.read_csv(DECISION_RETURNS_IN, parse_dates=["Date"])
            if name:
                sub = dec[dec["strategy_name"].eq(name)].set_index("Date").sort_index()
                if not sub.empty:
                    frames["mlx12_decision_focused"] = sub["net_return"].rename("mlx12_decision_focused")
        except Exception as exc:
            warn(f"Could not load MLX-12 comparison: {exc}", warnings_list)
    if TRIPLE_SUMMARY_JSON_IN.exists() and TRIPLE_RETURNS_IN.exists():
        try:
            data = json.loads(TRIPLE_SUMMARY_JSON_IN.read_text())
            tri = pd.read_csv(TRIPLE_RETURNS_IN, parse_dates=["Date"])
            for key, label in [("validation_selected_holdout", "mlx13_validation_filter"), ("best_holdout_diagnostic_strategy", "mlx13_holdout_diagnostic")]:
                name = data.get(key, {}).get("strategy_name")
                if name:
                    sub = tri[tri["strategy_name"].eq(name)].set_index("Date").sort_index()
                    if not sub.empty:
                        frames[label] = sub["net_return"].rename(label)
        except Exception as exc:
            warn(f"Could not load MLX-13 comparison: {exc}", warnings_list)
    if not frames:
        raise RuntimeError("No benchmark strategy returns were loaded.")
    out = pd.concat(frames.values(), axis=1).sort_index()
    return out, sources


def load_triple_barrier_guidance(dates: pd.DatetimeIndex, warnings_list: list[str]) -> pd.DataFrame:
    guidance = pd.DataFrame(index=dates, data={"tb_prod_danger": 0.0, "tb_prod_up": 0.0, "tb_phase4b_danger": 0.0, "tb_phase4b_up": 0.0})
    if not TRIPLE_LABELS_IN.exists():
        warn("MLX-13 triple-barrier labels missing; triple-barrier-aware objective will use zero guidance.", warnings_list)
        return guidance
    labels = pd.read_parquet(TRIPLE_LABELS_IN)
    labels["Date"] = pd.to_datetime(labels["Date"])
    mapping = {
        ("task_1_production_triple_barrier", "h13_u3_l3"): ("tb_prod_danger", "tb_prod_up"),
        ("task_2_phase4b_triple_barrier", "h13_u3_l3"): ("tb_phase4b_danger", "tb_phase4b_up"),
    }
    for (task, barrier), (down_col, up_col) in mapping.items():
        sub = labels[(labels["task_id"].eq(task)) & (labels["barrier_id"].eq(barrier))].set_index("Date")
        if sub.empty:
            continue
        guidance[down_col] = sub["label"].eq(-1).astype(float).reindex(dates).fillna(0.0)
        guidance[up_col] = sub["label"].eq(1).astype(float).reindex(dates).fillna(0.0)
    return guidance


def build_panel(features: pd.DataFrame, targets: pd.DataFrame, weekly_returns: pd.DataFrame, strategy_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
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
    state = infer_market_state_by_date(features).reindex(dates).fillna("unknown")
    safe_mask = np.array([ticker in SAFE_ASSETS for ticker in tickers], dtype=bool)
    if not safe_mask.any():
        warn("No safe-asset ETF columns found for safe-exposure penalty.", warnings_list)
    state_caps = state.map({"calm_trend": 0.20, "recovery_confirmed": 0.20, "neutral_mixed": 0.40, "recovery_fragile": 0.40, "stressed_panic": 0.85}).fillna(0.50).to_numpy(dtype="float32")
    tb_guidance = load_triple_barrier_guidance(dates, warnings_list)
    benchmark_returns = strategy_returns.reindex(dates)
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
        "state": state,
        "safe_mask": safe_mask,
        "state_safe_caps": state_caps,
        "triple_barrier_guidance": tb_guidance,
        "benchmark_returns": benchmark_returns,
    }
    meta = {
        "feature_columns": feature_cols + ["availability_mask_known_at_t"],
        "n_base_feature_columns": len(feature_cols),
        "n_features": int(x.shape[-1]),
        "n_dates": int(x.shape[0]),
        "n_assets": int(x.shape[1]),
        "input_tensor_shape": list(x.shape),
        "universe": tickers,
        "safe_assets": [t for t in tickers if t in SAFE_ASSETS],
        "train_only_medians": medians.to_dict(),
        "train_only_stds": stds.to_dict(),
        "feature_missing_rates": missing_rates,
        "preprocessing": "Train-only median fill and train-only standardization. Availability mask appended as known-at-date feature.",
        "objective_design": "Benchmark-relative decision losses compare model portfolio returns against production or Phase 4B and add penalties for turnover, downside, safe-asset exposure in good states, and optional triple-barrier labels.",
    }
    return panel, meta


def date_indices_for_split(dates: pd.DatetimeIndex, split: str) -> np.ndarray:
    labels = split_for_dates(dates)
    return np.flatnonzero(labels.eq(split).to_numpy())


def make_model_class(torch: Any) -> Any:
    nn = torch.nn

    class AssetMLPScorer(nn.Module):
        def __init__(self, n_features: int, n_assets: int, config: BenchConfig):
            super().__init__()
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
    weights = torch.softmax(masked, dim=1) * available.float()
    denom = weights.sum(dim=1, keepdim=True).clamp_min(1.0e-8)
    return weights / denom


def torch_bce_loss(torch: Any, logits: Any, y: Any, mask: Any, pos_weight: Any) -> Any:
    import torch.nn.functional as F

    if mask.sum().item() == 0:
        return torch.tensor(0.0, device=logits.device)
    return F.binary_cross_entropy_with_logits(logits[mask], y[mask], pos_weight=pos_weight)


def torch_portfolio_terms(torch: Any, config: BenchConfig, logits: Any, tensors: dict[str, Any]) -> dict[str, Any]:
    weights = masked_softmax(torch, logits, tensors["return_mask"], config.temperature)
    returns_filled = torch.nan_to_num(tensors["next_returns"], nan=0.0)
    gross = (weights * returns_filled).sum(dim=1)
    turnover = torch.cat([torch.zeros(1, device=weights.device), torch.abs(weights[1:] - weights[:-1]).sum(dim=1)])
    cost = turnover * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    bench = torch.nan_to_num(tensors[f"benchmark_{config.benchmark_name}"], nan=0.0)
    excess = net - bench
    safe_weight = weights[:, tensors["safe_indices"]].sum(dim=1) if tensors["safe_indices"].numel() else torch.zeros_like(net)
    risky_weight = 1.0 - safe_weight
    cap_penalty = torch.relu(safe_weight - tensors["state_safe_caps"]).pow(2).mean()
    top3_weight = weights.topk(min(3, weights.shape[1]), dim=1).values.sum(dim=1).mean()
    downside_excess = torch.relu(-excess).pow(2).mean().sqrt()
    port_downside = torch.relu(-net).pow(2).mean().sqrt()
    bench_downside = torch.relu(-bench).pow(2).mean().sqrt()
    cvar_proxy = torch.relu(-(net - bench.quantile(0.05))).mean()
    tb_danger = tensors["tb_phase4b_danger"] if config.benchmark_name == "phase4b" else tensors["tb_prod_danger"]
    tb_up = tensors["tb_phase4b_up"] if config.benchmark_name == "phase4b" else tensors["tb_prod_up"]
    tb_penalty = (tb_danger * risky_weight).mean() + (tb_up * safe_weight).mean()
    return {
        "weights": weights,
        "net": net,
        "bench": bench,
        "excess": excess,
        "turnover": turnover,
        "safe_weight": safe_weight,
        "risky_weight": risky_weight,
        "cap_penalty": cap_penalty,
        "top3_weight": top3_weight,
        "downside_excess": downside_excess,
        "port_downside": port_downside,
        "bench_downside": bench_downside,
        "cvar_proxy": cvar_proxy,
        "tb_penalty": tb_penalty,
    }


def torch_loss(torch: Any, config: BenchConfig, logits: Any, tensors: dict[str, Any], pos_weight: Any) -> tuple[Any, dict[str, float]]:
    terms = torch_portfolio_terms(torch, config, logits, tensors)
    excess = terms["excess"]
    mean_excess = excess.mean()
    te = excess.std(unbiased=False).clamp_min(1.0e-6)
    info_ratio = mean_excess / te
    port_vol = terms["net"].std(unbiased=False).clamp_min(1.0e-6)
    avg_turnover = terms["turnover"].mean()
    bce = torch_bce_loss(torch, logits, tensors["y_top"], tensors["target_mask"], pos_weight)
    loss_kind = config.loss_kind
    if loss_kind == "relative_return":
        loss = -mean_excess + 0.10 * port_vol + 0.004 * avg_turnover + 0.80 * terms["cap_penalty"]
    elif loss_kind == "relative_info_ratio":
        loss = -info_ratio + 0.02 * avg_turnover + 1.00 * terms["cap_penalty"]
    elif loss_kind == "risk_constrained_relative":
        downside_gap = torch.relu(terms["port_downside"] - terms["bench_downside"])
        loss = -mean_excess + 0.80 * downside_gap + 0.80 * terms["downside_excess"] + 0.40 * terms["cvar_proxy"] + 0.004 * avg_turnover + 0.60 * terms["cap_penalty"]
    elif loss_kind == "offensive_exposure_constrained":
        loss = -mean_excess + 0.20 * port_vol + 0.004 * avg_turnover + 3.00 * terms["cap_penalty"]
    elif loss_kind == "triple_barrier_aware":
        loss = -mean_excess + 0.30 * terms["downside_excess"] + 0.004 * avg_turnover + 1.00 * terms["cap_penalty"] + 0.75 * terms["tb_penalty"]
    elif loss_kind == "hybrid_bce_relative":
        relative_loss = -mean_excess + 0.20 * port_vol + 0.004 * avg_turnover + 1.00 * terms["cap_penalty"] + 0.25 * terms["tb_penalty"]
        loss = 0.65 * bce + 0.35 * relative_loss
    else:
        raise ValueError(f"Unknown loss kind: {loss_kind}")
    stats = {
        "mean_excess_return": float(mean_excess.detach().cpu()),
        "tracking_error": float(te.detach().cpu()),
        "information_ratio_like": float(info_ratio.detach().cpu()),
        "portfolio_weekly_vol": float(port_vol.detach().cpu()),
        "average_turnover": float(avg_turnover.detach().cpu()),
        "average_safe_weight": float(terms["safe_weight"].mean().detach().cpu()),
        "average_risky_weight": float(terms["risky_weight"].mean().detach().cpu()),
        "safe_cap_penalty": float(terms["cap_penalty"].detach().cpu()),
        "triple_barrier_penalty": float(terms["tb_penalty"].detach().cpu()),
        "bce_loss": float(bce.detach().cpu()),
        "average_top3_weight": float(terms["top3_weight"].detach().cpu()),
    }
    return loss, stats


def tensors_for_indices(torch: Any, panel_tensors: dict[str, Any], idx: Any, benchmark_name: str) -> dict[str, Any]:
    out = {
        "next_returns": panel_tensors["next_returns"][idx],
        "return_mask": panel_tensors["return_mask"][idx],
        "y_top": panel_tensors["y_top"][idx],
        "target_mask": panel_tensors["target_mask"][idx],
        "safe_indices": panel_tensors["safe_indices"],
        "state_safe_caps": panel_tensors["state_safe_caps"][idx],
        "tb_prod_danger": panel_tensors["tb_prod_danger"][idx],
        "tb_prod_up": panel_tensors["tb_prod_up"][idx],
        "tb_phase4b_danger": panel_tensors["tb_phase4b_danger"][idx],
        "tb_phase4b_up": panel_tensors["tb_phase4b_up"][idx],
        f"benchmark_{benchmark_name}": panel_tensors[f"benchmark_{benchmark_name}"][idx],
    }
    return out


def evaluate_loss(torch: Any, model: Any, panel_tensors: dict[str, Any], indices: np.ndarray, config: BenchConfig, pos_weight: Any) -> tuple[float, dict[str, float]]:
    model.eval()
    with torch.no_grad():
        idx = torch.tensor(indices, dtype=torch.long, device=panel_tensors["x"].device)
        logits = model(panel_tensors["x"][idx])
        loss, stats = torch_loss(torch, config, logits, tensors_for_indices(torch, panel_tensors, idx, config.benchmark_name), pos_weight)
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


def train_model(torch: Any, panel: dict[str, Any], config: BenchConfig, device: str) -> tuple[np.ndarray, pd.DataFrame, dict[str, Any]]:
    set_seed(torch, config.seed)
    Model = make_model_class(torch)
    model = Model(panel["x"].shape[-1], panel["x"].shape[1], config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    safe_indices = np.flatnonzero(panel["safe_mask"]).astype(np.int64)
    bench = panel["benchmark_returns"].reindex(panel["dates"]).fillna(0.0)
    tb = panel["triple_barrier_guidance"].reindex(panel["dates"]).fillna(0.0)
    panel_tensors = {
        "x": torch.from_numpy(panel["x"]).to(device),
        "y_top": torch.from_numpy(np.nan_to_num(panel["y_top"], nan=0.0).astype("float32")).to(device),
        "target_mask": torch.from_numpy(panel["target_mask"].astype("bool")).to(device),
        "next_returns": torch.from_numpy(panel["next_returns"].to_numpy(dtype="float32")).to(device),
        "return_mask": torch.from_numpy(panel["return_mask"].astype("bool")).to(device),
        "safe_indices": torch.from_numpy(safe_indices).to(device),
        "state_safe_caps": torch.from_numpy(panel["state_safe_caps"]).to(device),
        "tb_prod_danger": torch.from_numpy(tb["tb_prod_danger"].to_numpy(dtype="float32")).to(device),
        "tb_prod_up": torch.from_numpy(tb["tb_prod_up"].to_numpy(dtype="float32")).to(device),
        "tb_phase4b_danger": torch.from_numpy(tb["tb_phase4b_danger"].to_numpy(dtype="float32")).to(device),
        "tb_phase4b_up": torch.from_numpy(tb["tb_phase4b_up"].to_numpy(dtype="float32")).to(device),
    }
    for name in ["production", "phase4b"]:
        if name not in bench.columns:
            raise ValueError(f"Required benchmark missing: {name}")
        panel_tensors[f"benchmark_{name}"] = torch.from_numpy(bench[name].to_numpy(dtype="float32")).to(device)
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
        loss, train_stats = torch_loss(torch, config, logits, tensors_for_indices(torch, panel_tensors, train_tensor_idx, config.benchmark_name), pos_weight)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        val_loss, val_stats = evaluate_loss(torch, model, panel_tensors, val_idx, config, pos_weight)
        row = {
            "model_name": config.model_name,
            "loss_kind": config.loss_kind,
            "benchmark_name": config.benchmark_name,
            "seed": config.seed,
            "epoch": epoch,
            "train_loss": float(loss.detach().cpu()),
            "validation_loss": val_loss,
        }
        for prefix, stats in [("train", train_stats), ("validation", val_stats)]:
            for key, value in stats.items():
                row[f"{prefix}_{key}"] = value
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
        "benchmark_name": config.benchmark_name,
        "seed": config.seed,
        "best_epoch": best_epoch,
        "best_validation_loss": best_val,
        "architecture": {
            "model": "per-ETF MLP scorer with learned ETF embedding",
            "input_projection": f"Linear({panel['x'].shape[-1]} -> {config.hidden_dim})",
            "hidden_dim": config.hidden_dim,
            "dropout": config.dropout,
            "output": "one score per ETF per date",
            "allocation_training": "masked softmax long-only ETF portfolio",
            "temperature": config.temperature,
        },
    }
    return scores, pd.DataFrame(rows), info


def predictions_from_scores(panel: dict[str, Any], scores: np.ndarray, config: BenchConfig) -> pd.DataFrame:
    rows = []
    splits = split_for_dates(panel["dates"])
    for i, date in enumerate(panel["dates"]):
        for j, ticker in enumerate(panel["tickers"]):
            rows.append(
                {
                    "Date": date,
                    "ticker": ticker,
                    "split": splits.loc[date],
                    "model_name": config.model_name,
                    "loss_kind": config.loss_kind,
                    "benchmark_name": config.benchmark_name,
                    "seed": config.seed,
                    "score": float(scores[i, j]) if np.isfinite(scores[i, j]) else np.nan,
                    "actual_target": float(panel["y_top"][i, j]) if np.isfinite(panel["y_top"][i, j]) else np.nan,
                    "actual_rank": float(panel["y_rank"][i, j]) if np.isfinite(panel["y_rank"][i, j]) else np.nan,
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


def softmax_weights_from_scores(score_table: pd.DataFrame, dates: pd.DatetimeIndex, tickers: list[str], next_returns: pd.DataFrame, temperature: float) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    hit_rate = pd.Series(np.nan, index=dates)
    available_mask = next_returns.reindex(index=dates, columns=tickers).notna()
    available_sets = {date: set(available_mask.columns[available_mask.loc[date].to_numpy()]) for date in dates}
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        eligible = group[["ticker", "score", "actual_target"]].dropna(subset=["score"])
        eligible = eligible[eligible["ticker"].isin(available_sets.get(date, set()))]
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


def topn_weights_from_scores(score_table: pd.DataFrame, dates: pd.DatetimeIndex, tickers: list[str], top_n: int, weighting: str, next_returns: pd.DataFrame, vol_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    hit_rate = pd.Series(np.nan, index=dates)
    available_mask = next_returns.reindex(index=dates, columns=tickers).notna()
    available_sets = {date: set(available_mask.columns[available_mask.loc[date].to_numpy()]) for date in dates}
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        eligible = group[["ticker", "score", "actual_target"]].dropna(subset=["score"])
        eligible = eligible[eligible["ticker"].isin(available_sets.get(date, set()))]
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


def overlay_weights(wrapper: str, raw_weights: pd.DataFrame, state: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "bil_fallback_original":
        exposure = state.reindex(dates).map({"stressed_panic": 0.25, "neutral_mixed": 0.75}).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "regime_gate_original":
        exposure = state.reindex(dates).map({"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}).fillna(0.70)
        return add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"unknown wrapper {wrapper}")


def safe_weight_frame(weights: pd.DataFrame) -> pd.Series:
    cols = [c for c in weights.columns if c in SAFE_ASSETS]
    return weights.reindex(columns=cols).sum(axis=1) if cols else pd.Series(0.0, index=weights.index)


def compute_model_path(weights: pd.DataFrame, next_returns: pd.DataFrame, exposure: pd.Series, hit_rate: pd.Series, benchmark: pd.Series, benchmark_name: str) -> pd.DataFrame:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    bil_weight = weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index)
    safe_weight = safe_weight_frame(weights)
    return pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": bil_weight,
            "safe_weight": safe_weight,
            "risky_exposure": 1.0 - safe_weight,
            "model_exposure": exposure.reindex(weights.index).fillna(1.0),
            "benchmark_return": benchmark.reindex(weights.index),
            "benchmark_name": benchmark_name,
            "holdings_count": weights.gt(0.001).sum(axis=1),
            "top_quintile_hit_rate": hit_rate.reindex(weights.index),
            "top3_weight": weights.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1),
        },
        index=weights.index,
    )


def compute_core_sleeve_path(core_name: str, sleeve_weights: pd.DataFrame, next_returns: pd.DataFrame, state: pd.Series, hit_rate: pd.Series, strategy_returns: pd.DataFrame, benchmark: pd.Series, benchmark_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sleeve_weights.index
    risk_off = state.reindex(dates).isin(["stressed_panic"]).fillna(False)
    sleeve_exposure = pd.Series(0.10, index=dates)
    sleeve_exposure.loc[risk_off] = 0.0
    sleeve_gross = sleeve_weights.mul(next_returns.reindex(index=dates, columns=sleeve_weights.columns).fillna(0.0)).sum(axis=1)
    core = strategy_returns.reindex(dates)[core_name].fillna(0.0)
    bil = strategy_returns.reindex(dates)["BIL"].fillna(0.0) if "BIL" in strategy_returns.columns else pd.Series(0.0, index=dates)
    gross = (0.90 * core) + (sleeve_exposure * sleeve_gross) + ((0.10 - sleeve_exposure) * bil)
    effective_weights = sleeve_weights.mul(sleeve_exposure, axis=0)
    turnover = effective_weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover * (DEFAULT_COST_BPS / 10000.0)
    path = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": gross - cost,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": (0.10 - sleeve_exposure) + (effective_weights["BIL"] if "BIL" in effective_weights.columns else 0.0),
            "safe_weight": safe_weight_frame(effective_weights) + (0.10 - sleeve_exposure),
            "risky_exposure": sleeve_exposure,
            "model_exposure": sleeve_exposure,
            "benchmark_return": benchmark.reindex(dates),
            "benchmark_name": benchmark_name,
            "holdings_count": effective_weights.gt(0.001).sum(axis=1) + 1,
            "top_quintile_hit_rate": hit_rate.reindex(dates),
            "top3_weight": effective_weights.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1),
            "core_name": core_name,
            "core_exposure": 0.90,
        },
        index=dates,
    )
    audit_weights = effective_weights.copy()
    audit_weights[f"CORE_{core_name}"] = 0.90
    if "BIL" in audit_weights.columns:
        audit_weights["BIL"] = audit_weights["BIL"] + (0.10 - sleeve_exposure)
    return path, audit_weights


def max_drawdown(returns: pd.Series) -> float:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {"annual_return": np.nan, "annual_volatility": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "calmar": np.nan, "cvar_5": np.nan, "average_turnover": np.nan, "annual_cost_drag": np.nan, "average_bil_exposure": np.nan, "average_safe_exposure": np.nan, "average_risky_exposure": np.nan, "average_benchmark_excess_return": np.nan, "tracking_error": np.nan, "information_ratio": np.nan, "average_top3_weight": np.nan, "active_weeks": 0}
    wealth = (1.0 + r).cumprod()
    ann_ret = float(wealth.iloc[-1] ** (52.0 / len(r)) - 1.0) if wealth.iloc[-1] > 0 else np.nan
    ann_vol = float(r.std(ddof=0) * math.sqrt(52.0))
    mdd = max_drawdown(r)
    q5 = r.quantile(0.05)
    bench = pd.to_numeric(path.get("benchmark_return", pd.Series(dtype=float)), errors="coerce").reindex(r.index)
    excess = (r - bench).dropna()
    te = float(excess.std(ddof=0) * math.sqrt(52.0)) if not excess.empty else np.nan
    ann_excess = float(excess.mean() * 52.0) if not excess.empty else np.nan
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
        "average_safe_exposure": float(path.get("safe_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_risky_exposure": float(path.get("risky_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_benchmark_excess_return": ann_excess,
        "tracking_error": te,
        "information_ratio": float(ann_excess / te) if pd.notna(te) and te > 0 else np.nan,
        "average_top3_weight": float(path.get("top3_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def append_backtest(returns_frames: list[pd.DataFrame], weights_frames: list[pd.DataFrame], summary_rows: list[dict[str, Any]], path: pd.DataFrame, weights: pd.DataFrame, model_name: str, loss_kind: str, benchmark_name: str, seed: int, allocation_method: str, wrapper: str, rank_ic_by_split: dict[str, float]) -> None:
    strategy_name = f"{model_name}__{allocation_method}__{wrapper}"
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    dated["model_name"] = model_name
    dated["loss_kind"] = loss_kind
    dated["objective_benchmark"] = benchmark_name
    dated["seed"] = seed
    dated["allocation_method"] = allocation_method
    dated["wrapper"] = wrapper
    dated["cost_bps"] = DEFAULT_COST_BPS
    returns_frames.append(dated.reset_index(drop=True))
    for split in ("train", "validation", "holdout"):
        metrics = calc_metrics(dated[dated["split"].eq(split)])
        metrics.update({"strategy_name": strategy_name, "model_name": model_name, "loss_kind": loss_kind, "objective_benchmark": benchmark_name, "seed": seed, "allocation_method": allocation_method, "wrapper": wrapper, "split": split, "cost_bps": DEFAULT_COST_BPS, "rank_ic": rank_ic_by_split.get(split, np.nan)})
        summary_rows.append(metrics)
    w = weights.copy()
    w["Date"] = w.index
    long = w.reset_index(drop=True).melt(id_vars="Date", var_name="ticker", value_name="weight")
    long = long[long["weight"].abs() > 1e-6].copy()
    long["strategy_name"] = strategy_name
    long["model_name"] = model_name
    long["loss_kind"] = loss_kind
    long["objective_benchmark"] = benchmark_name
    long["seed"] = seed
    long["allocation_method"] = allocation_method
    long["wrapper"] = wrapper
    long["split"] = split_for_dates(long["Date"]).values
    weights_frames.append(long)


def run_backtests(panel: dict[str, Any], predictions: pd.DataFrame, strategy_returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = panel["dates"]
    tickers = panel["tickers"]
    next_returns = panel["next_returns"]
    vol_panel = panel["vol_panel"]
    state = panel["state"]
    summary_rows: list[dict[str, Any]] = []
    returns_frames: list[pd.DataFrame] = []
    weights_frames: list[pd.DataFrame] = []
    split_indices = {split: date_indices_for_split(dates, split) for split in ("train", "validation", "holdout")}
    for (model_name, loss_kind, benchmark_name, seed), group in predictions.groupby(["model_name", "loss_kind", "benchmark_name", "seed"], sort=True):
        score_matrix = group.pivot(index="Date", columns="ticker", values="score").reindex(index=dates, columns=tickers).to_numpy(dtype="float32")
        rank_ic_by_split = {split: rank_ic_for_dates(score_matrix, panel["y_rank"], panel["target_mask"], idxs) for split, idxs in split_indices.items()}
        allocation_specs = [("softmax_all", None, None)]
        for top_n in (10, 15):
            for weighting in ("inverse_vol", "equal_weight"):
                allocation_specs.append((f"top{top_n}_{weighting}", top_n, weighting))
        benchmark = panel["benchmark_returns"].reindex(dates)[benchmark_name].fillna(0.0)
        for allocation_method, top_n, weighting in allocation_specs:
            if allocation_method == "softmax_all":
                raw_weights, hit_rate = softmax_weights_from_scores(group, dates, tickers, next_returns, SOFTMAX_TEMPERATURE)
            else:
                raw_weights, hit_rate = topn_weights_from_scores(group, dates, tickers, int(top_n), str(weighting), next_returns, vol_panel)
            for wrapper in ("raw_ml", "bil_fallback_original", "regime_gate_original"):
                weights, exposure = overlay_weights(wrapper, raw_weights, state)
                path = compute_model_path(weights, next_returns, exposure, hit_rate, benchmark, benchmark_name)
                append_backtest(returns_frames, weights_frames, summary_rows, path, weights, str(model_name), str(loss_kind), str(benchmark_name), int(seed), allocation_method, wrapper, rank_ic_by_split)
            for core_name in ("production", "phase4b"):
                if core_name in strategy_returns.columns:
                    path, audit_weights = compute_core_sleeve_path(core_name, raw_weights, next_returns, state, hit_rate, strategy_returns, benchmark, benchmark_name)
                    append_backtest(returns_frames, weights_frames, summary_rows, path, audit_weights, str(model_name), str(loss_kind), str(benchmark_name), int(seed), allocation_method, f"{core_name}_core_plus_10pct_model_sleeve", rank_ic_by_split)
    returns_df = pd.concat(returns_frames, ignore_index=True) if returns_frames else pd.DataFrame()
    weights_df = pd.concat(weights_frames, ignore_index=True) if weights_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return returns_df, weights_df, summary


def comparison_table(summary: pd.DataFrame, strategy_returns: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    rows = []
    rows.extend(summary[summary["split"].eq("holdout")].assign(category="benchmark_relative_model").to_dict(orient="records"))
    for name in ["production", "official_shadow", "phase4b", "phase6", "phase7", "mlx5_sequence", "mlx6_transformer", "mlx9_ensemble", "mlx12_decision_focused", "mlx13_validation_filter", "mlx13_holdout_diagnostic", "SPY", "60_40", "simple_momentum"]:
        if name not in strategy_returns.columns:
            continue
        frame = pd.DataFrame({"net_return": strategy_returns[name], "gross_return": strategy_returns[name], "turnover": np.nan, "cost": 0.0, "bil_weight": 0.0, "safe_weight": 0.0, "risky_exposure": 1.0, "benchmark_return": strategy_returns["production"] if "production" in strategy_returns.columns else 0.0})
        frame["split"] = split_for_dates(frame.index).values
        metrics = calc_metrics(frame[frame["split"].eq("holdout")])
        metrics.update({"strategy_name": name, "category": "benchmark", "split": "holdout", "objective_benchmark": "production"})
        rows.append(metrics)
    if SEQUENCE_5C_SUMMARY_IN.exists():
        try:
            data = json.loads(SEQUENCE_5C_SUMMARY_IN.read_text())
            rows.append({"strategy_name": "mlx5c_bil_fallback_mean_summary", "category": "benchmark_summary_only", "split": "holdout", "annual_return": np.nan, "annual_volatility": np.nan, "sharpe": data.get("overall_mean_sharpe", np.nan), "max_drawdown": data.get("overall_worst_case_max_drawdown", np.nan), "cvar_5": data.get("overall_worst_case_cvar_5", np.nan)})
        except Exception as exc:
            warn(f"Could not load MLX-5C summary comparison: {exc}", warnings_list)
    return pd.DataFrame(rows).sort_values(["sharpe", "annual_return"], ascending=[False, False]).reset_index(drop=True)


def state_by_state(returns: pd.DataFrame, state: pd.Series, focus: list[str]) -> pd.DataFrame:
    rows = []
    hold = returns[returns["split"].eq("holdout") & returns["strategy_name"].isin(focus)].copy()
    hold["market_state"] = hold["Date"].map(state)
    for (strategy, mstate), group in hold.groupby(["strategy_name", "market_state"], dropna=False):
        metrics = calc_metrics(group.set_index("Date"))
        metrics.update({"strategy_name": strategy, "market_state": mstate, "weeks": int(len(group))})
        rows.append(metrics)
    return pd.DataFrame(rows)


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


def exposure_audit(weights: pd.DataFrame, universe_meta: pd.DataFrame, focus: list[str]) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame()
    category = {}
    if not universe_meta.empty and {"ticker", "category"}.issubset(universe_meta.columns):
        category = universe_meta.drop_duplicates("ticker").set_index("ticker")["category"].to_dict()
    rows = []
    hold = weights[weights["split"].eq("holdout") & weights["strategy_name"].isin(focus)].copy()
    for strategy, group in hold.groupby("strategy_name"):
        pivot = group.pivot_table(index="Date", columns="ticker", values="weight", aggfunc="sum").fillna(0.0)
        avg = pivot.mean().sort_values(ascending=False)
        for ticker, value in avg.items():
            rows.append({"strategy_name": strategy, "audit_type": "ticker", "item": ticker, "category": category.get(ticker, "synthetic_core" if ticker.startswith("CORE_") else "unknown"), "average_weight": float(value), "max_weight": float(pivot[ticker].max()), "holding_frequency": float((pivot[ticker] > 0.01).mean())})
        for cat in sorted(set(category.get(t, "synthetic_core" if t.startswith("CORE_") else "unknown") for t in pivot.columns)):
            cols = [t for t in pivot.columns if category.get(t, "synthetic_core" if t.startswith("CORE_") else "unknown") == cat]
            series = pivot[cols].sum(axis=1)
            rows.append({"strategy_name": strategy, "audit_type": "category", "item": cat, "category": cat, "average_weight": float(series.mean()), "max_weight": float(series.max()), "holding_frequency": float((series > 0.01).mean())})
        summaries = {
            "average_top3_weight": pivot.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1),
            "average_SPY_QQQ_SMH_weight": pivot.reindex(columns=[c for c in ["SPY", "QQQ", "SMH"] if c in pivot.columns]).sum(axis=1),
            "average_BIL_weight": pivot["BIL"] if "BIL" in pivot.columns else pd.Series(0.0, index=pivot.index),
            "average_safe_asset_weight": pivot.reindex(columns=[c for c in pivot.columns if c in SAFE_ASSETS]).sum(axis=1),
            "average_sector_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "US sectors"]).sum(axis=1),
            "average_commodities_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "Commodities"]).sum(axis=1),
        }
        for label, series in summaries.items():
            rows.append({"strategy_name": strategy, "audit_type": "summary", "item": label, "category": "", "average_weight": float(series.mean()), "max_weight": float(series.max()), "holding_frequency": np.nan})
    return pd.DataFrame(rows).sort_values(["strategy_name", "audit_type", "average_weight"], ascending=[True, True, False])


def best_row(summary: pd.DataFrame, split: str) -> dict[str, Any]:
    sub = summary[(summary["split"].eq(split)) & (summary["active_weeks"].ge(50))].copy()
    if sub.empty:
        return {}
    return sub.sort_values(["information_ratio", "sharpe", "max_drawdown", "annual_return"], ascending=[False, False, False, False]).iloc[0].to_dict()


def comp_value(comparison: pd.DataFrame, strategy: str, metric: str) -> float:
    sub = comparison[comparison["strategy_name"].eq(strategy)]
    if sub.empty or metric not in sub.columns:
        return np.nan
    value = sub.iloc[0][metric]
    return float(value) if pd.notna(value) else np.nan


def choose_recommendation(selected: dict[str, Any], comparison: pd.DataFrame) -> str:
    if not selected:
        return "REJECT"
    ir = float(selected.get("information_ratio", np.nan))
    ann_ret = float(selected.get("annual_return", np.nan))
    safe = float(selected.get("average_safe_exposure", np.nan))
    phase4b = comp_value(comparison, "phase4b", "sharpe")
    sharpe = float(selected.get("sharpe", np.nan))
    if pd.notna(safe) and safe > 0.55:
        return "PROMISING LEARNING RESULT BUT NOT PORTFOLIO CANDIDATE"
    if pd.notna(ir) and ir > 0 and pd.notna(sharpe) and pd.notna(phase4b) and sharpe > phase4b and pd.notna(ann_ret) and ann_ret > 0.08:
        return "PROMISING OPTIMIZATION DIRECTION BUT NEEDS STRICTER WALK-FORWARD"
    if pd.notna(ir) and ir > 0:
        return "KEEP AS RESEARCH ONLY"
    return "REJECT"


def write_notes(torch_meta: dict[str, Any], preprocess_meta: dict[str, Any], model_infos: list[dict[str, Any]], skipped: list[dict[str, Any]], candidate_defs: dict[str, Any], summary: pd.DataFrame, comparison: pd.DataFrame, state: pd.DataFrame, exposure: pd.DataFrame, walk: pd.DataFrame, summary_json: dict[str, Any], warnings_list: list[str]) -> None:
    best_val = summary_json.get("best_validation_model", {})
    selected = summary_json.get("validation_selected_holdout", {})
    best_hold = summary_json.get("best_holdout_diagnostic_model", {})
    arch = model_infos[0].get("architecture", {}) if model_infos else {}
    notes = f"""# Phase MLX-12B Benchmark-Relative Decision-Focused Learning Notes

## Research-Only Warning

Phase MLX-12B is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Benchmark-relative decision-focused learning trains the model on the quality of the portfolio decision relative to a benchmark such as production or Phase 4B. MLX-12 optimized an absolute Sharpe-like objective and found a low-volatility solution by hiding in BIL/bonds. MLX-12B asks a different question: can the model add incremental value over an existing strategy while keeping risk controlled?

Optimizing excess return versus production or Phase 4B is different from optimizing raw return or raw Sharpe. A portfolio that earns 2% with tiny volatility can have a high Sharpe, but it is not useful if production earns much more with acceptable risk. Relative objectives care about active return, tracking error, and information ratio.

Constraints on BIL and offensive exposure matter because otherwise a risk-aware model can choose the easiest feasible point: cash or bonds. This sprint penalizes excess safe-asset exposure in good states while still allowing BIL in stressed regimes. Tracking error measures the volatility of returns versus the benchmark. Information ratio is annualized excess return divided by tracking error.

Triple-barrier labels from MLX-13 help define path-aware penalties: danger labels penalize taking risk when bad paths historically occurred, while positive barrier labels discourage hiding in safe assets when good paths were available. This is still risky and can overfit because the labels are estimated from historical paths.

## EECS 127 / Optimization Connection

This sprint is an optimization-design exercise. The model has an objective function, a feasible set, and penalty terms. The feasible set is long-only ETF weights from a softmax allocation. The objective rewards benchmark-relative performance. The penalties represent Lagrangian-style tradeoffs: turnover, downside risk, BIL/safe-asset exposure, and triple-barrier path risk.

MLX-12 showed that the wrong objective gives the wrong optimum: absolute Sharpe made BIL/bonds look optimal. MLX-12B changes the objective and constraints, so the optimum is forced to answer a more useful question: can the model improve on a benchmark without simply becoming cash?

## Technical Setup

- Torch availability: {torch_meta}
- Universe size: {preprocess_meta.get('n_assets')}
- Input tensor shape: `{preprocess_meta.get('input_tensor_shape')}`
- Architecture: {arch}
- Objectives tested: {summary_json.get('objectives_run')}
- Benchmarks tested: {summary_json.get('benchmarks_run')}
- Candidate definitions: {candidate_defs}
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill and train-only standardization
- Leakage controls: model inputs exclude target-like columns; MLX-13 labels are used only in losses/penalties, not as input features
- Skipped variants: {skipped}

## Results

- Best validation-selected model: `{best_val.get('strategy_name', 'n/a')}` with validation information ratio {num(best_val.get('information_ratio'))}
- Validation-selected holdout annual return: {pct(selected.get('annual_return'))}
- Validation-selected holdout Sharpe: {num(selected.get('sharpe'))}
- Validation-selected holdout max drawdown: {pct(selected.get('max_drawdown'))}
- Validation-selected holdout CVaR 5%: {pct(selected.get('cvar_5'))}
- Validation-selected information ratio: {num(selected.get('information_ratio'))}
- Best holdout-diagnostic model: `{best_hold.get('strategy_name', 'n/a')}` with holdout information ratio {num(best_hold.get('information_ratio'))}

### Top Holdout Strategies

{markdown_table(summary[summary['split'].eq('holdout')].sort_values(['information_ratio', 'sharpe'], ascending=[False, False]), ['strategy_name', 'loss_kind', 'objective_benchmark', 'allocation_method', 'wrapper', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_benchmark_excess_return', 'tracking_error', 'information_ratio', 'average_safe_exposure', 'average_bil_exposure', 'average_top3_weight'], 25)}

### Strategy Comparison

{markdown_table(comparison, ['strategy_name', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_benchmark_excess_return', 'tracking_error', 'information_ratio', 'average_safe_exposure'], 30)}

### State-By-State Results

{markdown_table(state, ['strategy_name', 'market_state', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_benchmark_excess_return', 'information_ratio', 'average_bil_exposure', 'average_risky_exposure', 'weeks'], 40)}

### Walk-Forward Window Results

{markdown_table(walk, ['strategy_name', 'window', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_benchmark_excess_return', 'information_ratio', 'active_weeks'], 40)}

### Exposure Audit

{markdown_table(exposure, ['strategy_name', 'audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], 50)}

## Interpretation

- Did benchmark-relative training prevent BIL/bond collapse? {summary_json.get('bil_bond_collapse_fixed')}
- Did the validation-selected model beat original MLX-12 by annual return? {summary_json.get('validation_selected_beats_mlx12_annual_return')}
- Did it beat production by Sharpe? {summary_json.get('validation_selected_beats_production_sharpe')}
- Did it beat Phase 4B by Sharpe? {summary_json.get('validation_selected_beats_phase4b_sharpe')}
- Did it beat MLX-9 by Sharpe? {summary_json.get('validation_selected_beats_mlx9_sharpe')}
- Final recommendation: **{summary_json.get('final_recommendation')}**

The key educational result is whether changing the objective and constraints changes the learned solution. A positive result does not imply production readiness; it means the problem formulation is more useful than absolute Sharpe.

## Warnings

{chr(10).join(f'- {w}' for w in warnings_list)}
"""
    NOTES_OUT.write_text(notes)


def write_skipped_outputs(reason: str, torch_meta: dict[str, Any], warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    empty = pd.DataFrame()
    empty.to_parquet(PREDICTIONS_OUT, index=False)
    empty.to_parquet(WEIGHTS_OUT, index=False)
    for path in [RETURNS_OUT, SUMMARY_OUT, TRAINING_CURVES_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, EXPOSURE_AUDIT_OUT, WALKFORWARD_OUT]:
        empty.to_csv(path, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps({"research_only": True, "production_valid": False, "reason": reason}, indent=2))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps({}, indent=2))
    SKIPPED_RUNS_OUT.write_text(json.dumps([{"component": "torch_training", "reason": reason}], indent=2))
    SUMMARY_JSON_OUT.write_text(json.dumps({"phase": "benchmark_relative_decision_focused_learning", "research_only": True, "production_valid": False, "torch": torch_meta, "reason": reason, "warnings": warnings_list}, indent=2, default=json_default))
    NOTES_OUT.write_text(f"""# Phase MLX-12B Benchmark-Relative Decision-Focused Learning Notes

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

Benchmark-relative decision-focused learning was skipped because `{reason}`.

## EECS 127 / Optimization Connection

The sprint would compare objective functions, constraints, and penalty terms.
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    warn("Experimental research-only Phase MLX output; not production-valid.", warnings_list)
    warn("Benchmark-relative objectives still use yfinance/expanded ETF research data and remain high overfitting risk.", warnings_list)
    torch_meta = torch_status()
    if not torch_meta.get("available"):
        reason = "torch is missing or failed to import"
        warn(reason, warnings_list)
        write_skipped_outputs(reason, torch_meta, warnings_list)
        print("Phase MLX-12B skipped: torch unavailable.")
        return
    import torch

    device = "cpu"
    features, targets, weekly_returns, universe_meta = load_inputs(warnings_list)
    strategy_returns, strategy_sources = load_strategy_returns(weekly_returns, warnings_list)
    required = [b for b in ("production", "phase4b") if b not in strategy_returns.columns]
    if required:
        raise RuntimeError(f"Required benchmark returns missing for MLX-12B: {required}")
    panel, preprocess_meta = build_panel(features, targets, weekly_returns, strategy_returns, warnings_list)
    skipped = [
        {"variant": "absolute_sharpe_objective", "reason": "intentionally excluded to avoid MLX-12 BIL/bond collapse"},
        {"variant": "seed_2", "reason": "skipped to keep first benchmark-relative run bounded on CPU"},
        {"variant": "differentiable_top_k", "reason": "deferred; first version uses masked softmax training and top-N evaluation"},
        {"variant": "full_walk_forward_retraining", "reason": "deferred; selected predictions are evaluated by window without retraining per fold"},
        {"variant": "cvxpylayers_mean_variance_layer", "reason": "deferred; no optional optimizer-layer dependency added"},
    ]
    objectives = ["relative_return", "relative_info_ratio", "risk_constrained_relative", "offensive_exposure_constrained", "triple_barrier_aware", "hybrid_bce_relative"]
    benchmarks = ["production", "phase4b"]
    seed1_objectives = {"relative_return", "risk_constrained_relative", "hybrid_bce_relative"}
    configs: list[BenchConfig] = []
    for objective in objectives:
        seed_grid = SEEDS if objective in seed1_objectives else (0,)
        if 1 not in seed_grid:
            skipped.append({"variant": f"{objective}_seed1", "reason": "skipped after an initial full-grid attempt proved too slow for a bounded CPU first version"})
        for benchmark in benchmarks:
            for seed in seed_grid:
                configs.append(BenchConfig(model_name=f"{objective}_{benchmark}_seed{seed}", loss_kind=objective, benchmark_name=benchmark, seed=seed))
    candidate_defs = {
        "relative_return": "Maximize portfolio return above benchmark with turnover, volatility, and safe-exposure penalties.",
        "relative_info_ratio": "Maximize mean excess return divided by tracking error with penalties.",
        "risk_constrained_relative": "Reward excess return while penalizing downside worse than the benchmark, CVaR proxy, turnover, and safe exposure.",
        "offensive_exposure_constrained": "Strongly penalize hiding in safe assets in good states.",
        "triple_barrier_aware": "Use MLX-13 path-aware labels as penalties: avoid risky exposure on danger labels and avoid safe hiding on positive labels.",
        "hybrid_bce_relative": "Combine top-quintile BCE with benchmark-relative decision loss.",
        "benchmarks": benchmarks,
        "wrappers": ["raw_ml", "bil_fallback_original", "regime_gate_original", "production_core_plus_10pct_model_sleeve", "phase4b_core_plus_10pct_model_sleeve"],
    }
    all_predictions: list[pd.DataFrame] = []
    all_curves: list[pd.DataFrame] = []
    model_infos: list[dict[str, Any]] = []
    for i, config in enumerate(configs, start=1):
        print(f"Running benchmark-relative model {i}/{len(configs)}: {config.model_name}", flush=True)
        scores, curves, info = train_model(torch, panel, config, device)
        all_curves.append(curves)
        model_infos.append(info)
        all_predictions.append(predictions_from_scores(panel, scores, config))
    predictions = pd.concat(all_predictions, ignore_index=True)
    training_curves = pd.concat(all_curves, ignore_index=True)
    returns_df, weights_df, summary = run_backtests(panel, predictions, strategy_returns)
    comparison = comparison_table(summary, strategy_returns, warnings_list)
    best_val = best_row(summary, "validation")
    selected_holdout = {}
    if best_val:
        sub = summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq(best_val["strategy_name"]))]
        selected_holdout = sub.iloc[0].to_dict() if not sub.empty else {}
    best_holdout = best_row(summary, "holdout")
    focus = sorted(set([best_val.get("strategy_name"), best_holdout.get("strategy_name")]) - {None, ""})
    state = state_by_state(returns_df, panel["state"], focus)
    exposure = exposure_audit(weights_df, universe_meta, focus)
    walk = walkforward_summary(returns_df, focus)
    selected_sharpe = selected_holdout.get("sharpe", np.nan)
    selected_return = selected_holdout.get("annual_return", np.nan)
    selected_safe = selected_holdout.get("average_safe_exposure", np.nan)
    summary_json = {
        "phase": "benchmark_relative_decision_focused_learning",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "torch": torch_meta,
        "device": device,
        "models_run": [c.model_name for c in configs],
        "objectives_run": objectives,
        "benchmarks_run": benchmarks,
        "seeds_run": list(SEEDS),
        "universe_size": preprocess_meta["n_assets"],
        "input_tensor_shape": preprocess_meta["input_tensor_shape"],
        "model_architecture": model_infos[0].get("architecture", {}) if model_infos else {},
        "strategy_sources": strategy_sources,
        "candidate_definitions": candidate_defs,
        "skipped_runs": skipped,
        "best_validation_model": best_val,
        "validation_selected_holdout": selected_holdout,
        "best_holdout_diagnostic_model": best_holdout,
        "validation_selected_beats_mlx12_annual_return": bool(pd.notna(selected_return) and pd.notna(comp_value(comparison, "mlx12_decision_focused", "annual_return")) and selected_return > comp_value(comparison, "mlx12_decision_focused", "annual_return")),
        "validation_selected_beats_mlx12_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx12_decision_focused", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx12_decision_focused", "sharpe")),
        "validation_selected_beats_mlx13_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx13_validation_filter", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx13_validation_filter", "sharpe")),
        "validation_selected_beats_production_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "production", "sharpe")) and selected_sharpe > comp_value(comparison, "production", "sharpe")),
        "validation_selected_beats_phase4b_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "phase4b", "sharpe")) and selected_sharpe > comp_value(comparison, "phase4b", "sharpe")),
        "validation_selected_beats_mlx9_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(comp_value(comparison, "mlx9_ensemble", "sharpe")) and selected_sharpe > comp_value(comparison, "mlx9_ensemble", "sharpe")),
        "bil_bond_collapse_fixed": bool(pd.notna(selected_safe) and selected_safe < 0.45),
        "final_recommendation": choose_recommendation(selected_holdout, comparison),
        "warnings": warnings_list + ["No benchmark-relative decision-focused model is promoted automatically."],
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
            "walkforward": str(WALKFORWARD_OUT.relative_to(ROOT)),
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
    walk.to_csv(WALKFORWARD_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(preprocess_meta, indent=2, default=json_default))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps(candidate_defs, indent=2, default=json_default))
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(torch_meta, preprocess_meta, model_infos, skipped, candidate_defs, summary, comparison, state, exposure, walk, summary_json, summary_json["warnings"])
    print("Phase MLX-12B benchmark-relative decision-focused learning")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Torch: {torch_meta}")
    print(f"Device used: {device}")
    print(f"Universe size: {preprocess_meta['n_assets']}")
    print(f"Objectives run: {objectives}")
    print(f"Benchmarks run: {benchmarks}")
    print(f"Best validation model: {best_val.get('strategy_name') if best_val else 'n/a'}")
    print(f"Validation-selected holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Validation-selected holdout information ratio: {selected_holdout.get('information_ratio') if selected_holdout else np.nan}")
    print(f"Best holdout diagnostic model: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Best holdout diagnostic Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Final recommendation: {summary_json['final_recommendation']}")
    print("Outputs:")
    for path in [PREDICTIONS_OUT, WEIGHTS_OUT, RETURNS_OUT, SUMMARY_OUT, TRAINING_CURVES_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, EXPOSURE_AUDIT_OUT, WALKFORWARD_OUT, PREPROCESSING_METADATA_OUT, CANDIDATE_DEFINITIONS_OUT, SKIPPED_RUNS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
