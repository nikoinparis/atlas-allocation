#!/usr/bin/env python3
"""Test generic quarterly-cohort diversification around the 119.22% challenger."""

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
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner
import run_sec_breadth_dispersion_allocation_controller_v1 as controller
import run_sec_independent_market_regime_activation_v1 as regime
import run_sec_regime_increment_tranching_v1 as tranche
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_cohort_diversified_regime_tranche_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
INCUMBENT_CHALLENGER = ROOT / "evidence/sec_regime_increment_tranching_v1/selected_path__50bps.csv"
OUTPUT = ROOT / "evidence/sec_cohort_diversified_regime_tranche_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weighted_cohort_targets(
    choices: pd.DataFrame,
    index: pd.DatetimeIndex,
    cohort_weights: list[float],
) -> dict[pd.Timestamp, dict[str, float]]:
    cohorts = [(pd.Timestamp(decision), frame.sort_values("cik10")) for decision, frame in choices.groupby("decision_at", sort=True)]
    targets = {}
    for position, (decision, _) in enumerate(cohorts):
        available_cohorts = []
        available_weights = []
        for lag, raw_weight in enumerate(cohort_weights):
            if position - lag >= 0:
                available_cohorts.append(cohorts[position - lag][1])
                available_weights.append(float(raw_weight))
        total_weight = sum(available_weights)
        if total_weight <= 0:
            continue
        combined = {}
        for frame, raw_weight in zip(available_cohorts, available_weights):
            cohort_weight = raw_weight / total_weight
            per_name = cohort_weight / len(frame)
            for cik in frame.cik10:
                combined[str(cik)] = combined.get(str(cik), 0.0) + per_name
        later = index[index > decision.tz_localize(None)]
        if len(later):
            targets[later[0]] = combined
    return targets


def simulate_weighted_cash(
    prices: pd.DataFrame,
    targets: dict[pd.Timestamp, dict[str, float]],
    scenario: str,
    cost_bps: float,
) -> tuple[pd.DataFrame, float]:
    positions = {"cash::USD": 1.0}
    rows = []
    peak_weight = 0.0
    for offset, date in enumerate(prices.index[:-1]):
        total_before = sum(positions.values())
        turnover = 0.0
        adverse_loss = 0.0
        if date in targets:
            intended = targets[date]
            current = {key: value / total_before for key, value in positions.items()} if total_before else {"cash::USD": 1.0}
            available = {cik: weight for cik, weight in intended.items() if cik in prices and pd.notna(prices.at[date, cik])}
            missing_weight = sum(weight for cik, weight in intended.items() if cik not in available)
            target = dict(available)
            if scenario == "base" and missing_weight > 0:
                target["cash::USD"] = missing_weight
            comparison = set(current) | set(target) | set(intended)
            turnover = 0.5 * sum(abs(target.get(key, intended.get(key, 0.0) if scenario == "adverse" else 0.0) - current.get(key, 0.0)) for key in comparison)
            cost = total_before * turnover * float(cost_bps) / 10000.0
            deployable = total_before - cost
            positions = {key: deployable * weight for key, weight in target.items() if weight > 0}
            if scenario == "adverse":
                adverse_loss = deployable * missing_weight
        invested = sum(positions.values())
        if invested > 0:
            for asset, value in positions.items():
                if asset != "cash::USD":
                    peak_weight = max(peak_weight, value / invested)
        next_date = prices.index[offset + 1]
        next_positions = {}
        transition_loss = 0.0
        for asset, value in positions.items():
            if asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
                continue
            start, finish = prices.at[date, asset], prices.at[next_date, asset]
            if pd.notna(start) and pd.notna(finish) and float(start) != 0:
                next_positions[asset] = value * float(finish) / float(start)
            elif scenario == "base":
                next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
            else:
                transition_loss += value
        positions = next_positions
        total_after = sum(positions.values())
        net_return = total_after / total_before - 1.0 if total_before else 0.0
        rows.append({
            "Date": date, "gross_return": net_return + turnover * float(cost_bps) / 10000.0,
            "net_return": net_return, "turnover": turnover,
            "cost": turnover * float(cost_bps) / 10000.0,
            "adverse_loss": (adverse_loss + transition_loss) / total_before if total_before else 0.0,
            "wealth": total_after,
        })
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1.0
    return path, peak_weight


