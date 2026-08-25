#!/usr/bin/env python3
"""Attribute and tranche the incremental fast-regime exposure above the 112.93% base."""

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
import run_sec_independent_market_regime_activation_v1 as regime
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_regime_increment_tranching_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
BASE_EVIDENCE = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1"
SPIKE_EVIDENCE = ROOT / "evidence/sec_independent_market_regime_activation_v1"
OUTPUT = ROOT / "evidence/sec_regime_increment_tranching_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def smooth_increment(extra: pd.Series, tranches: int, policy: str) -> pd.Series:
    extra = extra.fillna(0.0).clip(lower=0.0)
    n = int(tranches)
    if n <= 1:
        return extra.copy()
    if policy == "symmetric_equal":
        return sum((extra.shift(lag).fillna(0.0) for lag in range(n)), start=pd.Series(0.0, index=extra.index)) / n
    if policy == "frontloaded":
        weights = np.arange(n, 0, -1, dtype=float)
        weights /= weights.sum()
        return sum(
            (float(weight) * extra.shift(lag).fillna(0.0) for lag, weight in enumerate(weights)),
            start=pd.Series(0.0, index=extra.index),
        )
    if policy == "entry_ramp":
        run = 0
        values = []
        for value in extra:
            if value > 0:
                run += 1
                values.append(float(value) * min(run, n) / n)
            else:
                run = 0
                values.append(0.0)
        return pd.Series(values, index=extra.index)
    if policy == "exit_decay":
        remaining = 0
        last = 0.0
        values = []
        for value in extra:
            if value > 0:
                last = float(value)
                remaining = n - 1
                values.append(last)
            elif remaining > 0:
                values.append(last * remaining / n)
                remaining -= 1
            else:
                values.append(0.0)
        return pd.Series(values, index=extra.index)
    raise ValueError(f"unknown tranche policy: {policy}")


def tranche_target(
    base_target: pd.DataFrame,
    raw_increment: pd.Series,
    multiplier: float,
    tranches: int,
    policy: str,
    maximum: float = 0.8,
    delay: int = 0,
) -> tuple[pd.DataFrame, pd.Series]:
    delayed = raw_increment.shift(int(delay)).fillna(0.0)
    deployed = float(multiplier) * smooth_increment(delayed, int(tranches), str(policy))
    cash = (base_target.cash_conversion + deployed).clip(lower=0.0, upper=float(maximum))
    target = pd.DataFrame({"leader": 1.0 - cash, "cash_conversion": cash}, index=base_target.index)
    return target, deployed


def candidate_name(multiplier: float, tranches: int, policy: str) -> str:
    return f"inc{int(round(float(multiplier) * 100)):03d}__tranches{int(tranches)}__{policy}"


def recent_metric(name: str, scenario: str, cost: int, path: pd.DataFrame) -> dict:
    return next(row for row in base.metric_rows(name, scenario, cost, path) if row["window"] == "trailing_1y")


