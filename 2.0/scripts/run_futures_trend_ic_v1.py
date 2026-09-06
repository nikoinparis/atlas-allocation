#!/usr/bin/env python3
"""Measure whether futures trend has any information coefficient, before building on it.

Step 247 found the breadth: 13.2 effective assets and a projected 155 bets a year,
clearing the 91 that an information ratio of 0.25 requires.  Breadth is capacity.
`IR = IC x sqrt(BR)` has two terms and the other one has never been measured here
for this asset class, so if IC is zero then 155 bets a year buys nothing at all.

Two quantities, measured separately because they are not the same thing:

  cross-sectional IC  rank correlation across assets between the trend signal and
                      the next-horizon return.  The Grinold and Kahn quantity, and
                      what the equity book's +0.026 was.
  time-series IC      per-asset correlation between an asset's own trend and its
                      own next return, pooled.  What a CTA actually trades.  A
                      cross-sectional number says nothing about it.

Everything is reported under four contamination treatments side by side, because
Step 247 measured these as unadjusted front-month series and a single treatment
would be a choice about the answer.

No strategy is built here and none is proposed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/futures_trend_ic_registry_v1.json"


def weekly_returns(prices: pd.DataFrame) -> pd.DataFrame:
    weekly = prices.resample("W-FRI").last()
    return (weekly / weekly.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)


def treatments(returns: pd.DataFrame) -> dict[str, tuple[pd.DataFrame, str]]:
    without_yen = [c for c in returns.columns if c != "6J=F"]
    clipped = returns[without_yen].where(returns[without_yen].abs() <= 0.25)
    return {
        "raw": (returns, "pearson"),
        "minus_6J": (returns[without_yen], "pearson"),
        "minus_6J_and_extremes": (clipped, "pearson"),
        "spearman_raw": (returns, "spearman"),
    }


def trend_signal(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Compound return over the lookback, known at the close of week t."""
    return (1.0 + returns.fillna(0.0)).rolling(lookback).apply(np.prod, raw=True) - 1.0


