#!/usr/bin/env python3
"""Locked retrospective audit of the 123.71% SEC cluster challenger."""

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
import run_sec_multisignal_company_rank_v1 as multisignal
import run_sec_cluster_aware_cash_sleeve_v1 as challenger
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_cluster_challenger_locked_audit_v1.json"
FACTORS = ROOT / "evidence/sec_independent_fundamental_discovery_v1/factor_scores.csv"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
CANDIDATE = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1"
PREDECESSOR = ROOT / "evidence/sec_regime_increment_tranching_v1"
BASE_CONTROL = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1/selected_path__50bps.csv"
FROZEN = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_cluster_challenger_locked_audit_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compound_metrics(returns: pd.Series) -> dict[str, float | int]:
    values = returns.dropna().astype(float)
    if values.empty:
        return {"weeks": 0, "total_return": 0.0, "annualized_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    wealth = (1.0 + values).cumprod()
    years = len(values) / 52.0
    annual = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else 0.0
    std = float(values.std(ddof=1))
    sharpe = float(values.mean() / std * np.sqrt(52.0)) if std > 0 else 0.0
    drawdown = float((wealth / wealth.cummax() - 1.0).min())
    return {"weeks": int(len(values)), "total_return": float(wealth.iloc[-1] - 1.0),
            "annualized_return": annual, "sharpe": sharpe, "max_drawdown": drawdown}


def shift_targets(targets: dict[pd.Timestamp, dict[str, float]], index: pd.DatetimeIndex, weeks: int) -> dict[pd.Timestamp, dict[str, float]]:
    shifted = {}
    positions = {date: position for position, date in enumerate(index)}
    for date, weights in targets.items():
        position = positions[pd.Timestamp(date)] + int(weeks)
        if position < len(index):
            shifted[index[position]] = dict(weights)
    return shifted


def aligned_returns(candidate_path: pd.DataFrame, control_path: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([
        candidate_path.net_return.rename("candidate"),
        control_path.net_return.rename("control"),
    ], axis=1).dropna()


def rolling_outperformance(joined: pd.DataFrame, weeks: int) -> tuple[float, int]:
    rolling = (1.0 + joined).rolling(int(weeks), min_periods=int(weeks)).apply(np.prod, raw=True) - 1.0
    complete = rolling.dropna()
    return float((complete.candidate > complete.control + 1e-12).mean()), int(len(complete))


def build_context(config: dict) -> dict:
    scores = pd.read_csv(FACTORS, dtype={"cik10": str}, parse_dates=["decision_at"])
    panel = multisignal.normalized_score_panel(scores)
    blend = {"name": "locked", **config["membership_weights"]}
    membership = challenger.blended_membership_scores(panel, blend)
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
    leaders = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(["base", "adverse"], [50, 100, 200])
    }
    breadth_signals = controller.breadth_dispersion_signals(weekly, 26)
    breadth_high = controller.regime_state(breadth_signals, 26, 0.4, "breadth_high")
    fast_features = challenger._fast_features(weekly, index)
    return {"scores": scores, "membership": membership, "index": index, "weekly": weekly,
            "leaders": leaders, "breadth_signals": breadth_signals,
            "breadth_high": breadth_high, "fast_features": fast_features}


def build_locked_path(
    context: dict,
    config: dict,
    banned: set[str] | None = None,
    decision_delay: int = 0,
    increment_delay: int = 0,
    cost: int = 50,
    scenario: str = "base",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    membership = context["membership"]
    if banned:
        membership = membership[~membership.cik10.isin(set(banned))]
    cohorts = challenger.selected_cohorts(membership, int(config["breadth"]))
    targets, choices = challenger.build_weighted_targets(
        cohorts, context["weekly"], context["index"], "equal", 26, 0.0, 1.0
    )
    if decision_delay:
        targets = shift_targets(targets, context["index"], int(decision_delay))
    sleeve, _ = cohort.simulate_weighted_cash(context["weekly"], targets, scenario, float(cost))
    strategy_target, _ = cohort.strategy_target(
        context["leaders"][("base", 50)], sleeve if scenario == "base" and cost == 50 else
        cohort.simulate_weighted_cash(context["weekly"], targets, "base", 50.0)[0],
        context["breadth_signals"], context["breadth_high"], context["fast_features"], 11, int(increment_delay),
    )
    path = controller.simulate_composite(
        context["leaders"][(scenario, int(cost))], sleeve, strategy_target, float(cost)
    )
    return path, strategy_target, choices


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    context = build_context(config)
    rebuilt, rebuilt_target, rebuilt_choices = build_locked_path(context, config)
    saved = pd.read_csv(CANDIDATE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    predecessor = pd.read_csv(PREDECESSOR / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    base_path = pd.read_csv(BASE_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen = pd.read_csv(FROZEN, parse_dates=["Date"]).set_index("Date")
    exact_rebuild = np.allclose(rebuilt.net_return.reindex(saved.index), saved.net_return,
                                rtol=0, atol=1e-12, equal_nan=True)
    if not exact_rebuild:
        raise RuntimeError("locked candidate failed exact reconstruction")
    joined = aligned_returns(saved, predecessor)

    # Three non-overlapping 52-week pseudo-holdouts, evaluated without any reselection.
    block_rows = []
    for block in range(3):
        finish = len(joined) - block * 52
        start = finish - 52
        frame = joined.iloc[start:finish]
        for asset in ["candidate", "control"]:
            block_rows.append({"block": 2 - block, "start": frame.index.min(), "end": frame.index.max(),
                               "asset": asset, **compound_metrics(frame[asset])})
    blocks = pd.DataFrame(block_rows).sort_values(["block", "asset"])
    block_pivot = blocks.pivot(index="block", columns="asset", values="annualized_return")
    positive_blocks = int((block_pivot.candidate > 0).sum())
    beating_blocks = int((block_pivot.candidate > block_pivot.control).sum())

    rolling_rows = []
    for weeks in config["rolling_windows_weeks"]:
        share, count = rolling_outperformance(joined, int(weeks))
        rolling_rows.append({"window_weeks": int(weeks), "outperformance_share": share, "completed_windows": count})
    rolling = pd.DataFrame(rolling_rows)

    endpoint_rows = []
    for offset in config["trailing_endpoint_offsets_weeks"]:
        finish = len(joined) - int(offset)
        frame = joined.iloc[max(0, finish - 52):finish]
        candidate_metric, control_metric = compound_metrics(frame.candidate), compound_metrics(frame.control)
        endpoint_rows.append({"offset_weeks": int(offset), "start": frame.index.min(), "end": frame.index.max(),
                              "candidate_cagr": candidate_metric["annualized_return"],
                              "control_cagr": control_metric["annualized_return"],
                              "candidate_beats": candidate_metric["annualized_return"] > control_metric["annualized_return"]})
    endpoints = pd.DataFrame(endpoint_rows)
    endpoint_share = float(endpoints.candidate_beats.mean())

    # Remove each 13-week quarter from the trailing year and annualize the remaining 39 weeks.
    recent = joined.iloc[-52:]
    quarter_rows = []
    for quarter in range(4):
        keep = pd.Series(True, index=recent.index)
        keep.iloc[quarter * 13:(quarter + 1) * 13] = False
        candidate_metric = compound_metrics(recent.loc[keep, "candidate"])
        control_metric = compound_metrics(recent.loc[keep, "control"])
        quarter_rows.append({"removed_quarter": quarter + 1,
                             "removed_start": recent.index[quarter * 13],
                             "removed_end": recent.index[(quarter + 1) * 13 - 1],
                             "candidate_cagr": candidate_metric["annualized_return"],
                             "control_cagr": control_metric["annualized_return"],
                             "candidate_beats": candidate_metric["annualized_return"] > control_metric["annualized_return"]})
    quarter_ablation = pd.DataFrame(quarter_rows)
    quarter_share = float(quarter_ablation.candidate_beats.mean())

    delay_rows = []
    for kind, values in [("decision", config["decision_delays_weeks"]),
                         ("increment", config["increment_delays_weeks"]),
                         ("combined", config["combined_delays_weeks"])]:
        for weeks in values:
            path, _, _ = build_locked_path(
                context, config,
                decision_delay=int(weeks) if kind in {"decision", "combined"} else 0,
                increment_delay=int(weeks) if kind in {"increment", "combined"} else 0,
            )
            metric = compound_metrics(path.net_return.iloc[-52:])
            delay_rows.append({"delay_type": kind, "delay_weeks": int(weeks),
                               "recent_cagr": metric["annualized_return"], "recent_sharpe": metric["sharpe"],
                               "recent_drawdown": metric["max_drawdown"]})
    delays = pd.DataFrame(delay_rows)

    prior_loo = pd.read_csv(CANDIDATE / "leave_one_company_out.csv", dtype={"cik10": str})
    worst_order = list(prior_loo.sort_values("recent_cagr").cik10)
    missing_rows = []
    for size in config["missing_issuer_bundle_sizes"]:
        banned = set(worst_order[:int(size)])
        path, _, _ = build_locked_path(context, config, banned=banned)
        metric = compound_metrics(path.net_return.iloc[-52:])
        missing_rows.append({"bundle_size": int(size), "banned_ciks": "|".join(sorted(banned)),
                             "recent_cagr": metric["annualized_return"], "recent_sharpe": metric["sharpe"],
                             "recent_drawdown": metric["max_drawdown"]})
    missing = pd.DataFrame(missing_rows)

    cost_rows = []
    for cost in [50, 100, 200]:
        path = pd.read_csv(CANDIDATE / f"selected_path__{cost}bps.csv", parse_dates=["Date"]).set_index("Date")
        metric = compound_metrics(path.net_return.iloc[-52:])
        cost_rows.append({"cost_bps": cost, "recent_cagr": metric["annualized_return"],
                          "recent_sharpe": metric["sharpe"], "recent_drawdown": metric["max_drawdown"]})
    costs = pd.DataFrame(cost_rows)

    recent_joined = joined.iloc[-52:]
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(controller.stable_excess_returns(recent_joined), int(block),
        int(config["bootstrap_draws"]), int(config["bootstrap_seed"])) for block in config["bootstrap_blocks_weeks"]])
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    gates = config["gates"]
    checks = {
        "locked_candidate_rebuilt_exactly": bool(exact_rebuild),
        "all_three_52w_blocks_positive": positive_blocks >= int(gates["minimum_positive_nonoverlapping_52w_blocks"]),
        "at_least_two_52w_blocks_beat_predecessor": beating_blocks >= int(gates["minimum_blocks_beating_predecessor"]),
        "all_rolling_horizons_at_least_50pct": bool((rolling.outperformance_share >= float(gates["minimum_rolling_outperformance_share"])).all()),
        "endpoint_outperformance_at_least_60pct": endpoint_share >= float(gates["minimum_endpoint_outperformance_share"]),
        "quarter_ablation_outperformance_at_least_75pct": quarter_share >= float(gates["minimum_quarter_ablation_outperformance_share"]),
        "all_delays_beat_112pct_base": bool((delays.recent_cagr >= float(gates["minimum_delay_recent_cagr"])).all()),
        "all_missing_bundles_beat_112pct_base": bool((missing.recent_cagr >= float(gates["minimum_missing_bundle_recent_cagr"])).all()),
        "200bps_beats_frozen_incumbent": float(costs.loc[costs.cost_bps == 200, "recent_cagr"].iloc[0]) >= float(gates["minimum_severe_cost_recent_cagr"]),
        "bootstrap_4w_at_least_95pct": b4 >= float(gates["minimum_bootstrap_probability"]),
        "bootstrap_13w_at_least_95pct": b13 >= float(gates["minimum_bootstrap_probability"]),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    blocks.to_csv(OUTPUT / "nonoverlapping_52w_blocks.csv", index=False)
    rolling.to_csv(OUTPUT / "rolling_outperformance.csv", index=False)
    endpoints.to_csv(OUTPUT / "trailing_endpoint_perturbation.csv", index=False)
    quarter_ablation.to_csv(OUTPUT / "quarter_ablation.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    missing.to_csv(OUTPUT / "missing_issuer_bundles.csv", index=False)
    costs.to_csv(OUTPUT / "cost_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    rebuilt.rename_axis("Date").to_csv(OUTPUT / "rebuilt_locked_path__50bps.csv")
    rebuilt_target.rename_axis("Date").to_csv(OUTPUT / "rebuilt_strategy_target_weights.csv")
    rebuilt_choices.to_csv(OUTPUT / "rebuilt_stock_target_weights.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate": config["candidate"], "history_start": str(joined.index.min().date()),
        "history_end": str(joined.index.max().date()), "history_weeks": int(len(joined)),
        "history_classification": "retrospective pseudo-holdout; not untouched forward evidence",
        "positive_nonoverlapping_52w_blocks": positive_blocks,
        "nonoverlapping_52w_blocks_beating_predecessor": beating_blocks,
        "rolling_outperformance": {str(int(row.window_weeks)): float(row.outperformance_share) for row in rolling.itertuples()},
        "trailing_endpoint_outperformance_share": endpoint_share,
        "quarter_ablation_outperformance_share": quarter_share,
        "worst_delay_recent_cagr": float(delays.recent_cagr.min()),
        "worst_delay_case": str(delays.sort_values("recent_cagr").iloc[0].delay_type) + "_" + str(int(delays.sort_values("recent_cagr").iloc[0].delay_weeks)) + "w",
        "worst_missing_bundle_recent_cagr": float(missing.recent_cagr.min()),
        "worst_missing_bundle_size": int(missing.sort_values("recent_cagr").iloc[0].bundle_size),
        "severe_200bps_recent_cagr": float(costs.loc[costs.cost_bps == 200, "recent_cagr"].iloc[0]),
        "bootstrap_4w_probability_positive_vs_predecessor": b4,
        "bootstrap_13w_probability_positive_vs_predecessor": b13,
        "checks": checks, "all_locked_audit_checks_passed": all_passed,
        "runtime": runtime,
        "artifact_sha256": {
            "source_candidate_path": sha256(CANDIDATE / "selected_path__50bps.csv"),
            "rebuilt_candidate_path": sha256(OUTPUT / "rebuilt_locked_path__50bps.csv"),
            "rolling_outperformance": sha256(OUTPUT / "rolling_outperformance.csv"),
            "delay_stress": sha256(OUTPUT / "delay_stress.csv"),
            "missing_issuer_bundles": sha256(OUTPUT / "missing_issuer_bundles.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Locked cluster challenger audit v1\n\n"
        f"The fixed 80/20 top-20 challenger was reconstructed exactly and audited over {len(joined)} weeks without "
        f"parameter reselection. It was positive in {positive_blocks}/3 non-overlapping 52-week pseudo-holdouts and beat "
        f"the 119.22% predecessor in {beating_blocks}/3. The worst execution/increment-delay case returned "
        f"{delays.recent_cagr.min():.2%}; simultaneously removing the five historically most damaging issuers left "
        f"{missing.recent_cagr.min():.2%}.\n\n"
        f"Endpoint and quarter-ablation outperformance shares were {endpoint_share:.2%}/{quarter_share:.2%}. "
        f"Four/thirteen-week bootstrap probabilities were {b4:.2%}/{b13:.2%}. Complete locked audit: "
        f"**{'PASS' if all_passed else 'FAIL'}**. This history is retrospective and does not count as untouched forward evidence.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
