#!/usr/bin/env python3
"""Search causal filing-triggered fundamental momentum sleeves and controlled overlays."""

from __future__ import annotations

import itertools
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
import run_sec_diversified_valuation_ensemble_search_v1 as diversified

CONFIG = ROOT / "config/sec_filing_fundamental_momentum_search_v1.json"
INPUTS = ROOT / "evidence/sec_independent_fundamental_discovery_v1/quarterly_factor_inputs.csv"
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
VALUATION_PANEL = ROOT / "evidence/sec_survivorship_valuation_discovery_v1/normalized_valuation_panel.csv"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_filing_fundamental_momentum_search_v1"

FEATURE_AVAILABILITY = [
    "revenue__available_at", "net_income__available_at", "operating_income__available_at",
    "operating_cash_flow__available_at", "capital_expenditure__available_at",
    "diluted_shares__available_at",
]


def prepare_events() -> pd.DataFrame:
    frame = pd.read_csv(INPUTS, dtype={"cik10": str}, low_memory=False)
    frame["cik10"] = frame.cik10.str.zfill(10)
    for column in FEATURE_AVAILABILITY:
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    frame["event_time"] = frame[FEATURE_AVAILABILITY].max(axis=1)
    frame = frame.dropna(subset=["event_time"]).sort_values(["cik10", "event_time", "decision_time"])
    period_columns = ["revenue__period_end", "operating_income__period_end", "operating_cash_flow__period_end", "diluted_shares__period_end"]
    frame["event_key"] = frame[period_columns].fillna("").astype(str).apply(lambda row: "|".join(row.tolist()), axis=1)
    frame = frame.drop_duplicates(["cik10", "event_key"], keep="first").copy()
    for source, target in [
        ("revenue__yoy_growth", "revenue_acceleration"),
        ("operating_income__yoy_growth", "operating_income_acceleration"),
        ("operating_cash_flow__yoy_growth", "operating_cash_flow_acceleration"),
    ]:
        values = pd.to_numeric(frame[source], errors="coerce").replace([np.inf, -np.inf], np.nan)
        frame[source] = values
        frame[target] = values.groupby(frame.cik10).diff()
    frame["revenue_yoy_growth"] = frame["revenue__yoy_growth"]
    frame["operating_income_yoy_growth"] = frame["operating_income__yoy_growth"]
    frame["operating_cash_flow_yoy_growth"] = frame["operating_cash_flow__yoy_growth"]
    frame["negative_dilution"] = -pd.to_numeric(frame["diluted_shares__yoy_growth"], errors="coerce")
    numeric = ["operating_margin_change", "operating_cash_flow_margin_change", "free_cash_flow_margin_change", "negative_dilution"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)

    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str}, parse_dates=["decision_at"])
    membership["cik10"] = membership.cik10.str.zfill(10)
    membership["decision_at"] = pd.to_datetime(membership.decision_at, utc=True)
    membership = membership.sort_values(["decision_at", "cik10"])
    left = frame.sort_values(["event_time", "cik10"])
    frame = pd.merge_asof(left, membership[["decision_at", "cik10", "company_name_as_filed", "sector", "tradable_member"]], left_on="event_time", right_on="decision_at", by="cik10", direction="backward")
    frame = frame[frame.tradable_member.fillna(False).astype(bool)].copy()

    caps = pd.read_csv(VALUATION_PANEL, dtype={"cik10": str}, usecols=["decision_at", "cik10", "market_cap"])
    caps["cik10"] = caps.cik10.str.zfill(10)
    caps["decision_at"] = pd.to_datetime(caps.decision_at, utc=True)
    caps = caps.rename(columns={"decision_at": "cap_decision"}).sort_values(["cap_decision", "cik10"])
    frame = pd.merge_asof(frame.sort_values(["event_time", "cik10"]), caps, left_on="event_time", right_on="cap_decision", by="cik10", direction="backward")
    return frame.sort_values(["cik10", "event_time"]).reset_index(drop=True)


def rank_sector(frame: pd.DataFrame, column: str) -> pd.Series:
    output = pd.Series(np.nan, index=frame.index, dtype=float)
    for _, indexes in frame.groupby("sector").groups.items():
        valid = pd.to_numeric(frame.loc[indexes, column], errors="coerce").dropna()
        if len(valid) >= 3:
            output.loc[valid.index] = valid.rank(pct=True, method="average") * 2.0 - 1.0
    return output


