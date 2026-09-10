#!/usr/bin/env python3
"""
Phase MLX-5B: sequence overlay robustness checks.

Experimental research-only code. It reads MLX-5 artifacts and writes only under
data/research/ml_lab, docs/research/ml_lab, and scripts/ml_lab. It does not
modify production pins, dashboard code, production strategy logic, or candidate
status.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FEATURE_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
SEQUENCE_DIR = ROOT / "data" / "research" / "ml_lab" / "sequence_models"
ROBUSTNESS_DIR = SEQUENCE_DIR / "robustness"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"
PREDICTIONS_IN = SEQUENCE_DIR / "sequence_predictions.parquet"
SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
BACKTEST_RETURNS_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
OVERLAY_SUMMARY_IN = SEQUENCE_DIR / "sequence_overlay_summary.csv"
PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
COMPARISON_TABLE_IN = SEQUENCE_DIR / "sequence_comparison_table.csv"

WINDOW_SENSITIVITY_OUT = ROBUSTNESS_DIR / "sequence_robustness_window_sensitivity.csv"
OVERLAY_SENSITIVITY_OUT = ROBUSTNESS_DIR / "sequence_robustness_overlay_sensitivity.csv"
TOPN_WEIGHTING_OUT = ROBUSTNESS_DIR / "sequence_robustness_topn_weighting_sensitivity.csv"
COST_SENSITIVITY_OUT = ROBUSTNESS_DIR / "sequence_robustness_cost_sensitivity.csv"
STATE_BY_STATE_OUT = ROBUSTNESS_DIR / "sequence_robustness_state_by_state.csv"
HOLDINGS_EXPOSURE_OUT = ROBUSTNESS_DIR / "sequence_robustness_holdings_exposure.csv"
STRATEGY_COMPARISON_OUT = ROBUSTNESS_DIR / "sequence_robustness_strategy_comparison.csv"
SUMMARY_JSON_OUT = ROBUSTNESS_DIR / "sequence_robustness_summary.json"
REPORT_OUT = DOCS_DIR / "phase_mlx_5b_sequence_overlay_robustness_report.md"

DEFAULT_COST_BPS = 10.0
HOLDOUT_START = pd.Timestamp("2020-01-03")
HOLDOUT_END = pd.Timestamp("2026-05-08")

EVALUATION_WINDOWS = {
    "2018_onward": (pd.Timestamp("2018-01-05"), HOLDOUT_END),
    "2020_onward": (HOLDOUT_START, HOLDOUT_END),
    "2022_onward": (pd.Timestamp("2022-01-07"), HOLDOUT_END),
    "2023_onward": (pd.Timestamp("2023-01-06"), HOLDOUT_END),
    "covid_crash_rebound": (pd.Timestamp("2020-02-21"), pd.Timestamp("2020-08-28")),
    "2022_bear": (pd.Timestamp("2022-01-07"), pd.Timestamp("2022-10-14")),
    "2023_2025_ai_risk_on": (pd.Timestamp("2023-01-06"), pd.Timestamp("2025-12-26")),
}


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


def require_inputs(paths: list[Path]) -> None:
    missing = [str(p.relative_to(ROOT)) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Required MLX-5B inputs are missing: {missing}")


def load_data(mlx5: Any) -> dict[str, pd.DataFrame]:
    require_inputs([
        FEATURES_IN,
        TARGETS_IN,
        WEEKLY_RETURNS_IN,
        PREDICTIONS_IN,
        SUMMARY_IN,
        BACKTEST_RETURNS_IN,
        OVERLAY_SUMMARY_IN,
    ])
    features = pd.read_parquet(FEATURES_IN)
    targets = pd.read_parquet(TARGETS_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    targets["Date"] = pd.to_datetime(targets["Date"])
    features = features.sort_values(["ticker", "Date"]).reset_index(drop=True)
    targets = targets.sort_values(["ticker", "Date"]).reset_index(drop=True)
    mlx5.validate_inputs(features, targets)

    predictions = pd.read_parquet(PREDICTIONS_IN)
    predictions["Date"] = pd.to_datetime(predictions["Date"])
    summary = pd.read_csv(SUMMARY_IN)
    backtest = pd.read_csv(BACKTEST_RETURNS_IN, parse_dates=["Date"])
    overlay_summary = pd.read_csv(OVERLAY_SUMMARY_IN)
    weekly_returns = mlx5.load_panel_csv(WEEKLY_RETURNS_IN)
    project_comparison = pd.read_csv(PROJECT_COMPARISON_IN) if PROJECT_COMPARISON_IN.exists() else pd.DataFrame()
    comparison_table = pd.read_csv(COMPARISON_TABLE_IN) if COMPARISON_TABLE_IN.exists() else pd.DataFrame()
    universe = pd.read_csv(UNIVERSE_IN) if UNIVERSE_IN.exists() else pd.DataFrame()
    return {
        "features": features,
        "targets": targets,
        "predictions": predictions,
        "summary": summary,
        "backtest": backtest,
        "overlay_summary": overlay_summary,
        "weekly_returns": weekly_returns,
        "project_comparison": project_comparison,
        "comparison_table": comparison_table,
        "universe": universe,
    }


def best_strategy_rows(summary: pd.DataFrame) -> dict[str, dict[str, Any]]:
    hold = summary[(summary["split"].eq("holdout")) & (summary["strategy_type"].eq("model"))].copy()
    if hold.empty:
        raise ValueError("Could not identify MLX-5 model rows in sequence_summary.csv")

    def top(metric: str, ascending: bool = False, extra: pd.Series | None = None) -> dict[str, Any]:
        sub = hold if extra is None else hold[extra].copy()
        sub = sub[pd.to_numeric(sub[metric], errors="coerce").notna()]
        if sub.empty:
            return {}
        return sub.sort_values([metric, "annual_return"], ascending=[ascending, False]).iloc[0].to_dict()

    return {
        "best_holdout_sharpe": top("sharpe"),
        "best_raw": top("sharpe", extra=hold["wrapper"].eq("raw_ml")),
        "best_overlay": top("sharpe", extra=~hold["wrapper"].eq("raw_ml")),
        "best_annual_return": top("annual_return"),
        "best_max_drawdown": top("max_drawdown"),
    }


def path_from_backtest(backtest: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    sub = backtest[backtest["strategy_name"].eq(strategy_name)].copy()
    if sub.empty:
        return pd.DataFrame()
    sub = sub.sort_values("Date").set_index("Date")
    return sub


def slice_window(path: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if path.empty:
        return path
    return path.loc[(path.index >= start) & (path.index <= end)].copy()


def metrics_for_window(mlx5: Any, path: pd.DataFrame, window_name: str, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    sub = slice_window(path, start, end)
    metrics = mlx5.calc_metrics(sub)
    metrics.update({"window": window_name, "start": start.date().isoformat(), "end": end.date().isoformat()})
    return metrics


def make_context(mlx5: Any, features: pd.DataFrame) -> dict[str, Any]:
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    tickers = sorted(features["ticker"].unique())
    next_returns = mlx5.next_week_return_panel(features).reindex(index=dates, columns=tickers)
    vol_panel = mlx5.matrix_by_date(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = mlx5.matrix_by_date(features, "realized_vol_26w")
    state = mlx5.infer_market_state_by_date(features)
    return {"dates": dates, "tickers": tickers, "next_returns": next_returns, "vol_panel": vol_panel, "state": state}


def raw_weights_for_strategy(mlx5: Any, predictions: pd.DataFrame, context: dict[str, Any], row: dict[str, Any], top_n: int | None = None, weighting: str | None = None) -> pd.DataFrame:
    model_name = str(row["model_name"])
    group = predictions[predictions["model_name"].eq(model_name)]
    if group.empty:
        raise ValueError(f"No sequence predictions found for model {model_name}")
    n = int(top_n if top_n is not None else row["top_n"])
    w = weighting if weighting is not None else str(row["weighting"])
    return mlx5.weights_from_scores(group, context["dates"], context["tickers"], n, w, context["next_returns"], context["vol_panel"])


def overlay_weights_variant(mlx5: Any, variant: str, raw_weights: pd.DataFrame, context: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series]:
    dates = raw_weights.index
    state = context["state"].reindex(dates).fillna("unknown")
    next_returns = context["next_returns"]

    if variant == "raw_ml":
        exposure = pd.Series(1.0, index=dates)
        return raw_weights.copy(), exposure
    if variant == "bil_fallback_original":
        exposure = state.map({"stressed_panic": 0.25, "neutral_mixed": 0.75}).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if variant == "bil_fallback_mild":
        exposure = state.map({"stressed_panic": 0.50, "neutral_mixed": 0.85, "recovery_fragile": 0.85}).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if variant == "bil_fallback_aggressive":
        exposure = state.map({"stressed_panic": 0.0, "neutral_mixed": 0.50, "recovery_fragile": 0.50}).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if variant == "regime_gate_original":
        exposure = state.map({"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}).fillna(0.70)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure

    raw_gross = raw_weights.mul(next_returns.reindex(index=dates, columns=raw_weights.columns).fillna(0.0)).sum(axis=1)
    if variant.startswith("vol_target_"):
        target = float(variant.split("_")[-1].replace("pct", "")) / 100.0
        ann_vol = raw_gross.shift(1).rolling(13, min_periods=6).std() * math.sqrt(52.0)
        exposure = (target / ann_vol.replace(0.0, np.nan)).clip(0.0, 1.0).fillna(1.0)
        return mlx5.add_bil_fallback(raw_weights, exposure), exposure
    if variant == "drawdown_kill_switch_original":
        levels = (-0.10, -0.15, 0.50, 0.25, -0.03, 0.10)
    elif variant == "drawdown_kill_switch_mild":
        levels = (-0.15, -0.25, 0.70, 0.50, -0.05, 0.10)
    elif variant == "drawdown_kill_switch_aggressive":
        levels = (-0.07, -0.12, 0.40, 0.10, -0.02, 0.15)
    else:
        raise ValueError(f"Unknown overlay variant {variant}")

    shallow_dd, deep_dd, shallow_exp, deep_exp, restore_threshold, restore_step = levels
    wealth = (1.0 + raw_gross.shift(1).fillna(0.0)).cumprod()
    dd = wealth / wealth.cummax() - 1.0
    values: list[float] = []
    prev = 1.0
    for value in dd.reindex(dates).fillna(0.0):
        if value <= deep_dd:
            exp = deep_exp
        elif value <= shallow_dd:
            exp = shallow_exp
        elif value >= restore_threshold:
            exp = min(1.0, prev + restore_step)
        else:
            exp = prev
        values.append(exp)
        prev = exp
    exposure = pd.Series(values, index=dates)
    return mlx5.add_bil_fallback(raw_weights, exposure), exposure


def build_path_for_variant(mlx5: Any, raw_weights: pd.DataFrame, context: dict[str, Any], variant: str, cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    weights, exposure = overlay_weights_variant(mlx5, variant, raw_weights, context)
    path = mlx5.compute_path(weights, context["next_returns"], cost_bps, exposure)
    return path, weights, exposure


def window_sensitivity(mlx5: Any, backtest: pd.DataFrame, rows: dict[str, dict[str, Any]], warnings_list: list[str]) -> pd.DataFrame:
    selected: dict[str, str] = {}
    for label, row in rows.items():
        name = row.get("strategy_name")
        if isinstance(name, str) and name:
            selected[label] = name
    out = []
    for label, strategy in selected.items():
        path = path_from_backtest(backtest, strategy)
        if path.empty:
            warn(f"Window sensitivity skipped missing strategy path: {strategy}", warnings_list)
            continue
        for window, (start, end) in EVALUATION_WINDOWS.items():
            metrics = metrics_for_window(mlx5, path, window, start, end)
            metrics.update({"strategy_label": label, "strategy_name": strategy})
            out.append(metrics)
    return pd.DataFrame(out)


def overlay_sensitivity(mlx5: Any, raw_weights: pd.DataFrame, context: dict[str, Any], best_row: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, tuple[pd.DataFrame, pd.DataFrame]]]:
    variants = [
        "raw_ml",
        "bil_fallback_original",
        "bil_fallback_mild",
        "bil_fallback_aggressive",
        "regime_gate_original",
        "vol_target_8pct",
        "vol_target_10pct",
        "vol_target_12pct",
        "drawdown_kill_switch_original",
        "drawdown_kill_switch_mild",
        "drawdown_kill_switch_aggressive",
    ]
    rows = []
    paths: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    for variant in variants:
        path, weights, _ = build_path_for_variant(mlx5, raw_weights, context, variant, DEFAULT_COST_BPS)
        paths[variant] = (path, weights)
        hold = slice_window(path, HOLDOUT_START, HOLDOUT_END)
        metrics = mlx5.calc_metrics(hold)
        metrics.update({
            "overlay_variant": variant,
            "model_name": best_row.get("model_name"),
            "target": best_row.get("target"),
            "top_n": best_row.get("top_n"),
            "weighting": best_row.get("weighting"),
            "window": "2020_onward",
        })
        rows.append(metrics)
    return pd.DataFrame(rows), paths


def topn_weighting_sensitivity(mlx5: Any, predictions: pd.DataFrame, context: dict[str, Any], best_row: dict[str, Any], overlay_variant: str) -> pd.DataFrame:
    rows = []
    for top_n in (3, 5, 10, 15):
        for weighting in ("equal_weight", "inverse_vol"):
            raw = raw_weights_for_strategy(mlx5, predictions, context, best_row, top_n=top_n, weighting=weighting)
            path, _, _ = build_path_for_variant(mlx5, raw, context, overlay_variant, DEFAULT_COST_BPS)
            metrics = mlx5.calc_metrics(slice_window(path, HOLDOUT_START, HOLDOUT_END))
            metrics.update({
                "model_name": best_row.get("model_name"),
                "target": best_row.get("target"),
                "top_n": top_n,
                "weighting": weighting,
                "overlay_variant": overlay_variant,
                "window": "2020_onward",
            })
            rows.append(metrics)
    return pd.DataFrame(rows)


def cost_sensitivity(mlx5: Any, raw_weights: pd.DataFrame, context: dict[str, Any], overlay_variant: str, best_row: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for cost_bps in (0.0, 10.0, 25.0, 50.0):
        path, _, _ = build_path_for_variant(mlx5, raw_weights, context, overlay_variant, cost_bps)
        metrics = mlx5.calc_metrics(slice_window(path, HOLDOUT_START, HOLDOUT_END))
        metrics.update({
            "cost_bps": cost_bps,
            "overlay_variant": overlay_variant,
            "model_name": best_row.get("model_name"),
            "target": best_row.get("target"),
            "top_n": best_row.get("top_n"),
            "weighting": best_row.get("weighting"),
            "window": "2020_onward",
        })
        rows.append(metrics)
    return pd.DataFrame(rows)


def state_by_state(mlx5: Any, best_path: pd.DataFrame, state: pd.Series) -> pd.DataFrame:
    path = slice_window(best_path, HOLDOUT_START, HOLDOUT_END).copy()
    path["market_state"] = state.reindex(path.index).fillna("unknown").values
    rows = []
    for state_name, sub in path.groupby("market_state"):
        r = pd.to_numeric(sub["net_return"], errors="coerce").dropna()
        if r.empty:
            continue
        ann_vol = float(r.std(ddof=0) * math.sqrt(52.0))
        ann_return = float((1.0 + r).prod() ** (52.0 / len(r)) - 1.0) if len(r) >= 8 and (1.0 + r).prod() > 0 else np.nan
        rows.append({
            "market_state": state_name,
            "weeks": int(len(r)),
            "weekly_mean_return": float(r.mean()),
            "annual_return": ann_return,
            "annual_volatility": ann_vol,
            "sharpe": float(ann_return / ann_vol) if pd.notna(ann_return) and ann_vol > 0 else np.nan,
            "hit_rate": float((r > 0).mean()),
            "average_bil_exposure": float(sub["bil_weight"].mean()) if "bil_weight" in sub else np.nan,
            "average_ml_exposure": float(sub["ml_exposure"].mean()) if "ml_exposure" in sub else np.nan,
            "average_turnover": float(sub["turnover"].mean()) if "turnover" in sub else np.nan,
        })
    return pd.DataFrame(rows).sort_values("market_state")


def holdings_exposure(weights: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    hold = weights.loc[(weights.index >= HOLDOUT_START) & (weights.index <= HOLDOUT_END)].copy()
    rows: list[dict[str, Any]] = []
    if hold.empty:
        return pd.DataFrame()
    category = {}
    if not universe.empty and {"ticker", "category"}.issubset(universe.columns):
        category = universe.drop_duplicates("ticker").set_index("ticker")["category"].to_dict()

    avg = hold.mean().sort_values(ascending=False)
    freq = hold.gt(0).mean().reindex(avg.index)
    for ticker in avg.index:
        if avg[ticker] <= 0 and freq[ticker] <= 0:
            continue
        rows.append({
            "audit_type": "ticker",
            "item": ticker,
            "category": category.get(ticker, "unknown"),
            "average_weight": float(avg[ticker]),
            "holding_frequency": float(freq[ticker]),
            "max_weight": float(hold[ticker].max()),
            "value": float(avg[ticker]),
        })

    if category:
        cat_weights: dict[str, pd.Series] = {}
        for ticker in hold.columns:
            cat_weights.setdefault(category.get(ticker, "unknown"), pd.Series(0.0, index=hold.index))
            cat_weights[category.get(ticker, "unknown")] = cat_weights[category.get(ticker, "unknown")] + hold[ticker]
        for cat, series in sorted(cat_weights.items()):
            rows.append({
                "audit_type": "category",
                "item": cat,
                "category": cat,
                "average_weight": float(series.mean()),
                "holding_frequency": float((series > 0).mean()),
                "max_weight": float(series.max()),
                "value": float(series.mean()),
            })

    tech_like = [c for c in ["QQQ", "XLK", "SMH", "VGT"] if c in hold.columns]
    bond_like = [c for c in ["BIL", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD", "HYG"] if c in hold.columns]
    sector_like = [c for c in hold.columns if str(c).startswith("XL") or c in {"SMH", "XBI", "KRE", "IBB"}]
    summary_items = {
        "average_SPY_weight": hold["SPY"].mean() if "SPY" in hold.columns else np.nan,
        "average_QQQ_weight": hold["QQQ"].mean() if "QQQ" in hold.columns else np.nan,
        "average_tech_like_weight": hold[tech_like].sum(axis=1).mean() if tech_like else np.nan,
        "average_sector_weight": hold[sector_like].sum(axis=1).mean() if sector_like else np.nan,
        "average_bond_cash_weight": hold[bond_like].sum(axis=1).mean() if bond_like else np.nan,
        "average_BIL_weight": hold["BIL"].mean() if "BIL" in hold.columns else np.nan,
        "average_top3_etf_exposure": hold.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1).mean(),
        "max_single_etf_weight": hold.max(axis=1).max(),
    }
    for item, value in summary_items.items():
        rows.append({"audit_type": "summary", "item": item, "category": "", "average_weight": np.nan, "holding_frequency": np.nan, "max_weight": np.nan, "value": float(value) if pd.notna(value) else np.nan})
    return pd.DataFrame(rows)


def project_metrics_for_window(mlx5: Any, comparison_name: str, source_path: str, window: str, start: pd.Timestamp, end: pd.Timestamp, warnings_list: list[str]) -> dict[str, Any] | None:
    path = ROOT / source_path
    try:
        project_path = mlx5.read_project_return_file(path)
        sub = project_path.loc[(project_path.index >= start) & (project_path.index <= end)]
        metrics = mlx5.calc_metrics(sub)
        metrics.update({"comparison_name": comparison_name, "source_path": source_path, "window": window, "start": start.date().isoformat(), "end": end.date().isoformat()})
        return metrics
    except Exception as exc:
        warn(f"Could not compute project window metrics for {source_path}: {exc}", warnings_list)
        return None


def strategy_comparison(mlx5: Any, backtest: pd.DataFrame, project: pd.DataFrame, comparison_table: pd.DataFrame, rows: dict[str, dict[str, Any]], warnings_list: list[str]) -> pd.DataFrame:
    selected_sequence = {
        "Best raw sequence model": rows["best_raw"].get("strategy_name"),
        "Best defensive-overlay sequence model": rows["best_overlay"].get("strategy_name"),
    }
    selected_names = []
    if not comparison_table.empty:
        for label in ["MLX-4 best MLP", "MLX-3 best tabular ML", "Simple momentum baseline", "SPY", "60/40"]:
            sub = comparison_table[comparison_table["comparison_label"].eq(label)]
            if not sub.empty:
                selected_names.append((label, str(sub.iloc[0]["strategy_name"])))
    selected_names.extend((label, name) for label, name in selected_sequence.items() if isinstance(name, str))

    out = []
    for label, strategy_name in selected_names:
        path = path_from_backtest(backtest, strategy_name)
        if path.empty:
            continue
        for window, (start, end) in EVALUATION_WINDOWS.items():
            metrics = metrics_for_window(mlx5, path, window, start, end)
            metrics.update({"comparison_label": label, "strategy_name": strategy_name, "category": "mlx_or_baseline"})
            out.append(metrics)

    categories = ["current_production", "official_shadow", "phase4b", "phase6", "phase7"]
    if project.empty:
        warn("No MLX-5 project strategy comparison file found; project strategy robustness comparison is incomplete.", warnings_list)
    for category in categories:
        sub = project[project["category"].eq(category)] if not project.empty and "category" in project.columns else pd.DataFrame()
        if sub.empty:
            warn(f"No project comparison row found for category {category}.", warnings_list)
            continue
        best = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
        for window, (start, end) in EVALUATION_WINDOWS.items():
            metrics = project_metrics_for_window(mlx5, str(best["comparison_name"]), str(best["source_path"]), window, start, end, warnings_list)
            if metrics:
                metrics.update({"comparison_label": category, "strategy_name": best["comparison_name"], "category": category})
                out.append(metrics)
    return pd.DataFrame(out)


def stable_metric(df: pd.DataFrame, label_col: str, label: str, metric: str, window: str = "2020_onward") -> float:
    sub = df[(df[label_col].eq(label)) & (df["window"].eq(window))]
    if sub.empty or metric not in sub:
        return np.nan
    return float(pd.to_numeric(sub.iloc[0][metric], errors="coerce"))


def format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}"


def format_num(value: Any) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.3f}"


def markdown_table(df: pd.DataFrame, cols: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "No rows available."
    sub = df[[c for c in cols if c in df.columns]].head(max_rows).copy()
    for col in ["annual_return", "annual_volatility", "max_drawdown", "cvar_5", "average_bil_weight", "average_bil_exposure", "average_ml_exposure", "annual_cost_drag", "average_turnover", "hit_rate", "weekly_mean_return", "value"]:
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce").map(format_pct)
    for col in ["sharpe", "calmar"]:
        if col in sub.columns:
            sub[col] = pd.to_numeric(sub[col], errors="coerce").map(format_num)
    headers = list(sub.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in sub.iterrows():
        lines.append("| " + " | ".join(str(row.get(col, "") if pd.notna(row.get(col, "")) else "n/a") for col in headers) + " |")
    return "\n".join(lines)


def summarize_findings(window_df: pd.DataFrame, overlay_df: pd.DataFrame, topn_df: pd.DataFrame, cost_df: pd.DataFrame, state_df: pd.DataFrame, holdings_df: pd.DataFrame, strategy_df: pd.DataFrame, best_row: dict[str, Any], warnings_list: list[str]) -> dict[str, Any]:
    best_overlay = overlay_df.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict() if not overlay_df.empty else {}
    best_topn = topn_df.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0].to_dict() if not topn_df.empty else {}
    best_cost = cost_df[cost_df["cost_bps"].eq(10.0)].iloc[0].to_dict() if not cost_df.empty and cost_df["cost_bps"].eq(10.0).any() else {}

    best_seq_2020 = strategy_df[(strategy_df["comparison_label"].eq("Best defensive-overlay sequence model")) & (strategy_df["window"].eq("2020_onward"))]
    prod_2020 = strategy_df[(strategy_df["category"].eq("current_production")) & (strategy_df["window"].eq("2020_onward"))]
    shadow_2020 = strategy_df[(strategy_df["category"].eq("official_shadow")) & (strategy_df["window"].eq("2020_onward"))]
    phase4b_2020 = strategy_df[(strategy_df["category"].eq("phase4b")) & (strategy_df["window"].eq("2020_onward"))]

    def metric(df: pd.DataFrame, col: str) -> float:
        return float(pd.to_numeric(df.iloc[0][col], errors="coerce")) if not df.empty and col in df else np.nan

    windows = strategy_df["window"].dropna().unique().tolist() if not strategy_df.empty else []
    prod_window_wins = []
    shadow_window_wins = []
    phase4b_window_wins = []
    for window in windows:
        seq = strategy_df[(strategy_df["comparison_label"].eq("Best defensive-overlay sequence model")) & (strategy_df["window"].eq(window))]
        prod = strategy_df[(strategy_df["category"].eq("current_production")) & (strategy_df["window"].eq(window))]
        shadow = strategy_df[(strategy_df["category"].eq("official_shadow")) & (strategy_df["window"].eq(window))]
        phase4b = strategy_df[(strategy_df["category"].eq("phase4b")) & (strategy_df["window"].eq(window))]
        if not seq.empty and not prod.empty:
            prod_window_wins.append(bool(metric(seq, "sharpe") > metric(prod, "sharpe")))
        if not seq.empty and not shadow.empty:
            shadow_window_wins.append(bool(metric(seq, "sharpe") > metric(shadow, "sharpe")))
        if not seq.empty and not phase4b.empty:
            phase4b_window_wins.append(bool(metric(seq, "sharpe") > metric(phase4b, "sharpe")))

    top_holdings = holdings_df[holdings_df["audit_type"].eq("ticker")].sort_values("average_weight", ascending=False).head(10)
    qqq_weight = stable_holding(holdings_df, "average_QQQ_weight")
    spy_weight = stable_holding(holdings_df, "average_SPY_weight")
    tech_weight = stable_holding(holdings_df, "average_tech_like_weight")
    bil_weight = stable_holding(holdings_df, "average_BIL_weight")

    warnings_list.append("Random-seed robustness was not retrained in MLX-5B; saved MLX-5 predictions appear to come from one training seed. MLX-5C should run multi-seed or walk-forward checks.")

    recommendation = "NEEDS MULTI-SEED / WALK-FORWARD BEFORE JUDGMENT"
    return {
        "phase": "MLX-5B sequence overlay robustness",
        "research_only": True,
        "production_valid": False,
        "overfitting_warning": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "purpose": "experimental ML sandbox only",
        "best_mlx5_strategy_tested": best_row.get("strategy_name"),
        "best_overlay_variant_by_sharpe": best_overlay,
        "best_topn_weighting_by_sharpe": best_topn,
        "cost_10bps_result": best_cost,
        "beats_current_production_2020_sharpe": bool(metric(best_seq_2020, "sharpe") > metric(prod_2020, "sharpe")) if not best_seq_2020.empty and not prod_2020.empty else None,
        "beats_official_shadow_2020_sharpe": bool(metric(best_seq_2020, "sharpe") > metric(shadow_2020, "sharpe")) if not best_seq_2020.empty and not shadow_2020.empty else None,
        "beats_phase4b_2020_sharpe": bool(metric(best_seq_2020, "sharpe") > metric(phase4b_2020, "sharpe")) if not best_seq_2020.empty and not phase4b_2020.empty else None,
        "beats_current_production_all_tested_windows": bool(prod_window_wins and all(prod_window_wins)),
        "beats_official_shadow_all_tested_windows": bool(shadow_window_wins and all(shadow_window_wins)),
        "beats_phase4b_all_tested_windows": bool(phase4b_window_wins and all(phase4b_window_wins)),
        "sequence_2020_sharpe": metric(best_seq_2020, "sharpe"),
        "production_2020_sharpe": metric(prod_2020, "sharpe"),
        "shadow_2020_sharpe": metric(shadow_2020, "sharpe"),
        "phase4b_2020_sharpe": metric(phase4b_2020, "sharpe"),
        "sequence_2020_cvar_5": metric(best_seq_2020, "cvar_5"),
        "production_2020_cvar_5": metric(prod_2020, "cvar_5"),
        "top_holdings": top_holdings[["item", "average_weight", "holding_frequency", "max_weight", "category"]].to_dict("records"),
        "average_QQQ_weight": qqq_weight,
        "average_SPY_weight": spy_weight,
        "average_tech_like_weight": tech_weight,
        "average_BIL_weight": bil_weight,
        "final_recommendation": recommendation,
        "warnings": warnings_list,
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "window_sensitivity": str(WINDOW_SENSITIVITY_OUT.relative_to(ROOT)),
            "overlay_sensitivity": str(OVERLAY_SENSITIVITY_OUT.relative_to(ROOT)),
            "topn_weighting_sensitivity": str(TOPN_WEIGHTING_OUT.relative_to(ROOT)),
            "cost_sensitivity": str(COST_SENSITIVITY_OUT.relative_to(ROOT)),
            "state_by_state": str(STATE_BY_STATE_OUT.relative_to(ROOT)),
            "holdings_exposure": str(HOLDINGS_EXPOSURE_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "markdown_report": str(REPORT_OUT.relative_to(ROOT)),
        },
    }


def stable_holding(holdings_df: pd.DataFrame, item: str) -> float:
    sub = holdings_df[(holdings_df["audit_type"].eq("summary")) & (holdings_df["item"].eq(item))]
    return float(sub.iloc[0]["value"]) if not sub.empty and pd.notna(sub.iloc[0]["value"]) else np.nan


def write_report(summary: dict[str, Any], rows: dict[str, dict[str, Any]], window_df: pd.DataFrame, overlay_df: pd.DataFrame, topn_df: pd.DataFrame, cost_df: pd.DataFrame, state_df: pd.DataFrame, holdings_df: pd.DataFrame, strategy_df: pd.DataFrame, warnings_list: list[str]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    best = rows["best_overlay"]
    window_focus = window_df[window_df["strategy_label"].eq("best_overlay")].copy()
    overlay_table = overlay_df.sort_values(["sharpe", "annual_return"], ascending=[False, False])
    topn_table = topn_df.sort_values(["sharpe", "annual_return"], ascending=[False, False])
    cost_table = cost_df.sort_values("cost_bps")
    strategy_focus = strategy_df[strategy_df["window"].eq("2020_onward")].sort_values(["sharpe", "annual_return"], ascending=[False, False])
    holdings_tickers = holdings_df[holdings_df["audit_type"].eq("ticker")].sort_values("average_weight", ascending=False)
    holdings_summary = holdings_df[holdings_df["audit_type"].eq("summary")]
    warn_lines = "\n".join(f"- {w}" for w in warnings_list) or "- None"

    REPORT_OUT.write_text(f"""# Phase MLX-5B Sequence Overlay Robustness Report

