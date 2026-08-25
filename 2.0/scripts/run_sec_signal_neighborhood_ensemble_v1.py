#!/usr/bin/env python3
"""Blend confirmed signal neighborhoods to target temporal and issuer robustness."""

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
import run_sec_breadth_dispersion_allocation_controller_v1 as controller
import run_sec_cohort_diversified_regime_tranche_v1 as cohort
import run_sec_cluster_aware_cash_sleeve_v1 as challenger
import run_sec_cluster_challenger_locked_audit_v1 as locked
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_signal_neighborhood_ensemble_v1.json"
CANDIDATE = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1"
PREDECESSOR = ROOT / "evidence/sec_regime_increment_tranching_v1"
OUTPUT = ROOT / "evidence/sec_signal_neighborhood_ensemble_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mix_targets(
    component_targets: dict[str, dict[pd.Timestamp, dict[str, float]]],
    weights: dict[str, float],
) -> dict[pd.Timestamp, dict[str, float]]:
    dates = sorted(set().union(*(set(component_targets[name]) for name in weights)))
    mixed = {}
    for date in dates:
        row = {}
        for name, share in weights.items():
            for cik, weight in component_targets[name].get(date, {}).items():
                row[cik] = row.get(cik, 0.0) + float(share) * float(weight)
        total = sum(row.values())
        if total > 0:
            mixed[date] = {cik: value / total for cik, value in row.items() if value > 0}
    return mixed


def recent_metric(path: pd.DataFrame) -> dict:
    return locked.compound_metrics(path.net_return.iloc[-52:])


def endpoint_share(path: pd.DataFrame, control: pd.DataFrame, offsets: list[int]) -> float:
    joined = locked.aligned_returns(path, control)
    outcomes = []
    for offset in offsets:
        finish = len(joined) - int(offset)
        frame = joined.iloc[max(0, finish - 52):finish]
        outcomes.append(locked.compound_metrics(frame.candidate)["annualized_return"] >
                        locked.compound_metrics(frame.control)["annualized_return"])
    return float(np.mean(outcomes))


def build_component_targets(context: dict, config: dict, banned: set[str] | None = None) -> tuple[dict, dict]:
    panel = __import__("run_sec_multisignal_company_rank_v1").normalized_score_panel(context["scores"])
    targets, choices = {}, {}
    for name, definition in config["membership_definitions"].items():
        blend = {"name": name, **definition}
        scores = challenger.blended_membership_scores(panel, blend)
        if banned:
            scores = scores[~scores.cik10.isin(set(banned))]
        cohorts = challenger.selected_cohorts(scores, int(config["breadth"]))
        targets[name], choices[name] = challenger.build_weighted_targets(
            cohorts, context["weekly"], context["index"], "equal", 26, 0.0, 1.0
        )
    return targets, choices


