#!/usr/bin/env python3
"""Assemble the immutable observation packet for the residual sleeve's forward clock.

The decision half of this pair is `build_residual_sleeve_decision_packet_v1.py`.
This is the other half, and without it the first realization window on
2026-09-18 would close with nothing recorded.

A realization needs a total return for every security in the union of both
books.  The books are keyed by ticker and every price panel here is keyed by
`cik10`, with the ETF sleeve priced from a third file, so the decision packet
carries a `price_identity` map and this script reads it rather than inverting a
non-injective mapping a week after the fact.

An unpriced holding is an error, never a zero.  A missing price is a fact about
the data, and silently calling it a flat week would put a fabricated return into
a hash-chained log that cannot be corrected.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.forward_evidence import ForwardEvidenceError, canonical_bytes, file_hash

PROTOCOL_PATH = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
FORWARD = ROOT / "evidence/forward_sec_residual_controlled_sleeve_v1"
NARROW_PRICES = ROOT / "data/clean_weekly_prices_v2/weekly_adjusted_prices_clean.csv.gz"
BROAD_PRICES = ROOT / "data/broad_full_history_panel_v1/weekly_adjusted_prices.csv.gz"
ETF_PRICES = ROOT / "data/derived/20260808T212827Z-de103c2e063d6c4a/weekly_prices.csv"
CASH = "cash::USD"


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def load_prices(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0)
    frame.index = pd.to_datetime(frame.index)
    frame.columns = [str(c) for c in frame.columns]
    return frame.sort_index()


def weekly_return(frame: pd.DataFrame, key: str, week: pd.Timestamp) -> float | None:
    if key not in frame.columns or week not in frame.index:
        return None
    position = frame.index.get_loc(week)
    if position == 0:
        return None
    current = pd.to_numeric(frame.iloc[position][key], errors="coerce")
    prior = pd.to_numeric(frame.iloc[position - 1][key], errors="coerce")
    if pd.isna(current) or pd.isna(prior) or prior <= 0:
        return None
    return float(current / prior - 1.0)


def load_decision(decision_packet: Path, realization: str) -> dict[str, object]:
    """The packet, checked against the recorded decision whenever one exists."""
    packet = json.loads(decision_packet.read_text(encoding="utf-8"))
    basis = {k: v for k, v in packet.items() if k != "packet_sha256"}
    if packet.get("packet_sha256") != sha256_value(basis):
        raise ForwardEvidenceError(f"decision packet hash mismatch: {decision_packet}")
    log = FORWARD / "decisions.jsonl"
    if log.is_file():
        records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
        match = next((r for r in records if str(r.get("eligible_realization_date")) == realization), None)
        if match is None:
            raise ForwardEvidenceError(f"no recorded decision realizes on {realization}")
        if str(match.get("decision_packet_sha256")) != packet["packet_sha256"]:
            raise ForwardEvidenceError(
                "this packet is not the one that was recorded for that decision; "
                "the log is authoritative and the packet on disk has changed"
            )
    return packet


def build(packet: dict[str, object], week: pd.Timestamp) -> tuple[dict[str, float], dict[str, object]]:
    held = sorted(set(packet["control_target_weights"]) | set(packet["residual_target_weights"]))
    identity = dict(packet["price_identity"])
    narrow, broad, etf = load_prices(NARROW_PRICES), load_prices(BROAD_PRICES), load_prices(ETF_PRICES)

    returns: dict[str, float] = {}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for symbol in held:
        if symbol == CASH:
            continue
        entry = identity.get(symbol)
        if entry is None:
            missing.append(f"{symbol} (no price identity in the decision packet)")
            continue
        key, source = str(entry["key"]), str(entry["source"])
        candidates = ([("narrow", narrow), ("broad", broad)] if source == "sec_cik10"
                      else [("etf", etf)])
        for label, frame in candidates:
            value = weekly_return(frame, key, week)
            if value is not None:
                returns[symbol] = value
                resolved[symbol] = f"{label}:{key}"
                break
        else:
            missing.append(f"{symbol} ({source} key {key})")
    if missing:
        raise ForwardEvidenceError(
            f"{len(missing)} held securities have no price for the week ending "
            f"{week.date()}; a realization cannot be recorded from an incomplete "
            f"week: {', '.join(missing)}"
        )
    provenance = {
        "priced_securities": len(returns),
        "cash_positions": int(CASH in held),
        "sources": {
            label: sum(1 for v in resolved.values() if v.startswith(label))
            for label in ("narrow", "broad", "etf")
        },
        "best_week": max(returns.items(), key=lambda kv: kv[1]),
        "worst_week": min(returns.items(), key=lambda kv: kv[1]),
    }
    return returns, provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--realization-date", required=True, help="the completed Friday being realized")
    parser.add_argument("--decision-packet", default="",
                        help="defaults to the incoming packet for the Friday one week earlier")
    parser.add_argument("--rehearsal", action="store_true")
    args = parser.parse_args()

    week = pd.Timestamp(args.realization_date)
    if week.weekday() != 4:
        raise SystemExit("forward realization dates must be Fridays")
    decision_date = (week - timedelta(days=7)).date()

    default = FORWARD / ("rehearsal" if args.rehearsal else "incoming") / (
        f"{'rehearsal__' if args.rehearsal else ''}decision__{decision_date}.json")
    decision_packet = ROOT / args.decision_packet if args.decision_packet else default
    if not decision_packet.is_file():
        raise SystemExit(f"no decision packet at {decision_packet}")

    packet_in = load_decision(decision_packet, str(week.date()))
    returns, provenance = build(packet_in, week)

    out = FORWARD / ("rehearsal" if args.rehearsal else "incoming")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{'rehearsal__' if args.rehearsal else ''}observation__{week.date()}"
    manifest = {
        "manifest_type": "sec_residual_forward_observation_sources_v1",
        "realization_date": str(week.date()),
        "decision_packet": str(decision_packet.relative_to(ROOT)),
        "decision_packet_sha256": packet_in["packet_sha256"],
        "files": {
            str(p.relative_to(ROOT)): file_hash(p)
            for p in sorted([NARROW_PRICES, BROAD_PRICES, ETF_PRICES, Path(__file__).resolve()],
                            key=lambda q: str(q))
        },
    }
    manifest_path = out / f"{stem}__sources.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    basis = {
        "packet_type": "sec_residual_forward_observation_v1",
        "protocol_version": "sec_residual_controlled_sleeve_forward_v1",
        "realization_date": str(week.date()),
        "snapshot_id": f"residual-obs-{week.date()}-{file_hash(manifest_path)[:12]}",
        "observed_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_data_through": str(week.date()),
        "source_manifest": str(manifest_path.relative_to(ROOT)),
        "source_manifest_sha256": file_hash(manifest_path),
        "asset_total_returns": {k: v for k, v in sorted(returns.items())},
        "provenance": provenance,
    }
    if args.rehearsal:
        basis["rehearsal"] = True
    packet = {**basis, "packet_sha256": sha256_value(basis)}
    packet_path = out / f"{stem}.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "packet": str(packet_path.relative_to(ROOT)),
        "packet_sha256": packet["packet_sha256"],
        "realization_date": packet["realization_date"],
        "priced_securities": provenance["priced_securities"],
        "sources": provenance["sources"],
        "best": provenance["best_week"],
        "worst": provenance["worst_week"],
        "equal_weight_of_held_names": round(sum(returns.values()) / len(returns), 6),
        "rehearsal": bool(args.rehearsal),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
