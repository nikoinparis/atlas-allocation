import unittest

from src.systematic_trader.rsi_pattern_protocol import repository_rsi, threshold_states, _pattern_at


class RsiPatternProtocolTests(unittest.TestCase):
    def test_repository_rsi_alignment_and_rising_path(self):
        values = repository_rsi(list(range(1, 17)), lag=14)
        self.assertEqual(len(values), 16)
        self.assertTrue(all(value is None for value in values[:14]))
        self.assertEqual(values[14], 100.0)

    def test_threshold_states_preserve_literal_daily_positions(self):
        rsi = [None, 20.0, 50.0, 80.0]
        self.assertEqual(threshold_states(rsi, long_only=False), [0, 1, 0, -1])
        self.assertEqual(threshold_states(rsi, long_only=True), [0, 1, 0, 0])

    def test_constructed_seven_node_pattern(self):
        series = [9.0] * 40
        index = 39; series[index] = 10.0
        series[14] = 10.0
        series[16] = 11.0
        series[20] = 10.0
        series[25] = 12.0
        series[30] = 10.0
        series[34] = 11.0
        self.assertEqual(_pattern_at(index, series), (14, 16, 20, 25, 30, 34, 39))


if __name__ == "__main__":
    unittest.main()
