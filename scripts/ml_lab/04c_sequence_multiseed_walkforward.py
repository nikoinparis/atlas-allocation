#!/usr/bin/env python3
"""
Phase MLX-5C: multi-seed and walk-forward sequence robustness.

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
ROBUSTNESS_DIR = SEQUENCE_DIR / "robustness"
OUTPUT_DIR = SEQUENCE_DIR / "multiseed_walkforward"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
SEQUENCE_RETURNS_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
ROBUSTNESS_SUMMARY_IN = ROBUSTNESS_DIR / "sequence_robustness_summary.json"

PREDICTIONS_OUT = OUTPUT_DIR / "sequence_multiseed_predictions.parquet"
BACKTEST_RETURNS_OUT = OUTPUT_DIR / "sequence_multiseed_backtest_returns.csv"
RUN_METRICS_OUT = OUTPUT_DIR / "sequence_multiseed_run_metrics.csv"
STABILITY_SUMMARY_OUT = OUTPUT_DIR / "sequence_multiseed_stability_summary.csv"
FOLD_DEFINITIONS_OUT = OUTPUT_DIR / "sequence_multiseed_fold_definitions.csv"
TRAINING_CURVES_OUT = OUTPUT_DIR / "sequence_multiseed_training_curves.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "sequence_multiseed_strategy_comparison.csv"
SKIPPED_RUNS_OUT = OUTPUT_DIR / "sequence_multiseed_skipped_runs.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "sequence_multiseed_summary.json"
REPORT_OUT = DOCS_DIR / "phase_mlx_5c_sequence_multiseed_walkforward_report.md"

TARGET = "top_quintile_forward_4w"
DEFAULT_COST_BPS = 10.0
MAX_EPOCHS = 4
PATIENCE = 1
HIDDEN_SIZE = 32
DROPOUT = 0.20
MODEL_TYPES = ("lstm", "gru", "tcn")
SEQUENCE_LENGTHS = (13, 26, 52)
SEEDS = (0, 1, 2)
TOP_NS = (10, 15)
WRAPPERS = ("bil_fallback_original", "raw_ml")


@dataclass(frozen=True)
class RunSpec:
    fold_name: str
    model_type: str
    sequence_length: int
    seed: int
    reason: str = ""


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


def set_run_seed(torch: Any, seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(max(1, min(4, __import__("os").cpu_count() or 1)))


def load_inputs(mlx5: Any) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [str(p.relative_to(ROOT)) for p in [FEATURES_IN, TARGETS_IN, WEEKLY_RETURNS_IN] if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-5C inputs missing: {missing}")
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    mlx5.validate_inputs(features, targets)
    weekly_returns = mlx5.load_panel_csv(WEEKLY_RETURNS_IN)
    return features, targets, weekly_returns


def fold_definitions(max_date: pd.Timestamp) -> pd.DataFrame:
    rows = [
        {
            "fold_name": "fold_a_2017_2018",
            "train_start": "2000-01-01",
            "train_end": "2014-12-31",
            "validation_start": "2015-01-01",
            "validation_end": "2016-12-31",
            "test_start": "2017-01-01",
            "test_end": "2018-12-31",
        },
        {
            "fold_name": "fold_b_2019_2020",
            "train_start": "2000-01-01",
            "train_end": "2016-12-31",
            "validation_start": "2017-01-01",
            "validation_end": "2018-12-31",
            "test_start": "2019-01-01",
            "test_end": "2020-12-31",
        },
        {
            "fold_name": "fold_c_2021_2022",
            "train_start": "2000-01-01",
            "train_end": "2018-12-31",
            "validation_start": "2019-01-01",
            "validation_end": "2020-12-31",
            "test_start": "2021-01-01",
            "test_end": "2022-12-31",
        },
        {
            "fold_name": "fold_d_2023_2026",
            "train_start": "2000-01-01",
            "train_end": "2020-12-31",
            "validation_start": "2021-01-01",
            "validation_end": "2022-12-31",
            "test_start": "2023-01-01",
            "test_end": max_date.date().isoformat(),
        },
    ]
    folds = pd.DataFrame(rows)
    for col in [c for c in folds.columns if c.endswith(("start", "end"))]:
        folds[col] = pd.to_datetime(folds[col])
    return folds


def split_for_fold(features: pd.DataFrame, fold: pd.Series) -> pd.Series:
    dates = features["Date"]
    split = pd.Series("unused", index=features.index, dtype="object")
    split.loc[(dates >= fold["train_start"]) & (dates <= fold["train_end"])] = "train"
    split.loc[(dates >= fold["validation_start"]) & (dates <= fold["validation_end"])] = "validation"
    split.loc[(dates >= fold["test_start"]) & (dates <= fold["test_end"])] = "test"
    return split


def build_grid(folds: pd.DataFrame) -> tuple[list[RunSpec], list[dict[str, Any]]]:
    run: list[RunSpec] = []
    skipped: list[dict[str, Any]] = []
    run_keys: set[tuple[str, str, int, int]] = set()

    def add(fold_name: str, model_type: str, seq_len: int, seed: int) -> None:
        key = (fold_name, model_type, seq_len, seed)
        if key not in run_keys:
            run_keys.add(key)
            run.append(RunSpec(fold_name, model_type, seq_len, seed))

    fold_names = folds["fold_name"].tolist()
    primary_fold = "fold_d_2023_2026"
    for fold_name in fold_names:
        add(fold_name, "lstm", 26, 0)
    for seed in (1, 2):
        add(primary_fold, "lstm", 26, seed)
    for model_type in ("gru", "tcn"):
        add(primary_fold, model_type, 26, 0)
    add(primary_fold, "lstm", 13, 0)

    for fold_name in fold_names:
        for model_type in MODEL_TYPES:
            for seq_len in SEQUENCE_LENGTHS:
                for seed in SEEDS:
                    key = (fold_name, model_type, seq_len, seed)
                    if key in run_keys:
                        continue
                    if seq_len == 52:
                        reason = "skipped 52-week sequence grid for bounded CPU runtime"
                    elif model_type in {"gru", "tcn"} and seed in {1, 2}:
                        reason = "skipped non-LSTM seed expansion for bounded CPU runtime"
                    elif seq_len == 13:
                        reason = "skipped non-primary 13-week seed/model expansion for bounded CPU runtime"
                    else:
                        reason = "skipped by bounded MLX-5C grid"
                    skipped.append({"fold_name": fold_name, "model_type": model_type, "sequence_length": seq_len, "seed": seed, "reason": reason})
    return run, skipped


def make_context(mlx5: Any, features: pd.DataFrame) -> dict[str, Any]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    tickers = sorted(features["ticker"].unique())
    next_returns = mlx5.next_week_return_panel(features).reindex(index=dates, columns=tickers)
    vol_panel = mlx5.matrix_by_date(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = mlx5.matrix_by_date(features, "realized_vol_26w")
    state = mlx5.infer_market_state_by_date(features)
    return {"dates": dates, "tickers": tickers, "next_returns": next_returns, "vol_panel": vol_panel, "state": state}


def apply_overlay(mlx5: Any, wrapper: str, raw_weights: pd.DataFrame, context: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    if wrapper == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if wrapper == "bil_fallback_original":
        state = context["state"].reindex(dates).fillna("unknown")
        exposure = state.map({"stressed_panic": 0.25, "neutral_mixed": 0.75}).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    raise ValueError(f"Unknown wrapper {wrapper}")


def test_dates_for_fold(context: dict[str, Any], fold: pd.Series) -> pd.DatetimeIndex:
    dates = context["dates"]
    return dates[(dates >= fold["test_start"]) & (dates <= fold["test_end"])]


def run_portfolios_for_predictions(mlx5: Any, pred: pd.DataFrame, context: dict[str, Any], fold: pd.Series, spec: RunSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = test_dates_for_fold(context, fold)
    all_paths: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for top_n in TOP_NS:
        raw = mlx5.weights_from_scores(pred, dates, context["tickers"], top_n, "inverse_vol", context["next_returns"], context["vol_panel"])
        for wrapper in WRAPPERS:
            weights, exposure = apply_overlay(mlx5, wrapper, raw, context)
            path = mlx5.compute_path(weights, context["next_returns"], DEFAULT_COST_BPS, exposure)
            strategy_name = f"{spec.model_type}_seq{spec.sequence_length}_seed{spec.seed}_{spec.fold_name}__top{top_n}__inverse_vol__{wrapper}"
            dated = path.reset_index(names="Date")
            dated["strategy_name"] = strategy_name
            dated["fold_name"] = spec.fold_name
            dated["model_type"] = spec.model_type
            dated["sequence_length"] = spec.sequence_length
            dated["seed"] = spec.seed
            dated["target"] = TARGET
            dated["top_n"] = top_n
            dated["weighting"] = "inverse_vol"
            dated["wrapper"] = wrapper
            dated["cost_bps"] = DEFAULT_COST_BPS
            all_paths.append(dated)

            metrics = mlx5.calc_metrics(path)
            metrics.update({
                "strategy_name": strategy_name,
                "fold_name": spec.fold_name,
                "model_type": spec.model_type,
                "sequence_length": spec.sequence_length,
                "seed": spec.seed,
                "target": TARGET,
                "top_n": top_n,
                "weighting": "inverse_vol",
                "wrapper": wrapper,
                "cost_bps": DEFAULT_COST_BPS,
                "test_start": fold["test_start"].date().isoformat(),
                "test_end": fold["test_end"].date().isoformat(),
            })
            rows.append(metrics)
    return pd.concat(all_paths, ignore_index=True), pd.DataFrame(rows)


def baseline_momentum_metrics(mlx5: Any, features: pd.DataFrame, context: dict[str, Any], fold: pd.Series) -> dict[str, Any]:
    dates = test_dates_for_fold(context, fold)
    momentum_col = "momentum_12_1" if "momentum_12_1" in features.columns else "trailing_return_26w"
    score = features[["Date", "ticker", momentum_col]].rename(columns={momentum_col: "score"})
    rows = []
    for top_n in TOP_NS:
        raw = mlx5.weights_from_scores(score, dates, context["tickers"], top_n, "inverse_vol", context["next_returns"], context["vol_panel"])
        path = mlx5.compute_path(raw, context["next_returns"], DEFAULT_COST_BPS)
        metrics = mlx5.calc_metrics(path)
        metrics.update({"benchmark_name": f"simple_momentum_{momentum_col}_top{top_n}_inverse_vol", "fold_name": fold["fold_name"]})
        rows.append(metrics)
    best = pd.DataFrame(rows).sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict()
    return best


def static_baseline_metric(mlx5: Any, context: dict[str, Any], fold: pd.Series, name: str) -> dict[str, Any]:
    dates = test_dates_for_fold(context, fold)
    weights = mlx5.static_baseline_weights(name, dates, context["tickers"], context["next_returns"])
    path = mlx5.compute_path(weights, context["next_returns"], DEFAULT_COST_BPS)
    metrics = mlx5.calc_metrics(path)
    metrics.update({"benchmark_name": name, "fold_name": fold["fold_name"]})
    return metrics


def select_project_files(mlx5: Any, warnings_list: list[str]) -> dict[str, Path]:
    selected: dict[str, Path] = {}
    if SEQUENCE_PROJECT_COMPARISON_IN.exists():
        comp = pd.read_csv(SEQUENCE_PROJECT_COMPARISON_IN)
        for category in ["current_production", "official_shadow", "phase4b", "phase6", "phase7"]:
            sub = comp[comp["category"].eq(category)] if "category" in comp.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No project comparison found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
            path = ROOT / str(row["source_path"])
            if path.exists():
                selected[category] = path
            else:
                warn(f"Project comparison file missing for {category}: {path}", warnings_list)
    else:
        warn("MLX-5 project comparison file missing; using discovered project strategy files only.", warnings_list)

    discovered = mlx5.discover_project_strategy_files()
    for name, path in discovered.items():
        category = mlx5.classify_project_strategy(name)
        if category in {"current_production", "official_shadow", "phase4b", "phase6", "phase7"}:
            selected.setdefault(category, path)
    return selected


def project_metric_for_fold(mlx5: Any, path: Path, fold: pd.Series, warnings_list: list[str]) -> dict[str, Any]:
    try:
        df = mlx5.read_project_return_file(path)
        sub = df.loc[(df.index >= fold["test_start"]) & (df.index <= fold["test_end"])]
        return mlx5.calc_metrics(sub)
    except Exception as exc:
        warn(f"Could not compute project benchmark for {path}: {exc}", warnings_list)
        return {}


def build_benchmark_table(mlx5: Any, features: pd.DataFrame, context: dict[str, Any], folds: pd.DataFrame, project_files: dict[str, Path], warnings_list: list[str]) -> pd.DataFrame:
    seq_backtest = pd.read_csv(SEQUENCE_RETURNS_IN, parse_dates=["Date"]) if SEQUENCE_RETURNS_IN.exists() else pd.DataFrame()
    rows = []
    for _, fold in folds.iterrows():
        benchmarks: dict[str, dict[str, Any]] = {
            "simple_momentum": baseline_momentum_metrics(mlx5, features, context, fold),
            "SPY": static_baseline_metric(mlx5, context, fold, "baseline_spy_buy_hold"),
            "60_40": static_baseline_metric(mlx5, context, fold, "baseline_60_40_spy_ief_or_agg"),
        }
        if not seq_backtest.empty:
            seq_names = {
                "MLX5_original_best": "lstm_classifier_top_quintile_forward_4w_seq26__top10__inverse_vol__bil_fallback",
                "MLX4_best_MLP": "mlx4_best_mlp",
                "MLX3_best_tabular": "mlx3_best_tabular_ml",
            }
            for label, strategy in seq_names.items():
                sub = seq_backtest[seq_backtest["strategy_name"].eq(strategy)].copy()
                if not sub.empty:
                    sub = sub.set_index("Date").sort_index()
                    sub = sub.loc[(sub.index >= fold["test_start"]) & (sub.index <= fold["test_end"])]
                    metrics = mlx5.calc_metrics(sub)
                    metrics["benchmark_name"] = label
                    benchmarks[label] = metrics
        for category, path in project_files.items():
            metrics = project_metric_for_fold(mlx5, path, fold, warnings_list)
            metrics["benchmark_name"] = category
            metrics["source_path"] = str(path.relative_to(ROOT))
            benchmarks[category] = metrics
        for name, metrics in benchmarks.items():
            metrics.update({
                "fold_name": fold["fold_name"],
                "benchmark_name": name,
                "test_start": fold["test_start"].date().isoformat(),
                "test_end": fold["test_end"].date().isoformat(),
            })
            rows.append(metrics)
    return pd.DataFrame(rows)


def add_benchmark_flags(run_metrics: pd.DataFrame, benchmark_table: pd.DataFrame) -> pd.DataFrame:
    out = run_metrics.copy()
    pivot = benchmark_table.pivot_table(index="fold_name", columns="benchmark_name", values="sharpe", aggfunc="max")
    for benchmark in ["simple_momentum", "current_production", "official_shadow", "phase4b", "phase6", "phase7", "SPY", "60_40"]:
        values = pivot[benchmark] if benchmark in pivot.columns else pd.Series(dtype=float)
        out[f"{benchmark}_sharpe"] = out["fold_name"].map(values)
        out[f"beats_{benchmark}"] = out["sharpe"] > out[f"{benchmark}_sharpe"]
    return out


def stability_summary(run_metrics: pd.DataFrame) -> pd.DataFrame:
    focus = run_metrics[run_metrics["wrapper"].eq("bil_fallback_original")].copy()
    groups: list[tuple[str, list[str]]] = [
        ("overall", []),
        ("model_type", ["model_type"]),
        ("sequence_length", ["sequence_length"]),
        ("seed", ["seed"]),
        ("fold", ["fold_name"]),
        ("top_n", ["top_n"]),
    ]
    rows = []
    for group_type, cols in groups:
        iterator = [((), focus)] if not cols else focus.groupby(cols, dropna=False)
        for key, sub in iterator:
            if sub.empty:
                continue
            if not isinstance(key, tuple):
                key = (key,)
            row = {
                "group_type": group_type,
                "group_value": "overall" if not cols else "|".join(str(x) for x in key),
                "runs": int(len(sub)),
                "mean_sharpe": float(sub["sharpe"].mean()),
                "median_sharpe": float(sub["sharpe"].median()),
                "min_sharpe": float(sub["sharpe"].min()),
                "max_sharpe": float(sub["sharpe"].max()),
                "std_sharpe": float(sub["sharpe"].std(ddof=0)),
                "pct_sharpe_gt_0": float((sub["sharpe"] > 0).mean()),
                "pct_beating_simple_momentum": float(sub["beats_simple_momentum"].fillna(False).mean()),
                "pct_beating_current_production": float(sub["beats_current_production"].fillna(False).mean()),
                "pct_beating_official_shadow": float(sub["beats_official_shadow"].fillna(False).mean()),
                "pct_beating_phase4b": float(sub["beats_phase4b"].fillna(False).mean()),
                "worst_case_max_drawdown": float(sub["max_drawdown"].min()),
                "worst_case_cvar_5": float(sub["cvar_5"].min()),
            }
            rows.append(row)
    return pd.DataFrame(rows)


def train_and_evaluate(mlx5: Any, torch: Any, features: pd.DataFrame, targets: pd.DataFrame, context: dict[str, Any], folds: pd.DataFrame, run_grid: list[RunSpec], skipped: list[dict[str, Any]], warnings_list: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pred_frames: list[pd.DataFrame] = []
    return_frames: list[pd.DataFrame] = []
    metric_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []

    fold_map = {row["fold_name"]: row for _, row in folds.iterrows()}
    prepared_by_fold: dict[str, dict[str, Any]] = {}
    split_by_fold: dict[str, pd.Series] = {}
    ids = features[["Date", "ticker"]].copy()

    for i, spec in enumerate(run_grid, start=1):
        print(f"Running MLX-5C {i}/{len(run_grid)}: fold={spec.fold_name} model={spec.model_type} seq={spec.sequence_length} seed={spec.seed}", flush=True)
        fold = fold_map[spec.fold_name]
        if spec.fold_name not in prepared_by_fold:
            split = split_for_fold(features, fold)
            split_by_fold[spec.fold_name] = split
            prepared_by_fold[spec.fold_name] = mlx5.prepare_features(features, split)
        split = split_by_fold[spec.fold_name]
        prepared = prepared_by_fold[spec.fold_name]
        all_end_indices = mlx5.valid_sequence_end_indices(features, spec.sequence_length)
        test_idx = all_end_indices[(split.iloc[all_end_indices].to_numpy() == "test")]
        if len(test_idx) < 100:
            skipped.append({**spec.__dict__, "reason": "insufficient test sequences"})
            continue
        set_run_seed(torch, spec.seed)
        config = mlx5.SequenceConfig(
            model_name=f"{spec.model_type}_seq{spec.sequence_length}_seed{spec.seed}_{spec.fold_name}",
            target=TARGET,
            model_type=spec.model_type,
            hidden_size=HIDDEN_SIZE,
            dropout=DROPOUT,
            seq_len=spec.sequence_length,
            max_epochs=MAX_EPOCHS,
            patience=PATIENCE,
        )
        model, curves, meta = mlx5.train_sequence_model(torch, config, prepared["x"], targets[TARGET], split, all_end_indices, "cpu", warnings_list)
        if model is None:
            skipped.append({**spec.__dict__, "reason": meta.get("reason", "training skipped")})
            continue
        scores = mlx5.predict_sequence_model(torch, model, prepared["x"], test_idx, spec.sequence_length, "cpu")
        pred = ids.iloc[test_idx].copy()
        pred["fold_name"] = spec.fold_name
        pred["model_type"] = spec.model_type
        pred["sequence_length"] = spec.sequence_length
        pred["seed"] = spec.seed
        pred["model_name"] = config.model_name
        pred["target"] = TARGET
        pred["score"] = scores
        pred["actual_target"] = targets[TARGET].iloc[test_idx].values
        pred_frames.append(pred)
        if not curves.empty:
            curves = curves.copy()
            curves["fold_name"] = spec.fold_name
            curves["seed"] = spec.seed
            curves["best_validation_loss_final"] = meta.get("best_validation_loss")
            curve_frames.append(curves)
        paths, metrics = run_portfolios_for_predictions(mlx5, pred, context, fold, spec)
        return_frames.append(paths)
        metric_frames.append(metrics)

    predictions = pd.concat(pred_frames, ignore_index=True) if pred_frames else pd.DataFrame()
    returns = pd.concat(return_frames, ignore_index=True) if return_frames else pd.DataFrame()
    metrics = pd.concat(metric_frames, ignore_index=True) if metric_frames else pd.DataFrame()
    curves = pd.concat(curve_frames, ignore_index=True) if curve_frames else pd.DataFrame()
    return predictions, returns, metrics, curves


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
    pct_cols = [c for c in sub.columns if c.startswith("pct_") or c in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "annual_cost_drag", "average_bil_weight", "worst_case_max_drawdown", "worst_case_cvar_5"}]
    for col in pct_cols:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(pct)
    for col in [c for c in ["sharpe", "mean_sharpe", "median_sharpe", "min_sharpe", "max_sharpe", "std_sharpe", "calmar"] if c in sub.columns]:
        sub[col] = pd.to_numeric(sub[col], errors="coerce").map(num)
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def choose_recommendation(stability: pd.DataFrame) -> str:
    overall = stability[(stability["group_type"].eq("overall")) & (stability["group_value"].eq("overall"))]
    if overall.empty:
        return "REJECT"
    row = overall.iloc[0]
    if row["mean_sharpe"] > 0.7 and row["pct_sharpe_gt_0"] >= 0.75 and row["pct_beating_current_production"] >= 0.50:
        return "PROMISING OFFENSIVE SLEEVE BUT NOT PRODUCTION"
    if row["mean_sharpe"] > 0.4 and row["pct_sharpe_gt_0"] >= 0.60:
        return "KEEP AS ML SHADOW"
    return "KEEP AS RESEARCH ONLY"


def write_report(summary: dict[str, Any], stability: pd.DataFrame, run_metrics: pd.DataFrame, benchmark_table: pd.DataFrame, folds: pd.DataFrame, skipped: list[dict[str, Any]], warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    focus = run_metrics[run_metrics["wrapper"].eq("bil_fallback_original")].copy()
    best_runs = focus.sort_values(["sharpe", "annual_return"], ascending=[False, False]).head(12)
    worst_runs = focus.sort_values(["sharpe", "annual_return"], ascending=[True, True]).head(8)
    fold_perf = stability[stability["group_type"].eq("fold")]
    model_perf = stability[stability["group_type"].eq("model_type")]
    seq_perf = stability[stability["group_type"].eq("sequence_length")]
    seed_perf = stability[stability["group_type"].eq("seed")]
    skip_lines = "\n".join(f"- {s.get('fold_name')} {s.get('model_type')} seq{s.get('sequence_length')} seed{s.get('seed')}: {s.get('reason')}" for s in skipped[:40]) or "- None"
    if len(skipped) > 40:
        skip_lines += f"\n- ... {len(skipped) - 40} additional bounded-grid skips recorded in JSON."
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"

    REPORT_OUT.write_text(f"""# Phase MLX-5C Sequence Multi-Seed Walk-Forward Report

