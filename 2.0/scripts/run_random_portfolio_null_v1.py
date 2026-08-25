#!/usr/bin/env python3
"""Are the saved strategies distinguishable from luck?

Every negative result this session says the signals cannot select. But the saved
strategies returned 92% to 156% on pure cash while the equal-weight universe
returned 30%. Either they are doing something, or they are extreme draws.

This builds the null directly: for each strategy, generate thousands of random
portfolios holding the same number of names, over the same window, with the same
rebalance dates, and locate the strategy's actual return in that distribution.

A second null matches on volatility percentile too, which asks whether any edge
survives once the volatility tilt from Step 191 is controlled for.
"""

from __future__ import annotations

import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
DASHBOARD = ROOT / "dashboard/public/return-first-dashboard.json"
OUTPUT = ROOT / "evidence/random_portfolio_null_v1"

DRAWS = 4000
SEED = 20260826
COST_BPS = 50.0
TILT_TOLERANCE = 0.05


def ticker_to_cik() -> dict[str, str]:
    out: dict[str, str] = {}
    with INVENTORY.open() as h:
        for row in csv.DictReader(h):
            m = re.search(r"/histories/([A-Za-z0-9.\-]+)\.csv\.gz$", row["path"])
            if m:
                out.setdefault(m.group(1).upper(), row["cik10"])
    return out


def stats(r: np.ndarray, periods: int = 52) -> dict:
    w = np.cumprod(1 + r)
    years = len(r) / periods
    sd = r.std(ddof=1)
    peak = np.maximum.accumulate(w)
    return {"cagr": float(w[-1] ** (1 / years) - 1),
            "sharpe": float(r.mean() / sd * math.sqrt(periods)) if sd else 0.0,
            "max_drawdown": float((w / peak - 1).min())}


def main() -> int:
    prices = pd.read_csv(PRICES, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    returns = prices.pct_change().replace([np.inf, -np.inf], np.nan)
    vol = returns.rolling(52, min_periods=40).std(ddof=1)
    volpct = vol.rank(axis=1, pct=True)

    tickers = ticker_to_cik()
    document = json.loads(DASHBOARD.read_text())
    rng = np.random.default_rng(SEED)

    rows = []
    for item in document["strategies"]:
        meta = item["strategy"]
        records = item["records"][-53:]           # trailing 52 weeks of decisions
        stamps = [pd.Timestamp(r["date"]) for r in records if pd.Timestamp(r["date"]) in returns.index]
        if len(stamps) < 20:
            continue

        # the strategy's own realised path over the same window, pure cash
        gross = np.array([float(r["grossReturn"]) for r in records[-len(stamps):]], dtype=float)
        exposure = max(1.0, max(sum(abs(h["weight"]) for h in r["holdings"] if not h["symbol"].startswith("cash"))
                                for r in records))
        actual = gross / exposure

        # observed size and tilt
        sizes, tilts = [], []
        for r in records:
            names = [h for h in r["holdings"] if not h["symbol"].startswith("cash")]
            sizes.append(len(names))
            stamp = pd.Timestamp(r["date"])
            if stamp in volpct.index:
                row = volpct.loc[stamp]
                w = t = 0.0
                for h in names:
                    cik = tickers.get(h["symbol"].upper())
                    if cik and cik in row.index and pd.notna(row[cik]):
                        wt = abs(float(h["weight"])); w += float(row[cik]) * wt; t += wt
                if t:
                    tilts.append(w / t)
        size = int(np.median(sizes)) or 20
        tilt = float(np.median(tilts)) if tilts else 0.5

        window = returns.loc[stamps]
        available = window.columns[window.notna().sum() >= len(stamps) * 0.8]
        matrix = window[available].fillna(0.0).to_numpy()

        # null 1: same size, uniformly random names
        picks = rng.random((DRAWS, matrix.shape[1])).argsort(axis=1)[:, :size]
        plain = np.array([stats(matrix[:, p].mean(axis=1))["cagr"] for p in picks])

        # null 2: same size, matched volatility percentile
        last = volpct.loc[stamps[-1]].reindex(available)
        eligible = np.flatnonzero(((last - tilt).abs() <= TILT_TOLERANCE).to_numpy())
        if len(eligible) >= size * 2:
            mpicks = np.array([rng.choice(eligible, size=size, replace=False) for _ in range(DRAWS)])
            matched = np.array([stats(matrix[:, p].mean(axis=1))["cagr"] for p in mpicks])
        else:
            matched = np.array([])

        realised = stats(actual)["cagr"]
        rows.append({
            "id": meta["id"], "short_name": meta["shortName"],
            "median_names_held": size, "median_volatility_tilt": tilt,
            "realised_cagr_pure_cash": realised,
            "random_median": float(np.median(plain)), "random_p95": float(np.quantile(plain, 0.95)),
            "random_p99": float(np.quantile(plain, 0.99)),
            "percentile_vs_random": float((plain < realised).mean()),
            "matched_median": float(np.median(matched)) if len(matched) else None,
            "matched_p95": float(np.quantile(matched, 0.95)) if len(matched) else None,
            "percentile_vs_matched": float((matched < realised).mean()) if len(matched) else None,
            "matched_pool": int(len(eligible)),
        })

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "null_comparison.csv", index=False)
    beats95 = [r["short_name"] for r in rows if r["percentile_vs_random"] >= 0.95]
    payload = {
        "experiment_id": "random-portfolio-null-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "draws_per_strategy": DRAWS, "seed": SEED,
        "window": "trailing 52 weekly decisions from each strategy's own record",
        "strategies": rows,
        "strategies_above_95th_percentile_of_random": beats95,
        "caveat": ("A high percentile is consistent with skill and also with a lucky draw; it is one "
                   "window. The matched null is the stricter test because it removes the volatility "
                   "tilt that Step 191 showed explains much of the return ranking."),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"{DRAWS:,} random portfolios per strategy, matched on size, trailing 52 weeks\n")
    print(f"  {'strategy':<26}{'names':>6}{'actual':>9}{'rand med':>10}{'rand p95':>10}{'pctile':>9}{'tilt-matched pctile':>21}")
    for r in sorted(rows, key=lambda x: -x["realised_cagr_pure_cash"]):
        mp = f"{100*r['percentile_vs_matched']:.1f}%" if r["percentile_vs_matched"] is not None else "n/a"
        print(f"  {r['short_name']:<26}{r['median_names_held']:>6}{100*r['realised_cagr_pure_cash']:>8.1f}%"
              f"{100*r['random_median']:>9.1f}%{100*r['random_p95']:>9.1f}%{100*r['percentile_vs_random']:>8.1f}%{mp:>21}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
