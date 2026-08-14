#!/usr/bin/env python3
"""Evaluate the predeclared Batch 53 execution-aware GGG candidates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_execution import asset_deadband, band_execution, scheduled_execution, volatility_adaptive_band
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/frozen_ggg_inputs_v1"
MANIFEST = SOURCE / "manifest.json"
PROGRAM = ROOT / "config/ggg_execution_aware_program_v1.json"
MODULE = ROOT / "src/systematic_trader/ggg_execution.py"
OUTPUT = ROOT / "evidence/ggg_execution_aware_batch_53"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frame_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    index = left.index.intersection(right.index); columns = left.columns.intersection(right.columns)
    values = (left.loc[index, columns] - right.loc[index, columns]).abs().to_numpy()
    return float(np.nanmax(values)) if values.size else float("inf")


def verify_manifest() -> bool:
    descriptor = json.loads(MANIFEST.read_text())
    return all(sha256(SOURCE / relative) == expected for relative, expected in descriptor["files"].items())


def metrics(path: pd.DataFrame) -> dict[str, object]:
    returns = pd.to_numeric(path.net_return, errors="coerce").dropna()
    turnover = pd.to_numeric(path.turnover, errors="coerce").reindex(returns.index)
    wealth = (1.0 + returns).cumprod(); years = len(returns) / 52.0
    arithmetic = float(returns.mean() * 52.0); volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    downside = float(np.sqrt(returns.clip(upper=0.0).pow(2).mean()) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "arithmetic_ann_return": arithmetic,
        "ann_vol": volatility, "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan,
        "sortino_zero_target": arithmetic / downside if downside else np.nan,
        "max_drawdown": float(drawdown.min()), "annual_one_way_turnover": float(turnover.mean() * 52.0),
        "total_modeled_cost": float(path.cost.reindex(returns.index).sum()),
    }


def transform(baseline: pd.DataFrame, prices: pd.DataFrame, spec: dict) -> pd.DataFrame:
    kind = spec["kind"]
    if kind == "scheduled":
        return scheduled_execution(baseline, cadence_weeks=int(spec["cadence_weeks"]))
    if kind == "monthly":
        return scheduled_execution(baseline, monthly=True)
    if kind == "monthly_emergency":
        return scheduled_execution(baseline, monthly=True, emergency_turnover=float(spec["emergency_turnover"]), emergency_cash_change=float(spec["emergency_cash_change"]))
    if kind == "asset_deadband":
        return asset_deadband(baseline, float(spec["asset_change_threshold"]))
    if kind == "asymmetric_band":
        return band_execution(baseline, entry_band=float(spec["risk_entry_band"]), exit_band=float(spec["risk_exit_band"]))
    if kind == "volatility_adaptive_band":
        return volatility_adaptive_band(baseline, prices, calm_band=float(spec["calm_band"]), stress_band=float(spec["stress_band"]), spy_volatility_threshold=float(spec["spy_volatility_threshold"]), lookback_weeks=int(spec["lookback_weeks"]))
    if kind == "scheduled_then_band":
        scheduled = scheduled_execution(baseline, cadence_weeks=int(spec["cadence_weeks"]))
        return band_execution(scheduled, entry_band=float(spec["band"]), exit_band=float(spec["band"]))
    if kind == "monthly_emergency_then_band":
        scheduled = scheduled_execution(baseline, monthly=True, emergency_turnover=float(spec["emergency_turnover"]), emergency_cash_change=float(spec["emergency_cash_change"]))
        return band_execution(scheduled, entry_band=float(spec["band"]), exit_band=float(spec["band"]))
    raise ValueError(f"unknown execution kind: {kind}")


def build_candidates(prices: pd.DataFrame, program: dict) -> dict[str, pd.DataFrame]:
    baseline = run_from_artifacts(SOURCE, prices_override=prices, causal_training=True).stages["final_etf_weights"]
    candidates = {
        "benchmark": baseline,
        "batch52_buffer_band_025": band_execution(baseline, entry_band=0.025, exit_band=0.025),
    }
    if len(program["candidates"]) != int(program["selection_budget"]):
        raise ValueError("candidate count does not equal predeclared selection budget")
    for name, spec in program["candidates"].items():
        candidates[name] = transform(baseline, prices, spec).reindex_like(baseline).fillna(0.0)
    return candidates


def windows(path: pd.DataFrame, secondary_start: str) -> dict[str, pd.DataFrame]:
    return {
        "full": path,
        "recent_3y": path.loc[path.index >= path.index.max() - pd.DateOffset(years=3)],
        "post_2024": path.loc[path.index >= pd.Timestamp(secondary_start)],
    }


def main() -> int:
    program = json.loads(PROGRAM.read_text()); manifest_verified = verify_manifest()
    prices = read_dated_csv(SOURCE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    candidates = build_candidates(prices, program); repeated = build_candidates(prices, program)
    determinism = pd.DataFrame([
        {"candidate": name, "first_hash": frame_hash(candidates[name]), "second_hash": frame_hash(repeated[name]), "hash_equal": frame_hash(candidates[name]) == frame_hash(repeated[name]), "maximum_difference": frame_difference(candidates[name], repeated[name])}
        for name in program["candidates"]
    ])
    performance_rows = []
    for name, weights in candidates.items():
        for cost in program["cost_bps"]:
            path = portfolio_path(weights, forward, float(cost))
            for window, subset in windows(path, program["secondary_window_start"]).items():
                performance_rows.append({"candidate": name, "cost_bps": cost, "window": window, **metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    prefix_rows = []
    for cutoff_text in program["prefix_cutoffs"]:
        cutoff = pd.Timestamp(cutoff_text); location = prices.index.get_loc(cutoff) + 1
        shocked = prices.copy(); shocked.iloc[location] *= pd.Series([1.4 if i % 2 == 0 else 0.6 for i in range(len(prices.columns))], index=prices.columns)
        alternatives = build_candidates(shocked, program)
        for name in program["candidates"]:
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "shocked_date": str(prices.index[location].date()), "maximum_prefix_difference": frame_difference(candidates[name].loc[:cutoff], alternatives[name].loc[:cutoff])})
    prefix = pd.DataFrame(prefix_rows)

    def row(candidate: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.candidate == candidate) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    benchmark = {(window, cost): row("benchmark", window, cost) for window in ("full", "recent_3y", "post_2024") for cost in program["cost_bps"]}
    gates = program["qualification_gates"]; qualification_rows = []
    for name in program["candidates"]:
        recent = row(name, "recent_3y", 50); recent100 = row(name, "recent_3y", 100)
        post = row(name, "post_2024", 50); full = row(name, "full", 50)
        maximum_prefix = float(prefix.loc[prefix.candidate == name, "maximum_prefix_difference"].max())
        checks = {
            "recent_cagr_gate": float(recent.cagr - benchmark[("recent_3y", 50)].cagr) >= float(gates["minimum_recent_3y_50bps_cagr_improvement"]),
            "post_2024_gate": float(post.cagr - benchmark[("post_2024", 50)].cagr) >= float(gates["minimum_post_2024_50bps_cagr_improvement"]),
            "full_cagr_gate": float(full.cagr - benchmark[("full", 50)].cagr) >= -float(gates["maximum_full_50bps_cagr_degradation"]),
            "recent_drawdown_gate": abs(float(recent.max_drawdown)) <= float(gates["maximum_recent_3y_drawdown_magnitude"]),
            "cost_stress_gate": float(recent100.cagr - benchmark[("recent_3y", 100)].cagr) >= float(gates["minimum_recent_3y_100bps_cagr_improvement"]),
            "prefix_gate": maximum_prefix <= float(gates["maximum_prefix_absolute_difference"]),
            "determinism_gate": bool(determinism.loc[determinism.candidate == name, "hash_equal"].all()),
            "manifest_gate": manifest_verified,
        }
        qualification_rows.append({
            "candidate": name, "recent_3y_50bps_cagr": recent.cagr,
            "recent_cagr_improvement": recent.cagr - benchmark[("recent_3y", 50)].cagr,
            "post_2024_cagr_improvement": post.cagr - benchmark[("post_2024", 50)].cagr,
            "full_cagr_improvement": full.cagr - benchmark[("full", 50)].cagr,
            "recent_3y_100bps_cagr_improvement": recent100.cagr - benchmark[("recent_3y", 100)].cagr,
            "recent_3y_50bps_sharpe": recent.sharpe_zero_rf, "recent_3y_50bps_max_drawdown": recent.max_drawdown,
            "recent_3y_annual_turnover": recent.annual_one_way_turnover,
            "recent_turnover_reduction": benchmark[("recent_3y", 50)].annual_one_way_turnover - recent.annual_one_way_turnover,
            "maximum_prefix_difference": maximum_prefix, **checks,
            "qualified_for_forward_challenger": all(checks.values()),
        })
    qualification = pd.DataFrame(qualification_rows).sort_values(["qualified_for_forward_challenger", "recent_3y_50bps_cagr", "candidate"], ascending=[False, False, True])
    shortlist = qualification.loc[qualification.qualified_for_forward_challenger, "candidate"].tolist(); selected = shortlist[0] if shortlist else None
    best_name = str(qualification.iloc[0].candidate); saved = candidates[selected or best_name].copy(); saved.index.name = "Date"

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False); qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False); determinism.to_csv(OUTPUT / "determinism.csv", index=False)
    saved.to_csv(OUTPUT / ("selected_forward_challenger_weights.csv" if selected else "best_unqualified_candidate_weights.csv"))
    comparator = {key: row("batch52_buffer_band_025", "recent_3y", 50)[key] for key in ("cagr", "sharpe_zero_rf", "max_drawdown", "annual_one_way_turnover")}
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 53, "program": program["program"],
        "program_sha256": sha256(PROGRAM), "module_sha256": sha256(MODULE), "manifest_sha256": sha256(MANIFEST),
        "frozen_source_hashes_verified": manifest_verified, "selection_budget": program["selection_budget"],
        "candidates_evaluated": len(program["candidates"]), "audit_comparator_recent_3y_50bps": comparator,
        "research_shortlist": shortlist, "selected_forward_challenger": selected,
        "best_candidate": best_name, "maximum_prefix_difference": float(prefix.maximum_prefix_difference.max()),
        "all_deterministic": bool(determinism.hash_equal.all()),
        "decision": "freeze_selected_research_challenger_pending_forward_engine" if selected else "no_candidate_qualified_no_forward_lock",
        "forward_clock_started": False,
        "forward_clock_blocker": "portable post-April causal GGG upstream engine is not yet available" if selected else "no candidate passed every predeclared gate",
        "promoted_to_production": False, "live_trading_enabled": False,
    }
    artifact_names = ["performance.csv", "qualification.csv", "prefix_invariance.csv", "determinism.csv", "selected_forward_challenger_weights.csv" if selected else "best_unqualified_candidate_weights.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifact_names}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    best = qualification.iloc[0]
    report = [
        "# Execution-aware causal GGG — Batch 53", "",
        f"Ten execution rules were fixed before evaluation. Frozen hashes verified: **{manifest_verified}**; all repeated histories deterministic: **{result['all_deterministic']}**; maximum future-shock prefix difference: **{result['maximum_prefix_difference']:.3e}**.", "",
        f"The best candidate was `{best.candidate}` with recent-three-year 50-bps CAGR **{best.recent_3y_50bps_cagr:.2%}**, improvement **{best.recent_cagr_improvement:.2%}**, Sharpe **{best.recent_3y_50bps_sharpe:.3f}**, drawdown **{best.recent_3y_50bps_max_drawdown:.2%}**, and annual turnover **{best.recent_3y_annual_turnover:.2f}x**.", "",
        f"Qualifying shortlist: **{', '.join(shortlist) if shortlist else 'none'}**. No historical result enables live trading.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report))
    print(json.dumps({"best": best_name, "best_recent_3y_50bps_cagr": best.recent_3y_50bps_cagr, "benchmark_recent_3y_50bps_cagr": benchmark[("recent_3y", 50)].cagr, "shortlist": shortlist, "selected": selected, "maximum_prefix_difference": result["maximum_prefix_difference"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
