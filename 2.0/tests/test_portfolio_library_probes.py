import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_portfolio_library_probes.py"
SPEC = importlib.util.spec_from_file_location("portfolio_library_probes", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PortfolioLibraryProbeTests(unittest.TestCase):
    def test_all_four_libraries_have_distinct_probes(self):
        self.assertEqual(set(MODULE.PROBES), {"ast-0183", "ast-0184", "ast-0185", "ast-0187"})
        self.assertTrue(all("PROBE_JSON=" in value for value in MODULE.PROBES.values()))

    def test_container_limits_are_hardened(self):
        limits = MODULE.limits()
        self.assertIn("--read-only", limits)
        self.assertIn("--cap-drop=all", limits)
        self.assertIn("--security-opt=no-new-privileges", limits)
        self.assertIn("--memory=2g", limits)


if __name__ == "__main__":
    unittest.main()
