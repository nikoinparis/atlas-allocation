#!/usr/bin/env python3
"""Falsify the strict monthly-cap 13-week 0/50 cash-conversion candidate."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_cash_conversion_capped_dynamic_v1 as capped

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv"
OUTPUT = ROOT / "evidence/sec_cash_conversion_capped_candidate_audit_v1"


def metrics(path: pd.DataFrame, window: str) -> dict:
    return next(row for row in base.metric_rows("candidate", "base", 50, path) if row["window"] == window)


def composite(leader: pd.Series, cash: pd.Series, delay: int = 0) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), cash.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, 13, 0.5, delay)
    return dynamic.simulate(returns, target, 50.0)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(DISCOVERY / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = choices[choices.family == "cash_conversion"]
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    targets = base.build_targets(choices, index)
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(choices.cik10)):
        if cik in sources:
            source, path = sources[cik]
            series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    weekly = pd.DataFrame(series, index=index)
    leader = dynamic.read_path(LEADER).net_return
    cash, peak_internal = capped.simulate_cash(weekly, targets, "base", 50.0, 1.0)
    baseline = composite(leader, cash.net_return)
    baseline_recent = metrics(baseline, "trailing_1y")

    rows = []
    for cik in sorted(set(choices.cik10)):
        altered = weekly.copy()
        altered[cik] = np.nan
        cash_loo, _ = capped.simulate_cash(altered, targets, "base", 50.0, 1.0)
        path = composite(leader, cash_loo.net_return)
        recent, full = metrics(path, "trailing_1y"), metrics(path, "full_recent")
        rows.append({"cik10": cik, "company_name": choices.loc[choices.cik10 == cik, "company_name"].iloc[-1], "trailing_1y_cagr": recent["cagr"], "trailing_1y_cagr_change": recent["cagr"] - baseline_recent["cagr"], "trailing_1y_sharpe": recent["sharpe_zero_rf"], "trailing_1y_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"]})
    loo = pd.DataFrame(rows).sort_values("trailing_1y_cagr_change")
    recent_ciks = set(choices.loc[choices.decision_at >= choices.decision_at.max() - pd.DateOffset(years=1), "cik10"])
    recent = loo[loo.cik10.isin(recent_ciks)]
    worst = recent.iloc[0]
    delay_rows = []
    for delay in (0, 1, 2):
        path = composite(leader, cash.net_return, delay)
        delay_rows.extend(row for row in base.metric_rows("strict_cap", f"delay_{delay}", 50, path) if row["window"] in {"full_recent", "trailing_1y", "ytd"})
    delays = pd.DataFrame(delay_rows)
    control = dynamic.read_path(LEADER)
    if "turnover" not in control:
        control["turnover"] = 0.0
    control_recent = metrics(control, "trailing_1y")["cagr"]
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    recent.to_csv(OUTPUT / "recent_leave_one_company_out.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    result = {
        "experiment": "sec_cash_conversion_capped_candidate_audit_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_trailing_1y_cagr": float(baseline_recent["cagr"]), "control_trailing_1y_cagr": float(control_recent),
        "peak_cash_sleeve_stock_weight": float(peak_internal), "peak_target_total_portfolio_stock_weight": float(0.5 * peak_internal),
        "worst_recent_exclusion_company": worst.company_name, "worst_recent_exclusion_cagr": float(worst.trailing_1y_cagr),
        "worst_recent_exclusion_change": float(worst.trailing_1y_cagr_change), "worst_recent_exclusion_beats_control": bool(worst.trailing_1y_cagr > control_recent),
        "one_week_delay_cagr": float(delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].cagr.iloc[0]),
        "two_week_delay_cagr": float(delays[(delays.scenario == "delay_2") & (delays.window == "trailing_1y")].cagr.iloc[0]),
        "all_delay_cases_beat_control": bool(delays[(delays.window == "trailing_1y") & (delays.scenario != "delay_0")].cagr.gt(control_recent).all()),
        "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
