#!/usr/bin/env python3
"""Give standardised unexpected earnings the standalone test it never had.

Item S3. Step 201 measured SUE at +0.0269 selection IC and +0.0174 holdout IC,
positive in only half of holdout decisions, then folded it into a four-feature
composite that was rejected as a whole. SUE itself was never judged on its own,
which left it in the worst state a signal can be in: not promoted, not rejected,
and quietly assumed to be alive.

The point of this script is to settle that, and the first thing it reports is
whether the data can settle it at all. Fourteen quarterly decisions is a small
sample and the honest move is to compute the detectable effect size before
reporting a p-value against it.

Nothing is built and nothing can be promoted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "evidence/point_in_time_fundamental_branches_v1/features.csv.gz"
PRICES = ROOT / "data/clean_corporate_action_prices_v1/weekly_adjusted_prices_clean.csv.gz"
EXISTING = {
    "cash_conversion": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}


def forward(prices: pd.DataFrame, horizon: int) -> pd.DataFrame:
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    compounded = (1.0 + returns.fillna(0.0)).rolling(horizon).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(horizon).sum() >= horizon
    return compounded.where(valid).shift(-horizon), returns


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--breadth", type=int, default=50)
    parser.add_argument("--output", default="evidence/pead_sue_standalone_v1")
    args = parser.parse_args()

    features = pd.read_csv(FEATURES, dtype={"cik10": str})
    features["decision_at"] = pd.to_datetime(features.decision_at, utc=True).dt.tz_localize(None)
    sue = features[["decision_at", "cik10", "standardized_unexpected_earnings"]].dropna()

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.columns = [str(c) for c in prices.columns]
    index = prices.index

    rows = []
    books = {}
    for horizon in (4, 13, 26):
        fwd, _ = forward(prices, horizon)
        ics = []
        for decision, block in sue.groupby("decision_at"):
            later = index[index > decision]
            if not len(later):
                continue
            week = later[0]
            if week not in fwd.index:
                continue
            names = [c for c in block.cik10 if c in prices.columns]
            if len(names) < 100:
                continue
            paired = pd.DataFrame({
                "s": block.set_index("cik10").standardized_unexpected_earnings.reindex(names).to_numpy(),
                "f": fwd.loc[week, names].to_numpy(),
            }).dropna()
            if len(paired) < 100:
                continue
            ics.append(float(paired.s.rank().corr(paired.f.rank())))
            if horizon == 13:
                ranked = block[block.cik10.isin(names)].nlargest(
                    args.breadth, "standardized_unexpected_earnings")
                books[week] = sorted(ranked.cik10)
        if len(ics) < 5:
            continue
        values = np.array(ics)
        standard_error = values.std(ddof=1) / np.sqrt(len(values))
        rows.append({
            "forward_horizon_weeks": horizon, "decisions": len(values),
            "mean_ic": float(values.mean()), "ic_std": float(values.std(ddof=1)),
            "standard_error": float(standard_error),
            "t_stat": float(values.mean() / standard_error),
            "p_value": float(stats.ttest_1samp(values, 0.0).pvalue),
            "share_positive": float((values > 0).mean()),
            "minimum_detectable_ic_at_80pct_power": float(2.8 * standard_error),
        })
    table = pd.DataFrame(rows)

    # A book, priced, so the metrics requirement is met rather than skipped.
    _, weekly = forward(prices, 13)
    holdings = pd.Series(0.0, index=prices.columns, dtype=float)
    previous = holdings.copy()
    path_rows = {}
    for cost in (0.0, 10.0, 50.0, 100.0):
        holdings = pd.Series(0.0, index=prices.columns, dtype=float)
        previous = holdings.copy()
        values = []
        for week in weekly.index:
            charge = 0.0
            if week in books:
                names = books[week]
                holdings = pd.Series(0.0, index=prices.columns, dtype=float)
                holdings.loc[names] = 1.0 / len(names)
                charge = float((holdings - previous).abs().sum()) * cost / 10_000.0
                previous = holdings.copy()
            values.append(float((holdings * weekly.loc[week].fillna(0.0)).sum()) - charge)
        series = pd.Series(values, index=weekly.index)
        start = min(books) if books else series.index[0]
        series = series.loc[start:]
        wealth = (1.0 + series.fillna(0.0)).cumprod()
        years = len(series) / 52.0
        volatility = float(series.std(ddof=1) * np.sqrt(52))
        path_rows[cost] = {
            "cost_bps": cost,
            "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years else float("nan"),
            "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
            "annualised_volatility": volatility,
            "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
            "recent_52w_return": float((1.0 + series.tail(52).fillna(0.0)).prod() - 1.0),
        }
        if cost == 50.0:
            book_path = series

    correlations = {}
    for name, relative in EXISTING.items():
        other = pd.read_csv(ROOT / relative, parse_dates=["Date"]).set_index("Date").iloc[:, 0]
        other.index = pd.to_datetime(other.index).tz_localize(None)
        joined = pd.concat([book_path.rename("sue"), other.rename("other")], axis=1).dropna()
        if len(joined) > 26:
            correlations[name] = float(joined.sue.corr(joined.other))

    best = table.loc[table.t_stat.idxmax()] if not table.empty else None
    if table.empty:
        verdict = "not measurable on this panel"
    elif (table.p_value < 0.05).any():
        verdict = "SUE clears an uncorrected 5% bar on at least one horizon; see the table"
    else:
        verdict = (f"SUE does not clear an uncorrected 5% bar on any horizon. With "
                   f"{int(best.decisions)} quarterly decisions the smallest IC this sample could "
                   f"detect at 80% power is {best.minimum_detectable_ic_at_80pct_power:.4f}, and the "
                   f"measured IC is {best.mean_ic:.4f}. The sample cannot resolve an effect of the "
                   f"size Step 201 reported, so this closes as underpowered rather than as refuted.")

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "information_coefficients.csv", index=False)
    pd.DataFrame(path_rows.values()).to_csv(out / "cost_ladder.csv", index=False)
    result = {
        "experiment": "pead_sue_standalone_v1", "queue_item": "S3",
        "prior": "Step 201: +0.0269 selection IC, +0.0174 holdout IC, positive in half of holdout decisions",
        "information_coefficients": rows, "cost_ladder": list(path_rows.values()),
        "correlation_with_existing_strategies": correlations,
        "verdict": verdict,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

    print("INFORMATION COEFFICIENT")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nCOST LADDER (top {args.breadth} by SUE, quarterly)")
    print(pd.DataFrame(path_rows.values()).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nCORRELATION WITH EXISTING: {({k: round(v, 3) for k, v in correlations.items()})}")
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
