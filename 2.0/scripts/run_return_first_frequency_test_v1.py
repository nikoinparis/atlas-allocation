#!/usr/bin/env python3
"""Compare monthly, weekly, buffered-weekly, and monthly-emergency return-first schedules."""

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
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix
from scripts.run_exhaustive_return_first_discovery_batch_66 import nonlinear_predictions, static_weights
from scripts.run_return_confirmation_diversification_batch_64 import alpha_blend
from systematic_trader.ggg_execution import band_execution, scheduled_execution
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.independent_return_sources import CASH
from systematic_trader.return_confirmation import cross_asset_features, four_week_labels
from systematic_trader.return_first_search import advanced_signal_families, delay_weights, regime_source_alphas

CONFIG = ROOT / "config/return_first_frequency_test_v1.json"
OUTPUT = ROOT / "evidence/return_first_frequency_test_v1"


def frame_hash(frame: pd.DataFrame) -> str:
    return hashlib.sha256(frame.to_csv(float_format="%.17g").encode()).hexdigest()


def weekly_weights(
    signal: pd.DataFrame,
    prices: pd.DataFrame,
    universe: list[str],
    *,
    top_n: int,
    minimum_score: float,
) -> pd.DataFrame:
    columns = list(dict.fromkeys([*prices.columns, CASH]))
    result = pd.DataFrame(0.0, index=prices.index, columns=columns)
    volatility = prices.pct_change(fill_method=None).rolling(26, min_periods=13).std(ddof=1)
    for date in prices.index:
        row = signal.reindex(index=[date], columns=universe).iloc[0]
        eligible = row[(row > minimum_score) & prices.loc[date, universe].notna()]
        selected = eligible.sort_values(ascending=False).head(top_n)
        current = pd.Series(0.0, index=columns)
        if len(selected):
            inverse = 1.0 / volatility.loc[date, selected.index].replace(0.0, np.nan)
            raw = (selected - minimum_score).clip(lower=1e-12) * inverse.fillna(1.0)
            current.loc[raw.index] = raw / raw.sum() * (len(selected) / top_n)
        destination = "BIL" if "BIL" in prices and pd.notna(prices.loc[date, "BIL"]) else CASH
        current[destination] += 1.0 - float(current.sum())
        result.loc[date] = current
    return result


def build_weekly_target(prices: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    formula = config["formula"]
    universe = json.loads((ROOT / "config/exhaustive_return_first_discovery_batch_66.json").read_text())["discovery_assets"]
    forward = next_week_returns(prices)
    xlk = static_weights(prices, {"XLK": 1.0})
    breadth = read_dated_csv(ROOT / config["breadth_component"]).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)

    features = cross_asset_features(prices, universe)
    xlk_gross = portfolio_path(xlk, forward.reindex(columns=xlk.columns), 0.0).net_return
    breadth_gross = portfolio_path(breadth, forward.reindex(columns=breadth.columns), 0.0).net_return
    decisions = prices.index
    labels = four_week_labels(breadth_gross - xlk_gross, decisions, int(formula["hgb_label_horizon_weeks"]))
    predictions, audit = nonlinear_predictions(
        features,
        labels,
        decisions,
        "hist_gradient_boosting",
        int(formula["hgb_minimum_weekly_training_rows"]),
        int(formula["hgb_seed"]),
    )
    hgb_alpha = predictions.reindex(decisions).gt(0.0).astype(float).reindex(prices.index).ffill().fillna(0.0)
    hgb = alpha_blend(xlk, breadth, hgb_alpha)
    base = mix([xlk, hgb], [float(formula["base_xlk_weight"]), float(formula["base_hgb_weight"])])

    signal = advanced_signal_families(prices)["rank_consensus"]
    ranked = weekly_weights(
        signal,
        prices,
        universe,
        top_n=int(formula["rank_top_n"]),
        minimum_score=float(formula["rank_minimum_score"]),
    )
    regime_alpha = regime_source_alphas(prices, universe)["broad_risk_on"]
    rank_component = alpha_blend(xlk, ranked, regime_alpha)
    target = mix([base, rank_component], [float(formula["base_weight"]), float(formula["rank_consensus_weight"])])
    return target, audit


