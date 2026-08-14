#!/usr/bin/env python3
"""Rebuild the 1.0 fragility-guard idea as a causal 2.0 challenger."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from run_trade_buffering_batch_08 import build_inputs
from src.systematic_trader.challenger_buffering import buffer_history
from src.systematic_trader.challenger_fragility_guard import causal_quality_and_fragility, apply_fragility_guard
from src.systematic_trader.point_in_time import compute_path
from src.systematic_trader.research_lab import period_slice, selection_score, summarize_periods


OUTPUT = ROOT / "evidence/fragility_guard_batch_09"
LEDGER = ROOT / "evidence/challenger_program_v1/trial_ledger.csv"
OFFENSE = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG"}
COSTS = (10.0, 25.0, 50.0, 100.0)
STRENGTHS = (0.04, 0.08, 0.12)
CROWDING_THRESHOLDS = (0.50, 0.75)
BUFFER_BANDS = (0.0, 0.05)


def configurations():
    yield "baseline", 0.0, 1.0, 0.0
    for strength in STRENGTHS:
        for threshold in CROWDING_THRESHOLDS:
            for band in BUFFER_BANDS:
                yield f"guard_s{strength:.2f}_c{threshold:.2f}_b{band:.2f}", strength, threshold, band


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    snapshot_id, dates, targets, simple_returns, prices = build_inputs()
    features = causal_quality_and_fragility(dates, prices, sorted(OFFENSE))
    scoreboard = []
    audits = {}
    for config_id, strength, threshold, band in configurations():
        guarded, guard_audit = apply_fragility_guard(
            dates, targets, features, offense_assets=OFFENSE,
            boost_strength=strength, crowding_threshold=threshold,
        )
        final_weights, buffer_audit = buffer_history(dates, guarded, entry_band=band)
        audits[config_id] = [
            {**guard, "buffer_band": buffer["band"], "buffer_held": buffer["buffer_held"]}
            for guard, buffer in zip(guard_audit, buffer_audit, strict=True)
        ]
        for cost_bps in COSTS:
            periods, accounting = compute_path(dates, final_weights, simple_returns, cost_bps=cost_bps)
            summary = summarize_periods(periods)
            development = summarize_periods(period_slice(periods, "2006-01-01", "2015-12-31"))
            later_1 = summarize_periods(period_slice(periods, "2016-01-01", "2020-12-31"))
            later_2 = summarize_periods(period_slice(periods, "2021-01-01", "9999-12-31"))
            scoreboard.append({
                "configuration_id": config_id, "boost_strength": strength,
                "crowding_threshold": threshold, "buffer_band": band, "cost_bps": cost_bps,
                **summary,
                "development_sharpe": development.get("sharpe_zero_rf", 0.0),
                "development_selection_score": selection_score(development),
                "oos_2016_2020_sharpe": later_1.get("sharpe_zero_rf", 0.0),
                "oos_2021_present_sharpe": later_2.get("sharpe_zero_rf", 0.0),
                "fully_invested_pass": accounting["fully_invested_pass"],
                "unpriced_exposure_events": accounting["unpriced_exposure_events"],
            })
    selection_rows = [row for row in scoreboard if float(row["cost_bps"]) == 10.0]
    selected = max(selection_rows, key=lambda row: (float(row["development_selection_score"]), str(row["configuration_id"])))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "scoreboard.csv", scoreboard)
    write_csv(OUTPUT / "selected_guard_audit.csv", audits[str(selected["configuration_id"])])
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "batch": 9, "track": "fragility_guard", "source_snapshot_id": snapshot_id,
        "historical_reference": "1.0 Phase 5 R2A offense scaling plus leadership-crowding cap",
        "implementation": "Independent causal proxy reconstruction using only free ETF prices available on each decision date",
        "configuration_count": len(scoreboard), "unique_rules": len(audits),
        "selected_at_10_bps": selected, "status": "challenger_not_final",
        "limitations": [
            "The exact 1.0 proprietary intermediate state-quality panels are not reused; this is a causal proxy reconstruction.",
            "Thresholds were predeclared but the research design was informed by the full historical era.",
            "Later periods are retrospective diagnostics and the ETF universe remains survivorship-prone."
        ],
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for row in scoreboard:
            writer.writerow([
                f"batch09-{row['configuration_id']}-{float(row['cost_bps']):.0f}", 9,
                "fragility_guard", "", row["configuration_id"], "completed",
                "retain_for_comparison", "development-selected after every predeclared rule ran",
                "evidence/fragility_guard_batch_09/scoreboard.csv",
            ])
    print(json.dumps({"trials": len(scoreboard), "selected_at_10_bps": selected}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
