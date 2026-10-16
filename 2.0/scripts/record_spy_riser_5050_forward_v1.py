#!/usr/bin/env python3
"""Forward clock for the 50% SPY + 50% steady-riser book (protocol spy_riser_5050_v1).

A chosen risk level, not an edge (Steps 347, 349, 352). The riser leg is Step 347's S2 rule
verbatim, using its own functions: top 20 by 52-week log-price slope x R-squared among liquid
names, equal weight, held 52 weeks while positions drift, 50 bps on traded notional. SPY comes
from the ETF vintage snapshot taken in each Friday window. The blend resets to 50/50 every week.
Decisions and observations are hash-chained; a missed window is left missed.

    record_spy_riser_5050_forward_v1.py --decision-date 2026-10-16 [--realize]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.systematic_trader.evaluation import performance_metrics  # noqa: E402
from src.systematic_trader.forward_evidence import (  # noqa: E402
    ForwardEvidenceError, append_record, file_hash, read_and_verify_log,
)
import record_frozen_book_forward_evidence_v1 as fb  # noqa: E402
import run_steady_riser_v1 as sr  # noqa: E402

PROTOCOL = ROOT / "config/forward/spy_riser_5050_v1.json"
OUTPUT = ROOT / "evidence/forward_spy_riser_5050_v1"
BOOKS = OUTPUT / "books"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
TOP, COST, HOLD_DAYS = 20, 0.005, 364


def spy_week_return(day: str) -> tuple[float, str]:
    """SPY's return for the week ending `day`, from the first ETF snapshot observed in that window."""
    manifests = sorted(fb.SnapshotStore(fb.STORE_ROOT).manifests(), key=lambda m: str(m["observed_at_utc"]))
    eligible = [m for m in manifests if fb.observed_in_window(str(m["observed_at_utc"]), day)]
    if not eligible:
        raise ForwardEvidenceError(f"no ETF snapshot observed in the {day} window yet")
    snapshot = str(eligible[0]["snapshot_id"])
    state = fb.weekly_simple_returns(snapshot, ["SPY"])
    if day not in state["returns"] or "SPY" not in state["returns"][day]:
        raise ForwardEvidenceError(f"snapshot {snapshot} has no SPY return for the week ending {day}")
    return float(state["returns"][day]["SPY"]), snapshot


def form_book(prices: pd.DataFrame, dollar: pd.DataFrame, decision: pd.Timestamp) -> pd.DataFrame:
    if decision not in prices.index:
        raise ForwardEvidenceError(f"the clean weekly panel has no row for {decision.date()}")
    pos = prices.index.get_loc(decision)
    block = sr.eligible(prices, dollar, pos)
    if block.shape[1] < 60:
        raise ForwardEvidenceError(f"only {block.shape[1]} eligible names at {decision.date()}")
    score = sr.signals(block)["S2_steady_riser"].nlargest(TOP)
    tick = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False) \
        .drop_duplicates("cik10").set_index("cik10").symbol
    return pd.DataFrame({"cik10": score.index, "ticker": [tick.get(c, c) for c in score.index],
                         "s2_score": score.to_numpy(), "entry_price": prices.loc[decision, score.index].to_numpy(),
                         "weight": 1.0 / TOP, "eligible_universe": block.shape[1]})


def write_book(book: pd.DataFrame, day: str) -> tuple[Path, str]:
    BOOKS.mkdir(parents=True, exist_ok=True)
    path = BOOKS / f"book_{day}.csv"
    if path.exists():
        raise ForwardEvidenceError(f"{path.name} already exists; a frozen book is never rewritten")
    book.to_csv(path, index=False, quoting=csv.QUOTE_MINIMAL)
    return path, file_hash(path)