## Research-Only Warning

Phase MLX-5C is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Random seed robustness checks whether a neural network result changes when training starts from different random initial weights and mini-batch order. Neural networks can produce different results from different seeds because optimization is non-convex and many parameter settings can fit noisy financial data.

Walk-forward validation trains on older data, validates on the next period, and tests on a later unseen period, then repeats this chronology across several market windows. It is more realistic than one train/validation/holdout split because it asks whether a strategy keeps working as market regimes change. Sequence length sensitivity checks whether the model depends on one very specific lookback window. This matters before trusting MLX-5 because a single 2020+ holdout win can still be seed-specific, regime-specific, or overlay-specific.

## Executive Summary

- Grid actually run: {summary['runs_completed']} training runs, {summary['portfolio_rows']} portfolio variants.
- Sequence lengths tested: {summary['sequence_lengths_tested']}
- Seeds tested: {summary['seeds_tested']}
- Folds tested: {summary['folds_tested']}
- Mean Sharpe across bil-fallback runs: {num(summary['overall_mean_sharpe'])}
- Median Sharpe: {num(summary['overall_median_sharpe'])}
- Worst Sharpe: {num(summary['overall_min_sharpe'])}
- Percent Sharpe > 0: {pct(summary['overall_pct_sharpe_gt_0'])}
- Percent beating simple momentum: {pct(summary['overall_pct_beating_simple_momentum'])}
- Percent beating production: {pct(summary['overall_pct_beating_current_production'])}
- Percent beating Phase 4B: {pct(summary['overall_pct_beating_phase4b'])}
- Worst max drawdown: {pct(summary['overall_worst_case_max_drawdown'])}
- Worst CVaR 5%: {pct(summary['overall_worst_case_cvar_5'])}
- Final recommendation: **{summary['final_recommendation']}**

