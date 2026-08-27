"""Bias-aware recursive strategy research with a genuinely locked final test.

The module deliberately separates development evaluation from locked-test
evaluation.  A proposer can inspect train/validation diagnostics, but the
locked evaluator is not called until the frozen promotion policy passes.
Every attempted hypothesis can be written to an append-only, hash-chained
ledger so failed trials remain part of the research record.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Literal, Mapping, Sequence

from .evaluation import performance_metrics


MetricFamily = Literal["cross_sectional", "timing"]
SplitName = Literal["train", "validation", "locked_test"]


class FrozenDict(dict):
    """JSON-compatible mapping that cannot be changed after construction."""

    def _immutable(self, *args: object, **kwargs: object) -> None:
        raise TypeError("frozen hypothesis parameters cannot be mutated")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __deepcopy__(self, memo: dict[int, object]) -> "FrozenDict":
        return self


def _deep_freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return FrozenDict((str(key), _deep_freeze(item)) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ResearchBoundaries:
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str
    locked_test_start: str
    locked_test_end: str

    def __post_init__(self) -> None:
        values = (
            self.train_start,
            self.train_end,
            self.validation_start,
            self.validation_end,
            self.locked_test_start,
            self.locked_test_end,
        )
        try:
            parsed = [datetime.strptime(value, "%Y-%m-%d").date() for value in values]
        except ValueError as exc:
            raise ValueError("research boundaries must be ISO YYYY-MM-DD dates") from exc
        if not (parsed[0] <= parsed[1] < parsed[2] <= parsed[3] < parsed[4] <= parsed[5]):
            raise ValueError("train, validation, and locked-test windows must be chronological and disjoint")

    def contains(self, split: SplitName, day: str) -> bool:
        bounds = {
            "train": (self.train_start, self.train_end),
            "validation": (self.validation_start, self.validation_end),
            "locked_test": (self.locked_test_start, self.locked_test_end),
        }
        start, end = bounds[split]
        return start <= day <= end


@dataclass(frozen=True)
class HypothesisSpec:
    """A complete, immutable statement of an idea before results are seen."""

    name: str
    thesis: str
    metric_family: MetricFamily
    signal_definition: str
    universe: str
    rebalance_frequency: str
    data_snapshot_id: str
    code_version: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    expected_direction: Literal[1, -1] = 1

    def __post_init__(self) -> None:
        if self.metric_family not in ("cross_sectional", "timing"):
            raise ValueError("metric_family must be cross_sectional or timing")
        if self.expected_direction not in (1, -1):
            raise ValueError("expected_direction must be fixed at +1 or -1")
        if not all((self.name, self.thesis, self.signal_definition, self.universe,
                    self.data_snapshot_id, self.code_version)):
            raise ValueError("hypothesis fields cannot be blank")
        object.__setattr__(self, "parameters", _deep_freeze(self.parameters))
        # Fail at freeze time instead of later during ID generation.
        _canonical(asdict(self))

    @property
    def hypothesis_id(self) -> str:
        return f"hyp-{_digest(asdict(self))[:16]}"

    def frozen_document(self) -> dict[str, object]:
        body = asdict(self)
        return {"hypothesis_id": self.hypothesis_id, "spec_sha256": _digest(body), "spec": body}


def write_frozen_hypothesis(spec: HypothesisSpec, path: str | Path) -> None:
    """Create a hypothesis file once; refuse silent replacement or mutation."""
    destination = Path(path)
    payload = _canonical(spec.frozen_document()) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != payload:
            raise FileExistsError(f"frozen hypothesis differs from existing file: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")


def verify_frozen_hypothesis(path: str | Path) -> HypothesisSpec:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    spec = HypothesisSpec(**document["spec"])
    if document.get("hypothesis_id") != spec.hypothesis_id or document.get("spec_sha256") != _digest(asdict(spec)):
        raise ValueError("frozen hypothesis integrity check failed")
    return spec


@dataclass(frozen=True)
class EvaluationResult:
    split: SplitName
    metric_family: MetricFamily
    primary_metric_name: str
    primary_metric: float
    observations: int
    metrics: Mapping[str, float | int]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            result[order[position]] = average
        cursor = end
    return result


def _correlation(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean, right_mean = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_ss = sum((x - left_mean) ** 2 for x in left)
    right_ss = sum((y - right_mean) ** 2 for y in right)
    if left_ss == 0.0 or right_ss == 0.0:
        return None
    return numerator / math.sqrt(left_ss * right_ss)


def evaluate_cross_sectional(
    rows: Sequence[Mapping[str, object]], *, split: SplitName, expected_direction: int = 1,
    periods_per_year: int = 52,
) -> EvaluationResult:
    """Compute date-level Spearman RankIC and annualized ICIR.

    Required columns are ``date``, ``asset``, ``score`` and
    ``forward_return``.  IC observations are dates, not asset rows.
    """
    grouped: dict[str, list[tuple[str, float, float]]] = {}
    for row in rows:
        day = str(row["date"])
        score, realized = float(row["score"]), float(row["forward_return"])
        if not (math.isfinite(score) and math.isfinite(realized)):
            raise ValueError("scores and forward returns must be finite")
        grouped.setdefault(day, []).append((str(row["asset"]), score, realized))
    rank_ics: list[float] = []
    for day in sorted(grouped):
        observations = grouped[day]
        if len({asset for asset, _, _ in observations}) != len(observations):
            raise ValueError(f"duplicate asset on {day}")
        scores = [item[1] for item in observations]
        returns = [item[2] for item in observations]
        correlation = _correlation(_ranks(scores), _ranks(returns))
        if correlation is not None:
            rank_ics.append(correlation * expected_direction)
    if not rank_ics:
        raise ValueError("cross-sectional evaluation needs at least one non-degenerate date")
    mean_ic = statistics.fmean(rank_ics)
    standard_deviation = statistics.stdev(rank_ics) if len(rank_ics) > 1 else 0.0
    icir = mean_ic / standard_deviation * math.sqrt(periods_per_year) if standard_deviation else 0.0
    hit_rate = sum(value > 0.0 for value in rank_ics) / len(rank_ics)
    metrics: dict[str, float | int] = {
        "rank_ic_mean": mean_ic,
        "rank_ic_std": standard_deviation,
        "icir": icir,
        "positive_rank_ic_share": hit_rate,
        "rank_ic_dates": len(rank_ics),
    }
    return EvaluationResult(split, "cross_sectional", "icir", icir, len(rank_ics), metrics)


def evaluate_timing(
    rows: Sequence[Mapping[str, object]], *, split: SplitName, periods_per_year: int = 252,
) -> EvaluationResult:
    """Judge a timing strategy by its investable, net portfolio return path."""
    ordered = sorted(rows, key=lambda row: str(row["date"]))
    if len({str(row["date"]) for row in ordered}) != len(ordered):
        raise ValueError("timing evaluation has duplicate dates")
    values = [float(row["net_return"]) for row in ordered]
    result = performance_metrics(values, periods_per_year=periods_per_year)
    metrics = result.to_dict()
    return EvaluationResult(
        split, "timing", "sharpe_zero_rf", float(metrics["sharpe_zero_rf"]),
        len(values), metrics,
    )


def evaluate_owned_metric(
    spec: HypothesisSpec, rows: Sequence[Mapping[str, object]], *, split: SplitName,
    periods_per_year: int,
) -> EvaluationResult:
    if spec.metric_family == "cross_sectional":
        return evaluate_cross_sectional(
            rows, split=split, expected_direction=spec.expected_direction,
            periods_per_year=periods_per_year,
        )
    return evaluate_timing(rows, split=split, periods_per_year=periods_per_year)


@dataclass(frozen=True)
class PromotionPolicy:
    minimum_train_observations: int = 52
    minimum_validation_observations: int = 26
    minimum_locked_observations: int = 26
    minimum_train_primary: float = 0.25
    minimum_validation_primary: float = 0.0
    maximum_validation_degradation: float = 0.75
    minimum_timing_sharpe: float = 0.5
    maximum_timing_drawdown: float = -0.30
    minimum_rank_ic: float = 0.01

    def gates(self, train: EvaluationResult, validation: EvaluationResult) -> dict[str, bool]:
        if train.metric_family != validation.metric_family:
            raise ValueError("train and validation metric families differ")
        denominator = abs(train.primary_metric)
        degradation = (
            (train.primary_metric - validation.primary_metric) / denominator
            if denominator > 1e-12 else float("inf")
        )
        gates = {
            "train_observations": train.observations >= self.minimum_train_observations,
            "validation_observations": validation.observations >= self.minimum_validation_observations,
            "train_primary": train.primary_metric >= self.minimum_train_primary,
            "validation_primary": validation.primary_metric >= self.minimum_validation_primary,
            "validation_degradation": degradation <= self.maximum_validation_degradation,
        }
        if train.metric_family == "cross_sectional":
            gates["rank_ic_effect_size"] = (
                float(validation.metrics["rank_ic_mean"]) >= self.minimum_rank_ic
            )
        else:
            gates["timing_sharpe"] = (
                float(validation.metrics["sharpe_zero_rf"]) >= self.minimum_timing_sharpe
            )
            gates["timing_drawdown"] = (
                float(validation.metrics["max_drawdown"]) >= self.maximum_timing_drawdown
            )
        gates["all"] = all(gates.values())
        return gates

    def locked_gates(
        self, validation: EvaluationResult, locked_test: EvaluationResult
    ) -> dict[str, bool]:
        """Final out-of-sample gate; its result is never fed back into research."""
        if validation.metric_family != locked_test.metric_family:
            raise ValueError("validation and locked-test metric families differ")
        denominator = abs(validation.primary_metric)
        degradation = (
            (validation.primary_metric - locked_test.primary_metric) / denominator
            if denominator > 1e-12 else float("inf")
        )
        gates = {
            "locked_observations": locked_test.observations >= self.minimum_locked_observations,
            "locked_primary": locked_test.primary_metric >= self.minimum_validation_primary,
            "locked_degradation": degradation <= self.maximum_validation_degradation,
        }
        if locked_test.metric_family == "cross_sectional":
            gates["locked_rank_ic_effect_size"] = (
                float(locked_test.metrics["rank_ic_mean"]) >= self.minimum_rank_ic
            )
        else:
            gates["locked_timing_sharpe"] = (
                float(locked_test.metrics["sharpe_zero_rf"]) >= self.minimum_timing_sharpe
            )
            gates["locked_timing_drawdown"] = (
                float(locked_test.metrics["max_drawdown"]) >= self.maximum_timing_drawdown
            )
        gates["all"] = all(gates.values())
        return gates


@dataclass(frozen=True)
class DevelopmentFeedback:
    """The only result object exposed to a recursive hypothesis proposer."""

    trial_number: int
    hypothesis_id: str
    train: EvaluationResult
    validation: EvaluationResult
    gates: Mapping[str, bool]
    diagnosis: tuple[str, ...]


def diagnose_development(
    train: EvaluationResult, validation: EvaluationResult, gates: Mapping[str, bool]
) -> tuple[str, ...]:
    findings: list[str] = []
    if not gates.get("train_observations", False) or not gates.get("validation_observations", False):
        findings.append("insufficient_sample")
    if train.primary_metric > 0.0 and validation.primary_metric <= 0.0:
        findings.append("sign_reversal_out_of_sample")
    elif validation.primary_metric < train.primary_metric * 0.5:
        findings.append("large_validation_decay")
    for name, passed in gates.items():
        if name != "all" and not passed:
            findings.append(f"failed_gate:{name}")
    return tuple(dict.fromkeys(findings)) or ("development_gates_passed",)


class TrialLedger:
    """Append-only JSONL ledger with a SHA-256 hash chain."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def entries(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def verify(self) -> bool:
        previous = "GENESIS"
        seen: set[str] = set()
        for entry in self.entries():
            supplied_hash = str(entry.get("entry_hash", ""))
            body = {key: value for key, value in entry.items() if key != "entry_hash"}
            if body.get("previous_hash") != previous or _digest(body) != supplied_hash:
                return False
            trial_id = str(body.get("trial_id"))
            if trial_id in seen:
                return False
            seen.add(trial_id)
            previous = supplied_hash
        return True

    def append(self, record: Mapping[str, object]) -> dict[str, object]:
        existing = self.entries()
        if not self.verify():
            raise ValueError("trial ledger integrity check failed")
        trial_id = str(record["trial_id"])
        if any(str(entry["trial_id"]) == trial_id for entry in existing):
            raise ValueError(f"duplicate trial_id: {trial_id}")
        body = {
            **dict(record),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "previous_hash": str(existing[-1]["entry_hash"]) if existing else "GENESIS",
        }
        entry = {**body, "entry_hash": _digest(body)}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(entry) + "\n")
        return entry


