#!/usr/bin/env python3
"""Validate the fixed 20% residual-momentum sleeve without promoting it."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_real_tournament_v2 import build_family_weights
from systematic_trader import sec_tournament_rehearsal as engine

CONFIG = ROOT / "config/sec_residual_controlled_sleeve_v1.json"
PANEL = ROOT / "data/sec_broad_research_panel_v2"
TOURNAMENT = ROOT / "evidence/sec_return_improvement_tournament_v2/final_result.json"
OUTPUT = ROOT / "evidence/sec_residual_controlled_sleeve_v1"
CONTROL_ROOT = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blend(control: pd.Series, sleeve: pd.Series, weight: float) -> pd.Series:
    joined = pd.concat([control.rename("control"), sleeve.rename("sleeve")], axis=1).fillna(0.0)
    return (1.0 - float(weight)) * joined.control + float(weight) * joined.sleeve


def levered(returns: pd.Series, multiplier: float, financing_rate: float) -> pd.Series:
    borrowing = max(0.0, float(multiplier) - 1.0)
    return float(multiplier) * returns - borrowing * float(financing_rate) / 52.0


def main() -> int:
    if not TOURNAMENT.exists():
        raise RuntimeError("sealed tournament result is required")
    config = json.loads(CONFIG.read_text())
    final = json.loads(TOURNAMENT.read_text())
    if final.get("qualified_families"):
        raise RuntimeError("controlled-sleeve diagnostic is only for the no-winner outcome")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "result.json"
    if result_path.exists():
        raise RuntimeError("controlled-sleeve validation is one-shot")
    sealed_files = [
        CONFIG,
        Path(__file__),
        ROOT / "src/systematic_trader/sec_real_tournament_v2.py",
        ROOT / "src/systematic_trader/sec_return_improvement.py",
        ROOT / "src/systematic_trader/sec_tournament_rehearsal.py",
        PANEL / "manifest.json",
        TOURNAMENT,
    ]
    seal = {
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "performance_evaluated_at_seal": False,
        "sealed_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sealed_files},
    }
    (OUTPUT / "execution_seal.json").write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n")

    panel = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    weekly = pd.read_csv(PANEL / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    program = json.loads((ROOT / "config/sec_return_improvement_program_v1.json").read_text())
    weights, _ = build_family_weights(panel, program)
    residual_weights = weights["residual_momentum"]
    sleeve_weight = float(config["residual_sleeve_weight"])
    paths: dict[tuple[int, int, str], pd.Series] = {}
    rows = []
    for cost in config["cost_bps"]:
        control_frame = pd.read_csv(CONTROL_ROOT / f"best_path__base__{int(cost)}bps.csv", parse_dates=["Date"]).set_index("Date")
        control = control_frame.net_return
        control.index = pd.to_datetime(control.index, utc=True)
        for delay in config["residual_execution_delays_weeks"]:
            residual = engine.portfolio_path(residual_weights, weekly, int(cost), int(delay))[0]
            candidate = blend(control.reindex(weekly.index).fillna(0.0), residual, sleeve_weight)
            paths[(int(cost), int(delay), "base")] = candidate
            for window, values in {"full": candidate, "recent_52w": candidate.tail(52), "recent_104w": candidate.tail(104)}.items():
                rows.append({"cost_bps": int(cost), "residual_delay_weeks": int(delay), "scenario": "base", "window": window, **engine.metrics(values)})
        adverse = engine.portfolio_path(residual_weights, weekly, int(cost), 0, "adverse_total_loss")[0]
        candidate = blend(control.reindex(weekly.index).fillna(0.0), adverse, sleeve_weight)
        paths[(int(cost), 0, "adverse_total_loss")] = candidate
        rows.append({"cost_bps": int(cost), "residual_delay_weeks": 0, "scenario": "adverse_total_loss", "window": "recent_52w", **engine.metrics(candidate.tail(52))})
    metrics = pd.DataFrame(rows)

    primary = paths[(50, 0, "base")]
    control = pd.read_csv(CONTROL_ROOT / "best_path__base__50bps.csv", parse_dates=["Date"]).set_index("Date").net_return
    control.index = pd.to_datetime(control.index, utc=True)
    control = control.reindex(primary.index).fillna(0.0)
    differences = primary - control
    bootstrap_rows = []
    for block in config["bootstrap_blocks_weeks"]:
        raw = engine.bootstrap_probability(differences, int(block), int(config["bootstrap_draws"]), int(config["bootstrap_seed"]))
        adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw) * int(config["familywise_trials"])))
        bootstrap_rows.append({"block_weeks": int(block), "raw_probability_positive": raw, "familywise_adjusted_probability_positive": adjusted})
    bootstrap = pd.DataFrame(bootstrap_rows)

    rolling_rows = []
    for window in (26, 52, 104):
        share, windows = engine.rolling_share(primary, control, window)
        rolling_rows.append({"window_weeks": window, "outperformance_share": share, "completed_windows": windows})
    rolling = pd.DataFrame(rolling_rows)

    year_rows = []
    for year in sorted(set(primary.index.year)):
        candidate_year = primary[primary.index.year == year]
        control_year = control[control.index.year == year]
        year_rows.append({"year": int(year), "candidate_cagr": engine.metrics(candidate_year)["cagr"], "control_cagr": engine.metrics(control_year)["cagr"], "difference": engine.metrics(candidate_year)["cagr"] - engine.metrics(control_year)["cagr"]})
    calendar = pd.DataFrame(year_rows)

    leverage_rows = []
    for multiplier in config["leverage_multipliers"]:
        for rate in config["financing_rates"]:
            values = levered(primary, float(multiplier), float(rate))
            for window, subset in {"full": values, "recent_52w": values.tail(52)}.items():
                leverage_rows.append({"multiplier": float(multiplier), "financing_rate": float(rate), "window": window, **engine.metrics(subset)})
    leverage = pd.DataFrame(leverage_rows)

    _, contributions = engine.portfolio_path(residual_weights, weekly, 50)
    positive = contributions.sum().clip(lower=0.0)
    max_issuer_share = float(positive.max() / positive.sum()) if positive.sum() else 0.0
    recent_candidate = engine.metrics(primary.tail(52))
    recent_control = engine.metrics(control.tail(52))
    full_candidate = engine.metrics(primary)
    full_control = engine.metrics(control)
    worst_delay = min(engine.metrics(paths[(50, delay, "base")].tail(52))["cagr"] for delay in config["residual_execution_delays_weeks"])
    gates = config["gates"]
    gate_results = {
        "recent_cagr": recent_candidate["cagr"] >= recent_control["cagr"] + gates["minimum_recent_cagr_improvement"],
        "full_cagr": full_candidate["cagr"] >= full_control["cagr"] + gates["minimum_full_cagr_improvement"],
        "recent_sharpe": recent_candidate["sharpe"] >= recent_control["sharpe"] + gates["minimum_recent_sharpe_improvement"],
        "recent_drawdown": recent_candidate["max_drawdown"] >= gates["maximum_recent_drawdown"],
        "delay": worst_delay >= gates["minimum_worst_delay_recent_cagr"],
        "multiplicity": float(bootstrap.familywise_adjusted_probability_positive.min()) >= gates["minimum_familywise_adjusted_probability_positive"],
        "issuer_concentration": max_issuer_share <= gates["maximum_positive_issuer_share"],
    }
    metrics.to_csv(OUTPUT / "metrics.csv", index=False)
    bootstrap.to_csv(OUTPUT / "block_bootstrap.csv", index=False)
    rolling.to_csv(OUTPUT / "rolling_outperformance.csv", index=False)
    calendar.to_csv(OUTPUT / "calendar_years.csv", index=False)
    leverage.to_csv(OUTPUT / "leverage_stress.csv", index=False)
    primary.rename("net_return").rename_axis("Date").to_csv(OUTPUT / "candidate_path.csv")
    artifacts = ["metrics.csv", "block_bootstrap.csv", "rolling_outperformance.csv", "calendar_years.csv", "leverage_stress.csv", "candidate_path.csv"]
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_contaminated": True,
        "recent_candidate": recent_candidate,
        "recent_control": recent_control,
        "full_candidate": full_candidate,
        "full_control": full_control,
        "full_return_correlation": float(pd.concat([primary, control], axis=1).corr().iloc[0, 1]),
        "worst_delay_recent_cagr": worst_delay,
        "maximum_positive_issuer_share": max_issuer_share,
        "gate_results": gate_results,
        "all_statistical_validation_gates_passed": bool(all(gate_results.values())),
        "promotion_authorized": False,
        "required_next_step": "frozen forward observation because the sleeve weight was selected on this sample",
        "live_trading_enabled": False,
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifacts},
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