## MLX-5 / MLX-5B Recap

MLX-5 found a promising LSTM sequence model with BIL fallback in the 2020+ holdout, but MLX-5B showed weaker 2018+ performance, negative COVID crash/rebound performance, high cost sensitivity, weak calm-trend results, and no random-seed robustness yet. MLX-5C directly tests those open questions with multiple chronological folds and bounded seed/model/sequence variations.

## Fold Definitions

{markdown_table(folds, ['fold_name', 'train_start', 'train_end', 'validation_start', 'validation_end', 'test_start', 'test_end'], max_rows=10)}

## Stability By Model

{markdown_table(model_perf, ['group_value', 'runs', 'mean_sharpe', 'median_sharpe', 'min_sharpe', 'max_sharpe', 'std_sharpe', 'pct_sharpe_gt_0', 'pct_beating_simple_momentum', 'pct_beating_current_production', 'pct_beating_phase4b', 'worst_case_max_drawdown', 'worst_case_cvar_5'])}

## Stability By Sequence Length

{markdown_table(seq_perf, ['group_value', 'runs', 'mean_sharpe', 'median_sharpe', 'min_sharpe', 'max_sharpe', 'std_sharpe', 'pct_sharpe_gt_0', 'pct_beating_simple_momentum', 'pct_beating_current_production', 'pct_beating_phase4b', 'worst_case_max_drawdown', 'worst_case_cvar_5'])}

