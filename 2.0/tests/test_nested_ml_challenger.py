import unittest

from src.systematic_trader.nested_ml_challenger import fit_ridge, nested_walk_forward, predict


class NestedMlChallengerTests(unittest.TestCase):
    def test_ridge_learns_simple_relation(self):
        features = [[float(i), float(i % 3)] for i in range(100)]
        labels = [2.0 * row[0] - row[1] for row in features]
        model = fit_ridge(features, labels, 0.01)
        self.assertAlmostEqual(predict(model, [10.0, 1.0]), 19.0, places=1)

    def test_outer_folds_have_embargo_and_no_overlap(self):
        dates = [f"d{i:04d}" for i in range(500)]
        features = [[float(i % 7), float(i % 11)] for i in range(500)]
        labels = [float(i % 5) for i in range(500)]
        predictions, folds = nested_walk_forward(dates, features, labels)
        self.assertTrue(predictions)
        self.assertTrue(all(row["causal_embargo_pass"] for row in folds))
        self.assertEqual(len(predictions), 240)


if __name__ == "__main__":
    unittest.main()
