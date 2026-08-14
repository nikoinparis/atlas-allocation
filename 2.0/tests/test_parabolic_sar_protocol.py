import unittest

from src.systematic_trader.parabolic_sar_protocol import repository_parabolic_sar


class ParabolicSarProtocolTests(unittest.TestCase):
    def test_source_initialization_is_preserved_but_first_row_not_long(self):
        rows = repository_parabolic_sar([
            {"high": 11, "low": 9, "close": 10},
            {"high": 12, "low": 10, "close": 11},
        ], initial_af=.02, step_af=.02, maximum_af=.2)
        self.assertFalse(rows[0]["long"])
        self.assertEqual(rows[1]["trend"], 1)
        self.assertEqual(rows[1]["real_sar"], 11.0)

    def test_uptrend_continuation_constrains_sar_and_increases_af(self):
        rows = repository_parabolic_sar([
            {"high": 11, "low": 9, "close": 10},
            {"high": 12, "low": 10, "close": 11.5},
            {"high": 13, "low": 10.5, "close": 12.5},
        ], initial_af=.02, step_af=.02, maximum_af=.2)
        self.assertEqual(rows[2]["trend"], 2)
        self.assertEqual(rows[2]["sar"], 9.0)
        self.assertEqual(rows[2]["ep"], 13.0)
        self.assertEqual(rows[2]["af"], .04)
        self.assertTrue(rows[2]["long"])

    def test_reversal_uses_prior_extreme_as_real_sar(self):
        rows = repository_parabolic_sar([
            {"high": 11, "low": 9, "close": 10},
            {"high": 12, "low": 10, "close": 11.5},
            {"high": 11, "low": 8, "close": 8.5},
        ], initial_af=.02, step_af=.02, maximum_af=.2)
        self.assertEqual(rows[2]["trend"], -1)
        self.assertEqual(rows[2]["real_sar"], 12.0)
        self.assertFalse(rows[2]["long"])
        self.assertEqual(rows[2]["af"], .02)

    def test_invalid_parameters_rejected(self):
        with self.assertRaises(ValueError):
            repository_parabolic_sar([{"high": 2, "low": 1, "close": 1.5}] * 2, initial_af=0, step_af=.02, maximum_af=.2)


if __name__ == "__main__":
    unittest.main()
