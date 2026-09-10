#!/usr/bin/env python3
"""
Phase MLX-2: build a date x ETF ML feature panel for experimental research.

This script is research-only. It consumes Phase MLX-1 expanded ETF outputs,
keeps all artifacts under data/research/ml_lab, and does not modify production
pins, dashboard code, strategy logic, or production candidates.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
EXPANDED_DIR = ROOT / "data" / "research" / "ml_lab" / "expanded_universe"
OUTPUT_DIR = ROOT / "data" / "research" / "ml_lab" / "feature_panel"
DOCS_DIR = ROOT / "docs" / "research" / "ml_lab"

PRICES_IN = EXPANDED_DIR / "expanded_etf_prices_weekly.csv"
RETURNS_IN = EXPANDED_DIR / "expanded_etf_returns_weekly.csv"

FEATURE_PANEL_OUT = OUTPUT_DIR / "ml_feature_panel.parquet"
TARGETS_OUT = OUTPUT_DIR / "ml_targets.parquet"
SAMPLE_OUT = OUTPUT_DIR / "ml_feature_panel_sample.csv"
METADATA_OUT = OUTPUT_DIR / "ml_feature_metadata.json"
COVERAGE_OUT = OUTPUT_DIR / "ml_feature_coverage_report.csv"
NOTES_OUT = DOCS_DIR / "phase_mlx_feature_panel_notes.md"

STOCK_BREADTH_PATH = ROOT / "data" / "research" / "stock_breadth" / "stock_breadth_weekly.csv"


BASE_FEATURE_DEFINITIONS = {
    "trailing_return_1w": "Simple return from t-1 week to t.",
    "trailing_return_4w": "Simple return from t-4 weeks to t.",
    "trailing_return_13w": "Simple return from t-13 weeks to t.",
    "trailing_return_26w": "Simple return from t-26 weeks to t.",
    "trailing_return_52w": "Simple return from t-52 weeks to t.",
    "momentum_12_1": "Simple return from t-52 weeks to t-4 weeks, skipping the most recent month.",
    "realized_vol_4w": "Annualized realized volatility of weekly log returns over trailing 4 weeks.",
    "realized_vol_13w": "Annualized realized volatility of weekly log returns over trailing 13 weeks.",
    "realized_vol_26w": "Annualized realized volatility of weekly log returns over trailing 26 weeks.",
    "rolling_sharpe_13w": "Annualized rolling mean / volatility of weekly log returns over trailing 13 weeks.",
    "rolling_sharpe_26w": "Annualized rolling mean / volatility of weekly log returns over trailing 26 weeks.",
    "rolling_max_drawdown_26w": "Worst drawdown inside the trailing 26-week price window through t.",
    "drawdown_from_52w_high": "Price at t divided by trailing 52-week high through t minus 1.",
    "relative_strength_vs_SPY_4w": "ETF trailing 4-week return minus SPY trailing 4-week return.",
    "relative_strength_vs_SPY_13w": "ETF trailing 13-week return minus SPY trailing 13-week return.",
    "relative_strength_vs_BIL_4w": "ETF trailing 4-week return minus BIL trailing 4-week return.",
    "relative_strength_vs_BIL_13w": "ETF trailing 13-week return minus BIL trailing 13-week return.",
    "beta_to_SPY_26w": "Trailing 26-week beta of ETF weekly log returns to SPY weekly log returns.",
    "corr_to_SPY_26w": "Trailing 26-week correlation of ETF weekly log returns to SPY weekly log returns.",
    "cross_sectional_return_rank_13w": "Percentile rank of ETF trailing 13-week return across the ETF universe at t.",
    "cross_sectional_return_rank_26w": "Percentile rank of ETF trailing 26-week return across the ETF universe at t.",
    "cross_sectional_vol_rank_13w": "Percentile rank of ETF trailing 13-week volatility across the ETF universe at t.",
}

TARGET_DEFINITIONS = {
    "forward_return_4w": "Simple return from t to t+4 weeks. Target only.",
    "forward_return_13w": "Simple return from t to t+13 weeks. Target only.",
    "forward_rank_4w": "Cross-sectional percentile rank of forward_return_4w at date t. Target only.",
    "forward_rank_13w": "Cross-sectional percentile rank of forward_return_13w at date t. Target only.",
    "beats_SPY_4w": "1 if ETF forward_return_4w exceeds SPY forward_return_4w, else 0. Target only.",
    "beats_BIL_4w": "1 if ETF forward_return_4w exceeds BIL forward_return_4w, else 0. Target only.",
    "positive_forward_4w": "1 if ETF forward_return_4w is positive, else 0. Target only.",
    "top_quintile_forward_4w": "1 if ETF is in the top 20% of forward_return_4w ranks at date t, else 0. Target only.",
}


def warn(message: str, warnings_list: list[str]) -> None:
    warnings_list.append(message)
    print(f"WARNING: {message}", file=sys.stderr)


def slug(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def load_panel_csv(path: Path, warnings_list: list[str]) -> pd.DataFrame:
    if not path.exists():
        warn(f"Required input missing: {path}", warnings_list)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        warn(f"Could not read required input {path}: {exc}", warnings_list)
        return pd.DataFrame()

    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    df.index.name = "Date"
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def read_date_indexed_csv(path: Path, warnings_list: list[str]) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        warn(f"Optional file could not be read and was skipped: {path} ({exc})", warnings_list)
        return pd.DataFrame()
    if "Date" not in df.columns:
        warn(f"Optional file has no Date column and was skipped: {path}", warnings_list)
        return pd.DataFrame()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["Date"]).set_index("Date").sort_index()
    df.index.name = "Date"
    return df


def rolling_max_drawdown(window: np.ndarray) -> float:
    clean = window[np.isfinite(window)]
    if clean.size < 2:
        return np.nan
    running_high = np.maximum.accumulate(clean)
    drawdowns = clean / running_high - 1.0
    return float(np.min(drawdowns))


def safe_binary(condition: pd.DataFrame, valid: pd.DataFrame) -> pd.DataFrame:
    return condition.astype(float).where(valid)


def build_base_feature_frames(
    prices: pd.DataFrame,
    weekly_log_returns: pd.DataFrame,
    warnings_list: list[str],
) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    weekly_log_returns = weekly_log_returns.reindex(index=prices.index, columns=prices.columns)

    for weeks in (1, 4, 13, 26, 52):
        features[f"trailing_return_{weeks}w"] = prices.pct_change(weeks)

    features["momentum_12_1"] = prices.shift(4).div(prices.shift(52)).sub(1.0)

    for weeks in (4, 13, 26):
        features[f"realized_vol_{weeks}w"] = weekly_log_returns.rolling(
            weeks, min_periods=max(2, math.ceil(weeks / 2))
        ).std() * math.sqrt(52.0)

    for weeks in (13, 26):
        rolling_mean = weekly_log_returns.rolling(weeks, min_periods=max(4, math.ceil(weeks / 2))).mean()
        rolling_vol = weekly_log_returns.rolling(weeks, min_periods=max(4, math.ceil(weeks / 2))).std()
        features[f"rolling_sharpe_{weeks}w"] = rolling_mean.div(rolling_vol.replace(0.0, np.nan)) * math.sqrt(52.0)

    features["rolling_max_drawdown_26w"] = prices.rolling(26, min_periods=13).apply(rolling_max_drawdown, raw=True)
    features["drawdown_from_52w_high"] = prices.div(prices.rolling(52, min_periods=26).max()).sub(1.0)

    for benchmark in ("SPY", "BIL"):
        if benchmark not in prices.columns:
            warn(f"Benchmark {benchmark} missing; relative-strength features versus {benchmark} will be NaN.", warnings_list)
            for weeks in (4, 13):
                features[f"relative_strength_vs_{benchmark}_{weeks}w"] = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
            continue
        for weeks in (4, 13):
            benchmark_return = prices[benchmark].pct_change(weeks)
            features[f"relative_strength_vs_{benchmark}_{weeks}w"] = features[f"trailing_return_{weeks}w"].sub(
                benchmark_return, axis=0
            )

    if "SPY" not in weekly_log_returns.columns:
        warn("SPY missing from returns; beta_to_SPY_26w and corr_to_SPY_26w will be NaN.", warnings_list)
        features["beta_to_SPY_26w"] = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
        features["corr_to_SPY_26w"] = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    else:
        spy_returns = weekly_log_returns["SPY"]
        spy_var = spy_returns.rolling(26, min_periods=13).var()
        cov_to_spy = weekly_log_returns.rolling(26, min_periods=13).cov(spy_returns)
        features["beta_to_SPY_26w"] = cov_to_spy.div(spy_var.replace(0.0, np.nan), axis=0)
        features["corr_to_SPY_26w"] = weekly_log_returns.rolling(26, min_periods=13).corr(spy_returns)

    features["cross_sectional_return_rank_13w"] = features["trailing_return_13w"].rank(axis=1, pct=True)
    features["cross_sectional_return_rank_26w"] = features["trailing_return_26w"].rank(axis=1, pct=True)
    features["cross_sectional_vol_rank_13w"] = features["realized_vol_13w"].rank(axis=1, pct=True)
    return features


def discover_regime_files(warnings_list: list[str]) -> tuple[list[Path], list[dict[str, str]]]:
    fixed_candidates = [
        ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history_refined.csv",
        ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv",
        ROOT / "data" / "04_layer2b_risk_regime_engine" / "regime_score.csv",
        ROOT / "data" / "04_layer2b_risk_regime_engine" / "regime_states.csv",
        ROOT / "data" / "04_layer2b_risk_regime_engine" / "phase_kk_targeta_regime_confidence_predictions.csv",
        ROOT / "public" / "dashboard-summary.json",
    ]
    discovered: list[Path] = []
    for base in [ROOT / "data" / "04_layer2b_risk_regime_engine", ROOT / "data" / "research"]:
        if not base.exists():
            warn(f"Optional regime search directory missing: {base}", warnings_list)
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() != ".csv":
                continue
            lower = path.name.lower()
            if (
                "market_state_history" in lower
                or lower in {"regime_score.csv", "regime_states.csv"}
                or ("state" in lower and "history" in lower)
            ):
                discovered.append(path)

    ordered: list[Path] = []
    seen: set[Path] = set()
    for path in fixed_candidates + discovered:
        if path in seen:
            continue
        seen.add(path)
        if path.exists():
            ordered.append(path)
        elif path.suffix != ".json":
            warn(f"Optional regime/state file missing: {path}", warnings_list)

    json_notes: list[dict[str, str]] = []
    dashboard_json = ROOT / "public" / "dashboard-summary.json"
    if dashboard_json.exists():
        try:
            payload = json.loads(dashboard_json.read_text())
            if not isinstance(payload, dict) or "Date" not in payload:
                json_notes.append(
                    {
                        "path": str(dashboard_json.relative_to(ROOT)),
                        "status": "found_skipped",
                        "reason": "dashboard summary is aggregate JSON, not a date-indexed regime history",
                    }
                )
                warn(
                    f"Found {dashboard_json}, but skipped it because it is not a date-indexed regime history.",
                    warnings_list,
                )
        except Exception as exc:
            json_notes.append(
                {
                    "path": str(dashboard_json.relative_to(ROOT)),
                    "status": "found_unreadable",
                    "reason": str(exc),
                }
            )
            warn(f"Found {dashboard_json}, but could not parse it as JSON: {exc}", warnings_list)
    else:
        json_notes.append(
            {
                "path": str(dashboard_json.relative_to(ROOT)),
                "status": "missing",
                "reason": "optional dashboard summary not found",
            }
        )
        warn(f"Optional dashboard summary not found: {dashboard_json}", warnings_list)

    return [path for path in ordered if path.suffix.lower() == ".csv"], json_notes


def build_regime_features(dates: pd.DatetimeIndex, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any]]:
    files, json_notes = discover_regime_files(warnings_list)
    if not files:
        warn("No optional regime/state CSV files found; regime features will be omitted.", warnings_list)
        return pd.DataFrame(index=dates), {}, {"found": False, "loaded_files": [], "json_notes": json_notes}

    combined = pd.DataFrame(index=dates)
    source_map: dict[str, str] = {}
    loaded_files: list[str] = []
    skipped_files: list[str] = []
    market_state_loaded = False

    preferred_numeric_patterns = (
        "prob",
        "score",
        "risk",
        "regime",
        "drawdown",
        "trend",
        "breadth",
        "canary",
        "stress",
        "corr",
        "fear",
        "confidence",
        "overlay",
        "multiplier",
        "defensive",
        "vol",
        "z_",
        "deterioration",
    )

    for path in files:
        df = read_date_indexed_csv(path, warnings_list)
        if df.empty:
            skipped_files.append(str(path.relative_to(ROOT)))
            continue
        loaded_files.append(str(path.relative_to(ROOT)))
        rel_path = str(path.relative_to(ROOT))

        if "market_state" in df.columns and not market_state_loaded:
            states = df["market_state"].astype("string").reindex(dates)
            dummies = pd.get_dummies(states, prefix="market_state", dummy_na=False)
            dummies.index = dates
            for col in dummies.columns:
                if col not in combined.columns:
                    combined[col] = dummies[col].astype(float)
                    source_map[col] = rel_path
            market_state_loaded = True

        for col in df.columns:
            if col in combined.columns or col == "market_state":
                continue
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().sum() == 0:
                continue
            lower = col.lower()
            if not any(pattern in lower for pattern in preferred_numeric_patterns):
                continue
            combined[col] = numeric.reindex(dates)
            source_map[col] = rel_path

    if combined.empty:
        warn("Regime/state files were found, but no usable date-indexed regime features were extracted.", warnings_list)

    return combined, source_map, {
        "found": bool(files),
        "loaded_files": loaded_files,
        "skipped_files": skipped_files,
        "json_notes": json_notes,
        "market_state_one_hot_found": any(col.startswith("market_state_") for col in combined.columns),
        "transition_good_state_prob_found": "transition_good_state_prob" in combined.columns,
        "risk_regime_score_found": "risk_regime_score" in combined.columns,
    }


def build_stock_breadth_features(dates: pd.DatetimeIndex, warnings_list: list[str]) -> tuple[pd.DataFrame, dict[str, str], dict[str, Any]]:
    if not STOCK_BREADTH_PATH.exists():
        warn(f"Optional stock breadth prototype file missing: {STOCK_BREADTH_PATH}", warnings_list)
        return (
            pd.DataFrame(index=dates),
            {},
            {
                "found": False,
                "loaded_file": None,
                "survivorship_biased_research_only": True,
                "production_valid": False,
            },
        )

    df = read_date_indexed_csv(STOCK_BREADTH_PATH, warnings_list)
    if df.empty:
        return (
            pd.DataFrame(index=dates),
            {},
            {
                "found": True,
                "loaded_file": str(STOCK_BREADTH_PATH.relative_to(ROOT)),
                "usable": False,
                "survivorship_biased_research_only": True,
                "production_valid": False,
            },
        )

    feature_df = pd.DataFrame(index=dates)
    source_map: dict[str, str] = {}
    for col in df.columns:
        if col == "diagnostic_label":
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.notna().sum() == 0:
            continue
        feature_df[col] = numeric.reindex(dates)
        source_map[col] = str(STOCK_BREADTH_PATH.relative_to(ROOT))

    return feature_df, source_map, {
        "found": True,
        "usable": not feature_df.empty,
        "loaded_file": str(STOCK_BREADTH_PATH.relative_to(ROOT)),
        "feature_columns": list(feature_df.columns),
        "survivorship_biased_research_only": True,
        "current_sp500_yfinance_prototype": True,
        "production_valid": False,
    }


def stack_feature_frames(feature_frames: dict[str, pd.DataFrame], dates: pd.DatetimeIndex, tickers: list[str]) -> pd.DataFrame:
    series_list = []
    for name, frame in feature_frames.items():
        aligned = frame.reindex(index=dates, columns=tickers)
        aligned.index.name = "Date"
        stacked = (
            aligned.reset_index()
            .melt(id_vars="Date", var_name="ticker", value_name=name)
            .set_index(["Date", "ticker"])[name]
        )
        series_list.append(stacked)
    panel = pd.concat(series_list, axis=1)
    panel.index.names = ["Date", "ticker"]
    return panel.reset_index()


def build_targets(prices: pd.DataFrame, warnings_list: list[str]) -> pd.DataFrame:
    targets: dict[str, pd.DataFrame] = {}
    targets["forward_return_4w"] = prices.shift(-4).div(prices).sub(1.0)
    targets["forward_return_13w"] = prices.shift(-13).div(prices).sub(1.0)
    targets["forward_rank_4w"] = targets["forward_return_4w"].rank(axis=1, pct=True)
    targets["forward_rank_13w"] = targets["forward_return_13w"].rank(axis=1, pct=True)

    for benchmark in ("SPY", "BIL"):
        target_name = f"beats_{benchmark}_4w"
        if benchmark not in prices.columns:
            warn(f"Benchmark {benchmark} missing; target {target_name} will be NaN.", warnings_list)
            targets[target_name] = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
            continue
        benchmark_forward = targets["forward_return_4w"][benchmark]
        benchmark_valid = pd.DataFrame(
            {ticker: benchmark_forward.notna() for ticker in prices.columns},
            index=prices.index,
        )
        valid = targets["forward_return_4w"].notna() & benchmark_valid
        targets[target_name] = safe_binary(targets["forward_return_4w"].gt(benchmark_forward, axis=0), valid)

    targets["positive_forward_4w"] = safe_binary(
        targets["forward_return_4w"].gt(0.0),
        targets["forward_return_4w"].notna(),
    )
    targets["top_quintile_forward_4w"] = safe_binary(
        targets["forward_rank_4w"].ge(0.80),
        targets["forward_rank_4w"].notna(),
    )

    target_panel = stack_feature_frames(targets, prices.index, list(prices.columns))
    return target_panel


def build_coverage_report(
    feature_panel: pd.DataFrame,
    targets: pd.DataFrame,
    feature_columns: list[str],
    target_columns: list[str],
    source_map: dict[str, str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_feature_rows = len(feature_panel)
    total_target_rows = len(targets)
    for col in feature_columns:
        valid_dates = feature_panel.loc[feature_panel[col].notna(), "Date"]
        rows.append(
            {
                "column": col,
                "role": "feature",
                "source": source_map.get(col, "computed_from_mlx_weekly_prices_returns"),
                "non_null_count": int(feature_panel[col].notna().sum()),
                "total_rows": int(total_feature_rows),
                "non_null_pct": float(feature_panel[col].notna().mean()) if total_feature_rows else 0.0,
                "first_valid_date": valid_dates.min().date().isoformat() if not valid_dates.empty else "",
                "last_valid_date": valid_dates.max().date().isoformat() if not valid_dates.empty else "",
            }
        )
    for col in target_columns:
        valid_dates = targets.loc[targets[col].notna(), "Date"]
        rows.append(
            {
                "column": col,
                "role": "target",
                "source": "computed_forward_from_mlx_weekly_prices",
                "non_null_count": int(targets[col].notna().sum()),
                "total_rows": int(total_target_rows),
                "non_null_pct": float(targets[col].notna().mean()) if total_target_rows else 0.0,
                "first_valid_date": valid_dates.min().date().isoformat() if not valid_dates.empty else "",
                "last_valid_date": valid_dates.max().date().isoformat() if not valid_dates.empty else "",
            }
        )
    return pd.DataFrame(rows).sort_values(["role", "column"]).reset_index(drop=True)


def write_notes() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_OUT.write_text(
        """# Phase MLX Feature Panel Notes

