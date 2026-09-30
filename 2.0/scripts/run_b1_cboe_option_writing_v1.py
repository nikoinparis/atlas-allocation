#!/usr/bin/env python3
"""B1 free first read: is there alpha in selling S&P 500 options, after beta and costs?

Executes docs/B1_CBOE_OPTION_WRITING_PREREGISTRATION_V1.md exactly as registered: five Cboe
option-writing indices, monthly excess returns regressed on the S&P 500's, Newey-West (3 lags)
alpha, a beta-matched blend as the comparison, the 0/10/50/100 bps-per-roll cost ladder, the
declared windows, leave-one-year-out, worst-five-month attribution, and a placebo that should
find nothing. Nothing here is added beyond the registration; anything that would be is reported
as a deviation instead.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
RAW = sorted((ROOT / "data/cboe_benchmark_indices_v1").glob("raw_*"))[-1]
OUTPUT = ROOT / "evidence/b1_cboe_option_writing_v1"
SERIES = {"PUT": 12, "WPUT": 52, "BXM": 12, "BXMD": 12, "CNDR": 12}   # rolls per year
COSTS_BPS = [0, 10, 50, 100]
WINDOWS = {"full": (None, None), "2005-2026": ("2005-01-01", None), "2008-2009": ("2008-01-01", "2009-12-31"),
           "2020": ("2020-01-01", "2020-12-31"), "2022": ("2022-01-01", "2022-12-31"),
           "2023-2026": ("2023-01-01", None)}
ALPHA_P_BAR = 0.01


def cboe(symbol: str) -> pd.Series:
    frame = pd.read_csv(RAW / f"{symbol}_History.csv")
    frame["DATE"] = pd.to_datetime(frame["DATE"], format="%m/%d/%Y")
    column = "CLOSE" if "CLOSE" in frame.columns else symbol
    return frame.set_index("DATE")[column].astype(float).sort_index()


def monthly_returns(levels: pd.Series) -> pd.Series:
    # Only consecutive month-ends. PUT's file has seven gaps of up to 1,159 days before 2007; a
    # plain dropna()+pct_change() turned each gap into one "month" and produced a 17% CAGR that
    # was an artefact. A month whose own end or the previous one is missing is dropped instead.
    month_end = levels.resample("ME").last()
    return month_end.pct_change(fill_method=None).dropna()


def newey_west_alpha(y: np.ndarray, x: np.ndarray, lags: int = 3) -> tuple[float, float, float]:
    X = np.column_stack([np.ones_like(x), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    n = len(y)
    xtx_inv = np.linalg.inv(X.T @ X)
    S = (X * resid[:, None]).T @ (X * resid[:, None])
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        gamma = (X[lag:] * resid[lag:, None]).T @ (X[:-lag] * resid[:-lag, None])
        S += weight * (gamma + gamma.T)
    cov = xtx_inv @ S @ xtx_inv
    t_alpha = beta[0] / np.sqrt(cov[0, 0])
    from math import erf, sqrt
    p = 1 - erf(abs(t_alpha) / sqrt(2))          # two-sided normal approximation
    return float(beta[0]), float(beta[1]), float(t_alpha), float(p)


def stats(returns: pd.Series, rf: pd.Series) -> dict:
    if len(returns) < 6:
        return {"months": int(len(returns))}
    wealth = (1 + returns).cumprod()
    years = len(returns) / 12
    excess = returns - rf.reindex(returns.index)
    return {
        "months": int(len(returns)), "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "vol": float(returns.std() * np.sqrt(12)),
        "sharpe": float(excess.mean() / returns.std() * np.sqrt(12)) if returns.std() > 0 else None,
        "max_drawdown": float((wealth / wealth.cummax().clip(lower=1.0) - 1).min()),
        "worst_month": float(returns.min()), "skew": float(returns.skew()),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    spx_daily = yf.download("^SP500TR", start="1988-01-01", auto_adjust=False, progress=False)["Close"].squeeze()
    irx = yf.download("^IRX", start="1985-01-01", auto_adjust=False, progress=False)["Close"].squeeze()
    spx = monthly_returns(spx_daily)
    rf = (irx.resample("ME").last() / 100 / 12).shift(1).reindex(spx.index).ffill()   # yield known at month start
    last_complete = pd.Timestamp(datetime.now(timezone.utc).date()).to_period("M").to_timestamp("M") - pd.offsets.MonthEnd(1)

    results, placebo_hits, placebo_draws = {}, 0, 0
    rng = np.random.default_rng(20260930)
    for symbol, rolls in SERIES.items():
        gross = monthly_returns(cboe(symbol))
        gross = gross[(gross.index >= spx.index[0]) & (gross.index <= last_complete)]
        record = {"first_month": str(gross.index[0].date()), "last_month": str(gross.index[-1].date()), "costs": {}}
        for bps in COSTS_BPS:
            net = gross - bps / 10_000 * rolls / 12
            y = (net - rf.reindex(net.index)).dropna()
            x = (spx.reindex(y.index) - rf.reindex(y.index))
            alpha, beta, t, p = newey_west_alpha(y.values, x.values)
            blend = beta * spx.reindex(net.index) + (1 - beta) * rf.reindex(net.index)
            windows = {}
            for name, (start, end) in WINDOWS.items():
                sl = slice(start, end)
                n, b = net.loc[sl], blend.loc[sl]
                if len(n) < 6:
                    continue
                wy, wx = (n - rf.reindex(n.index)).values, (spx.reindex(n.index) - rf.reindex(n.index)).values
                wa, wb, wt, wp = newey_west_alpha(wy, wx) if len(n) >= 24 else (float((wy - beta * wx).mean()), beta, None, None)
                windows[name] = {"strategy": stats(n, rf), "beta_matched_blend": stats(b, rf),
                                 "alpha_annual": wa * 12, "alpha_t": wt, "beta": wb}
            entry = {"alpha_annual": alpha * 12, "alpha_t": t, "alpha_p": p, "beta": beta, "windows": windows}
            if bps == 10:
                loyo = {}
                for year in sorted(set(y.index.year)):
                    keep = y.index.year != year
                    loyo[int(year)] = newey_west_alpha(y.values[keep], x.values[keep])[0] * 12
                worst_year = min(loyo, key=loyo.get)
                excess_vs_blend = (net - blend).dropna()
                worst5 = excess_vs_blend.nsmallest(5)
                entry["leave_one_year_out"] = {"min_alpha_annual": loyo[worst_year], "year_removed": worst_year,
                                               "all_positive": all(v > 0 for v in loyo.values())}
                entry["worst_five_months_vs_blend"] = {
                    "months": [str(d.date()) for d in worst5.index], "sum": float(worst5.sum()),
                    "total_excess_vs_blend": float(excess_vs_blend.sum())}
                resid_sd = float(np.std(y.values - (alpha + beta * x.values)))
                for _ in range(1000):
                    fake = beta * x.values + rng.normal(0, resid_sd, len(x))
                    placebo_hits += newey_west_alpha(fake, x.values)[3] < ALPHA_P_BAR
                    placebo_draws += 1
            record["costs"][str(bps)] = entry
        c10 = record["costs"]["10"]
        w = c10["windows"]
        passes = {
            "alpha_positive_p_below_0.01_at_10bps": c10["alpha_annual"] > 0 and c10["alpha_p"] < ALPHA_P_BAR,
            "alpha_positive_2005_2026": w.get("2005-2026", {}).get("alpha_annual", -1) > 0,
            "alpha_positive_2023_2026": w.get("2023-2026", {}).get("alpha_annual", -1) > 0,
            "2008_2009_drawdown_within_10pts_of_blend": ("2008-2009" in w and
                w["2008-2009"]["strategy"]["max_drawdown"] >= w["2008-2009"]["beta_matched_blend"]["max_drawdown"] - 0.10),
            "survives_leave_one_year_out": c10["leave_one_year_out"]["all_positive"],
        }
        record["registered_criteria"] = passes
        record["passes"] = all(passes.values())
        results[symbol] = record

    # The premium itself: VIX^2 against the next 21 trading days' realised variance.
    vix = cboe("VIX")
    spx_price = yf.download("^GSPC", start="1990-01-01", auto_adjust=False, progress=False)["Close"].squeeze()
    log_ret = np.log(spx_price).diff()
    realised = (log_ret.rolling(21).var() * 252 * 100 ** 2).shift(-21)
    premium = (vix ** 2 - realised.reindex(vix.index)).dropna()
    vrp = {name: {"mean_vix2_minus_rv": float(premium.loc[slice(s, e)].mean()),
                  "share_positive": float((premium.loc[slice(s, e)] > 0).mean())}
           for name, (s, e) in WINDOWS.items() if len(premium.loc[slice(s, e)])}

    summary = {
        "preregistration": "docs/B1_CBOE_OPTION_WRITING_PREREGISTRATION_V1.md",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(), "raw_vintage": RAW.name,
        "through_month": str(last_complete.date()),
        "placebo": {"draws": placebo_draws, "share_p_below_0.01": placebo_hits / max(placebo_draws, 1),
                    "expected": ALPHA_P_BAR},
        "variance_premium": vrp, "series": results, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(summary, indent=2, default=float) + "\n")

    for symbol, record in results.items():
        print(f"\n{symbol}  {record['first_month']} -> {record['last_month']}  PASSES={record['passes']}")
        for bps, entry in record["costs"].items():
            print(f"  {bps:>3}bps  alpha {entry['alpha_annual']:+.2%}/yr  t {entry['alpha_t']:+.2f}  p {entry['alpha_p']:.4f}  beta {entry['beta']:.2f}")
        for name, win in record["costs"]["10"]["windows"].items():
            s, b = win["strategy"], win["beta_matched_blend"]
            print(f"    10bps {name:10s} CAGR {s['cagr']:+.2%} vs blend {b['cagr']:+.2%} | Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}"
                  f" | maxDD {s['max_drawdown']:+.1%} vs {b['max_drawdown']:+.1%} | worst mo {s['worst_month']:+.1%} | skew {s['skew']:+.2f} | alpha {win['alpha_annual']:+.2%}")
        print("   criteria:", record["registered_criteria"])
        print("   LOYO:", record["costs"]["10"]["leave_one_year_out"], "| worst5:", record["costs"]["10"]["worst_five_months_vs_blend"]["sum"], "of", record["costs"]["10"]["worst_five_months_vs_blend"]["total_excess_vs_blend"])
    print("\nplacebo:", summary["placebo"])
    print("variance premium:", json.dumps(vrp, indent=0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
