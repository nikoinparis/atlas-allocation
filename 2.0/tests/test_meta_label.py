import unittest

from src.systematic_trader.meta_label import (
    classification_metrics,
    correctness_probabilities,
    fit_logistic_correctness,
)


class MetaLabelTests(unittest.TestCase):
    def test_logistic_correctness_learns_separable_secondary_label(self):
        features = [[float(value)] for value in range(-20, 20)]
        labels = [int(value > 0) for value in range(-20, 20)]
        model = fit_logistic_correctness(features, labels, iterations=800, learning_rate=0.1)
        probabilities = correctness_probabilities(model, [[-10.0], [10.0]])
        self.assertLess(probabilities[0], 0.5)
        self.assertGreater(probabilities[1], 0.5)

    def test_metrics_report_precision_f1_and_coverage(self):
        result = classification_metrics([1, 0, 1, 0], [True, True, False, False])
        self.assertEqual(0.5, result["precision"])
        self.assertEqual(0.5, result["recall"])
        self.assertEqual(0.5, result["f1"])
        self.assertEqual(0.5, result["coverage"])


if __name__ == "__main__":
    unittest.main()
