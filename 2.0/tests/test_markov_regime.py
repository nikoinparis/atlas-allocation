import unittest

from src.systematic_trader.markov_regime import (
    causal_stress_probabilities,
    fit_two_state_gaussian_markov,
    scaled_returns,
)


class MarkovRegimeTests(unittest.TestCase):
    def test_fit_identifies_lower_mean_state_as_stress(self):
        values = ([-0.03, -0.02, -0.01] * 20) + ([0.01, 0.02, 0.03] * 20)
        model = fit_two_state_gaussian_markov(values, iterations=20)
        self.assertLess(model.means[model.stress_state], model.means[1 - model.stress_state])

    def test_probabilities_are_prefix_causal(self):
        training = ([-0.02, -0.01, 0.01, 0.02] * 20)
        model = fit_two_state_gaussian_markov(training, iterations=20)
        base = [0.01, -0.02, 0.03, -0.01]
        original = causal_stress_probabilities(base, model)
        changed = causal_stress_probabilities(base[:3] + [0.50], model)
        self.assertEqual(original, changed)

    def test_scaling_charges_underlying_and_overlay_turnover(self):
        returns, exposures = scaled_returns(
            [0.10, 0.10], [1.0, 0.0], [0.0, 1.0], cost_bps=100.0, minimum_exposure=0.5
        )
        self.assertEqual([1.0, 0.5], exposures)
        self.assertAlmostEqual(0.08, returns[0])
        self.assertAlmostEqual(0.045, returns[1])


if __name__ == "__main__":
    unittest.main()
