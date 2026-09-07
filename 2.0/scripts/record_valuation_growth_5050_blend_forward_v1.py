#!/usr/bin/env python3
"""Record the 50/50 valuation-and-growth blend, derived from two running clocks.

This protocol observes nothing of its own. Step 275 found that blending the
revived valuation book with any of the three unlevered dashboard strategies beat
both components on Sharpe in nine of nine weight combinations, and that result is
worth exactly nothing as evidence: the nine weights were chosen after seeing the
answer, on a window both legs were already selected on. What this script does is
make the claim checkable, by fixing the weight at 0.5 before any forward data
exists and then deriving the blend mechanically from two logs it cannot edit.

It reads both legs' hash-chained observation logs, verifies both chains, and
appends one record per realization date the two legs share, pinning the source
record hashes. It cannot advance when either leg is missing that week, and
because it is a pure function of two append-only logs it cannot be recomputed
from a later vintage or quietly re-weighted.

The blend is rebalanced to 0.5/0.5 every week. That is a choice, and it is the
one that carries no free parameter: letting the legs drift would make the
realized weight a function of the returns, which is the thing being measured.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError, append_record, file_hash, read_and_verify_log,
)

PROTOCOL = ROOT / "config/forward/valuation_growth_5050_blend_forward_v1.json"
OUTPUT = ROOT / "evidence/forward_valuation_growth_5050_blend_v1"
WEIGHT = 0.5


def leg_returns(log: Path, first: str, extract) -> dict[str, tuple[float, str]]:
    records = read_and_verify_log(log, date_field="realization_date", first_eligible_date=first)
    return {str(r["realization_date"]): (float(extract(r)), str(r["record_hash"])) for r in records}


def correlation(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 8:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va <= 0 or vb <= 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va ** 0.5 * vb ** 0.5)


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()

    protocol = json.loads(PROTOCOL.read_text())
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("this protocol cannot enable execution")
    if float(protocol["leg_a"].get("weight", WEIGHT)) != WEIGHT and "weight" in protocol["leg_a"]:
        raise ForwardEvidenceError("the frozen weight is 0.5 and this script implements only 0.5")
    first = str(protocol["first_eligible_decision_date"])
    now = datetime.now(timezone.utc)

    a_log = ROOT / str(protocol["leg_a"]["log"])
    b_log = ROOT / str(protocol["leg_b"]["log"])
    leverage = str(protocol["leg_b"]["leverage_leg"])

    a = leg_returns(a_log, first, lambda r: r["net_return"])
    b = leg_returns(b_log, first, lambda r: r["path_net_returns"][leverage])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    blend_path = OUTPUT / "observations.jsonl"
    existing = read_and_verify_log(blend_path, date_field="realization_date", first_eligible_date=first)
    already = {str(r["realization_date"]) for r in existing}

    shared = sorted(set(a) & set(b))
    added = 0
    for day in shared:
        if day in already:
            continue
        a_return, a_hash = a[day]
        b_return, b_hash = b[day]
        payload = {
            "record_type": "valuation_growth_5050_blend_observation_v1",
            "protocol_version": protocol["protocol_version"],
            "realization_date": day,
            "weight_valuation": WEIGHT, "weight_growth": 1.0 - WEIGHT,
            "valuation_net_return": a_return, "growth_net_return": b_return,
            "valuation_record_hash": a_hash, "growth_record_hash": b_hash,
            "valuation_protocol": str(protocol["leg_a"]["protocol"]),
            "growth_protocol": str(protocol["leg_b"]["protocol"]),
            "growth_leverage_leg": leverage,
            "blend_net_return": WEIGHT * a_return + (1.0 - WEIGHT) * b_return,
            "derived_not_observed": True,
            "recorded_at_utc": now.isoformat(),
            "forward_protocol_sha256": file_hash(PROTOCOL),
            "execution_enabled": False,
        }
        append_record(blend_path, payload, date_field="realization_date", first_eligible_date=first)
        added += 1

    records = read_and_verify_log(blend_path, date_field="realization_date", first_eligible_date=first)
    blend = [float(r["blend_net_return"]) for r in records]
    va = [float(r["valuation_net_return"]) for r in records]
    gr = [float(r["growth_net_return"]) for r in records]
    blend_metrics = performance_metrics(blend).to_dict() if blend else {"observations": 0}
    a_metrics = performance_metrics(va).to_dict() if va else {"observations": 0}
    b_metrics = performance_metrics(gr).to_dict() if gr else {"observations": 0}
    realized_correlation = correlation(va, gr)

    # The whole result rests on the legs staying uncorrelated. Say so in the status
    # file rather than leaving it to be rediscovered when the clock finishes.
    beats_both = None
    if blend and all("sharpe" in m for m in (blend_metrics, a_metrics, b_metrics)):
        beats_both = bool(blend_metrics["sharpe"] > a_metrics["sharpe"]
                          and blend_metrics["sharpe"] > b_metrics["sharpe"])

    status = {
        "protocol_version": protocol["protocol_version"],
        "derived_not_observed": True,
        "weeks_available_valuation": len(a), "weeks_available_growth": len(b),
        "weeks_shared_and_recorded": len(records),
        "required_weeks": int(protocol["required_untouched_weeks"]),
        "remaining_weeks": max(0, int(protocol["required_untouched_weeks"]) - len(records)),
        "clock_complete": len(records) >= int(protocol["required_untouched_weeks"]),
        "latest_realization_date": str(records[-1]["realization_date"]) if records else None,
        "blend_performance_metrics": blend_metrics,
        "valuation_leg_performance_metrics": a_metrics,
        "growth_leg_performance_metrics": b_metrics,
        "realized_leg_correlation": realized_correlation,
        "correlation_refutation_threshold": 0.5,
        "correlation_refuted": (realized_correlation is not None and realized_correlation > 0.5),
        "blend_sharpe_beats_both_legs": beats_both,
        "observation_log_sha256": file_hash(blend_path),
        "forward_protocol_sha256": file_hash(PROTOCOL),
        "legs_were_selected_on_the_same_window": True,
        "generated_at_utc": now.isoformat(),
        "promotion_authorized": False, "execution_enabled": False, "live_trading_enabled": False,
    }
    (OUTPUT / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"added": added, **{k: status[k] for k in
        ("weeks_available_valuation", "weeks_available_growth", "weeks_shared_and_recorded",
         "remaining_weeks", "latest_realization_date", "realized_leg_correlation",
         "blend_sharpe_beats_both_legs")}}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
