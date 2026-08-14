"""IC and signal diagnostics for focused reversal recovery research."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .metrics import rank_ic
from .reversal_signals import CANDIDATES, FOCUSED_FAMILIES, family_for_feature

HOLDOUT_START = pd.Timestamp("2024-04-19")
TARGET_COLUMNS = ["fwd_4w_return", "fwd_8w_return", "fwd_12w_return"]


def compute_ic_by_feature(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = _merged(features, targets)
    numeric = [
        c
        for c in features.select_dtypes(include=[np.number]).columns
        if c not in {"feature_lag_weeks", "price"}
        and not c.startswith("active_")
    ]
    rows = []
    for feature in numeric:
        family = family_for_feature(feature)
        for target in TARGET_COLUMNS:
            for window, sub in _windows(df):
                rows.append(_ic_row(sub, feature, target, family, window))
    return pd.DataFrame(rows)


def compute_signal_scores(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = _merged(features, targets)
    rows = []
    for family, meta in FOCUSED_FAMILIES.items():
        for window, sub in _windows(df):
            row = _ic_row(sub, meta["score"], "fwd_8w_return", family, window)
            row["candidate"] = ""
            row["description"] = meta["description"]
            rows.append(row)
    for candidate, meta in CANDIDATES.items():
        for window, sub in _windows(df):
            row = _ic_row(sub, meta["score"], "fwd_8w_return", family_for_feature(meta["score"]), window)
            row["candidate"] = candidate
            row["description"] = meta["description"]
            row["active_rows"] = int(pd.to_numeric(sub[meta["active"]], errors="coerce").fillna(0).sum())
            rows.append(row)
    return pd.DataFrame(rows)


def compute_filter_diagnostics(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = _merged(features, targets)
    rows = []
    for candidate, meta in CANDIDATES.items():
        score = pd.to_numeric(df[meta["score"]], errors="coerce")
        raw_mask = score >= float(meta["threshold"])
        filtered_mask = pd.to_numeric(df[meta["active"]], errors="coerce").fillna(0) > 0
        for window, sub_idx in _window_masks(df):
            raw = df[raw_mask & sub_idx]
            filtered = df[filtered_mask & sub_idx]
            rows.append(
                {
                    "candidate": candidate,
                    "window": window,
                    "threshold": float(meta["threshold"]),
                    "raw_signal_rows": int(len(raw)),
                    "filtered_signal_rows": int(len(filtered)),
                    "rows_removed_by_filters": int(max(len(raw) - len(filtered), 0)),
                    "raw_precision": _mean(raw, "strong_bounce_label"),
                    "filtered_precision": _mean(filtered, "strong_bounce_label"),
                    "precision_delta": _mean(filtered, "strong_bounce_label") - _mean(raw, "strong_bounce_label"),
                    "raw_failed_bounce_rate": _mean(raw, "failed_bounce_label"),
                    "filtered_failed_bounce_rate": _mean(filtered, "failed_bounce_label"),
                    "failed_bounce_delta": _mean(filtered, "failed_bounce_label") - _mean(raw, "failed_bounce_label"),
                    "raw_crash_continuation_rate": _mean(raw, "crash_continuation_label"),
                    "filtered_crash_continuation_rate": _mean(filtered, "crash_continuation_label"),
                    "crash_continuation_delta": _mean(filtered, "crash_continuation_label") - _mean(raw, "crash_continuation_label"),
                    "filtered_avg_fwd_8w_return": float(filtered["fwd_8w_return"].mean()) if len(filtered) else np.nan,
                    "filtered_worst_fwd_8w_return": float(filtered["fwd_8w_return"].min()) if len(filtered) else np.nan,
                    "non_panic_pass_rate": _pass_rate(raw, "filter_non_panic"),
                    "vol_filter_pass_rate": _pass_rate(raw, "filter_vol_stabilizing"),
                    "credit_filter_pass_rate": _pass_rate(raw, "filter_credit_not_deteriorating"),
                }
            )
    return pd.DataFrame(rows)


def _merged(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _windows(df: pd.DataFrame):
    yield "full", df
    yield "train", df[df["Date"] < HOLDOUT_START]
    yield "holdout", df[df["Date"] >= HOLDOUT_START]


def _window_masks(df: pd.DataFrame):
    yield "full", pd.Series(True, index=df.index)
    yield "train", df["Date"] < HOLDOUT_START
    yield "holdout", df["Date"] >= HOLDOUT_START


def _ic_row(df: pd.DataFrame, feature: str, target: str, family: str, window: str) -> dict:
    sub = df[[feature, target, "strong_bounce_label", "failed_bounce_label", "crash_continuation_label"]].copy()
    sub[feature] = pd.to_numeric(sub[feature], errors="coerce")
    sub[target] = pd.to_numeric(sub[target], errors="coerce")
    sub = sub.dropna(subset=[feature, target])
    ic = float(sub[feature].corr(sub[target])) if len(sub) >= 20 and sub[feature].nunique() > 2 else np.nan
    ric = rank_ic(sub[feature], sub[target]) if len(sub) >= 20 else np.nan
    if len(sub) >= 20:
        active = sub[sub[feature] >= sub[feature].quantile(0.80)]
    else:
        active = sub.iloc[0:0]
    return {
        "family": family,
        "feature": feature,
        "target": target,
        "window": window,
        "ic": ic,
        "rank_ic": ric,
        "n": int(len(sub)),
        "strong_bounce_base_rate": _mean(sub, "strong_bounce_label"),
        "strong_bounce_precision_top_quintile": _mean(active, "strong_bounce_label"),
        "failed_bounce_rate_top_quintile": _mean(active, "failed_bounce_label"),
        "crash_continuation_rate_top_quintile": _mean(active, "crash_continuation_label"),
        "avg_forward_return_top_quintile": float(active[target].mean()) if len(active) else np.nan,
        "median_forward_return_top_quintile": float(active[target].median()) if len(active) else np.nan,
        "worst_forward_return_top_quintile": float(active[target].min()) if len(active) else np.nan,
    }


def _mean(df: pd.DataFrame, col: str) -> float:
    if len(df) == 0 or col not in df.columns:
        return np.nan
    return float(pd.to_numeric(df[col], errors="coerce").mean())


def _pass_rate(df: pd.DataFrame, col: str) -> float:
    if len(df) == 0 or col not in df.columns:
        return np.nan
    return float((pd.to_numeric(df[col], errors="coerce").fillna(0) > 0).mean())

