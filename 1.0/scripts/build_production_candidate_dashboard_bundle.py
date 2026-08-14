"""Build compact dashboard bundle from current production-candidate artifacts.

This is a data exposure script, not a promotion script. It reads the current
registry and production-candidate comparison CSVs, then regenerates the compact
public dashboard JSON files without changing production or shadow pins.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from production_config import OFFICIAL_SHADOW_PIN, PRODUCTION_CANDIDATE, ROLLBACK_PIN


ROOT = Path(__file__).resolve().parents[1]
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L1 = ROOT / "data" / "02_layer1_signals"
PUBLIC = ROOT / "public"
FRONTIER10 = ROOT / "data" / "research" / "frontier_phase10"

REGISTRY_JSON = L3 / "production_candidate_registry.json"
SUMMARY_CSV = L3 / "production_candidate_summary.csv"
STATE_CSV = L3 / "production_candidate_state_summary.csv"
EXPOSURE_CSV = L3 / "production_candidate_exposure_summary.csv"

BUNDLE_JSON = PUBLIC / "production-candidate-dashboard-bundle.json"
DASHBOARD_SUMMARY_JSON = PUBLIC / "dashboard-summary.json"
DASHBOARD_TIMESERIES_JSON = PUBLIC / "dashboard-timeseries.json"
DASHBOARD_STATE_JSON = PUBLIC / "dashboard-state-summary.json"
DASHBOARD_EXPOSURES_JSON = PUBLIC / "dashboard-exposures.json"

def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def clean_json(value: Any) -> Any:
    if isinstance(value, (bool,)):
        return value
    if isinstance(value, (int, str)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n")


def read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    return pd.read_csv(path)


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    return df.where(pd.notna(df), None).to_dict(orient="records")


def load_registry() -> dict[str, Any]:
    if not REGISTRY_JSON.exists():
        raise FileNotFoundError(REGISTRY_JSON)
    reg = json.loads(REGISTRY_JSON.read_text())
    if reg.get("current_production_pin") != PRODUCTION_CANDIDATE:
        raise RuntimeError(f"Refusing bundle build: current_production_pin is {reg.get('current_production_pin')}")
    rollback = reg.get("prior_production_pin") or reg.get("rollback_pin")
    if rollback != ROLLBACK_PIN:
        raise RuntimeError(f"Refusing bundle build: rollback/prior production pin is {rollback}")
    if reg.get("official_shadow_pin") != OFFICIAL_SHADOW_PIN:
        raise RuntimeError(f"Refusing bundle build: official_shadow_pin is {reg.get('official_shadow_pin')}")
    if reg.get("production_candidate") != PRODUCTION_CANDIDATE:
        raise RuntimeError(f"Refusing bundle build: production_candidate is {reg.get('production_candidate')}")
    return reg


def return_rows(name: str) -> list[dict[str, Any]]:
    path = L3 / f"portfolio_version_returns_{name}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    date_col = "Date" if "Date" in df.columns else "date"
    if date_col not in df.columns:
        raise ValueError(f"{rel(path)} lacks a Date/date column")
    keep = [c for c in [date_col, "gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"] if c in df.columns]
    df = df[keep].rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return records(df.dropna(subset=["date"]))


def latest_weight_payload(name: str, kind: str) -> dict[str, Any]:
    path = L3 / f"portfolio_version_{kind}_{name}.csv"
    if not path.exists():
        return {"latest": [], "history": [], "selectedColumns": []}
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    date_cols = {"Date", "date"}
    value_cols = [c for c in df.columns if c not in date_cols]
    if df.empty or not value_cols:
        return {"latest": [], "history": [], "selectedColumns": []}
    latest = pd.to_numeric(df[value_cols].iloc[-1], errors="coerce").dropna()
    latest_items = (
        latest[latest.abs() > 0.0001]
        .sort_values(key=lambda s: s.abs(), ascending=False)
        .reset_index()
    )
    latest_items.columns = ["name", "weight"]
    return {
        "latest": records(latest_items),
        "history": [],
        "selectedColumns": latest_items["name"].head(12).tolist(),
    }


def compact_records(path: Path, columns: list[str], limit: int | None = None, sort_by: str | None = None, ascending: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    status = {"source_path": rel(path), "exists": path.exists(), "rows": 0, "warning": None}
    if not path.exists():
        status["warning"] = f"{rel(path)} not found"
        return [], status
    df = pd.read_csv(path)
    status["rows"] = int(len(df))
    available = [col for col in columns if col in df.columns]
    missing = [col for col in columns if col not in df.columns]
    if missing:
        status["warning"] = f"missing columns: {', '.join(missing)}"
    if not available:
        return [], status
    df = df[available].copy()
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)
    if limit:
        df = df.head(limit)
    return records(df), status


def redundancy_payload(path: Path, limit: int = 22) -> tuple[dict[str, Any], dict[str, Any]]:
    status = {"source_path": rel(path), "exists": path.exists(), "rows": 0, "warning": None}
    if not path.exists():
        status["warning"] = f"{rel(path)} not found"
        return {"signals": [], "rowLabels": [], "values": []}, status
    raw = pd.read_csv(path)
    status["rows"] = int(len(raw))
    if raw.empty:
        return {"signals": [], "rowLabels": [], "values": []}, status
    label_col = raw.columns[0]
    labels = raw[label_col].astype(str).head(limit).tolist()
    matrix = raw.set_index(label_col)
    cols = [col for col in matrix.columns if col in labels][:limit]
    values = matrix.loc[labels, cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return {"signals": cols, "rowLabels": labels, "values": values.values.tolist()}, status


def layer1_payload() -> dict[str, Any]:
    validation_cols = [
        "signal_name",
        "recommendation",
        "avg_mean_ic",
        "avg_ic_tstat_nw",
        "avg_cross_coverage",
        "avg_abs_redundancy",
        "distinctiveness_score",
        "validation_quality_score",
        "net_sharpe_10bps",
    ]
    incremental_cols = [
        "study",
        "test_type",
        "candidate_signal",
        "signal_count",
        "signal_names",
        "ann_return",
        "ann_vol",
        "sharpe",
        "max_drawdown",
        "calmar",
        "cvar_5",
        "avg_weekly_turnover",
        "avg_bil_weight",
        "avg_spy_weight",
        "delta_ann_return_vs_base",
        "delta_sharpe_vs_base",
        "delta_max_drawdown_vs_base",
        "delta_cvar_5_vs_base",
        "delta_turnover_vs_base",
    ]
    subset_cols = ["combo_name", "signal_count", "signal_names", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_weekly_turnover", "avg_bil_weight", "avg_spy_weight"]
    ic_cols = ["signal_name", "evaluation_type", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "mean_coverage", "n_dates"]
    validation, validation_status = compact_records(L1 / "signal_summary_table.csv", validation_cols, limit=50, sort_by="validation_quality_score", ascending=False)
    quality = sorted(validation, key=lambda row: row.get("validation_quality_score") or -999, reverse=True)[:25]
    incremental, incremental_status = compact_records(L1 / "signal_incremental_contribution.csv", incremental_cols, limit=50)
    subsets, subset_status = compact_records(L1 / "signal_subset_comparison.csv", subset_cols, limit=25, sort_by="sharpe", ascending=False)
    ic_decay, ic_status = compact_records(L1 / "signal_ic_by_horizon.csv", ic_cols, limit=250)
    redundancy, redundancy_status = redundancy_payload(L1 / "signal_redundancy_matrix.csv")
    statuses = [validation_status, incremental_status, subset_status, ic_status, redundancy_status]
    return {
        "layer1_signal_validation_summary": validation,
        "layer1_signal_quality_ranking": quality,
        "layer1_incremental_signal_contribution": incremental,
        "layer1_signal_subset_comparison": subsets,
        "layer1_ic_decay_by_horizon": ic_decay,
        "layer1_signal_redundancy_matrix": redundancy,
        "layer1_data_status": {
            "source_paths_used": [item["source_path"] for item in statuses],
            "row_counts": {
                "layer1_signal_validation_summary": len(validation),
                "layer1_signal_quality_ranking": len(quality),
                "layer1_incremental_signal_contribution": len(incremental),
                "layer1_signal_subset_comparison": len(subsets),
                "layer1_ic_decay_by_horizon": len(ic_decay),
                "layer1_signal_redundancy_matrix": len(redundancy.get("values", [])),
            },
            "missing_source_warnings": [item["warning"] for item in statuses if item.get("warning")],
        },
    }


def phase10_checklist() -> list[dict[str, Any]]:
    gates = read_csv(FRONTIER10 / "final_candidate_phase_d_gates.csv", required=False)
    if gates.empty:
        return []
    out = gates.rename(columns={"comparison": "check", "ok": "passed_detail", "fail": "failed_detail"}).copy()
    out["passed"] = out["verdict"].astype(str).str.upper().eq("PASS")
    return records(out)


def main() -> None:
    reg = load_registry()
    summary = read_csv(SUMMARY_CSV)
    state = read_csv(STATE_CSV)
    exposure = read_csv(EXPOSURE_CSV)
    names = list(dict.fromkeys(summary["name"].astype(str).tolist()))

    missing_names = [name for name in names if name not in set(summary["name"].astype(str))]
    if missing_names:
        raise RuntimeError(f"Summary missing dashboard versions: {missing_names}")

    timeseries_payload = {"versionReturns": {name: return_rows(name) for name in names}}
    exposure_payload = {
        "exposure_summary": records(exposure),
        "versionWeights": {name: latest_weight_payload(name, "weights") for name in names},
        "versionSleeveWeights": {name: latest_weight_payload(name, "sleeve_weights") for name in names},
    }
    layer1 = layer1_payload()
    checklist = phase10_checklist()
    summary_payload = {
        "registry": reg,
        "summary": records(summary),
        "promotion_checklist": checklist,
        "layer1_signal_validation_summary": layer1["layer1_signal_validation_summary"],
        "layer1_signal_quality_ranking": layer1["layer1_signal_quality_ranking"],
        "layer1_data_status": layer1["layer1_data_status"],
        "files": {
            "timeseries": "/dashboard-timeseries.json",
            "state_summary": "/dashboard-state-summary.json",
            "exposures": "/dashboard-exposures.json",
        },
    }
    state_payload = {"state_summary": records(state)}
    bundle = {
        "registry": reg,
        "summary": records(summary),
        "state_summary": records(state),
        "exposure_summary": records(exposure),
        "promotion_checklist": checklist,
        **layer1,
        **timeseries_payload,
        **exposure_payload,
    }
    write_json(DASHBOARD_SUMMARY_JSON, summary_payload)
    write_json(DASHBOARD_TIMESERIES_JSON, timeseries_payload)
    write_json(DASHBOARD_STATE_JSON, state_payload)
    write_json(DASHBOARD_EXPOSURES_JSON, exposure_payload)
    write_json(BUNDLE_JSON, bundle)

    print("Production-candidate compact dashboard bundle")
    print(f"candidate: {reg['production_candidate']}")
    print(f"current_production_pin: {reg['current_production_pin']}")
    print(f"official_shadow_pin: {reg['official_shadow_pin']}")
    print(f"summary_rows: {len(summary)}")
    print(f"state_rows: {len(state)}")
    print(f"returns_versions: {len(timeseries_payload['versionReturns'])}")
    for path in [BUNDLE_JSON, DASHBOARD_SUMMARY_JSON, DASHBOARD_TIMESERIES_JSON, DASHBOARD_STATE_JSON, DASHBOARD_EXPOSURES_JSON]:
        print(f"wrote: {rel(path)} bytes={path.stat().st_size}")


if __name__ == "__main__":
    main()
