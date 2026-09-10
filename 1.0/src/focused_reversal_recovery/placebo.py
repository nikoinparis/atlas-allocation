"""Placebo tests for focused reversal timing."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics
from .backtest import DEFAULT_TILT, random_signal_like, run_active_backtest
from .reversal_signals import CANDIDATES


def run_placebo_tests(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    reference_candidate: str = "focused_reversal_composite",
    n_iter: int = 200,
) -> pd.DataFrame:
    active_col = CANDIDATES[reference_candidate]["active"]
    ref_signal = features[["Date", "ticker", "market_state", active_col]].rename(columns={active_col: "active"})
    ref = run_active_backtest(ref_signal, targets, reference_candidate, DEFAULT_TILT, comparison_kind="reference")
    ref_sharpe = float(ref["summary"]["overlay_sharpe"])

    placebo_sharpes = []
    placebo_cagrs = []
    for i in range(n_iter):
        signal = random_signal_like(features, active_col, seed=10_000 + i)
        result = run_active_backtest(signal, targets, "random_timing_placebo", DEFAULT_TILT, comparison_kind="placebo")
        placebo_sharpes.append(float(result["summary"]["overlay_sharpe"]))
        placebo_cagrs.append(float(result["summary"]["overlay_cagr"]))

    block_sharpes = _block_bootstrap_sharpes(ref["returns"], n_iter=n_iter, seed=44)
    rows = [
        {
            "test": "random_entry_same_frequency",
            "reference_candidate": reference_candidate,
            "n_iterations": n_iter,
            "reference_sharpe": ref_sharpe,
            "reference_cagr": float(ref["summary"]["overlay_cagr"]),
            "placebo_mean_sharpe": float(np.nanmean(placebo_sharpes)),
            "placebo_median_sharpe": float(np.nanmedian(placebo_sharpes)),
            "placebo_p95_sharpe": float(np.nanpercentile(placebo_sharpes, 95)),
            "placebo_mean_cagr": float(np.nanmean(placebo_cagrs)),
            "pct_placebo_beating_reference": float(np.mean(np.array(placebo_sharpes) >= ref_sharpe)),
            "same_signal_rows": int(pd.to_numeric(ref_signal["active"], errors="coerce").fillna(0).sum()),
        },
        {
            "test": "block_bootstrap_weekly_returns",
            "reference_candidate": reference_candidate,
            "n_iterations": n_iter,
            "reference_sharpe": ref_sharpe,
            "reference_cagr": float(ref["summary"]["overlay_cagr"]),
            "placebo_mean_sharpe": float(np.nanmean(block_sharpes)),
            "placebo_median_sharpe": float(np.nanmedian(block_sharpes)),
            "placebo_p95_sharpe": float(np.nanpercentile(block_sharpes, 95)),
            "placebo_mean_cagr": np.nan,
            "pct_placebo_beating_reference": float(np.mean(np.array(block_sharpes) >= ref_sharpe)),
            "same_signal_rows": int(pd.to_numeric(ref_signal["active"], errors="coerce").fillna(0).sum()),
        },
    ]
    return pd.DataFrame(rows)


def _block_bootstrap_sharpes(returns: pd.Series, n_iter: int, seed: int, block: int = 8) -> list[float]:
    r = pd.to_numeric(returns, errors="coerce").dropna()
    if len(r) < block * 3:
        return [np.nan] * n_iter
    rng = np.random.default_rng(seed)
    values = r.values
    sharpes = []
    starts = np.arange(0, len(values) - block + 1)
    for _ in range(n_iter):
        sampled = []
        while len(sampled) < len(values):
            start = int(rng.choice(starts))
            sampled.extend(values[start : start + block])
        boot = pd.Series(sampled[: len(values)])
        sharpes.append(metrics.sharpe(boot))
    return sharpes

