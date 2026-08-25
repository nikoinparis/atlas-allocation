#!/usr/bin/env python3
"""Diversify only the stabilized regime increment across independent SEC sleeves."""

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
import run_sec_regime_increment_tranching_v1 as tranche
import run_sec_breadth_dispersion_allocation_controller_v1 as controller
import run_sec_form4_dynamic_overlay_v1 as audit
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner
import run_sec_independent_market_regime_activation_v1 as regime

CONFIG = ROOT / "config/sec_increment_sleeve_diversification_v1.json"
FACTORS = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
BASE = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1"
INCUMBENT = ROOT / "evidence/sec_regime_increment_tranching_v1"
FROZEN = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_increment_sleeve_diversification_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recent_metric(name: str, scenario: str, cost: int, path: pd.DataFrame) -> dict:
    return next(row for row in base.metric_rows(name, scenario, cost, path) if row["window"] == "trailing_1y")


def fixed_route(index: pd.DatetimeIndex, families: list[str], cash_share: float) -> pd.DataFrame:
    route = pd.DataFrame(0.0, index=index, columns=["cash_conversion", *families])
    route["cash_conversion"] = float(cash_share)
    if families:
        route[families] = (1.0 - float(cash_share)) / len(families)
    return route


def causal_inverse_vol_route(
    returns: pd.DataFrame,
    families: list[str],
    cash_share: float,
    window: int,
) -> pd.DataFrame:
    """Route weights at t use sleeve returns ending no later than t-1."""
    volatility = returns[families].shift(1).rolling(int(window), min_periods=int(window)).std(ddof=1)
    inverse = 1.0 / volatility.replace(0.0, np.nan)
    normalized = inverse.div(inverse.sum(axis=1), axis=0)
    normalized = normalized.fillna(1.0 / len(families))
    route = pd.DataFrame(0.0, index=returns.index, columns=["cash_conversion", *families])
    route["cash_conversion"] = float(cash_share)
    route[families] = normalized * (1.0 - float(cash_share))
    return route


def routed_target(base_target: pd.DataFrame, increment: pd.Series, route: pd.DataFrame) -> pd.DataFrame:
    index = base_target.index.intersection(route.index)
    result = pd.DataFrame(0.0, index=index, columns=["leader", *route.columns])
    extra = increment.reindex(index).fillna(0.0).clip(lower=0.0)
    result["cash_conversion"] = base_target.cash_conversion.reindex(index).fillna(0.0) + extra * route.cash_conversion.reindex(index)
    for family in route.columns.drop("cash_conversion"):
        result[family] = extra * route[family].reindex(index)
    result["leader"] = 1.0 - result.drop(columns="leader").sum(axis=1)
    return result


def actual_increment(
    base_target: pd.DataFrame,
    raw_increment: pd.Series,
    delay: int = 0,
) -> pd.Series:
    target, _ = tranche.tranche_target(
        base_target, raw_increment, 1.0, 4, "symmetric_equal", 0.8, int(delay)
    )
    return (target.cash_conversion - base_target.cash_conversion).clip(lower=0.0)


def simulate(returns: pd.DataFrame, target: pd.DataFrame, cost: float) -> pd.DataFrame:
    index = returns.dropna().index.intersection(target.index)
    return dynamic.simulate(returns.reindex(index), target.reindex(index), float(cost))


def concentration_bound(
    base_target: pd.DataFrame,
    increment: pd.Series,
    route: pd.DataFrame,
    cash_internal_peak: float,
) -> float:
    """Conservative bound allowing the same issuer to overlap across every routed sleeve."""
    index = base_target.index.intersection(route.index)
    cash = base_target.cash_conversion.reindex(index) + increment.reindex(index) * route.cash_conversion.reindex(index)
    other = increment.reindex(index) * route.drop(columns="cash_conversion").sum(axis=1).reindex(index)
    return float((cash * float(cash_internal_peak) + other * 0.10).max())


