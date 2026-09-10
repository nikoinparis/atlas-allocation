"""Verify Track C research-only artifacts.

This verifier checks that Track C generated the required isolated outputs,
logged all candidates as research-only, preserved the Track A production pin,
and did not create a production-marked candidate.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from production_config import PRODUCTION_CANDIDATE, rel, require_official_production_pin, returns_path, weights_path  # noqa: E402


OUT = ROOT / "data" / "research" / "track_c_new_alpha"
DOC = ROOT / "docs" / "research" / "track_c_new_alpha"

REQUIRED_FILES = [
    OUT / "track_c_candidate_manifest.json",
    OUT / "track_c_standalone_sleeve_returns.csv",
    OUT / "track_c_standalone_sleeve_weights.csv",
    OUT / "track_c_standalone_sleeve_metrics.csv",
    OUT / "track_c_blend_returns.csv",
    OUT / "track_c_blend_weights.csv",
    OUT / "track_c_blend_metrics.csv",
    OUT / "track_c_cost_sensitivity.csv",
    OUT / "track_c_state_metrics.csv",
    OUT / "track_c_signal_ic.csv",
    OUT / "track_c_correlations.csv",
    OUT / "track_c_beta_adjusted_attribution.csv",
    OUT / "track_c_experiment_registry.csv",
    OUT / "track_c_reference_comparison.csv",
    DOC / "track_c_predeclared_research_plan.md",
    DOC / "track_c_new_alpha_research_report.md",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def main() -> None:
    rows = []
    registry_pin = require_official_production_pin()
    rows.append(
        check(
            "track_a_production_pin_preserved",
            registry_pin.get("current_production_pin") == PRODUCTION_CANDIDATE,
            f"current_production_pin={registry_pin.get('current_production_pin')}",
        )
    )

    missing = [rel(path) for path in REQUIRED_FILES if not path.exists()]
    rows.append(check("required_files_exist", not missing, f"missing={missing}"))

    if missing:
        result = pd.DataFrame(rows)
        OUT.mkdir(parents=True, exist_ok=True)
        result.to_csv(OUT / "track_c_verification.csv", index=False)
        (OUT / "track_c_verification.json").write_text(json.dumps({"checks": rows}, indent=2) + "\n")
        raise SystemExit("Track C verification failed: missing required files")

    manifest = json.loads((OUT / "track_c_candidate_manifest.json").read_text())
    rows.append(check("manifest_track_c", manifest.get("track") == "track_c_new_alpha", f"track={manifest.get('track')}"))
    rows.append(
        check(
            "manifest_research_only",
            manifest.get("research_status") == "research_only",
            f"research_status={manifest.get('research_status')}",
        )
    )
    rows.append(
        check(
            "manifest_production_candidate_matches_track_a",
            manifest.get("production_candidate") == PRODUCTION_CANDIDATE,
            f"production_candidate={manifest.get('production_candidate')}",
        )
    )
    rows.append(
        check(
            "track_a_returns_hash_preserved",
            manifest.get("track_a_returns_sha256") == sha256_file(returns_path(PRODUCTION_CANDIDATE)),
            "Track A returns hash matches manifest.",
        )
    )
    rows.append(
        check(
            "track_a_weights_hash_preserved",
            manifest.get("track_a_weights_sha256") == sha256_file(weights_path(PRODUCTION_CANDIDATE)),
            "Track A weights hash matches manifest.",
        )
    )

    standalone_metrics = pd.read_csv(OUT / "track_c_standalone_sleeve_metrics.csv")
    blend_metrics = pd.read_csv(OUT / "track_c_blend_metrics.csv")
    registry = pd.read_csv(OUT / "track_c_experiment_registry.csv")
    cost = pd.read_csv(OUT / "track_c_cost_sensitivity.csv")
    ic = pd.read_csv(OUT / "track_c_signal_ic.csv")

    rows.append(
        check(
            "standalone_candidate_count_is_six",
            int(manifest.get("standalone_candidate_count", -1)) == 6 and len(standalone_metrics) == 6,
            f"manifest_count={manifest.get('standalone_candidate_count')}, metrics_rows={len(standalone_metrics)}",
        )
    )
    rows.append(
        check(
            "all_candidate_names_are_track_c",
            registry["candidate_name"].astype(str).str.startswith("track_c_").all(),
            "All registry candidate names use track_c_ prefix.",
        )
    )
    rows.append(
        check(
            "registry_research_only",
            registry["research_status"].astype(str).eq("research_only").all(),
            "All Track C registry rows are research_only.",
        )
    )
    production_like = registry["promotion_status"].astype(str).str.contains("production", case=False, na=False) & ~registry[
        "promotion_status"
    ].astype(str).str.contains("not_eligible", case=False, na=False)
    rows.append(
        check(
            "no_track_c_production_promotion",
            not bool(production_like.any()) and not registry["verdict"].astype(str).str.contains("production", case=False).any(),
            "No Track C candidate is marked production.",
        )
    )
    cost_groups = cost.groupby("name")["cost_multiplier"].apply(lambda s: set(float(x) for x in s.dropna()))
    missing_cost = [name for name, vals in cost_groups.items() if not {1.0, 2.0, 3.0}.issubset(vals)]
    rows.append(check("cost_sensitivity_1x_2x_3x_present", not missing_cost, f"missing_cost_multipliers={missing_cost}"))
    rows.append(
        check(
            "ic_rows_present_for_all_standalone",
            len(ic["name"].dropna().unique()) == 6,
            f"ic_candidate_count={len(ic['name'].dropna().unique())}",
        )
    )
    rows.append(
        check(
            "blend_metrics_schema_ok",
            blend_metrics.empty or {"parent_candidate", "track_c_watchlist"}.issubset(blend_metrics.columns),
            f"blend_rows={len(blend_metrics)}",
        )
    )

    result = pd.DataFrame(rows)
    result.to_csv(OUT / "track_c_verification.csv", index=False)
    (OUT / "track_c_verification.json").write_text(json.dumps({"checks": rows}, indent=2) + "\n")
    failures = result[result["status"].eq("FAIL")]
    if not failures.empty:
        raise SystemExit(f"Track C verification failed: {failures.to_dict(orient='records')}")
    print(f"Track C verification passed: {len(rows)} checks.")


if __name__ == "__main__":
    main()
