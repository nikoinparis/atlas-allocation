#!/usr/bin/env python3
"""
Phase MLX-7: meta-labeling / second-stage filters.

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
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
SEQUENCE_DIR = ROOT / "data" / "research" / "ml_lab" / "sequence_models"
TRANSFORMER_DIR = ROOT / "data" / "research" / "ml_lab" / "transformers"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "meta_labeling"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
SEQUENCE_BACKTEST_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_PREDICTIONS_IN = SEQUENCE_DIR / "sequence_predictions.parquet"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
MLX5C_SUMMARY_IN = SEQUENCE_DIR / "multiseed_walkforward" / "sequence_multiseed_summary.json"
TRANSFORMER_BACKTEST_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_PREDICTIONS_IN = TRANSFORMER_DIR / "transformer_predictions.parquet"
TRANSFORMER_SUMMARY_JSON_IN = TRANSFORMER_DIR / "transformer_summary.json"

DATASETS_OUT = OUTPUT_DIR / "meta_label_datasets.parquet"
PREDICTIONS_OUT = OUTPUT_DIR / "meta_label_predictions.parquet"
MODEL_METRICS_OUT = OUTPUT_DIR / "meta_label_model_metrics.csv"
STRATEGY_RETURNS_OUT = OUTPUT_DIR / "meta_label_strategy_returns.csv"
STRATEGY_SUMMARY_OUT = OUTPUT_DIR / "meta_label_strategy_summary.csv"
FEATURE_IMPORTANCE_OUT = OUTPUT_DIR / "meta_label_feature_importance.csv"
TASK_DEFINITIONS_OUT = OUTPUT_DIR / "meta_label_task_definitions.json"
SKIPPED_TASKS_OUT = OUTPUT_DIR / "meta_label_skipped_tasks.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "meta_label_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_meta_labeling_notes.md"

DEFAULT_COST_BPS = 10.0
TARGET_LIKE_PREFIXES = ("forward_", "future_", "next_", "beats_", "top_quintile", "positive_forward")
SPLITS = ("train", "validation", "holdout")


@dataclass(frozen=True)
class MetaTask:
    task_id: str
    label_col: str
    label_positive_meaning: str
    purpose: str
    strategy_family: str


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


def split_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
    s = pd.Series(pd.to_datetime(dates), index=getattr(dates, "index", None))
    out = pd.Series("unassigned", index=s.index, dtype="object")
    out.loc[s <= pd.Timestamp("2017-12-31")] = "train"
    out.loc[(s >= pd.Timestamp("2018-01-01")) & (s <= pd.Timestamp("2019-12-31"))] = "validation"
    out.loc[s >= pd.Timestamp("2020-01-01")] = "holdout"
    return out


def load_inputs(mlx5: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-7 inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    mlx5.validate_inputs(features, targets)
    weekly_returns = mlx5.load_panel_csv(WEEKLY_RETURNS_IN)
    return features, targets, weekly_returns


def future_4w_return(returns: pd.Series) -> pd.Series:
    legs = [(1.0 + pd.to_numeric(returns, errors="coerce")).shift(-i) for i in range(1, 5)]
    return pd.concat(legs, axis=1).prod(axis=1, min_count=4) - 1.0


def trailing_drawdown(returns: pd.Series, window: int = 13) -> pd.Series:
    r = pd.to_numeric(returns, errors="coerce").fillna(0.0)
    wealth = (1.0 + r).cumprod()
    rolling_peak = wealth.rolling(window, min_periods=2).max()
    return wealth / rolling_peak - 1.0


def max_drawdown(returns: pd.Series) -> float:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calc_metrics(path: pd.DataFrame) -> dict[str, Any]:
    r = pd.to_numeric(path.get("net_return", pd.Series(dtype=float)), errors="coerce").dropna()
    if r.empty:
        return {"annual_return": np.nan, "annual_volatility": np.nan, "sharpe": np.nan, "max_drawdown": np.nan, "calmar": np.nan, "cvar_5": np.nan, "average_turnover": np.nan, "annual_cost_drag": np.nan, "average_bil_weight": np.nan, "average_ml_sleeve_exposure": np.nan, "active_weeks": 0}
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
        "average_bil_weight": float(path.get("bil_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_ml_sleeve_exposure": float(path.get("ml_sleeve_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "active_weeks": int(len(r)),
    }


def read_return_frame(mlx5: Any, path: Path, name: str, warnings_list: list[str]) -> pd.DataFrame:
    try:
        out = mlx5.read_project_return_file(path)
        return out
    except Exception as exc:
        warn(f"Could not read return file for {name}: {path}: {exc}", warnings_list)
        return pd.DataFrame()


def select_project_strategy_files(mlx5: Any, warnings_list: list[str]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    fixed = {
        "production": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_regime_confidence_boost.csv",
        "official_shadow": ROOT / "data" / "05_layer3_portfolio_construction" / "portfolio_version_returns_improved_phase2b_combo_abc.csv",
    }
    for name, path in fixed.items():
        if path.exists():
            selected[name] = path
        else:
            warn(f"Required project strategy file missing for {name}: {path}", warnings_list)
    if SEQUENCE_PROJECT_COMPARISON_IN.exists():
        comp = pd.read_csv(SEQUENCE_PROJECT_COMPARISON_IN)
        for category, alias in [("phase4b", "phase4b"), ("phase6", "phase6"), ("phase7", "phase7")]:
            sub = comp[comp["category"].eq(category)] if "category" in comp.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No MLX project comparison row found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
            path = ROOT / str(row["source_path"])
            if path.exists():
                selected[alias] = path
            else:
                warn(f"Selected project strategy file missing for {category}: {path}", warnings_list)
    else:
        warn("MLX sequence project comparison file missing; Phase 4B/6/7 selection may be incomplete.", warnings_list)
    return selected


def load_strategy_returns(mlx5: Any, weekly_returns: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str]]:
    returns: dict[str, pd.Series] = {}
    sources: dict[str, str] = {}
    project_files = select_project_strategy_files(mlx5, warnings_list)
    for name, path in project_files.items():
        frame = read_return_frame(mlx5, path, name, warnings_list)
        if not frame.empty:
            returns[name] = frame["net_return"].rename(name)
            sources[name] = str(path.relative_to(ROOT))

    if "BIL" in weekly_returns.columns:
        returns["BIL"] = weekly_returns["BIL"].rename("BIL")
        sources["BIL"] = str(WEEKLY_RETURNS_IN.relative_to(ROOT))
    else:
        warn("BIL returns missing; cash/BIL labels and filters may be skipped.", warnings_list)
    if "SPY" in weekly_returns.columns:
        returns["SPY"] = weekly_returns["SPY"].rename("SPY")
        sources["SPY"] = str(WEEKLY_RETURNS_IN.relative_to(ROOT))
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond:
        returns["sixty_forty"] = (0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]).rename("sixty_forty")
        sources["sixty_forty"] = str(WEEKLY_RETURNS_IN.relative_to(ROOT))

    if SEQUENCE_BACKTEST_IN.exists() and SEQUENCE_SUMMARY_IN.exists():
        seq_summary = pd.read_csv(SEQUENCE_SUMMARY_IN)
        sub = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("model")) & (~seq_summary["wrapper"].eq("raw_ml"))]
        if not sub.empty:
            best_name = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            seq = pd.read_csv(SEQUENCE_BACKTEST_IN, parse_dates=["Date"])
            seq = seq[seq["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not seq.empty:
                returns["mlx5_sequence"] = seq["net_return"].rename("mlx5_sequence")
                returns["mlx5_sequence_turnover"] = seq["turnover"].rename("mlx5_sequence_turnover")
                sources["mlx5_sequence"] = str(SEQUENCE_BACKTEST_IN.relative_to(ROOT))
    else:
        warn("MLX-5 sequence backtest/summary missing; MLX sleeve task may be skipped.", warnings_list)

    if TRANSFORMER_BACKTEST_IN.exists() and TRANSFORMER_SUMMARY_IN.exists():
        tr_summary = pd.read_csv(TRANSFORMER_SUMMARY_IN)
        sub = tr_summary[(tr_summary["split"].eq("holdout")) & (~tr_summary["wrapper"].eq("raw_ml"))]
        if not sub.empty:
            best_name = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            tr = pd.read_csv(TRANSFORMER_BACKTEST_IN, parse_dates=["Date"])
            tr = tr[tr["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not tr.empty:
                returns["mlx6_transformer"] = tr["net_return"].rename("mlx6_transformer")
                sources["mlx6_transformer"] = str(TRANSFORMER_BACKTEST_IN.relative_to(ROOT))

    if SEQUENCE_BACKTEST_IN.exists() and SEQUENCE_SUMMARY_IN.exists():
        seq_summary = pd.read_csv(SEQUENCE_SUMMARY_IN)
        mom = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("baseline_momentum"))]
        if not mom.empty:
            best_name = mom.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            seq = pd.read_csv(SEQUENCE_BACKTEST_IN, parse_dates=["Date"])
            seq = seq[seq["strategy_name"].eq(best_name)].set_index("Date").sort_index()
            if not seq.empty:
                returns["simple_momentum"] = seq["net_return"].rename("simple_momentum")
                sources["simple_momentum"] = str(SEQUENCE_BACKTEST_IN.relative_to(ROOT))

    panel = pd.concat(returns.values(), axis=1).sort_index() if returns else pd.DataFrame()
    panel.index.name = "Date"
    return panel, sources


def safe_feature_columns(features: pd.DataFrame) -> list[str]:
    cols = []
    for col in features.columns:
        if col in {"Date", "ticker"}:
            continue
        lower = col.lower()
        if lower.startswith(TARGET_LIKE_PREFIXES) or lower.endswith("_label"):
            continue
        if pd.api.types.is_numeric_dtype(features[col]):
            cols.append(col)
    return cols


def build_date_features(features: pd.DataFrame, returns: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    feature_cols = safe_feature_columns(features)
    by_date = features.groupby("Date")[feature_cols].mean(numeric_only=True).sort_index()
    by_date.columns = [f"feature_avg_{c}" for c in by_date.columns]

    # Add dispersion/coverage-style ETF aggregate features from known-at-date panel columns.
    for col in ["trailing_return_4w", "trailing_return_13w", "trailing_return_26w", "realized_vol_13w", "momentum_12_1"]:
        if col in features.columns:
            grouped = features.groupby("Date")[col]
            by_date[f"feature_cross_section_{col}_std"] = grouped.std()
            by_date[f"feature_cross_section_{col}_p75_minus_p25"] = grouped.quantile(0.75) - grouped.quantile(0.25)

    for name in [c for c in ["production", "mlx5_sequence"] if c in returns.columns]:
        r = returns[name].reindex(by_date.index)
        by_date[f"{name}_return_4w_trailing"] = (1.0 + r).rolling(4, min_periods=2).apply(np.prod, raw=True) - 1.0
        by_date[f"{name}_return_13w_trailing"] = (1.0 + r).rolling(13, min_periods=4).apply(np.prod, raw=True) - 1.0
        by_date[f"{name}_vol_13w_trailing"] = r.rolling(13, min_periods=4).std() * math.sqrt(52.0)
        by_date[f"{name}_drawdown_13w_trailing"] = trailing_drawdown(r, 13)
    if "mlx5_sequence_turnover" in returns.columns:
        by_date["mlx5_sequence_turnover_4w_avg"] = returns["mlx5_sequence_turnover"].reindex(by_date.index).rolling(4, min_periods=2).mean()
    return by_date


def add_model_confidence_features(date_features: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    out = date_features.copy()
    sources = [
        ("seq", SEQUENCE_PREDICTIONS_IN),
        ("transformer", TRANSFORMER_PREDICTIONS_IN),
    ]
    for prefix, path in sources:
        if not path.exists():
            warn(f"Optional {prefix} prediction file missing for model-confidence features: {path}", warnings_list)
            continue
        pred = pd.read_parquet(path)
        if pred.empty or "score" not in pred.columns:
            warn(f"Optional {prefix} predictions are empty or missing score column.", warnings_list)
            continue
        pred["Date"] = pd.to_datetime(pred["Date"])
        rows = []
        for date, group in pred.groupby("Date"):
            score = pd.to_numeric(group["score"], errors="coerce").dropna()
            if score.empty:
                continue
            top10 = score.sort_values(ascending=False).head(10)
            rows.append({
                "Date": date,
                f"{prefix}_score_mean": float(score.mean()),
                f"{prefix}_score_std": float(score.std(ddof=0)),
                f"{prefix}_score_top1": float(score.max()),
                f"{prefix}_score_median": float(score.median()),
                f"{prefix}_score_top10_mean": float(top10.mean()),
                f"{prefix}_score_top1_minus_median": float(score.max() - score.median()),
            })
        conf = pd.DataFrame(rows).set_index("Date").sort_index() if rows else pd.DataFrame()
        if not conf.empty:
            out = out.join(conf, how="left")
    return out


def create_tasks(meta: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, list[MetaTask], list[dict[str, str]]]:
    df = meta.copy()
    skipped: list[dict[str, str]] = []
    tasks: list[MetaTask] = []

    def need(cols: list[str], task_id: str) -> bool:
        missing = [c for c in cols if c not in df.columns]
        if missing:
            skipped.append({"task_id": task_id, "reason": f"missing required return columns: {missing}"})
            warn(f"Skipping meta-label task {task_id}: missing {missing}", warnings_list)
            return False
        return True

    for col in [c for c in ["production", "phase4b", "mlx5_sequence", "BIL"] if c in df.columns]:
        df[f"future_4w_{col}"] = future_4w_return(df[col])

    if need(["future_4w_production", "future_4w_BIL"], "task_a_core_production_risk_filter"):
        df["label_task_a_core_production_risk_filter"] = ((df["future_4w_production"] > 0.0) | (df["future_4w_production"] > df["future_4w_BIL"])).astype(float)
        tasks.append(MetaTask("task_a_core_production_risk_filter", "label_task_a_core_production_risk_filter", "production next 4-week return is positive or beats BIL", "identify when production should be trusted or risk-reduced", "production_bil_filter"))
    if need(["future_4w_production", "future_4w_BIL"], "task_b_production_beats_bil"):
        df["label_task_b_production_beats_bil"] = (df["future_4w_production"] > df["future_4w_BIL"]).astype(float)
        tasks.append(MetaTask("task_b_production_beats_bil", "label_task_b_production_beats_bil", "production beats BIL over next 4 weeks", "reduce exposure when production expected excess return is poor", "production_bil_filter"))
    if need(["future_4w_phase4b", "future_4w_production"], "task_c_phase4b_beats_production"):
        df["label_task_c_phase4b_beats_production"] = (df["future_4w_phase4b"] > df["future_4w_production"]).astype(float)
        tasks.append(MetaTask("task_c_phase4b_beats_production", "label_task_c_phase4b_beats_production", "Phase 4B beats production over next 4 weeks", "identify when more aggressive Phase 4B-like offense should be preferred", "phase4b_switch"))
    if need(["future_4w_mlx5_sequence", "future_4w_production", "future_4w_BIL"], "task_d_mlx5_sleeve_activation"):
        df["label_task_d_mlx5_sleeve_activation"] = ((df["future_4w_mlx5_sequence"] > df["future_4w_production"]) | (df["future_4w_mlx5_sequence"] > df["future_4w_BIL"])).astype(float)
        tasks.append(MetaTask("task_d_mlx5_sleeve_activation", "label_task_d_mlx5_sleeve_activation", "MLX-5 sequence sleeve beats production or BIL over next 4 weeks", "decide when to activate ML offensive sleeve", "mlx5_activation"))
    if need(["future_4w_production"], "task_e_bad_week_avoidance"):
        future_legs = pd.concat([df["production"].shift(-i) for i in range(1, 5)], axis=1)
        future_min_week = future_legs.min(axis=1)
        df["label_task_e_bad_week_avoidance"] = ((df["future_4w_production"] < -0.03) | (future_min_week < -0.04)).astype(float)
        tasks.append(MetaTask("task_e_bad_week_avoidance", "label_task_e_bad_week_avoidance", "next 4-week production loss or weekly shock exceeds threshold", "predict when to reduce ML or offensive exposure", "bad_week_filter"))

    for task in tasks:
        df.loc[df[task.label_col].isna(), task.label_col] = np.nan
    return df, tasks, skipped


def model_specs(warnings_list: list[str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    skipped: list[dict[str, str]] = []
    models: dict[str, Any] = {}
    try:
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        models["logistic_regression"] = LogisticRegression(max_iter=1000, class_weight="balanced", solver="lbfgs")
        models["random_forest"] = RandomForestClassifier(n_estimators=200, max_depth=4, min_samples_leaf=8, random_state=42, class_weight="balanced_subsample", n_jobs=2)
        models["gradient_boosting"] = GradientBoostingClassifier(n_estimators=120, learning_rate=0.04, max_depth=2, random_state=42)
    except Exception as exc:
        skipped.append({"model_name": "sklearn_core_models", "reason": f"sklearn models unavailable: {exc}"})
        warn(f"sklearn core classifiers unavailable: {exc}", warnings_list)
    try:
        from xgboost import XGBClassifier
        models["xgboost"] = XGBClassifier(n_estimators=100, max_depth=2, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, eval_metric="logloss", random_state=42, n_jobs=2)
    except Exception as exc:
        skipped.append({"model_name": "xgboost", "reason": f"optional xgboost unavailable: {exc}"})
        warn(f"Optional xgboost unavailable: {exc}", warnings_list)
    try:
        from lightgbm import LGBMClassifier
        models["lightgbm"] = LGBMClassifier(n_estimators=100, max_depth=2, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8, random_state=42, verbose=-1, n_jobs=2)
    except Exception as exc:
        skipped.append({"model_name": "lightgbm", "reason": f"optional lightgbm unavailable: {exc}"})
        warn(f"Optional lightgbm unavailable: {exc}", warnings_list)
    skipped.append({"model_name": "small_torch_mlp", "reason": "optional MLP skipped to keep MLX-7 bounded and interpretable"})
    return models, skipped


def prepare_xy(df: pd.DataFrame, feature_cols: list[str], task: MetaTask) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    valid = df[task.label_col].notna()
    x = df.loc[valid, feature_cols].replace([np.inf, -np.inf], np.nan)
    y = df.loc[valid, task.label_col].astype(int)
    split = df.loc[valid, "split"]
    return x, y, split


def fit_predict_models(df: pd.DataFrame, tasks: list[MetaTask], feature_cols: list[str], warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, str]]]:
    from sklearn.base import clone
    from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, precision_score, recall_score, roc_auc_score

    models, skipped_models = model_specs(warnings_list)
    prediction_frames: list[pd.DataFrame] = []
    metrics_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []

    for task in tasks:
        x, y, split = prepare_xy(df, feature_cols, task)
        train_mask = split.eq("train")
        if train_mask.sum() < 100 or y.loc[train_mask].nunique() < 2:
            skipped_models.append({"model_name": "all_models", "task_id": task.task_id, "reason": "insufficient train rows or only one class"})
            continue
        medians = x.loc[train_mask].median(numeric_only=True).fillna(0.0)
        filled = x.fillna(medians).fillna(0.0)
        means = filled.loc[train_mask].mean(numeric_only=True)
        stds = filled.loc[train_mask].std(numeric_only=True).replace(0.0, 1.0).fillna(1.0)

        for model_name, estimator in models.items():
            use_scaled = model_name == "logistic_regression"
            x_model = ((filled - means) / stds).astype(float) if use_scaled else filled.astype(float)
            try:
                model = clone(estimator)
                model.fit(x_model.loc[train_mask], y.loc[train_mask])
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(x_model)[:, 1]
                else:
                    raw = model.decision_function(x_model)
                    proba = 1.0 / (1.0 + np.exp(-raw))
                pred_label = (proba >= 0.50).astype(int)
                pred = pd.DataFrame({
                    "Date": x.index,
                    "task_id": task.task_id,
                    "label_col": task.label_col,
                    "model_name": model_name,
                    "split": split.values,
                    "actual": y.values,
                    "probability": proba,
                    "predicted_label": pred_label,
                })
                prediction_frames.append(pred)
                for split_name in SPLITS:
                    mask = split.eq(split_name)
                    if mask.sum() == 0:
                        continue
                    y_true = y.loc[mask]
                    p = pd.Series(proba, index=x.index).loc[mask]
                    label = (p >= 0.50).astype(int)
                    metrics = {
                        "task_id": task.task_id,
                        "model_name": model_name,
                        "split": split_name,
                        "rows": int(mask.sum()),
                        "positive_rate_actual": float(y_true.mean()),
                        "positive_prediction_rate": float(label.mean()),
                        "accuracy": float(accuracy_score(y_true, label)),
                        "precision": float(precision_score(y_true, label, zero_division=0)),
                        "recall": float(recall_score(y_true, label, zero_division=0)),
                        "f1": float(f1_score(y_true, label, zero_division=0)),
                        "brier": float(brier_score_loss(y_true, p.clip(0, 1))),
                    }
                    try:
                        metrics["roc_auc"] = float(roc_auc_score(y_true, p)) if y_true.nunique() > 1 else np.nan
                    except Exception:
                        metrics["roc_auc"] = np.nan
                    metrics_rows.append(metrics)
                if hasattr(model, "coef_"):
                    vals = np.asarray(model.coef_).reshape(-1)
                    for feature, value in zip(feature_cols, vals):
                        importance_rows.append({"task_id": task.task_id, "model_name": model_name, "feature": feature, "importance": float(value), "importance_type": "coefficient"})
                elif hasattr(model, "feature_importances_"):
                    vals = np.asarray(model.feature_importances_).reshape(-1)
                    for feature, value in zip(feature_cols, vals):
                        if value != 0:
                            importance_rows.append({"task_id": task.task_id, "model_name": model_name, "feature": feature, "importance": float(value), "importance_type": "feature_importance"})
            except Exception as exc:
                skipped_models.append({"model_name": model_name, "task_id": task.task_id, "reason": f"fit/predict failed: {exc}"})
                warn(f"Meta-label model failed for {task.task_id}/{model_name}: {exc}", warnings_list)

    predictions = pd.concat(prediction_frames, ignore_index=True) if prediction_frames else pd.DataFrame()
    metrics = pd.DataFrame(metrics_rows)
    importance = pd.DataFrame(importance_rows)
    if not importance.empty:
        importance["abs_importance"] = importance["importance"].abs()
        importance = importance.sort_values(["task_id", "model_name", "abs_importance"], ascending=[True, True, False])
    return predictions, metrics, importance, skipped_models


def select_best_models(model_metrics: pd.DataFrame) -> dict[str, str]:
    out: dict[str, str] = {}
    if model_metrics.empty:
        return out
    val = model_metrics[model_metrics["split"].eq("validation")].copy()
    val["selection_score"] = pd.to_numeric(val["roc_auc"], errors="coerce").fillna(0.5) + 0.25 * pd.to_numeric(val["f1"], errors="coerce").fillna(0.0)
    for task_id, group in val.groupby("task_id"):
        if group.empty:
            continue
        out[task_id] = str(group.sort_values(["selection_score", "f1"], ascending=[False, False]).iloc[0]["model_name"])
    return out


def strategy_path_from_weights(weights: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    weights = weights.sort_index().fillna(0.0)
    aligned = returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    gross = weights.mul(aligned).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover * (DEFAULT_COST_BPS / 10000.0)
    path = pd.DataFrame({
        "gross_return": gross,
        "net_return": gross - cost,
        "turnover": turnover,
        "cost": cost,
        "bil_weight": weights["BIL"] if "BIL" in weights.columns else 0.0,
        "ml_sleeve_weight": weights["mlx5_sequence"] if "mlx5_sequence" in weights.columns else 0.0,
    }, index=weights.index)
    return path


def simulate_meta_strategies(predictions: pd.DataFrame, best_models: dict[str, str], returns: pd.DataFrame, warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    thresholds = (0.50, 0.60, 0.70)
    all_paths: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    needed_base = {"production", "BIL"}
    if not needed_base.issubset(returns.columns):
        warn("Missing production or BIL returns; many meta strategies cannot be simulated.", warnings_list)
        return pd.DataFrame(), pd.DataFrame()

    def add_strategy(name: str, family: str, weights: pd.DataFrame, task_id: str, model_name: str, threshold: float, sleeve_size: float = np.nan) -> None:
        path = strategy_path_from_weights(weights, returns)
        dated = path.reset_index(names="Date")
        dated["split"] = split_for_dates(dated["Date"]).values
        dated["strategy_name"] = name
        dated["strategy_family"] = family
        dated["task_id"] = task_id
        dated["model_name"] = model_name
        dated["threshold"] = threshold
        dated["sleeve_size"] = sleeve_size
        all_paths.append(dated)
        for split_name in SPLITS:
            metrics = calc_metrics(dated[dated["split"].eq(split_name)])
            metrics.update({"strategy_name": name, "strategy_family": family, "task_id": task_id, "model_name": model_name, "threshold": threshold, "sleeve_size": sleeve_size, "split": split_name})
            summary_rows.append(metrics)

    pred_idx = predictions.copy()
    pred_idx["Date"] = pd.to_datetime(pred_idx["Date"])
    for task_id, model_name in best_models.items():
        p = pred_idx[(pred_idx["task_id"].eq(task_id)) & (pred_idx["model_name"].eq(model_name))].set_index("Date").sort_index()
        if p.empty:
            continue
        dates = p.index.intersection(returns.index)
        prob = p["probability"].reindex(dates)
        for threshold in thresholds:
            if task_id in {"task_a_core_production_risk_filter", "task_b_production_beats_bil"}:
                trust = (prob > threshold).astype(float)
                w = pd.DataFrame(0.0, index=dates, columns=["production", "BIL"])
                w["production"] = trust
                w["BIL"] = 1.0 - trust
                add_strategy(f"{task_id}__{model_name}__thr{threshold:.2f}__production_or_bil", "production_bil_filter", w, task_id, model_name, threshold)
            if task_id == "task_c_phase4b_beats_production" and "phase4b" in returns.columns:
                use_phase = (prob > threshold).astype(float)
                w = pd.DataFrame(0.0, index=dates, columns=["production", "phase4b"])
                w["phase4b"] = use_phase
                w["production"] = 1.0 - use_phase
                add_strategy(f"{task_id}__{model_name}__thr{threshold:.2f}__phase4b_switch", "phase4b_switch", w, task_id, model_name, threshold)
            if task_id == "task_d_mlx5_sleeve_activation" and "mlx5_sequence" in returns.columns:
                active = (prob > threshold).astype(float)
                for sleeve in (0.10, 0.20, 0.30):
                    w = pd.DataFrame(0.0, index=dates, columns=["production", "mlx5_sequence"])
                    w["mlx5_sequence"] = sleeve * active
                    w["production"] = 1.0 - w["mlx5_sequence"]
                    add_strategy(f"{task_id}__{model_name}__thr{threshold:.2f}__sleeve{sleeve:.0%}", "mlx5_sleeve_activation", w, task_id, model_name, threshold, sleeve)
            if task_id == "task_e_bad_week_avoidance":
                bad = (prob > threshold).astype(float)
                if "mlx5_sequence" in returns.columns:
                    w = pd.DataFrame(0.0, index=dates, columns=["mlx5_sequence", "BIL"])
                    w["BIL"] = bad
                    w["mlx5_sequence"] = 1.0 - bad
                    add_strategy(f"{task_id}__{model_name}__thr{threshold:.2f}__mlx5_or_bil", "bad_week_avoid_mlx5", w, task_id, model_name, threshold)
                w2 = pd.DataFrame(0.0, index=dates, columns=["production", "BIL"])
                w2["BIL"] = bad
                w2["production"] = 1.0 - bad
                add_strategy(f"{task_id}__{model_name}__thr{threshold:.2f}__production_or_bil", "bad_week_avoid_production", w2, task_id, model_name, threshold)

    returns_df = pd.concat(all_paths, ignore_index=True) if all_paths else pd.DataFrame()
    summary_df = pd.DataFrame(summary_rows)
    return returns_df, summary_df


def add_benchmarks(strategy_summary: pd.DataFrame, returns: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    rows = strategy_summary.to_dict("records") if not strategy_summary.empty else []
    benchmark_cols = ["production", "official_shadow", "phase4b", "phase6", "phase7", "mlx5_sequence", "mlx6_transformer", "simple_momentum", "SPY", "sixty_forty"]
    for name in benchmark_cols:
        if name not in returns.columns:
            continue
        path = pd.DataFrame({"net_return": returns[name], "gross_return": returns[name], "turnover": np.nan, "cost": 0.0, "bil_weight": 0.0, "ml_sleeve_weight": 1.0 if name.startswith("mlx") else 0.0}, index=returns.index)
        if name == "BIL":
            path["bil_weight"] = 1.0
        dated = path.reset_index(names="Date")
        dated["split"] = split_for_dates(dated["Date"]).values
        for split_name in SPLITS:
            metrics = calc_metrics(dated[dated["split"].eq(split_name)])
            metrics.update({"strategy_name": name, "strategy_family": "benchmark", "task_id": "", "model_name": "", "threshold": np.nan, "sleeve_size": np.nan, "split": split_name})
            rows.append(metrics)
    if MLX5C_SUMMARY_IN.exists():
        try:
            mlx5c = json.loads(MLX5C_SUMMARY_IN.read_text())
            rows.append({
                "annual_return": np.nan,
                "annual_volatility": np.nan,
                "sharpe": mlx5c.get("overall_mean_sharpe", np.nan),
                "max_drawdown": mlx5c.get("overall_worst_case_max_drawdown", np.nan),
                "calmar": np.nan,
                "cvar_5": mlx5c.get("overall_worst_case_cvar_5", np.nan),
                "average_turnover": np.nan,
                "annual_cost_drag": np.nan,
                "average_bil_weight": np.nan,
                "average_ml_sleeve_exposure": np.nan,
                "active_weeks": np.nan,
                "strategy_name": "mlx5c_bil_fallback_mean_summary",
                "strategy_family": "benchmark_summary_only",
                "task_id": "",
                "model_name": "",
                "threshold": np.nan,
                "sleeve_size": np.nan,
                "split": "holdout",
            })
        except Exception as exc:
            warn(f"Could not load MLX-5C summary benchmark: {exc}", warnings_list)
    else:
        warn("MLX-5C summary missing; benchmark comparison to MLX-5C is summary-only unavailable.", warnings_list)
    return pd.DataFrame(rows)


def best_row(df: pd.DataFrame, split: str = "holdout", strategy_family: str | None = None, metric: str = "sharpe", ascending: bool = False) -> dict[str, Any] | None:
    sub = df[df["split"].eq(split)].copy() if "split" in df.columns else df.copy()
    if strategy_family is not None:
        sub = sub[sub["strategy_family"].eq(strategy_family)]
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
    pct_cols = [c for c in sub.columns if c in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "annual_cost_drag", "average_bil_weight", "average_ml_sleeve_exposure", "positive_rate_actual", "positive_prediction_rate", "accuracy", "precision", "recall", "f1", "roc_auc"}]
    for col in pct_cols:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(pct)
    for col in [c for c in ["sharpe", "calmar", "brier"] if c in sub.columns]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(num)
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def choose_recommendation(summary: pd.DataFrame) -> str:
    prod = best_row(summary[summary["strategy_name"].eq("production")], "holdout")
    best_meta = best_row(summary[~summary["strategy_family"].isin(["benchmark", "benchmark_summary_only"])], "holdout")
    if best_meta is None or prod is None:
        return "KEEP AS RESEARCH ONLY"
    improves_sharpe = float(best_meta["sharpe"]) > float(prod["sharpe"])
    improves_dd = float(best_meta["max_drawdown"]) >= float(prod["max_drawdown"])
    if improves_sharpe and improves_dd:
        return "PROMISING FILTER BUT NEEDS WALK-FORWARD"
    if improves_sharpe:
        return "KEEP AS ML SHADOW FILTER"
    return "KEEP AS RESEARCH ONLY"


def write_notes(tasks: list[MetaTask], skipped_tasks: list[dict[str, str]], skipped_models: list[dict[str, str]], model_metrics: pd.DataFrame, strategy_summary: pd.DataFrame, feature_importance: pd.DataFrame, summary_json: dict[str, Any], warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    task_lines = "\n".join(f"- `{t.task_id}`: {t.label_positive_meaning}. Purpose: {t.purpose}." for t in tasks) or "- None"
    skipped_task_lines = "\n".join(f"- {s['task_id']}: {s['reason']}" for s in skipped_tasks) or "- None"
    skipped_model_lines = "\n".join(f"- {s.get('model_name')}: {s.get('reason')} {s.get('task_id', '')}" for s in skipped_models) or "- None"
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"
    holdout_metrics = model_metrics[model_metrics["split"].eq("holdout")].sort_values(["roc_auc", "f1"], ascending=[False, False]) if not model_metrics.empty else pd.DataFrame()
    holdout_strats = strategy_summary[strategy_summary["split"].eq("holdout")].sort_values(["sharpe", "annual_return"], ascending=[False, False]) if not strategy_summary.empty else pd.DataFrame()
    importance = feature_importance.sort_values("abs_importance", ascending=False).head(20) if not feature_importance.empty else pd.DataFrame()

    NOTES_OUT.write_text(f"""# Phase MLX Meta-Labeling Notes

