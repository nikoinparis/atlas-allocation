"""ETF tilt backtests for recovery prediction signals."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics
from .feature_engineering import TARGET_TICKERS, load_baseline_returns, load_weekly_prices
from .signal_families import FAMILIES

HOLDOUT_START = pd.Timestamp("2024-04-19")
DEFAULT_TILT = 0.05
TILT_SIZES = [0.025, 0.05, 0.075]


def run_family_backtests(features: pd.DataFrame, targets: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    rows = []
    returns_by_name = {}
    for family, meta in FAMILIES.items():
        for tilt in TILT_SIZES:
            label = f"{family}_tilt_{int(tilt * 1000)}bp"
            result = run_score_backtest(features, targets, meta["score"], label, threshold=0.65, tilt_size=tilt)
            rows.append(result["summary"])
            returns_by_name[label] = result["returns"]
    return pd.DataFrame(rows), returns_by_name


def run_combination_backtests(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    classifier_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.Series]]:
    rows = []
    returns_by_name = {}
    definitions = [
        ("equal_weight_six_family_composite", "score_equal_weight_composite", 0.65),
        ("regime_gated_composite", "score_regime_gated_composite", 0.60),
        ("and_gated_drawdown_credit_vol", "score_and_gated_composite", 0.55),
        ("or_score_composite", "score_or_composite", 0.75),
        ("momentum_reversal_interaction", "score_momentum_reversal_interaction", 0.65),
    ]
    for label, score, threshold in definitions:
        result = run_score_backtest(features, targets, score, label, threshold=threshold, tilt_size=DEFAULT_TILT)
        rows.append(result["summary"])
        returns_by_name[label] = result["returns"]

    for model in ("logistic_l2", "ridge_probability"):
        result = run_classifier_backtest(features, targets, classifier_predictions, model)
        rows.append(result["summary"])
        returns_by_name[f"classifier_{model}"] = result["returns"]

    placebo = run_random_placebo(features, targets, reference_label="regime_gated_composite")
    rows.append(placebo["summary"])
    returns_by_name["random_timing_placebo"] = placebo["returns"]

    equity = _equity_table(returns_by_name)
    return pd.DataFrame(rows), equity, returns_by_name


def run_score_backtest(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    score_col: str,
    label: str,
    *,
    threshold: float,
    tilt_size: float,
) -> dict:
    signal = features[["Date", "ticker", score_col, "market_state"]].copy()
    signal["active"] = pd.to_numeric(signal[score_col], errors="coerce") >= threshold
    return _run_active_backtest(signal, targets, label, tilt_size)


def run_classifier_backtest(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    classifier_predictions: pd.DataFrame,
    model: str,
) -> dict:
    pred = classifier_predictions[classifier_predictions["model"] == model].copy()
    train_probs = pred[pd.to_datetime(pred["Date"]) < HOLDOUT_START]["prediction"]
    threshold = float(train_probs.quantile(0.75)) if len(train_probs) else 0.75
    signal = pred[["Date", "ticker", "prediction", "market_state"]].rename(columns={"prediction": "score"}).copy()
    signal["active"] = signal["score"] >= threshold
    return _run_active_backtest(signal, targets, f"classifier_{model}", DEFAULT_TILT)


def run_random_placebo(features: pd.DataFrame, targets: pd.DataFrame, reference_label: str) -> dict:
    ref = features[["Date", "ticker", "score_regime_gated_composite", "market_state"]].copy()
    n_active = int((ref["score_regime_gated_composite"] >= 0.60).sum())
    rng = np.random.default_rng(42)
    signal = ref.rename(columns={"score_regime_gated_composite": "score"}).copy()
    signal["active"] = False
    if n_active > 0:
        eligible = signal.index.to_numpy()
        chosen = rng.choice(eligible, size=min(n_active, len(eligible)), replace=False)
        signal.loc[chosen, "active"] = True
    return _run_active_backtest(signal, targets, "random_timing_placebo", DEFAULT_TILT)


def _run_active_backtest(signal: pd.DataFrame, targets: pd.DataFrame, label: str, tilt_size: float) -> dict:
    prices = load_weekly_prices()[TARGET_TICKERS]
    asset_ret = prices.pct_change().fillna(0.0)
    baseline = load_baseline_returns()["net_return"].reindex(asset_ret.index).fillna(0.0)
    sig = signal.copy()
    sig["Date"] = pd.to_datetime(sig["Date"])
    sig = sig[sig["ticker"].isin(TARGET_TICKERS)]
    active = sig.pivot_table(index="Date", columns="ticker", values="active", aggfunc="max").reindex(asset_ret.index)
    active = active.reindex(columns=TARGET_TICKERS)
    for col in TARGET_TICKERS:
        active[col] = active[col].map(lambda x: bool(x) if pd.notna(x) else False)
    active_count = active.sum(axis=1).replace(0, np.nan)
    exposure = active.astype(float).div(active_count, axis=0).fillna(0.0) * tilt_size
    incremental = (exposure * asset_ret.sub(baseline, axis=0)).sum(axis=1)
    overlay = baseline + incremental

    metric_bundle = metrics.summarize(overlay, baseline)
    baseline_bundle = metrics.summarize(baseline)
    joined_targets = sig.merge(targets, on=["Date", "ticker"], how="left")
    active_targets = joined_targets[joined_targets["active"] == True]  # noqa: E712
    turnover = exposure.diff().abs().sum(axis=1).fillna(0.0)
    active_any = active.any(axis=1)
    activations = ((active.astype(int).diff() == 1).sum(axis=1) > 0).sum()
    years = len(baseline) / 52.0
    summary = {
        "variant": label,
        "tilt_size": tilt_size,
        **{f"overlay_{k}": v for k, v in metric_bundle.items()},
        **{f"baseline_{k}": v for k, v in baseline_bundle.items()},
        "incremental_sharpe": metric_bundle["sharpe"] - baseline_bundle["sharpe"],
        "incremental_cagr": metric_bundle["cagr"] - baseline_bundle["cagr"],
        "turnover": float(turnover.sum()),
        "avg_weekly_turnover": float(turnover.mean()),
        "activations_per_year": float(activations / years) if years > 0 else np.nan,
        "average_activation_length": _average_run_length(active_any),
        "signal_hit_rate": metrics.hit_rate(active_targets["fwd_8w_return"]) if len(active_targets) else np.nan,
        "avg_forward_return_after_signal": float(active_targets["fwd_8w_return"].mean()) if len(active_targets) else np.nan,
        "median_forward_return_after_signal": float(active_targets["fwd_8w_return"].median()) if len(active_targets) else np.nan,
        "worst_signal_outcome": float(active_targets["fwd_8w_return"].min()) if len(active_targets) else np.nan,
        "best_signal_outcome": float(active_targets["fwd_8w_return"].max()) if len(active_targets) else np.nan,
        "strong_recovery_precision": float(active_targets["strong_recovery_label"].mean()) if len(active_targets) else np.nan,
        "n_signal_rows": int(len(active_targets)),
        "sharpe_ex_best_signal_period": _sharpe_excluding_top(incremental, baseline, active_any, top_n=1),
        "sharpe_ex_top3_signal_periods": _sharpe_excluding_top(incremental, baseline, active_any, top_n=3),
        "train_sharpe": metrics.sharpe(overlay[overlay.index < HOLDOUT_START]),
        "holdout_sharpe": metrics.sharpe(overlay[overlay.index >= HOLDOUT_START]),
        "stress_period_diff": _stress_period_diff(overlay, baseline),
    }
    return {"summary": summary, "returns": overlay}


def _sharpe_excluding_top(incremental: pd.Series, baseline: pd.Series, active_any: pd.Series, top_n: int) -> float:
    inc = incremental.copy()
    active_inc = inc[active_any.reindex(inc.index).fillna(False)]
    if active_inc.empty:
        return metrics.sharpe(baseline + inc)
    drop_idx = active_inc.sort_values(ascending=False).index[:top_n]
    inc.loc[drop_idx] = 0.0
    return metrics.sharpe(baseline + inc)


def _average_run_length(active: pd.Series) -> float:
    runs = []
    cur = 0
    for val in active.astype(bool):
        if val:
            cur += 1
        elif cur:
            runs.append(cur)
            cur = 0
    if cur:
        runs.append(cur)
    return float(np.mean(runs)) if runs else 0.0


def _stress_period_diff(overlay: pd.Series, baseline: pd.Series) -> float:
    # Stress-period details are also reported by state in IC files; this keeps
    # backtest output self-contained without reloading state artifacts here.
    diff = overlay - baseline
    return float(diff[diff < 0].mean()) if len(diff[diff < 0]) else 0.0


def _equity_table(returns_by_name: dict[str, pd.Series]) -> pd.DataFrame:
    baseline = load_baseline_returns()["net_return"]
    out = pd.DataFrame(index=baseline.index)
    out.index.name = "Date"
    out["baseline_return"] = baseline.fillna(0.0)
    out["baseline_equity"] = (1.0 + out["baseline_return"]).cumprod()
    for name, ret in returns_by_name.items():
        aligned = ret.reindex(out.index).fillna(0.0)
        out[f"{name}_return"] = aligned
        out[f"{name}_equity"] = (1.0 + aligned).cumprod()
    return out
