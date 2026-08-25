#!/usr/bin/env python3
"""Falsify generic stock caps and persistent states around the breadth challenger."""

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
import run_sec_breadth_dispersion_allocation_controller_v1 as controller
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_breadth_controller_cap_persistence_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
CHALLENGER = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1"
OUTPUT = ROOT / "evidence/sec_breadth_controller_cap_persistence_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def persistent_boolean(raw: pd.Series, enter: int, exit_: int) -> pd.Series:
    """Confirm state changes using only current and earlier observations."""
    state = False
    true_run = false_run = 0
    values = []
    for value in raw.fillna(False).astype(bool):
        if value:
            true_run += 1
            false_run = 0
        else:
            false_run += 1
            true_run = 0
        if not state and true_run >= int(enter):
            state = True
        elif state and false_run >= int(exit_):
            state = False
        values.append(state)
    return pd.Series(values, index=raw.index, dtype=bool)


def label(cap, be: int, bx: int, oe: int, ox: int) -> str:
    cap_text = "uncapped" if cap is None else f"cap{float(cap):.2f}x"
    return f"{cap_text}__breadth{be}in{bx}out__overlay{oe}in{ox}out"


def persistent_target(
    base_target: pd.DataFrame,
    raw_breadth: pd.Series,
    be: int,
    bx: int,
    oe: int,
    ox: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    breadth_state = persistent_boolean(raw_breadth.reindex(base_target.index), be, bx)
    overlay_state = persistent_boolean(base_target.cash_conversion > 0, oe, ox)
    weight = pd.Series(
        np.where(breadth_state, 0.8, 0.5), index=base_target.index
    ).where(overlay_state, 0.0)
    target = pd.DataFrame({"leader": 1.0 - weight, "cash_conversion": weight}, index=base_target.index)
    states = pd.DataFrame(
        {
            "raw_breadth_state": raw_breadth.reindex(base_target.index).fillna(False).astype(bool),
            "persistent_breadth_state": breadth_state,
            "raw_overlay_state": (base_target.cash_conversion > 0),
            "persistent_overlay_state": overlay_state,
        }, index=base_target.index,
    )
    return target, states


def recent_metric(name: str, scenario: str, cost: int, path: pd.DataFrame) -> dict:
    return next(row for row in base.metric_rows(name, scenario, cost, path) if row["window"] == "trailing_1y")


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    cash_scores = raw[raw.family == "cash_conversion"].copy()
    choices = breadth_runner.make_choices(cash_scores, int(config["breadth"]))
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
    stock_targets = base.build_targets(choices, index)
    raw_breadth = controller.regime_state(
        controller.breadth_dispersion_signals(weekly, int(config["signal_horizon_weeks"])),
        int(config["calibration_weeks"]), float(config["state_quantile"]), str(config["state_mode"]),
    )
    leader = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"])
    }
    sleeves, peaks = {}, {}
    for cap, scenario, cost in itertools.product(
        config["cash_sleeve_cap_multiples"], config["scenarios"], config["cost_bps"]
    ):
        cap_key = "uncapped" if cap is None else f"{float(cap):.2f}"
        sleeves[(cap_key, scenario, int(cost))], peaks[(cap_key, scenario, int(cost))] = capped.simulate_cash(
            weekly, stock_targets, scenario, float(cost), cap, int(config["breadth"])
        )

    frozen = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date")
    challenger = pd.read_csv(CHALLENGER / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    challenger_recent = recent_metric("challenger", "base", 50, challenger)
    control_recent = recent_metric("control", "base", 50, frozen)
    control_full = next(r for r in base.metric_rows("control", "base", 50, frozen) if r["window"] == "full_recent")

    policies = list(itertools.product(
        config["breadth_entry_confirmations"], config["breadth_exit_confirmations"],
        config["overlay_entry_confirmations"], config["overlay_exit_confirmations"],
    ))
    rows, paths, targets, states, base_targets = [], {}, {}, {}, {}
    for cap in config["cash_sleeve_cap_multiples"]:
        cap_key = "uncapped" if cap is None else f"{float(cap):.2f}"
        signal = pd.concat([
            leader[("base", 50)].rename("leader"),
            sleeves[(cap_key, "base", 50)].net_return.rename("cash_conversion"),
        ], axis=1).dropna()
        base_target = capped.overlay_target(
            signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), 0.5
        )
        base_targets[cap_key] = base_target
        for be, bx, oe, ox in policies:
            name = label(cap, be, bx, oe, ox)
            target, state = persistent_target(base_target, raw_breadth, be, bx, oe, ox)
            targets[name], states[name] = target, state
            annual_turnover = float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0)
            candidate_paths = {}
            for cost in (50, 200):
                candidate_paths[cost] = controller.simulate_composite(
                    leader[("base", cost)], sleeves[(cap_key, "base", cost)], target, float(cost)
                )
                paths[(name, "base", cost)] = candidate_paths[cost]
            recent = recent_metric(name, "base", 50, candidate_paths[50])
            full = next(r for r in base.metric_rows(name, "base", 50, candidate_paths[50]) if r["window"] == "full_recent")
            severe = recent_metric(name, "base", 200, candidate_paths[200])
            delayed_base = capped.overlay_target(
                signal.index, signal.leader, signal.cash_conversion,
                int(config["overlay_lookback_weeks"]), 0.5, 1,
            )
            delayed_target, _ = persistent_target(delayed_base, raw_breadth, be, bx, oe, ox)
            delayed_path = controller.simulate_composite(
                leader[("base", 50)], sleeves[(cap_key, "base", 50)], delayed_target, 50.0
            )
            rows.append({
                "candidate": name, "cap_multiple": cap, "breadth_entry": be, "breadth_exit": bx,
                "overlay_entry": oe, "overlay_exit": ox, "recent_cagr": recent["cagr"],
                "recent_sharpe": recent["sharpe_zero_rf"], "recent_drawdown": recent["max_drawdown"],
                "full_cagr": full["cagr"], "severe_recent_cagr": severe["cagr"],
                "overlay_delay1_recent_cagr": recent_metric(name, "delay", 50, delayed_path)["cagr"],
                "peak_total_stock_weight": 0.8 * peaks[(cap_key, "base", 50)],
                "annual_one_way_turnover": annual_turnover,
                "breadth_transitions": int(state.persistent_breadth_state.astype(int).diff().abs().fillna(0).sum()),
                "overlay_transitions": int(state.persistent_overlay_state.astype(int).diff().abs().fillna(0).sum()),
            })
    screen = pd.DataFrame(rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)

    baseline_name = label(None, 1, 1, 1, 1)
    baseline_path = paths[(baseline_name, "base", 50)]
    baseline_matches = np.allclose(
        baseline_path.net_return.reindex(challenger.index), challenger.net_return,
        rtol=0, atol=1e-12, equal_nan=True,
    )
    if not baseline_matches:
        raise RuntimeError("unchanged cap/persistence baseline did not reproduce the frozen challenger")

    limits = config["selection"]
    qualified = screen[
        (screen.candidate != baseline_name)
        & (screen.recent_cagr >= max(
            float(limits["minimum_recent_cagr"]),
            float(challenger_recent["cagr"]) - float(limits["maximum_return_sacrifice_from_challenger"]),
        ))
        & (screen.full_cagr >= float(control_full["cagr"]))
        & (screen.severe_recent_cagr > float(control_recent["cagr"]) - 0.15)
        & (screen.overlay_delay1_recent_cagr > float(control_recent["cagr"]))
        & (screen.peak_total_stock_weight <= float(limits["maximum_peak_total_portfolio_stock_weight"]))
    ]
    selection_reason = "return-preserving robustness gates"
    selection_pool = qualified
    if selection_pool.empty:
        selection_pool = screen[
            screen.cap_multiple.notna()
            & (screen.cap_multiple <= 1.5)
            & (screen.recent_cagr >= float(challenger_recent["cagr"]) - float(limits["maximum_return_sacrifice_from_challenger"]))
        ]
        selection_reason = "no timing-robust candidate; strongest genuinely capped diagnostic"
    selected_row = selection_pool.assign(_recent_rank=selection_pool.recent_cagr.round(12)).sort_values(
        ["_recent_rank", "full_cagr", "overlay_delay1_recent_cagr", "peak_total_stock_weight"],
        ascending=[False, False, False, True],
    ).iloc[0]
    selected = str(selected_row.candidate)
    cap_value = selected_row.cap_multiple
    cap = None if pd.isna(cap_value) else float(cap_value)
    cap_key = "uncapped" if cap is None else f"{cap:.2f}"
    be, bx, oe, ox = map(int, [selected_row.breadth_entry, selected_row.breadth_exit, selected_row.overlay_entry, selected_row.overlay_exit])

    # Complete scenario/cost paths for the selected specification.
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        path = controller.simulate_composite(
            leader[(scenario, int(cost))], sleeves[(cap_key, scenario, int(cost))], targets[selected], float(cost)
        )
        paths[(selected, scenario, int(cost))] = path
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    states[selected].rename_axis("Date").to_csv(OUTPUT / "selected_states.csv")
    choices.to_csv(OUTPUT / "unchanged_portfolio_choices.csv", index=False)

    # Delay falsification recomputes the state machine from delayed inputs.
    delay_rows = []
    signal = pd.concat([
        leader[("base", 50)].rename("leader"), sleeves[(cap_key, "base", 50)].net_return.rename("cash_conversion")
    ], axis=1).dropna()
    for kind, values in (("controller", config["falsification"]["controller_signal_delays_weeks"]),
                         ("overlay", config["falsification"]["overlay_delays_weeks"])):
        for delay in values:
            delayed_raw = raw_breadth.shift(int(delay)).fillna(False) if kind == "controller" else raw_breadth
            delayed_base = capped.overlay_target(
                signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]),
                0.5, int(delay) if kind == "overlay" else 0,
            )
            delayed_target, _ = persistent_target(delayed_base, delayed_raw, be, bx, oe, ox)
            delayed_path = controller.simulate_composite(
                leader[("base", 50)], sleeves[(cap_key, "base", 50)], delayed_target, 50.0
            )
            metric = recent_metric(selected, f"{kind}_delay", 50, delayed_path)
            delay_rows.append({"delay_type": kind, "delay_weeks": int(delay), "recent_cagr": metric["cagr"]})
    delays = pd.DataFrame(delay_rows)

    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    rolling_share, rolling_windows = controller.stable_completed_rolling_outperformance(
        joined, int(config["falsification"]["rolling_comparison_weeks"])
    )
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    bootstrap = pd.DataFrame([
        dynamic.block_bootstrap(
            controller.stable_excess_returns(recent_joined), int(block),
            int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"]),
        ) for block in config["falsification"]["bootstrap_blocks_weeks"]
    ])

    # Exact recent leave-one-company-out attribution for the selected generic rule.
    cutoff = choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(choices.loc[choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        altered = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], int(config["breadth"]))
        sleeve, _ = capped.simulate_cash(
            weekly, base.build_targets(altered, index), "base", 50.0, cap, int(config["breadth"])
        )
        altered_signal = pd.concat([
            leader[("base", 50)].rename("leader"), sleeve.net_return.rename("cash_conversion")
        ], axis=1).dropna()
        altered_base = capped.overlay_target(
            altered_signal.index, altered_signal.leader, altered_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5,
        )
        altered_target, _ = persistent_target(altered_base, raw_breadth, be, bx, oe, ox)
        path = controller.simulate_composite(leader[("base", 50)], sleeve, altered_target, 50.0)
        metric = recent_metric(selected, "loo", 50, path)
        company = choices.loc[choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
                         "cagr_change": metric["cagr"] - float(selected_row.recent_cagr)})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -float(worst.cagr_change)) / improvement) if improvement > 0 else None
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    delay1 = float(delays[(delays.delay_type == "overlay") & (delays.delay_weeks == 1)].recent_cagr.iloc[0])
    checks = {
        "baseline_reproduces_112pct_challenger": bool(baseline_matches),
        "selected_by_return_preserving_robustness_gates": selection_reason == "return-preserving robustness gates",
        "recent_cagr_at_least_110pct": float(selected_row.recent_cagr) >= 1.10,
        "overlay_delay1_beats_frozen_control": delay1 > float(control_recent["cagr"]),
        "worst_loo_beats_frozen_control": float(worst.recent_cagr) > float(control_recent["cagr"]),
        "single_issuer_share_at_most_50pct": issuer_share is not None and issuer_share <= 0.5,
        "bootstrap_4w_at_least_95pct": b4 >= 0.95,
        "bootstrap_13w_at_least_95pct": b13 >= 0.95,
        "rolling_outperformance_at_least_50pct": rolling_share >= 0.5,
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    screen.to_csv(OUTPUT / "screening.csv", index=False)
    qualified.to_csv(OUTPUT / "eligible_candidates.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "eligible_candidate_count": int(len(qualified)),
        "selected_candidate": selected, "selection_reason": selection_reason, "cap_multiple": cap,
        "breadth_entry_confirmations": be, "breadth_exit_confirmations": bx,
        "overlay_entry_confirmations": oe, "overlay_exit_confirmations": ox,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "challenger_recent_cagr": float(challenger_recent["cagr"]), "control_recent_cagr": float(control_recent["cagr"]),
        "overlay_delay1_recent_cagr": delay1, "rolling_outperformance_share": rolling_share,
        "completed_rolling_windows": rolling_windows, "bootstrap_4w_probability_positive": b4,
        "bootstrap_13w_probability_positive": b13, "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr),
        "single_issuer_improvement_share": issuer_share, "checks": checks,
        "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_states": sha256(OUTPUT / "selected_states.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Generic cap and persistence retest v1\n\n"
        f"Tested {len(screen)} ticker-agnostic cap/persistence variants around the frozen breadth challenger. "
        f"The selected `{selected}` produced {selected_row.recent_cagr:.2%} recent CAGR, "
        f"{selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and "
        f"{selected_row.full_cagr:.2%} full CAGR. The unchanged challenger was {challenger_recent['cagr']:.2%}; "
        f"the frozen incumbent was {control_recent['cagr']:.2%}.\n\n"
        f"At 200-bps costs the result was {selected_row.severe_recent_cagr:.2%}; a one-week overlay delay was "
        f"{delay1:.2%}; the worst issuer removal ({worst.company_name}) left {worst.recent_cagr:.2%}. "
        f"Bootstrap probabilities were {b4:.2%}/{b13:.2%} and rolling outperformance was {rolling_share:.2%}.\n\n"
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
