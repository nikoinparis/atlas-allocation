#!/usr/bin/env python3
"""Build a public-inventory-validated Tiingo queue for Yahoo-failed recovered symbols."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
IDENTITY = ROOT / "evidence/sec_broad_recovered_identity_v2/recovered_single_symbol_queue.csv"
PRICE_RUNS = ROOT / "data/sec_broad_recovered_data_vintages"
INVENTORIES = ROOT / "data/tiingo_symbol_inventory_vintages"
OUTPUT = ROOT / "evidence/sec_broad_tiingo_queue_v2"
READINESS = ROOT / "evidence/sec_broad_universe_readiness_v2/issuer_acquisition_queue.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    identity = pd.read_csv(IDENTITY, dtype={"cik10": str})
    price_rows = pd.concat([
        pd.read_csv(path, dtype={"cik10": str})
        for path in sorted(PRICE_RUNS.glob("*/price_results.csv"))
    ], ignore_index=True)
    valid = price_rows["history_overlaps_eligible_interval"].astype(str).str.lower().eq("true")
    valid_ciks = set(price_rows.loc[valid, "cik10"])
    failed = identity[~identity["cik10"].isin(valid_ciks)].copy()
    # Use the current terminal-adjusted evaluation interval. The original
    # identity queue predates the SEC merger/delisting audit and can otherwise
    # demand prices after a company ceased to exist.
    readiness = pd.read_csv(READINESS, dtype={"cik10": str})[
        ["cik10", "first_recent_decision", "last_recent_decision", "recent_decision_rows"]
    ]
    failed = failed.drop(columns=["first_recent_decision", "last_recent_decision", "recent_decision_rows"]).merge(
        readiness, on="cik10", how="inner", validate="one_to_one"
    )
    failed["tiingo_symbol"] = failed["recovered_symbol"].astype(str).str.upper().str.replace(".", "-", regex=False)

    inventory_path = sorted(INVENTORIES.glob("*/supported_tickers.csv"))[-1]
    inventory = pd.read_csv(inventory_path, dtype=str)
    inventory["ticker"] = inventory["ticker"].astype(str).str.upper()
    inventory["startDate"] = pd.to_datetime(inventory["startDate"], utc=True, errors="coerce")
    inventory["endDate"] = pd.to_datetime(inventory["endDate"], utc=True, errors="coerce")
    inventory = inventory[inventory["assetType"].eq("Stock") & inventory["priceCurrency"].eq("USD")]
    merged = failed.merge(inventory, left_on="tiingo_symbol", right_on="ticker", how="left")
    first = pd.to_datetime(merged["first_recent_decision"], utc=True, errors="coerce")
    last = pd.to_datetime(merged["last_recent_decision"], utc=True, errors="coerce")
    merged["inventory_interval_overlap"] = (
        merged["startDate"].le(first + pd.Timedelta(days=10))
        & merged["endDate"].ge(last - pd.Timedelta(days=10))
    )
    candidates = (
        merged[merged["inventory_interval_overlap"]]
        .sort_values(["recent_decision_rows", "last_recent_decision", "cik10"], ascending=[False, False, True])
        .drop_duplicates("cik10")
        .rename(columns={"company_name_as_filed": "sec_company_name", "first_recent_decision": "first_eligible_decision", "last_recent_decision": "last_eligible_decision"})
    )
    unsupported = failed[~failed["cik10"].isin(candidates["cik10"])].copy()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUTPUT / "candidates.csv", index=False)
    unsupported.to_csv(OUTPUT / "inventory_unsupported.csv", index=False)
    result = {
        "experiment": "sec_broad_tiingo_queue_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "recovered_single_symbols": int(len(identity)),
        "yahoo_interval_valid": int(len(valid_ciks)),
        "yahoo_unresolved": int(len(failed)),
        "tiingo_inventory_candidates": int(len(candidates)),
        "inventory_unsupported": int(len(unsupported)),
        "inventory_source": str(inventory_path),
        "api_requests_per_candidate": 2,
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "candidates": sha256(OUTPUT / "candidates.csv"),
            "inventory_unsupported": sha256(OUTPUT / "inventory_unsupported.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
