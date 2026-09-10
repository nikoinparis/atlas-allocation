#!/usr/bin/env python3
"""
Phase MLX-13: triple-barrier meta-labeling and drift monitoring.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
"""

from __future__ import annotations

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
SEQUENCE_DIR = ML_DIR / "sequence_models"
SEQUENCE_5C_DIR = SEQUENCE_DIR / "multiseed_walkforward"
TRANSFORMER_DIR = ML_DIR / "transformers"
ENSEMBLE_DIR = ML_DIR / "ensembles"
DECISION_DIR = ML_DIR / "decision_focused"
OUTPUT_DIR = ML_DIR / "triple_barrier_meta"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_RETURNS_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_5C_SUMMARY_IN = SEQUENCE_5C_DIR / "sequence_multiseed_summary.json"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_RETURNS_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
ENSEMBLE_SUMMARY_JSON_IN = ENSEMBLE_DIR / "ensemble_summary.json"
ENSEMBLE_RETURNS_IN = ENSEMBLE_DIR / "ensemble_strategy_returns.csv"
DECISION_SUMMARY_JSON_IN = DECISION_DIR / "decision_focused_summary.json"
DECISION_RETURNS_IN = DECISION_DIR / "decision_focused_returns.csv"

LABELS_OUT = OUTPUT_DIR / "triple_barrier_labels.parquet"
LABEL_SUMMARY_OUT = OUTPUT_DIR / "triple_barrier_label_summary.csv"
MODEL_METRICS_OUT = OUTPUT_DIR / "triple_barrier_model_metrics.csv"
PREDICTIONS_OUT = OUTPUT_DIR / "triple_barrier_predictions.parquet"
STRATEGY_RETURNS_OUT = OUTPUT_DIR / "triple_barrier_strategy_returns.csv"
STRATEGY_SUMMARY_OUT = OUTPUT_DIR / "triple_barrier_strategy_summary.csv"
FEATURE_IMPORTANCE_OUT = OUTPUT_DIR / "triple_barrier_feature_importance.csv"
CONFUSION_OUT = OUTPUT_DIR / "triple_barrier_confusion_matrices.csv"
DRIFT_FEATURE_OUT = OUTPUT_DIR / "drift_feature_summary.csv"
DRIFT_PREDICTION_OUT = OUTPUT_DIR / "drift_prediction_summary.csv"
DRIFT_BEHAVIOR_OUT = OUTPUT_DIR / "drift_strategy_behavior_summary.csv"
DRIFT_PERFORMANCE_OUT = OUTPUT_DIR / "drift_performance_summary.csv"
TASK_DEFINITIONS_OUT = OUTPUT_DIR / "triple_barrier_task_definitions.json"
SKIPPED_TASKS_OUT = OUTPUT_DIR / "triple_barrier_skipped_tasks.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "triple_barrier_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_triple_barrier_meta_labeling_and_drift_notes.md"

DEFAULT_COST_BPS = 10.0
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
SPLITS = ("train", "validation", "holdout")
BARRIER_SETTINGS = [
    {"barrier_id": "h4_u1_l1", "horizon_weeks": 4, "upper_barrier": 0.01, "lower_barrier": -0.01},
    {"barrier_id": "h8_u2_l2", "horizon_weeks": 8, "upper_barrier": 0.02, "lower_barrier": -0.02},
    {"barrier_id": "h13_u3_l3", "horizon_weeks": 13, "upper_barrier": 0.03, "lower_barrier": -0.03},
]
THRESHOLDS = (0.50, 0.60, 0.70)


@dataclass(frozen=True)
class BarrierTask:
    task_id: str
    base_strategy: str
    compare_strategy: str | None
    label_type: str
    description: str
    positive_meaning: str
    negative_meaning: str


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
            "average_core_exposure",
            "average_ml_sleeve_exposure",
            "positive_rate",
            "negative_rate",
            "neutral_rate",
            "predicted_positive_rate",
            "predicted_danger_rate",
            "mean_probability_up",
            "mean_probability_down",
        }:
            tmp[col] = tmp[col].map(pct)
        elif col in {"sharpe", "calmar", "macro_f1", "balanced_accuracy", "accuracy", "roc_auc_ovr", "psi", "abs_z_shift"}:
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


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame) -> None:
    if len(features) != len(targets):
        raise ValueError(f"Feature/target row count mismatch: features={len(features)}, targets={len(targets)}")
    f_ids = features.sort_values(["Date", "ticker"])[["Date", "ticker"]].reset_index(drop=True)
    t_ids = targets.sort_values(["Date", "ticker"])[["Date", "ticker"]].reset_index(drop=True)
    if not f_ids.equals(t_ids):
        raise ValueError("Feature and target identifiers do not align.")
    overlap = sorted(set(features.columns) & TARGET_COLUMNS)
    if overlap:
        raise ValueError(f"Target columns leaked into features: {overlap}")
    target_like = [c for c in features.columns if c not in {"Date", "ticker"} and c.lower().startswith(TARGET_LIKE_PREFIXES)]
    if target_like:
        raise ValueError(f"Target-like feature columns found in inputs: {target_like[:10]}")


def safe_numeric_cols(features: pd.DataFrame) -> list[str]:
    cols = []
    for col in features.columns:
        if col in {"Date", "ticker"} or col in TARGET_COLUMNS:
            continue
        if col.lower().startswith(TARGET_LIKE_PREFIXES):
            continue
        if pd.api.types.is_numeric_dtype(features[col]):
            cols.append(col)
    return cols


