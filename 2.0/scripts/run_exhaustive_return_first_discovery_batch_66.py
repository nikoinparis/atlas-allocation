#!/usr/bin/env python3
"""Exhaustive, predeclared return-first discovery and adversarial validation."""

from __future__ import annotations

import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts import run_ggg_saved_strategy_improvement_batch_60 as batch60
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from scripts.run_breadth_ceiling_adversarial_validation_batch_65 import ols_attribution
from scripts.run_return_confirmation_diversification_batch_64 import alpha_blend, monthly_decisions
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.return_confirmation import cross_asset_features, four_week_labels
from systematic_trader.return_first_search import (
    build_advanced_sources,
    delay_weights,
    regime_source_alphas,
)

CONFIG_PATH = ROOT / "config/exhaustive_return_first_discovery_batch_66.json"
OUTPUT = ROOT / "evidence/exhaustive_return_first_discovery_batch_66"
BREADTH_WEIGHTS = ROOT / "evidence/return_confirmation_diversification_batch_64/selected_or_best_weights.csv"


def static_weights(prices: pd.DataFrame, allocations: dict[str, float]) -> pd.DataFrame:
    columns = prices.columns.union(pd.Index(["cash::USD"]))
    result = pd.DataFrame(0.0, index=prices.index, columns=columns)
    for asset, weight in allocations.items():
        if asset not in result:
            raise ValueError(f"missing asset {asset}")
        result[asset] = float(weight)
    if not np.isclose(result.sum(axis=1).iloc[-1], 1.0):
        raise ValueError("static allocation must sum to one")
    return result


def monthly_alpha(series: pd.Series, index: pd.DatetimeIndex) -> pd.Series:
    decisions = monthly_decisions(index)
    return series.reindex(decisions).reindex(index).ffill().fillna(float(series.dropna().iloc[0]) if series.notna().any() else 0.25)


def build_candidate_universe(prices: pd.DataFrame, config: dict) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    breadth = read_dated_csv(BREADTH_WEIGHTS).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    xlk = static_weights(prices, {"XLK": 1.0})
    sources = build_advanced_sources(
        prices,
        families=config["signal_families"],
        universe=config["discovery_assets"],
        top_ns=config["top_n"],
        methods=config["portfolio_methods"],
        minimum_score=float(config["minimum_score"]),
    )
    regimes = {name: monthly_alpha(alpha, prices.index) for name, alpha in regime_source_alphas(prices, config["discovery_assets"]).items()}
    candidates: dict[str, pd.DataFrame] = {"comparison::breadth_ceiling": breadth}
    inventory = [{"candidate": "comparison::breadth_ceiling", "signal_family": "existing", "construction": "comparison", "holdout_eligible": False}]

    for asset in config["simple_benchmarks"]:
        name = f"benchmark::{asset}"
        candidates[name] = static_weights(prices, {asset: 1.0})
        inventory.append({"candidate": name, "signal_family": "benchmark", "construction": "benchmark", "holdout_eligible": True})
    for label, allocations in config["fixed_benchmark_portfolios"].items():
        name = f"benchmark_portfolio::{label}"
        candidates[name] = static_weights(prices, allocations)
        inventory.append({"candidate": name, "signal_family": "benchmark_portfolio", "construction": "benchmark_portfolio", "holdout_eligible": True})

    for source_name, source in sources.items():
        family = source_name.split("__", 1)[0]
        name = f"standalone::{source_name}"
        candidates[name] = source
        inventory.append({"candidate": name, "signal_family": family, "construction": "standalone", "holdout_eligible": True})
        for source_weight in config["source_weights_in_core_blends"]:
            token = int(round(float(source_weight) * 100))
            name = f"xlk_blend::{source_name}::{token}"
            candidates[name] = mix([xlk, source], [1.0 - source_weight, source_weight])
            inventory.append({"candidate": name, "signal_family": family, "construction": "xlk_blend", "holdout_eligible": True})
            name = f"ceiling_blend::{source_name}::{token}"
            candidates[name] = mix([breadth, source], [1.0 - source_weight, source_weight])
            inventory.append({"candidate": name, "signal_family": family, "construction": "ceiling_blend", "holdout_eligible": True})
        for regime_name in config["dynamic_regimes"]:
            name = f"regime::{regime_name}::{source_name}"
            candidates[name] = alpha_blend(xlk, source, regimes[regime_name])
            inventory.append({"candidate": name, "signal_family": family, "construction": f"regime_{regime_name}", "holdout_eligible": True})
    return candidates, pd.DataFrame(inventory)


