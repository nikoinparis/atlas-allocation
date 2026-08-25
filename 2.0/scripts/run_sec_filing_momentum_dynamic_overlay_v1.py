#!/usr/bin/env python3
"""Conditionally allocate to the strongest causal SEC filing-momentum sleeve."""

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
import run_sec_survivorship_valuation_overlay_search_v1 as overlay

CONFIG = ROOT / "config/sec_filing_momentum_dynamic_overlay_v1.json"
SEARCH = ROOT / "evidence/sec_filing_fundamental_momentum_search_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_filing_momentum_dynamic_overlay_v1"


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(SEARCH / "best_portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices["cik10"] = choices.cik10.str.zfill(10)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp("2023-01-01"), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = discovery.source_map(), base.terminal_dates()
    series = {}
    for cik in sorted(set(choices.cik10)):
        spec = sources.get(cik)
        if spec:
            try:
                series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(series, index=weekly_index)
    targets = {pd.Timestamp(date): frame.sort_values("cik10").cik10.tolist() for date, frame in choices.groupby("decision_at")}
    rows, paths = [], {}
    recent_start = control.index.max() - pd.DateOffset(years=1)
    for underlying_cost in config["cost_bps"]:
        sleeve, _ = base.simulate(weekly, targets, "base", float(underlying_cost))
        joined = pd.concat([control, sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
        for lookback in config["lookbacks_weeks"]:
            leader_prior = (1.0 + joined.control).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
            sleeve_prior = (1.0 + joined.sleeve).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
            for gate in config["gates"]:
                condition = {
                    "relative": sleeve_prior > leader_prior,
                    "relative_positive": (sleeve_prior > leader_prior) & (sleeve_prior > 0.0),
                    "sleeve_positive": sleeve_prior > 0.0,
                    "leader_negative_relative": (leader_prior < 0.0) & (sleeve_prior > leader_prior),
                    "leader_negative_sleeve_positive": (leader_prior < 0.0) & (sleeve_prior > 0.0),
                }[gate]
                for allocation in config["allocations"]:
                    target = condition.astype(float) * float(allocation)
                    for outer_cost in config["cost_bps"]:
                        path = overlay.simulate(joined.control, joined.sleeve, target, float(outer_cost))
                        recent = overlay.metrics(path.loc[path.index >= recent_start, "net_return"])
                        full = overlay.metrics(path.net_return)
                        candidate = f"{gate}__lb{lookback}__w{float(allocation):.2f}__under{underlying_cost}__outer{outer_cost}"
                        rows.append({"candidate": candidate, "gate": gate, "lookback_weeks": lookback, "allocation": allocation, "underlying_cost_bps": underlying_cost, "outer_cost_bps": outer_cost, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"], "active_share": float((path.valuation_weight > 0.0).mean()), "average_sleeve_weight": float(path.valuation_weight.mean())})
                        paths[candidate] = path
    performance = pd.DataFrame(rows)
    primary = performance[(performance.underlying_cost_bps == 50) & (performance.outer_cost_bps == 50)].sort_values(["recent_cagr", "full_cagr"], ascending=False).copy()
    primary["beats_control_both"] = (primary.recent_cagr > float(config["control_recent_cagr"])) & (primary.full_cagr > float(config["control_full_cagr"]))
    best = primary.iloc[0]
    severe = performance[(performance.gate == best.gate) & (performance.lookback_weeks == best.lookback_weeks) & np.isclose(performance.allocation, best.allocation) & (performance.underlying_cost_bps == 200) & (performance.outer_cost_bps == 200)].iloc[0]
    paths[str(best.candidate)].rename_axis("Date").to_csv(OUTPUT / "best_path.csv")
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    primary.head(100).to_csv(OUTPUT / "top_candidates.csv", index=False)
    checks = {"signals_shifted": int(config["signal_shift_weeks"]) >= 1, "all_gates_reported": set(performance.gate) == set(config["gates"]), "all_costs_reported": set(performance.outer_cost_bps) == set(config["cost_bps"]), "allocations_bounded": bool(performance.allocation.between(0.0, 0.5).all()), "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all())}
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "tested_paths": int(len(performance)), "best_candidate": str(best.candidate), "best_recent_cagr": float(best.recent_cagr), "best_recent_sharpe": float(best.recent_sharpe), "best_recent_drawdown": float(best.recent_drawdown), "best_full_cagr": float(best.full_cagr), "best_full_drawdown": float(best.full_drawdown), "active_share": float(best.active_share), "average_sleeve_weight": float(best.average_sleeve_weight), "severe_200bps_recent_cagr": float(severe.recent_cagr), "candidates_beating_control_both": int(primary.beats_control_both.sum()), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# SEC filing momentum dynamic overlay v1\n\n" f"Tested {len(performance):,} lagged conditional allocations. The best candidate produced {best.recent_cagr:.2%} recent CAGR, {best.recent_sharpe:.2f} Sharpe, {best.recent_drawdown:.2%} drawdown, and {best.full_cagr:.2%} full CAGR. At severe 200-bps costs it retained {severe.recent_cagr:.2%}.\n\n" "All allocation gates use only rolling returns shifted by one week. No result is promoted without delay and issuer-exclusion falsification.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
