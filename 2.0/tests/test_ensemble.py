import unittest

from src.systematic_trader.ensemble import (
    average_holdings_overlap,
    breadth_admission_gate,
    combine_weight_histories,
    correlation,
    correlation_clusters,
    effective_independent_count,
    expected_maximum_sharpe,
    fundamental_law_decomposition,
    greedy_low_correlation_selection,
    marginal_effective_breadth,
    weighted_holdings_overlap,
)


class EnsembleTests(unittest.TestCase):
    def test_correlation_and_effective_count(self):
        self.assertAlmostEqual(1.0, correlation([1, 2, 3], [2, 4, 6]))
        matrix = {"a": {"a": 1.0, "b": 0.0}, "b": {"a": 0.0, "b": 1.0}}
        self.assertAlmostEqual(2.0, effective_independent_count(matrix))

    def test_overlap_and_combined_weights(self):
        self.assertAlmostEqual(0.5, weighted_holdings_overlap({"A": 1.0}, {"A": 0.5, "B": 0.5}))
        histories = {"x": {"d": {"A": 1.0}}, "y": {"d": {"B": 1.0}}}
        combined = combine_weight_histories(["d"], histories, {"x": 0.25, "y": 0.75})
        self.assertEqual({"A": 0.25, "B": 0.75}, combined["d"])
        self.assertEqual(0.0, average_holdings_overlap(["d"], histories["x"], histories["y"]))

    def test_clusters_and_greedy_selection(self):
        matrix = {
            "a": {"a": 1.0, "b": 0.95, "c": 0.2},
            "b": {"a": 0.95, "b": 1.0, "c": 0.3},
            "c": {"a": 0.2, "b": 0.3, "c": 1.0},
        }
        self.assertEqual([["a", "b"], ["c"]], correlation_clusters(list(matrix), matrix, 0.9))
        self.assertEqual(["a", "c"], greedy_low_correlation_selection(list(matrix), matrix, start="a", count=2))

    def test_expected_maximum_sharpe_increases_with_search_count(self):
        self.assertGreater(
            expected_maximum_sharpe(trials=288, observations=1000),
            expected_maximum_sharpe(trials=10, observations=1000),
        )

    def test_marginal_breadth_rewards_independent_not_duplicate_candidate(self):
        independent = {
            "a": {"a": 1.0, "b": 0.0},
            "b": {"a": 0.0, "b": 1.0},
        }
        duplicate = {
            "a": {"a": 1.0, "b": 1.0},
            "b": {"a": 1.0, "b": 1.0},
        }
        self.assertAlmostEqual(1.0, marginal_effective_breadth("b", independent))
        self.assertAlmostEqual(0.0, marginal_effective_breadth("b", duplicate))

    def test_breadth_gate_fails_closed_without_holdings_overlap(self):
        matrix = {
            "incumbent": {"incumbent": 1.0, "candidate": 1.0},
            "candidate": {"incumbent": 1.0, "candidate": 1.0},
        }
        with self.assertRaises(ValueError):
            breadth_admission_gate(
                candidate="candidate", matrix=matrix, holdings_overlap_by_peer={}
            )
        result = breadth_admission_gate(
            candidate="candidate",
            matrix=matrix,
            holdings_overlap_by_peer={"incumbent": 1.0},
        )
        self.assertFalse(result["breadth_gate_pass"])
        self.assertFalse(result["performance_promotion_authorized"])

    def test_fundamental_law_decomposition_keeps_transfer_efficiency_explicit(self):
        result = fundamental_law_decomposition(
            information_coefficient=0.05,
            effective_breadth=100.0,
            transfer_coefficient=0.5,
            realized_information_ratio=0.2,
        )
        self.assertAlmostEqual(0.5, result["theoretical_information_ratio"])
        self.assertAlmostEqual(0.25, result["implementable_information_ratio"])
        self.assertAlmostEqual(0.8, result["realized_to_implementable_efficiency"])


if __name__ == "__main__":
    unittest.main()
