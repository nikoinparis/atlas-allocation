#!/usr/bin/env python3
"""Test persistent earnings direction plus fundamental acceleration at quarterly rebalances."""

from __future__ import annotations

import hashlib
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
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner
import run_sec_form4_dynamic_overlay_v1 as audit
import run_sec_multisignal_company_rank_v1 as multi
import run_sec_filing_fundamental_momentum_search_v1 as filing

CONFIG = ROOT / "config/sec_persistent_earnings_acceleration_rank_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
REACTIONS = ROOT / "evidence/sec_earnings_drift_rank_v1/event_reactions.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_persistent_earnings_acceleration_rank_v1"
ACCELERATION_COLUMNS = ["revenue_acceleration", "operating_income_acceleration", "operating_cash_flow_acceleration"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(age: int, events: int, acceleration_weight: float, earnings_weight: float, buffer: int) -> str:
    return (
        f"age{int(age)}__persist{int(events)}__a{int(round(acceleration_weight * 100)):02d}"
        f"__e{int(round(earnings_weight * 100)):02d}__buf{int(buffer)}"
    )


def _naive(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize(None) if stamp.tzinfo is not None else stamp


def _sector_rank(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame.groupby("sector", sort=False)[column].rank(pct=True, method="average")


def build_feature_panel(
    cash_panel: pd.DataFrame,
    filing_events: pd.DataFrame,
    reactions: pd.DataFrame,
    fundamental_age_weeks: int,
    earnings_event_count: int,
    earnings_lookback_weeks: int,
    signal_delay_weeks: int = 0,
) -> pd.DataFrame:
    """Build quarterly features using only observations strictly known before each cutoff."""
    filings = filing_events.copy()
    filings["event_time_naive"] = pd.to_datetime(filings.event_time, utc=True).dt.tz_localize(None)
    earnings = reactions.copy()
    earnings["response_date"] = pd.to_datetime(earnings.response_date).dt.tz_localize(None)
    panel = cash_panel.copy()
    panel["decision_naive"] = pd.to_datetime(panel.decision_at, utc=True).dt.tz_localize(None)
    rows = []
    for decision, cash in panel.groupby("decision_naive", sort=True):
        cutoff = pd.Timestamp(decision) - pd.Timedelta(weeks=int(signal_delay_weeks))
        frame = cash.copy()

        recent_filings = filings[
            (filings.event_time_naive < cutoff)
            & (filings.event_time_naive >= cutoff - pd.Timedelta(weeks=int(fundamental_age_weeks)))
        ].copy()
        recent_filings = recent_filings.sort_values(["event_time_naive", "cik10"]).drop_duplicates("cik10", keep="last")
        acceleration_parts = []
        for column in ACCELERATION_COLUMNS:
            recent_filings[column] = pd.to_numeric(recent_filings[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            acceleration_parts.append(_sector_rank(recent_filings, column).rename(column))
        acceleration_matrix = pd.concat(acceleration_parts, axis=1)
        recent_filings["acceleration_score"] = acceleration_matrix.mean(axis=1, skipna=True).where(
            acceleration_matrix.notna().sum(axis=1) >= 2
        )
        acceleration_map = recent_filings.set_index("cik10").acceleration_score.to_dict()
        acceleration_time = recent_filings.set_index("cik10").event_time_naive.to_dict()

        eligible = earnings[
            (earnings.response_date < cutoff)
            & (earnings.response_date >= cutoff - pd.Timedelta(weeks=int(earnings_lookback_weeks)))
        ].sort_values(["cik10", "response_date", "accepted_at"])
        last_events = eligible.groupby("cik10", group_keys=False).tail(int(earnings_event_count)).copy()
        counts = last_events.groupby("cik10").size()
        valid_ciks = set(counts[counts >= int(earnings_event_count)].index)
        last_events = last_events[last_events.cik10.isin(valid_ciks)]
        persistent = last_events.groupby(["cik10", "sector"], as_index=False).agg(
            mean_abnormal_reaction=("abnormal_reaction", "mean"),
            positive_share=("abnormal_reaction", lambda values: float((values > 0).mean())),
            earnings_response_date=("response_date", "max"),
        )
        if len(persistent):
            persistent["reaction_rank"] = _sector_rank(persistent, "mean_abnormal_reaction")
            persistent["consistency_rank"] = _sector_rank(persistent, "positive_share")
            persistent["earnings_score"] = persistent[["reaction_rank", "consistency_rank"]].mean(axis=1)
            earnings_map = persistent.set_index("cik10").earnings_score.to_dict()
            earnings_time = persistent.set_index("cik10").earnings_response_date.to_dict()
        else:
            earnings_map, earnings_time = {}, {}

        frame["acceleration_score"] = frame.cik10.map(acceleration_map)
        frame["earnings_score"] = frame.cik10.map(earnings_map)
        frame["acceleration_event_time"] = frame.cik10.map(acceleration_time)
        frame["earnings_response_date"] = frame.cik10.map(earnings_time)
        frame["acceleration_available"] = frame.acceleration_score.notna()
        frame["earnings_available"] = frame.earnings_score.notna()
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def ranked_choices(
    feature_panel: pd.DataFrame,
    acceleration_weight: float,
    earnings_weight: float,
    breadth: int,
    rank_buffer: int,
    banned_cik: str | None = None,
) -> pd.DataFrame:
    rows = []
    previous: set[str] = set()
    total_secondary = float(acceleration_weight) + float(earnings_weight)
    for decision, frame in feature_panel.groupby("decision_at", sort=True):
        frame = frame.dropna(subset=["cash_score"]).copy()
        if banned_cik is not None:
            frame = frame[frame.cik10 != banned_cik]
        frame["adjusted_score"] = (
            (1.0 - total_secondary) * frame.cash_score
            + float(acceleration_weight) * frame.acceleration_score.fillna(0.5)
            + float(earnings_weight) * frame.earnings_score.fillna(0.5)
        )
        ranked = frame.sort_values(["adjusted_score", "cik10"], ascending=[False, True]).reset_index(drop=True)
        ranked["rank"] = np.arange(1, len(ranked) + 1)
        eligible = set(ranked.loc[ranked["rank"] <= int(breadth) + int(rank_buffer), "cik10"])
        survivors = previous & eligible
        selected = list(ranked.loc[ranked.cik10.isin(survivors), "cik10"])
        for cik in ranked.cik10:
            if cik not in survivors:
                selected.append(cik)
            if len(selected) == int(breadth):
                break
        selected_set = set(selected)
        if len(selected_set) != int(breadth):
            continue
        if selected_set != previous:
            chosen = ranked[ranked.cik10.isin(selected_set)].copy()
            chosen["intended_weight"] = 1.0 / int(breadth)
            rows.append(
                chosen[
                    [
                        "decision_at", "cik10", "company_name_as_filed", "sector", "cash_score",
                        "acceleration_score", "earnings_score", "acceleration_event_time",
                        "earnings_response_date", "adjusted_score", "rank", "intended_weight",
                    ]
                ]
            )
        previous = selected_set
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def composite(
    leader: pd.Series,
    sleeve: pd.DataFrame,
    config: dict,
    cost: float,
    overlay_delay: int = 0,
    fixed_target: pd.DataFrame | None = None,
) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    target = fixed_target
    if target is None:
        target = capped.overlay_target(
            returns.index,
            returns.leader,
            returns.cash_conversion,
            int(config["overlay_lookback_weeks"]),
            float(config["overlay_active_allocation"]),
            int(overlay_delay),
        )
    return dynamic.simulate(returns, target.reindex(returns.index), float(cost))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    normalized = multi.normalized_score_panel(raw)
    cash_panel = normalized[
        ["decision_at", "cik10", "company_name_as_filed", "sector", "cash_conversion"]
    ].rename(columns={"cash_conversion": "cash_score"}).dropna(subset=["cash_score"])
    filing_events = filing.prepare_events()
    reactions = pd.read_csv(REACTIONS, dtype={"cik10": str}, parse_dates=["accepted_at", "response_date"])
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(cash_panel.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=index)
    weekly = pd.DataFrame(series, index=index)

    feature_panels = {}
    for age, count in itertools.product(config["fundamental_age_weeks"], config["earnings_event_counts"]):
        feature_panels[(int(age), int(count), 0)] = build_feature_panel(
            cash_panel, filing_events, reactions, int(age), int(count), int(config["earnings_lookback_weeks"])
        )
    print(
        f"built {len(feature_panels)} quarterly feature panels from {len(filing_events):,} causal filing events "
        f"and {len(reactions):,} earnings reactions",
        flush=True,
    )

    leader_paths = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario in config["scenarios"] for cost in config["cost_bps"]
    }
    baseline_choices = breadth_runner.make_choices(raw[raw.family == "cash_conversion"].copy(), int(config["breadth"]))
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_sleeves, control_paths = {}, {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_sleeves[(scenario, int(cost))], _ = capped.simulate_cash(
            weekly, baseline_targets, scenario, float(cost), None, int(config["breadth"])
        )
    control_signal = pd.concat(
        [
            leader_paths[("base", 50)].rename("leader"),
            baseline_sleeves[("base", 50)].net_return.rename("cash_conversion"),
        ], axis=1,
    ).dropna()
    control_target = capped.overlay_target(
        control_signal.index, control_signal.leader, control_signal.cash_conversion,
        int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]),
    )
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        returns = pd.concat(
            [
                leader_paths[(scenario, int(cost))].rename("leader"),
                baseline_sleeves[(scenario, int(cost))].net_return.rename("cash_conversion"),
            ], axis=1,
        ).dropna()
        control_paths[(scenario, int(cost))] = dynamic.simulate(
            returns, control_target.reindex(returns.index), float(cost)
        )
    frozen = pd.read_csv(FROZEN_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen_check = np.allclose(
        control_paths[("base", 50)].net_return.reindex(frozen.index),
        frozen.net_return,
        rtol=0,
        atol=1e-12,
        equal_nan=True,
    )
    if not frozen_check:
        raise RuntimeError("frozen control reconstruction failed")
    control_paths[("base", 50)] = frozen
    control_recent = next(
        row for row in base.metric_rows("control", "base", 50, frozen) if row["window"] == "trailing_1y"
    )
    control_full = next(
        row for row in base.metric_rows("control", "base", 50, frozen) if row["window"] == "full_recent"
    )
    control_severe = next(
        row for row in base.metric_rows("control", "base", 200, control_paths[("base", 200)])
        if row["window"] == "trailing_1y"
    )

    structures, metric_rows, paths, choice_cache, sleeve_cache = [], [], {}, {}, {}
    grid = itertools.product(
        config["fundamental_age_weeks"], config["earnings_event_counts"],
        config["acceleration_weights"], config["earnings_weights"], config["rank_buffers"],
    )
    for age, count, acceleration_weight, earnings_weight, buffer in grid:
        if float(acceleration_weight) == 0.0 and float(earnings_weight) == 0.0:
            continue
        name = candidate_name(int(age), int(count), float(acceleration_weight), float(earnings_weight), int(buffer))
        feature_panel = feature_panels[(int(age), int(count), 0)]
        choices = ranked_choices(
            feature_panel, float(acceleration_weight), float(earnings_weight),
            int(config["breadth"]), int(buffer),
        )
        targets = base.build_targets(choices, index)
        sleeves, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeves[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(
                weekly, targets, scenario, float(cost), None, int(config["breadth"])
            )
        signal = pd.concat(
            [
                leader_paths[("base", 50)].rename("leader"),
                sleeves[("base", 50)].net_return.rename("cash_conversion"),
            ], axis=1,
        ).dropna()
        fixed_target = capped.overlay_target(
            signal.index, signal.leader, signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]),
        )
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            path = composite(
                leader_paths[(scenario, int(cost))], sleeves[(scenario, int(cost))],
                config, float(cost), fixed_target=fixed_target,
            )
            paths[(name, scenario, int(cost))] = path
            metric_rows.extend(base.metric_rows(name, scenario, int(cost), path))
        acceleration_coverage = float(feature_panel.acceleration_available.mean())
        earnings_coverage = float(feature_panel.earnings_available.mean())
        structures.append(
            {
                "candidate": name,
                "fundamental_age_weeks": int(age),
                "earnings_event_count": int(count),
                "acceleration_weight": float(acceleration_weight),
                "earnings_weight": float(earnings_weight),
                "rank_buffer": int(buffer),
                "acceleration_coverage": acceleration_coverage,
                "earnings_coverage": earnings_coverage,
                "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)],
                "sleeve_annual_turnover": float(sleeves[("base", 50)].turnover.mean() * 52.0),
            }
        )
        choice_cache[name], sleeve_cache[name] = choices, sleeves

    performance = pd.DataFrame(metric_rows)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    screen_rows = []
    for structure in structures:
        name = structure["candidate"]
        recent = primary[(primary.candidate == name) & (primary.window == "trailing_1y")].iloc[0]
        full = primary[(primary.candidate == name) & (primary.window == "full_recent")].iloc[0]
        severe = performance[
            (performance.candidate == name) & (performance.scenario == "base")
            & (performance.cost_bps == 200) & (performance.window == "trailing_1y")
        ].iloc[0]
        screen_rows.append(
            {
                **structure,
                "recent_cagr": recent.cagr,
                "recent_sharpe": recent.sharpe_zero_rf,
                "recent_drawdown": recent.max_drawdown,
                "full_cagr": full.cagr,
                "severe_recent_cagr": severe.cagr,
            }
        )
    screen = pd.DataFrame(screen_rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    gates = config["promotion_gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= control_recent["cagr"] + float(gates["minimum_recent_cagr_improvement"]))
        & (screen.full_cagr >= control_full["cagr"] + float(gates["minimum_full_cagr_improvement"]))
        & (screen.severe_recent_cagr > control_severe["cagr"])
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_portfolio_stock_weight"]))
        & (screen.sleeve_annual_turnover <= float(gates["maximum_sleeve_annual_one_way_turnover"]))
    )
    combined = screen[(screen.acceleration_weight > 0) & (screen.earnings_weight > 0)]
    selected_row = (combined[combined.surface_gates] if combined.surface_gates.any() else combined).iloc[0]
    selected = str(selected_row.candidate)
    for cost in [50, 100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    choice_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)
    feature_panels[(int(selected_row.fundamental_age_weeks), int(selected_row.earnings_event_count), 0)].to_csv(
        OUTPUT / "selected_feature_panel.csv", index=False
    )
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(
        joined, int(config["falsification"]["rolling_comparison_weeks"])
    )
    bootstrap = pd.DataFrame(
        [
            dynamic.block_bootstrap(
                recent_joined.candidate - recent_joined.control,
                int(block), int(config["falsification"]["bootstrap_draws"]),
                int(config["falsification"]["bootstrap_seed"]),
            )
            for block in config["falsification"]["bootstrap_blocks_weeks"]
        ]
    )

    age = int(selected_row.fundamental_age_weeks)
    count = int(selected_row.earnings_event_count)
    acceleration_weight = float(selected_row.acceleration_weight)
    earnings_weight = float(selected_row.earnings_weight)
    buffer = int(selected_row.rank_buffer)
    delay_rows = []
    for delay in config["falsification"]["feature_signal_delays_weeks"]:
        delayed_panel = build_feature_panel(
            cash_panel, filing_events, reactions, age, count,
            int(config["earnings_lookback_weeks"]), int(delay),
        )
        delayed_choices = ranked_choices(
            delayed_panel, acceleration_weight, earnings_weight, int(config["breadth"]), buffer,
        )
        sleeve, _ = capped.simulate_cash(
            weekly, base.build_targets(delayed_choices, index), "base", 50.0, None, int(config["breadth"])
        )
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(
            row for row in base.metric_rows(selected, f"feature_delay_{delay}", 50, path)
            if row["window"] == "trailing_1y"
        )
        delay_rows.append({"delay_type": "feature", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    for delay in config["falsification"]["overlay_delays_weeks"]:
        path = composite(
            leader_paths[("base", 50)], sleeve_cache[selected][("base", 50)],
            config, 50.0, overlay_delay=int(delay),
        )
        recent = next(
            row for row in base.metric_rows(selected, f"overlay_delay_{delay}", 50, path)
            if row["window"] == "trailing_1y"
        )
        delay_rows.append({"delay_type": "overlay", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    selected_choices = choice_cache[selected]
    cutoff = selected_choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(selected_choices.loc[selected_choices.decision_at >= cutoff, "cik10"]))
    selected_panel = feature_panels[(age, count, 0)]
    loo_rows = []
    for cik in recent_ciks:
        choices = ranked_choices(
            selected_panel, acceleration_weight, earnings_weight,
            int(config["breadth"]), buffer, banned_cik=cik,
        )
        sleeve, _ = capped.simulate_cash(
            weekly, base.build_targets(choices, index), "base", 50.0, None, int(config["breadth"])
        )
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(
            row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y"
        )
        company = selected_choices.loc[selected_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append(
            {"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"],
             "cagr_change": recent["cagr"] - selected_row.recent_cagr}
        )
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    neighbors = screen[
        (screen.fundamental_age_weeks == age) & (screen.earnings_event_count == count)
        & (screen.acceleration_weight > 0) & (screen.earnings_weight > 0)
    ].copy()
    neighbors["joint_improvement"] = (
        (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    )
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    fd1 = float(delays[(delays.delay_type == "feature") & (delays.delay_weeks == 1)].recent_cagr.iloc[0])
    fd2 = float(delays[(delays.delay_type == "feature") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    od1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0])
    od2 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    causal_panel = selected_panel.copy()
    decision_naive = pd.to_datetime(causal_panel.decision_at, utc=True).dt.tz_localize(None)
    acceleration_times = pd.to_datetime(causal_panel.acceleration_event_time, errors="coerce")
    earnings_times = pd.to_datetime(causal_panel.earnings_response_date, errors="coerce")
    checks = {
        "surface_gates": bool(selected_row.surface_gates),
        "all_acceleration_events_precede_decisions": bool((acceleration_times.dropna() < decision_naive.loc[acceleration_times.dropna().index]).all()),
        "all_earnings_responses_precede_decisions": bool((earnings_times.dropna() < decision_naive.loc[earnings_times.dropna().index]).all()),
        "feature_one_week_delay_beats_control": fd1 > control_recent["cagr"],
        "feature_two_week_delay_beats_control": fd2 > control_recent["cagr"],
        "overlay_one_week_delay_beats_control": od1 > control_recent["cagr"],
        "overlay_two_week_delay_beats_control": od2 > control_recent["cagr"],
        "rolling_gate": rolling_share >= float(gates["minimum_completed_rolling_outperformance_share"]),
        "neighborhood_gate": neighborhood_share >= float(gates["minimum_neighborhood_joint_improvement_share"]),
        "bootstrap_4w_gate": b4 >= float(gates["minimum_bootstrap_probability_positive"]),
        "bootstrap_13w_gate": b13 >= float(gates["minimum_bootstrap_probability_positive"]),
        "worst_loo_beats_control": float(worst.recent_cagr) > control_recent["cagr"],
        "single_issuer_influence_gate": issuer_share is not None and issuer_share <= float(gates["maximum_single_issuer_improvement_share"]),
        "persisted_recent_cagr_matches": bool(
            np.isclose(
                next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"],
                selected_row.recent_cagr, atol=1e-12, rtol=0,
            )
        ),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    acceleration_only = screen[
        (screen.fundamental_age_weeks == age) & (screen.earnings_event_count == count)
        & np.isclose(screen.acceleration_weight, acceleration_weight)
        & np.isclose(screen.earnings_weight, 0.0) & (screen.rank_buffer == buffer)
    ].iloc[0]
    earnings_only = screen[
        (screen.fundamental_age_weeks == age) & (screen.earnings_event_count == count)
        & np.isclose(screen.acceleration_weight, 0.0)
        & np.isclose(screen.earnings_weight, earnings_weight) & (screen.rank_buffer == buffer)
    ].iloc[0]

    performance.to_csv(OUTPUT / "performance.csv", index=False)
    screen.to_csv(OUTPUT / "screening.csv", index=False)
    neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)),
        "filing_events": int(len(filing_events)),
        "earnings_reactions": int(len(reactions)),
        "selected_candidate": selected,
        "fundamental_age_weeks": age,
        "earnings_event_count": count,
        "acceleration_weight": acceleration_weight,
        "earnings_weight": earnings_weight,
        "rank_buffer": buffer,
        "recent_cagr": float(selected_row.recent_cagr),
        "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown),
        "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "sleeve_annual_turnover": float(selected_row.sleeve_annual_turnover),
        "acceleration_coverage": float(selected_row.acceleration_coverage),
        "earnings_coverage": float(selected_row.earnings_coverage),
        "acceleration_only_recent_cagr": float(acceleration_only.recent_cagr),
        "earnings_only_recent_cagr": float(earnings_only.recent_cagr),
        "control_recent_cagr": float(control_recent["cagr"]),
        "control_full_cagr": float(control_full["cagr"]),
        "control_severe_recent_cagr": float(control_severe["cagr"]),
        "completed_rolling_windows": rolling_windows,
        "rolling_outperformance_share": rolling_share,
        "neighborhood_joint_improvement_share": neighborhood_share,
        "bootstrap_4w_probability_positive": b4,
        "bootstrap_13w_probability_positive": b13,
        "feature_one_week_delay_recent_cagr": fd1,
        "feature_two_week_delay_recent_cagr": fd2,
        "overlay_one_week_delay_recent_cagr": od1,
        "overlay_two_week_delay_recent_cagr": od2,
        "worst_loo_company": str(worst.company_name),
        "worst_loo_recent_cagr": float(worst.recent_cagr),
        "single_issuer_improvement_share": issuer_share,
        "checks": checks,
        "all_falsification_checks_passed": all_passed,
        "frozen_control_rebuilt_exactly": bool(frozen_check),
        "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_portfolio_choices": sha256(OUTPUT / "selected_portfolio_choices.csv"),
            "frozen_control_50bps": sha256(FROZEN_CONTROL),
        },
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Persistent earnings and fundamental acceleration rank v1\n\n"
        f"Tested {len(screen)} quarterly confirmation paths. The selected `{selected}` candidate "
        f"produced {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} "
        f"Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} "
        f"full CAGR versus {control_recent['cagr']:.2%}, {control_recent['sharpe_zero_rf']:.3f}, "
        f"{control_recent['max_drawdown']:.2%}, and {control_full['cagr']:.2%} for the frozen control. "
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%} versus "
        f"{control_severe['cagr']:.2%}.\n\n"
        f"Feature delays returned {fd1:.2%}/{fd2:.2%}, overlay delays returned {od1:.2%}/{od2:.2%}, "
        f"rolling outperformance was {rolling_share:.2%}, neighborhood joint improvement was "
        f"{neighborhood_share:.2%}, and bootstrap probabilities were {b4:.2%}/{b13:.2%}. "
        f"Removing {worst.company_name} left {worst.recent_cagr:.2%}.\n\n"
        f"The complete falsification decision was **{'PASS' if all_passed else 'FAIL'}**. "
        f"No strategy replacement, forward clock, or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
