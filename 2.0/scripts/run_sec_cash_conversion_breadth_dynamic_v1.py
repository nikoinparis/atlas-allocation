#!/usr/bin/env python3
"""Breadth and cap expansion for the conditional cash-conversion sleeve."""

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

CONFIG = ROOT / "config/sec_cash_conversion_breadth_dynamic_v1.json"
DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER_ROOT = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1"


def make_choices(scores: pd.DataFrame, breadth: int) -> pd.DataFrame:
    rows = []
    for decision, frame in scores.groupby("decision_at", sort=True):
        selected = frame.dropna(subset=["score"]).sort_values(["score", "cik10"], ascending=[False, True]).head(breadth)
        for row in selected.itertuples(index=False):
            rows.append({"decision_at": decision, "cik10": row.cik10, "company_name": row.company_name_as_filed, "score": row.score, "intended_weight": 1 / breadth})
    return pd.DataFrame(rows)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    scores = scores[scores.family == "cash_conversion"]
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    leader_paths = {(scenario, int(cost)): dynamic.read_path(LEADER_ROOT / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return for scenario in config["scenarios"] for cost in config["cost_bps"]}

    cash_paths, peak_weights, choices_by_breadth, prices_by_breadth = {}, {}, {}, {}
    for breadth in config["breadths"]:
        choices = make_choices(scores, int(breadth))
        choices_by_breadth[int(breadth)] = choices
        targets = base.build_targets(choices, index)
        series = {}
        for cik in sorted(set(choices.cik10)):
            if cik in sources:
                source, path = sources[cik]
                series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
        weekly = pd.DataFrame(series, index=index)
        prices_by_breadth[int(breadth)] = weekly
        for cap in config["cap_multiples"]:
            cap_label = "uncapped" if cap is None else f"cap_{cap:.2f}x"
            for scenario in config["scenarios"]:
                for cost in config["cost_bps"]:
                    path, peak = capped.simulate_cash(weekly, targets, scenario, float(cost), cap, int(breadth))
                    cash_paths[(int(breadth), cap_label, scenario, int(cost))] = path
                    peak_weights[(int(breadth), cap_label, scenario, int(cost))] = peak

    performance_rows, paths = [], {}
    for breadth in config["breadths"]:
        for cap in config["cap_multiples"]:
            cap_label = "uncapped" if cap is None else f"cap_{cap:.2f}x"
            signal = pd.concat([leader_paths[("base", 50)].rename("leader"), cash_paths[(int(breadth), cap_label, "base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
            for lookback in config["lookbacks"]:
                for high in config["active_allocations"]:
                    target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(lookback), float(high))
                    name = f"breadth{breadth}__{cap_label}__{lookback}w__{int(high*100)}"
                    for scenario in config["scenarios"]:
                        for cost in config["cost_bps"]:
                            returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), cash_paths[(int(breadth), cap_label, scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
                            path = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
                            paths[(name, scenario, int(cost))] = path
                            performance_rows.extend(base.metric_rows(name, scenario, int(cost), path))
    performance = pd.DataFrame(performance_rows)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50) & performance.window.isin(["full_recent", "trailing_1y", "ytd"])].pivot(index="candidate", columns="window", values=["cagr", "sharpe_zero_rf", "max_drawdown"])
    primary.columns = [f"{a}_{b}" for a, b in primary.columns]
    severe = performance[(performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].set_index("candidate")
    primary["trailing_1y_200bps_cagr"] = severe.cagr
    primary = primary.reset_index().sort_values("cagr_trailing_1y", ascending=False)
    best = primary.iloc[0]
    parts = best.candidate.split("__")
    breadth, cap_label, lookback, high = int(parts[0].replace("breadth", "")), parts[1], int(parts[2][:-1]), int(parts[3]) / 100

    # Exact leave-one-company-out audit for the best breadth/cap configuration.
    choices = choices_by_breadth[breadth]
    targets = base.build_targets(choices, index)
    weekly = prices_by_breadth[breadth]
    cap_value = None if cap_label == "uncapped" else float(cap_label.replace("cap_", "").replace("x", ""))
    baseline_cash = cash_paths[(breadth, cap_label, "base", 50)]
    baseline_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), baseline_cash.net_return.rename("cash_conversion")], axis=1).dropna()
    baseline_target = capped.overlay_target(baseline_returns.index, baseline_returns.leader, baseline_returns.cash_conversion, lookback, high)
    baseline_path = dynamic.simulate(baseline_returns, baseline_target, 50.0)
    baseline_recent = next(row for row in base.metric_rows(best.candidate, "base", 50, baseline_path) if row["window"] == "trailing_1y")
    loo_rows = []
    recent_ciks = set(choices.loc[choices.decision_at >= choices.decision_at.max() - pd.DateOffset(years=1), "cik10"])
    for cik in sorted(recent_ciks):
        altered = weekly.copy()
        altered[cik] = pd.NA
        loo_cash, _ = capped.simulate_cash(altered, targets, "base", 50.0, cap_value, breadth)
        returns = pd.concat([leader_paths[("base", 50)].rename("leader"), loo_cash.net_return.rename("cash_conversion")], axis=1).dropna()
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, lookback, high)
        path = dynamic.simulate(returns, target, 50.0)
        recent = next(row for row in base.metric_rows(best.candidate, "base", 50, path) if row["window"] == "trailing_1y")
        loo_rows.append({"cik10": cik, "company_name": choices.loc[choices.cik10 == cik, "company_name"].iloc[-1], "trailing_1y_cagr": recent["cagr"], "cagr_change": recent["cagr"] - baseline_recent["cagr"]})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    control_cagr = 0.9231041941304314
    primary.to_csv(OUTPUT / "screening.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    loo.to_csv(OUTPUT / "best_recent_leave_one_company_out.csv", index=False)
    baseline_target.rename_axis("Date").to_csv(OUTPUT / "best_target_weights.csv")
    choices.to_csv(OUTPUT / "best_portfolio_choices.csv", index=False)
    latest_choices = choices[choices.decision_at == choices.decision_at.max()].copy()
    current_cash_allocation = float(baseline_target.cash_conversion.iloc[-1])
    latest_choices["current_total_portfolio_target_weight"] = current_cash_allocation / breadth
    latest_choices.to_csv(OUTPUT / "best_current_cash_conversion_holdings.csv", index=False)
    for cost in config["cost_bps"]:
        paths[(best.candidate, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"best_path__base__{cost}bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(primary)),
        "best_candidate": best.candidate, "best_trailing_1y_cagr": float(best.cagr_trailing_1y), "best_trailing_1y_sharpe": float(best.sharpe_zero_rf_trailing_1y),
        "best_trailing_1y_drawdown": float(best.max_drawdown_trailing_1y), "best_ytd_cagr": float(best.cagr_ytd), "best_full_cagr": float(best.cagr_full_recent),
        "best_200bps_trailing_1y_cagr": float(best.trailing_1y_200bps_cagr), "best_peak_target_stock_weight": float(high * peak_weights[(breadth, cap_label, "base", 50)]),
        "current_cash_conversion_allocation": current_cash_allocation, "current_leader_allocation": 1.0 - current_cash_allocation,
        "worst_recent_exclusion_company": worst.company_name, "worst_recent_exclusion_cagr": float(worst.trailing_1y_cagr),
        "worst_recent_exclusion_beats_control": bool(worst.trailing_1y_cagr > control_cagr), "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
