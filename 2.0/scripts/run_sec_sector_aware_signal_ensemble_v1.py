#!/usr/bin/env python3
"""Apply generic sector-aware selection to the fixed signal-neighborhood ensemble."""

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
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_cluster_aware_cash_sleeve_v1 as challenger
import run_sec_cluster_challenger_locked_audit_v1 as locked
import run_sec_signal_neighborhood_ensemble_v1 as ensemble
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_sector_aware_signal_ensemble_v1.json"
PREDECESSOR = ROOT / "evidence/sec_regime_increment_tranching_v1/selected_path__50bps.csv"
SOURCE = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1"
OUTPUT = ROOT / "evidence/sec_sector_aware_signal_ensemble_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sector_capped_cohorts(scores: pd.DataFrame, breadth: int, sector_cap: float, banned: set[str] | None = None) -> pd.DataFrame:
    source = scores[~scores.cik10.isin(banned)] if banned else scores
    rows = []
    limit = int(math.floor(float(sector_cap) * int(breadth) + 1e-12))
    for _, frame in source.groupby("decision_at", sort=True):
        ranked = frame.sort_values(["score", "cik10"], ascending=[False, True])
        chosen_ciks, counts = [], {}
        for row in ranked.itertuples(index=False):
            sector = str(row.sector)
            if counts.get(sector, 0) < limit:
                chosen_ciks.append(str(row.cik10))
                counts[sector] = counts.get(sector, 0) + 1
            if len(chosen_ciks) == int(breadth):
                break
        chosen = ranked[ranked.cik10.astype(str).isin(chosen_ciks)].copy()
        order = {cik: position for position, cik in enumerate(chosen_ciks)}
        chosen["_order"] = chosen.cik10.astype(str).map(order)
        rows.append(chosen.sort_values("_order").drop(columns="_order"))
    return pd.concat(rows, ignore_index=True)


def component_targets(context: dict, config: dict, cash_cap: float, balance_cap: float,
                      banned: set[str] | None = None) -> tuple[dict, dict]:
    import run_sec_multisignal_company_rank_v1 as multisignal
    panel = multisignal.normalized_score_panel(context["scores"])
    definitions = {
        "cash100": {"cash_conversion": 1.0},
        "balance20": {"cash_conversion": 0.8, "balance_sheet_quality": 0.2},
    }
    caps = {"cash100": float(cash_cap), "balance20": float(balance_cap)}
    targets, choices = {}, {}
    for name, definition in definitions.items():
        scores = challenger.blended_membership_scores(panel, {"name": name, **definition})
        cohorts = sector_capped_cohorts(scores, int(config["breadth"]), caps[name], banned)
        targets[name], choices[name] = challenger.build_weighted_targets(
            cohorts, context["weekly"], context["index"], "equal", 26, 0.0, 1.0
        )
    return targets, choices


