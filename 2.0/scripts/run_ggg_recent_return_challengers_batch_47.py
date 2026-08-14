#!/usr/bin/env python3
"""Evaluate six predeclared recent-return challengers to causal GGG."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from systematic_trader.ggg_challengers import ChallengerSpec, apply_challenger
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
PROGRAM = ROOT / "config/ggg_recent_return_challengers_v1.json"
FREEZE = ROOT / "config/ggg_causal_upstream_freeze_v1.json"
MODULE = ROOT / "src/systematic_trader/ggg_challengers.py"
OUTPUT = ROOT / "evidence/ggg_recent_return_challengers_batch_47"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def frame_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    index = left.index.intersection(right.index)
    columns = left.columns.intersection(right.columns)
    values = (left.loc[index, columns] - right.loc[index, columns]).abs().to_numpy()
    return float(np.nanmax(values)) if values.size else float("inf")


def metrics(series: pd.Series) -> dict:
    returns = pd.to_numeric(series, errors="coerce").dropna()
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    arithmetic = float(returns.mean() * 52.0)
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "arithmetic_ann_return": arithmetic,
        "ann_vol": volatility, "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan,
        "max_drawdown": float(drawdown.min()),
    }


def verify_freeze() -> bool:
    freeze = json.loads(FREEZE.read_text())
    for sleeve, hashes in freeze["qualified_sleeves"].items():
        for kind in ("positions", "returns"):
            path = V1 / f"data/03_layer2a_strategy_logic/strategy_{kind}_{sleeve}.csv"
            if sha256(path) != hashes[f"{kind}_sha256"]:
                return False
    return True


def main() -> int:
    program = json.loads(PROGRAM.read_text())
    if len(program["challengers"]) != int(program["selection_budget"]):
        raise ValueError("Predeclared challenger count does not match the search budget")
    freeze_verified = verify_freeze()
    prices = read_dated_csv(V1 / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    baseline_result = run_from_artifacts(V1, causal_training=True)
    baseline = baseline_result.stages["final_etf_weights"]
    candidates: dict[str, pd.DataFrame] = {"benchmark": baseline}
    determinism_rows = []
    for name, values in program["challengers"].items():
        spec = ChallengerSpec(**values)
        first = apply_challenger(baseline, prices, spec)
        second = apply_challenger(baseline, prices, spec)
        candidates[name] = first
        determinism_rows.append({
            "candidate": name, "first_hash": frame_hash(first), "second_hash": frame_hash(second),
            "hash_equal": frame_hash(first) == frame_hash(second), "maximum_difference": frame_difference(first, second),
        })

    performance_rows = []
    for name, weights in candidates.items():
        for cost_bps in program["cost_bps"]:
            path = portfolio_path(weights, forward, float(cost_bps))
            windows = {
                "full": path["net_return"],
                "recent_3y": path.loc[path.index >= path.index.max() - pd.DateOffset(years=3), "net_return"],
                "post_2024": path.loc[path.index >= pd.Timestamp(program["secondary_window_start"]), "net_return"],
            }
            for window, returns in windows.items():
                performance_rows.append({"candidate": name, "cost_bps": cost_bps, "window": window, **metrics(returns)})
    performance = pd.DataFrame(performance_rows)

    prefix_rows = []
    for cutoff_text in program["prefix_cutoffs"]:
        cutoff = pd.Timestamp(cutoff_text)
        location = prices.index.get_loc(cutoff) + 1
        shocked = prices.copy()
        factors = pd.Series([1.4 if i % 2 == 0 else 0.6 for i in range(len(prices.columns))], index=prices.columns)
        shocked.iloc[location] = shocked.iloc[location] * factors
        shocked_baseline = run_from_artifacts(V1, prices_override=shocked, causal_training=True).stages["final_etf_weights"]
        for name, values in program["challengers"].items():
            alternative = apply_challenger(shocked_baseline, shocked, ChallengerSpec(**values))
            difference = frame_difference(candidates[name].loc[:cutoff], alternative.loc[:cutoff])
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "shocked_date": str(prices.index[location].date()), "maximum_prefix_difference": difference})
    prefix = pd.DataFrame(prefix_rows)
    determinism = pd.DataFrame(determinism_rows)

    def metric_row(candidate: str, window: str, cost: int = 50) -> pd.Series:
        return performance[(performance["candidate"] == candidate) & (performance["window"] == window) & (performance["cost_bps"] == cost)].iloc[0]

    benchmark_recent = metric_row("benchmark", "recent_3y")
    benchmark_post = metric_row("benchmark", "post_2024")
    benchmark_full = metric_row("benchmark", "full")
    gates = program["qualification_gates"]
    qualification_rows = []
    for name in program["challengers"]:
        recent = metric_row(name, "recent_3y")
        post = metric_row(name, "post_2024")
        full = metric_row(name, "full")
        candidate_prefix = float(prefix.loc[prefix["candidate"] == name, "maximum_prefix_difference"].max())
        deterministic = bool(determinism.loc[determinism["candidate"] == name, "hash_equal"].all())
        individual = {
            "recent_cagr_gate": float(recent["cagr"] - benchmark_recent["cagr"]) >= float(gates["minimum_recent_3y_50bps_cagr_improvement"]),
            "post_2024_cagr_gate": float(post["cagr"] - benchmark_post["cagr"]) >= float(gates["minimum_post_2024_50bps_cagr_improvement"]),
            "full_cagr_gate": float(full["cagr"] - benchmark_full["cagr"]) >= -float(gates["maximum_full_50bps_cagr_degradation"]),
            "drawdown_guard": abs(float(recent["max_drawdown"])) <= float(gates["maximum_recent_3y_drawdown_magnitude"]),
            "prefix_gate": candidate_prefix <= float(gates["maximum_prefix_absolute_difference"]),
            "determinism_gate": deterministic,
            "freeze_gate": freeze_verified,
        }
        qualification_rows.append({
            "candidate": name, "recent_3y_50bps_cagr": recent["cagr"],
            "recent_cagr_improvement": recent["cagr"] - benchmark_recent["cagr"],
            "post_2024_cagr_improvement": post["cagr"] - benchmark_post["cagr"],
            "full_cagr_improvement": full["cagr"] - benchmark_full["cagr"],
            "recent_3y_50bps_sharpe": recent["sharpe_zero_rf"], "recent_3y_50bps_max_drawdown": recent["max_drawdown"],
            "maximum_prefix_difference": candidate_prefix, **individual,
            "qualified_for_research_shortlist": all(individual.values()),
        })
    qualification = pd.DataFrame(qualification_rows).sort_values("recent_3y_50bps_cagr", ascending=False)
    shortlist = qualification.loc[qualification["qualified_for_research_shortlist"], "candidate"].tolist()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    prefix.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    determinism.to_csv(OUTPUT / "determinism.csv", index=False)
    qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "program": program["program"],
        "program_sha256": sha256(PROGRAM), "module_sha256": sha256(MODULE), "freeze_sha256": sha256(FREEZE),
        "frozen_source_hashes_verified": freeze_verified, "selection_budget": program["selection_budget"],
        "candidates_evaluated": len(program["challengers"]), "research_shortlist": shortlist,
        "benchmark_recent_3y_50bps": {key: benchmark_recent[key] for key in ("cagr", "sharpe_zero_rf", "max_drawdown")},
        "maximum_prefix_difference": float(prefix["maximum_prefix_difference"].max()),
        "all_deterministic": bool(determinism["hash_equal"].all()),
        "decision": "retain_qualified_challengers_for_locked_forward_comparison" if shortlist else "no_challenger_qualified",
        "promoted_to_production": False, "live_trading_enabled": False,
    }
    artifacts = ["performance.csv", "prefix_invariance.csv", "determinism.csv", "qualification.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifacts}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    best = qualification.iloc[0]
    report = [
        "# Causal GGG recent-return challengers — Batch 47", "",
        f"Six predeclared overlays were tested. Frozen input hashes verified: **{freeze_verified}**. Maximum future-shock prefix difference: {result['maximum_prefix_difference']:.3e}. All output hashes deterministic: **{result['all_deterministic']}**.", "",
        f"The 50-bps benchmark recent-three-year CAGR is {benchmark_recent['cagr']:.2%}. The best challenger is `{best['candidate']}` at {best['recent_3y_50bps_cagr']:.2%}, an improvement of {best['recent_cagr_improvement']:.2%}; Sharpe {best['recent_3y_50bps_sharpe']:.3f}, drawdown {best['recent_3y_50bps_max_drawdown']:.2%}.", "",
        f"Qualified research shortlist: {', '.join(shortlist) if shortlist else 'none'}. Passing means only that the predeclared retrospective gates were met; it is not production promotion because every evaluation window was already observed.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report))
    print(json.dumps({"shortlist": shortlist, "best": best["candidate"], "best_recent_3y_50bps_cagr": best["recent_3y_50bps_cagr"], "benchmark_recent_3y_50bps_cagr": benchmark_recent["cagr"], "maximum_prefix_difference": result["maximum_prefix_difference"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
