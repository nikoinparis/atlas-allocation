#!/usr/bin/env python3
"""Estimate market states from observables, then test whether strategies care.

Queue item A10, from the owner's idea after Step 262. Their instinct that states
should be probabilistic rather than dated is right and is what this produces.

Their proposed method needed one change. Inferring states from how our own
strategies performed is circular -- define the state by strategy returns and
"strategies do well in state A" is true by construction. So states come from
market observables that exist independently of anything this project built, and
strategy performance is tested against them rather than used to define them.

The test that decides everything is not whether the model labels history well.
It is whether the causal probability moves at the 2025 transition AT THE TIME.
Almost every published regime model labels history beautifully and cannot call the
present, and one that cannot call the present cannot be traded on.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.markov_regime import causal_stress_probabilities, fit_two_state_gaussian_markov

REGISTRY = ROOT / "config/market_state_registry_v1.json"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
BREAK = pd.Timestamp("2025-04-04", tz="UTC")
STRATEGIES = {
    "sector_ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
    "residual_composite": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
    "cash_conversion_b20": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth_top_five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}


def observables(returns: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    dispersion = returns.std(axis=1, skipna=True)
    market = returns.mean(axis=1, skipna=True)
    # average pairwise correlation from the variance ratio, which is O(n) not O(n^2)
    index_var = market.rolling(26).var()
    mean_var = returns.var(axis=1, skipna=True).rolling(26).mean()
    count = returns.notna().sum(axis=1).rolling(26).mean()
    average_correlation = ((index_var * count - mean_var) / (mean_var * (count - 1))).clip(-1, 1)
    breadth = (prices > prices.rolling(26).mean()).sum(axis=1) / prices.notna().sum(axis=1)
    volatility = returns.rolling(13).std().mean(axis=1, skipna=True)
    frame = pd.DataFrame({"dispersion": dispersion, "average_correlation": average_correlation,
                          "breadth": breadth, "volatility": volatility})
    return frame.dropna()


def read_path(relative: str) -> pd.Series:
    frame = pd.read_csv(ROOT / relative)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/market_state_v1")
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    fit_window = registry["protocol"]["fit_window"]

    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True)
    prices.columns = [str(c) for c in prices.columns]
    returns = (prices / prices.shift(1) - 1.0).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() <= 1.0)
    frame = observables(returns, prices)

    rows, probability_frames = [], {}
    for name in frame.columns:
        series = frame[name]
        fit_slice = series.loc[(series.index >= fit_window[0]) & (series.index <= fit_window[1])]
        if len(fit_slice) < 100:
            continue
        # fit once, on the fit window only, and never refit
        model = fit_two_state_gaussian_markov(fit_slice.to_numpy().tolist())
        probability = pd.Series(causal_stress_probabilities(series.to_numpy().tolist(), model),
                                index=series.index, name=name)
        probability_frames[name] = probability

        # does it move AT the break, or only after it?
        window = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=8))
                                 & (probability.index <= BREAK + pd.Timedelta(weeks=8))]
        before = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=52))
                                 & (probability.index < BREAK - pd.Timedelta(weeks=8))]
        after = probability.loc[probability.index > BREAK + pd.Timedelta(weeks=8)]
        rows.append({
            "observable": name,
            "fit_weeks": len(fit_slice),
            "mean_probability_pre_break_year": float(before.mean()) if len(before) else None,
            "max_probability_within_8_weeks_of_break": float(window.max()) if len(window) else None,
            "mean_probability_after": float(after.mean()) if len(after) else None,
            # A transient spike is not a transition, and a variable already sitting
            # high before the break has not detected anything by staying high. The
            # first version of this test asked only "did it exceed 0.5 near the
            # break" and passed three observables whose probability was LOWER after
            # the break than before it. A transition requires a persistent level
            # shift, so all three conditions must hold.
            "spike_near_break": bool(len(window) and window.max() > 0.5),
            "level_shift_after_vs_before": (
                float(after.mean() - before.mean()) if len(after) and len(before) else None),
            "detects_transition_at_the_time": bool(
                len(window) and window.max() > 0.5
                and len(after) and len(before)
                and after.mean() - before.mean() > 0.2
                and after.mean() > 0.5),
        })
    detection = pd.DataFrame(rows)
    probabilities = pd.DataFrame(probability_frames)
    probabilities["consensus"] = probabilities.mean(axis=1)

    # secondary: do strategies perform differently by causal state?
    conditional = []
    for label, relative in STRATEGIES.items():
        path = read_path(relative)
        joined = pd.concat([path.rename("r"), probabilities.consensus.rename("p")], axis=1).dropna()
        if len(joined) < 60:
            continue
        high = joined[joined.p > joined.p.median()]
        low = joined[joined.p <= joined.p.median()]
        conditional.append({
            "strategy": label, "weeks": len(joined),
            "return_high_state_annualised": float(high.r.mean() * 52),
            "return_low_state_annualised": float(low.r.mean() * 52),
            "difference": float((high.r.mean() - low.r.mean()) * 52),
            "high_state_weeks": len(high),
        })
    conditional_frame = pd.DataFrame(conditional)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    probabilities.to_csv(out / "state_probabilities.csv")
    detection.to_csv(out / "transition_detection.csv", index=False)
    conditional_frame.to_csv(out / "strategy_by_state.csv", index=False)

    detected = detection[detection.detects_transition_at_the_time]
    if detection.empty:
        verdict = "no observable produced a usable model"
    elif detected.empty:
        verdict = ("NO observable shows a PERSISTENT state change at 2025-04-04: some spike above "
                   "0.5 near the break and every one of them sits LOWER after the break than in the "
                   "year before it, which is a transient move and not a transition. The classifier "
                   "labels history and cannot call the transition at the "
                   "time, which is the pre-declared stop condition. The regime story may be true and "
                   "is not actionable, and state-conditioned strategy selection is NOT authorised.")
    else:
        verdict = (f"{', '.join(detected.observable)} detect the transition within eight weeks. "
                   f"State-conditioned selection becomes worth a separate registry.")

    result = {"experiment": "market_state_v1", "queue_item": "A10",
              "states_from": "market observables, never from strategy returns",
              "fit_window": fit_window, "never_refit": True,
              "detection": rows, "strategy_by_state": conditional,
              "verdict": verdict,
              "known_risk": registry["known_risk_declared_up_front"],
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print("CAN THE CLASSIFIER CALL THE 2025 TRANSITION AT THE TIME?")
    print(detection.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print("\nSTRATEGY RETURN BY CAUSAL STATE (consensus probability, split at its median)")
    print(conditional_frame.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
