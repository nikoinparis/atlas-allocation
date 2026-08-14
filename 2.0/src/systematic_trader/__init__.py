"""Portfolio Optimizer 2.0 research and simulation platform."""

__version__ = "2.0.0-dev"
"""Portfolio Optimizer 2.0 platform-owned systematic trading contracts."""

from .execution import (
    DuplicateFillError,
    ExecutionError,
    Fill,
    MarketBar,
    Order,
    OrderStatus,
    ReferenceExecutionEngine,
    Side,
    next_bar_fill,
    quote_is_valid,
)

__all__ = [
    "DuplicateFillError",
    "ExecutionError",
    "Fill",
    "MarketBar",
    "Order",
    "OrderStatus",
    "ReferenceExecutionEngine",
    "Side",
    "next_bar_fill",
    "quote_is_valid",
]
