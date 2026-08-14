"""ETF re-risking overlay backtests for focused reversal candidates."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metrics
from .feature_engineering import ROOT, TARGET_TICKERS, load_baseline_returns, load_weekly_prices
from .reversal_signals import ALL_CANDIDATES, CANDIDATES

HOLDOUT_START = pd.Timestamp("2024-04-19")
DEFAULT_TILT = 0.05
TILT_SIZES = [0.025, 0.05, 0.075]


def run_backtests(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    classifier_predictions: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.Series]]:
    rows: list[dict] = []
    returns_by_name: dict[str, pd.Series] = {}
    baseline = load_baseline_returns()["net_return"]
    baseline_summary = metrics.summarize(baseline)
    rows.append(
        {
            "candidate": "baseline",
            "variant": "baseline",
            "tilt_size": 0.0,
            "comparison_kind": "baseline",
            "is_default_tilt": True,
            **{f"overlay_{k}": v for k, v in baseline_summary.items()},
            **{f"baseline_{k}": v for k, v in baseline_summary.items()},
            "incremental_sharpe": 0.0,
            "incremental_cagr": 0.0,
        }
    )

    for candidate, meta in CANDIDATES.items():
        signal = features[["Date", "ticker", "market_state", meta["active"]]].rename(columns={meta["active"]: "active"})
        for tilt in TILT_SIZES:
            result = run_active_backtest(signal, targets, candidate, tilt, comparison_kind="rule_signal")
            rows.append(result["summary"])
            returns_by_name[result["summary"]["variant"]] = result["returns"]

    for model in ["classifier_logistic_reversal", "classifier_ridge_reversal"]:
        pred = classifier_predictions[classifier_predictions["model"] == model].copy()
        signal = pred[["Date", "ticker", "market_state", "active"]]
        for tilt in TILT_SIZES:
            result = run_active_backtest(signal, targets, model, tilt, comparison_kind="classifier_signal")
            rows.append(result["summary"])
            returns_by_name[result["summary"]["variant"]] = result["returns"]

    for tilt in TILT_SIZES:
        placebo_signal = random_signal_like(features, "active_focused_reversal_composite", seed=42)
        result = run_active_backtest(placebo_signal, targets, "random_timing_placebo", tilt, comparison_kind="placebo")
        rows.append(result["summary"])
        returns_by_name[result["summary"]["variant"]] = result["returns"]

        always_signal = always_on_signal(features)
        always = run_active_backtest(always_signal, targets, "always_on_spy_qqq_tilt", tilt, comparison_kind="benchmark")
        rows.append(always["summary"])
        returns_by_name[always["summary"]["variant"]] = always["returns"]

    broad = broad_previous_best_reference()
    if broad:
        rows.append(broad)

    equity = equity_table(returns_by_name)
    return pd.DataFrame(rows), equity, returns_by_name


def run_active_backtest(
    signal: pd.DataFrame,
    targets: pd.DataFrame,
    candidate: str,
    tilt_size: float,
    *,
    comparison_kind: str,
) -> dict:
    prices = load_weekly_prices()[TARGET_TICKERS]
    asset_ret = prices.pct_change().fillna(0.0)
    baseline = load_baseline_returns()["net_return"].reindex(asset_ret.index).fillna(0.0)

    sig = signal.copy()
    sig["Date"] = pd.to_datetime(sig["Date"])
    sig = sig[sig["ticker"].isin(TARGET_TICKERS)]
    sig["active"] = pd.to_numeric(sig["active"], errors="coerce").fillna(0) > 0
    active = sig.pivot_table(index="Date", columns="ticker", values="active", aggfunc="max").reindex(asset_ret.index)
    active = active.reindex(columns=TARGET_TICKERS).astype("boolean").fillna(False).astype(bool)
    active_count = active.sum(axis=1).replace(0, np.nan)
    exposure = active.astype(float).div(active_count, axis=0).fillna(0.0) * tilt_size
    incremental = (exposure * asset_ret.sub(baseline, axis=0)).sum(axis=1)
    overlay = baseline + incremental

    overlay_bundle = metrics.summarize(overlay, baseline)
    baseline_bundle = metrics.summarize(baseline)
    joined_targets = sig.merge(targets, on=["Date", "ticker"], how="left")
    active_targets = joined_targets[joined_targets["active"]]
    turnover = exposure.diff().abs().sum(axis=1).fillna(0.0)
    active_any = active.any(axis=1)
    years = max(len(baseline) / 52.0, 1.0)
    activations = int(((active.astype(int).diff() == 1).sum(axis=1) > 0).sum())
    variant = f"{candidate}_tilt_{int(tilt_size * 10000)}bp"

    sub_sharpes = _subperiod_sharpes(overlay)
    summary = {
        "candidate": candidate,
        "variant": variant,
        "tilt_size": tilt_size,
        "comparison_kind": comparison_kind,
        "is_default_tilt": bool(abs(tilt_size - DEFAULT_TILT) < 1e-12),
        **{f"overlay_{k}": v for k, v in overlay_bundle.items()},
        **{f"baseline_{k}": v for k, v in baseline_bundle.items()},
        "incremental_sharpe": overlay_bundle["sharpe"] - baseline_bundle["sharpe"],
        "incremental_cagr": overlay_bundle["cagr"] - baseline_bundle["cagr"],
        "turnover": float(turnover.sum()),
        "avg_weekly_turnover": float(turnover.mean()),
        "activations_per_year": float(activations / years),
        "average_activation_length": average_run_length(active_any),
        "signal_hit_rate": metrics.hit_rate(active_targets["fwd_8w_return"]) if len(active_targets) else np.nan,
        "avg_forward_return_after_signal": _mean(active_targets, "fwd_8w_return"),
        "median_forward_return_after_signal": _median(active_targets, "fwd_8w_return"),
        "worst_signal_outcome": _min(active_targets, "fwd_8w_return"),
        "best_signal_outcome": _max(active_targets, "fwd_8w_return"),
        "strong_bounce_precision": _mean(active_targets, "strong_bounce_label"),
        "failed_bounce_rate": _mean(active_targets, "failed_bounce_label"),
        "crash_continuation_rate": _mean(active_targets, "crash_continuation_label"),
        "n_signal_rows": int(len(active_targets)),
        "sharpe_ex_best_signal_period": sharpe_excluding_top(incremental, baseline, active_any, top_n=1),
        "sharpe_ex_top3_signal_periods": sharpe_excluding_top(incremental, baseline, active_any, top_n=3),
        "train_sharpe": metrics.sharpe(overlay[overlay.index < HOLDOUT_START]),
        "holdout_sharpe": metrics.sharpe(overlay[overlay.index >= HOLDOUT_START]),
        "subperiod_1_sharpe": sub_sharpes[0],
        "subperiod_2_sharpe": sub_sharpes[1],
        "subperiod_3_sharpe": sub_sharpes[2],
        "positive_subperiod_count": int(sum(np.isfinite(x) and x > 0 for x in sub_sharpes)),
        "worst_subperiod_sharpe": float(np.nanmin(sub_sharpes)) if np.isfinite(sub_sharpes).any() else np.nan,
        "stress_period_incremental_return": stress_period_incremental(sig, incremental),
    }
    return {"summary": summary, "returns": overlay, "incremental": incremental, "active_any": active_any}


def random_signal_like(features: pd.DataFrame, active_col: str, seed: int) -> pd.DataFrame:
    base = features[["Date", "ticker", "market_state", active_col]].rename(columns={active_col: "active"}).copy()
    n_active = int(pd.to_numeric(base["active"], errors="coerce").fillna(0).sum())
    base["active"] = False
    rng = np.random.default_rng(seed)
    if n_active > 0:
        eligible = base.index.to_numpy()
        chosen = rng.choice(eligible, size=min(n_active, len(eligible)), replace=False)
        base.loc[chosen, "active"] = True
    return base


def always_on_signal(features: pd.DataFrame) -> pd.DataFrame:
    signal = features[["Date", "ticker", "market_state"]].copy()
    signal["active"] = True
    return signal


def broad_previous_best_reference() -> dict:
    path = ROOT / "data" / "research" / "recovery_prediction" / "recovery_combination_backtests.csv"
    if not path.exists():
        return {}
    broad = pd.read_csv(path)
    if broad.empty:
        return {}
    if "regime_gated_composite" in set(broad["variant"].astype(str)):
        row = broad[broad["variant"] == "regime_gated_composite"].iloc[0]
    else:
        row = broad.sort_values("overlay_sharpe", ascending=False).iloc[0]
    out = {
        "candidate": "broad_previous_best_reference",
        "variant": "broad_previous_best_reference",
        "tilt_size": float(row.get("tilt_size", DEFAULT_TILT)),
        "comparison_kind": "broad_reference_only",
        "is_default_tilt": True,
    }
    for col, val in row.items():
        if col in {"variant", "tilt_size"}:
            continue
        out[col] = val
    out["source_variant"] = row.get("variant", "")
    return out


def equity_table(returns_by_name: dict[str, pd.Series]) -> pd.DataFrame:
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


def sharpe_excluding_top(incremental: pd.Series, baseline: pd.Series, active_any: pd.Series, top_n: int) -> float:
    inc = incremental.copy()
    active_inc = inc[active_any.reindex(inc.index).fillna(False)]
    if active_inc.empty:
        return metrics.sharpe(baseline + inc)
    drop_idx = active_inc.sort_values(ascending=False).index[:top_n]
    inc.loc[drop_idx] = 0.0
    return metrics.sharpe(baseline + inc)


def average_run_length(active: pd.Series) -> float:
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


def stress_period_incremental(sig: pd.DataFrame, incremental: pd.Series) -> float:
    state = sig.drop_duplicates("Date").set_index("Date")["market_state"].reindex(incremental.index).fillna("")
    stress = state.astype(str).str.lower().str.contains("panic|stress|risk_off", regex=True, na=False)
    return float(incremental[stress].mean()) if stress.sum() else 0.0


def _subperiod_sharpes(overlay: pd.Series) -> list[float]:
    n = len(overlay)
    if n < 3:
        return [np.nan, np.nan, np.nan]
    parts = np.array_split(np.arange(n), 3)
    return [metrics.sharpe(overlay.iloc[idx]) for idx in parts]


def _mean(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").mean()) if len(df) and col in df.columns else np.nan


def _median(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").median()) if len(df) and col in df.columns else np.nan


def _min(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").min()) if len(df) and col in df.columns else np.nan


def _max(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").max()) if len(df) and col in df.columns else np.nan
