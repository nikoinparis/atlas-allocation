#!/usr/bin/env python3
"""Test Form 4 purchasing as a bounded feature inside a diversified stock ranker."""

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
import run_sec_form4_insider_cluster_search_v1 as insider
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_form4_rank_feature_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_form4_rank_feature_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def form4_panels(events: pd.DataFrame, decisions: pd.DatetimeIndex, windows: list[int], family: str) -> dict[int, pd.DataFrame]:
    dummy = pd.DataFrame(index=decisions)
    panel_config = {
        "event_windows_days": windows,
        "families": ["all_open_market", "cluster_2plus", "executive_or_cluster", "discretionary", "discretionary_cluster_2plus"],
        "price_confirmation": ["none"],
    }
    built = insider.build_panels(events, dummy, decisions, panel_config)
    return {int(window): built[(int(window), family, "none")] for window in windows}


def select_sector_capped(frame: pd.DataFrame, breadth: int, sector_cap: float) -> pd.DataFrame:
    maximum = max(1, int(np.floor(int(breadth) * float(sector_cap) + 1e-12)))
    counts: dict[str, int] = {}
    selected = []
    for row in frame.sort_values(["adjusted_score", "cik10"], ascending=[False, True]).itertuples(index=False):
        sector = str(row.sector)
        if counts.get(sector, 0) >= maximum:
            continue
        selected.append(row)
        counts[sector] = counts.get(sector, 0) + 1
        if len(selected) == int(breadth):
            break
    return pd.DataFrame(selected, columns=frame.columns) if len(selected) == int(breadth) else pd.DataFrame(columns=frame.columns)


