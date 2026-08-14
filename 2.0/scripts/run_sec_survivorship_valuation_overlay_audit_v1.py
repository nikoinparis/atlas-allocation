#!/usr/bin/env python3
"""Falsify the strongest valuation overlay under delays, costs, and issuer exclusion."""

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
import run_sec_survivorship_valuation_discovery_v1 as discovery
import run_sec_survivorship_valuation_falsification_v1 as falsification
import run_sec_survivorship_valuation_overlay_search_v1 as overlay

CONFIG = ROOT / "config/sec_survivorship_valuation_overlay_audit_v1.json"
DISCOVERY = ROOT / "evidence/sec_survivorship_valuation_discovery_v1"
FALSIFICATION = ROOT / "evidence/sec_survivorship_valuation_falsification_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_survivorship_valuation_overlay_audit_v1"


def combined_metrics(control: pd.Series, sleeve: pd.Series | pd.DataFrame, allocation: float, cost: float) -> tuple[pd.DataFrame, dict, dict]:
    sleeve_returns = sleeve["net_return"] if isinstance(sleeve, pd.DataFrame) else sleeve
    joined = pd.concat([control, sleeve_returns.rename("sleeve")], axis=1, join="inner").dropna()
    target = pd.Series(float(allocation), index=joined.index)
    path = overlay.simulate(joined.control, joined.sleeve, target, float(cost))
    recent_start = path.index.max() - pd.DateOffset(years=1)
    return path, overlay.metrics(path.net_return), overlay.metrics(path.loc[path.index >= recent_start, "net_return"])


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = falsification.choose(scores, json.loads((ROOT / "config/sec_survivorship_valuation_falsification_v1.json").read_text()))
    selected = choices[choices.candidate == config["valuation_candidate"]].copy()
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp("2023-01-01"), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = discovery.source_map(), base.terminal_dates()
    price_series = {}
    for cik in sorted(set(selected.cik10)):
        spec = sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(price_series, index=weekly_index)
    targets = base.build_targets(selected, weekly_index)
    split_ciks = set(pd.read_csv(DISCOVERY / "split_distortion_audit.csv", dtype={"cik10": str}).cik10)
    if config["exclude_split_affected"]:
        for cik in split_ciks & set(weekly.columns):
            weekly[cik] = np.nan

    rows, paths = [], {}
    for delay in config["valuation_execution_delays_weeks"]:
        delayed_targets = falsification.shifted_targets(targets, weekly_index, int(delay))
        for underlying_cost in [50.0, 100.0, 200.0]:
            sleeve, _ = base.simulate(weekly, delayed_targets, "base", underlying_cost)
            for allocation in config["allocations"]:
                for outer_cost in config["outer_cost_bps"]:
                    path, full, recent = combined_metrics(control, sleeve, float(allocation), float(outer_cost))
                    name = f"delay{delay}__under{int(underlying_cost)}__w{allocation:.2f}__outer{outer_cost}"
                    rows.append({"scenario": name, "delay_weeks": delay, "underlying_cost_bps": underlying_cost, "allocation": allocation, "outer_cost_bps": outer_cost, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"]})
                    if delay == 0 and underlying_cost == 50 and outer_cost == 50:
                        paths[float(allocation)] = path
    stresses = pd.DataFrame(rows)

    recent_start = control.index.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(selected.loc[selected.decision_at.dt.tz_localize(None) >= recent_start - pd.DateOffset(months=3), "cik10"]) - split_ciks)
    loo_rows = []
    for cik in recent_ciks:
        stressed_weekly = weekly.copy()
        stressed_weekly[cik] = np.nan
        sleeve, _ = base.simulate(stressed_weekly, targets, "base", 50.0)
        company_rows = selected[selected.cik10 == cik]
        company = str(company_rows.company_name.iloc[-1]) if len(company_rows) else cik
        for allocation in config["allocations"]:
            _, full, recent = combined_metrics(control, sleeve, float(allocation), 50.0)
            loo_rows.append({"cik10": cik, "company_name": company, "allocation": allocation, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "cagr_delta_vs_control": recent["cagr"] - float(config["control_recent_cagr"])})
    loo = pd.DataFrame(loo_rows).sort_values(["allocation", "recent_cagr"])

    primary = stresses[(stresses.delay_weeks == 0) & (stresses.underlying_cost_bps == 50) & (stresses.outer_cost_bps == 50)].sort_values("allocation")
    worst_loo = loo.groupby("allocation", as_index=False).first()
    eligible = primary.merge(worst_loo[["allocation", "recent_cagr"]].rename(columns={"recent_cagr": "worst_loo_recent_cagr"}), on="allocation")
    eligible["beats_control_both"] = (eligible.recent_cagr > float(config["control_recent_cagr"])) & (eligible.full_cagr > float(config["control_full_cagr"]))
    eligible["loo_gate"] = eligible.worst_loo_recent_cagr >= float(config["minimum_leave_one_out_recent_cagr"])
    robust = eligible[eligible.beats_control_both & eligible.loo_gate].sort_values(["recent_cagr", "recent_sharpe"], ascending=False)
    chosen = robust.iloc[0] if len(robust) else eligible.sort_values("recent_cagr", ascending=False).iloc[0]
    chosen_allocation = float(chosen.allocation)
    chosen_path = paths[chosen_allocation]
    chosen_path.rename_axis("Date").to_csv(OUTPUT / "candidate_path_50bps.csv")
    stresses.to_csv(OUTPUT / "delay_and_cost_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_issuer_out.csv", index=False)
    eligible.to_csv(OUTPUT / "allocation_comparison.csv", index=False)
    selected.to_csv(OUTPUT / "valuation_portfolio_choices.csv", index=False)

    chosen_delay1 = stresses[(stresses.delay_weeks == 1) & (stresses.underlying_cost_bps == 50) & (stresses.outer_cost_bps == 50) & np.isclose(stresses.allocation, chosen_allocation)].iloc[0]
    chosen_delay2 = stresses[(stresses.delay_weeks == 2) & (stresses.underlying_cost_bps == 50) & (stresses.outer_cost_bps == 50) & np.isclose(stresses.allocation, chosen_allocation)].iloc[0]
    chosen_200 = stresses[(stresses.delay_weeks == 0) & (stresses.underlying_cost_bps == 200) & (stresses.outer_cost_bps == 200) & np.isclose(stresses.allocation, chosen_allocation)].iloc[0]
    chosen_loo = loo[np.isclose(loo.allocation, chosen_allocation)].iloc[0]
    checks = {"three_allocations_reported": set(stresses.allocation) == set(config["allocations"]), "three_delays_reported": set(stresses.delay_weeks) == set(config["valuation_execution_delays_weeks"]), "all_costs_reported": set(stresses.outer_cost_bps) == set(config["outer_cost_bps"]), "leave_one_out_reported": len(loo) > 0, "results_finite": bool(np.isfinite(stresses.select_dtypes("number").to_numpy()).all() and np.isfinite(loo.select_dtypes("number").to_numpy()).all())}
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "chosen_allocation": chosen_allocation, "recent_cagr": float(chosen.recent_cagr), "recent_sharpe": float(chosen.recent_sharpe), "recent_drawdown": float(chosen.recent_drawdown), "full_cagr": float(chosen.full_cagr), "full_drawdown": float(chosen.full_drawdown), "one_week_delay_recent_cagr": float(chosen_delay1.recent_cagr), "two_week_delay_recent_cagr": float(chosen_delay2.recent_cagr), "severe_200bps_recent_cagr": float(chosen_200.recent_cagr), "worst_leave_one_out_company": str(chosen_loo.company_name), "worst_leave_one_out_recent_cagr": float(chosen_loo.recent_cagr), "beats_control_recent_and_full": bool(chosen.beats_control_both), "concentration_gate_passed": bool(chosen.loo_gate), "robust_allocations": [float(x) for x in robust.allocation], "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# Survivorship-aware valuation overlay audit v1\n\n" f"The selected controlled allocation is {chosen_allocation:.0%}. It produced {chosen.recent_cagr:.2%} recent CAGR, {chosen.recent_sharpe:.2f} Sharpe, and {chosen.recent_drawdown:.2%} drawdown; full CAGR was {chosen.full_cagr:.2%}.\n\n" f"One- and two-week valuation execution delays produced {chosen_delay1.recent_cagr:.2%} and {chosen_delay2.recent_cagr:.2%}. At 200 bps on both underlying valuation turnover and overlay turnover, recent CAGR was {chosen_200.recent_cagr:.2%}. The weakest leave-one-issuer-out result was {chosen_loo.recent_cagr:.2%} after excluding {chosen_loo.company_name}.\n\n" "This remains a retrospective research candidate, not authorization for live trading.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
