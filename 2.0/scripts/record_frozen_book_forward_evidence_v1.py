#!/usr/bin/env python3
"""Record forward evidence for the three frozen-book ETF protocols.

Three protocols in `config/forward/` were frozen on 2026-08-12 with a first
eligible decision date of 2026-08-14 and have recorded nothing since, because no
recorder was ever written for them: `record_forward_portfolio_evidence.py` is
hardwired to `covariance_minimum_variance_v1`.

What these three can and cannot do has to be stated before any record is written.
Each pins a source bundle, `ggg_causal_v2_027530550388432a`, whose weekly prices
end at 2026-08-07. Their rules -- breadth confirmation, an annual grid
re-selection, a fixed 60/40 blend of two weight histories -- all need prices past
that date to produce a new book, and extending the bundle changes its hash and
therefore voids the pin. So no fresh strategy decision is available under any of
them. The only decision the frozen protocol still defines is the one it already
made: hold the last decided book, unchanged.

That is what this recorder writes, and every decision record says so in
`decision_basis`. A held book is a weaker object than a strategy: it tests the
names that were picked, not the rule that picks them, and it decays as the rule
it came from would have traded away from it. It is recorded because the
alternative is recording nothing at all.

Decisions are only written for weeks in which a data snapshot was actually
observed inside that week's Friday window, which is the same integrity test the
minimum-variance recorder applies. Records written after their window carry
`recorded_late` so the gap between observation and record is visible; the
snapshot, not the moment of writing, is the immutable object.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.data_vintage import SnapshotStore
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError,
    append_record,
    canonical_bytes,
    file_hash,
    read_and_verify_log,
)
from src.systematic_trader.weekly_data import prepare_weekly_adjusted_prices

STORE_ROOT = ROOT / "data/vintages"
UNIVERSE_PATH = ROOT / "config/free_etf_universe.json"
CASH = "cash::USD"
START = date(2005, 1, 7)

# The two protocols that name a weights hash but no path had their artifacts
# resolved by scanning every CSV under evidence/ for a matching digest on
# 2026-09-04. The resolved path is recorded here and its hash re-verified on
# every run, so a wrong or moved file fails closed rather than silently binding
# to something else.
PROTOCOLS = {
    "breadth_confirmed_trend_return_ceiling_v3": {
        "artifact": "evidence/breadth_ceiling_adversarial_validation_batch_65/current_holdings.csv",
        "artifact_kind": "holdings",
        "artifact_resolved_by": "sha256 scan of evidence/**/*.csv on 2026-09-04",
    },
    "past_only_consensus_selector_return_v1": {
        "artifact": "evidence/exhaustive_return_first_discovery_batch_66/"
                    "retrospective_ceiling_adversarial/past_only_selector_weights.csv",
        "artifact_kind": "history",
        "artifact_resolved_by": "sha256 scan of evidence/**/*.csv on 2026-09-04",
    },
    "return_first_60_40_blend_v1": {
        "artifact": "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv",
        "artifact_kind": "history",
        "artifact_resolved_by": "named directly by the protocol",
    },
}


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ForwardEvidenceError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def window_start(day: str) -> datetime:
    parsed = date.fromisoformat(day)
    if parsed.weekday() != 4:
        raise ForwardEvidenceError("forward evidence dates must be Fridays")
    return datetime.combine(parsed, time(21, 0), tzinfo=timezone.utc)


def observed_in_window(observed_at_utc: str, day: str) -> bool:
    start = window_start(day)
    return start <= parse_utc(observed_at_utc) < start + timedelta(days=7)


def read_frozen_book(path: Path, kind: str) -> dict[str, float]:
    """The last book the frozen artifact decided, as positive weights summing to one."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    header, body = rows[0], [r for r in rows[1:] if any(cell.strip() for cell in r)]
    if kind == "holdings":
        book = {r[0]: float(r[1]) for r in body}
    else:
        last = body[-1]
        book = {symbol: float(value) for symbol, value in zip(header[1:], last[1:])}
    book = {asset: weight for asset, weight in book.items() if weight > 1e-12}
    total = sum(book.values())
    if not book or abs(total - 1.0) > 1e-6:
        raise ForwardEvidenceError(f"frozen book from {path.name} does not sum to one: {total}")
    return dict(sorted(book.items()))


