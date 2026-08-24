import unittest

import numpy as np
import pandas as pd

from systematic_trader.sec_return_improvement import (
    CASH,
    adaptive_breadth,
    adaptive_concentration_weights,
    buffered_holding_selections,
    causal_strategy_allocator,
    event_conditioned_scores,
    purged_walk_forward_folds,
    residual_momentum_scores,
    sector_neutral_quality_scores,
    trend_quality_scores,
    walk_forward_ridge_rank,
)


class SECReturnImprovementTests(unittest.TestCase):
    @staticmethod
    def prices(periods=90):
        index = pd.date_range("2024-01-05", periods=periods, freq="W-FRI")
        step = np.arange(1.0, periods + 1.0)
        return pd.DataFrame(
            {
                "A": 50.0 + step * 1.2,
                "B": 60.0 + step * 0.8,
                "C": 40.0 + step * 0.4,
                "D": 45.0 + step * 0.7,
                "E": 30.0 + step * 0.2,
            },
            index=index,
        )

    def test_price_signals_do_not_change_when_future_prices_change(self):
        prices = self.prices()
        sectors = {"A": "tech", "B": "tech", "C": "industrial", "D": "industrial", "E": "energy"}
        cutoff = prices.index[72]
        altered = prices.copy()
        altered.loc[altered.index > cutoff, "A"] *= 20.0

        residual = residual_momentum_scores(
            prices, sectors, lookback_weeks=52, skip_weeks=4, minimum_history_weeks=26
        )
        altered_residual = residual_momentum_scores(
            altered, sectors, lookback_weeks=52, skip_weeks=4, minimum_history_weeks=26
        )
        trend, _ = trend_quality_scores(prices)
        altered_trend, _ = trend_quality_scores(altered)

        pd.testing.assert_frame_equal(residual.loc[:cutoff], altered_residual.loc[:cutoff])
        pd.testing.assert_frame_equal(trend.loc[:cutoff], altered_trend.loc[:cutoff])

    def test_quality_momentum_is_sector_neutral_and_respects_negative_features(self):
        panel = pd.DataFrame(
            {
                "decision_at": pd.to_datetime(["2026-01-01"] * 6, utc=True),
                "cik10": list("ABCDEF"),
                "sector": ["tech"] * 3 + ["energy"] * 3,
                "growth": [3, 2, 1, 30, 20, 10],
                "accruals": [1, 2, 3, 10, 20, 30],
            }
        )

        result = sector_neutral_quality_scores(
            panel,
            positive_features=["growth"],
            negative_features=["accruals"],
            minimum_available_features=2,
        )

        scores = result.set_index("cik10")["quality_momentum_score"]
        self.assertGreater(scores["A"], scores["C"])
        self.assertGreater(scores["D"], scores["F"])
        self.assertAlmostEqual(float(result.groupby("sector")["quality_momentum_score"].mean().abs().max()), 0.0)

    def test_event_conditioning_uses_only_strictly_delayed_events(self):
        decision = pd.Timestamp("2026-04-03", tz="UTC")
        base = pd.DataFrame({"decision_at": [decision, decision], "cik10": ["A", "B"], "score": [0.5, 0.5]})
        events = pd.DataFrame(
            {
                "available_at": [decision - pd.Timedelta(days=8), decision - pd.Timedelta(days=6)],
                "cik10": ["A", "B"],
                "event_score": [1.0, 1.0],
            }
        )

        result = event_conditioned_scores(base, events, event_weight=0.2, lookback_weeks=26, delay_weeks=1)
        scores = result.set_index("cik10")

        self.assertGreater(scores.loc["A", "conditioned_score"], scores.loc["B", "conditioned_score"])
        self.assertEqual(float(scores.loc["B", "event_score"]), 0.5)

    def test_adaptive_concentration_obeys_generic_issuer_and_sector_caps(self):
        components = pd.DataFrame(
            {
                "residual": [1.0, 0.9, 0.4, 0.2, 0.1],
                "quality": [1.0, 0.8, 0.3, 0.2, 0.1],
                "trend": [1.0, 0.9, 0.4, 0.1, 0.0],
            },
            index=list("ABCDE"),
        )
        breadth, confidence = adaptive_breadth(
            components, high_confidence_minimum=0.6, medium_confidence_minimum=0.3
        )
        weights = adaptive_concentration_weights(
            components.mean(axis=1),
            {"A": "tech", "B": "tech", "C": "energy", "D": "energy", "E": "health"},
            breadth=breadth,
            issuer_cap=0.20,
            sector_cap=0.40,
            conviction_power=1.5,
        )

        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(float(weights.drop(CASH).max()), 0.20 + 1e-12)
        self.assertLessEqual(float(weights[["A", "B"]].sum()), 0.40 + 1e-12)
        self.assertAlmostEqual(float(weights.sum()), 1.0)

    def test_purged_walk_forward_has_no_training_overlap(self):
        decisions = pd.date_range("2023-01-01", periods=14, freq="QS", tz="UTC")
        folds = purged_walk_forward_folds(
            decisions,
            minimum_training_decisions=6,
            test_decisions_per_fold=2,
            purge_decisions=1,
            embargo_decisions=1,
        )

        self.assertTrue(folds)
        for fold in folds:
            self.assertLess(max(fold.train_decisions), min(fold.test_decisions))
            train_end = decisions.get_loc(max(fold.train_decisions))
            test_start = decisions.get_loc(min(fold.test_decisions))
            self.assertGreaterEqual(test_start - train_end, 2)

    def test_ml_predictions_are_strictly_out_of_sample(self):
        decisions = pd.date_range("2023-01-01", periods=12, freq="QS", tz="UTC")
        rows = []
        for d_index, decision in enumerate(decisions):
            for company in range(30):
                feature = company / 30.0 + d_index * 0.01
                rows.append(
                    {
                        "decision_at": decision,
                        "cik10": f"{company:010d}",
                        "x1": feature,
                        "x2": np.sin(company),
                        "target": feature * 0.3 + np.cos(company) * 0.01,
                    }
                )
        panel = pd.DataFrame(rows)

        result = walk_forward_ridge_rank(
            panel,
            features=["x1", "x2"],
            target="target",
            alphas=[0.1, 1.0, 10.0],
            minimum_training_decisions=6,
            test_decisions_per_fold=2,
            purge_decisions=1,
            embargo_decisions=1,
            minimum_training_rows=100,
        )

        self.assertFalse(result.empty)
        self.assertTrue((result["train_end"] < result["decision_at"]).all())
        self.assertTrue(result["prediction_rank"].between(0.0, 1.0).all())
        self.assertTrue((result["confidence"] >= 0.0).all())

    def test_buffered_holding_keeps_incumbent_through_one_bad_decision(self):
        decisions = pd.date_range("2025-01-01", periods=4, freq="QS", tz="UTC")
        ranks = [
            {"A": 3.0, "B": 2.0, "C": 1.0},
            {"A": 0.0, "B": 3.0, "C": 2.0},
            {"A": 0.0, "B": 3.0, "C": 2.0},
            {"A": 0.0, "B": 3.0, "C": 2.0},
        ]
        panel = pd.DataFrame(
            [
                {"decision_at": decision, "cik10": cik, "score": score}
                for decision, values in zip(decisions, ranks)
                for cik, score in values.items()
            ]
        )

        result = buffered_holding_selections(
            panel,
            breadth=1,
            entry_rank_buffer=1,
            exit_rank_multiple=1.5,
            minimum_holding_decisions=2,
            maximum_holding_decisions=4,
        )

        selected = result.groupby("decision_at")["cik10"].first().tolist()
        self.assertEqual(selected[:2], ["A", "A"])
        self.assertEqual(selected[2], "B")

    def test_buffered_holding_exits_incumbent_when_current_score_is_missing(self):
        decisions = pd.date_range("2025-01-01", periods=2, freq="QS", tz="UTC")
        panel = pd.DataFrame([
            {"decision_at": decisions[0], "cik10": "A", "score": 2.0},
            {"decision_at": decisions[0], "cik10": "B", "score": 1.0},
            {"decision_at": decisions[1], "cik10": "A", "score": np.nan},
            {"decision_at": decisions[1], "cik10": "B", "score": 2.0},
        ])

        result = buffered_holding_selections(
            panel,
            breadth=1,
            entry_rank_buffer=1,
            exit_rank_multiple=2.0,
            minimum_holding_decisions=2,
            maximum_holding_decisions=4,
        )

        selected = result.groupby("decision_at")["cik10"].first().tolist()
        self.assertEqual(selected, ["A", "B"])

    def test_strategy_allocator_does_not_look_at_current_or_future_return(self):
        index = pd.date_range("2024-01-05", periods=70, freq="W-FRI")
        returns = pd.DataFrame(
            {"alpha": np.linspace(0.001, 0.01, 70), "defensive": np.linspace(0.004, 0.002, 70)},
            index=index,
        )
        cutoff = index[60]
        altered = returns.copy()
        altered.loc[altered.index >= cutoff, "alpha"] = -0.5
        kwargs = dict(
            lookback_weeks=52,
            minimum_history_weeks=26,
            momentum_lookbacks_weeks=[13, 26],
            maximum_sleeve_weight=0.6,
            minimum_active_sleeve_weight=0.1,
            independence_penalty=0.5,
        )

        original_weights = causal_strategy_allocator(returns, **kwargs)
        altered_weights = causal_strategy_allocator(altered, **kwargs)

        pd.testing.assert_series_equal(original_weights.loc[cutoff], altered_weights.loc[cutoff])


if __name__ == "__main__":
    unittest.main()