def drifted_values(book: pd.DataFrame, prices: pd.DataFrame, formed: pd.Timestamp, through: pd.Timestamp) -> pd.Series:
    """Each name's value per unit of the leg at `through`: weight x price / entry, last price carried."""
    block = prices.loc[formed:through, book.cik10].ffill()
    rel = block.iloc[-1] / book.set_index("cik10").entry_price
    return (book.set_index("cik10").weight * rel).fillna(book.set_index("cik10").weight)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--realize", action="store_true")
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    first = str(protocol["cadence"]["first_eligible_decision_date"])
    now = datetime.now(timezone.utc)
    decision = pd.Timestamp(args.decision_date)
    day = str(decision.date())
    start = fb.window_start(day)
    if date.fromisoformat(day) < date.fromisoformat(first):
        raise ForwardEvidenceError("decision predates the frozen boundary")
    if now < start:
        raise ForwardEvidenceError(f"the {day} window opens at 21:00 UTC that day; it is {now.isoformat()}")
    if now >= start + timedelta(days=7):
        raise ForwardEvidenceError(f"the {day} window closed; a missed window is not backfillable")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    decisions_path, observations_path = OUTPUT / "decisions.jsonl", OUTPUT / "observations.jsonl"
    prices, dollar = sr.load()
    added = {"decisions": 0, "observations": 0}

    decisions = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    if not any(str(r["decision_date"]) == day for r in decisions):
        last_formation = next((r for r in reversed(decisions) if r["formed_new_book"]), None)
        due = last_formation is None or (decision - pd.Timestamp(last_formation["decision_date"])).days >= HOLD_DAYS
        payload = {"record_type": "spy_riser_5050_decision_v1", "protocol_version": protocol["protocol_version"],
                   "decision_date": day, "eligible_realization_date": str((decision + pd.Timedelta(days=7)).date()),
                   "formed_new_book": bool(due), "recorded_at_utc": now.isoformat(),
                   "forward_protocol_sha256": file_hash(PROTOCOL), "execution_enabled": False}
        if due:
            book = form_book(prices, dollar, decision)
            path, digest = write_book(book, day)
            if last_formation is None:
                turnover = 1.0
            else:
                old = pd.read_csv(ROOT / last_formation["book_file"], dtype={"cik10": str})
                drift = drifted_values(old, prices, pd.Timestamp(last_formation["decision_date"]), decision)
                drift = drift / drift.sum()
                new = book.set_index("cik10").weight
                turnover = float(sum(abs(new.get(c, 0.0) - drift.get(c, 0.0)) for c in set(new.index) | set(drift.index)))
            payload.update({"book_file": str(path.relative_to(ROOT)), "book_sha256": digest,
                            "book_tickers": list(book.ticker), "eligible_universe": int(book.eligible_universe.iloc[0]),
                            "formation_turnover": turnover, "formation_cost": COST * turnover})
        else:
            payload.update({"book_file": last_formation["book_file"], "book_sha256": last_formation["book_sha256"],
                            "book_formed_on": last_formation["decision_date"]})
        append_record(decisions_path, payload, date_field="decision_date", first_eligible_date=first)
        added["decisions"] += 1

    if args.realize:
        prior = decision - pd.Timedelta(days=7)
        decisions = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
        match = next((r for r in decisions if str(r["decision_date"]) == str(prior.date())), None)
        if match is None:
            raise ForwardEvidenceError(f"no saved decision for {prior.date()} to realize")
        observed = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)
        if not any(str(r["realization_date"]) == day for r in observed):
            book_path = ROOT / match["book_file"]
            if file_hash(book_path) != match["book_sha256"]:
                raise ForwardEvidenceError(f"{book_path.name} does not match its pinned hash")
            book = pd.read_csv(book_path, dtype={"cik10": str})
            formed = pd.Timestamp(match.get("book_formed_on", match["decision_date"]))
            if decision not in prices.index:
                raise ForwardEvidenceError(f"the clean weekly panel has no row for {day}")
            before = drifted_values(book, prices, formed, prior).sum()
            after = drifted_values(book, prices, formed, decision).sum()
            riser = float(after / before - 1.0)
            cost = float(match.get("formation_cost", 0.0)) if match["formed_new_book"] else 0.0
            riser_net = (1.0 + riser) * (1.0 - cost) - 1.0
            spy, snapshot = spy_week_return(day)
            payload = {"record_type": "spy_riser_5050_observation_v1", "protocol_version": protocol["protocol_version"],
                       "decision_date": str(prior.date()), "realization_date": day,
                       "decision_record_hash": str(match["record_hash"]),
                       "riser_book_return": riser_net, "riser_formation_cost": cost, "spy_return": spy,
                       "spy_snapshot_id": snapshot, "blend_return": 0.5 * spy + 0.5 * riser_net,
                       "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                       "execution_enabled": False}
            append_record(observations_path, payload, date_field="realization_date", first_eligible_date=first)
            added["observations"] += 1

    decisions = read_and_verify_log(decisions_path, date_field="decision_date", first_eligible_date=first)
    observations = read_and_verify_log(observations_path, date_field="realization_date", first_eligible_date=first)
    blend = [float(o["blend_return"]) for o in observations]
    spy_r = [float(o["spy_return"]) for o in observations]
    status = {"protocol_version": protocol["protocol_version"], "role": "chosen risk level, not an edge",
              "saved_decisions": len(decisions), "observed_weeks": len(observations),
              "required_untouched_weeks": protocol["required_untouched_weeks"],
              "latest_decision_date": str(decisions[-1]["decision_date"]) if decisions else None,
              "latest_realization_date": str(observations[-1]["realization_date"]) if observations else None,
              "current_book": next((r["book_tickers"] for r in reversed(decisions) if r["formed_new_book"]), None),
              "decision_log_sha256": file_hash(decisions_path),
              "observation_log_sha256": file_hash(observations_path) if observations_path.exists() else None,
              "blend_performance_metrics": performance_metrics(blend).to_dict() if blend else {"observations": 0},
              "spy_performance_metrics": performance_metrics(spy_r).to_dict() if spy_r else {"observations": 0},
              "generated_at_utc": now.isoformat(),
              "promotion_authorized": False, "execution_enabled": False, "live_trading_enabled": False}
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in ("saved_decisions", "observed_weeks",
          "latest_decision_date", "latest_realization_date", "current_book")}}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
