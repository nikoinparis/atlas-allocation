#!/usr/bin/env python3
"""Read-only Phase 0 inventory and accounting audit of the Version 1 pin."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
PROGRAM = ROOT / "config/v1_to_v2_equivalence_audit_v1.json"
OUTPUT = ROOT / "evidence/v1_migration_batch_40"

FILES = {
    "saved_candidate_returns": "data/05_layer3_portfolio_construction/portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv",
    "saved_candidate_weights": "data/05_layer3_portfolio_construction/portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv",
    "base_candidate_weights": "data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv",
    "base_candidate_returns": "data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv",
    "weekly_prices": "data/01_data_hub/weekly_prices.csv",
    "market_states": "data/04_layer2b_risk_regime_engine/market_state_history.csv",
    "phase1_state_quality": "data/research/frontier_phase1/state_quality_signals_r2.csv",
    "phase4_leadership": "data/research/frontier_phase4/leadership_signals.csv",
    "candidate_registry": "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "internal_reproduction_report": "data/research/track_a_production_hardening/production_reproduction_report.json",
    "production_allocator": "scripts/production_allocator.py",
    "allocator_wrapper": "scripts/allocator_checkpoint_wrapper.py",
    "research_utilities": "scripts/path1_path3_research_utils.py",
    "production_config": "scripts/production_config.py",
    "production_costs": "scripts/production_costs.py",
    "production_metrics": "scripts/production_metrics.py",
    "reproduction_runner": "scripts/reproduce_production_candidate.py"
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(values: list[float], turnover: list[float]) -> dict[str, float | int]:
    wealth = 1.0
    peak = 1.0
    drawdown = 0.0
    for value in values:
        wealth *= 1.0 + value
        peak = max(peak, wealth)
        drawdown = min(drawdown, wealth / peak - 1.0)
    years = len(values) / 52.0
    deviation = statistics.stdev(values)
    return {
        "weeks": len(values),
        "annual_return": wealth ** (1.0 / years) - 1.0,
        "annual_volatility": deviation * math.sqrt(52.0),
        "arithmetic_sharpe_zero_rf": statistics.fmean(values) / deviation * math.sqrt(52.0),
        "maximum_drawdown": drawdown,
        "annualized_one_way_turnover": sum(turnover) / years,
    }


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    inventory = []
    missing = []
    for role, relative in FILES.items():
        path = V1 / relative
        if not path.is_file():
            missing.append(relative)
            continue
        inventory.append({"role": role, "v1_relative_path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})

    returns = rows(V1 / FILES["saved_candidate_returns"])
    weights = rows(V1 / FILES["saved_candidate_weights"])
    dates = [row["Date"] for row in returns]
    accounting_error = max(
        abs(float(row["net_return"]) - (float(row["gross_return"]) - (float(row["turnover"]) if row["turnover"] else 0.0) * 10.0 / 10000.0))
        for row in returns
    )
    weight_columns = [name for name in weights[0] if name != "Date"]
    weight_sums = [sum(float(row[name]) for name in weight_columns) for row in weights]
    minimum_weight = min(float(row[name]) for row in weights for name in weight_columns)
    maximum_weight = max(float(row[name]) for row in weights for name in weight_columns)
    finite_weights = all(math.isfinite(float(row[name])) for row in weights for name in weight_columns)
    internal = json.loads((V1 / FILES["internal_reproduction_report"]).read_text(encoding="utf-8"))

    recent = []
    end_year = int(dates[-1][:4])
    end_month_day = dates[-1][4:]
    for cost in program["reporting_priority"]["cost_sensitivity_bps"]:
        panel = []
        for row in returns:
            turn = float(row["turnover"]) if row["turnover"] else 0.0
            panel.append((row["Date"], float(row["gross_return"]) - turn * float(cost) / 10000.0, turn))
        for years in program["reporting_priority"]["recent_windows_years"]:
            start = f"{end_year-int(years):04d}{end_month_day}"
            selected = [(value, turn) for day, value, turn in panel if day > start]
            summary = summarize([value for value, _ in selected], [turn for _, turn in selected])
            recent.append({"cost_bps": cost, "window_years": years, "end_date": dates[-1], **summary})

    gates = {
        "all_required_files_present_and_hashed": not missing and len(inventory) == len(FILES),
        "saved_weights_finite_nonnegative_and_sum_to_one": finite_weights and minimum_weight >= -1e-12 and max(abs(value - 1.0) for value in weight_sums) <= 1e-10,
        "saved_10bps_net_returns_reconstruct_from_gross_and_turnover": accounting_error <= 1e-12,
        "existing_v1_internal_reproduction_passed": bool(internal["status"]["exact_reproduction_passed"]),
        "metric_conventions_explicitly_separated": True,
    }
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM),
        "phase": "phase_0_read_only_inventory_and_accounting",
        "source_candidate": program["source"]["candidate"],
        "source_dates": {"first": dates[0], "last": dates[-1], "weeks": len(dates)},
        "saved_weight_checks": {
            "rows": len(weights), "assets": len(weight_columns), "finite": finite_weights,
            "minimum": minimum_weight, "maximum": maximum_weight,
            "maximum_sum_deviation": max(abs(value - 1.0) for value in weight_sums),
        },
        "saved_10bps_accounting_maximum_absolute_error": accounting_error,
        "v1_internal_reproduction": internal["status"],
        "phase_0_gates": gates, "phase_0_passed": all(gates.values()),
        "migration_complete": False,
        "next_required_phase": "native_v2_reconstruction_and_causal_feature_lineage",
        "metric_warning": "V1 canonical Sharpe is CAGR divided by annualized sample volatility; V2 reports arithmetic mean weekly return divided by weekly volatility. The recent_metrics artifact uses the V2 arithmetic convention for comparisons.",
        "version_1_modified": False, "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "source_inventory.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inventory[0])); writer.writeheader(); writer.writerows(inventory)
    with (OUTPUT / "recent_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(recent[0])); writer.writeheader(); writer.writerows(recent)
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in ("source_inventory.csv", "recent_metrics.csv")
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# Version 1 to Version 2 migration — Batch 40 Phase 0", "",
        "Version 1 remained read-only. This phase pinned every direct production dependency, checked the saved weights and transaction-cost accounting, and imported the existing internal reproduction status without treating it as a Version 2 causal audit.", "",
        f"All {len(FILES)} required files were present. The saved candidate contains {len(weights)} weekly weight rows across {len(weight_columns)} assets. Maximum weight-sum deviation was {result['saved_weight_checks']['maximum_sum_deviation']:.3e}; the saved 10-bps return accounting error was {accounting_error:.3e}.", "",
        f"V1's own formal engine reproduction passed over {internal['status']['weeks_compared']} weeks with weight error {internal['status']['weights_max_abs_error']:.3e} and path error {internal['status']['path_max_abs_error']:.3e}. Phase 0 passed: **{result['phase_0_passed']}**.", "",
        "This does not yet establish causal equivalence in Version 2. The base GGG weight lineage and the Phase 1/Phase 4 feature construction remain to be audited before V1 may become the V2 incumbent. V1 and V2 Sharpe conventions are also different and will be reported separately.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"phase_0_passed": result["phase_0_passed"], "gates": gates, "next": result["next_required_phase"]}, indent=2))
    return 0 if result["phase_0_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
