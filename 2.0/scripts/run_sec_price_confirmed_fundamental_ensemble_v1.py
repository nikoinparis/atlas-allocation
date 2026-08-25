#!/usr/bin/env python3
"""Test frozen residual/trend confirmation inside the fixed fundamental ensemble."""

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
sys.path.insert(0, str(ROOT / "src"))

import run_sec_cluster_aware_cash_sleeve_v1 as challenger
import run_sec_cluster_challenger_locked_audit_v1 as locked
import run_sec_form4_dynamic_overlay_v1 as audit
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_multisignal_company_rank_v1 as multisignal
import run_sec_sector_aware_signal_ensemble_v1 as sector_ensemble
import run_sec_signal_neighborhood_ensemble_v1 as ensemble
from systematic_trader.sec_return_improvement import residual_momentum_scores, trend_quality_scores

CONFIG = ROOT / "config/sec_price_confirmed_fundamental_ensemble_v1.json"
SOURCE = ROOT / "evidence/sec_sector_aware_signal_ensemble_v1"
PREDECESSOR = ROOT / "evidence/sec_regime_increment_tranching_v1/selected_path__50bps.csv"
WORST_ORDER = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1/leave_one_company_out.csv"
OUTPUT = ROOT / "evidence/sec_price_confirmed_fundamental_ensemble_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def price_signal_panels(context: dict, config: dict) -> dict[str, pd.DataFrame]:
    panel = multisignal.normalized_score_panel(context["scores"])
    sectors = panel.sort_values("decision_at").drop_duplicates("cik10", keep="last").set_index("cik10").sector.to_dict()
    rules = config["price_signals"]
    residual = residual_momentum_scores(
        context["weekly"], sectors,
        lookback_weeks=int(rules["residual_lookback_weeks"]),
        skip_weeks=int(rules["residual_skip_weeks"]),
        sector_weight=float(rules["sector_residual_weight"]),
        market_weight=float(rules["market_residual_weight"]),
        minimum_history_weeks=int(rules["minimum_history_weeks"]),
    )
    trend, _ = trend_quality_scores(
        context["weekly"],
        high_window_weeks=int(rules["trend_high_window_weeks"]),
        positive_week_window=int(rules["trend_positive_week_window"]),
        momentum_horizons_weeks=tuple(int(value) for value in rules["trend_momentum_horizons_weeks"]),
        skip_weeks=int(rules["trend_skip_weeks"]),
    )
    return {"residual": residual, "trend": trend, "residual_trend": (residual + trend) / 2.0}


def latest_price_score(signal: pd.DataFrame, decision: pd.Timestamp, ciks: pd.Series) -> pd.Series:
    timestamp = pd.Timestamp(decision).tz_localize(None) if pd.Timestamp(decision).tzinfo else pd.Timestamp(decision)
    eligible = signal.index[signal.index <= timestamp]
    if not len(eligible):
        return pd.Series(0.5, index=ciks.index, dtype=float)
    row = signal.loc[eligible[-1]]
    return ciks.astype(str).map(((row + 1.0) / 2.0).clip(0.0, 1.0)).fillna(0.5)


def scored_components(context: dict, config: dict, spec: dict, signals: dict,
                      banned: set[str] | None = None) -> tuple[dict, dict]:
    panel = multisignal.normalized_score_panel(context["scores"])
    definitions = {
        "cash100": panel.cash_conversion,
        "balance20": 0.8 * panel.cash_conversion + 0.2 * panel.balance_sheet_quality,
    }
    control = config["control"]
    caps = {"cash100": float(control["cash_component_sector_cap"]),
            "balance20": float(control["balance_component_sector_cap"])}
    price_family = str(spec["price_family"])
    price_weight = float(spec["price_weight"])
    targets, choices = {}, {}
    for name, fundamental in definitions.items():
        scores = panel[["decision_at", "cik10", "company_name_as_filed", "sector"]].copy()
        scores["score"] = fundamental.astype(float)
        if price_family != "none":
            additions = []
            for decision, frame in scores.groupby("decision_at", sort=True):
                additions.append(latest_price_score(signals[price_family], decision, frame.cik10))
            price_score = pd.concat(additions).sort_index().reindex(scores.index)
            scores["score"] = (1.0 - price_weight) * scores.score + price_weight * price_score
        cohorts = sector_ensemble.sector_capped_cohorts(
            scores, int(control["breadth"]), caps[name], banned
        )
        targets[name], choices[name] = challenger.build_weighted_targets(
            cohorts, context["weekly"], context["index"], "equal", 26, 0.0, 1.0
        )
    return targets, choices


