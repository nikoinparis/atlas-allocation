"""Data loading and causal signal construction for options convexity research.

This module is strictly READ-ONLY with respect to the rest of the project. It
loads existing artifacts produced by the production pipeline and never writes to
them. All paths are resolved relative to the repository root so the module works
regardless of the current working directory.

What it provides
----------------
1. Weekly prices for the eligible underlyings (SPY, QQQ, IWM, TLT, GLD).
2. The baseline production ETF weight panel (date x ticker).
3. The market-state / regime history.
4. Per-underlying CAUSAL trend / momentum signals (lagged - no look-ahead).
5. A realized-volatility "implied vol" proxy (lagged) used for pricing and the
   IV-elevation activation filter.
6. An optional LIVE / snapshot option-chain loader via yfinance.

Causality note
--------------
Every signal returned for use at decision time week ``t`` is built only from
information available strictly BEFORE ``t`` (we shift by one week). This avoids
look-ahead bias, matching the project's research rules.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# Repository root: this file lives at <root>/src/options_convexity/option_data.py
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Eligible underlyings for v0. Kept small and liquid on purpose.
ELIGIBLE_UNDERLYINGS = ["SPY", "QQQ", "IWM", "TLT", "GLD"]

# Production artifact paths we READ (never write).
WEEKLY_PRICES_PATH = DATA / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE_PATH = DATA / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
# Baseline = the current production pin's ETF weight panel. We treat this as the
# "baseline ETF portfolio" the overlay sits on top of. We only read it.
BASELINE_PRODUCTION_PIN = "improved_frontier_phase5_fragility_guard"
BASELINE_WEIGHTS_PATH = (
    DATA
    / "05_layer3_portfolio_construction"
    / f"portfolio_version_weights_{BASELINE_PRODUCTION_PIN}.csv"
)
BASELINE_RETURNS_PATH = (
    DATA
    / "05_layer3_portfolio_construction"
    / f"portfolio_version_returns_{BASELINE_PRODUCTION_PIN}.csv"
)


def _read_dated(path: Path, date_col_candidates=("Date", "date")) -> pd.DataFrame:
    """Read a CSV and return it indexed by a normalized (tz-naive) date."""

    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")
    df = pd.read_csv(path)
    # The weight panel writes the date as an unnamed first column.
    if not any(c in df.columns for c in date_col_candidates) and df.columns[0].startswith("Unnamed"):
        df = df.rename(columns={df.columns[0]: "Date"})
    if df.columns[0] not in date_col_candidates and df.columns[0] == "":
        df = df.rename(columns={df.columns[0]: "Date"})
    date_col = next((c for c in date_col_candidates if c in df.columns), df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    try:
        df[date_col] = df[date_col].dt.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def load_weekly_prices(underlyings: list[str] | None = None) -> pd.DataFrame:
    """Return weekly close prices for the requested underlyings."""

    underlyings = underlyings or ELIGIBLE_UNDERLYINGS
    prices = _read_dated(WEEKLY_PRICES_PATH)
    missing = [t for t in underlyings if t not in prices.columns]
    if missing:
        raise KeyError(f"Underlyings missing from weekly prices: {missing}")
    return prices[underlyings].apply(pd.to_numeric, errors="coerce")


def load_baseline_weights() -> pd.DataFrame:
    """Return the baseline (production-pin) ETF weight panel, date x ticker."""

    weights = _read_dated(BASELINE_WEIGHTS_PATH)
    return weights.apply(pd.to_numeric, errors="coerce").fillna(0.0)


def load_baseline_returns() -> pd.DataFrame:
    """Return the baseline production weekly return path (net_return, etc.)."""

    return _read_dated(BASELINE_RETURNS_PATH)


def load_market_states() -> pd.DataFrame:
    """Return the market-state / regime history indexed by date."""

    return _read_dated(MARKET_STATE_PATH)


def build_trend_signals(prices: pd.DataFrame, lag_weeks: int = 1) -> dict[str, pd.DataFrame]:
    """Build CAUSAL per-underlying trend / momentum signals.

    For each underlying we compute, then LAG by ``lag_weeks`` so the value
    available at decision week ``t`` only uses prices up to week ``t - lag``:

    - ``mom_13w`` : trailing 13-week price return.
    - ``mom_26w`` : trailing 26-week price return.
    - ``above_sma_40w`` : 1.0 if price is above its 40-week moving average.

    Returns a dict keyed by signal name, each a DataFrame (date x underlying).
    The lag is what prevents look-ahead bias.
    """

    mom_13w = prices.pct_change(13)
    mom_26w = prices.pct_change(26)
    sma_40w = prices.rolling(40).mean()
    above_sma = (prices > sma_40w).astype(float)

    signals = {
        "mom_13w": mom_13w,
        "mom_26w": mom_26w,
        "above_sma_40w": above_sma,
    }
    # Lag every signal so it is strictly backward looking at decision time.
    return {name: df.shift(lag_weeks) for name, df in signals.items()}


def build_iv_proxy(prices: pd.DataFrame, window_weeks: int = 26, lag_weeks: int = 1) -> pd.DataFrame:
    """Build a CAUSAL realized-volatility proxy for implied volatility.

    Historical option-chain data is not available in this project, so for the
    PROXY backtest we approximate implied volatility with trailing realized
    volatility of weekly log returns, annualized by sqrt(52). The result is
    lagged so it is known before the decision week.

    IMPORTANT: this is an APPROXIMATION. Real implied vol usually trades at a
    premium to realized vol (the variance risk premium) and has its own term
    structure and skew. We deliberately do not model those here; instead the
    pricing layer applies a conservative IV markup and entry slippage so the
    proxy errs toward making options look EXPENSIVE, not cheap.
    """

    log_ret = np.log(prices / prices.shift(1))
    realized_vol = log_ret.rolling(window_weeks).std(ddof=1) * np.sqrt(52.0)
    return realized_vol.shift(lag_weeks)


def iv_percentile(iv_proxy: pd.DataFrame, lookback_weeks: int = 52) -> pd.DataFrame:
    """Return the rolling percentile rank (0-1) of the IV proxy vs its own past.

    Used by the activation filter "IV is not extremely elevated relative to its
    own recent history". A value near 1.0 means current vol is unusually high
    versus the trailing ``lookback_weeks``; near 0.0 means unusually low. The
    input is already lagged, so this stays causal.
    """

    def _rank(window: np.ndarray) -> float:
        current = window[-1]
        if np.isnan(current):
            return np.nan
        valid = window[~np.isnan(window)]
        if len(valid) < 2:
            return np.nan
        return float((valid <= current).mean())

    return iv_proxy.rolling(lookback_weeks, min_periods=12).apply(_rank, raw=True)


# ---------------------------------------------------------------------------
# LIVE / snapshot option-chain mode (optional). Used for research inspection
# of real current option chains. Not used by the historical proxy backtest.
# ---------------------------------------------------------------------------
def load_live_option_chain(ticker: str) -> pd.DataFrame:
    """Fetch current option chains for ``ticker`` via yfinance (LIVE mode).

    Returns a tidy DataFrame of CALL contracts with the columns used by the
    selection filters: ``expiration``, ``dte``, ``strike``, ``bid``, ``ask``,
    ``mid``, ``volume``, ``openInterest``, ``impliedVolatility``.

    This requires a network connection and yfinance. It is intentionally kept
    separate from the deterministic proxy backtest. If anything fails we raise a
    clear error so the caller can fall back to proxy mode.
    """

    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("yfinance is required for live option-chain mode") from exc

    from .option_pricing import mid_price

    tk = yf.Ticker(ticker)
    expirations = list(getattr(tk, "options", []) or [])
    if not expirations:
        raise RuntimeError(f"No option expirations returned for {ticker}")

    today = pd.Timestamp.utcnow().tz_localize(None).normalize()
    frames = []
    for exp in expirations:
        try:
            chain = tk.option_chain(exp)
        except Exception:
            continue
        calls = chain.calls.copy()
        if calls.empty:
            continue
        exp_ts = pd.Timestamp(exp)
        calls["expiration"] = exp_ts
        calls["dte"] = (exp_ts - today).days
        calls["mid"] = [
            mid_price(b, a) for b, a in zip(calls.get("bid", np.nan), calls.get("ask", np.nan))
        ]
        frames.append(calls)

    if not frames:
        raise RuntimeError(f"Could not assemble any call chain for {ticker}")

    out = pd.concat(frames, ignore_index=True)
    keep = [
        "expiration",
        "dte",
        "strike",
        "bid",
        "ask",
        "mid",
        "volume",
        "openInterest",
        "impliedVolatility",
    ]
    for col in keep:
        if col not in out.columns:
            out[col] = np.nan
    return out[keep]
