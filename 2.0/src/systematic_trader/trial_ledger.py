"""Count the trials, so multiple-testing corrections stop being guesses.

Step 199 could not state N. It reported a sensitivity grid instead, which is the
honest fallback but not a substitute for knowing. Every significance claim this
project makes from here depends on a number nobody has been recording.

The ledger is append-only and hash-chained for the same reason the forward
evidence store is: a trial count that can be quietly revised downward after a
disappointing result is not a trial count. Registration happens at evaluation
time, and the deflated Sharpe gate reads from it rather than accepting a number
supplied by the caller.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

GENESIS = "0" * 64


def _digest(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Trial:
    """One configuration evaluated against one dataset for one objective."""

    family: str
    experiment: str
    variant: str
    objective: str
    dataset: str
    evaluated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    outcome: str | None = None
    metric: float | None = None

    def body(self) -> dict:
        return {
            "family": self.family,
            "experiment": self.experiment,
            "variant": self.variant,
            "objective": self.objective,
            "dataset": self.dataset,
            "evaluated_at_utc": self.evaluated_at_utc,
            "outcome": self.outcome,
            "metric": self.metric,
        }


class TrialLedger:
    """Append-only, hash-chained record of every configuration evaluated."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self) -> str:
        previous = GENESIS
        for record in self.read():
            previous = record["record_hash"]
        return previous

    def append(self, trials: Iterable[Trial]) -> int:
        previous = self._last_hash()
        written = 0
        with self.path.open("a") as handle:
            for trial in trials:
                body = trial.body()
                body["previous_hash"] = previous
                record_hash = _digest(body)
                body["record_hash"] = record_hash
                handle.write(json.dumps(body, sort_keys=True) + "\n")
                previous = record_hash
                written += 1
        return written

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open() as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def verify(self) -> dict:
        """A broken chain means the count cannot be trusted; say so loudly."""
        previous = GENESIS
        for index, record in enumerate(self.read()):
            body = {k: v for k, v in record.items() if k != "record_hash"}
            if body.get("previous_hash") != previous:
                return {"valid": False, "broken_at": index, "reason": "previous_hash mismatch"}
            if _digest(body) != record["record_hash"]:
                return {"valid": False, "broken_at": index, "reason": "record_hash mismatch"}
            previous = record["record_hash"]
        return {"valid": True, "records": len(self.read())}

    def count(self, family: str | None = None, objective: str | None = None) -> int:
        records = self.read()
        if family is not None:
            records = [r for r in records if r["family"] == family]
        if objective is not None:
            records = [r for r in records if r["objective"] == objective]
        return len(records)

    def families(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.read():
            counts[record["family"]] = counts.get(record["family"], 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


EULER_MASCHERONI = 0.5772156649015329


def expected_maximum_sharpe(trials: int, sharpe_variance: float) -> float:
    """E[max Sharpe] over `trials` independent zero-skill draws."""
    if trials < 2:
        trials = 2
    from scipy import stats  # local import keeps the ledger importable without scipy

    gamma = EULER_MASCHERONI
    return math.sqrt(sharpe_variance) * (
        (1 - gamma) * stats.norm.ppf(1 - 1 / trials)
        + gamma * stats.norm.ppf(1 - 1 / (trials * math.e))
    )


def deflated_sharpe(returns, trials: int, periods: int = 52) -> dict:
    """Bailey and Lopez de Prado (2014). `returns` is a per-period return series."""
    from scipy import stats

    series = [float(x) for x in returns if x == x]
    n = len(series)
    if n < 20:
        raise ValueError("deflated Sharpe needs at least 20 observations")
    mean = sum(series) / n
    variance = sum((x - mean) ** 2 for x in series) / (n - 1)
    sd = math.sqrt(variance)
    # An exactly constant series still produces a tiny nonzero sd in floating
    # point, and a Sharpe computed from it explodes rather than erroring. Refuse
    # anything whose dispersion is negligible against its own scale.
    scale = max(abs(mean), max(abs(x) for x in series), 1e-12)
    if sd <= scale * 1e-9:
        raise ValueError("return series has no usable dispersion")
    sharpe = mean / sd
    skew = float(stats.skew(series))
    kurtosis = float(stats.kurtosis(series, fisher=False))
    adjustment = 1 - skew * sharpe + (kurtosis - 1) / 4 * sharpe**2
    sharpe_variance = adjustment / (n - 1)
    threshold = expected_maximum_sharpe(trials, sharpe_variance)
    z = (sharpe - threshold) * math.sqrt(n - 1) / math.sqrt(adjustment)
    return {
        "observations": n,
        "trials": trials,
        "annualised_sharpe": sharpe * math.sqrt(periods),
        "annualised_null_threshold": threshold * math.sqrt(periods),
        "deflated_sharpe_ratio": float(stats.norm.cdf(z)),
    }


def promotion_gate(returns, ledger: TrialLedger, family: str, periods: int = 52,
                   threshold: float = 0.95) -> dict:
    """Fail closed: an unregistered family has an unknown N, not an N of one."""
    trials = ledger.count(family=family)
    if trials == 0:
        return {
            "passes": False,
            "reason": "no trials registered for this family; register them before claiming significance",
            "family": family,
            "trials": 0,
        }
    verification = ledger.verify()
    if not verification["valid"]:
        return {"passes": False, "reason": "trial ledger chain is broken", "verification": verification}
    result = deflated_sharpe(returns, trials, periods)
    result.update({
        "family": family,
        "threshold": threshold,
        "passes": bool(result["deflated_sharpe_ratio"] >= threshold),
    })
    return result
