#!/usr/bin/env python3
"""Macro state: does the rates-and-conditions regime explain anything here?

The last untried family of state variable. A10 used market observables computed
from our own price panel and failed. A13 used whether selection is being rewarded
and found a real but untradeable relationship. This uses the things macro people
actually watch, none of which is computed from anything this project built:

  T10Y2Y            the yield curve slope, the classic regime indicator
  NFCI              the Chicago Fed's financial conditions index
  policy_minus_3m   policy stance against the front of the curve
  DTWEXBGS          the broad dollar
  VIX               and its one-to-three-month term structure slope
  HYG / IEF         high yield against treasuries, a credit spread proxy

Same protocol as A13, and the same deciding test: the state probability must shift
persistently at 2025-04-04 using only information available then. Fit on 2005-2020
and never refit.
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

BREAK = pd.Timestamp("2025-04-04", tz="UTC")
FIT_END = "2020-12-31"
ETF = ROOT / "data/derived/20260808T212827Z-de103c2e063d6c4a/weekly_prices.csv"
STRATEGIES = {
    "sector_ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
    "residual_composite": "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv",
    "cash_conversion_b20": "evidence/sec_cash_conversion_breadth_dynamic_v1/best_path__base__50bps.csv",
    "growth_top_five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
}


def newest(pattern: str) -> Path:
    candidates = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise SystemExit(f"no file matching {pattern}")
    return candidates[-1]


def observables() -> pd.DataFrame:
    fred = pd.read_csv(newest("data/regime_vintages/**/normalized/fred_weekly_supplemental.csv"),
                       parse_dates=["Date"]).set_index("Date")
    vix = pd.read_csv(newest("data/regime_vintages/**/normalized/vix_term_structure.csv"),
                      parse_dates=["Date"]).set_index("Date")
    etf = pd.read_csv(ETF, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    frame = pd.DataFrame({
        "curve_slope": fred["T10Y2Y"],
        "financial_conditions": fred["NFCI"],
        "policy_stance": fred["policy_minus_3m"],
        "dollar": fred["DTWEXBGS"].pct_change(13),
        "vix": vix["VIX"],
        "vix_term_slope": vix["slope_1m_3m"],
    })
    if {"HYG", "IEF"} <= set(etf.columns):
        credit = (etf["HYG"] / etf["IEF"])
        frame["credit_proxy"] = credit.pct_change(13)
    frame.index = pd.to_datetime(frame.index, utc=True)
    return frame.dropna(how="all")


def read_path(relative: str) -> pd.Series:
    frame = pd.read_csv(ROOT / relative)
    column = "Date" if "Date" in frame.columns else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column], utc=True)
    frame = frame.set_index(column).sort_index()
    name = next((c for c in ("net_return", "return") if c in frame.columns), frame.columns[0])
    return pd.to_numeric(frame[name], errors="coerce").dropna()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/macro_state_v1")
    args = parser.parse_args()

    frame = observables()
    rows, probabilities = [], {}
    for name in frame.columns:
        series = frame[name].dropna()
        fit_slice = series.loc[series.index <= FIT_END]
        if len(fit_slice) < 200:
            continue
        model = fit_two_state_gaussian_markov(fit_slice.to_numpy().tolist())
        probability = pd.Series(causal_stress_probabilities(series.to_numpy().tolist(), model),
                                index=series.index)
        probabilities[name] = probability
        window = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=8))
                                 & (probability.index <= BREAK + pd.Timedelta(weeks=8))]
        before = probability.loc[(probability.index >= BREAK - pd.Timedelta(weeks=52))
                                 & (probability.index < BREAK - pd.Timedelta(weeks=8))]
        after = probability.loc[probability.index > BREAK + pd.Timedelta(weeks=8)]
        detects = bool(len(window) and window.max() > 0.5 and len(after) and len(before)
                       and after.mean() - before.mean() > 0.2 and after.mean() > 0.5)
        rows.append({"observable": name, "fit_weeks": len(fit_slice),
                     "probability_pre_break_year": float(before.mean()) if len(before) else None,
                     "probability_max_near_break": float(window.max()) if len(window) else None,
                     "probability_after_break": float(after.mean()) if len(after) else None,
                     "level_shift": float(after.mean() - before.mean()) if len(after) and len(before) else None,
                     "detects_transition": detects})
    detection = pd.DataFrame(rows)
    consensus = pd.DataFrame(probabilities).mean(axis=1)

    conditional = []
    for label, relative in STRATEGIES.items():
        joined = pd.concat([read_path(relative).rename("r"), consensus.rename("p")], axis=1).dropna()
        if len(joined) < 60:
            continue
        cut = joined.p.median()
        high, low = joined[joined.p > cut], joined[joined.p <= cut]
        conditional.append({"strategy": label, "weeks": len(joined),
                            "return_high_macro_state": float(high.r.mean() * 52),
                            "return_low_macro_state": float(low.r.mean() * 52),
                            "difference": float((high.r.mean() - low.r.mean()) * 52)})

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(probabilities).assign(consensus=consensus).to_csv(out / "macro_state_probabilities.csv")
    detection.to_csv(out / "transition_detection.csv", index=False)

    detected = detection[detection.detects_transition]
    if detection.empty:
        verdict = "no macro observable produced a usable model"
    elif detected.empty:
        verdict = ("no macro observable shows a persistent state change at 2025-04-04. Rates, "
                   "financial conditions, the dollar, volatility and credit all fail the same test "
                   "the market observables failed in Step 266. The macro regime does not explain "
                   "April 2025 either.")
    else:
        verdict = f"{', '.join(detected.observable)} detect a persistent transition at the break"

    result = {"experiment": "macro_state_v1", "fit_window_end": FIT_END, "never_refit": True,
              "observables": list(frame.columns), "detection": rows,
              "strategy_by_macro_state": conditional, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(detection.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    print(pd.DataFrame(conditional).to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
