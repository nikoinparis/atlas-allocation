import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


FIXTURES = load("build_historical_fixtures")
REPLAYS = load("run_historical_replays")


class HistoricalFixtureTests(unittest.TestCase):
    def test_checked_in_fixture_matches_provenance(self):
        provenance = json.loads(FIXTURES.PROVENANCE.read_text(encoding="utf-8"))
        self.assertEqual(FIXTURES.sha256(FIXTURES.OUTPUT), provenance["fixture_sha256"])
        self.assertEqual(["SPY", "TLT", "GLD"], provenance["symbols"])
        self.assertGreater(provenance["rows"], 5_000)
        self.assertTrue(provenance["known_limits"])

    def test_builder_rejects_missing_selected_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prices.csv"
            metadata = root / "metadata.csv"
            output = root / "out.csv"
            provenance = root / "provenance.json"
            source.write_text("Date,SPY,TLT,GLD\n2006-01-03,100,,50\n", encoding="utf-8")
            metadata.write_text("ticker,pull_timestamp_utc,longName,currency,asset_class,description\n", encoding="utf-8")
            with patch.multiple(FIXTURES, SOURCE=source, METADATA_SOURCE=metadata, OUTPUT=output, PROVENANCE=provenance):
                with self.assertRaisesRegex(ValueError, "missing selected price"):
                    FIXTURES.build()


class HistoricalReplayRunnerTests(unittest.TestCase):
    def test_checked_in_replays_are_complete_but_do_not_claim_approval(self):
        output = ROOT / "evidence/historical_validation"
        summary = json.loads((output / "replays/summary.json").read_text(encoding="utf-8"))
        self.assertEqual(2, summary["completed"])
        self.assertEqual(2, summary["critical_pass"])
        report = (output / "report.md").read_text(encoding="utf-8")
        self.assertIn("Simple benchmark comparison | Fail", report)
        self.assertIn("Live or paper-trading approval | Not granted", report)

    def test_replay_command_is_offline_without_host_mount(self):
        row = {"entry_id": "ast-0022"}
        policy = {
            "python_test_image": "python:3.12", "python_legacy_test_image": "python:3.11",
            "limits": {"pids": 64, "cpus": 1},
        }
        command = REPLAYS.replay_command(row, policy, "po2-history-ast-0022")
        self.assertIn("--network=none", command)
        self.assertIn("--read-only", command)
        self.assertNotIn("/Users/", " ".join(command))

    def test_probe_sources_compile(self):
        compile(REPLAYS.probe_source("ast-0022"), "historical_bt.py", "exec")
        compile(REPLAYS.probe_source("ast-0047"), "historical_flashalpha.py", "exec")


if __name__ == "__main__":
    unittest.main()
