#!/usr/bin/env python3
"""Test lagged market-breadth and dispersion control of the frozen cash sleeve."""

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

CONFIG = ROOT / "config/sec_breadth_dispersion_allocation_controller_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1"
ECONOMIC_TOLERANCE = 1e-12


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(
    horizon: int,
    calibration: int,
    quantile: float,
    mode: str,
    low: float,
    high: float,
) -> str:
    return (
        f"h{int(horizon)}__cal{int(calibration)}__q{int(round(float(quantile) * 100)):02d}"
        f"__{mode}__w{int(round(float(low) * 100)):02d}_{int(round(float(high) * 100)):02d}"
    )


def breadth_dispersion_signals(weekly: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Signals at date t use prices ending no later than t-1."""
    returns = weekly.pct_change(int(horizon), fill_method=None).shift(1).replace([np.inf, -np.inf], np.nan)
    breadth = (returns > 0).where(returns.notna()).mean(axis=1)
    lower = returns.quantile(0.05, axis=1)
    upper = returns.quantile(0.95, axis=1)
    winsorized = returns.clip(lower=lower, upper=upper, axis=0)
    dispersion = winsorized.std(axis=1, ddof=1)
    coverage = returns.notna().sum(axis=1)
    return pd.DataFrame({"breadth": breadth, "dispersion": dispersion, "issuer_coverage": coverage})


def regime_state(
    signals: pd.DataFrame,
    calibration: int,
    quantile: float,
    mode: str,
    delay: int = 0,
) -> pd.Series:
    breadth_threshold = signals.breadth.rolling(
        int(calibration), min_periods=int(calibration)
    ).quantile(float(quantile)).shift(1)
    dispersion_threshold = signals.dispersion.rolling(
        int(calibration), min_periods=int(calibration)
    ).quantile(float(quantile)).shift(1)
    breadth_high = signals.breadth > breadth_threshold
    dispersion_high = signals.dispersion > dispersion_threshold
    if mode == "breadth_high":
        state = breadth_high
    elif mode == "dispersion_high":
        state = dispersion_high
    elif mode == "breadth_and_dispersion_high":
        state = breadth_high & dispersion_high
    elif mode == "breadth_high_dispersion_low":
        state = breadth_high & ~dispersion_high
    elif mode == "breadth_or_dispersion_high":
        state = breadth_high | dispersion_high
    else:
        raise ValueError(f"unknown state mode: {mode}")
    valid = breadth_threshold.notna() & dispersion_threshold.notna()
    return state.where(valid, False).shift(int(delay)).fillna(False).astype(bool)


def controller_target(
    base_target: pd.DataFrame,
    signals: pd.DataFrame,
    calibration: int,
    quantile: float,
    mode: str,
    low: float,
    high: float,
    signal_delay: int = 0,
) -> tuple[pd.DataFrame, pd.Series]:
    state = regime_state(signals.reindex(base_target.index), calibration, quantile, mode, signal_delay)
    active = base_target.cash_conversion > 0
    cash_weight = pd.Series(np.where(state, float(high), float(low)), index=base_target.index).where(active, 0.0)
    target = pd.DataFrame(index=base_target.index)
    target["leader"] = 1.0 - cash_weight
    target["cash_conversion"] = cash_weight
    return target, state


def simulate_composite(
    leader: pd.Series,
    sleeve: pd.DataFrame,
    target: pd.DataFrame,
    cost: float,
) -> pd.DataFrame:
    returns = pd.concat([leader.rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    return dynamic.simulate(returns, target.reindex(returns.index), float(cost))


def stable_excess_returns(joined: pd.DataFrame) -> pd.Series:
    difference = joined.candidate - joined.control
    return difference.mask(difference.abs() <= ECONOMIC_TOLERANCE, 0.0)


def stable_completed_rolling_outperformance(joined: pd.DataFrame, weeks: int) -> tuple[float, int]:
    rolling = (1.0 + joined).rolling(int(weeks), min_periods=int(weeks)).apply(np.prod, raw=True) - 1.0
    complete = rolling.dropna(subset=["candidate", "control"])
    difference = complete.candidate - complete.control
    share = float((difference > ECONOMIC_TOLERANCE).mean()) if len(complete) else 0.0
    return share, int(len(complete))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    cash_scores = raw[raw.family == "cash_conversion"].copy()
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(cash_scores.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=index)
    weekly = pd.DataFrame(series, index=index)
    signal_panels = {
        int(horizon): breadth_dispersion_signals(weekly, int(horizon))
        for horizon in config["signal_horizons_weeks"]
    }
    print(
        f"built {len(signal_panels)} strictly lagged breadth/dispersion panels across "
        f"{weekly.shape[1]} issuer histories",
        flush=True,
    )

    leader_paths = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario in config["scenarios"] for cost in config["cost_bps"]
    }
    baseline_choices = breadth_runner.make_choices(cash_scores, int(config["breadth"]))
    baseline_stock_targets = base.build_targets(baseline_choices, index)
    baseline_sleeves, peak_sleeve_weights = {}, {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_sleeves[(scenario, int(cost))], peak_sleeve_weights[(scenario, int(cost))] = capped.simulate_cash(
            weekly, baseline_stock_targets, scenario, float(cost), None, int(config["breadth"])
        )
    control_signal = pd.concat(
        [
            leader_paths[("base", 50)].rename("leader"),
            baseline_sleeves[("base", 50)].net_return.rename("cash_conversion"),
        ], axis=1,
    ).dropna()
    base_target = capped.overlay_target(
        control_signal.index, control_signal.leader, control_signal.cash_conversion,
        int(config["overlay_lookback_weeks"]), 0.5,
    )
    control_paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        control_paths[(scenario, int(cost))] = simulate_composite(
            leader_paths[(scenario, int(cost))], baseline_sleeves[(scenario, int(cost))],
            base_target, float(cost),
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

    structures, metric_rows, paths, target_cache, state_cache = [], [], {}, {}, {}
    grid = itertools.product(
        config["signal_horizons_weeks"], config["calibration_windows_weeks"],
        config["state_quantiles"], config["state_modes"], config["active_weight_pairs"],
    )
    for horizon, calibration, quantile, mode, pair in grid:
        low, high = float(pair[0]), float(pair[1])
        name = candidate_name(int(horizon), int(calibration), float(quantile), str(mode), low, high)
        target, state = controller_target(
            base_target, signal_panels[int(horizon)], int(calibration), float(quantile),
            str(mode), low, high,
        )
        target_cache[name], state_cache[name] = target, state
        annual_turnover = float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0)
        active = base_target.cash_conversion > 0
        state_share = float(state[active].mean()) if active.any() else 0.0
        transitions = int(state.astype(int).diff().abs().fillna(0).sum())
        peak_total_stock_weight = float(high * peak_sleeve_weights[("base", 50)])
        structures.append(
            {
                "candidate": name,
                "signal_horizon_weeks": int(horizon),
                "calibration_weeks": int(calibration),
                "state_quantile": float(quantile),
                "state_mode": str(mode),
                "low_active_weight": low,
                "high_active_weight": high,
                "high_state_share_when_active": state_share,
                "state_transitions": transitions,
                "controller_annual_one_way_turnover": annual_turnover,
                "peak_total_stock_weight": peak_total_stock_weight,
            }
        )
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            path = simulate_composite(
                leader_paths[(scenario, int(cost))], baseline_sleeves[(scenario, int(cost))],
                target, float(cost),
            )
            paths[(name, scenario, int(cost))] = path
            metric_rows.extend(base.metric_rows(name, scenario, int(cost), path))

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
        & (screen.controller_annual_one_way_turnover <= float(gates["maximum_controller_annual_one_way_turnover"]))
    )
    shortlist_rows = []
    delayed_bases = {
        int(delay): capped.overlay_target(
            control_signal.index, control_signal.leader, control_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5, int(delay),
        )
        for delay in config["falsification"]["overlay_delays_weeks"]
    }
    for candidate_row in screen[screen.surface_gates].itertuples(index=False):
        name = str(candidate_row.candidate)
        candidate_joined = pd.concat(
            [paths[(name, "base", 50)].net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1
        ).dropna()
        candidate_recent = candidate_joined.loc[
            candidate_joined.index >= candidate_joined.index.max() - pd.DateOffset(years=1)
        ]
        candidate_rolling, candidate_windows = stable_completed_rolling_outperformance(
            candidate_joined, int(config["falsification"]["rolling_comparison_weeks"])
        )
        boot = {
            int(block): dynamic.block_bootstrap(
                stable_excess_returns(candidate_recent),
                int(block), int(config["falsification"]["bootstrap_draws"]),
                int(config["falsification"]["bootstrap_seed"]),
            )
            for block in config["falsification"]["bootstrap_blocks_weeks"]
        }
        candidate_delays = {}
        for delay in config["falsification"]["controller_signal_delays_weeks"]:
            delayed_target, _ = controller_target(
                base_target,
                signal_panels[int(candidate_row.signal_horizon_weeks)],
                int(candidate_row.calibration_weeks),
                float(candidate_row.state_quantile),
                str(candidate_row.state_mode),
                float(candidate_row.low_active_weight),
                float(candidate_row.high_active_weight),
                int(delay),
            )
            delayed_path = simulate_composite(
                leader_paths[("base", 50)], baseline_sleeves[("base", 50)], delayed_target, 50.0
            )
            candidate_delays[("controller", int(delay))] = next(
                row for row in base.metric_rows(name, "shortlist", 50, delayed_path)
                if row["window"] == "trailing_1y"
            )["cagr"]
        for delay in config["falsification"]["overlay_delays_weeks"]:
            delayed_target, _ = controller_target(
                delayed_bases[int(delay)],
                signal_panels[int(candidate_row.signal_horizon_weeks)],
                int(candidate_row.calibration_weeks),
                float(candidate_row.state_quantile),
                str(candidate_row.state_mode),
                float(candidate_row.low_active_weight),
                float(candidate_row.high_active_weight),
            )
            delayed_path = simulate_composite(
                leader_paths[("base", 50)], baseline_sleeves[("base", 50)], delayed_target, 50.0
            )
            candidate_delays[("overlay", int(delay))] = next(
                row for row in base.metric_rows(name, "shortlist", 50, delayed_path)
                if row["window"] == "trailing_1y"
            )["cagr"]
        candidate_neighbors = screen[
            (screen.state_mode == candidate_row.state_mode)
            & (screen.signal_horizon_weeks == candidate_row.signal_horizon_weeks)
        ]
        candidate_neighborhood = float(
            (
                (candidate_neighbors.recent_cagr > control_recent["cagr"])
                & (candidate_neighbors.full_cagr > control_full["cagr"])
            ).mean()
        )
        b4_value = float(boot[4]["probability_positive"])
        b13_value = float(boot[13]["probability_positive"])
        preliminary = (
            candidate_rolling >= float(gates["minimum_completed_rolling_outperformance_share"])
            and candidate_neighborhood >= float(gates["minimum_neighborhood_joint_improvement_share"])
            and b4_value >= float(gates["minimum_bootstrap_probability_positive"])
            and b13_value >= float(gates["minimum_bootstrap_probability_positive"])
            and candidate_delays[("controller", 1)] > control_recent["cagr"]
            and candidate_delays[("controller", 2)] > control_recent["cagr"]
            and candidate_delays[("overlay", 1)] > control_recent["cagr"]
            and candidate_delays[("overlay", 2)] > control_recent["cagr"]
        )
        shortlist_rows.append(
            {
                "candidate": name,
                "recent_cagr": float(candidate_row.recent_cagr),
                "full_cagr": float(candidate_row.full_cagr),
                "completed_rolling_windows": candidate_windows,
                "rolling_outperformance_share": candidate_rolling,
                "neighborhood_joint_improvement_share": candidate_neighborhood,
                "bootstrap_4w_probability_positive": b4_value,
                "bootstrap_13w_probability_positive": b13_value,
                "controller_one_week_delay_recent_cagr": candidate_delays[("controller", 1)],
                "controller_two_week_delay_recent_cagr": candidate_delays[("controller", 2)],
                "overlay_one_week_delay_recent_cagr": candidate_delays[("overlay", 1)],
                "overlay_two_week_delay_recent_cagr": candidate_delays[("overlay", 2)],
                "preliminary_robustness_gates": bool(preliminary),
            }
        )
    shortlist = pd.DataFrame(shortlist_rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    robust_names = set(shortlist.loc[shortlist.preliminary_robustness_gates, "candidate"])
    selection_pool = screen[screen.candidate.isin(robust_names)]
    if selection_pool.empty:
        selection_pool = screen[screen.surface_gates] if screen.surface_gates.any() else screen
    selected_row = selection_pool.iloc[0]
    selected = str(selected_row.candidate)
    verification_joined = pd.concat(
        [paths[(selected, "base", 50)].net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1
    ).dropna()
    verification_rolling, _ = stable_completed_rolling_outperformance(
        verification_joined, int(config["falsification"]["rolling_comparison_weeks"])
    )
    recorded_rolling = float(shortlist.loc[shortlist.candidate == selected, "rolling_outperformance_share"].iloc[0])
    if not np.isclose(verification_rolling, recorded_rolling, rtol=0, atol=1e-12):
        raise RuntimeError(
            f"shortlist path changed during validation: recorded rolling={recorded_rolling}, "
            f"recomputed rolling={verification_rolling}"
        )
    for cost in [50, 100, 200]:
        paths[(selected, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    target_cache[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    selected_signals = signal_panels[int(selected_row.signal_horizon_weeks)].copy()
    selected_signals["high_state"] = state_cache[selected]
    selected_signals.to_csv(OUTPUT / "selected_signal_panel.csv", index_label="Date")
    baseline_choices.to_csv(OUTPUT / "unchanged_portfolio_choices.csv", index=False)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = stable_completed_rolling_outperformance(
        joined, int(config["falsification"]["rolling_comparison_weeks"])
    )
    if not np.isclose(rolling_share, recorded_rolling, rtol=0, atol=1e-12):
        raise RuntimeError(
            f"persisted shortlist mismatch: recorded rolling={recorded_rolling}, "
            f"persisted rolling={rolling_share}"
        )
    bootstrap = pd.DataFrame(
        [
            dynamic.block_bootstrap(
                stable_excess_returns(recent_joined),
                int(block), int(config["falsification"]["bootstrap_draws"]),
                int(config["falsification"]["bootstrap_seed"]),
            )
            for block in config["falsification"]["bootstrap_blocks_weeks"]
        ]
    )

    horizon = int(selected_row.signal_horizon_weeks)
    calibration = int(selected_row.calibration_weeks)
    quantile = float(selected_row.state_quantile)
    mode = str(selected_row.state_mode)
    low = float(selected_row.low_active_weight)
    high = float(selected_row.high_active_weight)
    delay_rows = []
    for delay in config["falsification"]["controller_signal_delays_weeks"]:
        target, _ = controller_target(
            base_target, signal_panels[horizon], calibration, quantile, mode, low, high, int(delay)
        )
        path = simulate_composite(
            leader_paths[("base", 50)], baseline_sleeves[("base", 50)], target, 50.0
        )
        recent = next(
            row for row in base.metric_rows(selected, f"controller_delay_{delay}", 50, path)
            if row["window"] == "trailing_1y"
        )
        delay_rows.append({"delay_type": "controller", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    for delay in config["falsification"]["overlay_delays_weeks"]:
        delayed_base = capped.overlay_target(
            control_signal.index, control_signal.leader, control_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5, int(delay),
        )
        target, _ = controller_target(
            delayed_base, signal_panels[horizon], calibration, quantile, mode, low, high
        )
        path = simulate_composite(
            leader_paths[("base", 50)], baseline_sleeves[("base", 50)], target, 50.0
        )
        recent = next(
            row for row in base.metric_rows(selected, f"overlay_delay_{delay}", 50, path)
            if row["window"] == "trailing_1y"
        )
        delay_rows.append({"delay_type": "overlay", "delay_weeks": int(delay), "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    recent_cutoff = baseline_choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(baseline_choices.loc[baseline_choices.decision_at >= recent_cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        altered_scores = cash_scores[cash_scores.cik10 != cik]
        choices = breadth_runner.make_choices(altered_scores, int(config["breadth"]))
        sleeve, _ = capped.simulate_cash(
            weekly, base.build_targets(choices, index), "base", 50.0, None, int(config["breadth"])
        )
        altered_signal = pd.concat(
            [leader_paths[("base", 50)].rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1
        ).dropna()
        altered_base = capped.overlay_target(
            altered_signal.index, altered_signal.leader, altered_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5,
        )
        target, _ = controller_target(
            altered_base, signal_panels[horizon], calibration, quantile, mode, low, high
        )
        path = simulate_composite(leader_paths[("base", 50)], sleeve, target, 50.0)
        recent = next(
            row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y"
        )
        company = baseline_choices.loc[baseline_choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append(
            {"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"],
             "cagr_change": recent["cagr"] - selected_row.recent_cagr}
        )
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    neighbors = screen[
        (screen.state_mode == mode) & (screen.signal_horizon_weeks == horizon)
    ].copy()
    neighbors["joint_improvement"] = (
        (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    )
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    cd1 = float(delays[(delays.delay_type == "controller") & (delays.delay_weeks == 1)].recent_cagr.iloc[0])
    cd2 = float(delays[(delays.delay_type == "controller") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    od1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0])
    od2 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 2)].recent_cagr.iloc[0])
    signals = signal_panels[horizon]
    lag_check = weekly.pct_change(horizon, fill_method=None).shift(1)
    checks = {
        "surface_gates": bool(selected_row.surface_gates),
        "signals_strictly_lagged": bool(signals.index.equals(lag_check.index)),
        "controller_one_week_delay_beats_control": cd1 > control_recent["cagr"],
        "controller_two_week_delay_beats_control": cd2 > control_recent["cagr"],
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

    performance.to_csv(OUTPUT / "performance.csv", index=False)
    screen.to_csv(OUTPUT / "screening.csv", index=False)
    shortlist.to_csv(OUTPUT / "robust_shortlist.csv", index=False)
    neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)),
        "headline_surface_passers": int(screen.surface_gates.sum()),
        "preliminary_robustness_passers": int(shortlist.preliminary_robustness_gates.sum()),
        "issuer_price_histories": int(weekly.shape[1]),
        "selected_candidate": selected,
        "signal_horizon_weeks": horizon,
        "calibration_weeks": calibration,
        "state_quantile": quantile,
        "state_mode": mode,
        "low_active_weight": low,
        "high_active_weight": high,
        "high_state_share_when_active": float(selected_row.high_state_share_when_active),
        "state_transitions": int(selected_row.state_transitions),
        "controller_annual_one_way_turnover": float(selected_row.controller_annual_one_way_turnover),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "recent_cagr": float(selected_row.recent_cagr),
        "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown),
        "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "control_recent_cagr": float(control_recent["cagr"]),
        "control_full_cagr": float(control_full["cagr"]),
        "control_severe_recent_cagr": float(control_severe["cagr"]),
        "completed_rolling_windows": rolling_windows,
        "rolling_outperformance_share": rolling_share,
        "neighborhood_joint_improvement_share": neighborhood_share,
        "bootstrap_4w_probability_positive": b4,
        "bootstrap_13w_probability_positive": b13,
        "controller_one_week_delay_recent_cagr": cd1,
        "controller_two_week_delay_recent_cagr": cd2,
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
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_signal_panel": sha256(OUTPUT / "selected_signal_panel.csv"),
            "robust_shortlist": sha256(OUTPUT / "robust_shortlist.csv"),
            "frozen_control_50bps": sha256(FROZEN_CONTROL),
        },
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Breadth and dispersion allocation controller v1\n\n"
        f"Tested {len(screen)} strictly lagged allocation controllers without changing the frozen "
        f"cash-conversion holdings. The selected `{selected}` path produced "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR "
        f"versus {control_recent['cagr']:.2%}, {control_recent['sharpe_zero_rf']:.3f}, "
        f"{control_recent['max_drawdown']:.2%}, and {control_full['cagr']:.2%} for the frozen control. "
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%} versus "
        f"{control_severe['cagr']:.2%}.\n\n"
        f"Controller delays returned {cd1:.2%}/{cd2:.2%}, overlay delays returned "
        f"{od1:.2%}/{od2:.2%}, rolling outperformance was {rolling_share:.2%}, neighborhood joint "
        f"improvement was {neighborhood_share:.2%}, and bootstrap probabilities were "
        f"{b4:.2%}/{b13:.2%}. Removing {worst.company_name} left {worst.recent_cagr:.2%}.\n\n"
        f"The complete falsification decision was **{'PASS' if all_passed else 'FAIL'}**. "
        f"No strategy replacement, forward clock, or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
