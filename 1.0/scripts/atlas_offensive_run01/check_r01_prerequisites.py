#!/usr/bin/env python3
"""Atlas Offensive R01 — prerequisite gate.

R01 (PIT stock breadth confirmation) may only execute when Norgate Data is
active and exported into data/stock_breadth/raw/. Per the Master Run Book
(§A.4) and CLAUDE.md, a missing prerequisite means STOP AND REPORT — no
substitute or scraped universe is permitted.

Output: data/research/atlas_offensive_run01/r01_prerequisite_check.csv
Exit code 0 always; prints R01_PREREQUISITES_MET or R01_BLOCKED_PREREQUISITE.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "stock_breadth" / "raw"
OUT_DIR = ROOT / "data" / "research" / "atlas_offensive_run01"


def real_input_exists(stem: str) -> tuple[bool, str]:
    """True when a non-template file/dir for this input group exists (scaffold convention)."""
    for candidate in [RAW / f"{stem}.parquet", RAW / f"{stem}.csv", RAW / stem]:
        if candidate.exists() and "_TEMPLATE." not in candidate.name:
            return True, str(candidate.relative_to(ROOT))
    return False, f"only templates or nothing under {RAW.relative_to(ROOT)}"


def main() -> None:
    checks = []

    norgate_installed = importlib.util.find_spec("norgatedata") is not None
    checks.append(
        {
            "check": "norgatedata_python_package",
            "required": True,
            "status": "PASS" if norgate_installed else "FAIL",
            "details": "importable" if norgate_installed else
            "norgatedata not installed; Norgate Data Updater is Windows-only — export must be produced elsewhere and copied in",
        }
    )

    for stem in ["index_membership", "stock_prices_daily", "security_master"]:
        ok, detail = real_input_exists(stem)
        checks.append(
            {"check": f"raw_input_{stem}", "required": True,
             "status": "PASS" if ok else "FAIL", "details": detail}
        )
    ok, detail = real_input_exists("sector_classification")
    checks.append(
        {"check": "raw_input_sector_classification", "required": False,
         "status": "PASS" if ok else "MISSING_OPTIONAL", "details": detail}
    )

    scaffold = ROOT / "scripts" / "build_pit_stock_breadth_panel.py"
    checks.append(
        {"check": "breadth_panel_scaffold_present", "required": True,
         "status": "PASS" if scaffold.exists() else "FAIL",
         "details": str(scaffold.relative_to(ROOT))}
    )

    r00_artifacts = {
        "holdout_declaration": ROOT / "docs" / "research" / "atlas_offensive" / "offensive_holdout_declaration.md",
        "trial_registry": ROOT / "data" / "research" / "atlas_offensive_trial_registry.csv",
        "preregistration_template": ROOT / "docs" / "research" / "atlas_offensive" / "preregistration_template.md",
        "run01_preregistration": ROOT / "docs" / "research" / "atlas_offensive" / "run01_preregistration.md",
        "cost_library": ROOT / "data" / "research" / "atlas_offensive_cost_library.csv",
    }
    for name, path in r00_artifacts.items():
        checks.append(
            {"check": f"r00_artifact_{name}", "required": True,
             "status": "PASS" if path.exists() else "FAIL",
             "details": str(path.relative_to(ROOT))}
        )

    df = pd.DataFrame(checks)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "r01_prerequisite_check.csv"
    df.to_csv(out_path, index=False)

    blocked = ((df["required"]) & (df["status"] == "FAIL")).any()
    print(df.to_string(index=False))
    print(f"\nWrote {out_path.relative_to(ROOT)}")
    print("R01_BLOCKED_PREREQUISITE" if blocked else "R01_PREREQUISITES_MET")


if __name__ == "__main__":
    main()
