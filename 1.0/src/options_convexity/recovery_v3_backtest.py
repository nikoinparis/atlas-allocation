"""Backtest engine for Recovery Options Overlay v3.

v3 is intentionally narrower than the previous recovery experiment:

* SPY/QQQ only.
* Outright calls only.
* 60-90 and 90-120 DTE only.
* Two-stage entries with smaller default sizing.
* Three profit-taking variants: no target, full +100%, partial + runner.

The accounting follows the corrected recovery engine: realized option P&L is
banked permanently, and open positions are marked each week. Each option lot is
compared against the matching ETF slice it displaced, so the result is an
incremental options overlay rather than hidden leverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import option_data, recovery_option_structures as ros, recovery_v3_signal_engine as sig

IV_MARKUP = 1.05
ENTRY_SLIPPAGE_FRAC = 0.05
EXIT_SLIPPAGE_FRAC = 0.05

PILOT_FRACTION = 0.50
INTENDED_RISK = 0.0025          # 0.25% full normal setup; pilot is half.
MAX_CONCURRENT_RISK = 0.0075    # 0.75% NAV.
MAX_ANNUAL_RISK = 0.015         # 1.50% NAV.

EXIT_DTE = 25
ADD_WINDOW_WEEKS = 6
FULL_PROFIT_TARGET = 1.0        # +100% option return.
PARTIAL_PROFIT_TARGET = 1.0
RUNNER_PEAK_GAIN = 2.0          # runner giveback only after +200% peak.
RUNNER_GIVEBACK_LEVEL = 1.0     # exit if falls back to +100%.
TRAILING_UNDERLYING_FAILURE = -0.06

TARGET_VOL_FOR_TILT = 0.16

DTE_BUCKETS = {
    "60-90": {"min": 60, "max": 90, "representative": 75},
    "90-120": {"min": 90, "max": 120, "representative": 105},
}

MONEYNESS_BUCKETS = {
    "itm_atm": {"otm": -0.01, "description": "slightly ITM / ATM"},
    "atm_5otm": {"otm": 0.02, "description": "ATM to 5% OTM primary"},
    "otm_5_8": {"otm": 0.065, "description": "5% to 8% OTM sensitivity"},
}

PROFIT_VARIANTS = {
    "no_target": "A) no profit target",
    "full_100": "B) full exit at +100%",
    "partial_runner": "C) sell 50% at +100%, keep runner",
}


@dataclass
class V3Config:
    dte_bucket: str = "60-90"
    moneyness_bucket: str = "atm_5otm"
    profit_variant: str = "partial_runner"
    intended_risk: float = INTENDED_RISK
    underlyings: list[str] = field(default_factory=lambda: list(sig.V3_UNDERLYINGS))

    @property
    def representative_dte(self) -> int:
        return DTE_BUCKETS[self.dte_bucket]["representative"]

    @property
    def holding_weeks(self) -> float:
        return max((self.representative_dte - EXIT_DTE) / 7.0, 1.0)

    @property
    def otm(self) -> float:
        return MONEYNESS_BUCKETS[self.moneyness_bucket]["otm"]

    @property
    def pilot_risk(self) -> float:
        return self.intended_risk * PILOT_FRACTION

    @property
    def addon_risk(self) -> float:
        return self.intended_risk * (1.0 - PILOT_FRACTION)

    def label(self) -> str:
        return f"v3|dte={self.dte_bucket}|mny={self.moneyness_bucket}|profit={self.profit_variant}"


@dataclass
class _Lot:
    stage: str
    open_date: pd.Timestamp
    open_index: int
    open_spot: float
    structure: ros.RecoveryStructure
    entry_cost_basis: float
    units: float
    budget_dollars: float
    premium_fraction: float
    original_dte: float
    vol_tilt_scale: float
    remaining_fraction: float = 1.0


@dataclass
class _OpenTrade:
    trade_id: int
    underlying: str
    pilot_date: pd.Timestamp
    pilot_index: int
    pilot_spot: float
    lots: list[_Lot]
    pilot_features: dict
    pilot_surplus: float
    added: bool = False
    add_date: pd.Timestamp | None = None
    partial_taken: bool = False
    partial_date: pd.Timestamp | None = None
    peak_option_return: float = -np.inf
    realized_option_pnl: float = 0.0
    realized_incremental: float = 0.0
    realized_tilt_incremental: float = 0.0
    realized_vol_tilt_incremental: float = 0.0
    partial_realized_pnl: float = 0.0
    partial_budget: float = 0.0
    runner_realized_pnl: float = 0.0
    runner_budget: float = 0.0

    @property
    def open_budget(self) -> float:
        return sum(lot.budget_dollars * lot.remaining_fraction for lot in self.lots)

    @property
    def total_budget(self) -> float:
        return sum(lot.budget_dollars for lot in self.lots)

    @property
    def open_premium_fraction(self) -> float:
        return sum(lot.premium_fraction * lot.remaining_fraction for lot in self.lots)


@dataclass
class V3Result:
    equity: pd.DataFrame
    trades: pd.DataFrame
    candidate_log: pd.DataFrame
    config: V3Config
    activations_per_year: float
    premium_at_risk_per_year: float
    cash_premium_per_year: float
    max_concurrent_risk: float
    avg_dte: float
    avg_moneyness: float
    addon_success_rate: float
    partial_trigger_rate: float
    late_entry_block_rate: float


_BASELINE_WEIGHTS: pd.DataFrame | None = None
_BASELINE_WEIGHT_CHANGE: pd.DataFrame | None = None


def _baseline_weight(date, ticker) -> float:
    global _BASELINE_WEIGHTS
    if _BASELINE_WEIGHTS is None:
        _BASELINE_WEIGHTS = option_data.load_baseline_weights()
    return sig._safe(_BASELINE_WEIGHTS, date, ticker, default=0.0)


def _baseline_weight_change_4w(date, ticker) -> float:
    global _BASELINE_WEIGHTS, _BASELINE_WEIGHT_CHANGE
    if _BASELINE_WEIGHTS is None:
        _BASELINE_WEIGHTS = option_data.load_baseline_weights()
    if _BASELINE_WEIGHT_CHANGE is None:
        _BASELINE_WEIGHT_CHANGE = _BASELINE_WEIGHTS - _BASELINE_WEIGHTS.shift(4)
    return sig._safe(_BASELINE_WEIGHT_CHANGE, date, ticker, default=0.0)


def run_v3_backtest(config: V3Config, signals: sig.V3SignalPanel | None = None) -> V3Result:
    """Run one deterministic v3 proxy backtest configuration."""

    underlyings = config.underlyings
    prices = option_data.load_weekly_prices(underlyings)
    baseline_returns = option_data.load_baseline_returns()
    states = option_data.load_market_states()
    signals = signals or sig.build_recovery_v3_signals(underlyings)

    calendar = baseline_returns.index
    net_return = pd.to_numeric(baseline_returns["net_return"], errors="coerce").fillna(0.0).reindex(calendar).fillna(0.0)
    baseline_equity = (1.0 + net_return).cumprod()
    cur_state = states["market_state"].astype(str).reindex(calendar)

    n = len(calendar)
    dte_days = config.representative_dte
    holding_weeks = config.holding_weeks

    open_trades: list[_OpenTrade] = []
    trades: list[dict] = []
    candidate_log: list[dict] = []
    annual_risk_spent: dict[int, float] = {}

    realized_opt = np.zeros(n)
    open_opt = np.zeros(n)
    realized_tilt = np.zeros(n)
    open_tilt = np.zeros(n)
    realized_vol_tilt = np.zeros(n)
    open_vol_tilt = np.zeros(n)
    running_realized_opt = 0.0
    running_realized_tilt = 0.0
    running_realized_vol_tilt = 0.0
    max_concurrent = 0.0
    next_trade_id = 1

    for i, date in enumerate(calendar):
        nav = float(baseline_equity.iloc[i])
        state_now = str(cur_state.iloc[i])
        spot_by_ticker = {t: _spot(prices, t, i) for t in underlyings}

        # 1) Manage open trades: profit taking, thesis exits, time stops.
        still_open: list[_OpenTrade] = []
        for trade in open_trades:
            spot_now = spot_by_ticker.get(trade.underlying)
            if spot_now is None or not np.isfinite(spot_now):
                spot_now = trade.pilot_spot
            features = signals.feature_row(date, trade.underlying)
            min_remaining_dte = min(lot.original_dte - 7.0 * (i - lot.open_index) for lot in trade.lots if lot.remaining_fraction > 0)

            current_return = _option_return(trade, spot_now, i)
            if np.isfinite(current_return):
                trade.peak_option_return = max(trade.peak_option_return, current_return)

            final_reason = None
            latest_lot = max(trade.lots, key=lambda lot: lot.open_index)
            latest_be = latest_lot.structure.breakeven_move
            expected_move = sig.expected_forward_move(features.get("weekly_drift"), max(min_remaining_dte - EXIT_DTE, 7.0) / 7.0)
            surplus = expected_move - latest_be if np.isfinite(expected_move) and np.isfinite(latest_be) else np.nan
            invalid = sig.thesis_invalidation_reasons(features, market_state=state_now, surplus=surplus)
            if min_remaining_dte <= EXIT_DTE:
                final_reason = "time_stop"
            elif invalid:
                final_reason = "thesis_invalidated:" + "|".join(invalid[:3])
            elif trade.partial_taken and spot_now <= trade.pilot_spot * (1.0 + TRAILING_UNDERLYING_FAILURE):
                final_reason = "underlying_trailing_failure"
            elif (
                config.profit_variant == "partial_runner"
                and trade.partial_taken
                and trade.peak_option_return >= RUNNER_PEAK_GAIN
                and current_return <= RUNNER_GIVEBACK_LEVEL
            ):
                final_reason = "runner_giveback"
            elif config.profit_variant == "full_100" and current_return >= FULL_PROFIT_TARGET:
                final_reason = "full_profit_target"

            if final_reason is None and config.profit_variant == "partial_runner" and not trade.partial_taken:
                if current_return >= PARTIAL_PROFIT_TARGET:
                    closed = _close_trade_fraction(trade, spot_now, i, 0.50)
                    running_realized_opt += closed["incremental"]
                    running_realized_tilt += closed["tilt_incremental"]
                    running_realized_vol_tilt += closed["vol_tilt_incremental"]
                    trade.partial_taken = True
                    trade.partial_date = date
                    trade.partial_realized_pnl += closed["option_pnl"]
                    trade.partial_budget += closed["budget"]

            if final_reason is not None:
                closed = _close_trade_fraction(trade, spot_now, i, 1.0)
                running_realized_opt += closed["incremental"]
                running_realized_tilt += closed["tilt_incremental"]
                running_realized_vol_tilt += closed["vol_tilt_incremental"]
                if trade.partial_taken:
                    trade.runner_realized_pnl += closed["option_pnl"]
                    trade.runner_budget += closed["budget"]
                trades.append(_trade_row(trade, date, i, spot_now, final_reason, config))
            else:
                inc = _open_increments(trade, spot_now, i)
                open_opt[i] += inc["incremental"]
                open_tilt[i] += inc["tilt_incremental"]
                open_vol_tilt[i] += inc["vol_tilt_incremental"]
                still_open.append(trade)

        open_trades = still_open
        realized_opt[i] = running_realized_opt
        realized_tilt[i] = running_realized_tilt
        realized_vol_tilt[i] = running_realized_vol_tilt

        # 2) Consider add-ons for pilot trades.
        for trade in list(open_trades):
            if trade.added:
                continue
            weeks_since_pilot = i - trade.pilot_index
            if weeks_since_pilot <= 0 or weeks_since_pilot > ADD_WINDOW_WEEKS:
                continue
            spot = spot_by_ticker.get(trade.underlying)
            if spot is None or not np.isfinite(spot) or spot <= 0:
                continue
            features = signals.feature_row(date, trade.underlying)
            structure, entry_cost_basis = _price_call_structure(spot, features, dte_days, config.otm)
            decision = sig.evaluate_stage2_addon(
                features,
                market_state=state_now,
                breakeven_move=structure.breakeven_move,
                holding_weeks=holding_weeks,
                weeks_since_pilot=weeks_since_pilot,
                max_add_window_weeks=ADD_WINDOW_WEEKS,
            )
            candidate_log.append(_candidate_row(date, trade.underlying, "stage2", decision, features, structure, True))
            if not decision.active:
                continue
            if not _risk_caps_allow(open_trades, annual_risk_spent, date, config.addon_risk):
                continue
            budget = config.addon_risk * nav
            trade.lots.append(_make_lot("addon", date, i, spot, structure, entry_cost_basis, budget, config.addon_risk, features))
            trade.added = True
            trade.add_date = date
            annual_risk_spent[int(pd.Timestamp(date).year)] = annual_risk_spent.get(int(pd.Timestamp(date).year), 0.0) + config.addon_risk

        # 3) Consider new pilot entries.
        if i + int(np.ceil(holding_weeks)) + 2 >= n:
            continue
        open_tickers = {trade.underlying for trade in open_trades}
        for ticker in underlyings:
            if ticker in open_tickers:
                continue
            spot = spot_by_ticker.get(ticker)
            if spot is None or not np.isfinite(spot) or spot <= 0:
                continue

            features = signals.feature_row(date, ticker)
            structure, entry_cost_basis = _price_call_structure(spot, features, dte_days, config.otm)
            base_w = _baseline_weight(date, ticker)
            base_w_chg = _baseline_weight_change_4w(date, ticker)
            decision = sig.evaluate_stage1_entry(
                features,
                market_state=state_now,
                baseline_weight=base_w,
                baseline_weight_change_4w=base_w_chg,
                breakeven_move=structure.breakeven_move,
                holding_weeks=holding_weeks,
            )
            log_candidate = (
                base_w >= sig.MIN_BASELINE_WEIGHT
                or base_w_chg > 0
                or features.get("recently_defensive", 0) > 0
            )
            if log_candidate:
                candidate_log.append(_candidate_row(date, ticker, "stage1", decision, features, structure, False))
            if not decision.active:
                continue
            if not _risk_caps_allow(open_trades, annual_risk_spent, date, config.pilot_risk):
                continue
            budget = config.pilot_risk * nav
            lot = _make_lot("pilot", date, i, spot, structure, entry_cost_basis, budget, config.pilot_risk, features)
            open_trades.append(
                _OpenTrade(
                    trade_id=next_trade_id,
                    underlying=ticker,
                    pilot_date=date,
                    pilot_index=i,
                    pilot_spot=spot,
                    lots=[lot],
                    pilot_features=features,
                    pilot_surplus=decision.surplus,
                )
            )
            next_trade_id += 1
            annual_risk_spent[int(pd.Timestamp(date).year)] = annual_risk_spent.get(int(pd.Timestamp(date).year), 0.0) + config.pilot_risk

        concurrent = sum(trade.open_premium_fraction for trade in open_trades)
        max_concurrent = max(max_concurrent, concurrent)

    # Close any remaining trades on the final available date.
    if open_trades:
        i = n - 1
        date = calendar[-1]
        for trade in open_trades:
            spot_now = _spot(prices, trade.underlying, i) or trade.pilot_spot
            closed = _close_trade_fraction(trade, spot_now, i, 1.0)
            running_realized_opt += closed["incremental"]
            running_realized_tilt += closed["tilt_incremental"]
            running_realized_vol_tilt += closed["vol_tilt_incremental"]
            trades.append(_trade_row(trade, date, i, spot_now, "data_end", config))
        realized_opt[-1] = running_realized_opt
        realized_tilt[-1] = running_realized_tilt
        realized_vol_tilt[-1] = running_realized_vol_tilt

    options_equity = baseline_equity.values + realized_opt + open_opt
    tilt_equity = baseline_equity.values + realized_tilt + open_tilt
    vol_tilt_equity = baseline_equity.values + realized_vol_tilt + open_vol_tilt
    equity = pd.DataFrame(
        {
            "baseline_equity": baseline_equity.values,
            "v3_options_equity": options_equity,
            "v3_tilt_equity": tilt_equity,
            "v3_vol_scaled_tilt_equity": vol_tilt_equity,
        },
        index=calendar,
    )
    equity.index.name = "Date"
    equity["baseline_return"] = equity["baseline_equity"].pct_change().fillna(0.0)
    equity["v3_options_return"] = equity["v3_options_equity"].pct_change().fillna(0.0)
    equity["v3_tilt_return"] = equity["v3_tilt_equity"].pct_change().fillna(0.0)
    equity["v3_vol_scaled_tilt_return"] = equity["v3_vol_scaled_tilt_equity"].pct_change().fillna(0.0)

    trades_df = pd.DataFrame(trades)
    candidate_df = pd.DataFrame(candidate_log)
    years = n / 52.0
    n_trades = len(trades_df)
    if n_trades:
        premium_sum = float(trades_df["premium_fraction"].sum())
        avg_dte = float(trades_df["avg_dte"].mean())
        avg_moneyness = float(trades_df["avg_moneyness"].mean())
        addon_success = float(trades_df["addon_taken"].mean())
        partial_trigger = float(trades_df["partial_taken"].mean())
    else:
        premium_sum = 0.0
        avg_dte = np.nan
        avg_moneyness = np.nan
        addon_success = np.nan
        partial_trigger = np.nan

    late_block_rate = np.nan
    if not candidate_df.empty and "late_entry_blocked" in candidate_df:
        late_block_rate = float(candidate_df["late_entry_blocked"].mean())

    return V3Result(
        equity=equity,
        trades=trades_df,
        candidate_log=candidate_df,
        config=config,
        activations_per_year=n_trades / years if years > 0 else np.nan,
        premium_at_risk_per_year=premium_sum / years if years > 0 else 0.0,
        cash_premium_per_year=premium_sum / years if years > 0 else 0.0,
        max_concurrent_risk=max_concurrent,
        avg_dte=avg_dte,
        avg_moneyness=avg_moneyness,
        addon_success_rate=addon_success,
        partial_trigger_rate=partial_trigger,
        late_entry_block_rate=late_block_rate,
    )


def options_equity_excluding(result: V3Result, drop_trade_ids: list[int]) -> pd.Series:
    eq = result.equity["v3_options_equity"].copy()
    if result.trades.empty:
        return eq
    for tid in drop_trade_ids:
        row = result.trades[result.trades["trade_id"] == tid]
        if row.empty:
            continue
        r = row.iloc[0]
        eq.loc[eq.index >= pd.Timestamp(r["exit_date"])] -= float(r["incremental_dollars"])
    return eq


def _price_call_structure(spot: float, features: dict, dte_days: int, otm: float) -> tuple[ros.RecoveryStructure, float]:
    rv = features.get("realized_vol")
    sigma = float(rv) * IV_MARKUP if rv is not None and np.isfinite(rv) and rv > 0 else 0.20
    structure = ros.build_outright_call(spot, sigma, dte_days, otm=otm)
    ros.price_structure(structure, ENTRY_SLIPPAGE_FRAC)
    entry_cost_basis = structure.entry_liquidation + ENTRY_SLIPPAGE_FRAC * structure.gross_premium
    return structure, entry_cost_basis


def _make_lot(
    stage: str,
    date,
    i: int,
    spot: float,
    structure: ros.RecoveryStructure,
    entry_cost_basis: float,
    budget: float,
    premium_fraction: float,
    features: dict,
) -> _Lot:
    units = budget / structure.max_loss_per_share
    return _Lot(
        stage=stage,
        open_date=pd.Timestamp(date),
        open_index=i,
        open_spot=spot,
        structure=structure,
        entry_cost_basis=entry_cost_basis,
        units=units,
        budget_dollars=budget,
        premium_fraction=premium_fraction,
        original_dte=structure.dte_days,
        vol_tilt_scale=_vol_tilt_scale(features.get("realized_vol")),
    )


def _risk_caps_allow(open_trades: list[_OpenTrade], annual_risk_spent: dict[int, float], date, new_risk: float) -> bool:
    concurrent = sum(trade.open_premium_fraction for trade in open_trades)
    if concurrent + new_risk > MAX_CONCURRENT_RISK + 1e-9:
        return False
    year = int(pd.Timestamp(date).year)
    if annual_risk_spent.get(year, 0.0) + new_risk > MAX_ANNUAL_RISK + 1e-9:
        return False
    return True


def _open_increments(trade: _OpenTrade, spot: float, i: int) -> dict[str, float]:
    incremental = 0.0
    tilt = 0.0
    vol_tilt = 0.0
    for lot in trade.lots:
        if lot.remaining_fraction <= 0:
            continue
        inc = _lot_increment(lot, spot, i, lot.remaining_fraction, apply_exit_slippage=False)
        incremental += inc["incremental"]
        tilt += inc["tilt_incremental"]
        vol_tilt += inc["vol_tilt_incremental"]
    return {"incremental": incremental, "tilt_incremental": tilt, "vol_tilt_incremental": vol_tilt}


def _lot_increment(lot: _Lot, spot: float, i: int, fraction: float, apply_exit_slippage: bool) -> dict[str, float]:
    remaining_dte = max(lot.original_dte - 7.0 * (i - lot.open_index), 0.0)
    liq = ros.net_liquidation_value(lot.structure, spot, remaining_dte)
    if apply_exit_slippage:
        liq -= EXIT_SLIPPAGE_FRAC * ros.gross_premium(lot.structure, spot, remaining_dte)
    option_pnl = lot.units * fraction * (liq - lot.entry_cost_basis)
    etf_pnl = lot.budget_dollars * fraction * (spot / lot.open_spot - 1.0)
    vol_etf_pnl = lot.budget_dollars * lot.vol_tilt_scale * fraction * (spot / lot.open_spot - 1.0)
    return {
        "option_pnl": option_pnl,
        "incremental": option_pnl - etf_pnl,
        "tilt_incremental": etf_pnl,
        "vol_tilt_incremental": vol_etf_pnl,
        "budget": lot.budget_dollars * fraction,
    }


def _close_trade_fraction(trade: _OpenTrade, spot: float, i: int, fraction_of_remaining: float) -> dict[str, float]:
    option_pnl = 0.0
    incremental = 0.0
    tilt = 0.0
    vol_tilt = 0.0
    budget = 0.0
    for lot in trade.lots:
        if lot.remaining_fraction <= 0:
            continue
        close_fraction = lot.remaining_fraction * fraction_of_remaining
        inc = _lot_increment(lot, spot, i, close_fraction, apply_exit_slippage=True)
        option_pnl += inc["option_pnl"]
        incremental += inc["incremental"]
        tilt += inc["tilt_incremental"]
        vol_tilt += inc["vol_tilt_incremental"]
        budget += inc["budget"]
        lot.remaining_fraction = max(lot.remaining_fraction - close_fraction, 0.0)
    trade.realized_option_pnl += option_pnl
    trade.realized_incremental += incremental
    trade.realized_tilt_incremental += tilt
    trade.realized_vol_tilt_incremental += vol_tilt
    return {
        "option_pnl": option_pnl,
        "incremental": incremental,
        "tilt_incremental": tilt,
        "vol_tilt_incremental": vol_tilt,
        "budget": budget,
    }


def _option_return(trade: _OpenTrade, spot: float, i: int) -> float:
    open_option_pnl = 0.0
    for lot in trade.lots:
        if lot.remaining_fraction <= 0:
            continue
        open_option_pnl += _lot_increment(lot, spot, i, lot.remaining_fraction, apply_exit_slippage=False)["option_pnl"]
    denom = trade.total_budget
    return (trade.realized_option_pnl + open_option_pnl) / denom if denom > 0 else np.nan


def _trade_row(trade: _OpenTrade, exit_date, exit_index: int, exit_spot: float, exit_reason: str, config: V3Config) -> dict:
    total_budget = trade.total_budget
    dtes = [lot.original_dte for lot in trade.lots]
    moneyness = [lot.structure.long_moneyness for lot in trade.lots]
    runner_return = trade.runner_realized_pnl / trade.runner_budget if trade.runner_budget > 0 else np.nan
    return {
        "trade_id": trade.trade_id,
        "variant": config.label(),
        "underlying": trade.underlying,
        "pilot_date": trade.pilot_date,
        "open_date": trade.pilot_date,
        "add_date": trade.add_date,
        "partial_date": trade.partial_date,
        "exit_date": exit_date,
        "exit_index": exit_index,
        "exit_reason": exit_reason,
        "profit_variant": config.profit_variant,
        "dte_bucket": config.dte_bucket,
        "moneyness_bucket": config.moneyness_bucket,
        "avg_dte": float(np.mean(dtes)) if dtes else np.nan,
        "avg_moneyness": float(np.mean(moneyness)) if moneyness else np.nan,
        "pilot_spot": trade.pilot_spot,
        "exit_spot": exit_spot,
        "weeks_held": int(exit_index - trade.pilot_index),
        "stage_count": len(trade.lots),
        "addon_taken": trade.added,
        "partial_taken": trade.partial_taken,
        "premium_fraction": sum(lot.premium_fraction for lot in trade.lots),
        "total_budget": total_budget,
        "trade_return": trade.realized_option_pnl / total_budget if total_budget > 0 else np.nan,
        "incremental_dollars": trade.realized_incremental,
        "tilt_incremental_dollars": trade.realized_tilt_incremental,
        "vol_scaled_tilt_incremental_dollars": trade.realized_vol_tilt_incremental,
        "pilot_surplus": trade.pilot_surplus,
        "peak_option_return": trade.peak_option_return,
        "runner_return": runner_return,
        "runner_best_return": runner_return,
        "runner_worst_return": runner_return,
    }


def _candidate_row(date, ticker: str, stage: str, decision: sig.V3Decision, features: dict, structure: ros.RecoveryStructure, existing_position: bool) -> dict:
    return {
        "date": date,
        "underlying": ticker,
        "stage": stage,
        "existing_position": existing_position,
        "entered": bool(decision.active),
        "late_entry_blocked": bool(decision.late_entry_reasons),
        "late_entry_reasons": "|".join(decision.late_entry_reasons),
        "reasons_failed": "|".join(decision.reasons_failed),
        "soft_score": decision.soft_score,
        "expected_move": decision.expected_move,
        "breakeven_move": decision.breakeven_move,
        "surplus": decision.surplus,
        "required_to_realized": decision.required_to_realized,
        "recovery_from_8w_low": features.get("recovery_from_8w_low"),
        "transition_age_weeks": features.get("transition_age_weeks"),
        "dist_fast_ma": features.get("dist_fast_ma"),
        "vix_percentile": features.get("vix_percentile"),
        "vix_normalizing": features.get("vix_normalizing"),
        "credit_improvement": features.get("credit_improvement"),
        "realized_vol_pct": features.get("realized_vol_pct"),
        "accel_4w": features.get("accel_4w"),
        "ma_fast_slope": features.get("ma_fast_slope"),
        "moneyness": structure.long_moneyness,
    }


def _vol_tilt_scale(realized_vol) -> float:
    if realized_vol is None or not np.isfinite(realized_vol) or realized_vol <= 0:
        return 1.0
    return float(np.clip(TARGET_VOL_FOR_TILT / float(realized_vol), 0.5, 1.5))


def _spot(prices: pd.DataFrame, ticker: str, i: int):
    try:
        val = float(prices[ticker].iloc[i])
    except (KeyError, IndexError, ValueError):
        return None
    return val if np.isfinite(val) else None