def latest_sector_share(mixed: dict, choices: dict) -> float:
    latest = max(mixed)
    sector_map = pd.concat(list(choices.values())).drop_duplicates("cik10").set_index("cik10").sector.to_dict()
    totals = {}
    for cik, weight in mixed[latest].items():
        sector = str(sector_map.get(cik, "unknown"))
        totals[sector] = totals.get(sector, 0.0) + float(weight)
    return float(max(totals.values()))


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context = locked.build_context({"membership_weights": {"cash_conversion": 0.8, "balance_sheet_quality": 0.2}})
    predecessor = pd.read_csv(PREDECESSOR, parse_dates=["Date"]).set_index("Date")
    source_path = pd.read_csv(ROOT / "evidence/sec_signal_neighborhood_ensemble_v1/selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    worst_order = list(pd.read_csv(SOURCE / "leave_one_company_out.csv", dtype={"cik10": str}).sort_values("recent_cagr").cik10)
    rows, paths, targets, mixed_cache, choices_cache, missing_detail = [], {}, {}, {}, {}, {}
    for spec in config["constructions"]:
        name = str(spec["name"])
        components, choices = component_targets(context, config, spec["cash_sector_cap"], spec["balance_sector_cap"])
        mixed = ensemble.mix_targets(components, {"cash100": 0.5, "balance20": 0.5})
        mixed_cache[name], choices_cache[name] = mixed, choices
        current, target, peak = ensemble.build_path(context, mixed)
        severe, _, _ = ensemble.build_path(context, mixed, cost=200)
        paths[(name, "base", 50)], paths[(name, "base", 200)], targets[name] = current, severe, target
        recent, severe_recent = ensemble.recent_metric(current), ensemble.recent_metric(severe)
        full = locked.compound_metrics(current.net_return)
        delay_values = []
        for delay in config["increment_delays_weeks"]:
            delay_values.append(ensemble.recent_metric(ensemble.build_path(context, mixed, increment_delay=int(delay))[0])["annualized_return"])
        for delay in config["decision_delays_weeks"]:
            delay_values.append(ensemble.recent_metric(ensemble.build_path(context, mixed, decision_delay=int(delay))[0])["annualized_return"])
        joined = locked.aligned_returns(current, predecessor)
        rolling26, _ = locked.rolling_outperformance(joined, 26)
        bundle_rows = []
        for size in config["missing_issuer_bundle_sizes"]:
            banned = set(worst_order[:int(size)])
            altered, _ = component_targets(context, config, spec["cash_sector_cap"], spec["balance_sector_cap"], banned)
            altered_mixed = ensemble.mix_targets(altered, {"cash100": 0.5, "balance20": 0.5})
            altered_path = ensemble.build_path(context, altered_mixed)[0]
            metric = ensemble.recent_metric(altered_path)
            bundle_rows.append({"candidate": name, "bundle_size": int(size),
                                "recent_cagr": metric["annualized_return"]})
        missing_detail[name] = pd.DataFrame(bundle_rows)
        rows.append({
            "candidate": name, "cash_sector_cap": float(spec["cash_sector_cap"]),
            "balance_sector_cap": float(spec["balance_sector_cap"]),
            "recent_cagr": recent["annualized_return"], "recent_sharpe": recent["sharpe"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["annualized_return"],
            "severe_recent_cagr": severe_recent["annualized_return"],
            "worst_delay_recent_cagr": min(delay_values),
            "endpoint_outperformance_share": ensemble.endpoint_share(current, predecessor, config["trailing_endpoint_offsets_weeks"]),
            "rolling26_outperformance_share": rolling26,
            "worst_missing_bundle_recent_cagr": min(row["recent_cagr"] for row in bundle_rows),
            "peak_total_stock_weight": float(target.cash_conversion.max() * peak),
            "latest_max_sector_share": latest_sector_share(mixed, choices),
            "latest_distinct_holdings": int(len(mixed[max(mixed)])),
        })
    screen = pd.DataFrame(rows)
    control = "uncapped_control"
    control_exact = np.allclose(paths[(control, "base", 50)].net_return.reindex(source_path.index),
                                source_path.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not control_exact:
        raise RuntimeError("uncapped sector control failed exact ensemble reproduction")
    gates = config["gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr >= float(gates["minimum_severe_recent_cagr"]))
        & (screen.worst_delay_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.endpoint_outperformance_share >= float(gates["minimum_endpoint_outperformance_share"]))
        & (screen.rolling26_outperformance_share >= float(gates["minimum_rolling_26w_outperformance_share"]))
        & (screen.worst_missing_bundle_recent_cagr >= float(gates["minimum_worst_five_issuer_cagr"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    pool = screen[(screen.candidate != control) & screen.surface_gates]
    reason = "all return, temporal, concentration, and five-issuer gates"
    if pool.empty:
        pool = screen[screen.candidate != control]
        reason = "no sector-aware construction passed all gates; best joint issuer/endpoint diagnostic"
    selected_row = pool.assign(
        _issuer_rank=pool.worst_missing_bundle_recent_cagr.round(12)
    ).sort_values(
        ["_issuer_rank", "endpoint_outperformance_share", "recent_cagr"], ascending=False
    ).iloc[0]
    selected = str(selected_row.candidate)
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = ensemble.build_path(
            context, mixed_cache[selected], scenario=scenario, cost=int(cost)
        )[0]
    selected_missing = missing_detail[selected]
    joined = locked.aligned_returns(paths[(selected, "base", 50)], predecessor)
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(locked.controller.stable_excess_returns(joined.iloc[-52:]), int(block),
        int(config["bootstrap_draws"]), int(config["bootstrap_seed"])) for block in config["bootstrap_blocks_weeks"]])
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    checks = {
        "control_reproduces_endpoint_ensemble": bool(control_exact),
        "selected_surface_gates_passed": bool(selected_row.surface_gates),
        "worst_five_issuer_bundle_beats_112pct_base": float(selected_row.worst_missing_bundle_recent_cagr) >= float(gates["minimum_worst_five_issuer_cagr"]),
        "bootstrap_4w_at_least_95pct": b4 >= float(config["minimum_bootstrap_probability"]),
        "bootstrap_13w_at_least_95pct": b13 >= float(config["minimum_bootstrap_probability"]),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_strategy_target_weights.csv")
    pd.DataFrame([{"rebalance_at": date, "cik10": cik, "intended_weight": weight}
                  for date, row in mixed_cache[selected].items() for cik, weight in row.items()]).to_csv(
        OUTPUT / "selected_stock_target_weights.csv", index=False)
    screen.sort_values(["surface_gates", "worst_missing_bundle_recent_cagr", "endpoint_outperformance_share"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    pd.concat(list(missing_detail.values()), ignore_index=True).to_csv(OUTPUT / "missing_issuer_bundles.csv", index=False)
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
        "worst_missing_bundle_recent_cagr": float(selected_row.worst_missing_bundle_recent_cagr),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "latest_max_sector_share": float(selected_row.latest_max_sector_share),
        "latest_distinct_holdings": int(selected_row.latest_distinct_holdings),
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
        "# Sector-aware signal ensemble v1\n\n"
        f"Tested {len(screen)} generic sector limits around the unchanged 50/50 holdings ensemble. `{selected}` returned "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"The latest maximum sector share was {selected_row.latest_max_sector_share:.2%}.\n\n"
        f"Endpoint/rolling-26 shares were {selected_row.endpoint_outperformance_share:.2%}/"
        f"{selected_row.rolling26_outperformance_share:.2%}; the worst five-issuer stress returned "
        f"{selected_row.worst_missing_bundle_recent_cagr:.2%}. Complete falsification: "
        f"**{'PASS' if all_passed else 'FAIL'}**. No promotion or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
