#!/usr/bin/env python3
"""Audit diversified valuation overlays under delay, cost, and issuer-removal stress."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_survivorship_valuation_discovery_v1 as discovery
import run_sec_diversified_valuation_ensemble_search_v1 as search
import run_sec_survivorship_valuation_overlay_search_v1 as overlay

CONFIG = ROOT / "config/sec_diversified_valuation_ensemble_audit_v1.json"
SEARCH = ROOT / "evidence/sec_diversified_valuation_ensemble_search_v1"
DISCOVERY = ROOT / "evidence/sec_survivorship_valuation_discovery_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_diversified_valuation_ensemble_audit_v1"


def parse_candidate(name: str) -> dict:
    match = re.fullmatch(r"(.+)__cohort(\d+)__w([0-9.]+)__50bps", name)
    if not match:
        raise ValueError(f"unparseable candidate: {name}")
    return {"sleeve": match.group(1), "cohorts": int(match.group(2)), "allocation": float(match.group(3))}


def combine(control: pd.Series, sleeve: pd.DataFrame, allocation: float, cost: float) -> pd.DataFrame:
    joined = pd.concat([control, sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
    return overlay.simulate(joined.control, joined.sleeve, pd.Series(float(allocation), index=joined.index), float(cost))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(SEARCH / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp("2023-01-01"), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    selected_ciks = set(choices.loc[choices.sleeve.isin([parse_candidate(x)["sleeve"] for x in config["candidates"]]), "cik10"])
    sources, terminals = discovery.source_map(), base.terminal_dates()
    price_series = {}
    for cik in sorted(selected_ciks):
        spec = sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(price_series, index=weekly_index)
    split_ciks = set(pd.read_csv(DISCOVERY / "split_distortion_audit.csv", dtype={"cik10": str}).cik10)
    for cik in split_ciks & set(weekly.columns):
        weekly[cik] = np.nan
    recent_start = control.index.max() - pd.DateOffset(years=1)

    stress_rows, loo_rows, summary_rows, paths = [], [], [], {}
    for candidate in config["candidates"]:
        parsed = parse_candidate(candidate)
        selected = choices[choices.sleeve == parsed["sleeve"]]
        targets = base.build_targets(selected, weekly_index)
        for delay in config["execution_delays_weeks"]:
            for cost in config["cost_bps"]:
                sleeve = search.cohort_sleeve(weekly, targets, parsed["cohorts"], float(cost), int(delay))
                path = combine(control, sleeve, parsed["allocation"], float(cost))
                recent = overlay.metrics(path.loc[path.index >= recent_start, "net_return"])
                full = overlay.metrics(path.net_return)
                stress_rows.append({"candidate": candidate, "delay_weeks": delay, "cost_bps": cost, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"]})
                if delay == 0 and cost == 50:
                    paths[candidate] = path

        recent_ciks = sorted(set(selected.loc[selected.decision_at.dt.tz_localize(None) >= recent_start - pd.DateOffset(months=3), "cik10"]) - split_ciks)
        for cik in recent_ciks:
            stressed = weekly.copy()
            stressed[cik] = np.nan
            sleeve = search.cohort_sleeve(stressed, targets, parsed["cohorts"], 50.0)
            path = combine(control, sleeve, parsed["allocation"], 50.0)
            recent = overlay.metrics(path.loc[path.index >= recent_start, "net_return"])
            full = overlay.metrics(path.net_return)
            company_rows = selected[selected.cik10 == cik]
            company = str(company_rows.company_name.iloc[-1]) if len(company_rows) else cik
            loo_rows.append({"candidate": candidate, "cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"]})

    stresses = pd.DataFrame(stress_rows)
    loo = pd.DataFrame(loo_rows)
    for candidate in config["candidates"]:
        primary = stresses[(stresses.candidate == candidate) & (stresses.delay_weeks == 0) & (stresses.cost_bps == 50)].iloc[0]
        delay1 = stresses[(stresses.candidate == candidate) & (stresses.delay_weeks == 1) & (stresses.cost_bps == 50)].iloc[0]
        delay2 = stresses[(stresses.candidate == candidate) & (stresses.delay_weeks == 2) & (stresses.cost_bps == 50)].iloc[0]
        severe = stresses[(stresses.candidate == candidate) & (stresses.delay_weeks == 0) & (stresses.cost_bps == 200)].iloc[0]
        candidate_loo = loo[loo.candidate == candidate].sort_values("recent_cagr")
        worst = candidate_loo.iloc[0]
        joined = pd.concat([paths[candidate].net_return.rename("candidate"), control], axis=1, join="inner").dropna()
        candidate_roll = (1.0 + joined.candidate).rolling(26).apply(np.prod, raw=True) - 1.0
        control_roll = (1.0 + joined.control).rolling(26).apply(np.prod, raw=True) - 1.0
        rolling_win = float((candidate_roll.dropna() > control_roll.reindex(candidate_roll.dropna().index)).mean())
        summary_rows.append({"candidate": candidate, "recent_cagr": primary.recent_cagr, "recent_sharpe": primary.recent_sharpe, "recent_drawdown": primary.recent_drawdown, "full_cagr": primary.full_cagr, "one_week_delay_recent_cagr": delay1.recent_cagr, "two_week_delay_recent_cagr": delay2.recent_cagr, "severe_200bps_recent_cagr": severe.recent_cagr, "worst_loo_company": worst.company_name, "worst_loo_recent_cagr": worst.recent_cagr, "worst_loo_full_cagr": worst.full_cagr, "rolling_26w_win_rate": rolling_win})
    summary = pd.DataFrame(summary_rows)
    summary["base_gate"] = (summary.recent_cagr > float(config["control_recent_cagr"])) & (summary.full_cagr > float(config["control_full_cagr"]))
    summary["delay_gate"] = (summary.one_week_delay_recent_cagr > float(config["control_recent_cagr"])) & (summary.two_week_delay_recent_cagr > float(config["control_recent_cagr"]))
    summary["loo_gate"] = (summary.worst_loo_recent_cagr > float(config["control_recent_cagr"])) & (summary.worst_loo_full_cagr > float(config["control_full_cagr"]))
    summary["rolling_gate"] = summary.rolling_26w_win_rate >= float(config["minimum_rolling_26w_win_rate"])
    summary["all_return_gates"] = summary[["base_gate", "delay_gate", "loo_gate", "rolling_gate"]].all(axis=1)
    passing = summary[summary.all_return_gates].sort_values(["recent_cagr", "recent_sharpe"], ascending=False)
    chosen = passing.iloc[0] if len(passing) else summary.sort_values(["loo_gate", "recent_cagr"], ascending=False).iloc[0]
    paths[str(chosen.candidate)].rename_axis("Date").to_csv(OUTPUT / "best_audited_path_50bps.csv")
    stresses.to_csv(OUTPUT / "delay_and_cost_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_issuer_out.csv", index=False)
    summary.to_csv(OUTPUT / "candidate_summary.csv", index=False)
    checks = {"all_candidates_reported": set(summary.candidate) == set(config["candidates"]), "all_delays_reported": set(stresses.delay_weeks) == set(config["execution_delays_weeks"]), "all_costs_reported": set(stresses.cost_bps) == set(config["cost_bps"]), "leave_one_out_reported": bool(len(loo)), "results_finite": bool(np.isfinite(stresses.select_dtypes("number").to_numpy()).all() and np.isfinite(loo.select_dtypes("number").to_numpy()).all())}
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "audited_candidates": int(len(summary)), "passing_candidates": int(len(passing)), "best_audited_candidate": str(chosen.candidate), "recent_cagr": float(chosen.recent_cagr), "recent_sharpe": float(chosen.recent_sharpe), "recent_drawdown": float(chosen.recent_drawdown), "full_cagr": float(chosen.full_cagr), "one_week_delay_recent_cagr": float(chosen.one_week_delay_recent_cagr), "two_week_delay_recent_cagr": float(chosen.two_week_delay_recent_cagr), "severe_200bps_recent_cagr": float(chosen.severe_200bps_recent_cagr), "worst_loo_company": str(chosen.worst_loo_company), "worst_loo_recent_cagr": float(chosen.worst_loo_recent_cagr), "worst_loo_full_cagr": float(chosen.worst_loo_full_cagr), "rolling_26w_win_rate": float(chosen.rolling_26w_win_rate), "all_return_gates_passed": bool(chosen.all_return_gates), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# Diversified valuation ensemble audit v1\n\n" f"Audited {len(summary)} leading structural neighborhoods. {len(passing)} passed the declared base, delay, leave-one-issuer-out, and rolling-window gates. The best audited candidate produced {chosen.recent_cagr:.2%} recent CAGR, {chosen.recent_sharpe:.2f} Sharpe, {chosen.recent_drawdown:.2%} drawdown, and {chosen.full_cagr:.2%} full CAGR.\n\n" f"One- and two-week delays produced {chosen.one_week_delay_recent_cagr:.2%} and {chosen.two_week_delay_recent_cagr:.2%}; severe costs produced {chosen.severe_200bps_recent_cagr:.2%}. The weakest issuer exclusion was {chosen.worst_loo_company} at {chosen.worst_loo_recent_cagr:.2%} recent and {chosen.worst_loo_full_cagr:.2%} full CAGR.\n\n" "This remains research-only and does not enable execution or live trading.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
