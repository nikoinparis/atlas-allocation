#!/usr/bin/env python3
"""How many names does it take to stop being a lottery?

Step 188 established that single names decide outcomes and that no signal here
ranks them ex ante. If both are true, holding more names is the only mechanism
that converts a lottery into an expectation. This measures the conversion rate:
draw equal-weight portfolios of N names from the panel, repeatedly, and watch
what happens to the spread of outcomes as N grows.

Selection is random by construction. That is the point: it isolates the effect
of breadth alone, with zero selection skill assumed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PRICES = ROOT / "data/sec_broad_panel_inputs_v2/weekly_adjusted_prices.csv.gz"
OUTPUT = ROOT / "evidence/breadth_diversification_curve_v1"

SIZES = [1, 3, 5, 10, 20, 40, 80, 160, 320]
DRAWS = 4000
HORIZON = 52
SEED = 20260825


def main() -> int:
    prices = pd.read_csv(PRICES, index_col=0)
    prices.index = pd.to_datetime(prices.index)
    # one full year of forward performance per name, from the latest complete window
    start = prices.index[-(HORIZON + 1)]
    end = prices.index[-1]
    window = prices.loc[start:end]
    total = (window.iloc[-1] / window.iloc[0] - 1.0).dropna()
    total = total[np.isfinite(total)]

    rng = np.random.default_rng(SEED)
    universe = total.to_numpy()
    rows = []
    for size in SIZES:
        # each draw is a distinct portfolio sampled without replacement within itself
        picks = rng.random((DRAWS, len(universe))).argsort(axis=1)[:, :size]
        outcomes = universe[picks].mean(axis=1)
        rows.append({
            "names": size,
            "median": float(np.median(outcomes)),
            "mean": float(outcomes.mean()),
            "p05": float(np.quantile(outcomes, 0.05)),
            "p25": float(np.quantile(outcomes, 0.25)),
            "p75": float(np.quantile(outcomes, 0.75)),
            "p95": float(np.quantile(outcomes, 0.95)),
            "spread_p05_p95": float(np.quantile(outcomes, 0.95) - np.quantile(outcomes, 0.05)),
            "probability_of_loss": float((outcomes < 0).mean()),
            "probability_below_minus_20pct": float((outcomes < -0.20).mean()),
            "standard_deviation": float(outcomes.std(ddof=1)),
        })

    table = pd.DataFrame(rows)
    base = table.loc[table.names == 1].iloc[0]
    table["spread_vs_single_name"] = table.spread_p05_p95 / base.spread_p05_p95

    OUTPUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUTPUT / "diversification_curve.csv", index=False)
    payload = {
        "experiment_id": "breadth-diversification-curve-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": {"start": str(start.date()), "end": str(end.date()), "weeks": HORIZON},
        "universe_names": int(len(total)),
        "draws_per_size": DRAWS,
        "selection": "uniform random, zero skill assumed",
        "curve": rows,
        "interpretation": (
            "The median barely moves with N because random selection has no edge. What collapses is the "
            "spread. Every additional name buys certainty, not return. That is precisely the trade a "
            "strategy with no measurable decile spread should want to make."
        ),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"universe {len(total)} names, {HORIZON} weeks to {end.date()}, {DRAWS} random draws per size\n")
    print(f"  {'names':>6}{'median':>10}{'5th pct':>10}{'95th pct':>10}{'p5-p95':>10}{'P(loss)':>10}{'P(<-20%)':>11}{'spread vs 1':>13}")
    for r, ratio in zip(rows, table.spread_vs_single_name):
        print(f"  {r['names']:>6}{100*r['median']:>9.1f}%{100*r['p05']:>9.1f}%{100*r['p95']:>9.1f}%"
              f"{100*r['spread_p05_p95']:>9.1f}%{100*r['probability_of_loss']:>9.1f}%"
              f"{100*r['probability_below_minus_20pct']:>10.1f}%{ratio:>12.2f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
