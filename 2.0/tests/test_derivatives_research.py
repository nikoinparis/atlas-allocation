import unittest

from src.systematic_trader.derivatives_research import (
    FuturesContractObservation,
    OptionQuoteObservation,
    futures_roll_return,
    short_option_tail_budget_gate,
    short_put_expiry_pnl,
)


class DerivativesResearchTests(unittest.TestCase):
    def test_futures_contract_requires_margin_and_spread_mechanics(self):
        observation = FuturesContractObservation(
            "2026-01-02T21:00:00Z", "CL", "CLG26", "2026-02-20", 70.0, 69.9, 70.1,
            1000.0, 8000.0, 7000.0, 2.5, 1.5,
        )
        observation.validate()
        with self.assertRaises(ValueError):
            FuturesContractObservation(
                "2026-01-02T21:00:00Z", "CL", "CLG26", "2026-02-20", 70.0, 70.2, 70.1,
                1000.0, 8000.0, 9000.0, 2.5, 1.5,
            ).validate()

    def test_roll_books_both_contract_legs_and_fees(self):
        result = futures_roll_return(
            prior_contract_price=70.0, prior_exit_price=72.0, next_entry_price=73.0,
            next_contract_price=74.0, multiplier=1000.0, contracts=1, total_fees=10.0,
            capital=100_000.0,
        )
        self.assertAlmostEqual(0.0299, result)

    def test_option_quote_requires_surface_risk_margin_and_exercise_fields(self):
        quote = OptionQuoteObservation(
            "2026-01-02T21:00:00Z", "SPX", "2026-01-30", 6000.0, "put", 20.0, 21.0,
            100, 0.22, -0.25, 0.001, 12.0, 25_000.0, 5.0, "european",
        )
        quote.validate()

    def test_short_put_tail_and_margin_gates_fail_closed(self):
        self.assertEqual(-98_000.0, short_put_expiry_pnl(
            premium=20.0, strike=1000.0, terminal_underlying=0.0
        ))
        result = short_option_tail_budget_gate(
            [-1000.0, -30_000.0], capital=100_000.0, maximum_weekly_loss_fraction=0.1,
            broker_margin_required=25_000.0, available_cash=20_000.0,
        )
        self.assertFalse(result["tail_loss_gate_pass"])
        self.assertFalse(result["margin_gate_pass"])
        self.assertFalse(result["combined_gate_pass"])
        self.assertFalse(result["live_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
