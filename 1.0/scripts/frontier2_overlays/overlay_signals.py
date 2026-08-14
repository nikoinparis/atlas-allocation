"""Reusable causal overlay signals for the Frontier-2 risk-structure sprint.

Every signal here follows the same causality convention:

    * Raw inputs end at Friday close of week ``t``.
    * The returned series is shifted one extra week, so the value used for
      week-``t`` decision weights only uses information through week ``t-1``.
      This is one week more conservative than strictly required by the
      production Friday-close convention and removes any timing dispute.
    * ``stressed_panic`` weeks are always forced to the neutral value by the
      runner, never here, so the raw signal series stays inspectable.

Signals:
    * VIX term-structure stress gate (persistent backwardation + resolution)
    * DAA-style canary momentum count (EEM + IEF as the AGG proxy)
    * Absorption-ratio fragility shift (Kritzman-Li-Page-Rigobon style)
    * Realized-vol scalar for conservative vol-managed offense scaling
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from path1_path3_research_utils import HUB, load_numeric_panel  # noqa: E402


CANARY_TICKERS = ("EEM", "IEF")
ABSORPTION_UNIVERSE = (
    "SPY", "QQQ", "IWM", "EFA", "EEM", "EWJ", "VNQ", "HYG", "LQD", "TLT",
    "IEF", "GLD", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY",
)


def load_vix_term_structure(warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(HUB / "vix_term_structure.csv", warnings, "vix_term_structure.csv")


def load_weekly_prices(warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(HUB / "weekly_prices.csv", warnings, "weekly_prices.csv")


def load_weekly_returns(warnings: list[str]) -> pd.DataFrame:
    return load_numeric_panel(HUB / "weekly_returns.csv", warnings, "weekly_returns.csv")


def vix_backwardation_events(
    vix: pd.DataFrame,
    index: pd.Index,
    *,
    persist_weeks: int = 2,
    rerisk_window_weeks: int = 4,
) -> pd.DataFrame:
    """Return causal backwardation persistence and resolution-event flags.

    ``bw_persistent`` is 1 when the 1m-3m VIX slope has been negative for at
    least ``persist_weeks`` consecutive weeks. ``bw_resolved_window`` is 1 for
    the ``rerisk_window_weeks`` weeks after a persistent backwardation episode
    flips back to contango. Both columns are shifted one week before reindexing
    so week-t decisions only see week t-1 information.
    """

    slope = pd.to_numeric(vix.get("slope_1m_3m"), errors="coerce")
    bw = (slope < 0).astype(float)
    bw[slope.isna()] = np.nan

    run = bw.copy()
    streak = 0.0
    values = []
    for v in bw.to_numpy():
        if np.isnan(v):
            streak = 0.0
            values.append(np.nan)
            continue
        streak = streak + 1.0 if v > 0 else 0.0
        values.append(streak)
    run = pd.Series(values, index=bw.index)

    persistent = (run >= persist_weeks).astype(float)
    # Resolution event: last week was a persistent episode, this week is contango.
    resolved = ((persistent.shift(1) > 0) & (bw == 0)).astype(float)
    resolved_window = (
        resolved.rolling(rerisk_window_weeks, min_periods=1).max().fillna(0.0)
    )

    out = pd.DataFrame(
        {
            "slope_1m_3m": slope,
            "bw_persistent": persistent,
            "bw_resolved_window": resolved_window,
        }
    )
    return out.shift(1).reindex(index).fillna(0.0)


def keller_13612w_momentum(prices: pd.Series) -> pd.Series:
    """Weekly analog of the Keller 13612W filter (1/3/6/12-month momentum)."""

    p = pd.to_numeric(prices, errors="coerce")
    return (
        12.0 * (p / p.shift(4) - 1.0)
        + 4.0 * (p / p.shift(13) - 1.0)
        + 2.0 * (p / p.shift(26) - 1.0)
        + (p / p.shift(52) - 1.0)
    )


def canary_bad_count(
    prices: pd.DataFrame,
    index: pd.Index,
    *,
    tickers: tuple[str, ...] = CANARY_TICKERS,
    confirm_weeks: int = 2,
) -> pd.Series:
    """Count of canary assets with non-positive 13612W momentum, confirmed.

    The raw count only takes effect after it has been unchanged for
    ``confirm_weeks`` consecutive weeks (hysteresis against flip-flopping);
    until confirmed, the previous confirmed count is held. Shifted one week.
    """

    missing = [t for t in tickers if t not in prices.columns]
    if missing:
        raise ValueError(f"Canary tickers missing from weekly prices: {missing}")
    moms = pd.DataFrame({t: keller_13612w_momentum(prices[t]) for t in tickers})
    raw_count = (moms <= 0).sum(axis=1).astype(float)
    raw_count[moms.isna().any(axis=1)] = np.nan

    confirmed = []
    held = np.nan
    stable = 0
    prev = np.nan
    for v in raw_count.to_numpy():
        if np.isnan(v):
            confirmed.append(held)
            stable = 0
            prev = np.nan
            continue
        stable = stable + 1 if v == prev else 1
        prev = v
        if stable >= confirm_weeks or np.isnan(held):
            held = v
        confirmed.append(held)
    out = pd.Series(confirmed, index=raw_count.index)
    return out.shift(1).reindex(index).ffill()


def absorption_ratio_shift(
    returns: pd.DataFrame,
    index: pd.Index,
    *,
    universe: tuple[str, ...] = ABSORPTION_UNIVERSE,
    cov_window: int = 52,
    n_components: int = 2,
    fast_window: int = 4,
    slow_window: int = 52,
) -> pd.DataFrame:
    """Absorption ratio of the risky ETF universe and its standardized shift.

    AR_t = share of total variance of the trailing ``cov_window`` weeks of
    standardized returns explained by the top ``n_components`` eigenvectors.
    The shift is (fast mean - slow mean) / slow std, per Kritzman et al.'s
    fast/slow construction. Shifted one week before reindexing.
    """

    cols = [c for c in universe if c in returns.columns]
    r = returns[cols].apply(pd.to_numeric, errors="coerce")

    ar_values: list[float] = []
    dates: list[pd.Timestamp] = []
    arr = r.to_numpy()
    for i in range(len(r)):
        if i + 1 < cov_window:
            ar_values.append(np.nan)
            dates.append(r.index[i])
            continue
        window = arr[i + 1 - cov_window : i + 1]
        valid_cols = ~np.isnan(window).any(axis=0)
        w = window[:, valid_cols]
        if w.shape[1] < max(4, n_components + 1):
            ar_values.append(np.nan)
            dates.append(r.index[i])
            continue
        std = w.std(axis=0, ddof=1)
        keep = std > 0
        w = (w[:, keep] - w[:, keep].mean(axis=0)) / std[keep]
        cov = np.cov(w, rowvar=False)
        eig = np.sort(np.linalg.eigvalsh(cov))[::-1]
        total = eig.sum()
        ar_values.append(float(eig[:n_components].sum() / total) if total > 0 else np.nan)
        dates.append(r.index[i])

    ar = pd.Series(ar_values, index=pd.Index(dates))
    fast = ar.rolling(fast_window, min_periods=fast_window).mean()
    slow_mean = ar.rolling(slow_window, min_periods=slow_window).mean()
    slow_std = ar.rolling(slow_window, min_periods=slow_window).std(ddof=1)
    shift = (fast - slow_mean) / slow_std.replace(0.0, np.nan)
    out = pd.DataFrame({"absorption_ratio": ar, "ar_shift": shift})
    return out.shift(1).reindex(index)


def realized_vol_scalar(
    net_returns: pd.Series,
    index: pd.Index,
    *,
    vol_window: int = 13,
    min_history: int = 104,
    clip_low: float = 0.85,
    clip_high: float = 1.15,
    update_every: int = 4,
) -> pd.Series:
    """Conservative Moreira-Muir style vol scalar for the portfolio's offense.

    target vol = expanding median of trailing realized vol (needs
    ``min_history`` weeks before activating; 1.0 before that). The scalar is
    refreshed every ``update_every`` weeks and held constant in between to
    limit turnover. Shifted one week.
    """

    ret = pd.to_numeric(net_returns, errors="coerce")
    realized = ret.rolling(vol_window, min_periods=vol_window).std(ddof=1) * np.sqrt(52.0)
    target = realized.expanding(min_periods=min_history).median()
    scalar = (target / realized).clip(clip_low, clip_high)
    scalar[target.isna() | realized.isna() | (realized <= 0)] = 1.0

    held = scalar.copy()
    last = 1.0
    values = []
    for i, v in enumerate(scalar.to_numpy()):
        if i % update_every == 0 and np.isfinite(v):
            last = float(v)
        values.append(last)
    held = pd.Series(values, index=scalar.index)
    return held.shift(1).reindex(index).fillna(1.0)
