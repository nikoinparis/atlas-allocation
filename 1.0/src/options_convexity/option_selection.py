"""Contract selection and call-spread construction.

These helpers implement the mechanical "which contract do I trade" logic:

1. Filter expirations by days-to-expiration (DTE).
2. Filter contracts by moneyness (how far OTM).
3. Filter contracts by liquidity (bid/ask spread, volume, open interest).
4. Construct a bull call spread from a real option chain (LIVE mode), or from
   synthetic Black-Scholes strikes (PROXY mode).

The filters operate on a tidy option-chain DataFrame (see
``option_data.load_live_option_chain``) so they can be unit-tested with small
hand-made frames. PROXY-mode construction does not need a chain - it derives
clean target strikes directly from the spot price.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .option_pricing import CallSpreadQuote, price_call_spread


# ----------------------------- v0 default knobs ----------------------------
# These are deliberately simple, round numbers chosen up front (not tuned to
# maximize backtest performance) to avoid overfitting the activation/selection.
DEFAULT_MIN_DTE = 60
DEFAULT_MAX_DTE = 120
DEFAULT_TARGET_DTE = 90  # ~13 weeks; sits inside the 60-120 band.

# Long leg 3-7% OTM; short leg 10-20% OTM. We pick the middle of each band.
DEFAULT_LONG_OTM = 0.05
DEFAULT_SHORT_OTM = 0.15

# Liquidity gates for LIVE mode.
DEFAULT_MAX_REL_SPREAD = 0.15  # reject if (ask-bid)/mid > 15%.
DEFAULT_MIN_OPEN_INTEREST = 100
DEFAULT_MIN_VOLUME = 10


def filter_by_dte(
    chain: pd.DataFrame,
    min_dte: int = DEFAULT_MIN_DTE,
    max_dte: int = DEFAULT_MAX_DTE,
) -> pd.DataFrame:
    """Keep only contracts whose DTE is within [min_dte, max_dte]."""

    return chain[(chain["dte"] >= min_dte) & (chain["dte"] <= max_dte)].copy()


def filter_by_moneyness(
    chain: pd.DataFrame,
    spot: float,
    min_otm: float,
    max_otm: float,
) -> pd.DataFrame:
    """Keep call contracts whose strike is between min_otm and max_otm OTM.

    ``min_otm``/``max_otm`` are fractions, e.g. 0.03 and 0.07 means strikes
    between 3% and 7% above the spot price.
    """

    lo = spot * (1.0 + min_otm)
    hi = spot * (1.0 + max_otm)
    return chain[(chain["strike"] >= lo) & (chain["strike"] <= hi)].copy()


def filter_by_liquidity(
    chain: pd.DataFrame,
    max_rel_spread: float = DEFAULT_MAX_REL_SPREAD,
    min_open_interest: int = DEFAULT_MIN_OPEN_INTEREST,
    min_volume: int = DEFAULT_MIN_VOLUME,
) -> pd.DataFrame:
    """Drop illiquid contracts: wide bid/ask, low open interest, or low volume.

    Wide spreads make the mid price unreliable and execution expensive. Low
    open interest / volume means the quote may be stale. We require a tradable,
    reasonably tight market on each leg.
    """

    out = chain.copy()
    mid = out["mid"].replace(0, np.nan)
    rel_spread = (out["ask"] - out["bid"]) / mid
    keep = (
        rel_spread.notna()
        & (rel_spread <= max_rel_spread)
        & (out["openInterest"].fillna(0) >= min_open_interest)
        & (out["volume"].fillna(0) >= min_volume)
    )
    return out[keep].copy()


def _closest_row(chain: pd.DataFrame, target_strike: float) -> pd.Series | None:
    """Return the chain row whose strike is closest to ``target_strike``."""

    if chain.empty:
        return None
    idx = (chain["strike"] - target_strike).abs().idxmin()
    return chain.loc[idx]


@dataclass
class SelectedSpread:
    """The concrete spread we decided to trade, with per-share economics."""

    underlying: str
    spot: float
    long_strike: float
    short_strike: float
    dte_days: float
    sigma: float
    net_premium: float  # per-share debit BEFORE slippage
    max_payoff: float  # per-share strike width
    source: str  # "proxy_bsm" or "live_chain"


def build_proxy_call_spread(
    underlying: str,
    spot: float,
    sigma: float,
    dte_days: float = DEFAULT_TARGET_DTE,
    long_otm: float = DEFAULT_LONG_OTM,
    short_otm: float = DEFAULT_SHORT_OTM,
    risk_free_rate: float = 0.02,
) -> SelectedSpread:
    """Construct a bull call spread for PROXY mode using Black-Scholes.

    Strikes are placed at clean OTM offsets from the spot (long_otm, short_otm),
    and both legs are priced with the same IV proxy ``sigma`` and the same DTE.
    This is the spread the historical proxy backtest trades.
    """

    long_strike = spot * (1.0 + long_otm)
    short_strike = spot * (1.0 + short_otm)
    quote: CallSpreadQuote = price_call_spread(
        spot=spot,
        long_strike=long_strike,
        short_strike=short_strike,
        dte_days=dte_days,
        sigma=sigma,
        risk_free_rate=risk_free_rate,
    )
    return SelectedSpread(
        underlying=underlying,
        spot=spot,
        long_strike=long_strike,
        short_strike=short_strike,
        dte_days=dte_days,
        sigma=sigma,
        net_premium=quote.net_premium,
        max_payoff=quote.max_payoff,
        source="proxy_bsm",
    )


def build_live_call_spread(
    underlying: str,
    spot: float,
    chain: pd.DataFrame,
    min_dte: int = DEFAULT_MIN_DTE,
    max_dte: int = DEFAULT_MAX_DTE,
    long_otm_band: tuple[float, float] = (0.03, 0.07),
    short_otm_band: tuple[float, float] = (0.10, 0.20),
    **liquidity_kwargs,
) -> SelectedSpread | None:
    """Construct a bull call spread from a LIVE option chain, or None.

    Applies DTE, moneyness, and liquidity filters, then picks the most liquid
    expiration and the strikes closest to the middle of each OTM band. Returns
    ``None`` if no acceptable spread survives the filters.
    """

    dte_ok = filter_by_dte(chain, min_dte, max_dte)
    if dte_ok.empty:
        return None

    # Choose the single expiration that has the most contracts surviving the
    # liquidity filter (a simple proxy for the most liquid expiry).
    best_exp, best_liquid = None, None
    for exp, grp in dte_ok.groupby("expiration"):
        liquid = filter_by_liquidity(grp, **liquidity_kwargs)
        if best_liquid is None or len(liquid) > len(best_liquid):
            best_exp, best_liquid = exp, liquid
    if best_liquid is None or best_liquid.empty:
        return None

    long_candidates = filter_by_moneyness(best_liquid, spot, *long_otm_band)
    short_candidates = filter_by_moneyness(best_liquid, spot, *short_otm_band)

    long_row = _closest_row(long_candidates, spot * (1.0 + np.mean(long_otm_band)))
    short_row = _closest_row(short_candidates, spot * (1.0 + np.mean(short_otm_band)))
    if long_row is None or short_row is None:
        return None
    if long_row["strike"] >= short_row["strike"]:
        return None

    net_premium = float(long_row["mid"] - short_row["mid"])
    if not np.isfinite(net_premium) or net_premium <= 0:
        return None

    return SelectedSpread(
        underlying=underlying,
        spot=spot,
        long_strike=float(long_row["strike"]),
        short_strike=float(short_row["strike"]),
        dte_days=float(long_row["dte"]),
        sigma=float(long_row.get("impliedVolatility", np.nan)),
        net_premium=net_premium,
        max_payoff=float(short_row["strike"] - long_row["strike"]),
        source="live_chain",
    )
