#!/usr/bin/env python3
"""
Phase MLX-14: date-grouped learning-to-rank ETF selector.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
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
OUTPUT_DIR = ML_DIR / "learning_to_rank"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"

TABULAR_DIR = ML_DIR / "tabular_ml"
NN_DIR = ML_DIR / "neural_networks"
SEQUENCE_DIR = ML_DIR / "sequence_models"
SEQUENCE_5C_DIR = SEQUENCE_DIR / "multiseed_walkforward"
TRANSFORMER_DIR = ML_DIR / "transformers"
ENSEMBLE_DIR = ML_DIR / "ensembles"
CROSS_ASSET_DIR = ML_DIR / "cross_asset_attention"
DECISION_DIR = ML_DIR / "decision_focused"
BENCH_REL_DIR = ML_DIR / "decision_focused_benchmark_relative"
TRIPLE_DIR = ML_DIR / "triple_barrier_meta"

PREDICTIONS_OUT = OUTPUT_DIR / "learning_to_rank_predictions.parquet"
RETURNS_OUT = OUTPUT_DIR / "learning_to_rank_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "learning_to_rank_summary.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "learning_to_rank_strategy_comparison.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "learning_to_rank_state_by_state.csv"
WALKFORWARD_OUT = OUTPUT_DIR / "learning_to_rank_walkforward_summary.csv"
FEATURE_IMPORTANCE_OUT = OUTPUT_DIR / "learning_to_rank_feature_importance.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "learning_to_rank_exposure_audit.csv"
PREPROCESSING_METADATA_OUT = OUTPUT_DIR / "learning_to_rank_preprocessing_metadata.json"
CANDIDATE_DEFINITIONS_OUT = OUTPUT_DIR / "learning_to_rank_candidate_definitions.json"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "learning_to_rank_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "learning_to_rank_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_learning_to_rank_etf_selector_notes.md"

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
SAFE_ASSETS = {"BIL", "SHV", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD", "MUB", "STIP", "VGSH", "VGIT"}
DEFAULT_COST_BPS = 10.0


def load_helper() -> Any:
    helper_path = ROOT / "scripts" / "ml_lab" / "10b_run_benchmark_relative_decision_focused_learning.py"
    if not helper_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("mlx12b_helper", helper_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


H = load_helper()


@dataclass(frozen=True)
class ModelResult:
    model_name: str
    model_family: str
    target_name: str
    ranking_target: str
    score: np.ndarray
    model_object: Any | None = None


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
    pct_cols = {
        "annual_return",
        "annual_volatility",
        "max_drawdown",
        "cvar_5",
        "average_turnover",
        "annual_cost_drag",
        "average_bil_exposure",
        "average_safe_exposure",
        "average_risky_exposure",
        "average_ml_exposure",
        "average_top3_weight",
    }
    num_cols = {"sharpe", "calmar", "rank_ic", "spearman_rank_corr", "ndcg_5", "ndcg_10", "top_quintile_hit_rate"}
    for col in tmp.columns:
        if col in pct_cols:
            tmp[col] = tmp[col].map(pct)
        elif col in num_cols:
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
    if H is not None:
        return H.split_for_dates(dates)
    parsed = pd.to_datetime(dates)
    index = dates.index if isinstance(dates, pd.Series) else pd.DatetimeIndex(parsed)
    s = pd.Series(parsed, index=index)
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
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
            "average_safe_exposure": np.nan,
            "average_risky_exposure": np.nan,
            "average_ml_exposure": np.nan,
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
        "average_safe_exposure": float(path.get("safe_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_risky_exposure": float(path.get("risky_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_ml_exposure": float(path.get("model_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_top3_weight": float(path.get("top3_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "top_quintile_hit_rate": float(path.get("top_quintile_hit_rate", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def package_status() -> dict[str, dict[str, Any]]:
    status = {}
    for package in ["lightgbm", "xgboost", "sklearn"]:
        spec = importlib.util.find_spec(package)
        item = {"available": bool(spec), "version": None}
        if spec:
            try:
                module = importlib.import_module(package)
                item["version"] = getattr(module, "__version__", None)
            except Exception as exc:
                item["available"] = False
                item["import_error"] = f"{type(exc).__name__}: {exc}"
        status[package] = item
    return status


def load_inputs(warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-14 inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    returns = pd.read_csv(WEEKLY_RETURNS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    returns["Date"] = pd.to_datetime(returns["Date"])
    features = features.sort_values(["Date", "ticker"]).reset_index(drop=True)
    targets = targets.sort_values(["Date", "ticker"]).reset_index(drop=True)
    if len(features) != len(targets):
        raise ValueError(f"Feature/target row count mismatch: {len(features)} vs {len(targets)}")
    if not features[["Date", "ticker"]].equals(targets[["Date", "ticker"]]):
        raise ValueError("Feature and target identifiers do not align.")
    overlap = sorted(set(features.columns) & TARGET_COLUMNS)
    if overlap:
        raise ValueError(f"Target columns leaked into features: {overlap}")
    bad = [c for c in features.columns if c not in {"Date", "ticker"} and c.lower().startswith(TARGET_LIKE_PREFIXES)]
    if bad:
        raise ValueError(f"Target-like feature columns found: {bad[:10]}")
    returns = returns.set_index("Date").sort_index()
    for col in returns.columns:
        returns[col] = pd.to_numeric(returns[col], errors="coerce")
    meta = pd.read_csv(UNIVERSE_IN) if UNIVERSE_IN.exists() else pd.DataFrame()
    if "BIL" not in returns.columns:
        warn("BIL returns missing; BIL fallback overlays will use a zero-return cash proxy where needed.", warnings_list)
    return features, targets, returns, meta


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


def read_return_file(path: Path) -> pd.DataFrame:
    if H is not None:
        return H.read_return_file(path)
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
    return df


def load_prior_strategy_by_name(
    label: str,
    returns_path: Path,
    strategy_name: str | None,
    warnings_list: list[str],
) -> pd.Series | None:
    if not strategy_name or not returns_path.exists():
        return None
    try:
        returns = pd.read_csv(returns_path, parse_dates=["Date"])
        sub = returns[returns["strategy_name"].eq(strategy_name)].set_index("Date").sort_index()
        if sub.empty or "net_return" not in sub.columns:
            warn(f"No return rows for prior comparison {label}: {strategy_name}", warnings_list)
            return None
        return pd.to_numeric(sub["net_return"], errors="coerce").rename(label)
    except Exception as exc:
        warn(f"Could not load prior comparison {label}: {exc}", warnings_list)
        return None


def load_prior_strategy_from_summary(
    label: str,
    summary_path: Path,
    returns_path: Path,
    warnings_list: list[str],
    prefer_validation_json: Path | None = None,
) -> pd.Series | None:
    if prefer_validation_json and prefer_validation_json.exists():
        try:
            data = json.loads(prefer_validation_json.read_text())
            for key in ("validation_selected_holdout", "best_validation_selected_ensemble", "best_validation_model"):
                name = data.get(key, {}).get("strategy_name")
                if name:
                    series = load_prior_strategy_by_name(label, returns_path, name, warnings_list)
                    if series is not None:
                        return series
        except Exception as exc:
            warn(f"Could not read validation-selected JSON for {label}: {exc}", warnings_list)
    if not summary_path.exists() or not returns_path.exists():
        warn(f"Optional comparison missing for {label}: {summary_path} / {returns_path}", warnings_list)
        return None
    try:
        summary = pd.read_csv(summary_path)
        sub = summary[summary["split"].eq("holdout")] if "split" in summary.columns else summary
        if sub.empty or "strategy_name" not in sub.columns:
            return None
        sort_cols = [c for c in ["sharpe", "annual_return"] if c in sub.columns]
        name = sub.sort_values(sort_cols, ascending=[False] * len(sort_cols)).iloc[0]["strategy_name"] if sort_cols else sub.iloc[0]["strategy_name"]
        return load_prior_strategy_by_name(label, returns_path, name, warnings_list)
    except Exception as exc:
        warn(f"Could not load prior comparison {label}: {exc}", warnings_list)
        return None


def load_strategy_returns(weekly_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    frames: dict[str, pd.Series] = {}
    sources: dict[str, str] = {}
    if H is not None:
        try:
            base, sources = H.load_strategy_returns(weekly_returns, warnings_list)
            for col in base.columns:
                frames[col] = base[col].rename(col)
        except Exception as exc:
            warn(f"Could not load shared project strategy comparisons: {exc}", warnings_list)
    if "SPY" in weekly_returns.columns and "SPY" not in frames:
        frames["SPY"] = weekly_returns["SPY"].rename("SPY")
    if "BIL" in weekly_returns.columns and "BIL" not in frames:
        frames["BIL"] = weekly_returns["BIL"].rename("BIL")
    elif "BIL" not in frames:
        frames["BIL"] = pd.Series(0.0, index=weekly_returns.index, name="BIL")
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond and "60_40" not in frames:
        frames["60_40"] = (0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]).rename("60_40")
    extras = {
        "mlx3_tabular": (
            TABULAR_DIR / "ml_tabular_summary.csv",
            TABULAR_DIR / "ml_tabular_backtest_returns.csv",
            None,
        ),
        "mlx4_mlp": (
            NN_DIR / "nn_summary.csv",
            NN_DIR / "nn_backtest_returns.csv",
            None,
        ),
        "mlx11_cross_asset_attention": (
            CROSS_ASSET_DIR / "cross_asset_attention_summary.csv",
            CROSS_ASSET_DIR / "cross_asset_attention_backtest_returns.csv",
            CROSS_ASSET_DIR / "cross_asset_attention_summary.json",
        ),
        "mlx12b_benchmark_relative": (
            BENCH_REL_DIR / "benchmark_relative_summary.csv",
            BENCH_REL_DIR / "benchmark_relative_returns.csv",
            BENCH_REL_DIR / "benchmark_relative_summary.json",
        ),
    }
    for label, (summary_path, returns_path, json_path) in extras.items():
        series = load_prior_strategy_from_summary(label, summary_path, returns_path, warnings_list, json_path)
        if series is not None:
            frames[label] = series
    if not frames:
        raise RuntimeError("No strategy return comparisons could be loaded.")
    return pd.concat(frames.values(), axis=1).sort_index(), sources


def relevance_from_rank(rank: pd.Series) -> pd.Series:
    r = pd.to_numeric(rank, errors="coerce")
    out = pd.Series(np.nan, index=rank.index)
    out.loc[r.notna()] = 0
    out.loc[r.ge(0.40)] = 1
    out.loc[r.ge(0.60)] = 2
    out.loc[r.ge(0.80)] = 3
    return out


def build_learning_frame(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    weekly_returns: pd.DataFrame,
    warnings_list: list[str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    tickers = sorted(set(features["ticker"].unique()) & set(weekly_returns.columns))
    frame = pd.concat([features.reset_index(drop=True), targets.drop(columns=["Date", "ticker"]).reset_index(drop=True)], axis=1)
    frame = frame[frame["ticker"].isin(tickers)].copy()
    frame["split"] = split_for_dates(frame["Date"]).values
    feature_cols = safe_feature_columns(features)
    train_mask = frame["split"].eq("train")
    medians = frame.loc[train_mask, feature_cols].median(numeric_only=True).fillna(0.0)
    means = frame.loc[train_mask, feature_cols].mean(numeric_only=True).fillna(0.0)
    stds = frame.loc[train_mask, feature_cols].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)
    missing_rates = frame[feature_cols].isna().mean().sort_values(ascending=False)
    x_filled = frame[feature_cols].fillna(medians)
    x_scaled = (x_filled - means) / stds
    frame["relevance_4w"] = relevance_from_rank(frame["forward_rank_4w"]).astype("float")
    frame["relevance_13w"] = relevance_from_rank(frame["forward_rank_13w"]).astype("float")
    frame["row_id"] = np.arange(len(frame))
    for col in feature_cols:
        frame[f"__x__{col}"] = x_filled[col].to_numpy(dtype="float32")
        frame[f"__z__{col}"] = x_scaled[col].to_numpy(dtype="float32")
    metadata = {
        "universe_size": int(len(tickers)),
        "date_count": int(frame["Date"].nunique()),
        "row_count": int(len(frame)),
        "feature_count": int(len(feature_cols)),
        "feature_columns": feature_cols,
        "top_missing_features": missing_rates.head(20).to_dict(),
        "train_only_median_fill": True,
        "train_only_standardization": True,
    }
    if TRIPLE_DIR.joinpath("triple_barrier_labels.parquet").exists():
        warnings_list.append("MLX-13 triple-barrier labels are strategy/date-level, not per-ETF relevance labels; they were not used as direct ETF ranking labels in MLX-14.")
    return frame.sort_values(["Date", "ticker"]).reset_index(drop=True), metadata


def group_sizes(df: pd.DataFrame) -> list[int]:
    return [int(v) for v in df.groupby("Date", sort=False).size().to_list()]


def qid_codes(df: pd.DataFrame) -> np.ndarray:
    return pd.factorize(df["Date"], sort=False)[0]


def ndcg_at_k(scores: np.ndarray, relevance: np.ndarray, k: int) -> float:
    mask = np.isfinite(scores) & np.isfinite(relevance)
    if int(mask.sum()) < 2:
        return np.nan
    s = scores[mask]
    rel = relevance[mask]
    k = min(k, len(s))
    order = np.argsort(-s)[:k]
    ideal = np.argsort(-rel)[:k]
    discounts = 1.0 / np.log2(np.arange(2, k + 2))
    dcg = float(((2.0 ** rel[order] - 1.0) * discounts).sum())
    idcg = float(((2.0 ** rel[ideal] - 1.0) * discounts).sum())
    return dcg / idcg if idcg > 0 else np.nan


def score_metrics_for_split(preds: pd.DataFrame, split: str) -> dict[str, float]:
    sub = preds[preds["split"].eq(split)]
    if sub.empty:
        return {"rank_ic": np.nan, "spearman_rank_corr": np.nan, "ndcg_5": np.nan, "ndcg_10": np.nan, "top_quintile_hit_rate": np.nan}
    rank_vals = []
    spearman_vals = []
    ndcg5_vals = []
    ndcg10_vals = []
    hit_vals = []
    for _, group in sub.groupby("Date", sort=False):
        score = pd.to_numeric(group["score"], errors="coerce")
        rank = pd.to_numeric(group["forward_rank_4w"], errors="coerce")
        ret = pd.to_numeric(group["forward_return_4w"], errors="coerce")
        rel = pd.to_numeric(group["relevance_4w"], errors="coerce")
        topq = pd.to_numeric(group["top_quintile_forward_4w"], errors="coerce")
        mask = score.notna() & rank.notna()
        if int(mask.sum()) >= 5:
            rank_corr = score[mask].corr(rank[mask], method="spearman")
            if pd.notna(rank_corr):
                rank_vals.append(float(rank_corr))
        mask_ret = score.notna() & ret.notna()
        if int(mask_ret.sum()) >= 5:
            corr = score[mask_ret].corr(ret[mask_ret], method="spearman")
            if pd.notna(corr):
                spearman_vals.append(float(corr))
        ndcg5 = ndcg_at_k(score.to_numpy(dtype=float), rel.to_numpy(dtype=float), 5)
        ndcg10 = ndcg_at_k(score.to_numpy(dtype=float), rel.to_numpy(dtype=float), 10)
        if pd.notna(ndcg5):
            ndcg5_vals.append(float(ndcg5))
        if pd.notna(ndcg10):
            ndcg10_vals.append(float(ndcg10))
        chosen = group.sort_values("score", ascending=False).head(10)
        if not chosen.empty:
            hit_vals.append(float(pd.to_numeric(chosen["top_quintile_forward_4w"], errors="coerce").mean()))
    return {
        "rank_ic": float(np.nanmean(rank_vals)) if rank_vals else np.nan,
        "spearman_rank_corr": float(np.nanmean(spearman_vals)) if spearman_vals else np.nan,
        "ndcg_5": float(np.nanmean(ndcg5_vals)) if ndcg5_vals else np.nan,
        "ndcg_10": float(np.nanmean(ndcg10_vals)) if ndcg10_vals else np.nan,
        "top_quintile_hit_rate": float(np.nanmean(hit_vals)) if hit_vals else np.nan,
    }


def fit_models(frame: pd.DataFrame, feature_cols: list[str], packages: dict[str, Any], warnings_list: list[str]) -> tuple[list[ModelResult], pd.DataFrame, pd.DataFrame, list[dict[str, str]]]:
    skipped: list[dict[str, str]] = []
    importance_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    results: list[ModelResult] = []
    x_cols = [f"__x__{c}" for c in feature_cols]
    z_cols = [f"__z__{c}" for c in feature_cols]
    X_all_tree = frame[x_cols].to_numpy(dtype="float32")
    X_all_scaled = frame[z_cols].to_numpy(dtype="float32")

    def add_result(name: str, family: str, target: str, ranking_target: str, score: np.ndarray, model: Any | None) -> None:
        result = ModelResult(name, family, target, ranking_target, score.astype("float32"), model)
        results.append(result)
        preds = prediction_frame(frame, result)
        for split in ("train", "validation", "holdout"):
            row = score_metrics_for_split(preds, split)
            row.update({"model_name": name, "model_family": family, "target_name": target, "ranking_target": ranking_target, "split": split})
            metric_rows.append(row)

    def add_importance(name: str, family: str, model: Any, scaled: bool = False) -> None:
        values = None
        importance_type = "feature_importance"
        if hasattr(model, "feature_importances_"):
            values = np.asarray(model.feature_importances_, dtype=float)
        elif hasattr(model, "coef_"):
            values = np.ravel(np.asarray(model.coef_, dtype=float))
            importance_type = "coefficient_abs"
            values = np.abs(values)
        if values is None:
            return
        for feature, value in zip(feature_cols, values):
            importance_rows.append({"model_name": name, "model_family": family, "feature": feature, "importance": float(value), "importance_type": importance_type, "scaled_features": bool(scaled)})

    # LightGBM LambdaRank models.
    if packages["lightgbm"]["available"]:
        try:
            import lightgbm as lgb
            from lightgbm import LGBMRanker

            for target, label_col in [("forward_return_4w_rank_relevance", "relevance_4w"), ("forward_return_13w_rank_relevance", "relevance_13w")]:
                train = frame[frame["split"].eq("train") & frame[label_col].notna()].sort_values(["Date", "ticker"])
                val = frame[frame["split"].eq("validation") & frame[label_col].notna()].sort_values(["Date", "ticker"])
                if train.empty or val.empty:
                    skipped.append({"variant": f"lightgbm_lambdarank_{label_col}", "reason": "missing train/validation ranking labels"})
                    continue
                name = f"lightgbm_lambdarank_{label_col}"
                model = LGBMRanker(
                    objective="lambdarank",
                    metric="ndcg",
                    n_estimators=220,
                    learning_rate=0.035,
                    num_leaves=31,
                    min_child_samples=20,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    random_state=14,
                    n_jobs=4,
                    verbosity=-1,
                )
                try:
                    model.fit(
                        train[x_cols],
                        train[label_col].astype(int),
                        group=group_sizes(train),
                        eval_set=[(val[x_cols], val[label_col].astype(int))],
                        eval_group=[group_sizes(val)],
                        eval_at=[5, 10],
                        callbacks=[lgb.early_stopping(25, verbose=False)],
                    )
                except TypeError:
                    model.fit(train[x_cols], train[label_col].astype(int), group=group_sizes(train))
                add_result(name, "lightgbm_ranker", target, label_col, model.predict(X_all_tree), model)
                add_importance(name, "lightgbm_ranker", model)
        except Exception as exc:
            skipped.append({"variant": "lightgbm_rankers", "reason": f"{type(exc).__name__}: {exc}"})
    else:
        skipped.append({"variant": "lightgbm_rankers", "reason": "lightgbm not installed/importable"})

    # XGBoost ranker.
    if packages["xgboost"]["available"]:
        try:
            from xgboost import XGBRanker

            label_col = "relevance_4w"
            train = frame[frame["split"].eq("train") & frame[label_col].notna()].sort_values(["Date", "ticker"])
            val = frame[frame["split"].eq("validation") & frame[label_col].notna()].sort_values(["Date", "ticker"])
            if train.empty or val.empty:
                skipped.append({"variant": "xgboost_rank_ndcg_relevance_4w", "reason": "missing train/validation ranking labels"})
            else:
                name = "xgboost_rank_ndcg_relevance_4w"
                model = XGBRanker(
                    objective="rank:ndcg",
                    eval_metric="ndcg@10",
                    n_estimators=160,
                    learning_rate=0.035,
                    max_depth=4,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    min_child_weight=10,
                    random_state=14,
                    n_jobs=4,
                    tree_method="hist",
                )
                model.fit(
                    train[x_cols],
                    train[label_col].astype(int),
                    qid=qid_codes(train),
                    eval_set=[(val[x_cols], val[label_col].astype(int))],
                    eval_qid=[qid_codes(val)],
                    verbose=False,
                )
                add_result(name, "xgboost_ranker", "forward_return_4w_rank_relevance", label_col, model.predict(X_all_tree), model)
                add_importance(name, "xgboost_ranker", model)
        except Exception as exc:
            skipped.append({"variant": "xgboost_rank_ndcg_relevance_4w", "reason": f"{type(exc).__name__}: {exc}"})
    else:
        skipped.append({"variant": "xgboost_rankers", "reason": "xgboost not installed/importable"})

    try:
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.linear_model import ElasticNet, Ridge

        train_cls = frame[frame["split"].eq("train") & frame["top_quintile_forward_4w"].notna()]
        y_cls = train_cls["top_quintile_forward_4w"].astype(int)
        classifiers = [
            (
                "random_forest_classifier_top_quintile_4w",
                "random_forest_classifier",
                RandomForestClassifier(n_estimators=220, max_depth=7, min_samples_leaf=25, class_weight="balanced_subsample", random_state=14, n_jobs=4),
            ),
            (
                "gradient_boosting_classifier_top_quintile_4w",
                "gradient_boosting_classifier",
                GradientBoostingClassifier(n_estimators=150, learning_rate=0.04, max_depth=3, random_state=14),
            ),
        ]
        for name, family, model in classifiers:
            if y_cls.nunique() < 2:
                skipped.append({"variant": name, "reason": "classification target has fewer than two train classes"})
                continue
            model.fit(train_cls[x_cols], y_cls)
            score = model.predict_proba(X_all_tree)[:, list(model.classes_).index(1)] if 1 in model.classes_ else model.predict(X_all_tree)
            add_result(name, family, "top_quintile_forward_4w", "classification_relevance", score, model)
            add_importance(name, family, model)

        train_reg = frame[frame["split"].eq("train") & frame["forward_return_4w"].notna()]
        regressors = [
            ("ridge_regression_forward_return_4w", "ridge_regression", Ridge(alpha=10.0), "forward_return_4w"),
            ("elasticnet_regression_forward_return_4w", "elasticnet_regression", ElasticNet(alpha=0.0005, l1_ratio=0.25, max_iter=5000, random_state=14), "forward_return_4w"),
        ]
        for name, family, model, target_col in regressors:
            sub = frame[frame["split"].eq("train") & frame[target_col].notna()]
            if sub.empty:
                skipped.append({"variant": name, "reason": "missing regression target rows"})
                continue
            model.fit(sub[z_cols], sub[target_col])
            add_result(name, family, target_col, "regression_score", model.predict(X_all_scaled), model)
            add_importance(name, family, model, scaled=True)
    except Exception as exc:
        skipped.append({"variant": "sklearn_fallback_models", "reason": f"{type(exc).__name__}: {exc}"})

    return results, pd.DataFrame(metric_rows), pd.DataFrame(importance_rows), skipped


def prediction_frame(frame: pd.DataFrame, result: ModelResult) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": frame["Date"].values,
            "ticker": frame["ticker"].values,
            "model_name": result.model_name,
            "model_family": result.model_family,
            "target_name": result.target_name,
            "ranking_target": result.ranking_target,
            "split": frame["split"].values,
            "score": result.score,
            "forward_return_4w": frame["forward_return_4w"].values,
            "forward_return_13w": frame["forward_return_13w"].values,
            "forward_rank_4w": frame["forward_rank_4w"].values,
            "forward_rank_13w": frame["forward_rank_13w"].values,
            "relevance_4w": frame["relevance_4w"].values,
            "relevance_13w": frame["relevance_13w"].values,
            "top_quintile_forward_4w": frame["top_quintile_forward_4w"].values,
            "beats_SPY_4w": frame["beats_SPY_4w"].values,
        }
    )


def build_prediction_panel(frame: pd.DataFrame, results: list[ModelResult]) -> pd.DataFrame:
    return pd.concat([prediction_frame(frame, result) for result in results], ignore_index=True) if results else pd.DataFrame()


def safe_weight_frame(weights: pd.DataFrame) -> pd.Series:
    cols = [c for c in weights.columns if c in SAFE_ASSETS]
    if not cols:
        return pd.Series(0.0, index=weights.index)
    return weights[cols].sum(axis=1)


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
    if wrapper == "defensive_first":
        exposure = state.reindex(dates).map({"calm_trend": 0.85, "recovery_confirmed": 0.85, "neutral_mixed": 0.50, "recovery_fragile": 0.40, "stressed_panic": 0.10}).fillna(0.50)
        return add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"Unknown wrapper: {wrapper}")


def topn_weights(score_table: pd.DataFrame, dates: pd.DatetimeIndex, tickers: list[str], top_n: int, weighting: str, next_returns: pd.DataFrame, vol_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    hit_rate = pd.Series(np.nan, index=dates)
    available_mask = next_returns.reindex(index=dates, columns=tickers).notna()
    available_sets = {date: set(available_mask.columns[available_mask.loc[date].to_numpy()]) for date in dates}
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        eligible = group[["ticker", "score", "top_quintile_forward_4w"]].dropna(subset=["score"])
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
        hit_rate.loc[date] = pd.to_numeric(chosen_frame["top_quintile_forward_4w"], errors="coerce").mean()
    return weights, hit_rate


def compute_model_path(weights: pd.DataFrame, next_returns: pd.DataFrame, exposure: pd.Series, hit_rate: pd.Series) -> pd.DataFrame:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (DEFAULT_COST_BPS / 10000.0)
    safe = safe_weight_frame(weights)
    return pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": gross - cost,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index),
            "safe_weight": safe,
            "risky_exposure": 1.0 - safe,
            "model_exposure": exposure.reindex(weights.index).fillna(1.0),
            "holdings_count": weights.gt(0.001).sum(axis=1),
            "top_quintile_hit_rate": hit_rate.reindex(weights.index),
            "top3_weight": weights.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1),
        },
        index=weights.index,
    )


def compute_core_sleeve_path(core_name: str, sleeve_weights: pd.DataFrame, next_returns: pd.DataFrame, state: pd.Series, hit_rate: pd.Series, strategy_returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    safe = safe_weight_frame(effective_weights) + (0.10 - sleeve_exposure)
    path = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": gross - cost,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": (0.10 - sleeve_exposure) + (effective_weights["BIL"] if "BIL" in effective_weights.columns else 0.0),
            "safe_weight": safe,
            "risky_exposure": sleeve_exposure,
            "model_exposure": sleeve_exposure,
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


def append_backtest(
    returns_frames: list[pd.DataFrame],
    weights_frames: list[pd.DataFrame],
    summary_rows: list[dict[str, Any]],
    path: pd.DataFrame,
    weights: pd.DataFrame,
    model_meta: dict[str, Any],
    allocation_method: str,
    wrapper: str,
    model_metrics: dict[tuple[str, str], dict[str, float]],
) -> None:
    strategy_name = f"{model_meta['model_name']}__{allocation_method}__{wrapper}"
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    for key, value in model_meta.items():
        dated[key] = value
    dated["allocation_method"] = allocation_method
    dated["wrapper"] = wrapper
    dated["cost_bps"] = DEFAULT_COST_BPS
    returns_frames.append(dated.reset_index(drop=True))
    for split in ("train", "validation", "holdout"):
        sub = dated[dated["split"].eq(split)]
        metrics = calc_metrics(sub.set_index("Date"))
        rank_metrics = model_metrics.get((model_meta["model_name"], split), {})
        metrics.update(rank_metrics)
        metrics.update(
            {
                "strategy_name": strategy_name,
                **model_meta,
                "allocation_method": allocation_method,
                "wrapper": wrapper,
                "split": split,
                "cost_bps": DEFAULT_COST_BPS,
            }
        )
        summary_rows.append(metrics)
    w = weights.copy()
    w["Date"] = w.index
    long = w.reset_index(drop=True).melt(id_vars="Date", var_name="ticker", value_name="weight")
    long = long[long["weight"].abs() > 1e-6].copy()
    long["strategy_name"] = strategy_name
    for key, value in model_meta.items():
        long[key] = value
    long["allocation_method"] = allocation_method
    long["wrapper"] = wrapper
    long["split"] = split_for_dates(long["Date"]).values
    weights_frames.append(long)


def run_backtests(predictions: pd.DataFrame, frame: pd.DataFrame, weekly_returns: pd.DataFrame, strategy_returns: pd.DataFrame, ranking_metrics: pd.DataFrame, universe_meta: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(frame["Date"].unique()))
    tickers = sorted(frame["ticker"].unique())
    next_returns = weekly_returns.reindex(index=dates, columns=tickers).shift(-1)
    fidx = frame.set_index(["Date", "ticker"])
    vol_panel = fidx["realized_vol_13w"].unstack("ticker").reindex(index=dates, columns=tickers) if "realized_vol_13w" in frame.columns else pd.DataFrame(index=dates, columns=tickers)
    state = infer_market_state_by_date(frame)
    metric_lookup = {
        (row["model_name"], row["split"]): {
            "rank_ic": row.get("rank_ic", np.nan),
            "spearman_rank_corr": row.get("spearman_rank_corr", np.nan),
            "ndcg_5": row.get("ndcg_5", np.nan),
            "ndcg_10": row.get("ndcg_10", np.nan),
            "model_top10_hit_rate": row.get("top_quintile_hit_rate", np.nan),
        }
        for _, row in ranking_metrics.iterrows()
    }
    returns_frames: list[pd.DataFrame] = []
    weights_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    allocation_specs = [(5, "equal_weight"), (10, "equal_weight"), (15, "equal_weight"), (5, "inverse_vol"), (10, "inverse_vol"), (15, "inverse_vol")]
    for (model_name, model_family, target_name, ranking_target), group in predictions.groupby(["model_name", "model_family", "target_name", "ranking_target"], sort=True):
        model_meta = {"model_name": model_name, "model_family": model_family, "target_name": target_name, "ranking_target": ranking_target}
        for top_n, weighting in allocation_specs:
            allocation_method = f"top{top_n}_{weighting}"
            raw_weights, hit_rate = topn_weights(group, dates, tickers, top_n, weighting, next_returns, vol_panel)
            for wrapper in ("raw_ml", "bil_fallback_original", "regime_gate_original", "defensive_first"):
                weights, exposure = overlay_weights(wrapper, raw_weights, state)
                path = compute_model_path(weights, next_returns, exposure, hit_rate)
                append_backtest(returns_frames, weights_frames, summary_rows, path, weights, model_meta, allocation_method, wrapper, metric_lookup)
            for core_name in ("production", "phase4b"):
                if core_name in strategy_returns.columns:
                    path, audit_weights = compute_core_sleeve_path(core_name, raw_weights, next_returns, state, hit_rate, strategy_returns)
                    append_backtest(returns_frames, weights_frames, summary_rows, path, audit_weights, model_meta, allocation_method, f"{core_name}_core_plus_10pct_ranker_sleeve", metric_lookup)
    returns_df = pd.concat(returns_frames, ignore_index=True) if returns_frames else pd.DataFrame()
    weights_df = pd.concat(weights_frames, ignore_index=True) if weights_frames else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return returns_df, weights_df, summary


def benchmark_rows(strategy_returns: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for name in [
        "production",
        "official_shadow",
        "phase4b",
        "phase6",
        "phase7",
        "mlx3_tabular",
        "mlx4_mlp",
        "mlx5_sequence",
        "mlx6_transformer",
        "mlx9_ensemble",
        "mlx11_cross_asset_attention",
        "mlx12_decision_focused",
        "mlx12b_benchmark_relative",
        "mlx13_validation_filter",
        "mlx13_holdout_diagnostic",
        "SPY",
        "60_40",
        "simple_momentum",
    ]:
        if name not in strategy_returns.columns:
            continue
        frame = pd.DataFrame(
            {
                "net_return": strategy_returns[name],
                "gross_return": strategy_returns[name],
                "turnover": np.nan,
                "cost": 0.0,
                "bil_weight": 0.0,
                "safe_weight": 0.0,
                "risky_exposure": 1.0,
                "model_exposure": 0.0,
                "top3_weight": np.nan,
                "top_quintile_hit_rate": np.nan,
            }
        )
        frame["split"] = split_for_dates(frame.index).values
        metrics = calc_metrics(frame[frame["split"].eq("holdout")])
        metrics.update({"strategy_name": name, "category": "benchmark", "split": "holdout"})
        rows.append(metrics)
    summary_path = SEQUENCE_5C_DIR / "sequence_multiseed_summary.json"
    if summary_path.exists():
        try:
            data = json.loads(summary_path.read_text())
            rows.append(
                {
                    "strategy_name": "mlx5c_bil_fallback_mean_summary",
                    "category": "benchmark_summary_only",
                    "split": "holdout",
                    "annual_return": np.nan,
                    "annual_volatility": np.nan,
                    "sharpe": data.get("overall_mean_sharpe", np.nan),
                    "max_drawdown": data.get("overall_worst_case_max_drawdown", np.nan),
                    "cvar_5": data.get("overall_worst_case_cvar_5", np.nan),
                }
            )
        except Exception:
            pass
    return rows


def build_strategy_comparison(summary: pd.DataFrame, strategy_returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rows.extend(summary[summary["split"].eq("holdout")].assign(category="learning_to_rank_model").to_dict(orient="records"))
    rows.extend(benchmark_rows(strategy_returns))
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
            "average_international_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "International equity"]).sum(axis=1),
        }
        for label, series in summaries.items():
            rows.append({"strategy_name": strategy, "audit_type": "summary", "item": label, "category": "", "average_weight": float(series.mean()), "max_weight": float(series.max()), "holding_frequency": np.nan})
    return pd.DataFrame(rows).sort_values(["strategy_name", "audit_type", "average_weight"], ascending=[True, True, False])


def best_validation_row(summary: pd.DataFrame) -> dict[str, Any]:
    sub = summary[(summary["split"].eq("validation")) & (summary["active_weeks"].ge(50))].copy()
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "annual_return", "ndcg_10", "max_drawdown"], ascending=[False, False, False, False]).iloc[0].to_dict()


def holdout_for_strategy(summary: pd.DataFrame, strategy_name: str) -> dict[str, Any]:
    sub = summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq(strategy_name))]
    return sub.iloc[0].to_dict() if not sub.empty else {}


def best_holdout_row(summary: pd.DataFrame) -> dict[str, Any]:
    sub = summary[(summary["split"].eq("holdout")) & (summary["active_weeks"].ge(50))].copy()
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "annual_return", "ndcg_10", "max_drawdown"], ascending=[False, False, False, False]).iloc[0].to_dict()


def comp_lookup(comparison: pd.DataFrame, name: str, field: str) -> float:
    row = comparison[comparison["strategy_name"].eq(name)]
    if row.empty or field not in row.columns:
        return np.nan
    return float(row.iloc[0][field])


def choose_recommendation(validation_holdout: dict[str, Any], comparison: pd.DataFrame) -> str:
    sharpe = validation_holdout.get("sharpe", np.nan)
    phase4b = comp_lookup(comparison, "phase4b", "sharpe")
    production = comp_lookup(comparison, "production", "sharpe")
    mlx9 = comp_lookup(comparison, "mlx9_ensemble", "sharpe")
    if pd.notna(sharpe) and pd.notna(phase4b) and sharpe > phase4b:
        return "PROMISING RANKING DIRECTION BUT NEEDS WALK-FORWARD"
    if pd.notna(sharpe) and pd.notna(production) and sharpe > production and pd.notna(mlx9) and sharpe > mlx9:
        return "PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION"
    if pd.notna(sharpe) and sharpe > 0.7:
        return "PROMISING LEARNING RESULT BUT NOT PORTFOLIO CANDIDATE"
    return "KEEP AS RESEARCH ONLY"


def write_notes(
    summary_json: dict[str, Any],
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    state: pd.DataFrame,
    walk: pd.DataFrame,
    exposure: pd.DataFrame,
    importance: pd.DataFrame,
    ranking_metrics: pd.DataFrame,
) -> None:
    best_val = summary_json.get("best_validation_selected_model", {})
    val_hold = summary_json.get("validation_selected_holdout", {})
    best_diag = summary_json.get("best_holdout_diagnostic_model", {})
    top_holdout = summary[summary["split"].eq("holdout")].sort_values(["sharpe", "annual_return"], ascending=[False, False]).head(20)
    top_importance = importance.sort_values(["model_name", "importance"], ascending=[True, False]).groupby("model_name").head(10) if not importance.empty else pd.DataFrame()
    text = f"""# Phase MLX-14 Date-Grouped Learning-to-Rank ETF Selector Notes

