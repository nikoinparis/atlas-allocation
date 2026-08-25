#!/usr/bin/env python3
"""Consolidate recovered SEC symbols and freeze an unambiguous price queue."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"
VINTAGES = ROOT / "data/sec_broad_identity_vintages"
OUTPUT = ROOT / "evidence/sec_broad_recovered_identity_v2"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    paths = sorted(VINTAGES.glob("*/symbol_recovery.csv"))
    if not paths:
        raise RuntimeError("no broad identity-recovery batches found")
    recovered = pd.concat([pd.read_csv(path, dtype={"cik10": str}) for path in paths], ignore_index=True)
    if recovered["cik10"].duplicated().any():
        raise RuntimeError("identity recovery batches contain duplicate CIKs")
    readiness = pd.read_csv(READINESS, dtype={"cik10": str})
    identity = readiness[readiness["queue_status"].eq("identity_recovery_required")][
        ["cik10", "first_recent_decision", "last_recent_decision", "recent_decision_rows"]
    ]
    recovered = recovered.merge(identity, on="cik10", how="left", validate="one_to_one")
    recovered["symbol_count"] = recovered["recovered_symbols"].fillna("").map(
        lambda value: len([item for item in str(value).split("|") if item])
    )
    single = recovered[recovered["symbol_count"].eq(1)].copy()
    single["recovered_symbol"] = single["recovered_symbols"].astype(str)
    duplicate_symbols = set(single.loc[single["recovered_symbol"].duplicated(keep=False), "recovered_symbol"])
    single["symbol_unique_across_recovered_ciks"] = ~single["recovered_symbol"].isin(duplicate_symbols)
    queue = single[single["symbol_unique_across_recovered_ciks"]].copy()
    quarantine = recovered[~recovered["cik10"].isin(queue["cik10"])].copy()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    recovered.to_csv(OUTPUT / "all_recovery_results.csv", index=False)
    queue.to_csv(OUTPUT / "recovered_single_symbol_queue.csv", index=False)
    quarantine.to_csv(OUTPUT / "identity_quarantine.csv", index=False)
    result = {
        "experiment": "sec_broad_recovered_identity_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "recovery_batches": int(len(paths)),
        "targets": int(len(recovered)),
        "explicit_symbol_recoveries": int(recovered["recovery_status"].eq("xbrl_symbol_recovered").sum()),
        "single_symbol_recoveries": int(len(single)),
        "unique_single_symbol_queue": int(len(queue)),
        "duplicate_symbol_ciks_quarantined": int((single["symbol_unique_across_recovered_ciks"] == False).sum()),
        "other_identity_cases_quarantined": int(len(quarantine) - (single["symbol_unique_across_recovered_ciks"] == False).sum()),
        "price_testing_authorized": True,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "all_recovery_results": sha256(OUTPUT / "all_recovery_results.csv"),
            "recovered_single_symbol_queue": sha256(OUTPUT / "recovered_single_symbol_queue.csv"),
            "identity_quarantine": sha256(OUTPUT / "identity_quarantine.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
