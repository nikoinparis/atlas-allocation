#!/usr/bin/env python3
"""Test diversified issuer-level combinations of independent SEC signals."""

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
import run_sec_form4_rank_feature_v1 as rank_feature

CONFIG = ROOT / "config/sec_multisignal_company_rank_v1.json"
SCORES = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
FROZEN_CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_multisignal_company_rank_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensemble_specs(config: dict) -> list[dict]:
    secondaries = list(config["secondary_families"])
    specs = [{"name": "cash100", "families": [], "secondary_total": 0.0}]
    for family in secondaries:
        for weight in config["single_secondary_weights"]:
            specs.append({"name": f"cash_{family}_{int(weight*100):02d}", "families": [family], "secondary_total": float(weight)})
    for left, right in itertools.combinations(secondaries, 2):
        for weight in config["pair_secondary_total_weights"]:
            specs.append({"name": f"cash_{left}+{right}_{int(weight*100):02d}", "families": [left, right], "secondary_total": float(weight)})
    for weight in config["all_secondary_total_weights"]:
        specs.append({"name": f"cash_all4_{int(weight*100):02d}", "families": secondaries, "secondary_total": float(weight)})
    return specs


def normalized_score_panel(scores: pd.DataFrame) -> pd.DataFrame:
    frame = scores.copy()
    frame["normalized_score"] = frame.groupby(["decision_at", "family"], sort=False).score.rank(pct=True, method="average")
    keys = ["decision_at", "cik10", "company_name_as_filed", "sector"]
    return frame.pivot_table(index=keys, columns="family", values="normalized_score", aggfunc="last").reset_index()


