from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_sec_return_tournament_readiness_v1.py"
SPEC = importlib.util.spec_from_file_location("tournament_readiness", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


class TournamentReadinessTests(unittest.TestCase):
    def test_hash_verification_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "artifact.csv"
            artifact.write_text("a\n1\n")
            digest = module.sha256(artifact)
            result = directory / "result.json"
            result.write_text('{"artifact_sha256":{"artifact":"' + digest + '"}}')
            self.assertEqual(module.verified_artifacts(result), {"artifact": True})
            artifact.write_text("a\n2\n")
            self.assertEqual(module.verified_artifacts(result), {"artifact": False})

    def test_audit_contains_no_performance_engine(self) -> None:
        source = SCRIPT.read_text()
        self.assertNotIn("net_return", source)
        self.assertNotIn("annualized_return", source)
        self.assertIn('"performance_evaluated": False', source)
        self.assertIn('"live_trading_enabled": False', source)


if __name__ == "__main__":
    unittest.main()