def build_versions(prices: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    incumbent = read_dated_csv(ROOT / config["monthly_incumbent"]).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    weekly, audit = build_weekly_target(prices, config)
    buffered = band_execution(
        weekly,
        entry_band=float(config["buffer_one_way_turnover"]),
        exit_band=float(config["buffer_one_way_turnover"]),
    )
    emergency = scheduled_execution(
        weekly,
        monthly=True,
        emergency_turnover=float(config["emergency_one_way_turnover"]),
        emergency_cash_change=float(config["emergency_bil_change"]),
    )
    return {
        "monthly_incumbent": incumbent,
        "weekly_full_refresh": weekly,
        "weekly_buffered": buffered,
        "monthly_emergency": emergency,
    }, audit


def windows(path: pd.DataFrame, training_end: pd.Timestamp) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full": path,
        "holdout": path.loc[path.index > training_end],
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_3y": path.loc[path.index >= end - pd.DateOffset(years=3)],
        "post_2024": path.loc[path.index >= pd.Timestamp("2024-01-05")],
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    bundle = ROOT / "data/ggg_vintages" / config["data_bundle"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    training_end = pd.Timestamp(config["training_end"])
    versions, ml_audit = build_versions(prices, config)

    repeat_weekly, _ = build_weekly_target(prices, config)
    deterministic = frame_hash(versions["weekly_full_refresh"]) == frame_hash(repeat_weekly)
    validation = {
        "deterministic": deterministic,
        "ml_embargo_pass": bool(ml_audit.embargo_pass.all()),
        "all_long_only": all(float(frame.min().min()) >= -1e-12 for frame in versions.values()),
        "all_fully_invested": all(float((frame.sum(axis=1) - 1.0).abs().max()) <= 1e-9 for frame in versions.values()),
    }

    prefix_rows = []
    for cutoff_text in config["prefix_cutoffs"]:
        cutoff = pd.Timestamp(cutoff_text)
        truncated, _ = build_weekly_target(prices.loc[:cutoff], config)
        expected = versions["weekly_full_refresh"].loc[:cutoff]
        difference = float((expected - truncated.reindex_like(expected)).abs().max().max())
        prefix_rows.append({"cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)
    validation["prefix_invariance_pass"] = bool(prefixes.prefix_pass.all())

    performance_rows = []
    paths: dict[str, dict[int, pd.DataFrame]] = {}
    for name, weights in versions.items():
        paths[name] = {}
        for cost in config["cost_bps"]:
            path = portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))
            paths[name][int(cost)] = path
            for window, subset in windows(path, training_end).items():
                performance_rows.append({"version": name, "cost_bps": int(cost), "window": window, **batch60.metrics(subset)})
    performance = pd.DataFrame(performance_rows)

    delay_rows = []
    for name, weights in versions.items():
        for delay in config["additional_execution_delays_weeks"]:
            delayed = delay_weights(weights, int(delay))
            path = portfolio_path(delayed, forward.reindex(columns=delayed.columns), 50.0)
            delay_rows.append({"version": name, "additional_delay_weeks": int(delay), **batch60.metrics(path.loc[path.index > training_end])})
    delays = pd.DataFrame(delay_rows)

    def metric(version: str, window: str, cost: int) -> pd.Series:
        return performance[(performance.version == version) & (performance.window == window) & (performance.cost_bps == cost)].iloc[0]

    incumbent = metric("monthly_incumbent", "holdout", 50)
    comparison_rows = []
    for name in versions:
        primary = metric(name, "holdout", 50)
        recent = metric(name, "trailing_3y", 50)
        comparison_rows.append({
            "version": name,
            "holdout_50bps_cagr": primary.cagr,
            "holdout_50bps_cagr_vs_monthly": primary.cagr - incumbent.cagr,
            "holdout_50bps_sharpe": primary.sharpe_zero_rf,
            "holdout_50bps_max_drawdown": primary.max_drawdown,
            "holdout_annual_turnover": primary.annual_one_way_turnover,
            "holdout_0bps_cagr": metric(name, "holdout", 0).cagr,
            "trailing_1y_50bps_cagr": metric(name, "trailing_1y", 50).cagr,
            "trailing_2y_50bps_cagr": metric(name, "trailing_2y", 50).cagr,
            "trailing_3y_50bps_cagr": recent.cagr,
            "trailing_3y_100bps_cagr": metric(name, "trailing_3y", 100).cagr,
            "trailing_3y_200bps_cagr": metric(name, "trailing_3y", 200).cagr,
            "full_50bps_cagr": metric(name, "full", 50).cagr,
            "full_50bps_max_drawdown": metric(name, "full", 50).max_drawdown,
            "actual_weight_change_weeks": int((versions[name].diff().abs().sum(axis=1) > 1e-8).sum()),
        })
    comparison = pd.DataFrame(comparison_rows).sort_values("holdout_50bps_cagr", ascending=False)
    point_leader = str(comparison.iloc[0].version)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    comparison.to_csv(OUTPUT / "comparison.csv", index=False)
    delays.to_csv(OUTPUT / "execution_delay_stress.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    ml_audit.to_csv(OUTPUT / "weekly_hgb_embargo_audit.csv", index=False)
    for name, weights in versions.items():
        weights.rename_axis("Date").to_csv(OUTPUT / f"{name}_weights.csv")

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": config["program"],
        "versions_tested": list(versions),
        "point_leader": point_leader,
        "point_leader_holdout_50bps_cagr": float(comparison.iloc[0].holdout_50bps_cagr),
        "monthly_incumbent_holdout_50bps_cagr": float(incumbent.cagr),
        "validation": validation,
        "research_only": True,
        "incumbent_replaced": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Return-first trading-frequency test\n\n"
        f"Tested the frozen monthly incumbent against full weekly refresh, weekly with a 5% turnover buffer, and monthly execution with a 15% emergency override. Point leader: **{point_leader}** at **{comparison.iloc[0].holdout_50bps_cagr:.2%}** retrospective holdout CAGR versus **{incumbent.cagr:.2%}** for the monthly incumbent.\n\n"
        f"At zero costs, monthly returned **{metric('monthly_incumbent', 'holdout', 0).cagr:.2%}**, full weekly **{metric('weekly_full_refresh', 'holdout', 0).cagr:.2%}**, buffered weekly **{metric('weekly_buffered', 'holdout', 0).cagr:.2%}**, and monthly-emergency **{metric('monthly_emergency', 'holdout', 0).cagr:.2%}**. The weekly shortfall therefore exists before fees and is amplified by turnover.\n\n"
        f"Deterministic: **{validation['deterministic']}**. ML embargo: **{validation['ml_embargo_pass']}**. Prefix invariance: **{validation['prefix_invariance_pass']}**. All portfolios long-only and fully invested: **{validation['all_long_only'] and validation['all_fully_invested']}**.\n\n"
        "This is schedule-sensitivity evidence on an already selection-contaminated retrospective candidate. No incumbent replacement, forward-clock change, paper trading, or live trading was authorized.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(comparison.to_string(index=False))
    return 0 if all(validation.values()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
