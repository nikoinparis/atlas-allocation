import unittest

from src.systematic_trader.shooting_star_protocol import shooting_star_shapes, shooting_star_short_states


def bar(open_, high, low, close):
    return {"open": open_, "high": high, "low": low, "close": close}


class ShootingStarProtocolTests(unittest.TestCase):
    def test_normalized_shape_requires_all_six_completed_bar_conditions(self):
        bars = [
            bar(9.5, 10.1, 9.4, 10.0),
            bar(10.0, 10.6, 9.9, 10.5),
            bar(10.61, 11.2, 10.599, 10.60),
        ]
        shapes, audit = shooting_star_shapes(bars, body_mode="normalized_absolute_expanding")
        self.assertEqual(shapes, [False, False, True])
        self.assertEqual(audit[-1]["condition_count"], 6)

    def test_confirmation_is_observed_one_bar_after_star(self):
        bars = [
            bar(9.5, 10.1, 9.4, 10.0),
            bar(10.0, 10.6, 9.9, 10.5),
            bar(10.61, 11.2, 10.599, 10.60),
            bar(10.58, 11.0, 10.2, 10.4),
            bar(10.4, 10.5, 10.1, 10.2),
        ]
        states, events, stars, _ = shooting_star_short_states(
            bars, body_mode="normalized_absolute_expanding", require_confirmation=True,
        )
        self.assertEqual(states[2], 0)
        self.assertEqual(events[3], "short_entry_confirmed")
        self.assertEqual(states[3], -1)
        self.assertEqual(stars[3], 2)

    def test_failed_confirmation_never_enters(self):
        bars = [
            bar(9.5, 10.1, 9.4, 10.0),
            bar(10.0, 10.6, 9.9, 10.5),
            bar(10.61, 11.2, 10.599, 10.60),
            bar(10.7, 11.3, 10.4, 10.8),
        ]
        states, events, _, _ = shooting_star_short_states(
            bars, body_mode="normalized_absolute_expanding", require_confirmation=True,
        )
        self.assertEqual(states, [0, 0, 0, 0])
        self.assertEqual(events[-1], "flat")

    def test_time_exit_is_seven_sessions_from_star(self):
        bars = [
            bar(9.5, 10.1, 9.4, 10.0),
            bar(10.0, 10.6, 9.9, 10.5),
            bar(10.61, 11.2, 10.599, 10.60),
        ] + [bar(10.5, 10.8, 10.3, 10.5) for _ in range(8)]
        states, events, _, _ = shooting_star_short_states(
            bars, body_mode="normalized_absolute_expanding", require_confirmation=False,
        )
        self.assertEqual(states[2], -1)
        self.assertEqual(states[8], -1)
        self.assertEqual(states[9], 0)
        self.assertEqual(events[9], "exit_time")

    def test_full_sample_future_bar_cannot_change_past_shape(self):
        prefix = [
            bar(9.5, 10.1, 9.4, 10.0),
            bar(10.0, 10.6, 9.9, 10.5),
            bar(10.61, 11.2, 10.599, 10.60),
        ]
        first, _ = shooting_star_shapes(prefix, body_mode="source_signed_expanding")
        extended, _ = shooting_star_shapes(prefix + [bar(100, 150, 50, 60)], body_mode="source_signed_expanding")
        self.assertEqual(first, extended[: len(prefix)])


if __name__ == "__main__":
    unittest.main()
