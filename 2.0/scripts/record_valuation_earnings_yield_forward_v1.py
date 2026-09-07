#!/usr/bin/env python3
"""Record forward evidence for the revived valuation book, week by week.

Step 274 revived the valuation family by widening a book that had failed a
concentration gate at ten names, and Step 275 found it uncorrelated with every
strategy on the dashboard. Both of those facts were measured on the same
2023-2026 window every other candidate here was selected on, so neither is
evidence. This is the machinery that produces evidence.

The book is the twenty highest earnings-yield issuers in the most recent
quarterly score block at or before the decision, equally weighted, rebalanced
when a new block arrives and left to drift in between, paying 50bps on turnover.

Two things about the score panel are worth stating plainly rather than hiding
in a comment. It currently ends at 2026-04-01, so a decision recorded in
September holds a book chosen from April data. That is stale but it is causal,
which is the property that matters, and every record names the block it used
so the staleness is visible in the log rather than assumed away. And when the
panel is regenerated, the block in force changes without this script changing;
that is the intended behaviour of a quarterly strategy, not drift in the
protocol.
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

PROTOCOL = ROOT / "config/forward/valuation_earnings_yield_forward_v1.json"
OUTPUT = ROOT / "evidence/forward_valuation_earnings_yield_v1"
SCORES = ROOT / "evidence/sec_survivorship_valuation_discovery_v1/factor_scores.csv"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
FAMILY = "earnings_yield"
BREADTH = 20


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
    """Names carrying a real price in the last week at or before the decision.

    Column presence is not tradability. Filtering on columns alone let two of
    twenty names into the rehearsal book with no price at the decision, which
    would have been held at 5% each and silently dropped at realization.
    """
    weeks = [w for w in prices.index if w <= decision]
    if not weeks:
        raise ForwardEvidenceError(f"the price panel has no week at or before {decision.date()}")
    row = prices.loc[max(weeks)]
    return {str(c) for c in row.index[row.notna() & (row > 0)]}


def book_for(decision: pd.Timestamp, priced: set[str]) -> tuple[str, dict[str, float]]:
    """The twenty highest earnings-yield issuers in the latest block at or before `decision`."""
    scores = pd.read_csv(SCORES, dtype={"cik10": str})
    scores["decision_at"] = pd.to_datetime(scores.decision_at, utc=True)
    scores = scores[(scores.family == FAMILY) & scores.cik10.isin(priced)].dropna(subset=["score"])
    eligible = [q for q in sorted(scores.decision_at.unique()) if q <= decision]
    if not eligible:
        raise ForwardEvidenceError(f"no quarterly score block at or before {decision.date()}")
    block_at = max(eligible)
    block = scores[scores.decision_at == block_at]
    if len(block) < BREADTH:
        raise ForwardEvidenceError(f"block {block_at.date()} has {len(block)} names, needs {BREADTH}")
    picked = block.nlargest(BREADTH, "score")
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
        # behind, not against the last decision's targets. Measuring it against the
        # targets would charge for drift the strategy never traded.
        held = dict(observed[-1]["weights_after"]) if observed else {}
        turnover = sum(abs(target.get(n, 0.0) - held.get(n, 0.0))
                       for n in set(target) | set(held)) / 2.0
        rebalanced = bool(not saved or str(saved[-1]["score_block_at"]) != block_at)
        payload = {
            "record_type": "valuation_earnings_yield_decision_v1",
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
            "family": FAMILY,
            "cost_bps": cost_bps,
            "scores_sha256": file_hash(SCORES),
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
        if not any(str(r["realization_date"]) == day for r in observed):
            weights = {str(k): float(v) for k, v in dict(match["target_weights"]).items()}
            gross, drifted, changes = weekly_return(prices, decision, weights)
            cost = float(match["turnover_from_held"]) * cost_bps / 10_000.0
            payload = {
                "record_type": "valuation_earnings_yield_observation_v1",
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
