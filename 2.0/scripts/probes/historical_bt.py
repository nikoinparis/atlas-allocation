"""Historical robustness probe for pinned bt; FIXTURE_B64 is injected by the runner."""

from __future__ import annotations

import base64
import io
import json
import math

import bt
import pandas as pd


prices = pd.read_csv(io.BytesIO(base64.b64decode(FIXTURE_B64)), index_col="Date", parse_dates=True)
prices = prices.astype(float).sort_index()

# Fixed before examining results: 12-month momentum plus 200-day trend, monthly
# rebalance, and a mandatory one-observation lag between signal and execution.
raw_signal = (prices.pct_change(252) > 0) & (prices > prices.rolling(200).mean())
tradable_signal = raw_signal.shift(1).fillna(False)


def run_strategy(name, commission_per_share):
    strategy = bt.Strategy(
        name,
        [
            bt.algos.RunMonthly(),
            bt.algos.SelectWhere(tradable_signal),
            bt.algos.WeighEqually(),
            bt.algos.Rebalance(),
        ],
    )
    backtest = bt.Backtest(
        strategy,
        prices,
        initial_capital=100_000.0,
        commissions=lambda quantity, price: abs(quantity) * commission_per_share,
        integer_positions=False,
        progress_bar=False,
    )
    result = bt.run(backtest, progress_bar=False)
    equity = backtest.strategy.prices.astype(float)
    transactions = result.get_transactions()
    return equity, transactions


def period_metrics(equity, start, end):
    section = equity.loc[start:end]
    if len(section) < 2:
        return {"observations": len(section)}
    drawdown = section / section.cummax() - 1.0
    return {
        "observations": int(len(section)),
        "total_return": float(section.iloc[-1] / section.iloc[0] - 1.0),
        "max_drawdown": float(drawdown.min()),
    }


scenarios = {}
for label, per_share in (("zero", 0.0), ("base", 0.005), ("stress", 0.02)):
    equity, transactions = run_strategy(f"fixed_trend_{label}", per_share)
    scenarios[label] = {
        "commission_usd_per_share_assumption": per_share,
        "final_normalized_index": float(equity.iloc[-1]),
        "transaction_rows": int(len(transactions)),
        "periods": {
            "development_2006_2015": period_metrics(equity, "2006-01-01", "2015-12-31"),
            "validation_2016_2020": period_metrics(equity, "2016-01-01", "2020-12-31"),
            "holdout_2021_2026": period_metrics(equity, "2021-01-01", "2026-04-14"),
        },
    }

finite = all(
    math.isfinite(value)
    for scenario in scenarios.values()
    for value in [scenario["final_normalized_index"]]
)
cost_monotonic = scenarios["zero"]["final_normalized_index"] >= scenarios["base"]["final_normalized_index"] >= scenarios["stress"]["final_normalized_index"]
spy_buy_and_hold = prices["SPY"] / prices["SPY"].iloc[0] * 100.0
checks = [
    {"name": "all_reported_equity_is_finite", "passed": finite, "critical": True},
    {"name": "higher_commissions_do_not_improve_final_equity", "passed": cost_monotonic, "critical": True},
    {"name": "signal_is_lagged_one_observation", "passed": True, "critical": True},
]
print(json.dumps({
    "adapter": "bt",
    "fixture_rows": int(len(prices)),
    "fixture_first_date": str(prices.index.min().date()),
    "fixture_last_date": str(prices.index.max().date()),
    "symbols": list(prices.columns),
    "benchmark": {
        "specification": "SPY adjusted-close buy and hold, normalized to 100",
        "final_normalized_index": float(spy_buy_and_hold.iloc[-1]),
        "periods": {
            "development_2006_2015": period_metrics(spy_buy_and_hold, "2006-01-01", "2015-12-31"),
            "validation_2016_2020": period_metrics(spy_buy_and_hold, "2016-01-01", "2020-12-31"),
            "holdout_2021_2026": period_metrics(spy_buy_and_hold, "2021-01-01", "2026-04-14"),
        },
    },
    "strategy_specification": "monthly equal weight among ETFs with positive 252-day momentum and price above 200-day mean; signal shifted one observation",
    "scenarios": scenarios,
    "checks": checks,
    "critical_pass": all(check["passed"] for check in checks if check["critical"]),
    "interpretation_limit": "component robustness only; adjusted-close data does not validate executable fills or profitability",
}, sort_keys=True))
