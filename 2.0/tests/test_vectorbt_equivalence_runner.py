import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_vectorbt_equivalence_batch_13.py"
SPEC = importlib.util.spec_from_file_location("vectorbt_equivalence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class VectorbtEquivalenceRunnerTests(unittest.TestCase):
    def test_license_and_non_incorporation_are_explicit(self):
        self.assertIn("LicenseRef-Commons-Clause", SCRIPT.read_text())
        self.assertIn('"incorporated_into_core":False', SCRIPT.read_text())

    def test_probe_runs_without_network_and_host_mounts(self):
        self.assertIn("--read-only", MODULE.limits())
        self.assertNotIn("/Users/", MODULE.PROBE)


if __name__ == "__main__":
    unittest.main()
