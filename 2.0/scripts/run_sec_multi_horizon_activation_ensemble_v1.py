#!/usr/bin/env python3
"""Test causal multi-horizon activation ensembles around the breadth challenger."""

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

CONFIG = ROOT / "config/sec_multi_horizon_activation_ensemble_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
CHALLENGER = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1/selected_path__50bps.csv"
OUTPUT = ROOT / "evidence/sec_multi_horizon_activation_ensemble_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activation_votes(signal_returns: pd.DataFrame, lookbacks: list[int], delay: int = 0) -> pd.DataFrame:
    """Each vote at t uses returns ending no later than t-1, then optional publication delay."""
    votes = {}
    for lookback in lookbacks:
        trend = dynamic.rolling_total(signal_returns, int(lookback))
        votes[f"vote_{int(lookback)}w"] = (
            (trend.cash_conversion > trend.leader) & (trend.cash_conversion > 0)
        ).shift(int(delay)).fillna(False).astype(bool)
    return pd.DataFrame(votes, index=signal_returns.index)


def ensemble_target(
    signal_returns: pd.DataFrame,
    breadth_state: pd.Series,
    lookbacks: list[int],
    threshold: int,
    mode: str,
    delay: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    votes = activation_votes(signal_returns, lookbacks, delay)
    count = votes.sum(axis=1)
    share = count / float(len(lookbacks))
    active = count >= int(threshold)
    high = breadth_state.reindex(votes.index).fillna(False).astype(bool)
    ceiling = pd.Series(np.where(high, 0.8, 0.5), index=votes.index)
    if mode == "binary":
        weight = ceiling.where(active, 0.0)
    elif mode == "proportional":
        weight = (ceiling * share).where(active, 0.0)
    elif mode == "confidence_blend":
        weight = (ceiling * (0.5 + 0.5 * share)).where(active, 0.0)
    else:
        raise ValueError(f"unknown allocation mode: {mode}")
    target = pd.DataFrame({"leader": 1.0 - weight, "cash_conversion": weight}, index=votes.index)
    panel = votes.copy()
    panel["vote_count"] = count
    panel["vote_share"] = share
    panel["active"] = active
    panel["breadth_high"] = high
    panel["cash_conversion_weight"] = weight
    return target, panel


def candidate_name(family: str, threshold: int, mode: str) -> str:
    return f"{family}__votes{int(threshold)}__{mode}"


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
    sleeves, sleeve_peaks = {}, {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        sleeves[(scenario, int(cost))], sleeve_peaks[(scenario, int(cost))] = capped.simulate_cash(
            weekly, stock_targets, scenario, float(cost), None, int(config["breadth"])
        )
    leaders = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"])
    }
    signal = pd.concat([
        leaders[("base", 50)].rename("leader"), sleeves[("base", 50)].net_return.rename("cash_conversion")
    ], axis=1).dropna()
    breadth_state = controller.regime_state(
        controller.breadth_dispersion_signals(weekly, int(config["signal_horizon_weeks"])),
        int(config["calibration_weeks"]), float(config["state_quantile"]), str(config["state_mode"]),
    )
    frozen = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date")
    challenger = pd.read_csv(CHALLENGER, parse_dates=["Date"]).set_index("Date")
    control_recent = recent_metric("control", "base", 50, frozen)
    control_full = next(r for r in base.metric_rows("control", "base", 50, frozen) if r["window"] == "full_recent")
    challenger_recent = recent_metric("challenger", "base", 50, challenger)

    paths, targets, panels, rows = {}, {}, {}, []
    for family, raw_lookbacks in config["lookback_families"].items():
        lookbacks = [int(value) for value in raw_lookbacks]
        for threshold in range(1, len(lookbacks) + 1):
            for mode in config["allocation_modes"]:
                name = candidate_name(family, threshold, str(mode))
                target, panel = ensemble_target(signal, breadth_state, lookbacks, threshold, str(mode))
                targets[name], panels[name] = target, panel
                current = controller.simulate_composite(
                    leaders[("base", 50)], sleeves[("base", 50)], target, 50.0
                )
                severe = controller.simulate_composite(
                    leaders[("base", 200)], sleeves[("base", 200)], target, 200.0
                )
                paths[(name, "base", 50)], paths[(name, "base", 200)] = current, severe
                recent = recent_metric(name, "base", 50, current)
                full = next(r for r in base.metric_rows(name, "base", 50, current) if r["window"] == "full_recent")
                severe_recent = recent_metric(name, "base", 200, severe)
                delay_values = {}
                for delay in config["falsification"]["activation_delays_weeks"]:
                    delayed_target, _ = ensemble_target(
                        signal, breadth_state, lookbacks, threshold, str(mode), int(delay)
                    )
                    delayed = controller.simulate_composite(
                        leaders[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0
                    )
                    delay_values[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed)["cagr"]
                annual_turnover = float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0)
                rows.append({
                    "candidate": name, "family": family, "lookbacks": "|".join(map(str, lookbacks)),
                    "lookback_count": len(lookbacks), "vote_threshold": threshold,
                    "allocation_mode": str(mode), "recent_cagr": recent["cagr"],
                    "recent_sharpe": recent["sharpe_zero_rf"], "recent_drawdown": recent["max_drawdown"],
                    "full_cagr": full["cagr"], "severe_recent_cagr": severe_recent["cagr"],
                    "delay1_recent_cagr": delay_values[1], "delay2_recent_cagr": delay_values[2],
                    "worst_current_delay_recent_cagr": min(recent["cagr"], delay_values[1], delay_values[2]),
                    "peak_total_stock_weight": float(target.cash_conversion.max() * sleeve_peaks[("base", 50)]),
                    "annual_one_way_turnover": annual_turnover,
                    "active_share": float(panel.active.mean()),
                })
    screen = pd.DataFrame(rows)
    control_name = candidate_name("single11_control", 1, "binary")
    control_matches = np.allclose(
        paths[(control_name, "base", 50)].net_return.reindex(challenger.index), challenger.net_return,
        rtol=0, atol=1e-12, equal_nan=True,
    )
    if not control_matches:
        raise RuntimeError("single 11-week binary control failed to reproduce the 112.93% challenger")
    gates = config["selection_gates"]
    screen["selection_gates"] = (
        (screen.candidate != control_name)
        & (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.delay1_recent_cagr > float(gates["minimum_delay_recent_cagr"]))
        & (screen.delay2_recent_cagr > float(gates["minimum_delay_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr > float(gates["minimum_severe_recent_cagr"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    eligible = screen[screen.selection_gates]
    selection_reason = "all return-preserving timing gates"
    pool = eligible
    if pool.empty:
        pool = screen[screen.candidate != control_name]
        selection_reason = "no candidate passed all timing gates; best worst-case diagnostic"
    selected_row = pool.assign(_rank=pool.worst_current_delay_recent_cagr.round(12)).sort_values(
        ["_rank", "recent_cagr", "full_cagr"], ascending=False
    ).iloc[0]
    selected = str(selected_row.candidate)
    family = str(selected_row.family)
    lookbacks = [int(v) for v in str(selected_row.lookbacks).split("|")]
    threshold = int(selected_row.vote_threshold)
    mode = str(selected_row.allocation_mode)

    # Complete cost and adverse paths with one target frozen from base/50-bps data.
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = controller.simulate_composite(
            leaders[(scenario, int(cost))], sleeves[(scenario, int(cost))], targets[selected], float(cost)
        )
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    panels[selected].rename_axis("Date").to_csv(OUTPUT / "selected_vote_panel.csv")
    choices.to_csv(OUTPUT / "unchanged_portfolio_choices.csv", index=False)

    # Persist complete delay evidence for the selected rule.
    delay_rows = []
    for delay in [0] + [int(v) for v in config["falsification"]["activation_delays_weeks"]]:
        delayed_target, _ = ensemble_target(signal, breadth_state, lookbacks, threshold, mode, delay)
        delayed_path = controller.simulate_composite(
            leaders[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0
        )
        delay_rows.extend(
            row for row in base.metric_rows(selected, f"delay_{delay}", 50, delayed_path)
            if row["window"] in {"trailing_1y", "full_recent", "ytd"}
        )
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

    # Exact issuer-removal audit recomputes every activation vote.
    cutoff = choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(choices.loc[choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        altered_choices = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], int(config["breadth"]))
        altered_sleeve, _ = capped.simulate_cash(
            weekly, base.build_targets(altered_choices, index), "base", 50.0, None, int(config["breadth"])
        )
        altered_signal = pd.concat([
            leaders[("base", 50)].rename("leader"), altered_sleeve.net_return.rename("cash_conversion")
        ], axis=1).dropna()
        altered_target, _ = ensemble_target(altered_signal, breadth_state, lookbacks, threshold, mode)
        path = controller.simulate_composite(leaders[("base", 50)], altered_sleeve, altered_target, 50.0)
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
    d1 = float(selected_row.delay1_recent_cagr)
    d2 = float(selected_row.delay2_recent_cagr)
    checks = {
        "single11_control_reproduces_challenger": bool(control_matches),
        "selection_gates_passed": bool(selected_row.selection_gates),
        "recent_cagr_at_least_110pct": float(selected_row.recent_cagr) >= 1.10,
        "both_activation_delays_beat_control": d1 > float(control_recent["cagr"]) and d2 > float(control_recent["cagr"]),
        "rolling_outperformance_at_least_50pct": rolling_share >= 0.5,
        "bootstrap_4w_at_least_95pct": b4 >= 0.95,
        "bootstrap_13w_at_least_95pct": b13 >= 0.95,
        "worst_loo_beats_control": float(worst.recent_cagr) > float(control_recent["cagr"]),
        "single_issuer_share_at_most_50pct": issuer_share is not None and issuer_share <= 0.5,
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    screen.sort_values(["worst_current_delay_recent_cagr", "recent_cagr"], ascending=False).to_csv(
        OUTPUT / "screening.csv", index=False
    )
    eligible.to_csv(OUTPUT / "eligible_candidates.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "eligible_candidate_count": int(len(eligible)),
        "selected_candidate": selected, "selection_reason": selection_reason, "family": family,
        "lookbacks_weeks": lookbacks, "vote_threshold": threshold, "allocation_mode": mode,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "delay1_recent_cagr": d1, "delay2_recent_cagr": d2,
        "worst_current_delay_recent_cagr": float(selected_row.worst_current_delay_recent_cagr),
        "challenger_recent_cagr": float(challenger_recent["cagr"]), "control_recent_cagr": float(control_recent["cagr"]),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "annual_one_way_turnover": float(selected_row.annual_one_way_turnover),
        "rolling_outperformance_share": rolling_share, "completed_rolling_windows": rolling_windows,
        "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13,
        "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr),
        "single_issuer_improvement_share": issuer_share, "checks": checks,
        "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_vote_panel": sha256(OUTPUT / "selected_vote_panel.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Multi-horizon activation ensemble v1\n\n"
        f"Tested {len(screen)} causal activation ensembles. The selected `{selected}` used "
        f"{lookbacks} week votes, threshold {threshold}, and `{mode}` sizing. It produced "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"One/two-week activation delays returned {d1:.2%}/{d2:.2%}.\n\n"
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%}. Rolling outperformance was "
        f"{rolling_share:.2%}; bootstrap probabilities were {b4:.2%}/{b13:.2%}; removing "
        f"{worst.company_name} left {worst.recent_cagr:.2%}.\n\n"
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. "
        f"No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
