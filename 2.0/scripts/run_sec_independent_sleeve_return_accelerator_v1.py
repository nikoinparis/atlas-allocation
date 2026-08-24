#!/usr/bin/env python3
"""Sealed return-accelerator tournament over independent SEC sleeves."""

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
sys.path.insert(0, str(ROOT / "src"))

from systematic_trader.sec_real_tournament_v2 import build_family_weights
from systematic_trader import sec_tournament_rehearsal as engine

CONFIG = ROOT / "config/sec_independent_sleeve_return_accelerator_v1.json"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
PANEL_ROOT = ROOT / "data/sec_broad_research_panel_v2"
CONTROL_ROOT = ROOT / "evidence/sec_cash_conversion_breadth_dynamic_v1"
FROZEN_RESULT = ROOT / "evidence/sec_residual_controlled_sleeve_v1/result.json"
FORWARD_PROTOCOL = ROOT / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
OUTPUT = ROOT / "evidence/sec_independent_sleeve_return_accelerator_v1"
FAMILIES = ["residual_momentum", "trend_quality", "quality_momentum", "event_conditioning"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_control(cost: int) -> pd.Series:
    frame = pd.read_csv(
        CONTROL_ROOT / f"best_path__base__{int(cost)}bps.csv",
        parse_dates=["Date"],
    ).set_index("Date")
    result = pd.to_numeric(frame.net_return, errors="coerce")
    result.index = pd.to_datetime(result.index, utc=True)
    return result.sort_index().rename("control")


def metrics(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return engine.metrics(clean)


def levered(values: pd.Series, multiplier: pd.Series, financing_rate: float, rebalance_cost_bps: float) -> pd.Series:
    aligned = multiplier.reindex(values.index).fillna(1.0)
    borrowing = (aligned - 1.0).clip(lower=0.0)
    financing = borrowing * float(financing_rate) / 52.0
    exposure_cost = aligned.diff().abs().fillna(0.0) * float(rebalance_cost_bps) / 10_000.0
    return aligned * values - financing - exposure_cost


def causal_allocator(
    sleeves: pd.DataFrame,
    control: pd.Series,
    *,
    lookback: int,
    top_k: int,
    low_allocation: float,
    high_allocation: float,
    cost_bps: float,
) -> tuple[pd.Series, pd.DataFrame]:
    excess = sleeves.sub(control, axis=0)
    known = excess.shift(1)
    mean = known.rolling(lookback, min_periods=lookback).mean()
    volatility = known.rolling(lookback, min_periods=lookback).std(ddof=1).replace(0.0, np.nan)
    strength = mean.div(volatility) * math.sqrt(52.0)
    trailing = (1.0 + known).rolling(lookback, min_periods=lookback).apply(np.prod, raw=True) - 1.0
    score = strength + trailing
    alpha_weights = pd.DataFrame(0.0, index=sleeves.index, columns=sleeves.columns)
    for day, row in score.iterrows():
        selected = row.replace([np.inf, -np.inf], np.nan).dropna().sort_values(ascending=False)
        selected = selected[selected > 0.0].head(int(top_k))
        if not selected.empty:
            alpha_weights.loc[day, selected.index] = 1.0 / len(selected)
    alpha = (alpha_weights * sleeves).sum(axis=1)
    alpha_excess = (alpha - control).shift(1)
    alpha_signal = (
        (1.0 + alpha_excess).rolling(lookback, min_periods=lookback).apply(np.prod, raw=True) - 1.0
    ) > 0.0
    allocation = pd.Series(
        np.where(alpha_weights.sum(axis=1) <= 0.0, 0.0, np.where(alpha_signal, high_allocation, low_allocation)),
        index=sleeves.index,
        dtype=float,
    )
    strategy_weights = alpha_weights.mul(allocation, axis=0)
    strategy_weights.insert(0, "control", 1.0 - allocation)
    turnover = 0.5 * strategy_weights.diff().abs().sum(axis=1).fillna(0.0)
    result = strategy_weights.control * control + (strategy_weights[sleeves.columns] * sleeves).sum(axis=1)
    result -= turnover * float(cost_bps) / 10_000.0
    audit = strategy_weights.copy()
    audit["alpha_allocation"] = allocation
    audit["allocator_turnover"] = turnover
    return result, audit


def exposure_multiplier(
    base: pd.Series,
    *,
    volatility_target: float | None,
    maximum_leverage: float,
    lookback: int,
    minimum_exposure: float,
) -> pd.Series:
    if volatility_target is None:
        return pd.Series(1.0, index=base.index)
    known_volatility = base.shift(1).rolling(lookback, min_periods=lookback).std(ddof=1) * math.sqrt(52.0)
    multiplier = float(volatility_target) / known_volatility.replace(0.0, np.nan)
    return multiplier.clip(lower=float(minimum_exposure), upper=float(maximum_leverage)).fillna(1.0)


def candidate_path(
    sleeves: pd.DataFrame,
    control: pd.Series,
    params: dict[str, object],
    config: dict[str, object],
) -> tuple[pd.Series, pd.DataFrame]:
    base, audit = causal_allocator(
        sleeves,
        control,
        lookback=int(params["lookback"]),
        top_k=int(params["top_k"]),
        low_allocation=float(params["low_allocation"]),
        high_allocation=float(params["high_allocation"]),
        cost_bps=float(config["primary_cost_bps"]),
    )
    multiplier = exposure_multiplier(
        base,
        volatility_target=params["volatility_target"],
        maximum_leverage=float(params["maximum_leverage"]),
        lookback=int(config["volatility_lookback_weeks"]),
        minimum_exposure=float(config["minimum_exposure"]),
    )
    audit["exposure_multiplier"] = multiplier
    return levered(base, multiplier, float(config["financing_rate"]), float(config["leverage_rebalance_cost_bps"])), audit


def parameter_grid(config: dict[str, object]) -> list[dict[str, object]]:
    grid = config["allocator_grid"]
    exposure_pairs = [(None, 1.0)] + [
        (target, cap)
        for target in grid["volatility_targets"]
        if target is not None
        for cap in grid["maximum_leverage"]
    ]
    rows = []
    for lookback, top_k, low, high, (target, cap) in itertools.product(
        grid["lookback_weeks"],
        grid["top_k_sleeves"],
        grid["low_alpha_allocations"],
        grid["high_alpha_allocations"],
        exposure_pairs,
    ):
        if float(high) < float(low):
            continue
        rows.append({
            "lookback": int(lookback),
            "top_k": int(top_k),
            "low_allocation": float(low),
            "high_allocation": float(high),
            "volatility_target": None if target is None else float(target),
            "maximum_leverage": float(cap),
        })
    return rows


def identifier(params: dict[str, object]) -> str:
    target = "none" if params["volatility_target"] is None else f"{float(params['volatility_target']):.2f}"
    return (
        f"lb{params['lookback']}__k{params['top_k']}__a{float(params['low_allocation']):.2f}-"
        f"{float(params['high_allocation']):.2f}__vol{target}__cap{float(params['maximum_leverage']):.2f}"
    )


def split_index(index: pd.Index, config: dict[str, object]) -> dict[str, pd.Index]:
    required = int(config["development_weeks"]) + int(config["validation_weeks"]) + int(config["locked_test_weeks"])
    if len(index) < required:
        raise RuntimeError(f"need {required} aligned weeks, found {len(index)}")
    selected = index[-required:]
    dev_end = int(config["development_weeks"])
    val_end = dev_end + int(config["validation_weeks"])
    return {
        "development": selected[:dev_end],
        "validation": selected[dev_end:val_end],
        "locked_test": selected[val_end:],
        "full": selected,
    }


def load_research_context() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    panel = pd.read_csv(PANEL_ROOT / "panel.csv.gz", dtype={"cik10": str})
    weekly = pd.read_csv(PANEL_ROOT / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    program = json.loads(PROGRAM.read_text())
    weights, _ = build_family_weights(panel, program)
    return weights, weekly


def build_inputs(
    weights: dict[str, pd.DataFrame],
    weekly: pd.DataFrame,
    cost: int,
    delay: int = 0,
    adverse: bool = False,
) -> tuple[pd.DataFrame, pd.Series, dict[str, pd.DataFrame]]:
    paths, contributions = {}, {}
    for family in FAMILIES:
        paths[family], contributions[family] = engine.portfolio_path(
            weights[family],
            weekly,
            int(cost),
            int(delay),
            "adverse_total_loss" if adverse else "base_cash",
        )
    sleeves = pd.DataFrame(paths)
    control = read_control(int(cost))
    common = control.dropna().index.intersection(sleeves.dropna(how="any").index)
    return sleeves.reindex(common), control.reindex(common), contributions


def baseline_path(control: pd.Series, residual: pd.Series, config: dict[str, object]) -> pd.Series:
    unlevered = 0.8 * control + 0.2 * residual
    multiplier = pd.Series(1.25, index=unlevered.index)
    return levered(unlevered, multiplier, float(config["financing_rate"]), 0.0)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    if sha256(FORWARD_PROTOCOL) != json.loads(
        ROOT.joinpath("evidence/forward_sec_residual_controlled_sleeve_v1/status.json").read_text()
    )["forward_protocol_sha256"]:
        raise RuntimeError("frozen forward protocol changed")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    result_path = OUTPUT / "result.json"
    if result_path.exists():
        raise RuntimeError("return-accelerator tournament is one-shot")
    sealed = [
        CONFIG,
        Path(__file__),
        PROGRAM,
        PANEL_ROOT / "manifest.json",
        FROZEN_RESULT,
        FORWARD_PROTOCOL,
        ROOT / "src/systematic_trader/sec_real_tournament_v2.py",
        ROOT / "src/systematic_trader/sec_return_improvement.py",
        ROOT / "src/systematic_trader/sec_tournament_rehearsal.py",
    ]
    seal = {
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
        "performance_evaluated_at_seal": False,
        "sealed_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in sealed},
        "frozen_forward_protocol_sha256": sha256(FORWARD_PROTOCOL),
        "live_trading_enabled": False,
    }
    (OUTPUT / "execution_seal.json").write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n")

    family_weights, weekly_returns = load_research_context()
    sleeves, control, contributions = build_inputs(
        family_weights, weekly_returns, int(config["primary_cost_bps"])
    )
    splits = split_index(control.index, config)
    benchmark = baseline_path(control, sleeves.residual_momentum, config)
    benchmark_metrics = {name: metrics(benchmark.reindex(days)) for name, days in splits.items()}
    rows, paths, audits = [], {}, {}
    for params in parameter_grid(config):
        name = identifier(params)
        path, audit = candidate_path(sleeves, control, params, config)
        paths[name], audits[name] = path, audit
        row = {"candidate": name, **params}
        for split, days in splits.items():
            values = metrics(path.reindex(days))
            row.update({f"{split}_{key}": value for key, value in values.items()})
        rows.append(row)
    screening = pd.DataFrame(rows)
    selection = config["selection"]
    eligible = screening[
        (screening.development_sharpe >= float(selection["minimum_development_sharpe"]))
        & (screening.development_max_drawdown >= float(selection["maximum_development_drawdown"]))
    ].copy()
    if eligible.empty:
        eligible = screening.copy()
    eligible["development_objective"] = (
        eligible.development_cagr
        + 0.15 * eligible.development_sharpe
        + 0.5 * eligible.development_max_drawdown
    )
    shortlist = eligible.sort_values("development_objective", ascending=False).head(int(selection["development_shortlist"]))
    validation = shortlist[
        (shortlist.validation_sharpe >= float(selection["minimum_validation_sharpe"]))
        & (shortlist.validation_max_drawdown >= float(selection["maximum_validation_drawdown"]))
    ]
    if validation.empty:
        validation = shortlist
    selected_row = validation.sort_values(
        ["validation_cagr", "validation_sharpe", "validation_max_drawdown"],
        ascending=False,
    ).iloc[0]
    selected_name = str(selected_row.candidate)
    selected_params = {
        key: (None if key == "volatility_target" and pd.isna(selected_row[key]) else selected_row[key].item() if hasattr(selected_row[key], "item") else selected_row[key])
        for key in ["lookback", "top_k", "low_allocation", "high_allocation", "volatility_target", "maximum_leverage"]
    }
    selected = paths[selected_name]
    audit = audits[selected_name]

    stress_rows = []
    for cost in config["stress_cost_bps"]:
        stressed_sleeves, stressed_control, _ = build_inputs(
            family_weights, weekly_returns, int(cost)
        )
        common = selected.index.intersection(stressed_control.index).intersection(stressed_sleeves.index)
        stressed, _ = candidate_path(stressed_sleeves.reindex(common), stressed_control.reindex(common), selected_params, {**config, "primary_cost_bps": int(cost)})
        stress_rows.append({"scenario": f"cost_{cost}bps", **metrics(stressed.reindex(splits["locked_test"].intersection(common)))})
    for delay in config["execution_delays_weeks"]:
        delayed_sleeves, delayed_control, _ = build_inputs(
            family_weights,
            weekly_returns,
            int(config["primary_cost_bps"]),
            int(delay),
        )
        common = selected.index.intersection(delayed_control.index).intersection(delayed_sleeves.index)
        delayed, _ = candidate_path(delayed_sleeves.reindex(common), delayed_control.reindex(common), selected_params, config)
        stress_rows.append({"scenario": f"delay_{delay}w", **metrics(delayed.reindex(splits["locked_test"].intersection(common)))})
    adverse_sleeves, adverse_control, _ = build_inputs(
        family_weights,
        weekly_returns,
        int(config["primary_cost_bps"]),
        0,
        True,
    )
    common = selected.index.intersection(adverse_control.index).intersection(adverse_sleeves.index)
    adverse, _ = candidate_path(adverse_sleeves.reindex(common), adverse_control.reindex(common), selected_params, config)
    stress_rows.append({"scenario": "adverse_missing_sleeves", **metrics(adverse.reindex(splits["locked_test"].intersection(common)))})
    stress = pd.DataFrame(stress_rows)

    differences = (selected - benchmark).reindex(splits["locked_test"]).dropna()
    bootstrap_rows = []
    trials = len(screening)
    for block in config["bootstrap_blocks_weeks"]:
        raw = engine.bootstrap_probability(differences, int(block), int(config["bootstrap_draws"]), int(config["bootstrap_seed"]))
        adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw) * trials))
        bootstrap_rows.append({"block_weeks": int(block), "raw_probability_positive": raw, "familywise_adjusted_probability_positive": adjusted})
    bootstrap = pd.DataFrame(bootstrap_rows)

    incremental = pd.DataFrame(0.0, index=selected.index, columns=sorted(set().union(*[set(frame.columns) for frame in contributions.values()])))
    for family in FAMILIES:
        family_contribution = contributions[family].reindex(index=selected.index, columns=incremental.columns).fillna(0.0)
        effective = audit[family] * audit.alpha_allocation * audit.exposure_multiplier
        incremental = incremental.add(family_contribution.mul(effective, axis=0), fill_value=0.0)
    positive = incremental.reindex(splits["locked_test"]).sum().clip(lower=0.0)
    issuer_share = float(positive.max() / positive.sum()) if positive.sum() else 0.0

    locked = metrics(selected.reindex(splits["locked_test"]))
    locked_benchmark = benchmark_metrics["locked_test"]
    severe = float(stress.loc[stress.scenario == "cost_200bps", "cagr"].iloc[0])
    worst_delay = float(stress[stress.scenario.str.startswith("delay_")].cagr.min())
    hurdles = config["hurdles"]
    gates = {
        "locked_cagr": locked["cagr"] >= locked_benchmark["cagr"] + float(hurdles["minimum_locked_cagr_improvement"]),
        "locked_sharpe": locked["sharpe"] >= locked_benchmark["sharpe"] + float(hurdles["minimum_locked_sharpe_improvement"]),
        "locked_drawdown": locked["max_drawdown"] >= float(hurdles["maximum_locked_drawdown"]),
        "cost_200bps": severe >= float(hurdles["minimum_200bps_locked_cagr"]),
        "execution_delay": worst_delay >= float(hurdles["minimum_worst_delay_locked_cagr"]),
        "incremental_issuer_concentration": issuer_share <= float(config["maximum_incremental_issuer_positive_return_share"]),
        "multiplicity": float(bootstrap.familywise_adjusted_probability_positive.min()) >= float(config["minimum_familywise_probability_positive"]),
    }

    source_correlation = pd.concat([control.rename("control"), sleeves], axis=1).corr()
    screening.to_csv(OUTPUT / "screening.csv", index=False)
    shortlist.to_csv(OUTPUT / "development_shortlist.csv", index=False)
    selected.rename("net_return").rename_axis("Date").to_csv(OUTPUT / "selected_path.csv")
    audit.rename_axis("Date").to_csv(OUTPUT / "selected_allocations.csv")
    stress.to_csv(OUTPUT / "stress_tests.csv", index=False)
    bootstrap.to_csv(OUTPUT / "block_bootstrap.csv", index=False)
    source_correlation.to_csv(OUTPUT / "source_correlations.csv")
    artifacts = ["screening.csv", "development_shortlist.csv", "selected_path.csv", "selected_allocations.csv", "stress_tests.csv", "block_bootstrap.csv", "source_correlations.csv"]
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "one_shot_tournament_complete",
        "common_endpoint": str(control.index.max().date()),
        "mismatched_endpoint_zero_fill_forbidden": True,
        "candidate_count": int(len(screening)),
        "selected_candidate": selected_name,
        "selected_parameters": selected_params,
        "split_dates": {name: {"start": str(days.min().date()), "end": str(days.max().date()), "weeks": int(len(days))} for name, days in splits.items()},
        "locked_candidate": locked,
        "locked_corrected_147pct_benchmark": locked_benchmark,
        "full_candidate": metrics(selected.reindex(splits["full"])),
        "full_corrected_benchmark": benchmark_metrics["full"],
        "locked_cagr_improvement": locked["cagr"] - locked_benchmark["cagr"],
        "locked_sharpe_improvement": locked["sharpe"] - locked_benchmark["sharpe"],
        "worst_delay_locked_cagr": worst_delay,
        "cost_200bps_locked_cagr": severe,
        "maximum_incremental_issuer_positive_return_share": issuer_share,
        "gate_results": gates,
        "all_economic_gates_passed": bool(all(value for key, value in gates.items() if key != "multiplicity")),
        "all_statistical_gates_passed": bool(all(gates.values())),
        "selection_contaminated": True,
        "frozen_forward_candidate_modified": False,
        "strategy_promotion_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifacts},
    }
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
