#!/usr/bin/env python3
"""Adversarial phase for Batch 66's retrospectively selected 52% ceiling."""

from __future__ import annotations

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
from scripts.run_aggressive_return_discovery_batch_62 import mix, rolling_win_share
from scripts.run_breadth_ceiling_adversarial_validation_batch_65 import ols_attribution
from scripts.run_exhaustive_return_first_discovery_batch_66 import metrics_for, monthly_alpha, static_weights
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, read_dated_csv
from systematic_trader.return_first_search import build_advanced_sources, delay_weights

CONFIG_PATH = ROOT / "config/batch66_retrospective_ceiling_adversarial.json"
MAIN_CONFIG_PATH = ROOT / "config/exhaustive_return_first_discovery_batch_66.json"
OUTPUT = ROOT / "evidence/exhaustive_return_first_discovery_batch_66/retrospective_ceiling_adversarial"
BREADTH_PATH = ROOT / "evidence/return_confirmation_diversification_batch_64/selected_or_best_weights.csv"


def alpha_blend(left: pd.DataFrame, right: pd.DataFrame, alpha: pd.Series) -> pd.DataFrame:
    columns = left.columns.union(right.columns)
    a = alpha.reindex(left.index).ffill().fillna(0.0)
    result = left.reindex(columns=columns, fill_value=0.0).mul(1.0 - a, axis=0)
    result = result.add(right.reindex(index=left.index, columns=columns, fill_value=0.0).mul(a, axis=0), fill_value=0.0)
    return result.div(result.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)


def source_alpha(prices: pd.DataFrame, universe: list[str], threshold: float, otherwise: float) -> pd.Series:
    r13 = prices.div(prices.shift(13)) - 1.0
    available = [asset for asset in universe if asset in prices]
    breadth = r13[available].gt(0.0).mean(axis=1).shift(1)
    weekly = pd.Series(np.where(breadth >= threshold, 1.0, otherwise), index=prices.index)
    return monthly_alpha(weekly, prices.index)


