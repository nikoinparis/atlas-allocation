import hashlib
import json
import unittest
from pathlib import Path

from src.systematic_trader.portfolio_construction import PortfolioSpec, build_portfolio_weights
from src.systematic_trader.research_lab import StrategySpec, experiment_id, retrospective_walk_forward


class PortfolioConstructionTests(unittest.TestCase):
    def setUp(self):
        self.dates = ["2025-01-03", "2025-01-31", "2025-02-07"]
        self.assets = ["AAA", "BBB"]
        self.scores = {day: {"AAA": 0.8, "BBB": 0.4} for day in self.dates}
        self.prices = {day: {"AAA": 10.0, "BBB": 10.0, "BIL": 10.0} for day in self.dates}
        self.returns = {
            "2025-01-03": {"AAA": 0.01, "BBB": 0.04, "BIL": 0.0},
            "2025-01-31": {"AAA": 0.01, "BBB": -0.04, "BIL": 0.0},
            "2025-02-07": {"AAA": 0.01, "BBB": 0.04, "BIL": 0.0},
        }

    def test_equal_weight_is_fully_invested_and_endpoint_is_not_rebalanced(self):
        weights, rebalances, _ = build_portfolio_weights(
            dates=self.dates, assets=self.assets, scores=self.scores, prices=self.prices,
            simple_returns=self.returns, spec=PortfolioSpec(method="equal_weight", top_n=2, min_signal=0.0)
        )
        self.assertEqual(0.5, weights["2025-01-31"]["AAA"])
        self.assertAlmostEqual(1.0, sum(weights["2025-02-07"].values()))
        self.assertNotIn("2025-02-07", rebalances)

    def test_score_weighting_changes_allocation(self):
        weights, _, _ = build_portfolio_weights(
            dates=self.dates, assets=self.assets, scores=self.scores, prices=self.prices,
            simple_returns=self.returns, spec=PortfolioSpec(method="score_weighted", top_n=2, min_signal=0.0)
        )
        self.assertGreater(weights["2025-01-31"]["AAA"], weights["2025-01-31"]["BBB"])


class ResearchLabTests(unittest.TestCase):
    def test_experiment_identity_is_deterministic_and_configuration_sensitive(self):
        base = StrategySpec(("momentum",), 4, PortfolioSpec("equal_weight", 4, 0.05))
        changed = StrategySpec(("momentum",), 8, PortfolioSpec("equal_weight", 4, 0.05))
        self.assertEqual(experiment_id(base, "snapshot"), experiment_id(base, "snapshot"))
        self.assertNotEqual(experiment_id(base, "snapshot"), experiment_id(changed, "snapshot"))

    def test_walk_forward_selects_using_training_only(self):
        def rows(train_return, evaluation_return):
            result = []
            for index in range(104):
                result.append({"realization_date": f"{2010 + index // 52}-{index % 12 + 1:02d}-01", "net_return": train_return, "turnover": 0.0, "cost": 0.0})
            for index in range(52):
                result.append({"realization_date": f"2016-{index % 12 + 1:02d}-{index % 27 + 1:02d}", "net_return": evaluation_return, "turnover": 0.0, "cost": 0.0})
            return result
        # Avoid zero-volatility metrics while making A clearly superior in training.
        a = rows(0.01, -0.01)
        b = rows(0.001, 0.02)
        for index, row in enumerate(a[:104]):
            row["net_return"] += 0.001 if index % 2 else -0.001
        for index, row in enumerate(b[:104]):
            row["net_return"] += 0.001 if index % 2 else -0.001
        selections, combined, _ = retrospective_walk_forward(
            [{"experiment_id": "A", "periods": a}, {"experiment_id": "B", "periods": b}],
            [{"train_start": "2010-01-01", "train_end": "2015-12-31", "evaluation_start": "2016-01-01", "evaluation_end": "2016-12-31"}],
        )
        self.assertEqual("A", selections[0]["selected_experiment_id"])
        self.assertTrue(combined)
        self.assertTrue(all(float(row["net_return"]) < 0.0 for row in combined))

    def test_frozen_v4_manifest_hashes_and_lab_reconciliation(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "config/strategies/composite_trend_quality_refined_free_snapshot_v4.json").read_text())
        for relative, expected in manifest["sha256"].items():
            self.assertEqual(expected, hashlib.sha256((root / relative).read_bytes()).hexdigest())
        result = json.loads((root / "evidence/research_lab_batch_01/result.json").read_text())
        benchmark = result["v4_benchmark"]
        frozen = manifest["frozen_benchmark_evidence"]
        self.assertEqual(frozen["experiment_id"], benchmark["experiment_id"])
        self.assertAlmostEqual(frozen["annual_return"], benchmark["full_annual_return"])
        self.assertAlmostEqual(frozen["sharpe_zero_rf"], benchmark["full_sharpe_zero_rf"])
        self.assertFalse(benchmark["untouched_holdout"])


if __name__ == "__main__":
    unittest.main()