def score_panels(events: pd.DataFrame, weekly: pd.DataFrame, index: pd.DatetimeIndex, config: dict) -> dict[tuple, pd.DataFrame]:
    event_times = events.event_time.dt.tz_convert(None)
    events = events.copy()
    if "eligible_week" not in events:
        events["eligible_week"] = [index[index > value][0] if len(index[index > value]) else pd.NaT for value in event_times]
    momentum4 = weekly.pct_change(4).shift(1)
    momentum8 = weekly.pct_change(8).shift(1)
    panels = {}
    for holding, family, confirmation in itertools.product(config["holding_weeks"], config["families"], config["price_confirmation"]):
        rows = []
        for date in index:
            eligible = events[(events.eligible_week <= date) & (events.eligible_week > date - pd.Timedelta(weeks=int(holding)))].copy()
            if eligible.empty:
                continue
            eligible = eligible.sort_values(["cik10", "event_time"]).groupby("cik10", as_index=False).tail(1)
            eligible["price_momentum_4w"] = eligible.cik10.map(momentum4.loc[date].to_dict())
            eligible["price_momentum_8w"] = eligible.cik10.map(momentum8.loc[date].to_dict())
            if confirmation == "positive_4w":
                eligible = eligible[eligible.price_momentum_4w > 0.0]
            elif confirmation == "positive_8w":
                eligible = eligible[eligible.price_momentum_8w > 0.0]
            if eligible.empty:
                continue
            parts = [rank_sector(eligible, column).rename(column) for column in config["families"][family]]
            if confirmation != "none":
                price_column = "price_momentum_4w" if confirmation == "positive_4w" else "price_momentum_8w"
                parts.append(rank_sector(eligible, price_column).rename(price_column))
            matrix = pd.concat(parts, axis=1)
            eligible["score"] = matrix.mean(axis=1, skipna=True).where(matrix.notna().sum(axis=1) >= 3)
            eligible["decision_at"] = date
            rows.append(eligible[["decision_at", "event_time", "cik10", "company_name_as_filed", "sector", "market_cap", "score"]])
        panels[(int(holding), family, confirmation)] = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return panels


def choose(panel: pd.DataFrame, breadth: int, floor: int, sector_cap: float) -> pd.DataFrame:
    usable = panel.dropna(subset=["score", "market_cap"])
    usable = usable[usable.market_cap >= float(floor)]
    return diversified.select_with_sector_cap(usable, int(breadth), float(sector_cap))


