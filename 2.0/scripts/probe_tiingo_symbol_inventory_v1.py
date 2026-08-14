#!/usr/bin/env python3
"""Acquire Tiingo's public symbol inventory and audit SEC historical coverage."""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/tiingo_delisted_price_probe_v1.json"
IDENTITY = ROOT / "evidence/sec_historical_identity_v1"
OUTPUT_ROOT = ROOT / "data/tiingo_symbol_inventory_vintages"
EVIDENCE = ROOT / "evidence/tiingo_delisted_coverage_probe_v1"


def tiingo_symbol(value: object) -> str:
    return str(value).strip().upper().replace(".", "-")


def latest(pattern: str) -> Path:
    values = sorted(ROOT.glob(pattern))
    if not values:
        raise RuntimeError(f"no artifact matches {pattern}")
    return values[-1]


def main() -> int:
    config = json.loads(CONFIG.read_text())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = OUTPUT_ROOT / f"{stamp}-tiingo-supported-symbols-v1"
    output.mkdir(parents=True, exist_ok=False)
    request = urllib.request.Request(config["supported_tickers_url"], headers={"User-Agent": "Portfolio Optimizer research"})
    with urllib.request.urlopen(request, timeout=120) as response:
        archive_bytes = response.read()
        status = int(response.status)
    archive_path = output / "supported_tickers.zip"
    archive_path.write_bytes(archive_bytes)
    with zipfile.ZipFile(archive_path) as archive:
        member = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        csv_bytes = archive.read(member)
    csv_path = output / "supported_tickers.csv"
    csv_path.write_bytes(csv_bytes)
    inventory = pd.read_csv(csv_path, dtype=str)
    inventory["ticker"] = inventory["ticker"].map(tiingo_symbol)
    inventory["startDate"] = pd.to_datetime(inventory["startDate"], utc=True, errors="coerce")
    inventory["endDate"] = pd.to_datetime(inventory["endDate"], utc=True, errors="coerce")
    scoped = inventory[
        inventory["assetType"].eq(config["inventory_scope"]["asset_type"])
        & inventory["priceCurrency"].eq(config["inventory_scope"]["price_currency"])
    ].copy()

    identities = pd.read_csv(IDENTITY / "combined_identity_map.csv", dtype={"cik10": str})
    membership = pd.read_csv(IDENTITY / "membership_with_candidate_symbols.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    usable = identities[identities["single_symbol_usable_for_price_probe"].astype(bool)].copy()
    usable["tiingo_symbol"] = usable["candidate_symbols"].map(tiingo_symbol)
    membership["tiingo_symbol"] = membership["candidate_symbols"].map(tiingo_symbol)
    intervals = membership.groupby("cik10", as_index=False).agg(
        first_eligible_decision=("decision_at", "min"), last_eligible_decision=("decision_at", "max")
    )
    candidates = usable.merge(intervals, on="cik10", how="left")

    by_symbol = {symbol: frame for symbol, frame in scoped.groupby("ticker")}

    def interval_match(row: pd.Series) -> bool:
        found = by_symbol.get(row["tiingo_symbol"])
        if found is None:
            return False
        return bool(((found["startDate"] <= row["last_eligible_decision"] + pd.Timedelta(days=10)) &
                     (found["endDate"] >= row["first_eligible_decision"])).any())

    candidates["inventory_interval_overlap"] = candidates.apply(interval_match, axis=1)
    candidates["inventory_status"] = candidates["inventory_interval_overlap"].map({True: "candidate_supported", False: "not_supported_for_eligible_interval"})

    def decision_match(row: pd.Series) -> bool:
        found = by_symbol.get(row["tiingo_symbol"])
        if found is None:
            return False
        decision = row["decision_at"]
        return bool(((found["startDate"] <= decision + pd.Timedelta(days=10)) & (found["endDate"] >= decision)).any())

    eligible_membership = membership[membership["single_symbol_usable_for_price_probe"].astype(bool)].copy()
    eligible_membership["tiingo_inventory_covers_execution"] = eligible_membership.apply(decision_match, axis=1)
    coverage = membership.groupby("decision_at", as_index=False).agg(members=("cik10", "nunique"))
    supported = eligible_membership[eligible_membership["tiingo_inventory_covers_execution"]].groupby("decision_at")["cik10"].nunique()
    coverage["inventory_supported_members"] = coverage["decision_at"].map(supported).fillna(0).astype(int)
    coverage["inventory_coverage"] = coverage["inventory_supported_members"] / coverage["members"]

    yahoo_price = latest("data/sec_recovered_price_probe_vintages/*/price_probe_results.csv")
    yahoo = pd.read_csv(yahoo_price)
    recovered = candidates[candidates["symbol_source"].isin(["last_filing_inline_xbrl", "last_filing_instance_xbrl"])]
    recovered = recovered.merge(yahoo[["ticker", "status"]], left_on="candidate_symbols", right_on="ticker", how="left")
    yahoo_failures = recovered[~recovered["status"].eq("ok")]
    rescued = yahoo_failures[yahoo_failures["inventory_interval_overlap"]]

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(EVIDENCE / "identity_inventory_matches.csv", index=False)
    eligible_membership.to_csv(EVIDENCE / "membership_inventory_coverage.csv", index=False)
    coverage.to_csv(EVIDENCE / "coverage_by_decision.csv", index=False)
    yahoo_failures.to_csv(EVIDENCE / "yahoo_failures_tiingo_candidates.csv", index=False)
    recent = coverage[coverage["decision_at"] >= pd.Timestamp("2023-01-01", tz="UTC")]
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "inventory_vintage": str(output),
        "inventory_rows": int(len(inventory)),
        "usd_stock_inventory_rows": int(len(scoped)),
        "usable_sec_identities": int(len(candidates)),
        "identities_with_interval_overlapping_tiingo_symbol": int(candidates["inventory_interval_overlap"].sum()),
        "identity_candidate_rate": float(candidates["inventory_interval_overlap"].mean()),
        "yahoo_failed_identities": int(len(yahoo_failures)),
        "yahoo_failed_identities_with_tiingo_candidate": int(len(rescued)),
        "yahoo_failure_rescue_candidate_rate": float(len(rescued) / len(yahoo_failures)) if len(yahoo_failures) else 0.0,
        "recent_min_inventory_coverage": float(recent["inventory_coverage"].min()),
        "latest_inventory_coverage": float(coverage.iloc[-1]["inventory_coverage"]),
        "api_token_required_for_price_validation": True,
        "strategy_testing_authorized": False,
        "next_gate": "fetch Tiingo metadata and adjusted histories for recovered/Yahoo-failed candidates; verify issuer name and date overlap",
    }
    manifest = {
        "vintage_id": output.name,
        "created_at_utc": result["created_at_utc"],
        "source_url": config["supported_tickers_url"],
        "http_status": status,
        "zip_bytes": len(archive_bytes),
        "zip_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "csv_bytes": len(csv_bytes),
        "csv_sha256": hashlib.sha256(csv_bytes).hexdigest(),
        "result": result,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (EVIDENCE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    report = f"""# Tiingo public-inventory coverage probe v1

Tiingo's public inventory contains **{result['usd_stock_inventory_rows']:,}** USD stock rows. It has date-overlapping symbol candidates for **{result['identities_with_interval_overlapping_tiingo_symbol']:,} of {result['usable_sec_identities']:,}** usable SEC identities ({result['identity_candidate_rate']:.1%}).

Most importantly, it can potentially rescue **{result['yahoo_failed_identities_with_tiingo_candidate']:,} of {result['yahoo_failed_identities']:,}** SEC identities whose recovered symbols failed at Yahoo ({result['yahoo_failure_rescue_candidate_rate']:.1%}). Inventory coverage is at least **{result['recent_min_inventory_coverage']:.1%}** from 2023 onward and **{result['latest_inventory_coverage']:.1%}** at the latest decision.

These are candidates, not validated prices. A free Tiingo API token is required to retrieve metadata and adjusted histories, verify issuer identity, and measure actual decision-date coverage. No strategy test is authorized yet.
"""
    (EVIDENCE / "report.md").write_text(report)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
