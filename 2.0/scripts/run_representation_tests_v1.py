#!/usr/bin/env python3
"""A8 and A9: does changing the input or the label representation help?

Both were named in CLAUDE.md section 3 and neither had been attempted in 272
steps. They are grouped because they ask the same question from two sides --
whether this project has been feeding its models the wrong representation rather
than the wrong data.

A8, fractional differentiation. Every price signal here differences returns fully,
which makes the series stationary and destroys its memory. Fractional
differencing at order d keeps as much memory as stationarity allows. The test is
not whether it predicts, it is whether the fractionally differenced series is
(a) stationary and (b) more correlated with the original level series than plain
returns are. If it is not both, it cannot help anything downstream.

A9, triple-barrier labelling. Everything here predicts "the return over N weeks".
Triple barrier predicts "does it hit +x before -y within a horizon", which is a
different and often more learnable target. Meta-labelling failed its precondition
in Step 201, and that may be because it was applied without this underneath.

Neither builds a strategy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
PANEL = ROOT / "data/sec_broad_research_panel_v4_clean"


def frac_diff_weights(order: float, size: int, threshold: float = 1e-5) -> np.ndarray:
    weights = [1.0]
    for k in range(1, size):
        value = -weights[-1] * (order - k + 1) / k
        if abs(value) < threshold:
            break
        weights.append(value)
    return np.array(weights[::-1])


def frac_diff(series: pd.Series, order: float, width: int = 120) -> pd.Series:
    weights = frac_diff_weights(order, width)
    values = series.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    span = len(weights)
    for i in range(span - 1, len(values)):
        window = values[i - span + 1:i + 1]
        if np.isnan(window).any():
            continue
        out[i] = float(weights @ window)
    return pd.Series(out, index=series.index)


def adf_stat(values: np.ndarray) -> float:
    """Augmented Dickey-Fuller statistic, one lag, computed directly."""
    clean = values[np.isfinite(values)]
    if len(clean) < 60:
        return float("nan")
    y = clean[1:]
    lag = clean[:-1]
    diff = y - lag
    x = np.column_stack([np.ones(len(lag)), lag])
    beta, residuals, *_ = np.linalg.lstsq(x, diff, rcond=None)
    fitted = x @ beta
    error = diff - fitted
    sigma2 = float(error @ error) / (len(diff) - 2)
    covariance = sigma2 * np.linalg.inv(x.T @ x)
    return float(beta[1] / np.sqrt(covariance[1, 1]))


def triple_barrier(returns: pd.Series, upper: float, lower: float, horizon: int) -> pd.Series:
    """+1 if the upper barrier is touched first, -1 if the lower, 0 if neither."""
    values = returns.to_numpy(dtype=float)
    labels = np.full(len(values), np.nan)
    for i in range(len(values) - horizon):
        path = np.cumprod(1.0 + np.nan_to_num(values[i + 1:i + 1 + horizon])) - 1.0
        hit_up = np.argmax(path >= upper) if (path >= upper).any() else None
        hit_dn = np.argmax(path <= -lower) if (path <= -lower).any() else None
        if hit_up is None and hit_dn is None:
            labels[i] = 0.0
        elif hit_dn is None or (hit_up is not None and hit_up < hit_dn):
            labels[i] = 1.0
        else:
            labels[i] = -1.0
    return pd.Series(labels, index=returns.index)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/representation_tests_v1")
    parser.add_argument("--sample-issuers", type=int, default=300)
    args = parser.parse_args()

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    coverage = prices.notna().sum().sort_values(ascending=False)
    sample = list(coverage.head(args.sample_issuers).index)

    # ---- A8 ----
    rows = []
    for order in (0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0):
        adf, memory, usable = [], [], 0
        for name in sample:
            level = np.log(prices[name].where(prices[name] > 0)).dropna()
            if len(level) < 300:
                continue
            differenced = frac_diff(level, order).dropna()
            if len(differenced) < 200:
                continue
            statistic = adf_stat(differenced.to_numpy())
            joined = pd.concat([differenced.rename("d"), level.rename("l")], axis=1).dropna()
            if len(joined) < 200 or not np.isfinite(statistic):
                continue
            adf.append(statistic)
            memory.append(float(joined.d.corr(joined.l)))
            usable += 1
        if usable < 30:
            continue
        rows.append({"order": order, "issuers": usable,
                     "mean_adf": float(np.mean(adf)),
                     "share_stationary_at_5pct": float(np.mean(np.array(adf) < -2.86)),
                     "mean_memory_correlation_with_level": float(np.mean(memory))})
    a8 = pd.DataFrame(rows)

    # ---- A9 ----
    panel = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    target = "future_sector_relative_return"
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    # the panel carries tz-aware decisions and the price index is tz-naive
    returns.index = pd.to_datetime(returns.index, utc=True)

    barrier_rows = []
    for upper, lower, horizon in ((0.10, 0.10, 13), (0.15, 0.15, 13), (0.10, 0.05, 13), (0.20, 0.20, 26)):
        labels = {name: triple_barrier(returns[name], upper, lower, horizon) for name in sample[:150]}
        frame = pd.DataFrame(labels)
        merged = []
        for decision, block in panel[panel.cik10.isin(frame.columns)].groupby("decision_at"):
            # panel decisions are quarter starts; the price index is Fridays, so an
            # exact match never fires. Map to the first week strictly after, which is
            # also the causal choice. The first run returned an empty table from this.
            later = frame.index[frame.index > decision]
            if not len(later):
                continue
            decision = later[0]
            names = [c for c in block.cik10 if c in frame.columns]
            pair = pd.DataFrame({
                "signal": block.set_index("cik10").residual_momentum.reindex(names).to_numpy(),
                "barrier": frame.loc[decision, names].to_numpy(),
                "plain": block.set_index("cik10")[target].reindex(names).to_numpy()}).dropna()
            if len(pair) < 40:
                continue
            merged.append({
                "ic_vs_barrier": float(pair.signal.rank().corr(pair.barrier.rank())),
                "ic_vs_plain_return": float(pair.signal.rank().corr(pair.plain.rank())),
                "share_zero_label": float((pair.barrier == 0).mean())})
        if len(merged) < 6:
            continue
        block = pd.DataFrame(merged)
        barrier_rows.append({
            "upper": upper, "lower": lower, "horizon_weeks": horizon, "decisions": len(block),
            "mean_ic_vs_barrier": float(block.ic_vs_barrier.mean()),
            "t_vs_barrier": float(block.ic_vs_barrier.mean() / (block.ic_vs_barrier.std(ddof=1) / np.sqrt(len(block)))),
            "mean_ic_vs_plain_return": float(block.ic_vs_plain_return.mean()),
            "t_vs_plain": float(block.ic_vs_plain_return.mean() / (block.ic_vs_plain_return.std(ddof=1) / np.sqrt(len(block)))),
            "share_no_barrier_touched": float(block.share_zero_label.mean())})
    a9 = pd.DataFrame(barrier_rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    a8.to_csv(out / "fractional_differentiation.csv", index=False)
    a9.to_csv(out / "triple_barrier.csv", index=False)

    best = a8[a8.share_stationary_at_5pct >= 0.9].sort_values("order").head(1) if not a8.empty else a8
    a8_verdict = ("no order tested is stationary in 90% of issuers" if best.empty else
                  f"order {best.iloc[0].order} is the lowest that is stationary in 90% of issuers, "
                  f"and it retains {best.iloc[0].mean_memory_correlation_with_level:.3f} correlation "
                  f"with the price level against {a8[a8.order==1.0].mean_memory_correlation_with_level.iloc[0]:.3f} "
                  f"for plain returns" if not a8[a8.order == 1.0].empty else "")
    improved = a9[a9.mean_ic_vs_barrier.abs() > a9.mean_ic_vs_plain_return.abs()] if not a9.empty else a9
    a9_verdict = ("triple-barrier labels are not measurable on this sample" if a9.empty else
                  f"{len(improved)} of {len(a9)} barrier configurations give a larger absolute IC than "
                  f"the plain forward return does")

    result = {"experiment": "representation_tests_v1", "queue_items": ["A8", "A9"],
              "builds_no_strategy": True,
              "fractional_differentiation": a8.to_dict("records"), "a8_verdict": a8_verdict,
              "triple_barrier": a9.to_dict("records"), "a9_verdict": a9_verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print("A8 FRACTIONAL DIFFERENTIATION")
    print(a8.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"  -> {a8_verdict}\n")
    print("A9 TRIPLE BARRIER")
    print(a9.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"  -> {a9_verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
