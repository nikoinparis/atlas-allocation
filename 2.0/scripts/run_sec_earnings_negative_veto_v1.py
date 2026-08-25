#!/usr/bin/env python3
"""Test a sparse negative-earnings veto at quarterly cash-conversion rebalances."""

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

CONFIG = ROOT / "config/sec_earnings_negative_veto_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
REACTIONS = ROOT / "evidence/sec_earnings_drift_rank_v1/event_reactions.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_earnings_negative_veto_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(window: int, percentile: float, maximum: int) -> str:
    return f"veto{int(window)}__q{int(round(percentile * 100)):02d}__max{int(maximum)}"


def veto_choices(
    scores: pd.DataFrame,
    reactions: pd.DataFrame,
    breadth: int,
    window_weeks: int,
    negative_percentile: float,
    maximum_vetoes: int,
    signal_delay: int = 0,
    banned_cik: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    choice_rows, veto_rows = [], []
    for decision, source in scores.groupby("decision_at", sort=True):
        decision_naive = pd.Timestamp(decision).tz_localize(None) if pd.Timestamp(decision).tzinfo else pd.Timestamp(decision)
        cutoff = decision_naive - pd.Timedelta(weeks=int(signal_delay))
        recent = reactions[(reactions.response_date < cutoff) & (reactions.response_date >= cutoff - pd.Timedelta(weeks=int(window_weeks)))].copy()
        recent = recent.sort_values(["response_date", "accepted_at"]).drop_duplicates("cik10", keep="last")
        recent["reaction_percentile"] = recent.groupby("sector", sort=False).abnormal_reaction.rank(pct=True, method="average")
        negative = recent[(recent.abnormal_reaction < 0) & (recent.reaction_percentile <= float(negative_percentile))].sort_values(["reaction_percentile", "abnormal_reaction", "cik10"])
        ranked = source.dropna(subset=["score"]).copy()
        if banned_cik is not None:
            ranked = ranked[ranked.cik10 != banned_cik]
        ranked = ranked.sort_values(["score", "cik10"], ascending=[False, True])
        initial = ranked.head(int(breadth))
        veto_candidates = negative[negative.cik10.isin(initial.cik10)].head(int(maximum_vetoes))
        vetoed = set(veto_candidates.cik10)
        selected = ranked[~ranked.cik10.isin(vetoed)].head(int(breadth)).copy()
        if len(selected) != int(breadth):
            continue
        selected["decision_at"] = decision
        selected["intended_weight"] = 1.0 / int(breadth)
        choice_rows.append(selected[["decision_at", "cik10", "company_name_as_filed", "sector", "score", "intended_weight"]])
        for row in veto_candidates.itertuples(index=False):
            veto_rows.append({"decision_at": decision, "cik10": row.cik10, "company_name_as_filed": row.company_name_as_filed, "response_date": row.response_date, "abnormal_reaction": row.abnormal_reaction, "reaction_percentile": row.reaction_percentile})
    return pd.concat(choice_rows, ignore_index=True), pd.DataFrame(veto_rows)


def composite(leader: pd.Series, sleeve: pd.DataFrame, config: dict, cost: float, delay: int = 0, fixed_target: pd.DataFrame | None = None) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    target = fixed_target
    if target is None:
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]), int(delay))
    return dynamic.simulate(returns, target, float(cost))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    scores = scores[scores.family == "cash_conversion"].copy()
    reactions = pd.read_csv(REACTIONS, dtype={"cik10": str}, parse_dates=["accepted_at", "response_date"])
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(scores.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=index)
    weekly = pd.DataFrame(series, index=index)
    leader_paths = {(scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return for scenario in config["scenarios"] for cost in config["cost_bps"]}

    baseline_choices = breadth_runner.make_choices(scores, int(config["breadth"]))
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_sleeves, control_paths = {}, {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_sleeves[(scenario, int(cost))], _ = capped.simulate_cash(weekly, baseline_targets, scenario, float(cost), None, int(config["breadth"]))
    signal = pd.concat([leader_paths[("base", 50)].rename("leader"), baseline_sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
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

    structures, metrics, paths, choices_cache, veto_cache, sleeve_cache = [], [], {}, {}, {}, {}
    grid = itertools.product(config["event_windows_weeks"], config["negative_sector_percentiles"], config["maximum_vetoes_per_rebalance"])
    for window, percentile, maximum in grid:
        name = candidate_name(int(window), float(percentile), int(maximum))
        choices, vetoes = veto_choices(scores, reactions, int(config["breadth"]), int(window), float(percentile), int(maximum))
        targets = base.build_targets(choices, index)
        sleeves, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeves[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(weekly, targets, scenario, float(cost), None, int(config["breadth"]))
        signal_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
        fixed_target = capped.overlay_target(signal_returns.index, signal_returns.leader, signal_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            path = composite(leader_paths[(scenario, int(cost))], sleeves[(scenario, int(cost))], config, float(cost), fixed_target=fixed_target)
            paths[(name, scenario, int(cost))] = path
            metrics.extend(base.metric_rows(name, scenario, int(cost), path))
        structures.append({"candidate": name, "event_window_weeks": int(window), "negative_percentile": float(percentile), "maximum_vetoes": int(maximum), "actual_vetoes": int(len(vetoes)), "vetoed_issuers": int(vetoes.cik10.nunique()) if len(vetoes) else 0, "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)], "sleeve_annual_turnover": float(sleeves[("base", 50)].turnover.mean() * 52.0)})
        choices_cache[name], veto_cache[name], sleeve_cache[name] = choices, vetoes, sleeves

    performance = pd.DataFrame(metrics)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    rows = []
    for structure in structures:
        name = structure["candidate"]
        recent = primary[(primary.candidate == name) & (primary.window == "trailing_1y")].iloc[0]
        full = primary[(primary.candidate == name) & (primary.window == "full_recent")].iloc[0]
        severe = performance[(performance.candidate == name) & (performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
        rows.append({**structure, "recent_cagr": recent.cagr, "recent_sharpe": recent.sharpe_zero_rf, "recent_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "severe_recent_cagr": severe.cagr})
    screen = pd.DataFrame(rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    gates = config["promotion_gates"]
    screen["surface_gates"] = (screen.recent_cagr >= control_recent["cagr"] + float(gates["minimum_recent_cagr_improvement"])) & (screen.full_cagr >= control_full["cagr"]) & (screen.severe_recent_cagr > control_severe["cagr"]) & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_portfolio_stock_weight"])) & (screen.sleeve_annual_turnover <= float(gates["maximum_sleeve_annual_one_way_turnover"]))
    selected_row = (screen[screen.surface_gates] if screen.surface_gates.any() else screen).iloc[0]
    selected = str(selected_row.candidate)
    for cost in [50, 100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    choices_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)
    veto_cache[selected].to_csv(OUTPUT / "selected_veto_log.csv", index=False)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(joined, int(config["falsification"]["rolling_comparison_weeks"]))
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])

    window, percentile, maximum = int(selected_row.event_window_weeks), float(selected_row.negative_percentile), int(selected_row.maximum_vetoes)
    delay_rows = []
    for delay in config["falsification"]["event_signal_delays_weeks"]:
        choices, _ = veto_choices(scores, reactions, int(config["breadth"]), window, percentile, maximum, int(delay))
        sleeve, _ = capped.simulate_cash(weekly, base.build_targets(choices, index), "base", 50.0, None, int(config["breadth"]))
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, f"event_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_type": "event_signal", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    for delay in config["falsification"]["overlay_delays_weeks"]:
        path = composite(leader_paths[("base", 50)], sleeve_cache[selected][("base", 50)], config, 50.0, int(delay))
        recent = next(row for row in base.metric_rows(selected, f"overlay_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_type": "overlay", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    recent_choices = choices_cache[selected]
    recent_ciks = sorted(set(recent_choices.loc[recent_choices.decision_at >= recent_choices.decision_at.max() - pd.DateOffset(years=1), "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        choices, _ = veto_choices(scores, reactions, int(config["breadth"]), window, percentile, maximum, banned_cik=cik)
        sleeve, _ = capped.simulate_cash(weekly, base.build_targets(choices, index), "base", 50.0, None, int(config["breadth"]))
        path = composite(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y")
        company = recent_choices.loc[recent_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None
    neighbors = screen.copy()
    neighbors["joint_improvement"] = (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0]); b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    ed1 = float(delays[(delays.delay_type == "event_signal") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); ed2 = float(delays[(delays.delay_type == "event_signal") & (delays.delay_weeks == 2)].recent_cagr.iloc[0]); od1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); od2 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    checks = {
        "surface_gates": bool(selected_row.surface_gates), "event_one_week_delay_beats_control": ed1 > control_recent["cagr"], "event_two_week_delay_beats_control": ed2 > control_recent["cagr"], "overlay_one_week_delay_beats_control": od1 > control_recent["cagr"], "overlay_two_week_delay_beats_control": od2 > control_recent["cagr"], "rolling_gate": rolling_share >= float(gates["minimum_completed_rolling_outperformance_share"]), "neighborhood_gate": neighborhood_share >= float(gates["minimum_neighborhood_joint_improvement_share"]), "bootstrap_4w_gate": b4 >= float(gates["minimum_bootstrap_probability_positive"]), "bootstrap_13w_gate": b13 >= float(gates["minimum_bootstrap_probability_positive"]), "worst_loo_beats_control": float(worst.recent_cagr) > control_recent["cagr"], "single_issuer_influence_gate": issuer_share is not None and issuer_share <= float(gates["maximum_single_issuer_improvement_share"]), "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected_row.recent_cagr, atol=1e-12, rtol=0))
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False); screen.to_csv(OUTPUT / "screening.csv", index=False); bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False); delays.to_csv(OUTPUT / "delay_stress.csv", index=False); loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False); neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)), "selected_candidate": selected, "event_window_weeks": window, "negative_percentile": percentile, "maximum_vetoes": maximum, "actual_vetoes": int(selected_row.actual_vetoes), "vetoed_issuers": int(selected_row.vetoed_issuers),
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe), "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr), "severe_recent_cagr": float(selected_row.severe_recent_cagr), "sleeve_annual_turnover": float(selected_row.sleeve_annual_turnover), "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]), "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share, "neighborhood_joint_improvement_share": neighborhood_share, "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13, "event_one_week_delay_recent_cagr": ed1, "event_two_week_delay_recent_cagr": ed2, "overlay_one_week_delay_recent_cagr": od1, "overlay_two_week_delay_recent_cagr": od2, "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": bool(frozen_check), "runtime": runtime, "artifact_sha256": {"selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"), "selected_veto_log": sha256(OUTPUT / "selected_veto_log.csv"), "frozen_control_50bps": sha256(FROZEN_CONTROL)}, "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        f"# SEC negative-earnings veto v1\n\n"
        f"Tested {len(screen)} sparse rules that use a recent strongly negative sector-relative "
        f"earnings reaction only to veto a stock at an existing quarterly cash-conversion "
        f"rebalance. The selected `{selected}` path used a {window}-week event window, "
        f"the bottom {percentile:.0%} within each sector, and no more than {maximum} vetoes per "
        f"rebalance. It made only {int(selected_row.actual_vetoes)} substitutions across "
        f"{int(selected_row.vetoed_issuers)} issuers.\n\n"
        f"At realistic 50-bps costs, the selected path produced {selected_row.recent_cagr:.2%} "
        f"trailing-one-year CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"The frozen control produced {control_recent['cagr']:.2%}, "
        f"{control_recent['sharpe_zero_rf']:.3f}, {control_recent['max_drawdown']:.2%}, and "
        f"{control_full['cagr']:.2%}. At severe 200-bps costs, the candidate returned "
        f"{selected_row.severe_recent_cagr:.2%} versus {control_severe['cagr']:.2%}.\n\n"
        f"The robustness evidence was weak: event delays returned {ed1:.2%}/{ed2:.2%}, outer "
        f"overlay delays returned {od1:.2%}/{od2:.2%}, completed rolling-window outperformance "
        f"was {rolling_share:.2%}, neighborhood joint improvement was {neighborhood_share:.2%}, "
        f"and 4-week/13-week bootstrap probabilities were {b4:.2%}/{b13:.2%}. Removing "
        f"{worst.company_name} reduced recent CAGR to {worst.recent_cagr:.2%}.\n\n"
        f"The complete falsification decision was **{'PASS' if all_passed else 'FAIL'}**. "
        f"The frozen leader remains unchanged, and no promotion, forward clock, or live "
        f"execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
