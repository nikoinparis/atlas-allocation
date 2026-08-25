#!/usr/bin/env python3
"""Test causal cluster-aware allocations inside the return-oriented cash sleeve."""

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
import run_sec_form4_dynamic_overlay_v1 as audit

CONFIG = ROOT / "config/sec_cluster_aware_cash_sleeve_v1.json"
FACTORS = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
CONTROL = ROOT / "evidence/sec_regime_increment_tranching_v1/selected_path__50bps.csv"
BASE_CONTROL = ROOT / "evidence/sec_breadth_dispersion_allocation_controller_v1/selected_path__50bps.csv"
FROZEN = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_cluster_aware_cash_sleeve_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cap_weights(weights: pd.Series, cap: float) -> pd.Series:
    """Project non-negative weights to a simplex with a per-name upper bound."""
    result = weights.clip(lower=0.0).fillna(0.0)
    result = result / result.sum() if result.sum() > 0 else pd.Series(1.0 / len(result), index=result.index)
    fixed = pd.Series(False, index=result.index)
    for _ in range(len(result) + 1):
        over = (~fixed) & (result > float(cap) + 1e-15)
        if not over.any():
            break
        result.loc[over] = float(cap)
        fixed.loc[over] = True
        remaining = 1.0 - float(result.loc[fixed].sum())
        free = ~fixed
        if not free.any():
            break
        free_total = float(result.loc[free].sum())
        result.loc[free] = remaining / int(free.sum()) if free_total <= 0 else result.loc[free] / free_total * remaining
    return result / result.sum()


def blended_membership_scores(panel: pd.DataFrame, blend: dict) -> pd.DataFrame:
    out = panel[["decision_at", "cik10", "company_name_as_filed", "sector"]].copy()
    out["score"] = 0.0
    for family, weight in blend.items():
        if family in {"name", "weighting_search"}:
            continue
        out["score"] += float(weight) * panel[family].fillna(0.5)
    return out.dropna(subset=["score"])


def selected_cohorts(scores: pd.DataFrame, breadth: int, banned_cik: str | None = None) -> pd.DataFrame:
    rows = []
    source = scores[scores.cik10 != str(banned_cik)] if banned_cik is not None else scores
    for decision, frame in source.groupby("decision_at", sort=True):
        selected = frame.sort_values(["score", "cik10"], ascending=[False, True]).head(int(breadth))
        rows.append(selected)
    return pd.concat(rows, ignore_index=True)


def raw_risk_weights(history: pd.DataFrame, method: str) -> pd.Series:
    usable = history.dropna(axis=1, how="all")
    result = pd.Series(1.0, index=history.columns)
    if usable.empty:
        return result
    vol = usable.std(ddof=1).replace(0.0, np.nan)
    corr = usable.corr().abs()
    if len(corr) > 1:
        average_corr = (corr.sum(axis=1) - 1.0) / (corr.notna().sum(axis=1) - 1).clip(lower=1)
    else:
        average_corr = pd.Series(1.0, index=usable.columns)
    if method == "inverse_volatility":
        score = 1.0 / vol
    elif method == "inverse_correlation":
        score = 1.0 / average_corr.replace(0.0, np.nan)
    elif method == "inverse_volatility_correlation":
        score = 1.0 / (vol * average_corr.replace(0.0, np.nan))
    else:
        raise ValueError(f"unknown risk method: {method}")
    result.loc[score.index] = score.replace([np.inf, -np.inf], np.nan).fillna(score.median()).fillna(1.0)
    return result


