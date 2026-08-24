#!/usr/bin/env python3
"""Audit broad Tiingo histories and emit exact covered company-decision keys."""

from __future__ import annotations

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.tiingo_delisted import issuer_name_match, issuer_name_score


CACHE = ROOT / "data/sec_broad_tiingo_cache_v2"
LEGACY_CACHE = ROOT / "data/tiingo_delisted_price_probe_cache_v1"
CANDIDATES = ROOT / "evidence/sec_broad_tiingo_queue_v2/candidates.csv"
SUPPLEMENT = ROOT / "evidence/sec_broad_tiingo_multi_symbol_supplement_v2/candidates.csv"
MEMBERSHIP = ROOT / "evidence/sec_broad_universe_readiness_v2/recent_membership_readiness.csv"
OUTPUT = ROOT / "evidence/sec_broad_tiingo_audit_v2"
TERMINALS = ROOT / "evidence/sec_broad_terminal_membership_v2/sec_terminal_membership.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    candidate_paths = [CANDIDATES] + ([SUPPLEMENT] if SUPPLEMENT.exists() else [])
    candidates = pd.concat(
        [pd.read_csv(path, dtype={"cik10": str}) for path in candidate_paths], ignore_index=True
    ).drop_duplicates("cik10", keep="first")
    candidate_ciks = set(candidates["cik10"].str.zfill(10))
    confirmed_terminal_ciks: set[str] = set()
    if TERMINALS.exists():
        terminal_rows = pd.read_csv(TERMINALS, dtype={"cik10": str})
        confirmed_terminal_ciks = set(terminal_rows["cik10"].str.zfill(10))
    # Reuse prior authenticated probes when they belong to this exact broad
    # queue.  New broad-cache results take precedence for the same issuer.
    ordered_paths = [
        path
        for cache_root in (LEGACY_CACHE, CACHE)
        for path in sorted(cache_root.glob("*/result.json"))
    ]

    def load_result(path: Path) -> tuple[str, Path, dict] | None:
        try:
            result = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        cik10 = str(result.get("cik10", "")).zfill(10)
        if not result.get("terminal") or cik10 not in candidate_ciks:
            return None
        return cik10, path, result

    # Each result is independent. Concurrent reads avoid serial stalls on
    # cloud-backed workspaces; assignment order still preserves broad-v2
    # precedence over the legacy cache for duplicate CIKs.
    with ThreadPoolExecutor(max_workers=16) as executor:
        loaded = executor.map(load_result, ordered_paths)
        result_records: dict[str, tuple[Path, dict]] = {
            cik10: (path, result)
            for item in loaded if item is not None
            for cik10, path, result in [item]
        }
    rows = []
    for cik10, (path, result) in sorted(result_records.items()):
        result["cik10"] = cik10
        result["cache_source"] = "broad_v2" if CACHE in path.parents else "legacy_authenticated_v1"
        price_path = path.parent / "prices.csv.gz"
        if price_path.exists():
            result["price_file"] = str(price_path)
        first_eligible = pd.to_datetime(result.get("first_eligible_decision"), utc=True, errors="coerce")
        last_eligible = pd.to_datetime(result.get("last_eligible_decision"), utc=True, errors="coerce")
        first_price = pd.to_datetime(result.get("first_price_date"), utc=True, errors="coerce")
        last_price = pd.to_datetime(result.get("last_price_date"), utc=True, errors="coerce")
        name_ok = issuer_name_match(result.get("sec_company_name"), result.get("provider_name"))
        covers_first = bool(pd.notna(first_price) and first_price <= first_eligible + pd.Timedelta(days=10))
        covers_last = bool(pd.notna(last_price) and last_price >= last_eligible - pd.Timedelta(days=10))
        if not name_ok:
            status = "rejected_name_mismatch_or_ticker_reuse"
        elif not covers_first:
            status = "rejected_missing_start"
        elif int(result.get("price_rows") or 0) < 2:
            status = "rejected_insufficient_prices"
        elif covers_last:
            status = "validated_history_through_last_decision"
        elif cik10 in confirmed_terminal_ciks:
            status = "validated_sec_confirmed_early_delisting"
        else:
            status = "validated_early_delisting_needs_terminal_audit"
        rows.append({
            **result,
            "strict_issuer_name_score": issuer_name_score(result.get("sec_company_name"), result.get("provider_name")),
            "strict_issuer_name_match": name_ok,
            "covers_first_eligible_decision": covers_first,
            "covers_last_eligible_decision": covers_last,
            "audit_status": status,
        })
    audit = pd.DataFrame(rows)
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    valid_statuses = {"validated_history_through_last_decision", "validated_sec_confirmed_early_delisting"}
    key_rows = []
    for row in audit[audit["audit_status"].isin(valid_statuses)].to_dict("records"):
        last_price = pd.to_datetime(row["last_price_date"], utc=True)
        eligible = membership[
            membership["cik10"].eq(str(row["cik10"]).zfill(10))
            & membership["decision_at"].le(last_price + pd.Timedelta(days=10))
        ]
        key_rows.extend({"decision_at": value, "cik10": str(row["cik10"]).zfill(10)} for value in eligible["decision_at"])
    keys = pd.DataFrame(key_rows, columns=["decision_at", "cik10"]).drop_duplicates()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUTPUT / "candidate_audit.csv", index=False)
    keys.to_csv(OUTPUT / "validated_price_decision_keys.csv", index=False)
    counts = audit["audit_status"].value_counts().to_dict() if not audit.empty else {}
    result = {
        "experiment": "sec_broad_tiingo_audit_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "terminal_cached_candidates": int(len(audit)),
        "legacy_authenticated_candidates_reused": int(audit["cache_source"].eq("legacy_authenticated_v1").sum()) if not audit.empty else 0,
        "validated_candidates": int(audit["audit_status"].isin(valid_statuses).sum()) if not audit.empty else 0,
        "validated_decision_keys": int(len(keys)),
        "early_delistings_requiring_terminal_audit": int(audit["audit_status"].eq("validated_early_delisting_needs_terminal_audit").sum()) if not audit.empty else 0,
        "status_counts": {str(key): int(value) for key, value in counts.items()},
        "strategy_testing_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "candidate_audit": sha256(OUTPUT / "candidate_audit.csv"),
            "validated_price_decision_keys": sha256(OUTPUT / "validated_price_decision_keys.csv"),
        },
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
