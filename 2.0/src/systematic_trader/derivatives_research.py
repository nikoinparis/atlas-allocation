"""Fail-closed data and risk contracts for futures and short-option research."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Sequence


@dataclass(frozen=True)
class FuturesContractObservation:
    timestamp_utc: str
    root: str
    contract: str
    expiration_date: str
    settlement_price: float
    bid: float
    ask: float
    multiplier: float
    initial_margin: float
    maintenance_margin: float
    commission_per_contract: float
    exchange_fee_per_contract: float

    def validate(self) -> None:
        timestamp = datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
        expiration = date.fromisoformat(self.expiration_date)
        if not self.root or not self.contract or expiration < timestamp.date():
            raise ValueError("valid root, contract, and non-expired observation required")
        numeric = (
            self.settlement_price, self.bid, self.ask, self.multiplier, self.initial_margin,
            self.maintenance_margin, self.commission_per_contract, self.exchange_fee_per_contract,
        )
        if any(not math.isfinite(value) or value < 0.0 for value in numeric):
            raise ValueError("finite nonnegative futures fields required")
        if min(self.settlement_price, self.bid, self.ask, self.multiplier, self.initial_margin, self.maintenance_margin) <= 0.0:
            raise ValueError("positive price, multiplier, and margin fields required")
        if self.bid > self.ask or self.maintenance_margin > self.initial_margin:
            raise ValueError("valid spread and margin ordering required")


def futures_roll_return(
    *, prior_contract_price: float, prior_exit_price: float,
    next_entry_price: float, next_contract_price: float,
    multiplier: float, contracts: int, total_fees: float,
    capital: float,
) -> float:
    """Explicitly book old-contract exit and new-contract holding P&L across a roll."""
    if min(prior_contract_price, prior_exit_price, next_entry_price, next_contract_price, multiplier, capital) <= 0.0:
        raise ValueError("positive prices, multiplier, and capital required")
    if contracts == 0 or total_fees < 0.0:
        raise ValueError("nonzero contracts and nonnegative fees required")
    direction = 1 if contracts > 0 else -1
    quantity = abs(contracts)
    pnl = direction * quantity * multiplier * (
        (prior_exit_price - prior_contract_price) + (next_contract_price - next_entry_price)
    ) - total_fees
    return pnl / capital


@dataclass(frozen=True)
class OptionQuoteObservation:
    timestamp_utc: str
    underlying: str
    expiration_date: str
    strike: float
    option_type: str
    bid: float
    ask: float
    multiplier: int
    implied_volatility: float
    delta: float
    gamma: float
    vega: float
    initial_margin: float
    assignment_fee: float
    exercise_style: str

    def validate(self) -> None:
        timestamp = datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
        expiration = date.fromisoformat(self.expiration_date)
        if expiration < timestamp.date() or self.option_type not in {"call", "put"}:
            raise ValueError("unexpired call or put required")
        if self.exercise_style not in {"american", "european"}:
            raise ValueError("explicit exercise style required")
        if not self.underlying or self.multiplier <= 0:
            raise ValueError("underlying and positive contract multiplier required")
        numeric = (
            self.strike, self.bid, self.ask, self.implied_volatility, self.gamma,
            self.vega, self.initial_margin, self.assignment_fee,
        )
        if any(not math.isfinite(value) or value < 0.0 for value in numeric):
            raise ValueError("finite nonnegative option quote and risk fields required")
        if self.strike <= 0.0 or self.ask <= 0.0 or self.bid > self.ask or self.initial_margin <= 0.0:
            raise ValueError("positive strike/ask/margin and valid spread required")
        if not -1.0 <= self.delta <= 1.0:
            raise ValueError("delta must be in [-1, 1]")


def short_put_expiry_pnl(
    *, premium: float, strike: float, terminal_underlying: float,
    multiplier: int = 100, contracts: int = 1,
    trading_and_assignment_fees: float = 0.0,
) -> float:
    if min(premium, strike, terminal_underlying, trading_and_assignment_fees) < 0.0:
        raise ValueError("nonnegative payoff inputs required")
    if multiplier <= 0 or contracts <= 0:
        raise ValueError("positive multiplier and contract count required")
    return contracts * multiplier * (premium - max(strike - terminal_underlying, 0.0)) - trading_and_assignment_fees


def short_option_tail_budget_gate(
    scenario_losses: Sequence[float], *, capital: float, maximum_weekly_loss_fraction: float,
    broker_margin_required: float, available_cash: float,
) -> dict[str, float | bool]:
    """Reject sizing that breaches either explicit tail loss or broker margin."""
    losses = [float(value) for value in scenario_losses]
    if not losses or capital <= 0.0 or not 0.0 < maximum_weekly_loss_fraction < 1.0:
        raise ValueError("tail scenarios, positive capital, and a fractional loss budget required")
    if broker_margin_required < 0.0 or available_cash < 0.0:
        raise ValueError("nonnegative margin and cash required")
    worst = min(losses)
    budget = capital * maximum_weekly_loss_fraction
    return {
        "worst_scenario_pnl": worst,
        "maximum_permitted_loss": budget,
        "tail_loss_gate_pass": abs(min(worst, 0.0)) <= budget,
        "margin_gate_pass": broker_margin_required <= available_cash,
        "combined_gate_pass": abs(min(worst, 0.0)) <= budget and broker_margin_required <= available_cash,
        "live_trading_enabled": False,
    }
