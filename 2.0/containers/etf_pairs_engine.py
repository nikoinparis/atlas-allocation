#!/usr/bin/env python3
"""Isolated causal Engle-Granger ETF pairs engine."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import warnings
from collections import defaultdict, deque
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
import statsmodels
from statsmodels.tsa.stattools import coint
from pair_protocol import long_short_turnover, update_pair_state


@dataclass(frozen=True)
class PairModel:
    x: str
    y: str
    alpha: float
    beta: float
    spread_mean: float
    spread_std: float
    p_value: float
    test_statistic: float
    half_life: float
    return_correlation: float

    @property
    def key(self) -> str:
        return f"{self.x}|{self.y}"


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise RuntimeError(f"refusing to write empty artifact {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({key: format(value, ".12g") if isinstance(value, float) else value for key, value in row.items()} for row in rows)


def pair_model(frame: pd.DataFrame, x: str, y: str, lookback: int, *, require_correlation: bool) -> PairModel | None:
    sample = frame[[x, y]].dropna().tail(lookback)
    if len(sample) < lookback or sample.index[-1] != frame.index[-1]:
        return None
    logs = np.log(sample.to_numpy(dtype=float))
    changes = np.diff(logs, axis=0)
    correlation = float(np.corrcoef(changes[:, 0], changes[:, 1])[0, 1])
    if not math.isfinite(correlation) or (require_correlation and correlation < 0.5):
        return None
    x_values, y_values = logs[:, 0], logs[:, 1]
    design = np.column_stack([np.ones(len(x_values)), x_values])
    alpha, beta = np.linalg.lstsq(design, y_values, rcond=None)[0]
    if not 0.1 <= beta <= 10.0:
        return None
    residual = y_values - alpha - beta * x_values
    spread_std = float(np.std(residual, ddof=1))
    if not math.isfinite(spread_std) or spread_std <= 1e-10:
        return None
    delta, lagged = np.diff(residual), residual[:-1]
    reversion = np.linalg.lstsq(np.column_stack([np.ones(len(lagged)), lagged]), delta, rcond=None)[0][1]
    if not reversion < 0.0:
        return None
    half_life = -math.log(2.0) / float(reversion)
    if not 2.0 <= half_life <= 60.0:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        statistic, p_value, _ = coint(y_values, x_values, trend="c", autolag="bic")
    if not math.isfinite(float(p_value)):
        return None
    return PairModel(
        x=x, y=y, alpha=float(alpha), beta=float(beta),
        spread_mean=float(np.mean(residual)), spread_std=spread_std,
        p_value=float(p_value), test_statistic=float(statistic),
        half_life=float(half_life), return_correlation=correlation,
    )


def bh_eligible(models: list[PairModel], q: float, raw_maximum: float) -> list[PairModel]:
    ordered = sorted(models, key=lambda item: (item.p_value, item.key))
    cutoff = -1
    total = len(ordered)
    for index, model in enumerate(ordered, start=1):
        if model.p_value <= q * index / total:
            cutoff = index
    if cutoff < 0:
        return []
    threshold = ordered[cutoff - 1].p_value
    return [model for model in ordered if model.p_value <= min(threshold, raw_maximum)]


def disjoint(models: list[PairModel], maximum: int) -> list[PairModel]:
    selected, used = [], set()
    for model in sorted(models, key=lambda item: (item.p_value, item.half_life, item.key)):
        if model.x in used or model.y in used:
            continue
        selected.append(model)
        used.update((model.x, model.y))
        if len(selected) >= maximum:
            break
    return selected


def random_disjoint(models: list[PairModel], count: int, seed: int) -> list[PairModel]:
    shuffled = list(models)
    random.Random(seed).shuffle(shuffled)
    selected, used = [], set()
    for model in shuffled:
        if model.x in used or model.y in used:
            continue
        selected.append(model)
        used.update((model.x, model.y))
        if len(selected) >= count:
            break
    return selected


def z_score(model: PairModel, prices: pd.Series) -> float:
    spread = math.log(float(prices[model.y])) - model.alpha - model.beta * math.log(float(prices[model.x]))
    return (spread - model.spread_mean) / model.spread_std


def cointegration_guard_p_value(frame: pd.DataFrame, model: PairModel, lookback: int) -> float | None:
    sample = frame[[model.x, model.y]].dropna().tail(lookback)
    if len(sample) < lookback or sample.index[-1] != frame.index[-1]:
        return None
    logs = np.log(sample.to_numpy(dtype=float))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, p_value, _ = coint(logs[:, 1], logs[:, 0], trend="c", autolag="bic")
    return float(p_value) if math.isfinite(float(p_value)) else None


def target_weights(models: list[PairModel], states: dict[str, int]) -> dict[str, float]:
    active = [model for model in models if states.get(model.key, 0) != 0]
    if not active:
        return {}
    weights: dict[str, float] = defaultdict(float)
    pair_leg = 0.5 / len(active)
    for model in active:
        y_sign = states[model.key]
        weights[model.y] += y_sign * pair_leg
        weights[model.x] -= y_sign * pair_leg
    return dict(weights)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    symbols = sorted(json.loads(Path(args.universe).read_text(encoding="utf-8"))["symbols"])
    raw = pd.read_csv(args.prices, usecols=["observation_date", "ticker", "adjusted_close"])
    raw = raw[raw["ticker"].isin(symbols)]
    prices = raw.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    prices = prices.reindex(columns=symbols)
    dates = list(prices.index)
    lookback = int(config["formation"]["lookback_days"])
    formation_indexes = []
    previous_quarter = None
    for index, day in enumerate(dates):
        stamp = pd.Timestamp(day)
        quarter = (stamp.year, stamp.quarter)
        if quarter != previous_quarter and index >= lookback - 1:
            formation_indexes.append(index)
        previous_quarter = quarter
    formation_set = set(formation_indexes)
    variants = ("real", "inverted", "random_pairs", "stale_5d")
    current_models: dict[str, list[PairModel]] = {variant: [] for variant in variants}
    states: dict[str, dict[str, int]] = {variant: {} for variant in variants}
    disabled: dict[str, set[str]] = {variant: set() for variant in variants}
    stale_z: dict[str, deque[float]] = {}
    weights: dict[str, dict[str, float]] = {variant: {} for variant in variants}
    rows: list[dict[str, object]] = []
    selected_rows: list[dict[str, object]] = []
    formation_rows: list[dict[str, object]] = []
    last_guard_month = None

    for index in range(lookback - 1, len(dates) - 1):
        day, next_day = dates[index], dates[index + 1]
        history = prices.iloc[:index + 1]
        if index in formation_set:
            tested = []
            random_pool = []
            for x, y in combinations(symbols, 2):
                model = pair_model(history, x, y, lookback, require_correlation=True)
                if model is not None:
                    tested.append(model)
                    random_pool.append(model)
            eligible = bh_eligible(tested, float(config["formation"]["benjamini_hochberg_fdr"]), float(config["formation"]["raw_p_value_maximum"]))
            chosen = disjoint(eligible, int(config["formation"]["maximum_pairs"]))
            stamp = pd.Timestamp(day)
            seed = int(hashlib.sha256(f"{day}|pairs-v1".encode()).hexdigest()[:12], 16)
            random_chosen = random_disjoint(random_pool, len(chosen), seed)
            for variant in variants:
                current_models[variant] = random_chosen if variant == "random_pairs" else chosen
                states[variant] = {model.key: 0 for model in current_models[variant]}
                disabled[variant] = set()
            stale_z = {model.key: deque(maxlen=6) for model in chosen}
            last_guard_month = pd.Timestamp(day).to_period("M")
            formation_rows.append({
                "formation_date": day, "available_assets": int(history.iloc[-lookback:].notna().all().sum()),
                "correlation_screened_pairs": len(tested), "bh_eligible_pairs": len(eligible),
                "selected_pairs": len(chosen), "random_control_pairs": len(random_chosen),
            })
            for variant, models in (("real", chosen), ("random_pairs", random_chosen)):
                for rank, model in enumerate(models, start=1):
                    selected_rows.append({
                        "formation_date": day, "variant": variant, "rank": rank, "x": model.x, "y": model.y,
                        "cointegration_p_value": model.p_value, "cointegration_test_statistic": model.test_statistic,
                        "hedge_alpha": model.alpha, "hedge_beta": model.beta, "spread_mean": model.spread_mean,
                        "spread_std": model.spread_std, "half_life_days": model.half_life,
                        "daily_return_correlation": model.return_correlation,
                    })

        month = pd.Timestamp(day).to_period("M")
        if last_guard_month is not None and month != last_guard_month:
            checked = {}
            for variant in variants:
                base_name = "random_pairs" if variant == "random_pairs" else "real"
                for model in current_models[variant]:
                    cache_key = (base_name, model.key)
                    if cache_key not in checked:
                        guard_p = cointegration_guard_p_value(history, model, lookback)
                        checked[cache_key] = guard_p is not None and guard_p <= 0.10
                    if not checked[cache_key]:
                        states[variant][model.key] = 0
                        disabled[variant].add(model.key)
            last_guard_month = month

        today = prices.iloc[index]
        tomorrow = prices.iloc[index + 1]
        for variant in variants:
            for model in current_models[variant]:
                if model.key in disabled[variant] or pd.isna(today[model.x]) or pd.isna(today[model.y]):
                    states[variant][model.key] = 0
                    continue
                z = z_score(model, today)
                if variant == "stale_5d":
                    history_z = stale_z.setdefault(model.key, deque(maxlen=6))
                    history_z.append(z)
                    if len(history_z) < 6:
                        continue
                    z = history_z[0]
                state, broken = update_pair_state(states[variant][model.key], z, invert=variant == "inverted")
                states[variant][model.key] = state
                if broken:
                    disabled[variant].add(model.key)
            target = target_weights(current_models[variant], states[variant])
            turnover = long_short_turnover(weights[variant], target)
            gross_return = 0.0
            valid = True
            for asset, weight in target.items():
                if pd.isna(today[asset]) or pd.isna(tomorrow[asset]):
                    valid = False
                    break
                gross_return += weight * (float(tomorrow[asset]) / float(today[asset]) - 1.0)
            if not valid:
                target, turnover, gross_return = {}, sum(abs(value) for value in weights[variant].values()), 0.0
            rows.append({
                "variant": variant, "decision_date": day, "realization_date": next_day,
                "gross_return": gross_return, "turnover": turnover,
                "short_exposure": sum(-value for value in target.values() if value < 0.0),
                "gross_exposure": sum(abs(value) for value in target.values()),
                "active_pairs": sum(value != 0 for value in states[variant].values()),
                "selected_pairs": len(current_models[variant]),
            })
            weights[variant] = target

    write_csv(output / "daily_periods.csv", rows)
    write_csv(output / "selected_pairs.csv", selected_rows)
    write_csv(output / "formation_audit.csv", formation_rows)
    metadata = {
        "engine": "causal_etf_pairs_v1", "python": platform.python_version(),
        "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__, "symbols": symbols, "daily_rows": len(rows),
        "formations": len(formation_rows), "selected_pair_rows": len(selected_rows),
        "variants": list(variants), "first_decision": rows[0]["decision_date"], "last_realization": rows[-1]["realization_date"],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
