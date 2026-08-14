#!/usr/bin/env python3
"""
Phase MLX-9: research-only model ensemble / combined ML shadow candidate.

Experimental research-only code. It writes only under data/research/ml_lab,
docs/research/ml_lab, and scripts/ml_lab. It does not modify production pins,
dashboard code, production strategy logic, or candidate status.
"""

from __future__ import annotations

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
TABULAR_DIR = ML_DIR / "tabular_ml"
NN_DIR = ML_DIR / "neural_networks"
SEQUENCE_DIR = ML_DIR / "sequence_models"
SEQUENCE_5C_DIR = SEQUENCE_DIR / "multiseed_walkforward"
TRANSFORMER_DIR = ML_DIR / "transformers"
META_DIR = ML_DIR / "meta_labeling"
RL_DIR = ML_DIR / "reinforcement_learning"
OUTPUT_DIR = ML_DIR / "ensembles"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

FEATURES_IN = FEATURE_DIR / "ml_feature_panel.parquet"
TARGETS_IN = FEATURE_DIR / "ml_targets.parquet"
WEEKLY_RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"
UNIVERSE_IN = EXPANDED_DIR / "expanded_etf_universe.csv"

TABULAR_PRED_IN = TABULAR_DIR / "ml_tabular_predictions.parquet"
TABULAR_SUMMARY_IN = TABULAR_DIR / "ml_tabular_summary.csv"
NN_PRED_IN = NN_DIR / "nn_predictions.parquet"
NN_SUMMARY_IN = NN_DIR / "nn_summary.csv"
SEQUENCE_PRED_IN = SEQUENCE_DIR / "sequence_predictions.parquet"
SEQUENCE_SUMMARY_IN = SEQUENCE_DIR / "sequence_summary.csv"
SEQUENCE_BACKTEST_IN = SEQUENCE_DIR / "sequence_backtest_returns.csv"
SEQUENCE_PROJECT_COMPARISON_IN = SEQUENCE_DIR / "sequence_project_strategy_comparison.csv"
SEQUENCE_5C_PRED_IN = SEQUENCE_5C_DIR / "sequence_multiseed_predictions.parquet"
SEQUENCE_5C_SUMMARY_IN = SEQUENCE_5C_DIR / "sequence_multiseed_summary.json"
TRANSFORMER_PRED_IN = TRANSFORMER_DIR / "transformer_predictions.parquet"
TRANSFORMER_SUMMARY_IN = TRANSFORMER_DIR / "transformer_summary.csv"
TRANSFORMER_BACKTEST_IN = TRANSFORMER_DIR / "transformer_backtest_returns.csv"
META_PRED_IN = META_DIR / "meta_label_predictions.parquet"
META_MODEL_METRICS_IN = META_DIR / "meta_label_model_metrics.csv"
META_STRATEGY_SUMMARY_IN = META_DIR / "meta_label_strategy_summary.csv"
META_STRATEGY_RETURNS_IN = META_DIR / "meta_label_strategy_returns.csv"
RL_SUMMARY_IN = RL_DIR / "rl_summary.csv"
RL_RETURNS_IN = RL_DIR / "rl_backtest_returns.csv"
RL_SUMMARY_JSON_IN = RL_DIR / "rl_summary.json"

SIGNAL_PANEL_OUT = OUTPUT_DIR / "ensemble_signal_panel.parquet"
PREDICTIONS_OUT = OUTPUT_DIR / "ensemble_predictions.parquet"
RETURNS_OUT = OUTPUT_DIR / "ensemble_strategy_returns.csv"
SUMMARY_OUT = OUTPUT_DIR / "ensemble_summary.csv"
VALIDATION_SELECTION_OUT = OUTPUT_DIR / "ensemble_validation_selection.csv"
WALKFORWARD_OUT = OUTPUT_DIR / "ensemble_walkforward_summary.csv"
STATE_BY_STATE_OUT = OUTPUT_DIR / "ensemble_state_by_state.csv"
EXPOSURE_AUDIT_OUT = OUTPUT_DIR / "ensemble_exposure_audit.csv"
STRATEGY_COMPARISON_OUT = OUTPUT_DIR / "ensemble_strategy_comparison.csv"
COMPONENT_AVAILABILITY_OUT = OUTPUT_DIR / "ensemble_component_availability.json"
CANDIDATE_DEFINITIONS_OUT = OUTPUT_DIR / "ensemble_candidate_definitions.json"
SUMMARY_JSON_OUT = OUTPUT_DIR / "ensemble_summary.json"
NOTES_OUT = DOCS_DIR / "phase_mlx_model_ensemble_notes.md"

DEFAULT_COST_BPS = 10.0
SAFE_ASSETS = {"BIL", "SHY", "IEF", "TLT", "TIP", "AGG", "BND", "MBB", "LQD"}
TARGET_LIKE_PREFIXES = ("forward_", "future_", "next_", "beats_", "top_quintile", "positive_forward")
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


@dataclass(frozen=True)
class CandidateSpec:
    candidate_name: str
    family: str
    score_column: str
    top_n: int
    wrapper: str
    weighting: str = "inverse_vol"
    eligible_column: str | None = None


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


