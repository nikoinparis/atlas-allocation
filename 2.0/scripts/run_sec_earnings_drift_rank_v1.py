#!/usr/bin/env python3
"""Test causal sector-relative post-earnings drift inside the cash ranker."""

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

CONFIG = ROOT / "config/sec_earnings_drift_rank_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_earnings_drift_rank_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(window: int, weight: float, breadth: int, buffer: int) -> str:
    return f"pead{int(window)}__w{int(round(weight * 100)):02d}__b{int(breadth)}__buf{int(buffer)}"


def build_event_reactions(events: pd.DataFrame, history: pd.DataFrame, sectors: dict[str, str]) -> pd.DataFrame:
    frame = events.copy()
    frame["accepted_at"] = pd.to_datetime(frame.available_at, utc=True).dt.tz_localize(None)
    frame["report_key"] = frame.report_date.fillna(frame.filing_date).astype(str)
    frame = frame.sort_values(["accepted_at", "accession"]).drop_duplicates(["cik10", "report_key"], keep="first")
    pair_cache: dict[tuple[pd.Timestamp, pd.Timestamp, str], float] = {}
    rows = []
    for row in frame.itertuples(index=False):
        date = pd.Timestamp(row.accepted_at).normalize()
        prior = history.index[history.index < date]
        after = history.index[history.index > date]
        if not len(prior) or not len(after) or row.cik10 not in history:
            continue
        prior_date, response_date = prior[-1], after[0]
        start, finish = history.at[prior_date, row.cik10], history.at[response_date, row.cik10]
        if pd.isna(start) or pd.isna(finish) or float(start) == 0:
            continue
        sector = sectors.get(str(row.cik10), str(row.sector))
        key = (prior_date, response_date, sector)
        if key not in pair_cache:
            members = [cik for cik, value in sectors.items() if value == sector and cik in history]
            returns = history.loc[response_date, members] / history.loc[prior_date, members] - 1.0
            pair_cache[key] = float(returns.replace([np.inf, -np.inf], np.nan).median())
        raw_return = float(finish / start - 1.0)
        rows.append({"cik10": str(row.cik10), "company_name_as_filed": row.company_name_as_filed, "sector": sector, "accession": row.accession, "accepted_at": row.accepted_at, "prior_price_date": prior_date, "response_date": response_date, "raw_reaction": raw_return, "sector_reaction": pair_cache[key], "abnormal_reaction": raw_return - pair_cache[key]})
    return pd.DataFrame(rows).sort_values(["response_date", "cik10", "accepted_at"]).reset_index(drop=True)


def event_rank_choices(
    cash_panel: pd.DataFrame,
    reactions: pd.DataFrame,
    decisions: pd.DatetimeIndex,
    window_weeks: int,
    event_weight: float,
    breadth: int,
    rank_buffer: int,
    signal_delay: int = 0,
    banned_cik: str | None = None,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, list[str]]]:
    panel = cash_panel.copy()
    panel["decision_naive"] = pd.to_datetime(panel.decision_at, utc=True).dt.tz_localize(None)
    fundamental_dates = pd.DatetimeIndex(sorted(panel.decision_naive.unique()))
    previous: set[str] = set()
    choice_rows, targets = [], {}
    for decision in decisions:
        available = fundamental_dates[fundamental_dates < decision]
        if not len(available):
            continue
        fundamental_date = available[-1]
        frame = panel[panel.decision_naive == fundamental_date].copy()
        if banned_cik is not None:
            frame = frame[frame.cik10 != banned_cik]
        causal_cutoff = decision - pd.Timedelta(weeks=int(signal_delay))
        recent = reactions[(reactions.response_date < causal_cutoff) & (reactions.response_date >= causal_cutoff - pd.Timedelta(weeks=int(window_weeks)))].copy()
        recent = recent.sort_values(["response_date", "accepted_at"]).drop_duplicates("cik10", keep="last")
        recent["event_score"] = recent.groupby("sector", sort=False).abnormal_reaction.rank(pct=True, method="average")
        event_map = recent.set_index("cik10").event_score.to_dict()
        response_map = recent.set_index("cik10").response_date.to_dict()
        frame["event_score"] = frame.cik10.map(event_map).fillna(0.5)
        frame["response_date"] = frame.cik10.map(response_map)
        frame["adjusted_score"] = frame.cash_score + float(event_weight) * (frame.event_score - 0.5)
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
            chosen["decision_at"] = decision
            chosen["intended_weight"] = 1.0 / int(breadth)
            choice_rows.append(chosen[["decision_at", "cik10", "company_name_as_filed", "sector", "cash_score", "event_score", "response_date", "adjusted_score", "rank", "intended_weight"]])
            targets[pd.Timestamp(decision)] = sorted(selected_set)
        previous = selected_set
    choices = pd.concat(choice_rows, ignore_index=True) if choice_rows else pd.DataFrame()
    return choices, targets


