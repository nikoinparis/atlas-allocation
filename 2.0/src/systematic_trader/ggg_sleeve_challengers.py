"""Causal sleeve-level allocation challengers for frozen GGG."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from systematic_trader.ggg_independent import CASH_PROXY, SLEEVES, lookthrough


@dataclass(frozen=True)
class SleeveTiltSpec:
    lookback: int
    momentum_strength: float
    sharpe_strength: float
    inverse_vol_strength: float


def cross_sectional_zscore(values: pd.Series) -> pd.Series:
    valid = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    output = pd.Series(0.0, index=values.index)
    if len(valid) > 1 and float(valid.std(ddof=1)) > 1e-12:
        output.loc[valid.index] = ((valid - valid.mean()) / valid.std(ddof=1)).clip(-2.0, 2.0)
    return output


def score_history(history: pd.DataFrame, spec: SleeveTiltSpec) -> pd.Series:
    sample = history.reindex(columns=SLEEVES).tail(spec.lookback)
    if len(sample) < max(13, spec.lookback // 2):
        return pd.Series(0.0, index=SLEEVES)
    momentum = (1.0 + sample.fillna(0.0)).prod(axis=0) - 1.0
    volatility = sample.std(ddof=1).replace(0.0, np.nan)
    sharpe = sample.mean().div(volatility)
    inverse_vol = -volatility
    return (
        spec.momentum_strength * cross_sectional_zscore(momentum)
        + spec.sharpe_strength * cross_sectional_zscore(sharpe)
        + spec.inverse_vol_strength * cross_sectional_zscore(inverse_vol)
    )


def monthly_score_panel(
    sleeve_returns: pd.DataFrame,
    decision_index: pd.DatetimeIndex,
    spec: SleeveTiltSpec,
) -> pd.DataFrame:
    """Use only outcomes through t-1 when computing a decision-row score."""
    month = decision_index.to_period("M").astype(str).to_numpy()
    rebalance = np.ones(len(decision_index), dtype=bool)
    if len(decision_index) > 1:
        rebalance[:-1] = month[:-1] != month[1:]
    scores: list[pd.Series] = []
    current = pd.Series(0.0, index=SLEEVES)
    for location, date in enumerate(decision_index):
        if rebalance[location]:
            available = sleeve_returns.loc[:date, SLEEVES]
            if len(available):
                available = available.iloc[:-1]
            current = score_history(available, spec)
        row = current.copy()
        row.name = date
        scores.append(row)
    return pd.DataFrame(scores).reindex(columns=SLEEVES).fillna(0.0)


def apply_sleeve_tilt(
    baseline_sleeve_weights: pd.DataFrame,
    sleeve_returns: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    universe: list[str],
    spec: SleeveTiltSpec,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = monthly_score_panel(sleeve_returns, baseline_sleeve_weights.index, spec)
    sleeve_rows: list[pd.Series] = []
    etf_rows: list[pd.Series] = []
    cash_column = f"cash::{CASH_PROXY}"
    for date in baseline_sleeve_weights.index:
        baseline = baseline_sleeve_weights.loc[date].reindex(SLEEVES).fillna(0.0).clip(lower=0.0)
        risky_budget = float(baseline.sum())
        tilted = baseline * np.exp(scores.loc[date])
        if tilted.sum() > 1e-12:
            tilted *= risky_budget / float(tilted.sum())
        row = pd.Series(0.0, index=SLEEVES + [cash_column])
        row.loc[SLEEVES] = tilted
        row.loc[cash_column] = max(0.0, 1.0 - float(tilted.sum()))
        row.name = date
        sleeve_rows.append(row)
        etf = lookthrough(date, tilted, sleeve_positions, universe, float(row[cash_column]))
        etf.name = date
        etf_rows.append(etf)
    return pd.DataFrame(sleeve_rows), pd.DataFrame(etf_rows).reindex(columns=universe).fillna(0.0)
