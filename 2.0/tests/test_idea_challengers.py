import unittest

from src.systematic_trader.idea_challengers import (
    DailyBar,
    MinuteBar,
    RankedAssetSignal,
    constrained_fractional_kelly,
    opening_candle_ema_atr_trade,
    option_stock_disagreement,
    overnight_decomposition,
    public_disclosure_is_tradable,
    ranked_asset_allocation,
)


class IdeaChallengerTests(unittest.TestCase):
    def test_overnight_adjusts_open_with_same_close_factor(self):
        rows = overnight_decomposition([
            DailyBar("2026-01-02", 100, 101, 99, 100, 50),
            DailyBar("2026-01-03", 102, 106, 101, 104, 52),
        ])
        self.assertAlmostEqual(rows[0]["overnight_gross"], 0.02)
        self.assertAlmostEqual(rows[0]["intraday_gross"], 104 / 102 - 1)
        self.assertAlmostEqual(rows[0]["close_to_close"], 0.04)

    def test_opening_rule_enters_next_bar_and_trails_without_same_bar_fill(self):
        bars = []
        for index in range(14):
            price = 100 + index * 0.1
            bars.append(MinuteBar(f"2026-01-02T09:{index:02d}:00-05:00", price, price + 0.2, price - 0.2, price + 0.1))
        bars.extend([
            MinuteBar("2026-01-02T09:14:00-05:00", 102.0, 103.0, 101.9, 102.8),
            MinuteBar("2026-01-02T09:15:00-05:00", 103.0, 104.0, 102.8, 103.8),
            MinuteBar("2026-01-02T09:16:00-05:00", 103.8, 104.2, 103.6, 104.0),
        ])
        result = opening_candle_ema_atr_trade(bars, session_start_index=14, ema_period=12, atr_period=14)
        self.assertEqual(result["side"], 1)
        self.assertEqual(result["entry_index"], 15)
        self.assertEqual(result["entry_price"], 103.0)
        self.assertFalse(result["same_candle_fill_used"])

    def test_ranked_allocation_converts_failed_slots_to_cash(self):
        signals = [
            RankedAssetSignal("A", 0.20, 0.10, 0.20, True),
            RankedAssetSignal("B", 0.15, 0.20, 0.10, False),
            RankedAssetSignal("C", -0.10, 0.05, 0.30, True),
        ]
        weights = ranked_asset_allocation(signals, top_n=2)
        self.assertAlmostEqual(sum(weights.values()), 1.0)
        self.assertGreaterEqual(weights["CASH"], 0.5)

    def test_fractional_kelly_respects_caps_and_gross(self):
        weights = constrained_fractional_kelly(
            [0.10, 0.05], [[0.04, 0.0], [0.0, 0.01]],
            fraction=0.25, maximum_weights=[0.4, 0.7], maximum_gross=0.8,
        )
        self.assertLessEqual(sum(weights), 0.8 + 1e-12)
        self.assertLessEqual(weights[0], 0.4)
        self.assertLessEqual(weights[1], 0.7)

    def test_option_disagreement_is_parity_attention_feature(self):
        result = option_stock_disagreement(
            stock_price=100, call_price=6, put_price=5, strike=100,
            years=0.25, risk_free_rate=0.0,
        )
        self.assertAlmostEqual(result["option_implied_stock_price"], 101.0)
        self.assertAlmostEqual(result["relative_disagreement"], 0.01)

    def test_disclosure_cannot_trade_before_publication(self):
        args = dict(transaction_at="2026-01-01T12:00:00+00:00", public_filing_at="2026-02-01T12:00:00+00:00")
        self.assertFalse(public_disclosure_is_tradable(**args, decision_at="2026-02-01T12:00:00+00:00"))
        self.assertTrue(public_disclosure_is_tradable(**args, decision_at="2026-02-01T12:00:01+00:00"))


if __name__ == "__main__":
    unittest.main()
