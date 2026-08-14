"""Reproduce the official production candidate and write Track A reports."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper
from production_allocator import production_pipeline_description, run_production_allocator
from production_config import (
    GGG_BASELINE,
    OFFICIAL_HOLDOUT_START,
    PRODUCTION_CANDIDATE,
    SUMMARY_PATH,
    TRACK_A_DIR,
    ensure_track_a_dirs,
    markdown_table,
    rel,
    require_official_production_pin,
    returns_path,
    weights_path,
)
from production_costs import cost_sensitivity_paths
from production_metrics import (
    arithmetic_annual_return,
    cagr,
    max_drawdown,
    metrics_from_path,
    var_cvar,
)


TOL = 1e-12
DOC_REPORT = Path(__file__).resolve().parents[1] / "docs" / "research" / "track_a_production_reproduction_report.md"


def read_dated(path: Path) -> pd.DataFrame:
    """Read a CSV with Date/date/Unnamed index into a Date-indexed frame."""

    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    date_col = "Date" if "Date" in df.columns else "date"
    if date_col not in df.columns:
        raise ValueError(f"{rel(path)} lacks Date/date")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def clean_json(value: Any) -> Any:
    """Convert pandas/numpy values into JSON-safe values."""

    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def max_abs_frame(left: pd.DataFrame, right: pd.DataFrame) -> float:
    """Maximum absolute difference between aligned frames."""

    diff = left - right
    if diff.empty:
        return np.nan
    return float(diff.abs().to_numpy().max())


def old_population_metrics(returns: pd.Series) -> dict[str, float]:
    """Reproduce the older ddof=0 helper convention for comparison only."""

    r = pd.to_numeric(returns, errors="coerce").dropna()
    if r.empty:
        return {}
    ann_return = cagr(r)
    ann_vol = float(r.std(ddof=0) * np.sqrt(52)) if len(r) > 1 else np.nan
    _, cvar_5 = var_cvar(r)
    return {
        "ann_return": ann_return,
        "arithmetic_ann_return": arithmetic_annual_return(r),
        "ann_vol": ann_vol,
        "sharpe": float(ann_return / ann_vol) if np.isfinite(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": max_drawdown(r),
        "cvar_5": cvar_5,
    }


def metric_comparison_rows(saved_path: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """Build old-vs-canonical-vs-registry metric comparison rows."""

    summary = pd.read_csv(SUMMARY_PATH)
    registry_row = summary[summary["name"].astype(str).eq(PRODUCTION_CANDIDATE)].iloc[0].to_dict()
    path_with_date = saved_path.reset_index().rename(columns={saved_path.index.name or "index": "Date"})
    canonical = metrics_from_path(path_with_date, weights=weights)
    holdout = metrics_from_path(path_with_date, weights=weights, start=OFFICIAL_HOLDOUT_START)
    old = old_population_metrics(saved_path["net_return"])
    old_holdout = old_population_metrics(saved_path.loc[saved_path.index >= OFFICIAL_HOLDOUT_START, "net_return"])
    mapping = [
        ("ann_return", "full_ann_return", canonical["ann_return"], old["ann_return"]),
        ("ann_vol", "full_ann_vol", canonical["ann_vol"], old["ann_vol"]),
        ("sharpe", "full_sharpe", canonical["sharpe"], old["sharpe"]),
        ("max_drawdown", "full_max_drawdown", canonical["max_drawdown"], old["max_drawdown"]),
        ("cvar_5", "full_cvar_5", canonical["cvar_5"], old["cvar_5"]),
        ("calmar", "full_calmar", canonical["calmar"], np.nan),
        ("avg_weekly_turnover", "avg_turnover", canonical["avg_weekly_turnover"], registry_row.get("avg_turnover")),
        ("holdout_ann_return", "holdout_ann_return", holdout["ann_return"], old_holdout["ann_return"]),
        ("holdout_ann_vol", "holdout_ann_vol", holdout["ann_vol"], old_holdout["ann_vol"]),
        ("holdout_sharpe", "holdout_sharpe", holdout["sharpe"], old_holdout["sharpe"]),
        ("holdout_max_drawdown", "holdout_max_drawdown", holdout["max_drawdown"], old_holdout["max_drawdown"]),
        ("holdout_cvar_5", "holdout_cvar_5", holdout["cvar_5"], old_holdout["cvar_5"]),
    ]
    rows = []
    for metric, registry_col, canonical_value, legacy_value in mapping:
        registry_value = registry_row.get(registry_col)
        rows.append(
            {
                "metric": metric,
                "canonical": canonical_value,
                "registry_summary": registry_value,
                "legacy_population_vol_formula": legacy_value,
                "canonical_minus_registry": (
                    float(canonical_value) - float(registry_value)
                    if pd.notna(canonical_value) and pd.notna(registry_value)
                    else np.nan
                ),
                "canonical_minus_legacy": (
                    float(canonical_value) - float(legacy_value)
                    if pd.notna(canonical_value) and pd.notna(legacy_value)
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def cost_sensitivity_report(weights: pd.DataFrame, next_week_returns: pd.DataFrame) -> pd.DataFrame:
    """Compute 1x, 2x, and 3x production cost sensitivity."""

    rows = []
    for multiplier, path in cost_sensitivity_paths(weights, next_week_returns).items():
        metrics = metrics_from_path(path, weights=weights)
        rows.append(
            {
                "cost_multiplier": multiplier,
                "cost_bps_per_one_way_turnover": multiplier * 10.0,
                "ann_return": metrics["ann_return"],
                "ann_vol": metrics["ann_vol"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "cvar_5": metrics["cvar_5"],
                "avg_weekly_turnover": metrics["avg_weekly_turnover"],
                "annualized_turnover": metrics["annualized_turnover"],
                "annualized_cost": metrics["annualized_cost"],
                "total_cost": metrics["total_cost"],
            }
        )
    return pd.DataFrame(rows)


def write_markdown_report(payload: dict[str, Any], metric_cmp: pd.DataFrame, sensitivity: pd.DataFrame) -> None:
    """Write a concise markdown reproduction report."""

    status = payload["status"]
    lines = [
        "# Track A Production Reproduction Report",
        "",
        "## Official Candidate",
        "",
        f"- Production candidate: `{PRODUCTION_CANDIDATE}`",
        f"- Registry verified: `{status['registry_verified']}`",
        f"- Pipeline: {production_pipeline_description()}",
        f"- Official holdout start: `{OFFICIAL_HOLDOUT_START.date()}`",
        "",
        "## Exact Reproduction",
        "",
        f"- Weight max absolute error: `{status['weights_max_abs_error']:.3e}`",
        f"- Return/path max absolute error: `{status['path_max_abs_error']:.3e}`",
        f"- Net return correlation: `{status['net_return_corr_vs_saved']:.12f}`",
        f"- Exact reproduction tolerance: `{TOL:.0e}`",
        f"- Reproduction passed: `{status['exact_reproduction_passed']}`",
        "",
        "## Metric Convention Note",
        "",
        "- Canonical Sharpe uses CAGR divided by sample annualized volatility (`ddof=1`).",
        "- Some older helper code used population volatility (`ddof=0`), which slightly raises Sharpe for the same return series.",
        "",
        "## Old vs Canonical Metrics",
        "",
        markdown_table(metric_cmp),
        "",
        "## Cost Sensitivity",
        "",
        markdown_table(sensitivity),
        "",
        "## Artifacts",
        "",
        f"- `{rel(TRACK_A_DIR / 'production_reproduction_report.json')}`",
        f"- `{rel(TRACK_A_DIR / 'production_reproduction_metrics_comparison.csv')}`",
        f"- `{rel(TRACK_A_DIR / 'production_cost_sensitivity.csv')}`",
        f"- `{rel(TRACK_A_DIR / 'production_reproduction_return_diffs.csv')}`",
    ]
    DOC_REPORT.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    ensure_track_a_dirs()
    registry = require_official_production_pin()
    formal = run_production_allocator()
    saved_weights = read_dated(weights_path(PRODUCTION_CANDIDATE)).reindex_like(formal.weights).fillna(0.0)
    saved_path = read_dated(returns_path(PRODUCTION_CANDIDATE))
    path_cols = ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]
    formal_path = formal.path.set_index("Date")[path_cols]
    joined = formal_path.join(saved_path[path_cols], how="inner", rsuffix="_saved")
    path_diffs = {
        col: float((joined[col] - joined[f"{col}_saved"]).abs().max())
        for col in path_cols
    }
    weights_diff = max_abs_frame(formal.weights, saved_weights)
    path_max = max(path_diffs.values())
    corr = float(joined["net_return"].corr(joined["net_return_saved"]))
    exact = bool(weights_diff <= TOL and path_max <= TOL and abs(corr - 1.0) <= TOL)

    metric_cmp = metric_comparison_rows(saved_path, saved_weights)
    wrapper = AllocatorCheckpointWrapper(GGG_BASELINE)
    sensitivity = cost_sensitivity_report(formal.weights, wrapper.next_week_returns)
    return_diffs = pd.DataFrame(
        {
            "Date": joined.index,
            **{f"{col}_diff": joined[col] - joined[f"{col}_saved"] for col in path_cols},
        }
    )

    payload = {
        "production_candidate": PRODUCTION_CANDIDATE,
        "registry": registry,
        "status": {
            "registry_verified": True,
            "weights_max_abs_error": weights_diff,
            "path_max_abs_error": path_max,
            "net_return_corr_vs_saved": corr,
            "exact_reproduction_passed": exact,
            "path_column_max_abs_errors": path_diffs,
            "weeks_compared": int(len(joined)),
        },
        "metric_convention": {
            "ann_return": "CAGR/geometric annual return",
            "ann_vol": "sample annualized weekly volatility, ddof=1",
            "sharpe": "CAGR / sample annualized volatility",
            "var_cvar": "weekly 5% VaR/CVaR on the evaluated return window",
            "turnover": "one-way turnover = 0.5 * L1 weight change",
            "cost": "one-way turnover * bps / 10000",
        },
    }
    (TRACK_A_DIR / "production_reproduction_report.json").write_text(
        json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n"
    )
    metric_cmp.to_csv(TRACK_A_DIR / "production_reproduction_metrics_comparison.csv", index=False)
    sensitivity.to_csv(TRACK_A_DIR / "production_cost_sensitivity.csv", index=False)
    return_diffs.to_csv(TRACK_A_DIR / "production_reproduction_return_diffs.csv", index=False)
    write_markdown_report(payload, metric_cmp, sensitivity)

    if not exact:
        raise SystemExit(f"Production reproduction failed: {payload['status']}")
    print("production reproduction passed")
    print(f"weights_max_abs_error={weights_diff:.3e}")
    print(f"path_max_abs_error={path_max:.3e}")
    print(f"wrote {rel(DOC_REPORT)}")


if __name__ == "__main__":
    main()
