"""Generate Track A validation-governance reports.

This script is read-only with respect to production artifacts.  It creates a
snapshot that makes candidate status, trial-count warnings, statistical audit
signals, and promotion gates explicit for the current production pin.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from production_config import (
    GGG_BASELINE,
    OFFICIAL_HOLDOUT_START,
    OFFICIAL_SHADOW_PIN,
    PRODUCTION_CANDIDATE,
    ROLLBACK_PIN,
    SUMMARY_PATH,
    TRACK_A_DIR,
    ensure_track_a_dirs,
    markdown_table,
    rel,
    require_official_production_pin,
    returns_path,
)
from production_metrics import holdout_metrics_from_path, metrics_from_path
from statistical_validation_layer import (
    deflated_sharpe_ratio_proxy,
    multiple_testing_adjusted_support,
    probabilistic_sharpe_ratio,
)


ROOT = Path(__file__).resolve().parents[1]
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
STAT_AUDIT = ROOT / "data" / "research" / "validation" / "statistical_validation_audit.csv"
PHASE10_GATES = ROOT / "data" / "research" / "frontier_phase10" / "final_candidate_phase_d_gates.csv"
PHASE10_BOOTSTRAP = ROOT / "data" / "research" / "frontier_phase10" / "final_candidate_bootstrap_summary.csv"
REPRO_JSON = TRACK_A_DIR / "production_reproduction_report.json"
COST_SENSITIVITY = TRACK_A_DIR / "production_cost_sensitivity.csv"
DOC_REPORT = ROOT / "docs" / "research" / "track_a_validation_governance_report.md"


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


def read_returns(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=["Date"]).sort_values("Date")


def load_stat_audit() -> pd.DataFrame:
    if not STAT_AUDIT.exists():
        return pd.DataFrame()
    return pd.read_csv(STAT_AUDIT)


def artifact_class(candidate: str, source_file: str, validation_verdict: str) -> str:
    """Classify saved artifacts for promotion governance."""

    if candidate == PRODUCTION_CANDIDATE:
        return "production"
    if candidate == OFFICIAL_SHADOW_PIN:
        return "shadow"
    if candidate in {ROLLBACK_PIN, GGG_BASELINE}:
        return "research-only"
    if candidate.startswith("baseline_") or "diagnostic" in candidate or "/ml_lab/" in source_file:
        return "diagnostic-only"
    if validation_verdict == "overfit_risk":
        return "rejected"
    return "research-only"


def experiment_registry_snapshot(stat: pd.DataFrame) -> pd.DataFrame:
    """Build an explicit candidate registry snapshot from saved returns."""

    generated_at = datetime.now(timezone.utc).isoformat()
    rows = []
    audit_by_candidate = stat.set_index("candidate").to_dict("index") if not stat.empty and "candidate" in stat.columns else {}
    for path in sorted(L3.glob("portfolio_version_returns_*.csv")):
        candidate = path.stem.replace("portfolio_version_returns_", "")
        audit = audit_by_candidate.get(candidate, {})
        source_file = str(path.relative_to(ROOT))
        validation_verdict = str(audit.get("validation_verdict", "not_scanned"))
        cls = artifact_class(candidate, source_file, validation_verdict)
        rows.append(
            {
                "candidate": candidate,
                "generated_at": generated_at,
                "source_file": source_file,
                "parameters": "unknown_from_saved_artifact",
                "parent_candidate": "unknown_from_saved_artifact",
                "artifact_class": cls,
                "promotion_status": {
                    PRODUCTION_CANDIDATE: "current_production",
                    OFFICIAL_SHADOW_PIN: "official_shadow",
                    ROLLBACK_PIN: "rollback_reference",
                    GGG_BASELINE: "wrapper_base_reference",
                }.get(candidate, "not_promoted"),
                "annual_return": audit.get("annual_return", np.nan),
                "annual_vol": audit.get("annual_vol", np.nan),
                "sharpe": audit.get("sharpe", np.nan),
                "max_drawdown": audit.get("max_drawdown", np.nan),
                "cvar_5": audit.get("cvar_5", np.nan),
                "avg_turnover": audit.get("avg_turnover", np.nan),
                "holdout_ann_return": np.nan,
                "holdout_sharpe": np.nan,
                "validation_verdict": validation_verdict,
                "trial_count_used": audit.get("trial_count_used", np.nan),
                "dsr_proxy": audit.get("dsr_proxy", np.nan),
                "pbo_proxy": audit.get("pbo_proxy", np.nan),
                "multiple_testing_adjusted_support": audit.get("multiple_testing_adjusted_support", np.nan),
            }
        )

    if SUMMARY_PATH.exists():
        summary = pd.read_csv(SUMMARY_PATH).set_index("name")
        for row in rows:
            if row["candidate"] in summary.index:
                s = summary.loc[row["candidate"]]
                row["annual_return"] = s.get("full_ann_return", row["annual_return"])
                row["annual_vol"] = s.get("full_ann_vol", row["annual_vol"])
                row["sharpe"] = s.get("full_sharpe", row["sharpe"])
                row["max_drawdown"] = s.get("full_max_drawdown", row["max_drawdown"])
                row["cvar_5"] = s.get("full_cvar_5", row["cvar_5"])
                row["avg_turnover"] = s.get("avg_turnover", row["avg_turnover"])
                row["holdout_ann_return"] = s.get("holdout_ann_return", row["holdout_ann_return"])
                row["holdout_sharpe"] = s.get("holdout_sharpe", row["holdout_sharpe"])
    return pd.DataFrame(rows)


def production_statistical_summary(stat: pd.DataFrame) -> dict[str, Any]:
    """Compute statistical-governance signals for the production pin."""

    returns = read_returns(returns_path(PRODUCTION_CANDIDATE))
    ret = pd.to_numeric(returns["net_return"], errors="coerce").dropna()
    trial_count = int(stat["trial_count_used"].max()) if not stat.empty and "trial_count_used" in stat.columns else 1
    candidate_count = int(stat["candidate"].nunique()) if not stat.empty and "candidate" in stat.columns else 0
    psr = probabilistic_sharpe_ratio(ret)
    dsr = deflated_sharpe_ratio_proxy(ret, trial_count=trial_count)
    mt_support = multiple_testing_adjusted_support(psr, trial_count)
    canonical = metrics_from_path(returns)
    holdout = holdout_metrics_from_path(returns, holdout_start=OFFICIAL_HOLDOUT_START)
    pbo = float(stat["pbo_proxy"].dropna().median()) if not stat.empty and "pbo_proxy" in stat.columns else np.nan
    prod_scanned = bool((stat.get("candidate", pd.Series(dtype=str)) == PRODUCTION_CANDIDATE).any()) if not stat.empty else False
    return {
        "candidate": PRODUCTION_CANDIDATE,
        "candidate_count_scanned": candidate_count,
        "trial_count_used": trial_count,
        "production_candidate_in_statistical_audit": prod_scanned,
        "psr_zero_benchmark": psr,
        "dsr_proxy_trial_adjusted": dsr,
        "multiple_testing_adjusted_support": mt_support,
        "pbo_proxy_project_median": pbo,
        "full_metrics": canonical,
        "holdout_metrics": holdout,
    }


def gate_rows(registry: dict[str, Any], stat_summary: dict[str, Any]) -> pd.DataFrame:
    """Create explicit Track A production gates."""

    rows = []

    def add(gate: str, status: str, detail: str, hard_gate: bool = True) -> None:
        rows.append({"gate": gate, "status": status, "hard_gate": hard_gate, "detail": detail})

    add(
        "registry_current_pin_matches",
        "PASS" if registry.get("current_production_pin") == PRODUCTION_CANDIDATE else "FAIL",
        f"current_production_pin={registry.get('current_production_pin')}",
    )
    add(
        "registry_production_candidate_matches",
        "PASS" if registry.get("production_candidate") == PRODUCTION_CANDIDATE else "FAIL",
        f"production_candidate={registry.get('production_candidate')}",
    )
    if REPRO_JSON.exists():
        repro = json.loads(REPRO_JSON.read_text())
        exact = bool(repro.get("status", {}).get("exact_reproduction_passed"))
        add("exact_reproduction", "PASS" if exact else "FAIL", f"report={rel(REPRO_JSON)}")
    else:
        add("exact_reproduction", "WARN", f"missing {rel(REPRO_JSON)}", hard_gate=True)
    if PHASE10_GATES.exists():
        gates = pd.read_csv(PHASE10_GATES)
        phase_pass = bool(gates["verdict"].astype(str).str.upper().eq("PASS").all()) if not gates.empty else False
        add("phase10a_pairwise_gates", "PASS" if phase_pass else "FAIL", f"source={rel(PHASE10_GATES)}")
    else:
        add("phase10a_pairwise_gates", "WARN", f"missing {rel(PHASE10_GATES)}")
    add(
        "statistical_audit_presence",
        "WARN" if not stat_summary["production_candidate_in_statistical_audit"] else "PASS",
        "Current production candidate was not present in the saved statistical audit; project-level trial count is still applied.",
        hard_gate=False,
    )
    add(
        "multiple_testing_warning",
        "WARN",
        f"trial_count={stat_summary['trial_count_used']}, scanned_candidates={stat_summary['candidate_count_scanned']}",
        hard_gate=False,
    )
    add(
        "cost_sensitivity",
        "PASS" if COST_SENSITIVITY.exists() else "WARN",
        f"source={rel(COST_SENSITIVITY)}",
        hard_gate=False,
    )
    holdout_sharpe = stat_summary["holdout_metrics"].get("sharpe")
    add(
        "holdout_metrics_present",
        "PASS" if np.isfinite(holdout_sharpe) else "FAIL",
        f"holdout_start={OFFICIAL_HOLDOUT_START.date()}, holdout_sharpe={holdout_sharpe}",
    )
    add(
        "manual_promotion_required",
        "PASS",
        "This script cannot promote candidates. Future production status requires explicit registry edit and hard-gate report.",
    )
    return pd.DataFrame(rows)


def write_report(snapshot: pd.DataFrame, gates: pd.DataFrame, stat_summary: dict[str, Any], bootstrap: pd.DataFrame) -> None:
    """Write markdown validation governance report."""

    counts = snapshot["artifact_class"].value_counts().rename_axis("artifact_class").reset_index(name="count")
    lines = [
        "# Track A Validation Governance Report",
        "",
        "## Scope",
        "",
        f"- Production candidate: `{PRODUCTION_CANDIDATE}`",
        f"- Saved portfolio return artifacts inventoried: `{len(snapshot)}`",
        f"- Statistical audit candidates scanned: `{stat_summary['candidate_count_scanned']}`",
        f"- Estimated trial count applied: `{stat_summary['trial_count_used']}`",
        f"- Production candidate present in statistical audit: `{stat_summary['production_candidate_in_statistical_audit']}`",
        "",
        "## Artifact Classes",
        "",
        markdown_table(counts),
        "",
        "## Production Statistical Warning",
        "",
        f"- PSR vs zero benchmark: `{stat_summary['psr_zero_benchmark']:.6f}`",
        f"- DSR proxy with trial count: `{stat_summary['dsr_proxy_trial_adjusted']:.6f}`",
        f"- Multiple-testing adjusted support: `{stat_summary['multiple_testing_adjusted_support']:.6f}`",
        f"- Project PBO proxy median: `{stat_summary['pbo_proxy_project_median']:.6f}`",
        "",
        "These are governance warnings, not retroactive de-promotion rules. The production artifact remains pinned only because it is the human-authorized conservative production candidate and now has exact reproduction checks.",
        "",
        "## Promotion Gates",
        "",
        markdown_table(gates),
        "",
        "## Bootstrap / Rolling Support",
        "",
        markdown_table(bootstrap) if not bootstrap.empty else "_No bootstrap summary found._",
        "",
        "## Outputs",
        "",
        f"- `{rel(TRACK_A_DIR / 'experiment_registry_snapshot.csv')}`",
        f"- `{rel(TRACK_A_DIR / 'production_promotion_gate_report.csv')}`",
        f"- `{rel(TRACK_A_DIR / 'track_a_validation_governance_summary.json')}`",
    ]
    DOC_REPORT.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    ensure_track_a_dirs()
    registry = require_official_production_pin()
    stat = load_stat_audit()
    snapshot = experiment_registry_snapshot(stat)
    stat_summary = production_statistical_summary(stat)
    gates = gate_rows(registry, stat_summary)
    bootstrap = pd.read_csv(PHASE10_BOOTSTRAP) if PHASE10_BOOTSTRAP.exists() else pd.DataFrame()

    snapshot.to_csv(TRACK_A_DIR / "experiment_registry_snapshot.csv", index=False)
    gates.to_csv(TRACK_A_DIR / "production_promotion_gate_report.csv", index=False)
    summary = {
        "production_candidate": PRODUCTION_CANDIDATE,
        "statistical_summary": stat_summary,
        "artifact_class_counts": snapshot["artifact_class"].value_counts().to_dict(),
        "gate_counts": gates["status"].value_counts().to_dict(),
    }
    (TRACK_A_DIR / "track_a_validation_governance_summary.json").write_text(
        json.dumps(clean_json(summary), indent=2, allow_nan=False) + "\n"
    )
    write_report(snapshot, gates, stat_summary, bootstrap)
    hard_failures = gates[gates["hard_gate"].eq(True) & gates["status"].eq("FAIL")]
    if not hard_failures.empty:
        raise SystemExit(f"Track A hard promotion gates failed: {hard_failures.to_dict(orient='records')}")
    print("validation governance report written")
    print(f"snapshot_rows={len(snapshot)}")
    print(f"wrote {rel(DOC_REPORT)}")


if __name__ == "__main__":
    main()