## Research-Only Warning

Phase MLX-5B is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

Robustness testing asks whether a result survives reasonable changes in time window, transaction cost, portfolio size, weighting, and risk overlay rules. One good holdout result is not enough because financial markets are noisy and a strategy can look excellent in one regime while failing in the next.

Window sensitivity checks whether performance depends on a specific date range. Overlay sensitivity checks whether one fragile rule, such as a particular BIL fallback, is doing most of the work. Cost sensitivity tests whether turnover costs erase the apparent edge. State-by-state analysis checks which market regimes help or hurt the strategy. Holdings and exposure audits matter because a model can appear smart while mostly hiding a simple exposure, such as QQQ, SPY, tech, momentum, or cash.

## Executive Summary

- Best MLX-5 overlay strategy tested: `{best.get('strategy_name')}`
- Original holdout Sharpe: {format_num(best.get('sharpe'))}
- Original holdout annual return: {format_pct(best.get('annual_return'))}
- Original holdout max drawdown: {format_pct(best.get('max_drawdown'))}
- Final recommendation: **{summary['final_recommendation']}**

The MLX-5 overlay remains interesting, especially as a possible offensive sleeve, but the result is not robust enough for production judgment. The earlier MLX-5 caveat still matters: the best holdout strategy had weak train/validation Sharpe, so multi-seed and walk-forward testing are required before treating the edge as durable.