## Research-Only Warning

Phase MLX-7 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Meta-labeling is a second-stage model. Instead of directly predicting which ETF will have the best return, it asks whether an already-defined strategy or sleeve should be trusted in the next period. For example, it can ask whether production is likely to beat BIL, whether Phase 4B is likely to beat production, or whether the MLX-5 sequence sleeve deserves activation.

This is different from direct return prediction because the model filters a decision that already exists. It might help this project by connecting the ML lab to the core ETF strategy: ML becomes a risk filter or offensive-sleeve activation signal rather than a replacement portfolio. It can overfit because the labels are noisy, the number of weekly examples is small, and a filter can accidentally learn one market era rather than durable behavior.

## Technical Setup

Meta-label tasks created:

{task_lines}

Features used:
- date-level averages of safe numeric MLX-2 features
- market state and risk/regime features from the feature panel
- stock breadth prototype features, marked research-only and survivorship-biased in MLX-2 metadata
- aggregate MLX sequence/Transformer confidence features where prediction files were available
- recent production and ML sleeve return, drawdown, volatility, and turnover features

Models run: Logistic Regression, Random Forest, Gradient Boosting, and optional XGBoost/LightGBM when importable. Splits are chronological: train through 2017-12-31, validation 2018-01-01 through 2019-12-31, holdout 2020-01-01 onward.

