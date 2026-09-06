#!/usr/bin/env python3
"""Assemble the dashboard's forward-tracking payload from evidence on disk.

Everything here is read from existing artifacts. The page it feeds has one job:
show what has and has not actually accumulated as untouched forward evidence, so
that a stale backtest cannot be mistaken for a live record.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard/public/forward-tracker.json"

STRATEGY_LABELS = {
    "sec-residual-controlled-1.25x-5pct-v1": "Residual-Controlled 1.25x",
    "sec-sector-ensemble-fragile-1.35x-v1": "Fragile Sector Ensemble 1.35x",
    "candidate-return-first-60-40-forward-v1": "ETF Incumbent 60/40",
    "sec-growth-survivorship-aware-v1": "Growth / Micron",
    "sec-cash-conversion-breadth20-dynamic-v1": "Cash-Conversion Breadth-20",
    "sec-sector-aware-signal-ensemble-v1": "Sector-Aware Signal Ensemble",
}


def protocol_rows() -> list[dict]:
    rows = []
    for status_path in sorted((ROOT / "evidence").glob("forward_*/status.json")):
        status = json.loads(status_path.read_text())
        name = status_path.parent.name.replace("forward_", "")
        observations = []
        log = status_path.parent / "observations.jsonl"
        if log.exists():
            for line in log.read_text().splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                observations.append({
                    "decisionDate": record.get("decision_date"),
                    "realizationDate": record.get("realization_date"),
                    "netReturn": record.get("net_return"),
                    "turnover": record.get("turnover"),
                })
        rows.append({
            "protocol": name,
            "observedWeeks": int(status.get("observed_weeks", 0)),
            "requiredWeeks": int(status.get("required_weeks", status.get("required_untouched_weeks", 52))),
            "latestRealization": status.get("latest_realization_date"),
            "executionEnabled": bool(status.get("execution_enabled", False)),
            "observations": observations,
        })
    return sorted(rows, key=lambda r: (-r["observedWeeks"], r["protocol"]))


def main() -> int:
    marks = pd.read_csv(ROOT / "evidence/dashboard_held_book_marks_v1/held_book_weekly_marks.csv")
    held_summary = json.loads((ROOT / "evidence/dashboard_held_book_marks_v1/summary.json").read_text())
    benchmarks = json.loads((ROOT / "evidence/dashboard_held_book_marks_v1/benchmarks.json").read_text())
    attribution = json.loads((ROOT / "evidence/dashboard_held_book_marks_v1/energy_attribution.json").read_text())
    panel = json.loads((ROOT / "data/clean_weekly_prices_v2/manifest.json").read_text())
    registry = json.loads((ROOT / "config/forward_prediction_registry_v1.json").read_text())

    held = []
    by_strategy = {row["strategy_id"]: row for row in held_summary["strategies"]}
    attribution_by_strategy = {row["strategy"]: row for row in attribution["rows"]}
    for strategy_id, group in marks.groupby("strategy_id"):
        group = group.sort_values("week_ending")
        held.append({
            "id": strategy_id,
            "label": STRATEGY_LABELS.get(strategy_id, strategy_id),
            "bookAsOf": by_strategy[strategy_id]["book_as_of"],
            "namesPriced": by_strategy[strategy_id]["names_priced"],
            "namesInBook": by_strategy[strategy_id]["names_in_book"],
            "grossExposure": by_strategy[strategy_id]["gross_exposure_priced"],
            "cumulativeReturn": by_strategy[strategy_id]["cumulative_return"],
            "weeks": [
                {"weekEnding": r.week_ending, "netReturn": r.net_return, "cumulative": r.cumulative}
                for r in group.itertuples()
            ],
            "energyWeight": attribution_by_strategy[strategy_id]["energy_weight"],
            "energyContribution": attribution_by_strategy[strategy_id]["energy_contrib"],
            "exEnergyContribution": attribution_by_strategy[strategy_id]["ex_energy"],
        })
    held.sort(key=lambda item: item["cumulativeReturn"], reverse=True)

    payload = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "dataThrough": panel["new_last_week"],
        "priorDataThrough": panel["prior_last_week"],
        "issuersPricedNewWeek": panel["coverage_new_week"],
        "panelReconciliation": panel["overlap_reconciliation"],
        "backtestsEndAt": held_summary["strategies"][0]["book_as_of"],
        "protocols": protocol_rows(),
        "registry": {
            "firstEligibleRealization": registry["first_eligible_realization"],
            "trackedStrategies": registry["strategies_tracked"],
            "skillThreshold": registry["predictions"]["skill"]["implies"],
            "selectionThreshold": registry["predictions"]["selection"]["implies"],
            "exposureThreshold": registry["predictions"]["unmeasured_exposure"]["implies"],
        },
        "heldBooks": {
            "weeks": held_summary["weeks"],
            "whatThisIs": held_summary["what_this_is"],
            "whatThisIsNot": held_summary["what_this_is_not"],
            "costTreatment": held_summary["cost_treatment"],
            "strategies": held,
            "benchmarks": benchmarks["cumulative"],
            "attributionNote": attribution["note"],
            "energySymbols": attribution["energy_symbols_classified"],
        },
        "liveTradingEnabled": False,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print(json.dumps({k: payload[k] for k in ["dataThrough", "backtestsEndAt", "liveTradingEnabled"]}, indent=2))
    for row in payload["protocols"]:
        print(f"  {row['protocol']}: {row['observedWeeks']}/{row['requiredWeeks']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
