#!/usr/bin/env python3
"""Evaluate one fixed defensive Markov-state scaler on the frozen v4 strategy."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import performance_metrics  # noqa: E402
from src.systematic_trader.markov_regime import (  # noqa: E402
    causal_stress_probabilities,
    fit_two_state_gaussian_markov,
    scaled_returns,
)


CONFIG = ROOT / "config/formal_markov_regime_scaling_v1.json"
OUTPUT = ROOT / "evidence/formal_markov_regime_scaling_v1"


def _metrics(values: list[float]) -> dict[str, int | float]:
    return performance_metrics(values).to_dict()


def build() -> tuple[dict[str, object], list[dict[str, object]]]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    source = ROOT / str(config["source_returns"])
    with source.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    dates = [str(row["realization_date"]) for row in rows]
    gross = [float(row["gross_return"]) for row in rows]
    turnover = [float(row["turnover"]) for row in rows]
    development_indices = [index for index, day in enumerate(dates) if day <= config["development_end"]]
    if not development_indices or development_indices != list(range(len(development_indices))):
        raise ValueError("development window must be a non-empty prefix")
    model = fit_two_state_gaussian_markov(
        [gross[index] for index in development_indices],
        iterations=int(config["fit_iterations"]),
        transition_persistence=float(config["initial_transition_persistence"]),
    )
    probabilities = causal_stress_probabilities(gross, model)
    cost_results: dict[str, object] = {}
    primary_rows: list[dict[str, object]] = []
    primary_cost = float(config["primary_cost_bps"])
    for cost in config["cost_grid_bps"]:
        baseline = [value - turn * float(cost) / 10000.0 for value, turn in zip(gross, turnover)]
        candidate, exposures = scaled_returns(
            gross, turnover, probabilities, cost_bps=float(cost),
            minimum_exposure=float(config["stress_minimum_exposure"]),
        )
        locked = [index for index, day in enumerate(dates) if day >= config["locked_evaluation_start"]]
        cost_results[str(cost)] = {
            "full_baseline": _metrics(baseline),
            "full_scaled": _metrics(candidate),
            "locked_baseline": _metrics([baseline[index] for index in locked]),
            "locked_scaled": _metrics([candidate[index] for index in locked]),
        }
        if float(cost) == primary_cost:
            primary_rows = [
                {
                    "realization_date": day,
                    "gross_return": raw,
                    "turnover": turn,
                    "stress_probability_known_before_return": probability,
                    "exposure": exposure,
                    "baseline_return": base,
                    "scaled_return": scaled,
                }
                for day, raw, turn, probability, exposure, base, scaled in zip(
                    dates, gross, turnover, probabilities, exposures, baseline, candidate
                )
            ]
    primary = cost_results[str(int(primary_cost)) if primary_cost.is_integer() else str(primary_cost)]
    locked_base = primary["locked_baseline"]
    locked_scaled = primary["locked_scaled"]
    drawdown_improvement = float(locked_scaled["max_drawdown"]) - float(locked_base["max_drawdown"])
    annual_return_drag = float(locked_base["annual_return"]) - float(locked_scaled["annual_return"])
    gates = config["promotion_gates"]
    historical_economic_gate = (
        drawdown_improvement >= float(gates["locked_period_max_drawdown_improvement_minimum"])
        and annual_return_drag <= float(gates["locked_period_annual_return_drag_maximum"])
    )

    def period(start: str, end: str) -> dict[str, object]:
        selected = [row for row in primary_rows if start <= str(row["realization_date"]) <= end]
        return {
            "start": start,
            "end": end,
            "observations": len(selected),
            "baseline": _metrics([float(row["baseline_return"]) for row in selected]),
            "scaled": _metrics([float(row["scaled_return"]) for row in selected]),
        }

    result = {
        "program": config["program"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "model": {
            "initial": model.initial,
            "transition": model.transition,
            "means": model.means,
            "variances": model.variances,
            "stress_state": model.stress_state,
        },
        "development_observations": len(development_indices),
        "locked_observations": sum(day >= config["locked_evaluation_start"] for day in dates),
        "cost_results": cost_results,
        "primary_locked_drawdown_improvement": drawdown_improvement,
        "primary_locked_annual_return_drag": annual_return_drag,
        "historical_economic_gate_pass": historical_economic_gate,
        "regime_diagnostics_not_untouched": {
            "2008_2009": period("2008-01-01", "2009-12-31"),
            "2020": period("2020-01-01", "2020-12-31"),
            "recent_2023_present": period("2023-01-01", "9999-12-31"),
        },
        "selection_contaminated": False,
        "promotion_authorized": False,
        "live_trading_enabled": False,
        "verdict": "RESEARCH_ONLY_FORWARD_REQUIRED" if historical_economic_gate else "REJECTED_HISTORICAL_GATE",
        "limitations": [
            "The model was fit once on 2005-2015 and evaluated from 2016, but the project owner has already seen the entire history.",
            "The 2008-2009 diagnostic lies inside model development and cannot support promotion.",
            "A two-state Gaussian return model is a deliberately simple defensive scaler, not a regime-transition alpha model.",
            "No untouched forward observation is created by this retrospective run.",
        ],
    }
    return result, primary_rows


def main() -> int:
    result, path_rows = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / "primary_path.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(path_rows[0]))
        writer.writeheader()
        writer.writerows(path_rows)
    result["primary_path_sha256"] = hashlib.sha256((OUTPUT / "primary_path.csv").read_bytes()).hexdigest()
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = (
        "# Formal Markov Regime Scaling V1\n\n"
        f"Verdict: **{result['verdict']}**. At the primary 50 bps cost, locked-period "
        f"drawdown changed by {result['primary_locked_drawdown_improvement'] * 100:.2f} percentage points "
        f"and annual-return drag was {result['primary_locked_annual_return_drag'] * 100:.2f} percentage points.\n\n"
        "This is a fixed, past-only defensive exposure test. It does not authorize promotion or live trading.\n"
    )
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "verdict", "primary_locked_drawdown_improvement", "primary_locked_annual_return_drag",
        "historical_economic_gate_pass", "promotion_authorized", "live_trading_enabled",
    )}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
