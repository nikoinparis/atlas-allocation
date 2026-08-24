#!/usr/bin/env python3
"""Record untouched forward evidence for the frozen SEC residual sleeve.

The recorder consumes immutable decision and realization packets.  It does not
download data, select parameters, place orders, or permit a later vintage to
fill a missed weekly window.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.evaluation import performance_metrics
from systematic_trader.forward_evidence import (
    ForwardEvidenceError,
    append_record,
    canonical_bytes,
    file_hash,
    read_and_verify_log,
    verify_pinned_files,
)


PROTOCOL_PATH = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
OUTPUT = ROOT / "evidence/forward_sec_residual_controlled_sleeve_v1"
ANCHOR_PATH = OUTPUT / "anchor.json"
DECISIONS_PATH = OUTPUT / "decisions.jsonl"
OBSERVATIONS_PATH = OUTPUT / "observations.jsonl"
STATUS_PATH = OUTPUT / "status.json"
REPORT_PATH = OUTPUT / "report.md"
CASH = "cash::USD"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ForwardEvidenceError("timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def eligible_window_start(day: str) -> datetime:
    parsed = date.fromisoformat(day)
    if parsed.weekday() != 4:
        raise ForwardEvidenceError("forward evidence dates must be Fridays")
    return datetime.combine(parsed, time(21, 0), tzinfo=timezone.utc)


def observed_in_weekly_window(observed_at_utc: str, week: str) -> bool:
    observed = parse_utc(observed_at_utc)
    start = eligible_window_start(week)
    return start <= observed < start + timedelta(days=7)


def normalize_weights(raw: object, *, label: str) -> dict[str, float]:
    if not isinstance(raw, dict) or not raw:
        raise ForwardEvidenceError(f"{label} weights must be a non-empty object")
    weights: dict[str, float] = {}
    for asset, value in raw.items():
        weight = float(value)
        if not str(asset).strip() or not math.isfinite(weight) or weight < 0.0:
            raise ForwardEvidenceError(f"{label} contains an invalid weight")
        if weight > 1.0 + 1e-12:
            raise ForwardEvidenceError(f"{label} contains a weight above 100%")
        if weight > 1e-15:
            weights[str(asset)] = weight
    if abs(sum(weights.values()) - 1.0) > 1e-10:
        raise ForwardEvidenceError(f"{label} weights must sum to one")
    return dict(sorted(weights.items()))


def blend_weights(
    control: dict[str, float], residual: dict[str, float], residual_weight: float
) -> dict[str, float]:
    assets = sorted(set(control) | set(residual))
    blended = {
        asset: (1.0 - residual_weight) * control.get(asset, 0.0)
        + residual_weight * residual.get(asset, 0.0)
        for asset in assets
    }
    return {asset: weight for asset, weight in blended.items() if weight > 1e-15}


def turnover(prior: dict[str, float], target: dict[str, float]) -> float:
    assets = set(prior) | set(target)
    return 0.5 * sum(abs(target.get(asset, 0.0) - prior.get(asset, 0.0)) for asset in assets)


def levered_return(net_return: float, multiplier: float, financing_rate: float) -> float:
    borrowed = max(0.0, multiplier - 1.0)
    return multiplier * net_return - borrowed * financing_rate / 52.0


def load_protocol() -> dict[str, object]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    verify_pinned_files(ROOT, dict(protocol["pinned_files_sha256"]))
    if protocol.get("live_trading_enabled") or protocol.get("execution_enabled"):
        raise ForwardEvidenceError("forward research protocol cannot enable execution")
    return protocol


def initialize_anchor(protocol: dict[str, object]) -> dict[str, object]:
    expected = {
        "schema_version": 1,
        "protocol_version": protocol["protocol_version"],
        "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        "historical_result_sha256": file_hash(ROOT / str(protocol["historical_result"])),
        "historical_data_through": protocol["historical_data_through"],
        "first_decision_prior_control_weights": {CASH: 1.0},
        "first_decision_prior_residual_weights": {CASH: 1.0},
        "first_decision_turnover_policy": "conservative full transition from cash",
        "purpose": "pre-forward provenance and turnover anchor; never counted as untouched evidence",
        "execution_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if ANCHOR_PATH.exists():
        if json.loads(ANCHOR_PATH.read_text(encoding="utf-8")) != expected:
            raise ForwardEvidenceError("forward anchor changed")
    else:
        ANCHOR_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return expected


def load_packet(path: Path) -> dict[str, object]:
    packet = json.loads(path.read_text(encoding="utf-8"))
    supplied = str(packet.get("packet_sha256", ""))
    basis = {key: value for key, value in packet.items() if key != "packet_sha256"}
    if supplied != sha256_value(basis):
        raise ForwardEvidenceError(f"packet hash mismatch: {path}")
    return packet


def verify_source_manifest(packet: dict[str, object]) -> None:
    relative = str(packet.get("source_manifest", ""))
    expected = str(packet.get("source_manifest_sha256", ""))
    if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ForwardEvidenceError("packet source manifest must be workspace-relative")
    source = ROOT / relative
    if not source.is_file() or file_hash(source) != expected:
        raise ForwardEvidenceError("packet source manifest is missing or changed")


def append_decision(
    protocol: dict[str, object], anchor: dict[str, object], packet: dict[str, object]
) -> dict[str, object]:
    if packet.get("packet_type") != "sec_residual_forward_decision_v1":
        raise ForwardEvidenceError("wrong decision packet type")
    if packet.get("protocol_version") != protocol["protocol_version"]:
        raise ForwardEvidenceError("decision packet references another protocol")
    day = str(packet.get("decision_date", ""))
    eligible_window_start(day)
    if date.fromisoformat(day) < date.fromisoformat(str(protocol["first_eligible_decision_date"])):
        raise ForwardEvidenceError("decision predates the frozen boundary")
    if not observed_in_weekly_window(str(packet.get("observed_at_utc", "")), day):
        raise ForwardEvidenceError("decision packet is outside its frozen weekly window")
    if date.fromisoformat(str(packet.get("source_data_through", ""))) > date.fromisoformat(day):
        raise ForwardEvidenceError("decision packet uses post-decision data")
    verify_source_manifest(packet)
    control = normalize_weights(packet.get("control_target_weights"), label="control")
    residual = normalize_weights(packet.get("residual_target_weights"), label="residual")
    existing = read_and_verify_log(
        DECISIONS_PATH,
        date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    prior_control = (
        dict(existing[-1]["control_target_weights"])
        if existing
        else dict(anchor["first_decision_prior_control_weights"])
    )
    prior_residual = (
        dict(existing[-1]["residual_target_weights"])
        if existing
        else dict(anchor["first_decision_prior_residual_weights"])
    )
    residual_weight = float(protocol["residual_sleeve_weight"])
    composite = blend_weights(control, residual, residual_weight)
    payload = {
        "record_type": "sec_residual_forward_decision_v1",
        "protocol_version": protocol["protocol_version"],
        "decision_date": day,
        "eligible_realization_date": (date.fromisoformat(day) + timedelta(days=7)).isoformat(),
        "snapshot_id": packet["snapshot_id"],
        "observed_at_utc": packet["observed_at_utc"],
        "source_data_through": packet["source_data_through"],
        "source_manifest": packet["source_manifest"],
        "source_manifest_sha256": packet["source_manifest_sha256"],
        "decision_packet_sha256": packet["packet_sha256"],
        "control_target_weights": control,
        "residual_target_weights": residual,
        "composite_target_weights": composite,
        "control_target_weights_sha256": sha256_value(control),
        "residual_target_weights_sha256": sha256_value(residual),
        "composite_target_weights_sha256": sha256_value(composite),
        "control_turnover": turnover(prior_control, control),
        "residual_turnover": turnover(prior_residual, residual),
        "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        "execution_enabled": False,
    }
    return append_record(
        DECISIONS_PATH,
        payload,
        date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )


def append_observation(protocol: dict[str, object], packet: dict[str, object]) -> dict[str, object]:
    if packet.get("packet_type") != "sec_residual_forward_observation_v1":
        raise ForwardEvidenceError("wrong observation packet type")
    if packet.get("protocol_version") != protocol["protocol_version"]:
        raise ForwardEvidenceError("observation packet references another protocol")
    realization = str(packet.get("realization_date", ""))
    eligible_window_start(realization)
    if date.fromisoformat(realization) < date.fromisoformat(str(protocol["first_eligible_realization_date"])):
        raise ForwardEvidenceError("observation predates the frozen boundary")
    if not observed_in_weekly_window(str(packet.get("observed_at_utc", "")), realization):
        raise ForwardEvidenceError("observation packet is outside its frozen weekly window")
    if date.fromisoformat(str(packet.get("source_data_through", ""))) < date.fromisoformat(realization):
        raise ForwardEvidenceError("observation packet does not contain the completed week")
    verify_source_manifest(packet)
    decisions = read_and_verify_log(
        DECISIONS_PATH,
        date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    decision = next(
        (row for row in decisions if str(row["eligible_realization_date"]) == realization),
        None,
    )
    if decision is None:
        raise ForwardEvidenceError("no frozen decision exists for this realization")
    raw_returns = packet.get("asset_total_returns")
    if not isinstance(raw_returns, dict):
        raise ForwardEvidenceError("observation packet lacks security total returns")
    asset_returns: dict[str, float] = {}
    held = set(decision["control_target_weights"]) | set(decision["residual_target_weights"])
    for asset in sorted(held):
        if asset == CASH:
            asset_returns[asset] = 0.0
            continue
        if asset not in raw_returns:
            raise ForwardEvidenceError(f"held security is unpriced: {asset}")
        value = float(raw_returns[asset])
        if not math.isfinite(value) or value <= -1.0:
            raise ForwardEvidenceError(f"invalid total return for held security: {asset}")
        asset_returns[asset] = value
    control_gross = sum(
        float(weight) * asset_returns[asset]
        for asset, weight in dict(decision["control_target_weights"]).items()
    )
    residual_gross = sum(
        float(weight) * asset_returns[asset]
        for asset, weight in dict(decision["residual_target_weights"]).items()
    )
    cost_rate = float(protocol["cost_bps_per_unit_turnover"]) / 10_000.0
    control_cost = float(decision["control_turnover"]) * cost_rate
    residual_cost = float(decision["residual_turnover"]) * cost_rate
    control_net = control_gross - control_cost
    residual_net = residual_gross - residual_cost
    sleeve_weight = float(protocol["residual_sleeve_weight"])
    unlevered = (1.0 - sleeve_weight) * control_net + sleeve_weight * residual_net
    path_returns = {"unlevered_1.00x": unlevered}
    for rate in protocol["financing_rates"]:
        label = f"levered_1.25x_{int(round(float(rate) * 100))}pct_financing"
        path_returns[label] = levered_return(unlevered, 1.25, float(rate))
    payload = {
        "record_type": "sec_residual_forward_observation_v1",
        "protocol_version": protocol["protocol_version"],
        "decision_date": decision["decision_date"],
        "realization_date": realization,
        "decision_record_hash": decision["record_hash"],
        "snapshot_id": packet["snapshot_id"],
        "observed_at_utc": packet["observed_at_utc"],
        "source_data_through": packet["source_data_through"],
        "source_manifest": packet["source_manifest"],
        "source_manifest_sha256": packet["source_manifest_sha256"],
        "observation_packet_sha256": packet["packet_sha256"],
        "asset_total_returns": asset_returns,
        "control_gross_return": control_gross,
        "residual_gross_return": residual_gross,
        "control_cost": control_cost,
        "residual_cost": residual_cost,
        "control_net_return": control_net,
        "residual_net_return": residual_net,
        "path_net_returns": path_returns,
        "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        "execution_enabled": False,
    }
    return append_record(
        OBSERVATIONS_PATH,
        payload,
        date_field="realization_date",
        first_eligible_date=str(protocol["first_eligible_realization_date"]),
    )


def update_status(protocol: dict[str, object]) -> dict[str, object]:
    decisions = read_and_verify_log(
        DECISIONS_PATH,
        date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    observations = read_and_verify_log(
        OBSERVATIONS_PATH,
        date_field="realization_date",
        first_eligible_date=str(protocol["first_eligible_realization_date"]),
    )
    paths = ["unlevered_1.00x", *[
        f"levered_1.25x_{int(round(float(rate) * 100))}pct_financing"
        for rate in protocol["financing_rates"]
    ]]
    metrics = {}
    for name in paths:
        values = [float(row["path_net_returns"][name]) for row in observations]
        metrics[name] = performance_metrics(values).to_dict() if values else {"observations": 0}
    required = int(protocol["required_untouched_weeks"])
    count = len(observations)
    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_version": protocol["protocol_version"],
        "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        "anchor_sha256": file_hash(ANCHOR_PATH),
        "decision_log_sha256": file_hash(DECISIONS_PATH),
        "observation_log_sha256": file_hash(OBSERVATIONS_PATH),
        "decision_log_head": decisions[-1]["record_hash"] if decisions else None,
        "observation_log_head": observations[-1]["record_hash"] if observations else None,
        "saved_decisions": len(decisions),
        "observed_weeks": count,
        "required_weeks": required,
        "remaining_weeks": max(0, required - count),
        "clock_complete": count >= required,
        "latest_decision_date": decisions[-1]["decision_date"] if decisions else None,
        "latest_realization_date": observations[-1]["realization_date"] if observations else None,
        "performance_metrics": metrics,
        "selection_contaminated": True,
        "promotion_authorized": False,
        "final": False,
        "approved_for_live_trading": False,
        "execution_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join([
            "# Frozen SEC Residual Sleeve Forward Evidence",
            "",
            f"Protocol: `{protocol['protocol_version']}`",
            "",
            f"- Saved forward decisions: **{len(decisions)}**.",
            f"- Untouched realized weeks: **{count}/{required}**.",
            f"- Remaining weeks: **{max(0, required - count)}**.",
            f"- Latest decision: **{status['latest_decision_date'] or 'none'}**.",
            f"- Latest realization: **{status['latest_realization_date'] or 'none'}**.",
            "- Tracked paths: **1.00x, 1.25x at 5% financing, and 1.25x at 8% financing**.",
            "- Execution enabled: **no**.",
            "",
            "Every packet and saved record is hashed. Missed decision or realization windows cannot be backfilled from a later data vintage. Historical performance through 2026-08-21 is an anchor only and never advances this clock.",
            "",
        ]),
        encoding="utf-8",
    )
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-packet", type=Path)
    parser.add_argument("--observation-packet", type=Path)
    parser.add_argument("--initialize-only", action="store_true")
    args = parser.parse_args()
    if args.initialize_only and (args.decision_packet or args.observation_packet):
        raise ForwardEvidenceError("initialize-only cannot append packets")
    protocol = load_protocol()
    anchor = initialize_anchor(protocol)
    appended_decision = False
    appended_observation = False
    if args.decision_packet:
        append_decision(protocol, anchor, load_packet(args.decision_packet))
        appended_decision = True
    if args.observation_packet:
        append_observation(protocol, load_packet(args.observation_packet))
        appended_observation = True
    status = update_status(protocol)
    print(json.dumps({
        "appended_decision": appended_decision,
        "appended_observation": appended_observation,
        "saved_decisions": status["saved_decisions"],
        "observed_weeks": status["observed_weeks"],
        "required_weeks": status["required_weeks"],
        "execution_enabled": status["execution_enabled"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ForwardEvidenceError as error:
        print(json.dumps({"status": "rejected", "reason": str(error)}, indent=2), file=sys.stderr)
        raise SystemExit(2)
