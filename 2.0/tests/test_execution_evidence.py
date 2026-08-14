import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/batch_01_backtest_execution'


class ExecutionEvidenceTests(unittest.TestCase):
    def test_all_ready_sources_passed_pinned_acquisition(self):
        summary = json.loads((EVIDENCE / 'source_smoke/summary.json').read_text())
        self.assertEqual(summary['total'], 18)
        self.assertEqual(summary['passed'], 18)
        self.assertEqual(summary['failed'], 0)
        self.assertFalse(summary['repository_code_executed'])

    def test_python_gate_never_uses_host_mounts_or_test_network(self):
        summary = json.loads((EVIDENCE / 'python_execution/summary.json').read_text())
        self.assertEqual(summary['total'], 9)
        self.assertFalse(summary['host_mounts'])
        self.assertTrue(summary['network_disabled_during_tests'])

    def test_each_python_result_is_pinned_and_records_isolation(self):
        results = sorted((EVIDENCE / 'python_execution').glob('ast-*.json'))
        self.assertEqual(len(results), 9)
        for path in results:
            result = json.loads(path.read_text())
            self.assertRegex(result['head_commit'], r'^[0-9a-f]{40}$')
            self.assertFalse(result['host_mounts'])

    def test_behavioral_probes_capture_known_critical_boundaries(self):
        probes = EVIDENCE / 'behavioral_probes'
        bt = json.loads((probes / 'ast-0022.json').read_text())
        flashalpha = json.loads((probes / 'ast-0047.json').read_text())
        self.assertFalse(bt['probe']['critical_pass'])
        self.assertFalse(flashalpha['probe']['critical_pass'])
        self.assertTrue(bt['network_disabled_during_probe'])
        self.assertTrue(flashalpha['network_disabled_during_probe'])
        bt_checks = {item['name']: item for item in bt['probe']['checks']}
        flash_checks = {item['name']: item for item in flashalpha['probe']['checks']}
        self.assertFalse(bt_checks['current_close_signal_cannot_execute_same_bar']['passed'])
        self.assertFalse(flash_checks['nonfinite_quote_is_rejected']['passed'])


if __name__ == '__main__':
    unittest.main()
