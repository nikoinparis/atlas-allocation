#!/usr/bin/env python3
"""Deep validation and causal regime-aware improvement search for GGG+xsmom."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv, run_from_artifacts

CONFIG_PATH = ROOT / "config/ggg_xsmom_deep_validation_batch_61.json"
REGISTRY_PATH = ROOT / "research_registry/strategy_candidates.json"
OUTPUT = ROOT / "evidence/ggg_xsmom_deep_validation_batch_61"


def dynamic_alpha(name: str, spec: dict, states: pd.Series, tail: pd.Series, candidate: pd.DataFrame) -> pd.Series:
    alpha = pd.Series(float(spec.get("neutral", spec.get("normal", 0.3))), index=candidate.index)
    favorable = states.isin(CONFIG["favorable_states"])
    adverse = states.isin(CONFIG["adverse_states"])
    risk_exposure = 1.0 - candidate.reindex(columns=["BIL", "cash::USD"], fill_value=0.0).sum(axis=1)
    if name.startswith("state_guard") or name.startswith("state_boost"):
        alpha.loc[favorable] = float(spec["favorable"])
        alpha.loc[adverse] = float(spec["adverse"])
    elif name.startswith("tail_guard"):
        alpha.loc[tail >= float(spec["tail_threshold"])] = float(spec["tail_risk"])
    elif name.startswith("exposure_boost"):
        alpha.loc[risk_exposure >= float(spec["exposure_threshold"])] = float(spec["high_candidate_exposure"])
    elif name == "state_exposure_combo":
        alpha.loc[adverse] = float(spec["adverse"])
        alpha.loc[favorable & (risk_exposure >= float(spec["exposure_threshold"]))] = float(spec["favorable_high_exposure"])
    else:
        raise ValueError(f"unknown dynamic variant: {name}")
    return alpha


def dynamic_blend(baseline: pd.DataFrame, candidate: pd.DataFrame, alpha: pd.Series) -> pd.DataFrame:
    columns = baseline.columns.union(candidate.columns)
    left = baseline.reindex(columns=columns, fill_value=0.0)
    right = candidate.reindex(index=baseline.index, columns=columns, fill_value=0.0)
    a = alpha.reindex(baseline.index).fillna(0.3).clip(0.0, 1.0)
    result = left.mul(1.0 - a, axis=0) + right.mul(a, axis=0)
    return result.div(result.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def maximum_drawdown_episode(path: pd.DataFrame) -> dict:
    returns = path.net_return.fillna(0.0)
    wealth = (1.0 + returns).cumprod()
    running_peak = wealth.cummax()
    drawdown = wealth / running_peak - 1.0
    trough = drawdown.idxmin()
    peak = wealth.loc[:trough].idxmax()
    recovered = wealth.loc[trough:]
    recovery_dates = recovered[recovered >= wealth.loc[peak]].index
    return {
        "peak": str(peak.date()), "trough": str(trough.date()),
        "recovery": str(recovery_dates[0].date()) if len(recovery_dates) else "unrecovered",
        "maximum_drawdown": float(drawdown.loc[trough]),
    }


def metric_row(path: pd.DataFrame, start: str | None = None, end: str | None = None) -> dict:
    subset = path.loc[start:end] if start or end else path
    return batch60.metrics(subset)


def main() -> int:
    global CONFIG
    CONFIG = json.loads(CONFIG_PATH.read_text())
    registry = json.loads(REGISTRY_PATH.read_text())
    source = next(row for row in registry["candidates"] if row["candidate_id"] == CONFIG["challenger_candidate_id"])
    bundle = ROOT / "data/ggg_vintages" / CONFIG["baseline_bundle_id"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    baseline = run_from_artifacts(bundle, causal_training=True, legacy_terminal_rebalance=False).stages["final_etf_weights"]
    candidate = batch60.build_candidate_weights(prices, [source])[CONFIG["challenger_candidate_id"]]
    static = batch60.blended_weights(baseline, candidate, float(CONFIG["favored_static_weight"]))

    paths = {
        "baseline": {cost: portfolio_path(baseline, forward.reindex(columns=baseline.columns), cost) for cost in (50, 100)},
        "static_30": {cost: portfolio_path(static, forward.reindex(columns=static.columns), cost) for cost in (50, 100)},
    }

    neighborhood_rows = []
    for alpha in CONFIG["alpha_neighborhood"]:
        weights = batch60.blended_weights(baseline, candidate, float(alpha))
        for cost in (50, 100):
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), cost)
            for window, subset in batch60.windows(path).items():
                neighborhood_rows.append({"candidate_weight": alpha, "cost_bps": cost, "window": window, **batch60.metrics(subset)})
    neighborhood = pd.DataFrame(neighborhood_rows)

    static50 = paths["static_30"][50]
    base50 = paths["baseline"][50]
    rolling_rows = []
    width, step = int(CONFIG["rolling_window_weeks"]), int(CONFIG["rolling_step_weeks"])
    starts = list(range(0, len(static50) - width + 1, step))
    final_start = len(static50) - width
    if final_start not in starts: starts.append(final_start)
    for start in starts:
        stop = start + width
        s, b = static50.iloc[start:stop], base50.iloc[start:stop]
        sm, bm = batch60.metrics(s), batch60.metrics(b)
        rolling_rows.append({"start": sm["start"], "end": sm["end"], "challenger_cagr": sm["cagr"], "baseline_cagr": bm["cagr"], "cagr_improvement": sm["cagr"] - bm["cagr"], "challenger_sharpe": sm["sharpe_zero_rf"], "baseline_sharpe": bm["sharpe_zero_rf"], "sharpe_improvement": sm["sharpe_zero_rf"] - bm["sharpe_zero_rf"], "challenger_drawdown": sm["max_drawdown"], "baseline_drawdown": bm["max_drawdown"]})
    rolling = pd.DataFrame(rolling_rows)

    subperiod_rows = []
    for period, (start, end) in CONFIG["subperiods"].items():
        for implementation, path in (("baseline", base50), ("static_30", static50)):
            subperiod_rows.append({"period": period, "implementation": implementation, **metric_row(path, start, end)})
    subperiods = pd.DataFrame(subperiod_rows)

    year_rows = []
    for year in sorted(set(static50.index.year)):
        if year < 2006: continue
        for implementation, path in (("baseline", base50), ("static_30", static50)):
            subset = path.loc[path.index.year == year]
            if len(subset) >= 26:
                year_rows.append({"year": year, "implementation": implementation, **batch60.metrics(subset)})
    years = pd.DataFrame(year_rows)

    state = read_dated_csv(bundle / "data/04_layer2b_risk_regime_engine/market_state_history.csv")["market_state"].reindex(prices.index).fillna("neutral_mixed")
    tail = pd.to_numeric(read_dated_csv(bundle / "data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv")["p_tail_risk"], errors="coerce").reindex(prices.index).fillna(0.0)
    variant_weights = {}
    variant_rows = []
    static_recent = batch60.metrics(batch60.windows(static50)["trailing_3y"])
    static_full = batch60.metrics(static50)
    for name, spec in CONFIG["dynamic_variants"].items():
        alpha = dynamic_alpha(name, spec, state, tail, candidate)
        weights = dynamic_blend(baseline, candidate, alpha)
        variant_weights[name] = weights
        for cost in (50, 100):
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), cost)
            for window, subset in batch60.windows(path).items():
                variant_rows.append({"variant": name, "cost_bps": cost, "window": window, "mean_candidate_weight": float(alpha.reindex(subset.index).mean()), **batch60.metrics(subset)})
    variants = pd.DataFrame(variant_rows)

    qualification_rows = []
    for name in CONFIG["dynamic_variants"]:
        recent = variants[(variants.variant == name) & (variants.cost_bps == 50) & (variants.window == "trailing_3y")].iloc[0]
        full = variants[(variants.variant == name) & (variants.cost_bps == 50) & (variants.window == "full")].iloc[0]
        diff = portfolio_path(variant_weights[name], forward.reindex(columns=variant_weights[name].columns), 50).loc[CONFIG["recent_start"]:, "net_return"] - static50.loc[CONFIG["recent_start"]:, "net_return"]
        raw_p = batch60.paired_block_pvalue(diff.to_numpy(), samples=int(CONFIG["bootstrap_samples"]), block=int(CONFIG["bootstrap_block_weeks"]), seed=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))
        adjusted = min(1.0, raw_p * len(CONFIG["dynamic_variants"]))
        rr, dr = CONFIG["variant_return_route"], CONFIG["variant_drawdown_route"]
        return_route = bool(
            recent.cagr - static_recent["cagr"] >= rr["minimum_recent_3y_cagr_improvement_over_static"]
            and recent.sharpe_zero_rf - static_recent["sharpe_zero_rf"] >= rr["minimum_recent_3y_sharpe_improvement_over_static"]
            and recent.max_drawdown - static_recent["max_drawdown"] >= -rr["maximum_recent_drawdown_deterioration"]
            and full.cagr - static_full["cagr"] >= -rr["maximum_full_cagr_sacrifice"]
            and adjusted <= rr["maximum_adjusted_pvalue"]
        )
        drawdown_route = bool(
            recent.cagr - static_recent["cagr"] >= -dr["maximum_recent_3y_cagr_sacrifice"]
            and full.max_drawdown - static_full["max_drawdown"] >= dr["minimum_full_drawdown_improvement"]
            and recent.sharpe_zero_rf - static_recent["sharpe_zero_rf"] >= dr["minimum_recent_3y_sharpe_improvement"]
        )
        qualification_rows.append({"variant": name, "recent_3y_cagr": recent.cagr, "recent_3y_cagr_vs_static": recent.cagr - static_recent["cagr"], "recent_3y_sharpe": recent.sharpe_zero_rf, "recent_3y_sharpe_vs_static": recent.sharpe_zero_rf - static_recent["sharpe_zero_rf"], "recent_3y_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "full_cagr_vs_static": full.cagr - static_full["cagr"], "full_drawdown": full.max_drawdown, "full_drawdown_improvement": full.max_drawdown - static_full["max_drawdown"], "raw_pvalue": raw_p, "adjusted_pvalue_6_trials": adjusted, "return_route_pass": return_route, "drawdown_route_pass": drawdown_route, "qualified": return_route or drawdown_route})
    qualification = pd.DataFrame(qualification_rows).sort_values(["qualified", "recent_3y_cagr"], ascending=False)

    base_recent100 = neighborhood[(neighborhood.candidate_weight == 0.3) & (neighborhood.cost_bps == 100) & (neighborhood.window == "trailing_3y")].iloc[0]
    baseline_recent100 = batch60.metrics(batch60.windows(paths["baseline"][100])["trailing_3y"])
    nearby_recent = neighborhood[(neighborhood.cost_bps == 50) & (neighborhood.window == "trailing_3y")]
    base_recent = batch60.metrics(batch60.windows(base50)["trailing_3y"])
    recent_years = years[years.year >= 2021].pivot(index="year", columns="implementation", values="cagr").dropna()
    static_gates = {
        "rolling_3y_cagr_win_share": float((rolling.cagr_improvement > 0).mean()) >= CONFIG["static_validation_gates"]["minimum_rolling_3y_cagr_win_share"],
        "recent_year_win_share": float((recent_years.static_30 > recent_years.baseline).mean()) >= CONFIG["static_validation_gates"]["minimum_recent_year_win_share"],
        "alpha_neighborhood_recent_3y": bool((nearby_recent.cagr > base_recent["cagr"]).all()),
        "recent_3y_100bps": float(base_recent100.cagr) > baseline_recent100["cagr"],
    }
    static_deep_pass = all(static_gates.values())
    qualified = qualification[qualification.qualified]
    selected_variant = str(qualified.iloc[0].variant) if len(qualified) else None

    determinism = all(batch60.frame_hash(variant_weights[name]) == batch60.frame_hash(dynamic_blend(baseline, candidate, dynamic_alpha(name, CONFIG["dynamic_variants"][name], state, tail, candidate))) for name in variant_weights)
    drawdowns = []
    for name, path in (("baseline", base50), ("static_30", static50)):
        drawdowns.append({"implementation": name, **maximum_drawdown_episode(path)})
    for name, weights in variant_weights.items():
        drawdowns.append({"implementation": name, **maximum_drawdown_episode(portfolio_path(weights, forward.reindex(columns=weights.columns), 50))})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    neighborhood.to_csv(OUTPUT / "alpha_neighborhood.csv", index=False)
    rolling.to_csv(OUTPUT / "rolling_3y_comparison.csv", index=False)
    subperiods.to_csv(OUTPUT / "subperiods.csv", index=False)
    years.to_csv(OUTPUT / "calendar_years.csv", index=False)
    variants.to_csv(OUTPUT / "dynamic_variant_performance.csv", index=False)
    qualification.to_csv(OUTPUT / "dynamic_variant_qualification.csv", index=False)
    pd.DataFrame(drawdowns).to_csv(OUTPUT / "maximum_drawdown_episodes.csv", index=False)
    if selected_variant:
        selected_alpha = dynamic_alpha(selected_variant, CONFIG["dynamic_variants"][selected_variant], state, tail, candidate)
        selected_alpha.rename("candidate_weight").to_csv(OUTPUT / "selected_variant_alpha.csv")
        saved_weights = variant_weights[selected_variant].copy()
        saved_weights.index.name = "Date"
        saved_weights.to_csv(OUTPUT / "selected_variant_weights.csv")
        variant_weights[selected_variant].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_variant_current_holdings.csv")
    result = {
        "batch": 61, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": "candidate-ggg-xsmom-30-v1", "static_deep_validation_pass": static_deep_pass,
        "static_validation_gates": static_gates,
        "rolling_3y_windows": len(rolling), "rolling_3y_cagr_win_share": float((rolling.cagr_improvement > 0).mean()),
        "rolling_3y_median_cagr_improvement": float(rolling.cagr_improvement.median()),
        "rolling_3y_worst_cagr_improvement": float(rolling.cagr_improvement.min()),
        "recent_year_win_share": float((recent_years.static_30 > recent_years.baseline).mean()),
        "dynamic_variants_tested": len(CONFIG["dynamic_variants"]), "qualified_dynamic_variants": int(qualification.qualified.sum()),
        "selected_dynamic_variant": selected_variant, "deterministic": determinism,
        "decision": "adopt_dynamic_variant_for_further_validation" if selected_variant else "retain_static_30_provisional_challenger",
        "retrospective_research_only": True, "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    best_variant = qualification.iloc[0]
    (OUTPUT / "report.md").write_text(
        "# Batch 61 — deep validation and improvement of GGG+xsmom\n\n"
        f"The favored static 30% challenger passed all declared deep-validation gates: **{static_deep_pass}**. "
        f"It beat causal GGG on CAGR in `{(rolling.cagr_improvement > 0).mean():.1%}` of {len(rolling)} rolling three-year windows, with median improvement `{rolling.cagr_improvement.median():+.2%}` and worst improvement `{rolling.cagr_improvement.min():+.2%}`.\n\n"
        f"All five nearby sizes from 20% through 40% improved trailing-three-year 50-bps CAGR over baseline: **{static_gates['alpha_neighborhood_recent_3y']}**. "
        f"The 30% version also retained an advantage at 100 bps: **{static_gates['recent_3y_100bps']}**.\n\n"
        f"Six causal state/exposure variants were tested. Qualified variants: **{int(qualification.qualified.sum())}**. "
        f"Best by the return-first ordering was `{best_variant.variant}` at `{best_variant.recent_3y_cagr:.2%}` trailing-three-year CAGR and `{best_variant.recent_3y_sharpe:.3f}` Sharpe. "
        f"Decision: `{result['decision']}`. The static 30% candidate remains provisional and no live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if determinism else 2


if __name__ == "__main__":
    CONFIG = {}
    raise SystemExit(main())