def load_inputs(warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-13 inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    weekly = pd.read_csv(WEEKLY_RETURNS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    weekly["Date"] = pd.to_datetime(weekly["Date"])
    features = features.sort_values(["Date", "ticker"]).reset_index(drop=True)
    targets = targets.sort_values(["Date", "ticker"]).reset_index(drop=True)
    validate_inputs(features, targets)
    weekly = weekly.set_index("Date").sort_index()
    for col in weekly.columns:
        weekly[col] = pd.to_numeric(weekly[col], errors="coerce")
    if "BIL" not in weekly.columns:
        warn("BIL returns missing; BIL fallback filters will use zero-return cash approximation.", warnings_list)
    return features, targets, weekly


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
        raise ValueError(f"No net_return/return column found in {path}")
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


def load_strategy_returns(weekly: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    frames: dict[str, pd.Series] = {}
    sources: dict[str, str] = {}
    for name, path in select_project_strategy_files(warnings_list).items():
        try:
            frame = read_return_file(path)
            frames[name] = frame["net_return"].rename(name)
            sources[name] = str(path.relative_to(ROOT))
        except Exception as exc:
            warn(f"Could not load project strategy {name}: {exc}", warnings_list)
    if "BIL" in weekly.columns:
        frames["BIL"] = weekly["BIL"].rename("BIL")
    else:
        frames["BIL"] = pd.Series(0.0, index=weekly.index, name="BIL")
    if "SPY" in weekly.columns:
        frames["SPY"] = weekly["SPY"].rename("SPY")
    bond = "IEF" if "IEF" in weekly.columns else "AGG" if "AGG" in weekly.columns else None
    if "SPY" in weekly.columns and bond:
        frames["sixty_forty"] = (0.60 * weekly["SPY"] + 0.40 * weekly[bond]).rename("sixty_forty")
    if SEQUENCE_SUMMARY_IN.exists() and SEQUENCE_RETURNS_IN.exists():
        seq = load_best_strategy(
            SEQUENCE_SUMMARY_IN,
            SEQUENCE_RETURNS_IN,
            "MLX-5 sequence",
            lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("model")) & (~s["wrapper"].eq("raw_ml"))],
            warnings_list,
        )
        if not seq.empty:
            frames["mlx5_sequence"] = seq["net_return"].rename("mlx5_sequence")
            sources["mlx5_sequence"] = str(SEQUENCE_RETURNS_IN.relative_to(ROOT))
        mom = load_best_strategy(
            SEQUENCE_SUMMARY_IN,
            SEQUENCE_RETURNS_IN,
            "simple momentum",
            lambda s: s[(s["split"].eq("holdout")) & (s["strategy_type"].eq("baseline_momentum"))],
            warnings_list,
        )
        if not mom.empty:
            frames["simple_momentum"] = mom["net_return"].rename("simple_momentum")
            sources["simple_momentum"] = str(SEQUENCE_RETURNS_IN.relative_to(ROOT))
    if TRANSFORMER_SUMMARY_IN.exists() and TRANSFORMER_RETURNS_IN.exists():
        tr = load_best_strategy(
            TRANSFORMER_SUMMARY_IN,
            TRANSFORMER_RETURNS_IN,
            "MLX-6 Transformer",
            lambda s: s[(s["split"].eq("holdout")) & (~s["wrapper"].eq("raw_ml"))],
            warnings_list,
        )
        if not tr.empty:
            frames["mlx6_transformer"] = tr["net_return"].rename("mlx6_transformer")
            sources["mlx6_transformer"] = str(TRANSFORMER_RETURNS_IN.relative_to(ROOT))
    if ENSEMBLE_SUMMARY_JSON_IN.exists() and ENSEMBLE_RETURNS_IN.exists():
        try:
            data = json.loads(ENSEMBLE_SUMMARY_JSON_IN.read_text())
            name = data.get("best_validation_selected_ensemble", {}).get("strategy_name")
            ens = pd.read_csv(ENSEMBLE_RETURNS_IN, parse_dates=["Date"])
            if name:
                sub = ens[ens["strategy_name"].eq(name)].set_index("Date").sort_index()
                if not sub.empty:
                    frames["mlx9_ensemble"] = sub["net_return"].rename("mlx9_ensemble")
                    sources["mlx9_ensemble"] = str(ENSEMBLE_RETURNS_IN.relative_to(ROOT))
        except Exception as exc:
            warn(f"Could not load MLX-9 ensemble returns: {exc}", warnings_list)
    if DECISION_SUMMARY_JSON_IN.exists() and DECISION_RETURNS_IN.exists():
        try:
            data = json.loads(DECISION_SUMMARY_JSON_IN.read_text())
            name = data.get("best_validation_model", {}).get("strategy_name")
            dec = pd.read_csv(DECISION_RETURNS_IN, parse_dates=["Date"])
            if name:
                sub = dec[dec["strategy_name"].eq(name)].set_index("Date").sort_index()
                if not sub.empty:
                    frames["mlx12_decision_focused"] = sub["net_return"].rename("mlx12_decision_focused")
                    sources["mlx12_decision_focused"] = str(DECISION_RETURNS_IN.relative_to(ROOT))
        except Exception as exc:
            warn(f"Could not load MLX-12 decision-focused returns: {exc}", warnings_list)
    if not frames:
        raise RuntimeError("No strategy returns were loaded.")
    returns = pd.concat(frames.values(), axis=1).sort_index()
    return returns, sources


def market_state_by_date(features: pd.DataFrame) -> pd.Series:
    state_cols = [c for c in features.columns if c.startswith("market_state_")]
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    if not state_cols:
        return pd.Series("unknown", index=dates)
    state = features[["Date"] + state_cols].drop_duplicates("Date").set_index("Date").reindex(dates)
    labels = state[state_cols].idxmax(axis=1).str.replace("market_state_", "", regex=False)
    labels[state[state_cols].sum(axis=1).fillna(0.0).eq(0.0)] = "unknown"
    return labels.fillna("unknown")


def trailing_return(series: pd.Series, window: int) -> pd.Series:
    return (1.0 + pd.to_numeric(series, errors="coerce")).rolling(window, min_periods=max(2, window // 2)).apply(np.prod, raw=True) - 1.0


def trailing_drawdown(series: pd.Series, window: int = 13) -> pd.Series:
    r = pd.to_numeric(series, errors="coerce").fillna(0.0)
    wealth = (1.0 + r).cumprod()
    peak = wealth.rolling(window, min_periods=2).max()
    return wealth / peak - 1.0


def build_date_features(features: pd.DataFrame, strategy_returns: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    safe_cols = safe_numeric_cols(features)
    grouped = features.groupby("Date", sort=True)
    date_features = pd.DataFrame(index=dates)
    state_cols = [c for c in safe_cols if c.startswith("market_state_")]
    direct_tokens = ("transition", "risk", "regime", "breadth", "pct_", "vix", "fear", "google")
    direct_cols = sorted(set(state_cols + [c for c in safe_cols if any(tok in c.lower() for tok in direct_tokens)]))
    for col in direct_cols:
        date_features[col] = grouped[col].first().reindex(dates)
    agg_tokens = ("trailing_return", "realized_vol", "rolling_sharpe", "rolling_max_drawdown", "drawdown_from", "relative_strength", "beta_to", "corr_to", "cross_sectional")
    agg_cols = [c for c in safe_cols if any(tok in c.lower() for tok in agg_tokens)]
    for col in agg_cols:
        vals = grouped[col]
        date_features[f"xs_mean_{col}"] = vals.mean().reindex(dates)
        date_features[f"xs_std_{col}"] = vals.std().reindex(dates)
    aligned = strategy_returns.reindex(dates)
    for name in [c for c in ["production", "phase4b", "mlx9_ensemble", "mlx5_sequence", "mlx6_transformer", "mlx12_decision_focused", "SPY", "BIL"] if c in aligned.columns]:
        r = pd.to_numeric(aligned[name], errors="coerce")
        date_features[f"{name}_ret_1w"] = r
        date_features[f"{name}_ret_4w"] = trailing_return(r, 4)
        date_features[f"{name}_ret_13w"] = trailing_return(r, 13)
        date_features[f"{name}_vol_13w"] = r.rolling(13, min_periods=6).std(ddof=0) * math.sqrt(52.0)
        date_features[f"{name}_drawdown_13w"] = trailing_drawdown(r, 13)
    feature_cols = [c for c in date_features.columns if not c.lower().startswith(TARGET_LIKE_PREFIXES)]
    date_features = date_features[feature_cols].replace([np.inf, -np.inf], np.nan)
    return date_features, feature_cols


def first_barrier_label(path: pd.Series, upper: float, lower: float) -> tuple[int | float, int | float, str]:
    if path.isna().all() or path.empty:
        return np.nan, np.nan, "missing"
    for step, value in enumerate(path, start=1):
        if pd.isna(value):
            continue
        if value >= upper:
            return 1, step, "upper"
        if value <= lower:
            return -1, step, "lower"
    return 0, int(path.notna().sum()) if path.notna().sum() else np.nan, "vertical"


def build_one_label_series(returns: pd.DataFrame, task: BarrierTask, setting: dict[str, Any]) -> pd.DataFrame:
    horizon = int(setting["horizon_weeks"])
    upper = float(setting["upper_barrier"])
    lower = float(setting["lower_barrier"])
    base = pd.to_numeric(returns[task.base_strategy], errors="coerce")
    compare = pd.to_numeric(returns[task.compare_strategy], errors="coerce") if task.compare_strategy else None
    rows = []
    dates = returns.index
    for i, date in enumerate(dates):
        future = dates[(dates > date)][:horizon]
        if len(future) < horizon:
            rows.append({"Date": date, "label": np.nan, "time_to_barrier": np.nan, "barrier_hit": "insufficient_future", "path_return": np.nan})
            continue
        if task.label_type == "relative":
            base_path = (1.0 + base.reindex(future)).cumprod() - 1.0
            comp_path = (1.0 + compare.reindex(future)).cumprod() - 1.0 if compare is not None else pd.Series(np.nan, index=future)
            path = base_path - comp_path
        else:
            path = (1.0 + base.reindex(future)).cumprod() - 1.0
        label, ttb, barrier = first_barrier_label(path, upper, lower)
        rows.append({"Date": date, "label": label, "time_to_barrier": ttb, "barrier_hit": barrier, "path_return": path.dropna().iloc[-1] if not path.dropna().empty else np.nan})
    return pd.DataFrame(rows)


def create_tasks(strategy_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[list[BarrierTask], list[dict[str, Any]]]:
    skipped = []
    candidates = [
        BarrierTask("task_1_production_triple_barrier", "production", None, "absolute", "Production path-aware risk/return label", "production hit profit barrier first", "production hit loss barrier first"),
        BarrierTask("task_2_phase4b_triple_barrier", "phase4b", None, "absolute", "Phase 4B path-aware risk/return label", "Phase 4B hit profit barrier first", "Phase 4B hit loss barrier first"),
        BarrierTask("task_3_phase4b_vs_production_switch", "phase4b", "production", "relative", "Phase 4B versus production relative path label", "Phase 4B outperformed production by upper barrier first", "Phase 4B underperformed production by lower barrier first"),
        BarrierTask("task_4_mlx9_sleeve_vs_production", "mlx9_ensemble", "production", "relative", "MLX-9 ensemble versus production path label", "MLX-9 outperformed production by upper barrier first", "MLX-9 underperformed production by lower barrier first"),
        BarrierTask("task_5_mlx5_offensive_sleeve_danger", "mlx5_sequence", None, "absolute", "MLX-5 offensive sleeve path danger label", "MLX-5 sleeve hit profit barrier first", "MLX-5 sleeve hit loss barrier first"),
    ]
    tasks = []
    for task in candidates:
        needed = [task.base_strategy] + ([task.compare_strategy] if task.compare_strategy else [])
        missing = [x for x in needed if x not in strategy_returns.columns]
        if missing:
            skipped.append({"task_id": task.task_id, "reason": f"missing strategy returns: {missing}"})
            warn(f"Skipping {task.task_id}; missing strategy returns: {missing}", warnings_list)
        else:
            tasks.append(task)
    return tasks, skipped


def build_labels(tasks: list[BarrierTask], strategy_returns: pd.DataFrame, state: pd.Series) -> pd.DataFrame:
    frames = []
    splits = split_for_dates(strategy_returns.index)
    for task in tasks:
        for setting in BARRIER_SETTINGS:
            df = build_one_label_series(strategy_returns, task, setting)
            df["task_id"] = task.task_id
            df["barrier_id"] = setting["barrier_id"]
            df["horizon_weeks"] = setting["horizon_weeks"]
            df["upper_barrier"] = setting["upper_barrier"]
            df["lower_barrier"] = setting["lower_barrier"]
            df["base_strategy"] = task.base_strategy
            df["compare_strategy"] = task.compare_strategy
            df["label_type"] = task.label_type
            df["split"] = df["Date"].map(splits)
            df["market_state"] = df["Date"].map(state)
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def label_summary(labels: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if labels.empty:
        return pd.DataFrame()
    for keys, group in labels.dropna(subset=["label"]).groupby(["task_id", "barrier_id", "split", "market_state"], dropna=False):
        task_id, barrier_id, split, mstate = keys
        counts = group["label"].value_counts()
        total = int(len(group))
        rows.append(
            {
                "task_id": task_id,
                "barrier_id": barrier_id,
                "split": split,
                "market_state": mstate,
                "n_labels": total,
                "positive_count": int(counts.get(1.0, 0)),
                "neutral_count": int(counts.get(0.0, 0)),
                "negative_count": int(counts.get(-1.0, 0)),
                "positive_rate": float(counts.get(1.0, 0) / total) if total else np.nan,
                "neutral_rate": float(counts.get(0.0, 0) / total) if total else np.nan,
                "negative_rate": float(counts.get(-1.0, 0) / total) if total else np.nan,
                "average_time_to_barrier": float(group["time_to_barrier"].mean()),
                "imbalance_warning": bool(total > 0 and group["label"].value_counts(normalize=True).max() > 0.80),
            }
        )
    return pd.DataFrame(rows)


def sklearn_status() -> tuple[dict[str, bool], list[dict[str, str]]]:
    status = {}
    skipped = []
    for package in ["sklearn", "xgboost", "lightgbm"]:
        available = importlib.util.find_spec(package) is not None
        status[package] = available
        if not available and package != "sklearn":
            skipped.append({"model": package, "reason": "optional package not installed/importable"})
    return status, skipped


def prepare_xy(features: pd.DataFrame, labels: pd.DataFrame, feature_cols: list[str], task_id: str, barrier_id: str) -> pd.DataFrame:
    lab = labels[(labels["task_id"].eq(task_id)) & (labels["barrier_id"].eq(barrier_id))].copy()
    lab = lab.dropna(subset=["label"])
    data = lab.merge(features.reset_index().rename(columns={"index": "Date"}), on="Date", how="left")
    data["class_id"] = data["label"].map({-1.0: 0, 0.0: 1, 1.0: 2}).astype(int)
    return data


def fit_models_for_labels(
    date_features: pd.DataFrame,
    feature_cols: list[str],
    labels: pd.DataFrame,
    sklearn_meta: dict[str, bool],
    warnings_list: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, str]]]:
    try:
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
    except Exception as exc:
        raise RuntimeError(f"scikit-learn is required for MLX-13 model training: {exc}") from exc

    skipped: list[dict[str, str]] = []
    model_specs: list[tuple[str, Any]] = [
        ("logistic_regression", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", LogisticRegression(max_iter=1000, class_weight="balanced", multi_class="auto"))])),
        ("random_forest", Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", RandomForestClassifier(n_estimators=120, max_depth=4, min_samples_leaf=8, random_state=13, class_weight="balanced_subsample", n_jobs=-1))])),
        ("gradient_boosting", Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", GradientBoostingClassifier(n_estimators=80, learning_rate=0.05, max_depth=2, random_state=13))])),
    ]
    if sklearn_meta.get("xgboost"):
        try:
            from xgboost import XGBClassifier

            model_specs.append(("xgboost", Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", XGBClassifier(n_estimators=80, max_depth=2, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, objective="multi:softprob", eval_metric="mlogloss", random_state=13, n_jobs=2))])))
        except Exception as exc:
            skipped.append({"model": "xgboost", "reason": f"import/config failed: {exc}"})
    if sklearn_meta.get("lightgbm"):
        try:
            from lightgbm import LGBMClassifier

            model_specs.append(("lightgbm", Pipeline([("imputer", SimpleImputer(strategy="median")), ("model", LGBMClassifier(n_estimators=80, max_depth=3, learning_rate=0.05, random_state=13, verbose=-1))])))
        except Exception as exc:
            skipped.append({"model": "lightgbm", "reason": f"import/config failed: {exc}"})

    metric_rows = []
    pred_rows = []
    importance_rows = []
    confusion_rows = []
    task_barriers = labels[["task_id", "barrier_id"]].drop_duplicates()
    for _, tb in task_barriers.iterrows():
        task_id = tb["task_id"]
        barrier_id = tb["barrier_id"]
        data = prepare_xy(date_features, labels, feature_cols, task_id, barrier_id)
        if data.empty:
            skipped.append({"task_id": task_id, "barrier_id": barrier_id, "reason": "no labels available"})
            continue
        train = data[data["split"].eq("train")]
        if train["class_id"].nunique() < 2:
            skipped.append({"task_id": task_id, "barrier_id": barrier_id, "reason": "fewer than two train classes"})
            continue
        x_train = train[feature_cols]
        y_train = train["class_id"]
        for model_name, model in model_specs:
            try:
                model.fit(x_train, y_train)
            except Exception as exc:
                skipped.append({"task_id": task_id, "barrier_id": barrier_id, "model": model_name, "reason": f"fit failed: {exc}"})
                continue
            classes = list(getattr(model.named_steps["model"], "classes_", [0, 1, 2]))
            for split in SPLITS:
                sub = data[data["split"].eq(split)].copy()
                if sub.empty:
                    continue
                x = sub[feature_cols]
                y = sub["class_id"].to_numpy()
                pred = model.predict(x)
                if hasattr(model, "predict_proba"):
                    raw_prob = model.predict_proba(x)
                    prob = pd.DataFrame(0.0, index=sub.index, columns=[0, 1, 2])
                    for i, cls in enumerate(classes):
                        if cls in prob.columns:
                            prob[cls] = raw_prob[:, i]
                else:
                    prob = pd.DataFrame(np.nan, index=sub.index, columns=[0, 1, 2])
                auc = np.nan
                try:
                    if len(np.unique(y)) > 1 and prob.notna().all().all():
                        auc = float(roc_auc_score(y, prob[[0, 1, 2]], multi_class="ovr", labels=[0, 1, 2]))
                except Exception:
                    auc = np.nan
                metrics = {
                    "task_id": task_id,
                    "barrier_id": barrier_id,
                    "model_name": model_name,
                    "split": split,
                    "n_obs": int(len(sub)),
                    "accuracy": float(accuracy_score(y, pred)),
                    "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
                    "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
                    "precision_positive": float(precision_score(y, pred, labels=[2], average="macro", zero_division=0)),
                    "recall_positive": float(recall_score(y, pred, labels=[2], average="macro", zero_division=0)),
                    "precision_negative": float(precision_score(y, pred, labels=[0], average="macro", zero_division=0)),
                    "recall_negative": float(recall_score(y, pred, labels=[0], average="macro", zero_division=0)),
                    "roc_auc_ovr": auc,
                    "actual_positive_rate": float((y == 2).mean()),
                    "actual_danger_rate": float((y == 0).mean()),
                    "predicted_positive_rate": float((pred == 2).mean()),
                    "predicted_danger_rate": float((pred == 0).mean()),
                }
                metric_rows.append(metrics)
                cm = confusion_matrix(y, pred, labels=[0, 1, 2])
                for a_i, actual in enumerate([-1, 0, 1]):
                    for p_i, predicted in enumerate([-1, 0, 1]):
                        confusion_rows.append({"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "split": split, "actual_label": actual, "predicted_label": predicted, "count": int(cm[a_i, p_i])})
                for date, actual, pred_cls, (_, prow) in zip(sub["Date"], sub["label"], pred, prob.iterrows()):
                    pred_rows.append(
                        {
                            "Date": date,
                            "task_id": task_id,
                            "barrier_id": barrier_id,
                            "model_name": model_name,
                            "split": split,
                            "actual_label": int(actual),
                            "predicted_label": {-1: -1, 0: -1, 1: 0, 2: 1}.get(int(pred_cls), np.nan),
                            "prob_down": float(prow[0]),
                            "prob_neutral": float(prow[1]),
                            "prob_up": float(prow[2]),
                            "confidence": float(np.nanmax([prow[0], prow[1], prow[2]])),
                            "entropy": float(-np.nansum([p * math.log(max(p, 1e-12)) for p in [prow[0], prow[1], prow[2]]])),
                        }
                    )
            fitted = model.named_steps["model"]
            if hasattr(fitted, "feature_importances_"):
                vals = fitted.feature_importances_
            elif hasattr(fitted, "coef_"):
                vals = np.mean(np.abs(fitted.coef_), axis=0)
            else:
                vals = np.zeros(len(feature_cols))
            top_idx = np.argsort(vals)[::-1][:30]
            for rank, idx in enumerate(top_idx, start=1):
                importance_rows.append({"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "feature": feature_cols[idx], "importance": float(vals[idx]), "rank": rank})
    return pd.DataFrame(metric_rows), pd.DataFrame(pred_rows), pd.DataFrame(importance_rows), pd.DataFrame(confusion_rows), skipped


def max_drawdown(returns: pd.Series) -> float:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {"annual_return": np.nan, "annual_volatility": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "calmar": np.nan, "cvar_5": np.nan, "average_turnover": np.nan, "annual_cost_drag": np.nan, "average_bil_exposure": np.nan, "average_core_exposure": np.nan, "average_ml_sleeve_exposure": np.nan, "active_weeks": 0}
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
        "average_core_exposure": float(path.get("core_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_ml_sleeve_exposure": float(path.get("ml_sleeve_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def make_weighted_path(name: str, returns: pd.DataFrame, weights: pd.DataFrame, family: str, meta: dict[str, Any]) -> pd.DataFrame:
    weights = weights.reindex(returns.index).fillna(0.0)
    gross = weights.mul(returns.reindex(weights.index).fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover * (DEFAULT_COST_BPS / 10000.0)
    out = pd.DataFrame(
        {
            "Date": weights.index,
            "gross_return": gross,
            "net_return": gross - cost,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": weights["BIL"] if "BIL" in weights.columns else 0.0,
            "core_exposure": weights[["production", "phase4b"]].sum(axis=1) if {"production", "phase4b"}.issubset(weights.columns) else np.nan,
            "ml_sleeve_exposure": weights[[c for c in weights.columns if c.startswith("mlx")]].sum(axis=1) if any(c.startswith("mlx") for c in weights.columns) else 0.0,
            "strategy_name": name,
            "strategy_family": family,
            **meta,
        }
    )
    out["split"] = split_for_dates(out["Date"]).values
    return out


def simulate_strategies(predictions: pd.DataFrame, strategy_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    returns_frames = []
    thresholds = THRESHOLDS
    for (task_id, barrier_id, model_name), pred in predictions.groupby(["task_id", "barrier_id", "model_name"], sort=False):
        p = pred.set_index("Date").sort_index()
        common = strategy_returns.index.intersection(p.index)
        if common.empty:
            continue
        p = p.reindex(common)
        ret = strategy_returns.reindex(common)
        for thr in thresholds:
            if task_id == "task_1_production_triple_barrier" and {"production", "BIL"}.issubset(ret.columns):
                w = pd.DataFrame(0.0, index=common, columns=ret.columns)
                danger = p["prob_down"] > thr
                w.loc[~danger, "production"] = 1.0
                w.loc[danger, "BIL"] = 1.0
                name = f"{task_id}__{barrier_id}__{model_name}__thr{thr:.2f}__production_risk_filter"
                returns_frames.append(make_weighted_path(name, ret, w, "production_risk_filter", {"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "threshold": thr}))
            if task_id == "task_3_phase4b_vs_production_switch" and {"production", "phase4b"}.issubset(ret.columns):
                w = pd.DataFrame(0.0, index=common, columns=ret.columns)
                use_phase = p["prob_up"] > thr
                w.loc[use_phase, "phase4b"] = 1.0
                w.loc[~use_phase, "production"] = 1.0
                name = f"{task_id}__{barrier_id}__{model_name}__thr{thr:.2f}__phase4b_switch"
                returns_frames.append(make_weighted_path(name, ret, w, "phase4b_switch", {"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "threshold": thr}))
            if task_id == "task_2_phase4b_triple_barrier" and {"production", "phase4b", "BIL"}.issubset(ret.columns):
                w = pd.DataFrame(0.0, index=common, columns=ret.columns)
                danger = p["prob_down"] > thr
                w.loc[~danger, "phase4b"] = 1.0
                w.loc[danger, "production"] = 0.50
                w.loc[danger, "BIL"] = 0.50
                name = f"{task_id}__{barrier_id}__{model_name}__thr{thr:.2f}__phase4b_danger_override"
                returns_frames.append(make_weighted_path(name, ret, w, "phase4b_danger_override", {"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "threshold": thr}))
            if task_id == "task_4_mlx9_sleeve_vs_production" and {"production", "mlx9_ensemble"}.issubset(ret.columns):
                w = pd.DataFrame(0.0, index=common, columns=ret.columns)
                active = p["prob_up"] > thr
                w["production"] = 1.0
                w.loc[active, "production"] = 0.90
                w.loc[active, "mlx9_ensemble"] = 0.10
                name = f"{task_id}__{barrier_id}__{model_name}__thr{thr:.2f}__mlx9_sleeve_activation"
                returns_frames.append(make_weighted_path(name, ret, w, "mlx9_sleeve_activation", {"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "threshold": thr}))
            if task_id == "task_5_mlx5_offensive_sleeve_danger" and {"mlx5_sequence", "BIL"}.issubset(ret.columns):
                w = pd.DataFrame(0.0, index=common, columns=ret.columns)
                danger = p["prob_down"] > thr
                w.loc[~danger, "mlx5_sequence"] = 1.0
                w.loc[danger, "mlx5_sequence"] = 0.25
                w.loc[danger, "BIL"] = 0.75
                name = f"{task_id}__{barrier_id}__{model_name}__thr{thr:.2f}__mlx5_bad_path_avoidance"
                returns_frames.append(make_weighted_path(name, ret, w, "mlx5_bad_path_avoidance", {"task_id": task_id, "barrier_id": barrier_id, "model_name": model_name, "threshold": thr}))
    returns_df = pd.concat(returns_frames, ignore_index=True) if returns_frames else pd.DataFrame()
    if returns_df.empty:
        warn("No triple-barrier strategies were simulated.", warnings_list)
        return returns_df, pd.DataFrame()
    summary_rows = []
    for (strategy, split), group in returns_df.groupby(["strategy_name", "split"], dropna=False):
        metrics = calc_metrics(group.set_index("Date"))
        first = group.iloc[0].to_dict()
        metrics.update({k: first.get(k) for k in ["strategy_name", "strategy_family", "task_id", "barrier_id", "model_name", "threshold"]})
        metrics["split"] = split
        summary_rows.append(metrics)
    summary = pd.DataFrame(summary_rows)
    for name in ["production", "official_shadow", "phase4b", "phase6", "phase7", "mlx5_sequence", "mlx6_transformer", "mlx9_ensemble", "mlx12_decision_focused", "SPY", "sixty_forty", "simple_momentum"]:
        if name not in strategy_returns.columns:
            continue
        frame = pd.DataFrame({"Date": strategy_returns.index, "net_return": strategy_returns[name], "gross_return": strategy_returns[name], "turnover": np.nan, "cost": 0.0, "bil_weight": 0.0, "core_exposure": np.nan, "ml_sleeve_exposure": np.nan, "strategy_name": name, "strategy_family": "benchmark", "task_id": "benchmark", "barrier_id": "benchmark", "model_name": "benchmark", "threshold": np.nan})
        frame["split"] = split_for_dates(frame["Date"]).values
        returns_df = pd.concat([returns_df, frame], ignore_index=True)
        for split, group in frame.groupby("split"):
            metrics = calc_metrics(group.set_index("Date"))
            metrics.update({"strategy_name": name, "strategy_family": "benchmark", "task_id": "benchmark", "barrier_id": "benchmark", "model_name": "benchmark", "threshold": np.nan, "split": split})
            summary_rows.append(metrics)
    return returns_df, pd.DataFrame(summary_rows)


def psi(train: pd.Series, test: pd.Series, bins: int = 10) -> float:
    tr = pd.to_numeric(train, errors="coerce").dropna()
    te = pd.to_numeric(test, errors="coerce").dropna()
    if len(tr) < 20 or len(te) < 20:
        return np.nan
    edges = np.unique(np.nanquantile(tr, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return np.nan
    tr_counts = np.histogram(tr, bins=edges)[0] / max(len(tr), 1)
    te_counts = np.histogram(te, bins=edges)[0] / max(len(te), 1)
    tr_counts = np.clip(tr_counts, 1e-6, None)
    te_counts = np.clip(te_counts, 1e-6, None)
    return float(np.sum((te_counts - tr_counts) * np.log(te_counts / tr_counts)))


def feature_drift(date_features: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    splits = split_for_dates(date_features.index)
    train = date_features[splits.eq("train")]
    rows = []
    for col in feature_cols:
        tr = pd.to_numeric(train[col], errors="coerce")
        tr_mean = tr.mean()
        tr_std = tr.std(ddof=0)
        for split in ("validation", "holdout"):
            sub = pd.to_numeric(date_features.loc[splits.eq(split), col], errors="coerce")
            rows.append(
                {
                    "feature": col,
                    "split": split,
                    "train_mean": float(tr_mean) if pd.notna(tr_mean) else np.nan,
                    "split_mean": float(sub.mean()) if len(sub) else np.nan,
                    "train_std": float(tr_std) if pd.notna(tr_std) else np.nan,
                    "split_std": float(sub.std(ddof=0)) if len(sub) else np.nan,
                    "z_shift": float((sub.mean() - tr_mean) / tr_std) if pd.notna(tr_std) and tr_std > 0 else np.nan,
                    "abs_z_shift": abs(float((sub.mean() - tr_mean) / tr_std)) if pd.notna(tr_std) and tr_std > 0 else np.nan,
                    "psi": psi(tr, sub),
                    "missing_rate_train": float(tr.isna().mean()),
                    "missing_rate_split": float(sub.isna().mean()) if len(sub) else np.nan,
                }
            )
    return pd.DataFrame(rows).sort_values(["abs_z_shift", "psi"], ascending=[False, False])


def prediction_drift(predictions: pd.DataFrame, state: pd.Series) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame()
    p = predictions.copy()
    p["year"] = pd.to_datetime(p["Date"]).dt.year
    p["market_state"] = p["Date"].map(state)
    rows = []
    for keys, group in p.groupby(["task_id", "barrier_id", "model_name", "split", "year", "market_state"], dropna=False):
        task_id, barrier_id, model_name, split, year, mstate = keys
        rows.append(
            {
                "task_id": task_id,
                "barrier_id": barrier_id,
                "model_name": model_name,
                "split": split,
                "year": year,
                "market_state": mstate,
                "n": int(len(group)),
                "mean_probability_up": float(group["prob_up"].mean()),
                "mean_probability_down": float(group["prob_down"].mean()),
                "predicted_positive_rate": float((group["predicted_label"] == 1).mean()),
                "predicted_danger_rate": float((group["predicted_label"] == -1).mean()),
                "mean_confidence": float(group["confidence"].mean()),
                "mean_entropy": float(group["entropy"].mean()),
            }
        )
    return pd.DataFrame(rows)


def strategy_behavior_drift(returns_df: pd.DataFrame, focus: list[str], state: pd.Series) -> pd.DataFrame:
    if returns_df.empty:
        return pd.DataFrame()
    df = returns_df[returns_df["strategy_name"].isin(focus)].copy()
    df["year"] = pd.to_datetime(df["Date"]).dt.year
    df["market_state"] = df["Date"].map(state)
    rows = []
    for keys, group in df.groupby(["strategy_name", "split", "year", "market_state"], dropna=False):
        strategy, split, year, mstate = keys
        rows.append(
            {
                "strategy_name": strategy,
                "split": split,
                "year": year,
                "market_state": mstate,
                "n": int(len(group)),
                "mean_turnover": float(group["turnover"].mean()),
                "mean_bil_exposure": float(group["bil_weight"].mean()),
                "mean_core_exposure": float(group["core_exposure"].mean()),
                "mean_ml_sleeve_exposure": float(group["ml_sleeve_exposure"].mean()),
                "mean_net_return": float(group["net_return"].mean()),
            }
        )
    return pd.DataFrame(rows)


def performance_drift(returns_df: pd.DataFrame, focus: list[str]) -> pd.DataFrame:
    windows = {
        "2017_2018": (pd.Timestamp("2017-01-01"), pd.Timestamp("2018-12-31")),
        "2019_2020": (pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-31")),
        "2021_2022": (pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-31")),
        "2023_2026": (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
    }
    rows = []
    for strategy in focus:
        path = returns_df[returns_df["strategy_name"].eq(strategy)].set_index("Date").sort_index()
        for window, (start, end) in windows.items():
            sub = path.loc[(path.index >= start) & (path.index <= end)]
            metrics = calc_metrics(sub)
            metrics.update({"strategy_name": strategy, "window": window})
            rows.append(metrics)
    return pd.DataFrame(rows)


def best_row(summary: pd.DataFrame, split: str, family_filter: str | None = None) -> dict[str, Any]:
    sub = summary[(summary["split"].eq(split)) & (summary["active_weeks"].ge(50))].copy()
    if family_filter:
        sub = sub[sub["strategy_family"].eq(family_filter)]
    else:
        sub = sub[~sub["strategy_family"].eq("benchmark")]
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "max_drawdown", "cvar_5", "annual_return"], ascending=[False, False, False, False]).iloc[0].to_dict()


def comp_value(summary: pd.DataFrame, strategy: str, metric: str) -> float:
    sub = summary[(summary["strategy_name"].eq(strategy)) & (summary["split"].eq("holdout"))]
    if sub.empty or metric not in sub.columns:
        return np.nan
    value = sub.iloc[0][metric]
    return float(value) if pd.notna(value) else np.nan


def choose_recommendation(selected: dict[str, Any], summary: pd.DataFrame, drift_feature: pd.DataFrame) -> str:
    if not selected:
        return "KEEP AS RESEARCH ONLY"
    sharpe = float(selected.get("sharpe", np.nan))
    prod = comp_value(summary, "production", "sharpe")
    phase4b = comp_value(summary, "phase4b", "sharpe")
    drift_count = int((drift_feature["abs_z_shift"] > 1.0).sum()) if not drift_feature.empty and "abs_z_shift" in drift_feature.columns else 0
    if pd.notna(sharpe) and pd.notna(prod) and sharpe > prod and pd.notna(phase4b) and sharpe > phase4b and drift_count < 20:
        return "PROMISING FILTER BUT NEEDS WALK-FORWARD"
    if pd.notna(sharpe) and pd.notna(prod) and sharpe > prod:
        return "KEEP AS ML SHADOW MONITOR"
    return "USE LABELS FOR MLX-12B OBJECTIVE DESIGN"


def write_notes(
    task_defs: dict[str, Any],
    skipped: list[dict[str, Any]],
    label_sum: pd.DataFrame,
    metrics: pd.DataFrame,
    confusion: pd.DataFrame,
    importance: pd.DataFrame,
    strategy_summary: pd.DataFrame,
    drift_feature: pd.DataFrame,
    drift_prediction: pd.DataFrame,
    drift_behavior: pd.DataFrame,
    drift_performance: pd.DataFrame,
    summary_json: dict[str, Any],
    warnings_list: list[str],
) -> None:
    best_val = summary_json.get("best_validation_strategy", {})
    selected_hold = summary_json.get("validation_selected_holdout", {})
    best_hold = summary_json.get("best_holdout_diagnostic_strategy", {})
    notes = f"""# Phase MLX Triple-Barrier Meta-Labeling and Drift Notes

## Research-Only Warning

Phase MLX triple-barrier meta-labeling is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Triple-barrier labeling is a path-aware way to define financial outcomes. Instead of labeling a date only by the return at a fixed endpoint, it asks which event happened first: an upper profit barrier, a lower loss/risk barrier, or a vertical time barrier.

Path-aware labels matter because finance is path-dependent. A strategy that ends four weeks up may still have hit an unacceptable loss first. A strategy that ends flat may have offered a clean profit-taking opportunity along the way. Triple-barrier labels try to preserve that information.

Meta-labeling means using ML as a second-stage decision filter around an existing strategy. The model is not asked to invent the whole portfolio. It is asked questions such as: should production take risk, should Phase 4B replace production, should an ML sleeve be active, or should an offensive sleeve be reduced?

Fixed-horizon labels such as `forward_return_4w` can fail because they ignore stops, drawdowns, volatility, and path quality. Triple-barrier labels differ by encoding the first barrier hit over the future path. This connects to Marcos Lopez de Prado's financial ML framework: first define events and barriers, then train labels that match the trading decision.

Label design is part of the ML objective. If the label only rewards endpoint return, the model learns endpoint return. If the label rewards hitting a profit barrier before a loss barrier, the model learns something closer to path quality. In this ETF project, that matters because the real decision is not prediction accuracy; it is when to trust production, Phase 4B, or an ML sleeve.

## EECS 127 / Optimization Connection

Optimization starts by defining an objective function and feasible set. In portfolio ML, the objective might be return, Sharpe, drawdown control, CVaR, turnover, or a weighted combination. The feasible decisions might be long-only weights, risk limits, BIL fallback, or rules about when an ML sleeve is allowed to activate.

Constraints shape behavior. A filter creates a constraint on when a strategy can take risk. A probability threshold is a decision boundary. Turnover, volatility, and downside penalties are tradeoffs, just like penalty terms in constrained optimization.

MLX-12 showed the danger of optimizing the wrong objective too directly: a Sharpe-like objective found a trivial feasible solution by hiding in BIL/bonds. That was mathematically coherent but not the desired offensive alpha behavior. MLX-13 improves the problem definition before future optimization by changing the labels from endpoint returns to path-aware barrier outcomes.

This is very EECS 127: before solving, define the right objective, constraints, and feasible set. Bad problem formulation gives a bad optimum, even if the solver works perfectly.

## Technical Setup

- Tasks labeled: {list(task_defs.keys())}
- Barrier settings: {BARRIER_SETTINGS}
- Models run: {summary_json.get('models_run')}
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward
- Leakage controls: features are known at date `t`; labels use future paths only as targets; forward-return target columns are excluded from features
- Skipped tasks/models: {skipped}

## Label Analysis

{markdown_table(label_sum.sort_values(['task_id', 'barrier_id', 'split', 'market_state']), ['task_id', 'barrier_id', 'split', 'market_state', 'n_labels', 'positive_rate', 'neutral_rate', 'negative_rate', 'average_time_to_barrier', 'imbalance_warning'], 40)}

## Model Results

### Best Classification Rows

{markdown_table(metrics[metrics['split'].eq('validation')].sort_values(['macro_f1', 'balanced_accuracy'], ascending=[False, False]), ['task_id', 'barrier_id', 'model_name', 'split', 'accuracy', 'balanced_accuracy', 'macro_f1', 'precision_positive', 'recall_positive', 'precision_negative', 'recall_negative', 'predicted_positive_rate', 'predicted_danger_rate'], 25)}

### Confusion Matrix Sample

{markdown_table(confusion.head(30), ['task_id', 'barrier_id', 'model_name', 'split', 'actual_label', 'predicted_label', 'count'], 30)}

### Feature Importance Sample

{markdown_table(importance.sort_values('importance', ascending=False), ['task_id', 'barrier_id', 'model_name', 'feature', 'importance', 'rank'], 30)}

## Strategy Results

- Best validation-selected strategy: `{best_val.get('strategy_name', 'n/a')}`
- Validation-selected holdout annual return: {pct(selected_hold.get('annual_return'))}
- Validation-selected holdout Sharpe: {num(selected_hold.get('sharpe'))}
- Validation-selected max drawdown: {pct(selected_hold.get('max_drawdown'))}
- Validation-selected CVaR 5%: {pct(selected_hold.get('cvar_5'))}
- Best holdout-diagnostic strategy: `{best_hold.get('strategy_name', 'n/a')}` with Sharpe {num(best_hold.get('sharpe'))}

{markdown_table(strategy_summary[strategy_summary['split'].eq('holdout')].sort_values(['sharpe', 'annual_return'], ascending=[False, False]), ['strategy_name', 'strategy_family', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_turnover', 'average_bil_exposure', 'average_ml_sleeve_exposure'], 30)}

## Drift Monitoring

### Feature Drift

{markdown_table(drift_feature, ['feature', 'split', 'train_mean', 'split_mean', 'z_shift', 'abs_z_shift', 'psi', 'missing_rate_train', 'missing_rate_split'], 25)}

### Prediction Drift

{markdown_table(drift_prediction, ['task_id', 'barrier_id', 'model_name', 'split', 'year', 'market_state', 'mean_probability_up', 'mean_probability_down', 'predicted_positive_rate', 'predicted_danger_rate', 'mean_confidence', 'mean_entropy'], 35)}

### Strategy Behavior Drift

{markdown_table(drift_behavior, ['strategy_name', 'split', 'year', 'market_state', 'mean_turnover', 'mean_bil_exposure', 'mean_core_exposure', 'mean_ml_sleeve_exposure', 'mean_net_return'], 35)}

### Performance Drift

{markdown_table(drift_performance, ['strategy_name', 'window', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'active_weeks'], 40)}

## Interpretation

- Did triple-barrier labels improve meta-labeling? {summary_json.get('triple_barrier_helped')}
- Did the validation-selected filter beat production by holdout Sharpe? {summary_json.get('validation_selected_beats_production_sharpe')}
- Did it beat Phase 4B by holdout Sharpe? {summary_json.get('validation_selected_beats_phase4b_sharpe')}
- Did drift monitoring flag feature shifts? {summary_json.get('feature_drift_warning')}
- Final recommendation: **{summary_json.get('final_recommendation')}**

These labels are useful for future MLX-12B objective design because they make the target path-aware before optimizing a portfolio loss. This remains research-only until it passes stricter walk-forward, PIT data, and monitoring tests.

## Warnings

{chr(10).join(f'- {w}' for w in warnings_list)}
"""
    NOTES_OUT.write_text(notes)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    warn("Experimental research-only Phase MLX output; not production-valid.", warnings_list)
    warn("Triple-barrier labels use future paths only as targets; results remain high overfitting risk.", warnings_list)
    features, targets, weekly = load_inputs(warnings_list)
    strategy_returns, strategy_sources = load_strategy_returns(weekly, warnings_list)
    state = market_state_by_date(features).reindex(strategy_returns.index).fillna("unknown")
    date_features, feature_cols = build_date_features(features, strategy_returns)
    date_features = date_features.reindex(strategy_returns.index)
    tasks, skipped_tasks = create_tasks(strategy_returns, warnings_list)
    labels = build_labels(tasks, strategy_returns, state)
    label_sum = label_summary(labels)
    sklearn_meta, skipped_models = sklearn_status()
    model_metrics, predictions, importance, confusion, model_skips = fit_models_for_labels(date_features, feature_cols, labels, sklearn_meta, warnings_list)
    skipped_all = skipped_tasks + skipped_models + model_skips
    strategy_returns_df, strategy_summary = simulate_strategies(predictions, strategy_returns, warnings_list)
    best_val = best_row(strategy_summary, "validation") if not strategy_summary.empty else {}
    selected_holdout = {}
    if best_val:
        sub = strategy_summary[(strategy_summary["split"].eq("holdout")) & (strategy_summary["strategy_name"].eq(best_val["strategy_name"]))]
        selected_holdout = sub.iloc[0].to_dict() if not sub.empty else {}
    best_holdout = best_row(strategy_summary, "holdout") if not strategy_summary.empty else {}
    focus = sorted(set([best_val.get("strategy_name"), best_holdout.get("strategy_name"), "production", "phase4b", "mlx9_ensemble", "mlx12_decision_focused"]) - {None, ""})
    drift_feature = feature_drift(date_features, feature_cols)
    drift_prediction = prediction_drift(predictions, state)
    drift_behavior = strategy_behavior_drift(strategy_returns_df, focus, state)
    drift_perf = performance_drift(strategy_returns_df, focus)
    task_defs = {
        task.task_id: {
            "base_strategy": task.base_strategy,
            "compare_strategy": task.compare_strategy,
            "label_type": task.label_type,
            "description": task.description,
            "positive_meaning": task.positive_meaning,
            "negative_meaning": task.negative_meaning,
        }
        for task in tasks
    }
    selected_sharpe = selected_holdout.get("sharpe", np.nan)
    summary_json = {
        "phase": "triple_barrier_meta_labeling_and_drift",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "strategy_sources": strategy_sources,
        "tasks_created": list(task_defs.keys()),
        "barrier_settings": BARRIER_SETTINGS,
        "models_run": sorted(model_metrics["model_name"].dropna().unique().tolist()) if not model_metrics.empty else [],
        "sklearn_status": sklearn_meta,
        "skipped_tasks_models": skipped_all,
        "best_validation_strategy": best_val,
        "validation_selected_holdout": selected_holdout,
        "best_holdout_diagnostic_strategy": best_holdout,
        "validation_selected_beats_production_sharpe": bool(pd.notna(selected_sharpe) and selected_sharpe > comp_value(strategy_summary, "production", "sharpe")),
        "validation_selected_beats_phase4b_sharpe": bool(pd.notna(selected_sharpe) and selected_sharpe > comp_value(strategy_summary, "phase4b", "sharpe")),
        "validation_selected_beats_mlx9_sharpe": bool(pd.notna(selected_sharpe) and selected_sharpe > comp_value(strategy_summary, "mlx9_ensemble", "sharpe")),
        "validation_selected_beats_mlx12_sharpe": bool(pd.notna(selected_sharpe) and selected_sharpe > comp_value(strategy_summary, "mlx12_decision_focused", "sharpe")),
        "triple_barrier_helped": bool(pd.notna(selected_sharpe) and selected_sharpe > comp_value(strategy_summary, "production", "sharpe")),
        "feature_drift_warning": bool((drift_feature["abs_z_shift"] > 1.0).sum() > 20) if not drift_feature.empty else False,
        "top_feature_drift": drift_feature.head(20).to_dict(orient="records") if not drift_feature.empty else [],
        "final_recommendation": choose_recommendation(selected_holdout, strategy_summary, drift_feature),
        "warnings": warnings_list + ["No triple-barrier model or filter is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "labels": str(LABELS_OUT.relative_to(ROOT)),
            "label_summary": str(LABEL_SUMMARY_OUT.relative_to(ROOT)),
            "model_metrics": str(MODEL_METRICS_OUT.relative_to(ROOT)),
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "strategy_returns": str(STRATEGY_RETURNS_OUT.relative_to(ROOT)),
            "strategy_summary": str(STRATEGY_SUMMARY_OUT.relative_to(ROOT)),
            "feature_importance": str(FEATURE_IMPORTANCE_OUT.relative_to(ROOT)),
            "confusion_matrices": str(CONFUSION_OUT.relative_to(ROOT)),
            "drift_feature_summary": str(DRIFT_FEATURE_OUT.relative_to(ROOT)),
            "drift_prediction_summary": str(DRIFT_PREDICTION_OUT.relative_to(ROOT)),
            "drift_strategy_behavior_summary": str(DRIFT_BEHAVIOR_OUT.relative_to(ROOT)),
            "drift_performance_summary": str(DRIFT_PERFORMANCE_OUT.relative_to(ROOT)),
            "task_definitions": str(TASK_DEFINITIONS_OUT.relative_to(ROOT)),
            "skipped_tasks": str(SKIPPED_TASKS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }
    labels.to_parquet(LABELS_OUT, index=False)
    label_sum.to_csv(LABEL_SUMMARY_OUT, index=False)
    model_metrics.to_csv(MODEL_METRICS_OUT, index=False)
    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    strategy_returns_df.to_csv(STRATEGY_RETURNS_OUT, index=False)
    strategy_summary.to_csv(STRATEGY_SUMMARY_OUT, index=False)
    importance.to_csv(FEATURE_IMPORTANCE_OUT, index=False)
    confusion.to_csv(CONFUSION_OUT, index=False)
    drift_feature.to_csv(DRIFT_FEATURE_OUT, index=False)
    drift_prediction.to_csv(DRIFT_PREDICTION_OUT, index=False)
    drift_behavior.to_csv(DRIFT_BEHAVIOR_OUT, index=False)
    drift_perf.to_csv(DRIFT_PERFORMANCE_OUT, index=False)
    TASK_DEFINITIONS_OUT.write_text(json.dumps(task_defs, indent=2, default=json_default))
    SKIPPED_TASKS_OUT.write_text(json.dumps(skipped_all, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(task_defs, skipped_all, label_sum, model_metrics, confusion, importance, strategy_summary, drift_feature, drift_prediction, drift_behavior, drift_perf, summary_json, summary_json["warnings"])
    print("Phase MLX triple-barrier meta-labeling and drift monitoring")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Tasks created: {list(task_defs.keys())}")
    print(f"Barrier settings: {BARRIER_SETTINGS}")
    print(f"Models run: {summary_json['models_run']}")
    print(f"Best validation strategy: {best_val.get('strategy_name') if best_val else 'n/a'}")
    print(f"Validation-selected holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Best holdout diagnostic strategy: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Best holdout diagnostic Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Final recommendation: {summary_json['final_recommendation']}")
    print("Outputs:")
    for path in [LABELS_OUT, LABEL_SUMMARY_OUT, MODEL_METRICS_OUT, PREDICTIONS_OUT, STRATEGY_RETURNS_OUT, STRATEGY_SUMMARY_OUT, FEATURE_IMPORTANCE_OUT, CONFUSION_OUT, DRIFT_FEATURE_OUT, DRIFT_PREDICTION_OUT, DRIFT_BEHAVIOR_OUT, DRIFT_PERFORMANCE_OUT, TASK_DEFINITIONS_OUT, SKIPPED_TASKS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
