import tempfile
import unittest
from pathlib import Path

from src.systematic_trader.trial_ledger import (
    Trial,
    TrialLedger,
    deflated_sharpe,
    promotion_gate,
)


def sample_returns(n=200, mean=0.004, sd=0.02, seed=0):
    import random
    rng = random.Random(seed)
    return [rng.gauss(mean, sd) for _ in range(n)]


class TrialLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.ledger = TrialLedger(Path(self.directory.name) / "trials.jsonl")

    def tearDown(self):
        self.directory.cleanup()

    def trials(self, count, family="alpha"):
        return [Trial(family, "exp", f"v{i}", "sharpe", "panel") for i in range(count)]

    def test_empty_ledger_verifies_and_counts_zero(self):
        self.assertEqual(self.ledger.count(), 0)
        self.assertTrue(self.ledger.verify()["valid"])

    def test_append_chains_and_counts_by_family(self):
        self.ledger.append(self.trials(5, "alpha"))
        self.ledger.append(self.trials(3, "beta"))
        self.assertEqual(self.ledger.count(), 8)
        self.assertEqual(self.ledger.count(family="alpha"), 5)
        self.assertEqual(self.ledger.families(), {"alpha": 5, "beta": 3})
        self.assertTrue(self.ledger.verify()["valid"])

    def test_tampering_breaks_the_chain(self):
        self.ledger.append(self.trials(6))
        lines = self.ledger.path.read_text().splitlines()
        lines[2] = lines[2].replace('"v2"', '"tampered"')
        self.ledger.path.write_text("\n".join(lines) + "\n")
        verification = self.ledger.verify()
        self.assertFalse(verification["valid"])
        self.assertEqual(verification["broken_at"], 2)

    def test_deletion_breaks_the_chain(self):
        self.ledger.append(self.trials(6))
        lines = self.ledger.path.read_text().splitlines()
        del lines[3]
        self.ledger.path.write_text("\n".join(lines) + "\n")
        self.assertFalse(self.ledger.verify()["valid"])

    def test_gate_fails_closed_on_unregistered_family(self):
        result = promotion_gate(sample_returns(), self.ledger, "never_registered")
        self.assertFalse(result["passes"])
        self.assertEqual(result["trials"], 0)

    def test_gate_fails_closed_on_broken_chain(self):
        self.ledger.append(self.trials(30))
        lines = self.ledger.path.read_text().splitlines()
        lines[1] = lines[1].replace('"v1"', '"x"')
        self.ledger.path.write_text("\n".join(lines) + "\n")
        result = promotion_gate(sample_returns(), self.ledger, "alpha")
        self.assertFalse(result["passes"])
        self.assertIn("chain", result["reason"])

    def test_more_trials_never_raise_the_deflated_ratio(self):
        returns = sample_returns()
        ratios = [deflated_sharpe(returns, n)["deflated_sharpe_ratio"] for n in (10, 100, 1000, 5000)]
        self.assertEqual(ratios, sorted(ratios, reverse=True))

    def test_null_threshold_rises_with_trials(self):
        returns = sample_returns()
        low = deflated_sharpe(returns, 10)["annualised_null_threshold"]
        high = deflated_sharpe(returns, 5000)["annualised_null_threshold"]
        self.assertGreater(high, low)

    def test_short_series_is_refused(self):
        with self.assertRaises(ValueError):
            deflated_sharpe(sample_returns(n=10), 100)

    def test_zero_variance_series_is_refused(self):
        with self.assertRaises(ValueError):
            deflated_sharpe([0.01] * 100, 100)


if __name__ == "__main__":
    unittest.main()
