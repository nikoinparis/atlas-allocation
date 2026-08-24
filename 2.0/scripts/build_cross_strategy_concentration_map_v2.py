#!/usr/bin/env python3
"""Freeze the symbol -> instrument/sector map used by concentration controls.

Version 2. Corrects an exchange-traded-product classification gap in v1.

Equity sectors come from the SEC broad research panel (SIC-derived divisions)
joined to tickers through the panel's own price-source inventory. Exchange
traded products carry no CIK in that inventory and are classified explicitly
here; their sector look-through weights live in the experiment config.

Nothing in this file evaluates performance. The map is a risk-control input.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICE_INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
PANEL = ROOT / "data/sec_broad_research_panel_v2/panel.csv.gz"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "data/cross_strategy_concentration_map_v2"

# Exchange traded products. These are not issuers; they are baskets, and they
# must be expanded before any sector concentration number means anything.
#
# v2 fix: v1 carried a short hand-written list that missed SLV, XLB, XLP, XLV,
# XLY, VTV, VWO, BIL and PDBC. A missing symbol silently falls through to the
# issuer bucket, which both overstates single-issuer concentration and
# understates fund concentration. In the residual/sector pair SLV alone reached
# 21.5% and 26.8% de-levered weight and was being counted as a company.
EXCHANGE_TRADED = {
    # SPDR sector funds
    "XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY",
    # broad US equity
    "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "IVV", "VUG", "VTV", "IWF", "IWD",
    "MDY", "IJH", "IJR", "RSP",
    # international
    "EFA", "VEA", "EWJ", "VWO", "EEM", "IEFA", "IEMG", "VXUS", "ACWI",
    # fixed income
    "AGG", "BND", "LQD", "HYG", "JNK", "TLT", "IEF", "SHY", "BIL", "TIP", "MUB",
    "SHV", "GOVT",
    # commodity and real asset
    "GLD", "SLV", "IAU", "USO", "UNG", "DBC", "PDBC", "GDX", "GDXJ", "VNQ", "IYR",
}

# Symbols that are not tradeable instruments at all. These are export artifacts
# and must never be silently absorbed into an issuer or sector bucket.
DATA_ARTIFACTS = {"PRICES"}

HISTORY_PATH = re.compile(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ticker_to_cik() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with PRICE_INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = HISTORY_PATH.search(row["path"])
            if match:
                mapping.setdefault(match.group(1).upper(), row["cik10"])
    return mapping


def cik_to_sector() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with gzip.open(PANEL, "rt") as handle:
        for row in csv.DictReader(handle):
            mapping.setdefault(row["cik10"], row["sector"])
    return mapping


def held_symbols() -> list[str]:
    document = json.loads(DASHBOARD.read_text())
    symbols: set[str] = set()
    for item in document["strategies"]:
        for record in item["records"]:
            for holding in record["holdings"]:
                symbol = holding["symbol"]
                if not symbol.startswith("cash"):
                    symbols.add(symbol.upper())
    return sorted(symbols)


def main() -> int:
    tickers = ticker_to_cik()
    sectors = cik_to_sector()
    rows = []
    for symbol in held_symbols():
        if symbol in DATA_ARTIFACTS:
            rows.append({
                "symbol": symbol,
                "instrument_type": "data_artifact",
                "cik10": "",
                "sector": "data_artifact",
                "source": "explicit_data_artifact_list",
            })
            continue
        if symbol in EXCHANGE_TRADED:
            rows.append({
                "symbol": symbol,
                "instrument_type": "exchange_traded_product",
                "cik10": "",
                "sector": "look_through_required",
                "source": "explicit_exchange_traded_list",
            })
            continue
        cik = tickers.get(symbol, "")
        sector = sectors.get(cik, "") if cik else ""
        rows.append({
            "symbol": symbol,
            "instrument_type": "equity",
            "cik10": cik,
            "sector": sector or "unclassified",
            "source": "sec_broad_research_panel_v2" if sector else "unresolved_identity",
        })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    map_path = OUTPUT / "sector_map.csv"
    with map_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "instrument_type", "cik10", "sector", "source"])
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    manifest = {
        "experiment": "cross_strategy_concentration_map_v2",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbols": len(rows),
        "counts_by_source": counts,
        "input_sha256": {
            "data/sec_broad_panel_inputs_v2/price_source_inventory.csv": sha256(PRICE_INVENTORY),
            "data/sec_broad_research_panel_v2/panel.csv.gz": sha256(PANEL),
            "dashboard/public/return-first-dashboard.json": sha256(DASHBOARD),
        },
        "artifact_sha256": {"sector_map.csv": sha256(map_path)},
        "sector_vintage_is_point_in_time": False,
        "sector_vintage_note": (
            "SIC-derived sector divisions reflect the current SEC company-facts vintage, not the "
            "sector recorded at each historical decision date. They are used only as a risk "
            "constraint and never as a return signal."
        ),
        "performance_evaluated": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
