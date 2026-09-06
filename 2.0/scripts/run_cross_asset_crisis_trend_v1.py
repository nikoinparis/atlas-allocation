#!/usr/bin/env python3
"""Evaluate one preregistered non-equity trend diversifier and its fixed blend."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.cross_asset_trend import (  # noqa: E402
    _capped_inverse_volatility,
    apply_next_week_returns,
    blend_returns,
    build_trend_weights,
    performance_metrics,
)


CONFIG = ROOT / "config/cross_asset_crisis_trend_v1.json"
OUTPUT = ROOT / "evidence/cross_asset_crisis_trend_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_prices(bundle: str) -> tuple[pd.DataFrame, Path]:
    path = ROOT / "data/ggg_vintages" / bundle / "data/01_data_hub/weekly_prices.csv"
    frame = pd.read_csv(path)
    date_column = frame.columns[0]
    frame[date_column] = pd.to_datetime(frame[date_column]).dt.tz_localize(None)
    return frame.set_index(date_column).apply(pd.to_numeric, errors="coerce").sort_index(), path


def saved_strategy_returns(source: Path) -> pd.DataFrame:
    payload = json.loads(source.read_text())
    series: dict[str, pd.Series] = {}
    for item in payload["strategies"]:
        rows = pd.DataFrame(item["records"])
        rows["date"] = pd.to_datetime(rows["date"], utc=True).dt.tz_localize(None)
        series[item["strategy"]["id"]] = rows.set_index("date").netReturn.astype(float)
    return pd.concat(series, axis=1, sort=True).sort_index().dropna()


def block_bootstrap_pvalue(difference: pd.Series, samples: int = 20_000, block: int = 13) -> float:
    values = difference.dropna().to_numpy(dtype=float)
    centered = values - values.mean()
    rng = np.random.default_rng(20260827)
    starts = np.arange(len(values) - block + 1)
    nonpositive = 0
    blocks_needed = math.ceil(len(values) / block)
    for _ in range(samples):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([centered[start:start + block] for start in chosen])[: len(values)]
        if sample.mean() >= values.mean():
            nonpositive += 1
    return float((nonpositive + 1) / (samples + 1))


def contribution_table(returns: pd.DataFrame) -> pd.DataFrame:
    count = returns.shape[1]
    weights = np.repeat(1.0 / count, count)
    annual_mean = returns.mean() * 52.0
    covariance = returns.cov() * 52.0
    portfolio_variance = float(weights @ covariance.to_numpy() @ weights)
    risk = weights * (covariance.to_numpy() @ weights) / portfolio_variance
    arithmetic = weights * annual_mean.to_numpy()
    return pd.DataFrame(
        {
            "strategy": returns.columns,
            "annual_arithmetic_return_contribution": arithmetic,
            "return_contribution_share": arithmetic / arithmetic.sum(),
            "variance_risk_contribution_share": risk,
        }
    ).sort_values("variance_risk_contribution_share", ascending=False)


def random_placebo_weights(
    prices: pd.DataFrame,
    primary: pd.DataFrame,
    assets: list[str],
    cash_asset: str,
    cap: float,
    seed: int,
    evaluation_index: pd.Index,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    weekly = prices[assets].pct_change(fill_method=None)
    volatility = weekly.rolling(26, min_periods=13).std(ddof=1) * math.sqrt(52.0)
    local_primary = primary.reindex(evaluation_index)
    changes = local_primary.diff().abs().sum(axis=1).fillna(0.0) > 1e-12
    changes.iloc[0] = True
    targets: dict[pd.Timestamp, pd.Series] = {}
    for date in local_primary.index[changes]:
        if changes.loc[date]:
            active_count = int((local_primary.loc[date, assets] > 1e-12).sum())
            available = volatility.loc[date].replace([np.inf, -np.inf], np.nan).dropna()
            available = available[available > 0.0]
            chosen = rng.choice(available.index.to_numpy(), size=min(active_count, len(available)), replace=False) if active_count else []
            target = pd.Series(0.0, index=primary.columns, dtype=float)
            if len(chosen):
                risk = _capped_inverse_volatility(available.loc[list(chosen)], cap)
                target.loc[risk.index] = risk
            target[cash_asset] = max(0.0, 1.0 - float(target.sum()))
            targets[date] = target
    return pd.DataFrame.from_dict(targets, orient="index").reindex(evaluation_index).ffill().fillna(0.0)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    trend_config = config["trend_sleeve"]
    source = ROOT / config["base_portfolio"]["source"]
    prices, price_path = read_prices(config["source_price_bundle"])
    saved = saved_strategy_returns(source)
    excluded = config["base_portfolio"]["excluded_strategy"]
    if excluded not in saved:
        raise RuntimeError(f"excluded strategy is absent: {excluded}")
    base = saved.drop(columns=[excluded]).mean(axis=1).rename("five_sleeve_base")
    all_six = saved.mean(axis=1).rename("all_six_equal_weight")

    assets = list(trend_config["assets"])
    cash_asset = str(trend_config["cash_asset"])
    primary_weights = build_trend_weights(
        prices,
        assets,
        cash_asset,
        trend_config["signal_lookbacks_weeks"],
        int(trend_config["volatility_lookback_weeks"]),
        int(trend_config["minimum_volatility_observations"]),
        float(trend_config["maximum_asset_weight"]),
        int(trend_config["rebalance_every_weeks"]),
    )

    score_rows: list[dict] = []
    paths: dict[str, pd.Series] = {"all_six": all_six, "five_sleeve_base": base}
    score_rows.extend(
        [
            {"portfolio": "all_six", "cost_bps": "native", **performance_metrics(all_six)},
            {"portfolio": "five_sleeve_base", "cost_bps": "native", **performance_metrics(base)},
        ]
    )
    trend_paths: dict[int, pd.DataFrame] = {}
    trend_weight = float(config["portfolio"]["trend_weight"])
    for cost in config["cost_bps_one_way"]:
        path = apply_next_week_returns(prices, primary_weights, float(cost))
        trend_paths[int(cost)] = path
        standalone = path.net_return.rename(f"trend_{cost}bps")
        candidate = blend_returns(base, standalone, trend_weight).rename(f"candidate_{cost}bps")
        paths[standalone.name] = standalone
        paths[candidate.name] = candidate
        score_rows.append({"portfolio": "trend_standalone", "cost_bps": int(cost), **performance_metrics(standalone)})
        score_rows.append({"portfolio": "candidate_80_20", "cost_bps": int(cost), **performance_metrics(candidate)})
    scorecard = pd.DataFrame(score_rows)

    primary_cost = 50
    trend_primary = trend_paths[primary_cost].net_return
    candidate_primary = paths[f"candidate_{primary_cost}bps"]
    base_metrics = performance_metrics(base)
    base_candidate_window = base.reindex(candidate_primary.index).dropna()
    base_candidate_metrics = performance_metrics(base_candidate_window)
    candidate_metrics = performance_metrics(candidate_primary)
    scorecard = pd.concat(
        [scorecard, pd.DataFrame([{"portfolio": "five_sleeve_base_candidate_window", "cost_bps": "native", **base_candidate_metrics}])],
        ignore_index=True,
    )

    correlations = pd.concat([saved, trend_primary.rename("cross_asset_trend")], axis=1, sort=True).corr()["cross_asset_trend"].drop("cross_asset_trend")
    correlation_table = correlations.rename("correlation_to_cross_asset_trend").rename_axis("strategy").reset_index()

    regime_rows = []
    regimes = {
        "calendar_2008": ("2008-01-01", "2008-12-31"),
        "global_financial_crisis_2008_2009": ("2008-01-01", "2009-12-31"),
        "covid_2020": ("2020-01-01", "2020-12-31"),
        "rates_inflation_2022": ("2022-01-01", "2022-12-31"),
        "saved_strategy_common_window": (str(base.index[0].date()), str(base.index[-1].date())),
    }
    for name, (start, end) in regimes.items():
        subset = trend_primary.loc[start:end]
        if len(subset):
            regime_rows.append({"regime": name, **performance_metrics(subset)})
    regimes_frame = pd.DataFrame(regime_rows)

    prefix_cutoff = pd.Timestamp(config["robustness"]["prefix_invariance_cutoff"])
    truncated_prices = prices.loc[:prefix_cutoff]
    truncated_weights = build_trend_weights(
        truncated_prices,
        assets,
        cash_asset,
        trend_config["signal_lookbacks_weeks"],
        int(trend_config["volatility_lookback_weeks"]),
        int(trend_config["minimum_volatility_observations"]),
        float(trend_config["maximum_asset_weight"]),
        int(trend_config["rebalance_every_weeks"]),
    )
    prefix_difference = float((primary_weights.loc[:prefix_cutoff] - truncated_weights).abs().max().max())

    leave_one_rows = []
    for omitted in assets:
        remaining = [asset for asset in assets if asset != omitted]
        weights = build_trend_weights(
            prices,
            remaining,
            cash_asset,
            trend_config["signal_lookbacks_weeks"],
            int(trend_config["volatility_lookback_weeks"]),
            int(trend_config["minimum_volatility_observations"]),
            float(trend_config["maximum_asset_weight"]),
            int(trend_config["rebalance_every_weeks"]),
        )
        path = apply_next_week_returns(prices, weights, primary_cost).net_return
        blend = blend_returns(base, path, trend_weight)
        leave_one_rows.append({"omitted_asset": omitted, **performance_metrics(blend)})
    leave_one = pd.DataFrame(leave_one_rows)

    neighborhood_rows = []
    for lookbacks in config["robustness"]["lookback_neighborhoods"]:
        weights = build_trend_weights(
            prices,
            assets,
            cash_asset,
            lookbacks,
            int(trend_config["volatility_lookback_weeks"]),
            int(trend_config["minimum_volatility_observations"]),
            float(trend_config["maximum_asset_weight"]),
            int(trend_config["rebalance_every_weeks"]),
        )
        path = apply_next_week_returns(prices, weights, primary_cost).net_return
        for weight in config["robustness"]["trend_weight_neighborhood"]:
            blended = blend_returns(base, path, float(weight))
            neighborhood_rows.append(
                {"lookbacks": "/".join(map(str, lookbacks)), "trend_weight": float(weight), **performance_metrics(blended)}
            )
    neighborhoods = pd.DataFrame(neighborhood_rows)

    placebo_rows = []
    for trial in range(int(config["robustness"]["random_placebo_trials"])):
        weights = random_placebo_weights(
            prices,
            primary_weights,
            assets,
            cash_asset,
            float(trend_config["maximum_asset_weight"]),
            int(config["robustness"]["random_seed"]) + trial,
            base.index,
        )
        random_path = apply_next_week_returns(prices, weights, primary_cost).net_return
        metrics = performance_metrics(blend_returns(base, random_path, trend_weight))
        placebo_rows.append({"trial": trial, **metrics})
    placebos = pd.DataFrame(placebo_rows)
    placebo_joint_p = float(
        ((placebos.sharpe_zero_rf >= candidate_metrics["sharpe_zero_rf"]) & (placebos.calmar >= candidate_metrics["calmar"])).mean()
    )

    paired = candidate_primary - base_candidate_window
    raw_pvalue = block_bootstrap_pvalue(paired)
    return_floor = float(base_candidate_metrics["cagr"]) - 0.05
    gates = {
        "improves_sharpe": candidate_metrics["sharpe_zero_rf"] > base_candidate_metrics["sharpe_zero_rf"],
        "improves_calmar": candidate_metrics["calmar"] > base_candidate_metrics["calmar"],
        "cagr_within_five_points": candidate_metrics["cagr"] >= return_floor,
        "prefix_invariance": prefix_difference <= 1e-12,
        "all_leave_one_out_cagr_positive": bool((leave_one.cagr > 0.0).all()),
        "all_neighborhood_cagr_positive": bool((neighborhoods.cagr > 0.0).all()),
    }
    retained = all(gates.values())

    contribution = contribution_table(saved)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.concat(paths, axis=1, sort=True).to_csv(OUTPUT / "weekly_paths.csv")
    primary_weights.to_csv(OUTPUT / "trend_weights.csv")
    scorecard.to_csv(OUTPUT / "scorecard.csv", index=False)
    contribution.to_csv(OUTPUT / "saved_strategy_contributions.csv", index=False)
    correlation_table.to_csv(OUTPUT / "correlations.csv", index=False)
    regimes_frame.to_csv(OUTPUT / "trend_regimes.csv", index=False)
    leave_one.to_csv(OUTPUT / "leave_one_market_out.csv", index=False)
    neighborhoods.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    placebos.to_csv(OUTPUT / "random_placebos.csv", index=False)

    result = {
        "experiment": config["experiment"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha256(CONFIG),
        "saved_strategy_source_sha256": sha256(source),
        "price_source_sha256": sha256(price_path),
        "primary_cost_bps_one_way": primary_cost,
        "all_six": performance_metrics(all_six),
        "five_sleeve_base": base_metrics,
        "five_sleeve_base_candidate_window": base_candidate_metrics,
        "candidate_80_20": candidate_metrics,
        "trend_standalone_full": performance_metrics(trend_primary),
        "maximum_component_correlation": float(correlations.abs().max()),
        "median_component_correlation": float(correlations.median()),
        "prefix_maximum_weight_difference": prefix_difference,
        "paired_block_bootstrap_raw_pvalue_vs_base": raw_pvalue,
        "program_wide_adjusted_pvalue": None,
        "program_wide_adjustment_note": "No verified global attempt counter exists in the repository, so no project-wide significance claim is made.",
        "random_placebo_joint_sharpe_calmar_pvalue": placebo_joint_p,
        "primary_gates": gates,
        "decision": "retain_as_retrospective_challenger" if retained else "reject_as_portfolio_improvement",
        "strategy_promotion_authorized": False,
        "forward_clock_started": False,
        "live_trading_enabled": False,
        "cost_caveat": "Saved sleeve returns are already net under heterogeneous native assumptions; exact holdings-level cross-sleeve netting and market impact are unavailable. Trend turnover costs are explicit.",
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")

    growth_row = contribution.loc[contribution.strategy == excluded].iloc[0]
    report = f"""# Cross-asset crisis trend v1

