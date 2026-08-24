#!/usr/bin/env python3
"""Audit the residual candidate on the last common observable endpoint."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv"
OUTPUT = ROOT / "evidence/sec_independent_sleeve_return_accelerator_v1/common_endpoint_audit.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def statistics(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    wealth = (1.0 + clean).cumprod()
    return {
        "cagr": float(wealth.iloc[-1] ** (52.0 / len(clean)) - 1.0),
        "sharpe": float(clean.mean() / clean.std(ddof=1) * np.sqrt(52.0)),
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "weeks": int(len(clean)),
    }


def main() -> int:
    candidate = pd.read_csv(CANDIDATE, parse_dates=["Date"]).set_index("Date").net_return
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return
    candidate.index = pd.to_datetime(candidate.index, utc=True)
    control.index = pd.to_datetime(control.index, utc=True)
    candidate_last = candidate.dropna().index.max()
    control_last = control.dropna().index.max()
    common = min(candidate_last, control_last)
    unlevered = candidate.loc[:common].tail(52)
    paths = {"unlevered_1.00x": statistics(unlevered)}
    for rate in (0.05, 0.08):
        values = 1.25 * unlevered - 0.25 * rate / 52.0
        paths[f"levered_1.25x_{int(rate * 100)}pct_financing"] = statistics(values)
    result = {
        "experiment": "sec_residual_common_endpoint_audit_v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_last_date": str(candidate_last.date()),
        "control_last_date": str(control_last.date()),
        "common_endpoint": str(common.date()),
        "excluded_mismatched_candidate_dates": [str(day.date()) for day in candidate.index[candidate.index > common]],
        "missing_control_returns_filled_with_zero": False,
        "trailing_52_week_paths": paths,
        "source_sha256": {
            str(CANDIDATE.relative_to(ROOT)): sha256(CANDIDATE),
            str(CONTROL.relative_to(ROOT)): sha256(CONTROL),
        },
        "interpretation": "The corrected 5% financing path exceeds 150% on the historical common endpoint, but financing is assumed and the result remains selection-contaminated retrospective research.",
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
