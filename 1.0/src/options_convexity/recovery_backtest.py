"""Recovery options proxy backtest engine (with corrected P&L banking).

Key difference vs v1/v2
-----------------------
The v1/v2 engines only reflected OPEN-position mark-to-market and dropped a
position's realized P&L the week after it closed - which is why their overlay
CAGR came out exactly equal to the baseline (option returns never compounded
into the curve). This engine BANKS realized P&L permanently:

    overlay_equity(t) = baseline_equity(t)
                        + realized_incremental_cumulative(t)
                        + open_position_incremental_MTM(t)

so a closed option trade's gain or loss stays in the equity path. This is the
honest model. Because long premium has a negative expected-return base rate
(volatility risk premium), under a conservative proxy this makes the overlay
MORE likely to be rejected, not less - which is the point.

Accounting per position
------------------------
At entry we carve ``premium_at_risk = per_trade_risk * NAV`` dollars out of the
matching ETF (no leverage) and put that capital at risk in the option. Units are
sized so the option's worst-case loss equals exactly the carved amount. Each
week the position's incremental value vs simply holding that ETF slice is:

    increment(t) = units*(liq(t) - entry_cost_basis) - carved*((S_t/S_entry) - 1)

Entry slippage is in the cost basis; exit slippage is charged at close. Held to a
21-30 DTE time stop (never to expiry), with optional profit target and a
recovery-thesis-invalidation stop.

Tactical ETF tilt benchmark
---------------------------
For every option trade, a PAIRED tilt position is run over the same window: it
overweights the matching ETF by ``per_trade_risk`` of NAV (capital-matched,
funded from cash). This answers "do options add anything beyond just leaning
long the ETF on the same signals?".

PROXY ONLY - approximate, not production-grade. Does not touch production/v1/v2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data, recovery_option_structures as ros, recovery_signal_engine as rse

# ----------------------------- config (visible) ----------------------------
IV_MARKUP = 1.05
ENTRY_SLIPPAGE_FRAC = 0.05
EXIT_SLIPPAGE_FRAC = 0.05
RISK_FREE_RATE = 0.02

PER_TRADE_RISK = 0.005        # 0.50% NAV premium-at-risk per trade.
MAX_CONCURRENT_RISK = 0.01    # 1.0% NAV total at any time.
MAX_ANNUAL_RISK = 0.02        # 2.0% NAV/yr (reported; gate elsewhere).

EXIT_DTE = 25                 # time stop: close near 21-30 DTE.
PROFIT_TARGET = 1.0           # +100% of capital-at-risk -> take profit.
STOP_LOSS_MOVE = -0.08        # underlying -8% from entry -> thesis invalidated.

OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")

DTE_BUCKETS = {
    "60-90": {"min": 60, "max": 90, "representative": 75},
    "90-120": {"min": 90, "max": 120, "representative": 105},
    "60-120": {"min": 60, "max": 120, "representative": 90},
}

STRUCTURE_BUILDERS = {
    "outright_call": ros.build_outright_call,
    "backspread_1x2": ros.build_1x2_backspread,
}


@dataclass
class RecoveryConfig:
    structure: str = "outright_call"
    dte_bucket: str = "60-120"
    profit_taking: bool = True
    gate_flags: dict = field(default_factory=lambda: dict(rse.DEFAULT_GATE_FLAGS))
    per_trade_risk: float = PER_TRADE_RISK
    underlyings: list[str] = field(default_factory=lambda: list(rse.RECOVERY_UNDERLYINGS))

    @property
    def representative_dte(self) -> int:
        return DTE_BUCKETS[self.dte_bucket]["representative"]

    @property
    def holding_weeks(self) -> float:
        return max((self.representative_dte - EXIT_DTE) / 7.0, 1.0)

    def label(self) -> str:
        pt = "PT" if self.profit_taking else "noPT"
        return f"{self.structure}|dte={self.dte_bucket}|{pt}"


@dataclass
class _OpenPos:
    underlying: str
    open_date: pd.Timestamp
    open_index: int
    open_spot: float
    structure: ros.RecoveryStructure
    entry_cost_basis: float
    units: float
    budget_dollars: float
    premium_fraction: float
    original_dte: float
    features: dict
    surplus: float


@dataclass
class RecoveryResult:
    equity: pd.DataFrame            # baseline / options / tilt equities + returns
    trades: pd.DataFrame
    candidate_log: pd.DataFrame
    config: RecoveryConfig
    activations_per_year: float
    premium_at_risk_per_year: float
    cash_premium_per_year: float
    max_concurrent_risk: float
    avg_dte: float
    avg_moneyness: float


_BASELINE_WEIGHTS: pd.DataFrame | None = None


def _baseline_weight(date, ticker) -> float:
    global _BASELINE_WEIGHTS
    if _BASELINE_WEIGHTS is None:
        _BASELINE_WEIGHTS = option_data.load_baseline_weights()
    return rse._safe(_BASELINE_WEIGHTS, date, ticker, default=0.0)


def run_recovery_backtest(config: RecoveryConfig, signals: rse.RecoverySignalPanel | None = None) -> RecoveryResult:
    """Run the recovery proxy backtest for one configuration."""

    underlyings = config.underlyings
    prices = option_data.load_weekly_prices(underlyings)
    etf_ret = prices.pct_change()
    baseline_returns = option_data.load_baseline_returns()
    states = option_data.load_market_states()
    signals = signals or rse.build_recovery_signals(underlyings)

    calendar = baseline_returns.index
    net_return = pd.to_numeric(baseline_returns["net_return"], errors="coerce").fillna(0.0).reindex(calendar).fillna(0.0)
    baseline_equity = (1.0 + net_return).cumprod()
    cur_state = states["market_state"].astype(str).reindex(calendar)

    n = len(calendar)
    builder = STRUCTURE_BUILDERS[config.structure]
    dte_days = config.representative_dte
    holding_weeks = config.holding_weeks

    open_positions: list[_OpenPos] = []
    trades: list[dict] = []
    candidate_log: list[dict] = []

    realized_opt = np.zeros(n)    # cumulative banked option incremental.
    open_opt = np.zeros(n)        # open-position option incremental MTM.
    realized_tilt = np.zeros(n)
    open_tilt = np.zeros(n)
    running_realized_opt = 0.0
    running_realized_tilt = 0.0
    max_concurrent = 0.0
    annual_risk_spent: dict[int, float] = {}

    for i, date in enumerate(calendar):
        spot_by_ticker = {t: _spot(prices, t, i) for t in underlyings}
        state_now = str(cur_state.iloc[i])

        # ---- 1) Manage open positions (MTM + exits) -----------------------
        still_open: list[_OpenPos] = []
        for pos in open_positions:
            weeks_held = i - pos.open_index
            remaining_dte = pos.original_dte - 7.0 * weeks_held
            spot_now = spot_by_ticker.get(pos.underlying)
            if spot_now is None or not np.isfinite(spot_now):
                spot_now = pos.open_spot

            liq = ros.net_liquidation_value(pos.structure, spot_now, max(remaining_dte, 0.0))
            opt_pnl_per_share = liq - pos.entry_cost_basis
            opt_increment = pos.units * opt_pnl_per_share - pos.budget_dollars * (spot_now / pos.open_spot - 1.0)
            tilt_increment = pos.budget_dollars * (spot_now / pos.open_spot - 1.0)

            # Decide exit (held to time stop; optional profit / thesis stop).
            exit_reason = None
            if remaining_dte <= EXIT_DTE:
                exit_reason = "time_stop"
            elif config.profit_taking and (pos.units * opt_pnl_per_share) >= PROFIT_TARGET * pos.budget_dollars:
                exit_reason = "profit_target"
            elif state_now == rse.PANIC_STATE or spot_now <= pos.open_spot * (1.0 + STOP_LOSS_MOVE):
                exit_reason = "thesis_invalidated"

            if exit_reason is not None:
                # Apply exit slippage on the gross notional at close.
                gross_exit = ros.gross_premium(pos.structure, spot_now, max(remaining_dte, 0.0))
                liq_eff = liq - EXIT_SLIPPAGE_FRAC * gross_exit
                opt_pnl_share_eff = liq_eff - pos.entry_cost_basis
                opt_increment = pos.units * opt_pnl_share_eff - pos.budget_dollars * (spot_now / pos.open_spot - 1.0)
                running_realized_opt += opt_increment
                running_realized_tilt += tilt_increment
                trade_return = (pos.units * opt_pnl_share_eff) / pos.budget_dollars  # P&L / capital-at-risk.
                trades.append({
                    "underlying": pos.underlying, "open_date": pos.open_date, "exit_date": date,
                    "exit_index": i, "exit_reason": exit_reason, "structure": config.structure,
                    "dte_bucket": config.dte_bucket, "dte_days": pos.original_dte,
                    "weeks_held": weeks_held, "open_spot": pos.open_spot, "exit_spot": spot_now,
                    "long_strike": pos.structure.lowest_long_strike,
                    "moneyness_long_otm": pos.structure.long_moneyness,
                    "sigma": pos.structure.sigma, "entry_cost_basis": pos.entry_cost_basis,
                    "max_loss_per_share": pos.structure.max_loss_per_share,
                    "premium_fraction": pos.premium_fraction,
                    "trade_return": trade_return,
                    "incremental_dollars": opt_increment,
                    "tilt_incremental_dollars": tilt_increment,
                    "surplus": pos.surplus,
                    "profit_taking": config.profit_taking,
                })
            else:
                open_opt[i] += opt_increment
                open_tilt[i] += tilt_increment
                still_open.append(pos)
        open_positions = still_open
        realized_opt[i] = running_realized_opt
        realized_tilt[i] = running_realized_tilt

        # Track concurrent premium-at-risk (fraction of current NAV).
        nav = float(baseline_equity.iloc[i])
        concurrent_frac = sum(p.premium_fraction for p in open_positions)
        max_concurrent = max(max_concurrent, concurrent_frac)

        # ---- 2) Consider opening new positions ----------------------------
        if i + 2 >= n:  # need at least some room before data ends.
            continue
        open_tickers = {p.underlying for p in open_positions}
        already_risk = sum(p.premium_fraction for p in open_positions)

        for ticker in underlyings:
            if ticker in open_tickers:
                continue
            spot = spot_by_ticker.get(ticker)
            if spot is None or not np.isfinite(spot) or spot <= 0:
                continue

            features = signals.feature_row(date, ticker)
            base_w = _baseline_weight(date, ticker)

            # Price the candidate structure with the marked-up realized-vol proxy.
            rv = features.get("realized_vol")
            sigma = float(rv) * IV_MARKUP if rv is not None and np.isfinite(rv) and rv > 0 else 0.20
            structure = builder(spot, sigma, dte_days)
            ros.price_structure(structure, ENTRY_SLIPPAGE_FRAC)
            if not ros.backspread_risk_zone_acceptable(structure):
                continue
            entry_cost_basis = structure.entry_liquidation + ENTRY_SLIPPAGE_FRAC * structure.gross_premium
            if structure.max_loss_per_share <= 0:
                continue

            decision = rse.evaluate_recovery_entry(
                features, market_state=state_now, baseline_weight=base_w,
                breakeven_move=structure.breakeven_move, horizon_weeks=holding_weeks,
                holding_weeks=holding_weeks, gate_flags=config.gate_flags,
            )

            # Log eligibility (core hard context) for diagnostics.
            core_ok = (base_w >= rse.MIN_BASELINE_WEIGHT and state_now != rse.PANIC_STATE
                       and features.get("recently_defensive", 0) > 0
                       and state_now in rse.RISK_ON_IMPROVING_STATES)
            if core_ok:
                candidate_log.append({
                    "date": date, "underlying": ticker, "entered": bool(decision.active),
                    "surplus": decision.surplus, "expected_move": decision.expected_move,
                    "breakeven_move": structure.breakeven_move, "soft_score": decision.soft_score,
                    "accel_4w": features.get("accel_4w"), "ma_slope": features.get("ma_slope"),
                    "recovery_from_low": features.get("recovery_from_low"),
                    "transition_flag": features.get("transition_flag"),
                    "vix_normalizing": features.get("vix_normalizing"),
                    "vix_term_normalizing": features.get("vix_term_normalizing"),
                    "realized_vol_pct": features.get("realized_vol_pct"),
                    "credit_improvement": features.get("credit_improvement"),
                })

            if not decision.active:
                continue

            # Sizing: premium-at-risk capped per-trade and concurrently.
            new_budget = config.per_trade_risk * nav
            if already_risk + config.per_trade_risk > MAX_CONCURRENT_RISK + 1e-9:
                continue
            year = int(pd.Timestamp(date).year)
            if annual_risk_spent.get(year, 0.0) + config.per_trade_risk > MAX_ANNUAL_RISK + 1e-9:
                continue
            units = new_budget / structure.max_loss_per_share

            open_positions.append(_OpenPos(
                underlying=ticker, open_date=date, open_index=i, open_spot=spot,
                structure=structure, entry_cost_basis=entry_cost_basis, units=units,
                budget_dollars=new_budget, premium_fraction=config.per_trade_risk,
                original_dte=dte_days, features=features, surplus=decision.surplus,
            ))
            already_risk += config.per_trade_risk
            annual_risk_spent[year] = annual_risk_spent.get(year, 0.0) + config.per_trade_risk

    # ---- Assemble equities -------------------------------------------------
    options_equity = baseline_equity.values + realized_opt + open_opt
    tilt_equity = baseline_equity.values + realized_tilt + open_tilt
    equity = pd.DataFrame({
        "baseline_equity": baseline_equity.values,
        "options_equity": options_equity,
        "tilt_equity": tilt_equity,
    }, index=calendar)
    equity.index.name = "Date"
    equity["baseline_return"] = equity["baseline_equity"].pct_change().fillna(0.0)
    equity["options_return"] = equity["options_equity"].pct_change().fillna(0.0)
    equity["tilt_return"] = equity["tilt_equity"].pct_change().fillna(0.0)

    trades_df = pd.DataFrame(trades)
    years = n / 52.0
    n_trades = len(trades_df)
    # Cash premium per year only meaningful for net-debit structures.
    cash_premium = 0.0
    if n_trades:
        cash_premium = float(trades_df.apply(
            lambda r: r["premium_fraction"] if r["entry_cost_basis"] > 0 else 0.0, axis=1).sum())

    return RecoveryResult(
        equity=equity, trades=trades_df, candidate_log=pd.DataFrame(candidate_log), config=config,
        activations_per_year=n_trades / years if years > 0 else np.nan,
        premium_at_risk_per_year=(float(trades_df["premium_fraction"].sum()) / years) if n_trades else 0.0,
        cash_premium_per_year=cash_premium / years if years > 0 else 0.0,
        max_concurrent_risk=max_concurrent,
        avg_dte=float(trades_df["dte_days"].mean()) if n_trades else np.nan,
        avg_moneyness=float(trades_df["moneyness_long_otm"].mean()) if n_trades else np.nan,
    )


def options_equity_excluding(result: RecoveryResult, drop_trade_ids: list[int]) -> pd.Series:
    """Return the options equity with the given trades' banked P&L removed.

    Robustness check helper: subtract each dropped trade's realized incremental
    dollars from the options equity on/after its exit date. (Pre-exit open MTM of
    a removed trade is a small transient and is not subtracted - standard for a
    best-trade-removal robustness check.)
    """

    eq = result.equity["options_equity"].copy()
    if result.trades.empty:
        return eq
    for tid in drop_trade_ids:
        if tid not in result.trades.index:
            continue
        row = result.trades.loc[tid]
        eq.loc[eq.index >= pd.Timestamp(row["exit_date"])] -= float(row["incremental_dollars"])
    return eq


def _spot(prices: pd.DataFrame, ticker: str, i: int):
    try:
        val = float(prices[ticker].iloc[i])
    except (KeyError, IndexError, ValueError):
        return None
    return val if np.isfinite(val) else None
