import unittest

from scripts.run_sec_return_improvement_tournament_v1 import authorization_state


class SECReturnImprovementTournamentTests(unittest.TestCase):
    def test_gate_blocks_performance_before_authorization(self):
        self.assertEqual(
            authorization_state({"strategy_testing_authorized": False}, True, True),
            "blocked_broad_research_gate",
        )

    def test_protocol_mismatch_has_priority(self):
        self.assertEqual(
            authorization_state({"strategy_testing_authorized": True}, False, True),
            "blocked_frozen_protocol_mismatch",
        )

    def test_panel_is_required_after_gate_opens(self):
        self.assertEqual(
            authorization_state({"strategy_testing_authorized": True}, True, False),
            "authorized_waiting_for_broad_panel",
        )


if __name__ == "__main__":
    unittest.main()
