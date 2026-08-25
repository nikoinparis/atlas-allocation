#!/usr/bin/env python3
"""Freeze one SEC-reported primary common-symbol candidate per multi-symbol issuer."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"
RECOVERY = ROOT / "evidence/sec_broad_recovered_identity_v2/all_recovery_results.csv"
OUTPUT = ROOT / "evidence/sec_broad_multi_symbol_primary_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(symbol: str) -> str:
    return str(symbol).strip().upper().replace("/", ".")


def main() -> int:
    readiness = pd.read_csv(READINESS, dtype={"cik10": str})
    recovery = pd.read_csv(RECOVERY, dtype={"cik10": str})
    unresolved = readiness[readiness["queue_status"].eq("identity_recovery_required")][
        ["cik10", "current_tickers", "first_recent_decision", "last_recent_decision", "recent_decision_rows"]
    ]
    frame = recovery.merge(unresolved, on="cik10", how="inner", validate="one_to_one")
    # The recovery evidence already carries the original dates; use the latest
    # readiness dates as the canonical interval after the merge.
    for column in ("first_recent_decision", "last_recent_decision", "recent_decision_rows"):
        latest = f"{column}_y"
        original = f"{column}_x"
        if latest in frame:
            frame[column] = frame[latest]
        elif original in frame:
            frame[column] = frame[original]
    frame = frame[frame["symbol_count"].ge(2)].copy()
    frame["recovered_symbol"] = frame["recovered_symbols"].fillna("").map(
        lambda value: normalize(str(value).split("|")[0])
    )
    frame["current_primary"] = frame["current_tickers"].fillna("").map(
        lambda value: normalize(str(value).split("|")[0]) if str(value) else ""
    )
    frame["selection_basis"] = frame.apply(
        lambda row: "sec_current_primary_matches_xbrl_first"
        if row["current_primary"] == row["recovered_symbol"]
        else "sec_xbrl_first_reported_symbol",
        axis=1,
    )
    # Exclude obvious debt/preferred identifiers. Warrants normally appear
    # after the issuer's common symbol, which is why only the first SEC XBRL
    # symbol is eligible here.
    frame["candidate_format_valid"] = frame["recovered_symbol"].map(
        lambda value: bool(value)
        and not bool(re.search(r"\d", value))
        and ".P" not in value
        and "-P" not in value
        and not bool(re.search(r"(?:[.-](?:WT|WS|W|U))$", value))
    )
    duplicate = set(
        frame.loc[frame["recovered_symbol"].duplicated(keep=False), "recovered_symbol"]
    )
    frame["candidate_unique_across_ciks"] = ~frame["recovered_symbol"].isin(duplicate)
    frame["audit_status"] = "accepted_primary_candidate"
    frame.loc[~frame["candidate_format_valid"], "audit_status"] = "rejected_security_format"
    frame.loc[~frame["candidate_unique_across_ciks"], "audit_status"] = "rejected_duplicate_symbol"
    queue = frame[frame["audit_status"].eq("accepted_primary_candidate")].copy()
    quarantine = frame[~frame["audit_status"].eq("accepted_primary_candidate")].copy()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    queue.to_csv(OUTPUT / "primary_symbol_queue.csv", index=False)
    quarantine.to_csv(OUTPUT / "quarantine.csv", index=False)
    result = {
        "experiment": "sec_broad_multi_symbol_primary_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "multi_symbol_targets": int(len(frame)),
        "accepted_primary_candidates": int(len(queue)),
        "quarantined": int(len(quarantine)),
        "selection_basis_counts": {str(k): int(v) for k, v in queue["selection_basis"].value_counts().items()},
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "primary_symbol_queue": sha256(OUTPUT / "primary_symbol_queue.csv"),
            "quarantine": sha256(OUTPUT / "quarantine.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
