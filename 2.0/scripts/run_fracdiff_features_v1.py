#!/usr/bin/env python3
"""A11: do the same signals work better on fractionally differenced inputs?

Step 265 established that order-0.3 fractional differencing is stationary in
99.7% of issuers while retaining 0.856 correlation with the price level, against
0.050 for the plain returns every feature in this project is built from.

This is not a new signal. It is the same momentum signal on a better-conditioned
input, and it is tested that way: identical construction, identical windows, one
changed input. The honest expectation is a modest improvement in an existing
information coefficient rather than a new source of edge.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
ORDER = 0.3
WIDTH = 120
SKIP = 1


def weights(order: float, size: int, threshold: float = 1e-5) -> np.ndarray:
    out = [1.0]
    for k in range(1, size):
        value = -out[-1] * (order - k + 1) / k
        if abs(value) < threshold:
            break
        out.append(value)
    return np.array(out[::-1])


def frac_diff_frame(level: pd.DataFrame, order: float) -> pd.DataFrame:
    w = weights(order, WIDTH)
    span = len(w)
    values = level.to_numpy(dtype=float)
    out = np.full_like(values, np.nan)
    for i in range(span - 1, values.shape[0]):
        window = values[i - span + 1:i + 1]
        mask = ~np.isnan(window).any(axis=0)
        out[i, mask] = w @ window[:, mask]
    return pd.DataFrame(out, index=level.index, columns=level.columns)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/fracdiff_features_v1")
    args = parser.parse_args()

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    coverage = prices.notna().sum().sort_values(ascending=False)
    prices = prices[list(coverage[coverage > 400].index)]

    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    level = np.log(prices.where(prices > 0))
    fractional = frac_diff_frame(level, ORDER)

    rows = []
    for lookback in (4, 13, 26, 52):
        plain = ((1.0 + returns.fillna(0.0)).rolling(lookback).apply(np.prod, raw=True) - 1.0).shift(SKIP)
        # the same lookback on the fractionally differenced series
        fdiff = fractional.rolling(lookback).sum().shift(SKIP)
        for horizon in (4, 13):
            compounded = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
            valid = returns.notna().rolling(horizon).sum() >= horizon
            forward = compounded.where(valid).shift(-horizon)
            for label, signal in (("plain_returns", plain), ("fractional_0.3", fdiff)):
                ics = []
                for week in signal.index[::horizon]:
                    if week not in forward.index:
                        continue
                    pair = pd.DataFrame({"s": signal.loc[week], "f": forward.loc[week]}).dropna()
                    if len(pair) < 200:
                        continue
                    value = pair.s.rank().corr(pair.f.rank())
                    if np.isfinite(value):
                        ics.append(float(value))
                if len(ics) < 20:
                    continue
                a = np.array(ics)
                rows.append({"input": label, "lookback": lookback, "horizon": horizon,
                             "observations": len(a), "mean_ic": float(a.mean()),
                             "t_stat": float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))),
                             "p_value": float(stats.ttest_1samp(a, 0.0).pvalue)})
    table = pd.DataFrame(rows)

    comparison = []
    for lookback in table.lookback.unique():
        for horizon in table.horizon.unique():
            a = table[(table.input == "plain_returns") & (table.lookback == lookback) & (table.horizon == horizon)]
            b = table[(table.input == "fractional_0.3") & (table.lookback == lookback) & (table.horizon == horizon)]
            if a.empty or b.empty:
                continue
            comparison.append({"lookback": int(lookback), "horizon": int(horizon),
                               "plain_ic": float(a.iloc[0].mean_ic), "plain_t": float(a.iloc[0].t_stat),
                               "fracdiff_ic": float(b.iloc[0].mean_ic), "fracdiff_t": float(b.iloc[0].t_stat),
                               "abs_ic_improved": bool(abs(b.iloc[0].mean_ic) > abs(a.iloc[0].mean_ic)),
                               "abs_t_improved": bool(abs(b.iloc[0].t_stat) > abs(a.iloc[0].t_stat))})
    compare = pd.DataFrame(comparison)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "information_coefficients.csv", index=False)
    compare.to_csv(out / "comparison.csv", index=False)

    improved = int(compare.abs_t_improved.sum()) if not compare.empty else 0
    verdict = (f"the fractionally differenced input gives a larger absolute t-statistic in "
               f"{improved} of {len(compare)} matched configurations. "
               + ("It is the better input and every price feature here should be rebuilt on it."
                  if improved > len(compare) / 2 else
                  "It is not the better input on this panel, so the memory it preserves is not the "
                  "memory these signals needed, and Step 265's result stands as a property of the "
                  "series rather than a usable improvement."))

    result = {"experiment": "fracdiff_features_v1", "queue_item": "A11",
              "order": ORDER, "issuers": int(prices.shape[1]),
              "matched_configurations": len(compare), "configurations_improved": improved,
              "table": rows, "comparison": comparison, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(compare.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