def path_score(path: pd.DataFrame, end: pd.Timestamp) -> tuple[float, dict[str, float]]:
    history = path.loc[:end]
    trailing5 = history.loc[history.index >= end - pd.DateOffset(years=5)]
    trailing3 = history.loc[history.index >= end - pd.DateOffset(years=3)]
    m5 = batch60.metrics(trailing5)
    m3 = batch60.metrics(trailing3)
    score = 0.60 * m5["cagr"] + 0.30 * m3["cagr"] + 0.10 * m5["sharpe_zero_rf"]
    return float(score), {
        "training_5y_cagr": m5["cagr"], "training_3y_cagr": m3["cagr"],
        "training_5y_sharpe": m5["sharpe_zero_rf"], "training_5y_drawdown": m5["max_drawdown"],
    }


def training_rankings(
    paths: dict[str, pd.DataFrame], inventory: pd.DataFrame, training_end: pd.Timestamp,
) -> pd.DataFrame:
    meta = inventory.set_index("candidate")
    rows = []
    for name, path in paths.items():
        if name not in meta.index or not bool(meta.loc[name, "holdout_eligible"]):
            continue
        score, details = path_score(path, training_end)
        rows.append({"candidate": name, "training_score": score, **meta.loc[name].to_dict(), **details})
    return pd.DataFrame(rows).sort_values("training_score", ascending=False).reset_index(drop=True)