def blended_scores(panel: pd.DataFrame, spec: dict) -> pd.DataFrame:
    out = panel[["decision_at", "cik10", "company_name_as_filed", "sector"]].copy()
    total = float(spec["secondary_total"])
    out["score"] = (1.0 - total) * panel.cash_conversion
    if spec["families"]:
        each = total / len(spec["families"])
        for family in spec["families"]:
            out["score"] = out.score + each * panel[family].fillna(0.5)
    return out.dropna(subset=["score"])


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw_scores = pd.read_csv(SCORES, dtype={"cik10": str}, parse_dates=["decision_at"])
    panel = normalized_score_panel(raw_scores)
    specs = ensemble_specs(config)
    decisions = pd.DatetimeIndex(sorted(pd.to_datetime(panel.decision_at, utc=True).dt.tz_localize(None).unique()))
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")

    events = insider.load_events()
    form4 = rank_feature.form4_panels(events, decisions, [int(config["form4_window_days"])], str(config["form4_family"]))[int(config["form4_window_days"])]
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
    print(f"loaded {len(specs)} issuer-level ensembles, {len(events):,} Form 4 filings, and {weekly.shape[1]} price histories", flush=True)

    leader_paths = {
        (scenario, int(cost)): dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return
        for scenario in config["scenarios"] for cost in config["cost_bps"]
    }
    cash_scores = raw_scores[raw_scores.family == "cash_conversion"].copy()
    baseline_choices = breadth_runner.make_choices(cash_scores, int(config["breadth"]))
    baseline_targets = base.build_targets(baseline_choices, index)
    baseline_cash = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        baseline_cash[(scenario, int(cost))], _ = capped.simulate_cash(weekly, baseline_targets, scenario, float(cost), None, int(config["breadth"]))
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

    paths, targets, choices_cache, sleeve_cache = {}, {}, {}, {}
    structures, performance_rows = [], []
    rank_config = {"breadth": int(config["breadth"]), "influence_tail_percentile": 0.8, "influence_lookback_weeks": 26}
    for spec in specs:
        scores = blended_scores(panel, spec)
        for form4_weight, sector_cap in itertools.product(config["form4_feature_weights"], config["sector_caps"]):
            choices = rank_feature.ranked_choices(scores, form4, weekly, float(form4_weight), 0.0, float(sector_cap), rank_config)
            if choices.empty:
                continue
            name = f"{spec['name']}__f4{int(float(form4_weight)*100):02d}__sector{int(float(sector_cap)*100)}"
            stock_targets = base.build_targets(choices, index)
            sleeve_paths, peaks = {}, {}
            for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
                sleeve_paths[(scenario, int(cost))], peaks[(scenario, int(cost))] = capped.simulate_cash(weekly, stock_targets, scenario, float(cost), float(config["internal_stock_cap_multiple"]), int(config["breadth"]))
            signal = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeve_paths[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
            target = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
            targets[name], choices_cache[name], sleeve_cache[name] = target, choices, sleeve_paths
            structures.append({"candidate": name, "ensemble": spec["name"], "family_set": "+".join(spec["families"]) or "cash_only", "secondary_total": spec["secondary_total"], "form4_weight": float(form4_weight), "sector_cap": float(sector_cap), "peak_total_stock_weight": float(config["overlay_active_allocation"]) * peaks[("base", 50)]})
            for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
                returns = pd.concat([leader_paths[(scenario, int(cost))].rename("leader"), sleeve_paths[(scenario, int(cost))].net_return.rename("cash_conversion")], axis=1).dropna()
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
        screen_rows.append({**structure, "recent_cagr": recent.cagr, "recent_sharpe": recent.sharpe_zero_rf, "recent_drawdown": recent.max_drawdown, "full_cagr": full.cagr, "severe_recent_cagr": severe.cagr, "recent_beats": recent.cagr >= control_recent["cagr"] + float(config["promotion_gates"]["minimum_recent_cagr_improvement"]), "full_beats": full.cagr >= control_full["cagr"], "severe_beats": severe.cagr > control_severe["cagr"]})
    screen = pd.DataFrame(screen_rows).sort_values(["recent_cagr", "full_cagr"], ascending=False)
    screen["surface_gates"] = screen.recent_beats & screen.full_beats & screen.severe_beats & (screen.peak_total_stock_weight <= float(config["promotion_gates"]["maximum_peak_total_portfolio_stock_weight"]))
    challengers = screen[screen.family_set != "cash_only"]
    selected_row = (challengers[challengers.surface_gates] if challengers.surface_gates.any() else challengers).iloc[0]
    selected = str(selected_row.candidate)
    matched_cash = screen[(screen.family_set == "cash_only") & np.isclose(screen.form4_weight, selected_row.form4_weight) & np.isclose(screen.sector_cap, selected_row.sector_cap)].iloc[0]

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
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])

    selected_sleeves = sleeve_cache[selected]
    selected_returns = pd.concat([leader_paths[("base", 50)].rename("leader"), selected_sleeves[("base", 50)].net_return.rename("cash_conversion")], axis=1).dropna()
    delay_rows = []
    for delay in [0] + [int(value) for value in config["falsification"]["signal_delays_weeks"]]:
        target = capped.overlay_target(selected_returns.index, selected_returns.leader, selected_returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]), delay)
        path = dynamic.simulate(selected_returns, target, 50.0)
        recent = next(row for row in base.metric_rows(selected, f"delay_{delay}", 50, path) if row["window"] == "trailing_1y")
        delay_rows.append({"delay_weeks": delay, "recent_cagr": recent["cagr"]})
    delays = pd.DataFrame(delay_rows)

    spec = next(item for item in specs if item["name"] == selected_row.ensemble)
    blend = blended_scores(panel, spec)
    recent_choices = choices_cache[selected]
    recent_ciks = sorted(set(recent_choices.loc[recent_choices.decision_at >= recent_choices.decision_at.max() - pd.DateOffset(years=1), "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        choices = rank_feature.ranked_choices(blend, form4, weekly, float(selected_row.form4_weight), 0.0, float(selected_row.sector_cap), rank_config, banned_cik=cik)
        stock_targets = base.build_targets(choices, index)
        sleeve, _ = capped.simulate_cash(weekly, stock_targets, "base", 50.0, float(config["internal_stock_cap_multiple"]), int(config["breadth"]))
        returns = pd.concat([leader_paths[("base", 50)].rename("leader"), sleeve.net_return.rename("cash_conversion")], axis=1).dropna()
        target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, int(config["overlay_lookback_weeks"]), float(config["overlay_active_allocation"]))
        path = dynamic.simulate(returns, target, 50.0)
        recent = next(row for row in base.metric_rows(selected, "loo", 50, path) if row["window"] == "trailing_1y")
        company = recent_choices.loc[recent_choices.cik10 == cik, "company_name_as_filed"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.recent_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    improvement = float(selected_row.recent_cagr - control_recent["cagr"])
    single_issuer_share = float(max(0.0, -worst.cagr_change) / improvement) if improvement > 0 else None

    neighbors = screen[(screen.family_set == selected_row.family_set) & (screen.form4_weight.isin(config["form4_feature_weights"])) & (screen.sector_cap.isin(config["sector_caps"]))].copy()
    neighbors["joint_improvement"] = (neighbors.recent_cagr > control_recent["cagr"]) & (neighbors.full_cagr > control_full["cagr"])
    neighborhood_share = float(neighbors.joint_improvement.mean())
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    minimum_bootstrap = float(config["promotion_gates"]["minimum_bootstrap_probability_positive"])
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
        "persisted_recent_cagr_matches": bool(np.isclose(next(row for row in base.metric_rows(selected, "saved", 50, saved) if row["window"] == "trailing_1y")["cagr"], selected_row.recent_cagr, atol=1e-12, rtol=0))
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    screen.to_csv(OUTPUT / "screening.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    neighbors.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)), "selected_candidate": selected,
        "selected_family_set": str(selected_row.family_set), "selected_secondary_total_weight": float(selected_row.secondary_total), "selected_form4_weight": float(selected_row.form4_weight),
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe), "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr), "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "control_recent_cagr": float(control_recent["cagr"]), "control_full_cagr": float(control_full["cagr"]), "control_severe_recent_cagr": float(control_severe["cagr"]),
        "matched_cash_recent_cagr": float(matched_cash.recent_cagr), "matched_cash_full_cagr": float(matched_cash.full_cagr),
        "multisignal_incremental_recent_cagr": float(selected_row.recent_cagr - matched_cash.recent_cagr), "multisignal_incremental_full_cagr": float(selected_row.full_cagr - matched_cash.full_cagr),
        "completed_rolling_windows": rolling_windows, "rolling_outperformance_share": rolling_share, "neighborhood_joint_improvement_share": neighborhood_share,
        "bootstrap_4w_probability_positive": b4, "bootstrap_13w_probability_positive": b13, "worst_loo_company": str(worst.company_name), "worst_loo_recent_cagr": float(worst.recent_cagr), "single_issuer_improvement_share": single_issuer_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "frozen_control_rebuilt_exactly": bool(frozen_check), "runtime": runtime,
        "artifact_sha256": {"selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"), "frozen_control_50bps": sha256(FROZEN_CONTROL)},
        "strategy_replacement_authorized": False, "live_trading_enabled": False
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC multi-signal company rank v1\n\n"
        f"Tested {len(screen)} diversified issuer-level combinations. The selected 80% cash-conversion / 20% balance-sheet-quality candidate produced {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR, versus {control_recent['cagr']:.2%} recent and {control_full['cagr']:.2%} full CAGR for the frozen control. It retained {selected_row.severe_recent_cagr:.2%} recent CAGR at 200-bps costs.\n\n"
        f"The one-week delayed result was {delays.loc[delays.delay_weeks == 1, 'recent_cagr'].iloc[0]:.2%}, and the two-week result was {delays.loc[delays.delay_weeks == 2, 'recent_cagr'].iloc[0]:.2%}. It beat the control in {rolling_share:.2%} of {rolling_windows} completed rolling windows, while {neighborhood_share:.2%} of its parameter neighborhood improved both recent and full CAGR. Four-week and thirteen-week bootstrap probabilities were {b4:.2%} and {b13:.2%}. Removing {worst.company_name} left {worst.recent_cagr:.2%}; that issuer accounted for {single_issuer_share:.2%} of the candidate's improvement.\n\n"
        f"The falsification decision was {'PASS' if all_passed else 'FAIL'}. The candidate was not promoted. No live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
