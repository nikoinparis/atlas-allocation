import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / "config/runtime_profiles.json").read_text(encoding="utf-8"))

    def test_all_non_python_queue_candidates_have_profiles(self):
        expected = {"ast-0019", "ast-0020", "ast-0021", "ast-0030", "ast-0035", "ast-0036", "ast-0046", "ast-0051"}
        self.assertEqual(expected, set(self.config["candidates"]))

    def test_every_candidate_resolves_to_offline_test_profile(self):
        profiles = self.config["profiles"]
        for candidate in self.config["candidates"].values():
            profile = profiles[candidate["profile"]]
            self.assertEqual("disabled", profile["test_phase_network"])

    def test_common_policy_forbids_host_access_and_secrets(self):
        policy = self.config["common_isolation"]
        self.assertTrue(policy["rootless"])
        self.assertFalse(policy["host_mounts"])
        self.assertFalse(policy["host_secrets"])
        self.assertTrue(policy["drop_all_capabilities"])


if __name__ == "__main__":
    unittest.main()