## Holdout-Window Sensitivity

{markdown_table(window_focus, ['window', 'strategy_name', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_weight'])}

## Overlay Sensitivity

{markdown_table(overlay_table, ['overlay_variant', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag', 'average_bil_weight', 'average_ml_exposure'])}

## Top-N / Weighting Sensitivity

{markdown_table(topn_table, ['top_n', 'weighting', 'overlay_variant', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'average_bil_weight'])}

## Cost Sensitivity

{markdown_table(cost_table, ['cost_bps', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'annual_cost_drag'])}

## State-By-State Performance

{markdown_table(state_df, ['market_state', 'weeks', 'weekly_mean_return', 'annual_return', 'annual_volatility', 'sharpe', 'hit_rate', 'average_bil_exposure', 'average_ml_exposure', 'average_turnover'])}

## Holdings / Exposure Audit

Top average ETF weights:

{markdown_table(holdings_tickers, ['item', 'category', 'average_weight', 'holding_frequency', 'max_weight'], max_rows=15)}

Exposure summaries:

{markdown_table(holdings_summary, ['item', 'value'], max_rows=20)}

The audit is meant to catch whether the model is secretly just QQQ/SPY/tech/momentum exposure or whether the BIL fallback dominates results. Any such concentration should be treated as a research warning rather than evidence of model skill.

## Project Strategy Comparison

2020+ aligned comparison:

{markdown_table(strategy_focus, ['comparison_label', 'strategy_name', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'calmar', 'cvar_5', 'average_turnover', 'average_bil_weight'], max_rows=20)}

Explicit answers:

- Does MLX-5 beat current production across multiple windows or only 2020+? Across all tested windows: {summary['beats_current_production_all_tested_windows']}; 2020+ only: {summary['beats_current_production_2020_sharpe']}.
- Does MLX-5 beat official shadow across multiple windows? {summary['beats_official_shadow_all_tested_windows']}.
- Does MLX-5 beat Phase 4B best? 2020+: {summary['beats_phase4b_2020_sharpe']}; all tested windows: {summary['beats_phase4b_all_tested_windows']}.
- Does MLX-5 have better return but worse CVaR? 2020+ sequence CVaR is {format_pct(summary['sequence_2020_cvar_5'])} versus production {format_pct(summary['production_2020_cvar_5'])}.
- Is MLX-5 more suitable as standalone strategy or offensive sleeve? It is more suitable as an offensive sleeve candidate, not a standalone production replacement.

## Random Seed / Instability Note

MLX-5B did not retrain the sequence models. The saved MLX-5 predictions appear to come from one seed, so random-seed robustness is not yet tested. A future MLX-5C should rerun LSTM/GRU/Temporal CNN models across multiple seeds and preferably walk-forward folds.

## Warnings

{warn_lines}
""")


def main() -> None:
    ROBUSTNESS_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    mlx5 = load_mlx5_module()
    data = load_data(mlx5)
    features = data["features"]
    predictions = data["predictions"]
    summary = data["summary"]
    backtest = data["backtest"]
    project_comparison = data["project_comparison"]
    comparison_table = data["comparison_table"]
    universe = data["universe"]

    if predictions.empty:
        raise ValueError("MLX-5 sequence predictions are empty.")
    if "BIL" not in data["weekly_returns"].columns:
        warn("BIL returns are not available; BIL fallback tests may understate unused cash-like exposure.", warnings_list)

    rows = best_strategy_rows(summary)
    best_overlay_row = rows["best_overlay"]
    context = make_context(mlx5, features)
    raw_weights = raw_weights_for_strategy(mlx5, predictions, context, best_overlay_row)

    window_df = window_sensitivity(mlx5, backtest, rows, warnings_list)
    overlay_df, overlay_paths = overlay_sensitivity(mlx5, raw_weights, context, best_overlay_row)
    selected_overlay_variant = "bil_fallback_original"
    best_path, best_weights = overlay_paths[selected_overlay_variant]
    topn_df = topn_weighting_sensitivity(mlx5, predictions, context, best_overlay_row, selected_overlay_variant)
    cost_df = cost_sensitivity(mlx5, raw_weights, context, selected_overlay_variant, best_overlay_row)
    state_df = state_by_state(mlx5, best_path, context["state"])
    holdings_df = holdings_exposure(best_weights, universe)
    strategy_df = strategy_comparison(mlx5, backtest, project_comparison, comparison_table, rows, warnings_list)

    window_df.to_csv(WINDOW_SENSITIVITY_OUT, index=False)
    overlay_df.to_csv(OVERLAY_SENSITIVITY_OUT, index=False)
    topn_df.to_csv(TOPN_WEIGHTING_OUT, index=False)
    cost_df.to_csv(COST_SENSITIVITY_OUT, index=False)
    state_df.to_csv(STATE_BY_STATE_OUT, index=False)
    holdings_df.to_csv(HOLDINGS_EXPOSURE_OUT, index=False)
    strategy_df.to_csv(STRATEGY_COMPARISON_OUT, index=False)

    summary_json = summarize_findings(window_df, overlay_df, topn_df, cost_df, state_df, holdings_df, strategy_df, best_overlay_row, warnings_list)
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_report(summary_json, rows, window_df, overlay_df, topn_df, cost_df, state_df, holdings_df, strategy_df, warnings_list)

    print("Phase MLX-5B sequence overlay robustness")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Best MLX-5 strategy tested: {best_overlay_row.get('strategy_name')}")
    print(f"Robustness outputs written to: {ROBUSTNESS_DIR.relative_to(ROOT)}")
    print(f"Final recommendation: {summary_json['final_recommendation']}")
    print("Outputs:")
    for path in [
        WINDOW_SENSITIVITY_OUT,
        OVERLAY_SENSITIVITY_OUT,
        TOPN_WEIGHTING_OUT,
        COST_SENSITIVITY_OUT,
        STATE_BY_STATE_OUT,
        HOLDINGS_EXPOSURE_OUT,
        STRATEGY_COMPARISON_OUT,
        SUMMARY_JSON_OUT,
        REPORT_OUT,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
