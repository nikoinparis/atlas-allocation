"""Activation rules and sizing for the options convexity overlay (v0).

The whole point of this research is that the overlay should be RARE. It only
activates when the existing system is already clearly bullish AND the specific
ETF has a strong, confirmed uptrend. The rules below are the v0 gates from the
research brief. They are intentionally simple and use round-number thresholds
chosen up front so we do not overfit the activation logic to the backtest.

Every input used here is causal (already lagged in ``option_data``), so the
decision at week ``t`` never peeks at week ``t`` outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ----------------------------- v0 activation knobs -------------------------
# Market states considered clearly bullish / non-defensive. Everything else
# (neutral_mixed, recovery_fragile, stressed_panic) blocks activation.
RISK_ON_STATES = {"calm_trend", "recovery_confirmed"}

# A state we treat as panic / stress / drawdown-defense; always blocks.
DEFENSIVE_STATES = {"stressed_panic", "recovery_fragile"}

# Strong-trend thresholds for the specific ETF (must clear BOTH horizons).
MIN_MOM_13W = 0.03  # +3% trailing 13-week momentum.
MIN_MOM_26W = 0.05  # +5% trailing 26-week momentum.

# Block if the broad market is already in a meaningful drawdown.
MAX_MARKET_DRAWDOWN = -0.10  # i.e. allow only if drawdown shallower than -10%.

# ETF must already carry at least this baseline weight to be overlay-eligible.
MIN_BASELINE_WEIGHT = 0.02

# IV-elevation gate: skip if the IV proxy is in the top of its own recent range.
MAX_IV_PERCENTILE = 0.80  # block if current vol percentile > 80% of trailing year.

# Sizing: premium budget as a fraction of total portfolio value.
DEFAULT_PREMIUM_BUDGET = 0.02  # 2% default.
MIN_PREMIUM_BUDGET = 0.01  # 1% floor when active.
HARD_CAP_TOTAL_PREMIUM = 0.03  # absolute hard cap across ALL active options.


@dataclass
class ActivationDecision:
    """Result of evaluating the activation rules for one ETF on one date."""

    underlying: str
    active: bool
    reasons_failed: list[str] = field(default_factory=list)
    # Diagnostic values captured for the trade log / debugging.
    market_state: str = ""
    mom_13w: float = float("nan")
    mom_26w: float = float("nan")
    baseline_weight: float = float("nan")
    iv_pct: float = float("nan")


def evaluate_activation(
    underlying: str,
    *,
    market_state: str,
    market_drawdown: float,
    mom_13w: float,
    mom_26w: float,
    above_sma: float,
    baseline_weight: float,
    iv_pct: float,
    liquidity_ok: bool,
    iv_history_available: bool = True,
) -> ActivationDecision:
    """Evaluate ALL v0 activation rules. Activates only if every rule passes.

    The seven v0 rules (from the research brief):
      1. Regime/risk engine is risk-on / non-defensive.
      2. ETF has a strong positive trend/momentum signal.
      3. ETF already has positive baseline target weight.
      4. Portfolio is NOT in panic / stress / drawdown-defense mode.
      5. Options liquidity filter passes.
      6. IV is not extremely elevated vs its own recent history (if available).
      7. Options allocation stays small - enforced at sizing time, see below.

    Rule 7 (small allocation) is a sizing constraint rather than a yes/no gate,
    so it is enforced in ``size_premium_budget`` and the backtest's hard cap;
    here we only decide eligibility.
    """

    failed: list[str] = []

    # Rule 1: risk-on / non-defensive regime.
    if market_state not in RISK_ON_STATES:
        failed.append("regime_not_risk_on")

    # Rule 4: explicit panic / stress / drawdown-defense block.
    if market_state in DEFENSIVE_STATES:
        failed.append("defensive_state")
    if not (market_drawdown is None) and market_drawdown < MAX_MARKET_DRAWDOWN:
        failed.append("market_in_drawdown")

    # Rule 2: strong positive ETF trend on BOTH horizons, plus above its MA.
    if not (mom_13w is not None and mom_13w >= MIN_MOM_13W):
        failed.append("weak_mom_13w")
    if not (mom_26w is not None and mom_26w >= MIN_MOM_26W):
        failed.append("weak_mom_26w")
    if not (above_sma is not None and above_sma >= 1.0):
        failed.append("below_sma")

    # Rule 3: ETF already receives meaningful baseline weight.
    if not (baseline_weight is not None and baseline_weight >= MIN_BASELINE_WEIGHT):
        failed.append("insufficient_baseline_weight")

    # Rule 5: liquidity filter (in proxy mode the 5 ETFs are highly liquid and
    # this passes by construction; in live mode it reflects the chain filter).
    if not liquidity_ok:
        failed.append("liquidity_failed")

    # Rule 6: IV not extremely elevated vs its own recent history. Only applied
    # when IV history is available; otherwise we skip this gate (documented).
    if iv_history_available:
        if iv_pct is not None and iv_pct == iv_pct and iv_pct > MAX_IV_PERCENTILE:
            failed.append("iv_too_elevated")

    return ActivationDecision(
        underlying=underlying,
        active=len(failed) == 0,
        reasons_failed=failed,
        market_state=market_state,
        mom_13w=mom_13w,
        mom_26w=mom_26w,
        baseline_weight=baseline_weight,
        iv_pct=iv_pct,
    )


def size_premium_budget(
    baseline_weight: float,
    already_allocated: float,
    requested_budget: float = DEFAULT_PREMIUM_BUDGET,
    hard_cap: float = HARD_CAP_TOTAL_PREMIUM,
) -> float:
    """Return the premium budget (fraction of portfolio) for one new option.

    Enforces three constraints so the overlay always stays small:
      * The budget never exceeds the matching ETF's baseline weight (the sleeve
        is funded by REDUCING that ETF, never by adding leverage).
      * The TOTAL premium across all active options never exceeds ``hard_cap``
        (3%). ``already_allocated`` is the premium already committed this week.
      * If the remaining room is below the 1% floor, we allocate nothing.

    Returns 0.0 when there is no room left.
    """

    remaining_room = hard_cap - already_allocated
    if remaining_room <= 0:
        return 0.0

    # Cannot spend more premium than the ETF weight we are reducing.
    budget = min(requested_budget, baseline_weight, remaining_room)

    # Keep activations meaningful: skip dust allocations below the floor.
    if budget < MIN_PREMIUM_BUDGET:
        return 0.0
    return float(budget)
