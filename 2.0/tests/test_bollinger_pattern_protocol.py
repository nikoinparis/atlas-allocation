import unittest

from src.systematic_trader.bollinger_pattern_protocol import bollinger_bands, find_bottom_w


class BollingerPatternProtocolTests(unittest.TestCase):
    def test_bands_use_full_window_and_sample_std(self):
        mid, std, upper, lower = bollinger_bands([1, 2, 3], window=3)
        self.assertEqual(mid, [None, None, 2.0])
        self.assertEqual(std[-1], 1.0)
        self.assertEqual(upper[-1], 4.0)
        self.assertEqual(lower[-1], 0.0)

    def test_exact_repository_search_order_finds_constructed_w(self):
        size, index = 76, 75
        price = [9.0] * size; mid = [9.0] * size; upper = [12.0] * size; lower = [7.0] * size
        upper[index] = 10.0; price[index] = 11.0
        mid[60] = price[60] = 10.0
        lower[40] = price[40] = 8.0
        mid[30] = 9.0; price[30] = 10.0
        lower[70] = 7.89995; price[70] = 7.9
        self.assertEqual(find_bottom_w(index, price, mid, upper, lower, period=75, alpha=.0001, normalized=False), (30, 40, 60, 70, 75))

    def test_search_never_reads_future_index(self):
        price = [10.0] * 80; mid = [10.0] * 80; upper = [11.0] * 80; lower = [9.0] * 80
        self.assertIsNone(find_bottom_w(75, price, mid, upper, lower, period=75, alpha=.0001, normalized=False))


if __name__ == "__main__":
    unittest.main()
