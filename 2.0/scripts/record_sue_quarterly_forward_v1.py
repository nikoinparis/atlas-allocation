#!/usr/bin/env python3
"""Record forward evidence for the SUE book, week by week.

The clock this serves was frozen on 2026-09-06 with a first eligible decision
date of 2026-09-11, and on that date it had no recorder at all -- it was
referenced only by the pre-flight, and had no evidence directory. This is that
recorder, written to the same shape as
`record_valuation_earnings_yield_forward_v1.py`, which is the one quarterly
clock in this project that has started cleanly.

Why the clock exists, in the protocol's own words: SUE measures +0.0053 at
t=0.71 over fifteen years and +0.0316 at t=3.57 on the recent high-coverage
window, and those two facts cannot be separated from history, because the recent
window is BOTH where the data is clean AND where every other strategy here was
selected. Step 253 measured this book's correlation against the existing
strategies at 0.002 and 0.008, the lowest this project has ever recorded against
a set that correlates 0.506 to 0.874 internally. None of that is evidence. This
is the machinery that produces evidence.

The book is the fifty highest SUE among roster members priced at the decision,
equally weighted, rebalanced when a new quarterly score block arrives and left
to drift in between, paying 50bps on turnover.

**Two joins in this file are the kind that have silently produced zeros here
before, and both are asserted rather than trusted.**

The SUE panel stores `cik10` zero-padded to ten characters and pandas will read
it as an integer and strip the padding unless told not to, which turns an
overlap of 2,536 names into an overlap of nought and a book of fifty into a
crash or, worse, an empty selection. Step 302 lost a session to exactly this
shape of bug on Indonesian tickers -- joining `ticker` against `vendor_ticker`
-- so the read pins the dtype and the code then checks the overlap is non-empty
and says so if it is not.

Column presence in the price panel is not tradability. The valuation recorder
found two of twenty names entering a rehearsal book with no price at the
decision, which would have been held at 2% each and silently dropped at
realization, so tradability is tested on the value, not on the column.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError, append_record, canonical_bytes, file_hash, read_and_verify_log,
)

PROTOCOL = ROOT / "config/forward/sue_quarterly_forward_v1.json"
OUTPUT = ROOT / "evidence/forward_sue_quarterly_v1"
SCORES = ROOT / "evidence/extended_sue_panel_v1/sue_panel.csv.gz"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
SIGNAL = "standardized_unexpected_earnings"
BREADTH = 50


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def window_start(day: str) -> datetime:
    parsed = date.fromisoformat(day)
    if parsed.weekday() != 4:
        raise ForwardEvidenceError("forward evidence dates must be Fridays")
    return datetime.combine(parsed, time(21, 0), tzinfo=timezone.utc)


def load_prices() -> pd.DataFrame:
    frame = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame.columns = [str(c) for c in frame.columns]
    return frame


def tradable_at(prices: pd.DataFrame, decision: pd.Timestamp) -> set[str]:
    """Names carrying a real price in the last week at or before the decision."""
    weeks = [w for w in prices.index if w <= decision]
    if not weeks:
        raise ForwardEvidenceError(f"the price panel has no week at or before {decision.date()}")
    row = prices.loc[max(weeks)]
    return {str(c) for c in row.index[row.notna() & (row > 0)]}


def book_for(decision: pd.Timestamp, priced: set[str]) -> tuple[str, dict[str, float]]:
    """The fifty highest-SUE issuers in the latest block at or before `decision`."""
    # dtype is pinned: without it pandas reads 0000001750 as 1750 and every join
    # against the price panel's zero-padded columns returns nothing.
    scores = pd.read_csv(SCORES, dtype={"cik10": str})
    scores["cik10"] = scores.cik10.str.zfill(10)
    scores["decision_at"] = pd.to_datetime(scores.decision_at, utc=True)
    scores = scores.dropna(subset=[SIGNAL])

    eligible = [q for q in sorted(scores.decision_at.unique()) if q <= decision]
    if not eligible:
        raise ForwardEvidenceError(f"no quarterly score block at or before {decision.date()}")
    block_at = max(eligible)
    block = scores[scores.decision_at == block_at]

    overlap = block[block.cik10.isin(priced)]
    if overlap.empty:
        raise ForwardEvidenceError(
            f"block {block_at.date()} has {len(block)} scored names and none of them is priced "
            "-- this is an identifier-format mismatch, not an empty universe"
        )
    if len(overlap) < BREADTH:
        raise ForwardEvidenceError(
            f"block {block_at.date()} has {len(overlap)} priced names, needs {BREADTH}"
        )
    picked = overlap.nlargest(BREADTH, SIGNAL)
    return str(block_at.date()), {str(c): 1.0 / BREADTH for c in picked.cik10}


def weekly_return(prices: pd.DataFrame, week: pd.Timestamp, weights: dict[str, float]):
    """Return per held name for the week ending `week`, and the drifted weights after it."""
    if week not in prices.index:
        raise ForwardEvidenceError(f"the price panel has no week ending {week.date()}")
    position = prices.index.get_loc(week)
    if position == 0:
        raise ForwardEvidenceError("no prior week to compute a return from")
    changes: dict[str, float] = {}
    for name, weight in weights.items():
        if name not in prices.columns:
            continue
        now, before = prices.iloc[position][name], prices.iloc[position - 1][name]
        if pd.isna(now) or pd.isna(before) or before <= 0:
            continue
        change = float(now / before - 1.0)
        if abs(change) <= 1.0:
            changes[name] = change
    if not changes:
        raise ForwardEvidenceError(f"no held name is priced for the week ending {week.date()}")
    held = sum(weights[n] for n in changes)
    gross = sum(weights[n] * changes[n] for n in changes) / held
    grown = {n: weights[n] * (1.0 + changes[n]) for n in changes}
    total = sum(grown.values())
    return gross, {n: v / total for n, v in grown.items()}, changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True, help="the Friday being recorded")
    parser.add_argument("--realize", action="store_true",
                        help="also record the realization for the decision one week earlier")
    parser.add_argument("--dry-run", action="store_true",
                        help="build the book and print the record without appending it")
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    first = str(protocol["first_eligible_decision_date"])
    cost_bps = float(protocol["cost_bps_per_unit_turnover"])

    now = datetime.now(timezone.utc)
    decision = pd.Timestamp(args.decision_date, tz="UTC")
    day = str(decision.date())
    if date.fromisoformat(day) < date.fromisoformat(first):
        raise ForwardEvidenceError("decision predates the frozen boundary")
    if now < window_start(day):
        raise ForwardEvidenceError(f"the {day} window opens at 21:00 UTC that day; it is {now.isoformat()}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    decisions_path, observations_path = OUTPUT / "decisions.jsonl", OUTPUT / "observations.jsonl"
    prices = load_prices()
    added = {"decisions": 0, "observations": 0}

    saved = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    observed = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)

    if not any(str(r["decision_date"]) == day for r in saved):
        block_at, target = book_for(decision, tradable_at(prices, decision))
        # Turnover is measured against the drifted weights the last realization left
        # behind, not against the last decision's targets, so drift the strategy never
        # traded is not charged for.
        held = dict(observed[-1]["weights_after"]) if observed else {}
        turnover = sum(abs(target.get(n, 0.0) - held.get(n, 0.0))
                       for n in set(target) | set(held)) / 2.0
        rebalanced = bool(not saved or str(saved[-1]["score_block_at"]) != block_at)
        payload = {
            "record_type": "sue_quarterly_decision_v1",
            "protocol_version": protocol["protocol_version"],
            "decision_date": day,
            "eligible_realization_date": str((decision + pd.Timedelta(days=7)).date()),
            "score_block_at": block_at,
            "score_block_is_new": rebalanced,
            "score_block_age_days": (decision - pd.Timestamp(block_at, tz="UTC")).days,
            "target_weights": target if rebalanced else (held or target),
            "target_weights_sha256": sha256_value(target if rebalanced else (held or target)),
            "turnover_from_held": turnover if rebalanced else 0.0,
            "breadth": BREADTH,
            "signal": SIGNAL,
            "cost_bps": cost_bps,
            "scores_sha256": file_hash(SCORES),
            "prices_sha256": file_hash(PRICES),
            "recorded_at_utc": now.isoformat(),
            "forward_protocol_sha256": file_hash(PROTOCOL),
            "modifies": "nothing",
            "execution_enabled": False,
        }
        if args.dry_run:
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        append_record(decisions_path, payload, date_field="decision_date", first_eligible_date=first)
        added["decisions"] += 1
    elif args.dry_run:
        print(json.dumps({"already_recorded": day}, indent=2))
        return 0

    if args.realize:
        prior = decision - pd.Timedelta(days=7)
        saved = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
        match = next((r for r in saved if str(r["decision_date"]) == str(prior.date())), None)
        if match is None:
            raise ForwardEvidenceError(f"no saved decision for {prior.date()} to realize")
        if not any(str(r["realization_date"]) == day for r in observed):
            weights = {str(k): float(v) for k, v in dict(match["target_weights"]).items()}
            gross, drifted, changes = weekly_return(prices, decision, weights)
            cost = float(match["turnover_from_held"]) * cost_bps / 10_000.0
            payload = {
                "record_type": "sue_quarterly_observation_v1",
                "protocol_version": protocol["protocol_version"],
                "decision_date": str(prior.date()), "realization_date": day,
                "decision_record_hash": str(match["record_hash"]),
                "target_weights_sha256": str(match["target_weights_sha256"]),
                "asset_returns": changes,
                "priced_names": len(changes), "book_names": len(weights),
                "gross_return": gross, "turnover": float(match["turnover_from_held"]),
                "cost": cost, "net_return": gross - cost,
                "weights_after": drifted,
                "recorded_at_utc": now.isoformat(),
                "forward_protocol_sha256": file_hash(PROTOCOL),
                "execution_enabled": False,
            }
            append_record(observations_path, payload, date_field="realization_date", first_eligible_date=first)
            added["observations"] += 1

    decisions = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    observations = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)
    values = [float(o["net_return"]) for o in observations]
    status = {
        "protocol_version": protocol["protocol_version"],
        "saved_decisions": len(decisions), "observed_weeks": len(observations),
        "required_weeks": int(protocol["required_untouched_weeks"]),
        "remaining_weeks": max(0, int(protocol["required_untouched_weeks"]) - len(observations)),
        "clock_complete": len(observations) >= int(protocol["required_untouched_weeks"]),
        "latest_decision_date": str(decisions[-1]["decision_date"]) if decisions else None,
        "latest_realization_date": str(observations[-1]["realization_date"]) if observations else None,
        "latest_score_block_at": str(decisions[-1]["score_block_at"]) if decisions else None,
        "decision_log_sha256": file_hash(decisions_path),
        "observation_log_sha256": file_hash(observations_path),
        "forward_protocol_sha256": file_hash(PROTOCOL),
        "performance_metrics": performance_metrics(values).to_dict() if values else {"observations": 0},
        # SUE's historical record was read before this clock was frozen, so the
        # selection is contaminated in the same way every other candidate here is.
        # The clock is the uncontaminated part; the prior is not.
        "selection_contaminated": True,
        "generated_at_utc": now.isoformat(),
        "promotion_authorized": False, "execution_enabled": False, "live_trading_enabled": False,
    }
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in
        ("saved_decisions", "observed_weeks", "remaining_weeks",
         "latest_decision_date", "latest_realization_date", "latest_score_block_at")}},
        indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
