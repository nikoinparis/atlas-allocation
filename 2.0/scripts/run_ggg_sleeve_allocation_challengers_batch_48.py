#!/usr/bin/env python3
"""Run the six predeclared causal GGG sleeve-allocation challengers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import SLEEVES, next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.ggg_sleeve_challengers import SleeveTiltSpec, apply_sleeve_tilt


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/frozen_ggg_inputs_v1"
MANIFEST = SOURCE / "manifest.json"
PROGRAM = ROOT / "config/ggg_sleeve_allocation_challengers_v1.json"
MODULE = ROOT / "src/systematic_trader/ggg_sleeve_challengers.py"
OUTPUT = ROOT / "evidence/ggg_sleeve_allocation_challengers_batch_48"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frame_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    index = left.index.intersection(right.index)
    columns = left.columns.intersection(right.columns)
    values = (left.loc[index, columns] - right.loc[index, columns]).abs().to_numpy()
    return float(np.nanmax(values)) if values.size else float("inf")


def verify_manifest() -> bool:
    manifest = json.loads(MANIFEST.read_text())
    return all(sha256(SOURCE / relative) == expected for relative, expected in manifest["files"].items())


def metrics(series: pd.Series) -> dict:
    returns = pd.to_numeric(series, errors="coerce").dropna()
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    arithmetic = float(returns.mean() * 52.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {"weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()), "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "arithmetic_ann_return": arithmetic, "ann_vol": volatility, "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan, "max_drawdown": float(drawdown.min())}


def positions(result, source: Path, prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    layer2a = source / "data/03_layer2a_strategy_logic"
    output = {
        name: read_dated_csv(layer2a / f"strategy_positions_{name}.csv").reindex(index=prices.index, columns=prices.columns).fillna(0.0)
        for name in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "taa_10m_sma"]
    }
    output["composite_regime_offense_component"] = result.component_positions["offense"]
    output["composite_regime_defense_component"] = result.component_positions["defense"]
    return output


def build_candidates(result, prices: pd.DataFrame, specs: dict) -> tuple[dict[str, pd.DataFrame], list[dict]]:
    sleeve_positions = positions(result, SOURCE, prices)
    candidates = {"benchmark": result.stages["final_etf_weights"]}
    deterministic = []
    for name, values in specs.items():
        spec = SleeveTiltSpec(**values)
        _, first = apply_sleeve_tilt(result.stages["final_sleeve_weights"], result.sleeve_return_panel, sleeve_positions, list(prices.columns), spec)
        _, second = apply_sleeve_tilt(result.stages["final_sleeve_weights"], result.sleeve_return_panel, sleeve_positions, list(prices.columns), spec)
        candidates[name] = first
        deterministic.append({"candidate": name, "first_hash": frame_hash(first), "second_hash": frame_hash(second), "hash_equal": frame_hash(first) == frame_hash(second), "maximum_difference": frame_difference(first, second)})
    return candidates, deterministic


def main() -> int:
    program = json.loads(PROGRAM.read_text())
    if len(program["challengers"]) != program["selection_budget"]:
        raise ValueError("Challenger count exceeds the predeclared budget")
    manifest_verified = verify_manifest()
    prices = read_dated_csv(SOURCE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    baseline_result = run_from_artifacts(SOURCE, causal_training=True)
    candidates, deterministic_rows = build_candidates(baseline_result, prices, program["challengers"])
    performance_rows = []
    for name, weights in candidates.items():
        for cost_bps in program["cost_bps"]:
            path = portfolio_path(weights, forward, float(cost_bps))
            windows = {"full": path["net_return"], "recent_3y": path.loc[path.index >= path.index.max() - pd.DateOffset(years=3), "net_return"], "post_2024": path.loc[path.index >= pd.Timestamp(program["secondary_window_start"]), "net_return"]}
            for window, returns in windows.items():
                performance_rows.append({"candidate": name, "cost_bps": cost_bps, "window": window, **metrics(returns)})
    performance = pd.DataFrame(performance_rows)
    prefix_rows = []
    for cutoff_text in program["prefix_cutoffs"]:
        cutoff = pd.Timestamp(cutoff_text)
        next_location = prices.index.get_loc(cutoff) + 1
        shocked = prices.copy()
        shocked.iloc[next_location] *= pd.Series([1.4 if i % 2 == 0 else 0.6 for i in range(len(prices.columns))], index=prices.columns)
        shocked_result = run_from_artifacts(SOURCE, prices_override=shocked, causal_training=True)
        shocked_candidates, _ = build_candidates(shocked_result, shocked, program["challengers"])
        for name in program["challengers"]:
            difference = frame_difference(candidates[name].loc[:cutoff], shocked_candidates[name].loc[:cutoff])
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "shocked_date": str(prices.index[next_location].date()), "maximum_prefix_difference": difference})
    prefix = pd.DataFrame(prefix_rows)
    deterministic = pd.DataFrame(deterministic_rows)

    def row(candidate: str, window: str) -> pd.Series:
        return performance[(performance["candidate"] == candidate) & (performance["cost_bps"] == 50) & (performance["window"] == window)].iloc[0]

    benchmark = {window: row("benchmark", window) for window in ("full", "recent_3y", "post_2024")}
    gates = program["qualification_gates"]
    qualification_rows = []
    for name in program["challengers"]:
        observed = {window: row(name, window) for window in benchmark}
        maximum_prefix = float(prefix.loc[prefix["candidate"] == name, "maximum_prefix_difference"].max())
        checks = {
            "recent_cagr_gate": observed["recent_3y"]["cagr"] - benchmark["recent_3y"]["cagr"] >= gates["minimum_recent_3y_50bps_cagr_improvement"],
            "post_2024_gate": observed["post_2024"]["cagr"] - benchmark["post_2024"]["cagr"] >= gates["minimum_post_2024_50bps_cagr_improvement"],
            "full_cagr_gate": observed["full"]["cagr"] - benchmark["full"]["cagr"] >= -gates["maximum_full_50bps_cagr_degradation"],
            "recent_drawdown_gate": abs(observed["recent_3y"]["max_drawdown"]) <= gates["maximum_recent_3y_drawdown_magnitude"],
            "recent_sharpe_gate": observed["recent_3y"]["sharpe_zero_rf"] >= benchmark["recent_3y"]["sharpe_zero_rf"],
            "prefix_gate": maximum_prefix <= gates["maximum_prefix_absolute_difference"],
            "determinism_gate": bool(deterministic.loc[deterministic["candidate"] == name, "hash_equal"].all()),
            "manifest_gate": manifest_verified,
        }
        qualification_rows.append({"candidate": name, "recent_3y_50bps_cagr": observed["recent_3y"]["cagr"], "recent_cagr_improvement": observed["recent_3y"]["cagr"] - benchmark["recent_3y"]["cagr"], "post_2024_cagr_improvement": observed["post_2024"]["cagr"] - benchmark["post_2024"]["cagr"], "full_cagr_improvement": observed["full"]["cagr"] - benchmark["full"]["cagr"], "recent_3y_50bps_sharpe": observed["recent_3y"]["sharpe_zero_rf"], "recent_3y_50bps_max_drawdown": observed["recent_3y"]["max_drawdown"], "maximum_prefix_difference": maximum_prefix, **checks, "qualified_for_research_shortlist": all(checks.values())})
    qualification = pd.DataFrame(qualification_rows).sort_values("recent_3y_50bps_cagr", ascending=False)
    shortlist = qualification.loc[qualification["qualified_for_research_shortlist"], "candidate"].tolist()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    deterministic.to_csv(OUTPUT / "determinism.csv", index=False)
    qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    best = qualification.iloc[0]
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "program": program["program"], "program_sha256": sha256(PROGRAM), "module_sha256": sha256(MODULE), "manifest_sha256": sha256(MANIFEST), "snapshot_hashes_verified": manifest_verified, "selection_budget": program["selection_budget"], "candidates_evaluated": len(program["challengers"]), "research_shortlist": shortlist, "maximum_prefix_difference": float(prefix["maximum_prefix_difference"].max()), "all_deterministic": bool(deterministic["hash_equal"].all()), "benchmark_recent_3y_50bps": {key: benchmark["recent_3y"][key] for key in ("cagr", "sharpe_zero_rf", "max_drawdown")}, "decision": "retain_qualified_challengers_for_locked_forward_comparison" if shortlist else "no_challenger_qualified", "promoted_to_production": False, "live_trading_enabled": False}
    artifacts = ["performance.csv", "prefix_invariance.csv", "determinism.csv", "qualification.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifacts}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = ["# Causal GGG sleeve-allocation challengers — Batch 48", "", f"Six predeclared structural sleeve tilts were tested. Snapshot hashes verified: **{manifest_verified}**. Maximum future-shock prefix difference: {result['maximum_prefix_difference']:.3e}. All deterministic: **{result['all_deterministic']}**.", "", f"The benchmark recent-three-year CAGR at 50 bps is {benchmark['recent_3y']['cagr']:.2%}. Best candidate `{best['candidate']}` produced {best['recent_3y_50bps_cagr']:.2%}, improvement {best['recent_cagr_improvement']:.2%}, Sharpe {best['recent_3y_50bps_sharpe']:.3f}, and drawdown {best['recent_3y_50bps_max_drawdown']:.2%}.", "", f"Qualified research shortlist: {', '.join(shortlist) if shortlist else 'none'}. Already-observed history cannot authorize production promotion.", ""]
    (OUTPUT / "report.md").write_text("\n".join(report))
    print(json.dumps({"shortlist": shortlist, "best": best["candidate"], "best_recent_3y_50bps_cagr": best["recent_3y_50bps_cagr"], "benchmark_recent_3y_50bps_cagr": benchmark["recent_3y"]["cagr"], "maximum_prefix_difference": result["maximum_prefix_difference"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
