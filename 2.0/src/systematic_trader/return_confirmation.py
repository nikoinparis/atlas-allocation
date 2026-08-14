"""Causal cross-asset features and embargoed ridge confirmation models."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .nested_ml_challenger import fit_ridge, predict


def cross_asset_features(prices: pd.DataFrame, universe: list[str]) -> pd.DataFrame:
    """Compute decision features, delayed one full weekly observation."""
    prices = prices.apply(pd.to_numeric, errors="coerce")
    returns = prices.pct_change(fill_method=None)
    r13 = prices.div(prices.shift(13)) - 1.0
    r26 = prices.div(prices.shift(26)) - 1.0

    def series(name: str, frame: pd.DataFrame = r13) -> pd.Series:
        return frame[name] if name in frame else pd.Series(np.nan, index=prices.index)

    features = pd.DataFrame(index=prices.index)
    for asset in ("SPY", "QQQ", "IWM", "HYG", "TLT", "PDBC", "GLD", "UUP", "XLE", "XLK"):
        features[f"r13_{asset}"] = series(asset)
    for asset in ("SPY", "QQQ", "IWM", "PDBC"):
        features[f"r26_{asset}"] = series(asset, r26)
    features["hyg_minus_tlt_13"] = series("HYG") - series("TLT")
    features["spy_minus_tlt_13"] = series("SPY") - series("TLT")
    features["pdbc_minus_uup_13"] = series("PDBC") - series("UUP")
    available = [asset for asset in universe if asset in r13]
    features["breadth_positive_13"] = r13[available].gt(0.0).mean(axis=1)
    features["breadth_positive_26"] = r26[available].gt(0.0).mean(axis=1)
    features["spy_volatility_13"] = returns["SPY"].rolling(13, min_periods=8).std(ddof=1) * np.sqrt(52.0)
    return features.replace([np.inf, -np.inf], np.nan).shift(1)


def four_week_labels(excess_returns: pd.Series, decisions: pd.DatetimeIndex, horizon: int = 4) -> pd.DataFrame:
    rows = []
    returns = pd.to_numeric(excess_returns, errors="coerce")
    for decision in decisions:
        location = returns.index.get_loc(decision)
        window = returns.iloc[location:location + horizon]
        if len(window) != horizon or window.isna().any():
            continue
        rows.append({
            "decision": decision,
            "label_end": returns.index[location + horizon - 1],
            "label": float(window.sum()),
        })
    return pd.DataFrame(rows).set_index("decision") if rows else pd.DataFrame(columns=["label_end", "label"])


def expanding_ridge_predictions(
    features: pd.DataFrame,
    labels: pd.DataFrame,
    decisions: pd.DatetimeIndex,
    *,
    penalty: float,
    minimum_training: int = 60,
) -> tuple[pd.Series, pd.DataFrame]:
    predictions = pd.Series(np.nan, index=features.index, dtype=float)
    audit = []
    usable_features = features.dropna()
    columns = list(features.columns)
    for decision in decisions:
        if decision not in usable_features.index:
            continue
        eligible = labels[(labels.label_end < decision) & labels.index.isin(usable_features.index)]
        if len(eligible) < minimum_training:
            audit.append({"decision": decision, "training_rows": len(eligible), "maximum_label_end": pd.NaT, "embargo_pass": True, "predicted": False})
            continue
        x = usable_features.loc[eligible.index, columns].to_numpy(dtype=float).tolist()
        y = eligible.label.to_numpy(dtype=float).tolist()
        model = fit_ridge(x, y, penalty)
        predictions.loc[decision] = predict(model, usable_features.loc[decision, columns].to_numpy(dtype=float).tolist())
        maximum_label_end = eligible.label_end.max()
        audit.append({"decision": decision, "training_rows": len(eligible), "maximum_label_end": maximum_label_end, "embargo_pass": bool(maximum_label_end < decision), "predicted": True})
    return predictions.ffill(), pd.DataFrame(audit).set_index("decision")


def tiered_alpha(predictions: pd.Series, decisions: pd.DatetimeIndex, *, low: float, middle: float, high: float, quantile: float) -> pd.Series:
    alpha = pd.Series(middle, index=predictions.index, dtype=float)
    history: list[float] = []
    for decision in decisions:
        value = predictions.get(decision)
        if pd.isna(value):
            continue
        threshold = float(np.quantile(history, quantile)) if len(history) >= 24 else np.inf
        alpha.loc[decision] = high if float(value) > max(0.0, threshold) else middle if float(value) > 0.0 else low
        history.append(float(value))
    return alpha.loc[decisions].reindex(predictions.index).ffill().fillna(middle)