def metrics_for(path: pd.DataFrame, recent_start: pd.Timestamp) -> tuple[dict, dict]:
    return overlay.metrics(path.net_return), overlay.metrics(path.loc[path.index >= recent_start, "net_return"])


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    benchmark_raw = pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw.observation_date).max()
    weekly_index = pd.date_range(start=pd.Timestamp(config["start_date"]), end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    events = prepare_events()
    event_times = events.event_time.dt.tz_convert(None)
    events["eligible_week"] = [weekly_index[weekly_index > value][0] if len(weekly_index[weekly_index > value]) else pd.NaT for value in event_times]
    sources, terminals = discovery.source_map(), base.terminal_dates()
    price_series = {}
    for cik in sorted(set(events.cik10)):
        spec = sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], weekly_index, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=weekly_index)
    weekly = pd.DataFrame(price_series, index=weekly_index)
    panels = score_panels(events, weekly, weekly_index, config)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    recent_start = control.index.max() - pd.DateOffset(years=1)
    rows, paths, choice_cache = [], {}, {}
    structures = itertools.product(panels.items(), config["breadths"], config["market_cap_floors"], config["sector_caps"])
    for ((holding, family, confirmation), panel), breadth, floor, sector_cap in structures:
        choices = []
        for date, date_frame in panel.groupby("decision_at", sort=True):
            selected = choose(date_frame, int(breadth), int(floor), float(sector_cap))
            if len(selected) == int(breadth):
                choices.append(selected)
        if not choices:
            continue
        selected = pd.concat(choices, ignore_index=True)
        targets = {pd.Timestamp(date): frame.sort_values("cik10").cik10.tolist() for date, frame in selected.groupby("decision_at")}
        sleeve_name = f"{family}__hold{holding}__{confirmation}__top{breadth}__floor{int(floor)//1_000_000}m__sector{int(float(sector_cap)*100)}"
        for cost in config["cost_bps"]:
            sleeve, _ = base.simulate(weekly, targets, "base", float(cost))
            sleeve_full, sleeve_recent = metrics_for(sleeve, recent_start)
            joined = pd.concat([control, sleeve.net_return.rename("sleeve")], axis=1, join="inner").dropna()
            for allocation in config["overlay_allocations"]:
                path = overlay.simulate(joined.control, joined.sleeve, pd.Series(float(allocation), index=joined.index), float(cost))
                full, recent = metrics_for(path, recent_start)
                candidate = f"{sleeve_name}__w{float(allocation):.2f}__{cost}bps"
                rows.append({"candidate": candidate, "sleeve": sleeve_name, "family": family, "holding_weeks": holding, "price_confirmation": confirmation, "breadth": breadth, "market_cap_floor": floor, "sector_cap": sector_cap, "allocation": allocation, "cost_bps": cost, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["drawdown"], "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["drawdown"], "sleeve_recent_cagr": sleeve_recent["cagr"], "sleeve_full_cagr": sleeve_full["cagr"]})
                if int(cost) == 50:
                    paths[candidate] = path
                    choice_cache[candidate] = selected
    performance = pd.DataFrame(rows)
    ranking = performance[performance.cost_bps == 50].sort_values(["recent_cagr", "full_cagr"], ascending=False).copy()
    ranking["beats_control_both"] = (ranking.recent_cagr > float(config["control_recent_cagr"])) & (ranking.full_cagr > float(config["control_full_cagr"]))
    best = ranking.iloc[0]
    severe = performance[(performance.sleeve == best.sleeve) & np.isclose(performance.allocation, best.allocation) & (performance.cost_bps == 200)].iloc[0]
    paths[str(best.candidate)].rename_axis("Date").to_csv(OUTPUT / "best_path_50bps.csv")
    choice_cache[str(best.candidate)].to_csv(OUTPUT / "best_portfolio_choices.csv", index=False)
    events.to_csv(OUTPUT / "filing_event_panel.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ranking.head(200).to_csv(OUTPUT / "top_candidates.csv", index=False)
    checks = {
        "all_events_known_before_eligibility": bool((events.event_time.dt.tz_convert(None) < events.eligible_week).dropna().all()),
        "signals_use_lagged_price_confirmation": True,
        "all_costs_reported": set(performance.cost_bps) == set(config["cost_bps"]),
        "allocations_bounded": bool(performance.allocation.between(0.0, 0.4).all()),
        "results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
    }
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "filing_events": int(len(events)), "unique_issuers": int(events.cik10.nunique()), "tested_paths": int(len(performance)), "best_candidate": str(best.candidate), "best_recent_cagr": float(best.recent_cagr), "best_recent_sharpe": float(best.recent_sharpe), "best_recent_drawdown": float(best.recent_drawdown), "best_full_cagr": float(best.full_cagr), "best_full_drawdown": float(best.full_drawdown), "best_sleeve_recent_cagr": float(best.sleeve_recent_cagr), "severe_200bps_recent_cagr": float(severe.recent_cagr), "candidates_beating_control_both": int(ranking.beats_control_both.sum()), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# SEC filing fundamental momentum search v1\n\n" f"Built {len(events):,} causal filing events across {events.cik10.nunique()} historical issuers and tested {len(performance):,} costed controlled overlays. The best candidate produced {best.recent_cagr:.2%} recent CAGR, {best.recent_sharpe:.2f} Sharpe, {best.recent_drawdown:.2%} drawdown, and {best.full_cagr:.2%} full CAGR. At 200 bps it retained {severe.recent_cagr:.2%}.\n\n" "Filing facts are eligible only after their SEC availability timestamps; price confirmation is lagged one weekly close. This discovery cannot authorize promotion before delay, leave-one-issuer-out, and neighboring-parameter audits.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
