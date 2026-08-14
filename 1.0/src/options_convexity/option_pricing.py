"""Option pricing helpers for the options convexity research module.

This file is deliberately verbose and commented because options pricing is new
to the project owner. The goal is clarity over cleverness.

We use the standard Black-Scholes-Merton (BSM) model for European call options.
For ETF options that are American style this is an approximation, but for calls
on non-dividend (or low-dividend) underlyings the difference is small, and in
PROXY mode everything here is explicitly labelled approximate / not
production-grade.

Key vocabulary
--------------
- spot (S)   : current price of the underlying ETF.
- strike (K) : the price at which the option lets you buy the underlying.
- DTE        : days to expiration.
- T          : time to expiration expressed in YEARS (DTE / 365).
- sigma      : annualized implied volatility (here proxied by realized vol).
- r          : annualized risk-free rate (small constant in proxy mode).
- OTM        : "out of the money" - for a call, strike above the spot.

A "call spread" (a.k.a. bull call spread / vertical debit spread) means:
    BUY  one call at a lower strike  (K_long, closer to the money)
    SELL one call at a higher strike (K_short, further OTM, same expiry)
You pay a net debit (premium) up front. The most you can lose is that debit.
The most you can make is (K_short - K_long) minus the debit. This caps both
the cost and the payoff, which is why it is preferred over a naked long call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# We use scipy's normal CDF (already a project dependency). Falls back to a
# math.erf based implementation so the module never hard-fails on import.
try:
    from scipy.stats import norm

    def _norm_cdf(x: float) -> float:
        return float(norm.cdf(x))

except Exception:  # pragma: no cover - defensive fallback only

    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# Number of calendar days we use to convert DTE into year-fractions.
DAYS_PER_YEAR = 365.0


def black_scholes_call_price(
    spot: float,
    strike: float,
    dte_days: float,
    sigma: float,
    risk_free_rate: float = 0.02,
) -> float:
    """Return the Black-Scholes price of a single European CALL option.

    Parameters mirror the vocabulary above. ``dte_days`` is days to expiry.
    Returns a price in the same units as ``spot`` (e.g. dollars per share).

    The price is always >= 0. Degenerate inputs (zero time, zero vol) collapse
    to the option's intrinsic value, which keeps the function well behaved.
    """

    # Guard against invalid inputs so we never produce NaN / negative prices.
    if spot <= 0 or strike <= 0:
        return 0.0

    time_years = max(dte_days, 0.0) / DAYS_PER_YEAR

    # With no time left or no volatility the option is worth only its intrinsic
    # value: max(S - K, 0). This is the correct limiting case.
    if time_years <= 0.0 or sigma <= 0.0:
        return max(spot - strike, 0.0)

    vol_sqrt_t = sigma * math.sqrt(time_years)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * sigma * sigma) * time_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t

    price = spot * _norm_cdf(d1) - strike * math.exp(-risk_free_rate * time_years) * _norm_cdf(d2)

    # Floating point can produce a tiny negative number; clamp to zero.
    return max(price, 0.0)


@dataclass
class CallSpreadQuote:
    """A priced bull call spread.

    All prices are per-share (per single underlying unit). ``net_premium`` is
    the up-front debit you pay to open the spread BEFORE slippage / commission.
    """

    spot: float
    long_strike: float
    short_strike: float
    dte_days: float
    sigma: float
    long_price: float
    short_price: float

    @property
    def net_premium(self) -> float:
        """Net debit paid to open the spread (long leg minus short leg)."""

        return self.long_price - self.short_price

    @property
    def max_payoff(self) -> float:
        """Maximum value of the spread at expiry: the strike width."""

        return self.short_strike - self.long_strike


def price_call_spread(
    spot: float,
    long_strike: float,
    short_strike: float,
    dte_days: float,
    sigma: float,
    risk_free_rate: float = 0.02,
) -> CallSpreadQuote:
    """Price a bull call spread using Black-Scholes for both legs.

    ``long_strike`` must be below ``short_strike`` (you buy the cheaper, lower
    strike and sell the more-OTM higher strike). The returned quote exposes the
    net premium (a positive debit) and the maximum payoff (the strike width).
    """

    if long_strike >= short_strike:
        raise ValueError(
            f"long_strike ({long_strike}) must be below short_strike ({short_strike}) "
            "for a bull call spread"
        )

    long_price = black_scholes_call_price(spot, long_strike, dte_days, sigma, risk_free_rate)
    short_price = black_scholes_call_price(spot, short_strike, dte_days, sigma, risk_free_rate)

    return CallSpreadQuote(
        spot=spot,
        long_strike=long_strike,
        short_strike=short_strike,
        dte_days=dte_days,
        sigma=sigma,
        long_price=long_price,
        short_price=short_price,
    )


def call_spread_payoff_at_expiry(
    final_spot: float,
    long_strike: float,
    short_strike: float,
) -> float:
    """Return the per-share payoff of a bull call spread held to expiration.

    The payoff profile is:
        - 0                       if final_spot <= long_strike   (both expire worthless)
        - final_spot - long_strike if long_strike < final_spot < short_strike
        - short_strike - long_strike if final_spot >= short_strike (max payoff)

    This is simply the intrinsic value of the long call minus the intrinsic
    value of the short call at expiry, and is always >= 0.
    """

    long_intrinsic = max(final_spot - long_strike, 0.0)
    short_intrinsic = max(final_spot - short_strike, 0.0)
    return long_intrinsic - short_intrinsic


def mid_price(bid: float, ask: float) -> float:
    """Return the mid price = (bid + ask) / 2 when both are valid.

    Used for LIVE / snapshot option-chain mode. Falls back gracefully: if only
    one side is available we return it; if neither is valid we return NaN so
    the caller can reject the contract.
    """

    has_bid = bid is not None and bid > 0
    has_ask = ask is not None and ask > 0
    if has_bid and has_ask:
        return (bid + ask) / 2.0
    if has_ask:
        return float(ask)
    if has_bid:
        return float(bid)
    return float("nan")


def apply_entry_slippage(
    net_premium: float,
    slippage_pct: float = 0.05,
    commission_per_spread: float = 0.0,
) -> float:
    """Return the realistic cost to OPEN a spread, after slippage / commission.

    A buyer of a spread pays slightly more than the theoretical mid because of
    the bid/ask spread. We model that as a percentage markup on the net debit
    plus an optional fixed commission. ``slippage_pct`` of 0.05 means we assume
    we pay 5% more than the modelled premium - a conservative haircut for the
    convexity buyer. This makes the proxy backtest pessimistic, not optimistic.
    """

    if net_premium <= 0:
        return net_premium
    return net_premium * (1.0 + slippage_pct) + commission_per_spread
