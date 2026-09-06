#!/usr/bin/env python3
"""Audit price-series endpoints for early Tiingo delistings without inventing reasons."""

from __future__ import annotations

import json
import gzip
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "evidence/tiingo_delisted_authenticated_probe_v1/candidate_audit.csv"
OUTPUT = ROOT / "evidence/tiingo_terminal_outcomes_v1"
SEC_CACHE = ROOT / "data/sec_historical_identity_cache"


def completion_filing(cik10: str, last_price_date: pd.Timestamp) -> dict | None:
    path = SEC_CACHE / f"submissions_{cik10}.gz"
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()))
    recent = payload.get("filings", {}).get("recent", {})
    matches = []
    delisting_notices = []
    window_start = last_price_date - pd.Timedelta(days=365)
    window_end = last_price_date + pd.Timedelta(days=10)
    for index, form in enumerate(recent.get("form", [])):
        filing_date = pd.to_datetime(recent.get("filingDate", [])[index], utc=True, errors="coerce")
        if pd.isna(filing_date) or filing_date < window_start or filing_date > window_end:
            continue
        if form == "25-NSE":
            delisting_notices.append({
                "filing_date": filing_date,
                "accession": recent.get("accessionNumber", [])[index],
            })
            continue
        if form != "8-K":
            continue
        items = {item.strip() for item in str(recent.get("items", [])[index]).split(",")}
        matches.append({
            "filing_date": filing_date,
            "accession": recent.get("accessionNumber", [])[index],
            "primary_document": recent.get("primaryDocument", [])[index],
            "items": items,
        })
    if not matches:
        return None
    for match in matches:
        nearby = [
            value for value in delisting_notices
            if abs((value["filing_date"] - match["filing_date"]).days) <= 10
        ]
        match["nearby_25_nse"] = bool(nearby)
        match["notice_accessions"] = [value["accession"] for value in nearby]
    matches.sort(
        key=lambda value: (
            "2.01" in value["items"] and "3.01" in value["items"],
            "5.01" in value["items"] or value["nearby_25_nse"],
            value["filing_date"],
        ),
        reverse=True,
    )
    result = matches[0]
    return result


def main() -> int:
    candidates = pd.read_csv(CANDIDATES, dtype={"cik10": str})
    early = candidates[candidates["audit_status"] == "validated_early_delisting_needs_terminal_audit"].copy()
    rows = []
    for row in early.to_dict("records"):
        # Cached rows carry the absolute path of whichever container wrote them,
        # which is /project/... for some vintages and /workspace/2.0/... for others.
        path = Path(str(row["price_file"]))
        for prefix in ("/project/", "/workspace/2.0/"):
            if str(path).startswith(prefix):
                path = ROOT / path.relative_to(prefix)
                break
        frame = pd.read_csv(path, compression="gzip")
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        frame = frame.sort_values("date").dropna(subset=["date"])
        raw_last_price_timestamp = frame.iloc[-1]["date"]
        filing = completion_filing(str(row["cik10"]), raw_last_price_timestamp)
        core_completion_items = {"2.01", "3.01"}
        is_merger_completion = bool(
            filing and core_completion_items.issubset(filing["items"])
            and ("5.01" in filing["items"] or filing["nearby_25_nse"])
        )
        effective = frame
        if is_merger_completion:
            through_completion = frame[frame["date"] <= filing["filing_date"]]
            if not through_completion.empty:
                effective = through_completion
        close = pd.to_numeric(effective.get("close"), errors="coerce")
        adjusted = pd.to_numeric(effective.get("adjClose"), errors="coerce")
        volume = pd.to_numeric(effective.get("volume"), errors="coerce")
        final = effective.iloc[-1]
        last_price_timestamp = effective.iloc[-1]["date"]
        prior_5 = close.iloc[-6] if len(close) >= 6 else close.iloc[0]
        prior_21 = close.iloc[-22] if len(close) >= 22 else close.iloc[0]
        final_close = float(close.iloc[-1])
        rows.append({
            "cik10": row["cik10"],
            "ticker": row["tiingo_symbol"],
            "company_name": row["sec_company_name"],
            "provider_end_date": row["provider_end_date"],
            "raw_last_price_date": raw_last_price_timestamp.date().isoformat(),
            "last_price_date": last_price_timestamp.date().isoformat(),
            "last_close": final_close,
            "last_adjusted_close": float(adjusted.iloc[-1]),
            "last_volume": float(volume.iloc[-1]) if pd.notna(volume.iloc[-1]) else np.nan,
            "last_5_session_return": float(final_close / float(prior_5) - 1.0) if float(prior_5) != 0 else np.nan,
            "last_21_session_return": float(final_close / float(prior_21) - 1.0) if float(prior_21) != 0 else np.nan,
            "final_dividend": float(final.get("divCash", 0.0) or 0.0),
            "final_split_factor": float(final.get("splitFactor", 1.0) or 1.0),
            "sec_completion_filing_date": filing["filing_date"].date().isoformat() if filing else None,
            "sec_completion_accession": filing["accession"] if filing else None,
            "sec_completion_items": "|".join(sorted(filing["items"])) if filing else None,
            "sec_nearby_25_nse": filing["nearby_25_nse"] if filing else False,
            "sec_25_nse_accessions": "|".join(filing["notice_accessions"]) if filing else None,
            "terminal_reason": "merger_or_acquisition_completion" if is_merger_completion else "unknown_requires_classification",
            "terminal_return_available": is_merger_completion,
            "provisional_backtest_rule": "liquidate_at_last_tradable_close_then_cash" if is_merger_completion else "apply_minus_100_percent_sensitivity_if_unresolved",
        })
    outcomes = pd.DataFrame(rows).sort_values(["last_price_date", "ticker"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    outcomes.to_csv(OUTPUT / "terminal_outcomes.csv", index=False)
    result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "early_delistings": int(len(outcomes)),
        "known_terminal_reasons": int((outcomes["terminal_reason"] != "unknown_requires_classification").sum()) if len(outcomes) else 0,
        "terminal_returns_available": int(outcomes["terminal_return_available"].sum()) if len(outcomes) else 0,
        "strategy_testing_authorized": False,
        "required_sensitivity": [
            "base: liquidate at final observed close and hold cash until next decision",
            "adverse: apply -100% terminal return to every unresolved early delisting",
        ],
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# Tiingo terminal-outcome audit v1\n\nThe current authenticated batches contain **{len(outcomes)}** verified histories ending before the SEC staleness window. Acceptance-dated SEC metadata classifies **{result['known_terminal_reasons']}** as merger/acquisition completions. Classification requires 8-K Items 2.01 and 3.01 plus either Item 5.01 or a Form 25-NSE, all within ten days of the last trade. For these cases the reproducible rule is liquidation at the final tradable close followed by cash. Unresolved cases require a -100% terminal-return sensitivity. Full strategy testing remains blocked until all priority price batches and outcomes are audited.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
