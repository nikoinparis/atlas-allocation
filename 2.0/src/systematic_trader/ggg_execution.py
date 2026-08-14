"""Causal execution transforms for reducing GGG turnover without changing its target engine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from systematic_trader.challenger_buffering import buffered_target
from systematic_trader.ggg_independent import CASH_PROXY


def _validate(row: pd.Series) -> pd.Series:
    result = pd.to_numeric(row, errors="coerce").fillna(0.0)
    if (result < -1e-12).any() or abs(float(result.sum()) - 1.0) > 1e-9:
        raise ValueError("execution output must remain long-only and fully invested")
    return result.clip(lower=0.0)


def _turnover(previous: pd.Series, target: pd.Series) -> float:
    return float(0.5 * target.sub(previous, fill_value=0.0).abs().sum())


def scheduled_execution(
    targets: pd.DataFrame,
    *,
    cadence_weeks: int | None = None,
    monthly: bool = False,
    emergency_turnover: float | None = None,
    emergency_cash_change: float | None = None,
) -> pd.DataFrame:
    if (cadence_weeks is None) == (not monthly):
        raise ValueError("choose exactly one of cadence_weeks or monthly")
    if cadence_weeks is not None and cadence_weeks < 1:
        raise ValueError("cadence_weeks must be positive")
    rows: list[pd.Series] = []
    previous: pd.Series | None = None
    last_execution = -10**9
    months = targets.index.to_period("M")
    for location, (date, target) in enumerate(targets.iterrows()):
        target = _validate(target)
        if previous is None:
            execute = True
        elif monthly:
            execute = location == len(targets) - 1 or months[location] != months[location + 1]
        else:
            execute = location - last_execution >= int(cadence_weeks)
        if previous is not None and not execute and emergency_turnover is not None:
            cash_change = abs(float(target.get(CASH_PROXY, 0.0) - previous.get(CASH_PROXY, 0.0)))
            execute = _turnover(previous, target) >= emergency_turnover or cash_change >= float(emergency_cash_change or 1.0)
        current = target if execute or previous is None else previous.copy()
        if execute:
            last_execution = location
        current.name = date
        rows.append(_validate(current))
        previous = current
    return pd.DataFrame(rows).reindex(columns=targets.columns).fillna(0.0)


def asset_deadband(targets: pd.DataFrame, threshold: float) -> pd.DataFrame:
    if threshold < 0 or threshold >= 1:
        raise ValueError("threshold must be in [0, 1)")
    risky = [column for column in targets if column != CASH_PROXY]
    rows: list[pd.Series] = []
    previous: pd.Series | None = None
    for date, target in targets.iterrows():
        target = _validate(target)
        if previous is None:
            current = target
        else:
            delta = target[risky] - previous[risky]
            selected = delta.where(delta.abs() > threshold, 0.0)
            negative = selected.clip(upper=0.0)
            positive = selected.clip(lower=0.0)
            available = float(previous.get(CASH_PROXY, 0.0) - negative.sum())
            positive_total = float(positive.sum())
            if positive_total > available + 1e-15:
                positive *= max(0.0, available) / positive_total
            current = previous.copy()
            current.loc[risky] = previous[risky] + negative + positive
            current.loc[CASH_PROXY] = 1.0 - float(current[risky].sum())
        current.name = date
        rows.append(_validate(current))
        previous = current
    return pd.DataFrame(rows).reindex(columns=targets.columns).fillna(0.0)


def band_execution(
    targets: pd.DataFrame,
    *,
    entry_band: float,
    exit_band: float,
    dynamic_band: pd.Series | None = None,
) -> pd.DataFrame:
    previous: pd.Series | None = None
    rows: list[pd.Series] = []
    for date, target in targets.iterrows():
        target = _validate(target)
        if previous is None:
            current = target
        else:
            if dynamic_band is not None:
                band = float(dynamic_band.reindex(targets.index).loc[date])
            else:
                entering_risk = float(target.get(CASH_PROXY, 0.0)) < float(previous.get(CASH_PROXY, 0.0))
                band = entry_band if entering_risk else exit_band
            values, _ = buffered_target(previous.to_dict(), target.to_dict(), no_trade_turnover=band)
            current = pd.Series(values).reindex(targets.columns).fillna(0.0)
        current.name = date
        rows.append(_validate(current))
        previous = current
    return pd.DataFrame(rows).reindex(columns=targets.columns).fillna(0.0)


def volatility_adaptive_band(
    targets: pd.DataFrame,
    prices: pd.DataFrame,
    *,
    calm_band: float,
    stress_band: float,
    spy_volatility_threshold: float,
    lookback_weeks: int,
) -> pd.DataFrame:
    spy = pd.to_numeric(prices["SPY"], errors="coerce").pct_change(fill_method=None)
    volatility = spy.rolling(lookback_weeks, min_periods=lookback_weeks).std(ddof=1) * np.sqrt(52.0)
    bands = pd.Series(calm_band, index=targets.index)
    bands.loc[volatility.reindex(targets.index).gt(spy_volatility_threshold)] = stress_band
    return band_execution(targets, entry_band=calm_band, exit_band=calm_band, dynamic_band=bands)
