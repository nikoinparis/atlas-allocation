"""Forward targets for focused reversal recovery research."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .feature_engineering import TARGET_TICKERS, load_weekly_prices


def build_targets(feature_panel: pd.DataFrame) -> pd.DataFrame:
    prices = load_weekly_prices()[TARGET_TICKERS]
    rows = []
    for ticker in TARGET_TICKERS:
        px = prices[ticker]
        tmp = pd.DataFrame(index=prices.index)
        tmp["ticker"] = ticker
        for h in (4, 8, 12):
            tmp[f"fwd_{h}w_return"] = px.shift(-h) / px - 1.0
        tmp["fwd_8w_return_rank_pct"] = tmp["fwd_8w_return"].rank(pct=True)
        tmp["future_8w_min_return"] = _future_min_return(px, 8)
        tmp["future_12w_min_return"] = _future_min_return(px, 12)
        recent_weakness = px.pct_change(4) <= -0.03
        tmp["strong_bounce_label"] = ((tmp["fwd_8w_return"] >= 0.04) | (tmp["fwd_4w_return"] >= 0.025)).astype(float)
        tmp["failed_bounce_label"] = ((tmp["fwd_4w_return"] > 0.015) & (tmp["fwd_12w_return"] <= 0.0)).astype(float)
        tmp["crash_continuation_label"] = (recent_weakness & (tmp["future_8w_min_return"] <= -0.06)).astype(float)
        tmp["reversal_success_label"] = (
            (tmp["fwd_8w_return"] > 0.0) & (tmp["future_8w_min_return"] > -0.04)
        ).astype(float)
        rows.append(tmp.reset_index().rename(columns={"index": "Date"}))

    targets = pd.concat(rows, ignore_index=True)
    keep = feature_panel[["Date", "ticker"]].drop_duplicates()
    return keep.merge(targets, on=["Date", "ticker"], how="left")


def _future_min_return(px: pd.Series, horizon: int) -> pd.Series:
    vals = []
    arr = px.values.astype(float)
    for i in range(len(arr)):
        end = min(i + horizon + 1, len(arr))
        future = arr[i + 1:end]
        if len(future) == 0 or not np.isfinite(arr[i]) or arr[i] <= 0:
            vals.append(np.nan)
        else:
            vals.append(float(np.nanmin(future / arr[i] - 1.0)))
    return pd.Series(vals, index=px.index)

