"""Platform-owned execution and accounting reference behavior.

Third-party engines are measured against these contracts. They never become
the authority for cash, positions, order state, or risk decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Iterable


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"


class ExecutionError(ValueError):
    """Base class for reference execution contract violations."""


class DuplicateFillError(ExecutionError):
    pass


@dataclass(frozen=True)
class MarketBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        prices = (self.open, self.high, self.low, self.close)
        if not all(isfinite(value) and value > 0 for value in prices):
            raise ValueError("bar prices must be finite and positive")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("bar high is inconsistent")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("bar low is inconsistent")
        if not isfinite(self.volume) or self.volume < 0:
            raise ValueError("bar volume must be finite and non-negative")


@dataclass(frozen=True)
class Order:
    order_id: str
    symbol: str
    side: Side
    quantity: float
    submitted_at: datetime

    def __post_init__(self) -> None:
        if not self.order_id or not self.symbol:
            raise ValueError("order_id and symbol are required")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("order quantity must be finite and positive")


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    timestamp: datetime
    fee: float = 0.0

    def __post_init__(self) -> None:
        if not self.fill_id or not self.order_id or not self.symbol:
            raise ValueError("fill identifiers and symbol are required")
        if not isfinite(self.quantity) or self.quantity <= 0:
            raise ValueError("fill quantity must be finite and positive")
        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("fill price must be finite and positive")
        if not isfinite(self.fee) or self.fee < 0:
            raise ValueError("fill fee must be finite and non-negative")


@dataclass
class OrderState:
    order: Order
    status: OrderStatus
    remaining_quantity: float
    rejection_reason: str = ""
    fills: list[Fill] = field(default_factory=list)


class ReferenceExecutionEngine:
    """Small deterministic oracle for ledger and order-state invariants."""

    def __init__(self, initial_cash: float, *, allow_short: bool = False) -> None:
        if not isfinite(initial_cash) or initial_cash < 0:
            raise ValueError("initial_cash must be finite and non-negative")
        self.initial_cash = float(initial_cash)
        self.cash = float(initial_cash)
        self.allow_short = allow_short
        self.positions: dict[str, float] = {}
        self.orders: dict[str, OrderState] = {}
        self.applied_fill_ids: set[str] = set()
        self.total_fees = 0.0
        self.audit_log: list[dict[str, object]] = []

    def submit(self, order: Order, *, reference_price: float, estimated_fee: float = 0.0) -> OrderState:
        if order.order_id in self.orders:
            raise ExecutionError(f"duplicate order id: {order.order_id}")
        reason = ""
        if not isfinite(reference_price) or reference_price <= 0:
            reason = "invalid_reference_price"
        elif not isfinite(estimated_fee) or estimated_fee < 0:
            reason = "invalid_estimated_fee"
        elif order.side is Side.BUY and order.quantity * reference_price + estimated_fee > self.cash + 1e-12:
            reason = "insufficient_buying_power"
        elif order.side is Side.SELL and not self.allow_short:
            if order.quantity > self.positions.get(order.symbol, 0.0) + 1e-12:
                reason = "insufficient_position"
        status = OrderStatus.REJECTED if reason else OrderStatus.ACCEPTED
        state = OrderState(order, status, order.quantity, reason)
        self.orders[order.order_id] = state
        self.audit_log.append({"event": "order_submitted", "order_id": order.order_id, "status": status.value, "reason": reason})
        return state

    def apply_fill(self, fill: Fill) -> OrderState:
        if fill.fill_id in self.applied_fill_ids:
            raise DuplicateFillError(f"duplicate fill id: {fill.fill_id}")
        if fill.order_id not in self.orders:
            raise ExecutionError(f"unknown order id: {fill.order_id}")
        state = self.orders[fill.order_id]
        order = state.order
        if state.status is OrderStatus.REJECTED:
            raise ExecutionError("cannot fill a rejected order")
        if state.status is OrderStatus.FILLED:
            raise ExecutionError("cannot overfill a completed order")
        if fill.symbol != order.symbol or fill.side is not order.side:
            raise ExecutionError("fill does not match its order")
        if fill.timestamp < order.submitted_at:
            raise ExecutionError("fill timestamp precedes submission")
        if fill.quantity > state.remaining_quantity + 1e-12:
            raise ExecutionError("fill exceeds remaining order quantity")

        signed_quantity = fill.quantity if fill.side is Side.BUY else -fill.quantity
        cash_change = -signed_quantity * fill.price - fill.fee
        new_cash = self.cash + cash_change
        new_position = self.positions.get(fill.symbol, 0.0) + signed_quantity
        if new_cash < -1e-9:
            raise ExecutionError("fill would create negative cash")
        if not self.allow_short and new_position < -1e-12:
            raise ExecutionError("fill would create a short position")

        self.cash = new_cash
        self.positions[fill.symbol] = new_position
        self.total_fees += fill.fee
        self.applied_fill_ids.add(fill.fill_id)
        state.fills.append(fill)
        state.remaining_quantity = max(0.0, state.remaining_quantity - fill.quantity)
        state.status = OrderStatus.FILLED if state.remaining_quantity <= 1e-12 else OrderStatus.PARTIALLY_FILLED
        self.audit_log.append({"event": "fill_applied", "fill_id": fill.fill_id, "order_id": fill.order_id, "status": state.status.value})
        return state

    def equity(self, marks: dict[str, float]) -> float:
        value = self.cash
        for symbol, quantity in self.positions.items():
            mark = marks.get(symbol)
            if mark is None or not isfinite(mark) or mark <= 0:
                raise ExecutionError(f"missing or invalid mark for {symbol}")
            value += quantity * mark
        return value

    def reconciles(self, marks: dict[str, float]) -> bool:
        gross_trading_cash = 0.0
        for state in self.orders.values():
            for fill in state.fills:
                signed = fill.quantity if fill.side is Side.BUY else -fill.quantity
                gross_trading_cash -= signed * fill.price + fill.fee
        expected_cash = self.initial_cash + gross_trading_cash
        return abs(expected_cash - self.cash) <= 1e-9 and isfinite(self.equity(marks))


def next_bar_fill(
    order: Order,
    bars: Iterable[MarketBar],
    *,
    slippage_bps: float = 0.0,
    fee: float = 0.0,
    fill_id: str = "canonical-fill",
) -> Fill:
    """Fill strictly after the signal/order timestamp at the next bar open."""
    if not isfinite(slippage_bps) or slippage_bps < 0:
        raise ValueError("slippage_bps must be finite and non-negative")
    next_bar = next((bar for bar in sorted(bars, key=lambda item: item.timestamp) if bar.timestamp > order.submitted_at), None)
    if next_bar is None:
        raise ExecutionError("no future bar is available")
    direction = 1.0 if order.side is Side.BUY else -1.0
    price = next_bar.open * (1.0 + direction * slippage_bps / 10_000.0)
    return Fill(fill_id, order.order_id, order.symbol, order.side, order.quantity, price, next_bar.timestamp, fee)


def quote_is_valid(bid: float, ask: float, *, max_relative_spread: float = 0.50) -> bool:
    if not all(isfinite(value) and value > 0 for value in (bid, ask)):
        return False
    if ask < bid:
        return False
    mid = (bid + ask) / 2.0
    return (ask - bid) / mid <= max_relative_spread
