"""Normalization helpers for immutable free regime-data snapshots."""

from __future__ import annotations

import pandas as pd

GOOGLE_KEYWORDS = ("recession", "stock market crash", "inflation", "bear market")


def completed_fridays(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="W-FRI", name="Date")


def normalize_cboe(observations: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = observations.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    wide = frame.dropna(subset=["observation_date", "value"]).pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="last"
    )
    weekly = wide.sort_index().resample("W-FRI").last().reindex(index)
    for name in ("VIX", "VIX3M", "VIX6M"):
        if name not in weekly:
            weekly[name] = pd.NA
    weekly["slope_1m_3m"] = weekly["VIX3M"] - weekly["VIX"]
    weekly["slope_1m_6m"] = weekly["VIX6M"] - weekly["VIX"]
    weekly["contango"] = weekly["slope_1m_3m"].gt(0).astype(int)
    weekly["stress_flag"] = weekly["VIX"].gt(30).astype(int)
    return weekly[["VIX", "VIX3M", "VIX6M", "slope_1m_3m", "slope_1m_6m", "contango", "stress_flag"]]


def normalize_fred(observations: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = observations.copy()
    frame["observation_date"] = pd.to_datetime(frame["observation_date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"], errors="coerce")
    wide = frame.dropna(subset=["observation_date", "value"]).pivot_table(
        index="observation_date", columns="series_id", values="value", aggfunc="last"
    )
    weekly = wide.sort_index().resample("W-FRI").last().reindex(index).ffill()
    if {"FEDFUNDS", "DGS3MO"}.issubset(weekly.columns):
        weekly["policy_minus_3m"] = weekly["FEDFUNDS"] - weekly["DGS3MO"]
    return weekly


def normalize_google(raw: pd.DataFrame, index: pd.DatetimeIndex) -> pd.DataFrame:
    frame = raw.copy()
    date_column = "Date" if "Date" in frame else frame.columns[0]
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    frame = frame.dropna(subset=[date_column]).set_index(date_column)
    available = [name for name in GOOGLE_KEYWORDS if name in frame]
    weekly = frame[available].apply(pd.to_numeric, errors="coerce").resample("W-FRI").last()
    weekly = weekly.reindex(index).ffill(limit=2)
    for column in available:
        mean = weekly[column].rolling(104, min_periods=52).mean()
        std = weekly[column].rolling(104, min_periods=52).std()
        weekly[f"{column}_zscore"] = (weekly[column] - mean) / (std + 1e-8)
    weekly["fear_composite"] = weekly[available].mean(axis=1) if available else pd.NA
    mean = weekly["fear_composite"].rolling(104, min_periods=52).mean()
    std = weekly["fear_composite"].rolling(104, min_periods=52).std()
    weekly["fear_composite_zscore"] = (weekly["fear_composite"] - mean) / (std + 1e-8)
    return weekly


def splice_frozen_history(frozen: pd.DataFrame, continuation: pd.DataFrame, cutoff: str) -> pd.DataFrame:
    cutoff_date = pd.Timestamp(cutoff)
    left = frozen.loc[frozen.index <= cutoff_date]
    right = continuation.loc[continuation.index > cutoff_date]
    return pd.concat([left, right]).sort_index()