def forward_return(returns: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Return over the horizon strictly after week t. No overlap with the signal."""
    forward = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    return forward.shift(-horizon)


def cross_sectional_ic(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int,
                       method: str) -> np.ndarray:
    """One IC per non-overlapping week, so the series is not autocorrelated by construction."""
    values = []
    for week in signal.index[::horizon]:
        if week not in forward.index:
            continue
        pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week]}).dropna()
        if len(pair) < 10:
            continue
        if method == "spearman":
            correlation = pair.s.rank().corr(pair.f.rank())
        else:
            correlation = pair.s.rank().corr(pair.f.rank())  # IC is a rank correlation either way
        if np.isfinite(correlation):
            values.append(float(correlation))
    return np.array(values)


def time_series_ic(signal: pd.DataFrame, forward: pd.DataFrame, horizon: int) -> dict[str, object]:
    """Per asset, does its own trend predict its own next return? Pooled across assets."""
    per_asset = {}
    for column in signal.columns:
        pair = pd.DataFrame({"s": signal[column], "f": forward[column]}).dropna().iloc[::horizon]
        if len(pair) < 40:
            continue
        correlation = pair.s.rank().corr(pair.f.rank())
        if np.isfinite(correlation):
            per_asset[column] = float(correlation)
    if not per_asset:
        return {"assets": 0}
    values = np.array(list(per_asset.values()))
    return {
        "assets": len(values),
        "mean_ic": float(values.mean()),
        "median_ic": float(np.median(values)),
        "share_positive": float((values > 0).mean()),
        "t_stat_across_assets": float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values)))),
        "p_value_across_assets": float(stats.ttest_1samp(values, 0.0).pvalue),
        "best": max(per_asset, key=per_asset.get),
        "worst": min(per_asset, key=per_asset.get),
    }


def block_bootstrap(values: np.ndarray, draws: int, block: int, seed: int) -> dict[str, float]:
    if len(values) < block * 2:
        block = max(2, len(values) // 4)
    rng = np.random.default_rng(seed)
    blocks = max(1, len(values) // block)
    means = []
    for _ in range(draws):
        starts = rng.integers(0, max(1, len(values) - block), size=blocks)
        means.append(float(np.mean([values[s:s + block].mean() for s in starts])))
    means = np.array(means)
    return {
        "probability_positive": float((means > 0).mean()),
        "two_sided_p_value": float(2 * min((means > 0).mean(), (means <= 0).mean())),
        "p05": float(np.quantile(means, 0.05)),
        "p95": float(np.quantile(means, 0.95)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/futures_trend_ic_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    prices = pd.read_csv(ROOT / registry["data"], index_col=0, parse_dates=True)
    prices = prices.apply(pd.to_numeric, errors="coerce")
    returns = weekly_returns(prices).loc["2005-01-01":]

    boot = registry["bootstrap"]
    threshold = float(registry["bonferroni_threshold"])
    rows = []
    for label, (frame, method) in treatments(returns).items():
        for lookback in registry["declared_configurations"]["trend_lookback_weeks"]:
            signal = trend_signal(frame, lookback)
            for horizon in registry["declared_configurations"]["forward_horizon_weeks"]:
                forward = forward_return(frame, horizon)
                cs = cross_sectional_ic(signal, forward, horizon, method)
                ts = time_series_ic(signal, forward, horizon)
                if len(cs) < 20:
                    continue
                stats_cs = block_bootstrap(cs, boot["draws"], boot["block_weeks"], boot["seed"])
                rows.append({
                    "treatment": label,
                    "trend_lookback_weeks": lookback,
                    "forward_horizon_weeks": horizon,
                    "cs_observations": len(cs),
                    "cs_mean_ic": float(cs.mean()),
                    "cs_ic_std": float(cs.std(ddof=1)),
                    "cs_t_stat": float(cs.mean() / (cs.std(ddof=1) / np.sqrt(len(cs)))),
                    "cs_bootstrap_p": stats_cs["two_sided_p_value"],
                    "cs_clears_bonferroni": bool(stats_cs["two_sided_p_value"] < threshold),
                    "ts_assets": ts.get("assets"),
                    "ts_mean_ic": ts.get("mean_ic"),
                    "ts_share_positive": ts.get("share_positive"),
                    "ts_t_stat": ts.get("t_stat_across_assets"),
                    "ts_p_value": ts.get("p_value_across_assets"),
                    "ts_clears_bonferroni": bool((ts.get("p_value_across_assets") or 1.0) < threshold),
                })
    frame_out = pd.DataFrame(rows)

    # Placebo: shuffle the signal across assets each week and confirm the estimator returns zero.
    rng = np.random.default_rng(boot["seed"])
    base = returns[[c for c in returns.columns if c != "6J=F"]]
    base = base.where(base.abs() <= 0.25)
    signal = trend_signal(base, 12)
    forward = forward_return(base, 4)
    placebo = []
    for _ in range(200):
        shuffled = signal.apply(lambda row: pd.Series(rng.permutation(row.to_numpy()), index=row.index), axis=1)
        ic = cross_sectional_ic(shuffled, forward, 4, "pearson")
        if len(ic):
            placebo.append(float(ic.mean()))
    placebo = np.array(placebo)

    primary = frame_out[frame_out.treatment == "minus_6J_and_extremes"]
    signs = frame_out.groupby(["trend_lookback_weeks", "forward_horizon_weeks"]).cs_mean_ic.apply(
        lambda s: len(set(np.sign(s))) == 1)
    verdict_parts = []
    # The first version of this branch keyed on significance alone and printed
    # "the expected shape for trend following" for a set of rows whose ICs were
    # every one of them negative. A clearing row with a negative IC is evidence
    # against the signal, not for it, and a verdict that cannot tell the two
    # apart is worse than no verdict. Sign is checked first now.
    cs_clear = frame_out[frame_out.cs_clears_bonferroni]
    ts_clear = frame_out[frame_out.ts_clears_bonferroni]
    cs_positive = cs_clear[cs_clear.cs_mean_ic > 0]
    ts_positive = ts_clear[ts_clear.ts_mean_ic > 0]
    if cs_clear.empty and ts_clear.empty:
        verdict = ("no configuration clears Bonferroni in either definition: futures trend has no "
                   "demonstrated IC on this data, and Step 247's breadth is capacity with nothing to put in it")
    elif cs_positive.empty and ts_positive.empty:
        verdict = (f"every one of the {len(cs_clear) + len(ts_clear)} clearing rows has a NEGATIVE "
                   "information coefficient. Trend is not predictive on this data; short-horizon trend is "
                   "significantly ANTI-predictive. That is either mean reversion or roll contamination, and "
                   "an unadjusted front-month series cannot tell the two apart, because rolling through "
                   "contango manufactures exactly this negative short-horizon autocorrelation")
    elif ts_positive.empty:
        verdict = "cross-sectional IC clears positively somewhere; time-series does not. See the table."
    elif cs_positive.empty:
        verdict = ("time-series IC clears POSITIVELY and cross-sectional does not, the expected shape for "
                   "trend following: any strategy must be time-series and Step 247's breadth projection "
                   "must be recomputed for a time-series design")
    else:
        verdict = "at least one configuration clears positively in both definitions; see the table"
    verdict_parts.append(
        f"clearing rows: cross-sectional {len(cs_clear)} ({len(cs_positive)} positive), "
        f"time-series {len(ts_clear)} ({len(ts_positive)} positive)")
    if not signs.all():
        verdict_parts.append("WARNING: the four contamination treatments disagree in sign for at least "
                             "one configuration, which the registry declared makes the measurement unusable there")

    result = {
        "experiment": "futures_trend_ic_v1",
        "declared_trials": registry["declared_configurations"]["total_trials"],
        "bonferroni_threshold": threshold,
        "builds_no_strategy": True,
        "weeks": int(len(returns)),
        "assets": int(returns.shape[1]),
        "comparison_baseline": registry["comparison_baseline"],
        "placebo": {
            "draws": int(len(placebo)),
            "mean": float(placebo.mean()) if len(placebo) else None,
            "p05": float(np.quantile(placebo, 0.05)) if len(placebo) else None,
            "p95": float(np.quantile(placebo, 0.95)) if len(placebo) else None,
        },
        "configurations_clearing_cross_sectional": int(frame_out.cs_clears_bonferroni.sum()),
        "configurations_clearing_time_series": int(frame_out.ts_clears_bonferroni.sum()),
        "treatments_agree_in_sign_everywhere": bool(signs.all()),
        "verdict": verdict,
        "clearing_rows_positive_cross_sectional": int((frame_out[frame_out.cs_clears_bonferroni].cs_mean_ic > 0).sum()),
        "clearing_rows_positive_time_series": int((frame_out[frame_out.ts_clears_bonferroni].ts_mean_ic > 0).sum()),
        "warnings": verdict_parts,
        "caveat": registry["interpretation_fixed_in_advance"]["always"],
        "live_trading_enabled": False,
        "strategy_promotion_authorized": False,
    }
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    frame_out.to_csv(out / "configurations.csv", index=False)
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

    show = primary[["trend_lookback_weeks", "forward_horizon_weeks", "cs_mean_ic", "cs_t_stat",
                    "cs_bootstrap_p", "ts_mean_ic", "ts_share_positive", "ts_t_stat", "ts_p_value"]]
    print("PRIMARY TREATMENT: minus 6J, weekly moves above 25% removed\n")
    print(show.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nplacebo mean IC over {len(placebo)} shuffles: {placebo.mean():+.5f} "
          f"[{np.quantile(placebo,0.05):+.5f}, {np.quantile(placebo,0.95):+.5f}]")
    print(f"clearing Bonferroni {threshold}: cross-sectional {result['configurations_clearing_cross_sectional']}, "
          f"time-series {result['configurations_clearing_time_series']} of {len(frame_out)} rows")
    print(f"treatments agree in sign everywhere: {result['treatments_agree_in_sign_everywhere']}")
    print(f"\nVERDICT: {verdict}")
    for warning in verdict_parts:
        print(f"  {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
