import json
import unittest

import scripts.run_sec_multisignal_plateau_confirmation_v1 as subject


class MultiSignalPlateauTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(subject.CONFIG.read_text())

    def test_grid_is_locked_to_twenty_unique_paths(self):
        names = {
            subject.candidate_name(weight, breadth)
            for weight in self.config["secondary_weights"]
            for breadth in self.config["breadths"]
        }

        self.assertEqual(len(names), 20)
        self.assertIn("bsq200__breadth20", names)

    def test_primary_is_inside_fine_grid(self):
        self.assertIn(self.config["primary_secondary_weight"], self.config["secondary_weights"])
        self.assertIn(self.config["primary_breadth"], self.config["breadths"])


if __name__ == "__main__":
    unittest.main()
