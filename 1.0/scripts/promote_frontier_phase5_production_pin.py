"""Promote improved_frontier_phase5_fragility_guard to the official production pin.

This is a governance/data update only. It does not rebuild portfolio returns,
weights, or allocation logic. It rewrites the registry and compact comparison
CSVs so the new live production pin is explicit while the former production pin
is preserved as rollback/prior production.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "data" / "05_layer3_portfolio_construction"

NEW_PRODUCTION = "improved_frontier_phase5_fragility_guard"
OLD_PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
PRIOR_CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense"

REGISTRY_JSON = PORT / "production_candidate_registry.json"
SUMMARY_CSV = PORT / "production_candidate_summary.csv"
STATE_CSV = PORT / "production_candidate_state_summary.csv"
EXPOSURE_CSV = PORT / "production_candidate_exposure_summary.csv"


def safe_json(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_json(v) for v in value]
    return value


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def require_names(df: pd.DataFrame, column: str, names: list[str], path: Path) -> None:
    available = set(df[column].astype(str))
    missing = [name for name in names if name not in available]
    if missing:
        raise RuntimeError(f"{path.relative_to(ROOT)} missing required {column} values: {missing}")


def role_for(name: str) -> str:
    if name == NEW_PRODUCTION:
        return "current_production"
    if name == OLD_PRODUCTION:
        return "prior_production_pin_and_rollback"
    if name == SHADOW:
        return "official_shadow"
    return "historical_reference"


def recompute_summary(summary: pd.DataFrame) -> pd.DataFrame:
    require_names(summary, "name", [NEW_PRODUCTION, OLD_PRODUCTION, SHADOW], SUMMARY_CSV)
    summary = summary[summary["name"].astype(str).isin([NEW_PRODUCTION, OLD_PRODUCTION, SHADOW])].copy()
    summary["role"] = summary["name"].astype(str).map(role_for)
    prod = summary.set_index("name").loc[NEW_PRODUCTION]
    shadow = summary.set_index("name").loc[SHADOW]
    for col in [
        "full_ann_return",
        "full_sharpe",
        "full_max_drawdown",
        "full_cvar_5",
        "holdout_ann_return",
        "holdout_sharpe",
        "avg_BIL",
        "avg_SPY",
        "avg_turnover",
    ]:
        if col in summary.columns:
            summary[f"{col}_delta_vs_production"] = summary[col] - prod[col]
            summary[f"{col}_delta_vs_official_shadow"] = summary[col] - shadow[col]
    if "avg_turnover" in summary.columns:
        summary["turnover_ratio_vs_production"] = summary["avg_turnover"] / prod["avg_turnover"]
    order = {NEW_PRODUCTION: 0, OLD_PRODUCTION: 1, SHADOW: 2}
    summary["_order"] = summary["name"].map(order)
    return summary.sort_values("_order").drop(columns=["_order"])


def recompute_state(state: pd.DataFrame) -> pd.DataFrame:
    require_names(state, "candidate", [NEW_PRODUCTION, OLD_PRODUCTION, SHADOW], STATE_CSV)
    state = state[state["candidate"].astype(str).isin([NEW_PRODUCTION, OLD_PRODUCTION, SHADOW])].copy()
    state["role"] = state["candidate"].astype(str).map(role_for)
    prod = state[state["candidate"].eq(NEW_PRODUCTION)].set_index("state")
    for col in ["ann_return", "sharpe", "mean_wkly"]:
        if col in state.columns:
            state[f"{col}_delta_vs_production"] = state.apply(
                lambda row: row[col] - prod.loc[row["state"], col] if row["state"] in prod.index else np.nan,
                axis=1,
            )
    order = {NEW_PRODUCTION: 0, OLD_PRODUCTION: 1, SHADOW: 2}
    state["_order"] = state["candidate"].map(order)
    return state.sort_values(["_order", "state"]).drop(columns=["_order"])


def recompute_exposure(exposure: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    require_names(exposure, "name", [NEW_PRODUCTION, OLD_PRODUCTION, SHADOW], EXPOSURE_CSV)
    exposure = exposure[exposure["name"].astype(str).isin([NEW_PRODUCTION, OLD_PRODUCTION, SHADOW])].copy()
    exposure["role"] = exposure["name"].astype(str).map(role_for)
    prod = summary.set_index("name").loc[NEW_PRODUCTION]
    for col in ["avg_BIL", "avg_SPY", "avg_turnover"]:
        if col in exposure.columns:
            exposure[f"{col}_delta_vs_production"] = exposure[col] - prod[col]
    if "avg_turnover" in exposure.columns:
        exposure["turnover_ratio_vs_production"] = exposure["avg_turnover"] / prod["avg_turnover"]
    order = {NEW_PRODUCTION: 0, OLD_PRODUCTION: 1, SHADOW: 2}
    exposure["_order"] = exposure["name"].map(order)
    return exposure.sort_values("_order").drop(columns=["_order"])


def comparison_payload(summary: pd.DataFrame) -> dict[str, Any]:
    idx = summary.set_index("name")
    prod = idx.loc[NEW_PRODUCTION]
    payload: dict[str, Any] = {}
    for label, comp_name in [
        ("vs_prior_production_pin", OLD_PRODUCTION),
        ("vs_official_shadow", SHADOW),
        ("vs_prior_production_candidate", PRIOR_CANDIDATE),
    ]:
        if comp_name not in idx.index:
            if comp_name == PRIOR_CANDIDATE:
                continue
            raise RuntimeError(f"Missing comparator in summary: {comp_name}")
        comp = idx.loc[comp_name]
        payload[label] = {
            "comparator": comp_name,
            "annual_return": {"production": prod["full_ann_return"], "comparator": comp["full_ann_return"], "delta": prod["full_ann_return"] - comp["full_ann_return"]},
            "sharpe": {"production": prod["full_sharpe"], "comparator": comp["full_sharpe"], "delta": prod["full_sharpe"] - comp["full_sharpe"]},
            "max_drawdown": {"production": prod["full_max_drawdown"], "comparator": comp["full_max_drawdown"], "delta": prod["full_max_drawdown"] - comp["full_max_drawdown"]},
            "cvar_5": {"production": prod["full_cvar_5"], "comparator": comp["full_cvar_5"], "delta": prod["full_cvar_5"] - comp["full_cvar_5"]},
            "holdout_sharpe": {"production": prod["holdout_sharpe"], "comparator": comp["holdout_sharpe"], "delta": prod["holdout_sharpe"] - comp["holdout_sharpe"]},
            "avg_BIL": {"production": prod["avg_BIL"], "comparator": comp["avg_BIL"], "delta": prod["avg_BIL"] - comp["avg_BIL"]},
            "avg_SPY": {"production": prod["avg_SPY"], "comparator": comp["avg_SPY"], "delta": prod["avg_SPY"] - comp["avg_SPY"]},
            "avg_turnover": {"production": prod["avg_turnover"], "comparator": comp["avg_turnover"], "delta": prod["avg_turnover"] - comp["avg_turnover"]},
        }
    return payload


def update_registry(summary: pd.DataFrame) -> dict[str, Any]:
    registry = json.loads(REGISTRY_JSON.read_text())
    if registry.get("production_candidate") != NEW_PRODUCTION:
        raise RuntimeError(f"Unexpected production_candidate before promotion: {registry.get('production_candidate')}")
    if registry.get("official_shadow_pin") != SHADOW:
        raise RuntimeError(f"Unexpected official_shadow_pin before promotion: {registry.get('official_shadow_pin')}")
    registry.update(
        {
            "current_production_pin": NEW_PRODUCTION,
            "rollback_pin": OLD_PRODUCTION,
            "prior_production_pin": OLD_PRODUCTION,
            "official_shadow_pin": SHADOW,
            "production_candidate": NEW_PRODUCTION,
            "prior_production_candidate": PRIOR_CANDIDATE,
            "candidate_status": "PROMOTED_TO_PRODUCTION",
            "promotion_phase": "Frontier Phase 10A",
            "promotion_report": "docs/research/frontier_phase10_final_evaluation_report.md",
            "latest_research_status": "PHASE10A_PRODUCTION_PIN_UPDATED_WITH_HUMAN_AUTHORIZATION",
            "dashboard_status_label": "Current production: Frontier Phase5 Fragility Guard",
            "production_label": "Current production",
            "shadow_label": "Official shadow",
            "candidate_label": "Current production: Frontier Phase5 Fragility Guard",
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "do_not_auto_promote": False,
            "rollback_available": True,
            "headline_metric_comparison": comparison_payload(summary),
            "promotion_reason_summary": [
                "Phase 10A verdict PROMOTE",
                "human authorization received for production pin update",
                "named artifact reproduced Phase 10A metrics at machine precision",
                "dashboard exposure and smoke tests passed",
                "higher Sharpe than prior production pin and official shadow",
                "better max drawdown and CVaR than prior production pin",
                "holdout Sharpe improvement versus prior production pin",
                "stressed_panic offense unchanged versus GGG baseline",
            ],
            "known_caveats": [
                "sleeve-weight artifact is a review proxy derived from GGG sleeve weights because the strategy is a wrapper modifier",
                "prior production pin retained as rollback",
                "future research should compare against the new production pin and preserve Phase2B as rollback reference",
            ],
            "next_manual_steps": [
                "Review final production promotion report.",
                "Commit the production-pin update with the suggested commit message.",
                "Deploy/review the dashboard build.",
                "Monitor future research against the new production baseline.",
            ],
        }
    )
    REGISTRY_JSON.write_text(json.dumps(safe_json(registry), indent=2, allow_nan=False) + "\n")
    return registry


def main() -> None:
    summary = recompute_summary(load_csv(SUMMARY_CSV))
    state = recompute_state(load_csv(STATE_CSV))
    exposure = recompute_exposure(load_csv(EXPOSURE_CSV), summary)
    update_registry(summary)
    summary.to_csv(SUMMARY_CSV, index=False)
    state.to_csv(STATE_CSV, index=False)
    exposure.to_csv(EXPOSURE_CSV, index=False)
    print(f"Promoted current_production_pin to {NEW_PRODUCTION}")
    print(f"Recorded prior_production_pin / rollback as {OLD_PRODUCTION}")
    print(f"Official shadow remains {SHADOW}")


if __name__ == "__main__":
    main()
