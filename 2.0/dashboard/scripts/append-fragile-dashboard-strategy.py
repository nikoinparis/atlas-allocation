#!/usr/bin/env python3
"""Append the exact-daily fragile 1.35x view without rebuilding archived prices."""

from __future__ import annotations

import copy
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path


APP = Path(__file__).resolve().parents[1]
V2 = APP.parent
OUTPUT = APP / "public/return-first-dashboard.json"
DAILY_PATH = V2 / "evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1/daily_path__1.35x.csv"
RESULT = V2 / "evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1/result.json"
BASE_ID = "sec-sector-aware-signal-ensemble-v1"
NEW_ID = "sec-sector-ensemble-fragile-1.35x-v1"


def friday(value: date) -> date:
    return value + timedelta(days=(4 - value.weekday()) % 7)


def main() -> int:
    bundle = json.loads(OUTPUT.read_text())
    base = next(item for item in bundle["strategies"] if item["strategy"]["id"] == BASE_ID)
    result = json.loads(RESULT.read_text())
    daily_rows = []
    weekly_returns: dict[str, float] = {}
    with DAILY_PATH.open(newline="") as handle:
        for row in csv.DictReader(handle):
            value = datetime.strptime(row["Date"], "%Y-%m-%d").date()
            net_return = float(row["net_return"])
            daily_rows.append({"date": value.isoformat(), "netReturn": net_return, "rebalance": False, "tradingDay": True})
            key = friday(value).isoformat()
            weekly_returns[key] = (1.0 + weekly_returns.get(key, 0.0)) * (1.0 + net_return) - 1.0

    previous: dict[str, float] = {}
    records = []
    wealth = 1.0
    peak = 1.0
    rebalance_dates = set()
    for source_record in base["records"]:
        current = {
            str(item["symbol"]): 1.35 * float(item.get("weight") or 0.0)
            for item in source_record["holdings"]
        }
        current["cash::USD"] = current.get("cash::USD", 0.0) - 0.35
        symbols = sorted(set(previous) | set(current))
        holdings = []
        turnover = 0.0
        for symbol in symbols:
            weight = current.get(symbol, 0.0)
            change = weight - previous.get(symbol, 0.0)
            turnover += abs(change)
            if abs(weight) > 1e-10 or abs(change) > 1e-10:
                holdings.append({"symbol": symbol, "weight": weight, "change": change})
        holdings.sort(key=lambda item: abs(float(item["weight"])), reverse=True)
        record_date = str(source_record["date"])
        net_return = weekly_returns.get(record_date, 0.0)
        wealth *= 1.0 + net_return
        peak = max(peak, wealth)
        rebalance = any(abs(float(item["change"])) > 1e-8 for item in holdings)
        if rebalance:
            rebalance_dates.add(record_date)
        records.append({
            "date": record_date,
            "grossReturn": net_return,
            "netReturn": net_return,
            "turnover": 0.5 * turnover,
            "cost": 0.0,
            "wealth": wealth,
            "drawdown": wealth / peak - 1.0,
            "rebalance": rebalance,
            "holdings": holdings,
        })
        previous = current
    for row in daily_rows:
        row["rebalance"] = row["date"] in rebalance_dates

    payload = copy.deepcopy(base)
    payload["strategy"] = {
        "id": NEW_ID,
        "name": "Sector Ensemble 1.35x — Fragile Return Ceiling",
        "shortName": "174.97% Fragile 1.35x",
        "subtitle": "Sector-aware filing ensemble · 1.35x exposure · 6% financing · failed issuer falsification",
        "badge": "FAILED ROBUSTNESS · 174.97%",
        "asOf": daily_rows[-1]["date"],
        "retrospectiveHoldout": {
            "cagr": result["daily_recent_cagr"],
            "sharpe": result["daily_recent_sharpe"],
            "maxDrawdown": result["daily_recent_drawdown"],
            "start": daily_rows[-252]["date"],
        },
        "fullHistory": {
            "cagr": result["daily_full_cagr"],
            "maxDrawdown": min(float(row["drawdown"]) for row in csv.DictReader(DAILY_PATH.open(newline=""))),
            "start": daily_rows[0]["date"],
        },
        "featuredMetric": {
            "label": "DAILY-AUDITED TRAILING 1Y",
            "value": result["daily_recent_cagr"],
            "note": "Return ceiling only · underlying five-issuer and bootstrap gates failed",
        },
        "forward": {
            "status": "FRAGILE DIAGNOSTIC · NOT ELIGIBLE",
            "observedWeeks": 0,
            "requiredWeeks": 52,
            "firstDecision": "Not scheduled",
            "firstRealization": "Not scheduled",
            "note": "The leverage layer passed its narrow daily checks, but the underlying strategy failed complete falsification.",
        },
        "disclosures": {
            "researchOnly": True,
            "liveTradingEnabled": False,
            "costBps": 50,
            "returnConvention": "Exact daily adjusted-close path; fixed 1.35x exposure, 6% annual financing and 25 bps exposure-change cost. Selection-contaminated.",
        },
    }
    payload["records"] = records
    payload["dailyRecords"] = daily_rows
    payload["validation"] = {
        "candidateLevelGatesPassed": result["candidate_level_gates_passed"],
        "underlyingStrategyFalsificationPassed": result["underlying_strategy_falsification_passed"],
        "completeFalsificationPassed": result["complete_falsification_passed"],
    }
    bundle["strategies"] = [item for item in bundle["strategies"] if item["strategy"]["id"] != NEW_ID]
    bundle["strategies"].insert(1, payload)
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(bundle, separators=(",", ":")) + "\n")
    temporary.replace(OUTPUT)
    print(f"wrote {OUTPUT} with {len(bundle['strategies'])} strategies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
