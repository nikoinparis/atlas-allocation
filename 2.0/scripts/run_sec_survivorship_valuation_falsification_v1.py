#!/usr/bin/env python3
"""Falsify the broad split-normalized valuation discovery across liquidity, breadth, timing, and exclusions."""

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

CONFIG = ROOT / "config/sec_survivorship_valuation_falsification_v1.json"
DISCOVERY = ROOT / "evidence/sec_survivorship_valuation_discovery_v1"
OUTPUT = ROOT / "evidence/sec_survivorship_valuation_falsification_v1"


def candidate_name(family: str, breadth: int, floor: int) -> str:
    return f"{family}__top{breadth}__floor{floor // 1_000_000}m"


def choose(scores: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for (decision, family), frame in scores.groupby(["decision_at", "family"], sort=True):
        for floor in config["market_cap_floors"]:
            usable = frame.dropna(subset=["score", "market_cap"])
            usable = usable[usable.market_cap >= float(floor)]
            for breadth in config["breadths"]:
                if len(usable) < int(breadth):
                    continue
                selected = usable.sort_values(["score", "cik10"], ascending=[False, True]).head(int(breadth))
                for row in selected.itertuples(index=False):
                    rows.append({"decision_at": decision, "family": family, "breadth": int(breadth), "market_cap_floor": int(floor), "candidate": candidate_name(family, int(breadth), int(floor)), "cik10": row.cik10, "company_name": row.company_name_as_filed, "sector": row.sector, "score": row.score, "market_cap": row.market_cap, "intended_weight": 1.0 / int(breadth)})
    return pd.DataFrame(rows)


def shifted_targets(targets: dict[pd.Timestamp, list[str]], index: pd.DatetimeIndex, delay: int) -> dict[pd.Timestamp, list[str]]:
    output = {}
    for date, assets in targets.items():
        positions = np.flatnonzero(index >= date)
        if len(positions) and positions[0] + delay < len(index):
            output[index[positions[0] + delay]] = assets
    return output


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = choose(scores, config)
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp("2023-01-01"), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = discovery.source_map(), base.terminal_dates()
    price_series = {}
    for cik in sorted(set(choices.cik10)):
        spec = sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(price_series, index=weekly_index)

    performance_rows, paths, events = [], {}, []
    for cost in config["cost_bps"]:
        for candidate, selected in choices.groupby("candidate", sort=True):
            targets = base.build_targets(selected, weekly_index)
            for scenario in ["base", "adverse"]:
                path, event = base.simulate(weekly, targets, scenario, float(cost))
                performance_rows.extend(base.metric_rows(candidate, scenario, int(cost), path))
                event["candidate"], event["cost_bps"] = candidate, int(cost)
                events.append(event)
                if int(cost) == 50 and scenario == "base":
                    paths[candidate] = path
    performance = pd.DataFrame(performance_rows)
    primary = performance[(performance.cost_bps == 50) & (performance.scenario == "base")]
    recent = primary[primary.window == "trailing_1y"].sort_values("cagr", ascending=False)
    full = primary[primary.window == "full_recent"][["candidate", "cagr", "sharpe_zero_rf", "max_drawdown"]].rename(columns={"cagr": "full_cagr", "sharpe_zero_rf": "full_sharpe", "max_drawdown": "full_drawdown"})
    ranking = recent.merge(full, on="candidate", how="left")
    best_name = str(ranking.iloc[0].candidate)
    best_choices = choices[choices.candidate == best_name]
    best_targets = base.build_targets(best_choices, weekly_index)

    delay_rows = []
    for delay in config["execution_delays_weeks"]:
        for cost in config["cost_bps"]:
            path, _ = base.simulate(weekly, shifted_targets(best_targets, weekly_index, int(delay)), "base", float(cost))
            for row in base.metric_rows(best_name, f"delay_{delay}", int(cost), path):
                delay_rows.append(row)
    delays = pd.DataFrame(delay_rows)

    end_date = paths[best_name].index.max()
    recent_start = end_date - pd.DateOffset(years=1)
    recent_ciks = sorted(set(best_choices.loc[best_choices.decision_at.dt.tz_localize(None) >= recent_start - pd.DateOffset(months=3), "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        stressed = weekly.copy()
        stressed[cik] = np.nan
        path, _ = base.simulate(stressed, best_targets, "base", 50.0)
        metric = base.standard_metrics(path.loc[path.index >= recent_start])
        company = best_choices.loc[best_choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "trailing_1y_cagr": metric["cagr"], "trailing_1y_sharpe": metric["sharpe_zero_rf"], "trailing_1y_drawdown": metric["max_drawdown"], "cagr_delta": metric["cagr"] - float(ranking.iloc[0].cagr)})
    loo = pd.DataFrame(loo_rows).sort_values("trailing_1y_cagr")

    split_ciks = set(pd.read_csv(DISCOVERY / "split_distortion_audit.csv", dtype={"cik10": str}).cik10)
    split_stressed = weekly.copy()
    for cik in split_ciks & set(split_stressed.columns):
        split_stressed[cik] = np.nan
    split_path, _ = base.simulate(split_stressed, best_targets, "base", 50.0)
    split_recent = base.standard_metrics(split_path.loc[split_path.index >= recent_start])
    split_full = base.standard_metrics(split_path)

    ranking["recent_above_control"] = ranking.cagr > float(config["concentration_control_recent_cagr"])
    ranking["full_above_control"] = ranking.full_cagr > float(config["require_full_cagr_above"])
    qualifying = ranking[ranking.recent_above_control & ranking.full_above_control]
    worst_loo = loo.iloc[0]
    delay_recent = delays[(delays.cost_bps == 50) & (delays.window == "trailing_1y")].sort_values("scenario")
    checks = {
        "market_cap_floors_reported": set(choices.market_cap_floor) == set(config["market_cap_floors"]),
        "breadths_reported": set(choices.breadth) == set(config["breadths"]),
        "base_and_adverse_reported": True,
        "costs_reported": set(performance.cost_bps) == set(config["cost_bps"]),
        "delays_reported": set(int(value.rsplit("_", 1)[1]) for value in delays.scenario.unique()) == set(config["execution_delays_weeks"]),
        "leave_one_company_out_reported": bool(len(loo)),
        "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ranking.to_csv(OUTPUT / "recent_full_ranking.csv", index=False)
    path_directory = OUTPUT / "candidate_paths_50bps"
    path_directory.mkdir(parents=True, exist_ok=True)
    for candidate in ranking.head(20).candidate:
        paths[str(candidate)].rename_axis("Date").to_csv(path_directory / f"{candidate}.csv")
    choices.to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    pd.concat(events, ignore_index=True).to_csv(OUTPUT / "rebalance_events.csv", index=False)
    delays.to_csv(OUTPUT / "delay_and_cost_stress.csv", index=False)
    loo.to_csv(OUTPUT / "recent_leave_one_company_out.csv", index=False)
    paths[best_name].rename_axis("Date").to_csv(OUTPUT / "best_path_50bps.csv")
    split_path.rename_axis("Date").to_csv(OUTPUT / "best_path_excluding_split_affected_50bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tested_candidate_structures": int(choices.candidate.nunique()), "best_candidate": best_name,
        "best_recent_50bps_cagr": float(ranking.iloc[0].cagr), "best_recent_50bps_sharpe": float(ranking.iloc[0].sharpe_zero_rf), "best_recent_50bps_drawdown": float(ranking.iloc[0].max_drawdown),
        "best_full_50bps_cagr": float(ranking.iloc[0].full_cagr), "best_full_50bps_drawdown": float(ranking.iloc[0].full_drawdown),
        "candidates_beating_control_recent_and_full": int(len(qualifying)),
        "worst_recent_exclusion_company": str(worst_loo.company_name), "worst_recent_exclusion_cagr": float(worst_loo.trailing_1y_cagr),
        "one_week_delay_recent_cagr": float(delay_recent[delay_recent.scenario == "delay_1"].iloc[0].cagr),
        "two_week_delay_recent_cagr": float(delay_recent[delay_recent.scenario == "delay_2"].iloc[0].cagr),
        "exclude_all_split_affected_recent_cagr": float(split_recent["cagr"]), "exclude_all_split_affected_full_cagr": float(split_full["cagr"]),
        "concentration_gate_passed": bool(worst_loo.trailing_1y_cagr >= float(config["minimum_recent_exclusion_cagr"])),
        "replacement_return_gate_passed": bool(len(qualifying) > 0),
        "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Survivorship-aware valuation falsification v1\n\n"
        f"Tested {result['tested_candidate_structures']} family/breadth/liquidity structures. The best candidate was `{best_name}` at {result['best_recent_50bps_cagr']:.2%} recent CAGR and {result['best_full_50bps_cagr']:.2%} full CAGR. "
        f"Worst recent leave-one-company-out CAGR was {result['worst_recent_exclusion_cagr']:.2%} after excluding {result['worst_recent_exclusion_company']}.\n\n"
        f"One- and two-week delays retained {result['one_week_delay_recent_cagr']:.2%} and {result['two_week_delay_recent_cagr']:.2%}. "
        f"Excluding every split-affected issuer produced {result['exclude_all_split_affected_recent_cagr']:.2%} recent and {result['exclude_all_split_affected_full_cagr']:.2%} full CAGR.\n\n"
        "No strategy is promoted by this retrospective audit. A controlled overlay must still improve the frozen leader under cost, delay, and exclusion stress.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
