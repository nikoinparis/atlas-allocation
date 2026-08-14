"""v2 proxy overlay backtest engine.

This generalizes the v1 engine so a single code path can run any combination of:
  * DTE bucket (representative DTE),
  * option structure (call spread / ATM spread / delta-targeted / naked call),
  * entry-filter ablation level (1..5),
  * premium budget.

It reuses the v1 accounting that produced an honest result:

    overlay_equity = baseline_equity + sum over open positions of
                     (option mark-to-market value - value of the sold ETF slice)

so every option is measured against simply leaving that money in the matching
ETF over the same window (the self-funding source). Options are priced with
Black-Scholes on a realized-volatility IV proxy, held to expiry, settled at
intrinsic, and are non-overlapping per underlying. Conservative entry slippage
and a bid/ask half-spread proxy make options look EXPENSIVE, biasing results
against the overlay.

PROXY MODE: results are APPROXIMATE and NOT production-grade. No real historical
option-chain data is used. This module does not touch production or v1 files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import metrics, option_data, options_dte_sweep, options_signal_engine_v2

# Conservative cost model (intentionally pessimistic for the option buyer).
IV_MARKUP = 1.05          # price options ~5% richer than realized vol.
ENTRY_SLIPPAGE_PCT = 0.05  # pay 5% over modelled mid on entry.
HALF_SPREAD_PROXY = 0.05   # extra 5% bid/ask half-spread proxy (no real chains).
RISK_FREE_RATE = 0.02

# v2 sizing: smaller than v1 by default.
DEFAULT_PREMIUM_BUDGET = 0.01
MIN_PREMIUM_BUDGET = 0.005   # 0.5% floor.
HARD_CAP_TOTAL_PREMIUM = 0.03  # 3% absolute cap across all open options.

OFFICIAL_HOLDOUT_START = pd.Timestamp("2024-04-19")


@dataclass
class V2Config:
    """One concrete v2 backtest configuration."""

    dte_bucket: str = "45-75"
    structure: str = "spread_3_7_10_20"
    ablation_level: int = 5
    premium_budget: float = DEFAULT_PREMIUM_BUDGET
    underlyings: list[str] = field(default_factory=lambda: list(option_data.ELIGIBLE_UNDERLYINGS))

    @property
    def representative_dte(self) -> int:
        return options_dte_sweep.DTE_BUCKETS[self.dte_bucket]["representative"]

    @property
    def horizon_weeks(self) -> int:
        # Round the representative DTE to whole weeks for the weekly clock.
        return max(int(round(self.representative_dte / 7.0)), 1)

    def label(self) -> str:
        return f"{self.structure}|dte={self.dte_bucket}|L{self.ablation_level}|b={self.premium_budget}"


@dataclass
class _OpenPosition:
    underlying: str
    open_date: pd.Timestamp
    open_index: int
    expiry_index: int
    open_spot: float
    structure: options_dte_sweep.StructureSpec
    original_dte: float
    entry_cost_per_share: float
    units: float
    premium_dollars: float
    premium_fraction: float
    features: dict
    expected_move: float
    breakeven_move: float
    surplus: float


@dataclass
class V2BacktestResult:
    equity: pd.DataFrame
    trades: pd.DataFrame
    config: V2Config
    activations_per_year: float
    premium_spent_per_year: float
    avg_dte: float
    avg_moneyness: float
    # Diagnostics captured while scanning (for the signal-diagnostics output).
    candidate_feature_log: pd.DataFrame


def _v2_size_budget(baseline_weight: float, already_allocated: float, requested: float) -> float:
    """Size a new option premium: small, self-funded, hard-capped at 3%."""

    room = HARD_CAP_TOTAL_PREMIUM - already_allocated
    if room <= 0:
        return 0.0
    budget = min(requested, baseline_weight, room)
    if budget < MIN_PREMIUM_BUDGET:
        return 0.0
    return float(budget)


def run_v2_backtest(config: V2Config, signals: options_signal_engine_v2.V2SignalPanel | None = None) -> V2BacktestResult:
    """Run the v2 proxy overlay backtest for a single configuration."""

    underlyings = config.underlyings
    prices = option_data.load_weekly_prices(underlyings)
    baseline_returns = option_data.load_baseline_returns()
    states = option_data.load_market_states()
    signals = signals or options_signal_engine_v2.build_v2_signals(underlyings)

    calendar = baseline_returns.index
    net_return = pd.to_numeric(baseline_returns["net_return"], errors="coerce").fillna(0.0).reindex(calendar).fillna(0.0)
    baseline_equity = (1.0 + net_return).cumprod()

    state_aligned = states.reindex(calendar)
    market_state = state_aligned["market_state"].astype(str)
    market_dd = pd.to_numeric(state_aligned.get("market_drawdown"), errors="coerce")

    horizon = config.horizon_weeks
    dte_days = config.representative_dte
    n = len(calendar)

    open_positions: list[_OpenPosition] = []
    trades: list[dict] = []
    candidate_log: list[dict] = []
    overlay_pnl = np.zeros(n)

    for i, date in enumerate(calendar):
        # ---- 1) Mark / settle existing positions --------------------------
        still_open: list[_OpenPosition] = []
        for pos in open_positions:
            weeks_elapsed = i - pos.open_index
            remaining_dte = max(pos.original_dte - 7.0 * weeks_elapsed, 0.0)
            spot_now = _spot(prices, pos.underlying, i, fallback=pos.open_spot)

            option_value = pos.units * options_dte_sweep.price_structure(
                pos.structure, spot=spot_now, remaining_dte=remaining_dte, risk_free_rate=RISK_FREE_RATE
            )
            etf_slice_value = pos.premium_dollars * (spot_now / pos.open_spot)
            overlay_pnl[i] += option_value - etf_slice_value

            if i >= pos.expiry_index:
                final_intrinsic = options_dte_sweep.structure_payoff_at_expiry(pos.structure, spot_now)
                trade_return = final_intrinsic / pos.entry_cost_per_share - 1.0
                etf_bh_return = spot_now / pos.open_spot - 1.0
                trades.append(
                    {
                        "underlying": pos.underlying,
                        "open_date": pos.open_date,
                        "expiry_date": date,
                        "structure": pos.structure.name,
                        "dte_bucket": config.dte_bucket,
                        "dte_days": pos.original_dte,
                        "ablation_level": config.ablation_level,
                        "open_spot": pos.open_spot,
                        "expiry_spot": spot_now,
                        "long_strike": pos.structure.long_strike,
                        "moneyness_long_otm": options_dte_sweep.average_moneyness(pos.structure),
                        "sigma": pos.structure.sigma,
                        "entry_cost_per_share": pos.entry_cost_per_share,
                        "premium_fraction": pos.premium_fraction,
                        "final_intrinsic": final_intrinsic,
                        "trade_return": trade_return,
                        "etf_buy_hold_return": etf_bh_return,
                        "incremental_return_vs_etf": pos.premium_fraction * (trade_return - etf_bh_return),
                        "expected_move": pos.expected_move,
                        "breakeven_move": pos.breakeven_move,
                        "surplus": pos.surplus,
                        "accel_4w": pos.features.get("accel_4w"),
                        "vol_percentile": pos.features.get("vol_percentile"),
                        "dd_recovery": pos.features.get("dd_recovery"),
                    }
                )
            else:
                still_open.append(pos)
        open_positions = still_open

        # ---- 2) Consider opening new positions ----------------------------
        if i + horizon >= n:
            continue  # not enough room to settle before data ends.

        already_allocated = sum(p.premium_fraction for p in open_positions)
        open_underlyings = {p.underlying for p in open_positions}

        for ticker in underlyings:
            if ticker in open_underlyings:
                continue

            spot = _spot(prices, ticker, i, fallback=np.nan)
            if not np.isfinite(spot) or spot <= 0:
                continue

            features = signals.feature_row(date, ticker)
            base_w = _baseline_weight(date, ticker)

            # Price the candidate structure with the (marked-up) IV proxy.
            rv = features.get("realized_vol")
            sigma = float(rv) * IV_MARKUP if rv is not None and np.isfinite(rv) and rv > 0 else 0.20
            structure = options_dte_sweep.build_structure(config.structure, spot, sigma, dte_days, RISK_FREE_RATE)
            net_premium = options_dte_sweep.price_structure(structure, risk_free_rate=RISK_FREE_RATE)
            if net_premium <= 0:
                continue
            entry_cost = net_premium * (1.0 + ENTRY_SLIPPAGE_PCT + HALF_SPREAD_PROXY)
            be_move = options_dte_sweep.breakeven_move(structure, entry_cost)

            decision = options_signal_engine_v2.evaluate_v2_entry(
                features,
                level=config.ablation_level,
                market_state=str(market_state.iloc[i]),
                market_drawdown=float(market_dd.iloc[i]) if np.isfinite(market_dd.iloc[i]) else 0.0,
                baseline_weight=base_w,
                breakeven_move=be_move,
                horizon_weeks=horizon,
                iv_history_available=np.isfinite(features.get("vol_percentile", np.nan)),
            )

            # Log every bullish-eligible candidate (level-1 pass) for diagnostics.
            level1 = options_signal_engine_v2.evaluate_v2_entry(
                features, level=1, market_state=str(market_state.iloc[i]),
                market_drawdown=float(market_dd.iloc[i]) if np.isfinite(market_dd.iloc[i]) else 0.0,
                baseline_weight=base_w, breakeven_move=be_move, horizon_weeks=horizon,
            )
            if level1.active:
                candidate_log.append(
                    {
                        "date": date, "underlying": ticker, "entered": bool(decision.active),
                        "surplus": decision.surplus, "expected_move": decision.expected_move,
                        "breakeven_move": be_move, "accel_4w": features.get("accel_4w"),
                        "ma_slope": features.get("ma_slope"), "vol_percentile": features.get("vol_percentile"),
                        "rv_vs_median": features.get("rv_vs_median"), "dd_recovery": features.get("dd_recovery"),
                        "risk_on_transition": features.get("risk_on_transition"),
                        "credit_improvement": features.get("credit_improvement"),
                    }
                )

            if not decision.active:
                continue

            budget = _v2_size_budget(base_w, already_allocated, config.premium_budget)
            if budget <= 0:
                continue

            premium_dollars = budget * float(baseline_equity.iloc[i])
            units = premium_dollars / entry_cost
            open_positions.append(
                _OpenPosition(
                    underlying=ticker, open_date=date, open_index=i, expiry_index=i + horizon,
                    open_spot=spot, structure=structure, original_dte=dte_days,
                    entry_cost_per_share=entry_cost, units=units, premium_dollars=premium_dollars,
                    premium_fraction=budget, features=features,
                    expected_move=decision.expected_move, breakeven_move=be_move, surplus=decision.surplus,
                )
            )
            already_allocated += budget

    # ---- Assemble equity + summaries --------------------------------------
    overlay_equity = baseline_equity.values + overlay_pnl
    equity = pd.DataFrame(
        {"baseline_equity": baseline_equity.values, "overlay_equity": overlay_equity},
        index=calendar,
    )
    equity.index.name = "Date"
    equity["baseline_return"] = equity["baseline_equity"].pct_change().fillna(0.0)
    equity["overlay_return"] = equity["overlay_equity"].pct_change().fillna(0.0)

    trades_df = pd.DataFrame(trades)
    years = n / 52.0
    n_trades = len(trades_df)

    return V2BacktestResult(
        equity=equity,
        trades=trades_df,
        config=config,
        activations_per_year=n_trades / years if years > 0 else np.nan,
        premium_spent_per_year=(float(trades_df["premium_fraction"].sum()) / years) if n_trades else 0.0,
        avg_dte=float(trades_df["dte_days"].mean()) if n_trades else np.nan,
        avg_moneyness=float(trades_df["moneyness_long_otm"].mean()) if n_trades else np.nan,
        candidate_feature_log=pd.DataFrame(candidate_log),
    )


def sharpe_excluding_best_trade(result: V2BacktestResult) -> float:
    """Recompute overlay Sharpe with the single best trade's P&L removed.

    Robustness check for "is the edge just one lucky trade?". We strip the best
    trade's incremental dollar contribution from the overlay equity on/after its
    expiry and recompute Sharpe on the resulting return path.
    """

    equity, trades = result.equity, result.trades
    if trades.empty:
        return metrics.sharpe(equity["overlay_return"])

    best_idx = trades["incremental_return_vs_etf"].astype(float).idxmax()
    best = trades.loc[best_idx]
    open_date = pd.Timestamp(best["open_date"])
    base_at_open = float(equity.loc[:open_date]["baseline_equity"].iloc[-1])
    incr_dollars = float(best["incremental_return_vs_etf"]) * base_at_open

    adj = equity.copy()
    mask = adj.index >= pd.Timestamp(best["expiry_date"])
    adj.loc[mask, "overlay_equity"] = adj.loc[mask, "overlay_equity"] - incr_dollars
    return metrics.sharpe(adj["overlay_equity"].pct_change().fillna(0.0))


# --------------------------------------------------------------------------
# small caching of the baseline weight panel (read once, reused per lookup)
# --------------------------------------------------------------------------
_BASELINE_WEIGHTS_CACHE: pd.DataFrame | None = None


def _baseline_weight(date, ticker: str) -> float:
    global _BASELINE_WEIGHTS_CACHE
    if _BASELINE_WEIGHTS_CACHE is None:
        _BASELINE_WEIGHTS_CACHE = option_data.load_baseline_weights()
    return _safe(_BASELINE_WEIGHTS_CACHE, date, ticker, default=0.0)


def _spot(prices: pd.DataFrame, ticker: str, i: int, fallback: float) -> float:
    try:
        val = float(prices[ticker].iloc[i])
    except (KeyError, IndexError, ValueError):
        return fallback
    return val if np.isfinite(val) else fallback


def _safe(df: pd.DataFrame, date, ticker: str, default: float = np.nan) -> float:
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