## Stability By Seed

{markdown_table(seed_perf, ['group_value', 'runs', 'mean_sharpe', 'median_sharpe', 'min_sharpe', 'max_sharpe', 'std_sharpe', 'pct_sharpe_gt_0', 'pct_beating_simple_momentum', 'pct_beating_current_production', 'pct_beating_phase4b', 'worst_case_max_drawdown', 'worst_case_cvar_5'])}

## Walk-Forward Fold Performance

{markdown_table(fold_perf, ['group_value', 'runs', 'mean_sharpe', 'median_sharpe', 'min_sharpe', 'max_sharpe', 'std_sharpe', 'pct_sharpe_gt_0', 'pct_beating_simple_momentum', 'pct_beating_current_production', 'pct_beating_phase4b', 'worst_case_max_drawdown', 'worst_case_cvar_5'])}

## Best Bil-Fallback Runs

{markdown_table(best_runs, ['fold_name', 'model_type', 'sequence_length', 'seed', 'top_n', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'average_bil_weight', 'beats_simple_momentum', 'beats_current_production', 'beats_phase4b'])}

## Worst Bil-Fallback Runs

{markdown_table(worst_runs, ['fold_name', 'model_type', 'sequence_length', 'seed', 'top_n', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'average_bil_weight', 'beats_simple_momentum', 'beats_current_production', 'beats_phase4b'])}