def build_weighted_targets(
    cohorts: pd.DataFrame,
    prices: pd.DataFrame,
    index: pd.DatetimeIndex,
    method: str,
    lookback: int,
    shrinkage: float,
    cap_multiple: float,
) -> tuple[dict[pd.Timestamp, dict[str, float]], pd.DataFrame]:
    targets, rows = {}, []
    for decision, frame in cohorts.groupby("decision_at", sort=True):
        frame = frame.sort_values("cik10")
        names = [str(value) for value in frame.cik10]
        equal = pd.Series(1.0 / len(names), index=names)
        if method == "equal":
            raw = equal
        elif method == "sector_balance":
            sector_counts = frame.groupby("sector").cik10.transform("count").to_numpy()
            sector_total = max(1, frame.sector.nunique())
            raw = pd.Series(1.0 / sector_total / sector_counts, index=names)
        else:
            prior = prices.loc[prices.index < pd.Timestamp(decision).tz_localize(None)].reindex(columns=names)
            history = prior.pct_change(fill_method=None).tail(int(lookback))
            raw = raw_risk_weights(history, method)
        raw = raw / raw.sum() if raw.sum() > 0 else equal
        shrunk = (1.0 - float(shrinkage)) * equal + float(shrinkage) * raw
        weights = cap_weights(shrunk, float(cap_multiple) / len(names))
        later = index[index > pd.Timestamp(decision).tz_localize(None)]
        if not len(later):
            continue
        rebalance = later[0]
        targets[rebalance] = weights.to_dict()
        for cik, weight in weights.items():
            source = frame[frame.cik10.astype(str) == str(cik)].iloc[0]
            rows.append({
                "decision_at": decision, "rebalance_at": rebalance, "cik10": cik,
                "company_name": source.company_name_as_filed, "sector": source.sector,
                "intended_weight": float(weight), "method": method, "lookback": int(lookback),
                "shrinkage": float(shrinkage), "cap_multiple": float(cap_multiple),
            })
    return targets, pd.DataFrame(rows)


def candidate_specs(config: dict) -> list[dict]:
    specs = [{"method": "equal", "lookback": 26, "shrinkage": 0.0, "cap_multiple": 1.0}]
    for method, lookback, shrinkage, cap in itertools.product(
        config["risk_methods"], config["lookback_weeks"], config["risk_shrinkages"], config["cap_multiples"]
    ):
        specs.append({"method": method, "lookback": int(lookback), "shrinkage": float(shrinkage), "cap_multiple": float(cap)})
    for shrinkage, cap in itertools.product(config["sector_shrinkages"], config["cap_multiples"]):
        specs.append({"method": "sector_balance", "lookback": 26, "shrinkage": float(shrinkage), "cap_multiple": float(cap)})
    return specs


def label(membership: str, spec: dict) -> str:
    return (
        f"{membership}__{spec['method']}__lb{int(spec['lookback'])}"
        f"__s{int(round(float(spec['shrinkage'])*100)):02d}__cap{float(spec['cap_multiple']):.2f}x"
    )


