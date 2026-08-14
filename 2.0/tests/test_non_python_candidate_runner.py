import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_non_python_candidate_tests.py"
spec = importlib.util.spec_from_file_location("non_python_runner", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class NonPythonRunnerTests(unittest.TestCase):
    def test_checked_in_execution_evidence_records_pass_and_failure(self):
        evidence = ROOT / "evidence/non_python_execution"
        node = json.loads((evidence / "ast-0051.json").read_text(encoding="utf-8"))
        rust = json.loads((evidence / "ast-0036.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", node["status"])
        self.assertEqual(0, node["tests"]["offline_unit"]["exit_code"])
        self.assertEqual("dependency_failed", rust["status"])
        self.assertIn("polars", rust["dependency_log"].lower())
        barter = json.loads((evidence / "ast-0021.json").read_text(encoding="utf-8"))
        hft = json.loads((evidence / "ast-0046.json").read_text(encoding="utf-8"))
        self.assertEqual("passed", barter["status"])
        self.assertEqual("generated_by_execution_gate", barter["lockfile_origin"])
        self.assertEqual("passed", hft["status"])
        self.assertEqual(0, hft["tests"]["hftbacktest_core"]["exit_code"])

    def test_profiles_pin_commits_and_use_offline_tests(self):
        self.assertEqual({"ast-0021", "ast-0036", "ast-0046", "ast-0051"}, set(module.CANDIDATES))
        command = module.container_command(
            name="probe", image="example:pin", volume="named-volume",
            command=["tool", "test"], offline=True,
        )
        self.assertIn("--network=none", command)
        self.assertIn("named-volume:/work:rw", command)
        self.assertNotIn("/Users/", " ".join(command))

    def test_dependency_and_test_network_are_separate(self):
        online = module.container_command(
            name="deps", image="example:pin", volume="named-volume",
            command=["tool", "fetch"], offline=False,
        )
        offline = module.container_command(
            name="tests", image="example:pin", volume="named-volume",
            command=["tool", "test"], offline=True,
        )
        self.assertNotIn("--network=none", online)
        self.assertIn("--network=none", offline)


if __name__ == "__main__":
    unittest.main()