def route_specs(index: pd.DatetimeIndex, returns: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    families = list(config["independent_families"])
    specs = {"cash100_control": fixed_route(index, families, 1.0)}
    for family in families:
        for cash_share in config["pair_cash_shares"]:
            name = f"cash{int(cash_share*100):02d}__{family}{int((1-cash_share)*100):02d}"
            specs[name] = fixed_route(index, [family], float(cash_share)).reindex(columns=["cash_conversion", *families], fill_value=0.0)
    for cash_share in config["fixed_cash_shares"]:
        name = f"cash{int(cash_share*100):02d}__equal_independent"
        specs[name] = fixed_route(index, families, float(cash_share))
    for window, cash_share in itertools.product(
        config["inverse_volatility_windows_weeks"], config["inverse_volatility_cash_shares"]
    ):
        name = f"cash{int(cash_share*100):02d}__invvol{int(window)}w"
        specs[name] = causal_inverse_vol_route(returns, families, float(cash_share), int(window))
    return specs


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    families = list(config["independent_families"])
    base_target = pd.read_csv(BASE / "selected_target_weights.csv", parse_dates=["Date"]).set_index("Date")
    increment_panel = pd.read_csv(INCUMBENT / "selected_increment_panel.csv", parse_dates=["Date"]).set_index("Date")
    raw_increment = increment_panel.raw_increment.reindex(base_target.index).fillna(0.0)
    increment = actual_increment(base_target, raw_increment)
    incumbent = pd.read_csv(INCUMBENT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    base_path = pd.read_csv(BASE / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    frozen = pd.read_csv(FROZEN, parse_dates=["Date"]).set_index("Date")
    incumbent_recent = recent_metric("incumbent", "base", 50, incumbent)
    base_recent = recent_metric("base", "base", 50, base_path)
    frozen_recent = recent_metric("frozen", "base", 50, frozen)

    sleeve_paths = {}
    scores = pd.read_csv(FACTORS / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    cash_scores = scores[scores.family == "cash_conversion"].copy()
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    weekly_index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    sources, terminals = base.price_sources(), base.terminal_dates()
    issuer_prices = {}
    for cik in sorted(set(cash_scores.cik10)):
        if cik in sources:
            source, path = sources[cik]
            try:
                issuer_prices[cik] = base.read_weekly_price(path, source, weekly_index, terminals.get(cik))
            except OSError:
                issuer_prices[cik] = pd.Series(np.nan, index=weekly_index)
    cash_weekly = pd.DataFrame(issuer_prices, index=weekly_index)
    cash_choices = breadth_runner.make_choices(cash_scores, 20)
    cash_targets = base.build_targets(cash_choices, weekly_index)
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        sleeve_paths[("leader", scenario, int(cost))] = dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        sleeve_paths[("cash_conversion", scenario, int(cost))], _ = capped.simulate_cash(
            cash_weekly, cash_targets, scenario, float(cost), None, 20
        )
        sleeve_paths[("cash_conversion", scenario, int(cost))] = sleeve_paths[("cash_conversion", scenario, int(cost))].net_return
        for family in families:
            sleeve_paths[(family, scenario, int(cost))] = dynamic.read_path(
                FACTORS / f"path_{family}__{scenario}__{cost}bps.csv"
            ).net_return

    def returns_for(scenario: str, cost: int) -> pd.DataFrame:
        return pd.DataFrame({
            asset: sleeve_paths[(asset, scenario, int(cost))]
            for asset in ["leader", "cash_conversion", *families]
        }).dropna()

    signal_returns = returns_for("base", 50)
    specs = route_specs(base_target.index, signal_returns, config)
    incumbent_cash_peak = float(json.loads((INCUMBENT / "result.json").read_text())["peak_total_stock_weight"])
    selected_cash_max = float(pd.read_csv(INCUMBENT / "selected_target_weights.csv").cash_conversion.max())
    cash_internal_peak = incumbent_cash_peak / selected_cash_max

    rows, targets, paths = [], {}, {}
    for name, route in specs.items():
        target = routed_target(base_target, increment, route)
        targets[name] = target
        current = simulate(returns_for("base", 50), target, 50.0)
        severe = simulate(returns_for("base", 200), target, 200.0)
        paths[(name, "base", 50)], paths[(name, "base", 200)] = current, severe
        recent = recent_metric(name, "base", 50, current)
        full = next(r for r in base.metric_rows(name, "base", 50, current) if r["window"] == "full_recent")
        severe_recent = recent_metric(name, "base", 200, severe)
        delays = {}
        for delay in config["falsification"]["increment_delays_weeks"]:
            delayed = actual_increment(base_target, raw_increment, int(delay))
            delayed_target = routed_target(base_target, delayed, route)
            delayed_path = simulate(returns_for("base", 50), delayed_target, 50.0)
            delays[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed_path)["cagr"]
        route_average = route.loc[increment > 1e-12].mean()
        row = {
            "candidate": name, "recent_cagr": recent["cagr"],
            "recent_sharpe": recent["sharpe_zero_rf"], "recent_drawdown": recent["max_drawdown"],
            "full_cagr": full["cagr"], "severe_recent_cagr": severe_recent["cagr"],
            "delay1_recent_cagr": delays[1], "delay2_recent_cagr": delays[2],
            "worst_current_delay_recent_cagr": min(recent["cagr"], delays[1], delays[2]),
            "peak_total_stock_weight_bound": concentration_bound(base_target, increment, route, cash_internal_peak),
            "annual_one_way_turnover": float(0.5 * target.diff().abs().sum(axis=1).mean() * 52.0),
        }
        row.update({f"average_increment_{asset}_share": float(route_average[asset]) for asset in route.columns})
        rows.append(row)

    screen = pd.DataFrame(rows)
    control = paths[("cash100_control", "base", 50)]
    control_matches = np.allclose(
        control.net_return.reindex(incumbent.index), incumbent.net_return,
        rtol=0, atol=1e-12, equal_nan=True,
    )
    if not control_matches:
        raise RuntimeError("cash-only route failed to reproduce the 119.22% incumbent challenger")
    gates = config["surface_gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.delay1_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.delay2_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr >= float(gates["minimum_severe_recent_cagr"]))
        & (screen.peak_total_stock_weight_bound <= float(gates["maximum_peak_total_stock_weight"]))
    )

    ablation_rows = []
    for name, route in specs.items():
        for asset in route.columns:
            if float(route[asset].max()) <= 0:
                continue
            ablated = route.copy()
            ablated[asset] = 0.0
            ablated_target = routed_target(base_target, increment, ablated)
            path = simulate(returns_for("base", 50), ablated_target, 50.0)
            metric = recent_metric(name, f"remove_{asset}", 50, path)
            ablation_rows.append({"candidate": name, "removed_sleeve": asset, "recent_cagr": metric["cagr"]})
    ablations = pd.DataFrame(ablation_rows)
    worst_ablation = ablations.groupby("candidate").recent_cagr.min().rename("worst_sleeve_removal_recent_cagr")
    screen = screen.merge(worst_ablation, on="candidate", how="left")
    screen["robust_floor"] = screen[[
        "recent_cagr", "delay1_recent_cagr", "delay2_recent_cagr", "worst_sleeve_removal_recent_cagr"
    ]].min(axis=1)
    noncontrol = screen[(screen.candidate != "cash100_control") & screen.surface_gates]
    if noncontrol.empty:
        selected = "cash100_control"
        reason = "no diversified construction passed all return, delay, cost, full-period, and concentration gates"
    else:
        selected = str(noncontrol.sort_values(["robust_floor", "recent_cagr", "full_cagr"], ascending=False).iloc[0].candidate)
        reason = "best robust floor among diversified surface passers"
    selected_row = screen.set_index("candidate").loc[selected]

    # Full selected-candidate company-removal falsification. Cash-sleeve removals
    # rebuild the established controller and raw increment; independent-sleeve
    # removals rerank the same point-in-time family before resimulation.
    selected_route = specs[selected]
    selected_assets = [asset for asset in selected_route.columns if float(selected_route[asset].max()) > 0]
    choices_by_asset = {"cash_conversion": cash_choices}
    for family in families:
        family_scores = scores[scores.family == family]
        choices_by_asset[family] = breadth_runner.make_choices(family_scores, 10)
    last_decision = max(frame.decision_at.max() for frame in choices_by_asset.values())
    recent_cutoff = last_decision - pd.DateOffset(years=1)
    recent_ciks = sorted(set().union(*[
        set(choices_by_asset[asset].loc[choices_by_asset[asset].decision_at >= recent_cutoff, "cik10"])
        for asset in selected_assets
    ]))
    breadth_signals = controller.breadth_dispersion_signals(cash_weekly, 26)
    breadth_high = controller.regime_state(breadth_signals, 26, 0.4, "breadth_high")
    etfs = regime.weekly_etf_prices(weekly_index)
    vix = pd.read_csv(regime.VIX, parse_dates=["Date"]).set_index("Date")
    fast_features = regime.regime_features(
        etfs, cash_weekly, vix,
        {"trend_weeks": 13, "volatility_weeks": 8, "credit_weeks": 8,
         "breadth_weeks": 13, "calibration_weeks": 26},
    )
    loo_rows = []
    for cik in recent_ciks:
        altered_returns = returns_for("base", 50).copy()
        altered_base_target = base_target
        altered_increment = increment
        if cik in set(choices_by_asset["cash_conversion"].cik10):
            altered_cash_choices = breadth_runner.make_choices(cash_scores[cash_scores.cik10 != cik], 20)
            altered_cash, _ = capped.simulate_cash(
                cash_weekly, base.build_targets(altered_cash_choices, weekly_index), "base", 50.0, None, 20
            )
            altered_returns["cash_conversion"] = altered_cash.net_return.reindex(altered_returns.index)
            signal = pd.concat([
                altered_returns.leader.rename("leader"),
                altered_returns.cash_conversion.rename("cash_conversion"),
            ], axis=1).dropna()
            overlay = capped.overlay_target(signal.index, signal.leader, signal.cash_conversion, 11, 0.5)
            altered_base_target, _ = controller.controller_target(
                overlay, breadth_signals, 26, 0.4, "breadth_high", 0.5, 0.8
            )
            altered_spike_target, _ = regime.regime_target(
                overlay.cash_conversion > 0, fast_features, breadth_high, 5, "union"
            )
            altered_raw = (altered_spike_target.cash_conversion - altered_base_target.cash_conversion).clip(lower=0.0)
            altered_increment = actual_increment(altered_base_target, altered_raw)
        for family in [asset for asset in selected_assets if asset != "cash_conversion"]:
            if cik not in set(choices_by_asset[family].cik10):
                continue
            family_scores = scores[(scores.family == family) & (scores.cik10 != cik)]
            altered_choices = breadth_runner.make_choices(family_scores, 10)
            altered_path, _ = base.simulate(
                cash_weekly, base.build_targets(altered_choices, weekly_index), "base", 50.0
            )
            altered_returns[family] = altered_path.net_return.reindex(altered_returns.index)
        altered_target = routed_target(altered_base_target, altered_increment, selected_route)
        altered_path = simulate(altered_returns, altered_target, 50.0)
        metric = recent_metric(selected, "loo", 50, altered_path)
        names = scores.loc[scores.cik10 == cik, "company_name_as_filed"].dropna()
        company = str(names.iloc[-1]) if len(names) else cik
        loo_rows.append({
            "cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
            "cagr_change": metric["cagr"] - float(selected_row.recent_cagr),
            "cash_sleeve_member": cik in set(choices_by_asset["cash_conversion"].cik10),
            "other_selected_sleeves": "|".join(
                family for family in selected_assets
                if family != "cash_conversion" and cik in set(choices_by_asset[family].cik10)
            ),
        })
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst_loo = loo.iloc[0]

    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        paths[(selected, scenario, int(cost))] = simulate(returns_for(scenario, int(cost)), targets[selected], float(cost))
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    specs[selected].rename_axis("Date").to_csv(OUTPUT / "selected_increment_route.csv")

    selected_path = paths[(selected, "base", 50)]
    joined = pd.concat([selected_path.net_return.rename("candidate"), incumbent.net_return.rename("control")], axis=1).dropna()
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
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    diversified = selected != "cash100_control"
    checks = {
        "control_reproduces_119pct_challenger": bool(control_matches),
        "diversified_candidate_selected": diversified,
        "selected_surface_gates_passed": bool(selected_row.surface_gates),
        "recent_cagr_beats_119pct_control": float(selected_row.recent_cagr) > float(incumbent_recent["cagr"]),
        "robust_floor_beats_112pct_base": float(selected_row.robust_floor) > float(base_recent["cagr"]),
        "worst_company_removal_beats_frozen": float(worst_loo.recent_cagr) > float(frozen_recent["cagr"]),
        "worst_company_removal_beats_112pct_base": float(worst_loo.recent_cagr) > float(base_recent["cagr"]),
        "rolling_outperformance_at_least_50pct": rolling_share >= float(config["falsification"]["minimum_rolling_outperformance_share"]),
        "bootstrap_4w_at_least_95pct": b4 >= float(config["falsification"]["minimum_bootstrap_probability"]),
        "bootstrap_13w_at_least_95pct": b13 >= float(config["falsification"]["minimum_bootstrap_probability"]),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    screen.sort_values(["robust_floor", "recent_cagr"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    screen[screen.surface_gates].to_csv(OUTPUT / "surface_passers.csv", index=False)
    ablations.to_csv(OUTPUT / "sleeve_removal.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "surface_passer_count": int(screen.surface_gates.sum()),
        "selected_candidate": selected, "selection_reason": reason,
        "selected_is_diversified": diversified,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "delay1_recent_cagr": float(selected_row.delay1_recent_cagr),
        "delay2_recent_cagr": float(selected_row.delay2_recent_cagr),
        "worst_sleeve_removal_recent_cagr": float(selected_row.worst_sleeve_removal_recent_cagr),
        "worst_loo_company": str(worst_loo.company_name),
        "worst_loo_recent_cagr": float(worst_loo.recent_cagr),
        "robust_floor": float(selected_row.robust_floor),
        "peak_total_stock_weight_bound": float(selected_row.peak_total_stock_weight_bound),
        "incumbent_challenger_recent_cagr": float(incumbent_recent["cagr"]),
        "base_recent_cagr": float(base_recent["cagr"]), "frozen_recent_cagr": float(frozen_recent["cagr"]),
        "rolling_outperformance_share_vs_119pct_control": rolling_share,
        "completed_rolling_windows": rolling_windows,
        "bootstrap_4w_probability_positive_vs_119pct_control": b4,
        "bootstrap_13w_probability_positive_vs_119pct_control": b13,
        "average_selected_increment_route": {asset: float(selected_route.loc[increment > 1e-12, asset].mean()) for asset in selected_route},
        "checks": checks, "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {
            "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
            "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
            "selected_increment_route": sha256(OUTPUT / "selected_increment_route.csv"),
            "screening": sha256(OUTPUT / "screening.csv"),
        },
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Increment sleeve diversification v1\n\n"
        f"Tested {len(screen)} fixed and strictly causal inverse-volatility routes for only the stabilized regime increment; "
        "the 112.93% base and four-week execution schedule were unchanged. "
        f"The selected `{selected}` returned {selected_row.recent_cagr:.2%} recent CAGR, "
        f"{selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, "
        f"{selected_row.full_cagr:.2%} full CAGR, and {selected_row.severe_recent_cagr:.2%} at 200-bps costs.\n\n"
        f"Its one/two-week increment delays returned {selected_row.delay1_recent_cagr:.2%}/{selected_row.delay2_recent_cagr:.2%}, "
        f"its worst sleeve-removal result was {selected_row.worst_sleeve_removal_recent_cagr:.2%}, and removing "
        f"{worst_loo.company_name} left {worst_loo.recent_cagr:.2%}. "
        f"Complete falsification: **{'PASS' if all_passed else 'FAIL'}**. "
        "No promotion, forward clock, or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
