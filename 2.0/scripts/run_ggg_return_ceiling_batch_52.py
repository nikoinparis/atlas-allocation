#!/usr/bin/env python3
"""Attribute GGG's return ceiling and evaluate the fixed Batch 52 challengers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts
from systematic_trader.ggg_return_expansion import breadth_risk_on, conditional_weights, redeploy_cash, turnover_transform

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/frozen_ggg_inputs_v1"
MANIFEST = SOURCE / "manifest.json"
PROGRAM = ROOT / "config/ggg_return_ceiling_program_v1.json"
MODULES = [ROOT / "src/systematic_trader/ggg_independent.py", ROOT / "src/systematic_trader/ggg_return_expansion.py"]
OUTPUT = ROOT / "evidence/ggg_return_ceiling_batch_52"


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


def metrics(path: pd.DataFrame) -> dict[str, object]:
    returns = pd.to_numeric(path["net_return"], errors="coerce").dropna()
    turnover = pd.to_numeric(path["turnover"], errors="coerce").reindex(returns.index)
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    arithmetic = float(returns.mean() * 52.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    downside = float(np.sqrt(returns.clip(upper=0.0).pow(2).mean()) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "total_return": float(wealth.iloc[-1] - 1.0), "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "arithmetic_ann_return": arithmetic, "ann_vol": volatility,
        "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan,
        "sortino_zero_target": arithmetic / downside if downside else np.nan,
        "max_drawdown": float(drawdown.min()),
        "annual_one_way_turnover": float(turnover.mean() * 52.0),
    }


def windows(path: pd.DataFrame, secondary_start: str) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full": path,
        "recent_3y": path.loc[path.index >= end - pd.DateOffset(years=3)],
        "post_2024": path.loc[path.index >= pd.Timestamp(secondary_start)],
    }


def all_specs(program: dict) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for group in ("turnover_candidates", "breadth_candidates", "volatility_candidates", "combination_candidates"):
        merged.update(program[group])
    if len(merged) != int(program["selection_budget"]):
        raise ValueError("candidate count does not equal predeclared selection budget")
    return merged


def build_candidates(prices: pd.DataFrame, program: dict) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    base_result = run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=0.12)
    baseline = base_result.stages["final_etf_weights"]
    vol_cache = {
        0.14: run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=0.14).stages["final_etf_weights"],
        0.16: run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=0.16).stages["final_etf_weights"],
    }
    formula = program["breadth_formula"]
    risk_on = breadth_risk_on(prices, formula["universe"], 0.70)
    candidates: dict[str, pd.DataFrame] = {"benchmark": baseline}
    for name, spec in all_specs(program).items():
        kind = spec["kind"]
        if kind in {"turnover_band", "minimum_total_change", "stagger"}:
            candidate = turnover_transform(baseline, kind, float(spec["value"]))
        elif kind == "breadth_cash":
            candidate = redeploy_cash(baseline, risk_on, float(spec["cash_fraction"]))
        elif kind == "target_volatility":
            candidate = vol_cache[float(spec["target_volatility"])]
        elif kind == "breadth_conditional_vol":
            candidate = conditional_weights(baseline, vol_cache[float(spec["target_volatility"])], risk_on)
        elif kind == "target_volatility_then_turnover_band":
            candidate = turnover_transform(vol_cache[float(spec["target_volatility"])], "turnover_band", float(spec["value"]))
        elif kind == "breadth_cash_then_turnover_band":
            expanded = redeploy_cash(baseline, risk_on, float(spec["cash_fraction"]))
            candidate = turnover_transform(expanded, "turnover_band", float(spec["value"]))
        elif kind == "breadth_conditional_vol_then_turnover_band":
            expanded = conditional_weights(baseline, vol_cache[float(spec["target_volatility"])], risk_on)
            candidate = turnover_transform(expanded, "turnover_band", float(spec["value"]))
        else:
            raise ValueError(f"unknown candidate kind: {kind}")
        candidates[name] = candidate.reindex_like(baseline).fillna(0.0)
    diagnostics = {
        "breadth_risk_on_weeks": int(risk_on.sum()),
        "breadth_risk_on_share": float(risk_on.mean()),
        "mean_baseline_cash": float(baseline["BIL"].mean()),
        "mean_recent_3y_baseline_cash": float(baseline.loc[baseline.index >= baseline.index.max() - pd.DateOffset(years=3), "BIL"].mean()),
        "mean_target_vol_multiplier": float(base_result.audit_log["target_vol_multiplier"].mean()),
        "mean_regime_multiplier": float(base_result.audit_log["regime_multiplier"].mean()),
    }
    return candidates, diagnostics


def attribution(prices: pd.DataFrame, program: dict) -> pd.DataFrame:
    forward = next_week_returns(prices)
    base_result = run_from_artifacts(SOURCE, prices_override=prices, causal_training=True)
    baseline = base_result.stages["final_etf_weights"]
    all_risk = pd.Series(True, index=baseline.index)
    counterfactuals = {
        "baseline_50bps": (baseline, 50.0, "observed benchmark"),
        "baseline_gross_zero_cost": (baseline, 0.0, "cost ceiling"),
        "cash_fully_reinvested": (redeploy_cash(baseline, all_risk, 1.0), 50.0, "cash ceiling; pro-rata risky holdings"),
        "etf_cap_removed": (run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, max_etf_weight=1.0).stages["final_etf_weights"], 50.0, "35% ETF cap ceiling"),
        "target_vol_14": (run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=0.14).stages["final_etf_weights"], 50.0, "14% volatility budget"),
        "target_vol_16": (run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=0.16).stages["final_etf_weights"], 50.0, "16% volatility budget"),
        "volatility_ceiling_removed": (run_from_artifacts(SOURCE, prices_override=prices, causal_training=True, target_volatility=10.0).stages["final_etf_weights"], 50.0, "volatility multiplier ceiling only; regime controls retained"),
    }
    rows = []
    for name, (weights, cost, interpretation) in counterfactuals.items():
        path = portfolio_path(weights, forward, cost)
        for window, subset in windows(path, program["secondary_window_start"]).items():
            rows.append({"counterfactual": name, "window": window, "cost_bps": cost, "interpretation": interpretation, "mean_bil_weight": float(weights.reindex(subset.index)["BIL"].mean()), "mean_risky_weight": float(1.0 - weights.reindex(subset.index)["BIL"].mean()), **metrics(subset)})
    frame = pd.DataFrame(rows)
    base = frame[frame["counterfactual"].eq("baseline_50bps")].set_index("window")
    frame["cagr_difference_vs_baseline"] = [float(row.cagr - base.loc[row.window, "cagr"]) for row in frame.itertuples()]
    return frame


def main() -> int:
    program = json.loads(PROGRAM.read_text())
    manifest_verified = verify_manifest()
    prices = read_dated_csv(SOURCE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    candidates, diagnostics = build_candidates(prices, program)
    repeated, _ = build_candidates(prices, program)
    determinism = pd.DataFrame([
        {"candidate": name, "first_hash": frame_hash(weights), "second_hash": frame_hash(repeated[name]), "hash_equal": frame_hash(weights) == frame_hash(repeated[name]), "maximum_difference": frame_difference(weights, repeated[name])}
        for name, weights in candidates.items() if name != "benchmark"
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
        cutoff = pd.Timestamp(cutoff_text)
        location = prices.index.get_loc(cutoff) + 1
        shocked = prices.copy()
        shocked.iloc[location] *= pd.Series([1.4 if i % 2 == 0 else 0.6 for i in range(len(prices.columns))], index=prices.columns)
        alternatives, _ = build_candidates(shocked, program)
        for name in all_specs(program):
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "shocked_date": str(prices.index[location].date()), "maximum_prefix_difference": frame_difference(candidates[name].loc[:cutoff], alternatives[name].loc[:cutoff])})
    prefix = pd.DataFrame(prefix_rows)

    def row(candidate: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.candidate == candidate) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    benchmark = {(window, cost): row("benchmark", window, cost) for window in ("full", "recent_3y", "post_2024") for cost in program["cost_bps"]}
    gates = program["qualification_gates"]
    qualification_rows = []
    for name in all_specs(program):
        recent = row(name, "recent_3y", 50)
        recent100 = row(name, "recent_3y", 100)
        post = row(name, "post_2024", 50)
        full = row(name, "full", 50)
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
            "recent_3y_annual_turnover": recent.annual_one_way_turnover, "maximum_prefix_difference": maximum_prefix,
            **checks, "qualified_for_forward_challenger": all(checks.values()),
        })
    qualification = pd.DataFrame(qualification_rows).sort_values(["qualified_for_forward_challenger", "recent_3y_50bps_cagr", "candidate"], ascending=[False, False, True])
    shortlist = qualification.loc[qualification.qualified_for_forward_challenger, "candidate"].tolist()
    selected = shortlist[0] if shortlist else None
    attribution_frame = attribution(prices, program)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    determinism.to_csv(OUTPUT / "determinism.csv", index=False)
    attribution_frame.to_csv(OUTPUT / "return_ceiling_attribution.csv", index=False)
    if selected:
        saved = candidates[selected].copy(); saved.index.name = "Date"
        saved.to_csv(OUTPUT / "selected_candidate_weights.csv")
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "batch": 52,
        "program": program["program"], "program_sha256": sha256(PROGRAM),
        "module_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in MODULES},
        "manifest_sha256": sha256(MANIFEST), "frozen_source_hashes_verified": manifest_verified,
        "selection_budget": program["selection_budget"], "candidates_evaluated": len(all_specs(program)),
        "diagnostics": diagnostics, "research_shortlist": shortlist, "selected_forward_challenger": selected,
        "maximum_prefix_difference": float(prefix.maximum_prefix_difference.max()),
        "all_deterministic": bool(determinism.hash_equal.all()),
        "decision": "freeze_selected_research_challenger_pending_operational_forward_readiness" if selected else "no_candidate_qualified_no_forward_lock",
        "forward_clock_started": False, "forward_clock_blocker": "post-April causal GGG upstream decisions are not yet generated by the free-data forward pipeline" if selected else "no candidate passed every predeclared gate",
        "promoted_to_production": False, "live_trading_enabled": False,
    }
    artifact_names = ["performance.csv", "qualification.csv", "prefix_invariance.csv", "determinism.csv", "return_ceiling_attribution.csv"] + (["selected_candidate_weights.csv"] if selected else [])
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifact_names}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    best = qualification.iloc[0]
    report = [
        "# GGG return-ceiling and expansion program — Batch 52", "",
        f"Frozen hashes verified: **{manifest_verified}**. Twelve candidates were fixed before execution. All deterministic: **{result['all_deterministic']}**; maximum future-shock prefix difference: **{result['maximum_prefix_difference']:.3e}**.", "",
        f"The benchmark recent-three-year 50-bps CAGR was **{benchmark[('recent_3y', 50)].cagr:.2%}**. The highest-return candidate was `{best.candidate}` at **{best.recent_3y_50bps_cagr:.2%}**, an improvement of **{best.recent_cagr_improvement:.2%}**, with Sharpe **{best.recent_3y_50bps_sharpe:.3f}** and drawdown **{best.recent_3y_50bps_max_drawdown:.2%}**.", "",
        f"Qualifying forward challengers: **{', '.join(shortlist) if shortlist else 'none'}**. Selected: **{selected or 'none'}**.", "",
        "A historical pass is not a profitability claim. Even if selected, the forward clock remains stopped until the full causal GGG upstream decision path can operate on post-April snapshots. No live trading is enabled.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report))
    print(json.dumps({"selected": selected, "shortlist": shortlist, "best": best.candidate, "best_recent_3y_50bps_cagr": best.recent_3y_50bps_cagr, "benchmark_recent_3y_50bps_cagr": benchmark[("recent_3y", 50)].cagr, "maximum_prefix_difference": result["maximum_prefix_difference"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