def episode_attribution(
    base_path: pd.DataFrame,
    spike_path: pd.DataFrame,
    base_target: pd.DataFrame,
    spike_target: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = pd.concat([
        base_path.net_return.rename("base_return"), spike_path.net_return.rename("spike_return"),
        base_target.cash_conversion.rename("base_cash_weight"),
        spike_target.cash_conversion.rename("spike_cash_weight"),
    ], axis=1).dropna()
    joined["increment_weight"] = (joined.spike_cash_weight - joined.base_cash_weight).clip(lower=0.0)
    joined["weekly_excess_return"] = joined.spike_return - joined.base_return
    joined["active_increment"] = joined.increment_weight > 1e-12
    joined["episode"] = (joined.active_increment & ~joined.active_increment.shift(1).fillna(False)).cumsum()
    active = joined[joined.active_increment].copy()
    episode_rows = []
    for episode, group in active.groupby("episode"):
        episode_rows.append({
            "episode": int(episode), "start": group.index.min(), "end": group.index.max(),
            "weeks": int(len(group)), "maximum_increment_weight": float(group.increment_weight.max()),
            "base_compound_return": float((1 + group.base_return).prod() - 1),
            "spike_compound_return": float((1 + group.spike_return).prod() - 1),
            "sum_weekly_excess_return": float(group.weekly_excess_return.sum()),
        })
    return joined, pd.DataFrame(episode_rows)


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
    issuer_weekly = pd.DataFrame(series, index=index)
    stock_targets = base.build_targets(choices, index)
    sleeves, sleeve_peaks = {}, {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        sleeves[(scenario, int(cost))], sleeve_peaks[(scenario, int(cost))] = capped.simulate_cash(
            issuer_weekly, stock_targets, scenario, float(cost), None, int(config["breadth"])
        )
    leaders = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"])
    }
    base_target = pd.read_csv(BASE_EVIDENCE / "selected_target_weights.csv", parse_dates=["Date"]).set_index("Date")
    spike_target = pd.read_csv(SPIKE_EVIDENCE / "return_leader_target_weights.csv", parse_dates=["Date"]).set_index("Date")
    raw_increment = (spike_target.cash_conversion - base_target.cash_conversion).clip(lower=0.0)
    base_path = pd.read_csv(BASE_EVIDENCE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    spike_path = pd.read_csv(SPIKE_EVIDENCE / "return_leader_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    frozen = pd.read_csv(FROZEN, parse_dates=["Date"]).set_index("Date")
    base_recent = recent_metric("base", "base", 50, base_path)
    frozen_recent = recent_metric("frozen", "base", 50, frozen)
    event_detail, episodes = episode_attribution(base_path, spike_path, base_target, spike_target)
    event_detail.to_csv(OUTPUT / "increment_week_attribution.csv", index_label="Date")
    episodes.to_csv(OUTPUT / "increment_episode_attribution.csv", index=False)

    specifications = []
    for multiplier in config["increment_multipliers"]:
        specifications.append((float(multiplier), 1, "symmetric_equal"))
        for tranches in [int(v) for v in config["tranche_counts"] if int(v) > 1]:
            for policy in config["tranche_policies"]:
                specifications.append((float(multiplier), tranches, str(policy)))
    rows, paths, targets, deployed_cache = [], {}, {}, {}
    for multiplier, tranches, policy in specifications:
        name = candidate_name(multiplier, tranches, policy)
        target, deployed = tranche_target(
            base_target, raw_increment, multiplier, tranches, policy,
            float(config["maximum_cash_sleeve_weight"]),
        )
        targets[name], deployed_cache[name] = target, deployed
        current = controller.simulate_composite(leaders[("base", 50)], sleeves[("base", 50)], target, 50.0)
        severe = controller.simulate_composite(leaders[("base", 200)], sleeves[("base", 200)], target, 200.0)
        paths[(name, "base", 50)], paths[(name, "base", 200)] = current, severe
        recent = recent_metric(name, "base", 50, current)
        full = next(r for r in base.metric_rows(name, "base", 50, current) if r["window"] == "full_recent")
        severe_recent = recent_metric(name, "base", 200, severe)
        delay_values = {}
        for delay in config["falsification"]["increment_delays_weeks"]:
            delayed_target, _ = tranche_target(
                base_target, raw_increment, multiplier, tranches, policy,
                float(config["maximum_cash_sleeve_weight"]), int(delay),
            )
            delayed_path = controller.simulate_composite(
                leaders[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0
            )
            delay_values[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed_path)["cagr"]
        rows.append({
            "candidate": name, "increment_multiplier": multiplier, "tranches": tranches,
            "policy": policy, "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe_zero_rf"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"],
            "severe_recent_cagr": severe_recent["cagr"], "delay1_recent_cagr": delay_values[1],
            "delay2_recent_cagr": delay_values[2],
            "worst_current_delay_recent_cagr": min(recent["cagr"], delay_values[1], delay_values[2]),
            "peak_total_stock_weight": float(target.cash_conversion.max() * sleeve_peaks[("base", 50)]),
            "annual_one_way_turnover": float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0),
            "increment_active_share": float((deployed > 1e-12).mean()),
        })
    screen = pd.DataFrame(rows)
    direct_name = candidate_name(1.0, 1, "symmetric_equal")
    direct_matches = np.allclose(
        paths[(direct_name, "base", 50)].net_return.reindex(spike_path.index), spike_path.net_return,
        rtol=0, atol=1e-12, equal_nan=True,
    )
    if not direct_matches:
        raise RuntimeError("direct 100% increment failed to reproduce the 119.33% spike")
    gates = config["selection_gates"]
    screen["selection_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.delay1_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.delay2_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr > float(gates["minimum_severe_recent_cagr"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    eligible = screen[screen.selection_gates]
    selection_reason = "all return-preserving tranche gates"
    pool = eligible
    if pool.empty:
        pool = screen
        selection_reason = "no candidate passed all tranche gates; best worst-case diagnostic"
    selected_row = pool.assign(_rank=pool.worst_current_delay_recent_cagr.round(12)).sort_values(
        ["_rank", "recent_cagr", "full_cagr"], ascending=False
    ).iloc[0]
    selected = str(selected_row.candidate)
    multiplier = float(selected_row.increment_multiplier)
    tranches = int(selected_row.tranches)
    policy = str(selected_row.policy)

    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = controller.simulate_composite(
            leaders[(scenario, int(cost))], sleeves[(scenario, int(cost))], targets[selected], float(cost)
        )
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    pd.DataFrame({"raw_increment": raw_increment, "deployed_increment": deployed_cache[selected]}).to_csv(
        OUTPUT / "selected_increment_panel.csv", index_label="Date"
    )
    choices.to_csv(OUTPUT / "unchanged_portfolio_choices.csv", index=False)

    delay_rows = []
    for delay in [0] + [int(v) for v in config["falsification"]["increment_delays_weeks"]]:
        delayed_target, _ = tranche_target(
            base_target, raw_increment, multiplier, tranches, policy,
            float(config["maximum_cash_sleeve_weight"]), delay,
        )
        delayed_path = controller.simulate_composite(
            leaders[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0
        )
        delay_rows.extend(
            row for row in base.metric_rows(selected, f"delay_{delay}", 50, delayed_path)
            if row["window"] in {"trailing_1y", "full_recent", "ytd"}
        )
    delays = pd.DataFrame(delay_rows)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), base_path.net_return.rename("control")], axis=1).dropna()
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

    etfs = regime.weekly_etf_prices(index)
    vix = pd.read_csv(regime.VIX, parse_dates=["Date"]).set_index("Date")
    fast_features = regime.regime_features(
        etfs, issuer_weekly, vix,
        {"trend_weeks": 13, "volatility_weeks": 8, "credit_weeks": 8,
         "breadth_weeks": 13, "calibration_weeks": 26},
    )
    breadth_signals = controller.breadth_dispersion_signals(issuer_weekly, 26)
    breadth_high = controller.regime_state(breadth_signals, 26, 0.4, "breadth_high")
    cutoff = choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(choices.loc[choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        altered_choices = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], int(config["breadth"]))
        altered_sleeve, _ = capped.simulate_cash(
            issuer_weekly, base.build_targets(altered_choices, index), "base", 50.0, None, int(config["breadth"])
        )
        altered_signal = pd.concat([
            leaders[("base", 50)].rename("leader"), altered_sleeve.net_return.rename("cash_conversion")
        ], axis=1).dropna()
        altered_overlay = capped.overlay_target(
            altered_signal.index, altered_signal.leader, altered_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5,
        )
        altered_base_target, _ = controller.controller_target(
            altered_overlay, breadth_signals, 26, 0.4, "breadth_high", 0.5, 0.8
        )
        altered_spike_target, _ = regime.regime_target(
            altered_overlay.cash_conversion > 0, fast_features, breadth_high, 5, "union"
        )
        altered_increment = (
            altered_spike_target.cash_conversion - altered_base_target.cash_conversion
        ).clip(lower=0.0)
        altered_target, _ = tranche_target(
            altered_base_target, altered_increment, multiplier, tranches, policy,
            float(config["maximum_cash_sleeve_weight"]),
        )
        path = controller.simulate_composite(leaders[("base", 50)], altered_sleeve, altered_target, 50.0)
        metric = recent_metric(selected, "loo", 50, path)
        company = choices.loc[choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
                         "cagr_change": metric["cagr"] - float(selected_row.recent_cagr)})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - base_recent["cagr"])
    issuer_share = float(max(0.0, -float(worst.cagr_change)) / improvement) if improvement > 0 else None
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    d1, d2 = float(selected_row.delay1_recent_cagr), float(selected_row.delay2_recent_cagr)
    checks = {
        "direct_increment_reproduces_119pct_spike": bool(direct_matches),
        "selection_gates_passed": bool(selected_row.selection_gates),
        "recent_cagr_at_least_115pct": float(selected_row.recent_cagr) >= 1.15,
        "both_increment_delays_at_least_base": d1 >= float(base_recent["cagr"]) and d2 >= float(base_recent["cagr"]),
        "rolling_outperformance_at_least_50pct": rolling_share >= 0.5,
        "bootstrap_4w_at_least_95pct": b4 >= 0.95,
        "bootstrap_13w_at_least_95pct": b13 >= 0.95,
        "worst_loo_beats_frozen": float(worst.recent_cagr) > float(frozen_recent["cagr"]),
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
        "increment_episodes": int(len(episodes)), "increment_active_weeks": int(event_detail.active_increment.sum()),
        "selected_candidate": selected, "selection_reason": selection_reason,
        "increment_multiplier": multiplier, "tranches": tranches, "tranche_policy": policy,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "delay1_recent_cagr": d1, "delay2_recent_cagr": d2,
        "worst_current_delay_recent_cagr": float(selected_row.worst_current_delay_recent_cagr),
        "base_recent_cagr": float(base_recent["cagr"]), "spike_recent_cagr": float(recent_metric("spike", "base", 50, spike_path)["cagr"]),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "annual_one_way_turnover": float(selected_row.annual_one_way_turnover),
        "rolling_outperformance_share_vs_base": rolling_share, "completed_rolling_windows": rolling_windows,
        "bootstrap_4w_probability_positive_vs_base": b4, "bootstrap_13w_probability_positive_vs_base": b13,
        "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr),
        "single_issuer_increment_improvement_share": issuer_share, "checks": checks,
        "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_increment_panel": sha256(OUTPUT / "selected_increment_panel.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
            "episode_attribution": sha256(OUTPUT / "increment_episode_attribution.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Regime increment tranching v1\n\n"
        f"Attributed {int(event_detail.active_increment.sum())} incremental weeks across {len(episodes)} episodes and "
        f"tested {len(screen)} ticker-agnostic strength/tranching variants above the untouched 112.93% base. "
        f"The selected `{selected}` produced {selected_row.recent_cagr:.2%} recent CAGR, "
        f"{selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and "
        f"{selected_row.full_cagr:.2%} full CAGR. Increment-only one/two-week delays returned {d1:.2%}/{d2:.2%}.\n\n"
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%}. Versus the 112.93% base, rolling "
        f"outperformance was {rolling_share:.2%} and bootstrap probabilities were {b4:.2%}/{b13:.2%}. "
        f"Removing {worst.company_name} left {worst.recent_cagr:.2%}.\n\n"
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. "
        f"No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
