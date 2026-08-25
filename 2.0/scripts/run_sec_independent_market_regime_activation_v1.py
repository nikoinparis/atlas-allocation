#!/usr/bin/env python3
"""Test independent causal market-regime activation around the breadth challenger."""

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

CONFIG = ROOT / "config/sec_independent_market_regime_activation_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
CHALLENGER = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1/selected_path__50bps.csv"
ETF_PRICES = ROOT / "data/vintages/20260814T220630Z-6807cd7f14ae66bb/payload/prices.csv"
VIX = ROOT / "data/regime_vintages/20260812T090851Z-5c6de663ac77/normalized_v2/vix_term_structure.csv"
OUTPUT = ROOT / "evidence/sec_independent_market_regime_activation_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weekly_etf_prices(index: pd.DatetimeIndex) -> pd.DataFrame:
    raw = pd.read_csv(
        ETF_PRICES, usecols=["observation_date", "ticker", "adjusted_close"],
        parse_dates=["observation_date"],
    )
    raw = raw[raw.ticker.isin(["SPY", "HYG", "LQD"])]
    pivot = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    return pivot.resample("W-FRI").last().reindex(index).ffill()


def regime_features(
    etfs: pd.DataFrame,
    issuer_weekly: pd.DataFrame,
    vix: pd.DataFrame,
    spec: dict,
) -> pd.DataFrame:
    """All features at t use market observations ending no later than t-1."""
    trend_weeks = int(spec["trend_weeks"])
    vol_weeks = int(spec["volatility_weeks"])
    credit_weeks = int(spec["credit_weeks"])
    breadth_weeks = int(spec["breadth_weeks"])
    calibration = int(spec["calibration_weeks"])
    spy_return = etfs.SPY.pct_change(trend_weeks, fill_method=None).shift(1)
    market_trend = spy_return > 0
    weekly_spy_return = etfs.SPY.pct_change(fill_method=None)
    realized_vol = weekly_spy_return.shift(1).rolling(vol_weeks, min_periods=vol_weeks).std(ddof=1) * np.sqrt(52)
    vol_threshold = realized_vol.rolling(calibration, min_periods=calibration).median().shift(1)
    low_volatility = realized_vol < vol_threshold
    hyg_return = etfs.HYG.pct_change(credit_weeks, fill_method=None).shift(1)
    lqd_return = etfs.LQD.pct_change(credit_weeks, fill_method=None).shift(1)
    credit_strong = (hyg_return > lqd_return) & (hyg_return > 0)
    breadth_panel = controller.breadth_dispersion_signals(issuer_weekly, breadth_weeks)
    breadth_threshold = breadth_panel.breadth.rolling(
        calibration, min_periods=calibration
    ).median().shift(1)
    breadth_strong = breadth_panel.breadth > breadth_threshold
    aligned_vix = vix.reindex(etfs.index).ffill()
    vix_contango = aligned_vix.contango.shift(1).fillna(0).astype(float) > 0
    valid = pd.DataFrame({
        "market_trend": market_trend,
        "low_volatility": low_volatility,
        "credit_strong": credit_strong,
        "vix_contango": vix_contango,
        "breadth_strong": breadth_strong,
    }, index=etfs.index).fillna(False).astype(bool)
    valid["risk_on_score"] = valid.sum(axis=1)
    return valid


