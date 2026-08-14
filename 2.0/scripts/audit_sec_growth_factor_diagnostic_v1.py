#!/usr/bin/env python3
"""Adversarial audit of the non-promotable SEC growth-factor pilot."""

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
from scripts.run_breadth_ceiling_adversarial_validation_batch_65 import ols_attribution
from scripts.run_exhaustive_return_first_discovery_batch_66 import metrics_for
from scripts.run_sec_fundamental_factor_diagnostic_v1 import build_weights, static_weights, weekly_prices
from systematic_trader.ggg_independent import next_week_returns, portfolio_path
from systematic_trader.return_first_search import delay_weights

CONFIG = ROOT / "config/sec_fundamental_factor_diagnostic_v1.json"
SCORES = ROOT / "evidence/sec_fundamental_factor_diagnostic_v1/factor_scores.csv"
OUTPUT = ROOT / "evidence/sec_fundamental_factor_diagnostic_v1/growth_adversarial"


def metric(weights: pd.DataFrame, forward: pd.DataFrame, training_end: pd.Timestamp, cost: float = 50.0) -> tuple[pd.DataFrame, dict]:
    path = portfolio_path(weights, forward.reindex(columns=weights.columns), cost)
    return path, metrics_for(path.loc[path.index >= pd.Timestamp("2012-01-06")], training_end)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    sec_vintage = ROOT / "data/sec_vintages" / config["sec_vintage"]
    price_vintage = ROOT / "data/sec_pilot_price_vintages" / config["price_vintage"]
    tickers = sorted(pd.read_csv(sec_vintage / "universe.csv").ticker.tolist())
    prices = weekly_prices(price_vintage / "prices.csv", tickers + ["SPY", "XLK", "XLE"])
    forward = next_week_returns(prices)
    scores = pd.read_csv(SCORES)
    growth = scores[scores.family == "growth"].copy()
    training_end = pd.Timestamp(config["training_end"])
    xlk_weights = static_weights(prices, {"XLK": 1.0})
    xlk_path, xlk_metric = metric(xlk_weights, forward, training_end)
    frozen_weights, _ = build_weights(scores, prices, "growth", 5, 10)
    frozen_path, frozen_metric = metric(frozen_weights, forward, training_end)

    neighborhood_rows = []
    for top_n in (3, 5, 8):
        weights, _ = build_weights(scores, prices, "growth", top_n, 10)
        _, result = metric(weights, forward, training_end)
        neighborhood_rows.append({"top_n": top_n, **result, "beats_xlk": result["holdout_cagr"] > xlk_metric["holdout_cagr"]})
    neighborhood = pd.DataFrame(neighborhood_rows)

    delay_rows = []
    for weeks in (1, 4, 13):
        delayed = delay_weights(frozen_weights, weeks, cash_asset="cash::USD")
        _, result = metric(delayed, forward, training_end)
        delay_rows.append({"additional_delay_weeks": weeks, **result, "beats_xlk": result["holdout_cagr"] > xlk_metric["holdout_cagr"]})
    delays = pd.DataFrame(delay_rows)

    leaveout_rows = []
    for ticker in tickers:
        reduced = scores[scores.ticker != ticker]
        weights, _ = build_weights(reduced, prices, "growth", 5, 10)
        _, result = metric(weights, forward, training_end)
        leaveout_rows.append({"excluded_ticker": ticker, **result, "beats_xlk": result["holdout_cagr"] > xlk_metric["holdout_cagr"]})
    leaveout = pd.DataFrame(leaveout_rows).sort_values("holdout_cagr")

    rng = np.random.default_rng(93001)
    placebo_rows = []
    for permutation in range(100):
        shuffled = growth.copy()
        shuffled["score"] = shuffled.groupby(["decision_time", "sector"])["score"].transform(lambda values: pd.Series(rng.permutation(values.to_numpy()), index=values.index))
        placebo_scores = scores[scores.family != "growth"].copy()
        placebo_scores = pd.concat([placebo_scores, shuffled], ignore_index=True)
        weights, _ = build_weights(placebo_scores, prices, "growth", 5, 10)
        _, result = metric(weights, forward, training_end)
        placebo_rows.append({"permutation": permutation, **result})
    placebos = pd.DataFrame(placebo_rows)
    percentile = float((placebos.holdout_cagr <= frozen_metric["holdout_cagr"]).mean())

    holdout = frozen_path.loc[frozen_path.index > training_end]
    years = [(batch60.metrics(group)["cagr"], int(year)) for year, group in holdout.groupby(holdout.index.year) if len(group) >= 40]
    strongest_year = max(years)[1]
    keep = holdout.index[holdout.index.year != strongest_year]
    ex_candidate = batch60.metrics(frozen_path.reindex(keep))["cagr"]
    ex_xlk = batch60.metrics(xlk_path.reindex(keep))["cagr"]

    difference = frozen_path.loc[frozen_path.index > training_end, "net_return"] - xlk_path.loc[xlk_path.index > training_end, "net_return"]
    raw_pvalue = batch60.paired_block_pvalue(difference.to_numpy(), samples=30000, block=13, seed=93002)
    adjusted_pvalue = min(1.0, raw_pvalue * 5)
    factors = {}
    for ticker in ("SPY", "XLK", "XLE"):
        weights = static_weights(prices, {ticker: 1.0})
        factors[ticker] = portfolio_path(weights, forward.reindex(columns=weights.columns), 50.0).net_return
    attribution = pd.DataFrame(ols_attribution(frozen_path.net_return, pd.DataFrame(factors)))
    alpha = float(attribution.loc[attribution.model == "multifactor", "annual_alpha"].iloc[0])

    gates = {
        "neighborhood": float(neighborhood.beats_xlk.mean()) >= 2 / 3,
        "delays": float(delays.beats_xlk.mean()) >= 2 / 3,
        "leave_one_out": float(leaveout.beats_xlk.mean()) >= 0.60,
        "placebo": percentile >= 0.95,
        "excluded_best_year": ex_candidate > ex_xlk,
        "multifactor_alpha": alpha >= 0.0,
        "adjusted_pvalue": adjusted_pvalue <= 0.10,
    }
    robust = all(gates.values())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    neighborhood.to_csv(OUTPUT / "top_n_neighborhood.csv", index=False)
    delays.to_csv(OUTPUT / "execution_delays.csv", index=False)
    leaveout.to_csv(OUTPUT / "leave_one_stock_out.csv", index=False)
    placebos.to_csv(OUTPUT / "score_placebos.csv", index=False)
    attribution.to_csv(OUTPUT / "factor_attribution.csv", index=False)
    result = {
        "candidate": "sec_growth_top5_pilot", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "holdout_50bps_cagr": frozen_metric["holdout_cagr"], "xlk_holdout_cagr": xlk_metric["holdout_cagr"],
        "top_n_share_beating_xlk": float(neighborhood.beats_xlk.mean()), "delay_share_beating_xlk": float(delays.beats_xlk.mean()),
        "leave_one_out_share_beating_xlk": float(leaveout.beats_xlk.mean()), "worst_leave_one_out_cagr": float(leaveout.holdout_cagr.min()),
        "placebo_percentile": percentile, "excluded_strongest_year": strongest_year,
        "ex_best_year_advantage_over_xlk": ex_candidate - ex_xlk, "multifactor_annual_alpha": alpha,
        "raw_pvalue_vs_xlk": raw_pvalue, "adjusted_pvalue_5_families": adjusted_pvalue,
        "gates": gates, "adversarial_pilot_pass": robust,
        "strategy_promotion_authorized": False,
        "decision": "prioritize_growth_for_survivorship_safe_rebuild" if robust else "retain_growth_as_unconfirmed_pilot_signal",
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    failed = [name for name, passed in gates.items() if not passed]
    (OUTPUT / "report.md").write_text(
        "# SEC growth-factor pilot adversarial audit\n\n"
        f"Frozen top-five growth CAGR was **{frozen_metric['holdout_cagr']:.2%}** versus XLK **{xlk_metric['holdout_cagr']:.2%}**. Adversarial pilot pass: **{robust}**. Failed gates: `{', '.join(failed) if failed else 'none'}`.\n\n"
        f"Top-N win share: **{neighborhood.beats_xlk.mean():.1%}**; delay win share: **{delays.beats_xlk.mean():.1%}**; leave-one-stock-out win share: **{leaveout.beats_xlk.mean():.1%}**; placebo percentile: **{percentile:.1%}**; ex-best-year advantage: **{ex_candidate-ex_xlk:.2%}**; multifactor alpha: **{alpha:.2%}**; five-family adjusted p-value: **{adjusted_pvalue:.3f}**.\n\n"
        "This remains a non-promotable diagnostic because the current-membership stock universe is survivorship-biased and lacks delisted constituents.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
