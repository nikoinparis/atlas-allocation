#!/usr/bin/env python3
"""Carry each dashboard strategy's daily path from its backtest end to the latest close.

The backtests in return-first-dashboard.json stop at their 2026-08 endpoints. This
appends one daily record per later trading day, taken from the what-if replay
(scripts/build_paper_replay_v1.py -> evidence/paper_replay_v1/daily_nav.csv), which
holds each strategy's last decided book unchanged and marks it at Yahoo daily closes.

So the dashboard's start-date simulator, calendar and daily tape can run from each
strategy's first backtest day through the latest close. The appended days are flagged
`heldBook: true` and are NOT the strategy's rules being re-run: no rebalancing, no
sleeve or leverage overlay, no costs. They are a retrospective replay, never forward
evidence.

Idempotent: earlier appended records are removed before the new ones are added.
Run from the 2.0 directory, after build_paper_replay_v1.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

APP = Path(__file__).resolve().parents[1]
V2 = APP.parent
DASHBOARD = APP / "public/return-first-dashboard.json"
REPLAY = V2 / "evidence/paper_replay_v1/daily_nav.csv"
NOTE = (" After the backtest end, daily returns come from a what-if replay that holds the last "
        "decided book unchanged at Yahoo daily closes (no rebalancing, overlays or costs); "
        "those days are a retrospective replay, not forward evidence.")


def main() -> int:
    payload = json.loads(DASHBOARD.read_text())
    replay = pd.read_csv(REPLAY)
    for item in payload["strategies"]:
        strategy = item["strategy"]
        original = [row for row in item["dailyRecords"] if not row.get("heldBook")]
        backtest_end = max(row["date"] for row in original if row.get("tradingDay"))
        rows = replay[(replay["strategy"] == strategy["id"]) & (replay["date"] > backtest_end)].sort_values("date")
        appended = [{"date": str(r.date), "netReturn": float(r.daily_return), "rebalance": False,
                     "tradingDay": True, "heldBook": True} for r in rows.itertuples()]
        item["dailyRecords"] = original + appended
        convention = strategy["disclosures"]["returnConvention"].replace(NOTE, "")
        strategy["disclosures"]["returnConvention"] = convention + (NOTE if appended else "")
        strategy["dailyThrough"] = item["dailyRecords"][-1]["date"]
        strategy["heldBookExtension"] = ({"backtestEnd": backtest_end, "from": appended[0]["date"],
                                          "through": appended[-1]["date"], "days": len(appended)}
                                         if appended else None)
        wealth = 1.0
        for row in item["dailyRecords"]:
            wealth *= 1.0 + (row["netReturn"] or 0.0)
        print(f"{strategy['id']:45s} {item['dailyRecords'][0]['date']} -> {strategy['dailyThrough']}"
              f"  +{len(appended):3d} days  growth of $1: {wealth:8.3f}")
    DASHBOARD.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
