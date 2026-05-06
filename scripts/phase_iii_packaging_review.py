"""Phase III packaging / deployment review for GGG1.

No strategy research or rebuilds. This script records deployment status,
creates dashboard/export summaries, and validates that rollback artifacts remain
available.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L1 = ROOT / "data" / "02_layer1_signals"
PHASE_DIR = ROOT / "data" / "research" / "phase_iii_production_candidate_review"
PUBLIC = ROOT / "public"
DOCS = ROOT / "docs" / "research"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense"
REPORT = "docs/research/2026-04-27_phase_iii_production_candidate_review_report.md"

SUMMARY_CSV = L3 / "production_candidate_summary.csv"
STATE_CSV = L3 / "production_candidate_state_summary.csv"
EXPOSURE_CSV = L3 / "production_candidate_exposure_summary.csv"
REGISTRY_JSON = L3 / "production_candidate_registry.json"
BUNDLE_JSON = PUBLIC / "production-candidate-dashboard-bundle.json"
DASHBOARD_SUMMARY_JSON = PUBLIC / "dashboard-summary.json"
DASHBOARD_TIMESERIES_JSON = PUBLIC / "dashboard-timeseries.json"
DASHBOARD_STATE_JSON = PUBLIC / "dashboard-state-summary.json"
DASHBOARD_EXPOSURES_JSON = PUBLIC / "dashboard-exposures.json"
PACKAGING_REPORT = DOCS / "2026-04-27_phase_iii_packaging_deployment_review.md"
GGG1_PACKAGING_REPORT = DOCS / "2026-04-27_ggg1_production_candidate_packaging_review.md"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def clean_json(value):
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    return value


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(clean_json(payload), indent=2, allow_nan=False) + "\n")


def metric_rows() -> pd.DataFrame:
    metrics = read_csv(PHASE_DIR / "phase_iii_final_metric_comparison.csv")
    full = metrics[metrics["window"].eq("full_window")].copy()
    keep = [CANDIDATE, PRODUCTION, SHADOW]
    full = full[full["name"].isin(keep)].copy()
    role = {
        CANDIDATE: "production_candidate_pending_human_review",
        PRODUCTION: "current_production_and_rollback",
        SHADOW: "official_shadow",
    }
    full.insert(0, "role", full["name"].map(role))

    prod = full.set_index("name").loc[PRODUCTION]
    shadow = full.set_index("name").loc[SHADOW]
    for col in ["full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "holdout_ann_return", "holdout_sharpe", "avg_BIL", "avg_SPY", "avg_turnover"]:
        full[f"{col}_delta_vs_production"] = full[col] - prod[col]
        full[f"{col}_delta_vs_official_shadow"] = full[col] - shadow[col]
    full["turnover_ratio_vs_production"] = full["avg_turnover"] / prod["avg_turnover"]
    return full


def state_rows() -> pd.DataFrame:
    state = read_csv(PHASE_DIR / "phase_iii_state_by_state_comparison.csv")
    keep = [CANDIDATE, PRODUCTION, SHADOW]
    state = state[state["candidate"].isin(keep)].copy()
    role = {
        CANDIDATE: "production_candidate_pending_human_review",
        PRODUCTION: "current_production_and_rollback",
        SHADOW: "official_shadow",
    }
    state.insert(0, "role", state["candidate"].map(role))
    prod = state[state["candidate"].eq(PRODUCTION)].set_index("state")
    for col in ["ann_return", "sharpe", "mean_wkly"]:
        state[f"{col}_delta_vs_production"] = state.apply(
            lambda r: r[col] - prod.loc[r["state"], col] if r["state"] in prod.index else float("nan"),
            axis=1,
        )
    return state


def exposure_rows(summary: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "role",
        "name",
        "avg_BIL",
        "avg_SPY",
        "avg_turnover",
        "turnover_ratio_vs_production",
        "max_single_etf_weight",
        "avg_BIL_delta_vs_production",
        "avg_SPY_delta_vs_production",
        "avg_turnover_delta_vs_production",
    ]
    return summary[cols].copy()


def downsample_returns(name: str, step: int = 4) -> list[dict]:
    path = L3 / f"portfolio_version_returns_{name}.csv"
    df = pd.read_csv(path, index_col=0).reset_index(names="date")
    keep = (df.index % step == 0) | (df.index == len(df) - 1)
    df = df.loc[keep, ["date", "gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]].copy()
    df.insert(1, "method", name)
    return df.where(pd.notna(df), None).to_dict(orient="records")


def latest_weight_payload(name: str, kind: str) -> dict:
    path = L3 / f"portfolio_version_{kind}_{name}.csv"
    df = pd.read_csv(path, index_col=0)
    latest = df.iloc[-1].dropna()
    latest_items = (
        latest[latest.abs() > 0.0001]
        .sort_values(key=lambda s: s.abs(), ascending=False)
        .reset_index()
    )
    latest_items.columns = ["name", "weight"]
    return {
        "latest": latest_items.to_dict(orient="records"),
        "history": [],
        "selectedColumns": latest_items["name"].head(12).tolist(),
    }


def compact_records(path: Path, columns: list[str], limit: int | None = None, sort_by: str | None = None, ascending: bool = False) -> tuple[list[dict], dict]:
    status = {"source_path": str(path.relative_to(ROOT)), "exists": path.exists(), "rows": 0, "warning": None}
    if not path.exists():
        status["warning"] = f"{path.relative_to(ROOT)} not found"
        return [], status
    df = pd.read_csv(path)
    status["rows"] = int(len(df))
    available = [col for col in columns if col in df.columns]
    missing = [col for col in columns if col not in df.columns]
    if missing:
        status["warning"] = f"missing columns: {', '.join(missing)}"
    df = df[available].copy()
    if sort_by and sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=ascending)
    if limit:
        df = df.head(limit)
    return df.where(pd.notna(df), None).to_dict(orient="records"), status


def redundancy_payload(path: Path, limit: int = 22) -> tuple[dict, dict]:
    status = {"source_path": str(path.relative_to(ROOT)), "exists": path.exists(), "rows": 0, "warning": None}
    if not path.exists():
        status["warning"] = f"{path.relative_to(ROOT)} not found"
        return {"signals": [], "rowLabels": [], "values": []}, status
    raw = pd.read_csv(path)
    status["rows"] = int(len(raw))
    if raw.empty:
        status["warning"] = "source file is empty"
        return {"signals": [], "rowLabels": [], "values": []}, status
    label_col = raw.columns[0]
    labels = raw[label_col].astype(str).head(limit).tolist()
    matrix = raw.set_index(label_col)
    cols = [col for col in matrix.columns if col in labels][:limit]
    values = matrix.loc[labels, cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return {"signals": cols, "rowLabels": labels, "values": values.values.tolist()}, status


def layer1_payload() -> dict:
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
    subset_cols = [
        "combo_name",
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
    ]
    ic_cols = [
        "signal_name",
        "evaluation_type",
        "horizon_weeks",
        "mean_ic",
        "ic_tstat_nw",
        "hit_rate",
        "mean_coverage",
        "n_dates",
    ]

    validation, validation_status = compact_records(
        L1 / "signal_summary_table.csv",
        validation_cols,
        limit=50,
        sort_by="validation_quality_score",
        ascending=False,
    )
    quality = sorted(validation, key=lambda row: row.get("validation_quality_score") or -999, reverse=True)[:25]
    incremental, incremental_status = compact_records(L1 / "signal_incremental_contribution.csv", incremental_cols, limit=50)
    subsets, subset_status = compact_records(L1 / "signal_subset_comparison.csv", subset_cols, limit=25, sort_by="sharpe", ascending=False)
    ic_decay, ic_status = compact_records(L1 / "signal_ic_by_horizon.csv", ic_cols, limit=250)
    redundancy, redundancy_status = redundancy_payload(L1 / "signal_redundancy_matrix.csv")
    status = {
        "source_paths_used": [
            validation_status["source_path"],
            incremental_status["source_path"],
            subset_status["source_path"],
            ic_status["source_path"],
            redundancy_status["source_path"],
        ],
        "row_counts": {
            "layer1_signal_validation_summary": len(validation),
            "layer1_signal_quality_ranking": len(quality),
            "layer1_incremental_signal_contribution": len(incremental),
            "layer1_signal_subset_comparison": len(subsets),
            "layer1_ic_decay_by_horizon": len(ic_decay),
            "layer1_signal_redundancy_matrix": len(redundancy.get("values", [])),
        },
        "missing_source_warnings": [
            item["warning"]
            for item in [validation_status, incremental_status, subset_status, ic_status, redundancy_status]
            if item.get("warning")
        ],
    }
    return {
        "layer1_signal_validation_summary": validation,
        "layer1_signal_quality_ranking": quality,
        "layer1_incremental_signal_contribution": incremental,
        "layer1_signal_subset_comparison": subsets,
        "layer1_ic_decay_by_horizon": ic_decay,
        "layer1_signal_redundancy_matrix": redundancy,
        "layer1_data_status": status,
    }


def registry(summary: pd.DataFrame | None = None) -> dict:
    metric_comparison = {}
    if summary is not None and not summary.empty:
        idx = summary.set_index("name")
        cand = idx.loc[CANDIDATE]
        for label, comparator_name in [
            ("vs_old_production", PRODUCTION),
            ("vs_official_shadow", SHADOW),
        ]:
            comp = idx.loc[comparator_name]
            metric_comparison[label] = {
                "comparator": comparator_name,
                "annual_return": {"candidate": cand["full_ann_return"], "comparator": comp["full_ann_return"], "delta": cand["full_ann_return"] - comp["full_ann_return"]},
                "sharpe": {"candidate": cand["full_sharpe"], "comparator": comp["full_sharpe"], "delta": cand["full_sharpe"] - comp["full_sharpe"]},
                "max_drawdown": {"candidate": cand["full_max_drawdown"], "comparator": comp["full_max_drawdown"], "delta": cand["full_max_drawdown"] - comp["full_max_drawdown"]},
                "cvar_5": {"candidate": cand["full_cvar_5"], "comparator": comp["full_cvar_5"], "delta": cand["full_cvar_5"] - comp["full_cvar_5"]},
                "holdout_sharpe": {"candidate": cand["holdout_sharpe"], "comparator": comp["holdout_sharpe"], "delta": cand["holdout_sharpe"] - comp["holdout_sharpe"]},
                "avg_BIL": {"candidate": cand["avg_BIL"], "comparator": comp["avg_BIL"], "delta": cand["avg_BIL"] - comp["avg_BIL"]},
                "avg_SPY": {"candidate": cand["avg_SPY"], "comparator": comp["avg_SPY"], "delta": cand["avg_SPY"] - comp["avg_SPY"]},
            }
    return {
        "current_production_pin": PRODUCTION,
        "rollback_pin": PRODUCTION,
        "official_shadow_pin": SHADOW,
        "production_candidate": CANDIDATE,
        "candidate_status": "PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW",
        "promotion_phase": "Phase III",
        "promotion_report": REPORT,
        "latest_research_status": "KEEP_GGG1_AS_PRODUCTION_CANDIDATE_AFTER_JJJ4_KKK_LLL_MMM",
        "do_not_auto_promote": True,
        "rollback_available": True,
        "dashboard_status_label": "Production candidate: GGG1",
        "production_label": "Current production / rollback",
        "shadow_label": "Official shadow",
        "candidate_label": "Production candidate: GGG1",
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "headline_metric_comparison": metric_comparison,
        "promotion_reason_summary": [
            "higher annual return",
            "higher Sharpe",
            "better max drawdown",
            "better CVaR",
            "better holdout Sharpe",
            "survives doubled-cost and 1-week delay",
            "passes allocator benchmark",
            "lower SPY exposure",
            "turnover remains under 1.10x cap",
        ],
        "known_caveats": [
            "old committee +0.30pp annual-return gate was not fully met",
            "bootstrap confidence intervals overlap",
            "worst single week is worse than production",
            "turnover is close to the 1.10x limit",
            "human deployment review still required",
        ],
        "next_manual_steps": [
            "Verify Vercel dashboard loads the compact bundle.",
            "Verify old production rollback files exist.",
            "Verify GGG1 return, ETF weight, and sleeve weight files exist.",
            "Review caveats before officially flipping the live production pin.",
            "After human approval, update current_production_pin to GGG1 in a separate commit.",
        ],
    }


def artifact_status() -> dict[str, bool]:
    names = [CANDIDATE, PRODUCTION, SHADOW]
    status = {}
    for name in names:
        for kind in ["returns", "weights", "sleeve_weights"]:
            path = L3 / f"portfolio_version_{kind}_{name}.csv"
            status[str(path.relative_to(ROOT))] = path.exists() and path.stat().st_size > 0
    for path in [REGISTRY_JSON, SUMMARY_CSV, STATE_CSV, EXPOSURE_CSV, PACKAGING_REPORT, GGG1_PACKAGING_REPORT]:
        status[str(path.relative_to(ROOT))] = path.exists() and path.stat().st_size > 0
    return status


def report_markdown(summary: pd.DataFrame, checklist: pd.DataFrame, status: dict[str, bool], commands: list[str]) -> str:
    idx = summary.set_index("name")
    cand = idx.loc[CANDIDATE]
    prod = idx.loc[PRODUCTION]
    shadow = idx.loc[SHADOW]
    failed = checklist[~checklist["passed"].astype(bool)]
    recommendation = "READY FOR HUMAN DEPLOYMENT REVIEW" if all(status.values()) and failed.empty else "NEEDS PACKAGING FIX"
    command_block = "\n".join(commands)
    md = f"""# Phase III Packaging / Deployment Review