## Benchmark Comparison

{markdown_table(benchmark_table.sort_values(['fold_name', 'benchmark_name']), ['fold_name', 'benchmark_name', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover'], max_rows=40)}

## Skipped Runs

{skip_lines}

## Interpretation

The MLX-5 edge survives only if the average and worst-case rows above remain acceptable across folds, not merely because one 2020+ configuration looked good. If the average fold is weak but one fold is strong, this should stay research-only or ML-shadow at most. If the result remains positive across seeds and folds but does not reliably beat Phase 4B or production risk metrics, it is better framed as a possible offensive sleeve rather than a standalone strategy.

## Warnings

{warn_lines}
""")


def empty_outputs(reason: str, warnings_list: list[str]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame().to_parquet(PREDICTIONS_OUT, index=False)
    pd.DataFrame().to_csv(BACKTEST_RETURNS_OUT, index=False)
    pd.DataFrame().to_csv(RUN_METRICS_OUT, index=False)
    pd.DataFrame().to_csv(STABILITY_SUMMARY_OUT, index=False)
    pd.DataFrame().to_csv(FOLD_DEFINITIONS_OUT, index=False)
    pd.DataFrame().to_csv(TRAINING_CURVES_OUT, index=False)
    pd.DataFrame().to_csv(STRATEGY_COMPARISON_OUT, index=False)
    skipped = [{"reason": reason}]
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2) + "\n")
    summary = {"phase": "MLX-5C", "production_valid": False, "research_only": True, "reason": reason, "warnings": warnings_list}
    SUMMARY_JSON_OUT.write_text(json.dumps(summary, indent=2, default=json_default))
    REPORT_OUT.write_text(f"""# Phase MLX-5C Sequence Multi-Seed Walk-Forward Report

## Research-Only Warning

Experimental only. Not production-valid. High overfitting risk. No production pins changed.

## Educational Explanation

Random seed robustness and walk-forward validation test whether a neural-network result survives different initialization and different chronological train/test windows.

## Results

Training was skipped: {reason}
""")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    torch_meta = torch_status()
    if not torch_meta.get("available"):
        warn("torch is missing; skipping MLX-5C sequence training.", warnings_list)
        empty_outputs("torch missing", warnings_list)
        return
    import torch

    mlx5 = load_mlx5_module()
    mlx5.BATCH_SIZE = 4096
    features, targets, weekly_returns = load_inputs(mlx5)
    if "BIL" not in weekly_returns.columns:
        warn("BIL returns not found in expanded weekly returns; fallback exposure may be incomplete.", warnings_list)

    context = make_context(mlx5, features)
    folds = fold_definitions(pd.Timestamp(features["Date"].max()))
    run_grid, skipped = build_grid(folds)
    folds.to_csv(FOLD_DEFINITIONS_OUT, index=False)
    project_files = select_project_files(mlx5, warnings_list)
    benchmark_table = build_benchmark_table(mlx5, features, context, folds, project_files, warnings_list)

    predictions, returns, run_metrics, curves = train_and_evaluate(mlx5, torch, features, targets, context, folds, run_grid, skipped, warnings_list)
    if run_metrics.empty:
        warn("No MLX-5C run metrics were produced.", warnings_list)
        stability = pd.DataFrame()
    else:
        run_metrics = add_benchmark_flags(run_metrics, benchmark_table)
        stability = stability_summary(run_metrics)

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    returns.to_csv(BACKTEST_RETURNS_OUT, index=False)
    run_metrics.to_csv(RUN_METRICS_OUT, index=False)
    stability.to_csv(STABILITY_SUMMARY_OUT, index=False)
    curves.to_csv(TRAINING_CURVES_OUT, index=False)
    benchmark_table.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    SKIPPED_RUNS_OUT.write_text(json.dumps(skipped, indent=2, default=json_default) + "\n")

    overall = stability[(stability["group_type"].eq("overall")) & (stability["group_value"].eq("overall"))].iloc[0].to_dict() if not stability.empty else {}
    recommendation = choose_recommendation(stability) if not stability.empty else "REJECT"
    focus = run_metrics[run_metrics["wrapper"].eq("bil_fallback_original")] if not run_metrics.empty else pd.DataFrame()
    completed_training_runs = int(predictions["model_name"].nunique()) if not predictions.empty and "model_name" in predictions.columns else 0
    summary = {
        "phase": "MLX-5C multi-seed walk-forward sequence robustness",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "torch": torch_meta,
        "device_used": "cpu",
        "bounded_runtime": True,
        "runs_completed": completed_training_runs,
        "portfolio_rows": int(len(run_metrics)),
        "sequence_lengths_tested": sorted(focus["sequence_length"].dropna().astype(int).unique().tolist()) if not focus.empty else [],
        "seeds_tested": sorted(focus["seed"].dropna().astype(int).unique().tolist()) if not focus.empty else [],
        "folds_tested": sorted(focus["fold_name"].dropna().unique().tolist()) if not focus.empty else [],
        "model_types_tested": sorted(focus["model_type"].dropna().unique().tolist()) if not focus.empty else [],
        "theoretical_grid_runs": int(len(folds) * len(MODEL_TYPES) * len(SEQUENCE_LENGTHS) * len(SEEDS)),
        "bounded_training_runs_planned": int(len(run_grid)),
        "skipped_runs": int(len(skipped)),
        "overall_mean_sharpe": overall.get("mean_sharpe", np.nan),
        "overall_median_sharpe": overall.get("median_sharpe", np.nan),
        "overall_min_sharpe": overall.get("min_sharpe", np.nan),
        "overall_max_sharpe": overall.get("max_sharpe", np.nan),
        "overall_std_sharpe": overall.get("std_sharpe", np.nan),
        "overall_pct_sharpe_gt_0": overall.get("pct_sharpe_gt_0", np.nan),
        "overall_pct_beating_simple_momentum": overall.get("pct_beating_simple_momentum", np.nan),
        "overall_pct_beating_current_production": overall.get("pct_beating_current_production", np.nan),
        "overall_pct_beating_official_shadow": overall.get("pct_beating_official_shadow", np.nan),
        "overall_pct_beating_phase4b": overall.get("pct_beating_phase4b", np.nan),
        "overall_worst_case_max_drawdown": overall.get("worst_case_max_drawdown", np.nan),
        "overall_worst_case_cvar_5": overall.get("worst_case_cvar_5", np.nan),
        "final_recommendation": recommendation,
        "warnings": warnings_list + ["52-week sequence grid and full GRU/TCN seed expansion skipped for bounded CPU runtime.", "Experimental research-only Phase MLX output; not production-valid."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "backtest_returns": str(BACKTEST_RETURNS_OUT.relative_to(ROOT)),
            "run_metrics": str(RUN_METRICS_OUT.relative_to(ROOT)),
            "stability_summary": str(STABILITY_SUMMARY_OUT.relative_to(ROOT)),
            "fold_definitions": str(FOLD_DEFINITIONS_OUT.relative_to(ROOT)),
            "training_curves": str(TRAINING_CURVES_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "skipped_runs": str(SKIPPED_RUNS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "markdown_report": str(REPORT_OUT.relative_to(ROOT)),
        },
    }
    SUMMARY_JSON_OUT.write_text(json.dumps(summary, indent=2, default=json_default))
    write_report(summary, stability, run_metrics, benchmark_table, folds, skipped, summary["warnings"],)

    print("Phase MLX-5C multi-seed walk-forward sequence robustness")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Torch available: {torch_meta.get('available')} version={torch_meta.get('version')}")
    print("Device used: cpu")
    print(f"Training runs planned: {len(run_grid)}")
    print(f"Portfolio rows: {len(run_metrics)}")
    print(f"Sequence lengths tested: {summary['sequence_lengths_tested']}")
    print(f"Seeds tested: {summary['seeds_tested']}")
    print(f"Folds tested: {summary['folds_tested']}")
    print(f"Mean Sharpe: {summary['overall_mean_sharpe']}")
    print(f"Median Sharpe: {summary['overall_median_sharpe']}")
    print(f"Worst Sharpe: {summary['overall_min_sharpe']}")
    print(f"Final recommendation: {summary['final_recommendation']}")
    print("Outputs:")
    for path in [
        PREDICTIONS_OUT,
        BACKTEST_RETURNS_OUT,
        RUN_METRICS_OUT,
        STABILITY_SUMMARY_OUT,
        FOLD_DEFINITIONS_OUT,
        TRAINING_CURVES_OUT,
        STRATEGY_COMPARISON_OUT,
        SKIPPED_RUNS_OUT,
        SUMMARY_JSON_OUT,
        REPORT_OUT,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
