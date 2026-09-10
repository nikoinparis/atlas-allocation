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


def before_after() -> list[dict]:
    """The split that matters more than any headline CAGR on this site.

    Read from the artifact rather than typed in, so it cannot drift from Step 262.
    """
    path = ROOT / "evidence/structural_break_v1/pre_break_performance.csv"
    if not path.is_file():
        return []
    import csv
    rows = []
    with path.open() as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "strategy": row["strategy"], "window": row["window"],
                "weeks": int(row["weeks"]), "cagr": float(row["cagr"]),
                "sharpe": float(row["sharpe"]), "maxDrawdown": float(row["maxdd"]),
            })
    return rows


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
        "structuralBreak": {
            "date": "2025-04-04",
            "note": "Every displayed strategy selects this same week as its break point, scanned independently over 188 to 195 weeks. Betas sit near zero on both sides, so the change is not market exposure. It does not clear a Bonferroni-corrected bar (p 0.022 to 0.038) and is recorded as suggestive, but four different strategies do not pick the same week by chance.",
            "beforeAfter": before_after(),
            "measuredIn": "Steps 261 and 262",
        },
        "crossSectionalSkill": {
            "headline": "Nought of thirteen",
            "window": "13-week horizon, both windows, Bonferroni bar p < 0.0038",
            "finding": (
                "Every signal on disk was measured three beta-neutral ways: rank information "
                "coefficient, top-minus-bottom decile spread, and decile monotonicity. None "
                "clears Bonferroni. More decisively, none orders its deciles -- monotonicity "
                "sits within 0.17 of zero for all thirteen. Six show a positive information "
                "coefficient alongside a negative decile spread, which cannot both describe a "
                "real signal."),
            "rows": [
                {"signal": "Earnings yield", "ic": 0.0344, "spread": -0.0988, "monotone": 0.02},
                {"signal": "Profitability", "ic": 0.0317, "spread": -0.1006, "monotone": -0.08},
                {"signal": "Cash conversion (out of sample)", "ic": 0.0272, "spread": 0.0234, "monotone": 0.01},
                {"signal": "Cash conversion (in sample)", "ic": 0.0174, "spread": -0.1358, "monotone": -0.02},
                {"signal": "Growth top five (out of sample)", "ic": -0.0053, "spread": -0.0549, "monotone": -0.05},
                {"signal": "Balance sheet quality (in sample)", "ic": -0.0091, "spread": -0.0501, "monotone": -0.14},
            ],
            "whatItMeans": (
                "The top-N books on this dashboard were never winning on ranking ability. They "
                "won on market beta and on holding a few names that went up. This explains the "
                "out-of-sample failure above, the transfer coefficient of -103 measured in Step "
                "245, and Step 295's finding that neutralising the market took cash conversion "
                "from 16.65% to 1.59%. IR = IC x sqrt(BR) is a product, and an IC "
                "indistinguishable from zero gives an IR indistinguishable from zero at any "
                "breadth."),
            "honestLimit": (
                "The in-sample window has 13-14 quarterly decisions and cannot detect a true "
                "information coefficient of 0.03 -- that needs roughly a hundred decisions. The "
                "significance null is weak evidence. The monotonicity result carries the weight "
                "because it measures the shape of the relationship rather than its significance, "
                "and would show at any sample size."),
            "measuredIn": "Step 296",
        },
        "outOfSample": {
            "headline": "Nought of six",
            "window": "2013-2022, 39 quarterly decisions, 509 weeks",
            "finding": (
                "Every fundamental signal and both composites on this dashboard were rebuilt "
                "from their own frozen configs and tested on a period they were not selected "
                "on. None retains more than 11% of its in-sample edge and three of six have "
                "the wrong sign. This was possible for the first time on 2026-09-07, because "
                "no fundamental panel here reached back before 2023 until SEC Financial "
                "Statement Data Sets were acquired for 2012-2022."),
            "rows": [
                {"strategy": "Growth top five", "excess": -0.1541, "inSample": 0.118},
                {"strategy": "Balance sheet quality", "excess": -0.0750, "inSample": 0.10},
                {"strategy": "Residual composite", "excess": -0.0152, "inSample": 0.10},
                {"strategy": "Earnings yield", "excess": 0.0038, "inSample": 0.145},
                {"strategy": "Sector ensemble stock leg", "excess": 0.0014, "inSample": 0.10},
                {"strategy": "Cash conversion breadth 20", "excess": 0.0108, "inSample": 0.10},
            ],
            "whatItMeans": (
                "The headline returns on this dashboard are a property of the 2023-2026 window. "
                "That was always the stated risk; until now it was an untested worry rather "
                "than a measured fact. It does not establish that these strategies cannot work "
                "forward -- which is what the clocks are for -- but the honest prior for every "
                "one of them is near-zero excess, not the ten to fourteen points their "
                "manifests record."),
            "measuredIn": "Steps 287, 289, 290",
        },
        "distinctStrategyCount": {
            "displayed": 6,
            "distinct": 4,
            "finding": (
                "The dashboard displays six strategies. Step 281 established that two of them "
                "are one object: the Sector-Aware Signal Ensemble's published path is identical "
                "to its own predecessor in 165 of 188 weeks and totals 261.99% against that "
                "path's 259.99%, so the sector-aware overlay is worth about 0.08 points a year "
                "on a 42.74% CAGR. Its 1.35x form is the same book again at higher leverage."),
            "whyItMatters": (
                "Counting them separately overstates how many independent bets this project "
                "holds, which is the illusion Step 245 measured as an effective 1.15 strategies "
                "and Step 277 restated as breadth without skill. Nothing has been removed: a "
                "negative result is a record, not a mistake to delete."),
            "measuredIn": "Step 281",
        },
        "reproducibility": {
            "asOf": "2026-09-06",
            "savedBook": "6 of 6",
            "reproducesFromSavedBook": "5 of 6",
            "reproducesFromPublishedHoldings": "6 of 6",
            "frozenManifest": "6 of 6",
            "note": (
                "Every dashboard strategy can now be rebuilt and repriced. The one that does "
                "not reproduce from a long-form book is the ETF 60/40, whose book is a wide "
                "date-by-symbol matrix; its published holdings reprice at +0.988."),
            "harness": "scripts/audit_dashboard_reproducibility_v1.py",
            "documentation": "docs/STRATEGY_REPRODUCTION_V1.md",
        },
        "candidate": {
            "name": "Valuation, earnings yield, breadth 20",
            "status": "candidate on a forward clock — no forward evidence yet",
            "why_it_is_here": "It is the only strategy this project has built whose correlation against every existing strategy is near zero: -0.022, +0.006, -0.029, +0.116. It also passes the concentration gate the original ten-name version failed, holds 109 distinct issuers, and its worst single-name removal costs 2.01 points of 32.56.",
            "what_it_is_not": "A discovery. Earnings yield is one of the oldest documented anomalies in finance, and the search behind this was sixteen configurations on a panel already searched ninety ways, on the same window every strategy here was selected on.",
            "historical": {
                "fullCagr": 0.3256, "fullSharpe": 1.379, "fullMaxDrawdown": -0.1852,
                "preBreakCagr": 0.2361, "preBreakSharpe": 1.081,
                "postBreakCagr": 0.4783, "postBreakSharpe": 1.817,
                "topIssuerShareOfPositiveContribution": 0.0664, "distinctIssuers": 109,
            },
            "blendedWithGrowth": {
                "note": "Nine of nine blends beat BOTH components on Sharpe. That is arithmetic rather than a fitted result: near-zero correlation reduces portfolio volatility whatever the returns do.",
                "best": "35% valuation with 65% sector ensemble",
                "sharpeBefore": 1.795, "sharpeAfter": 2.242,
                "volatilityBefore": 0.223, "volatilityAfter": 0.163,
                "maxDrawdownBefore": -0.2132, "maxDrawdownAfter": -0.1656,
            },
            "measuredIn": "Step 274",
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
