#!/usr/bin/env python3
"""Sealed cross-strategy residual allocator, v3.

Identical logic to v2, rerun against a corrected instrument classification map.

One-shot research experiment. It supersedes v1, which compared return series
only. This version reconciles every source series against its own daily record
before evaluating anything, rebuilds the combined book at the holdings level so
that trading costs and concentration are measured on what is actually held,
charges both sources symmetrically, and refuses to look at financed exposure
until the unlevered book has genuinely improved.

No promotion, authorisation, or live trading follows from running this file.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_cross_strategy_residual_allocator_v3.json"
SOURCE = ROOT / "dashboard/public/return-first-dashboard.json"
SECTOR_MAP = ROOT / json.loads(CONFIG.read_text())["sector_map_path"]
OUTPUT = ROOT / "evidence/sec_cross_strategy_residual_allocator_v3"
SEAL = OUTPUT / "execution_seal.json"

CASH_PREFIX = "cash::"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# metrics
# --------------------------------------------------------------------------

def statistics(returns: pd.Series, periods: int = 52) -> dict:
    values = returns.dropna().astype(float)
    wealth = (1.0 + values).cumprod()
    years = len(values) / periods
    deviation = values.std(ddof=1)
    return {
        "observations": int(len(values)),
        "start": str(values.index.min().date()),
        "end": str(values.index.max().date()),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(values.mean() / deviation * math.sqrt(periods)) if deviation else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "ending_value_10000": float(wealth.iloc[-1] * 10000.0),
    }


# --------------------------------------------------------------------------
# stage 0 - exact daily reconciliation, run before any performance evaluation
# --------------------------------------------------------------------------

def compound_daily_to_weekly(daily: pd.Series, weekly_index: pd.DatetimeIndex) -> pd.Series:
    edges = weekly_index.to_numpy()
    position = np.searchsorted(edges, daily.index.to_numpy(), side="left")
    grouped = (1.0 + daily).groupby(pd.Series(position, index=daily.index)).prod() - 1.0
    grouped = grouped[grouped.index < len(edges)]
    grouped.index = pd.DatetimeIndex(edges[grouped.index.to_numpy()])
    return grouped


def reconcile(item: dict, tolerance: float) -> dict:
    records = item["records"]
    index = pd.DatetimeIndex([pd.Timestamp(row["date"]) for row in records])
    net = pd.Series([float(row["netReturn"]) for row in records], index=index)
    gross = pd.Series([float(row["grossReturn"]) for row in records], index=index)
    cost = pd.Series([float(row["cost"]) for row in records], index=index)
    wealth = pd.Series([float(row["wealth"]) for row in records], index=index)
    daily = pd.Series(
        {pd.Timestamp(row["date"]): float(row["netReturn"]) for row in item["dailyRecords"]}
    ).sort_index()

    rebuilt = compound_daily_to_weekly(daily, index)
    aligned = pd.concat([net.rename("weekly"), rebuilt.rename("daily")], axis=1).dropna()
    daily_error = float((aligned.weekly - aligned.daily).abs().max()) if len(aligned) else float("inf")
    wealth_error = float((net.add(1.0).cumprod() - wealth).abs().max())
    identity_error = float((gross - cost - net).abs().max())

    checks = {
        "weekly_net_return_equals_compounded_daily": daily_error,
        "weekly_wealth_equals_cumulative_net_return": wealth_error,
        "weekly_net_equals_gross_minus_cost": identity_error,
    }
    return {
        "weekly_observations": int(len(net)),
        "daily_observations": int(len(daily)),
        "reconciled_weeks": int(len(aligned)),
        "max_absolute_error": checks,
        "passed": {name: bool(error <= tolerance) for name, error in checks.items()},
        "all_passed": bool(all(error <= tolerance for error in checks.values())),
        "charged_total_turnover": float(pd.Series([float(row["turnover"]) for row in records]).sum()),
        "charged_total_cost": float(cost.sum()),
        "implied_average_cost_bps": float(cost.sum() / pd.Series([float(row["turnover"]) for row in records]).sum() * 10000.0)
        if pd.Series([float(row["turnover"]) for row in records]).sum() else 0.0,
    }


# --------------------------------------------------------------------------
# stage 1 - unlever returns and holdings
# --------------------------------------------------------------------------

def unlever(item: dict, rule: dict) -> dict:
    records = item["records"]
    index = pd.DatetimeIndex([pd.Timestamp(row["date"]) for row in records])
    gross_display = pd.Series([float(row["grossReturn"]) for row in records], index=index)
    net_display = pd.Series([float(row["netReturn"]) for row in records], index=index)
    turnover_display = pd.Series([float(row["turnover"]) for row in records], index=index)
    exposure = float(rule["display_gross"])
    financing = (exposure - 1.0) * float(rule["annual_financing_rate"]) / 52.0

    holdings: dict[pd.Timestamp, dict[str, float]] = {}
    for row in records:
        stamp = pd.Timestamp(row["date"])
        holdings[stamp] = {
            holding["symbol"].upper(): float(holding["weight"]) / exposure
            for holding in row["holdings"]
            if not holding["symbol"].startswith(CASH_PREFIX)
        }
    return {
        "gross": (gross_display + financing) / exposure,
        "net_as_published": (net_display + financing) / exposure,
        "turnover": turnover_display / exposure,
        "holdings": holdings,
    }


# --------------------------------------------------------------------------
# stage 2 - concentration with exchange traded look-through
# --------------------------------------------------------------------------

def load_sector_map(path: Path) -> dict[str, dict[str, str]]:
    frame = pd.read_csv(path, dtype=str).fillna("")
    return {row.symbol.upper(): {"instrument_type": row.instrument_type, "sector": row.sector} for row in frame.itertuples()}


def concentration(weights: dict[str, float], sector_map: dict, look_through: dict) -> dict:
    def kind(symbol: str) -> str:
        return sector_map.get(symbol, {}).get("instrument_type", "unmapped")

    # A data artifact is not a tradeable instrument and must not be absorbed
    # into either the issuer or the fund bucket.
    artifact = {symbol: abs(weight) for symbol, weight in weights.items() if kind(symbol) == "data_artifact"}
    issuer = {symbol: abs(weight) for symbol, weight in weights.items()
              if kind(symbol) not in {"exchange_traded_product", "data_artifact"}}
    traded = {symbol: abs(weight) for symbol, weight in weights.items()
              if kind(symbol) == "exchange_traded_product"}
    sectors: dict[str, float] = defaultdict(float)
    for symbol, weight in issuer.items():
        sectors[sector_map.get(symbol, {}).get("sector") or "unclassified"] += weight
    for symbol, weight in traded.items():
        split = look_through.get(symbol)
        if not split:
            sectors["unclassified_exchange_traded"] += weight
            continue
        for sector, share in split.items():
            sectors[sector] += weight * float(share)
    return {
        "max_single_issuer_weight": max(issuer.values()) if issuer else 0.0,
        "max_single_exchange_traded_weight": max(traded.values()) if traded else 0.0,
        "max_total_exchange_traded_weight": sum(traded.values()),
        "max_look_through_sector_weight": max(sectors.values()) if sectors else 0.0,
        "data_artifact_weight": sum(artifact.values()),
        "top_sector": max(sectors, key=sectors.get) if sectors else "",
    }


def combined_holdings(base: dict[str, float], sleeve: dict[str, float], allocation: float) -> dict[str, float]:
    merged: dict[str, float] = defaultdict(float)
    for symbol, weight in base.items():
        merged[symbol] += (1.0 - allocation) * weight
    for symbol, weight in sleeve.items():
        merged[symbol] += allocation * weight
    return dict(merged)


def concentration_profile(dates, base_h, sleeve_h, allocation, sector_map, look_through, percentile) -> dict:
    rows = [concentration(combined_holdings(base_h[stamp], sleeve_h[stamp], allocation), sector_map, look_through)
            for stamp in dates]
    frame = pd.DataFrame(rows, index=pd.DatetimeIndex(dates))
    numeric = frame.drop(columns=["top_sector"])
    return {
        **{f"p{int(percentile * 100)}_{column}": float(numeric[column].quantile(percentile)) for column in numeric.columns},
        **{f"max_{column}": float(numeric[column].max()) for column in numeric.columns},
        "most_frequent_top_sector": frame.top_sector.mode().iloc[0] if len(frame) else "",
    }


# --------------------------------------------------------------------------
# stage 3 - breadth: do the two books actually hold different things
# --------------------------------------------------------------------------

def holdings_overlap(base: dict[str, float], sleeve: dict[str, float]) -> float:
    base_total = sum(abs(weight) for weight in base.values())
    sleeve_total = sum(abs(weight) for weight in sleeve.values())
    if not base_total or not sleeve_total:
        return 0.0
    return float(sum(
        min(abs(base.get(symbol, 0.0)) / base_total, abs(sleeve.get(symbol, 0.0)) / sleeve_total)
        for symbol in set(base) | set(sleeve)
    ))


def effective_independent_strategies(returns: pd.DataFrame) -> float:
    correlation = returns.corr().to_numpy()
    eigenvalues = np.linalg.eigvalsh(correlation)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    if eigenvalues.sum() <= 0:
        return 0.0
    return float(eigenvalues.sum() ** 2 / np.square(eigenvalues).sum())


# --------------------------------------------------------------------------
# stage 4 - causal signals, lagged inputs only
# --------------------------------------------------------------------------

def causal_signals(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    signal = config["signal"]
    lagged = frame.shift(1)
    lookback = signal["beta_correlation_lookback_weeks"]
    minimum = signal["minimum_history_weeks"]
    covariance = lagged.sleeve.rolling(lookback, min_periods=minimum).cov(lagged.base)
    variance = lagged.base.rolling(lookback, min_periods=minimum).var().replace(0.0, np.nan)
    beta = covariance / variance
    correlation = lagged.sleeve.rolling(lookback, min_periods=minimum).corr(lagged.base)
    residual = lagged.sleeve - beta * lagged.base
    short = signal["short_residual_momentum_weeks"]
    long = signal["long_residual_momentum_weeks"]
    short_momentum = (1.0 + residual).rolling(short, min_periods=short).apply(np.prod, raw=True) - 1.0
    long_momentum = (1.0 + residual).rolling(long, min_periods=long).apply(np.prod, raw=True) - 1.0
    sleeve_momentum = (1.0 + lagged.sleeve).rolling(short, min_periods=short).apply(np.prod, raw=True) - 1.0
    residual_mean = residual.rolling(long, min_periods=long).mean()
    residual_std = residual.rolling(long, min_periods=long).std(ddof=1).replace(0.0, np.nan)
    information_ratio = residual_mean / residual_std * math.sqrt(52)
    gate = (short_momentum > 0.0) & (long_momentum > 0.0) & (sleeve_momentum > 0.0) & (correlation <= signal["maximum_correlation"])
    return pd.DataFrame({
        "beta": beta,
        "correlation": correlation,
        "residual_short_momentum": short_momentum,
        "residual_long_momentum": long_momentum,
        "sleeve_momentum": sleeve_momentum,
        "residual_information_ratio": information_ratio,
        "gate": gate.fillna(False),
    }, index=frame.index)


def target_weights(signals: pd.DataFrame, rule: str, cap: float, config: dict) -> pd.Series:
    if rule == "static":
        return pd.Series(cap, index=signals.index, name="target_weight")
    if rule == "gated":
        return signals.gate.astype(float).mul(cap).rename("target_weight")
    if rule == "covariance_scaled":
        ceiling = config["signal"]["maximum_residual_information_ratio"]
        scale = (signals.residual_information_ratio / ceiling).clip(0.0, 1.0).fillna(0.0)
        return signals.gate.astype(float).mul(scale).mul(cap).rename("target_weight")
    raise ValueError(f"unknown rule: {rule}")


# --------------------------------------------------------------------------
# stage 5 - holdings-level allocator path
# --------------------------------------------------------------------------

def allocator_path(
    frame: pd.DataFrame,
    base_h: dict,
    sleeve_h: dict,
    targets: pd.Series,
    cost_bps: float,
    delay: int = 0,
    positive_retention: float = 1.0,
    shock: float = 0.0,
    shock_index: pd.Timestamp | None = None,
    drop_symbols_by_week: dict | None = None,
    excluded_symbols: set | None = None,
) -> pd.DataFrame:
    """Rebuild the combined book week by week and charge its real turnover."""
    weight = targets.shift(delay).fillna(0.0).clip(0.0, 1.0)
    dates = list(frame.index)
    previous: dict[str, float] = {}
    rows = []
    for stamp in dates:
        allocation = float(weight.loc[stamp])
        sleeve_weights = dict(sleeve_h[stamp])
        if excluded_symbols:
            sleeve_weights = {s: w for s, w in sleeve_weights.items() if s not in excluded_symbols}
        if drop_symbols_by_week and stamp in drop_symbols_by_week:
            sleeve_weights = {s: w for s, w in sleeve_weights.items() if s not in drop_symbols_by_week[stamp]}
        book = combined_holdings(base_h[stamp], sleeve_weights, allocation)
        symbols = set(book) | set(previous)
        turnover = sum(abs(book.get(symbol, 0.0) - previous.get(symbol, 0.0)) for symbol in symbols)
        cost = turnover * cost_bps / 10000.0

        base_gross = float(frame.base_gross.loc[stamp])
        sleeve_gross = float(frame.sleeve_gross.loc[stamp])
        # A dropped or excluded sleeve name contributes nothing; the freed weight sits in cash.
        retained = sum(abs(w) for w in sleeve_weights.values())
        original = sum(abs(w) for w in sleeve_h[stamp].values())
        survival = retained / original if original else 0.0
        sleeve_effective = sleeve_gross * survival

        increment = sleeve_effective - base_gross
        if positive_retention != 1.0 and increment > 0.0:
            increment *= positive_retention
        if shock and shock_index is not None and stamp == shock_index:
            increment += shock
        net = base_gross + allocation * increment - cost
        rows.append({
            "base_gross": base_gross,
            "sleeve_gross": sleeve_gross,
            "sleeve_effective": sleeve_effective,
            "target_weight": allocation,
            "holdings_turnover": turnover,
            "cost": cost,
            "net_return": net,
        })
        previous = book
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates))


def base_only_path(frame: pd.DataFrame, base_h: dict, cost_bps: float) -> pd.DataFrame:
    zero = pd.Series(0.0, index=frame.index)
    return allocator_path(frame, base_h, {k: {} for k in base_h}, zero, cost_bps)


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

def expanding_folds(development_length: int, config: dict) -> list[tuple[int, int]]:
    selection = config["selection"]
    start = selection["minimum_training_weeks"] + selection["purge_weeks"]
    folds = []
    while start + selection["validation_weeks"] <= development_length:
        folds.append((start, start + selection["validation_weeks"]))
        start += selection["step_weeks"]
    if not folds:
        raise RuntimeError("no purged walk-forward validation fold")
    return folds


def objective(metrics: dict, config: dict) -> float:
    selection = config["selection"]
    return float(
        metrics["cagr"]
        + selection["objective_sharpe_weight"] * metrics["sharpe"]
        - selection["objective_drawdown_penalty"] * abs(metrics["max_drawdown"])
    )


def paired_block_probability(selected: pd.Series, base: pd.Series, simulations: int, block: int, seed: int) -> float:
    difference = (selected - base).to_numpy()
    count = len(difference)
    rng = np.random.default_rng(seed)
    starts = np.arange(max(1, count - block + 1))
    wins = 0
    for _ in range(simulations):
        chunks = []
        total = 0
        while total < count:
            start = int(rng.choice(starts))
            chunk = difference[start:start + block]
            chunks.append(chunk)
            total += len(chunk)
        sample = np.concatenate(chunks)[:count]
        wins += float(np.prod(1.0 + sample) > 1.0)
    return wins / simulations


def candidate_name(rule: str, cap: float) -> str:
    return f"{rule}__cap_{int(round(cap * 100)):02d}pct"


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    final_path = OUTPUT / "final_result.json"
    seal = json.loads(SEAL.read_text()) if SEAL.exists() else {}
    sealed = seal.get("sealed_sha256", {})
    seal_valid = bool(sealed) and all(
        (ROOT / path).exists() and sha256(ROOT / path) == digest for path, digest in sealed.items()
    )
    if not seal_valid or final_path.exists():
        print(json.dumps({
            "status": "blocked_execution_seal" if not seal_valid else "blocked_one_shot_already_complete",
            "live_trading_enabled": False,
        }, indent=2))
        return 0

    document = json.loads(SOURCE.read_text())
    by_id = {item["strategy"]["id"]: item for item in document["strategies"]}
    base_item = by_id[config["base_strategy_id"]]
    sleeve_item = by_id[config["sleeve_strategy_id"]]

    # ---- stage 0: reconciliation, fail closed before any performance number
    tolerance = float(config["daily_reconciliation"]["tolerance"])
    reconciliation = {
        "base": reconcile(base_item, tolerance),
        "sleeve": reconcile(sleeve_item, tolerance),
    }
    reconciliation["all_passed"] = bool(
        reconciliation["base"]["all_passed"] and reconciliation["sleeve"]["all_passed"]
    )
    if config["daily_reconciliation"]["fail_closed"] and not reconciliation["all_passed"]:
        (OUTPUT / "reconciliation_failure.json").write_text(json.dumps(reconciliation, indent=2) + "\n")
        print(json.dumps({"status": "aborted_daily_reconciliation_failed", "reconciliation": reconciliation}, indent=2))
        return 1

    # ---- stage 1: unlever both sources
    base = unlever(base_item, config["base_source_reconstruction"])
    sleeve = unlever(sleeve_item, config["sleeve_source_reconstruction"])

    anchor = config["base_source_reconstruction"]
    published = float(anchor["published_cash_only_trailing_52w"])
    rebuilt = float((1.0 + base["net_as_published"].iloc[-52:]).prod() - 1.0)
    anchor_error = abs(rebuilt - published)
    if anchor_error > float(anchor["reconciliation_tolerance"]):
        print(json.dumps({
            "status": "aborted_cash_only_anchor_mismatch",
            "published": published, "rebuilt": rebuilt, "error": anchor_error,
        }, indent=2))
        return 1

    # ---- cost symmetry: the sleeve was published with zero charged cost
    sleeve_cost_bps = float(config["holdings_turnover_cost_bps"])
    cost_symmetry = {
        "base_implied_average_cost_bps": reconciliation["base"]["implied_average_cost_bps"],
        "sleeve_implied_average_cost_bps": reconciliation["sleeve"]["implied_average_cost_bps"],
        "sleeve_total_turnover": reconciliation["sleeve"]["charged_total_turnover"],
        "sleeve_uncharged_cost_at_experiment_bps": float(
            reconciliation["sleeve"]["charged_total_turnover"] * sleeve_cost_bps / 10000.0
        ),
        "asymmetry_detected": bool(
            reconciliation["sleeve"]["implied_average_cost_bps"] < sleeve_cost_bps - 1.0
        ),
        "correction": "All allocator paths charge combined-book turnover at the experiment rate, so both sources pay the same price to trade.",
    }

    frame = pd.concat([
        base["gross"].rename("base_gross"),
        sleeve["gross"].rename("sleeve_gross"),
        base["net_as_published"].rename("base_net"),
        sleeve["net_as_published"].rename("sleeve_net"),
    ], axis=1).dropna()
    if len(frame) < 130:
        raise RuntimeError("insufficient common history for the frozen split")
    dates = list(frame.index)
    base_h = {stamp: base["holdings"][stamp] for stamp in dates}
    sleeve_h = {stamp: sleeve["holdings"][stamp] for stamp in dates}

    signal_frame = pd.DataFrame({"base": frame.base_net, "sleeve": frame.sleeve_net}, index=frame.index)
    signals = causal_signals(signal_frame, config)

    locked_weeks = config["selection"]["locked_replay_weeks"]
    purge_weeks = config["selection"]["purge_weeks"]
    locked_start = len(frame) - locked_weeks
    locked_dates = dates[locked_start:]
    development_end = locked_start - purge_weeks

    # ---- stage 3: breadth
    overlap_series = pd.Series(
        {stamp: holdings_overlap(base_h[stamp], sleeve_h[stamp]) for stamp in dates}
    )
    window = config["breadth"]["overlap_window_weeks"]
    shared_names = sorted(set(base_h[dates[-1]]) & set(sleeve_h[dates[-1]]))
    breadth = {
        "mean_holdings_overlap_full": float(overlap_series.mean()),
        "mean_holdings_overlap_recent": float(overlap_series.iloc[-window:].mean()),
        "min_holdings_overlap": float(overlap_series.min()),
        "max_holdings_overlap": float(overlap_series.max()),
        "return_correlation_full": float(frame.base_net.corr(frame.sleeve_net)),
        "return_correlation_recent": float(frame.base_net.iloc[-window:].corr(frame.sleeve_net.iloc[-window:])),
        "effective_independent_strategies": effective_independent_strategies(
            frame[["base_net", "sleeve_net"]].iloc[-window:]
        ),
        "shared_names_final_week": len(shared_names),
        "base_names_final_week": len(base_h[dates[-1]]),
        "sleeve_names_final_week": len(sleeve_h[dates[-1]]),
        "shared_names_sample": shared_names[:30],
        "threshold": float(config["breadth"]["maximum_mean_holdings_overlap"]),
    }
    breadth["passed"] = bool(breadth["mean_holdings_overlap_recent"] <= breadth["threshold"])

    # ---- stage 4: candidates and purged walk-forward selection
    candidates = {
        candidate_name(rule, cap): (rule, cap, target_weights(signals, rule, cap, config))
        for rule in config["candidate_rules"] for cap in config["candidate_caps"]
    }
    folds = expanding_folds(development_end, config)
    cost_bps = float(config["holdings_turnover_cost_bps"])

    fold_rows, scores = [], []
    for name, (rule, cap, targets) in candidates.items():
        path = allocator_path(frame, base_h, sleeve_h, targets, cost_bps)
        candidate_scores, valid_risk = [], True
        for number, (start, end) in enumerate(folds, 1):
            metrics = statistics(path.net_return.iloc[start:end])
            score = objective(metrics, config)
            valid_risk &= metrics["max_drawdown"] >= config["selection"]["minimum_validation_max_drawdown"]
            candidate_scores.append(score)
            fold_rows.append({"candidate": name, "rule": rule, "cap": cap, "fold": number,
                              "validation_start": metrics["start"], "validation_end": metrics["end"],
                              "objective": score, **metrics})
        scores.append({"candidate": name, "rule": rule, "cap": cap,
                       "mean_validation_objective": float(np.mean(candidate_scores)),
                       "minimum_validation_objective": float(np.min(candidate_scores)),
                       "risk_gate_passed": bool(valid_risk)})

    score_frame = pd.DataFrame(scores).sort_values(["risk_gate_passed", "mean_validation_objective"], ascending=[False, False])
    eligible = score_frame[score_frame.risk_gate_passed]
    chosen_row = (eligible if not eligible.empty else score_frame).iloc[0]
    chosen = str(chosen_row.candidate)
    rule, cap, targets = candidates[chosen]

    # ---- stage 5: locked replay
    base_path = base_only_path(frame, base_h, cost_bps).iloc[locked_start:]
    headline_path = allocator_path(frame, base_h, sleeve_h, targets, cost_bps).iloc[locked_start:]
    base_metrics = statistics(base_path.net_return)
    headline_metrics = statistics(headline_path.net_return)

    # ---- concentration, base alone versus the selected combined book
    sector_map = load_sector_map(SECTOR_MAP)
    look_through = {k: v for k, v in config["concentration"]["look_through"].items() if isinstance(v, dict)}
    percentile = float(config["concentration"]["measure_at_percentile"])
    base_concentration = concentration_profile(locked_dates, base_h, sleeve_h, 0.0, sector_map, look_through, percentile)
    selected_concentration = concentration_profile(locked_dates, base_h, sleeve_h, float(cap), sector_map, look_through, percentile)
    per_cap_concentration = {
        f"cap_{int(round(value * 100)):02d}pct": concentration_profile(
            locked_dates, base_h, sleeve_h, float(value), sector_map, look_through, percentile)
        for value in config["candidate_caps"]
    }

    absolute_caps = config["concentration"]["absolute_caps"]
    tolerances = config["concentration"]["incremental_tolerances"]
    key = f"p{int(percentile * 100)}_"
    absolute_base = {name: bool(base_concentration[key + name] <= limit) for name, limit in absolute_caps.items()}
    absolute_selected = {name: bool(selected_concentration[key + name] <= limit) for name, limit in absolute_caps.items()}
    incremental = {
        name: {
            "base": base_concentration[key + name],
            "selected": selected_concentration[key + name],
            "delta": selected_concentration[key + name] - base_concentration[key + name],
            "tolerance": limit,
            "passed": bool(selected_concentration[key + name] - base_concentration[key + name] <= limit),
        }
        for name, limit in tolerances.items()
    }

    # look-through sensitivity: tilt each broad fund further into its largest sector
    shift = float(config["concentration"]["look_through_sensitivity"]["concentrated_shift"])
    perturbed = {}
    for symbol, split in look_through.items():
        if len(split) == 1:
            perturbed[symbol] = dict(split)
            continue
        top = max(split, key=split.get)
        tilted = {sector: (share + shift if sector == top else share) for sector, share in split.items()}
        total = sum(tilted.values())
        perturbed[symbol] = {sector: share / total for sector, share in tilted.items()}
    sensitivity_base = concentration_profile(locked_dates, base_h, sleeve_h, 0.0, sector_map, perturbed, percentile)
    sensitivity_selected = concentration_profile(locked_dates, base_h, sleeve_h, float(cap), sector_map, perturbed, percentile)
    look_through_sensitivity = {
        "perturbed_base_p95_sector": sensitivity_base[key + "max_look_through_sector_weight"],
        "perturbed_selected_p95_sector": sensitivity_selected[key + "max_look_through_sector_weight"],
        "perturbed_delta": sensitivity_selected[key + "max_look_through_sector_weight"] - sensitivity_base[key + "max_look_through_sector_weight"],
        "verdict_unchanged": bool(
            (sensitivity_selected[key + "max_look_through_sector_weight"] - sensitivity_base[key + "max_look_through_sector_weight"] <= tolerances["max_look_through_sector_weight"])
            == incremental["max_look_through_sector_weight"]["passed"]
        ),
    }
    concentration_block = {
        "measured_at_percentile": percentile,
        "base_alone": base_concentration,
        "selected_candidate": selected_concentration,
        "per_cap": per_cap_concentration,
        "absolute_caps": absolute_caps,
        "absolute_passed_base_alone": absolute_base,
        "absolute_passed_selected": absolute_selected,
        "incremental": incremental,
        "look_through_sensitivity": look_through_sensitivity,
        "incumbent_already_breaches_absolute_caps": bool(not all(absolute_base.values())),
    }

    # ---- stage 6: stresses, every one of them inside the locked window
    shock_index = locked_dates[len(locked_dates) // 2]
    top_k_list = config["stress"]["missing_stock_top_k"]
    missing_by_k = {}
    for k in top_k_list:
        drops = {stamp: set(sorted(sleeve_h[stamp], key=lambda s: -abs(sleeve_h[stamp][s]))[:k]) for stamp in dates}
        missing_by_k[f"missing_top_{k}_sleeve_names"] = allocator_path(
            frame, base_h, sleeve_h, targets, cost_bps, drop_symbols_by_week=drops).iloc[locked_start:]

    stress_paths = {
        "double_cost": allocator_path(frame, base_h, sleeve_h, targets, float(config["stress"]["double_cost_bps"])).iloc[locked_start:],
        **{f"delay_{delay}_weeks": allocator_path(frame, base_h, sleeve_h, targets, cost_bps, delay=delay).iloc[locked_start:]
           for delay in config["stress"]["delay_weeks"]},
        "positive_increment_decay": allocator_path(frame, base_h, sleeve_h, targets, cost_bps,
                                                   positive_retention=config["stress"]["positive_increment_retention"]).iloc[locked_start:],
        "sleeve_shock": allocator_path(frame, base_h, sleeve_h, targets, cost_bps,
                                       shock=config["stress"]["sleeve_shock"], shock_index=shock_index).iloc[locked_start:],
        **missing_by_k,
    }
    stress_metrics = {name: statistics(path.net_return) for name, path in stress_paths.items()}
    vacuity = {
        name: bool(float((path.net_return - headline_path.net_return).abs().max()) < 1e-12)
        for name, path in stress_paths.items()
    }

    # ---- leave one issuer out, the project's chronic failure mode
    counts: dict[str, float] = defaultdict(float)
    for stamp in locked_dates:
        for symbol, weight in sleeve_h[stamp].items():
            counts[symbol] += abs(weight)
    top_names = [name for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])][: int(config["stress"]["leave_one_issuer_out_top_n"])]
    leave_one_out = {}
    for name in top_names:
        path = allocator_path(frame, base_h, sleeve_h, targets, cost_bps, excluded_symbols={name}).iloc[locked_start:]
        metrics = statistics(path.net_return)
        leave_one_out[name] = {
            "cagr": metrics["cagr"],
            "sharpe": metrics["sharpe"],
            "max_drawdown": metrics["max_drawdown"],
            "cagr_versus_base": metrics["cagr"] - base_metrics["cagr"],
            "still_beats_base": bool(metrics["cagr"] > base_metrics["cagr"]),
        }
    leave_one_out_summary = {
        "names_tested": top_names,
        "all_still_beat_base": bool(all(entry["still_beats_base"] for entry in leave_one_out.values())) if leave_one_out else False,
        "worst_name": min(leave_one_out, key=lambda n: leave_one_out[n]["cagr"]) if leave_one_out else "",
        "worst_cagr_versus_base": min((entry["cagr_versus_base"] for entry in leave_one_out.values()), default=0.0),
        "detail": leave_one_out,
    }

    # ---- bootstrap with the cumulative, not the local, trial count
    bootstrap = {
        str(block): paired_block_probability(
            headline_path.net_return, base_path.net_return,
            int(config["stress"]["bootstrap_simulations"]), int(block), int(config["stress"]["bootstrap_seed"]) + int(block))
        for block in config["stress"]["bootstrap_blocks"]
    }
    trials = int(config["stress"]["cumulative_trials_searched"])
    familywise_threshold = 1.0 - float(config["stress"]["familywise_alpha"]) / trials

    gates = {
        "daily_reconciliation": bool(reconciliation["all_passed"]),
        "locked_cagr_improvement": bool(headline_metrics["cagr"] - base_metrics["cagr"] >= config["promotion_gates"]["minimum_locked_cagr_improvement"]),
        "locked_sharpe": bool(headline_metrics["sharpe"] - base_metrics["sharpe"] >= config["promotion_gates"]["minimum_locked_sharpe_delta"]),
        "locked_drawdown": bool(headline_metrics["max_drawdown"] >= base_metrics["max_drawdown"] - config["promotion_gates"]["maximum_drawdown_deterioration"]),
        "double_cost_improvement": bool(stress_metrics["double_cost"]["cagr"] > base_metrics["cagr"]),
        "delay_improvement": bool(all(stress_metrics[f"delay_{delay}_weeks"]["cagr"] > base_metrics["cagr"] for delay in config["stress"]["delay_weeks"])),
        "missing_stock_improvement": bool(all(stress_metrics[f"missing_top_{k}_sleeve_names"]["cagr"] > base_metrics["cagr"] for k in top_k_list)),
        "leave_one_issuer_out_improvement": bool(leave_one_out_summary["all_still_beat_base"]),
        "incremental_concentration": bool(all(entry["passed"] for entry in incremental.values())),
        "absolute_concentration": bool(all(absolute_selected.values())),
        "breadth_overlap": bool(breadth["passed"]),
        "familywise_bootstrap": bool(all(probability >= familywise_threshold for probability in bootstrap.values())),
        "source_research_gate": bool(config["source_research_gate_passed"]),
    }
    promoted = all(gates.values())

    # ---- stage 7: financing is not evaluated until the unlevered book has earned it
    if config["financing"]["evaluate_only_if_unlevered_promoted"] and not promoted:
        financing_block = {
            "evaluated": False,
            "reason": "The unlevered allocator did not clear every gate. Financing multiplies whatever edge exists, including an edge of zero, so no levered path was computed.",
            "failed_gates": sorted(name for name, passed in gates.items() if not passed),
        }
    else:
        financed = {}
        for exposure in config["financing"]["gross_exposures"]:
            for rate in config["financing"]["annual_financing_rates"]:
                levered = headline_path.net_return * exposure - (exposure - 1.0) * rate / 52.0
                financed[f"gross_{exposure}x_rate_{int(rate * 100)}pct"] = statistics(levered)
        financing_block = {"evaluated": True, "paths": financed}

    # ---- evidence
    pd.DataFrame(fold_rows).to_csv(OUTPUT / "purged_walk_forward_folds.csv", index=False)
    score_frame.to_csv(OUTPUT / "candidate_selection.csv", index=False)
    pd.concat([frame, signals, headline_path.add_prefix("selected_"),
               overlap_series.rename("holdings_overlap")], axis=1).rename_axis("Date").to_csv(OUTPUT / "selected_path.csv")
    pd.DataFrame([{"stress": name, "is_vacuous": vacuity[name], **metrics} for name, metrics in stress_metrics.items()]).to_csv(
        OUTPUT / "locked_stress_results.csv", index=False)
    pd.DataFrame([{"symbol": name, **entry} for name, entry in leave_one_out.items()]).to_csv(
        OUTPUT / "leave_one_issuer_out.csv", index=False)
    pd.DataFrame([{"allocation": name, **profile} for name, profile in per_cap_concentration.items()]).to_csv(
        OUTPUT / "concentration_by_allocation.csv", index=False)

    result = {
        "experiment_id": config["experiment_id"],
        "supersedes": config["supersedes"],
        "status": "completed_research_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen_config_sha256": sha256(CONFIG),
        "frozen_source_sha256": sha256(SOURCE),
        "frozen_sector_map_sha256": sha256(SECTOR_MAP),
        "daily_reconciliation": reconciliation,
        "cash_only_anchor": {"published": published, "rebuilt": rebuilt, "absolute_error": anchor_error, "passed": True},
        "cost_symmetry": cost_symmetry,
        "breadth": breadth,
        "selection_protocol": {
            "candidate_count": len(candidates),
            "fold_count": len(folds),
            "development_weeks": int(development_end),
            "purge_weeks": purge_weeks,
            "locked_replay_weeks": locked_weeks,
            "cumulative_trials_searched": trials,
            "locked_replay_is_selection_contaminated": bool(config["locked_replay_is_selection_contaminated"]),
            "locked_replay_contamination_reason": config["locked_replay_contamination_reason"],
        },
        "selected_candidate": {"name": chosen, "rule": rule, "cap": float(cap),
                               "mean_validation_objective": float(chosen_row.mean_validation_objective)},
        "locked_replay": {
            "base": base_metrics,
            "selected": headline_metrics,
            "cagr_improvement": headline_metrics["cagr"] - base_metrics["cagr"],
            "sharpe_improvement": headline_metrics["sharpe"] - base_metrics["sharpe"],
            "drawdown_change": headline_metrics["max_drawdown"] - base_metrics["max_drawdown"],
        },
        "concentration": concentration_block,
        "stresses": stress_metrics,
        "stress_vacuity_check": vacuity,
        "leave_one_issuer_out": leave_one_out_summary,
        "paired_moving_block_probability_of_outperformance": bootstrap,
        "familywise_probability_threshold": familywise_threshold,
        "promotion_gates": gates,
        "promoted": promoted,
        "conclusion": "eligible_for_forward_challenger" if promoted else "diagnostic_only_not_a_replacement",
        "financing": financing_block,
        "source_research_gate_reason": config["source_research_gate_reason"],
        "live_trading_enabled": False,
    }
    final_path.write_text(json.dumps(result, indent=2) + "\n")
    artifacts = ["purged_walk_forward_folds.csv", "candidate_selection.csv", "selected_path.csv",
                 "locked_stress_results.csv", "leave_one_issuer_out.csv", "concentration_by_allocation.csv",
                 "final_result.json"]
    (OUTPUT / "artifact_manifest.json").write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": {name: sha256(OUTPUT / name) for name in artifacts},
        "live_trading_enabled": False,
    }, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
