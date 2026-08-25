#!/usr/bin/env python3
"""Freeze conservative current-primary candidates for unresolved multi-ticker issuers."""

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
OUTPUT = ROOT / "evidence/sec_broad_current_primary_recovery_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    readiness = pd.read_csv(READINESS, dtype={"cik10": str})
    recovery = pd.read_csv(RECOVERY, dtype={"cik10": str})
    candidates = readiness[
        readiness["queue_status"].eq("identity_recovery_required") & readiness["current_tickers"].notna()
    ].copy()
    candidates["recovered_symbol"] = candidates["current_tickers"].str.split("|").str[0].str.upper()
    all_symbols = recovery.assign(symbol=recovery["recovered_symbols"].fillna("").str.split("|"))[
        ["cik10", "symbol"]
    ].explode("symbol")
    duplicate_symbols = set(
        all_symbols.loc[all_symbols["symbol"].duplicated(keep=False) & all_symbols["symbol"].ne(""), "symbol"]
    )
    candidates["audit_status"] = "accepted_current_primary_candidate"
    candidates.loc[candidates["recovered_symbol"].isin(duplicate_symbols), "audit_status"] = "rejected_duplicate_symbol"
    candidates.loc[
        candidates["recovered_symbol"].str.contains(r"(?:[.-]P|[.-](?:WT|WS|W|U)$)", regex=True)
        | candidates["company_name_as_filed"].str.contains("COMMODITY TRUST", case=False, na=False),
        "audit_status",
    ] = "rejected_non_common_security"
    candidates["selection_basis"] = "sec_current_primary_ticker"
    queue = candidates[candidates["audit_status"].eq("accepted_current_primary_candidate")].copy()
    quarantine = candidates[~candidates["audit_status"].eq("accepted_current_primary_candidate")].copy()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    queue.to_csv(OUTPUT / "primary_symbol_queue.csv", index=False)
    quarantine.to_csv(OUTPUT / "quarantine.csv", index=False)
    result = {
        "experiment": "sec_broad_current_primary_recovery_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "targets": int(len(candidates)),
        "accepted": int(len(queue)),
        "quarantined": int(len(quarantine)),
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
