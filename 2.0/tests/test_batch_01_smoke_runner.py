import base64
import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/run_batch_01_smoke_tests.py"
SPEC = importlib.util.spec_from_file_location("batch_01_smoke_runner", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SmokeRunnerTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "entry_id": "ast-9999",
            "name": "fixture",
            "repository": "owner/repository",
            "head_commit": "a" * 40,
            "planned_environment": "python_container",
        }
        self.policy = {
            "source_inspection_image": "docker.io/alpine/git:2.49.1",
            "limits": {
                "pids": 256,
                "memory": "768m",
                "cpus": 1,
                "work_tmpfs": "1536m",
                "timeout_seconds": 600,
            },
        }

    def test_container_command_has_required_isolation(self):
        command = MODULE.container_command(self.row, self.policy)
        joined = " ".join(command)
        self.assertIn("--read-only", command)
        self.assertIn("--cap-drop=all", command)
        self.assertIn("--security-opt=no-new-privileges", command)
        self.assertIn("--pids-limit=256", command)
        self.assertIn("--memory=768m", command)
        self.assertNotIn("--volume", command)
        self.assertNotIn("/Users/", joined)

    def test_result_parser_ignores_unstructured_output(self):
        parsed = MODULE.parse_result_lines("noise\nACTUAL_COMMIT=abc=123\nbad-key=x\n")
        self.assertEqual(parsed, {"ACTUAL_COMMIT": "abc=123"})

    def test_line_decoder(self):
        encoded = base64.b64encode(b"pyproject.toml\ntests\n").decode()
        self.assertEqual(MODULE.decode_lines(encoded), ["pyproject.toml", "tests"])


if __name__ == "__main__":
    unittest.main()
