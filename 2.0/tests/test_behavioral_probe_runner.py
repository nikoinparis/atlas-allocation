import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("behavioral_probe_runner", SCRIPTS / "run_behavioral_probes.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class BehavioralProbeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "entry_id": "ast-0047",
            "repository": "owner/repo",
            "head_commit": "a" * 40,
        }
        self.policy = {
            "python_test_image": "docker.io/library/python:3.12-bookworm",
            "python_legacy_test_image": "docker.io/library/python:3.11-bookworm",
            "limits": {"pids": 256, "cpus": 1},
        }

    def test_probe_command_is_offline_and_has_no_host_mount(self):
        command = MODULE.probe_command(self.row, self.policy, "po2-behavior-ast-0047")
        joined = " ".join(command)
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop=all", command)
        self.assertIn("po2-behavior-ast-0047:/work:rw", command)
        self.assertNotIn("/Users/", joined)

    def test_probe_sources_compile(self):
        for probe in MODULE.PROBES.values():
            compile(probe.read_text(encoding="utf-8"), str(probe), "exec")


if __name__ == "__main__":
    unittest.main()
