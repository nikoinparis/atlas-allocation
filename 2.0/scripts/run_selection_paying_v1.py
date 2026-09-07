#!/usr/bin/env python3
"""Is stock selection being rewarded right now? An index, and a state model on it.

A10 asked what state the market is in and failed. This asks a different question:
not what the market is doing, but whether picking stocks is being *rewarded* --
and it measures that from eight generic characteristics out of any equity
textbook rather than from anything this project built, which is what keeps it
non-circular.

If momentum, volatility, price, beta, downside deviation, max return and skew all
predict returns in a given week, the cross-section is separable that week whoever
is doing the choosing. If none of them does, selection is not paying and no
signal will save you.

The deciding test is the same one A10 failed and it is causal on purpose: the
index's state probability must shift persistently at 2025-04-04 using only
information available then. An index that explains the past is not a signal.
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
import sys
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.markov_regime import causal_stress_probabilities, fit_two_state_gaussian_markov

REGISTRY = ROOT / "config/selection_paying_registry_v1.json"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
HORIZON, SKIP = 4, 1
STRATEGIES = {
    "sector_ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
    "residual_composite": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
    "cash_conversion_b20": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth_top_five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}


def characteristics(returns: pd.DataFrame, prices: pd.DataFrame) -> dict[str, pd.DataFrame]:
    market = returns.mean(axis=1, skipna=True)
    compound = lambda n: (1.0 + returns.fillna(0.0)).rolling(n).apply(np.prod, raw=True) - 1.0
    beta_cov = returns.mul(market, axis=0).rolling(52).mean() - returns.rolling(52).mean().mul(
        market.rolling(52).mean(), axis=0)
    downside = returns.where(returns < 0).rolling(26, min_periods=8).std()
    out = {
        "momentum_4w": compound(4),
        "momentum_52w": compound(52),
        "volatility_13w": returns.rolling(13).std(),
        "log_price": np.log(prices.where(prices > 0)),
        "beta_52w": beta_cov.div(market.rolling(52).var(), axis=0),
        "downside_deviation_26w": downside,
        "max_weekly_return_13w": returns.rolling(13).max(),
        "return_skew_52w": returns.rolling(52).skew(),
    }
    return {name: frame.shift(SKIP) for name, frame in out.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/selection_paying_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fit_window = registry["protocol"]["fit_window"]

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)

    compounded = (1.0 + returns.fillna(0.0)).rolling(HORIZON).apply(np.prod, raw=True) - 1.0
    valid = returns.notna().rolling(HORIZON).sum() >= HORIZON
    forward = compounded.where(valid).shift(-HORIZON)

    chars = characteristics(returns, prices)
    weekly = []
    for week in returns.index:
        if week not in forward.index:
            continue
        outcome = forward.loc[week]
        values = []
        for frame in chars.values():
            pair = pd.DataFrame({"s": frame.loc[week], "f": outcome}).dropna()
            if len(pair) < 300:
                continue
            value = pair.s.rank().corr(pair.f.rank())
            if np.isfinite(value):
                values.append(abs(float(value)))
        if len(values) >= 6:
            weekly.append({"week": week, "index": float(np.mean(values)), "characteristics": len(values)})
    index = pd.DataFrame(weekly).set_index("week")["index"].dropna()

    fit_slice = index.loc[(index.index >= fit_window[0]) & (index.index <= fit_window[1])]
    model = fit_two_state_gaussian_markov(fit_slice.to_numpy().tolist())
    probability = pd.Series(causal_stress_probabilities(index.to_numpy().tolist(), model), index=index.index)

    window = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=8))
                             & (probability.index <= BREAK + pd.Timedelta(weeks=8))]
    before = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=52))
                             & (probability.index < BREAK - pd.Timedelta(weeks=8))]
    after = probability.loc[probability.index > BREAK + pd.Timedelta(weeks=8)]
    detects = bool(len(window) and window.max() > 0.5 and len(after) and len(before)
                   and after.mean() - before.mean() > 0.2 and after.mean() > 0.5)

    conditional, tradeable = [], []
    for label, relative in STRATEGIES.items():
        frame = pd.read_csv(ROOT / relative)
        column = "Date" if "Date" in frame.columns else frame.columns[0]
        frame[column] = pd.to_datetime(frame[column], utc=True)
        frame = frame.set_index(column).sort_index()
        name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
        path = pd.to_numeric(frame[name], errors="coerce").dropna()
        joined = pd.concat([path.rename("r"), probability.rename("p")], axis=1).dropna()
        if len(joined) < 60:
            continue
        cut = joined.p.median()
        high, low = joined[joined.p > cut], joined[joined.p <= cut]
        conditional.append({"strategy": label, "weeks": len(joined),
                            "return_when_selection_pays": float(high.r.mean() * 52),
                            "return_when_it_does_not": float(low.r.mean() * 52),
                            "difference": float((high.r.mean() - low.r.mean()) * 52)})
        # switching: hold only when the causal probability is above its own median
        switched = joined.r.where(joined.p > cut, 0.0)
        turnover = (joined.p > cut).astype(int).diff().abs().fillna(0)
        switched = switched - turnover * 50 / 10_000.0
        vol_u = float(joined.r.std(ddof=1) * np.sqrt(52))
        vol_s = float(switched.std(ddof=1) * np.sqrt(52))
        tradeable.append({"strategy": label,
                          "unconditional_return": float(joined.r.mean() * 52),
                          "conditional_return_after_costs": float(switched.mean() * 52),
                          "unconditional_sharpe": float(joined.r.mean() * 52 / vol_u) if vol_u else None,
                          "conditional_sharpe": float(switched.mean() * 52 / vol_s) if vol_s else None,
                          "switches": int(turnover.sum())})

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"index": index, "causal_probability": probability}).to_csv(out / "index.csv")

    if not detects:
        verdict = ("the selection-paying index does NOT shift persistently at 2025-04-04 "
                   f"(pre-break year {before.mean():.3f}, post-break {after.mean():.3f}). April 2025 "
                   "was not selection starting to pay, and the pre-declared reading closes the regime "
                   "thread for good rather than for now.")
    elif all(row["difference"] <= 0 for row in conditional):
        verdict = ("the index shifts at the break but no strategy earns more when it is high, so it "
                   "measures something real that these strategies are not exposed to")
    else:
        verdict = "the index shifts and strategies earn more when it is high; see the tradeable table"

    result = {"experiment": "selection_paying_v1", "queue_item": "A13",
              "weeks": int(len(index)), "index_mean": float(index.mean()),
              "index_in_fit_window": float(fit_slice.mean()),
              "index_pre_break_year": float(index.loc[before.index].mean()) if len(before) else None,
              "index_post_break": float(index.loc[after.index].mean()) if len(after) else None,
              "probability_pre_break_year": float(before.mean()) if len(before) else None,
              "probability_max_near_break": float(window.max()) if len(window) else None,
              "probability_post_break": float(after.mean()) if len(after) else None,
              "detects_transition": detects,
              "strategy_by_index": conditional, "switching": tradeable, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")

    print(f"index computed over {len(index)} weeks, mean {index.mean():.4f}")
    print(f"  index level: fit window {fit_slice.mean():.4f} | year before break "
          f"{index.loc[before.index].mean():.4f} | after break {index.loc[after.index].mean():.4f}")
    print(f"  causal probability: before {before.mean():.3f} | max near break {window.max():.3f} | "
          f"after {after.mean():.3f} | detects transition: {detects}\n")
    print(pd.DataFrame(conditional).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    print(pd.DataFrame(tradeable).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