Date: 2026-04-27

## Commands executed

```
{command_block}
```

## Files created / modified

- `scripts/phase_iii_packaging_review.py`
- `data/05_layer3_portfolio_construction/production_candidate_registry.json`
- `data/05_layer3_portfolio_construction/production_candidate_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_state_summary.csv`
- `data/05_layer3_portfolio_construction/production_candidate_exposure_summary.csv`
- `public/production-candidate-dashboard-bundle.json`
- `public/dashboard-summary.json`
- `public/dashboard-timeseries.json`
- `public/dashboard-state-summary.json`
- `public/dashboard-exposures.json`
- `docs/research/2026-04-27_phase_iii_packaging_deployment_review.md`
- `docs/research/2026-04-27_ggg1_production_candidate_packaging_review.md`
- `docs/research/project_journey.md`

## Registry status

GGG1 is registered as `PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW`.
Current production and rollback remain `{PRODUCTION}`. Official shadow remains
`{SHADOW}`.

Latest research status:
`KEEP_GGG1_AS_PRODUCTION_CANDIDATE_AFTER_JJJ4_KKK_LLL_MMM`.

## Dashboard / export bundle status

Created lightweight dashboard/export bundle:

- `production_candidate_summary.csv`
- `production_candidate_state_summary.csv`
- `production_candidate_exposure_summary.csv`
- `public/production-candidate-dashboard-bundle.json`
- `public/dashboard-summary.json`
- `public/dashboard-timeseries.json`
- `public/dashboard-state-summary.json`
- `public/dashboard-exposures.json`