def weekly_simple_returns(snapshot_id: str, assets: list[str]) -> dict[str, dict[str, float]]:
    store = SnapshotStore(STORE_ROOT)
    manifest = next((m for m in store.manifests() if m["snapshot_id"] == snapshot_id), None)
    if manifest is None:
        raise ForwardEvidenceError(f"unknown snapshot: {snapshot_id}")
    store.verify(snapshot_id)
    universe = sorted(json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, preparation = prepare_weekly_adjusted_prices(
        STORE_ROOT / snapshot_id / "payload" / "prices.csv",
        observed_at_date=parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=START,
        expected_symbols=universe,
    )
    returns: dict[str, dict[str, float]] = {}
    for index in range(1, len(dates)):
        day, previous = dates[index], dates[index - 1]
        row = {}
        for asset in assets:
            if asset == CASH:
                row[asset] = 0.0
                continue
            current, prior = prices[day].get(asset), prices[previous].get(asset)
            if current is not None and prior is not None and prior > 0.0:
                row[asset] = math.expm1(math.log(current / prior))
        returns[day] = row
    return {"dates": dates, "returns": returns, "preparation": preparation, "manifest": manifest}


def fridays_from(first: str, through: date) -> list[str]:
    day = date.fromisoformat(first)
    out = []
    while day <= through:
        out.append(day.isoformat())
        day += timedelta(days=7)
    return out


def run(protocol_id: str, *, now: datetime) -> dict[str, object]:
    spec = PROTOCOLS[protocol_id]
    config = json.loads((ROOT / f"config/forward/{protocol_id}.json").read_text(encoding="utf-8"))
    if config.get("live_trading_enabled"):
        raise ForwardEvidenceError("forward research protocol cannot enable execution")

    artifact = ROOT / str(spec["artifact"])
    digest = file_hash(artifact)
    if digest != config["weights_artifact_sha256"]:
        raise ForwardEvidenceError(f"{protocol_id}: weights artifact hash does not match the protocol")
    book = read_frozen_book(artifact, str(spec["artifact_kind"]))

    output = ROOT / f"evidence/forward_{protocol_id}"
    output.mkdir(parents=True, exist_ok=True)
    decisions_path, observations_path = output / "decisions.jsonl", output / "observations.jsonl"
    first_decision = str(config["first_eligible_decision_date"])

    anchor = {
        "schema_version": 1,
        "protocol_id": config["protocol_id"],
        "forward_protocol_sha256": file_hash(ROOT / f"config/forward/{protocol_id}.json"),
        "weights_artifact": str(spec["artifact"]),
        "weights_artifact_sha256": digest,
        "weights_artifact_resolved_by": spec["artifact_resolved_by"],
        "frozen_book": book,
        "first_decision_prior_weights": {CASH: 1.0},
        "source_bundle": config["source_bundle"],
        "source_bundle_data_through": "2026-08-07",
        "decision_basis": "held_frozen_book",
        "limitation": (
            "The pinned source bundle ends 2026-08-07, so no fresh strategy decision can be "
            "produced without changing its hash and voiding the pin. Every forward decision "
            "under this protocol holds the last decided book unchanged, which tests the book "
            "rather than the rule and decays as a test of the rule."
        ),
        "execution_enabled": False,
    }
    anchor_path = output / "anchor.json"
    if anchor_path.exists():
        if json.loads(anchor_path.read_text(encoding="utf-8")) != anchor:
            raise ForwardEvidenceError(f"{protocol_id}: forward anchor changed")
    else:
        anchor_path.write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifests = sorted(SnapshotStore(STORE_ROOT).manifests(), key=lambda m: str(m["observed_at_utc"]))
    assets = sorted(set(book) | {CASH})
    cache: dict[str, dict[str, object]] = {}
    added = {"decisions": 0, "observations": 0}

    for day in fridays_from(first_decision, now.date()):
        eligible = [m for m in manifests if observed_in_window(str(m["observed_at_utc"]), day)]
        if not eligible:
            continue
        chosen = eligible[0]
        snapshot_id = str(chosen["snapshot_id"])
        state = cache.setdefault(snapshot_id, weekly_simple_returns(snapshot_id, assets))
        if day not in state["dates"]:
            raise ForwardEvidenceError(f"snapshot {snapshot_id} lacks completed decision week {day}")

        existing = read_and_verify_log(
            decisions_path, date_field="decision_date", first_eligible_date=first_decision
        )
        if not any(str(r["decision_date"]) == day for r in existing):
            prior = dict(existing[-1]["target_weights"]) if existing else dict(anchor["first_decision_prior_weights"])
            turnover = 0.5 * sum(
                abs(book.get(a, 0.0) - prior.get(a, 0.0)) for a in set(prior) | set(book)
            )
            payload = {
                "record_type": "frozen_book_forward_decision_v1",
                "protocol_id": config["protocol_id"],
                "decision_date": day,
                "eligible_realization_date": (date.fromisoformat(day) + timedelta(days=7)).isoformat(),
                "decision_basis": "held_frozen_book",
                "decision_snapshot_id": snapshot_id,
                "decision_snapshot_observed_at_utc": str(chosen["observed_at_utc"]),
                "source_data_through": day,
                "target_weights": book,
                "target_weights_sha256": hash_value(book),
                "turnover_from_prior_saved_target": turnover,
                "modeled_cost": 0.0,
                "modeled_cost_note": "the protocol states no forward cost; turnover is recorded so a cost can be applied later",
                "recorded_at_utc": now.isoformat(),
                "recorded_late": not observed_in_window(now.isoformat(), day),
                "forward_protocol_sha256": anchor["forward_protocol_sha256"],
                "execution_enabled": False,
            }
            append_record(decisions_path, payload, date_field="decision_date",
                          first_eligible_date=first_decision)
            added["decisions"] += 1

    for decision in read_and_verify_log(
        decisions_path, date_field="decision_date", first_eligible_date=first_decision
    ):
        realization = str(decision["eligible_realization_date"])
        observed = read_and_verify_log(
            observations_path, date_field="realization_date",
            first_eligible_date=str(config["first_eligible_realization_date"]),
        )
        if any(str(r["realization_date"]) == realization for r in observed):
            continue
        eligible = [m for m in manifests if observed_in_window(str(m["observed_at_utc"]), realization)]
        if not eligible:
            continue
        chosen = eligible[0]
        snapshot_id = str(chosen["snapshot_id"])
        state = cache.setdefault(snapshot_id, weekly_simple_returns(snapshot_id, assets))
        if realization not in state["returns"]:
            continue
        row = state["returns"][realization]
        weights = dict(decision["target_weights"])
        missing = [a for a in weights if a not in row]
        if missing:
            raise ForwardEvidenceError(f"{protocol_id}: {realization} lacks returns for {missing}")
        gross = sum(weights[a] * row[a] for a in weights)
        payload = {
            "record_type": "frozen_book_forward_observation_v1",
            "protocol_id": config["protocol_id"],
            "decision_date": str(decision["decision_date"]),
            "realization_date": realization,
            "decision_record_hash": str(decision["record_hash"]),
            "realization_snapshot_id": snapshot_id,
            "realization_snapshot_observed_at_utc": str(chosen["observed_at_utc"]),
            "asset_returns": {a: row[a] for a in sorted(weights)},
            "gross_return": gross,
            "cost": 0.0,
            "net_return": gross,
            "recorded_at_utc": now.isoformat(),
            "recorded_late": not observed_in_window(now.isoformat(), realization),
            "forward_protocol_sha256": anchor["forward_protocol_sha256"],
            "execution_enabled": False,
        }
        append_record(observations_path, payload, date_field="realization_date",
                      first_eligible_date=str(config["first_eligible_realization_date"]))
        added["observations"] += 1

    decisions = read_and_verify_log(decisions_path, date_field="decision_date",
                                    first_eligible_date=first_decision)
    observations = read_and_verify_log(
        observations_path, date_field="realization_date",
        first_eligible_date=str(config["first_eligible_realization_date"]),
    )
    values = [float(o["net_return"]) for o in observations]
    required = int(config["required_weeks"])
    status = {
        "protocol_id": config["protocol_id"],
        "candidate": config["candidate"],
        "decision_basis": "held_frozen_book",
        "anchor_sha256": file_hash(anchor_path),
        "decision_log_sha256": file_hash(decisions_path),
        "observation_log_sha256": file_hash(observations_path),
        "decision_log_head": decisions[-1]["record_hash"] if decisions else None,
        "observation_log_head": observations[-1]["record_hash"] if observations else None,
        "saved_decisions": len(decisions),
        "observed_weeks": len(observations),
        "required_weeks": required,
        "remaining_weeks": max(0, required - len(observations)),
        "latest_decision_date": str(decisions[-1]["decision_date"]) if decisions else None,
        "latest_realization_date": str(observations[-1]["realization_date"]) if observations else None,
        "records_written_after_their_window": sum(
            1 for r in list(decisions) + list(observations) if r.get("recorded_late")
        ),
        "performance_metrics": performance_metrics(values).to_dict() if values else {"observations": 0},
        "source_bundle_data_through": "2026-08-07",
        "limitation": anchor["limitation"],
        "generated_at_utc": now.isoformat(),
        "clock_complete": len(observations) >= required,
        "approved_for_live_trading": False,
        "promotion_authorized": False,
        "execution_enabled": False,
        "live_trading_enabled": False,
    }
    (output / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "report.md").write_text(
        f"# Held-Frozen-Book Forward Evidence\n\n"
        f"Protocol: `{config['protocol_id']}`\n\n"
        f"- Decision basis: **held frozen book** (the pinned source bundle ends 2026-08-07).\n"
        f"- Saved forward decisions: **{len(decisions)}**.\n"
        f"- Realized weeks: **{len(observations)}/{required}**.\n"
        f"- Latest decision: **{status['latest_decision_date'] or 'none'}**.\n"
        f"- Latest realization: **{status['latest_realization_date'] or 'none'}**.\n"
        f"- Records written after their window: **{status['records_written_after_their_window']}**.\n"
        f"- Execution enabled: **no**.\n\n"
        f"{anchor['limitation']}\n\n"
        f"Decision and observation logs are independently hash-chained. Every record is bound to a "
        f"snapshot that was observed inside its own Friday window; a week with no such snapshot is "
        f"skipped rather than filled from a later vintage.\n",
        encoding="utf-8",
    )
    return {"protocol_id": protocol_id, "added": added, "status": status}


def hash_value(value: object) -> str:
    import hashlib
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", action="append", choices=sorted(PROTOCOLS), default=None)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    results = []
    for protocol_id in args.protocol or sorted(PROTOCOLS):
        try:
            results.append(run(protocol_id, now=now))
        except ForwardEvidenceError as error:
            print(json.dumps({"protocol_id": protocol_id, "status": "rejected",
                              "reason": str(error)}, indent=2), file=sys.stderr)
            return 2
    for result in results:
        s = result["status"]
        print(f"{result['protocol_id']:<46} +{result['added']['decisions']}d +{result['added']['observations']}o "
              f"-> {s['observed_weeks']}/{s['required_weeks']} weeks, "
              f"total {s['performance_metrics'].get('total_return', 0.0):+.4%}, "
              f"late records {s['records_written_after_their_window']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
