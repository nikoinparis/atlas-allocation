#!/usr/bin/env python3
"""Independent consistency and rolling-window audit for the adaptive-risk experiment."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evidence/sec_residual_financing_adaptive_risk_v1"
OUTPUT = ROOT / "evidence/sec_residual_financing_adaptive_risk_audit_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compounded(values: pd.Series) -> float:
    return float((1.0 + pd.to_numeric(values, errors="coerce").dropna()).prod() - 1.0)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "result.json"
    if result_path.exists():
        raise RuntimeError("adaptive-risk audit is one-shot")
    source_result = json.loads((SOURCE / "result.json").read_text())
    for name, expected in source_result["artifact_sha256"].items():
        if sha256(SOURCE / name) != expected:
            raise RuntimeError(f"source artifact hash mismatch: {name}")

    variants = {}
    for path in sorted(SOURCE.glob("path__*.csv")):
        frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
        frame.index = pd.to_datetime(frame.index, utc=True)
        variants[path.stem.replace("path__", "")] = frame.net_return
    benchmark_name = "fixed_1.25x_realistic_financing"
    benchmark = variants[benchmark_name]

    rolling_rows = []
    for name, values in variants.items():
        joined = pd.concat([values.rename("candidate"), benchmark.rename("benchmark")], axis=1).dropna()
        for weeks in (26, 52):
            differences = []
            for end in range(weeks, len(joined) + 1):
                block = joined.iloc[end - weeks:end]
                differences.append(compounded(block.candidate) - compounded(block.benchmark))
            rolling_rows.append({
                "variant": name,
                "window_weeks": weeks,
                "completed_windows": len(differences),
                "outperformance_share": float(np.mean(np.asarray(differences) > 0)) if differences else 0.0,
                "median_return_difference": float(np.median(differences)) if differences else 0.0,
                "worst_return_difference": float(np.min(differences)) if differences else 0.0,
            })
    rolling = pd.DataFrame(rolling_rows)

    calendar_rows = []
    for name, values in variants.items():
        for year, subset in values.groupby(values.index.year):
            calendar_rows.append({"variant": name, "year": int(year), "compounded_return": compounded(subset), "weeks": int(len(subset))})
    calendar = pd.DataFrame(calendar_rows)

    multipliers = pd.read_csv(SOURCE / "adaptive_multipliers.csv", parse_dates=["Date"]).set_index("Date").target_multiplier
    distribution = multipliers.value_counts().sort_index()
    transitions = int((multipliers != multipliers.shift(1)).sum() - 1)
    audit_files = [SOURCE / "metrics.csv", SOURCE / "stress_grid.csv", SOURCE / "margin_shocks.csv", SOURCE / "risk_contribution_diagnostics.csv"]
    rolling.to_csv(OUTPUT / "rolling_windows.csv", index=False)
    calendar.to_csv(OUTPUT / "calendar_years.csv", index=False)
    audit = {
        "experiment": "sec_residual_financing_adaptive_risk_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_result_sha256": sha256(SOURCE / "result.json"),
        "source_artifact_hashes_verified": True,
        "common_endpoint": source_result["common_endpoint"],
        "adaptive_multiplier_week_counts": {str(float(level)): int(count) for level, count in distribution.items()},
        "adaptive_multiplier_transitions": transitions,
        "historical_margin_safety_breaches": source_result["historical_margin_safety_breaches"],
        "full_window_start_mismatch": {
            name: str(values.index.min().date()) for name, values in variants.items()
        },
        "full_window_comparison_authorized": False,
        "comparable_primary_window": "trailing_52w",
        "comparable_secondary_window": "trailing_104w",
        "research_display_winner": source_result["research_display_winner"],
        "replacement_authorized": False,
        "live_trading_enabled": False,
        "source_support_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in audit_files},
        "artifact_sha256": {
            "rolling_windows.csv": sha256(OUTPUT / "rolling_windows.csv"),
            "calendar_years.csv": sha256(OUTPUT / "calendar_years.csv"),
        },
    }
    result_path.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
