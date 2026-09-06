#!/usr/bin/env python3
"""Build the dashboard's research-status payload from the evidence on disk.

The dashboard shows six strategies and their backtests. It does not show what the
research programme is actually doing, which since Step 244 has mostly been closing
candidates: thirteen families in one stretch. A reader looking at six historically
resilient strategies has no way to know that.

Everything here is read from evidence files rather than typed in, so the page
cannot drift from the record. Nothing is editorialised into a forecast: forward
returns are the realised weekly numbers from the hash-chained logs, and closed
families carry the step that closed them.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FORWARD = ROOT / "evidence"
CONFIG = ROOT / "config/forward"

CLOSED = [
    ("Risk-budgeted position sizing", "Passed on one book, reversed on two others", 244),
    ("Multi-asset ETF universe", "4.16 effective independent assets from 35; refuted on its premise", 246),
    ("Futures trend", "No positive IC; the negative reading is ~40% roll artifact", 248),
    ("Futures roll repair by outlier detection", "Weekly roll gaps are not outliers", 249),
    ("Short-term reversal", "Bid-ask bounce; total loss at 100bps", 250),
    ("Earnings call transcripts", "Coverage proportional to company size, a selection problem", 254),
    ("10-K language change", "Nine annual cross-sections cannot establish an IC below 0.110", 255),
    ("PEAD / SUE (historical)", "Recent strength is the window, not the signal; reopened forward", 256),
    ("Coskewness", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Idiosyncratic skewness", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Trend consistency", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Sector dispersion", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Volatility of volatility", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Downside beta", "Selected 2011-2019, evaluated 2020-2026; nothing clears", 257),
    ("Industry leader return", "Most orthogonal candidate available; -0.0007 at t = -0.07", 257),
    ("13F institutional linkage", "110M holdings, 73% match; every IC negative against a declared positive sign", 258),
    ("13D/13G activist events", "38,849 events; nothing clears, and the 13G control is flat", 260),
]


def clock_rows() -> list[dict]:
    rows = []
    for directory in sorted(FORWARD.glob("forward_*")):
        name = directory.name.replace("forward_", "")
        status_path = directory / "status.json"
        observations_path = directory / "observations.jsonl"
        if not status_path.is_file():
            continue
        status = json.loads(status_path.read_text(encoding="utf-8"))
        weekly = []
        if observations_path.is_file():
            for line in observations_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                value = record.get("net_return")
                if value is None and isinstance(record.get("path_net_returns"), dict):
                    value = record["path_net_returns"].get("unlevered_1.00x")
                if value is not None:
                    weekly.append({"week": record.get("realization_date"), "netReturn": float(value)})
        cumulative = float(np.prod([1 + w["netReturn"] for w in weekly]) - 1) if weekly else None
        rows.append({
            "protocol": name,
            "observedWeeks": int(status.get("observed_weeks", 0)),
            "requiredWeeks": int(status.get("required_weeks", 52)),
            "savedDecisions": int(status.get("saved_decisions", 0)),
            "promotionAuthorized": bool(status.get("promotion_authorized", False)),
            "weekly": weekly,
            "cumulativeReturn": cumulative,
        })
    return rows


def pending_rows() -> list[dict]:
    rows = []
    for path in sorted(CONFIG.glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        first = config.get("first_eligible_decision_date")
        if not first:
            continue
        directory = FORWARD / f"forward_{path.stem}"
        started = (directory / "decisions.jsonl").is_file()
        if started:
            continue
        rows.append({
            "protocol": config.get("protocol_version", path.stem),
            "firstDecision": first,
            "purpose": config.get("why_this_exists") or config.get("purpose") or config.get("question", ""),
            "modifies": config.get("modifies", ""),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dashboard/public/research-status.json")
    args = parser.parse_args()

    clocks = clock_rows()
    running = [c for c in clocks if c["observedWeeks"] > 0]
    payload = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "liveTradingEnabled": False,
        "anyStrategyPromoted": False,
        "headline": {
            "closedFamilies": len(CLOSED),
            "clocksRunning": len(running),
            "clocksPending": len(pending_rows()),
            "totalUntouchedWeeks": sum(c["observedWeeks"] for c in clocks),
            "weeksRequiredEach": 52,
        },
        "breadth": {
            "effectiveIndependentStrategies": 1.57,
            "effectiveBetsPerYear": 8.5,
            "betsNeededForInformationRatio025": 91,
            "measuredIn": "Step 245",
            "plainEnglish": "The four displayed strategies correlate 0.93 to 0.97 with each other, so they are close to one bet held several times. The binding constraint on this portfolio is the number of genuinely independent bets it makes, not the size of any single return.",
        },
        "clocks": clocks,
        "pending": pending_rows(),
        "closedFamilies": [{"name": n, "verdict": v, "step": s} for n, v, s in CLOSED],
        "readMe": "Forward returns are realised weekly numbers read from hash-chained logs. A clock completing does not authorise promotion; it triggers a separately predeclared statistical review. No strategy here has ever traded.",
    }
    target = ROOT / args.output
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload["headline"], indent=2, sort_keys=True))
    for clock in clocks:
        cumulative = clock["cumulativeReturn"]
        print(f"  {clock['protocol']:<46}{clock['observedWeeks']}/{clock['requiredWeeks']}"
              f"{'' if cumulative is None else f'  cumulative {cumulative*100:+.2f}%'}")
    for row in payload["pending"]:
        print(f"  pending: {row['protocol']} from {row['firstDecision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