def split_for_dates(dates: pd.Series | pd.DatetimeIndex) -> pd.Series:
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
            "average_ml_sleeve_exposure": np.nan,
            "average_core_exposure": np.nan,
            "average_number_of_etfs_held": np.nan,
            "hit_rate": np.nan,
            "active_weeks": 0,
        }
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
        "average_bil_exposure": float(path.get("bil_weight", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_ml_sleeve_exposure": float(path.get("ml_sleeve_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_core_exposure": float(path.get("core_exposure", pd.Series(dtype=float)).reindex(r.index).mean()),
        "average_number_of_etfs_held": float(path.get("holdings_count", pd.Series(dtype=float)).reindex(r.index).mean()),
        "hit_rate": float((r > 0).mean()),
        "active_weeks": int(len(r)),
    }


def markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows available._"
    tmp = df.loc[:, [c for c in columns if c in df.columns]].head(max_rows).copy()
    for col in tmp.columns:
        if col in {"annual_return", "annual_volatility", "max_drawdown", "cvar_5", "average_turnover", "annual_cost_drag", "average_bil_exposure", "average_ml_sleeve_exposure", "average_core_exposure"}:
            tmp[col] = tmp[col].map(pct)
        elif col in {"sharpe", "calmar", "hit_rate"}:
            tmp[col] = tmp[col].map(num)
    headers = list(tmp.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in tmp.iterrows():
        values = []
        for col in headers:
            value = row[col]
            if pd.isna(value):
                values.append("n/a")
            else:
                text = str(value).replace("|", "\\|").replace("\n", " ")
                values.append(text)
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def load_weekly_returns(warnings_list: list[str]) -> pd.DataFrame:
    if not WEEKLY_RETURNS_IN.exists():
        raise FileNotFoundError(f"Required weekly returns missing: {WEEKLY_RETURNS_IN}")
    df = pd.read_csv(WEEKLY_RETURNS_IN)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if "BIL" not in df.columns:
        warn("BIL returns are missing; fallback overlays will be less meaningful.", warnings_list)
    return df


def load_features() -> pd.DataFrame:
    if not FEATURES_IN.exists():
        raise FileNotFoundError(f"Required feature panel missing: {FEATURES_IN}")
    features = pd.read_parquet(FEATURES_IN)
    features["Date"] = pd.to_datetime(features["Date"])
    return features.sort_values(["Date", "ticker"]).reset_index(drop=True)


def validate_inputs(features: pd.DataFrame, warnings_list: list[str]) -> None:
    if TARGETS_IN.exists():
        targets = pd.read_parquet(TARGETS_IN)
        if len(targets) != len(features):
            warn(f"Feature/target row count mismatch: features={len(features)}, targets={len(targets)}", warnings_list)
        overlap = sorted(set(features.columns) & TARGET_COLUMNS)
        if overlap:
            raise ValueError(f"Target columns leaked into feature panel: {overlap}")
    else:
        warn(f"Optional target file missing for validation: {TARGETS_IN}", warnings_list)
    target_like = [c for c in features.columns if c not in {"Date", "ticker"} and c.lower().startswith(TARGET_LIKE_PREFIXES)]
    if target_like:
        raise ValueError(f"Target-like feature columns found: {target_like[:10]}")


def infer_market_state_by_date(features: pd.DataFrame) -> pd.Series:
    state_cols = [c for c in features.columns if c.startswith("market_state_")]
    dates = pd.DatetimeIndex(sorted(features["Date"].unique()))
    if not state_cols:
        return pd.Series("unknown", index=dates)
    state = features[["Date"] + state_cols].drop_duplicates("Date").set_index("Date").reindex(dates)
    labels = state[state_cols].idxmax(axis=1).str.replace("market_state_", "", regex=False)
    labels[state[state_cols].sum(axis=1).fillna(0.0).eq(0.0)] = "unknown"
    return labels.fillna("unknown")


def feature_matrix(features: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in features.columns:
        return pd.DataFrame()
    return features.pivot(index="Date", columns="ticker", values=column).sort_index()


def load_universe_meta() -> pd.DataFrame:
    if not UNIVERSE_IN.exists():
        return pd.DataFrame()
    return pd.read_csv(UNIVERSE_IN)


def rank_scores(frame: pd.DataFrame, component: str) -> pd.DataFrame:
    tmp = frame[["Date", "ticker", "score"]].copy()
    tmp["Date"] = pd.to_datetime(tmp["Date"])
    tmp["score"] = pd.to_numeric(tmp["score"], errors="coerce")
    tmp = tmp.dropna(subset=["Date", "ticker", "score"])
    if tmp.empty:
        return pd.DataFrame(columns=["Date", "ticker", f"{component}_score", f"{component}_rank"])
    tmp = tmp.groupby(["Date", "ticker"], as_index=False)["score"].mean()
    tmp[f"{component}_score"] = tmp["score"]
    tmp[f"{component}_rank"] = tmp.groupby("Date")["score"].rank(method="average", pct=True)
    return tmp.drop(columns=["score"])


def preferred_or_best_model(pred: pd.DataFrame, summary_path: Path, preferred: list[str], component_name: str, warnings_list: list[str]) -> str | None:
    models = set(pred.get("model_name", pd.Series(dtype=str)).dropna().astype(str).unique())
    for name in preferred:
        if name in models:
            return name
    if summary_path.exists():
        try:
            summary = pd.read_csv(summary_path)
            sub = summary[summary["split"].eq("validation")].copy() if "split" in summary.columns else pd.DataFrame()
            if "strategy_type" in sub.columns:
                sub = sub[~sub["strategy_type"].astype(str).str.contains("baseline", case=False, na=False)]
            if component_name == "tabular" and "sharpe" in sub.columns:
                suspicious = sub[sub["sharpe"].gt(3.0)]
                if not suspicious.empty:
                    warn("Tabular validation contains extreme Sharpe outliers; using a safer non-outlier component where possible.", warnings_list)
                sub = sub[sub["sharpe"].le(3.0) | sub["sharpe"].isna()]
            sub = sub[sub["model_name"].astype(str).isin(models)] if "model_name" in sub.columns else pd.DataFrame()
            if not sub.empty:
                return str(sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["model_name"])
        except Exception as exc:
            warn(f"Could not select validation model for {component_name}: {exc}", warnings_list)
    return sorted(models)[0] if models else None


def load_component_scores(warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    components: list[pd.DataFrame] = []
    availability: dict[str, Any] = {}

    def add_component(name: str, path: Path, summary_path: Path | None, preferred_models: list[str], aggregate_all: bool = False) -> None:
        if not path.exists():
            availability[name] = {"available": False, "path": str(path.relative_to(ROOT)), "reason": "missing"}
            warn(f"Component missing: {name} at {path}", warnings_list)
            return
        try:
            pred = pd.read_parquet(path)
            pred["Date"] = pd.to_datetime(pred["Date"])
            if "score" not in pred.columns or "ticker" not in pred.columns:
                raise ValueError("prediction file lacks score/ticker columns")
            selected_model = None
            if not aggregate_all and "model_name" in pred.columns:
                selected_model = preferred_or_best_model(pred, summary_path or Path(""), preferred_models, name, warnings_list)
                if selected_model:
                    pred = pred[pred["model_name"].astype(str).eq(selected_model)].copy()
            if name == "sequence_5c":
                pred = pred[pred.get("target", "top_quintile_forward_4w").astype(str).eq("top_quintile_forward_4w")].copy()
            ranked = rank_scores(pred, name)
            if ranked.empty:
                availability[name] = {"available": False, "path": str(path.relative_to(ROOT)), "reason": "no usable rows"}
                warn(f"Component {name} had no usable score rows.", warnings_list)
                return
            components.append(ranked)
            availability[name] = {
                "available": True,
                "path": str(path.relative_to(ROOT)),
                "rows": int(len(ranked)),
                "selected_model": selected_model,
                "aggregate_all_models": aggregate_all,
            }
        except Exception as exc:
            availability[name] = {"available": False, "path": str(path.relative_to(ROOT)), "reason": f"{type(exc).__name__}: {exc}"}
            warn(f"Could not load component {name}: {exc}", warnings_list)

    add_component(
        "sequence_5c",
        SEQUENCE_5C_PRED_IN,
        None,
        [],
        aggregate_all=True,
    )
    add_component(
        "sequence_base",
        SEQUENCE_PRED_IN,
        SEQUENCE_SUMMARY_IN,
        ["lstm_classifier_top_quintile_forward_4w_seq26", "gru_classifier_beats_SPY_4w_seq26"],
    )
    add_component(
        "transformer",
        TRANSFORMER_PRED_IN,
        TRANSFORMER_SUMMARY_IN,
        ["transformer_encoder_top_quintile_forward_4w_seq26_seed0", "transformer_encoder_top_quintile_forward_4w_seq13_seed0"],
    )
    add_component(
        "mlp",
        NN_PRED_IN,
        NN_SUMMARY_IN,
        ["deep_dropout_mlp_classifier_top_quintile_forward_4w", "mlp_classifier_top_quintile_forward_4w", "mlp_classifier_beats_SPY_4w"],
    )
    add_component(
        "tabular",
        TABULAR_PRED_IN,
        TABULAR_SUMMARY_IN,
        ["random_forest_classifier__top_quintile_forward_4w", "random_forest_classifier__beats_SPY_4w", "gradient_boosting_classifier__top_quintile_forward_4w"],
    )

    if not components:
        raise RuntimeError("No ensemble signal components could be loaded.")
    panel = components[0]
    for comp in components[1:]:
        panel = panel.merge(comp, on=["Date", "ticker"], how="outer")
    panel = panel.sort_values(["Date", "ticker"]).reset_index(drop=True)
    return panel, availability


def weighted_score(panel: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    numerator = pd.Series(0.0, index=panel.index)
    denom = pd.Series(0.0, index=panel.index)
    for col, weight in weights.items():
        if col not in panel.columns:
            continue
        values = pd.to_numeric(panel[col], errors="coerce")
        mask = values.notna()
        numerator.loc[mask] += values.loc[mask] * weight
        denom.loc[mask] += weight
    return numerator.div(denom.replace(0.0, np.nan))


def build_signal_panel(base_panel: pd.DataFrame, availability: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    panel = base_panel.copy()
    sequence_main = "sequence_5c_rank" if "sequence_5c_rank" in panel.columns else "sequence_base_rank"
    candidate_defs: dict[str, Any] = {}

    def add_score(name: str, family: str, weights: dict[str, float], description: str) -> None:
        panel[name] = weighted_score(panel, weights)
        candidate_defs[name] = {"family": family, "weights": weights, "description": description}

    add_score(
        "score_rank_average_all",
        "rank_average",
        {
            sequence_main: 1.0,
            "transformer_rank": 1.0,
            "mlp_rank": 1.0,
            "tabular_rank": 1.0,
        },
        "Equal-weight rank average across available sequence, Transformer, MLP, and tabular scores.",
    )
    add_score(
        "score_rank_average_no_tabular",
        "rank_average",
        {sequence_main: 1.0, "transformer_rank": 1.0, "mlp_rank": 1.0},
        "Rank average of the stronger ML components, excluding tabular ML by default.",
    )
    add_score(
        "score_sequence_dominant_70_20_10",
        "sequence_dominant",
        {sequence_main: 0.70, "transformer_rank": 0.20, "mlp_rank": 0.10},
        "Sequence-dominant blend: 70% sequence, 20% Transformer, 10% MLP.",
    )
    add_score(
        "score_sequence_transformer_80_20",
        "sequence_dominant",
        {sequence_main: 0.80, "transformer_rank": 0.20},
        "Sequence plus Transformer confirmation: 80% sequence, 20% Transformer.",
    )
    add_score(
        "score_sequence_only",
        "sequence_baseline",
        {sequence_main: 1.0},
        "Pure MLX-5C sequence signal baseline.",
    )
    major_cols = [c for c in [sequence_main, "transformer_rank", "mlp_rank"] if c in panel.columns]
    if major_cols:
        panel["agreement_count_2of3"] = panel[major_cols].ge(0.80).sum(axis=1)
        panel["score_agreement_2of3"] = panel[major_cols].mean(axis=1, skipna=True)
        panel["eligible_agreement_2of3"] = panel["agreement_count_2of3"].ge(min(2, len(major_cols))).astype(float)
        candidate_defs["score_agreement_2of3"] = {
            "family": "agreement_filter",
            "weights": {c: 1.0 for c in major_cols},
            "description": "Average score used only where at least two major models rank the ETF in the top quintile.",
        }
    else:
        panel["eligible_agreement_2of3"] = 0.0

    candidate_defs["component_availability_snapshot"] = availability
    return panel, candidate_defs


def weights_from_scores(
    score_table: pd.DataFrame,
    dates: pd.DatetimeIndex,
    tickers: list[str],
    top_n: int,
    next_returns: pd.DataFrame,
    vol_panel: pd.DataFrame,
    score_column: str,
    eligible_column: str | None = None,
) -> pd.DataFrame:
    weights = pd.DataFrame(0.0, index=dates, columns=tickers)
    has_bil = "BIL" in tickers
    for date, group in score_table.groupby("Date", sort=False):
        if date not in weights.index:
            continue
        eligible = group[["ticker", score_column] + ([eligible_column] if eligible_column else [])].copy()
        eligible = eligible.rename(columns={score_column: "score"}).dropna(subset=["score"])
        if eligible_column:
            eligible = eligible[pd.to_numeric(eligible[eligible_column], errors="coerce").fillna(0.0) > 0.0]
        if eligible.empty:
            if has_bil:
                weights.loc[date, "BIL"] = 1.0
            continue
        available = next_returns.loc[date] if date in next_returns.index else pd.Series(dtype=float)
        available_lookup = available.notna().to_dict()
        available_mask = eligible["ticker"].map(lambda ticker: bool(available_lookup.get(ticker, False)))
        eligible = eligible[available_mask]
        chosen = eligible.sort_values("score", ascending=False).head(top_n)["ticker"].tolist()
        if not chosen:
            if has_bil:
                weights.loc[date, "BIL"] = 1.0
            continue
        vol = vol_panel.reindex(index=[date], columns=chosen).iloc[0].replace([np.inf, -np.inf], np.nan) if not vol_panel.empty and date in vol_panel.index else pd.Series(index=chosen, dtype=float)
        inv = 1.0 / vol.where(vol > 0.0)
        if inv.notna().sum() and inv.sum(skipna=True) > 0:
            w = inv.fillna(0.0) / inv.fillna(0.0).sum()
        else:
            w = pd.Series(1.0 / len(chosen), index=chosen)
        weights.loc[date, w.index] = w.values
    return weights


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
    if wrapper == "bil_fallback":
        mapping = {"stressed_panic": 0.25, "neutral_mixed": 0.75}
        exposure = state.reindex(dates).map(mapping).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "regime_gate":
        mapping = {"calm_trend": 1.0, "recovery_confirmed": 1.0, "neutral_mixed": 0.60, "recovery_fragile": 0.60, "stressed_panic": 0.25}
        exposure = state.reindex(dates).map(mapping).fillna(0.70)
        return add_bil_fallback(raw_weights, exposure), exposure
    raw_gross = raw_weights.mul(next_returns.reindex(index=dates, columns=raw_weights.columns).fillna(0.0)).sum(axis=1)
    if wrapper == "vol_target_10pct":
        ann_vol = raw_gross.shift(1).rolling(13, min_periods=6).std() * math.sqrt(52.0)
        exposure = (0.10 / ann_vol.replace(0.0, np.nan)).clip(0.0, 1.0).fillna(1.0)
        return add_bil_fallback(raw_weights, exposure), exposure
    if wrapper == "drawdown_kill_switch":
        wealth = (1.0 + raw_gross.shift(1).fillna(0.0)).cumprod()
        dd = wealth / wealth.cummax() - 1.0
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


def compute_path(weights: pd.DataFrame, next_returns: pd.DataFrame, exposure: pd.Series | None = None, core_exposure: pd.Series | float = 0.0) -> pd.DataFrame:
    aligned = next_returns.reindex(index=weights.index, columns=weights.columns)
    gross = weights.mul(aligned.fillna(0.0)).sum(axis=1)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = 0.0
    cost = turnover.fillna(0.0) * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    bil_weight = weights["BIL"] if "BIL" in weights.columns else pd.Series(0.0, index=weights.index)
    safe_cols = [c for c in weights.columns if c in SAFE_ASSETS]
    offensive_cols = [c for c in weights.columns if c not in SAFE_ASSETS and not c.startswith("CORE_")]
    out = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": turnover,
            "cost": cost,
            "bil_weight": bil_weight,
            "safe_weight": weights.reindex(columns=safe_cols).sum(axis=1) if safe_cols else 0.0,
            "offensive_weight": weights.reindex(columns=offensive_cols).sum(axis=1) if offensive_cols else 0.0,
            "ml_sleeve_exposure": exposure.reindex(weights.index).fillna(1.0) if exposure is not None else 1.0,
            "core_exposure": core_exposure if isinstance(core_exposure, float) else core_exposure.reindex(weights.index).fillna(0.0),
            "holdings_count": weights.gt(0.001).sum(axis=1),
        },
        index=weights.index,
    )
    return out


def append_strategy(
    returns_frames: list[pd.DataFrame],
    weights_frames: list[pd.DataFrame],
    summary_rows: list[dict[str, Any]],
    path: pd.DataFrame,
    weights: pd.DataFrame,
    strategy_name: str,
    strategy_family: str,
    score_name: str = "",
    top_n: int | float = np.nan,
    wrapper: str = "",
    core_name: str = "",
    sleeve_size: float | None = None,
    selection_group: str = "ensemble",
) -> None:
    dated = path.copy()
    dated["Date"] = dated.index
    dated["split"] = split_for_dates(dated["Date"]).values
    dated["strategy_name"] = strategy_name
    dated["strategy_family"] = strategy_family
    dated["score_name"] = score_name
    dated["top_n"] = top_n
    dated["weighting"] = "inverse_vol"
    dated["wrapper"] = wrapper
    dated["core_name"] = core_name
    dated["sleeve_size"] = sleeve_size
    dated["selection_group"] = selection_group
    returns_frames.append(dated.reset_index(drop=True))

    for split in ("train", "validation", "holdout"):
        metrics = calc_metrics(dated[dated["split"].eq(split)])
        metrics.update(
            {
                "strategy_name": strategy_name,
                "strategy_family": strategy_family,
                "score_name": score_name,
                "top_n": top_n,
                "weighting": "inverse_vol",
                "wrapper": wrapper,
                "core_name": core_name,
                "sleeve_size": sleeve_size,
                "selection_group": selection_group,
                "split": split,
                "cost_bps": DEFAULT_COST_BPS,
            }
        )
        summary_rows.append(metrics)

    w = weights.copy()
    w["Date"] = w.index
    long = w.reset_index(drop=True).melt(id_vars="Date", var_name="ticker", value_name="weight")
    long = long[long["weight"].abs() > 1e-9].copy()
    long["strategy_name"] = strategy_name
    long["strategy_family"] = strategy_family
    long["split"] = split_for_dates(long["Date"]).values
    weights_frames.append(long)


def build_candidate_specs(signal_panel: pd.DataFrame) -> list[CandidateSpec]:
    base_scores = [
        ("score_rank_average_all", "rank_average"),
        ("score_rank_average_no_tabular", "rank_average"),
        ("score_sequence_dominant_70_20_10", "sequence_dominant"),
        ("score_sequence_transformer_80_20", "sequence_dominant"),
        ("score_sequence_only", "sequence_baseline"),
    ]
    specs: list[CandidateSpec] = []
    for score, family in base_scores:
        if score not in signal_panel.columns:
            continue
        for top_n in (10, 15):
            for wrapper in ("raw_ml", "bil_fallback"):
                specs.append(CandidateSpec(f"{score.replace('score_', '')}__top{top_n}__inverse_vol__{wrapper}", family, score, top_n, wrapper))
    for score in ("score_rank_average_no_tabular", "score_sequence_dominant_70_20_10"):
        if score not in signal_panel.columns:
            continue
        for top_n in (10, 15):
            for wrapper in ("regime_gate", "vol_target_10pct", "drawdown_kill_switch"):
                specs.append(CandidateSpec(f"defensive_first__{score.replace('score_', '')}__top{top_n}__inverse_vol__{wrapper}", "defensive_first", score, top_n, wrapper))
    if "score_agreement_2of3" in signal_panel.columns:
        for top_n in (10, 15):
            for wrapper in ("raw_ml", "bil_fallback"):
                specs.append(CandidateSpec(f"agreement_2of3__top{top_n}__inverse_vol__{wrapper}", "agreement_filter", "score_agreement_2of3", top_n, wrapper, eligible_column="eligible_agreement_2of3"))
    return specs


def read_project_return_file(path: Path) -> pd.DataFrame:
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
        raise ValueError(f"No net_return column in {path}")
    df["net_return"] = pd.to_numeric(df["net_return"], errors="coerce")
    df["gross_return"] = pd.to_numeric(df["gross_return"], errors="coerce") if "gross_return" in df.columns else df["net_return"]
    df["turnover"] = pd.to_numeric(df["turnover"], errors="coerce") if "turnover" in df.columns else np.nan
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce") if "cost" in df.columns else 0.0
    return df[["gross_return", "net_return", "turnover", "cost"]]


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
        for category in ("phase4b", "phase6", "phase7", "latest_candidate"):
            sub = comp[comp["category"].eq(category)] if "category" in comp.columns else pd.DataFrame()
            if sub.empty:
                warn(f"No project strategy comparison found for {category}.", warnings_list)
                continue
            row = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
            path = ROOT / str(row["source_path"])
            if path.exists():
                selected[category] = path
            else:
                warn(f"Selected project file missing for {category}: {path}", warnings_list)
    else:
        warn(f"Optional project strategy comparison missing: {SEQUENCE_PROJECT_COMPARISON_IN}", warnings_list)
    return selected


def load_project_returns(warnings_list: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    for name, path in select_project_strategy_files(warnings_list).items():
        try:
            out[name] = read_project_return_file(path)
        except Exception as exc:
            warn(f"Could not read project strategy {name}: {exc}", warnings_list)
    return out


def load_best_external_strategy_returns(
    summary_path: Path,
    returns_path: Path,
    summary_filter: Any,
    output_name: str,
    warnings_list: list[str],
) -> pd.DataFrame:
    if not summary_path.exists() or not returns_path.exists():
        warn(f"Optional external strategy missing for {output_name}: {summary_path} / {returns_path}", warnings_list)
        return pd.DataFrame()
    try:
        summary = pd.read_csv(summary_path)
        sub = summary_filter(summary)
        if sub.empty:
            warn(f"No matching strategy rows found for {output_name}.", warnings_list)
            return pd.DataFrame()
        best = sub.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]
        strategy_name = best["strategy_name"]
        returns = pd.read_csv(returns_path, parse_dates=["Date"])
        frame = returns[returns["strategy_name"].eq(strategy_name)].set_index("Date").sort_index()
        if frame.empty:
            warn(f"Returns missing for selected {output_name}: {strategy_name}", warnings_list)
            return pd.DataFrame()
        frame = frame.rename(columns={"bil_weight": "average_bil_exposure"})
        return frame
    except Exception as exc:
        warn(f"Could not load {output_name}: {exc}", warnings_list)
        return pd.DataFrame()


def benchmark_paths(weekly_returns: pd.DataFrame, project_returns: dict[str, pd.DataFrame], warnings_list: list[str]) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {name: frame for name, frame in project_returns.items()}
    if "SPY" in weekly_returns.columns:
        out["SPY"] = pd.DataFrame({"gross_return": weekly_returns["SPY"], "net_return": weekly_returns["SPY"], "turnover": np.nan, "cost": 0.0})
    bond = "IEF" if "IEF" in weekly_returns.columns else "AGG" if "AGG" in weekly_returns.columns else None
    if "SPY" in weekly_returns.columns and bond:
        ret = 0.60 * weekly_returns["SPY"] + 0.40 * weekly_returns[bond]
        out["60_40"] = pd.DataFrame({"gross_return": ret, "net_return": ret, "turnover": np.nan, "cost": 0.0})

    if SEQUENCE_SUMMARY_IN.exists() and SEQUENCE_BACKTEST_IN.exists():
        seq_summary = pd.read_csv(SEQUENCE_SUMMARY_IN)
        seq_returns = pd.read_csv(SEQUENCE_BACKTEST_IN, parse_dates=["Date"])
        momentum = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("baseline_momentum"))]
        if not momentum.empty:
            name = momentum.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            out["simple_momentum"] = seq_returns[seq_returns["strategy_name"].eq(name)].set_index("Date").sort_index()
        seq = seq_summary[(seq_summary["split"].eq("holdout")) & (seq_summary["strategy_type"].eq("model")) & (~seq_summary["wrapper"].eq("raw_ml"))]
        if not seq.empty:
            name = seq.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            out["mlx5_sequence"] = seq_returns[seq_returns["strategy_name"].eq(name)].set_index("Date").sort_index()
    if TRANSFORMER_SUMMARY_IN.exists() and TRANSFORMER_BACKTEST_IN.exists():
        tr_summary = pd.read_csv(TRANSFORMER_SUMMARY_IN)
        tr_returns = pd.read_csv(TRANSFORMER_BACKTEST_IN, parse_dates=["Date"])
        tr = tr_summary[(tr_summary["split"].eq("holdout")) & (~tr_summary["wrapper"].eq("raw_ml"))]
        if not tr.empty:
            name = tr.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            out["mlx6_transformer"] = tr_returns[tr_returns["strategy_name"].eq(name)].set_index("Date").sort_index()
    if META_STRATEGY_SUMMARY_IN.exists() and META_STRATEGY_RETURNS_IN.exists():
        meta_summary = pd.read_csv(META_STRATEGY_SUMMARY_IN)
        meta_returns = pd.read_csv(META_STRATEGY_RETURNS_IN, parse_dates=["Date"])
        meta = meta_summary[(meta_summary["split"].eq("holdout")) & (~meta_summary["strategy_family"].isin(["benchmark", "benchmark_summary_only"]))]
        if not meta.empty:
            name = meta.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            out["mlx7_meta_label"] = meta_returns[meta_returns["strategy_name"].eq(name)].set_index("Date").sort_index()
    if RL_SUMMARY_IN.exists() and RL_RETURNS_IN.exists():
        rl_summary = pd.read_csv(RL_SUMMARY_IN)
        rl_returns = pd.read_csv(RL_RETURNS_IN, parse_dates=["Date"])
        rl = rl_summary[rl_summary["split"].eq("holdout")]
        if not rl.empty:
            name = rl.sort_values(["sharpe", "annual_return"], ascending=[False, False]).iloc[0]["strategy_name"]
            out["mlx8_rl"] = rl_returns[rl_returns["strategy_name"].eq(name)].set_index("Date").sort_index()
    return out


def make_synthetic_weights(index: pd.DatetimeIndex, columns: list[str], weights: dict[str, pd.Series | float]) -> pd.DataFrame:
    out = pd.DataFrame(0.0, index=index, columns=columns)
    for col, value in weights.items():
        if col not in out.columns:
            out[col] = 0.0
        out[col] = value if isinstance(value, float) else value.reindex(index).fillna(0.0)
    return out


def blend_core_with_sleeve(
    core_name: str,
    core_frame: pd.DataFrame,
    sleeve_name: str,
    sleeve_path: pd.DataFrame,
    sleeve_weights: pd.DataFrame,
    sleeve_size: float,
    activation: pd.Series | None = None,
    strategy_name: str | None = None,
    strategy_family: str = "core_ml_sleeve",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(set(core_frame.index) & set(sleeve_path.index)))
    core = core_frame.reindex(dates)
    sleeve = sleeve_path.reindex(dates)
    active = activation.reindex(dates).fillna(0.0).clip(0.0, 1.0) if activation is not None else pd.Series(1.0, index=dates)
    ml_alloc = sleeve_size * active
    core_alloc = 1.0 - ml_alloc
    gross = core_alloc * core["gross_return"].fillna(core["net_return"]) + ml_alloc * sleeve["gross_return"].fillna(sleeve["net_return"])
    blended_turnover = ml_alloc * sleeve["turnover"].fillna(0.0) + ml_alloc.diff().abs().fillna(0.0)
    cost = ml_alloc * sleeve["cost"].fillna(0.0) + blended_turnover * (DEFAULT_COST_BPS / 10000.0)
    net = gross - cost
    path = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": net,
            "turnover": blended_turnover,
            "cost": cost,
            "bil_weight": ml_alloc * sleeve["bil_weight"].fillna(0.0),
            "safe_weight": ml_alloc * sleeve.get("safe_weight", pd.Series(0.0, index=dates)).reindex(dates).fillna(0.0),
            "offensive_weight": ml_alloc * sleeve.get("offensive_weight", pd.Series(0.0, index=dates)).reindex(dates).fillna(0.0),
            "ml_sleeve_exposure": ml_alloc,
            "core_exposure": core_alloc,
            "holdings_count": sleeve.get("holdings_count", pd.Series(0.0, index=dates)).reindex(dates).fillna(0.0),
        },
        index=dates,
    )
    w = sleeve_weights.reindex(dates).fillna(0.0).mul(ml_alloc, axis=0)
    w[f"CORE_{core_name.upper()}"] = core_alloc
    return path, w