Leakage controls: all meta features are known at date `t`; future 4-week strategy outcomes are used only as labels; forward target-like columns are excluded from input features; train-only medians and standardization are used for model fitting.

Skipped tasks:

{skipped_task_lines}

Skipped models:

{skipped_model_lines}

## Classification Results

{markdown_table(holdout_metrics, ['task_id', 'model_name', 'rows', 'positive_rate_actual', 'positive_prediction_rate', 'accuracy', 'precision', 'recall', 'f1', 'roc_auc', 'brier'], max_rows=25)}

## Strategy Results

{markdown_table(holdout_strats, ['strategy_name', 'strategy_family', 'task_id', 'model_name', 'threshold', 'sleeve_size', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_weight', 'average_ml_sleeve_exposure'], max_rows=30)}

## Feature Importance

{markdown_table(importance, ['task_id', 'model_name', 'feature', 'importance', 'importance_type'], max_rows=20)}

## Interpretation

- Best classification model: `{summary_json.get('best_classification_model', {}).get('task_model', 'n/a')}`
- Best meta-label strategy: `{summary_json.get('best_meta_strategy', {}).get('strategy_name', 'n/a')}`
- Production+BIL filter improved production by holdout Sharpe: {summary_json.get('production_filter_beats_production_sharpe')}
- Phase 4B switch improved production by holdout Sharpe: {summary_json.get('phase4b_switch_beats_production_sharpe')}
- MLX-5 sleeve activation improved production by holdout Sharpe: {summary_json.get('mlx5_activation_beats_production_sharpe')}
- Bad-week avoidance reduced drawdown versus production: {summary_json.get('bad_week_avoidance_reduced_drawdown')}

Final recommendation: **{summary_json.get('final_recommendation')}**

## Warnings

{warn_lines}
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    mlx5 = load_mlx5_module()
    features, targets, weekly_returns = load_inputs(mlx5)
    returns, return_sources = load_strategy_returns(mlx5, weekly_returns, warnings_list)
    if returns.empty:
        raise RuntimeError("No strategy returns could be loaded for MLX-7 meta-labeling.")

    date_features = build_date_features(features, returns, warnings_list)
    date_features = add_model_confidence_features(date_features, warnings_list)
    meta = date_features.join(returns, how="left")
    meta["split"] = split_for_dates(meta.index).values
    meta, tasks, skipped_tasks = create_tasks(meta, warnings_list)
    if not tasks:
        warn("No meta-label tasks could be created.", warnings_list)

    label_cols = [t.label_col for t in tasks]
    future_cols = [c for c in meta.columns if c.startswith("future_4w_")]
    return_cols = [c for c in returns.columns]
    excluded = set(label_cols + future_cols + return_cols + ["split"])
    feature_cols = [c for c in meta.columns if c not in excluded and pd.api.types.is_numeric_dtype(meta[c])]
    feature_cols = [c for c in feature_cols if not c.lower().startswith(TARGET_LIKE_PREFIXES)]

    predictions, model_metrics, feature_importance, skipped_models = fit_predict_models(meta, tasks, feature_cols, warnings_list)
    best_models = select_best_models(model_metrics)
    strategy_returns, strategy_summary_raw = simulate_meta_strategies(predictions, best_models, returns, warnings_list)
    strategy_summary = add_benchmarks(strategy_summary_raw, returns, warnings_list)

    task_definitions = {
        task.task_id: {
            "label_col": task.label_col,
            "label_positive_meaning": task.label_positive_meaning,
            "purpose": task.purpose,
            "strategy_family": task.strategy_family,
        }
        for task in tasks
    }
    task_definitions["_metadata"] = {
        "research_only": True,
        "production_valid": False,
        "feature_count": len(feature_cols),
        "return_sources": return_sources,
        "train_only_preprocessing": True,
        "label_horizon": "future 4 weekly returns from t+1 through t+4",
    }

    best_classification = None
    if not model_metrics.empty:
        hold_cls = model_metrics[model_metrics["split"].eq("holdout")].copy()
        hold_cls["selection_score"] = pd.to_numeric(hold_cls["roc_auc"], errors="coerce").fillna(0.5) + 0.25 * pd.to_numeric(hold_cls["f1"], errors="coerce").fillna(0.0)
        if not hold_cls.empty:
            row = hold_cls.sort_values(["selection_score", "f1"], ascending=[False, False]).iloc[0].to_dict()
            row["task_model"] = f"{row['task_id']} / {row['model_name']}"
            best_classification = row
    best_meta = best_row(strategy_summary[~strategy_summary["strategy_family"].isin(["benchmark", "benchmark_summary_only"])], "holdout")
    production = best_row(strategy_summary[strategy_summary["strategy_name"].eq("production")], "holdout")
    phase4b = best_row(strategy_summary[strategy_summary["strategy_name"].eq("phase4b")], "holdout")
    mlx5 = best_row(strategy_summary[strategy_summary["strategy_name"].eq("mlx5_sequence")], "holdout")

    def family_beats(family: str, benchmark: dict[str, Any] | None, metric: str = "sharpe") -> bool | None:
        row = best_row(strategy_summary[strategy_summary["strategy_family"].eq(family)], "holdout")
        if row is None or benchmark is None:
            return None
        return bool(float(row[metric]) > float(benchmark[metric]))

    def family_reduces_drawdown(family: str, benchmark: dict[str, Any] | None) -> bool | None:
        row = best_row(strategy_summary[strategy_summary["strategy_family"].eq(family)], "holdout")
        if row is None or benchmark is None:
            return None
        return bool(float(row["max_drawdown"]) >= float(benchmark["max_drawdown"]))

    final_recommendation = choose_recommendation(strategy_summary)
    summary_json = {
        "phase": "MLX-7 meta-labeling",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "feature_count": len(feature_cols),
        "tasks_created": [t.task_id for t in tasks],
        "tasks_skipped": skipped_tasks,
        "models_run": sorted(model_metrics["model_name"].dropna().unique().tolist()) if not model_metrics.empty else [],
        "models_skipped": skipped_models,
        "best_models_by_task": best_models,
        "best_classification_model": best_classification or {},
        "best_meta_strategy": best_meta or {},
        "production_benchmark": production or {},
        "phase4b_benchmark": phase4b or {},
        "mlx5_benchmark": mlx5 or {},
        "production_filter_beats_production_sharpe": family_beats("production_bil_filter", production),
        "phase4b_switch_beats_production_sharpe": family_beats("phase4b_switch", production),
        "mlx5_activation_beats_production_sharpe": family_beats("mlx5_sleeve_activation", production),
        "bad_week_avoidance_reduced_drawdown": family_reduces_drawdown("bad_week_avoid_production", production),
        "final_recommendation": final_recommendation,
        "warnings": warnings_list + ["Experimental research-only Phase MLX output; not production-valid.", "No meta-label strategy is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "datasets": str(DATASETS_OUT.relative_to(ROOT)),
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "model_metrics": str(MODEL_METRICS_OUT.relative_to(ROOT)),
            "strategy_returns": str(STRATEGY_RETURNS_OUT.relative_to(ROOT)),
            "strategy_summary": str(STRATEGY_SUMMARY_OUT.relative_to(ROOT)),
            "feature_importance": str(FEATURE_IMPORTANCE_OUT.relative_to(ROOT)),
            "task_definitions": str(TASK_DEFINITIONS_OUT.relative_to(ROOT)),
            "skipped_tasks": str(SKIPPED_TASKS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }

    meta.reset_index(names="Date").to_parquet(DATASETS_OUT, index=False)
    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    model_metrics.to_csv(MODEL_METRICS_OUT, index=False)
    strategy_returns.to_csv(STRATEGY_RETURNS_OUT, index=False)
    strategy_summary.to_csv(STRATEGY_SUMMARY_OUT, index=False)
    feature_importance.to_csv(FEATURE_IMPORTANCE_OUT, index=False)
    TASK_DEFINITIONS_OUT.write_text(json.dumps(task_definitions, indent=2, default=json_default))
    SKIPPED_TASKS_OUT.write_text(json.dumps({"skipped_tasks": skipped_tasks, "skipped_models": skipped_models}, indent=2, default=json_default) + "\n")
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(tasks, skipped_tasks, skipped_models, model_metrics, strategy_summary, feature_importance, summary_json, summary_json["warnings"])

    print("Phase MLX-7 meta-labeling")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Tasks created: {[t.task_id for t in tasks]}")
    print(f"Tasks skipped: {len(skipped_tasks)}")
    print(f"Models run: {summary_json['models_run']}")
    print(f"Models skipped: {len(skipped_models)}")
    print(f"Best classification model: {summary_json['best_classification_model'].get('task_model', 'n/a')}")
    print(f"Best meta-label strategy: {summary_json['best_meta_strategy'].get('strategy_name', 'n/a')}")
    print(f"Best meta-label holdout Sharpe: {summary_json['best_meta_strategy'].get('sharpe', np.nan)}")
    print(f"Final recommendation: {final_recommendation}")
    print("Outputs:")
    for path in [DATASETS_OUT, PREDICTIONS_OUT, MODEL_METRICS_OUT, STRATEGY_RETURNS_OUT, STRATEGY_SUMMARY_OUT, FEATURE_IMPORTANCE_OUT, TASK_DEFINITIONS_OUT, SKIPPED_TASKS_OUT, SUMMARY_JSON_OUT, NOTES_OUT]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
