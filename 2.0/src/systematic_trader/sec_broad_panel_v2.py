"""Gate-independent transformations for a point-in-time broad SEC panel."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

FEATURES = ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def next_execution_date(index: pd.DatetimeIndex, decision: pd.Timestamp, delay_weeks: int) -> pd.Timestamp:
    eligible = index[index >= decision + pd.Timedelta(weeks=delay_weeks)]
    if eligible.empty:
        return pd.NaT
    return eligible[0]


def materialize_panel(membership: pd.DataFrame, features: pd.DataFrame, weekly_prices: pd.DataFrame,
                      *, target_horizon_weeks: int = 13, execution_delay_weeks: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
    required_membership = {"decision_at", "available_at", "cik10", "sector", "validated_price_available"}
    required_features = {"decision_at", "available_at", "cik10", *FEATURES}
    if not required_membership.issubset(membership):
        raise ValueError(f"membership missing {sorted(required_membership - set(membership))}")
    if not required_features.issubset(features):
        raise ValueError(f"features missing {sorted(required_features - set(features))}")
    if execution_delay_weeks < 1:
        raise ValueError("real panel requires at least one full weekly execution delay")
    members, signals = membership.copy(), features.copy()
    members["cik10"] = members.cik10.astype(str).str.zfill(10)
    signals["cik10"] = signals.cik10.astype(str).str.zfill(10)
    members["decision_at"] = pd.to_datetime(members.decision_at, utc=True)
    members["membership_available_at"] = pd.to_datetime(members.pop("available_at"), utc=True)
    signals["decision_at"] = pd.to_datetime(signals.decision_at, utc=True)
    signals["available_at"] = pd.to_datetime(signals.available_at, utc=True)
    if members.duplicated(["decision_at", "cik10"]).any() or signals.duplicated(["decision_at", "cik10"]).any():
        raise ValueError("duplicate decision/issuer source keys")
    panel = members.merge(signals, on=["decision_at", "cik10"], how="left", validate="one_to_one")
    if (panel.membership_available_at > panel.decision_at).any() or (panel.available_at > panel.decision_at).fillna(False).any():
        raise ValueError("source became available after its decision")
    prices = weekly_prices.copy().apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices = prices.sort_index()
    all_ciks = sorted(set(panel.cik10.astype(str)))
    prices = prices.reindex(columns=all_ciks)
    execution_map = {decision: next_execution_date(prices.index, decision, execution_delay_weeks) for decision in panel.decision_at.unique()}
    panel["execution_at"] = panel.decision_at.map(execution_map)
    panel["label_end_at"] = panel.execution_at + pd.Timedelta(weeks=target_horizon_weeks)
    execution_prices, future_returns = [], []
    for row in panel.itertuples(index=False):
        execution = row.execution_at
        end_candidates = prices.index[prices.index >= row.label_end_at] if pd.notna(row.label_end_at) else pd.DatetimeIndex([])
        start = prices.at[execution, row.cik10] if pd.notna(execution) and execution in prices.index else np.nan
        end = prices.at[end_candidates[0], row.cik10] if len(end_candidates) else np.nan
        valid = bool(row.validated_price_available) and pd.notna(start) and float(start) > 0
        execution_prices.append(float(start) if valid else np.nan)
        future_returns.append(float(end / start - 1.0) if valid and pd.notna(end) else np.nan)
    panel["price_at_execution"] = execution_prices
    panel["validated_price_available"] = panel.validated_price_available.astype(bool) & panel.price_at_execution.notna()
    panel["missing_price_policy"] = np.where(panel.validated_price_available, "validated", "base_cash_adverse_total_loss")
    panel["raw_future_return"] = future_returns
    panel["future_sector_relative_return"] = panel.raw_future_return - panel.groupby(["decision_at", "sector"]).raw_future_return.transform("median")
    weekly_returns = prices.pct_change(fill_method=None)
    ordered = ["decision_at", "execution_at", "label_end_at", "available_at", "cik10", "sector", "validated_price_available", "price_at_execution", "missing_price_policy", *FEATURES, "future_sector_relative_return"]
    return panel[ordered].sort_values(["decision_at", "cik10"]).reset_index(drop=True), weekly_returns


def validate_materialized_panel(panel: pd.DataFrame, *, target_horizon_weeks: int = 13) -> dict[str, int | bool]:
    required = {"decision_at", "execution_at", "label_end_at", "available_at", "cik10", "sector", "validated_price_available", "missing_price_policy", *FEATURES, "future_sector_relative_return"}
    if not required.issubset(panel):
        raise ValueError(f"materialized panel missing {sorted(required - set(panel))}")
    data = panel.copy()
    for column in ["decision_at", "execution_at", "label_end_at", "available_at"]:
        data[column] = pd.to_datetime(data[column], utc=True)
    if (data.available_at > data.decision_at).fillna(False).any():
        raise ValueError("late feature in materialized panel")
    if (data.execution_at < data.decision_at + pd.Timedelta(weeks=1)).fillna(False).any():
        raise ValueError("execution delay shorter than one week")
    if (data.label_end_at < data.execution_at + pd.Timedelta(weeks=target_horizon_weeks)).fillna(False).any():
        raise ValueError("training label horizon is too short")
    if data.duplicated(["decision_at", "cik10"]).any():
        raise ValueError("duplicate materialized keys")
    bad_missing = ~data.validated_price_available.astype(bool) & data.missing_price_policy.ne("base_cash_adverse_total_loss")
    if bad_missing.any():
        raise ValueError("missing price lacks explicit stress policy")
    return {"rows": len(data), "decisions": data.decision_at.nunique(), "issuers": data.cik10.nunique(), "causal_timestamps": True, "explicit_missing_policy": True}
