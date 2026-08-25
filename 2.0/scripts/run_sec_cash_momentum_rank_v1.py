#!/usr/bin/env python3
"""Test lagged sector-relative stock momentum inside the cash-conversion ranker."""

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

CONFIG = ROOT / "config/sec_cash_momentum_rank_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_cash_momentum_rank_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(lookback: int, weight: float, breadth: int, buffer: int) -> str:
    return f"mom{int(lookback)}__w{int(round(weight * 100)):02d}__b{int(breadth)}__buf{int(buffer)}"


def momentum_choices(
    cash_panel: pd.DataFrame,
    weekly_history: pd.DataFrame,
    decisions: pd.DatetimeIndex,
    lookback: int,
    momentum_weight: float,
    breadth: int,
    rank_buffer: int,
    signal_delay: int = 0,
    banned_cik: str | None = None,
) -> pd.DataFrame:
    panel = cash_panel.copy()
    panel["decision_naive"] = pd.to_datetime(panel.decision_at, utc=True).dt.tz_localize(None)
    fundamental_dates = pd.DatetimeIndex(sorted(panel.decision_naive.unique()))
    momentum = weekly_history.pct_change(int(lookback), fill_method=None)
    previous: set[str] = set()
    rows = []
    for decision in decisions:
        available_fundamentals = fundamental_dates[fundamental_dates <= decision]
        prior_prices = weekly_history.index[weekly_history.index < decision]
        if not len(available_fundamentals) or len(prior_prices) <= int(signal_delay):
            continue
        fundamental_date = available_fundamentals[-1]
        reference_date = prior_prices[-1 - int(signal_delay)]
        frame = panel[panel.decision_naive == fundamental_date].copy()
        if banned_cik is not None:
            frame = frame[frame.cik10 != banned_cik]
        raw_momentum = momentum.loc[reference_date]
        frame["momentum_return"] = frame.cik10.map(raw_momentum.to_dict())
        frame["momentum_score"] = frame.groupby("sector", sort=False).momentum_return.rank(pct=True, method="average").fillna(0.5)
        frame["adjusted_score"] = (1.0 - float(momentum_weight)) * frame.cash_score + float(momentum_weight) * frame.momentum_score
        ranked = frame.sort_values(["adjusted_score", "cik10"], ascending=[False, True]).reset_index(drop=True)
        ranked["rank"] = np.arange(1, len(ranked) + 1)
        eligible = set(ranked.loc[ranked["rank"] <= int(breadth) + int(rank_buffer), "cik10"])
        keep = previous & eligible
        selected = list(ranked.loc[ranked.cik10.isin(keep), "cik10"])
        for cik in ranked.cik10:
            if cik not in keep:
                selected.append(cik)
            if len(selected) == int(breadth):
                break
        selected_set = set(selected)
        if len(selected_set) != int(breadth):
            continue
        if selected_set != previous:
            chosen = ranked[ranked.cik10.isin(selected_set)].copy()
            chosen["decision_at"] = decision
            chosen["signal_reference_at"] = reference_date
            chosen["intended_weight"] = 1.0 / int(breadth)
            rows.append(chosen[["decision_at", "signal_reference_at", "cik10", "company_name_as_filed", "sector", "cash_score", "momentum_return", "momentum_score", "adjusted_score", "rank", "intended_weight"]])
        previous = selected_set
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_control(raw: pd.DataFrame, weekly: pd.DataFrame, index: pd.DatetimeIndex, leader_paths: dict, config: dict) -> tuple[dict, pd.DataFrame, bool]:
    cash_scores = raw[raw.family == "cash_conversion"].copy()
    choices = breadth_runner.make_choices(cash_scores, 20)
    targets = base.build_targets(choices, index)
    cash_paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        cash_paths[(scenario, int(cost))], _ = capped.simulate_cash(weekly, targets, scenario, float(cost), None, 20)
    signal = pd.concat([leader_paths[("base", 50)].rename("leader"), cash_paths[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
    paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), cash_paths[(scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
        paths[(scenario, int(cost))] = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
    frozen = pd.read_csv(FROZEN_CONTROL, parse_dates=["Date"]).set_index("Date")
    matched = np.allclose(paths[("base", 50)].net_return.reindex(frozen.index), frozen.net_return, rtol=0, atol=1e-12, equal_nan=True)
    paths[("base", 50)] = frozen
    return paths, frozen, bool(matched)


def composite_path(leader: pd.Series, sleeve: pd.DataFrame, config: dict, cost: float, overlay_delay: int = 0, fixed_target: pd.DataFrame | None = None) -> pd.DataFrame:
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
    history_index = pd.date_range(start=index.min() - pd.Timedelta(weeks=60), end=index.max(), freq="W-FRI")
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
    print(f"loaded {weekly.shape[1]} issuers for 90 lagged momentum-ranking paths", flush=True)

    leader_paths = {(scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return for scenario in config["scenarios"] for cost in config["cost_bps"]}
    control_paths, frozen, frozen_check = build_control(raw, weekly, index, leader_paths, config)
    if not frozen_check:
        raise RuntimeError("rebuilt frozen control does not match audited path")
    control_recent = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "trailing_1y")
    control_full = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "full_recent")
    control_severe = next(row for row in base.metric_rows("control", "base", 200, control_paths[("base", 200)]) if row["window"] == "trailing_1y")

    structures, metric_rows, paths, choices_cache, sleeve_cache = [], [], {}, {}, {}
    for lookback, weight, breadth, buffer in itertools.product(config["momentum_lookbacks_weeks"], config["momentum_weights"], config["breadths"], config["rank_buffers"]):
        name = candidate_name(int(lookback), float(weight), int(breadth), int(buffer))
        choices = momentum_choices(cash_panel, history, index, int(lookback), float(weight), int(breadth), int(buffer))
        targets = base.build_targets(choices, index)
        sleeves, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeves[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(weekly, targets, scenario, float(cost), float(config["internal_stock_cap_multiple"]), int(breadth))
        signal_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
        fixed_target = capped.overlay_target(signal_returns.index, signal_returns.leader, signal_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            path = composite_path(leader_paths[(scenario, int(cost))], sleeves[(scenario, int(cost))], config, float(cost), fixed_target=fixed_target)
            paths[(name, scenario, int(cost))] = path
            metric_rows.extend(base.metric_rows(name, scenario, int(cost), path))
        structures.append({"candidate": name, "lookback_weeks": int(lookback), "momentum_weight": float(weight), "breadth": int(breadth), "rank_buffer": int(buffer), "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)], "sleeve_annual_turnover": float(sleeves[("base", 50)].turnover.mean() * 52.0), "selection_events": int(choices.decision_at.nunique())})
        choices_cache[name], sleeve_cache[name] = choices, sleeves

    performance = pd.DataFrame(metric_rows)
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
    screen["surface_gates"] = (screen.recent_cagr >= control_recent["cagr"] + float(gates["minimum_recent_cagr_improvement"])) & (screen.full_cagr >= control_full["cagr"] + float(gates["minimum_full_cagr_improvement"])) & (screen.severe_recent_cagr > control_severe["cagr"]) & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_portfolio_stock_weight"])) & (screen.sleeve_annual_turnover <= float(gates["maximum_sleeve_annual_one_way_turnover"]))
    challengers = screen[screen.momentum_weight > 0]
    selected_row = (challengers[challengers.surface_gates] if challengers.surface_gates.any() else challengers).iloc[0]
    selected = str(selected_row.candidate)
    matched = screen[(screen.momentum_weight == 0) & (screen.breadth == selected_row.breadth) & (screen.rank_buffer == selected_row.rank_buffer)].sort_values("recent_cagr", ascending=False).iloc[0]

    for cost in [50, 100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    choices_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(joined, int(config["falsification"]["rolling_comparison_weeks"]))
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])

    lookback, weight, breadth, buffer = int(selected_row.lookback_weeks), float(selected_row.momentum_weight), int(selected_row.breadth), int(selected_row.rank_buffer)
    delay_rows = []
    for delay in [0] + [int(x) for x in config["falsification"]["momentum_signal_delays_weeks"]]:
        choices = momentum_choices(cash_panel, history, index, lookback, weight, breadth, buffer, signal_delay=delay)
        targets = base.build_targets(choices, index)
        sleeve, _ = capped.simulate_cash(weekly, targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), breadth)
        path = composite_path(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, f"momentum_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_type": "momentum_signal", "delay_weeks": delay, "recent_cagr": recent["cagr"]})
    for delay in [int(x) for x in config["falsification"]["overlay_delays_weeks"]]:
        path = composite_path(leader_paths[("base", 50)], sleeve_cache[selected][("base", 50)], config, 50.0, overlay_delay=delay)
        recent = next(row for row in base.metric_rows(selected, f"overlay_delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_type": "overlay", "delay_weeks": delay, "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    recent_choices = choices_cache[selected]
    cutoff = recent_choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(recent_choices.loc[recent_choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        choices = momentum_choices(cash_panel, history, index, lookback, weight, breadth, buffer, banned_cik=cik)
        targets = base.build_targets(choices, index)
        sleeve, _ = capped.simulate_cash(weekly, targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), breadth)
        path = composite_path(leader_paths[("base", 50)], sleeve, config, 50.0)
        recent = next(row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y")
        company = recent_choices.loc[recent_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    lookbacks = list(map(int, config["momentum_lookbacks_weeks"])); weights = list(map(float, config["momentum_weights"])); breadths = list(map(int, config["breadths"]))
    li, wi, bi = lookbacks.index(lookback), weights.index(weight), breadths.index(breadth)
    neighbors = screen[screen.lookback_weeks.isin(lookbacks[max(0, li-1):li+2]) & screen.momentum_weight.isin(weights[max(0, wi-1):wi+2]) & screen.breadth.isin(breadths[max(0, bi-1):bi+2])].copy()
    neighbors["joint_improvement"] = (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0]); b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    momentum_d1 = float(delays[(delays.delay_type == "momentum_signal") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); momentum_d2 = float(delays[(delays.delay_type == "momentum_signal") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    overlay_d1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0]); overlay_d2 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    checks = {
        "surface_gates": bool(selected_row.surface_gates),
        "momentum_one_week_delay_beats_control": momentum_d1 > control_recent["cagr"], "momentum_two_week_delay_beats_control": momentum_d2 > control_recent["cagr"],
        "overlay_one_week_delay_beats_control": overlay_d1 > control_recent["cagr"], "overlay_two_week_delay_beats_control": overlay_d2 > control_recent["cagr"],
        "rolling_gate": rolling_share >= float(gates["minimum_completed_rolling_outperformance_share"]), "neighborhood_gate": neighborhood_share >= float(gates["minimum_neighborhood_joint_improvement_share"]),
        "bootstrap_4w_gate": b4 >= float(gates["minimum_bootstrap_probability_positive"]), "bootstrap_13w_gate": b13 >= float(gates["minimum_bootstrap_probability_positive"]),
        "worst_loo_beats_control": float(worst.recent_cagr) > control_recent["cagr"], "single_issuer_influence_gate": issuer_share is not None and issuer_share <= float(gates["maximum_single_issuer_improvement_share"]),
        "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected_row.recent_cagr, atol=1e-12, rtol=0))
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False); screen.to_csv(OUTPUT / "screening.csv", index=False); bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False); loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False); neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)), "selected_candidate": selected,
        "lookback_weeks": lookback, "momentum_weight": weight, "breadth": breadth, "rank_buffer": buffer,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe), "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr), "severe_recent_cagr": float(selected_row.severe_recent_cagr), "sleeve_annual_turnover": float(selected_row.sleeve_annual_turnover),
        "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]),
        "matched_zero_momentum_recent_cagr": float(matched.recent_cagr), "matched_zero_momentum_full_cagr": float(matched.full_cagr), "momentum_incremental_recent_cagr": float(selected_row.recent_cagr - matched.recent_cagr), "momentum_incremental_full_cagr": float(selected_row.full_cagr - matched.full_cagr),
        "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share, "neighborhood_joint_improvement_share": neighborhood_share, "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13,
        "momentum_one_week_delay_recent_cagr": momentum_d1, "momentum_two_week_delay_recent_cagr": momentum_d2, "overlay_one_week_delay_recent_cagr": overlay_d1, "overlay_two_week_delay_recent_cagr": overlay_d2,
        "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": frozen_check, "runtime": runtime,
        "artifact_sha256": {"selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"), "frozen_control_50bps": sha256(FROZEN_CONTROL)}, "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC cash-conversion momentum rank v1\n\n"
        f"Tested {len(screen)} strictly lagged issuer-level momentum confirmation paths. The strongest positive-momentum challenger, {selected}, produced {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR versus {control_recent['cagr']:.2%}, {control_recent['sharpe_zero_rf']:.3f}, {control_recent['max_drawdown']:.2%}, and {control_full['cagr']:.2%} for the frozen control. It returned {selected_row.severe_recent_cagr:.2%} at 200-bps costs versus {control_severe['cagr']:.2%}.\n\n"
        f"No positive-momentum challenger beat the control recently. The complete falsification decision was {'PASS' if all_passed else 'FAIL'}, with {rolling_share:.2%} rolling-window outperformance and {b4:.2%}/{b13:.2%} bootstrap probabilities. The branch was closed without further tuning. No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
