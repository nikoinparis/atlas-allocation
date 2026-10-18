#!/usr/bin/env python3
"""Forward clock: 80% SPY/GLD/SHY + 20% DBMF, with plain SPY/GLD/SHY from the same prices (trend_sleeve_8020_v1).

A diversifier allocation judged forward (Steps 340, 369). Each weekly realization downloads adjusted
closes, stores the two closes it used per asset in the record, and is hash-chained; a missed window
is left missed.

    record_trend_sleeve_8020_forward_v1.py --decision-date 2026-10-16 [--realize]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.systematic_trader.evaluation import performance_metrics  # noqa: E402
from src.systematic_trader.forward_evidence import ForwardEvidenceError, append_record, file_hash, read_and_verify_log  # noqa: E402
import record_frozen_book_forward_evidence_v1 as fb  # noqa: E402

PROTOCOL = ROOT / "config/forward/trend_sleeve_8020_v1.json"
OUTPUT = ROOT / "evidence/forward_trend_sleeve_8020_v1"
ASSETS = ["SPY", "GLD", "SHY", "DBMF"]


def friday_closes(day: str) -> pd.DataFrame:
    end = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    raw = yf.download(ASSETS, start=(pd.Timestamp(day) - pd.Timedelta(days=21)).strftime("%Y-%m-%d"), end=end,
                      auto_adjust=True, progress=False)["Close"][ASSETS].dropna()
    return raw


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--realize", action="store_true")
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    first = str(protocol["cadence"]["first_eligible_decision_date"])
    weights = protocol["rule"]["weights"]
    now = datetime.now(timezone.utc)
    day = str(pd.Timestamp(args.decision_date).date())
    start = fb.window_start(day)
    if date.fromisoformat(day) < date.fromisoformat(first):
        raise ForwardEvidenceError("decision predates the frozen boundary")
    if now < start:
        raise ForwardEvidenceError(f"the {day} window opens at 21:00 UTC that day")
    if now >= start + timedelta(days=7):
        raise ForwardEvidenceError(f"the {day} window closed; a missed window is not backfillable")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dpath, opath = OUTPUT / "decisions.jsonl", OUTPUT / "observations.jsonl"
    added = {"decisions": 0, "observations": 0}
    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
    closes = friday_closes(day)
    if pd.Timestamp(day) not in closes.index:
        raise ForwardEvidenceError(f"no closes for {day} yet for all of {ASSETS}")
    if not any(str(r["decision_date"]) == day for r in decisions):
        append_record(dpath, {"record_type": "trend_sleeve_8020_decision_v1", "protocol_version": protocol["protocol_version"],
                              "decision_date": day, "eligible_realization_date": str((pd.Timestamp(day) + pd.Timedelta(days=7)).date()),
                              "weights": weights, "closes_at_decision": {a: float(closes.loc[day, a]) for a in ASSETS},
                              "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                              "execution_enabled": False},
                      date_field="decision_date", first_eligible_date=first)
        added["decisions"] += 1
    if args.realize:
        prior = str((pd.Timestamp(day) - pd.Timedelta(days=7)).date())
        decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
        match = next((r for r in decisions if str(r["decision_date"]) == prior), None)
        if match is None:
            raise ForwardEvidenceError(f"no saved decision for {prior}")
        observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=first)
        if not any(str(r["realization_date"]) == day for r in observed):
            if pd.Timestamp(prior) not in closes.index:
                raise ForwardEvidenceError(f"download lacks the prior Friday {prior}")
            # Both closes come from the same download, so later dividend adjustments cannot mix vintages.
            r = {a: float(closes.loc[day, a] / closes.loc[prior, a] - 1) for a in ASSETS}
            mix = sum(weights[a] * r[a] for a in ASSETS)
            base = (r["SPY"] + r["GLD"] + r["SHY"]) / 3
            append_record(opath, {"record_type": "trend_sleeve_8020_observation_v1", "protocol_version": protocol["protocol_version"],
                                  "decision_date": prior, "realization_date": day, "decision_record_hash": match["record_hash"],
                                  "asset_returns": r, "closes_used": {a: [float(closes.loc[prior, a]), float(closes.loc[day, a])] for a in ASSETS},
                                  "sleeve_8020_return": mix, "base_spy_gld_shy_return": base,
                                  "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                                  "execution_enabled": False},
                          date_field="realization_date", first_eligible_date=first)
            added["observations"] += 1
    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
    observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=first)
    mix = [o["sleeve_8020_return"] for o in observed]
    base = [o["base_spy_gld_shy_return"] for o in observed]
    status = {"protocol_version": protocol["protocol_version"], "role": "diversifier allocation, not an edge",
              "saved_decisions": len(decisions), "observed_weeks": len(observed),
              "latest_decision_date": decisions[-1]["decision_date"] if decisions else None,
              "latest_realization_date": observed[-1]["realization_date"] if observed else None,
              "sleeve_8020_metrics": performance_metrics(mix).to_dict() if mix else {"observations": 0},
              "base_metrics": performance_metrics(base).to_dict() if base else {"observations": 0},
              "generated_at_utc": now.isoformat(), "promotion_authorized": False, "execution_enabled": False,
              "live_trading_enabled": False}
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in ("saved_decisions", "observed_weeks", "latest_decision_date",
                                                                "latest_realization_date")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
