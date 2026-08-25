import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_candidate_breadth_gate_v1", ROOT / "scripts/run_candidate_breadth_gate_v1.py"
)
SUBJECT = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(SUBJECT)


class CandidateBreadthGateV1Tests(unittest.TestCase):
    def _write_csv(self, path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def test_runner_reports_independent_candidate_and_never_authorizes_performance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dates = [f"2025-{month:02d}-01" for month in range(1, 13)]
            self._write_csv(
                root / "candidate_returns.csv",
                ["realization_date", "net_return"],
                [{"realization_date": day, "net_return": (-1) ** index * 0.01} for index, day in enumerate(dates)],
            )
            self._write_csv(
                root / "peer_returns.csv",
                ["realization_date", "net_return"],
                [{"realization_date": day, "net_return": 0.002 * index} for index, day in enumerate(dates)],
            )
            for name, asset in (("candidate", "A"), ("peer", "B")):
                self._write_csv(
                    root / f"{name}_holdings.csv",
                    ["decision_date", "asset", "weight"],
                    [{"decision_date": day, "asset": asset, "weight": 1.0} for day in dates],
                )
            manifest = {
                "candidate": {
                    "name": "candidate",
                    "returns_csv": "candidate_returns.csv",
                    "holdings_csv": "candidate_holdings.csv",
                },
                "incumbents": [{
                    "name": "peer",
                    "returns_csv": "peer_returns.csv",
                    "holdings_csv": "peer_holdings.csv",
                }],
                "minimum_common_return_observations": 12,
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            result = SUBJECT.build(path)
            self.assertTrue(result["breadth_gate"]["breadth_gate_pass"])
            self.assertEqual(0.0, result["candidate_holdings_overlap_by_peer"]["peer"])
            self.assertFalse(result["strategy_edge_proven"])
            self.assertFalse(result["live_trading_enabled"])

    def test_runner_rejects_incomplete_holdings_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dates = ["2025-01-01", "2025-02-01"]
            for name in ("candidate", "peer"):
                self._write_csv(
                    root / f"{name}_returns.csv",
                    ["realization_date", "net_return"],
                    [{"realization_date": day, "net_return": index * 0.01} for index, day in enumerate(dates)],
                )
            self._write_csv(
                root / "candidate_holdings.csv",
                ["decision_date", "asset", "weight"],
                [{"decision_date": dates[0], "asset": "A", "weight": 1.0}],
            )
            self._write_csv(
                root / "peer_holdings.csv",
                ["decision_date", "asset", "weight"],
                [{"decision_date": dates[1], "asset": "B", "weight": 1.0}],
            )
            manifest = {
                "candidate": {"name": "candidate", "returns_csv": "candidate_returns.csv", "holdings_csv": "candidate_holdings.csv"},
                "incumbents": [{"name": "peer", "returns_csv": "peer_returns.csv", "holdings_csv": "peer_holdings.csv"}],
                "minimum_common_return_observations": 2,
            }
            path = root / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "no common holdings dates"):
                SUBJECT.build(path)


if __name__ == "__main__":
    unittest.main()
