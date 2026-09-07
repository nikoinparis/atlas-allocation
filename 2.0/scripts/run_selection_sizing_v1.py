#!/usr/bin/env python3
"""Option 2: size by the selection-paying probability instead of switching on it.

Step 269 found the relationship real and correctly signed -- all four strategies
earn twenty to thirty points more when the index is high -- and found switching
destroys value because the low state still returns 23 to 25 percent a year.

The remaining expression is sizing: hold more when selection is paying, less when
it is not, never zero. That is leverage, and leverage is where this project has
been wrong before, so it is tested with the caps declared and the fragility
measured rather than assumed.

Three things are reported that a naive test would omit: the result in both
sub-periods around the April 2025 break, the drawdown rather than only the return,
and the financing cost of the borrowed fraction.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "evidence/selection_paying_v1/index.csv"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
FINANCING = 0.05
COST_BPS = 50.0
STRATEGIES = {
    "sector_ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
    "residual_composite": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
    "cash_conversion_b20": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth_top_five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}
# declared before running: three caps, from "barely any leverage" to "the level this
# project has previously found carries a 37% overfitting probability"
CAPS = [(0.75, 1.25), (0.50, 1.50), (1.00, 1.00)]


def read_path(relative: str) -> pd.Series:
    frame = pd.read_csv(ROOT / relative)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def summarise(series: pd.Series) -> dict[str, float]:
    if len(series) < 10:
        return {}
    wealth = (1.0 + series.fillna(0.0)).cumprod()
    years = len(series) / 52.0
    volatility = float(series.std(ddof=1) * np.sqrt(52))
    return {"cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
            "sharpe": float(series.mean() * 52 / volatility) if volatility else float("nan"),
            "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
            "annual_volatility": volatility}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/selection_sizing_v1")
    args = parser.parse_args()

    index = pd.read_csv(INDEX, index_col=0, parse_dates=True)
    index.index = pd.to_datetime(index.index, utc=True)
    probability = index["causal_probability"].dropna()

    rows = []
    for label, relative in STRATEGIES.items():
        path = read_path(relative)
        joined = pd.concat([path.rename("r"), probability.rename("p")], axis=1).dropna()
        if len(joined) < 80:
            continue
        for low, high in CAPS:
            # exposure scales linearly with the causal probability, between the caps
            exposure = low + (high - low) * joined.p
            borrowed = (exposure - 1.0).clip(lower=0.0)
            turnover = exposure.diff().abs().fillna(0.0)
            sized = exposure * joined.r - borrowed * FINANCING / 52.0 - turnover * COST_BPS / 10_000.0
            for window, mask in (("full", pd.Series(True, index=joined.index)),
                                 ("pre_break", joined.index < BREAK),
                                 ("post_break", joined.index >= BREAK)):
                a, b = joined.r[mask], sized[mask]
                if len(a) < 30:
                    continue
                base, test = summarise(a), summarise(b)
                rows.append({"strategy": label, "caps": f"{low}-{high}", "window": window,
                             "weeks": len(a), "base_cagr": base["cagr"], "sized_cagr": test["cagr"],
                             "base_sharpe": base["sharpe"], "sized_sharpe": test["sharpe"],
                             "base_maxdd": base["max_drawdown"], "sized_maxdd": test["max_drawdown"],
                             "sharpe_gain": test["sharpe"] - base["sharpe"],
                             "drawdown_worse_by": base["max_drawdown"] - test["max_drawdown"]})
    table = pd.DataFrame(rows)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "sizing.csv", index=False)

    full = table[table.window == "full"]
    improved = full[full.sharpe_gain > 0]
    robust = []
    for row in improved.itertuples():
        pre = table[(table.strategy == row.strategy) & (table.caps == row.caps) & (table.window == "pre_break")]
        post = table[(table.strategy == row.strategy) & (table.caps == row.caps) & (table.window == "post_break")]
        if not pre.empty and not post.empty and pre.iloc[0].sharpe_gain > 0 and post.iloc[0].sharpe_gain > 0:
            robust.append(f"{row.strategy}@{row.caps}")

    if table.empty:
        verdict = "no comparable series"
    elif improved.empty:
        verdict = ("sizing by the selection-paying probability improves no strategy's Sharpe on the "
                   "full window. The relationship is real and neither expression of it -- switching "
                   "in Step 269, sizing here -- is worth holding.")
    elif not robust:
        verdict = (f"{len(improved)} configuration(s) improve Sharpe on the full window but none in "
                   f"both sub-periods, so the gain cannot be separated from the post-break surge")
    else:
        verdict = (f"{', '.join(robust)} improve Sharpe on the full window and in both sub-periods. "
                   f"Read the drawdown column before believing it: this is leverage.")

    result = {"experiment": "selection_sizing_v1",
              "expression": "linear exposure between declared caps, driven by the causal probability",
              "financing_rate": FINANCING, "cost_bps": COST_BPS, "declared_caps": CAPS,
              "rows": rows, "improved_full_window": improved.strategy.tolist(),
              "robust_across_sub_periods": robust, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    show = ["strategy", "caps", "window", "base_cagr", "sized_cagr", "base_sharpe", "sized_sharpe",
            "base_maxdd", "sized_maxdd"]
    print(table[table.window == "full"][show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
