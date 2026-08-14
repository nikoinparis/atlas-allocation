"""Historical PROXY overlay backtest and baseline-vs-overlay comparison.

This is the heart of the research experiment. Because reliable historical
option-chain data is NOT available in this project, this backtest runs in PROXY
mode: it prices call spreads with Black-Scholes using a realized-volatility IV
proxy. Results are therefore APPROXIMATE and NOT production-grade. They are a
study of whether the idea is worth pursuing, not a tradable P&L.

How the overlay is modelled (read this before trusting the numbers)
------------------------------------------------------------------
* We start from the existing baseline production portfolio's weekly NET returns.
  We never recompute or modify the baseline; we only add an overlay on top.
* The options sleeve is SELF-FUNDED: when we activate an option on ETF X we
  "sell" a small slice of ETF X (the premium budget, 1-3%, hard-capped at 3%)
  and spend exactly that on a bull call spread. No leverage is added.
* Each open option is marked-to-market every week with Black-Scholes (decaying
  time, entry IV held fixed for determinism), and at expiry it settles at
  intrinsic value. Positions are held to expiry (no early exit) and are
  non-overlapping per underlying.
* The overlay equity is:  baseline_equity + (option value - sold-ETF-slice value)
  summed over open positions. So we always measure the option versus simply
  leaving that money in the matching ETF over the same window. That is the
  honest "incremental" question: did the convexity beat the ETF it replaced?
* Entry slippage and a conservative IV markup make options look EXPENSIVE, so
  the proxy is biased against the overlay, not for it.

All decision-time signals are causal (lagged in ``option_data``); the backtest
never uses week-t outcomes to make the week-t decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data, overlay_rules
from .option_pricing import (
    apply_entry_slippage,
    call_spread_payoff_at_expiry,
    price_call_spread,
)
from .option_selection import build_proxy_call_spread

# Horizon in weeks for a held-to-expiry spread (~90 DTE = 13 weeks).
HORIZON_WEEKS = 13
ENTRY_SLIPPAGE_PCT = 0.05
IV_MARKUP = 1.05  # IV proxy markup: options priced ~5% richer than realized vol.
RISK_FREE_RATE = 0.02


@dataclass
class OpenPosition:
    """An open spread position tracked through its life for weekly MTM."""

    underlying: str
    open_date: pd.Timestamp
    expiry_index: int
    open_spot: float
    long_strike: float
    short_strike: float
    sigma: float
    original_dte: float
    entry_cost_per_share: float  # per-share debit actually paid (with slippage)
    units: float  # number of underlying-share-equivalents
    premium_dollars: float  # premium spent, in portfolio-equity dollars
    premium_fraction: float  # premium as fraction of portfolio at open


@dataclass
class OverlayBacktestResult:
    """Bundle of everything the runner needs to write outputs."""

    equity: pd.DataFrame  # date, baseline_equity, overlay_equity, returns
    trades: pd.DataFrame
    activations_per_year: float
    premium_spent_per_year: float
    config: dict = field(default_factory=dict)


def _spread_mtm(position: OpenPosition, spot: float, remaining_dte: float) -> float:
    """Mark-to-market the spread (theoretical, no slippage) at ``spot``.

    At or past expiry the value is the intrinsic settlement payoff.
    """

    if remaining_dte <= 0:
        return call_spread_payoff_at_expiry(spot, position.long_strike, position.short_strike)
    quote = price_call_spread(
        spot=spot,
        long_strike=position.long_strike,
        short_strike=position.short_strike,
        dte_days=remaining_dte,
        sigma=position.sigma,
        risk_free_rate=RISK_FREE_RATE,
    )
    return max(quote.net_premium, 0.0)


def run_proxy_overlay_backtest(
    underlyings: list[str] | None = None,
    *,
    premium_budget: float = overlay_rules.DEFAULT_PREMIUM_BUDGET,
    horizon_weeks: int = HORIZON_WEEKS,
) -> OverlayBacktestResult:
    """Run the full historical proxy overlay backtest.

    Returns an :class:`OverlayBacktestResult` with the equity curves, the trade
    log, and activation / premium summary statistics. Deterministic given the
    input data and config (no randomness).
    """

    underlyings = underlyings or option_data.ELIGIBLE_UNDERLYINGS

    # --- Load read-only inputs ---------------------------------------------
    prices = option_data.load_weekly_prices(underlyings)
    baseline_weights = option_data.load_baseline_weights()
    baseline_returns = option_data.load_baseline_returns()
    states = option_data.load_market_states()

    # --- Build causal (lagged) signals -------------------------------------
    trend = option_data.build_trend_signals(prices)
    iv_proxy = option_data.build_iv_proxy(prices)
    iv_pct = option_data.iv_percentile(iv_proxy)

    # Align everything onto the baseline return calendar (the trading clock).
    calendar = baseline_returns.index
    net_return = pd.to_numeric(baseline_returns["net_return"], errors="coerce").fillna(0.0)
    net_return = net_return.reindex(calendar).fillna(0.0)

    # Pre-extract state columns we need, aligned to the calendar.
    state_series = states.reindex(calendar)
    market_state = state_series["market_state"].astype(str)
    market_dd = pd.to_numeric(state_series.get("market_drawdown"), errors="coerce")

    n = len(calendar)
    open_positions: list[OpenPosition] = []
    trades: list[dict] = []

    # Net overlay dollar P&L vs baseline at each week (option value minus the
    # value the sold ETF slice would have had). Added on top of baseline equity.
    overlay_pnl = np.zeros(n)

    # Track baseline equity so the premium budget is sized off real portfolio $.
    baseline_equity = (1.0 + net_return).cumprod()

    for i, date in enumerate(calendar):
        # ---- 1) Mark existing open positions to market for THIS week ------
        still_open: list[OpenPosition] = []
        for pos in open_positions:
            weeks_elapsed = i - (pos.expiry_index - horizon_weeks)
            remaining_dte = max(pos.original_dte - 7.0 * weeks_elapsed, 0.0)
            spot_now = float(prices[pos.underlying].iloc[i]) if pos.underlying in prices else np.nan

            if np.isnan(spot_now):
                # If price is unavailable, carry value flat (defensive).
                spot_now = pos.open_spot

            option_value = pos.units * _spread_mtm(pos, spot_now, remaining_dte)
            etf_slice_value = pos.premium_dollars * (spot_now / pos.open_spot)
            overlay_pnl[i] += option_value - etf_slice_value

            if i >= pos.expiry_index:
                # Settle at expiry: record the realized trade economics.
                final_intrinsic = call_spread_payoff_at_expiry(
                    spot_now, pos.long_strike, pos.short_strike
                )
                trade_return = final_intrinsic / pos.entry_cost_per_share - 1.0
                etf_buy_hold_return = spot_now / pos.open_spot - 1.0
                incremental_vs_etf = pos.premium_fraction * (trade_return - etf_buy_hold_return)
                trades.append(
                    {
                        "underlying": pos.underlying,
                        "open_date": pos.open_date,
                        "expiry_date": date,
                        "open_spot": pos.open_spot,
                        "expiry_spot": spot_now,
                        "long_strike": pos.long_strike,
                        "short_strike": pos.short_strike,
                        "sigma": pos.sigma,
                        "dte_days": pos.original_dte,
                        "entry_cost_per_share": pos.entry_cost_per_share,
                        "premium_fraction": pos.premium_fraction,
                        "final_intrinsic": final_intrinsic,
                        "trade_return": trade_return,
                        "etf_buy_hold_return": etf_buy_hold_return,
                        "incremental_return_vs_etf": incremental_vs_etf,
                    }
                )
            else:
                still_open.append(pos)
        open_positions = still_open

        # ---- 2) Consider opening NEW positions this week ------------------
        # Cannot open if there is no room to settle before the data ends.
        if i + horizon_weeks >= n:
            continue

        already_allocated = sum(p.premium_fraction for p in open_positions)
        open_underlyings = {p.underlying for p in open_positions}

        for ticker in underlyings:
            if ticker in open_underlyings:
                continue  # non-overlapping per underlying.

            spot = float(prices[ticker].iloc[i])
            if not np.isfinite(spot) or spot <= 0:
                continue

            # Gather causal signal values for this ticker / week.
            mom_13w = _safe(trend["mom_13w"], date, ticker)
            mom_26w = _safe(trend["mom_26w"], date, ticker)
            above_sma = _safe(trend["above_sma_40w"], date, ticker)
            ticker_iv = _safe(iv_proxy, date, ticker)
            ticker_iv_pct = _safe(iv_pct, date, ticker)
            base_w = _safe(baseline_weights, date, ticker, default=0.0)

            decision = overlay_rules.evaluate_activation(
                ticker,
                market_state=str(market_state.iloc[i]),
                market_drawdown=float(market_dd.iloc[i]) if np.isfinite(market_dd.iloc[i]) else 0.0,
                mom_13w=mom_13w,
                mom_26w=mom_26w,
                above_sma=above_sma,
                baseline_weight=base_w,
                iv_pct=ticker_iv_pct,
                liquidity_ok=True,  # 5 chosen ETFs are highly liquid (proxy mode).
                iv_history_available=np.isfinite(ticker_iv_pct),
            )
            if not decision.active:
                continue

            budget = overlay_rules.size_premium_budget(
                baseline_weight=base_w,
                already_allocated=already_allocated,
                requested_budget=premium_budget,
            )
            if budget <= 0:
                continue

            # Price the proxy spread with the (marked-up) IV proxy.
            sigma = float(ticker_iv) * IV_MARKUP if np.isfinite(ticker_iv) and ticker_iv > 0 else 0.20
            spread = build_proxy_call_spread(ticker, spot, sigma, dte_days=horizon_weeks * 7)
            if spread.net_premium <= 0:
                continue

            entry_cost = apply_entry_slippage(spread.net_premium, ENTRY_SLIPPAGE_PCT)
            premium_dollars = budget * float(baseline_equity.iloc[i])
            units = premium_dollars / entry_cost  # share-equivalents

            open_positions.append(
                OpenPosition(
                    underlying=ticker,
                    open_date=date,
                    expiry_index=i + horizon_weeks,
                    open_spot=spot,
                    long_strike=spread.long_strike,
                    short_strike=spread.short_strike,
                    sigma=sigma,
                    original_dte=horizon_weeks * 7,
                    entry_cost_per_share=entry_cost,
                    units=units,
                    premium_dollars=premium_dollars,
                    premium_fraction=budget,
                )
            )
            already_allocated += budget

    # --- Assemble equity curves --------------------------------------------
    overlay_equity = baseline_equity.values + overlay_pnl
    equity = pd.DataFrame(
        {
            "baseline_equity": baseline_equity.values,
            "overlay_equity": overlay_equity,
        },
        index=calendar,
    )
    equity.index.name = "Date"
    equity["baseline_return"] = equity["baseline_equity"].pct_change().fillna(0.0)
    equity["overlay_return"] = equity["overlay_equity"].pct_change().fillna(0.0)

    trades_df = pd.DataFrame(trades)
    years = n / 52.0
    n_trades = len(trades_df)
    total_premium_fraction = (
        float(trades_df["premium_fraction"].sum()) if n_trades else 0.0
    )

    return OverlayBacktestResult(
        equity=equity,
        trades=trades_df,
        activations_per_year=n_trades / years if years > 0 else np.nan,
        premium_spent_per_year=total_premium_fraction / years if years > 0 else np.nan,
        config={
            "underlyings": underlyings,
            "premium_budget": premium_budget,
            "hard_cap_total_premium": overlay_rules.HARD_CAP_TOTAL_PREMIUM,
            "horizon_weeks": horizon_weeks,
            "entry_slippage_pct": ENTRY_SLIPPAGE_PCT,
            "iv_markup": IV_MARKUP,
            "risk_free_rate": RISK_FREE_RATE,
            "mode": "historical_proxy_black_scholes",
            "proxy_warning": "APPROXIMATE - not production-grade. IV is proxied by "
            "realized volatility; no real option-chain data used.",
        },
    )


def _safe(df: pd.DataFrame, date, ticker: str, default: float = np.nan) -> float:
    """Safely fetch df.loc[date, ticker] returning ``default`` if missing/NaN."""

    try:
        val = df.loc[date, ticker]
    except (KeyError, IndexError):
        return default
    if isinstance(val, pd.Series):
        val = val.iloc[0]
    try:
        val = float(val)
    except (TypeError, ValueError):
        return default
    return val if np.isfinite(val) else default
