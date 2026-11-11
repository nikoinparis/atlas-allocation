#!/usr/bin/env python3
"""Forward clock: SPY/GLD/SHY reset only when a weight drifts > 5pp, next to the weekly-reset mix (banded_spy_gld_shy_v1).

A rebalancing-rule twin of static_spy_gld_shy_v1 (Step 377, T4), modelled on the trend-sleeve recorder.
Each record stores the closes it used and is hash-chained; a missed window is left missed.

    record_banded_spy_gld_shy_forward_v1.py --decision-date 2026-11-13 [--realize]

--rehearse-dir DIR writes to DIR instead of the evidence folder and skips the window and boundary
checks. It exists only for the dry run against an existing clock's numbers and can never touch the
real logs.
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

PROTOCOL = ROOT / "config/forward/banded_spy_gld_shy_v1.json"
OUTPUT = ROOT / "evidence/forward_banded_spy_gld_shy_v1"
ASSETS = ["SPY", "GLD", "SHY"]


def drift(weights: dict[str, float], returns: dict[str, float]) -> dict[str, float]:
    """Weights after one holding period with no trading."""
    total = sum(weights[a] * (1 + returns[a]) for a in ASSETS)
    return {a: weights[a] * (1 + returns[a]) / total for a in ASSETS}


def band_step(held: dict[str, float], returns: dict[str, float], target: dict[str, float], band: float):
    """One decision: drift the held weights, reset to target only if any weight is outside the band.

    Returns (new weights, drifted weights, rebalanced, turnover)."""
    drifted = drift(held, returns)
    if max(abs(drifted[a] - target[a]) for a in ASSETS) > band:
        return dict(target), drifted, True, sum(abs(target[a] - drifted[a]) for a in ASSETS)
    return drifted, drifted, False, 0.0


def closes_since(day: str, earliest: str) -> pd.DataFrame:
    end = (pd.Timestamp(day) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (pd.Timestamp(earliest) - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    return yf.download(ASSETS, start=start, end=end, auto_adjust=True, progress=False)["Close"][ASSETS].dropna()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--realize", action="store_true")
    parser.add_argument("--rehearse-dir", default=None)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    target = {a: float(protocol["rule"]["target_weights"][a]) for a in ASSETS}
    band = float(protocol["rule"]["band"])
    rehearse = args.rehearse_dir is not None
    output = Path(args.rehearse_dir) if rehearse else OUTPUT
    if rehearse and output.resolve() == OUTPUT.resolve():
        raise ForwardEvidenceError("a rehearsal cannot write to the evidence folder")
    first = "2000-01-07" if rehearse else str(protocol["cadence"]["first_eligible_decision_date"])
    now = datetime.now(timezone.utc)
    day = str(pd.Timestamp(args.decision_date).date())
    start = fb.window_start(day)
    if not rehearse:
        if date.fromisoformat(day) < date.fromisoformat(first):
            raise ForwardEvidenceError("decision predates the frozen boundary")
        if now < start:
            raise ForwardEvidenceError(f"the {day} window opens at 21:00 UTC that day")
        if now >= start + timedelta(days=7):
            raise ForwardEvidenceError(f"the {day} window closed; a missed window is not backfillable")
    output.mkdir(parents=True, exist_ok=True)
    dpath, opath = output / "decisions.jsonl", output / "observations.jsonl"
    added = {"decisions": 0, "observations": 0}
    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
    earlier = [r for r in decisions if str(r["decision_date"]) < day]
    last = earlier[-1] if earlier else None
    prior = str((pd.Timestamp(day) - pd.Timedelta(days=7)).date())
    closes = closes_since(day, str(last["decision_date"]) if last else prior)
    if pd.Timestamp(day) not in closes.index:
        raise ForwardEvidenceError(f"no closes for {day} yet for all of {ASSETS}")

    if not any(str(r["decision_date"]) == day for r in decisions):
        if last is None:
            weights, drifted, rebalanced, turnover, since = dict(target), None, False, 0.0, None
        else:
            since = str(last["decision_date"])
            if pd.Timestamp(since) not in closes.index:
                raise ForwardEvidenceError(f"download lacks the last saved decision date {since}")
            # Both closes come from the same download, so later dividend adjustments cannot mix vintages.
            r = {a: float(closes.loc[day, a] / closes.loc[since, a] - 1) for a in ASSETS}
            weights, drifted, rebalanced, turnover = band_step(last["weights"], r, target, band)
        append_record(dpath, {"record_type": "banded_spy_gld_shy_decision_v1", "protocol_version": protocol["protocol_version"],
                              "decision_date": day, "eligible_realization_date": str((pd.Timestamp(day) + pd.Timedelta(days=7)).date()),
                              "weights": weights, "drifted_weights_before_decision": drifted, "drift_measured_since": since,
                              "rebalanced": rebalanced, "turnover": turnover,
                              "closes_at_decision": {a: float(closes.loc[day, a]) for a in ASSETS},
                              "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                              "execution_enabled": False},
                      date_field="decision_date", first_eligible_date=first)
        added["decisions"] += 1

    if args.realize:
        decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
        match = next((r for r in decisions if str(r["decision_date"]) == prior), None)
        if match is None:
            raise ForwardEvidenceError(f"no saved decision for {prior}")
        observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=first)
        if not any(str(r["realization_date"]) == day for r in observed):
            if pd.Timestamp(prior) not in closes.index:
                raise ForwardEvidenceError(f"download lacks the prior Friday {prior}")
            r = {a: float(closes.loc[day, a] / closes.loc[prior, a] - 1) for a in ASSETS}
            banded = sum(match["weights"][a] * r[a] for a in ASSETS)
            base = sum(target[a] * r[a] for a in ASSETS)
            base_drifted = drift(target, r)
            append_record(opath, {"record_type": "banded_spy_gld_shy_observation_v1", "protocol_version": protocol["protocol_version"],
                                  "decision_date": prior, "realization_date": day, "decision_record_hash": match["record_hash"],
                                  "asset_returns": r, "closes_used": {a: [float(closes.loc[prior, a]), float(closes.loc[day, a])] for a in ASSETS},
                                  "banded_return": banded, "weekly_reset_return": base,
                                  "weekly_reset_turnover": sum(abs(target[a] - base_drifted[a]) for a in ASSETS),
                                  "recorded_at_utc": now.isoformat(), "forward_protocol_sha256": file_hash(PROTOCOL),
                                  "execution_enabled": False},
                          date_field="realization_date", first_eligible_date=first)
            added["observations"] += 1

    decisions = read_and_verify_log(dpath, date_field="decision_date", first_eligible_date=first)
    observed = read_and_verify_log(opath, date_field="realization_date", first_eligible_date=first)
    banded = [o["banded_return"] for o in observed]
    base = [o["weekly_reset_return"] for o in observed]
    status = {"protocol_version": protocol["protocol_version"], "role": "rebalancing-rule twin of the benchmark, not an edge",
              "saved_decisions": len(decisions), "observed_weeks": len(observed),
              "latest_decision_date": decisions[-1]["decision_date"] if decisions else None,
              "latest_realization_date": observed[-1]["realization_date"] if observed else None,
              "current_weights": decisions[-1]["weights"] if decisions else None,
              "band_rebalances": sum(1 for d in decisions if d["rebalanced"]),
              "banded_turnover_total": sum(d["turnover"] for d in decisions),
              "weekly_reset_turnover_total": sum(o["weekly_reset_turnover"] for o in observed),
              "banded_metrics": performance_metrics(banded).to_dict() if banded else {"observations": 0},
              "weekly_reset_metrics": performance_metrics(base).to_dict() if base else {"observations": 0},
              "required_untouched_weeks": protocol["required_untouched_weeks"], "rehearsal": rehearse,
              "generated_at_utc": now.isoformat(), "promotion_authorized": False, "execution_enabled": False,
              "live_trading_enabled": False}
    (output / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in ("saved_decisions", "observed_weeks", "latest_decision_date",
                                                                "latest_realization_date", "band_rebalances")}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
