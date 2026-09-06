#!/usr/bin/env python3
"""Record forward evidence for the equal-weight benchmark, week by week.

A companion to `sec_residual_controlled_sleeve_forward_v1`, and deliberately not
part of it. That protocol is frozen and this touches none of it; it reads only
its sleeve weights and cadence so the two series stay comparable.

The reason it exists is that a forward return series on its own settles very
little. Step 222 found the composite's 80% control leg losing to an equal
weighting of its own universe, Step 231 found the composite's edge over a blended
equal-weight benchmark to be a coin flip at P(>0)=0.533, and Steps 230 and 232
established that neither leg can be validated out of sample from free data. Fifty
two weeks of an unbenchmarked number would leave all of that exactly where it is.

The benchmark makes no selection. It holds every tradable member of the governing
quarterly roster at equal weight, rebalances when the roster does, and pays the
same 50bps on turnover. Decisions and observations are hash-chained on the same
weekly Friday cadence, and a missed window is left missed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError, append_record, canonical_bytes, file_hash, read_and_verify_log,
)

PROTOCOL = ROOT / "config/forward/equal_weight_benchmark_v1.json"
OUTPUT = ROOT / "evidence/forward_equal_weight_benchmark_v1"
NARROW_MEMBERSHIP = ROOT / "evidence/full_history_price_panel_v1/classified_membership.csv"
BROAD_MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_full_v1/recent_membership_readiness.csv"
NARROW_PRICES = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
BROAD_PRICES = ROOT / "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz"
CASH = "cash::USD"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def window_start(day: str) -> datetime:
    parsed = date.fromisoformat(day)
    if parsed.weekday() != 4:
        raise ForwardEvidenceError("forward evidence dates must be Fridays")
    return datetime.combine(parsed, time(21, 0), tzinfo=timezone.utc)


def roster(path: Path, decision: pd.Timestamp) -> list[str]:
    """Tradable members of the latest quarterly roster at or before `decision`."""
    frame = pd.read_csv(path, dtype={"cik10": str})
    frame["decision_at"] = pd.to_datetime(frame.decision_at, utc=True, errors="coerce").dt.tz_localize(None)
    flag = next((c for c in ("tradable_member", "validated_price_available", "execution_price_available")
                 if c in frame.columns), None)
    if flag is None:
        raise ForwardEvidenceError(f"no tradability column in {path.name}")
    quarters = sorted(frame.decision_at.dropna().unique())
    eligible = [q for q in quarters if q <= decision]
    if not eligible:
        raise ForwardEvidenceError(f"no quarterly roster at or before {decision.date()}")
    block = frame[(frame.decision_at == max(eligible)) & frame[flag].astype(bool)]
    return sorted(set(block.cik10))


def realized(prices: Path, members: list[str], week: pd.Timestamp) -> tuple[float, int]:
    frame = pd.read_csv(prices, index_col=0)
    frame.index = pd.to_datetime(frame.index)
    if week not in frame.index:
        raise ForwardEvidenceError(f"{prices.name} has no week ending {week.date()}")
    position = frame.index.get_loc(week)
    if position == 0:
        raise ForwardEvidenceError("no prior week to compute a return from")
    held = [c for c in members if c in frame.columns]
    change = frame.iloc[position][held] / frame.iloc[position - 1][held] - 1.0
    change = change.dropna()
    return (float(change.mean()) if len(change) else 0.0), int(len(change))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True, help="the Friday being recorded")
    parser.add_argument("--realize", action="store_true",
                        help="also record the realization for the decision one week earlier")
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("benchmark protocol cannot enable execution")
    residual = json.loads((ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json").read_text())
    narrow_weight = float(residual["control_weight"])
    broad_weight = float(residual["residual_sleeve_weight"])
    first = str(protocol["cadence"]["first_eligible_decision_date"])

    now = datetime.now(timezone.utc)
    decision = pd.Timestamp(args.decision_date)
    day = str(decision.date())
    window_start(day)
    if date.fromisoformat(day) < date.fromisoformat(first):
        raise ForwardEvidenceError("decision predates the frozen boundary")
    if now < window_start(day):
        raise ForwardEvidenceError(f"the {day} window opens at 21:00 UTC that day; it is {now.isoformat()}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    decisions_path, observations_path = OUTPUT / "decisions.jsonl", OUTPUT / "observations.jsonl"

    narrow, broad = roster(NARROW_MEMBERSHIP, decision), roster(BROAD_MEMBERSHIP, decision)
    existing = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    added = {"decisions": 0, "observations": 0}
    if not any(str(r["decision_date"]) == day for r in existing):
        payload = {
            "record_type": "equal_weight_benchmark_decision_v1",
            "protocol_version": protocol["protocol_version"],
            "decision_date": day,
            "eligible_realization_date": str((decision + pd.Timedelta(days=7)).date()),
            "narrow_members": len(narrow), "broad_members": len(broad),
            "narrow_roster_sha256": sha256_value(narrow), "broad_roster_sha256": sha256_value(broad),
            "sleeve_weights": {"narrow": narrow_weight, "broad": broad_weight},
            "cost_bps": float(protocol["construction"]["cost_bps_per_unit_turnover"]),
            "selection": "none; every tradable member held at equal weight",
            "recorded_at_utc": now.isoformat(),
            "forward_protocol_sha256": file_hash(PROTOCOL),
            "execution_enabled": False,
        }
        append_record(decisions_path, payload, date_field="decision_date", first_eligible_date=first)
        added["decisions"] += 1

    if args.realize:
        prior = decision - pd.Timedelta(days=7)
        saved = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
        match = next((r for r in saved if str(r["decision_date"]) == str(prior.date())), None)
        if match is None:
            raise ForwardEvidenceError(f"no saved decision for {prior.date()} to realize")
        observed = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)
        if not any(str(r["realization_date"]) == day for r in observed):
            n_return, n_priced = realized(NARROW_PRICES, roster(NARROW_MEMBERSHIP, prior), decision)
            b_return, b_priced = realized(BROAD_PRICES, roster(BROAD_MEMBERSHIP, prior), decision)
            payload = {
                "record_type": "equal_weight_benchmark_observation_v1",
                "protocol_version": protocol["protocol_version"],
                "decision_date": str(prior.date()), "realization_date": day,
                "decision_record_hash": str(match["record_hash"]),
                "equal_weight_narrow_return": n_return, "narrow_priced": n_priced,
                "equal_weight_broad_return": b_return, "broad_priced": b_priced,
                "blended_benchmark_return": narrow_weight * n_return + broad_weight * b_return,
                "recorded_at_utc": now.isoformat(),
                "forward_protocol_sha256": file_hash(PROTOCOL),
                "execution_enabled": False,
            }
            append_record(observations_path, payload, date_field="realization_date", first_eligible_date=first)
            added["observations"] += 1

    decisions = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    observations = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)
    values = [float(o["blended_benchmark_return"]) for o in observations]
    status = {
        "protocol_version": protocol["protocol_version"],
        "is_a_benchmark_not_a_strategy": True,
        "saved_decisions": len(decisions), "observed_weeks": len(observations),
        "latest_decision_date": str(decisions[-1]["decision_date"]) if decisions else None,
        "latest_realization_date": str(observations[-1]["realization_date"]) if observations else None,
        "decision_log_sha256": file_hash(decisions_path),
        "observation_log_sha256": file_hash(observations_path),
        "blended_performance_metrics": performance_metrics(values).to_dict() if values else {"observations": 0},
        "generated_at_utc": now.isoformat(),
        "promotion_authorized": False, "execution_enabled": False, "live_trading_enabled": False,
    }
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in
        ("saved_decisions", "observed_weeks", "latest_decision_date", "latest_realization_date")}},
        indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
