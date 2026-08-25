import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from src.systematic_trader.recursive_research import (
    HypothesisSpec,
    PromotionPolicy,
    RecursiveResearchEngine,
    ResearchBoundaries,
    TrialLedger,
    evaluate_cross_sectional,
    evaluate_timing,
    verify_frozen_hypothesis,
    write_frozen_hypothesis,
)


def timing_spec(**parameters):
    return HypothesisSpec(
        name="opening candle", thesis="opening direction persists", metric_family="timing",
        signal_definition="first bar versus EMA", universe="SPY", rebalance_frequency="daily",
        data_snapshot_id="snap-1", code_version="abc123", parameters=parameters,
    )


class RecursiveResearchTests(unittest.TestCase):
    def setUp(self):
        self.boundaries = ResearchBoundaries(
            "2020-01-01", "2020-12-31", "2021-01-01", "2021-12-31",
            "2022-01-01", "2022-12-31",
        )

    def test_boundaries_reject_overlap(self):
        with self.assertRaises(ValueError):
            ResearchBoundaries("2020-01-01", "2021-01-01", "2021-01-01", "2022-01-01", "2023-01-01", "2024-01-01")

    def test_hypothesis_is_content_addressed_and_frozen_file_detects_tampering(self):
        spec = timing_spec(ema=12)
        self.assertNotEqual(spec.hypothesis_id, replace(spec, parameters={"ema": 13}).hypothesis_id)
        with self.assertRaises(TypeError):
            spec.parameters["ema"] = 99
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hypothesis.json"
            write_frozen_hypothesis(spec, path)
            self.assertEqual(spec, verify_frozen_hypothesis(path))
            document = json.loads(path.read_text())
            document["spec"]["parameters"]["ema"] = 99
            path.write_text(json.dumps(document))
            with self.assertRaises(ValueError):
                verify_frozen_hypothesis(path)

    def test_metric_ownership(self):
        cross = []
        for date in ("2020-01-03", "2020-01-10"):
            for asset, value in (("A", 1.0), ("B", 2.0), ("C", 3.0)):
                cross.append({"date": date, "asset": asset, "score": value, "forward_return": value / 100})
        ic = evaluate_cross_sectional(cross, split="train")
        self.assertEqual("icir", ic.primary_metric_name)
        self.assertEqual(1.0, ic.metrics["rank_ic_mean"])
        timing = evaluate_timing([
            {"date": f"2020-01-{day:02d}", "net_return": 0.01 if day % 2 else -0.002}
            for day in range(1, 11)
        ], split="train")
        self.assertEqual("sharpe_zero_rf", timing.primary_metric_name)
        self.assertIn("max_drawdown", timing.metrics)

    def test_lockbox_is_not_called_for_failed_trials_and_feedback_has_no_lockbox(self):
        with tempfile.TemporaryDirectory() as directory:
            locked_calls = []
            feedback_seen = []
            engine = RecursiveResearchEngine(
                boundaries=self.boundaries,
                policy=PromotionPolicy(minimum_train_observations=4, minimum_validation_observations=4),
                ledger=TrialLedger(Path(directory) / "ledger.jsonl"), periods_per_year=252,
            )

            def development(spec, split):
                year = 2020 if split == "train" else 2021
                return [{"date": f"{year}-01-{day:02d}", "net_return": -0.01 if day % 2 else 0.001} for day in range(1, 7)]

            def locked(spec):
                locked_calls.append(spec.hypothesis_id)
                return [{"date": "2022-01-03", "net_return": 0.01}]

            def proposer(feedback):
                feedback_seen.append(feedback)
                self.assertFalse(hasattr(feedback, "locked_test"))
                return None

            outcomes = engine.run(
                initial=timing_spec(ema=12), development_evaluator=development,
                locked_evaluator=locked, proposer=proposer, max_trials=3,
            )
            self.assertEqual([], locked_calls)
            self.assertEqual(1, len(feedback_seen))
            self.assertIsNone(outcomes[0]["locked_test"])

    def test_recursive_failure_then_promotion_opens_lockbox_once(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = TrialLedger(Path(directory) / "ledger.jsonl")
            engine = RecursiveResearchEngine(
                boundaries=self.boundaries,
                policy=PromotionPolicy(
                    minimum_train_observations=6, minimum_validation_observations=6,
                    minimum_locked_observations=6,
                    minimum_train_primary=0.1, minimum_validation_primary=0.1,
                    maximum_validation_degradation=1.0, minimum_timing_sharpe=0.1,
                    maximum_timing_drawdown=-0.50,
                ),
                ledger=ledger, periods_per_year=252,
            )
            locked_calls = []

            def rows(year, good):
                return [
                    {"date": f"{year}-01-{day:02d}", "net_return": (0.01 if day % 3 else -0.002) if good else (-0.01 if day % 3 else 0.002)}
                    for day in range(1, 13)
                ]

            def development(spec, split):
                return rows(2020 if split == "train" else 2021, bool(spec.parameters["good"]))

            def locked(spec):
                locked_calls.append(spec.hypothesis_id)
                return rows(2022, True)

            def proposer(feedback):
                self.assertIn("failed_gate:validation_primary", feedback.diagnosis)
                return timing_spec(good=True)

            outcomes = engine.run(
                initial=timing_spec(good=False), development_evaluator=development,
                locked_evaluator=locked, proposer=proposer, max_trials=3,
            )
            self.assertEqual(2, len(outcomes))
            self.assertEqual("rejected_in_development", outcomes[0]["status"])
            self.assertEqual("promoted_research_candidate", outcomes[1]["status"])
            self.assertTrue(outcomes[1]["locked_test_gates"]["all"])
            self.assertEqual(1, len(locked_calls))
            self.assertTrue(ledger.verify())

    def test_ledger_detects_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = TrialLedger(path)
            ledger.append({"trial_id": "trial-1", "status": "failed"})
            self.assertTrue(ledger.verify())
            text = path.read_text().replace("failed", "passed")
            path.write_text(text)
            self.assertFalse(ledger.verify())


if __name__ == "__main__":
    unittest.main()
