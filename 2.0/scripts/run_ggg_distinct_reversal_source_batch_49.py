#!/usr/bin/env python3
"""Test a distinct trend-qualified reversal source and fixed GGG blends."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.trend_reversal_source import ReversalSpec, blend_with_ggg, build_reversal_weights


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/frozen_ggg_inputs_v1"
MANIFEST = SOURCE / "manifest.json"
PROGRAM = ROOT / "config/ggg_distinct_reversal_source_v1.json"
MODULE = ROOT / "src/systematic_trader/trend_reversal_source.py"
OUTPUT = ROOT / "evidence/ggg_distinct_reversal_source_batch_49"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frame_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    index = left.index.intersection(right.index); columns = left.columns.intersection(right.columns)
    values = (left.loc[index, columns] - right.loc[index, columns]).abs().to_numpy()
    return float(np.nanmax(values)) if values.size else float("inf")


def verify_manifest() -> bool:
    manifest = json.loads(MANIFEST.read_text())
    return all(sha256(SOURCE / relative) == expected for relative, expected in manifest["files"].items())


def metrics(series: pd.Series) -> dict:
    returns = pd.to_numeric(series, errors="coerce").dropna(); wealth = (1.0 + returns).cumprod(); years = len(returns) / 52.0
    arithmetic = float(returns.mean() * 52.0); volatility = float(returns.std(ddof=1) * np.sqrt(52.0)); drawdown = wealth / wealth.cummax() - 1.0
    return {"weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()), "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "arithmetic_ann_return": arithmetic, "ann_vol": volatility, "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan, "max_drawdown": float(drawdown.min())}


def correlation(left: pd.Series, right: pd.Series) -> float:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    return float(aligned["left"].corr(aligned["right"]))


def build_all(prices: pd.DataFrame, baseline: pd.DataFrame, program: dict) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    sources = {name: build_reversal_weights(prices, program["formula"]["universe"], ReversalSpec(**values)) for name, values in program["source_variants"].items()}
    candidates = {"benchmark": baseline}
    for name, definition in program["candidates"].items():
        source = sources[definition["source"]]
        candidates[name] = source if definition["kind"] == "standalone" else blend_with_ggg(baseline, source, float(definition["blend_weight"]))
    return sources, candidates


def main() -> int:
    program = json.loads(PROGRAM.read_text())
    if len(program["candidates"]) != program["selection_budget"]:
        raise ValueError("Candidate count does not match predeclared budget")
    manifest_verified = verify_manifest()
    prices = read_dated_csv(SOURCE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    ggg = run_from_artifacts(SOURCE, causal_training=True).stages["final_etf_weights"]
    sources, candidates = build_all(prices, ggg, program)
    deterministic_rows = []
    _, second_candidates = build_all(prices, ggg, program)
    for name in program["candidates"]:
        deterministic_rows.append({"candidate": name, "first_hash": frame_hash(candidates[name]), "second_hash": frame_hash(second_candidates[name]), "hash_equal": frame_hash(candidates[name]) == frame_hash(second_candidates[name]), "maximum_difference": frame_difference(candidates[name], second_candidates[name])})
    performance_rows = []; return_series = {}
    for name, weights in candidates.items():
        for cost_bps in program["cost_bps"]:
            path = portfolio_path(weights, forward, float(cost_bps))
            if cost_bps == 50:
                return_series[name] = path["net_return"]
            windows = {"full": path["net_return"], "recent_3y": path.loc[path.index >= path.index.max() - pd.DateOffset(years=3), "net_return"], "post_2024": path.loc[path.index >= pd.Timestamp(program["secondary_window_start"]), "net_return"]}
            for window, returns in windows.items():
                performance_rows.append({"candidate": name, "cost_bps": cost_bps, "window": window, **metrics(returns)})
    performance = pd.DataFrame(performance_rows)
    correlation_rows = []
    for source_name in sources:
        candidate_name = f"{source_name}_standalone"
        correlation_rows.append({"source": source_name, "candidate": candidate_name, "full_correlation_to_ggg_50bps": correlation(return_series[candidate_name], return_series["benchmark"]), "recent_3y_correlation_to_ggg_50bps": correlation(return_series[candidate_name].loc[return_series[candidate_name].index >= return_series[candidate_name].index.max() - pd.DateOffset(years=3)], return_series["benchmark"])})
    correlations = pd.DataFrame(correlation_rows)
    prefix_rows = []
    for cutoff_text in program["prefix_cutoffs"]:
        cutoff = pd.Timestamp(cutoff_text); next_location = prices.index.get_loc(cutoff) + 1
        shocked = prices.copy(); shocked.iloc[next_location] *= pd.Series([1.4 if i % 2 == 0 else 0.6 for i in range(len(prices.columns))], index=prices.columns)
        shocked_ggg = run_from_artifacts(SOURCE, prices_override=shocked, causal_training=True).stages["final_etf_weights"]
        _, shocked_candidates = build_all(shocked, shocked_ggg, program)
        for name in program["candidates"]:
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "shocked_date": str(prices.index[next_location].date()), "maximum_prefix_difference": frame_difference(candidates[name].loc[:cutoff], shocked_candidates[name].loc[:cutoff])})
    prefix = pd.DataFrame(prefix_rows); deterministic = pd.DataFrame(deterministic_rows)

    def row(candidate: str, window: str, cost: int) -> pd.Series:
        return performance[(performance["candidate"] == candidate) & (performance["window"] == window) & (performance["cost_bps"] == cost)].iloc[0]

    standalone_pass = {}
    source_gate_rows = []
    common = program["common_gates"]; standalone_gates = program["standalone_gates"]
    for source_name in program["source_variants"]:
        candidate = f"{source_name}_standalone"; recent = row(candidate, "recent_3y", 50); full100 = row(candidate, "full", 100)
        corr = float(correlations.loc[correlations["source"] == source_name, "full_correlation_to_ggg_50bps"].iloc[0]); max_prefix = float(prefix.loc[prefix["candidate"] == candidate, "maximum_prefix_difference"].max())
        checks = {"recent_return_gate": recent["cagr"] >= standalone_gates["minimum_recent_3y_50bps_cagr"], "full_100bps_gate": full100["cagr"] >= standalone_gates["minimum_full_100bps_cagr"], "correlation_gate": abs(corr) <= standalone_gates["maximum_abs_correlation_to_ggg"], "drawdown_gate": abs(recent["max_drawdown"]) <= standalone_gates["maximum_recent_3y_drawdown_magnitude"], "prefix_gate": max_prefix <= common["maximum_prefix_absolute_difference"], "determinism_gate": bool(deterministic.loc[deterministic["candidate"] == candidate, "hash_equal"].all()), "manifest_gate": manifest_verified}
        standalone_pass[source_name] = all(checks.values())
        source_gate_rows.append({"source": source_name, "candidate": candidate, "recent_3y_50bps_cagr": recent["cagr"], "full_100bps_cagr": full100["cagr"], "full_correlation_to_ggg": corr, "recent_3y_50bps_max_drawdown": recent["max_drawdown"], **checks, "standalone_qualified": all(checks.values())})
    source_qualification = pd.DataFrame(source_gate_rows)
    benchmark = {window: row("benchmark", window, 50) for window in ("full", "recent_3y", "post_2024")}; blend_gates = program["blend_gates"]
    blend_rows = []
    for name, definition in program["candidates"].items():
        if definition["kind"] != "blend": continue
        observed = {window: row(name, window, 50) for window in benchmark}; max_prefix = float(prefix.loc[prefix["candidate"] == name, "maximum_prefix_difference"].max())
        checks = {"parent_source_gate": standalone_pass[definition["source"]], "recent_cagr_gate": observed["recent_3y"]["cagr"] - benchmark["recent_3y"]["cagr"] >= blend_gates["minimum_recent_3y_50bps_cagr_improvement"], "post_2024_gate": observed["post_2024"]["cagr"] - benchmark["post_2024"]["cagr"] >= blend_gates["minimum_post_2024_50bps_cagr_improvement"], "full_cagr_gate": observed["full"]["cagr"] - benchmark["full"]["cagr"] >= -blend_gates["maximum_full_50bps_cagr_degradation"], "drawdown_gate": abs(observed["recent_3y"]["max_drawdown"]) <= blend_gates["maximum_recent_3y_drawdown_magnitude"], "prefix_gate": max_prefix <= common["maximum_prefix_absolute_difference"], "determinism_gate": bool(deterministic.loc[deterministic["candidate"] == name, "hash_equal"].all()), "manifest_gate": manifest_verified}
        blend_rows.append({"candidate": name, "source": definition["source"], "blend_weight": definition["blend_weight"], "recent_3y_50bps_cagr": observed["recent_3y"]["cagr"], "recent_cagr_improvement": observed["recent_3y"]["cagr"] - benchmark["recent_3y"]["cagr"], "post_2024_cagr_improvement": observed["post_2024"]["cagr"] - benchmark["post_2024"]["cagr"], "full_cagr_improvement": observed["full"]["cagr"] - benchmark["full"]["cagr"], "recent_3y_50bps_sharpe": observed["recent_3y"]["sharpe_zero_rf"], "recent_3y_50bps_max_drawdown": observed["recent_3y"]["max_drawdown"], **checks, "blend_qualified": all(checks.values())})
    blend_qualification = pd.DataFrame(blend_rows).sort_values("recent_3y_50bps_cagr", ascending=False)
    shortlist = blend_qualification.loc[blend_qualification["blend_qualified"], "candidate"].tolist()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False); correlations.to_csv(OUTPUT / "correlations.csv", index=False); prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False); deterministic.to_csv(OUTPUT / "determinism.csv", index=False); source_qualification.to_csv(OUTPUT / "source_qualification.csv", index=False); blend_qualification.to_csv(OUTPUT / "blend_qualification.csv", index=False)
    best = blend_qualification.iloc[0]
    result = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "program": program["program"], "program_sha256": sha256(PROGRAM), "module_sha256": sha256(MODULE), "manifest_sha256": sha256(MANIFEST), "snapshot_hashes_verified": manifest_verified, "candidates_evaluated": len(program["candidates"]), "standalone_sources_qualified": [name for name, passed in standalone_pass.items() if passed], "research_blend_shortlist": shortlist, "maximum_prefix_difference": float(prefix["maximum_prefix_difference"].max()), "all_deterministic": bool(deterministic["hash_equal"].all()), "benchmark_recent_3y_50bps_cagr": benchmark["recent_3y"]["cagr"], "decision": "retain_qualified_distinct_source_blends" if shortlist else "distinct_reversal_source_rejected", "promoted_to_production": False, "live_trading_enabled": False}
    artifacts = ["performance.csv", "correlations.csv", "prefix_invariance.csv", "determinism.csv", "source_qualification.csv", "blend_qualification.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifacts}; (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = ["# Distinct trend-qualified reversal source — Batch 49", "", f"Two standalone sources and four fixed GGG blends were tested. Snapshot hashes verified: **{manifest_verified}**; all deterministic: **{result['all_deterministic']}**; maximum prefix difference: {result['maximum_prefix_difference']:.3e}.", "", f"Qualified standalone sources: {', '.join(result['standalone_sources_qualified']) if result['standalone_sources_qualified'] else 'none'}. Best blend `{best['candidate']}` produced recent-three-year 50-bps CAGR {best['recent_3y_50bps_cagr']:.2%} versus benchmark {benchmark['recent_3y']['cagr']:.2%}, an improvement of {best['recent_cagr_improvement']:.2%}.", "", f"Qualified blend shortlist: {', '.join(shortlist) if shortlist else 'none'}. No production promotion is permitted from observed history.", ""]
    (OUTPUT / "report.md").write_text("\n".join(report)); print(json.dumps({"standalone_qualified": result["standalone_sources_qualified"], "shortlist": shortlist, "best_blend": best["candidate"], "best_recent_3y_50bps_cagr": best["recent_3y_50bps_cagr"], "benchmark": benchmark["recent_3y"]["cagr"]}, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
