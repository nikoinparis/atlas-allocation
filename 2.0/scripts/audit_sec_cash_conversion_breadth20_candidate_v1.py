#!/usr/bin/env python3
"""Final falsification audit for the breadth-20, 11-week, 0/50 candidate."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv"
OUTPUT = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1"


def metric(path: pd.DataFrame, window: str) -> dict:
    return next(row for row in base.metric_rows("candidate", "base", 50, path) if row["window"] == window)


def composite(leader: pd.Series, cash: pd.Series, delay: int = 0) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), cash.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, 11, 0.5, delay)
    return dynamic.simulate(returns, target, 50.0)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = breadth_runner.make_choices(scores[scores.family == "cash_conversion"], 20)
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
    cash, peak_internal = capped.simulate_cash(weekly, targets, "base", 50.0, None, 20)
    baseline = composite(leader, cash.net_return)
    baseline_returns = pd.concat([leader.rename("leader"), cash.net_return.rename("cash_conversion")], axis=1).dropna()
    baseline_target = capped.overlay_target(baseline_returns.index, baseline_returns.leader, baseline_returns.cash_conversion, 11, 0.5)
    baseline_recent, baseline_full = metric(baseline, "trailing_1y"), metric(baseline, "full_recent")
    control_frame = dynamic.read_path(LEADER)
    control_frame["turnover"] = control_frame.get("turnover", 0.0)
    control_recent, control_full = metric(control_frame, "trailing_1y"), metric(control_frame, "full_recent")

    recent_ciks = set(choices.loc[choices.decision_at >= choices.decision_at.max() - pd.DateOffset(years=1), "cik10"])
    loo_rows = []
    for number, cik in enumerate(sorted(recent_ciks), 1):
        altered = weekly.copy()
        altered[cik] = pd.NA
        loo_cash, _ = capped.simulate_cash(altered, targets, "base", 50.0, None, 20)
        path = composite(leader, loo_cash.net_return)
        recent, full = metric(path, "trailing_1y"), metric(path, "full_recent")
        loo_rows.append({"cik10": cik, "company_name": choices.loc[choices.cik10 == cik, "company_name"].iloc[-1], "trailing_1y_cagr": recent["cagr"], "cagr_change": recent["cagr"] - baseline_recent["cagr"], "trailing_1y_sharpe": recent["sharpe_zero_rf"], "trailing_1y_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"]})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]

    delay_rows, delayed_paths = [], {}
    for delay in (0, 1, 2):
        path = composite(leader, cash.net_return, delay)
        delayed_paths[delay] = path
        delay_rows.extend(row for row in base.metric_rows("breadth20", f"delay_{delay}", 50, path) if row["window"] in {"full_recent", "trailing_1y", "ytd"})
    delays = pd.DataFrame(delay_rows)
    joined = pd.concat([baseline.net_return.rename("candidate"), control_frame.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, block, 5000, 20260814) for block in (4, 13)])
    rolling = (1 + joined).rolling(26).apply(lambda values: values.prod(), raw=True) - 1
    rolling_share = float((rolling.candidate > rolling.control).dropna().mean())
    prefix_matches = []
    for cutoff in baseline_returns.index[26::26]:
        prefix = baseline_returns.loc[:cutoff]
        rebuilt = capped.overlay_target(prefix.index, prefix.leader, prefix.cash_conversion, 11, 0.5)
        prefix_matches.append(bool(rebuilt.equals(baseline_target.loc[:cutoff])))
    surface = pd.read_csv(ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1/screening.csv")
    surface_recent_share = float((surface.cagr_trailing_1y > control_recent["cagr"]).mean())
    surface_joint_share = float(((surface.cagr_trailing_1y > control_recent["cagr"]) & (surface.cagr_full_recent > control_full["cagr"])).mean())
    checks = {
        "recent_return_beats_control": baseline_recent["cagr"] > control_recent["cagr"],
        "full_return_beats_control": baseline_full["cagr"] > control_full["cagr"],
        "worst_exclusion_beats_control": worst.trailing_1y_cagr > control_recent["cagr"],
        "one_week_delay_beats_control": delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].cagr.iloc[0] > control_recent["cagr"],
        "two_week_delay_beats_control": delays[(delays.scenario == "delay_2") & (delays.window == "trailing_1y")].cagr.iloc[0] > control_recent["cagr"],
        "bootstrap_4w_probability_above_95pct": bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0] >= 0.95,
        "bootstrap_13w_probability_above_95pct": bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0] >= 0.95,
        "peak_target_stock_weight_below_10pct": 0.5 * peak_internal < 0.10,
        "prefix_invariance": all(prefix_matches),
        "breadth_surface_recent_majority": surface_recent_share >= 0.70,
        "breadth_surface_joint_half": surface_joint_share >= 0.50,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    loo.to_csv(OUTPUT / "recent_leave_one_company_out.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    baseline.rename_axis("Date").to_csv(OUTPUT / "candidate_path_50bps.csv")
    baseline_target.rename_axis("Date").to_csv(OUTPUT / "target_weights.csv")
    choices.to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    latest = choices[choices.decision_at == choices.decision_at.max()].copy()
    current_cash_allocation = float(baseline_target.cash_conversion.iloc[-1])
    latest["current_total_portfolio_target_weight"] = current_cash_allocation / 20.0
    latest.to_csv(OUTPUT / "current_cash_conversion_holdings.csv", index=False)
    result = {
        "experiment": "sec_cash_conversion_breadth20_candidate_audit_v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "trailing_1y_cagr": float(baseline_recent["cagr"]), "trailing_1y_sharpe": float(baseline_recent["sharpe_zero_rf"]), "trailing_1y_drawdown": float(baseline_recent["max_drawdown"]),
        "full_cagr": float(baseline_full["cagr"]), "control_trailing_1y_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]),
        "peak_target_total_portfolio_stock_weight": float(0.5 * peak_internal), "worst_recent_exclusion_company": worst.company_name,
        "current_cash_conversion_allocation": current_cash_allocation, "current_leader_allocation": 1.0 - current_cash_allocation,
        "worst_recent_exclusion_cagr": float(worst.trailing_1y_cagr), "one_week_delay_cagr": float(delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].cagr.iloc[0]),
        "two_week_delay_cagr": float(delays[(delays.scenario == "delay_2") & (delays.window == "trailing_1y")].cagr.iloc[0]), "rolling_26w_outperformance_share": rolling_share,
        "breadth_surface_recent_improvement_share": surface_recent_share, "breadth_surface_recent_and_full_improvement_share": surface_joint_share,
        "checks": checks, "all_falsification_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