## Research-Only Warning

Phase MLX-14 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading, production pins, dashboard changes, or candidate promotion.

## Educational Explanation

Learning-to-rank trains a model to order items rather than predict an exact number. In this ETF project, the natural question is often not "what exact return will SPY or TLT have?" but "which ETFs should be ranked above the others this week?" That makes ETF selection a cross-sectional ranking problem.

Ranking differs from regression because the model does not need a perfectly calibrated return forecast. It mainly needs the relative ordering to be useful. Ranking differs from classification because a top-quintile classifier treats each ETF row as a separate yes/no decision, while a date-grouped ranker sees all ETFs from the same date as one comparison group.

Date-grouped ranking means every weekly date is its own group. The model should compare SPY, TLT, GLD, QQQ, sectors, bonds, and BIL against each other at date `t`; it should not compare a 2008 ETF row against a 2024 ETF row as if they were in the same selection contest.

LambdaRank and LambdaMART are ranking methods that optimize ordering quality by emphasizing swaps near the top of the ranked list. LightGBM and XGBoost expose these ideas through LambdaRank / rank:NDCG objectives. NDCG, or normalized discounted cumulative gain, rewards putting high-relevance assets near the top. Rank IC is the Spearman correlation between model scores and future cross-sectional ranks.

Ranking can still overfit. The labels come from future returns, the ETF universe is selected, yfinance histories are research-only, and weekly financial data is noisy. A good validation rank IC or NDCG is not automatically a good portfolio.

