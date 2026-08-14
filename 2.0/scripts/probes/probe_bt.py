"""Platform-owned behavioral probe executed against pinned bt source."""

from __future__ import annotations

import json

import bt
import pandas as pd


def simple_backtest(commissions=None):
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    prices = pd.DataFrame({"SPY": [100.0, 100.0, 100.0]}, index=dates)
    strategy = bt.Strategy(
        "buy_once",
        [bt.algos.RunOnce(), bt.algos.SelectAll(), bt.algos.WeighEqually(), bt.algos.Rebalance()],
    )
    backtest = bt.Backtest(
        strategy,
        prices,
        initial_capital=1_000.0,
        commissions=commissions,
        integer_positions=False,
        progress_bar=False,
    )
    result = bt.run(backtest, progress_bar=False)
    return backtest, result


no_cost_backtest, _ = simple_backtest()
cost_backtest, cost_result = simple_backtest(lambda quantity, price: 1.0)
transactions = cost_result.get_transactions()
commission_applied = cost_backtest.strategy.value < no_cost_backtest.strategy.value
cash_nonnegative = cost_backtest.strategy.capital >= -1e-9
position = cost_backtest.strategy["SPY"].position

dates = pd.to_datetime(["2024-02-01", "2024-02-02", "2024-02-03"])
prices = pd.DataFrame({"SPY": [100.0, 110.0, 90.0]}, index=dates)
signal = pd.DataFrame({"SPY": [False, True, False]}, index=dates)
lookahead_strategy = bt.Strategy(
    "current_close_signal",
    [
        bt.algos.RunDaily(),
        bt.algos.SelectWhere(signal),
        bt.algos.WeighEqually(),
        bt.algos.Rebalance(),
    ],
)
lookahead_backtest = bt.Backtest(
    lookahead_strategy,
    prices,
    initial_capital=1_000.0,
    integer_positions=False,
    progress_bar=False,
)
lookahead_result = bt.run(lookahead_backtest, progress_bar=False)
lookahead_transactions = lookahead_result.get_transactions().reset_index()
first_trade_time = None
first_trade_price = None
if not lookahead_transactions.empty:
    first_trade_time = str(lookahead_transactions.iloc[0]["Date"])
    first_trade_price = float(lookahead_transactions.iloc[0]["price"])
same_bar_execution = first_trade_time is not None and first_trade_time.startswith("2024-02-02")

checks = [
    {"name": "commission_hook_reduces_value", "expected": True, "actual": commission_applied, "passed": commission_applied, "critical": True},
    {"name": "rebalance_preserves_nonnegative_cash", "expected": True, "actual": cash_nonnegative, "passed": cash_nonnegative, "critical": True},
    {"name": "portfolio_position_is_recorded", "expected": True, "actual": position > 0, "passed": position > 0, "critical": True},
    {
        "name": "current_close_signal_cannot_execute_same_bar",
        "expected": False,
        "actual": same_bar_execution,
        "passed": not same_bar_execution,
        "critical": True,
        "observed_trade_time": first_trade_time,
        "observed_trade_price": first_trade_price,
    },
]
critical_pass = all(item["passed"] for item in checks if item["critical"])
result = {
    "adapter": "bt",
    "checks": checks,
    "critical_pass": critical_pass,
    "observations": {
        "transaction_count": int(len(transactions)),
        "final_value_with_cost": float(cost_backtest.strategy.value),
        "final_value_without_cost": float(no_cost_backtest.strategy.value),
        "final_cash_with_cost": float(cost_backtest.strategy.capital),
        "final_position": float(position),
    },
    "capabilities": {
        "portfolio_rebalancing": True,
        "commission_hook": True,
        "cash_and_position_accounting": True,
        "automatic_next_bar_execution": False,
        "partial_fills": False,
        "order_rejection_lifecycle": False,
    },
    "decision": "conditional_research_adapter_requires_shifted_signals_and_platform_execution",
}
print(json.dumps(result, sort_keys=True))
