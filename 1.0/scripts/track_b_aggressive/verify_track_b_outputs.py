"""Verify Track B research artifacts without touching production."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from production_config import PRODUCTION_CANDIDATE, markdown_table, rel, require_official_production_pin  # noqa: E402


OUT = ROOT / "data" / "research" / "track_b_aggressive"
DOC = ROOT / "docs" / "research" / "track_b_aggressive"
REQUIRED = [
    OUT / "track_b_benchmark_returns.csv",
    OUT / "track_b_benchmark_weights.csv",
    OUT / "track_b_benchmark_metrics.csv",
    OUT / "track_b_candidate_returns.csv",
    OUT / "track_b_candidate_weights.csv",
    OUT / "track_b_candidate_metrics.csv",
    OUT / "track_b_candidate_manifest.json",
    OUT / "track_b_experiment_registry.csv",
    OUT / "track_b_cost_sensitivity.csv",
    OUT / "track_b_state_metrics.csv",
    OUT / "track_b_rolling_origin_metrics.csv",
    OUT / "track_b_return_attribution.csv",
    OUT / "track_b_state_contribution.csv",
    OUT / "track_b_shortlist.csv",
    DOC / "track_b_predeclared_experiment_plan.md",
    DOC / "track_b_benchmark_comparison.md",
    DOC / "track_b_return_attribution.md",
    DOC / "track_b_higher_return_research_report.md",
]


def main() -> None:
    require_official_production_pin()
    rows = []
    for path in REQUIRED:
        rows.append({"check": f"exists:{rel(path)}", "passed": path.exists(), "detail": rel(path)})

    metrics = pd.read_csv(OUT / "track_b_candidate_metrics.csv")
    registry = pd.read_csv(OUT / "track_b_experiment_registry.csv")
    benchmarks = pd.read_csv(OUT / "track_b_benchmark_metrics.csv")
    shortlist = pd.read_csv(OUT / "track_b_shortlist.csv")
    manifest = json.loads((OUT / "track_b_candidate_manifest.json").read_text())

    rows.extend(
        [
            {"check": "candidate_count_12", "passed": len(metrics) == 12, "detail": str(len(metrics))},
            {"check": "benchmark_count_7", "passed": len(benchmarks) == 7, "detail": str(len(benchmarks))},
            {"check": "all_candidates_prefixed", "passed": metrics["name"].astype(str).str.startswith("track_b_aggressive_").all(), "detail": ""},
            {"check": "registry_research_only", "passed": registry["status"].astype(str).eq("research_only").all(), "detail": ""},
            {"check": "registry_not_promoted", "passed": registry["promotion_status"].astype(str).eq("not_promoted").all(), "detail": ""},
            {"check": "manifest_no_production_write", "passed": manifest.get("production_registry_written") is False, "detail": str(manifest.get("production_registry_written"))},
            {"check": "track_a_baseline_present", "passed": "track_a_production" in set(benchmarks["name"].astype(str)), "detail": ""},
            {"check": "production_pin_unchanged", "passed": PRODUCTION_CANDIDATE == "improved_frontier_phase5_fragility_guard", "detail": PRODUCTION_CANDIDATE},
            {"check": "no_track_b_mandate_promotion", "passed": not bool(shortlist.get("mandate_9_10_met", pd.Series(dtype=bool)).fillna(False).any()), "detail": "mandate hits are research observations only"},
        ]
    )
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "track_b_verification.csv", index=False)
    (OUT / "track_b_verification.json").write_text(json.dumps(result.to_dict(orient="records"), indent=2) + "\n")
    (DOC / "track_b_verification.md").write_text(
        "\n".join(["# Track B Verification", "", markdown_table(result), ""]).rstrip() + "\n"
    )
    failed = result[~result["passed"]]
    if not failed.empty:
        raise SystemExit(f"Track B verification failed: {failed.to_dict(orient='records')}")
    print("Track B verification passed")
    print(f"candidates={len(metrics)} benchmarks={len(benchmarks)}")
    print(f"wrote {rel(DOC / 'track_b_verification.md')}")


if __name__ == "__main__":
    main()