## EECS 127 / Optimization Connection

The ranking loss is an objective function. Top-N ETF selection is a constrained decision: choose a small set of long-only positions from the weekly ETF universe. The loss should match the decision. MLX-12 and MLX-12B tried direct portfolio losses and showed that the wrong objective can create unstable or strategically wrong optima. MLX-14 uses a less direct but more stable objective: learn the ordering, then apply portfolio constraints and overlays after scoring.

## Technical Setup

- Universe size: {summary_json.get('universe_size')}
- Feature count: {summary_json.get('feature_count')}
- Ranking targets: {summary_json.get('ranking_targets_used')}
- Packages: {summary_json.get('packages')}
- Models run: {summary_json.get('ranker_models_run')}
- Skipped variants: {summary_json.get('skipped_runs')}
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Preprocessing: train-only median fill; train-only standardization for linear fallback models
- Leakage controls: target-like feature columns are excluded; date groups are chronological; action at date `t` earns next-week returns
- Transaction cost: {DEFAULT_COST_BPS:.0f} bps per unit turnover

## Results

- Best validation-selected ranker: `{best_val.get('strategy_name')}`
- Validation-selected holdout annual return: {pct(val_hold.get('annual_return'))}
- Validation-selected holdout Sharpe: {num(val_hold.get('sharpe'))}
- Validation-selected holdout max drawdown: {pct(val_hold.get('max_drawdown'))}
- Validation-selected holdout CVaR 5%: {pct(val_hold.get('cvar_5'))}
- Validation-selected holdout rank IC: {num(val_hold.get('rank_ic'))}
- Validation-selected holdout NDCG@10: {num(val_hold.get('ndcg_10'))}
- Validation-selected holdout top-quintile hit rate: {num(val_hold.get('top_quintile_hit_rate'))}
- Best holdout-diagnostic ranker: `{best_diag.get('strategy_name')}`

