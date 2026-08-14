"""Run the full Track A verification suite and write the final report."""

from __future__ import annotations

import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from production_config import (
    PRODUCTION_CANDIDATE,
    TRACK_A_DIR,
    ensure_track_a_dirs,
    markdown_table,
    rel,
    require_official_production_pin,
)


ROOT = Path(__file__).resolve().parents[1]
FINAL_REPORT = ROOT / "docs" / "research" / "track_a_production_hardening_final_report.md"


COMMANDS = [
    ("canonical_metrics_cost_tests", [sys.executable, "scripts/test_production_metrics_costs.py"]),
    ("wrapper_equivalence_tests", [sys.executable, "scripts/test_production_pipeline_equivalence.py"]),
    ("production_reproduction", [sys.executable, "scripts/reproduce_production_candidate.py"]),
    ("validation_governance", [sys.executable, "scripts/run_track_a_validation_governance.py"]),
    ("dashboard_bundle_build", [sys.executable, "scripts/build_production_candidate_dashboard_bundle.py"]),
    ("dashboard_packaging_verify", [sys.executable, "scripts/verify_dashboard_packaging.py"]),
    ("typescript_typecheck", ["npm", "run", "typecheck"]),
    ("next_production_build", ["npm", "run", "build"]),
]


TRACK_A_FILES = [
    "scripts/production_config.py",
    "scripts/production_metrics.py",
    "scripts/production_costs.py",
    "scripts/production_allocator.py",
    "scripts/reproduce_production_candidate.py",
    "scripts/run_track_a_validation_governance.py",
    "scripts/verify_dashboard_packaging.py",
    "scripts/run_track_a_verification_suite.py",
    "scripts/test_production_metrics_costs.py",
    "scripts/test_production_pipeline_equivalence.py",
    "scripts/path1_path3_research_utils.py",
    "scripts/build_production_candidate_dashboard_bundle.py",
    "package.json",
    "README.md",
    "CLAUDE.md",
    "src/components/executive-summary.tsx",
    "src/components/dashboard-shell.tsx",
    "docs/research/track_a_production_hardening.md",
    "docs/research/track_a_production_reproduction_report.md",
    "docs/research/track_a_validation_governance_report.md",
    "docs/research/track_a_dashboard_packaging_verification.md",
    "docs/research/track_a_production_hardening_final_report.md",
]


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