def mixed_targets(context: dict, config: dict, spec: dict, signals: dict,
                  banned: set[str] | None = None) -> tuple[dict, dict]:
    components, choices = scored_components(context, config, spec, signals, banned)
    return ensemble.mix_targets(components, config["control"]["component_mix"]), choices


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context = locked.build_context({"membership_weights": {"cash_conversion": 0.8, "balance_sheet_quality": 0.2}})
    signals = price_signal_panels(context, config)
    predecessor = pd.read_csv(PREDECESSOR, parse_dates=["Date"]).set_index("Date")
    source_control = pd.read_csv(SOURCE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    worst_order = list(pd.read_csv(WORST_ORDER, dtype={"cik10": str}).sort_values("recent_cagr").cik10)
    specs = {str(spec["name"]): spec for spec in config["candidate_specs"]}
    rows, paths, mixed_cache, target_cache, missing_rows = [], {}, {}, {}, []
    challenger_count = int(config["multiple_testing"]["challenger_count"])
    gates = config["gates"]
    for name, spec in specs.items():
        mixed, _ = mixed_targets(context, config, spec, signals)
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
        bundle_metrics = []
        for size in config["missing_issuer_bundle_sizes"]:
            altered, _ = mixed_targets(context, config, spec, signals, set(worst_order[:int(size)]))
            metric = ensemble.recent_metric(ensemble.build_path(context, altered)[0])
            bundle_metrics.append(metric["annualized_return"])
            missing_rows.append({"candidate": name, "bundle_size": int(size),
                                 "banned_ciks": "|".join(worst_order[:int(size)]),
                                 "recent_cagr": metric["annualized_return"]})
        joined_recent = locked.aligned_returns(current, source_control).iloc[-52:]
        probabilities = [dynamic.block_bootstrap(
            joined_recent.candidate - joined_recent.control, int(block), int(config["bootstrap_draws"]), int(config["bootstrap_seed"])
        )["probability_positive"] for block in config["bootstrap_blocks_weeks"]]
        minimum_raw = float(min(probabilities))
        adjusted = 1.0 if name == "fundamental_control" else max(0.0, 1.0 - min(1.0, (1.0 - minimum_raw) * challenger_count))
        row = {
            "candidate": name, "price_family": spec["price_family"], "price_weight": float(spec["price_weight"]),
            "recent_cagr": recent["annualized_return"], "recent_sharpe": recent["sharpe"],
            "recent_drawdown": recent["max_drawdown"], "full_cagr": full["annualized_return"],
            "severe_recent_cagr": severe_recent["annualized_return"], "worst_delay_recent_cagr": min(delays),
            "endpoint_outperformance_share": ensemble.endpoint_share(current, source_control, config["endpoint_offsets_weeks"]),
            "rolling26_outperformance_share": rolling26, "rolling26_windows": windows26,
            "worst_missing_bundle_recent_cagr": min(bundle_metrics),
            "peak_total_stock_weight": float(target.cash_conversion.max() * peak),
            "latest_distinct_holdings": int(len(mixed[max(mixed)])),
            "minimum_raw_bootstrap_probability": minimum_raw,
            "bonferroni_adjusted_probability": adjusted,
        }
        row["all_candidate_gates"] = bool(
            name != "fundamental_control"
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
            and row["bonferroni_adjusted_probability"] >= float(gates["minimum_adjusted_bootstrap_probability"])
        )
        rows.append(row)
    screen = pd.DataFrame(rows)
    control_exact = np.allclose(paths[("fundamental_control", "base", 50)].net_return.reindex(source_control.index),
                                source_control.net_return, rtol=0, atol=1e-12, equal_nan=True)
    if not control_exact:
        raise RuntimeError("fundamental control failed exact source reproduction")
    passers = screen[screen.all_candidate_gates]
    if len(passers):
        selected_row = passers.sort_values(["recent_cagr", "recent_sharpe"], ascending=False).iloc[0]
        reason = "all predeclared return, risk, temporal, issuer, and adjusted-bootstrap gates"
    else:
        selected_row = screen[screen.candidate != "fundamental_control"].sort_values(
            ["recent_cagr", "recent_sharpe"], ascending=False).iloc[0]
        reason = "no candidate passed all gates; highest-return diagnostic only"
    selected = str(selected_row.candidate)
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = ensemble.build_path(
            context, mixed_cache[selected], scenario=scenario, cost=int(cost)
        )[0]
    screen.sort_values(["all_candidate_gates", "recent_cagr", "recent_sharpe"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
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
                            "stock_targets": sha256(OUTPUT / "selected_stock_target_weights.csv")}
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Price-confirmed fundamental ensemble v1\n\n"
        f"The frozen batch tested {len(screen)} fundamental/residual/trend combinations. `{selected}` returned "
        f"{selected_row.recent_cagr:.2%} recent CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"{selected_row.recent_drawdown:.2%} drawdown, and {selected_row.full_cagr:.2%} full CAGR. "
        f"Its worst five-issuer stress was {selected_row.worst_missing_bundle_recent_cagr:.2%}.\n\n"
        f"Complete candidate gates: **{'PASS' if bool(selected_row.all_candidate_gates) else 'FAIL'}**. "
        "No promotion or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
