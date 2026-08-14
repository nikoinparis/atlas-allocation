import importlib.util
import json
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/run_python_candidate_tests.py'
SPEC = importlib.util.spec_from_file_location('python_candidate_runner', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PythonCandidateRunnerTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            'entry_id': 'ast-9999', 'name': 'fixture', 'repository': 'owner/repo',
            'head_commit': 'a' * 40,
        }
        self.policy = {
            'python_test_image': 'docker.io/library/python:3.12-slim-bookworm',
            'python_legacy_test_image': 'docker.io/library/python:3.11-bookworm',
            'limits': {'pids': 256, 'cpus': 1},
        }

    def test_install_uses_named_volume_and_no_host_path(self):
        command = MODULE.install_command(self.row, self.policy, 'po2-python-ast-9999')
        joined = ' '.join(command)
        self.assertIn('po2-python-ast-9999:/work:rw', command)
        self.assertNotIn('/Users/', joined)
        self.assertIn('--read-only', command)
        self.assertIn('--cap-drop=all', command)

    def test_test_phase_disables_network(self):
        command = MODULE.test_command(self.row, self.policy, 'po2-python-ast-9999')
        self.assertIn('--network=none', command)
        self.assertIn('--entrypoint', command)

    def test_qf_lib_uses_legacy_compatible_python(self):
        row = dict(self.row, entry_id='ast-0039')
        self.assertEqual(MODULE.candidate_image(row, self.policy), self.policy['python_legacy_test_image'])

    def test_policy_file_is_valid_json(self):
        policy = json.loads((Path(__file__).resolve().parents[1] / 'config/sandbox_policy.json').read_text())
        self.assertTrue(policy['rootless_required'])


if __name__ == '__main__':
    unittest.main()