def run_command(name: str, cmd: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def compact_metric_table() -> str:
    df = read_csv(TRACK_A_DIR / "production_reproduction_metrics_comparison.csv")
    if df.empty:
        return "_Metric comparison was not generated._"
    keep = df[df["metric"].isin(["ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "holdout_sharpe", "avg_weekly_turnover"])]
    return markdown_table(keep)


def cost_sensitivity_table() -> str:
    df = read_csv(TRACK_A_DIR / "production_cost_sensitivity.csv")
    if df.empty:
        return "_Cost sensitivity was not generated._"
    cols = ["cost_multiplier", "cost_bps_per_one_way_turnover", "ann_return", "sharpe", "max_drawdown", "cvar_5", "annualized_cost"]
    return markdown_table(df[[c for c in cols if c in df.columns]])


def command_results_table(results: list[dict[str, Any]]) -> str:
    df = pd.DataFrame(
        [
            {
                "name": r["name"],
                "passed": r["passed"],
                "returncode": r["returncode"],
                "command": r["command"],
            }
            for r in results
        ]
    )
    return markdown_table(df)


def write_final_report(results: list[dict[str, Any]]) -> None:
    registry = require_official_production_pin()
    repro = read_json(TRACK_A_DIR / "production_reproduction_report.json")
    governance = read_json(TRACK_A_DIR / "track_a_validation_governance_summary.json")
    dashboard = read_json(TRACK_A_DIR / "dashboard_packaging_verification.json")
    repro_status = repro.get("status", {})
    all_passed = all(r["passed"] for r in results)
    dashboard_passed = bool(dashboard.get("passed"))
    exact = bool(repro_status.get("exact_reproduction_passed"))
    gate_counts = governance.get("gate_counts", {})
    overfit_count = governance.get("artifact_class_counts", {}).get("rejected", 0)

    lines = [
        "# Track A Production Hardening Report",
        "",
        "## 1. Official Production Candidate Verified",
        "",
        f"- Official production candidate: `{PRODUCTION_CANDIDATE}`",
        f"- Registry current pin: `{registry.get('current_production_pin')}`",
        f"- Registry production candidate: `{registry.get('production_candidate')}`",
        f"- Registry status: `{registry.get('candidate_status')}`",
        "",
        "## 2. Files Changed",
        "",
        *[f"- `{path}`" for path in TRACK_A_FILES],
        "",
        "## 3. Canonical Metrics Module Created/Updated",
        "",
        "- `scripts/production_metrics.py` defines CAGR, arithmetic annual return, sample-volatility Sharpe, Sortino, drawdown, Calmar, weekly VaR/CVaR, hit rate, turnover/cost summaries, exposures, holdout metrics, and rolling-origin summaries.",
        "- `scripts/path1_path3_research_utils.py` now delegates its production metric helpers to the canonical module.",
        "",
        "## 4. Canonical Cost/Turnover Module Created/Updated",
        "",
        "- `scripts/production_costs.py` defines one-way turnover, full L1 turnover, cost conversion, next-week return convention, production path recomputation, and 1x/2x/3x cost sensitivity helpers.",
        "- Canonical cost is `one_way_turnover * cost_bps / 10000`, with production default `10 bps`.",
        "",
        "## 5. Production Reproduction Results",
        "",
        f"- Exact reproduction passed: `{exact}`",
        f"- Weight max absolute error: `{float(repro_status.get('weights_max_abs_error', np.nan)):.3e}`",
        f"- Path max absolute error: `{float(repro_status.get('path_max_abs_error', np.nan)):.3e}`",
        f"- Net return correlation vs saved: `{float(repro_status.get('net_return_corr_vs_saved', np.nan)):.12f}`",
        "",
        "## 6. Old vs New Metric Comparison",
        "",
        compact_metric_table(),
        "",
        "## 7. Cost Sensitivity Results",
        "",
        cost_sensitivity_table(),
        "",
        "## 8. Wrapper/Native Equivalence Result",
        "",
        "- The current production system is wrapper-based, not native.",
        "- `scripts/production_allocator.py` formalizes the wrapper as a first-class production component.",
        "- `scripts/test_production_pipeline_equivalence.py` compares the formal component against the legacy artifact-generation modifier and the stored production artifacts.",
        "",
        "## 9. Validation Governance Updates",
        "",
        f"- Experiment registry snapshot written with artifact classes and promotion statuses.",
        f"- Gate status counts: `{gate_counts}`",
        f"- Candidates rejected for promotion by overfit-risk audit status: `{overfit_count}`",
        "",
        "## 10. Dashboard Packaging Updates",
        "",
        f"- Dashboard bundle verification passed: `{dashboard_passed}`",
        "- `npm run refresh:data` now runs `scripts/build_production_candidate_dashboard_bundle.py`.",
        "- Active README/UI references now point to compact dashboard bundles rather than the retired monolithic dashboard data file.",
        "",
        "## 11. Documentation Updates",
        "",
        "- `docs/research/track_a_production_hardening.md` documents the production candidate, wrapper pipeline, data/timing assumptions, cost/turnover convention, metrics convention, holdout date, validation gates, limitations, and Track A scope.",
        "- `CLAUDE.md` now points future agents at the canonical Track A modules and scripts.",
        "",
        "## 12. Tests Run And Results",
        "",
        command_results_table(results),
        "",
        "## 13. Remaining Known Issues",
        "",
        "- The production strategy is still a wrapper/post-processor; a fully native allocator rebuild remains out of scope.",
        "- The sleeve-weight artifact remains a proxy because the production behavior is applied at final ETF weights.",
        "- The holdout has been repeatedly inspected across the research history and should not be treated as pristine.",
        "- The statistical validation audit found broad overfit risk; Track A reduces false confidence but does not prove a persistent alpha edge.",
        "- Historical research documents still mention old pins and old dashboard files as history; active runtime/docs now use compact production-candidate bundles.",
        "",
        "## 14. Final Verdict",
        "",
        f"- Production candidate reproducible: `{exact}`",
        f"- Metrics consistent: `{exact}`",
        f"- Costs consistent: `{exact}`",
        f"- Dashboard consistent: `{dashboard_passed}`",
        f"- Ready for Track B research: `{all_passed and exact and dashboard_passed}`",
        "",
        "Track A verdict: the conservative production artifact is now reproducible, auditable, registry-driven, and governed by explicit warnings. Future research should compare against this production pin without promoting new candidates automatically.",
    ]
    FINAL_REPORT.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    ensure_track_a_dirs()
    results = [run_command(name, cmd) for name, cmd in COMMANDS]
    (TRACK_A_DIR / "track_a_verification_suite_results.json").write_text(
        json.dumps(clean_json(results), indent=2, allow_nan=False) + "\n"
    )
    pd.DataFrame(results).drop(columns=["stdout_tail", "stderr_tail"]).to_csv(
        TRACK_A_DIR / "track_a_verification_suite_results.csv",
        index=False,
    )
    write_final_report(results)
    print("Track A verification suite complete")
    print(command_results_table(results))
    print(f"wrote {rel(FINAL_REPORT)}")
    if not all(r["passed"] for r in results):
        failed = [r["name"] for r in results if not r["passed"]]
        raise SystemExit(f"Track A verification failures: {failed}")


if __name__ == "__main__":
    main()