def strategy_target(
    leader: pd.Series,
    sleeve: pd.DataFrame,
    breadth_signals: pd.DataFrame,
    breadth_high: pd.Series,
    fast_features: pd.DataFrame,
    overlay_lookback: int,
    delay: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    signal = pd.concat([leader.rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    overlay = regime.capped.overlay_target(
        signal.index, signal.leader, signal.cash_conversion, int(overlay_lookback), 0.5
    )
    base_target, _ = controller.controller_target(
        overlay, breadth_signals, 26, 0.4, "breadth_high", 0.5, 0.8
    )
    spike_target, _ = regime.regime_target(
        overlay.cash_conversion > 0, fast_features, breadth_high, 5, "union"
    )
    raw_increment = (spike_target.cash_conversion - base_target.cash_conversion).clip(lower=0.0)
    target, deployed = tranche.tranche_target(base_target, raw_increment, 1.0, 4, "symmetric_equal", 0.8, delay)
    panel = pd.DataFrame({
        "base_cash_weight": base_target.cash_conversion,
        "raw_increment": raw_increment,
        "deployed_increment": deployed,
        "final_cash_weight": target.cash_conversion,
    })
    return target, panel


def recent_metric(name: str, scenario: str, cost: int, path: pd.DataFrame) -> dict:
    return next(row for row in base.metric_rows(name, scenario, cost, path) if row["window"] == "trailing_1y")


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
    issuer_weekly = pd.DataFrame(series, index=index)
    leaders = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"])
    }
    breadth_signals = controller.breadth_dispersion_signals(issuer_weekly, 26)
    breadth_high = controller.regime_state(breadth_signals, 26, 0.4, "breadth_high")
    etfs = regime.weekly_etf_prices(index)
    vix = pd.read_csv(regime.VIX, parse_dates=["Date"]).set_index("Date")
    fast_features = regime.regime_features(
        etfs, issuer_weekly, vix,
        {"trend_weeks": 13, "volatility_weeks": 8, "credit_weeks": 8,
         "breadth_weeks": 13, "calibration_weeks": 26},
    )
    incumbent = pd.read_csv(INCUMBENT_CHALLENGER, parse_dates=["Date"]).set_index("Date")
    frozen = pd.read_csv(FROZEN, parse_dates=["Date"]).set_index("Date")
    incumbent_recent = recent_metric("incumbent", "base", 50, incumbent)
    frozen_recent = recent_metric("frozen", "base", 50, frozen)

    constructions = {item["name"]: item for item in config["constructions"]}
    choices_cache, weighted_targets_cache, sleeves, peaks = {}, {}, {}, {}
    for name, spec in constructions.items():
        choices = breadth_runner.make_choices(cash_scores, int(spec["breadth"]))
        choices_cache[name] = choices
        weighted_targets_cache[name] = weighted_cohort_targets(choices, index, list(spec["cohort_weights"]))
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeves[(name, scenario, int(cost))], peaks[(name, scenario, int(cost))] = simulate_weighted_cash(
                issuer_weekly, weighted_targets_cache[name], scenario, float(cost)
            )

    rows, paths, strategy_targets, panels = [], {}, {}, {}
    for name, spec in constructions.items():
        target, panel = strategy_target(
            leaders[("base", 50)], sleeves[(name, "base", 50)], breadth_signals,
            breadth_high, fast_features, int(config["overlay_lookback_weeks"]),
        )
        strategy_targets[name], panels[name] = target, panel
        current = controller.simulate_composite(leaders[("base", 50)], sleeves[(name, "base", 50)], target, 50.0)
        severe = controller.simulate_composite(leaders[("base", 200)], sleeves[(name, "base", 200)], target, 200.0)
        paths[(name, "base", 50)], paths[(name, "base", 200)] = current, severe
        recent = recent_metric(name, "base", 50, current)
        full = next(r for r in base.metric_rows(name, "base", 50, current) if r["window"] == "full_recent")
        severe_recent = recent_metric(name, "base", 200, severe)
        delay_values = {}
        for delay in config["falsification"]["increment_delays_weeks"]:
            delayed_target, _ = strategy_target(
                leaders[("base", 50)], sleeves[(name, "base", 50)], breadth_signals,
                breadth_high, fast_features, int(config["overlay_lookback_weeks"]), int(delay),
            )
            delayed_path = controller.simulate_composite(
                leaders[("base", 50)], sleeves[(name, "base", 50)], delayed_target, 50.0
            )
            delay_values[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed_path)["cagr"]
        rows.append({
            "candidate": name, "breadth": int(spec["breadth"]),
            "cohort_weights": "|".join(str(v) for v in spec["cohort_weights"]),
            "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe_zero_rf"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"],
            "severe_recent_cagr": severe_recent["cagr"], "delay1_recent_cagr": delay_values[1],
            "delay2_recent_cagr": delay_values[2],
            "worst_current_delay_recent_cagr": min(recent["cagr"], delay_values[1], delay_values[2]),
            "peak_total_stock_weight": float(target.cash_conversion.max() * peaks[(name, "base", 50)]),
            "annual_one_way_turnover": float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0),
            "latest_distinct_holdings": int(len(weighted_targets_cache[name][max(weighted_targets_cache[name])])),
        })
    screen = pd.DataFrame(rows)
    control_name = "top20_current_control"
    control_matches = np.allclose(
        paths[(control_name, "base", 50)].net_return.reindex(incumbent.index), incumbent.net_return,
        rtol=0, atol=1e-12, equal_nan=True,
    )
    if not control_matches:
        raise RuntimeError("current top-20 control failed to reproduce the 119.22% challenger")
    gates = config["surface_gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.delay1_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.delay2_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr > float(gates["minimum_severe_recent_cagr"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    surface_passer_names = list(screen.loc[screen.surface_gates, "candidate"])
    # The grid is intentionally small; audit every construction so a diagnostic
    # fallback is never selected without issuer-removal evidence.
    surface_names = list(screen.candidate)
    loo_rows = []
    for name in surface_names:
        spec = constructions[name]
        choices = choices_cache[name]
        cutoff = choices.decision_at.max() - pd.DateOffset(years=1)
        recent_ciks = sorted(set(choices.loc[choices.decision_at >= cutoff, "cik10"]))
        candidate_recent = float(screen.loc[screen.candidate == name, "recent_cagr"].iloc[0])
        for cik in recent_ciks:
            altered_choices = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], int(spec["breadth"]))
            altered_weighted = weighted_cohort_targets(altered_choices, index, list(spec["cohort_weights"]))
            altered_sleeve, _ = simulate_weighted_cash(issuer_weekly, altered_weighted, "base", 50.0)
            altered_target, _ = strategy_target(
                leaders[("base", 50)], altered_sleeve, breadth_signals, breadth_high,
                fast_features, int(config["overlay_lookback_weeks"]),
            )
            path = controller.simulate_composite(leaders[("base", 50)], altered_sleeve, altered_target, 50.0)
            metric = recent_metric(name, "loo", 50, path)
            company_rows = choices.loc[choices.cik10 == cik, "company_name"]
            company = company_rows.iloc[-1] if len(company_rows) else cik
            loo_rows.append({
                "candidate": name, "cik10": cik, "company_name": company,
                "recent_cagr": metric["cagr"], "cagr_change": metric["cagr"] - candidate_recent,
            })
    loo = pd.DataFrame(loo_rows).sort_values(["candidate", "cagr_change"])
    loo_summary_rows = []
    for name in surface_names:
        subset = loo[loo.candidate == name].sort_values("cagr_change")
        worst = subset.iloc[0]
        row = screen[screen.candidate == name].iloc[0]
        improvement = float(row.recent_cagr - incumbent_recent["cagr"])
        issuer_share = float(max(0.0, -float(worst.cagr_change)) / improvement) if improvement > 0 else None
        robust_floor = min(
            float(row.recent_cagr), float(row.delay1_recent_cagr), float(row.delay2_recent_cagr),
            float(worst.recent_cagr),
        )
        loo_summary_rows.append({
            "candidate": name, "worst_loo_company": worst.company_name,
            "worst_loo_recent_cagr": worst.recent_cagr,
            "worst_loo_cagr_change": worst.cagr_change,
            "single_issuer_increment_improvement_share": issuer_share,
            "robust_floor_cagr": robust_floor,
        })
    loo_summary = pd.DataFrame(loo_summary_rows)
    screen = screen.merge(loo_summary, on="candidate", how="left")
    pool = screen[(screen.surface_gates) & (screen.candidate != control_name)].copy()
    selection_reason = "non-control surface passer maximizing predeclared robust floor"
    if pool.empty:
        pool = screen[screen.candidate != control_name].copy()
        selection_reason = "no non-control surface passer; best issuer-aware robust-floor diagnostic"
    selected_row = pool.assign(_rank=pool.robust_floor_cagr.round(12)).sort_values(
        ["_rank", "recent_cagr", "full_cagr"], ascending=False
    ).iloc[0]
    selected = str(selected_row.candidate)

    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = controller.simulate_composite(
            leaders[(scenario, int(cost))], sleeves[(selected, scenario, int(cost))],
            strategy_targets[selected], float(cost),
        )
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    strategy_targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    panels[selected].rename_axis("Date").to_csv(OUTPUT / "selected_increment_panel.csv")
    choices_cache[selected].to_csv(OUTPUT / "selected_portfolio_choices.csv", index=False)
    weighted_rows = []
    for date, weights in weighted_targets_cache[selected].items():
        for cik, weight in weights.items():
            weighted_rows.append({"effective_date": date, "cik10": cik, "sleeve_target_weight": weight})
    pd.DataFrame(weighted_rows).to_csv(OUTPUT / "selected_weighted_cohort_targets.csv", index=False)

    delay_rows = []
    for delay in [0] + [int(v) for v in config["falsification"]["increment_delays_weeks"]]:
        delayed_target, _ = strategy_target(
            leaders[("base", 50)], sleeves[(selected, "base", 50)], breadth_signals,
            breadth_high, fast_features, int(config["overlay_lookback_weeks"]), delay,
        )
        path = controller.simulate_composite(leaders[("base", 50)], sleeves[(selected, "base", 50)], delayed_target, 50.0)
        delay_rows.extend(
            row for row in base.metric_rows(selected, f"delay_{delay}", 50, path)
            if row["window"] in {"trailing_1y", "full_recent", "ytd"}
        )
    delays = pd.DataFrame(delay_rows)
    saved = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([saved.net_return.rename("candidate"), incumbent.net_return.rename("control")], axis=1).dropna()
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
    selected_loo = loo[loo.candidate == selected].sort_values("cagr_change")
    worst = selected_loo.iloc[0]
    selected_issuer_share = (
        None if pd.isna(selected_row.single_issuer_increment_improvement_share)
        else float(selected_row.single_issuer_increment_improvement_share)
    )
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    checks = {
        "top20_control_reproduces_119pct_challenger": bool(control_matches),
        "non_control_surface_gates_passed": bool(selected_row.surface_gates),
        "recent_cagr_at_least_115pct": float(selected_row.recent_cagr) >= 1.15,
        "both_increment_delays_at_least_112pct_base": float(selected_row.delay1_recent_cagr) >= 1.1293348809519022 and float(selected_row.delay2_recent_cagr) >= 1.1293348809519022,
        "worst_loo_beats_frozen": float(worst.recent_cagr) > float(frozen_recent["cagr"]),
        "worst_loo_beats_119pct_control_loo": float(worst.recent_cagr) > 1.0916574328451771,
        "single_issuer_share_at_most_50pct": selected_issuer_share is not None and selected_issuer_share <= 0.5,
        "rolling_outperformance_at_least_50pct": rolling_share >= 0.5,
        "bootstrap_4w_at_least_95pct": b4 >= 0.95,
        "bootstrap_13w_at_least_95pct": b13 >= 0.95,
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    screen.sort_values(["robust_floor_cagr", "recent_cagr"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out_all_surface_passers.csv", index=False)
    loo_summary.to_csv(OUTPUT / "leave_one_company_out_summary.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "surface_passer_count": int(len(surface_passer_names)),
        "selected_candidate": selected, "selection_reason": selection_reason,
        "breadth": int(selected_row.breadth), "cohort_weights": str(selected_row.cohort_weights).split("|"),
        "latest_distinct_holdings": int(selected_row.latest_distinct_holdings),
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "delay1_recent_cagr": float(selected_row.delay1_recent_cagr), "delay2_recent_cagr": float(selected_row.delay2_recent_cagr),
        "robust_floor_cagr": float(selected_row.robust_floor_cagr),
        "incumbent_challenger_recent_cagr": float(incumbent_recent["cagr"]),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "annual_one_way_turnover": float(selected_row.annual_one_way_turnover),
        "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr),
        "single_issuer_increment_improvement_share": selected_issuer_share,
        "rolling_outperformance_share_vs_incumbent_challenger": rolling_share,
        "completed_rolling_windows": rolling_windows,
        "bootstrap_4w_probability_positive_vs_incumbent_challenger": b4,
        "bootstrap_13w_probability_positive_vs_incumbent_challenger": b13,
        "checks": checks, "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_weighted_cohort_targets": sha256(OUTPUT / "selected_weighted_cohort_targets.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
            "loo_summary": sha256(OUTPUT / "leave_one_company_out_summary.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Cohort-diversified regime tranche v1\n\n"
        f"Tested {len(screen)} generic breadth/cohort constructions while rebuilding the same four-week "
        f"regime increment. {int(screen.surface_gates.sum())} passed the headline surface. The predeclared "
        f"issuer-aware selection chose `{selected}`, which produced {selected_row.recent_cagr:.2%} recent CAGR, "
        f"{selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and "
        f"{selected_row.full_cagr:.2%} full CAGR. One/two-week increment delays returned "
        f"{selected_row.delay1_recent_cagr:.2%}/{selected_row.delay2_recent_cagr:.2%}.\n\n"
        f"At 200-bps costs it returned {selected_row.severe_recent_cagr:.2%}. Removing {worst.company_name} "
        f"left {worst.recent_cagr:.2%}; rolling outperformance versus the 119.22% challenger was "
        f"{rolling_share:.2%}; bootstrap probabilities were {b4:.2%}/{b13:.2%}.\n\n"
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