The full dashboard payload was not rebuilt and the old production row was not
removed.

## GGG1 vs production

- annual return: {cand['full_ann_return']*100:.2f}% vs {prod['full_ann_return']*100:.2f}% ({(cand['full_ann_return']-prod['full_ann_return'])*100:+.3f}pp)
- Sharpe: {cand['full_sharpe']:.4f} vs {prod['full_sharpe']:.4f} ({cand['full_sharpe']-prod['full_sharpe']:+.4f})
- max drawdown: {cand['full_max_drawdown']*100:.2f}% vs {prod['full_max_drawdown']*100:.2f}% ({(cand['full_max_drawdown']-prod['full_max_drawdown'])*100:+.2f}pp)
- CVaR-5%: {cand['full_cvar_5']*100:.2f}% vs {prod['full_cvar_5']*100:.2f}% ({(cand['full_cvar_5']-prod['full_cvar_5'])*100:+.2f}pp)
- holdout Sharpe: {cand['holdout_sharpe']:.4f} vs {prod['holdout_sharpe']:.4f} ({cand['holdout_sharpe']-prod['holdout_sharpe']:+.4f})
- avg SPY: {cand['avg_SPY']*100:.2f}% vs {prod['avg_SPY']*100:.2f}% ({(cand['avg_SPY']-prod['avg_SPY'])*100:+.2f}pp)
- turnover ratio: {cand['turnover_ratio_vs_production']:.4f}x

