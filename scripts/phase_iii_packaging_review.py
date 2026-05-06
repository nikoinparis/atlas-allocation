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


def registry() -> dict:
    return {
        "current_production_pin": PRODUCTION,
        "rollback_pin": PRODUCTION,
        "official_shadow_pin": SHADOW,
        "production_candidate": CANDIDATE,
        "candidate_status": "PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW",
        "promotion_phase": "Phase III",
        "promotion_report": REPORT,
        "promotion_reason_summary": [
            "improves annual return",
            "improves Sharpe",
            "improves max drawdown",
            "improves CVaR",
            "improves holdout Sharpe",
            "survives doubled-cost and 1-week delay",
            "passes allocator benchmark",
            "lowers SPY exposure",
            "turnover remains under 1.10x cap",
        ],
        "known_caveats": [
            "committee internal +0.30pp annual-return gate was not met exactly",
            "bootstrap confidence intervals overlap",
            "worst single week is worse than production",
            "human deployment review still required",
        ],
    }


def artifact_status() -> dict[str, bool]:
    names = [CANDIDATE, PRODUCTION, SHADOW]
    status = {}
    for name in names:
        for kind in ["returns", "weights", "sleeve_weights"]:
            path = L3 / f"portfolio_version_{kind}_{name}.csv"
            status[str(path.relative_to(ROOT))] = path.exists() and path.stat().st_size > 0
    for path in [REGISTRY_JSON, SUMMARY_CSV, STATE_CSV, EXPOSURE_CSV, PACKAGING_REPORT]:
        status[str(path.relative_to(ROOT))] = path.exists() and path.stat().st_size > 0
    return status


def write_report(summary: pd.DataFrame, checklist: pd.DataFrame, status: dict[str, bool]) -> None:
    idx = summary.set_index("name")
    cand = idx.loc[CANDIDATE]
    prod = idx.loc[PRODUCTION]
    shadow = idx.loc[SHADOW]
    failed = checklist[~checklist["passed"].astype(bool)]
    recommendation = "READY FOR HUMAN DEPLOYMENT REVIEW" if all(status.values()) and failed.empty else "NEEDS PACKAGING FIX"
    md = f"""# Phase III Packaging / Deployment Review

Date: 2026-04-27

## Commands executed

```
python3 scripts/phase_iii_packaging_review.py
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
- `docs/research/project_journey.md`
- `CLAUDE.md`

## Registry status

GGG1 is registered as `PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW`.
Current production and rollback remain `{PRODUCTION}`. Official shadow remains
`{SHADOW}`.

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

## Caveats

- committee internal +0.30pp annual-return gate was not met exactly
- bootstrap confidence intervals overlap
- worst single week is worse than production
- human deployment review still required

## Final packaging recommendation

**{recommendation}.**

## Exact next manual steps

1. Human reviewer confirms GGG1 deployment acceptance despite the listed caveats.
2. If accepted, update the live production pin in the dashboard/app config in a separate deployment PR.
3. Preserve `{PRODUCTION}` as rollback in the registry and deployment notes.
4. Rebuild the full dashboard payload only after the human deployment decision.
"""
    PACKAGING_REPORT.write_text(md)


def main() -> None:
    summary = metric_rows()
    state = state_rows()
    exposure = exposure_rows(summary)
    checklist = read_csv(PHASE_DIR / "phase_iii_promotion_checklist.csv")

    write_json(REGISTRY_JSON, registry())
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
    summary_payload = {
        "registry": registry(),
        "summary": summary.to_dict(orient="records"),
        "promotion_checklist": checklist.to_dict(orient="records"),
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
        "registry": registry(),
        "summary": summary.to_dict(orient="records"),
        "state_summary": state.to_dict(orient="records"),
        "exposure_summary": exposure.to_dict(orient="records"),
        "promotion_checklist": checklist.to_dict(orient="records"),
        **timeseries_payload,
        **exposure_payload,
    }
    write_json(DASHBOARD_SUMMARY_JSON, summary_payload)
    write_json(DASHBOARD_TIMESERIES_JSON, timeseries_payload)
    write_json(DASHBOARD_STATE_JSON, state_payload)
    write_json(DASHBOARD_EXPOSURES_JSON, exposure_payload)
    write_json(BUNDLE_JSON, bundle)

    status = artifact_status()
    write_report(summary, checklist, status)
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
    print(f"missing_required_artifacts: {missing if missing else 'none'}")
    print("recommendation: READY FOR HUMAN DEPLOYMENT REVIEW" if not missing else "recommendation: NEEDS PACKAGING FIX")


if __name__ == "__main__":
    main()
