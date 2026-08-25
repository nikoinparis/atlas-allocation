#!/usr/bin/env python3
"""A standing gate for volatility exposure.

Step 189 found that a high-volatility tilt alone explains most of the saved
strategies' return ranking, and that nothing in the existing battery measures it.
This turns that measurement into a gate any future candidate must pass, so the
exposure is chosen rather than inherited.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/volatility_tilt_gate_v1.json"
PRICES = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/volatility_tilt_gate_v1"
PUBLIC = ROOT / "dashboard/public/volatility-tilt.json"


def ticker_to_cik() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
            if match:
                mapping.setdefault(match.group(1).upper(), row["cik10"])
    return mapping


def verdict(tilt: float, config: dict) -> tuple[str, bool, bool]:
    rules, bands = config["gate_rules"], config["thresholds"]
    low, high = bands["neutral_band"]
    if tilt > rules["fails_above"]:
        return "fails_hard_maximum", False, True
    if tilt > rules["requires_declaration_above"]:
        return "requires_declaration_and_bear_evidence", False, True
    if tilt < low:
        return "defensive_tilt", True, False
    return "neutral", True, False


def main() -> int:
    config = json.loads(CONFIG.read_text())
    prices = pd.read_csv(PRICES, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    measure = config["measure"]
    volatility = prices.pct_change().rolling(measure["volatility_lookback_weeks"],
                                             min_periods=measure["minimum_weeks"]).std(ddof=1)
    percentile = volatility.rank(axis=1, pct=True)

    tickers = ticker_to_cik()
    document = json.loads(DASHBOARD.read_text())

    rows = []
    for item in document["strategies"]:
        weighted, total, samples = 0.0, 0.0, 0
        for record in item["records"]:
            stamp = pd.Timestamp(record["date"])
            if stamp not in percentile.index:
                continue
            row = percentile.loc[stamp]
            for holding in record["holdings"]:
                symbol = holding["symbol"].upper()
                if symbol.startswith("CASH"):
                    continue
                cik = tickers.get(symbol)
                if cik and cik in row.index and pd.notna(row[cik]):
                    weight = abs(float(holding["weight"]))
                    weighted += float(row[cik]) * weight
                    total += weight
                    samples += 1
        if not samples:
            continue
        tilt = weighted / total
        label, passes, needs_bear = verdict(tilt, config)
        rows.append({
            "id": item["strategy"]["id"],
            "short_name": item["strategy"]["shortName"],
            "volatility_tilt": float(tilt),
            "verdict": label,
            "passes_gate": bool(passes),
            "requires_bear_regime_evidence": bool(needs_bear),
            "bear_regime_evidence_available": False,
            "observations": samples,
        })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "volatility_tilt_gate.csv", index=False)
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": config["thresholds"],
        "strategies": rows,
        "any_strategy_passes": bool(any(r["passes_gate"] for r in rows)),
        "note": ("No SEC strategy can supply bear-regime evidence: the stock price panel starts "
                 "2022-12-02. Every tilted book therefore fails the evidence requirement by data "
                 "availability, not by construction."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    PUBLIC.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True))

    band = config["thresholds"]["neutral_band"]
    print(f"neutral band {band[0]:.2f}-{band[1]:.2f}   declare above {config['gate_rules']['requires_declaration_above']:.2f}   fail above {config['gate_rules']['fails_above']:.2f}\n")
    print(f"  {'strategy':<28}{'tilt':>8}  {'verdict':<40}{'gate'}")
    for r in sorted(rows, key=lambda x: -x["volatility_tilt"]):
        print(f"  {r['short_name']:<28}{r['volatility_tilt']:>8.3f}  {r['verdict']:<40}{'PASS' if r['passes_gate'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
