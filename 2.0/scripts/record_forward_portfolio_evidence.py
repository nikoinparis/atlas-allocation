#!/usr/bin/env python3
"""Append genuinely post-freeze decisions and returns for the frozen portfolio."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_covariance_portfolios_batch_06 as batch06
from src.systematic_trader.evaluation import performance_metrics
from src.systematic_trader.forward_evidence import (
    ForwardEvidenceError,
    append_record,
    canonical_bytes,
    file_hash,
    read_and_verify_log,
    verify_pinned_files,
)
from src.systematic_trader.portfolio_construction import PortfolioSpec
from src.systematic_trader.research_lab import StrategySpec
from src.systematic_trader.strategy_allocation import (
    cap_non_cash_weights,
    combine_dynamic_weight_histories,
)


PROTOCOL_PATH = ROOT / "config/forward/covariance_minimum_variance_v1.json"
PORTFOLIO_REGISTRY_PATH = ROOT / "research_registry/portfolio_candidates.json"
OUTPUT = ROOT / "evidence/forward_covariance_minimum_variance_v1"
ANCHOR_PATH = OUTPUT / "anchor.json"
DECISIONS_PATH = OUTPUT / "decisions.jsonl"
OBSERVATIONS_PATH = OUTPUT / "observations.jsonl"
STATUS_PATH = OUTPUT / "status.json"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_protocol() -> dict[str, object]:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    portfolio_path = ROOT / str(protocol["portfolio_manifest"])
    if file_hash(portfolio_path) != protocol["portfolio_manifest_sha256"]:
        raise ForwardEvidenceError("frozen portfolio manifest hash changed")
    verify_pinned_files(ROOT, protocol["pinned_files_sha256"])
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8"))
    if portfolio["portfolio_version"] != protocol["portfolio_version"]:
        raise ForwardEvidenceError("forward protocol references the wrong portfolio version")
    if portfolio["final"] or portfolio["approved_for_live_trading"]:
        raise ForwardEvidenceError("forward recorder cannot operate on a live-approved manifest")
    return protocol


def spec_from_protocol(spec: dict[str, object]) -> StrategySpec:
    return StrategySpec(
        signals=tuple(spec["signals"]),
        smoothing_weeks=int(spec["smoothing_weeks"]),
        portfolio=PortfolioSpec(
            method=str(spec["portfolio_method"]),
            top_n=int(spec["top_n"]),
            min_signal=float(spec["minimum_signal"]),
        ),
        cost_bps=float(spec["cost_bps"]),
        rebalance_frequency=str(spec["rebalance_frequency"]),
    )


def snapshot_manifest(snapshot_id: str) -> dict[str, object]:
    store = batch06.SnapshotStore(batch06.STORE_ROOT)
    manifest = next(
        (item for item in store.manifests() if item["snapshot_id"] == snapshot_id), None
    )
    if manifest is None:
        raise ForwardEvidenceError(f"unknown snapshot: {snapshot_id}")
    store.verify(snapshot_id)
    return manifest


def compute_snapshot_state(
    snapshot_id: str, protocol: dict[str, object]
) -> dict[str, object]:
    manifest = snapshot_manifest(snapshot_id)
    payload = batch06.STORE_ROOT / snapshot_id / "payload"
    all_assets = sorted(json.loads(batch06.UNIVERSE_PATH.read_text(encoding="utf-8"))["symbols"])
    dates, prices, preparation = batch06.prepare_weekly_adjusted_prices(
        payload / "prices.csv",
        observed_at_date=batch06.parse_utc(str(manifest["observed_at_utc"])).date(),
        start_date=batch06.date(2005, 1, 7),
        expected_symbols=all_assets,
    )
    log_returns = batch06.weekly_log_returns(dates, all_assets, prices)
    simple_returns = {
        day: {
            asset: math.expm1(value) if value is not None else None
            for asset, value in row.items()
        }
        for day, row in log_returns.items()
    }
    trend_signals, _ = batch06.reconstruct_five_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns
    )
    non_momentum, _, _ = batch06.reconstruct_non_momentum_signals(
        dates=dates, assets=all_assets, prices=prices, weekly_log_returns=log_returns,
        prices_path=payload / "prices.csv", actions_path=payload / "corporate_actions.csv",
    )
    specs = protocol["constituent_specs"]
    runs = {
        "trend_v4": batch06.run_experiment(
            spec=spec_from_protocol(specs["trend_v4"]), snapshot_id=snapshot_id,
            dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=trend_signals,
            prices=prices, simple_returns=simple_returns,
        ),
        "defensive": batch06.run_experiment(
            spec=spec_from_protocol(specs["defensive"]), snapshot_id=snapshot_id,
            dates=dates, assets=batch06.RISK_ASSETS, strategy_panels=non_momentum,
            prices=prices, simple_returns=simple_returns,
        ),
    }
    histories = {name: run["weights"] for name, run in runs.items()}
    sleeve_returns = batch06.sleeve_return_panel(runs)
    coefficients, allocation_audit = batch06.build_coefficients(
        dates, sleeve_returns, method="minimum_variance",
        lookback=int(protocol["portfolio_rules"]["covariance_lookback_weeks"]),
        shrinkage=float(protocol["portfolio_rules"]["diagonal_shrinkage"]),
    )
    weights = cap_non_cash_weights(
        combine_dynamic_weight_histories(dates, histories, coefficients),
        maximum_asset_weight=float(protocol["portfolio_rules"]["maximum_underlying_asset_weight"]),
    )
    return {
        "manifest": manifest,
        "dates": dates,
        "prices": prices,
        "simple_returns": simple_returns,
        "weights": weights,
        "coefficients": coefficients,
        "allocation_audit": allocation_audit,
        "preparation": preparation,
    }


def eligible_window_start(day: str) -> datetime:
    return datetime.combine(date.fromisoformat(day), time(21, 0), tzinfo=timezone.utc)


def manifest_in_weekly_window(manifest: dict[str, object], week: str) -> bool:
    observed = batch06.parse_utc(str(manifest["observed_at_utc"]))
    start = eligible_window_start(week)
    return start <= observed < start + timedelta(days=7)


def positive_weights(row: dict[str, float]) -> dict[str, float]:
    return {asset: weight for asset, weight in sorted(row.items()) if weight > 1e-15}


def initialize_anchor(protocol: dict[str, object]) -> dict[str, object]:
    portfolio = json.loads((ROOT / str(protocol["portfolio_manifest"])).read_text(encoding="utf-8"))
    snapshot_id = str(portfolio["source_snapshot_id"])
    state = compute_snapshot_state(snapshot_id, protocol)
    anchor_date = str(portfolio["source_data_through"])
    if anchor_date not in state["dates"]:
        raise ForwardEvidenceError("pre-freeze anchor date is absent from the frozen snapshot")
    expected = {
        "schema_version": 1,
        "portfolio_version": protocol["portfolio_version"],
        "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        "source_snapshot_id": snapshot_id,
        "source_snapshot_observed_at_utc": state["manifest"]["observed_at_utc"],
        "anchor_decision_date": anchor_date,
        "sleeve_coefficients": state["coefficients"][anchor_date],
        "target_weights": positive_weights(state["weights"][anchor_date]),
        "target_weights_sha256": sha256_value(positive_weights(state["weights"][anchor_date])),
        "purpose": "pre-freeze turnover anchor only; never counted as untouched evidence",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if ANCHOR_PATH.exists():
        existing = json.loads(ANCHOR_PATH.read_text(encoding="utf-8"))
        if existing != expected:
            raise ForwardEvidenceError("pre-freeze anchor changed")
    else:
        ANCHOR_PATH.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return expected


def available_manifests(snapshot_ids: list[str] | None) -> list[dict[str, object]]:
    store = batch06.SnapshotStore(batch06.STORE_ROOT)
    manifests = [item for item in store.manifests() if item["provider"] == "free_yahoo_via_yfinance"]
    if snapshot_ids:
        requested = set(snapshot_ids)
        manifests = [item for item in manifests if str(item["snapshot_id"]) in requested]
        missing = requested - {str(item["snapshot_id"]) for item in manifests}
        if missing:
            raise ForwardEvidenceError(f"requested snapshots do not exist: {sorted(missing)}")
    return sorted(manifests, key=lambda item: batch06.parse_utc(str(item["observed_at_utc"])))


def append_available_decisions(
    protocol: dict[str, object], anchor: dict[str, object], manifests: list[dict[str, object]]
) -> int:
    existing = read_and_verify_log(
        DECISIONS_PATH, date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    recorded = {str(row["decision_date"]) for row in existing}
    prior_weights = dict(existing[-1]["target_weights"]) if existing else dict(anchor["target_weights"])
    appended = 0
    state_cache: dict[str, dict[str, object]] = {}
    first = date.fromisoformat(str(protocol["first_eligible_decision_date"]))
    latest_observed = max(
        (batch06.parse_utc(str(item["observed_at_utc"])).date() for item in manifests),
        default=first - timedelta(days=1),
    )
    decision = first
    while decision <= latest_observed:
        day = decision.isoformat()
        if day not in recorded:
            eligible = [item for item in manifests if manifest_in_weekly_window(item, day)]
            chosen = eligible[0] if eligible else None
            if chosen is not None:
                snapshot_id = str(chosen["snapshot_id"])
                state = state_cache.setdefault(snapshot_id, compute_snapshot_state(snapshot_id, protocol))
                if day not in state["dates"] or str(state["preparation"]["weekly_end"]) < day:
                    raise ForwardEvidenceError(f"snapshot {snapshot_id} lacks completed decision week {day}")
                target = positive_weights(state["weights"][day])
                assets = set(prior_weights) | set(target)
                turnover = 0.5 * sum(abs(target.get(asset, 0.0) - prior_weights.get(asset, 0.0)) for asset in assets)
                payload = {
                    "record_type": "forward_decision",
                    "portfolio_version": protocol["portfolio_version"],
                    "decision_date": day,
                    "eligible_realization_date": (decision + timedelta(days=7)).isoformat(),
                    "decision_snapshot_id": snapshot_id,
                    "decision_snapshot_observed_at_utc": chosen["observed_at_utc"],
                    "source_data_through": state["preparation"]["weekly_end"],
                    "sleeve_coefficients": state["coefficients"][day],
                    "target_weights": target,
                    "target_weights_sha256": sha256_value(target),
                    "turnover_from_prior_saved_target": turnover,
                    "modeled_cost": turnover * float(protocol["cost_bps_per_unit_turnover"]) / 10_000.0,
                    "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
                    "execution_enabled": False,
                }
                record = append_record(
                    DECISIONS_PATH, payload, date_field="decision_date",
                    first_eligible_date=str(protocol["first_eligible_decision_date"]),
                )
                prior_weights = target
                recorded.add(day)
                existing.append(record)
                appended += 1
        decision += timedelta(days=7)
    return appended


def append_available_observations(
    protocol: dict[str, object], manifests: list[dict[str, object]]
) -> int:
    decisions = read_and_verify_log(
        DECISIONS_PATH, date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    observations = read_and_verify_log(
        OBSERVATIONS_PATH, date_field="realization_date",
        first_eligible_date=str(protocol["first_eligible_realization_date"]),
    )
    recorded = {str(row["realization_date"]) for row in observations}
    state_cache: dict[str, dict[str, object]] = {}
    appended = 0
    for decision_record in decisions:
        realization = str(decision_record["eligible_realization_date"])
        if realization in recorded:
            continue
        eligible = [item for item in manifests if manifest_in_weekly_window(item, realization)]
        chosen = eligible[0] if eligible else None
        if chosen is None:
            continue
        snapshot_id = str(chosen["snapshot_id"])
        state = state_cache.setdefault(snapshot_id, compute_snapshot_state(snapshot_id, protocol))
        if realization not in state["simple_returns"]:
            raise ForwardEvidenceError(f"snapshot {snapshot_id} lacks return week {realization}")
        target = dict(decision_record["target_weights"])
        asset_returns: dict[str, float] = {}
        gross = 0.0
        for asset, weight in target.items():
            if asset == "cash::USD":
                value = 0.0
            else:
                raw = state["simple_returns"][realization].get(asset)
                if raw is None:
                    raise ForwardEvidenceError(f"held asset {asset} is unpriced on {realization}")
                value = float(raw)
            asset_returns[asset] = value
            gross += float(weight) * value
        cost = float(decision_record["modeled_cost"])
        payload = {
            "record_type": "forward_observation",
            "portfolio_version": protocol["portfolio_version"],
            "decision_date": decision_record["decision_date"],
            "realization_date": realization,
            "decision_record_hash": decision_record["record_hash"],
            "target_weights_sha256": decision_record["target_weights_sha256"],
            "realization_snapshot_id": snapshot_id,
            "realization_snapshot_observed_at_utc": chosen["observed_at_utc"],
            "asset_returns": asset_returns,
            "gross_return": gross,
            "turnover": decision_record["turnover_from_prior_saved_target"],
            "cost": cost,
            "net_return": gross - cost,
            "forward_protocol_sha256": file_hash(PROTOCOL_PATH),
        }
        append_record(
            OBSERVATIONS_PATH, payload, date_field="realization_date",
            first_eligible_date=str(protocol["first_eligible_realization_date"]),
        )
        recorded.add(realization)
        appended += 1
    return appended


def update_status(protocol: dict[str, object], manifests: list[dict[str, object]]) -> dict[str, object]:
    decisions = read_and_verify_log(
        DECISIONS_PATH, date_field="decision_date",
        first_eligible_date=str(protocol["first_eligible_decision_date"]),
    )
    observations = read_and_verify_log(
        OBSERVATIONS_PATH, date_field="realization_date",
        first_eligible_date=str(protocol["first_eligible_realization_date"]),
    )
    values = [float(row["net_return"]) for row in observations]
    metrics = performance_metrics(values).to_dict() if values else {"observations": 0}
    required = int(protocol["required_untouched_weeks"])
    count = len(observations)
    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "portfolio_version": protocol["portfolio_version"],
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
        "latest_available_snapshot_id": manifests[-1]["snapshot_id"] if manifests else None,
        "latest_available_snapshot_observed_at_utc": manifests[-1]["observed_at_utc"] if manifests else None,
        "performance_metrics": metrics,
        "final": False,
        "approved_for_live_trading": False,
        "execution_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = "\n".join([
        "# Frozen Portfolio Forward Evidence", "",
        f"Portfolio: `{protocol['portfolio_version']}`", "",
        f"- Saved forward decisions: **{len(decisions)}**.",
        f"- Untouched realized weeks: **{count}/{required}**.",
        f"- Remaining required weeks: **{max(0, required - count)}**.",
        f"- Latest decision: **{status['latest_decision_date'] or 'none'}**.",
        f"- Latest realization: **{status['latest_realization_date'] or 'none'}**.",
        "- Execution enabled: **no**.", "",
        "Decision and observation logs are independently hash-chained. A missing weekly snapshot cannot be backfilled from a later vintage. No performance claim is available while the observation count is zero.", "",
    ])
    (OUTPUT / "report.md").write_text(report, encoding="utf-8")

    registry = json.loads(PORTFOLIO_REGISTRY_PATH.read_text(encoding="utf-8"))
    candidate = next(item for item in registry["candidates"] if item["portfolio_candidate_id"] == "portfolio-54d99427e079f726")
    candidate["forward_clock"] = {
        "first_eligible_decision_date": protocol["first_eligible_decision_date"],
        "first_eligible_realization_date": protocol["first_eligible_realization_date"],
        "required_weeks": required,
        "observed_weeks": count,
        "latest_realization_date": status["latest_realization_date"],
        "forward_protocol": str(PROTOCOL_PATH.relative_to(ROOT)),
        "status_file": str(STATUS_PATH.relative_to(ROOT)),
    }
    registry["last_updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    PORTFOLIO_REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot-id", action="append", dest="snapshot_ids")
    parser.add_argument("--initialize-only", action="store_true")
    args = parser.parse_args()
    protocol = load_protocol()
    anchor = initialize_anchor(protocol)
    manifests = available_manifests(args.snapshot_ids)
    appended_decisions = 0
    appended_observations = 0
    if not args.initialize_only:
        appended_decisions = append_available_decisions(protocol, anchor, manifests)
        appended_observations = append_available_observations(protocol, manifests)
    status = update_status(protocol, manifests)
    print(json.dumps({
        "appended_decisions": appended_decisions,
        "appended_observations": appended_observations,
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
