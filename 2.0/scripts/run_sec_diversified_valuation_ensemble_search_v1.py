#!/usr/bin/env python3
"""Search diversified point-in-time valuation ensembles beside the frozen weekly leader."""

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

CONFIG = ROOT / "config/sec_diversified_valuation_ensemble_search_v1.json"
DISCOVERY = ROOT / "evidence/sec_survivorship_valuation_discovery_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_diversified_valuation_ensemble_search_v1"


def build_ensemble_scores(scores: pd.DataFrame, family_sets: dict[str, list[str]]) -> pd.DataFrame:
    identity = ["decision_at", "cik10", "company_name_as_filed", "sector", "market_cap"]
    wide = scores.pivot_table(index=identity, columns="family", values="score", aggfunc="first").reset_index()
    rows = []
    for name, families in family_sets.items():
        frame = wide[identity].copy()
        values = wide[families]
        frame["ensemble"] = name
        required = 1 if len(families) == 1 else 2
        frame["score"] = values.mean(axis=1, skipna=True).where(values.notna().sum(axis=1) >= required)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def select_with_sector_cap(frame: pd.DataFrame, breadth: int, cap: float) -> pd.DataFrame:
    maximum = max(1, int(np.floor(float(breadth) * float(cap) + 1e-12)))
    counts: dict[str, int] = {}
    selected = []
    for row in frame.sort_values(["score", "cik10"], ascending=[False, True]).itertuples(index=False):
        sector = str(row.sector)
        if counts.get(sector, 0) >= maximum:
            continue
        selected.append(row)
        counts[sector] = counts.get(sector, 0) + 1
        if len(selected) == int(breadth):
            break
    return pd.DataFrame(selected, columns=frame.columns) if len(selected) == int(breadth) else pd.DataFrame(columns=frame.columns)


def build_choices(ensemble_scores: pd.DataFrame, config: dict) -> pd.DataFrame:
    rows = []
    for (decision, ensemble), frame in ensemble_scores.groupby(["decision_at", "ensemble"], sort=True):
        usable = frame.dropna(subset=["score", "market_cap"])
        for floor in config["market_cap_floors"]:
            liquid = usable[usable.market_cap >= float(floor)]
            for breadth in config["breadths"]:
                for sector_cap in config["sector_caps"]:
                    chosen = select_with_sector_cap(liquid, int(breadth), float(sector_cap))
                    if len(chosen) != int(breadth):
                        continue
                    sleeve = f"{ensemble}__top{breadth}__floor{int(floor)//1_000_000}m__sector{int(float(sector_cap)*100)}"
                    for row in chosen.itertuples(index=False):
                        rows.append({"decision_at": decision, "sleeve": sleeve, "ensemble": ensemble, "breadth": int(breadth), "market_cap_floor": int(floor), "sector_cap": float(sector_cap), "cik10": row.cik10, "company_name": row.company_name_as_filed, "sector": row.sector, "score": row.score, "market_cap": row.market_cap, "intended_weight": 1.0 / int(breadth)})
    return pd.DataFrame(rows)


