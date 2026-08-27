"""Pure-Python contracts for the 2026 idea-challenger research program.

The functions here are deliberately separated from live execution.  They make
timing, costs, unavailable data, and promotion boundaries explicit so an idea
can be implemented and rejected without weakening the platform's controls.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class DailyBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    adjusted_close: float

    def adjusted(self) -> tuple[float, float, float, float]:
        if min(self.open, self.high, self.low, self.close, self.adjusted_close) <= 0.0:
            raise ValueError("positive OHLC and adjusted close required")
        factor = self.adjusted_close / self.close
        return self.open * factor, self.high * factor, self.low * factor, self.adjusted_close


@dataclass(frozen=True)
class MinuteBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float

    def validate(self) -> None:
        if min(self.open, self.high, self.low, self.close) <= 0.0:
            raise ValueError("positive intraday OHLC required")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("intraday OHLC ordering is invalid")
        datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))


@dataclass(frozen=True)
class RankedAssetSignal:
    ticker: str
    momentum: float
    volatility: float
    average_correlation: float
    trend_positive: bool


def _validate_cost(cost_bps: float) -> float:
    cost = float(cost_bps) / 10000.0
    if not 0.0 <= cost < 1.0:
        raise ValueError("cost_bps must be in [0, 10000)")
    return cost


def overnight_decomposition(bars: Sequence[DailyBar], *, round_trip_cost_bps: float = 0.0) -> list[dict[str, float | str]]:
    """Split daily returns into previous close->open and open->close legs.

    Costs are charged once to each independently traded leg.  Buy-and-hold
    close-to-close is shown without artificial daily trading costs.
    """
    cost = _validate_cost(round_trip_cost_bps)
    ordered = sorted(bars, key=lambda bar: bar.date)
    rows: list[dict[str, float | str]] = []
    for previous, current in zip(ordered, ordered[1:]):
        previous_close = previous.adjusted()[3]
        current_open, _, _, current_close = current.adjusted()
        overnight_gross = current_open / previous_close - 1.0
        intraday_gross = current_close / current_open - 1.0
        rows.append({
            "date": current.date,
            "overnight_gross": overnight_gross,
            "overnight_net": (1.0 + overnight_gross) * (1.0 - cost) - 1.0,
            "intraday_gross": intraday_gross,
            "intraday_net": (1.0 + intraday_gross) * (1.0 - cost) - 1.0,
            "close_to_close": current_close / previous_close - 1.0,
        })
    return rows


def compound(returns: Sequence[float]) -> float:
    wealth = 1.0
    for value in returns:
        if float(value) <= -1.0 or not math.isfinite(float(value)):
            raise ValueError("finite simple returns above -100% required")
        wealth *= 1.0 + float(value)
    return wealth - 1.0


def ema(values: Sequence[float], period: int) -> list[float]:
    if period < 1 or not values:
        raise ValueError("positive EMA period and observations required")
    alpha = 2.0 / (period + 1.0)
    result = [float(values[0])]
    for value in values[1:]:
        result.append(alpha * float(value) + (1.0 - alpha) * result[-1])
    return result


def true_ranges(bars: Sequence[MinuteBar]) -> list[float]:
    if not bars:
        raise ValueError("bars required")
    for bar in bars:
        bar.validate()
    result = [bars[0].high - bars[0].low]
    for previous, current in zip(bars, bars[1:]):
        result.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    return result


def opening_candle_ema_atr_trade(
    history_and_session: Sequence[MinuteBar], *, session_start_index: int,
    ema_period: int = 12, atr_period: int = 14, atr_multiplier: float = 2.0,
    cost_bps: float = 0.0,
) -> dict[str, float | int | str | bool]:
    """Simulate the exact first-candle/EMA idea with next-bar entry.

    `session_start_index` identifies the first completed regular-hours bar.  The
    signal uses that bar and prior history; execution occurs at the next bar's
    open.  The active trailing stop is checked before it is updated from each
    newly completed bar, preventing same-bar lookahead.
    """
    bars = list(history_and_session)
    if not 0 <= session_start_index < len(bars) - 1:
        raise ValueError("the session must include a first candle and a later executable bar")
    if ema_period < 2 or atr_period < 2 or atr_multiplier <= 0.0:
        raise ValueError("valid EMA and ATR settings required")
    if session_start_index + 1 < max(ema_period, atr_period):
        raise ValueError("insufficient history before the first session candle")
    for bar in bars:
        bar.validate()
    costs = _validate_cost(cost_bps)
    closes = [bar.close for bar in bars[: session_start_index + 1]]
    ema_value = ema(closes, ema_period)[-1]
    ranges = true_ranges(bars[: session_start_index + 1])
    atr = statistics.fmean(ranges[-atr_period:])
    signal_close = bars[session_start_index].close
    side = 1 if signal_close > ema_value else -1
    entry_index = session_start_index + 1
    entry = bars[entry_index].open
    stop = entry - side * atr_multiplier * atr
    exit_price = bars[-1].close
    exit_index = len(bars) - 1
    stopped = False
    favorable = entry
    for index in range(entry_index, len(bars)):
        bar = bars[index]
        if side == 1:
            if bar.open <= stop:
                exit_price, exit_index, stopped = bar.open, index, True
                break
            if bar.low <= stop:
                exit_price, exit_index, stopped = stop, index, True
                break
            favorable = max(favorable, bar.high)
            stop = max(stop, favorable - atr_multiplier * atr)
        else:
            if bar.open >= stop:
                exit_price, exit_index, stopped = bar.open, index, True
                break
            if bar.high >= stop:
                exit_price, exit_index, stopped = stop, index, True
                break
            favorable = min(favorable, bar.low)
            stop = min(stop, favorable + atr_multiplier * atr)
    gross = side * (exit_price / entry - 1.0)
    net = (1.0 + gross) * (1.0 - costs) - 1.0
    return {
        "side": side,
        "ema": ema_value,
        "atr": atr,
        "entry_index": entry_index,
        "entry_price": entry,
        "exit_index": exit_index,
        "exit_price": exit_price,
        "stopped": stopped,
        "gross_return": gross,
        "net_return": net,
        "same_candle_fill_used": False,
    }


def ranked_asset_allocation(signals: Sequence[RankedAssetSignal], *, top_n: int = 5) -> dict[str, float]:
    """Rank momentum, volatility and correlation, then apply a trend gate.

    Lower aggregate rank is better.  A failed trend gate converts the slot to
    CASH instead of reallocating it to another risky asset.  This is the
    transparent RAAM-inspired contract used by the local replication; it does
    not claim exact equivalence to opaque/proprietary paper details.
    """
    items = list(signals)
    if top_n < 1 or len(items) < top_n or len({item.ticker for item in items}) != len(items):
        raise ValueError("unique signals sufficient for top_n are required")

    def ranks(key, reverse=False):
        ordered = sorted(items, key=lambda item: ((-key(item) if reverse else key(item)), item.ticker))
        return {item.ticker: rank for rank, item in enumerate(ordered, 1)}

    momentum_rank = ranks(lambda item: item.momentum, reverse=True)
    volatility_rank = ranks(lambda item: item.volatility)
    correlation_rank = ranks(lambda item: item.average_correlation)
    ordered = sorted(items, key=lambda item: (
        momentum_rank[item.ticker] + volatility_rank[item.ticker] + correlation_rank[item.ticker],
        item.ticker,
    ))[:top_n]
    weight = 1.0 / top_n
    result: dict[str, float] = {item.ticker: weight for item in ordered if item.trend_positive and item.momentum > 0.0}
    result["CASH"] = 1.0 - sum(result.values())
    return result


def _solve_linear(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    size = len(vector)
    if size < 1 or len(matrix) != size or any(len(row) != size for row in matrix):
        raise ValueError("square matrix and matching vector required")
    augmented = [[float(value) for value in row] + [float(vector[index])] for index, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular covariance matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [value - factor * base for value, base in zip(augmented[row], augmented[column])]
    return [augmented[index][-1] for index in range(size)]


def constrained_fractional_kelly(
    expected_returns: Sequence[float], covariance: Sequence[Sequence[float]], *,
    fraction: float = 0.25, maximum_weights: Sequence[float] | None = None,
    maximum_gross: float = 1.0,
) -> list[float]:
    if not 0.0 <= fraction <= 1.0 or maximum_gross < 0.0:
        raise ValueError("fraction must be in [0,1] and maximum gross nonnegative")
    means = [float(value) for value in expected_returns]
    caps = [float(value) for value in (maximum_weights or [maximum_gross] * len(means))]
    if len(caps) != len(means) or any(cap < 0.0 for cap in caps):
        raise ValueError("valid per-asset caps required")
    raw = _solve_linear(covariance, means)
    weights = [min(cap, max(0.0, fraction * value)) for value, cap in zip(raw, caps)]
    gross = sum(weights)
    if gross > maximum_gross > 0.0:
        weights = [value * maximum_gross / gross for value in weights]
    elif maximum_gross == 0.0:
        weights = [0.0 for _ in weights]
    return weights


def option_implied_stock_price(
    *, call_price: float, put_price: float, strike: float, years: float,
    risk_free_rate: float, present_value_dividends: float = 0.0,
) -> float:
    if min(call_price, put_price, strike, years) < 0.0 or strike <= 0.0:
        raise ValueError("nonnegative option inputs and positive strike required")
    return call_price - put_price + strike * math.exp(-risk_free_rate * years) + present_value_dividends


def option_stock_disagreement(
    *, stock_price: float, call_price: float, put_price: float, strike: float,
    years: float, risk_free_rate: float, present_value_dividends: float = 0.0,
) -> dict[str, float]:
    if stock_price <= 0.0:
        raise ValueError("positive stock price required")
    implied = option_implied_stock_price(
        call_price=call_price, put_price=put_price, strike=strike, years=years,
        risk_free_rate=risk_free_rate, present_value_dividends=present_value_dividends,
    )
    return {
        "stock_price": stock_price,
        "option_implied_stock_price": implied,
        "absolute_disagreement": implied - stock_price,
        "relative_disagreement": implied / stock_price - 1.0,
    }


def public_disclosure_is_tradable(
    *, transaction_at: str, public_filing_at: str, decision_at: str
) -> bool:
    transaction = datetime.fromisoformat(transaction_at.replace("Z", "+00:00"))
    filing = datetime.fromisoformat(public_filing_at.replace("Z", "+00:00"))
    decision = datetime.fromisoformat(decision_at.replace("Z", "+00:00"))
    if filing < transaction:
        raise ValueError("public filing cannot precede the disclosed transaction")
    return decision > filing