def regime_target(
    base_active: pd.Series,
    features: pd.DataFrame,
    breadth_high: pd.Series,
    threshold: int,
    mode: str,
    delay: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    delayed_features = features[[
        "market_trend", "low_volatility", "credit_strong", "vix_contango", "breadth_strong"
    ]].shift(int(delay)).fillna(False).astype(bool)
    score = delayed_features.sum(axis=1)
    market_active = score >= int(threshold)
    base_state = base_active.reindex(features.index).shift(int(delay)).fillna(False).astype(bool)
    if mode == "market_only":
        active = market_active
    elif mode == "confirm":
        active = base_state & market_active
    elif mode == "bridge1":
        active = base_state | (base_state.shift(1).fillna(False) & market_active)
    elif mode == "bridge2":
        recent_base = base_state | base_state.shift(1).fillna(False) | base_state.shift(2).fillna(False)
        active = base_state | (recent_base & market_active)
    elif mode == "union":
        active = base_state | market_active
    else:
        raise ValueError(f"unknown activation mode: {mode}")
    high_state = breadth_high.reindex(features.index).shift(int(delay)).fillna(False).astype(bool)
    weight = pd.Series(np.where(high_state, 0.8, 0.5), index=features.index).where(active, 0.0)
    target = pd.DataFrame({"leader": 1.0 - weight, "cash_conversion": weight}, index=features.index)
    panel = delayed_features.copy()
    panel["risk_on_score"] = score
    panel["market_active"] = market_active
    panel["base_active"] = base_state
    panel["active"] = active
    panel["breadth_high_allocation"] = high_state
    panel["cash_conversion_weight"] = weight
    return target, panel


def candidate_name(family: str, threshold: int, mode: str) -> str:
    return f"{family}__score{int(threshold)}__{mode}"


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
    issuer_weekly = pd.DataFrame(series, index=index)
    etfs = weekly_etf_prices(index)
    vix = pd.read_csv(VIX, parse_dates=["Date"]).set_index("Date")
    feature_panels = {
        name: regime_features(etfs, issuer_weekly, vix, spec)
        for name, spec in config["regime_families"].items()
    }
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
    signal = pd.concat([
        leaders[("base", 50)].rename("leader"), sleeves[("base", 50)].net_return.rename("cash_conversion")
    ], axis=1).dropna()
    base_target = capped.overlay_target(
        signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), 0.5
    )
    base_active = base_target.cash_conversion > 0
    breadth_high = controller.regime_state(
        controller.breadth_dispersion_signals(
            issuer_weekly, int(config["breadth_controller_horizon_weeks"])
        ), int(config["breadth_controller_calibration_weeks"]),
        float(config["breadth_controller_quantile"]), "breadth_high",
    )
    frozen = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date")
    challenger = pd.read_csv(CHALLENGER, parse_dates=["Date"]).set_index("Date")
    control_recent = recent_metric("control", "base", 50, frozen)
    challenger_recent = recent_metric("challenger", "base", 50, challenger)

    paths, targets, panels, rows = {}, {}, {}, []
    for family, features in feature_panels.items():
        for threshold in range(1, 6):
            for mode in config["activation_modes"]:
                name = candidate_name(family, threshold, str(mode))
                target, panel = regime_target(base_active, features, breadth_high, threshold, str(mode))
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
                for delay in config["falsification"]["signal_delays_weeks"]:
                    delayed_target, _ = regime_target(
                        base_active, features, breadth_high, threshold, str(mode), int(delay)
                    )
                    delayed_path = controller.simulate_composite(
                        leaders[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0
                    )
                    delay_values[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed_path)["cagr"]
                rows.append({
                    "candidate": name, "family": family, "risk_on_threshold": threshold,
                    "activation_mode": str(mode), "recent_cagr": recent["cagr"],
                    "recent_sharpe": recent["sharpe_zero_rf"], "recent_drawdown": recent["max_drawdown"],
                    "full_cagr": full["cagr"], "severe_recent_cagr": severe_recent["cagr"],
                    "delay1_recent_cagr": delay_values[1], "delay2_recent_cagr": delay_values[2],
                    "worst_current_delay_recent_cagr": min(recent["cagr"], delay_values[1], delay_values[2]),
                    "peak_total_stock_weight": float(target.cash_conversion.max() * sleeve_peaks[("base", 50)]),
                    "annual_one_way_turnover": float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0),
                    "active_share": float(panel.active.mean()),
                })
    screen = pd.DataFrame(rows)
    gates = config["selection_gates"]
    screen["selection_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
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
        pool = screen
        selection_reason = "no candidate passed all timing gates; best worst-case diagnostic"
    selected_row = pool.assign(_rank=pool.worst_current_delay_recent_cagr.round(12)).sort_values(
        ["_rank", "recent_cagr", "full_cagr"], ascending=False
    ).iloc[0]
    selected = str(selected_row.candidate)
    family = str(selected_row.family)
    threshold = int(selected_row.risk_on_threshold)
    mode = str(selected_row.activation_mode)
    features = feature_panels[family]

    return_row = screen.sort_values(["recent_cagr", "full_cagr"], ascending=False).iloc[0]
    return_leader = str(return_row.candidate)
    return_family = str(return_row.family)
    return_threshold = int(return_row.risk_on_threshold)
    return_mode = str(return_row.activation_mode)

    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = controller.simulate_composite(
            leaders[(scenario, int(cost))], sleeves[(scenario, int(cost))], targets[selected], float(cost)
        )
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    panels[selected].rename_axis("Date").to_csv(OUTPUT / "selected_regime_panel.csv")
    choices.to_csv(OUTPUT / "unchanged_portfolio_choices.csv", index=False)
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(return_leader, scenario, int(cost))] = controller.simulate_composite(
            leaders[(scenario, int(cost))], sleeves[(scenario, int(cost))], targets[return_leader], float(cost)
        )
    for cost in config["cost_bps"]:
        paths[(return_leader, "base", int(cost))].rename_axis("Date").to_csv(
            OUTPUT / f"return_leader_path__{cost}bps.csv"
        )
    targets[return_leader].rename_axis("Date").to_csv(OUTPUT / "return_leader_target_weights.csv")
    panels[return_leader].rename_axis("Date").to_csv(OUTPUT / "return_leader_regime_panel.csv")

    delay_rows = []
    for delay in [0] + [int(v) for v in config["falsification"]["signal_delays_weeks"]]:
        delayed_target, _ = regime_target(base_active, features, breadth_high, threshold, mode, delay)
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
        altered_base = capped.overlay_target(
            altered_signal.index, altered_signal.leader, altered_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5,
        ).cash_conversion > 0
        altered_target, _ = regime_target(altered_base, features, breadth_high, threshold, mode)
        path = controller.simulate_composite(leaders[("base", 50)], altered_sleeve, altered_target, 50.0)
        metric = recent_metric(selected, "loo", 50, path)
        company = choices.loc[choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
                         "cagr_change": metric["cagr"] - float(selected_row.recent_cagr)})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -float(worst.cagr_change)) / improvement) if improvement > 0 else None

    return_loo_rows = []
    return_features = feature_panels[return_family]
    for cik in recent_ciks:
        altered_choices = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], int(config["breadth"]))
        altered_sleeve, _ = capped.simulate_cash(
            issuer_weekly, base.build_targets(altered_choices, index), "base", 50.0, None, int(config["breadth"])
        )
        altered_signal = pd.concat([
            leaders[("base", 50)].rename("leader"), altered_sleeve.net_return.rename("cash_conversion")
        ], axis=1).dropna()
        altered_base = capped.overlay_target(
            altered_signal.index, altered_signal.leader, altered_signal.cash_conversion,
            int(config["overlay_lookback_weeks"]), 0.5,
        ).cash_conversion > 0
        altered_target, _ = regime_target(
            altered_base, return_features, breadth_high, return_threshold, return_mode
        )
        path = controller.simulate_composite(leaders[("base", 50)], altered_sleeve, altered_target, 50.0)
        metric = recent_metric(return_leader, "return_loo", 50, path)
        company = choices.loc[choices.cik10 == cik, "company_name"].iloc[-1]
        return_loo_rows.append({
            "cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
            "cagr_change": metric["cagr"] - float(return_row.recent_cagr),
        })
    return_loo = pd.DataFrame(return_loo_rows).sort_values("cagr_change")
    return_worst = return_loo.iloc[0]
    return_improvement = float(return_row.recent_cagr - control_recent["cagr"])
    return_issuer_share = (
        float(max(0.0, -float(return_worst.cagr_change)) / return_improvement)
        if return_improvement > 0 else None
    )
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    d1, d2 = float(selected_row.delay1_recent_cagr), float(selected_row.delay2_recent_cagr)
    checks = {
        "selection_gates_passed": bool(selected_row.selection_gates),
        "recent_cagr_at_least_110pct": float(selected_row.recent_cagr) >= 1.10,
        "both_signal_delays_beat_control": d1 > float(control_recent["cagr"]) and d2 > float(control_recent["cagr"]),
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
    return_loo.to_csv(OUTPUT / "return_leader_leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "eligible_candidate_count": int(len(eligible)),
        "selected_candidate": selected, "selection_reason": selection_reason,
        "regime_family": family, "risk_on_threshold": threshold, "activation_mode": mode,
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
        "return_leader": {
            "candidate": return_leader,
            "regime_family": return_family,
            "risk_on_threshold": return_threshold,
            "activation_mode": return_mode,
            "recent_cagr": float(return_row.recent_cagr),
            "recent_sharpe": float(return_row.recent_sharpe),
            "recent_drawdown": float(return_row.recent_drawdown),
            "full_cagr": float(return_row.full_cagr),
            "severe_recent_cagr": float(return_row.severe_recent_cagr),
            "delay1_recent_cagr": float(return_row.delay1_recent_cagr),
            "delay2_recent_cagr": float(return_row.delay2_recent_cagr),
            "worst_loo_company": str(return_worst.company_name),
            "worst_loo_recent_cagr": float(return_worst.recent_cagr),
            "single_issuer_improvement_share": return_issuer_share,
        },
        "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_regime_panel": sha256(OUTPUT / "selected_regime_panel.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
            "return_leader_path_50bps": sha256(OUTPUT / "return_leader_path__50bps.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Independent market-regime activation v1\n\n"
        f"Tested {len(screen)} causal market-regime controllers. The selected `{selected}` produced "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"One/two-week delayed signals returned {d1:.2%}/{d2:.2%}.\n\n"
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%}. Rolling outperformance was "
        f"{rolling_share:.2%}; bootstrap probabilities were {b4:.2%}/{b13:.2%}; removing "
        f"{worst.company_name} left {worst.recent_cagr:.2%}.\n\n"
        f"The separate return leader `{return_leader}` reached {return_row.recent_cagr:.2%} current CAGR, "
        f"but only {return_row.delay1_recent_cagr:.2%} after a one-week delay and "
        f"{return_row.severe_recent_cagr:.2%} at 200-bps costs. Removing {return_worst.company_name} "
        f"left {return_worst.recent_cagr:.2%}.\n\n"
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. "
        f"No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
