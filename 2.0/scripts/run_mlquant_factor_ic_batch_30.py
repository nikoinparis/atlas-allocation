#!/usr/bin/env python3
"""Evaluate the predeclared mlquant ETF factor-IC experiment."""

from __future__ import annotations

import csv
import argparse
import hashlib
import json
import math
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.factor_ic_protocol import (
    circular_block_bootstrap_means,
    quantile,
    summarize,
)

PROGRAM = ROOT / "config/mlquant_etf_factor_ic_program_v1.json"
OUTPUT = ROOT / "evidence/mlquant_factor_ic_batch_30"
IMAGE = "localhost/po2-mlquant-batch29:latest"
EXPORTER = ROOT / "scripts/export_mlquant_factors_batch_30.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_export() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in ("asset_coverage.csv", "all_factor_audit.csv", "daily_rank_ic.csv", "export_metadata.json"):
        target = OUTPUT / name
        if target.exists():
            target.unlink()
    command = [
        "podman", "run", "--rm",
        "-v", f"{ROOT}:/project:ro",
        "-v", f"{OUTPUT}:/output:rw",
        IMAGE,
        "python", "/project/scripts/export_mlquant_factors_batch_30.py",
        "--program", "/project/config/mlquant_etf_factor_ic_program_v1.json",
        "--output", "/output",
    ]
    subprocess.run(command, check=True, cwd=ROOT)


