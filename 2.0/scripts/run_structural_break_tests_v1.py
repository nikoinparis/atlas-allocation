#!/usr/bin/env python3
"""Find structural breaks from the data instead of assuming where they are.

Queue item A6, and the first structural-break test in 272 recorded steps.

The owner keeps asking whether a strategy that worked last decade still works
now. Every answer so far came from splitting the sample at a date I chose. That
is an assumption dressed as a test. This scans every candidate break date and
lets the data pick.

The statistic is a supremum Wald test for a break in mean, and its null is
obtained by a moving-block bootstrap rather than a table. Asymptotic critical
values for sup-Wald assume independence, and weekly strategy returns are not
independent; bootstrapping under the no-break null with blocks preserves the
autocorrelation that would otherwise manufacture significance.

A structural break is a description of the past. It does not predict the next one.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/structural_break_registry_v1.json"

SERIES = {
    "sector_ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
    "residual_composite": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
    "cash_conversion_b20": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth_top_five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}
PANEL = "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
TRIM = 0.15


def sup_wald(values: np.ndarray) -> tuple[float, int]:
    """Largest Wald statistic for a break in mean over interior candidate dates."""
    n = len(values)
    low, high = int(TRIM * n), int((1 - TRIM) * n)
    best, position = -np.inf, -1
    total = values.sum()
    total_sq = (values ** 2).sum()
    running = 0.0
    for i in range(1, n):
        running += values[i - 1]
        if i < low or i > high:
            continue
        left_n, right_n = i, n - i
        left_mean, right_mean = running / left_n, (total - running) / right_n
        pooled = (total_sq - (running ** 2) / left_n - ((total - running) ** 2) / right_n) / (n - 2)
        if pooled <= 0:
            continue
        statistic = (left_mean - right_mean) ** 2 / (pooled * (1 / left_n + 1 / right_n))
        if statistic > best:
            best, position = statistic, i
    return float(best), position


def block_bootstrap_null(values: np.ndarray, draws: int, block: int, seed: int) -> np.ndarray:
    """Resample under the no-break null, preserving autocorrelation."""
    centred = values - values.mean()
    n = len(centred)
    blocks = max(1, n // block)
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(draws):
        starts = rng.integers(0, max(1, n - block), size=blocks + 1)
        sample = np.concatenate([centred[s:s + block] for s in starts])[:n]
        if len(sample) < n:
            continue
        out.append(sup_wald(sample)[0])
    return np.array(out)


def cusum_of_squares(values: np.ndarray) -> dict[str, float]:
    squares = values ** 2
    cumulative = np.cumsum(squares) / squares.sum()
    n = len(values)
    expected = np.arange(1, n + 1) / n
    deviation = cumulative - expected
    position = int(np.argmax(np.abs(deviation)))
    return {"max_abs_deviation": float(np.abs(deviation).max()), "position": position}


def read_series(relative: str) -> pd.Series:
    frame = pd.read_csv(ROOT / relative)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/structural_break_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    boot = registry["method"]["bootstrap"]
    threshold = float(registry["bonferroni_threshold"])

    series = {name: read_series(path) for name, path in SERIES.items()}
    prices = pd.read_csv(ROOT / PANEL, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    market = returns.mean(axis=1, skipna=True).dropna()
    market.index = pd.to_datetime(market.index, utc=True)
    series["equal_weight_universe_2011_2026"] = market

    rows = []
    for name, values in series.items():
        array = values.to_numpy(dtype=float)
        if len(array) < 60:
            continue
        statistic, position = sup_wald(array)
        null = block_bootstrap_null(array, boot["draws"], boot["block_weeks"], boot["seed"])
        p_value = float((null >= statistic).mean()) if len(null) else float("nan")
        cusum = cusum_of_squares(array)
        left, right = array[:position], array[position:]
        rows.append({
            "series": name, "weeks": len(array),
            "start": str(values.index.min().date()), "end": str(values.index.max().date()),
            "break_date": str(values.index[position].date()) if position > 0 else None,
            "sup_wald": statistic, "bootstrap_p": p_value,
            "clears_bonferroni": bool(p_value < threshold),
            "mean_before_annualised": float(left.mean() * 52) if len(left) else None,
            "mean_after_annualised": float(right.mean() * 52) if len(right) else None,
            "volatility_before": float(left.std(ddof=1) * np.sqrt(52)) if len(left) > 2 else None,
            "volatility_after": float(right.std(ddof=1) * np.sqrt(52)) if len(right) > 2 else None,
            "cusum_sq_max_deviation": cusum["max_abs_deviation"],
            "cusum_sq_date": str(values.index[cusum["position"]].date()),
        })
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "structural_breaks.csv", index=False)

    breaking = table[table.clears_bonferroni]
    dates = sorted(breaking.break_date.dropna().tolist())
    if table.empty:
        verdict = "no series long enough to test"
    elif breaking.empty:
        verdict = ("no series shows a structural break in mean that survives a block-bootstrap null. "
                   "The regime hypothesis is not supported by these series, and the window splits used "
                   "so far were arbitrary but harmless.")
    elif len(set(d[:4] for d in dates)) == 1:
        verdict = (f"breaks cluster in {dates[0][:4]}: {', '.join(dates)}. That date, not one I chose, "
                   f"is where future tests should split, and prior results split elsewhere should be re-read.")
    else:
        verdict = (f"breaks found at different dates per series ({', '.join(dates)}), which would be the "
                   f"first evidence here that the strategies respond to different regimes rather than one")

    result = {"experiment": "structural_break_v1", "queue_item": "A6",
              "first_structural_break_test_in_the_project": True,
              "declared_trials": registry["declared_trials"], "bonferroni_threshold": threshold,
              "bootstrap": boot, "rows": rows, "break_dates": dates, "verdict": verdict,
              "caveat": registry["interpretation_fixed_in_advance"]["always"],
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    show = ["series", "weeks", "break_date", "sup_wald", "bootstrap_p", "clears_bonferroni",
            "mean_before_annualised", "mean_after_annualised", "volatility_before", "volatility_after"]
    print(table[show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