def cohort_sleeve(weekly: pd.DataFrame, targets: dict, cohorts: int, cost: float, extra_delay: int = 0) -> pd.DataFrame:
    paths = []
    for offset in range(int(cohorts)):
        shifted = falsification.shifted_targets(targets, weekly.index, int(offset) + int(extra_delay))
        path, _ = base.simulate(weekly, shifted, "base", float(cost))
        paths.append(path)
    result = paths[0].copy()
    for column in ["gross_return", "turnover", "cost", "net_return"]:
        result[column] = pd.concat([path[column] for path in paths], axis=1).mean(axis=1)
    result["wealth"] = (1.0 + result.net_return).cumprod()
    result["drawdown"] = result.wealth / result.wealth.cummax() - 1.0
    return result


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    ensemble_scores = build_ensemble_scores(scores, config["family_sets"])
    choices = build_choices(ensemble_scores, config)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
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
    split_ciks = set(pd.read_csv(DISCOVERY / "split_distortion_audit.csv", dtype={"cik10": str}).cik10)
    if config["exclude_split_affected"]:
        for cik in split_ciks & set(weekly.columns):
            weekly[cik] = np.nan

    rows, primary_paths = [], {}
    recent_start = control.index.max() - pd.DateOffset(years=1)
    for sleeve_name, selected in choices.groupby("sleeve", sort=True):
        targets = base.build_targets(selected, weekly_index)
        for cohorts in config["staggered_cohorts"]:
            for cost in config["cost_bps"]:
                sleeve = cohort_sleeve(weekly, targets, int(cohorts), float(cost))
                joined = pd.concat([control, sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
                for allocation in config["overlay_allocations"]:
                    target = pd.Series(float(allocation), index=joined.index)
                    path = overlay.simulate(joined.control, joined.sleeve, target, float(cost))
                    recent = overlay.metrics(path.loc[path.index >= recent_start, "net_return"])
                    full = overlay.metrics(path.net_return)
                    candidate = f"{sleeve_name}__cohort{cohorts}__w{float(allocation):.2f}__{cost}bps"
                    rows.append({"candidate": candidate, "sleeve": sleeve_name, "ensemble": selected.ensemble.iloc[0], "breadth": int(selected.breadth.iloc[0]), "market_cap_floor": int(selected.market_cap_floor.iloc[0]), "sector_cap": float(selected.sector_cap.iloc[0]), "cohorts": int(cohorts), "allocation": float(allocation), "cost_bps": int(cost), "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"]})
                    if int(cost) == 50:
                        primary_paths[candidate] = path
    performance = pd.DataFrame(rows)
    ranking = performance[performance.cost_bps == 50].sort_values(["recent_cagr", "full_cagr"], ascending=False).copy()
    ranking["beats_control_both"] = (ranking.recent_cagr > float(config["control_recent_cagr"])) & (ranking.full_cagr > float(config["control_full_cagr"]))
    best = ranking.iloc[0]
    severe = performance[(performance.sleeve == best.sleeve) & (performance.cohorts == best.cohorts) & np.isclose(performance.allocation, best.allocation) & (performance.cost_bps == 200)].iloc[0]
    choices.to_csv(OUTPUT / "portfolio_choices.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ranking.head(200).to_csv(OUTPUT / "top_candidates.csv", index=False)
    primary_paths[str(best.candidate)].rename_axis("Date").to_csv(OUTPUT / "best_path_50bps.csv")
    checks = {"all_family_sets_reported": set(choices.ensemble) == set(config["family_sets"]), "all_breadths_reported": set(choices.breadth) == set(config["breadths"]), "all_sector_caps_reported": set(choices.sector_cap) == set(config["sector_caps"]), "all_cohorts_reported": set(performance.cohorts) == set(config["staggered_cohorts"]), "all_costs_reported": set(performance.cost_bps) == set(config["cost_bps"]), "weights_bounded": bool(performance.allocation.between(0.0, 0.4).all()), "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all())}
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "tested_sleeves": int(choices.sleeve.nunique()), "tested_paths": int(len(performance)), "best_candidate": str(best.candidate), "best_recent_cagr": float(best.recent_cagr), "best_recent_sharpe": float(best.recent_sharpe), "best_recent_drawdown": float(best.recent_drawdown), "best_full_cagr": float(best.full_cagr), "best_full_drawdown": float(best.full_drawdown), "severe_200bps_recent_cagr": float(severe.recent_cagr), "candidates_beating_control_both": int(ranking.beats_control_both.sum()), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# Diversified valuation ensemble search v1\n\n" f"Tested {result['tested_paths']:,} costed paths across {result['tested_sleeves']} diversified sleeves. The best path produced {best.recent_cagr:.2%} recent CAGR, {best.recent_sharpe:.2f} Sharpe, {best.recent_drawdown:.2%} drawdown, and {best.full_cagr:.2%} full CAGR. At 200 bps it retained {severe.recent_cagr:.2%} recent CAGR.\n\n" "No result is promoted until the leading diversified candidates survive extra execution delay and leave-one-issuer-out audits.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