One fixed candidate was registered before measurement: 80% equal weight across the five saved strategies other than `{excluded}`, plus 20% causal long-only trend across bonds, credit, metals, commodities and the dollar.

## Result

- All six saved strategies: {100*result['all_six']['cagr']:.2f}% CAGR, {result['all_six']['sharpe_zero_rf']:.2f} Sharpe, {100*result['all_six']['max_drawdown']:.2f}% maximum drawdown, {100*result['all_six']['worst_rolling_52w']:.2f}% worst rolling year.
- Five-sleeve base: {100*result['five_sleeve_base']['cagr']:.2f}% CAGR, {result['five_sleeve_base']['sharpe_zero_rf']:.2f} Sharpe, {100*result['five_sleeve_base']['max_drawdown']:.2f}% maximum drawdown, {100*result['five_sleeve_base']['worst_rolling_52w']:.2f}% worst rolling year.
- Five-sleeve base on the candidate's identical 180-week window: {100*result['five_sleeve_base_candidate_window']['cagr']:.2f}% CAGR, {result['five_sleeve_base_candidate_window']['sharpe_zero_rf']:.2f} Sharpe, {100*result['five_sleeve_base_candidate_window']['max_drawdown']:.2f}% maximum drawdown, {100*result['five_sleeve_base_candidate_window']['worst_rolling_52w']:.2f}% worst rolling year.
- Fixed 80/20 candidate at 50 bps trend costs: {100*result['candidate_80_20']['cagr']:.2f}% CAGR, {result['candidate_80_20']['sharpe_zero_rf']:.2f} Sharpe, {100*result['candidate_80_20']['max_drawdown']:.2f}% maximum drawdown, {100*result['candidate_80_20']['worst_rolling_52w']:.2f}% worst rolling year.

The excluded growth/Micron sleeve contributed {100*growth_row.return_contribution_share:.1f}% of equal-weight arithmetic return and {100*growth_row.variance_risk_contribution_share:.1f}% of variance risk on the common window. That confirms the direction of the removal decision, but not the different figures in the external summary.

Decision: **{result['decision']}**. This is retrospective research on strategies already selected from the same 2023-2026 window. It cannot alter the September 4 registry, start a forward clock, authorize promotion, or support live trading. The project-wide attempt count is not reproducible, so the raw block-bootstrap result is not presented as multiplicity-adjusted evidence.
"""
    (OUTPUT / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