def selector(grid: dict[str, pd.DataFrame], paths: dict[str, pd.DataFrame], xlk: pd.DataFrame, prices: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = xlk.copy()
    choices = []
    for year in range(int(cfg["past_only_selector_first_year"]), prices.index.max().year + 1):
        dates = prices.index[prices.index.year == year]
        prior = prices.index[prices.index < dates.min()] if len(dates) else pd.DatetimeIndex([])
        if len(prior) < int(cfg["past_only_selector_training_weeks"]):
            continue
        end = prior.max()
        start = prior[-int(cfg["past_only_selector_training_weeks"])]
        scores = [(batch60.metrics(path.loc[start:end])["cagr"], name) for name, path in paths.items()]
        score, name = max(scores)
        output.loc[dates] = grid[name].reindex(dates).to_numpy()
        choices.append({"year": year, "selection_date": str(dates.min().date()), "candidate": name, "training_cagr": score})
    return output, pd.DataFrame(choices)


def main() -> int:
    cfg = json.loads(CONFIG_PATH.read_text())
    main_cfg = json.loads(MAIN_CONFIG_PATH.read_text())
    bundle = ROOT / "data/ggg_vintages" / main_cfg["data_bundle"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    training_end = pd.Timestamp(main_cfg["training_end"])
    xlk = static_weights(prices, {"XLK": 1.0})
    breadth_ceiling = read_dated_csv(BREADTH_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    sources = build_advanced_sources(
        prices, families=["rank_consensus"], universe=main_cfg["discovery_assets"],
        top_ns=cfg["neighborhood"]["top_n"], methods=["equal_weight", "score_inverse_volatility"], minimum_score=0.0,
    )
    grid = {}
    for threshold in cfg["neighborhood"]["breadth_thresholds"]:
        for otherwise in cfg["neighborhood"]["otherwise_source_weights"]:
            alpha = source_alpha(prices, main_cfg["discovery_assets"], float(threshold), float(otherwise))
            for top_n in cfg["neighborhood"]["top_n"]:
                for method in cfg["neighborhood"]["methods"]:
                    source = sources[f"rank_consensus__top{top_n}__{method}"]
                    name = f"threshold_{threshold:.2f}__low_{otherwise:.2f}__top{top_n}__{method}"
                    grid[name] = alpha_blend(xlk, source, alpha)
    frozen_name = "threshold_0.65__low_0.25__top1__score_invvol"
    candidate = grid[frozen_name]
    paths50 = {name: portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0) for name, weights in grid.items()}
    candidate_paths = {cost: portfolio_path(candidate, forward.reindex(columns=candidate.columns), float(cost)) for cost in cfg["cost_bps"]}
    xlk_paths = {cost: portfolio_path(xlk, forward.reindex(columns=xlk.columns), float(cost)) for cost in cfg["cost_bps"]}
    breadth_paths = {cost: portfolio_path(breadth_ceiling, forward.reindex(columns=breadth_ceiling.columns), float(cost)) for cost in cfg["cost_bps"]}
    candidate_metrics = {cost: metrics_for(path, training_end) for cost, path in candidate_paths.items()}
    xlk_metrics = {cost: metrics_for(path, training_end) for cost, path in xlk_paths.items()}
    breadth_metrics = {cost: metrics_for(path, training_end) for cost, path in breadth_paths.items()}

    neighborhood_rows = []
    for name, path in paths50.items():
        metrics = metrics_for(path, training_end)
        neighborhood_rows.append({"candidate": name, **metrics, "beats_xlk": metrics["holdout_cagr"] > xlk_metrics[50]["holdout_cagr"], "beats_breadth": metrics["holdout_cagr"] > breadth_metrics[50]["holdout_cagr"]})
    neighborhood = pd.DataFrame(neighborhood_rows).sort_values("holdout_cagr", ascending=False)

    delay_rows = []
    for weeks in cfg["additional_execution_delays_weeks"]:
        weights = delay_weights(candidate, int(weeks))
        path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
        metrics = metrics_for(path, training_end)
        delay_rows.append({"additional_delay_weeks": weeks, **metrics, "beats_xlk": metrics["holdout_cagr"] > xlk_metrics[50]["holdout_cagr"], "beats_breadth": metrics["holdout_cagr"] > breadth_metrics[50]["holdout_cagr"]})
    delays = pd.DataFrame(delay_rows)

    rng = np.random.default_rng(int(cfg["placebo_seed"]))
    frozen_alpha = source_alpha(prices, main_cfg["discovery_assets"], 0.65, 0.25)
    source = sources["rank_consensus__top1__score_invvol"]
    decisions = frozen_alpha.index.to_series().groupby(frozen_alpha.index.to_period("M")).tail(1).index
    decision_values = frozen_alpha.reindex(decisions).to_numpy()
    placebo_rows = []
    for permutation in range(int(cfg["placebo_permutations"])):
        shuffled = decision_values.copy(); rng.shuffle(shuffled)
        alpha = pd.Series(shuffled, index=decisions).reindex(prices.index).ffill().fillna(0.25)
        weights = alpha_blend(xlk, source, alpha)
        metrics = metrics_for(portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0), training_end)
        placebo_rows.append({"permutation": permutation, **metrics})
    placebos = pd.DataFrame(placebo_rows)
    placebo_percentile = float((placebos.holdout_cagr <= candidate_metrics[50]["holdout_cagr"]).mean())

    selector_weights, selector_choices = selector(grid, paths50, xlk, prices, cfg)
    selector_paths = {cost: portfolio_path(selector_weights, forward.reindex(columns=selector_weights.columns), float(cost)) for cost in cfg["cost_bps"]}
    selector_path = selector_paths[50]
    selector_metrics_by_cost = {cost: metrics_for(path, training_end) for cost, path in selector_paths.items()}
    selector_metrics = selector_metrics_by_cost[50]
    selector_delay_rows = []
    for weeks in cfg["additional_execution_delays_weeks"]:
        weights = delay_weights(selector_weights, int(weeks))
        path = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0)
        metrics = metrics_for(path, training_end)
        selector_delay_rows.append({"additional_delay_weeks": weeks, **metrics, "beats_xlk": metrics["holdout_cagr"] > xlk_metrics[50]["holdout_cagr"], "beats_breadth": metrics["holdout_cagr"] > breadth_metrics[50]["holdout_cagr"]})
    selector_delays = pd.DataFrame(selector_delay_rows)
    selector_rolling_share, selector_rolling_median, selector_rolling_worst = rolling_win_share(selector_path, xlk_paths[50])
    selector_holdout = selector_path.loc[selector_path.index > training_end]
    selector_years = [(batch60.metrics(group)["cagr"], int(year)) for year, group in selector_holdout.groupby(selector_holdout.index.year) if len(group) >= 40]
    selector_strongest_year = max(selector_years)[1]
    selector_keep = selector_holdout.index[selector_holdout.index.year != selector_strongest_year]
    selector_ex_candidate = batch60.metrics(selector_path.reindex(selector_keep))["cagr"]
    selector_ex_xlk = batch60.metrics(xlk_paths[50].reindex(selector_keep))["cagr"]
    selector_ex_breadth = batch60.metrics(breadth_paths[50].reindex(selector_keep))["cagr"]
    selector_difference = selector_path.loc[selector_path.index > training_end, "net_return"] - xlk_paths[50].loc[xlk_paths[50].index > training_end, "net_return"]
    selector_raw_pvalue = batch60.paired_block_pvalue(selector_difference.to_numpy(), samples=30000, block=13, seed=660013)
    rolling_share, rolling_median, rolling_worst = rolling_win_share(candidate_paths[50], xlk_paths[50])

    holdout = candidate_paths[50].loc[candidate_paths[50].index > training_end]
    full_years = [(batch60.metrics(group)["cagr"], int(year)) for year, group in holdout.groupby(holdout.index.year) if len(group) >= 40]
    strongest_year = max(full_years)[1]
    keep = holdout.index[holdout.index.year != strongest_year]
    ex_candidate = batch60.metrics(candidate_paths[50].reindex(keep))["cagr"]
    ex_xlk = batch60.metrics(xlk_paths[50].reindex(keep))["cagr"]
    ex_breadth = batch60.metrics(breadth_paths[50].reindex(keep))["cagr"]

    factor_returns = {}
    for asset in ("SPY", "QQQ", "XLK", "XLE"):
        weights = static_weights(prices, {asset: 1.0})
        factor_returns[asset] = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0).net_return
    attribution = pd.DataFrame(ols_attribution(candidate_paths[50].net_return, pd.DataFrame(factor_returns)))
    multifactor_alpha = float(attribution.loc[attribution.model == "multifactor", "annual_alpha"].iloc[0])
    selector_attribution = pd.DataFrame(ols_attribution(selector_path.net_return, pd.DataFrame(factor_returns)))
    selector_multifactor_alpha = float(selector_attribution.loc[selector_attribution.model == "multifactor", "annual_alpha"].iloc[0])

    rules = cfg["adversarial_gates"]
    gates = {
        "neighborhood": float(neighborhood.beats_xlk.mean()) >= rules["minimum_neighborhood_share_beating_xlk"],
        "delays": float(delays.beats_xlk.mean()) >= rules["minimum_delay_share_beating_xlk"],
        "placebo": placebo_percentile >= rules["minimum_placebo_percentile"],
        "past_only_selector": selector_metrics["holdout_cagr"] - xlk_metrics[50]["holdout_cagr"] >= rules["minimum_past_only_selector_advantage_over_xlk"],
        "excluded_best_year": ex_candidate - ex_xlk >= rules["minimum_ex_best_year_advantage_over_xlk"],
        "rolling": rolling_share >= rules["minimum_rolling_3y_win_share_over_xlk"],
        "multifactor_alpha": multifactor_alpha >= rules["minimum_multifactor_annual_alpha"],
        "full_return": candidate_metrics[50]["full_cagr"] >= rules["minimum_full_50bps_cagr"],
        "full_drawdown": abs(candidate_metrics[50]["full_drawdown"]) <= rules["maximum_full_50bps_drawdown_magnitude"],
        "cost_200": candidate_metrics[200]["holdout_cagr"] >= rules["minimum_holdout_200bps_cagr"],
    }
    confirmed = all(gates.values())
    selector_gates = {
        "beat_xlk": selector_metrics["holdout_cagr"] - xlk_metrics[50]["holdout_cagr"] >= 0.005,
        "beat_breadth": selector_metrics["holdout_cagr"] - breadth_metrics[50]["holdout_cagr"] >= 0.005,
        "cost_100": selector_metrics_by_cost[100]["holdout_cagr"] > breadth_metrics[100]["holdout_cagr"],
        "cost_200": selector_metrics_by_cost[200]["holdout_cagr"] >= 0.20,
        "delays": float(selector_delays.beats_breadth.mean()) >= 2.0 / 3.0,
        "excluded_best_year": selector_ex_candidate > max(selector_ex_xlk, selector_ex_breadth),
        "rolling": selector_rolling_share >= 0.5,
        "multifactor_alpha": selector_multifactor_alpha >= 0.0,
        "full_return": selector_metrics["full_cagr"] >= 0.04,
        "full_drawdown": abs(selector_metrics["full_drawdown"]) <= 0.5,
        "raw_pvalue": selector_raw_pvalue <= 0.10,
    }
    selector_confirmed = all(selector_gates.values())
    calendar_rows = []
    for label, path in (("candidate", candidate_paths[50]), ("XLK", xlk_paths[50]), ("breadth", breadth_paths[50])):
        for year, group in path.loc[path.index > training_end].groupby(path.loc[path.index > training_end].index.year):
            calendar_rows.append({"implementation": label, "year": int(year), **batch60.metrics(group)})

    OUTPUT.mkdir(parents=True, exist_ok=True)
    neighborhood.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    delays.to_csv(OUTPUT / "execution_delays.csv", index=False)
    placebos.to_csv(OUTPUT / "placebo_regimes.csv", index=False)
    selector_choices.to_csv(OUTPUT / "past_only_selector_choices.csv", index=False)
    selector_delays.to_csv(OUTPUT / "past_only_selector_delays.csv", index=False)
    pd.DataFrame(calendar_rows).to_csv(OUTPUT / "calendar_years.csv", index=False)
    attribution.to_csv(OUTPUT / "factor_attribution.csv", index=False)
    selector_attribution.to_csv(OUTPUT / "past_only_selector_factor_attribution.csv", index=False)
    candidate.rename_axis("Date").to_csv(OUTPUT / "frozen_candidate_weights.csv")
    candidate.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "current_holdings.csv")
    selector_weights.rename_axis("Date").to_csv(OUTPUT / "past_only_selector_weights.csv")
    selector_weights.iloc[-1].loc[lambda x: x > 1e-12].sort_values(ascending=False).rename("weight").to_csv(OUTPUT / "past_only_selector_current_holdings.csv")
    result = {
        "batch": "66B", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "candidate": cfg["frozen_candidate"],
        "holdout_50bps_cagr": candidate_metrics[50]["holdout_cagr"], "holdout_50bps_sharpe": candidate_metrics[50]["holdout_sharpe"],
        "holdout_50bps_drawdown": candidate_metrics[50]["holdout_drawdown"], "holdout_100bps_cagr": candidate_metrics[100]["holdout_cagr"],
        "holdout_200bps_cagr": candidate_metrics[200]["holdout_cagr"], "holdout_300bps_cagr": candidate_metrics[300]["holdout_cagr"],
        "xlk_holdout_cagr": xlk_metrics[50]["holdout_cagr"], "breadth_holdout_cagr": breadth_metrics[50]["holdout_cagr"],
        "neighborhood_count": len(neighborhood), "neighborhood_share_beating_xlk": float(neighborhood.beats_xlk.mean()),
        "neighborhood_share_beating_breadth": float(neighborhood.beats_breadth.mean()), "delay_share_beating_xlk": float(delays.beats_xlk.mean()),
        "placebo_percentile": placebo_percentile, "past_only_selector_holdout_cagr": selector_metrics["holdout_cagr"],
        "past_only_selector_holdout_sharpe": selector_metrics["holdout_sharpe"], "past_only_selector_holdout_drawdown": selector_metrics["holdout_drawdown"],
        "past_only_selector_100bps_cagr": selector_metrics_by_cost[100]["holdout_cagr"], "past_only_selector_200bps_cagr": selector_metrics_by_cost[200]["holdout_cagr"],
        "past_only_selector_full_cagr": selector_metrics["full_cagr"], "past_only_selector_full_drawdown": selector_metrics["full_drawdown"],
        "past_only_selector_delay_share_beating_breadth": float(selector_delays.beats_breadth.mean()),
        "past_only_selector_ex_best_year_advantage_over_xlk": selector_ex_candidate - selector_ex_xlk,
        "past_only_selector_ex_best_year_advantage_over_breadth": selector_ex_candidate - selector_ex_breadth,
        "past_only_selector_rolling_3y_win_share_over_xlk": selector_rolling_share,
        "past_only_selector_rolling_median_advantage": selector_rolling_median, "past_only_selector_rolling_worst_advantage": selector_rolling_worst,
        "past_only_selector_multifactor_annual_alpha": selector_multifactor_alpha, "past_only_selector_raw_pvalue": selector_raw_pvalue,
        "past_only_selector_gates": selector_gates, "past_only_selector_confirmation_pass": selector_confirmed,
        "excluded_strongest_year": strongest_year, "ex_best_year_advantage_over_xlk": ex_candidate - ex_xlk,
        "ex_best_year_advantage_over_breadth": ex_candidate - ex_breadth, "rolling_3y_win_share_over_xlk": rolling_share,
        "rolling_median_advantage": rolling_median, "rolling_worst_advantage": rolling_worst, "multifactor_annual_alpha": multifactor_alpha,
        "full_50bps_cagr": candidate_metrics[50]["full_cagr"], "full_50bps_drawdown": candidate_metrics[50]["full_drawdown"],
        "gates": gates, "adversarial_confirmation_pass": confirmed,
        "decision": "promote_past_only_selector_as_provisional_return_replacement" if selector_confirmed else "retain_52pct_ceiling_and_past_only_selector_as_unconfirmed_high_return_research",
        "retrospectively_selected": True, "leverage_used": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failed = [name for name, passed in gates.items() if not passed]
    selector_failed = [name for name, passed in selector_gates.items() if not passed]
    (OUTPUT / "report.md").write_text(
        "# Batch 66B — adversarial challenge of the 52% retrospective ceiling\n\n"
        f"The frozen rule returned **{candidate_metrics[50]['holdout_cagr']:.2%}** at 50 bps, **{candidate_metrics[100]['holdout_cagr']:.2%}** at 100 bps, and **{candidate_metrics[200]['holdout_cagr']:.2%}** at 200 bps versus XLK **{xlk_metrics[50]['holdout_cagr']:.2%}**.\n\n"
        f"Adversarial confirmation: **{confirmed}**. Failed gates: `{', '.join(failed) if failed else 'none'}`. Neighborhood share beating XLK: **{neighborhood.beats_xlk.mean():.1%}**; delay share: **{delays.beats_xlk.mean():.1%}**; placebo percentile: **{placebo_percentile:.1%}**; past-only selector: **{selector_metrics['holdout_cagr']:.2%}**.\n\n"
        f"The strictly past-only selector returned **{selector_metrics['holdout_cagr']:.2%}** at 50 bps, **{selector_metrics_by_cost[100]['holdout_cagr']:.2%}** at 100 bps, and **{selector_metrics_by_cost[200]['holdout_cagr']:.2%}** at 200 bps. Selector confirmation: **{selector_confirmed}**; failed gates: `{', '.join(selector_failed) if selector_failed else 'none'}`.\n\n"
        f"Decision: `{result['decision']}`. The rule remains explicitly marked as retrospectively selected. No leverage or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