## GGG1 vs official shadow

- annual return delta: {(cand['full_ann_return']-shadow['full_ann_return'])*100:+.3f}pp
- Sharpe delta: {cand['full_sharpe']-shadow['full_sharpe']:+.4f}
- max drawdown delta: {(cand['full_max_drawdown']-shadow['full_max_drawdown'])*100:+.2f}pp
- CVaR-5% delta: {(cand['full_cvar_5']-shadow['full_cvar_5'])*100:+.2f}pp
- holdout Sharpe delta: {cand['holdout_sharpe']-shadow['holdout_sharpe']:+.4f}

## Audit checklist

Phase III promotion checklist: {int(checklist['passed'].astype(bool).sum())}/{len(checklist)} passed.
Research committee remains `KEEP AS SHADOW` due to the internal +0.30pp
annual-return gate. Realism audit passes doubled cost. Allocator benchmark
passes. Robustness simulation point estimates beat production, but bootstrap
intervals overlap.

## Failed post-GGG1 research attempts

- JJJ4 adaptive risk-contribution allocation: failed to clearly improve or
  de-risk GGG1; final decision `KEEP_GGG1_AS_PRODUCTION_CANDIDATE`.
- LLL defense component rebuild: all defense-component rebuild candidates were
  rejected.
- MMM composite selective signals rebuild: all CSS rebuild candidates were
  rejected or failed turnover/quality gates.

