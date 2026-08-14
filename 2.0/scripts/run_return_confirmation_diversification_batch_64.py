#!/usr/bin/env python3
"""Cross-asset and embargoed-ML confirmation of the 24% return ceiling."""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from scripts.run_independent_return_source_discovery_batch_63 import build_sources
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.return_confirmation import cross_asset_features, expanding_ridge_predictions, four_week_labels, tiered_alpha

CONFIG_PATH = ROOT / "config/return_confirmation_diversification_batch_64.json"
BATCH63_CONFIG = ROOT / "config/independent_return_source_discovery_batch_63.json"
OUTPUT = ROOT / "evidence/return_confirmation_diversification_batch_64"
BUNDLE = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a"
CORE_PATH = ROOT / "evidence/aggressive_return_discovery_batch_62/selected_candidate_weights.csv"
CEILING_PATH = ROOT / "evidence/independent_return_source_discovery_batch_63/selected_or_best_weights.csv"


def monthly_decisions(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    month = index.to_period("M").astype(str).to_numpy()
    selected = np.zeros(len(index), dtype=bool)
    if len(index) > 1:
        selected[:-1] = month[:-1] != month[1:]
    if len(index):
        selected[0] = True
        selected[-1] = (index[-1] + pd.Timedelta(days=7)).month != index[-1].month
    return index[selected]


def alpha_blend(core: pd.DataFrame, source: pd.DataFrame, alpha: pd.Series) -> pd.DataFrame:
    columns = core.columns.union(source.columns)
    a = alpha.reindex(core.index).ffill().fillna(0.6).clip(0.0, 1.0)
    result = core.reindex(columns=columns, fill_value=0.0).mul(1.0 - a, axis=0)
    result = result.add(source.reindex(index=core.index, columns=columns, fill_value=0.0).mul(a, axis=0), fill_value=0.0)
    return result.div(result.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def cross_asset_alphas(features: pd.DataFrame, decisions: pd.DatetimeIndex, config: dict) -> dict[str, pd.Series]:
    f = features.reindex(decisions)
    breadth = f.breadth_positive_13 >= 0.65
    risk = (f.r26_SPY > 0.0) & (f.hyg_minus_tlt_13 > 0.0) & (f.spy_volatility_13 < 0.25)
    commodity = (f.r13_PDBC > 0.0) & (f.r13_XLE > 0.0) & (f.r13_UUP < 0.0)
    leadership = (f.r13_QQQ > 0.0) & (f.r13_IWM > 0.0) & (f.r13_XLK > 0.0)
    confirmations = breadth.astype(int) + risk.astype(int) + commodity.astype(int) + leadership.astype(int)

    def binary(condition: pd.Series, favorable: float, otherwise: float) -> pd.Series:
        values = pd.Series(np.where(condition.fillna(False), favorable, otherwise), index=decisions)
        return values.reindex(features.index).ffill().fillna(otherwise)

    variants = config["cross_asset_variants"]
    count = variants["confirmation_count"]
    count_alpha = pd.Series(np.where(confirmations >= count["high_count"], count["high"], np.where(confirmations >= count["middle_count"], count["middle"], count["low"])), index=decisions).reindex(features.index).ffill().fillna(count["low"])
    return {
        "cross::breadth_boost": binary(breadth, variants["breadth_boost"]["favorable"], variants["breadth_boost"]["otherwise"]),
        "cross::risk_on_confirmation": binary(risk, variants["risk_on_confirmation"]["favorable"], variants["risk_on_confirmation"]["otherwise"]),
        "cross::commodity_confirmation": binary(commodity, variants["commodity_confirmation"]["favorable"], variants["commodity_confirmation"]["otherwise"]),
        "cross::equity_leadership": binary(leadership, variants["equity_leadership"]["favorable"], variants["equity_leadership"]["otherwise"]),
        "cross::confirmation_count": count_alpha,
        "cross::dual_breadth_risk": binary(breadth & risk, variants["dual_breadth_risk"]["favorable"], variants["dual_breadth_risk"]["otherwise"]),
    }


def build_all(prices: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame], pd.DataFrame]:
    core = read_dated_csv(CORE_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    batch63_config = json.loads(BATCH63_CONFIG.read_text())
    source = build_sources(prices, batch63_config)[config["trend_source"]]
    ceiling = mix([core, source], [0.4, 0.6])
    features = cross_asset_features(prices, batch63_config["discovery_assets"])
    decisions = monthly_decisions(prices.index)
    alphas = cross_asset_alphas(features, decisions, config)

    forward = next_week_returns(prices)
    core_gross = portfolio_path(core, forward.reindex(columns=core.columns), 0).net_return
    source_gross = portfolio_path(source, forward.reindex(columns=source.columns), 0).net_return
    labels = four_week_labels(source_gross - core_gross, decisions, int(config["ml_label_horizon_weeks"]))
    audits = []
    for spec in config["ml_variants"]:
        predictions, audit = expanding_ridge_predictions(
            features, labels, decisions, penalty=float(spec["penalty"]),
            minimum_training=int(config["ml_minimum_training_months"]),
        )
        alpha = tiered_alpha(predictions, decisions, low=float(spec["low"]), middle=float(spec["middle"]), high=float(spec["high"]), quantile=float(spec["quantile"]))
        alphas[f"ml::{spec['name']}"] = alpha
        audit = audit.copy(); audit["variant"] = spec["name"]
        audits.append(audit.reset_index())
    candidates = {"comparison_ceiling": ceiling, **{name: alpha_blend(core, source, alpha) for name, alpha in alphas.items()}}
    return candidates, alphas, pd.concat(audits, ignore_index=True)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    prices = read_dated_csv(BUNDLE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    candidates, alphas, audit = build_all(prices, config)
    repeated, repeated_alphas, _ = build_all(prices, config)
    deterministic = all(batch60.frame_hash(frame) == batch60.frame_hash(repeated[name]) for name, frame in candidates.items())
    embargo_pass = bool(audit.embargo_pass.all())
    trial_count = len(candidates) - 1
    if trial_count != int(config["multiple_testing_trials"]):
        raise RuntimeError("trial budget mismatch")

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix, _, _ = build_all(prices.loc[:cutoff], config)
        for name, full in candidates.items():
            if name == "comparison_ceiling": continue
            expected = full.loc[:cutoff]
            actual = prefix[name].reindex_like(expected)
            difference = float((expected - actual).abs().max().max())
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)

    performance_rows, paths = [], {}
    for name, weights in candidates.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][int(cost)] = path
            for window, subset in batch60.windows(path).items():
                performance_rows.append({"candidate": name, "cost_bps": cost, "window": window, "mean_trend_weight": 0.6 if name == "comparison_ceiling" else float(alphas[name].reindex(subset.index).mean()), **batch60.metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    def row(name: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.candidate == name) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    base = {window: row("comparison_ceiling", window, 50) for window in ("trailing_1y", "trailing_2y", "trailing_3y", "full")}
    base100 = row("comparison_ceiling", "trailing_3y", 100)
    rules = config["qualification_gates"]
    qualification_rows = []
    for name in alphas:
        r1, r2, r3, full = row(name, "trailing_1y", 50), row(name, "trailing_2y", 50), row(name, "trailing_3y", 50), row(name, "full", 50)
        r100 = row(name, "trailing_3y", 100)
        share, median, worst = rolling_win_share(paths[name][50], paths["comparison_ceiling"][50])
        paired = paths[name][50].loc[r3.start:r3.end, "net_return"] - paths["comparison_ceiling"][50].loc[r3.start:r3.end, "net_return"]
        raw_p = batch60.paired_block_pvalue(paired.to_numpy(), samples=int(config["bootstrap_samples"]), block=int(config["bootstrap_block_weeks"]), seed=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))
        adjusted = min(1.0, raw_p * trial_count)
        checks = {
            "three_year_return": r3.cagr - base["trailing_3y"].cagr >= rules["minimum_trailing_3y_cagr_improvement"],
            "one_year_guard": r1.cagr - base["trailing_1y"].cagr >= -rules["maximum_trailing_1y_cagr_sacrifice"],
            "two_year_guard": r2.cagr - base["trailing_2y"].cagr >= -rules["maximum_trailing_2y_cagr_sacrifice"],
            "cost_stress": r100.cagr - base100.cagr >= rules["minimum_trailing_3y_100bps_improvement"],
            "rolling_win_share": share >= rules["minimum_rolling_3y_win_share"],
            "recent_drawdown": abs(r3.max_drawdown) <= rules["maximum_recent_drawdown_magnitude"],
            "full_drawdown": abs(full.max_drawdown) <= rules["maximum_full_drawdown_magnitude"],
            "adjusted_pvalue": adjusted <= rules["maximum_adjusted_pvalue"],
        }
        qualification_rows.append({"candidate": name, "family": name.split("::")[0], "trailing_1y_cagr": r1.cagr, "trailing_2y_cagr": r2.cagr, "trailing_3y_cagr": r3.cagr, "trailing_3y_cagr_vs_ceiling": r3.cagr - base["trailing_3y"].cagr, "trailing_3y_sharpe": r3.sharpe_zero_rf, "trailing_3y_100bps_cagr": r100.cagr, "recent_drawdown": r3.max_drawdown, "full_cagr": full.cagr, "full_drawdown": full.max_drawdown, "rolling_win_share": share, "rolling_median_cagr_difference": median, "rolling_worst_cagr_difference": worst, "mean_trend_weight_recent_3y": r3.mean_trend_weight, "raw_pvalue": raw_p, "adjusted_pvalue_12_trials": adjusted, **{f"gate_{key}": value for key, value in checks.items()}, "qualified": all(checks.values())})
    qualification = pd.DataFrame(qualification_rows).sort_values(["qualified", "trailing_3y_cagr"], ascending=False)
    passing = qualification[qualification.qualified]
    selected = str(passing.iloc[0].candidate) if len(passing) else None
    point_best = str(qualification.iloc[0].candidate)
    saved = selected or point_best

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    qualification.to_csv(OUTPUT / "qualification.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    audit.to_csv(OUTPUT / "ml_embargo_audit.csv", index=False)
    pd.DataFrame([{"candidate": name, "first_hash": batch60.frame_hash(frame), "second_hash": batch60.frame_hash(repeated[name]), "deterministic": batch60.frame_hash(frame) == batch60.frame_hash(repeated[name])} for name, frame in candidates.items()]).to_csv(OUTPUT / "determinism.csv", index=False)
    saved_weights = candidates[saved].copy(); saved_weights.index.name = "Date"
    saved_weights.to_csv(OUTPUT / "selected_or_best_weights.csv")
    saved_weights.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_or_best_current_holdings.csv")
    best = qualification.iloc[0]
    result = {
        "batch": 64, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_trials": trial_count,
        "deterministic": deterministic, "ml_embargo_pass": embargo_pass,
        "ml_predictions": int(audit.predicted.sum()), "prefix_invariance_pass": bool(prefixes.prefix_pass.all()),
        "maximum_prefix_weight_difference": float(prefixes.maximum_weight_difference.max()),
        "comparison_ceiling_trailing_3y_cagr": float(base["trailing_3y"].cagr),
        "qualified_candidates": len(passing), "selected_candidate": selected,
        "research_ceiling_candidate": point_best,
        "best_point_candidate": point_best, "best_point_trailing_1y_cagr": float(best.trailing_1y_cagr),
        "best_point_trailing_2y_cagr": float(best.trailing_2y_cagr), "best_point_trailing_3y_cagr": float(best.trailing_3y_cagr),
        "best_point_rolling_win_share": float(best.rolling_win_share),
        "decision": "save_confirmed_diversified_return_engine" if selected else "save_unconfirmed_cross_asset_return_ceiling_and_reject_ml_promotion",
        "retrospective_research_only": True, "leverage_used": False, "forward_clock_started": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Batch 64 — cross-asset and embargoed-ML confirmation\n\n"
        f"Tested {trial_count} fixed confirmation variants against the 24.10% ceiling. Deterministic: **{deterministic}**; ML embargo pass: **{embargo_pass}**; all {len(prefixes)} prefix checks passed: **{bool(prefixes.prefix_pass.all())}**.\n\n"
        f"Best point variant `{point_best}` produced one/two/three-year CAGR `{best.trailing_1y_cagr:.2%}` / `{best.trailing_2y_cagr:.2%}` / `{best.trailing_3y_cagr:.2%}` and beat the ceiling in `{best.rolling_win_share:.1%}` of rolling three-year windows.\n\n"
        f"Qualified candidates: **{len(passing)}**. Selected: `{selected}`. Research ceiling retained even if unqualified: `{point_best}`. "
        f"Decision: `{result['decision']}`. No leverage, forward clock, or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if deterministic and embargo_pass and bool(prefixes.prefix_pass.all()) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "failure_traceback.txt").write_text(traceback.format_exc())
        raise