def build_walk_forward_selectors(
    candidate_weights: dict[str, pd.DataFrame], paths50: dict[str, pd.DataFrame],
    prices: pd.DataFrame, training: pd.DataFrame, config: dict,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    eligible = training.candidate.tolist()
    xlk = candidate_weights["benchmark::XLK"]
    outputs = {
        "selector::top1": xlk.copy(),
        "selector::equal_top3": xlk.copy(),
    }
    choices = []
    for year in range(int(config["walk_forward"]["first_selection_year"]), prices.index.max().year + 1):
        year_dates = prices.index[prices.index.year == year]
        if len(year_dates) == 0:
            continue
        selection_date = year_dates.min()
        prior_dates = prices.index[prices.index < selection_date]
        if len(prior_dates) < int(config["walk_forward"]["training_weeks"]):
            continue
        end = prior_dates.max()
        scores = []
        for name in eligible:
            score, _ = path_score(paths50[name], end)
            scores.append((score, name))
        ordered = sorted(scores, reverse=True)
        top = [name for _, name in ordered[:3]]
        outputs["selector::top1"].loc[year_dates] = candidate_weights[top[0]].reindex(year_dates).to_numpy()
        top3 = mix([candidate_weights[name] for name in top], [1 / 3, 1 / 3, 1 / 3])
        outputs["selector::equal_top3"].loc[year_dates] = top3.reindex(year_dates).to_numpy()
        choices.append({"selection_year": year, "selection_date": str(selection_date.date()), "top1": top[0], "top2": top[1], "top3": top[2], "top1_training_score": ordered[0][0]})
    return outputs, pd.DataFrame(choices)


def _model(name: str, seed: int):
    if name == "random_forest":
        return RandomForestRegressor(n_estimators=120, max_depth=4, min_samples_leaf=8, max_features=0.75, random_state=seed, n_jobs=1)
    if name == "extra_trees":
        return ExtraTreesRegressor(n_estimators=120, max_depth=4, min_samples_leaf=8, max_features=0.75, random_state=seed, n_jobs=1)
    if name == "gradient_boosting":
        return GradientBoostingRegressor(n_estimators=100, max_depth=2, min_samples_leaf=8, learning_rate=0.03, loss="huber", random_state=seed)
    if name == "hist_gradient_boosting":
        return HistGradientBoostingRegressor(max_iter=100, max_depth=3, min_samples_leaf=12, learning_rate=0.05, l2_regularization=1.0, random_state=seed)
    raise ValueError(name)


def nonlinear_predictions(
    features: pd.DataFrame, labels: pd.DataFrame, decisions: pd.DatetimeIndex,
    model_name: str, minimum_training: int, seed: int,
) -> tuple[pd.Series, pd.DataFrame]:
    predictions = pd.Series(np.nan, index=features.index, dtype=float)
    audit = []
    for decision in decisions:
        row = features.reindex([decision])
        if row.isna().all(axis=1).iloc[0]:
            continue
        eligible = labels[(labels.label_end < decision) & labels.index.isin(features.index)]
        if len(eligible) < minimum_training:
            audit.append({"decision": decision, "training_rows": len(eligible), "maximum_label_end": pd.NaT, "embargo_pass": True, "predicted": False})
            continue
        x_train = features.reindex(eligible.index)
        keep = x_train.notna().sum(axis=0) >= max(12, len(x_train) // 3)
        x_train = x_train.loc[:, keep]
        x_row = row.loc[:, keep]
        imputer = SimpleImputer(strategy="median")
        x = imputer.fit_transform(x_train)
        x_new = imputer.transform(x_row)
        model = _model(model_name, seed)
        model.fit(x, eligible.label.to_numpy(dtype=float))
        predictions.loc[decision] = float(model.predict(x_new)[0])
        maximum = eligible.label_end.max()
        audit.append({"decision": decision, "training_rows": len(eligible), "maximum_label_end": maximum, "embargo_pass": bool(maximum < decision), "predicted": True})
    return predictions.reindex(decisions).reindex(features.index).ffill(), pd.DataFrame(audit)


def build_ml_candidates(
    prices: pd.DataFrame, forward: pd.DataFrame, xlk: pd.DataFrame, breadth: pd.DataFrame, config: dict,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    decisions = monthly_decisions(prices.index)
    features = cross_asset_features(prices, config["discovery_assets"])
    xlk_gross = portfolio_path(xlk, forward.reindex(columns=xlk.columns), 0.0).net_return
    breadth_gross = portfolio_path(breadth, forward.reindex(columns=breadth.columns), 0.0).net_return
    labels = four_week_labels(breadth_gross - xlk_gross, decisions, int(config["nonlinear_ml"]["label_horizon_weeks"]))
    result, audits = {}, []
    for index, model_name in enumerate(config["nonlinear_ml"]["models"]):
        predictions, audit = nonlinear_predictions(
            features, labels, decisions, model_name,
            int(config["nonlinear_ml"]["minimum_training_months"]),
            int(config["nonlinear_ml"]["random_seed"]) + index,
        )
        audit["model"] = model_name
        audits.append(audit)
        for rule in config["nonlinear_ml"]["allocation_rules"]:
            alpha_at_decisions = pd.Series(0.0, index=decisions, dtype=float)
            history: list[float] = []
            for decision in decisions:
                prediction = predictions.get(decision)
                if pd.isna(prediction):
                    alpha_at_decisions.loc[decision] = 0.0
                    continue
                if rule == "sign":
                    alpha_at_decisions.loc[decision] = 1.0 if prediction > 0.0 else 0.0
                else:
                    threshold = float(np.quantile(np.abs(history), 0.70)) if len(history) >= 24 else np.inf
                    alpha_at_decisions.loc[decision] = 1.0 if prediction > threshold else 0.0 if prediction < 0.0 else 0.5
                history.append(float(prediction))
            alpha = alpha_at_decisions.reindex(prices.index).ffill().fillna(0.0)
            result[f"ml::{model_name}::{rule}"] = alpha_blend(xlk, breadth, alpha)
    return result, pd.concat(audits, ignore_index=True)


def metrics_for(path: pd.DataFrame, training_end: pd.Timestamp) -> dict[str, float]:
    holdout = path.loc[path.index > training_end]
    full = batch60.metrics(path)
    recent = batch60.metrics(holdout)
    return {
        "holdout_cagr": recent["cagr"], "holdout_sharpe": recent["sharpe_zero_rf"],
        "holdout_sortino": recent["sortino_zero_target"], "holdout_drawdown": recent["max_drawdown"],
        "holdout_turnover": recent["annual_one_way_turnover"], "full_cagr": full["cagr"],
        "full_sharpe": full["sharpe_zero_rf"], "full_drawdown": full["max_drawdown"],
    }


def excluded_best_year(candidate: pd.DataFrame, comparison: pd.DataFrame, training_end: pd.Timestamp) -> tuple[int, float]:
    holdout = candidate.loc[candidate.index > training_end]
    years = []
    for year, group in holdout.groupby(holdout.index.year):
        if len(group) >= 40:
            years.append((batch60.metrics(group)["cagr"], int(year)))
    strongest = max(years)[1]
    keep = holdout.index[holdout.index.year != strongest]
    advantage = batch60.metrics(candidate.reindex(keep))["cagr"] - batch60.metrics(comparison.reindex(keep))["cagr"]
    return strongest, float(advantage)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text())
    bundle = ROOT / "data/ggg_vintages" / config["data_bundle"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    training_end = pd.Timestamp(config["training_end"])

    candidates, inventory = build_candidate_universe(prices, config)
    expected_sources = len(config["signal_families"]) * len(config["top_n"]) * len(config["portfolio_methods"])
    expected_candidates = 1 + len(config["simple_benchmarks"]) + len(config["fixed_benchmark_portfolios"]) + expected_sources * (1 + 2 * len(config["source_weights_in_core_blends"]) + len(config["dynamic_regimes"]))
    if len(candidates) != expected_candidates:
        raise RuntimeError(f"candidate budget mismatch {len(candidates)} != {expected_candidates}")

    repeated, _ = build_candidate_universe(prices, config)
    determinism = pd.DataFrame([
        {"candidate": name, "first_hash": batch60.frame_hash(frame), "second_hash": batch60.frame_hash(repeated[name]), "deterministic": batch60.frame_hash(frame) == batch60.frame_hash(repeated[name])}
        for name, frame in candidates.items()
    ])
    paths50 = {name: portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0) for name, weights in candidates.items()}
    training = training_rankings(paths50, inventory, training_end)
    overall_training_winner = str(training.iloc[0].candidate)

    finalist_names = {overall_training_winner}
    for column in ("signal_family", "construction"):
        finalist_names.update(training.sort_values("training_score", ascending=False).groupby(column, sort=False).head(int(config["family_finalists_per_family"])).candidate)

    selectors, selector_choices = build_walk_forward_selectors(candidates, paths50, prices, training, config)
    candidates.update(selectors)
    ml_candidates, ml_audit = build_ml_candidates(prices, forward, candidates["benchmark::XLK"], candidates["comparison::breadth_ceiling"], config)
    candidates.update(ml_candidates)
    finalist_names.update(selectors)
    finalist_names.update(ml_candidates)
    finalist_names = sorted(finalist_names)

    prefix_rows = []
    for cutoff_text in ("2025-12-26", "2026-04-10", "2026-07-31"):
        cutoff = pd.Timestamp(cutoff_text)
        prefix_candidates, _ = build_candidate_universe(prices.loc[:cutoff], config)
        for name in inventory[inventory.construction == "standalone"].candidate:
            expected = candidates[name].loc[:cutoff]
            actual = prefix_candidates[name].reindex_like(expected)
            difference = float((expected - actual).abs().max().max())
            prefix_rows.append({"candidate": name, "cutoff": cutoff_text, "maximum_weight_difference": difference, "prefix_pass": difference <= 1e-12})
    prefixes = pd.DataFrame(prefix_rows)

    all_holdout_rows = []
    for name, path in paths50.items():
        all_holdout_rows.append({"candidate": name, **metrics_for(path, training_end)})
    retrospective = pd.DataFrame(all_holdout_rows).sort_values("holdout_cagr", ascending=False)
    retrospective_ceiling = str(retrospective.iloc[0].candidate)

    cost_paths: dict[str, dict[int, pd.DataFrame]] = {}
    for name in set(finalist_names) | {"comparison::breadth_ceiling", "benchmark::XLK"}:
        weights = candidates[name]
        cost_paths[name] = {int(cost): portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost)) for cost in config["cost_bps"]}

    breadth50 = cost_paths["comparison::breadth_ceiling"][50]
    xlk50 = cost_paths["benchmark::XLK"][50]
    breadth_metrics = {cost: metrics_for(cost_paths["comparison::breadth_ceiling"][cost], training_end) for cost in config["cost_bps"]}
    xlk_metrics = {cost: metrics_for(cost_paths["benchmark::XLK"][cost], training_end) for cost in config["cost_bps"]}
    rules = config["promotion_gates"]
    validation_rows, delay_rows = [], []
    trial_count = len(finalist_names)
    for name in finalist_names:
        by_cost = {cost: metrics_for(cost_paths[name][int(cost)], training_end) for cost in config["cost_bps"]}
        primary = by_cost[50]
        share, rolling_median, rolling_worst = rolling_win_share(cost_paths[name][50], xlk50)
        holdout_difference = cost_paths[name][50].loc[cost_paths[name][50].index > training_end, "net_return"] - xlk50.loc[xlk50.index > training_end, "net_return"]
        raw_p = batch60.paired_block_pvalue(
            holdout_difference.to_numpy(), samples=int(config["bootstrap_samples"]),
            block=int(config["bootstrap_block_weeks"]), seed=int(hashlib.sha256(name.encode()).hexdigest()[:8], 16),
        )
        adjusted_p = min(1.0, raw_p * trial_count)
        delayed_advantages = []
        for weeks in config["additional_execution_delays_weeks"]:
            delayed = delay_weights(candidates[name], int(weeks))
            delayed_path = portfolio_path(delayed, forward.reindex(columns=delayed.columns), 50.0)
            delayed_metric = metrics_for(delayed_path, training_end)
            advantage = delayed_metric["holdout_cagr"] - breadth_metrics[50]["holdout_cagr"]
            delayed_advantages.append(advantage)
            delay_rows.append({"candidate": name, "additional_delay_weeks": weeks, **delayed_metric, "holdout_cagr_advantage_over_breadth": advantage})
        strongest_year, ex_year_advantage = excluded_best_year(cost_paths[name][50], breadth50, training_end)
        checks = {
            "beat_xlk": primary["holdout_cagr"] - xlk_metrics[50]["holdout_cagr"] >= rules["minimum_holdout_cagr_advantage_over_xlk"],
            "beat_breadth": primary["holdout_cagr"] - breadth_metrics[50]["holdout_cagr"] >= rules["minimum_holdout_cagr_advantage_over_breadth_ceiling"],
            "cost_100": by_cost[100]["holdout_cagr"] - breadth_metrics[100]["holdout_cagr"] >= rules["minimum_holdout_100bps_cagr_advantage_over_breadth_ceiling"],
            "cost_200": by_cost[200]["holdout_cagr"] >= rules["minimum_holdout_200bps_cagr"],
            "drawdown": abs(primary["holdout_drawdown"]) <= rules["maximum_holdout_drawdown_magnitude"],
            "full_return": primary["full_cagr"] >= rules["minimum_full_cagr"],
            "delays": float(np.mean(np.asarray(delayed_advantages) > 0.0)) >= rules["minimum_delay_share_beating_breadth_ceiling"],
            "excluded_best_year": ex_year_advantage >= rules["minimum_ex_best_year_advantage_over_breadth_ceiling"],
            "rolling": share >= rules["minimum_rolling_3y_win_share_over_xlk"],
            "multiplicity": adjusted_p <= rules["maximum_familywise_adjusted_pvalue"],
        }
        validation_rows.append({
            "candidate": name, **primary,
            "holdout_cagr_advantage_over_xlk": primary["holdout_cagr"] - xlk_metrics[50]["holdout_cagr"],
            "holdout_cagr_advantage_over_breadth": primary["holdout_cagr"] - breadth_metrics[50]["holdout_cagr"],
            "holdout_100bps_cagr": by_cost[100]["holdout_cagr"], "holdout_200bps_cagr": by_cost[200]["holdout_cagr"],
            "rolling_3y_win_share_over_xlk": share, "rolling_median_advantage": rolling_median,
            "rolling_worst_advantage": rolling_worst, "raw_pvalue": raw_p,
            "familywise_adjusted_pvalue": adjusted_p, "delay_win_share_over_breadth": float(np.mean(np.asarray(delayed_advantages) > 0.0)),
            "excluded_strongest_year": strongest_year, "ex_best_year_advantage_over_breadth": ex_year_advantage,
            **{f"gate_{key}": value for key, value in checks.items()}, "qualified": all(checks.values()),
        })
    validation = pd.DataFrame(validation_rows).sort_values(["qualified", "holdout_cagr"], ascending=False)
    delays = pd.DataFrame(delay_rows)
    passing = validation[validation.qualified]
    selected = str(passing.iloc[0].candidate) if len(passing) else None
    validation_point_leader = str(validation.iloc[0].candidate)
    saved_name = selected or validation_point_leader

    calendar_rows = []
    for name in (saved_name, "benchmark::XLK", "comparison::breadth_ceiling"):
        path = cost_paths[name][50].loc[cost_paths[name][50].index > training_end]
        for year, group in path.groupby(path.index.year):
            calendar_rows.append({"candidate": name, "year": int(year), **batch60.metrics(group)})
    calendar = pd.DataFrame(calendar_rows)

    factor_paths = {}
    for asset in ("SPY", "QQQ", "XLK", "XLE"):
        if f"benchmark::{asset}" in candidates:
            factor_paths[asset] = portfolio_path(candidates[f"benchmark::{asset}"], forward.reindex(columns=candidates[f"benchmark::{asset}"].columns), 50.0).net_return
    attribution = pd.DataFrame(ols_attribution(cost_paths[saved_name][50].net_return, pd.DataFrame(factor_paths)))

    OUTPUT.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(OUTPUT / "candidate_inventory.csv", index=False)
    training.to_csv(OUTPUT / "training_rankings.csv", index=False)
    retrospective.to_csv(OUTPUT / "retrospective_all_candidate_holdout_leaderboard.csv", index=False)
    validation.to_csv(OUTPUT / "holdout_validation.csv", index=False)
    delays.to_csv(OUTPUT / "execution_delay_stress.csv", index=False)
    calendar.to_csv(OUTPUT / "calendar_years.csv", index=False)
    selector_choices.to_csv(OUTPUT / "walk_forward_selector_choices.csv", index=False)
    ml_audit.to_csv(OUTPUT / "nonlinear_ml_embargo_audit.csv", index=False)
    prefixes.to_csv(OUTPUT / "source_prefix_invariance.csv", index=False)
    determinism.to_csv(OUTPUT / "candidate_determinism.csv", index=False)
    attribution.to_csv(OUTPUT / "factor_attribution.csv", index=False)
    candidates[saved_name].rename_axis("Date").to_csv(OUTPUT / "selected_or_best_weights.csv")
    candidates[saved_name].iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "selected_or_best_current_holdings.csv")
    candidates[retrospective_ceiling].rename_axis("Date").to_csv(OUTPUT / "retrospective_ceiling_weights.csv")

    best = validation.iloc[0]
    retro = retrospective.iloc[0]
    result = {
        "batch": 66, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "predeclared_candidate_count": expected_candidates, "advanced_source_count": expected_sources,
        "validation_finalist_count": trial_count, "nonlinear_ml_candidate_count": len(ml_candidates),
        "deterministic": bool(determinism.deterministic.all()), "prefix_invariance_pass": bool(prefixes.prefix_pass.all()),
        "ml_embargo_pass": bool(ml_audit.embargo_pass.all()), "ml_predictions": int(ml_audit.predicted.sum()),
        "training_selected_candidate": overall_training_winner,
        "breadth_holdout_50bps_cagr": breadth_metrics[50]["holdout_cagr"],
        "xlk_holdout_50bps_cagr": xlk_metrics[50]["holdout_cagr"],
        "retrospective_all_candidate_ceiling": retrospective_ceiling,
        "retrospective_all_candidate_ceiling_holdout_cagr": float(retro.holdout_cagr),
        "validation_point_leader": validation_point_leader,
        "validation_point_leader_holdout_cagr": float(best.holdout_cagr),
        "validation_point_leader_holdout_sharpe": float(best.holdout_sharpe),
        "validation_point_leader_holdout_drawdown": float(best.holdout_drawdown),
        "qualified_replacement_count": int(len(passing)), "selected_replacement": selected,
        "saved_research_candidate": saved_name,
        "decision": "promote_provisional_return_replacement" if selected else "retain_current_strategy_and_save_unconfirmed_research_ceiling",
        "existing_forward_protocol_untouched": True, "retrospective_research_only": True,
        "leverage_used": False, "shorting_used": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failed = [column.removeprefix("gate_") for column in validation.columns if column.startswith("gate_") and not bool(best[column])]
    (OUTPUT / "report.md").write_text(
        "# Batch 66 — exhaustive return-first discovery and validation\n\n"
        f"The frozen campaign evaluated **{expected_candidates}** candidates built from **{expected_sources}** advanced causal sources, benchmark-aware blends, four regime rules, simple benchmark portfolios, two past-only selectors, and **{len(ml_candidates)}** nonlinear embargoed ML allocators. "
        f"Determinism: **{bool(determinism.deterministic.all())}**; prefix invariance: **{bool(prefixes.prefix_pass.all())}**; ML embargo: **{bool(ml_audit.embargo_pass.all())}**.\n\n"
        f"The breadth ceiling returned **{breadth_metrics[50]['holdout_cagr']:.2%}** and XLK returned **{xlk_metrics[50]['holdout_cagr']:.2%}** after the frozen training cutoff. "
        f"The unrestricted retrospective ceiling was `{retrospective_ceiling}` at **{retro.holdout_cagr:.2%}**, but it is not eligible for promotion because the same holdout selected it.\n\n"
        f"Among **{trial_count}** candidates fixed without using holdout outcomes, `{validation_point_leader}` was best at **{best.holdout_cagr:.2%}** CAGR, Sharpe **{best.holdout_sharpe:.3f}**, and drawdown **{best.holdout_drawdown:.2%}**. "
        f"Qualified replacements: **{len(passing)}**. Selected replacement: `{selected}`. Failed gates for the point leader: `{', '.join(failed) if failed else 'none'}`.\n\n"
        f"Decision: `{result['decision']}`. The existing 52-week forward protocol was not modified. No leverage, shorting, live trading, or paper-broker execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["deterministic"] and result["prefix_invariance_pass"] and result["ml_embargo_pass"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "failure_traceback.txt").write_text(traceback.format_exc())
        raise
