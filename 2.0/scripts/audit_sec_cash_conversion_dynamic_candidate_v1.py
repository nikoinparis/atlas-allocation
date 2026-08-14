#!/usr/bin/env python3
"""Company-dependence and local-surface audit for the 13-week 0/50 candidate."""

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

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
SURFACE = ROOT / "evidence/sec_cash_conversion_return_surface_v1"
OUTPUT = ROOT / "evidence/sec_cash_conversion_dynamic_candidate_audit_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv"


def metric(path: pd.DataFrame, window: str) -> dict:
    rows = base.metric_rows("candidate", "base", 50, path)
    return next(row for row in rows if row["window"] == window)


def candidate_target(index: pd.DatetimeIndex, leader: pd.Series, cash: pd.Series, delay: int = 0) -> pd.DataFrame:
    signal = pd.DataFrame({"leader": leader, "cash_conversion": cash}).reindex(index)
    trend = dynamic.rolling_total(signal, 13)
    active = ((trend.cash_conversion > trend.leader) & (trend.cash_conversion > 0)).shift(delay).fillna(False)
    target = pd.DataFrame(0.0, index=index, columns=["leader", "cash_conversion"])
    target.cash_conversion = np.where(active, 0.5, 0.0)
    target.leader = 1 - target.cash_conversion
    return target


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(DISCOVERY / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = choices[choices.family == "cash_conversion"].copy()
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    cash_targets = base.build_targets(choices, index)
    sources, terminals = base.price_sources(), base.terminal_dates()
    weekly = pd.DataFrame(index=index)
    for cik in sorted(set(choices.cik10)):
        if cik in sources:
            source, path = sources[cik]
            weekly[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    cash_baseline, _ = base.simulate(weekly, cash_targets, "base", 50.0)
    frozen_cash = dynamic.read_path(DISCOVERY / "path_cash_conversion__base__50bps.csv")
    reproduction_error = float((cash_baseline.net_return - frozen_cash.net_return.reindex(cash_baseline.index)).abs().max())
    leader = dynamic.read_path(LEADER).net_return
    common = pd.concat([leader.rename("leader"), cash_baseline.net_return.rename("cash_conversion")], axis=1).dropna()
    baseline_target = candidate_target(common.index, common.leader, common.cash_conversion)
    baseline = dynamic.simulate(common, baseline_target, 50.0)
    baseline_recent = metric(baseline, "trailing_1y")

    rows = []
    for number, cik in enumerate(sorted(set(choices.cik10)), 1):
        altered = weekly.copy()
        altered[cik] = np.nan
        cash_loo, _ = base.simulate(altered, cash_targets, "base", 50.0)
        combined = pd.concat([leader.rename("leader"), cash_loo.net_return.rename("cash_conversion")], axis=1).dropna()
        target = candidate_target(combined.index, combined.leader, combined.cash_conversion)
        path = dynamic.simulate(combined, target, 50.0)
        recent = metric(path, "trailing_1y")
        full = metric(path, "full_recent")
        rows.append({"cik10": cik, "company_name": choices.loc[choices.cik10 == cik, "company_name"].iloc[-1], "trailing_1y_cagr": recent["cagr"], "trailing_1y_cagr_change": recent["cagr"] - baseline_recent["cagr"], "trailing_1y_sharpe": recent["sharpe_zero_rf"], "trailing_1y_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"]})
        if number % 25 == 0:
            print(f"leave-one-company-out {number}/{choices.cik10.nunique()}", flush=True)
    loo = pd.DataFrame(rows).sort_values("trailing_1y_cagr_change")
    recent_ciks = set(choices.loc[choices.decision_at >= choices.decision_at.max() - pd.DateOffset(years=1), "cik10"])
    recent_loo = loo[loo.cik10.isin(recent_ciks)].copy()

    screen = pd.read_csv(SURFACE / "screening_gates.csv")
    parsed = screen.candidate.str.extract(r"cash_rel_(\d+)w_(\d+)_(\d+)")
    cash = screen[parsed[0].notna()].copy()
    cash[["lookback", "low", "high"]] = parsed[parsed[0].notna()].astype(int).to_numpy()
    local = cash[cash.lookback.between(10, 16) & cash.high.isin([40, 50])].copy()
    control = screen[screen.candidate == "control"].iloc[0]
    local["recent_improvement"] = local.trailing_1y_cagr > control.trailing_1y_cagr
    local["recent_and_full_improvement"] = local.recent_improvement & (local.full_cagr > control.full_cagr)
    local.to_csv(OUTPUT / "local_parameter_neighborhood.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    recent_loo.to_csv(OUTPUT / "recent_leave_one_company_out.csv", index=False)
    worst = recent_loo.iloc[0]
    result = {
        "experiment": "sec_cash_conversion_dynamic_candidate_audit_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "baseline_trailing_1y_cagr": float(baseline_recent["cagr"]), "cash_path_reproduction_max_return_error": reproduction_error,
        "local_configurations": int(len(local)), "local_recent_improvement_share": float(local.recent_improvement.mean()),
        "local_screen_gate_share": float(local.all_screen_gates.mean()), "local_recent_and_full_improvement_share": float(local.recent_and_full_improvement.mean()),
        "recent_companies_tested": int(len(recent_loo)), "worst_recent_exclusion_company": worst.company_name,
        "worst_recent_exclusion_cagr": float(worst.trailing_1y_cagr), "worst_recent_exclusion_change": float(worst.trailing_1y_cagr_change),
        "worst_recent_exclusion_still_beats_control": bool(worst.trailing_1y_cagr > control.trailing_1y_cagr),
        "validation_passed": bool(reproduction_error < 1e-12), "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Cash-conversion dynamic candidate audit v1\n\n"
        f"Within the local 10–16-week, 40–50% neighborhood, **{result['local_recent_improvement_share']:.1%}** of configurations beat the control's trailing-year CAGR and **{result['local_screen_gate_share']:.1%}** passed every return, drawdown, Sharpe, older-history, and severe-cost screen.\n\n"
        f"The worst recent company exclusion was {worst.company_name}, reducing CAGR to **{worst.trailing_1y_cagr:.2%}**. The result {'still beat' if result['worst_recent_exclusion_still_beats_control'] else 'did not beat'} the control.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["validation_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