Phase MLX-2 builds a date × ETF machine-learning feature panel for the experimental hard-ML research lab.

## Data Source

Required inputs come from the Phase MLX-1 expanded ETF universe:

- `data/research/ml_lab/expanded_universe/expanded_etf_prices_weekly.csv`
- `data/research/ml_lab/expanded_universe/expanded_etf_returns_weekly.csv`

These inputs are based on `yfinance` research data. They are not production-valid and should not be used for live trading decisions.

## Feature Definitions

The panel is one row per ETF per weekly Friday date. ETF-level features use information available at or before date `t`, including trailing returns, 12-1 momentum, realized volatility, rolling Sharpe, trailing max drawdown, drawdown from 52-week high, relative strength versus `SPY` and `BIL`, rolling beta/correlation to `SPY`, and cross-sectional ranks computed only from same-date trailing features.

Optional regime features are merged by date when project state files are available. Market-state values are converted to one-hot variables, and numeric risk/regime/probability/score fields are included without global standardization.

Optional stock breadth prototype features are merged by date when `data/research/stock_breadth/stock_breadth_weekly.csv` exists. These features are current-S&P/yfinance prototype features and are survivorship-biased, research-only, and not production-valid.

## Target Definitions

Targets are saved separately from features:

- `forward_return_4w`
- `forward_return_13w`
- `forward_rank_4w`
- `forward_rank_13w`
- `beats_SPY_4w`
- `beats_BIL_4w`
- `positive_forward_4w`
- `top_quintile_forward_4w`