def recent_metric(name: str, scenario: str, cost: int, path: pd.DataFrame) -> dict:
    return next(row for row in base.metric_rows(name, scenario, cost, path) if row["window"] == "trailing_1y")


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = audit.verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw_scores = pd.read_csv(FACTORS / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    panel = multisignal.normalized_score_panel(raw_scores)
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
    leader = {
        (scenario, int(cost)): dynamic.read_path(
            LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv"
        ).net_return
        for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"])
    }
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date")
    base_control = pd.read_csv(BASE_CONTROL, parse_dates=["Date"]).set_index("Date")
    frozen = pd.read_csv(FROZEN, parse_dates=["Date"]).set_index("Date")
    control_recent = recent_metric("control", "base", 50, control)
    base_recent = recent_metric("base", "base", 50, base_control)
    frozen_recent = recent_metric("frozen", "base", 50, frozen)
    breadth_signals = controller.breadth_dispersion_signals(weekly, 26)
    breadth_high = controller.regime_state(breadth_signals, 26, 0.4, "breadth_high")
    fast_features = _fast_features(weekly, index)

    membership_scores = {
        blend["name"]: blended_membership_scores(panel, blend)
        for blend in config["membership_blends"]
    }
    specifications = candidate_specs(config)
    rows, paths, strategy_targets, stock_targets_cache, choices_cache, peaks = [], {}, {}, {}, {}, {}
    for membership, scores in membership_scores.items():
        cohorts = selected_cohorts(scores, int(config["breadth"]))
        blend_config = next(item for item in config["membership_blends"] if item["name"] == membership)
        membership_specs = specifications if bool(blend_config.get("weighting_search", True)) else specifications[:1]
        for spec in membership_specs:
            name = label(membership, spec)
            weighted_targets, choices = build_weighted_targets(
                cohorts, weekly, index, spec["method"], spec["lookback"], spec["shrinkage"], spec["cap_multiple"]
            )
            stock_targets_cache[name], choices_cache[name] = weighted_targets, choices
            sleeves = {}
            for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
                sleeves[(scenario, int(cost))], peaks[(name, scenario, int(cost))] = cohort.simulate_weighted_cash(
                    weekly, weighted_targets, scenario, float(cost)
                )
            target, _ = cohort.strategy_target(leader[("base", 50)], sleeves[("base", 50)],
                breadth_signals, breadth_high, fast_features, 11, 0)
            strategy_targets[name] = target
            current = controller.simulate_composite(leader[("base", 50)], sleeves[("base", 50)], target, 50.0)
            severe = controller.simulate_composite(leader[("base", 200)], sleeves[("base", 200)], target, 200.0)
            paths[(name, "base", 50)], paths[(name, "base", 200)] = current, severe
            recent = recent_metric(name, "base", 50, current)
            full = next(r for r in base.metric_rows(name, "base", 50, current) if r["window"] == "full_recent")
            severe_recent = recent_metric(name, "base", 200, severe)
            delays = {}
            for delay in config["falsification"]["increment_delays_weeks"]:
                delayed_target, _ = cohort.strategy_target(leader[("base", 50)], sleeves[("base", 50)],
                    breadth_signals, breadth_high, fast_features, 11, int(delay))
                delayed_path = controller.simulate_composite(leader[("base", 50)], sleeves[("base", 50)], delayed_target, 50.0)
                delays[int(delay)] = recent_metric(name, f"delay_{delay}", 50, delayed_path)["cagr"]
            rows.append({
                "candidate": name, "membership": membership, **spec,
                "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe_zero_rf"],
                "recent_drawdown": recent["max_drawdown"], "full_cagr": full["cagr"],
                "severe_recent_cagr": severe_recent["cagr"],
                "delay1_recent_cagr": delays[1], "delay2_recent_cagr": delays[2],
                "worst_current_delay_recent_cagr": min(recent["cagr"], delays[1], delays[2]),
                "peak_total_stock_weight": float(target.cash_conversion.max() * peaks[(name, "base", 50)]),
            })
    screen = pd.DataFrame(rows)
    control_name = label("cash100", specifications[0])
    control_matches = np.allclose(paths[(control_name, "base", 50)].net_return.reindex(control.index), control.net_return,
                                  rtol=0, atol=1e-12, equal_nan=True)
    if not control_matches:
        raise RuntimeError("equal-weight cash100 control failed to reproduce the 119.22% challenger")
    gates = config["surface_gates"]
    screen["surface_gates"] = (
        (screen.recent_cagr >= float(gates["minimum_recent_cagr"]))
        & (screen.delay1_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.delay2_recent_cagr >= float(gates["minimum_delay_recent_cagr"]))
        & (screen.full_cagr >= float(gates["minimum_full_cagr"]))
        & (screen.severe_recent_cagr >= float(gates["minimum_severe_recent_cagr"]))
        & (screen.peak_total_stock_weight <= float(gates["maximum_peak_total_stock_weight"]))
    )
    pool = screen[(screen.candidate != control_name) & screen.surface_gates]
    reason = "best current/delay floor among non-control surface passers"
    if pool.empty:
        pool = screen[screen.candidate != control_name]
        reason = "no non-control surface passer; best diagnostic floor"
    selected_row = pool.sort_values(["worst_current_delay_recent_cagr", "recent_cagr", "full_cagr"], ascending=False).iloc[0]
    selected = str(selected_row.candidate)

    # Complete selected specification under all costs/scenarios and full issuer removal.
    selected_membership = str(selected_row.membership)
    selected_spec = {key: selected_row[key] for key in ["method", "lookback", "shrinkage", "cap_multiple"]}
    selected_sleeves = {}
    for scenario, cost in itertools.product(config["scenarios"], config["cost_bps"]):
        selected_sleeves[(scenario, int(cost))], _ = cohort.simulate_weighted_cash(
            weekly, stock_targets_cache[selected], scenario, float(cost)
        )
        paths[(selected, scenario, int(cost))] = controller.simulate_composite(
            leader[(scenario, int(cost))], selected_sleeves[(scenario, int(cost))], strategy_targets[selected], float(cost)
        )
    recent_choices = choices_cache[selected]
    cutoff = recent_choices.decision_at.max() - pd.DateOffset(years=1)
    recent_ciks = sorted(set(recent_choices.loc[recent_choices.decision_at >= cutoff, "cik10"]))
    loo_rows = []
    for cik in recent_ciks:
        altered_cohorts = selected_cohorts(membership_scores[selected_membership], int(config["breadth"]), cik)
        altered_targets, _ = build_weighted_targets(altered_cohorts, weekly, index,
            str(selected_spec["method"]), int(selected_spec["lookback"]),
            float(selected_spec["shrinkage"]), float(selected_spec["cap_multiple"]))
        altered_sleeve, _ = cohort.simulate_weighted_cash(weekly, altered_targets, "base", 50.0)
        altered_target, _ = cohort.strategy_target(leader[("base", 50)], altered_sleeve,
            breadth_signals, breadth_high, fast_features, 11, 0)
        altered_path = controller.simulate_composite(leader[("base", 50)], altered_sleeve, altered_target, 50.0)
        metric = recent_metric(selected, "loo", 50, altered_path)
        company = recent_choices.loc[recent_choices.cik10 == cik, "company_name"].iloc[-1]
        loo_rows.append({"cik10": cik, "company_name": company, "recent_cagr": metric["cagr"],
                         "cagr_change": metric["cagr"] - float(selected_row.recent_cagr)})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change")
    worst = loo.iloc[0]
    saved = paths[(selected, "base", 50)]
    joined = pd.concat([saved.net_return.rename("candidate"), control.net_return.rename("control")], axis=1).dropna()
    rolling_share, rolling_windows = controller.stable_completed_rolling_outperformance(
        joined, int(config["falsification"]["rolling_comparison_weeks"])
    )
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    bootstrap = pd.DataFrame([dynamic.block_bootstrap(controller.stable_excess_returns(recent_joined), int(block),
        int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"]))
        for block in config["falsification"]["bootstrap_blocks_weeks"]])
    b4 = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    b13 = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    balance_neighborhood = screen[
        screen.membership.isin(["cash85_balance15", "cash825_balance175", "cash80_balance20", "cash775_balance225", "cash75_balance25"])
        & (screen.method == "equal")
    ].copy()
    balance_neighborhood["beats_control_and_surface"] = (
        (balance_neighborhood.recent_cagr > float(control_recent["cagr"]))
        & balance_neighborhood.surface_gates
    )
    neighborhood_share = float(balance_neighborhood.beats_control_and_surface.mean())
    checks = {
        "control_reproduces_119pct_challenger": bool(control_matches),
        "selected_surface_gates_passed": bool(selected_row.surface_gates),
        "recent_cagr_beats_119pct_control": float(selected_row.recent_cagr) > float(control_recent["cagr"]),
        "worst_loo_beats_119pct_control": float(worst.recent_cagr) > float(control_recent["cagr"]),
        "worst_loo_beats_112pct_base": float(worst.recent_cagr) > float(base_recent["cagr"]),
        "balance_weight_neighborhood_at_least_60pct": neighborhood_share >= 0.6,
        "rolling_outperformance_at_least_50pct": rolling_share >= float(config["falsification"]["minimum_rolling_outperformance_share"]),
        "bootstrap_4w_at_least_95pct": b4 >= float(config["falsification"]["minimum_bootstrap_probability"]),
        "bootstrap_13w_at_least_95pct": b13 >= float(config["falsification"]["minimum_bootstrap_probability"]),
    }
    all_passed = audit.required_gates_pass(checks, list(checks))
    for cost in config["cost_bps"]:
        paths[(selected, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")
    strategy_targets[selected].rename_axis("Date").to_csv(OUTPUT / "selected_strategy_target_weights.csv")
    choices_cache[selected].to_csv(OUTPUT / "selected_stock_target_weights.csv", index=False)
    screen.sort_values(["worst_current_delay_recent_cagr", "recent_cagr"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    screen[screen.surface_gates].to_csv(OUTPUT / "surface_passers.csv", index=False)
    loo.to_csv(OUTPUT / "leave_one_company_out.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    balance_neighborhood.to_csv(OUTPUT / "balance_weight_neighborhood.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": int(len(screen)), "surface_passer_count": int(screen.surface_gates.sum()),
        "selected_candidate": selected, "selection_reason": reason,
        "recent_cagr": float(selected_row.recent_cagr), "recent_sharpe": float(selected_row.recent_sharpe),
        "recent_drawdown": float(selected_row.recent_drawdown), "full_cagr": float(selected_row.full_cagr),
        "severe_recent_cagr": float(selected_row.severe_recent_cagr),
        "delay1_recent_cagr": float(selected_row.delay1_recent_cagr), "delay2_recent_cagr": float(selected_row.delay2_recent_cagr),
        "peak_total_stock_weight": float(selected_row.peak_total_stock_weight),
        "control_recent_cagr": float(control_recent["cagr"]), "base_recent_cagr": float(base_recent["cagr"]),
        "frozen_recent_cagr": float(frozen_recent["cagr"]), "worst_loo_company": str(worst.company_name),
        "worst_loo_recent_cagr": float(worst.recent_cagr),
        "rolling_outperformance_share_vs_119pct_control": rolling_share, "completed_rolling_windows": rolling_windows,
        "bootstrap_4w_probability_positive_vs_119pct_control": b4,
        "bootstrap_13w_probability_positive_vs_119pct_control": b13,
        "balance_weight_neighborhood_pass_share": neighborhood_share,
        "checks": checks, "all_falsification_checks_passed": all_passed, "runtime": runtime,
        "artifact_sha256": {}, "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    for key, filename in {"selected_path_50bps": "selected_path__50bps.csv", "screening": "screening.csv",
                          "stock_targets": "selected_stock_target_weights.csv"}.items():
        result["artifact_sha256"][key] = sha256(OUTPUT / filename)
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Cluster-aware cash sleeve v1\n\n"
        f"Tested {len(screen)} causal membership/risk-allocation variants while rebuilding the unchanged breadth controller, "
        f"fast-regime increment, and four-week schedule. `{selected}` returned {selected_row.recent_cagr:.2%} recent CAGR, "
        f"{selected_row.recent_sharpe:.3f} Sharpe, {selected_row.recent_drawdown:.2%} drawdown, "
        f"{selected_row.full_cagr:.2%} full CAGR, and {selected_row.severe_recent_cagr:.2%} at 200-bps costs.\n\n"
        f"One/two-week increment delays returned {selected_row.delay1_recent_cagr:.2%}/{selected_row.delay2_recent_cagr:.2%}. "
        f"Removing {worst.company_name} left {worst.recent_cagr:.2%}. Complete falsification: "
        f"**{'PASS' if all_passed else 'FAIL'}**. No promotion, forward clock, or live execution was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _fast_features(weekly: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    import run_sec_independent_market_regime_activation_v1 as regime
    etfs = regime.weekly_etf_prices(index)
    vix = pd.read_csv(regime.VIX, parse_dates=["Date"]).set_index("Date")
    return regime.regime_features(etfs, weekly, vix, {
        "trend_weeks": 13, "volatility_weeks": 8, "credit_weeks": 8,
        "breadth_weeks": 13, "calibration_weeks": 26,
    })


if __name__ == "__main__":
    raise SystemExit(main())
