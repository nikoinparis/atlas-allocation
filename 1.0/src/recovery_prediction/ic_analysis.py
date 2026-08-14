"""Information-coefficient diagnostics for recovery prediction."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import rank_ic
from .signal_families import FAMILIES

HOLDOUT_START = pd.Timestamp("2024-04-19")


def compute_ic_by_feature(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    rows = []
    numeric = [
        c for c in features.select_dtypes(include=[np.number]).columns
        if c not in {"feature_lag_weeks", "price"}
    ]
    horizons = ["fwd_4w_return", "fwd_8w_return", "fwd_12w_return"]
    for feature in numeric:
        family = _family_for_feature(feature)
        for target in horizons:
            for window, sub in _windows(df):
                rows.append(_ic_row(sub, feature, target, family, window))
    return pd.DataFrame(rows)


def compute_ic_by_regime(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    rows = []
    for family, meta in FAMILIES.items():
        score = meta["score"]
        for regime, sub in df.groupby("market_state"):
            for target in ("fwd_4w_return", "fwd_8w_return", "fwd_12w_return"):
                row = _ic_row(sub, score, target, family, f"regime:{regime}")
                rows.append(row)
    return pd.DataFrame(rows)


def _windows(df: pd.DataFrame):
    d = df.copy()
    d["Date"] = pd.to_datetime(d["Date"])
    yield "full", d
    yield "train", d[d["Date"] < HOLDOUT_START]
    yield "holdout", d[d["Date"] >= HOLDOUT_START]


def _ic_row(df: pd.DataFrame, feature: str, target: str, family: str, window: str) -> dict:
    sub = df[[feature, target, "strong_recovery_label"]].dropna()
    ic = float(sub[feature].corr(sub[target])) if len(sub) >= 20 and sub[feature].nunique() > 2 else np.nan
    ric = rank_ic(sub[feature], sub[target]) if len(sub) >= 20 else np.nan
    active = sub[sub[feature] >= sub[feature].quantile(0.80)] if len(sub) >= 20 else sub.iloc[0:0]
    base_rate = float(sub["strong_recovery_label"].mean()) if len(sub) else np.nan
    precision = float(active["strong_recovery_label"].mean()) if len(active) else np.nan
    return {
        "family": family,
        "feature": feature,
        "target": target,
        "window": window,
        "ic": ic,
        "rank_ic": ric,
        "n": int(len(sub)),
        "strong_recovery_base_rate": base_rate,
        "strong_recovery_precision_top_quintile": precision,
        "avg_forward_return_top_quintile": float(active[target].mean()) if len(active) else np.nan,
        "median_forward_return_top_quintile": float(active[target].median()) if len(active) else np.nan,
    }


def family_scores(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    rows = []
    for family, meta in FAMILIES.items():
        score = meta["score"]
        for window, sub in _windows(df):
            row = _ic_row(sub, score, "fwd_8w_return", family, window)
            row["description"] = meta["description"]
            rows.append(row)
    return pd.DataFrame(rows)


def _family_for_feature(feature: str) -> str:
    for family, meta in FAMILIES.items():
        if feature == meta["score"]:
            return family
    if "drawdown" in feature or "low" in feature or "oversold" in feature:
        return "drawdown_reversal"
    if "negative" in feature or "reversal" in feature:
        return "short_horizon_reversal"
    if "breadth" in feature or "sector" in feature or "risky_pct" in feature:
        return "breadth_thrust"
    if "hyg" in feature or "credit" in feature:
        return "credit_improvement"
    if "vix" in feature or "vol" in feature:
        return "volatility_normalization"
    if "momentum" in feature or "trend" in feature:
        return "momentum_reversal_interaction"
    return "other"

