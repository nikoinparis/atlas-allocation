#!/usr/bin/env python3
"""Test generic overlap budgets between two frozen fundamental components."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_cluster_aware_cash_sleeve_v1 as challenger
import run_sec_cluster_challenger_locked_audit_v1 as locked
import run_sec_form4_dynamic_overlay_v1 as audit
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_multisignal_company_rank_v1 as multisignal
import run_sec_signal_neighborhood_ensemble_v1 as ensemble

CONFIG = ROOT / "config/sec_cross_component_overlap_budget_v1.json"
SOURCE = ROOT / "evidence/sec_sector_aware_signal_ensemble_v1"
PREDECESSOR = ROOT / "evidence/sec_regime_increment_tranching_v1/selected_path__50bps.csv"
WORST_ORDER = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1/leave_one_company_out.csv"
OUTPUT = ROOT / "evidence/sec_cross_component_overlap_budget_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_ranked(frame: pd.DataFrame, breadth: int, sector_cap: float,
                  first_names: set[str] | None = None, maximum_overlap: int | None = None) -> pd.DataFrame:
    ranked = frame.sort_values(["score", "cik10"], ascending=[False, True])
    sector_limit = int(math.floor(float(sector_cap) * int(breadth) + 1e-12))
    selected, sector_counts, overlap = [], {}, 0
    reference = first_names or set()
    for row in ranked.itertuples(index=False):
        cik, sector = str(row.cik10), str(row.sector)
        is_overlap = cik in reference
        if sector_counts.get(sector, 0) >= sector_limit:
            continue
        if maximum_overlap is not None and is_overlap and overlap >= int(maximum_overlap):
            continue
        selected.append(cik)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        overlap += int(is_overlap)
        if len(selected) == int(breadth):
            break
    if len(selected) != int(breadth):
        raise RuntimeError(f"unable to fill constrained cohort: selected={len(selected)} breadth={breadth}")
    order = {cik: position for position, cik in enumerate(selected)}
    result = ranked[ranked.cik10.astype(str).isin(selected)].copy()
    result["_order"] = result.cik10.astype(str).map(order)
    return result.sort_values("_order").drop(columns="_order")


def constrained_cohorts(scores: dict[str, pd.DataFrame], breadth: int, caps: dict[str, float],
                        order: str, maximum_overlap: int) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    first, second = ("cash100", "balance20") if order == "cash_first" else ("balance20", "cash100")
    output = {first: [], second: []}
    overlap_rows = []
    decisions = sorted(set(scores[first].decision_at) & set(scores[second].decision_at))
    for decision in decisions:
        first_frame = scores[first][scores[first].decision_at == decision]
        second_frame = scores[second][scores[second].decision_at == decision]
        chosen_first = select_ranked(first_frame, breadth, caps[first])
        first_names = set(chosen_first.cik10.astype(str))
        chosen_second = select_ranked(second_frame, breadth, caps[second], first_names, maximum_overlap)
        second_names = set(chosen_second.cik10.astype(str))
        output[first].append(chosen_first)
        output[second].append(chosen_second)
        overlap_rows.append({"decision_at": decision, "selection_order": order,
                             "maximum_overlap": int(maximum_overlap),
                             "realized_overlap": int(len(first_names & second_names)),
                             "distinct_holdings": int(len(first_names | second_names))})
    return {name: pd.concat(frames, ignore_index=True) for name, frames in output.items()}, pd.DataFrame(overlap_rows)


def build_mixed(context: dict, config: dict, order: str, maximum_overlap: int,
                banned: set[str] | None = None) -> tuple[dict, pd.DataFrame]:
    panel = multisignal.normalized_score_panel(context["scores"])
    base = panel[["decision_at", "cik10", "company_name_as_filed", "sector"]]
    scores = {
        "cash100": base.assign(score=panel.cash_conversion),
        "balance20": base.assign(score=0.8 * panel.cash_conversion + 0.2 * panel.balance_sheet_quality),
    }
    if banned:
        scores = {name: frame[~frame.cik10.astype(str).isin(banned)].copy() for name, frame in scores.items()}
    cohorts, overlap = constrained_cohorts(
        scores, int(config["breadth_per_component"]), config["component_sector_caps"], order, int(maximum_overlap)
    )
    targets = {}
    for name, cohort in cohorts.items():
        targets[name], _ = challenger.build_weighted_targets(
            cohort, context["weekly"], context["index"], "equal", 26, 0.0, 1.0
        )
    return ensemble.mix_targets(targets, config["component_mix"]), overlap


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context = locked.build_context({"membership_weights": {"cash_conversion": 0.8, "balance_sheet_quality": 0.2}})
    source_control = pd.read_csv(SOURCE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    predecessor = pd.read_csv(PREDECESSOR, parse_dates=["Date"]).set_index("Date")
    worst_order = list(pd.read_csv(WORST_ORDER, dtype={"cik10": str}).sort_values("recent_cagr").cik10)
    specs = [(order, int(overlap)) for order in config["selection_orders"]
             for overlap in config["maximum_overlap_counts"] if not (order == "balance_first" and int(overlap) == 20)]
    rows, paths, mixed_cache, target_cache, overlap_detail, missing_rows = [], {}, {}, {}, [], []
    gates = config["gates"]
    challenger_count = int(config["multiple_testing"]["challenger_count"])
    for order, maximum_overlap in specs:
        name = f"{order}_overlap{maximum_overlap}"
        mixed, overlap = build_mixed(context, config, order, maximum_overlap)
        overlap.insert(0, "candidate", name)
        overlap_detail.append(overlap)
        mixed_cache[name] = mixed
        current, target, peak = ensemble.build_path(context, mixed)
        severe, _, _ = ensemble.build_path(context, mixed, cost=200)
        paths[(name, "base", 50)], paths[(name, "base", 200)], target_cache[name] = current, severe, target
        recent, severe_recent = ensemble.recent_metric(current), ensemble.recent_metric(severe)
        full = locked.compound_metrics(current.net_return)
        delays = []
        for delay in config["decision_delays_weeks"]:
            delays.append(ensemble.recent_metric(ensemble.build_path(context, mixed, decision_delay=int(delay))[0])["annualized_return"])
        for delay in config["increment_delays_weeks"]:
            delays.append(ensemble.recent_metric(ensemble.build_path(context, mixed, increment_delay=int(delay))[0])["annualized_return"])
        rolling26, windows26 = locked.rolling_outperformance(locked.aligned_returns(current, source_control), 26)
        bundle_values = []
        for size in config["missing_issuer_bundle_sizes"]:
            altered, _ = build_mixed(context, config, order, maximum_overlap, set(worst_order[:int(size)]))
            metric = ensemble.recent_metric(ensemble.build_path(context, altered)[0])
            bundle_values.append(metric["annualized_return"])
            missing_rows.append({"candidate": name, "bundle_size": int(size),
                                 "banned_ciks": "|".join(worst_order[:int(size)]),
                                 "recent_cagr": metric["annualized_return"]})
        joined_predecessor = locked.aligned_returns(current, predecessor).iloc[-52:]
        raw_probabilities = [dynamic.block_bootstrap(
            joined_predecessor.candidate - joined_predecessor.control,
            int(block), int(config["bootstrap_draws"]), int(config["bootstrap_seed"])
        )["probability_positive"] for block in config["bootstrap_blocks_weeks"]]
        minimum_raw = float(min(raw_probabilities))
        adjusted = 1.0 if name == config["control"] else max(
            0.0, 1.0 - min(1.0, (1.0 - minimum_raw) * challenger_count)
        )
        latest_overlap = overlap.sort_values("decision_at").iloc[-1]
        row = {
            "candidate": name, "selection_order": order, "maximum_overlap": maximum_overlap,
            "latest_realized_overlap": int(latest_overlap.realized_overlap),
            "latest_distinct_holdings": int(latest_overlap.distinct_holdings),
            "recent_cagr": recent["annualized_return"], "recent_sharpe": recent["sharpe"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["annualized_return"],
            "severe_recent_cagr": severe_recent["annualized_return"], "worst_delay_recent_cagr": min(delays),
            "endpoint_outperformance_share": ensemble.endpoint_share(current, source_control, config["endpoint_offsets_weeks"]),
            "rolling26_outperformance_share": rolling26, "rolling26_windows": windows26,
            "worst_missing_bundle_recent_cagr": min(bundle_values),
            "peak_total_stock_weight": float(target.cash_conversion.max() * peak),
            "minimum_raw_bootstrap_probability_vs_predecessor": minimum_raw,
            "bonferroni_adjusted_probability_vs_predecessor": adjusted,
        }
        row["all_candidate_gates"] = bool(
            name != config["control"]
            and row["recent_cagr"] >= float(gates["minimum_recent_cagr"])
            and row["recent_sharpe"] >= float(gates["minimum_recent_sharpe"])
            and row["recent_drawdown"] >= float(gates["minimum_recent_drawdown"])
            and row["full_cagr"] >= float(gates["minimum_full_cagr"])
            and row["severe_recent_cagr"] >= float(gates["minimum_severe_recent_cagr"])
            and row["worst_delay_recent_cagr"] >= float(gates["minimum_delay_recent_cagr"])
            and row["endpoint_outperformance_share"] >= float(gates["minimum_endpoint_outperformance_share"])
            and row["rolling26_outperformance_share"] >= float(gates["minimum_rolling_26w_outperformance_share"])
            and row["worst_missing_bundle_recent_cagr"] >= float(gates["minimum_worst_five_issuer_cagr"])
            and row["peak_total_stock_weight"] <= float(gates["maximum_peak_total_stock_weight"])
            and row["bonferroni_adjusted_probability_vs_predecessor"] >= float(gates["minimum_adjusted_bootstrap_probability_vs_predecessor"])
        )
        rows.append(row)
    screen = pd.DataFrame(rows)
    control = str(config["control"])
    control_exact = np.allclose(paths[(control, "base", 50)].net_return.reindex(source_control.index),
                                source_control.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not control_exact:
        raise RuntimeError("overlap control failed exact sector-ensemble reproduction")
    passers = screen[screen.all_candidate_gates]
    if len(passers):
        selected_row = passers.sort_values(["recent_cagr", "worst_missing_bundle_recent_cagr"], ascending=False).iloc[0]
        reason = "all predeclared return, risk, temporal, issuer, and adjusted-bootstrap gates"
    else:
        selected_row = screen[screen.candidate != control].sort_values(
            ["worst_missing_bundle_recent_cagr", "recent_cagr"], ascending=False
        ).iloc[0]
        reason = "no candidate passed all gates; strongest five-issuer diagnostic only"
    selected = str(selected_row.candidate)
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = ensemble.build_path(
            context, mixed_cache[selected], scenario=scenario, cost=int(cost)
        )[0]
    screen.sort_values(["all_candidate_gates", "worst_missing_bundle_recent_cagr", "recent_cagr"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    pd.concat(overlap_detail, ignore_index=True).to_csv(OUTPUT / "overlap_by_decision.csv", index=False)
    pd.DataFrame(missing_rows).to_csv(OUTPUT / "missing_issuer_bundles.csv", index=False)
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    target_cache[selected].rename_axis("Date").to_csv(OUTPUT / "selected_strategy_target_weights.csv")
    pd.DataFrame([{"rebalance_at": date, "cik10": cik, "intended_weight": weight}
                  for date, row in mixed_cache[selected].items() for cik, weight in row.items()]).to_csv(
        OUTPUT / "selected_stock_target_weights.csv", index=False
    )
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_config_sha256": sha256(CONFIG), "candidate_count": int(len(screen)),
        "selected_candidate": selected, "selection_reason": reason,
        "selected_metrics": {key: (bool(value) if isinstance(value, (bool, np.bool_)) else float(value) if isinstance(value, (float, np.floating)) else int(value) if isinstance(value, (int, np.integer)) else value)
                             for key, value in selected_row.to_dict().items()},
        "candidate_level_gates_passed": bool(selected_row.all_candidate_gates),
        "control_exact_reproduction": bool(control_exact), "runtime": runtime,
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
        "artifact_sha256": {"screening": sha256(OUTPUT / "screening.csv"),
                            "selected_path": sha256(OUTPUT / "selected_path__50bps.csv"),
                            "overlap": sha256(OUTPUT / "overlap_by_decision.csv"),
                            "stock_targets": sha256(OUTPUT / "selected_stock_target_weights.csv")}
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Cross-component overlap budget v1\n\n"
        f"The frozen batch tested {len(screen)} generic overlap constructions. `{selected}` returned "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"Its latest cohort had {int(selected_row.latest_distinct_holdings)} distinct holdings and its worst "
        f"five-issuer stress returned {selected_row.worst_missing_bundle_recent_cagr:.2%}.\n\n"
        f"Complete candidate gates: **{'PASS' if bool(selected_row.all_candidate_gates) else 'FAIL'}**. "
        "No promotion or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
