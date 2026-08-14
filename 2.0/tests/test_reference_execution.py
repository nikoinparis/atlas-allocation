import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from systematic_trader.execution import (  # noqa: E402
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


class ReferenceExecutionTests(unittest.TestCase):
    def setUp(self):
        self.t0 = datetime(2024, 1, 2, 21, 0, tzinfo=timezone.utc)

    def test_cash_position_fees_and_equity_reconcile(self):
        engine = ReferenceExecutionEngine(10_000)
        order = Order("o1", "SPY", Side.BUY, 10, self.t0)
        self.assertEqual(engine.submit(order, reference_price=100, estimated_fee=1).status, OrderStatus.ACCEPTED)
        engine.apply_fill(Fill("f1", "o1", "SPY", Side.BUY, 10, 101, self.t0 + timedelta(minutes=1), 1))
        self.assertEqual(engine.cash, 8_989)
        self.assertEqual(engine.positions["SPY"], 10)
        self.assertEqual(engine.equity({"SPY": 102}), 10_009)
        self.assertTrue(engine.reconciles({"SPY": 102}))

    def test_insufficient_cash_is_rejected_before_fill(self):
        engine = ReferenceExecutionEngine(100)
        state = engine.submit(Order("o1", "SPY", Side.BUY, 2, self.t0), reference_price=60, estimated_fee=1)
        self.assertEqual(state.status, OrderStatus.REJECTED)
        self.assertEqual(state.rejection_reason, "insufficient_buying_power")
        self.assertEqual(engine.cash, 100)

    def test_partial_fills_preserve_remaining_quantity(self):
        engine = ReferenceExecutionEngine(10_000)
        order = Order("o1", "SPY", Side.BUY, 10, self.t0)
        engine.submit(order, reference_price=100)
        state = engine.apply_fill(Fill("f1", "o1", "SPY", Side.BUY, 4, 100, self.t0 + timedelta(minutes=1), 0.4))
        self.assertEqual(state.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(state.remaining_quantity, 6)
        state = engine.apply_fill(Fill("f2", "o1", "SPY", Side.BUY, 6, 101, self.t0 + timedelta(minutes=2), 0.6))
        self.assertEqual(state.status, OrderStatus.FILLED)
        self.assertEqual(engine.positions["SPY"], 10)
        self.assertEqual(engine.total_fees, 1)

    def test_duplicate_fill_cannot_change_the_ledger_twice(self):
        engine = ReferenceExecutionEngine(10_000)
        engine.submit(Order("o1", "SPY", Side.BUY, 1, self.t0), reference_price=100)
        fill = Fill("f1", "o1", "SPY", Side.BUY, 1, 100, self.t0 + timedelta(minutes=1))
        engine.apply_fill(fill)
        before = (engine.cash, dict(engine.positions))
        with self.assertRaises(DuplicateFillError):
            engine.apply_fill(fill)
        self.assertEqual(before, (engine.cash, engine.positions))

    def test_overfill_is_rejected_without_mutation(self):
        engine = ReferenceExecutionEngine(10_000)
        engine.submit(Order("o1", "SPY", Side.BUY, 1, self.t0), reference_price=100)
        with self.assertRaises(ExecutionError):
            engine.apply_fill(Fill("f1", "o1", "SPY", Side.BUY, 2, 100, self.t0 + timedelta(minutes=1)))
        self.assertEqual(engine.cash, 10_000)
        self.assertEqual(engine.positions, {})

    def test_signal_at_close_fills_only_at_next_bar_open(self):
        order = Order("o1", "SPY", Side.BUY, 1, self.t0)
        bars = [
            MarketBar(self.t0, 99, 102, 98, 101, 1000),
            MarketBar(self.t0 + timedelta(days=1), 103, 105, 102, 104, 1000),
        ]
        fill = next_bar_fill(order, bars, slippage_bps=10, fee=0.5)
        self.assertEqual(fill.timestamp, bars[1].timestamp)
        self.assertAlmostEqual(fill.price, 103.103)

    def test_missing_future_bar_does_not_same_bar_fill(self):
        order = Order("o1", "SPY", Side.BUY, 1, self.t0)
        with self.assertRaises(ExecutionError):
            next_bar_fill(order, [MarketBar(self.t0, 99, 102, 98, 101, 1000)])

    def test_nonfinite_and_crossed_quotes_are_rejected(self):
        self.assertFalse(quote_is_valid(math.nan, 1.0))
        self.assertFalse(quote_is_valid(1.1, 1.0))
        self.assertFalse(quote_is_valid(0.0, 1.0))
        self.assertTrue(quote_is_valid(0.95, 1.0))


if __name__ == "__main__":
    unittest.main()