### Top Holdout Ranker Strategies

{markdown_table(top_holdout, ['strategy_name', 'model_family', 'target_name', 'allocation_method', 'wrapper', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'rank_ic', 'ndcg_10', 'top_quintile_hit_rate', 'average_bil_exposure', 'average_safe_exposure', 'average_top3_weight'], 25)}

### Ranking Metrics

{markdown_table(ranking_metrics.sort_values(['split', 'ndcg_10'], ascending=[True, False]), ['model_name', 'model_family', 'target_name', 'split', 'rank_ic', 'spearman_rank_corr', 'ndcg_5', 'ndcg_10', 'top_quintile_hit_rate'], 30)}

### Strategy Comparison

{markdown_table(comparison, ['strategy_name', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'top_quintile_hit_rate', 'rank_ic', 'ndcg_10', 'average_bil_exposure', 'average_safe_exposure'], 35)}

### State-By-State Results

{markdown_table(state, ['strategy_name', 'market_state', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_ml_exposure', 'weeks'], 30)}

### Walk-Forward Window Results

{markdown_table(walk, ['strategy_name', 'window', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'top_quintile_hit_rate', 'rank_ic', 'ndcg_10', 'active_weeks'], 20)}

### Feature Importance

{markdown_table(top_importance, ['model_name', 'model_family', 'feature', 'importance', 'importance_type'], 40)}

### Exposure Audit

{markdown_table(exposure, ['strategy_name', 'audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], 50)}

## Interpretation

The key question is whether explicit date-grouped ranking helped more than prediction-trained ML and direct decision-focused losses. The validation-selected result is the main answer; holdout-only best rows are diagnostic and should not be treated as selected strategies.

Ranking is more aligned with ETF selection than ordinary regression/classification because the portfolio only needs a useful ordering. But it still has the same core finance ML risks: weak stationarity, regime dependence, transaction costs, and high data-mining risk.

Final recommendation: **{summary_json.get('final_recommendation')}**.

## Warnings

{chr(10).join('- ' + str(w) for w in summary_json.get('warnings', []))}
"""
    NOTES_OUT.write_text(text)


def main() -> None:
    warnings_list: list[str] = []
    warn("Experimental research-only Phase MLX output; not production-valid.", warnings_list)
    warn("Learning-to-rank uses yfinance/expanded ETF research data and remains high overfitting risk.", warnings_list)
    packages = package_status()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    features, targets, weekly_returns, universe_meta = load_inputs(warnings_list)
    strategy_returns, strategy_sources = load_strategy_returns(weekly_returns, warnings_list)
    frame, preprocess_meta = build_learning_frame(features, targets, weekly_returns, warnings_list)
    feature_cols = preprocess_meta["feature_columns"]

    skipped = [
        {"variant": "full_walk_forward_retraining", "reason": "deferred; selected predictions are evaluated by window without retraining per fold"},
        {"variant": "pairwise_neural_ranking_loss", "reason": "deferred; first version uses LightGBM/XGBoost rankers plus supervised fallbacks"},
        {"variant": "triple_barrier_per_etf_relevance", "reason": "MLX-13 labels are strategy/date-level labels, not ETF-level ranking labels"},
    ]

    model_results, ranking_metrics, feature_importance, fit_skipped = fit_models(frame, feature_cols, packages, warnings_list)
    skipped.extend(fit_skipped)
    if not model_results:
        skipped.append({"variant": "all_rankers", "reason": "no ranker or fallback model completed"})
        write_empty_outputs(packages, preprocess_meta, skipped, warnings_list)
        return

    predictions = build_prediction_panel(frame, model_results)
    returns_df, weights_df, summary = run_backtests(predictions, frame, weekly_returns, strategy_returns, ranking_metrics, universe_meta)
    comparison = build_strategy_comparison(summary, strategy_returns)
    best_val = best_validation_row(summary)
    val_hold = holdout_for_strategy(summary, best_val.get("strategy_name", ""))
    best_diag = best_holdout_row(summary)
    focus = [x.get("strategy_name") for x in [val_hold, best_diag] if x.get("strategy_name")]
    state = state_by_state(returns_df, infer_market_state_by_date(frame), focus)
    walk = walkforward_summary(returns_df, focus)
    exposure = exposure_audit(weights_df, universe_meta, focus)

    final_recommendation = choose_recommendation(val_hold, comparison)
    summary_json = {
        "phase": "learning_to_rank_etf_selector",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "packages": packages,
        "universe_size": preprocess_meta["universe_size"],
        "feature_count": preprocess_meta["feature_count"],
        "row_count": preprocess_meta["row_count"],
        "date_count": preprocess_meta["date_count"],
        "ranking_targets_used": ["forward_return_4w date-group relevance", "forward_return_13w date-group relevance", "top_quintile_forward_4w fallback", "forward_return_4w regression fallback"],
        "ranker_models_run": [r.model_name for r in model_results],
        "skipped_runs": skipped,
        "best_validation_selected_model": best_val,
        "validation_selected_holdout": val_hold,
        "best_holdout_diagnostic_model": best_diag,
        "validation_selected_beats_mlx5c_sharpe": bool(pd.notna(val_hold.get("sharpe", np.nan)) and val_hold.get("sharpe", np.nan) > comp_lookup(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")),
        "validation_selected_beats_mlx9_sharpe": bool(pd.notna(val_hold.get("sharpe", np.nan)) and val_hold.get("sharpe", np.nan) > comp_lookup(comparison, "mlx9_ensemble", "sharpe")),
        "validation_selected_beats_production_sharpe": bool(pd.notna(val_hold.get("sharpe", np.nan)) and val_hold.get("sharpe", np.nan) > comp_lookup(comparison, "production", "sharpe")),
        "validation_selected_beats_phase4b_sharpe": bool(pd.notna(val_hold.get("sharpe", np.nan)) and val_hold.get("sharpe", np.nan) > comp_lookup(comparison, "phase4b", "sharpe")),
        "final_recommendation": final_recommendation,
        "warnings": warnings_list + ["No learning-to-rank model is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "strategy_sources": strategy_sources,
        "outputs": [str(p.relative_to(ROOT)) for p in [PREDICTIONS_OUT, RETURNS_OUT, SUMMARY_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, WALKFORWARD_OUT, FEATURE_IMPORTANCE_OUT, EXPOSURE_AUDIT_OUT, PREPROCESSING_METADATA_OUT, CANDIDATE_DEFINITIONS_OUT, SKIPPED_RUNS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]],
    }

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    returns_df.to_csv(RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    state.to_csv(STATE_BY_STATE_OUT, index=False)
    walk.to_csv(WALKFORWARD_OUT, index=False)
    feature_importance.to_csv(FEATURE_IMPORTANCE_OUT, index=False)
    exposure.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(preprocess_meta, indent=2, default=json_default))
    CANDIDATE_DEFINITIONS_OUT.write_text(
        json.dumps(
            {
                "lightgbm_lambdarank": "Date-grouped LambdaRank/NDCG ranker using 0/1/2/3 relevance labels from future date-wise ranks.",
                "xgboost_rank_ndcg": "Date-grouped XGBoost rank:NDCG ranker using query IDs equal to weekly dates.",
                "fallback_classifiers": "Random Forest and Gradient Boosting top-quintile classifiers converted to ranking scores.",
                "fallback_regressors": "Ridge and ElasticNet forward-return regressors converted to ranking scores.",
                "portfolio_tests": ["top5/top10/top15 equal weight", "top5/top10/top15 inverse volatility", "raw ML", "BIL fallback", "regime gate", "defensive first", "production/Phase4B 10% ranker sleeve"],
            },
            indent=2,
        )
    )
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(summary_json, summary, comparison, state, walk, exposure, feature_importance, ranking_metrics)

    print("Phase MLX-14 learning-to-rank ETF selector")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Packages: {packages}")
    print(f"Universe size: {preprocess_meta['universe_size']}")
    print(f"Models run: {[r.model_name for r in model_results]}")
    print(f"Best validation-selected model: {best_val.get('strategy_name')}")
    print(f"Validation-selected holdout Sharpe: {val_hold.get('sharpe')}")
    print(f"Best holdout diagnostic model: {best_diag.get('strategy_name')}")
    print(f"Best holdout diagnostic Sharpe: {best_diag.get('sharpe')}")
    print(f"Final recommendation: {final_recommendation}")
    print("Outputs:")
    for path in [PREDICTIONS_OUT, RETURNS_OUT, SUMMARY_OUT, STRATEGY_COMPARISON_OUT, STATE_BY_STATE_OUT, WALKFORWARD_OUT, FEATURE_IMPORTANCE_OUT, EXPOSURE_AUDIT_OUT, PREPROCESSING_METADATA_OUT, CANDIDATE_DEFINITIONS_OUT, SKIPPED_RUNS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


def write_empty_outputs(packages: dict[str, Any], preprocess_meta: dict[str, Any], skipped: list[dict[str, str]], warnings_list: list[str]) -> None:
    empty = pd.DataFrame()
    empty.to_parquet(PREDICTIONS_OUT, index=False)
    empty.to_csv(RETURNS_OUT, index=False)
    empty.to_csv(SUMMARY_OUT, index=False)
    empty.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    empty.to_csv(STATE_BY_STATE_OUT, index=False)
    empty.to_csv(WALKFORWARD_OUT, index=False)
    empty.to_csv(FEATURE_IMPORTANCE_OUT, index=False)
    empty.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    PREPROCESSING_METADATA_OUT.write_text(json.dumps(preprocess_meta, indent=2, default=json_default))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps({}, indent=2))
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2))
    summary_json = {
        "phase": "learning_to_rank_etf_selector",
        "production_valid": False,
        "research_only": True,
        "packages": packages,
        "skipped_runs": skipped,
        "warnings": warnings_list,
        "final_recommendation": "REJECT",
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
    }
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(summary_json, empty, empty, empty, empty, empty, empty, empty)


if __name__ == "__main__":
    main()
