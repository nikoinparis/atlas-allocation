#!/usr/bin/env python3
"""Extract point-in-time fundamentals from the SEC company-facts cache.

Every XBRL fact carries the date it was filed. Only facts already filed by a
given week may be used for that week's signal, which is what keeps a restatement
published later from reaching backwards into an earlier decision.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/sec_recent_companyfacts_cache_v1"
OUTPUT = ROOT / "data/fundamental_signal_panel_v1"

# concept -> candidate XBRL tags, first match wins
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "gross_profit": ["GrossProfit"],
    "assets": ["Assets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "liabilities": ["Liabilities"],
    "shares": ["CommonStockSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic",
               "WeightedAverageNumberOfDilutedSharesOutstanding"],
}


def latest_facts(document: dict, cik: str, sink: list, cutoff: str) -> None:
    """Append (cik, concept, filed, value) rows. Only facts filed on or after the
    cutoff are kept; older vintages cannot matter for a panel starting in 2022."""
    us = document.get("facts", {}).get("us-gaap", {})
    for concept, tags in CONCEPTS.items():
        for tag in tags:
            block = us.get(tag)
            if not block:
                continue
            units = block.get("units", {})
            series = units.get("USD") or units.get("shares") or next(iter(units.values()), [])
            for item in series:
                filed = item.get("filed")
                value = item.get("val")
                if filed is None or value is None or filed < cutoff:
                    continue
                sink.append((cik, concept, filed, float(value)))
            break


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    files = sorted(CACHE.glob("companyfacts_*.gz"))
    cutoff = "2021-01-01"
    sink: list = []
    for index, path in enumerate(files, 1):
        cik = path.stem.replace("companyfacts_", "")
        try:
            with gzip.open(path, "rt") as handle:
                document = json.load(handle)
        except Exception:
            continue
        latest_facts(document, cik, sink, cutoff)
        if index % 750 == 0:
            print(f"  {index}/{len(files)} filings read, {len(sink):,} facts", flush=True)

    panel = pd.DataFrame(sink, columns=["cik10", "concept", "filed", "value"])
    panel["filed"] = pd.to_datetime(panel["filed"])
    panel = panel.sort_values("filed").drop_duplicates(["cik10", "concept", "filed"], keep="last")
    panel.to_csv(OUTPUT / "facts.csv.gz", index=False, compression="gzip")
    print(f"\nrows: {len(panel):,}  issuers: {panel.cik10.nunique():,}  concepts: {panel.concept.nunique()}", flush=True)
    print(panel.groupby("concept").size().to_string(), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
