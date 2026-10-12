#!/usr/bin/env python3
"""Queue item B6: is any book here more than known factor exposure?

Every alpha this project has reported is a CAPM intercept or an excess over a
benchmark. Step 295 found ninety per cent of cash conversion's return was market
beta; this asks the same question of the other known factors. Ken French's daily
five factors plus momentum, compounded to week-ending Fridays, regressed against
each book's weekly net return over the risk-free rate. Newey-West standard
errors, four lags. A diagnostic: it cannot create a strategy.

Books are judged in two windows, as everywhere else here: the 2023-2026 window
they were chosen on, and the 2013-2022 out-of-sample rebuilds. The equal-weight
universe rides along as a control -- if a book's factor alpha matches the
universe's, the alpha belongs to the universe, not the selection.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.systematic_trader.return_conventions import load_aligned

FF = sorted((ROOT / "data/fama_french_factor_vintages").glob("*-ff5-mom-daily"))[-1]
OUTPUT = ROOT / "evidence/factor_attribution_v1"
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
LAGS = 4

BOOKS = {
    "IN 2023-2026": {
        "growth top five": "evidence/sec_growth_survivorship_retest_v1/path_growth__base__50bps.csv",
        "cash conversion": "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv",
        "sector ensemble": "evidence/sec_sector_aware_signal_ensemble_v1/selected_path__50bps.csv",
        "valuation breadth 20": "evidence/valuation_revival_v1/path__breadth20__50bps.csv",
    },
    "OOS 2013-2022": {
        "growth top five": "evidence/dashboard_signals_out_of_sample_v1/path__growth_top5__50bps.csv",
        "cash conversion": "evidence/dashboard_signals_out_of_sample_v1/path__cash_conversion_breadth20__50bps.csv",
        "balance sheet quality": "evidence/dashboard_signals_out_of_sample_v1/path__balance_sheet_quality__50bps.csv",
        "sector ensemble stock leg": "evidence/composites_out_of_sample_v1/path__sector_ensemble_stock_leg__50bps.csv",
        "residual composite": "evidence/composites_out_of_sample_v1/path__residual_composite__50bps.csv",
        "valuation book": "evidence/valuation_out_of_sample_v1/path__book__50bps.csv",
        "CONTROL valuation universe": "evidence/valuation_out_of_sample_v1/path__universe__50bps.csv",
    },
}


def read_french(name: str) -> pd.DataFrame:
    path = next(FF.glob(f"{name}*.csv"))
    lines = path.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(","))
    rows = []
    for line in lines[start + 1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or not parts[0].isdigit() or len(parts[0]) != 8:
            if rows:
                break
            continue
        rows.append(parts)
    header = ["date"] + [h.strip() for h in lines[start].split(",")[1:]]
    frame = pd.DataFrame(rows, columns=header)
    frame["date"] = pd.to_datetime(frame.date, format="%Y%m%d", utc=True)
    return frame.set_index("date").astype(float) / 100.0


def weekly_factors() -> pd.DataFrame:
    daily = read_french("F-F_Research_Data_5_Factors").join(read_french("F-F_Momentum"), how="inner")
    daily.columns = [c.strip() for c in daily.columns]
    weekly = (1.0 + daily).resample("W-FRI").prod() - 1.0
    # Drop a trailing week the French file does not fully cover.
    last = daily.index[-1]
    if last.dayofweek != 4:
        weekly = weekly[weekly.index < last.normalize()]
    return weekly


def newey_west(x: np.ndarray, y: np.ndarray, lags: int):
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    resid = y - x @ beta
    n = len(y)
    xe = x * resid[:, None]
    s = xe.T @ xe
    for lag in range(1, lags + 1):
        w = 1.0 - lag / (lags + 1.0)
        g = xe[lag:].T @ xe[:-lag]
        s += w * (g + g.T)
    bread = np.linalg.inv(x.T @ x)
    cov = bread @ s @ bread
    se = np.sqrt(np.diag(cov))
    r2 = 1.0 - resid.var() / y.var()
    return beta, beta / se, r2


def attribute(series: pd.Series, factors: pd.DataFrame) -> dict:
    frame = pd.concat({"r": series}, axis=1).join(factors, how="inner").dropna()
    y = (frame.r - frame.RF).to_numpy()
    out = {"weeks": int(len(frame)), "first": str(frame.index[0].date()),
           "last": str(frame.index[-1].date())}
    for label, cols in (("capm", ["Mkt-RF"]), ("ff6", FACTORS)):
        x = np.column_stack([np.ones(len(frame))] + [frame[c].to_numpy() for c in cols])
        beta, t, r2 = newey_west(x, y, LAGS)
        out[label] = {"alpha_annual": float((1 + beta[0]) ** 52 - 1), "alpha_t": float(t[0]),
                      "r2": float(r2),
                      "loadings": {c: float(b) for c, b in zip(cols, beta[1:])},
                      "loading_t": {c: float(v) for c, v in zip(cols, t[1:])}}
    out["raw_excess_annual"] = float((1 + y.mean()) ** 52 - 1)
    return out


def main() -> int:
    factors = weekly_factors()
    print(f"factors: {FF.name}, weekly {factors.index[0].date()} to {factors.index[-1].date()}")
    market = factors["Mkt-RF"] + factors["RF"]
    results = {}
    for window, books in BOOKS.items():
        print(f"\n== {window}")
        print(f"{'book':28s} {'wks':>4s} {'CAPM a':>8s} {'t':>6s} {'FF6 a':>8s} {'t':>6s} {'R2':>5s}  "
              + " ".join(f"{c:>7s}" for c in FACTORS))
        for name, path in books.items():
            series = load_aligned(path, root=ROOT, benchmark=market)
            series.index = pd.to_datetime(series.index, utc=True).normalize()
            r = attribute(series, factors)
            results[f"{window} | {name}"] = r
            c, f = r["capm"], r["ff6"]
            loads = " ".join(f"{f['loadings'][k]:+7.2f}" for k in FACTORS)
            print(f"{name:28s} {r['weeks']:4d} {c['alpha_annual']:+8.2%} {c['alpha_t']:+6.2f} "
                  f"{f['alpha_annual']:+8.2%} {f['alpha_t']:+6.2f} {f['r2']:5.2f}  {loads}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result.json").write_text(json.dumps({
        "factor_vintage": FF.name, "newey_west_lags": LAGS, "results": results,
        "this_is_a_diagnostic_not_a_search": True,
        "live_trading_enabled": False, "strategy_promotion_authorized": False,
    }, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
