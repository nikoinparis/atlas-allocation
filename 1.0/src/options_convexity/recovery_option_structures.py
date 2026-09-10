"""Option structures for the Options Convexity *Recovery* research experiment.

This experiment deliberately tests only TWO long-premium upside structures, the
ones that preserve the rare large right-tail winner (the whole reason to use
options for recovery convexity):

  1. **Outright long call** - simple long convexity. Max loss = premium paid.
  2. **1x2 call backspread** - sell 1 lower-strike call, buy 2 higher-strike
     calls, same expiry. Cheap (often a small credit) with unbounded right-tail
     upside, but it has a RISK ZONE between the strikes where it loses the most.

We intentionally do NOT use debit call spreads here: v1/v2 showed that the short
upper leg of a debit spread caps exactly the rare large winner we are trying to
capture.

Everything is signed-leg based: a structure is ``[(sign, strike), ...]`` where
``sign>0`` is long and ``sign<0`` is short. One set of pricing / mark-to-market /
payoff / max-loss functions then works for both structures.

PROXY ONLY: pricing is Black-Scholes on a realized-vol IV proxy. No real chains,
bid/ask, skew, term structure or fills. Clearly approximate.

This module is self-contained pricing logic and does not touch v1/v2 files or
production.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .option_pricing import black_scholes_call_price

# --------------------------------------------------------------------------
# Structure geometry knobs (kept visible; coarse, not tuned).
# --------------------------------------------------------------------------
# Outright call: slightly OTM (brief: ATM..25-delta, ~0-5% OTM proxy).
OUTRIGHT_CALL_OTM = 0.02

# 1x2 backspread: short strike near the money, long strikes further OTM.
BACKSPREAD_SHORT_OTM = 0.02   # K1 (the single short call), ~2% OTM.
BACKSPREAD_LONG_OTM = 0.10    # K2 (the two long calls), ~10% OTM.

RISK_FREE_RATE = 0.02

# A backspread is rejected if its modelled max loss per unit of strike width is
# too large relative to the premium budget (i.e. the risk zone is too punishing).
MAX_RISK_ZONE_RATIO = 0.60    # max_loss must be <= 60% of the strike width.


@dataclass
class RecoveryStructure:
    """A concrete, signed-leg option structure for one (spot, sigma, dte)."""

    name: str
    legs: list[tuple[int, float]]   # [(sign, strike), ...]
    spot: float
    sigma: float
    dte_days: float
    # Filled in by ``price_structure``:
    entry_liquidation: float = field(default=np.nan)  # net value to open (debit>0)
    gross_premium: float = field(default=np.nan)      # total notional transacted
    max_loss_per_share: float = field(default=np.nan)
    breakeven_move: float = field(default=np.nan)

    @property
    def lowest_long_strike(self) -> float:
        longs = [k for s, k in self.legs if s > 0]
        return min(longs) if longs else np.nan

    @property
    def long_moneyness(self) -> float:
        """OTM fraction of the lowest long strike (e.g. 0.02 == 2% OTM)."""

        return self.lowest_long_strike / self.spot - 1.0


def build_outright_call(spot: float, sigma: float, dte_days: float, otm: float = OUTRIGHT_CALL_OTM) -> RecoveryStructure:
    """Build a single long call ~``otm`` out of the money."""

    strike = spot * (1.0 + otm)
    return RecoveryStructure(name="outright_call", legs=[(+1, strike)], spot=spot, sigma=sigma, dte_days=dte_days)


def build_1x2_backspread(
    spot: float,
    sigma: float,
    dte_days: float,
    short_otm: float = BACKSPREAD_SHORT_OTM,
    long_otm: float = BACKSPREAD_LONG_OTM,
) -> RecoveryStructure:
    """Build a 1x2 call backspread: short 1 call at K1, long 2 calls at K2."""

    k1 = spot * (1.0 + short_otm)   # the single short call (lower strike).
    k2 = spot * (1.0 + long_otm)    # the two long calls (higher strike).
    return RecoveryStructure(name="backspread_1x2", legs=[(-1, k1), (+2, k2)], spot=spot, sigma=sigma, dte_days=dte_days)


def net_liquidation_value(structure: RecoveryStructure, spot: float, remaining_dte: float) -> float:
    """Mark-to-market liquidation value (per share) of the structure's legs.

    This is what you would receive (positive) or pay (negative) to flatten the
    position right now. At/after expiry it is the intrinsic payoff. Used both for
    the entry cost basis and for ongoing MTM.
    """

    if remaining_dte <= 0:
        return payoff_at_expiry(structure, spot)
    value = 0.0
    for sign, strike in structure.legs:
        value += sign * black_scholes_call_price(spot, strike, remaining_dte, structure.sigma, RISK_FREE_RATE)
    return value


def gross_premium(structure: RecoveryStructure, spot: float, dte_days: float) -> float:
    """Total absolute option notional transacted (for slippage on every leg)."""

    total = 0.0
    for sign, strike in structure.legs:
        total += abs(sign) * black_scholes_call_price(spot, strike, dte_days, structure.sigma, RISK_FREE_RATE)
    return total


def payoff_at_expiry(structure: RecoveryStructure, final_spot: float) -> float:
    """Intrinsic settlement value (per share) at expiration."""

    payoff = 0.0
    for sign, strike in structure.legs:
        payoff += sign * max(final_spot - strike, 0.0)
    return payoff


def compute_max_loss(structure: RecoveryStructure, entry_cost_basis: float) -> float:
    """Worst-case loss per share at expiry, given the (slippage-loaded) basis.

    We scan the expiry payoff over a grid of underlying prices (including the
    strikes, where the kinks are) and take the largest shortfall of payoff below
    the entry cost basis. For a long call this is just the premium; for a 1x2
    backspread it correctly finds the risk zone around the upper strike. Upside
    is unbounded, so the worst case is always at a finite grid point.
    """

    strikes = [k for _, k in structure.legs]
    grid = sorted(set([0.0] + strikes + [structure.spot * m for m in (0.5, 0.8, 1.0, 1.2, 1.5, 2.0)]))
    worst = 0.0
    for s in grid:
        loss = entry_cost_basis - payoff_at_expiry(structure, s)
        worst = max(worst, loss)
    # Never report a non-positive max loss (avoids divide-by-zero in sizing).
    return max(worst, 1e-9)


def compute_breakeven_move(structure: RecoveryStructure, entry_cost_basis: float) -> float:
    """Smallest UPWARD move at which the structure breaks even at expiry.

    Scans upward from the spot until expiry payoff >= the entry cost basis. This
    is the "required breakeven move" the recovery signal compares against the
    expected forward move. Conservative: it uses the expiry payoff even though we
    exit early, so the bar is if anything a little high.
    """

    spot = structure.spot
    # Fine upward scan to ~+60% which comfortably brackets our structures.
    for frac in np.arange(0.0, 0.60, 0.0025):
        s = spot * (1.0 + frac)
        if payoff_at_expiry(structure, s) >= entry_cost_basis:
            return float(frac)
    return float("inf")  # never breaks even within the scanned range.


def price_structure(
    structure: RecoveryStructure,
    entry_slippage_frac: float,
) -> RecoveryStructure:
    """Populate entry economics (basis, gross, max loss, breakeven) in place.

    ``entry_cost_basis`` = net liquidation to open PLUS entry slippage charged on
    the gross notional. For a credit structure the net liquidation is negative
    (you receive), and slippage reduces that credit - always conservative.
    """

    net = net_liquidation_value(structure, structure.spot, structure.dte_days)
    gross = gross_premium(structure, structure.spot, structure.dte_days)
    entry_cost_basis = net + entry_slippage_frac * gross

    structure.entry_liquidation = net
    structure.gross_premium = gross
    structure.max_loss_per_share = compute_max_loss(structure, entry_cost_basis)
    structure.breakeven_move = compute_breakeven_move(structure, entry_cost_basis)
    return structure


def backspread_risk_zone_acceptable(structure: RecoveryStructure) -> bool:
    """Reject a backspread whose risk-zone loss is too large vs its strike width.

    The 1x2 backspread's danger is finishing right at the upper strike. We
    require the modelled max loss to be a modest fraction of the strike width so
    the structure is genuinely cheap convexity rather than a disguised short-vol
    bet. Always True for the outright call (no internal risk zone).
    """

    if structure.name != "backspread_1x2":
        return True
    strikes = sorted(k for _, k in structure.legs)
    width = strikes[-1] - strikes[0]
    if width <= 0:
        return False
    return structure.max_loss_per_share <= MAX_RISK_ZONE_RATIO * width
