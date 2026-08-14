#!/usr/bin/env python3
"""Falsify the cash-conversion sleeve and blend it with the frozen 10/40 leader."""

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

CONFIG = ROOT / "config/sec_cash_conversion_confirmation_blend_v1.json"
DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = ROOT / "evidence/sec_cash_conversion_confirmation_blend_v1"


def trailing_cagr(path: pd.DataFrame, years: int = 1) -> float:
    end = path.index.max()
    returns = path.loc[path.index >= end - pd.DateOffset(years=years), "net_return"].dropna()
    return float((1 + returns).prod() ** (52 / len(returns)) - 1)


def read_path(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame else frame.columns[0]
    frame[date_column] = pd.to_datetime(frame[date_column])
    return frame.set_index(date_column).sort_index()


def blend_paths(leader: pd.DataFrame, sleeve: pd.DataFrame, weight: float, reset_dates: set[pd.Timestamp], cost_bps: float) -> pd.DataFrame:
    joined = pd.concat([leader.net_return.rename("leader"), sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
    leader_value, sleeve_value = 1.0 - weight, weight
    rows = []
    for date, row in joined.iterrows():
        before = leader_value + sleeve_value
        turnover = 0.0
        cost = 0.0
        if date in reset_dates and before > 0:
            current = sleeve_value / before
            turnover = abs(current - weight)
            cost = before * turnover * cost_bps / 10000.0
            deployable = before - cost
            leader_value, sleeve_value = deployable * (1 - weight), deployable * weight
            before = leader_value + sleeve_value + cost
        leader_value *= 1 + float(row.leader)
        sleeve_value *= 1 + float(row.sleeve)
        after = leader_value + sleeve_value
        rows.append({"Date": date, "gross_return": after / before - 1 + (cost / before if before else 0), "net_return": after / before - 1, "turnover": turnover, "cost": cost / before if before else 0, "wealth": after})
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(DISCOVERY / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = choices[choices.family == config["frozen_family"]].copy()
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    targets = base.build_targets(choices, weekly_index)
    reset_dates = set(targets)
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(choices.cik10)):
        if cik in sources:
            source, path = sources[cik]
            series[cik] = base.read_weekly_price(path, source, weekly_index, terminals.get(cik))
    weekly = pd.DataFrame(series, index=weekly_index)

    baseline_paths, performance_rows, blend_paths_out = {}, [], {}
    for cost in config["cost_bps"]:
        for scenario in config["scenarios"]:
            sleeve, _ = base.simulate(weekly, targets, scenario, float(cost))
            baseline_paths[(scenario, cost)] = sleeve
            leader = read_path(LEADER / f"path__{scenario}__{config['leader']}__{cost}bps.csv")
            for weight in config["independent_sleeve_weights"]:
                path = blend_paths(leader, sleeve, float(weight), reset_dates, float(cost))
                label = f"leader_plus_cash_conversion_{int(weight * 100):02d}"
                performance_rows.extend(base.metric_rows(label, scenario, int(cost), path))
                blend_paths_out[(scenario, cost, weight)] = path

    baseline = baseline_paths[("base", 50)]
    loo_rows = []
    for cik in sorted(set(choices.cik10)):
        altered = weekly.copy()
        if cik in altered:
            altered[cik] = np.nan
        path, _ = base.simulate(altered, targets, "base", 50.0)
        loo_rows.append({"cik10": cik, "company_name": choices.loc[choices.cik10 == cik, "company_name"].iloc[-1], "baseline_trailing_1y_cagr": trailing_cagr(baseline), "leave_one_out_trailing_1y_cagr": trailing_cagr(path), "cagr_contribution": trailing_cagr(baseline) - trailing_cagr(path)})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_contribution", ascending=False)
    recent_active = choices[choices.decision_at >= choices.decision_at.max() - pd.DateOffset(years=1)]
    relevant = loo[loo.cik10.isin(set(recent_active.cik10))]

    performance = pd.DataFrame(performance_rows)
    focus = performance[(performance.cost_bps == 50) & (performance.scenario == "base") & performance.window.isin(["full_recent", "trailing_2y", "trailing_1y", "ytd"])].copy()
    control = focus[focus.candidate == "leader_plus_cash_conversion_00"].set_index("window")
    focus["cagr_delta_vs_leader"] = [row.cagr - control.loc[row.window, "cagr"] for row in focus.itertuples()]
    best = focus[focus.window == "trailing_1y"].sort_values("cagr", ascending=False).iloc[0]
    severe = performance[(performance.cost_bps == 200) & (performance.scenario == "base") & (performance.window == "trailing_1y") & (performance.candidate == best.candidate)].iloc[0]
    largest = relevant.iloc[0]
    checks = {
        "all_weights_scenarios_costs_reported": len(performance.candidate.unique()) == len(config["independent_sleeve_weights"]),
        "zero_weight_matches_leader": bool(abs(focus[focus.candidate == "leader_plus_cash_conversion_00"].cagr_delta_vs_leader).max() < 1e-12),
        "leave_one_out_complete": bool(loo.cik10.nunique() == choices.cik10.nunique()),
        "finite_outputs": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    focus.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    for (scenario, cost, weight), path in blend_paths_out.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{scenario}__cash_conversion_{int(weight*100):02d}__{cost}bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "best_recent_blend": best.candidate, "best_trailing_1y_cagr_50bps": float(best.cagr),
        "best_trailing_1y_sharpe_50bps": float(best.sharpe_zero_rf), "best_trailing_1y_drawdown_50bps": float(best.max_drawdown),
        "best_trailing_1y_cagr_200bps": float(severe.cagr),
        "largest_recent_single_company": largest.company_name, "largest_recent_single_company_cagr_contribution": float(largest.cagr_contribution),
        "leave_one_out_recent_companies": int(len(relevant)), "all_validation_checks_passed": bool(all(checks.values())),
        "validation_checks": checks, "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Cash-conversion confirmation and leader blend v1\n\n"
        f"The strongest trailing-year blend was **{best.candidate}** at **{best.cagr:.2%} CAGR**, **{best.sharpe_zero_rf:.3f} Sharpe**, and **{best.max_drawdown:.2%} drawdown** at 50 bps. At 200 bps its trailing-year CAGR was **{severe.cagr:.2%}**.\n\n"
        f"The largest recent leave-one-company-out CAGR contribution was **{largest.cagr_contribution:.2%}** from {largest.company_name}. Results remain research-only and are not promoted.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
