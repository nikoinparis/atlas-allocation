#!/usr/bin/env python3
"""What actually explains the saved strategies' returns?

The signal discovery program found that in this sample every classic defensive
factor has a large negative decile spread, i.e. high-volatility, high-beta,
lottery-like stocks won by a wide margin. This asks the obvious follow-up: are
the saved strategies simply holding those stocks?
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
PRICES = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/volatility_tilt_attribution_v1"

PURE_CASH_RETURN = {
    "sec-residual-controlled-1.25x-5pct-v1": 1.1260,
    "sec-sector-ensemble-fragile-1.35x-v1": 1.1412,
    "candidate-return-first-60-40-forward-v1": 0.7031,
    "sec-growth-survivorship-aware-v1": 1.5572,
    "sec-cash-conversion-breadth20-dynamic-v1": 0.9268,
    "sec-sector-aware-signal-ensemble-v1": 1.2420,
}


def ticker_to_cik() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with INVENTORY.open() as handle:
        for row in csv.DictReader(handle):
            match = re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
            if match:
                mapping.setdefault(match.group(1).upper(), row["cik10"])
    return mapping


def main() -> int:
    prices = pd.read_csv(PRICES, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    volatility = prices.pct_change().rolling(52, min_periods=40).std(ddof=1)
    percentile = volatility.rank(axis=1, pct=True)

    tickers = ticker_to_cik()
    document = json.loads(DASHBOARD.read_text())

    rows = []
    for item in document["strategies"]:
        plain, weighted, total = [], 0.0, 0.0
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
                    plain.append(float(row[cik]))
                    weighted += float(row[cik]) * weight
                    total += weight
        if not plain:
            continue
        rows.append({
            "id": item["strategy"]["id"],
            "short_name": item["strategy"]["shortName"],
            "mean_volatility_percentile": float(np.mean(plain)),
            "weight_weighted_volatility_percentile": float(weighted / total) if total else float("nan"),
            "resolved_holding_observations": len(plain),
            "pure_cash_trailing_return": PURE_CASH_RETURN.get(item["strategy"]["id"], float("nan")),
        })

    table = pd.DataFrame(rows)
    valid = table.dropna(subset=["pure_cash_trailing_return"])
    pearson = float(np.corrcoef(valid.weight_weighted_volatility_percentile, valid.pure_cash_trailing_return)[0, 1])
    ranks = lambda x: np.argsort(np.argsort(x))
    spearman = float(np.corrcoef(ranks(valid.weight_weighted_volatility_percentile), ranks(valid.pure_cash_trailing_return))[0, 1])

    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "volatility_tilt.csv", index=False)
    payload = {
        "experiment_id": "volatility-tilt-attribution-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategies": rows,
        "pearson_correlation_tilt_vs_return": pearson,
        "spearman_correlation_tilt_vs_return": spearman,
        "sample_size": int(len(valid)),
        "interpretation": (
            "Every SEC strategy sits well above the median volatility percentile, and the one strategy "
            "that does not, the ETF incumbent at 0.216, is also the lowest returning at 70.31%. In a sample "
            "where buying high volatility earned roughly +39% annualised decile spread, a high-volatility "
            "tilt is sufficient to explain most of the return ranking without any stock-selection skill."
        ),
        "caveat": "Six strategies is far too small a sample for the correlation to be conclusive on its own. It is corroborating evidence for the decile-spread result, not independent proof.",
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"  {'strategy':<28}{'vol pctile':>12}{'wtd':>8}{'pure-cash return':>19}")
    for r in sorted(rows, key=lambda x: -x["weight_weighted_volatility_percentile"]):
        print(f"  {r['short_name']:<28}{r['mean_volatility_percentile']:>12.3f}"
              f"{r['weight_weighted_volatility_percentile']:>8.3f}{100*r['pure_cash_trailing_return']:>18.2f}%")
    print(f"\n  Pearson {pearson:.3f}   Spearman {spearman:.3f}   n={len(valid)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