def ranked_choices(
    scores: pd.DataFrame,
    form4: pd.DataFrame,
    weekly: pd.DataFrame,
    feature_weight: float,
    penalty_strength: float,
    sector_cap: float,
    config: dict,
    banned_cik: str | None = None,
) -> pd.DataFrame:
    rows = []
    form4_by_date = {pd.Timestamp(date): frame for date, frame in form4.groupby("decision_at", sort=False)} if len(form4) else {}
    tail_start = float(config["influence_tail_percentile"])
    for decision, frame in scores.groupby("decision_at", sort=True):
        frame = frame.dropna(subset=["score"]).copy()
        if banned_cik is not None:
            frame = frame[frame.cik10 != banned_cik]
        date = pd.Timestamp(decision).tz_localize(None) if pd.Timestamp(decision).tzinfo else pd.Timestamp(decision)
        event_frame = form4_by_date.get(date)
        event_scores = {} if event_frame is None else event_frame.set_index("cik10").score.to_dict()
        frame["form4_score"] = frame.cik10.map(event_scores).fillna(0.0).clip(0.0, 1.0)
        prior_dates = weekly.index[weekly.index < date]
        if len(prior_dates) > int(config["influence_lookback_weeks"]):
            latest = prior_dates[-1]
            momentum = weekly.pct_change(int(config["influence_lookback_weeks"])).loc[latest]
            ranks = frame.cik10.map(momentum.to_dict()).rank(pct=True, method="average")
            tail = ((ranks - tail_start) / (1.0 - tail_start)).clip(0.0, 1.0).fillna(0.0)
        else:
            tail = pd.Series(0.0, index=frame.index)
        frame["influence_penalty"] = tail * float(penalty_strength)
        frame["adjusted_score"] = frame.score + float(feature_weight) * frame.form4_score - frame.influence_penalty
        chosen = select_sector_capped(frame, int(config["breadth"]), float(sector_cap))
        if len(chosen) != int(config["breadth"]):
            continue
        chosen = chosen.copy()
        chosen["decision_at"] = decision
        chosen["intended_weight"] = 1.0 / int(config["breadth"])
        rows.append(chosen[["decision_at", "cik10", "company_name_as_filed", "sector", "score", "form4_score", "influence_penalty", "adjusted_score", "intended_weight"]])
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    scores = scores[scores.family == "cash_conversion"].copy()
    decisions = pd.DatetimeIndex(sorted(pd.to_datetime(scores.decision_at, utc=True).dt.tz_localize(None).unique()))
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")

    events = insider.load_events()
    panels = form4_panels(events, decisions, [int(value) for value in config["form4_windows_days"]], str(config["form4_family"]))
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
    print(f"loaded {len(events):,} Form 4 filings and prices for {weekly.shape[1]} ranked issuers", flush=True)

    leader_paths = {
        (scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return
        for scenario in config["scenarios"] for cost in config["cost_bps"]
    }
    baseline_choices = breadth_runner.make_choices(scores, int(config["breadth"]))
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_cash = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_cash[(scenario, int(cost))], _ = capped.simulate_cash(
            weekly, baseline_targets, scenario, float(cost), None, int(config["breadth"])
        )
    baseline_signal = pd.concat([
        leader_paths[("base", 50)].rename("leader"), baseline_cash[("base", 50)].net_return.rename("cash_conversion")
    ], axis=1).dropna()
    control_target = capped.overlay_target(
        baseline_signal.index, baseline_signal.leader, baseline_signal.cash_conversion,
        int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]),
    )
    control_paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        returns = pd.concat([
            leader_paths[(scenario, int(cost))].rename("leader"),
            baseline_cash[(scenario, int(cost))].net_return.rename("cash_conversion"),
        ], axis=1).dropna()
        control_paths[(scenario, int(cost))] = dynamic.simulate(returns, control_target.reindex(returns.index), float(cost))
    frozen = pd.read_csv(FROZEN_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen_check = np.allclose(
        control_paths[("base", 50)].net_return.reindex(frozen.index), frozen.net_return, rtol=0, atol=1e-12, equal_nan=True
    )
    if not frozen_check:
        raise RuntimeError("rebuilt frozen control does not match its audited 50-bps path")
    control_paths[("base", 50)] = frozen

    structures, performance_rows, paths, targets = [], [], {}, {}
    choices_cache = {}
    grid = itertools.product(
        config["form4_windows_days"], config["form4_feature_weights"],
        config["influence_penalty_strengths"], config["sector_caps"],
    )
    for window, weight, penalty, sector_cap in grid:
        choices = ranked_choices(scores, panels[int(window)], weekly, float(weight), float(penalty), float(sector_cap), config)
        if choices.empty:
            continue
        name = f"win{window}__f4w{int(float(weight)*100):02d}__pen{int(float(penalty)*100):02d}__sector{int(float(sector_cap)*100)}"
        stock_targets = base.build_targets(choices, index)
        sleeve_paths, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeve_paths[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(
                weekly, stock_targets, scenario, float(cost), float(config["internal_stock_cap_multiple"]), int(config["breadth"])
            )
        signal = pd.concat([
            leader_paths[("base", 50)].rename("leader"), sleeve_paths[("base", 50)].net_return.rename("cash_conversion")
        ], axis=1).dropna()
        target = capped.overlay_target(
            signal.index, signal.leader, signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]),
        )
        targets[name], choices_cache[name] = target, choices
        structures.append({"candidate": name, "window_days": int(window), "feature_weight": float(weight), "penalty_strength": float(penalty), "sector_cap": float(sector_cap), "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)]})
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            returns = pd.concat([
                leader_paths[(scenario, int(cost))].rename("leader"),
                sleeve_paths[(scenario, int(cost))].net_return.rename("cash_conversion"),
            ], axis=1).dropna()
            path = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
            paths[(name, scenario, int(cost))] = path
            performance_rows.extend(base.metric_rows(name, scenario, int(cost), path))
    performance = pd.DataFrame(performance_rows)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    control_recent = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "trailing_1y")
    control_full = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "full_recent")
    control_severe = next(row for row in base.metric_rows("control", "base", 200, control_paths[("base", 200)]) if row["window"] == "trailing_1y")
    screen_rows = []
    for structure in structures:
        name = structure["candidate"]
        recent = primary[(primary.candidate == name) & (primary.window == "trailing_1y")].iloc[0]
        full = primary[(primary.candidate == name) & (primary.window == "full_recent")].iloc[0]
        severe = performance[(performance.candidate == name) & (performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
        adverse = performance[(performance.candidate == name) & (performance.scenario == "adverse") & (performance.cost_bps == 50) & (performance.window == "trailing_1y")].iloc[0]
        screen_rows.append({**structure, "recent_cagr": recent.cagr, "recent_sharpe": recent.sharpe_zero_rf, "recent_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "severe_recent_cagr": severe.cagr, "adverse_recent_cagr": adverse.cagr, "recent_beats": recent.cagr >= control_recent["cagr"] + float(config["promotion_gates"]["minimum_recent_cagr_improvement"]), "full_beats": full.cagr >= control_full["cagr"] + float(config["promotion_gates"]["minimum_full_cagr_improvement"]), "severe_beats": severe.cagr > control_severe["cagr"]})
    screen = pd.DataFrame(screen_rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    screen["surface_gates"] = screen.recent_beats & screen.full_beats & screen.severe_beats & (screen.peak_total_stock_weight <= float(config["promotion_gates"]["maximum_peak_total_portfolio_stock_weight"]))
    form4_candidates = screen[screen.feature_weight > 0].copy()
    selected = str((form4_candidates[form4_candidates.surface_gates] if form4_candidates.surface_gates.any() else form4_candidates).iloc[0].candidate)
    selected_row = screen[screen.candidate == selected].iloc[0]
    matched_baseline = screen[
        (screen.feature_weight == 0)
        & np.isclose(screen.penalty_strength, selected_row.penalty_strength)
        & np.isclose(screen.sector_cap, selected_row.sector_cap)
    ].sort_values("recent_cagr", ascending=False).iloc[0]
    selected_path = paths[(selected, "base", 50)]
    selected_path.rename_axis("Date").to_csv(OUTPUT / "selected_path__50bps.csv")
    for cost in [100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    choices_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)

    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(joined, int(config["falsification"]["rolling_comparison_weeks"]))
    bootstrap = pd.DataFrame([
        dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"]))
        for block in config["falsification"]["bootstrap_blocks_weeks"]
    ])

    window_text, weight_text, penalty_text, sector_text = selected.split("__")
    window = int(window_text.replace("win", "")); feature_weight = int(weight_text.replace("f4w", "")) / 100
    penalty = int(penalty_text.replace("pen", "")) / 100; sector_cap = int(sector_text.replace("sector", "")) / 100
    # Delay the already-causal allocation decision itself; this is conservative
    # and avoids reconstructing a future-dependent signal.
    delay_rows = []
    selected_returns = None
    selected_choices = choices_cache[selected]
    selected_targets = base.build_targets(selected_choices, index)
    selected_sleeve, _ = capped.simulate_cash(weekly, selected_targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), int(config["breadth"]))
    selected_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), selected_sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    for delay in [0] + [int(value) for value in config["falsification"]["signal_delays_weeks"]]:
        target = capped.overlay_target(selected_returns.index, selected_returns.leader, selected_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]), delay)
        path = dynamic.simulate(selected_returns, target, 50.0)
        recent = next(row for row in base.metric_rows(selected, f"delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_weeks": delay, "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    recent_ciks = sorted(set(selected_choices.loc[selected_choices.decision_at >= selected_choices.decision_at.max() - pd.DateOffset(years=1), "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        choices = ranked_choices(scores, panels[window], weekly, feature_weight, penalty, sector_cap, config, banned_cik=cik)
        stock_targets = base.build_targets(choices, index)
        sleeve, _ = capped.simulate_cash(weekly, stock_targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), int(config["breadth"]))
        returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        path = dynamic.simulate(returns, target, 50.0)
        recent = next(row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y")
        company = selected_choices.loc[selected_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    single_issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    weight_values = list(map(float, config["form4_feature_weights"])); penalty_values = list(map(float, config["influence_penalty_strengths"]))
    wi, pi = weight_values.index(feature_weight), penalty_values.index(penalty)
    neighbors = screen[(screen.window_days == window) & np.isclose(screen.sector_cap, sector_cap) & screen.feature_weight.isin(weight_values[max(0, wi-1):wi+2]) & screen.penalty_strength.isin(penalty_values[max(0, pi-1):pi+2])].copy()
    neighbors["joint_improvement"] = (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    neighborhood_share = float(neighbors.joint_improvement.mean())
    minimum_bootstrap = float(config["promotion_gates"]["minimum_bootstrap_probability_positive"])
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0]); b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    checks = {
        "surface_gates": bool(selected_row.surface_gates),
        "one_week_delay_beats_control": bool(delays.loc[delays.delay_weeks == 1, "recent_cagr"].iloc[0] > control_recent["cagr"]),
        "two_week_delay_beats_control": bool(delays.loc[delays.delay_weeks == 2, "recent_cagr"].iloc[0] > control_recent["cagr"]),
        "rolling_gate": bool(rolling_share >= float(config["promotion_gates"]["minimum_completed_rolling_outperformance_share"])),
        "neighborhood_gate": bool(neighborhood_share >= float(config["promotion_gates"]["minimum_neighborhood_joint_improvement_share"])),
        "bootstrap_4w_gate": bool(b4 >= minimum_bootstrap),
        "bootstrap_13w_gate": bool(b13 >= minimum_bootstrap),
        "worst_loo_beats_control": bool(worst.recent_cagr > control_recent["cagr"]),
        "single_issuer_influence_gate": bool(single_issuer_share is not None and single_issuer_share <= float(config["promotion_gates"]["maximum_single_issuer_improvement_share"])),
        "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected_row.recent_cagr, atol=1e-12, rtol=0)),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False); screen.to_csv(OUTPUT / "screening.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False); delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False); neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)),
        "selected_candidate": selected, "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe), "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr), "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]),
        "matched_zero_form4_recent_cagr": float(matched_baseline.recent_cagr), "matched_zero_form4_full_cagr": float(matched_baseline.full_cagr),
        "form4_incremental_recent_cagr": float(selected_row.recent_cagr - matched_baseline.recent_cagr), "form4_incremental_full_cagr": float(selected_row.full_cagr - matched_baseline.full_cagr),
        "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share, "neighborhood_joint_improvement_share": neighborhood_share,
        "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13, "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": single_issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": bool(frozen_check), "runtime": runtime,
        "artifact_sha256": {"selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"), "frozen_control_50bps": sha256(FROZEN_CONTROL)},
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC Form 4 rank feature v1\n\n"
        f"Tested {len(screen)} causal, diversified ranking variants. The selected candidate produced {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR, versus {control_recent['cagr']:.2%} and {control_full['cagr']:.2%} for the frozen control.\n\n"
        f"Against its matched zero-Form-4 baseline, the feature added {selected_row.recent_cagr - matched_baseline.recent_cagr:.2%} to recent CAGR but removed {matched_baseline.full_cagr - selected_row.full_cagr:.2%} from full CAGR. A one-week decision delay returned {delays.loc[delays.delay_weeks == 1, 'recent_cagr'].iloc[0]:.2%}; only {rolling_share:.2%} of completed rolling windows beat the control; 4-week and 13-week bootstrap probabilities were {b4:.2%} and {b13:.2%}; and excluding {worst.company_name} reduced recent CAGR to {worst.recent_cagr:.2%}.\n\n"
        f"The full falsification decision was {'PASS' if all_passed else 'FAIL'}. Form 4 boosts were bounded, every sleeve held 20 equal-target names, sector exposure was capped, extreme prior winners received a causal ranking penalty, and exact leave-one-company-out reranking replaced each excluded issuer. The candidate was not promoted. No live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
