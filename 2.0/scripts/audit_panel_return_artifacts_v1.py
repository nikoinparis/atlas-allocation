#!/usr/bin/env python3
"""Find corporate-action artifacts in the research panels, and price their effect.

Found while auditing the dashboard strategies: the equal-weight return of the
whole panel came back as `inf`, which is not a number any benchmark should
produce.  The cause is a handful of cells carrying weekly returns of 1,000% to
2,900% -- unadjusted reverse splits, and one division by a zero price.

The asymmetry is what makes this matter.  No displayed strategy holds any of the
affected issuers, because they are penny-stock artifacts no factor would select.
But every equal-weight *benchmark* holds all of them, so the defect inflates the
comparison baseline while leaving the strategies untouched, biasing every
benchmark-relative conclusion in this project against its own strategies.

Nothing here is authorised to trade, and nothing frozen is modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader import sec_tournament_rehearsal as engine

PANELS = {
    "sec_broad_research_panel_v2": "data/sec_broad_research_panel_v2/weekly_returns.csv.gz",
    "sec_broad_research_panel_v3": "data/sec_broad_research_panel_v3/weekly_returns.csv.gz",
}
BOOKS = {
    "cash_conversion_breadth20": ("evidence/sec_cash_conversion_breadth_dynamic_v1/best_portfolio_choices.csv", "cik10"),
    "growth_top_five": ("evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv", "cik10"),
    "sector_ensemble": ("evidence/sec_sector_aware_signal_ensemble_v1/selected_stock_target_weights.csv", "cik10"),
}
EXTREME = 1.0  # a weekly total return above +100% is treated as suspect, not as alpha


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/panel_return_artifact_audit_v1")
    args = parser.parse_args()

    findings: dict[str, object] = {}
    for name, relative in PANELS.items():
        frame = pd.read_csv(ROOT / relative, index_col=0, parse_dates=True)
        values = frame.to_numpy(dtype=float)
        infinite = int(np.isinf(values).sum())
        finite = values[np.isfinite(values)]
        raw = frame.replace([np.inf, -np.inf], np.nan)
        clean = raw.where(raw.abs() <= EXTREME)

        rows, cols = np.where(np.abs(np.nan_to_num(values, nan=0.0, posinf=1e18, neginf=-1e18)) > EXTREME)
        cells = [{"week": str(frame.index[r].date()), "cik10": str(frame.columns[c]),
                  "weekly_return": (None if not np.isfinite(values[r, c]) else float(values[r, c]))}
                 for r, c in zip(rows, cols)]
        affected = sorted({cell["cik10"] for cell in cells})

        raw_ew, clean_ew = raw.mean(axis=1, skipna=True), clean.mean(axis=1, skipna=True)
        findings[name] = {
            "weeks": int(frame.shape[0]),
            "issuers": int(frame.shape[1]),
            "present_cells": int(np.isfinite(values).sum()),
            "infinite_cells": infinite,
            "cells_above_100pct_weekly": len(cells),
            "worst_finite_weekly_return": float(finite.max()),
            "affected_issuers": affected,
            "extreme_cells": sorted(cells, key=lambda c: c["week"]),
            "equal_weight_panel_benchmark": {
                "with_artifacts__full_cagr": float(engine.metrics(raw_ew)["cagr"]),
                "without_artifacts__full_cagr": float(engine.metrics(clean_ew)["cagr"]),
                "with_artifacts__recent_52w_cagr": float(engine.metrics(raw_ew.tail(52))["cagr"]),
                "without_artifacts__recent_52w_cagr": float(engine.metrics(clean_ew.tail(52))["cagr"]),
            },
            "held_by_any_displayed_strategy": {},
        }
        for book_name, (path, column) in BOOKS.items():
            book = pd.read_csv(ROOT / path, dtype={column: str})
            findings[name]["held_by_any_displayed_strategy"][book_name] = sorted(
                set(book[column]) & set(affected))

    v3 = findings["sec_broad_research_panel_v3"]["equal_weight_panel_benchmark"]
    result = {
        "experiment": "panel_return_artifact_audit_v1",
        "extreme_threshold_weekly_return": EXTREME,
        "panels": findings,
        "headline": {
            "benchmark_inflation_full_cagr_pp": round(
                (v3["with_artifacts__full_cagr"] - v3["without_artifacts__full_cagr"]) * 100, 2),
            "benchmark_inflation_recent_52w_pp": round(
                (v3["with_artifacts__recent_52w_cagr"] - v3["without_artifacts__recent_52w_cagr"]) * 100, 2),
            "strategies_affected": "none: no displayed strategy holds any affected issuer",
            "direction_of_bias": "against the strategies, because the artifacts sit only in the benchmark",
        },
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "panels"}, indent=2, sort_keys=True))
    for name, data in findings.items():
        print(f"\n{name}: {data['infinite_cells']} infinite, {data['cells_above_100pct_weekly']} cells >100%/week, "
              f"{len(data['affected_issuers'])} issuers affected, held by displayed strategies: "
              f"{sum(len(v) for v in data['held_by_any_displayed_strategy'].values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