DevelopmentEvaluator = Callable[[HypothesisSpec, Literal["train", "validation"]], Sequence[Mapping[str, object]]]
LockedEvaluator = Callable[[HypothesisSpec], Sequence[Mapping[str, object]]]
Proposer = Callable[[DevelopmentFeedback], HypothesisSpec | None]


class RecursiveResearchEngine:
    """Run recursive development trials and open the lockbox only on promotion."""

    def __init__(
        self, *, boundaries: ResearchBoundaries, policy: PromotionPolicy,
        ledger: TrialLedger, periods_per_year: int,
    ):
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")
        self.boundaries = boundaries
        self.policy = policy
        self.ledger = ledger
        self.periods_per_year = periods_per_year

    def _validate_dates(self, rows: Sequence[Mapping[str, object]], split: SplitName) -> None:
        if not rows:
            raise ValueError(f"{split} returned no rows")
        dates = [str(row["date"]) for row in rows]
        try:
            for day in dates:
                datetime.strptime(day, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError(f"{split} contains a non-ISO date") from exc
        outside = sorted({day for day in dates if not self.boundaries.contains(split, day)})
        if outside:
            raise ValueError(f"{split} contains dates outside its frozen boundary: {outside[:3]}")

    def run(
        self, *, initial: HypothesisSpec, development_evaluator: DevelopmentEvaluator,
        locked_evaluator: LockedEvaluator, proposer: Proposer, max_trials: int,
    ) -> list[dict[str, object]]:
        if max_trials < 1:
            raise ValueError("max_trials must be at least one")
        outcomes: list[dict[str, object]] = []
        spec: HypothesisSpec | None = initial
        if not self.ledger.verify():
            raise ValueError("trial ledger integrity check failed")
        seen_hypotheses = {
            str(entry.get("hypothesis", {}).get("hypothesis_id"))
            for entry in self.ledger.entries()
            if isinstance(entry.get("hypothesis"), dict)
        }
        for trial_number in range(1, max_trials + 1):
            if spec is None:
                break
            if spec.hypothesis_id in seen_hypotheses:
                raise ValueError("proposer repeated a previously tested frozen hypothesis")
            seen_hypotheses.add(spec.hypothesis_id)
            train_rows = development_evaluator(spec, "train")
            validation_rows = development_evaluator(spec, "validation")
            self._validate_dates(train_rows, "train")
            self._validate_dates(validation_rows, "validation")
            train = evaluate_owned_metric(
                spec, train_rows, split="train", periods_per_year=self.periods_per_year
            )
            validation = evaluate_owned_metric(
                spec, validation_rows, split="validation", periods_per_year=self.periods_per_year
            )
            gates = self.policy.gates(train, validation)
            diagnosis = diagnose_development(train, validation, gates)
            feedback = DevelopmentFeedback(
                trial_number, spec.hypothesis_id, train, validation, gates, diagnosis
            )

            # The proposer is deliberately called before any lockbox access and
            # receives an object with no locked-test field.
            next_spec = None if gates["all"] else proposer(feedback)
            locked: EvaluationResult | None = None
            locked_gates: dict[str, bool] | None = None
            if gates["all"]:
                locked_rows = locked_evaluator(spec)
                self._validate_dates(locked_rows, "locked_test")
                locked = evaluate_owned_metric(
                    spec, locked_rows, split="locked_test", periods_per_year=self.periods_per_year
                )
                locked_gates = self.policy.locked_gates(validation, locked)
            status = (
                "promoted_research_candidate" if locked_gates and locked_gates["all"]
                else "failed_locked_test" if locked is not None
                else "rejected_in_development"
            )
            trial_id = f"trial-{trial_number:04d}-{spec.hypothesis_id[4:]}"
            record: dict[str, object] = {
                "trial_id": trial_id,
                "hypothesis": spec.frozen_document(),
                "boundaries": asdict(self.boundaries),
                "metric_owner": spec.metric_family,
                "train": train.to_dict(),
                "validation": validation.to_dict(),
                "development_gates": dict(gates),
                "diagnosis": list(diagnosis),
                "status": status,
                "locked_test": locked.to_dict() if locked else None,
                "locked_test_gates": locked_gates,
            }
            self.ledger.append(record)
            outcomes.append(record)
            if locked is not None:
                break
            spec = next_spec
        return outcomes
