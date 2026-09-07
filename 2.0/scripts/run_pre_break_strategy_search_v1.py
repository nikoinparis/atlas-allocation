#!/usr/bin/env python3
"""A12: did anything this project built work BEFORE April 2025?

The owner's second hypothesis, and the prior question A10 skipped. If our four
strategies were market-average until April 2025 and excellent after, is there a
strategy among the ones already built and rejected that was excellent before it?

The honest test is not "find the best pre-break path" -- with 723 saved paths the
best will look wonderful by chance. It is the **rank correlation between pre-break
and post-break performance across all of them**, which is one number over the whole
set and needs no multiple-testing correction:

  strongly negative  different things worked in each period. Two states exist.
  near zero          performance in one period says nothing about the other.
  positive           the same things worked throughout, and April 2025 was a
                     change in degree rather than in kind. No regime story.

Anything found here is a hypothesis to test forward, never a strategy to adopt:
these paths were rejected for reasons, and this search is explicitly the best of
many.
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
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
MIN_PRE, MIN_POST = 60, 40


def load_paths() -> dict[str, pd.Series]:
    out = {}
    for path in sorted(ROOT.glob("evidence/**/*.csv")):
        name = path.name.lower()
        if not any(k in name for k in ("path", "candidate")):
            continue
        if path.stat().st_size > 20_000_000:
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty or len(frame.columns) < 2:
            continue
        column = frame.columns[0]
        try:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
        except Exception:
            continue
        frame = frame.dropna(subset=[column]).set_index(column).sort_index()
        numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
        if not numeric:
            continue
        series = frame[numeric[0]].dropna()
        # a return series, not a weight or price series
        if len(series) < MIN_PRE + MIN_POST or series.abs().median() > 0.2 or series.abs().max() > 2.0:
            continue
        key = str(path.relative_to(ROOT))
        out[key] = series
    return out


def annualised(series: pd.Series) -> tuple[float, float]:
    if len(series) < 10:
        return float("nan"), float("nan")
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return float(series.mean() * 52), (float(series.mean() * 52 / volatility) if volatility else float("nan"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/pre_break_strategy_search_v1")
    args = parser.parse_args()

    paths = load_paths()
    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    market = returns.where(returns.abs() <= 1.0).mean(axis=1, skipna=True)

    rows = []
    for key, series in paths.items():
        pre, post = series[series.index < BREAK], series[series.index >= BREAK]
        if len(pre) < MIN_PRE or len(post) < MIN_POST:
            continue
        market_pre = market[(market.index >= pre.index.min()) & (market.index < BREAK)]
        pre_return, pre_sharpe = annualised(pre)
        post_return, post_sharpe = annualised(post)
        rows.append({"path": key, "pre_weeks": len(pre), "post_weeks": len(post),
                     "pre_return": pre_return, "pre_sharpe": pre_sharpe,
                     "post_return": post_return, "post_sharpe": post_sharpe,
                     "pre_excess_over_market": pre_return - float(market_pre.mean() * 52)})
    table = pd.DataFrame(rows).dropna(subset=["pre_sharpe", "post_sharpe"])

    correlation = float(table.pre_sharpe.rank().corr(table.post_sharpe.rank()))
    n = len(table)
    t_stat = correlation * np.sqrt((n - 2) / max(1e-9, 1 - correlation ** 2)) if n > 3 else float("nan")
    p_value = float(2 * (1 - stats.t.cdf(abs(t_stat), n - 2))) if n > 3 else float("nan")

    best_pre = table.nlargest(15, "pre_sharpe")
    market_pre_return = float(market[market.index < BREAK].mean() * 52)
    market_post_return = float(market[market.index >= BREAK].mean() * 52)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "paths_before_and_after.csv", index=False)

    if n < 50:
        verdict = "too few comparable paths to answer"
    elif p_value < 0.05 and correlation < -0.2:
        verdict = (f"pre-break and post-break performance are NEGATIVELY related across {n} saved "
                   f"paths (rank correlation {correlation:+.3f}, p={p_value:.4f}). Different things "
                   f"worked in each period, which is real support for the owner's two-state story.")
    elif p_value < 0.05 and correlation > 0.2:
        verdict = (f"pre-break and post-break performance are POSITIVELY related across {n} paths "
                   f"(rank correlation {correlation:+.3f}, p={p_value:.4f}). The same things worked "
                   f"throughout and April 2025 was a change in degree, not in kind. No regime story.")
    else:
        verdict = (f"pre-break and post-break performance are essentially unrelated across {n} paths "
                   f"(rank correlation {correlation:+.3f}, p={p_value:.4f}). Doing well before says "
                   f"nothing about doing well after, which supports neither a clean two-state story "
                   f"nor a single-regime one -- it is what you would see if both periods were mostly "
                   f"noise around different means.")

    result = {"experiment": "pre_break_strategy_search_v1", "queue_item": "A12",
              "paths_compared": n, "break_date": str(BREAK.date()),
              "rank_correlation_pre_vs_post": correlation, "t_stat": float(t_stat), "p_value": p_value,
              "market_pre_break_annualised": market_pre_return,
              "market_post_break_annualised": market_post_return,
              "share_beating_market_pre_break": float((table.pre_excess_over_market > 0).mean()),
              "best_pre_break": best_pre[["path", "pre_return", "pre_sharpe", "post_return", "post_sharpe"]].to_dict("records"),
              "multiple_testing_note": f"{n} paths searched; the best pre-break performer is the best of {n} and is a hypothesis, never a strategy",
              "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"{n} saved paths with at least {MIN_PRE} pre-break and {MIN_POST} post-break weeks")
    print(f"market: {market_pre_return*100:.2f}% before the break, {market_post_return*100:.2f}% after")
    print(f"share of paths beating the market before the break: {result['share_beating_market_pre_break']:.1%}\n")
    print("BEST FIFTEEN BEFORE THE BREAK, and what they did after:")
    print(best_pre[["path", "pre_return", "pre_sharpe", "post_return", "post_sharpe"]].to_string(
        index=False, float_format=lambda v: f"{v:.3f}", max_colwidth=58))
    print(f"\nrank correlation between pre-break and post-break Sharpe: {correlation:+.4f} (p={p_value:.4f})")
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
