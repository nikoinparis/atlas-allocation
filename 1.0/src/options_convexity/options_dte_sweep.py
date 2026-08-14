"""DTE buckets and option-structure construction for the v2 experiment.

This module defines:
  * the DTE buckets the v2 sweep tests,
  * the option structures the v2 sweep tests,
  * a generic "legs" representation so the backtest can price / mark / settle
    any of them with one code path,
  * a Black-Scholes call-delta helper and a delta-targeted strike solver.

A structure is represented as a list of LEGS. Each leg is ``(sign, strike)``:
  * ``sign = +1`` is a long call (we own it),
  * ``sign = -1`` is a short call (we sold it).
The net premium of a debit structure is ``sum(sign * call_price(strike))`` and
is positive (we pay to open). Keeping everything as signed legs means call
spreads, ATM spreads, delta-targeted spreads and naked calls all share the same
pricing / mark-to-market / payoff functions.

All pricing reuses the v1 ``option_pricing`` Black-Scholes implementation; this
module never modifies v1 files.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .option_pricing import black_scholes_call_price

try:
    from scipy.stats import norm

    def _norm_cdf(x: float) -> float:
        return float(norm.cdf(x))

except Exception:  # pragma: no cover - defensive fallback

    def _norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


DAYS_PER_YEAR = 365.0

# DTE buckets requested for the sweep. Each maps to a representative DTE (the
# midpoint) that the backtest actually trades, plus the inclusive day range used
# for labelling / validation.
DTE_BUCKETS = {
    "21-45": {"min": 21, "max": 45, "representative": 33},
    "45-75": {"min": 45, "max": 75, "representative": 60},
    "75-100": {"min": 75, "max": 100, "representative": 87},
    "100-150": {"min": 100, "max": 150, "representative": 125},
}

# Option structures the sweep tests. Call spreads are the DEFAULT preferred
# structure (lower premium and theta bleed than naked calls). The naked call is
# included ONLY as a comparison, never as the preferred structure.
STRUCTURES = {
    "spread_3_7_10_20": {
        "kind": "spread",
        "long_otm": 0.05,   # mid of the 3-7% band
        "short_otm": 0.15,  # mid of the 10-20% band
        "preferred": True,
        "desc": "Call spread: long 5% OTM, short 15% OTM (v1-style).",
    },
    "spread_atm_10": {
        "kind": "spread",
        "long_otm": 0.00,   # at-the-money long
        "short_otm": 0.10,  # 10% OTM short
        "preferred": True,
        "desc": "Call spread: long ATM, short 10% OTM (more delta, costlier).",
    },
    "spread_delta_40_20": {
        "kind": "delta_spread",
        "long_delta": 0.40,
        "short_delta": 0.20,
        "preferred": True,
        "desc": "Delta-targeted call spread: long ~0.40 delta, short ~0.20 delta.",
    },
    "naked_call_5otm": {
        "kind": "naked",
        "long_otm": 0.05,
        "preferred": False,  # comparison only.
        "desc": "Naked long call 5% OTM (comparison only - NOT preferred).",
    },
}

# The pre-registered MAIN v2 configuration (chosen BEFORE seeing sweep results
# to avoid overfitting): mid DTE, default call spread, full filter stack, small
# size. The sweeps explore around it; promotion decisions use THIS config.
MAIN_CONFIG = {
    "dte_bucket": "45-75",
    "structure": "spread_3_7_10_20",
    "ablation_level": 5,
    "premium_budget": 0.01,
}


@dataclass
class StructureSpec:
    """A concrete, priced structure for one (spot, sigma, dte)."""

    name: str
    kind: str
    legs: list[tuple[int, float]]  # [(sign, strike), ...]
    long_strike: float             # lowest long strike (for breakeven/moneyness)
    spot: float
    dte_days: float
    sigma: float


def black_scholes_call_delta(
    spot: float,
    strike: float,
    dte_days: float,
    sigma: float,
    risk_free_rate: float = 0.02,
) -> float:
    """Return the Black-Scholes delta of a European call, in [0, 1].

    Delta is the sensitivity of the option price to the underlying and, loosely,
    the model's probability the call finishes in the money. We use it to place
    delta-targeted strikes. Degenerate inputs collapse to the intrinsic-style
    0/1 boundary so the solver stays well-behaved.
    """

    if spot <= 0 or strike <= 0:
        return 0.0
    time_years = max(dte_days, 0.0) / DAYS_PER_YEAR
    if time_years <= 0.0 or sigma <= 0.0:
        return 1.0 if spot > strike else 0.0
    vol_sqrt_t = sigma * math.sqrt(time_years)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * sigma * sigma) * time_years) / vol_sqrt_t
    return float(_norm_cdf(d1))


def strike_for_delta(
    spot: float,
    target_delta: float,
    dte_days: float,
    sigma: float,
    risk_free_rate: float = 0.02,
) -> float:
    """Solve for the call strike whose delta equals ``target_delta``.

    Delta decreases monotonically as the strike rises, so we can bisect on
    strike. Returns a strike in a sensible bracket around the spot. Deterministic
    (fixed iteration count, no randomness).
    """

    lo, hi = spot * 0.5, spot * 3.0  # wide bracket: low strike -> delta ~1.
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        d = black_scholes_call_delta(spot, mid, dte_days, sigma, risk_free_rate)
        if d > target_delta:
            lo = mid  # delta too high -> need a higher strike.
        else:
            hi = mid
    return 0.5 * (lo + hi)


def build_structure(
    structure_name: str,
    spot: float,
    sigma: float,
    dte_days: float,
    risk_free_rate: float = 0.02,
) -> StructureSpec:
    """Build the signed legs for the named structure at the given spot/sigma/DTE."""

    spec = STRUCTURES[structure_name]
    kind = spec["kind"]

    if kind == "spread":
        long_strike = spot * (1.0 + spec["long_otm"])
        short_strike = spot * (1.0 + spec["short_otm"])
        legs = [(+1, long_strike), (-1, short_strike)]

    elif kind == "delta_spread":
        long_strike = strike_for_delta(spot, spec["long_delta"], dte_days, sigma, risk_free_rate)
        short_strike = strike_for_delta(spot, spec["short_delta"], dte_days, sigma, risk_free_rate)
        # Guard: long strike must be below short strike for a debit spread.
        if long_strike >= short_strike:
            short_strike = long_strike * 1.05
        legs = [(+1, long_strike), (-1, short_strike)]

    elif kind == "naked":
        long_strike = spot * (1.0 + spec["long_otm"])
        legs = [(+1, long_strike)]

    else:  # pragma: no cover - guarded by STRUCTURES keys
        raise ValueError(f"Unknown structure kind: {kind}")

    return StructureSpec(
        name=structure_name,
        kind=kind,
        legs=legs,
        long_strike=min(strike for sign, strike in legs if sign > 0),
        spot=spot,
        dte_days=dte_days,
        sigma=sigma,
    )


def price_structure(
    structure: StructureSpec,
    spot: float | None = None,
    remaining_dte: float | None = None,
    risk_free_rate: float = 0.02,
) -> float:
    """Mark-to-market value (per share) of the structure's legs.

    With no override, prices at the structure's own spot/DTE/sigma (the entry
    quote). Pass ``spot`` / ``remaining_dte`` to mark an open position later in
    its life. At or past expiry (remaining_dte <= 0) the value is intrinsic.
    """

    s = structure.spot if spot is None else spot
    t = structure.dte_days if remaining_dte is None else remaining_dte
    sigma = structure.sigma

    if t <= 0:
        return structure_payoff_at_expiry(structure, s)

    value = 0.0
    for sign, strike in structure.legs:
        value += sign * black_scholes_call_price(s, strike, t, sigma, risk_free_rate)
    # Debit structures are worth >= 0; clamp tiny negative FP noise.
    return max(value, 0.0)


def structure_payoff_at_expiry(structure: StructureSpec, final_spot: float) -> float:
    """Intrinsic settlement value (per share) of the structure at expiration."""

    payoff = 0.0
    for sign, strike in structure.legs:
        payoff += sign * max(final_spot - strike, 0.0)
    return max(payoff, 0.0)


def breakeven_move(structure: StructureSpec, entry_cost_per_share: float) -> float:
    """Underlying move needed at expiry to recoup the premium paid.

    For any of our debit call structures the lowest long strike sets the point
    where payoff starts accruing, so breakeven spot = long_strike + entry_cost,
    i.e. required move = (long_strike + entry_cost)/spot - 1. This is exactly the
    "required breakeven return" the v2 entry filter compares against the expected
    forward move.
    """

    breakeven_spot = structure.long_strike + entry_cost_per_share
    return breakeven_spot / structure.spot - 1.0


def average_moneyness(structure: StructureSpec) -> float:
    """Return the long leg's OTM fraction (e.g. 0.05 == 5% OTM)."""

    return structure.long_strike / structure.spot - 1.0