def switch_core_returns(
    production: pd.DataFrame,
    phase4b: pd.DataFrame,
    use_phase4b: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.DatetimeIndex(sorted(set(production.index) & set(phase4b.index) & set(use_phase4b.index)))
    use = use_phase4b.reindex(dates).fillna(0.0).clip(0.0, 1.0)
    prod = production.reindex(dates)
    ph4 = phase4b.reindex(dates)
    switch_turnover = use.diff().abs().fillna(0.0)
    gross = (1.0 - use) * prod["gross_return"].fillna(prod["net_return"]) + use * ph4["gross_return"].fillna(ph4["net_return"])
    cost = (1.0 - use) * prod["cost"].fillna(0.0) + use * ph4["cost"].fillna(0.0) + switch_turnover * (DEFAULT_COST_BPS / 10000.0)
    path = pd.DataFrame(
        {
            "gross_return": gross,
            "net_return": gross - cost,
            "turnover": switch_turnover,
            "cost": cost,
            "bil_weight": 0.0,
            "safe_weight": 0.0,
            "offensive_weight": 0.0,
            "ml_sleeve_exposure": 0.0,
            "core_exposure": 1.0,
            "holdings_count": 1.0,
        },
        index=dates,
    )
    weights = make_synthetic_weights(dates, ["CORE_PRODUCTION", "CORE_PHASE4B"], {"CORE_PRODUCTION": 1.0 - use, "CORE_PHASE4B": use})
    return path, weights


def load_meta_probability(task_id: str, warnings_list: list[str]) -> tuple[pd.Series, str | None]:
    if not META_PRED_IN.exists():
        warn(f"Meta-label predictions missing for {task_id}: {META_PRED_IN}", warnings_list)
        return pd.Series(dtype=float), None
    try:
        pred = pd.read_parquet(META_PRED_IN)
        pred["Date"] = pd.to_datetime(pred["Date"])
        sub = pred[pred["task_id"].eq(task_id)].copy()
        if sub.empty:
            warn(f"Meta-label task missing in predictions: {task_id}", warnings_list)
            return pd.Series(dtype=float), None
        selected_model = None
        if META_MODEL_METRICS_IN.exists():
            metrics = pd.read_csv(META_MODEL_METRICS_IN)
            m = metrics[(metrics["task_id"].eq(task_id)) & (metrics["split"].eq("validation"))].copy()
            if not m.empty:
                sort_cols = [c for c in ["roc_auc", "f1", "accuracy"] if c in m.columns]
                selected_model = str(m.sort_values(sort_cols, ascending=False).iloc[0]["model_name"]) if sort_cols else str(m.iloc[0]["model_name"])
        if selected_model and selected_model in set(sub["model_name"].astype(str)):
            sub = sub[sub["model_name"].astype(str).eq(selected_model)]
        else:
            selected_model = str(sub["model_name"].mode().iloc[0])
            sub = sub[sub["model_name"].astype(str).eq(selected_model)]
        prob = sub.groupby("Date")["probability"].mean().sort_index()
        return prob, selected_model
    except Exception as exc:
        warn(f"Could not load meta-label probability for {task_id}: {exc}", warnings_list)
        return pd.Series(dtype=float), None


def strategy_returns_by_name(returns_df: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    return returns_df[returns_df["strategy_name"].eq(strategy_name)].set_index("Date").sort_index()


def weights_by_name(weights_df: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    sub = weights_df[weights_df["strategy_name"].eq(strategy_name)]
    if sub.empty:
        return pd.DataFrame()
    return sub.pivot_table(index="Date", columns="ticker", values="weight", aggfunc="sum").fillna(0.0).sort_index()


def best_summary_row(summary: pd.DataFrame, split: str, selection_group: str = "ensemble") -> dict[str, Any]:
    sub = summary[(summary["split"].eq(split)) & (summary["selection_group"].eq(selection_group)) & (summary["active_weeks"].ge(50))].copy()
    if sub.empty:
        return {}
    return sub.sort_values(["sharpe", "max_drawdown", "cvar_5", "annual_return"], ascending=[False, False, False, False]).iloc[0].to_dict()


def build_validation_selection(summary: pd.DataFrame, best_validation: dict[str, Any], best_holdout: dict[str, Any]) -> pd.DataFrame:
    val = summary[(summary["split"].eq("validation")) & (summary["selection_group"].eq("ensemble"))].copy()
    hold = summary[summary["split"].eq("holdout")][["strategy_name", "annual_return", "sharpe", "max_drawdown", "cvar_5"]].copy()
    hold = hold.rename(columns={c: f"holdout_{c}" for c in ["annual_return", "sharpe", "max_drawdown", "cvar_5"]})
    out = val.merge(hold, on="strategy_name", how="left")
    out["selected_by_validation"] = out["strategy_name"].eq(best_validation.get("strategy_name"))
    out["best_holdout_diagnostic"] = out["strategy_name"].eq(best_holdout.get("strategy_name"))
    return out.sort_values(["selected_by_validation", "sharpe", "annual_return"], ascending=[False, False, False]).reset_index(drop=True)


def strategy_comparison(summary: pd.DataFrame, benchmark: dict[str, pd.DataFrame], warnings_list: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hold = summary[summary["split"].eq("holdout")].copy()
    for _, row in hold.iterrows():
        item = row.to_dict()
        item["comparison_label"] = item["strategy_name"]
        item["category"] = "ensemble" if item.get("selection_group") == "ensemble" else item.get("strategy_family", "ensemble")
        rows.append(item)
    for name, frame in benchmark.items():
        if frame.empty:
            continue
        path = frame.copy()
        path["split"] = split_for_dates(path.index).values
        metrics = calc_metrics(path[path["split"].eq("holdout")])
        metrics.update({"strategy_name": name, "comparison_label": name, "category": "benchmark", "split": "holdout", "selection_group": "benchmark"})
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


def walkforward_summary(returns_df: pd.DataFrame, benchmark: dict[str, pd.DataFrame], focus_strategies: list[str]) -> pd.DataFrame:
    windows = {
        "2017_2018": (pd.Timestamp("2017-01-01"), pd.Timestamp("2018-12-31")),
        "2019_2020": (pd.Timestamp("2019-01-01"), pd.Timestamp("2020-12-31")),
        "2021_2022": (pd.Timestamp("2021-01-01"), pd.Timestamp("2022-12-31")),
        "2023_2026": (pd.Timestamp("2023-01-01"), pd.Timestamp("2026-12-31")),
    }
    rows: list[dict[str, Any]] = []
    for strategy in focus_strategies:
        path = strategy_returns_by_name(returns_df, strategy)
        if path.empty:
            continue
        for window, (start, end) in windows.items():
            sub = path.loc[(path.index >= start) & (path.index <= end)]
            metrics = calc_metrics(sub)
            metrics.update({"strategy_name": strategy, "category": "ensemble", "window": window})
            rows.append(metrics)
    for name, frame in benchmark.items():
        if name not in {"production", "official_shadow", "phase4b", "phase6", "phase7", "simple_momentum", "SPY", "60_40", "mlx5_sequence", "mlx6_transformer", "mlx7_meta_label", "mlx8_rl"}:
            continue
        for window, (start, end) in windows.items():
            sub = frame.loc[(frame.index >= start) & (frame.index <= end)]
            metrics = calc_metrics(sub)
            metrics.update({"strategy_name": name, "category": "benchmark", "window": window})
            rows.append(metrics)
    return pd.DataFrame(rows)


def state_by_state(returns_df: pd.DataFrame, state: pd.Series, focus_strategies: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    hold = returns_df[returns_df["split"].eq("holdout") & returns_df["strategy_name"].isin(focus_strategies)].copy()
    if hold.empty:
        return pd.DataFrame()
    hold["market_state"] = hold["Date"].map(state)
    for (strategy, mstate), group in hold.groupby(["strategy_name", "market_state"], dropna=False):
        metrics = calc_metrics(group.set_index("Date"))
        metrics.update({"strategy_name": strategy, "market_state": mstate, "weeks": int(len(group))})
        rows.append(metrics)
    return pd.DataFrame(rows).sort_values(["strategy_name", "sharpe"], ascending=[True, False])


def exposure_audit(weights_df: pd.DataFrame, universe_meta: pd.DataFrame, focus_strategies: list[str]) -> pd.DataFrame:
    if weights_df.empty:
        return pd.DataFrame()
    category = {}
    if not universe_meta.empty and {"ticker", "category"}.issubset(universe_meta.columns):
        category = universe_meta.drop_duplicates("ticker").set_index("ticker")["category"].to_dict()
    for synthetic in ["CORE_PRODUCTION", "CORE_PHASE4B", "CORE_LATEST_CANDIDATE"]:
        category[synthetic] = "Core strategy"
    category["CORE_PRODUCTION_PHASE4B_SWITCH"] = "Core strategy"
    category["MLX8_RL_DIAGNOSTIC"] = "RL diagnostic"
    hold = weights_df[weights_df["split"].eq("holdout") & weights_df["strategy_name"].isin(focus_strategies)].copy()
    rows: list[dict[str, Any]] = []
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
        top3 = pivot.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1)
        summary_groups = {
            "average_top3_weight": top3,
            "average_SPY_QQQ_SMH_weight": pivot.reindex(columns=[c for c in ["SPY", "QQQ", "SMH"] if c in pivot.columns]).sum(axis=1),
            "average_BIL_weight": pivot["BIL"] if "BIL" in pivot.columns else pd.Series(0.0, index=pivot.index),
            "average_safe_asset_weight": pivot.reindex(columns=[c for c in pivot.columns if c in SAFE_ASSETS]).sum(axis=1),
            "average_commodities_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "Commodities"]).sum(axis=1),
            "average_sector_weight": pivot.reindex(columns=[c for c in pivot.columns if category.get(c) == "US sectors"]).sum(axis=1),
        }
        for label, series in summary_groups.items():
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


def best_metric(comp: pd.DataFrame, strategy: str, metric: str) -> float:
    sub = comp[comp["strategy_name"].eq(strategy)]
    if sub.empty or metric not in sub.columns:
        return np.nan
    value = sub.iloc[0][metric]
    return float(value) if pd.notna(value) else np.nan


def choose_recommendation(selected_holdout: dict[str, Any], comp: pd.DataFrame, walk: pd.DataFrame) -> str:
    if not selected_holdout:
        return "REJECT"
    sharpe = float(selected_holdout.get("sharpe", np.nan))
    dd = float(selected_holdout.get("max_drawdown", np.nan))
    prod = best_metric(comp, "production", "sharpe")
    phase4b = best_metric(comp, "phase4b", "sharpe")
    cvar = float(selected_holdout.get("cvar_5", np.nan))
    if pd.notna(sharpe) and pd.notna(phase4b) and sharpe > phase4b and pd.notna(dd) and dd > -0.15 and pd.notna(cvar) and cvar > -0.035:
        return "READY FOR STRICTER AUDIT, NOT PRODUCTION"
    if pd.notna(sharpe) and pd.notna(prod) and sharpe > prod and pd.notna(dd) and dd > -0.18:
        return "PROMISING FILTER / SLEEVE BUT NEEDS WALK-FORWARD"
    if pd.notna(sharpe) and sharpe > 0.75:
        return "KEEP AS ML SHADOW"
    if pd.notna(sharpe) and sharpe > 0:
        return "KEEP AS RESEARCH ONLY"
    return "REJECT"


def write_notes(
    availability: dict[str, Any],
    candidate_defs: dict[str, Any],
    summary: pd.DataFrame,
    validation_selection: pd.DataFrame,
    comparison: pd.DataFrame,
    walk: pd.DataFrame,
    state: pd.DataFrame,
    exposure: pd.DataFrame,
    summary_json: dict[str, Any],
    warnings_list: list[str],
) -> None:
    best_val = summary_json.get("best_validation_selected_ensemble", {})
    best_hold = summary_json.get("best_holdout_diagnostic_ensemble", {})
    notes = f"""# Phase MLX Model Ensemble Notes

## Research-Only Warning

Phase MLX-9 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data where applicable, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed.

## Educational Explanation

An ensemble combines several models or strategies instead of relying on one forecast. Combining models can help when different models make different errors, but it can hurt when the added models are weak, overfit, or all just rediscover the same exposure.

Rank averaging converts each model's weekly ETF scores into within-date ranks and then averages those ranks. This makes signals easier to combine even when their raw probabilities are on different scales. An agreement filter only activates an ETF when multiple models independently rank it highly. A core plus ML sleeve keeps production or Phase 4B as the stable base and adds a smaller ML allocation only around the edges.

Validation selection matters because choosing the best result on holdout is hindsight. This script selects a primary ensemble by 2018-2019 validation Sharpe and reports the 2020+ holdout separately. The best holdout-only ensemble is included as diagnostic research, not as a valid promotion candidate.

## Technical Setup

- Components loaded: {', '.join(k for k, v in availability.items() if v.get('available'))}
- Components skipped: {', '.join(f"{k} ({v.get('reason')})" for k, v in availability.items() if not v.get('available')) or 'none'}
- Candidate ensemble families tested: rank-average, sequence-dominant, agreement-filter, defensive-first, core plus ML sleeve, meta-label-gated core/sleeve, and RL diagnostic blend.
- Validation selection: highest validation Sharpe among ensemble candidates, with holdout reported after selection.
- Overlays used: raw ML, BIL fallback, regime gate, 10% volatility target, and drawdown kill switch where applicable.
- Transaction cost assumption: 10 bps per unit turnover.
- Leakage controls: predictions at date `t` are treated as known-at-date scores; action at `t` earns next-week returns; forward target columns are not used as ensemble inputs.

## Results

- Best validation-selected ensemble: `{best_val.get('strategy_name', 'n/a')}`
- Validation Sharpe: {num(best_val.get('validation_sharpe'))}
- Holdout annual return: {pct(best_val.get('holdout_annual_return'))}
- Holdout Sharpe: {num(best_val.get('holdout_sharpe'))}
- Holdout max drawdown: {pct(best_val.get('holdout_max_drawdown'))}
- Holdout CVaR 5%: {pct(best_val.get('holdout_cvar_5'))}

- Best holdout-diagnostic ensemble: `{best_hold.get('strategy_name', 'n/a')}`
- Diagnostic holdout annual return: {pct(best_hold.get('annual_return'))}
- Diagnostic holdout Sharpe: {num(best_hold.get('sharpe'))}
- Diagnostic holdout max drawdown: {pct(best_hold.get('max_drawdown'))}
- Diagnostic holdout CVaR 5%: {pct(best_hold.get('cvar_5'))}

### Validation Selection

{markdown_table(validation_selection, ['strategy_name', 'strategy_family', 'sharpe', 'annual_return', 'max_drawdown', 'cvar_5', 'holdout_sharpe', 'holdout_annual_return', 'holdout_max_drawdown', 'selected_by_validation', 'best_holdout_diagnostic'], 15)}

### Strategy Comparison

{markdown_table(comparison, ['strategy_name', 'category', 'annual_return', 'annual_volatility', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_ml_sleeve_exposure', 'average_core_exposure'], 25)}

### Walk-Forward Windows

{markdown_table(walk, ['strategy_name', 'category', 'window', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'active_weeks'], 40)}

### State-By-State Results

{markdown_table(state, ['strategy_name', 'market_state', 'annual_return', 'sharpe', 'max_drawdown', 'cvar_5', 'average_bil_exposure', 'average_ml_sleeve_exposure', 'average_core_exposure', 'weeks'], 40)}

### Exposure Audit

{markdown_table(exposure, ['strategy_name', 'audit_type', 'item', 'category', 'average_weight', 'max_weight', 'holding_frequency'], 40)}

## Interpretation

- Does the validation-selected ensemble beat production by holdout Sharpe? {summary_json.get('validation_selected_beats_production_sharpe')}
- Does it beat official shadow by holdout Sharpe? {summary_json.get('validation_selected_beats_official_shadow_sharpe')}
- Does it beat Phase 4B by holdout Sharpe? {summary_json.get('validation_selected_beats_phase4b_sharpe')}
- Does it beat MLX-5C mean Sharpe? {summary_json.get('validation_selected_beats_mlx5c_sharpe')}
- Does it beat MLX-6 Transformer? {summary_json.get('validation_selected_beats_mlx6_sharpe')}
- Does it beat MLX-7 meta-labeling? {summary_json.get('validation_selected_beats_mlx7_sharpe')}
- Does it beat MLX-8 RL? {summary_json.get('validation_selected_beats_mlx8_sharpe')}
- Is the best result selected by validation rather than holdout hindsight? Yes for the primary candidate; the holdout-only best is labeled diagnostic.
- Final recommendation: **{summary_json.get('final_recommendation')}**

The ensemble is useful only if it improves risk-adjusted performance without hiding a worse tail profile behind model complexity. If the improvement comes mainly from one window or one component, it should remain a research-only shadow or offensive sleeve candidate.

## Warnings

{chr(10).join(f'- {w}' for w in warnings_list)}
"""
    NOTES_OUT.write_text(notes)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    warnings_list: list[str] = []
    warn("Experimental research-only Phase MLX output; not production-valid.", warnings_list)
    warn("Expanded ETF/yfinance research data can introduce selection bias and data-mining risk.", warnings_list)

    features = load_features()
    validate_inputs(features, warnings_list)
    weekly_returns = load_weekly_returns(warnings_list)
    next_returns = weekly_returns.shift(-1)
    universe_meta = load_universe_meta()
    state = infer_market_state_by_date(features)
    vol_panel = feature_matrix(features, "realized_vol_13w")
    if vol_panel.empty:
        vol_panel = feature_matrix(features, "realized_vol_26w")

    component_panel, availability = load_component_scores(warnings_list)
    signal_panel, candidate_defs = build_signal_panel(component_panel, availability)
    signal_panel.to_parquet(SIGNAL_PANEL_OUT, index=False)

    tickers = sorted(set(weekly_returns.columns) & set(signal_panel["ticker"].dropna().astype(str).unique()))
    dates = pd.DatetimeIndex(sorted(signal_panel["Date"].dropna().unique()))
    specs = build_candidate_specs(signal_panel)
    if not specs:
        raise RuntimeError("No ensemble candidate specs could be built.")

    predictions_rows: list[pd.DataFrame] = []
    returns_frames: list[pd.DataFrame] = []
    weights_frames: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []

    # Standalone ML ensemble sleeves.
    ml_paths: dict[str, pd.DataFrame] = {}
    ml_weights: dict[str, pd.DataFrame] = {}
    for spec in specs:
        raw_w = weights_from_scores(signal_panel, dates, tickers, spec.top_n, next_returns, vol_panel, spec.score_column, spec.eligible_column)
        wrapped_w, exposure = overlay_weights(spec.wrapper, raw_w, next_returns, state)
        path = compute_path(wrapped_w, next_returns, exposure=exposure, core_exposure=0.0)
        append_strategy(returns_frames, weights_frames, summary_rows, path, wrapped_w, spec.candidate_name, spec.family, spec.score_column, spec.top_n, spec.wrapper)
        ml_paths[spec.candidate_name] = path
        ml_weights[spec.candidate_name] = wrapped_w
        pred = signal_panel[["Date", "ticker", spec.score_column] + ([spec.eligible_column] if spec.eligible_column else [])].copy()
        pred = pred.rename(columns={spec.score_column: "score"})
        pred["candidate_name"] = spec.candidate_name
        pred["strategy_family"] = spec.family
        pred["top_n"] = spec.top_n
        pred["wrapper"] = spec.wrapper
        pred["eligible"] = pred[spec.eligible_column] if spec.eligible_column else pred["score"].notna().astype(float)
        predictions_rows.append(pred[["Date", "ticker", "candidate_name", "strategy_family", "top_n", "wrapper", "score", "eligible"]])

    returns_df = pd.concat(returns_frames, ignore_index=True)
    weights_df = pd.concat(weights_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    preliminary_best = best_summary_row(summary, "validation")
    sleeve_candidates = summary[(summary["split"].eq("validation")) & (summary["strategy_family"].isin(["rank_average", "sequence_dominant", "sequence_baseline", "defensive_first"]))].copy()
    if sleeve_candidates.empty:
        best_sleeve_name = preliminary_best.get("strategy_name")
    else:
        best_sleeve_name = sleeve_candidates.sort_values(["sharpe", "max_drawdown", "annual_return"], ascending=[False, False, False]).iloc[0]["strategy_name"]
    if best_sleeve_name not in ml_paths:
        best_sleeve_name = next(iter(ml_paths))
        warn("Could not locate validation-selected ML sleeve path; using first available sleeve for blends.", warnings_list)

    project_returns = load_project_returns(warnings_list)
    bench = benchmark_paths(weekly_returns, project_returns, warnings_list)

    # Core + ML sleeve candidates.
    blend_returns: list[pd.DataFrame] = []
    blend_weights: list[pd.DataFrame] = []
    blend_summary: list[dict[str, Any]] = []
    base_sleeve_path = ml_paths[best_sleeve_name]
    base_sleeve_weights = ml_weights[best_sleeve_name]
    for core_name in ("production", "phase4b"):
        if core_name not in project_returns:
            warn(f"Core strategy unavailable for core+ML sleeve: {core_name}", warnings_list)
            continue
        for sleeve_size in (0.10, 0.20, 0.30):
            name = f"{core_name}_plus_ml_sleeve_{int(sleeve_size * 100)}pct__{best_sleeve_name}"
            path, weights = blend_core_with_sleeve(core_name, project_returns[core_name], best_sleeve_name, base_sleeve_path, base_sleeve_weights, sleeve_size, strategy_name=name)
            append_strategy(blend_returns, blend_weights, blend_summary, path, weights, name, "core_ml_sleeve", best_sleeve_name, np.nan, "core_blend", core_name, sleeve_size)

    # Meta-label-gated core switch and ML sleeve activation.
    task_c_prob, task_c_model = load_meta_probability("task_c_phase4b_beats_production", warnings_list)
    task_d_prob, task_d_model = load_meta_probability("task_d_mlx5_sleeve_activation", warnings_list)
    if "production" in project_returns and "phase4b" in project_returns and not task_c_prob.empty:
        for threshold in (0.50, 0.60, 0.70):
            use_phase4b = (task_c_prob > threshold).astype(float)
            core_path, core_weights = switch_core_returns(project_returns["production"], project_returns["phase4b"], use_phase4b)
            core_name = f"meta_phase4b_switch_thr{threshold:.2f}_{task_c_model}"
            append_strategy(blend_returns, blend_weights, blend_summary, core_path, core_weights, core_name, "meta_label_gated", "task_c_phase4b_switch", np.nan, "meta_switch", "production_phase4b_switch", None)
            if not task_d_prob.empty:
                for sleeve_size in (0.10, 0.20, 0.30):
                    active = (task_d_prob > threshold).astype(float)
                    path, weights = blend_core_with_sleeve("production_phase4b_switch", core_path, best_sleeve_name, base_sleeve_path, base_sleeve_weights, sleeve_size, active)
                    name = f"meta_core_switch_plus_ml_sleeve_{int(sleeve_size * 100)}pct_thr{threshold:.2f}"
                    append_strategy(blend_returns, blend_weights, blend_summary, path, weights, name, "meta_label_gated", best_sleeve_name, np.nan, "meta_switch_plus_sleeve", "production_phase4b_switch", sleeve_size)
            else:
                warn("Task D ML sleeve activation probabilities missing; skipped meta-gated ML sleeve activation variants.", warnings_list)

    # RL diagnostic blend: intentionally low weight only.
    if "mlx8_rl" in bench:
        rl_frame = bench["mlx8_rl"]
        for core_name in ("production", "phase4b"):
            if core_name not in project_returns:
                continue
            for rl_weight in (0.05, 0.10):
                dates_blend = pd.DatetimeIndex(sorted(set(project_returns[core_name].index) & set(rl_frame.index)))
                core = project_returns[core_name].reindex(dates_blend)
                rl = rl_frame.reindex(dates_blend)
                gross = (1.0 - rl_weight) * core["gross_return"].fillna(core["net_return"]) + rl_weight * rl["gross_return"].fillna(rl["net_return"])
                cost = (1.0 - rl_weight) * core["cost"].fillna(0.0) + rl_weight * rl["cost"].fillna(0.0)
                path = pd.DataFrame(
                    {
                        "gross_return": gross,
                        "net_return": gross - cost,
                        "turnover": rl_weight * rl["turnover"].fillna(0.0),
                        "cost": cost,
                        "bil_weight": rl_weight * rl.get("bil_weight", pd.Series(0.0, index=dates_blend)).reindex(dates_blend).fillna(0.0),
                        "safe_weight": np.nan,
                        "offensive_weight": np.nan,
                        "ml_sleeve_exposure": rl_weight,
                        "core_exposure": 1.0 - rl_weight,
                        "holdings_count": np.nan,
                    },
                    index=dates_blend,
                )
                weights = make_synthetic_weights(dates_blend, [f"CORE_{core_name.upper()}", "MLX8_RL_DIAGNOSTIC"], {f"CORE_{core_name.upper()}": 1.0 - rl_weight, "MLX8_RL_DIAGNOSTIC": rl_weight})
                name = f"{core_name}_plus_rl_diagnostic_{int(rl_weight * 100)}pct"
                append_strategy(blend_returns, blend_weights, blend_summary, path, weights, name, "rl_diagnostic_blend", "mlx8_rl", np.nan, "rl_low_weight", core_name, rl_weight)
    else:
        warn("MLX-8 RL benchmark returns missing; skipped RL diagnostic blend.", warnings_list)

    if blend_returns:
        returns_df = pd.concat([returns_df, pd.concat(blend_returns, ignore_index=True)], ignore_index=True)
        weights_df = pd.concat([weights_df, pd.concat(blend_weights, ignore_index=True)], ignore_index=True)
        summary = pd.concat([summary, pd.DataFrame(blend_summary)], ignore_index=True)

    predictions = pd.concat(predictions_rows, ignore_index=True) if predictions_rows else pd.DataFrame()
    best_validation = best_summary_row(summary, "validation")
    best_holdout = best_summary_row(summary, "holdout")
    validation_selection = build_validation_selection(summary, best_validation, best_holdout)

    selected_holdout = {}
    if best_validation:
        row = summary[(summary["split"].eq("holdout")) & (summary["strategy_name"].eq(best_validation["strategy_name"]))]
        selected_holdout = row.iloc[0].to_dict() if not row.empty else {}

    comparison = strategy_comparison(summary, bench, warnings_list)
    focus = sorted(set([best_validation.get("strategy_name"), best_holdout.get("strategy_name")]) - {None, ""})
    walk = walkforward_summary(returns_df, bench, focus)
    state_results = state_by_state(returns_df, state, focus)
    exposure = exposure_audit(weights_df, universe_meta, focus)

    def beats(strategy: str, metric: str = "sharpe") -> bool:
        selected = selected_holdout.get(metric, np.nan)
        other = best_metric(comparison, strategy, metric)
        return bool(pd.notna(selected) and pd.notna(other) and float(selected) > other)

    mlx5c_sharpe = best_metric(comparison, "mlx5c_bil_fallback_mean_summary", "sharpe")
    selected_sharpe = selected_holdout.get("sharpe", np.nan)
    final_recommendation = choose_recommendation(selected_holdout, comparison, walk)
    summary_json = {
        "phase": "MLX-9 model ensemble",
        "production_valid": False,
        "research_only": True,
        "selection_bias_warning": True,
        "data_mining_warning": True,
        "overfitting_warning": True,
        "purpose": "experimental ML sandbox only",
        "components_loaded": [k for k, v in availability.items() if v.get("available")],
        "components_skipped": {k: v for k, v in availability.items() if not v.get("available")},
        "ensemble_candidates_tested": int(summary["strategy_name"].nunique()),
        "best_validation_selected_ensemble": {
            **best_validation,
            "holdout_annual_return": selected_holdout.get("annual_return", np.nan),
            "holdout_sharpe": selected_holdout.get("sharpe", np.nan),
            "holdout_max_drawdown": selected_holdout.get("max_drawdown", np.nan),
            "holdout_cvar_5": selected_holdout.get("cvar_5", np.nan),
            "validation_sharpe": best_validation.get("sharpe", np.nan),
        },
        "best_holdout_diagnostic_ensemble": best_holdout,
        "validation_selected_beats_production_sharpe": beats("production"),
        "validation_selected_beats_official_shadow_sharpe": beats("official_shadow"),
        "validation_selected_beats_phase4b_sharpe": beats("phase4b"),
        "validation_selected_beats_mlx5c_sharpe": bool(pd.notna(selected_sharpe) and pd.notna(mlx5c_sharpe) and selected_sharpe > mlx5c_sharpe),
        "validation_selected_beats_mlx6_sharpe": beats("mlx6_transformer"),
        "validation_selected_beats_mlx7_sharpe": beats("mlx7_meta_label"),
        "validation_selected_beats_mlx8_sharpe": beats("mlx8_rl"),
        "final_recommendation": final_recommendation,
        "warnings": warnings_list + ["No ensemble model is promoted automatically."],
        "no_production_pins_changed": True,
        "no_dashboard_changes": True,
        "no_production_strategy_logic_changed": True,
        "outputs": {
            "signal_panel": str(SIGNAL_PANEL_OUT.relative_to(ROOT)),
            "predictions": str(PREDICTIONS_OUT.relative_to(ROOT)),
            "strategy_returns": str(RETURNS_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
            "validation_selection": str(VALIDATION_SELECTION_OUT.relative_to(ROOT)),
            "walkforward": str(WALKFORWARD_OUT.relative_to(ROOT)),
            "state_by_state": str(STATE_BY_STATE_OUT.relative_to(ROOT)),
            "exposure_audit": str(EXPOSURE_AUDIT_OUT.relative_to(ROOT)),
            "strategy_comparison": str(STRATEGY_COMPARISON_OUT.relative_to(ROOT)),
            "component_availability": str(COMPONENT_AVAILABILITY_OUT.relative_to(ROOT)),
            "candidate_definitions": str(CANDIDATE_DEFINITIONS_OUT.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
    }

    predictions.to_parquet(PREDICTIONS_OUT, index=False)
    returns_df.to_csv(RETURNS_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)
    validation_selection.to_csv(VALIDATION_SELECTION_OUT, index=False)
    walk.to_csv(WALKFORWARD_OUT, index=False)
    state_results.to_csv(STATE_BY_STATE_OUT, index=False)
    exposure.to_csv(EXPOSURE_AUDIT_OUT, index=False)
    comparison.to_csv(STRATEGY_COMPARISON_OUT, index=False)
    COMPONENT_AVAILABILITY_OUT.write_text(json.dumps(availability, indent=2, default=json_default))
    CANDIDATE_DEFINITIONS_OUT.write_text(json.dumps(candidate_defs, indent=2, default=json_default))
    SUMMARY_JSON_OUT.write_text(json.dumps(summary_json, indent=2, default=json_default))
    write_notes(availability, candidate_defs, summary, validation_selection, comparison, walk, state_results, exposure, summary_json, summary_json["warnings"])

    print("Phase MLX-9 model ensemble")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print(f"Components loaded: {summary_json['components_loaded']}")
    print(f"Components skipped: {list(summary_json['components_skipped'].keys())}")
    print(f"Ensemble candidates tested: {summary_json['ensemble_candidates_tested']}")
    print(f"Best validation-selected ensemble: {best_validation.get('strategy_name') if best_validation else 'n/a'}")
    print(f"Validation-selected holdout Sharpe: {selected_holdout.get('sharpe') if selected_holdout else np.nan}")
    print(f"Best holdout-diagnostic ensemble: {best_holdout.get('strategy_name') if best_holdout else 'n/a'}")
    print(f"Best holdout-diagnostic Sharpe: {best_holdout.get('sharpe') if best_holdout else np.nan}")
    print(f"Final recommendation: {final_recommendation}")
    print("Outputs:")
    for path in [
        SIGNAL_PANEL_OUT,
        PREDICTIONS_OUT,
        RETURNS_OUT,
        SUMMARY_OUT,
        VALIDATION_SELECTION_OUT,
        WALKFORWARD_OUT,
        STATE_BY_STATE_OUT,
        EXPOSURE_AUDIT_OUT,
        STRATEGY_COMPARISON_OUT,
        COMPONENT_AVAILABILITY_OUT,
        CANDIDATE_DEFINITIONS_OUT,
        SUMMARY_JSON_OUT,
        NOTES_OUT,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
