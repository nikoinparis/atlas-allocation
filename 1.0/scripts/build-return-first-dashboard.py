#!/usr/bin/env python3
"""Build the Vercel dashboard snapshot from the frozen Version 2 strategy artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
V2 = ROOT / "2.0"
WEIGHTS = V2 / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
PRICES = V2 / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
RESULT = V2 / "evidence/forward_return_first_60_40_blend_v1/result.json"
STATUS = V2 / "evidence/forward_return_first_60_40_blend_v1/status.json"
CONFIG = V2 / "config/forward/return_first_60_40_blend_v1.json"
OUTPUT = APP / "public/return-first-dashboard.json"


def load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame.columns else "date" if "date" in frame.columns else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    return frame.set_index(date_column).sort_index()


def clean(value: float | int | None) -> float | int | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def main() -> int:
    weights = load_frame(WEIGHTS).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    prices = load_frame(PRICES).apply(pd.to_numeric, errors="coerce").reindex(weights.index)
    prices["cash::USD"] = 1.0
    prices = prices.reindex(columns=weights.columns)

    ordinary_returns = prices.pct_change()
    forward_returns = ordinary_returns.shift(-1)
    gross = (weights * forward_returns).sum(axis=1).fillna(0.0)
    turnover = 0.5 * weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 50.0 / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0

    records: list[dict[str, object]] = []
    previous = pd.Series(0.0, index=weights.columns)
    for date, row in weights.iterrows():
        delta = row - previous
        holdings = [
            {"symbol": str(symbol), "weight": clean(value), "change": clean(delta[symbol])}
            for symbol, value in row.items()
            if abs(float(value)) > 1e-10 or abs(float(delta[symbol])) > 1e-10
        ]
        holdings.sort(key=lambda item: abs(float(item["weight"] or 0.0)), reverse=True)
        changed = bool((delta.abs() > 1e-8).any())
        records.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "grossReturn": clean(gross.loc[date]),
                "netReturn": clean(net.loc[date]),
                "turnover": clean(turnover.loc[date]),
                "cost": clean(cost.loc[date]),
                "wealth": clean(wealth.loc[date]),
                "drawdown": clean(drawdown.loc[date]),
                "rebalance": changed,
                "holdings": holdings,
            }
        )
        previous = row

    result = json.loads(RESULT.read_text())
    status = json.loads(STATUS.read_text())
    config = json.loads(CONFIG.read_text())
    payload = {
        "strategy": {
            "id": result["candidate"],
            "name": "Return-First 60/40",
            "subtitle": "Frozen research candidate · 50 bps costs",
            "asOf": records[-1]["date"],
            "retrospectiveHoldout": {
                "cagr": result["holdout_50bps_cagr"],
                "sharpe": result["holdout_50bps_sharpe"],
                "maxDrawdown": result["holdout_50bps_drawdown"],
                "start": "2023-08-04",
            },
            "fullHistory": {
                "cagr": result["full_50bps_cagr"],
                "maxDrawdown": result["full_50bps_drawdown"],
                "start": records[0]["date"],
            },
            "forward": {
                "status": status["status"],
                "observedWeeks": status["observed_weeks"],
                "requiredWeeks": status["required_weeks"],
                "firstDecision": config["first_eligible_decision_date"],
                "firstRealization": config["first_eligible_realization_date"],
            },
            "disclosures": {
                "researchOnly": result["retrospective_research_only"],
                "liveTradingEnabled": result["live_trading_enabled"],
                "costBps": 50,
                "returnConvention": "Each weekly return is attributed to its strategy decision date and realized over the following weekly interval.",
            },
        },
        "records": records,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(records):,} weekly records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