## Caveats

- committee internal +0.30pp annual-return gate was not met exactly
- bootstrap confidence intervals overlap
- worst single week is worse than production
- turnover is close to the 1.10x limit
- human deployment review still required

## Final packaging recommendation

**{recommendation}.**

## Manual deployment checklist

1. Verify Vercel dashboard loads.
2. Verify compact bundle loads.
3. Verify old production rollback files exist.
4. Verify GGG1 return/weight/sleeve files exist.
5. Verify registry is correct.
6. Verify no giant `dashboard-data.json` is tracked.
7. Review caveats before officially flipping production pin.
8. After human approval, optionally update `current_production_pin` to GGG1 in a separate commit.
"""
    return md


def write_report(summary: pd.DataFrame, checklist: pd.DataFrame, status: dict[str, bool], commands: list[str]) -> None:
    md = report_markdown(summary, checklist, status, commands)
    PACKAGING_REPORT.write_text(md)
    GGG1_PACKAGING_REPORT.write_text(md.replace("Phase III Packaging / Deployment Review", "GGG1 Production Candidate Packaging Review"))


def main() -> None:
    summary = metric_rows()
    state = state_rows()
    exposure = exposure_rows(summary)
    checklist = read_csv(PHASE_DIR / "phase_iii_promotion_checklist.csv")

    reg = registry(summary)
    write_json(REGISTRY_JSON, reg)
    summary.to_csv(SUMMARY_CSV, index=False)
    state.to_csv(STATE_CSV, index=False)
    exposure.to_csv(EXPOSURE_CSV, index=False)

    names = [CANDIDATE, PRODUCTION, SHADOW]
    timeseries_payload = {
        "versionReturns": {name: downsample_returns(name) for name in names},
    }
    exposure_payload = {
        "exposure_summary": exposure.to_dict(orient="records"),
        "versionWeights": {name: latest_weight_payload(name, "weights") for name in names},
        "versionSleeveWeights": {name: latest_weight_payload(name, "sleeve_weights") for name in names},
    }
    layer1 = layer1_payload()
    summary_payload = {
        "registry": reg,
        "summary": summary.to_dict(orient="records"),
        "promotion_checklist": checklist.to_dict(orient="records"),
        "layer1_signal_validation_summary": layer1["layer1_signal_validation_summary"],
        "layer1_signal_quality_ranking": layer1["layer1_signal_quality_ranking"],
        "layer1_data_status": layer1["layer1_data_status"],
        "files": {
            "timeseries": "/dashboard-timeseries.json",
            "state_summary": "/dashboard-state-summary.json",
            "exposures": "/dashboard-exposures.json",
        },
    }
    state_payload = {
        "state_summary": state.to_dict(orient="records"),
    }
    bundle = {
        "registry": reg,
        "summary": summary.to_dict(orient="records"),
        "state_summary": state.to_dict(orient="records"),
        "exposure_summary": exposure.to_dict(orient="records"),
        "promotion_checklist": checklist.to_dict(orient="records"),
        **layer1,
        **timeseries_payload,
        **exposure_payload,
    }
    write_json(DASHBOARD_SUMMARY_JSON, summary_payload)
    write_json(DASHBOARD_TIMESERIES_JSON, timeseries_payload)
    write_json(DASHBOARD_STATE_JSON, state_payload)
    write_json(DASHBOARD_EXPOSURES_JSON, exposure_payload)
    write_json(BUNDLE_JSON, bundle)

    status = artifact_status()
    status_for_report = dict(status)
    for path in [PACKAGING_REPORT, GGG1_PACKAGING_REPORT]:
        status_for_report[str(path.relative_to(ROOT))] = True
    write_report(summary, checklist, status_for_report, ["python3 scripts/phase_iii_packaging_review.py"])
    status = artifact_status()
    missing = [path for path, ok in status.items() if not ok]
    print("Phase III packaging review")
    print(f"registry: {REGISTRY_JSON.relative_to(ROOT)}")
    print(f"summary_csv: {SUMMARY_CSV.relative_to(ROOT)}")
    print(f"state_csv: {STATE_CSV.relative_to(ROOT)}")
    print(f"exposure_csv: {EXPOSURE_CSV.relative_to(ROOT)}")
    print(f"dashboard_bundle: {BUNDLE_JSON.relative_to(ROOT)}")
    print(f"dashboard_summary: {DASHBOARD_SUMMARY_JSON.relative_to(ROOT)}")
    print(f"dashboard_timeseries: {DASHBOARD_TIMESERIES_JSON.relative_to(ROOT)}")
    print(f"dashboard_state: {DASHBOARD_STATE_JSON.relative_to(ROOT)}")
    print(f"dashboard_exposures: {DASHBOARD_EXPOSURES_JSON.relative_to(ROOT)}")
    print(f"report: {PACKAGING_REPORT.relative_to(ROOT)}")
    print(f"ggg1_report: {GGG1_PACKAGING_REPORT.relative_to(ROOT)}")
    print(f"missing_required_artifacts: {missing if missing else 'none'}")
    print("recommendation: READY FOR HUMAN DEPLOYMENT REVIEW" if not missing else "recommendation: NEEDS PACKAGING FIX")


if __name__ == "__main__":
    main()