Forward returns and forward ranks are labels only. They are not joined into the feature parquet.

## Leakage Prevention

- Feature columns use trailing or same-date information only.
- Forward returns are kept only in `ml_targets.parquet`.
- The script does not globally standardize, normalize, or fit scalers.
- Cross-sectional feature ranks use same-date trailing values, not future returns.
- Future ranks are target columns only.

## Missing File Warnings

Project regime/state files and stock breadth prototype files are optional. Missing or unparseable optional files should produce warnings and metadata entries, not crashes.

## Research-Only Status

This panel is experimental and high-overfitting-risk. The expanded ETF universe can introduce selection bias and data-mining risk. No output from this lab is production-valid, no dashboard code is changed, and no strategy candidate should be promoted from this work without separate validation and human review.

## Next Step

MLX-3 will train initial tabular ML models on this feature/target split with explicit walk-forward validation and leakage checks.
""",
        encoding="utf-8",
    )


def main() -> int:
    warnings_list: list[str] = []
    print("Phase MLX-2 date x ETF ML feature panel builder")
    print("WARNING: experimental research-only output; not production-valid; high overfitting risk.")
    print("WARNING: expanded ETF ML panels can introduce selection bias and data-mining risk.")

    prices = load_panel_csv(PRICES_IN, warnings_list)
    returns = load_panel_csv(RETURNS_IN, warnings_list)
    if prices.empty or returns.empty:
        warn("Required MLX-1 prices or returns are empty; cannot build feature panel.", warnings_list)
        return 1

    prices = prices.dropna(axis=1, how="all").sort_index()
    returns = returns.reindex(index=prices.index, columns=prices.columns).sort_index()
    dates = prices.index
    tickers = list(prices.columns)

    base_frames = build_base_feature_frames(prices, returns, warnings_list)
    regime_features, regime_source_map, regime_meta = build_regime_features(dates, warnings_list)
    stock_breadth_features, stock_source_map, stock_meta = build_stock_breadth_features(dates, warnings_list)

    source_map = {name: "computed_from_mlx_weekly_prices_returns" for name in base_frames}
    source_map.update(regime_source_map)
    source_map.update(stock_source_map)

    feature_panel = stack_feature_frames(base_frames, dates, tickers)
    if not regime_features.empty:
        feature_panel = feature_panel.merge(regime_features.reset_index(), on="Date", how="left")
    if not stock_breadth_features.empty:
        feature_panel = feature_panel.merge(stock_breadth_features.reset_index(), on="Date", how="left")

    targets = build_targets(prices, warnings_list)

    feature_columns = [col for col in feature_panel.columns if col not in {"Date", "ticker"}]
    target_columns = [col for col in targets.columns if col not in {"Date", "ticker"}]
    coverage = build_coverage_report(feature_panel, targets, feature_columns, target_columns, source_map)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    feature_panel.to_parquet(FEATURE_PANEL_OUT, index=False)
    targets.to_parquet(TARGETS_OUT, index=False)
    feature_panel.head(500).to_csv(SAMPLE_OUT, index=False)
    coverage.to_csv(COVERAGE_OUT, index=False)
    write_notes()

    metadata = {
        "phase": "MLX-2 date x ETF ML feature panel",
        "source": "Phase MLX-1 yfinance-based expanded ETF weekly prices and returns",
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
        "global_standardization_applied": False,
        "feature_panel_shape": list(feature_panel.shape),
        "target_shape": list(targets.shape),
        "number_of_etfs": len(tickers),
        "number_of_dates": len(dates),
        "number_of_features": len(feature_columns),
        "number_of_targets": len(target_columns),
        "date_range": {
            "start": dates.min().date().isoformat(),
            "end": dates.max().date().isoformat(),
        },
        "tickers": tickers,
        "input_paths": {
            "weekly_prices": str(PRICES_IN.relative_to(ROOT)),
            "weekly_returns": str(RETURNS_IN.relative_to(ROOT)),
        },
        "outputs": {
            "feature_panel": str(FEATURE_PANEL_OUT.relative_to(ROOT)),
            "targets": str(TARGETS_OUT.relative_to(ROOT)),
            "sample": str(SAMPLE_OUT.relative_to(ROOT)),
            "metadata": str(METADATA_OUT.relative_to(ROOT)),
            "coverage_report": str(COVERAGE_OUT.relative_to(ROOT)),
            "notes": str(NOTES_OUT.relative_to(ROOT)),
        },
        "feature_columns": feature_columns,
        "target_columns": target_columns,
        "base_feature_definitions": BASE_FEATURE_DEFINITIONS,
        "target_definitions": TARGET_DEFINITIONS,
        "feature_source_map": source_map,
        "regime_features": regime_meta,
        "stock_breadth_features": stock_meta,
        "leakage_prevention": [
            "Feature columns use trailing or same-date values available at or before date t.",
            "Forward returns and forward ranks are target-only columns saved in ml_targets.parquet.",
            "No global standardization, scaler fitting, or full-sample normalization is applied.",
            "Cross-sectional feature ranks are computed from same-date trailing features only.",
            "Future ranks are target columns only and are not included in ml_feature_panel.parquet.",
        ],
        "warnings": warnings_list
        + [
            "Experimental research-only Phase MLX output; not production-valid.",
            "Expanded ETF universe testing can introduce selection bias and data-mining risk.",
            "High overfitting risk; do not use for live trading decisions.",
            "Stock breadth prototype features, when present, are survivorship-biased research diagnostics.",
        ],
    }
    METADATA_OUT.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    print(f"Feature panel shape: {feature_panel.shape}")
    print(f"Target shape: {targets.shape}")
    print(f"ETFs: {len(tickers)}")
    print(f"Dates: {len(dates)}")
    print(f"Features: {len(feature_columns)}")
    print(f"Date range: {dates.min().date().isoformat()} to {dates.max().date().isoformat()}")
    print(f"Regime features found: {bool(regime_meta.get('loaded_files'))}")
    print(f"Regime files loaded: {', '.join(regime_meta.get('loaded_files', [])) or 'none'}")
    print(f"Stock breadth features found: {stock_meta.get('usable', False)}")
    print(f"Warnings: {len(metadata['warnings'])}")
    print("Outputs:")
    for path in metadata["outputs"].values():
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