def period_for(day: date, periods: dict[str, list[str]]) -> str | None:
    for name, (start, end) in periods.items():
        if date.fromisoformat(start) <= day <= date.fromisoformat(end):
            return name
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reuse-export", action="store_true", help="reuse deterministic container export")
    args = parser.parse_args()
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    if not args.reuse_export:
        run_export()
    rows = read_csv(OUTPUT / "daily_rank_ic.csv")
    values: dict[tuple[str, str, str], list[float]] = {}
    for row in rows:
        if not row["rank_ic"]:
            continue
        period = period_for(date.fromisoformat(row["date"]), program["periods"])
        if period is None:
            continue
        values.setdefault((row["factor"], row["variant"], period), []).append(float(row["rank_ic"]))

    factors = program["source_preselected_factors"]
    variants = ["primary", "stale_1", "stale_5", "inverted", "asset_permutation", "return_permutation"]
    summary_rows: list[dict[str, object]] = []
    factor_results = []
    gates = program["qualification_gate"]
    uncertainty = program["uncertainty"]
    for factor_number, factor in enumerate(factors):
        development = values.get((factor, "primary", "development"), [])
        development_summary = summarize(development)
        direction = 1 if float(development_summary["mean_ic"]) >= 0.0 else -1
        for variant in variants:
            for period in program["periods"]:
                raw = values.get((factor, variant, period), [])
                signed = [direction * value for value in raw]
                row = summarize(signed)
                summary_rows.append({"factor": factor, "direction": direction, "variant": variant, "period": period, **row})

        validation = [direction * value for value in values.get((factor, "primary", "validation"), [])]
        test = [direction * value for value in values.get((factor, "primary", "retrospective_test"), [])]
        combined = validation + test
        bootstrap = circular_block_bootstrap_means(
            combined,
            block_size=int(uncertainty["block_sessions"]),
            replicates=int(uncertainty["replicates"]),
            seed=int(uncertainty["seed"]) + factor_number,
        )
        lower = quantile(bootstrap, float(uncertainty["per_factor_one_sided_alpha"]))
        combined_mean = sum(combined) / len(combined)
        control_means = {}
        for variant in ("stale_5", "asset_permutation", "return_permutation"):
            control = []
            for period in ("validation", "retrospective_test"):
                control.extend(direction * value for value in values.get((factor, variant, period), []))
            control_means[variant] = sum(control) / len(control) if control else math.nan
        checks = {
            "minimum_ic_dates_each_period": all(
                len(values.get((factor, "primary", period), [])) >= int(gates["minimum_ic_dates_each_period"])
                for period in program["periods"]
            ),
            "minimum_absolute_development_mean_ic": abs(float(development_summary["mean_ic"])) >= float(gates["minimum_absolute_development_mean_ic"]),
            "validation_signed_mean_ic_strictly_positive": bool(validation) and sum(validation) / len(validation) > 0.0,
            "retrospective_test_signed_mean_ic_strictly_positive": bool(test) and sum(test) / len(test) > 0.0,
            "combined_validation_test_familywise_bootstrap_lower_strictly_positive": lower > 0.0,
            "combined_mean_must_exceed_stale_5_session_control": combined_mean > abs(control_means["stale_5"]),
            "combined_mean_must_exceed_asset_and_return_permutation_controls": combined_mean > max(abs(control_means["asset_permutation"]), abs(control_means["return_permutation"])),
        }
        factor_results.append({
            "factor": factor,
            "development_direction": direction,
            "development_mean_ic_raw": development_summary["mean_ic"],
            "validation_signed_mean_ic": sum(validation) / len(validation),
            "retrospective_test_signed_mean_ic": sum(test) / len(test),
            "combined_validation_test_signed_mean_ic": combined_mean,
            "familywise_bootstrap_lower": lower,
            "control_signed_means": control_means,
            "checks": checks,
            "qualified": all(checks.values()),
        })
    write_csv(OUTPUT / "ic_summary.csv", summary_rows)

    audit_rows = read_csv(OUTPUT / "all_factor_audit.csv")
    audit_passed = sum(row["status"] == "pass" and int(row["nonfinite_valid_cells"]) == 0 for row in audit_rows)
    metadata = json.loads((OUTPUT / "export_metadata.json").read_text(encoding="utf-8"))
    result = {
        "program": program["program"],
        "repository_commit": program["repository"]["commit"],
        "source_snapshot_id": program["source_snapshot"]["snapshot_id"],
        "input_metadata": metadata,
        "all_factor_audit": {"registered": len(audit_rows), "passed_finite": audit_passed, "failed": len(audit_rows) - audit_passed},
        "factor_results": factor_results,
        "qualified_factors": [row["factor"] for row in factor_results if row["qualified"]],
        "portfolio_backtest_authorized": any(row["qualified"] for row in factor_results),
        "live_trading_enabled": False,
        "interpretation": "Retrospective factor-quality evidence only; not an executable strategy return or profit claim.",
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    lines = [
        "# ml-quant-trading ETF factor qualification — Batch 30", "",
        f"Pinned repository commit: `{program['repository']['commit']}`", "",
        f"The repository registered {len(audit_rows)} factors; {audit_passed} completed the mechanical finiteness audit. No factor outside the six source-preselected ETF factors was screened for performance.", "",
        "| Factor | Dev direction | Dev mean IC | Validation signed IC | Test signed IC | Combined lower bound | Qualified |", "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in factor_results:
        lines.append(
            f"| {row['factor']} | {row['development_direction']:+d} | {float(row['development_mean_ic_raw']):.4f} | "
            f"{float(row['validation_signed_mean_ic']):.4f} | {float(row['retrospective_test_signed_mean_ic']):.4f} | "
            f"{float(row['familywise_bootstrap_lower']):.4f} | {'yes' if row['qualified'] else 'no'} |"
        )
    lines.extend([
        "", f"Qualified factors: {', '.join(result['qualified_factors']) if result['qualified_factors'] else 'none'}.", "",
        "This is a close-to-next-close rank-IC diagnostic on a fixed survivor ETF universe using a typical-price VWAP proxy. It is not a tradable return series. A portfolio backtest is permitted only for factors that pass every predeclared gate, and would require separate next-session execution, turnover, costs, and risk controls.", "",
    ])
    (OUTPUT / "report.md").write_text("\n".join(lines), encoding="utf-8")

    projected = ["asset_coverage.csv", "all_factor_audit.csv", "daily_rank_ic.csv", "export_metadata.json", "ic_summary.csv", "result.json", "report.md"]
    determinism = {name: sha256(OUTPUT / name) for name in projected}
    (OUTPUT / "artifact_hashes.json").write_text(json.dumps(determinism, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
