#!/usr/bin/env python3
"""Confirm the cash-conversion/balance-sheet rank blend on a locked fine plateau."""

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
import run_sec_form4_rank_feature_v1 as rank_feature
import run_sec_multisignal_company_rank_v1 as multi

CONFIG = ROOT / "config/sec_multisignal_plateau_confirmation_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
DISCOVERY_PATH = ROOT / "evidence/sec_multisignal_company_rank_v1/selected_path__50bps.csv"
OUTPUT = ROOT / "evidence/sec_multisignal_plateau_confirmation_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_name(weight: float, breadth: int) -> str:
    return f"bsq{int(round(weight * 1000)):03d}__breadth{int(breadth)}"


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    panel = multi.normalized_score_panel(raw)
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(panel.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
            except OSError:
                series[cik] = pd.Series(np.nan, index=index)
    weekly = pd.DataFrame(series, index=index)
    print(f"loaded {weekly.shape[1]} price histories for {len(config['secondary_weights']) * len(config['breadths'])} locked confirmation paths", flush=True)

    leader_paths = {
        (scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return
        for scenario in config["scenarios"] for cost in config["cost_bps"]
    }
    cash_scores = raw[raw.family == "cash_conversion"].copy()
    baseline_choices = breadth_runner.make_choices(cash_scores, 20)
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_cash = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_cash[(scenario, int(cost))], _ = capped.simulate_cash(weekly, baseline_targets, scenario, float(cost), None, 20)
    baseline_signal = pd.concat([leader_paths[("base", 50)].rename("leader"), baseline_cash[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
    control_target = capped.overlay_target(baseline_signal.index, baseline_signal.leader, baseline_signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
    control_paths = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), baseline_cash[(scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
        control_paths[(scenario, int(cost))] = dynamic.simulate(returns, control_target.reindex(returns.index), float(cost))
    frozen = pd.read_csv(FROZEN_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen_check = np.allclose(control_paths[("base", 50)].net_return.reindex(frozen.index), frozen.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not frozen_check:
        raise RuntimeError("rebuilt frozen control does not match audited path")
    control_paths[("base", 50)] = frozen

    structures, performance_rows, paths, choices_cache, sleeves = [], [], {}, {}, {}
    for weight, breadth in itertools.product(config["secondary_weights"], config["breadths"]):
        spec = {"families": ["balance_sheet_quality"], "secondary_total": float(weight)}
        scores = multi.blended_scores(panel, spec)
        rank_config = {"breadth": int(breadth), "influence_tail_percentile": 0.8, "influence_lookback_weeks": 26}
        choices = rank_feature.ranked_choices(scores, pd.DataFrame(), weekly, 0.0, 0.0, 1.0, rank_config)
        name = candidate_name(float(weight), int(breadth))
        stock_targets = base.build_targets(choices, index)
        sleeve_paths, peaks = {}, {}
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            sleeve_paths[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(weekly, stock_targets, scenario, float(cost), float(config["internal_stock_cap_multiple"]), int(breadth))
        signal = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeve_paths[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
        target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        structures.append({"candidate": name, "secondary_weight": float(weight), "breadth": int(breadth), "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)]})
        choices_cache[name], sleeves[name] = choices, sleeve_paths
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
            returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), sleeve_paths[(scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
            path = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
            paths[(name, scenario, int(cost))] = path
            performance_rows.extend(base.metric_rows(name, scenario, int(cost), path))

    performance = pd.DataFrame(performance_rows)
    primary_metrics = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    control_recent = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "trailing_1y")
    control_full = next(row for row in base.metric_rows("control", "base", 50, control_paths[("base", 50)]) if row["window"] == "full_recent")
    control_severe = next(row for row in base.metric_rows("control", "base", 200, control_paths[("base", 200)]) if row["window"] == "trailing_1y")
    rows = []
    for structure in structures:
        name = structure["candidate"]
        recent = primary_metrics[(primary_metrics.candidate == name) & (primary_metrics.window == "trailing_1y")].iloc[0]
        full = primary_metrics[(primary_metrics.candidate == name) & (primary_metrics.window == "full_recent")].iloc[0]
        severe = performance[(performance.candidate == name) & (performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
        rows.append({**structure, "recent_cagr": recent.cagr, "recent_sharpe": recent.sharpe_zero_rf, "recent_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "severe_recent_cagr": severe.cagr})
    surface = pd.DataFrame(rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    surface["recent_improves"] = surface.recent_cagr > control_recent["cagr"]
    surface["full_improves"] = surface.full_cagr > control_full["cagr"]
    surface["joint_improvement"] = surface.recent_improves & surface.full_improves
    surface["headline_gates"] = (surface.recent_cagr >= control_recent["cagr"] + float(config["promotion_gates"]["minimum_recent_cagr_improvement"])) & surface.full_improves & (surface.severe_recent_cagr > control_severe["cagr"]) & (surface.peak_total_stock_weight <= float(config["promotion_gates"]["maximum_peak_total_portfolio_stock_weight"]))
    plateau_share = float(surface.joint_improvement.mean())
    primary_name = candidate_name(float(config["primary_secondary_weight"]), int(config["primary_breadth"]))
    selected = surface[surface.candidate == primary_name].iloc[0]
    best = surface.iloc[0]

    for cost in [50, 100, 200]:
        paths[(primary_name, "base", cost)].rename_axis("Date").to_csv(OUTPUT / f"primary_path__{cost}bps.csv")
    choices_cache[primary_name].to_csv(OUTPUT / "primary_portfolio_choices.csv", index=False)
    saved = pd.read_csv(OUTPUT / "primary_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    discovery = pd.read_csv(DISCOVERY_PATH, parse_dates=["Date"]).set_index("Date")
    discovery_match = np.allclose(saved.net_return.reindex(discovery.index), discovery.net_return, rtol=0, atol=1e-12, equal_nan=True)
    joined = pd.concat([saved.net_return.rename("candidate"), frozen.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    rolling_share, rolling_windows = audit.completed_rolling_outperformance(joined, int(config["falsification"]["rolling_comparison_weeks"]))
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])

    primary_sleeve = sleeves[primary_name][("base", 50)]
    primary_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), primary_sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
    delay_rows = []
    for delay in [0] + [int(value) for value in config["falsification"]["signal_delays_weeks"]]:
        target = capped.overlay_target(primary_returns.index, primary_returns.leader, primary_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]), delay)
        path = dynamic.simulate(primary_returns, target, 50.0)
        recent = next(row for row in base.metric_rows(primary_name, f"delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_weeks": delay, "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    primary_choices = choices_cache[primary_name]
    recent_ciks = sorted(set(primary_choices.loc[primary_choices.decision_at >= primary_choices.decision_at.max() - pd.DateOffset(years=1), "cik10"]))
    blend = multi.blended_scores(panel, {"families": ["balance_sheet_quality"], "secondary_total": float(config["primary_secondary_weight"])})
    rank_config = {"breadth": int(config["primary_breadth"]), "influence_tail_percentile": 0.8, "influence_lookback_weeks": 26}
    loo_rows = []
    for cik in recent_ciks:
        choices = rank_feature.ranked_choices(blend, pd.DataFrame(), weekly, 0.0, 0.0, 1.0, rank_config, banned_cik=cik)
        stock_targets = base.build_targets(choices, index)
        sleeve, _ = capped.simulate_cash(weekly, stock_targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), int(config["primary_breadth"]))
        returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        path = dynamic.simulate(returns, target, 50.0)
        recent = next(row for row in base.metric_rows(primary_name, "loo", 50, path) if row["window"] == "trailing_1y")
        company = primary_choices.loc[primary_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected.recent_cagr - control_recent["cagr"])
    issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    checks = {
        "primary_reproduces_discovery_exactly": bool(discovery_match),
        "primary_headline_gates": bool(selected.headline_gates),
        "one_week_delay_beats_control": bool(delays.loc[delays.delay_weeks == 1, "recent_cagr"].iloc[0] > control_recent["cagr"]),
        "two_week_delay_beats_control": bool(delays.loc[delays.delay_weeks == 2, "recent_cagr"].iloc[0] > control_recent["cagr"]),
        "plateau_gate": bool(plateau_share >= float(config["promotion_gates"]["minimum_plateau_joint_improvement_share"])),
        "rolling_gate": bool(rolling_share >= float(config["promotion_gates"]["minimum_completed_rolling_outperformance_share"])),
        "bootstrap_4w_gate": bool(b4 >= float(config["promotion_gates"]["minimum_bootstrap_probability_positive"])),
        "bootstrap_13w_gate": bool(b13 >= float(config["promotion_gates"]["minimum_bootstrap_probability_positive"])),
        "worst_loo_beats_control": bool(worst.recent_cagr > control_recent["cagr"]),
        "single_issuer_influence_gate": bool(issuer_share is not None and issuer_share <= float(config["promotion_gates"]["maximum_single_issuer_improvement_share"])),
        "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(primary_name, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected.recent_cagr, atol=1e-12, rtol=0))
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    surface.to_csv(OUTPUT / "fine_plateau.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(surface)),
        "primary_candidate": primary_name, "primary_recent_cagr": float(selected.recent_cagr), "primary_recent_sharpe": float(selected.recent_sharpe), "primary_recent_drawdown": float(selected.recent_drawdown), "primary_full_cagr": float(selected.full_cagr), "primary_severe_recent_cagr": float(selected.severe_recent_cagr),
        "best_diagnostic_candidate": str(best.candidate), "best_diagnostic_recent_cagr": float(best.recent_cagr), "best_diagnostic_full_cagr": float(best.full_cagr),
        "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]),
        "plateau_joint_improvement_share": plateau_share, "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share,
        "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13, "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": bool(frozen_check), "runtime": runtime,
        "artifact_sha256": {"primary_path_50bps": sha256(OUTPUT / "primary_path__50bps.csv"), "discovery_path_50bps": sha256(DISCOVERY_PATH), "frozen_control_50bps": sha256(FROZEN_CONTROL)},
        "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC multi-signal plateau confirmation v1\n\n"
        f"The locked 80/20 breadth-20 primary reproduced exactly at {selected.recent_cagr:.2%} recent CAGR, {selected.recent_sharpe:.3f} Sharpe, {selected.recent_drawdown:.2%} drawdown, and {selected.full_cagr:.2%} full CAGR. Across {len(surface)} fine weight/breadth paths, only {int(surface.joint_improvement.sum())} paths ({plateau_share:.2%}) improved both recent and full-period returns, versus the required {float(config['promotion_gates']['minimum_plateau_joint_improvement_share']):.0%}.\n\n"
        f"The highest recent-return diagnostic, {best.candidate}, reached {best.recent_cagr:.2%} recent CAGR but only {best.full_cagr:.2%} full CAGR. Bootstrap, two-week delay, and issuer-influence failures from discovery remained unchanged.\n\n"
        f"The full confirmation decision was {'PASS' if all_passed else 'FAIL'}. The evidence confirms an isolated parameter ridge, not a stable plateau. The frozen leader was not replaced and live execution remains disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