def composite(leader: pd.Series, sleeve: pd.DataFrame, config: dict, cost: float, overlay_delay: int = 0, fixed_target: pd.DataFrame | None = None) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    target = fixed_target
    if target is None:
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]), int(overlay_delay))
    return dynamic.simulate(returns, target, float(cost))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    normalized = multi.normalized_score_panel(raw)
    cash_panel = normalized[["decision_at", "cik10", "company_name_as_filed", "sector", "cash_conversion"]].rename(columns={"cash_conversion": "cash_score"}).dropna(subset=["cash_score"])
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    history_index = pd.date_range(start="2021-12-03", end=index.max(), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(cash_panel.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                series[cik] = base.read_weekly_price(path, source, history_index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=history_index)
    history = pd.DataFrame(series, index=history_index)
    weekly = history.reindex(index)
    event_path = ROOT / "data/sec_earnings_event_vintages" / config["event_vintage"] / "earnings_8k_events.csv"
    events = pd.read_csv(event_path, dtype={"cik10": str})
    sectors = cash_panel.sort_values("decision_at").drop_duplicates("cik10", keep="last").set_index("cik10").sector.to_dict()
    reactions = build_event_reactions(events, history, sectors)
    reactions.to_csv(OUTPUT / "event_reactions.csv", index=False)
    print(f"built {len(reactions):,} conservative event reactions across {reactions.cik10.nunique()} priced issuers", flush=True)

    leader_paths = {(scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return for scenario in config["scenarios"] for cost in config["cost_bps"]}
    baseline_choices = breadth_runner.make_choices(raw[raw.family == "cash_conversion"].copy(), 20)
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_sleeves = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_sleeves[(scenario, int(cost))], _ = capped.simulate_cash(weekly, baseline_targets, scenario, float(cost), None, 20)
    signal = pd.concat([leader_paths[("base", 50)].rename("leader"), baseline_sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
    control_paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), baseline_sleeves[(scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
        control_paths[(scenario, int(cost))] = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
    frozen = pd.read_csv(FROZEN_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen_check = np.allclose(control_paths[("base", 50)].net_return.reindex(frozen.index), frozen.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not frozen_check:
        raise RuntimeError("frozen control reconstruction failed")
    control_paths[("base", 50)] = frozen
    control_recent = next(row for row in base.metric_rows("control", "base", 50, frozen) if row["window"] == "trailing_1y")
    control_full = next(row for row in base.metric_rows("control", "base", 50, frozen) if row["window"] == "full_recent")
    control_severe = next(row for row in base.metric_rows("control", "base", 200, control_paths[("base", 200)]) if row["window"] == "trailing_1y")

    structures, metrics, paths, choice_cache, sleeve_cache = [], [], {}, {}, {}
    grid = itertools.product(config["event_windows_weeks"], config["event_feature_weights"], config["breadths"], config["rank_buffers"])
    for window, weight, breadth, buffer in grid:
        name = candidate_name(int(window), float(weight), int(breadth), int(buffer))
        choices, targets = event_rank_choices(cash_panel, reactions, index, int(window), float(weight), int(breadth), int(buffer))
        sleeves, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeves[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(weekly, targets, scenario, float(cost), None, int(breadth))
        signal_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
        fixed_target = capped.overlay_target(signal_returns.index, signal_returns.leader, signal_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            path = composite(leader_paths[(scenario, int(cost))], sleeves[(scenario, int(cost))], config, float(cost), fixed_target=fixed_target)
            paths[(name, scenario, int(cost))] = path
            metrics.extend(base.metric_rows(name, scenario, int(cost), path))
        structures.append({"candidate": name, "event_window_weeks": int(window), "event_weight": float(weight), "breadth": int(breadth), "rank_buffer": int(buffer), "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)], "sleeve_annual_turnover": float(sleeves[("base", 50)].turnover.mean() * 52.0), "selection_events": int(len(targets))})
        choice_cache[name], sleeve_cache[name] = choices, sleeves

    performance = pd.DataFrame(metrics)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    screen_rows = []
    for structure in structures:
        name = structure["candidate"]
        recent = primary[(primary.candidate == name) & (primary.window == "trailing_1y")].iloc[0]
        full = primary[(primary.candidate == name) & (primary.window == "full_recent")].iloc[0]
        severe = performance[(performance.candidate == name) & (performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
        screen_rows.append({**structure, "recent_cagr": recent.cagr, "recent_sharpe": recent.sharpe_zero_rf, "recent_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "severe_recent_cagr": severe.cagr})
    screen = pd.DataFrame(screen_rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    gates = config["promotion_gates"]
    screen["surface_gates"] = (screen.recent_cagr >= control_recent["cagr"] + float(gates["minimum_recent_cagr_improvement"])) & (screen.full_cagr >= control_full["cagr"]) & (screen.severe_recent_cagr > control_severe["cagr"]) & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_portfolio_stock_weight"])) & (screen.sleeve_annual_turnover <= float(gates["maximum_sleeve_annual_one_way_turnover"]))
    selected_row = (screen[screen.surface_gates] if screen.surface_gates.any() else screen).iloc[0]
    selected = str(selected_row.candidate)
    for cost in [50, 100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    choice_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(joined, int(config["falsification"]["rolling_comparison_weeks"]))
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])

    window, weight, breadth, buffer = int(selected_row.event_window_weeks), float(selected_row.event_weight), int(selected_row.breadth), int(selected_row.rank_buffer)
    delays_rows = []
    for delay in config["falsification"]["event_signal_delays_weeks"]:
        choices, targets = event_rank_choices(cash_panel, reactions, index, window, weight, breadth, buffer, int(delay))
        sleeve, _ = capped.simulate_cash(weekly, targets, "base", 50.0, None, breadth)
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, f"event_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delays_rows.append({"delay_type": "event_signal", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    for delay in config["falsification"]["overlay_delays_weeks"]:
        path = composite(leader_paths[("base", 50)], sleeve_cache[selected][("base", 50)], config, 50.0, int(delay))
        recent = next(row for row in base.metric_rows(selected, f"overlay_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delays_rows.append({"delay_type": "overlay", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delays_rows)

    selected_choices = choice_cache[selected]
    cutoff = selected_choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(selected_choices.loc[selected_choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        choices, targets = event_rank_choices(cash_panel, reactions, index, window, weight, breadth, buffer, banned_cik=cik)
        sleeve, _ = capped.simulate_cash(weekly, targets, "base", 50.0, None, breadth)
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y")
        company = selected_choices.loc[selected_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    windows = list(map(int, config["event_windows_weeks"])); weights = list(map(float, config["event_feature_weights"])); breadths = list(map(int, config["breadths"]))
    xi, wi, bi = windows.index(window), weights.index(weight), breadths.index(breadth)
    neighbors = screen[screen.event_window_weeks.isin(windows[max(0, xi-1):xi+2]) & screen.event_weight.isin(weights[max(0, wi-1):wi+2]) & screen.breadth.isin(breadths[max(0, bi-1):bi+2])].copy()
    neighbors["joint_improvement"] = (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0]); b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    ed1 = float(delays[(delays.delay_type == "event_signal") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); ed2 = float(delays[(delays.delay_type == "event_signal") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    od1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); od2 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    causal_choices = selected_choices.response_date.dropna() < selected_choices.loc[selected_choices.response_date.notna(), "decision_at"]
    checks = {
        "surface_gates": bool(selected_row.surface_gates), "all_used_event_responses_precede_decisions": bool(causal_choices.all()),
        "event_one_week_delay_beats_control": ed1 > control_recent["cagr"], "event_two_week_delay_beats_control": ed2 > control_recent["cagr"], "overlay_one_week_delay_beats_control": od1 > control_recent["cagr"], "overlay_two_week_delay_beats_control": od2 > control_recent["cagr"],
        "rolling_gate": rolling_share >= float(gates["minimum_completed_rolling_outperformance_share"]), "neighborhood_gate": neighborhood_share >= float(gates["minimum_neighborhood_joint_improvement_share"]), "bootstrap_4w_gate": b4 >= float(gates["minimum_bootstrap_probability_positive"]), "bootstrap_13w_gate": b13 >= float(gates["minimum_bootstrap_probability_positive"]),
        "worst_loo_beats_control": float(worst.recent_cagr) > control_recent["cagr"], "single_issuer_influence_gate": issuer_share is not None and issuer_share <= float(gates["maximum_single_issuer_improvement_share"]), "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected_row.recent_cagr, atol=1e-12, rtol=0))
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False); screen.to_csv(OUTPUT / "screening.csv", index=False); bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False); delays.to_csv(OUTPUT / "delay_stress.csv", index=False); loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False); neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)), "priced_event_reactions": int(len(reactions)), "priced_event_issuers": int(reactions.cik10.nunique()), "selected_candidate": selected,
        "event_window_weeks": window, "event_weight": weight, "breadth": breadth, "rank_buffer": buffer, "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe), "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr), "severe_recent_cagr": float(selected_row.severe_recent_cagr), "sleeve_annual_turnover": float(selected_row.sleeve_annual_turnover),
        "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]), "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share, "neighborhood_joint_improvement_share": neighborhood_share, "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13,
        "event_one_week_delay_recent_cagr": ed1, "event_two_week_delay_recent_cagr": ed2, "overlay_one_week_delay_recent_cagr": od1, "overlay_two_week_delay_recent_cagr": od2, "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": bool(frozen_check), "runtime": runtime, "artifact_sha256": {"event_reactions": sha256(OUTPUT / "event_reactions.csv"), "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"), "frozen_control_50bps": sha256(FROZEN_CONTROL)}, "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC earnings-drift rank v1\n\n"
        f"Built {len(reactions):,} conservative sector-relative event reactions across {reactions.cik10.nunique()} priced issuers and tested {len(screen)} issuer-ranking paths. The strongest candidate, {selected}, produced {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR versus {control_recent['cagr']:.2%}, {control_recent['sharpe_zero_rf']:.3f}, {control_recent['max_drawdown']:.2%}, and {control_full['cagr']:.2%} for the frozen control.\n\n"
        f"The complete falsification decision was {'PASS' if all_passed else 'FAIL'}. Severe-cost recent CAGR was {selected_row.severe_recent_cagr:.2%}, event-delay results were {ed1:.2%}/{ed2:.2%}, and bootstrap probabilities were {b4:.2%}/{b13:.2%}. No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