def build_path(
    context: dict,
    mixed_targets: dict,
    scenario: str = "base",
    cost: int = 50,
    decision_delay: int = 0,
    increment_delay: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    targets = locked.shift_targets(mixed_targets, context["index"], int(decision_delay)) if decision_delay else mixed_targets
    signal_sleeve, peak = cohort.simulate_weighted_cash(context["weekly"], targets, "base", 50.0)
    target, _ = cohort.strategy_target(
        context["leaders"][("base", 50)], signal_sleeve, context["breadth_signals"],
        context["breadth_high"], context["fast_features"], 11, int(increment_delay),
    )
    sleeve = signal_sleeve if scenario == "base" and int(cost) == 50 else cohort.simulate_weighted_cash(
        context["weekly"], targets, scenario, float(cost)
    )[0]
    path = controller.simulate_composite(context["leaders"][(scenario, int(cost))], sleeve, target, float(cost))
    return path, target, float(peak)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context = locked.build_context({"membership_weights": {"cash_conversion": 0.8, "balance_sheet_quality": 0.2}})
    component_targets, component_choices = build_component_targets(context, config)
    predecessor = pd.read_csv(PREDECESSOR / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    source_candidate = pd.read_csv(CANDIDATE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")

    rows, paths, targets, mixed_cache = [], {}, {}, {}
    for spec in config["ensembles"]:
        name = str(spec["name"])
        mixed = mix_targets(component_targets, spec["components"])
        mixed_cache[name] = mixed
        current, target, peak = build_path(context, mixed)
        severe, _, _ = build_path(context, mixed, cost=200)
        paths[(name, "base", 50)], paths[(name, "base", 200)], targets[name] = current, severe, target
        recent, severe_recent = recent_metric(current), recent_metric(severe)
        full = locked.compound_metrics(current.net_return)
        delay_values = []
        for delay in config["increment_delays_weeks"]:
            delayed, _, _ = build_path(context, mixed, increment_delay=int(delay))
            delay_values.append(recent_metric(delayed)["annualized_return"])
        for delay in config["decision_delays_weeks"]:
            delayed, _, _ = build_path(context, mixed, decision_delay=int(delay))
            delay_values.append(recent_metric(delayed)["annualized_return"])
        joined = locked.aligned_returns(current, predecessor)
        rolling26, windows26 = locked.rolling_outperformance(joined, 26)
        rows.append({
            "candidate": name, "components": json.dumps(spec["components"], sort_keys=True),
            "recent_cagr": recent["annualized_return"], "recent_sharpe": recent["sharpe"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["annualized_return"],
            "severe_recent_cagr": severe_recent["annualized_return"],
            "worst_delay_recent_cagr": min(delay_values),
            "endpoint_outperformance_share": endpoint_share(current, predecessor, config["trailing_endpoint_offsets_weeks"]),
            "rolling26_outperformance_share": rolling26, "rolling26_windows": windows26,
            "peak_total_stock_weight": float(target.cash_conversion.max() * peak),
            "latest_distinct_holdings": int(len(mixed[max(mixed)])),
        })
    screen = pd.DataFrame(rows)
    control_name = "balance20_control"
    control_exact = np.allclose(paths[(control_name, "base", 50)].net_return.reindex(source_candidate.index),
                                source_candidate.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not control_exact:
        raise RuntimeError("balance20 ensemble control failed exact 123.71% reproduction")
    gates = config["surface_gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr >= float(gates["minimum_severe_recent_cagr"]))
        & (screen.worst_delay_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.endpoint_outperformance_share >= float(gates["minimum_endpoint_outperformance_share"]))
        & (screen.rolling26_outperformance_share >= float(gates["minimum_rolling_26w_outperformance_share"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    pool = screen[(screen.candidate != control_name) & screen.surface_gates]
    reason = "endpoint/rolling robustness gates with recent return at least 119.22%"
    if pool.empty:
        pool = screen[screen.candidate != control_name]
        reason = "no ensemble passed all endpoint gates; strongest endpoint diagnostic"
    selected_row = pool.sort_values(
        ["endpoint_outperformance_share", "rolling26_outperformance_share", "recent_cagr", "full_cagr"],
        ascending=False,
    ).iloc[0]
    selected = str(selected_row.candidate)

    # Full selected costs/scenarios and simultaneous issuer-removal bundles.
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = build_path(
            context, mixed_cache[selected], scenario=scenario, cost=int(cost)
        )[0]
    prior_loo = pd.read_csv(CANDIDATE / "leave_one_company_out.csv", dtype={"cik10": str}).sort_values("recent_cagr")
    worst_order = list(prior_loo.cik10)
    selected_spec = next(item for item in config["ensembles"] if item["name"] == selected)
    missing_rows = []
    for size in config["missing_issuer_bundle_sizes"]:
        banned = set(worst_order[:int(size)])
        altered_components, _ = build_component_targets(context, config, banned)
        altered_mixed = mix_targets(altered_components, selected_spec["components"])
        path, _, _ = build_path(context, altered_mixed)
        metric = recent_metric(path)
        missing_rows.append({"bundle_size": int(size), "banned_ciks": "|".join(sorted(banned)),
                             "recent_cagr": metric["annualized_return"], "recent_sharpe": metric["sharpe"],
                             "recent_drawdown": metric["max_drawdown"]})
    missing = pd.DataFrame(missing_rows)
    selected_path = paths[(selected, "base", 50)]
    joined = locked.aligned_returns(selected_path, predecessor)
    recent_joined = joined.iloc[-52:]
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(controller.stable_excess_returns(recent_joined), int(block),
        int(config["bootstrap_draws"]), int(config["bootstrap_seed"])) for block in config["bootstrap_blocks_weeks"]])
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    checks = {
        "control_reproduces_123pct_candidate": bool(control_exact),
        "selected_surface_gates_passed": bool(selected_row.surface_gates),
        "recent_cagr_at_least_119pct": float(selected_row.recent_cagr) >= float(gates["minimum_recent_cagr"]),
        "worst_five_issuer_bundle_beats_112pct_base": float(missing.recent_cagr.min()) >= float(gates["minimum_delay_recent_cagr"]),
        "bootstrap_4w_at_least_95pct": b4 >= float(config["minimum_bootstrap_probability"]),
        "bootstrap_13w_at_least_95pct": b13 >= float(config["minimum_bootstrap_probability"]),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_strategy_target_weights.csv")
    pd.DataFrame([
        {"rebalance_at": date, "cik10": cik, "intended_weight": weight}
        for date, row in mixed_cache[selected].items() for cik, weight in row.items()
    ]).to_csv(OUTPUT / "selected_stock_target_weights.csv", index=False)
    screen.sort_values(["surface_gates", "endpoint_outperformance_share", "recent_cagr"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    missing.to_csv(OUTPUT / "missing_issuer_bundles.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "surface_passer_count": int(screen.surface_gates.sum()),
        "selected_candidate": selected, "selection_reason": reason,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "worst_delay_recent_cagr": float(selected_row.worst_delay_recent_cagr),
        "endpoint_outperformance_share": float(selected_row.endpoint_outperformance_share),
        "rolling26_outperformance_share": float(selected_row.rolling26_outperformance_share),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "latest_distinct_holdings": int(selected_row.latest_distinct_holdings),
        "worst_missing_bundle_recent_cagr": float(missing.recent_cagr.min()),
        "bootstrap_4w_probability_positive_vs_predecessor": b4,
        "bootstrap_13w_probability_positive_vs_predecessor": b13,
        "checks": checks, "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
            "stock_targets": sha256(OUTPUT / "selected_stock_target_weights.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Signal-neighborhood ensemble v1\n\n"
        f"Tested {len(screen)} fixed ensembles of only the confirmed balance-score neighborhood and cash-only predecessor. "
        f"`{selected}` returned {selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. Its endpoint/rolling-26 "
        f"outperformance shares were {selected_row.endpoint_outperformance_share:.2%}/{selected_row.rolling26_outperformance_share:.2%}.\n\n"
        f"The worst five-issuer bundle stress returned {missing.recent_cagr.min():.2%}; bootstrap probabilities were "
        f"{b4:.2%}/{b13:.2%}. Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. "
        "No promotion, forward clock, or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
