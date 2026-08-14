"""Verify Track A dashboard packaging against the production registry."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from production_config import (
    EXPOSURE_SUMMARY_PATH,
    OFFICIAL_SHADOW_PIN,
    PRODUCTION_CANDIDATE,
    PUBLIC_DIR,
    ROLLBACK_PIN,
    STATE_SUMMARY_PATH,
    SUMMARY_PATH,
    TRACK_A_DIR,
    ensure_track_a_dirs,
    markdown_table,
    rel,
    require_official_production_pin,
    returns_path,
    sleeve_weights_path,
    weights_path,
)
from production_metrics import metrics_from_path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = PUBLIC_DIR / "production-candidate-dashboard-bundle.json"
DASHBOARD_SUMMARY = PUBLIC_DIR / "dashboard-summary.json"
DASHBOARD_TIMESERIES = PUBLIC_DIR / "dashboard-timeseries.json"
DASHBOARD_STATE = PUBLIC_DIR / "dashboard-state-summary.json"
DASHBOARD_EXPOSURES = PUBLIC_DIR / "dashboard-exposures.json"
DOC_REPORT = ROOT / "docs" / "research" / "track_a_dashboard_packaging_verification.md"
TOL = 1e-10


def clean_json(value: Any) -> Any:
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
    return value


def read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=["Date"]).sort_values("Date")


def check(condition: bool, name: str, detail: str, hard: bool = True) -> dict[str, Any]:
    return {"check": name, "status": "PASS" if condition else "FAIL", "hard": hard, "detail": detail}


def active_dashboard_data_references() -> list[str]:
    """Return active stale references to the old monolithic dashboard-data file."""

    offenders: list[str] = []
    files = [ROOT / "package.json", ROOT / "README.md", *sorted((ROOT / "src").rglob("*"))]
    for path in files:
        if path.is_dir() or path.suffix not in {"", ".json", ".md", ".ts", ".tsx", ".js", ".jsx"}:
            continue
        try:
            text = path.read_text(errors="ignore")
        except UnicodeDecodeError:
            continue
        if "dashboard-data.json" in text:
            offenders.append(rel(path))
    return offenders


def main() -> None:
    ensure_track_a_dirs()
    registry = require_official_production_pin()
    required = [
        SUMMARY_PATH,
        STATE_SUMMARY_PATH,
        EXPOSURE_SUMMARY_PATH,
        returns_path(PRODUCTION_CANDIDATE),
        weights_path(PRODUCTION_CANDIDATE),
        sleeve_weights_path(PRODUCTION_CANDIDATE),
        BUNDLE,
        DASHBOARD_SUMMARY,
        DASHBOARD_TIMESERIES,
        DASHBOARD_STATE,
        DASHBOARD_EXPOSURES,
    ]
    rows: list[dict[str, Any]] = []
    for path in required:
        rows.append(check(path.exists(), f"exists:{rel(path)}", f"path={rel(path)}"))

    if BUNDLE.exists():
        bundle = json.loads(BUNDLE.read_text())
        rows.append(
            check(
                bundle.get("registry", {}).get("current_production_pin") == PRODUCTION_CANDIDATE,
                "bundle_registry_current_pin",
                f"bundle={bundle.get('registry', {}).get('current_production_pin')}",
            )
        )
        rows.append(
            check(
                bundle.get("registry", {}).get("production_candidate") == registry.get("production_candidate"),
                "bundle_candidate_matches_registry",
                f"bundle={bundle.get('registry', {}).get('production_candidate')}, registry={registry.get('production_candidate')}",
            )
        )
        summary_names = {str(row.get("name")) for row in bundle.get("summary", [])}
        rows.append(
            check(
                {PRODUCTION_CANDIDATE, ROLLBACK_PIN, OFFICIAL_SHADOW_PIN}.issubset(summary_names),
                "bundle_required_versions",
                f"versions={sorted(summary_names)}",
            )
        )

    if all(path.exists() for path in [BUNDLE, SUMMARY_PATH, STATE_SUMMARY_PATH, EXPOSURE_SUMMARY_PATH, returns_path(PRODUCTION_CANDIDATE)]):
        source_mtime = max(
            path.stat().st_mtime
            for path in [
                SUMMARY_PATH,
                STATE_SUMMARY_PATH,
                EXPOSURE_SUMMARY_PATH,
                returns_path(PRODUCTION_CANDIDATE),
                weights_path(PRODUCTION_CANDIDATE),
                sleeve_weights_path(PRODUCTION_CANDIDATE),
            ]
            if path.exists()
        )
        bundle_mtime = min(path.stat().st_mtime for path in [BUNDLE, DASHBOARD_SUMMARY, DASHBOARD_TIMESERIES, DASHBOARD_STATE, DASHBOARD_EXPOSURES])
        rows.append(
            check(
                bundle_mtime >= source_mtime,
                "dashboard_bundle_fresh",
                f"oldest_bundle_mtime={bundle_mtime}, newest_source_mtime={source_mtime}",
            )
        )

    if SUMMARY_PATH.exists() and returns_path(PRODUCTION_CANDIDATE).exists():
        summary = pd.read_csv(SUMMARY_PATH)
        prod = summary[summary["name"].astype(str).eq(PRODUCTION_CANDIDATE)]
        returns = read_dated(returns_path(PRODUCTION_CANDIDATE))
        metrics = metrics_from_path(returns)
        if prod.empty:
            rows.append(check(False, "summary_has_production_row", f"missing {PRODUCTION_CANDIDATE}"))
        else:
            prod_row = prod.iloc[0]
            metric_map = {
                "full_ann_return": "ann_return",
                "full_ann_vol": "ann_vol",
                "full_sharpe": "sharpe",
                "full_max_drawdown": "max_drawdown",
                "full_cvar_5": "cvar_5",
            }
            max_diff = max(abs(float(prod_row[src]) - float(metrics[dst])) for src, dst in metric_map.items())
            rows.append(
                check(
                    max_diff <= TOL,
                    "summary_metrics_match_canonical",
                    f"max_diff={max_diff:.3e}",
                )
            )

    offenders = active_dashboard_data_references()
    rows.append(
        check(
            not offenders,
            "no_active_dashboard_data_json_dependency",
            "offenders=" + ", ".join(offenders) if offenders else "none",
        )
    )

    result = pd.DataFrame(rows)
    result.to_csv(TRACK_A_DIR / "dashboard_packaging_verification.csv", index=False)
    payload = {
        "production_candidate": PRODUCTION_CANDIDATE,
        "checks": result.to_dict(orient="records"),
        "passed": bool(result[result["hard"].eq(True)]["status"].eq("PASS").all()),
    }
    (TRACK_A_DIR / "dashboard_packaging_verification.json").write_text(
        json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n"
    )
    lines = [
        "# Track A Dashboard Packaging Verification",
        "",
        f"- Production candidate: `{PRODUCTION_CANDIDATE}`",
        f"- Passed hard checks: `{payload['passed']}`",
        "",
        markdown_table(result),
        "",
        "## Outputs",
        "",
        f"- `{rel(TRACK_A_DIR / 'dashboard_packaging_verification.csv')}`",
        f"- `{rel(TRACK_A_DIR / 'dashboard_packaging_verification.json')}`",
    ]
    DOC_REPORT.write_text("\n".join(lines).rstrip() + "\n")
    if not payload["passed"]:
        raise SystemExit(f"Dashboard packaging verification failed: {result[result['status'].eq('FAIL')].to_dict(orient='records')}")
    print("dashboard packaging verification passed")
    print(f"wrote {rel(DOC_REPORT)}")


if __name__ == "__main__":
    main()
