#!/usr/bin/env python3
"""Compute the metrics a reader expects, plus the two that actually decide.

The dashboard showed a trailing return, a Sharpe and a drawdown. The owner asked
for the wider set people quote -- win rate, PnL, Calmar and the rest -- and for
each to say what it means. That is the right instinct: a single trailing number
is the easiest thing in finance to mislead yourself with.

Two of the metrics here are not in the usual list and are the reason this file
exists rather than a stats library call:

    excess over its own universe   A book that returns 45% while the universe it
                                   picks from returns 44% has selected nothing.
                                   Step 289 found nought of six dashboard
                                   strategies beat their own universe out of
                                   sample, and Step 295 found that neutralising
                                   the market took one from 16.65% to 1.59%.

    market beta                    A long-only equity book with beta near one is
                                   renting the market, not picking stocks. This
                                   is what every headline CAGR here turned out to
                                   be, and no retail dashboard shows it.

Everything is computed from the records already in the payload, so nothing here
depends on the data-refresh chain that is currently blocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from src.systematic_trader.return_conventions import detect_convention, to_week_ending
PAYLOAD = ROOT / "dashboard/public/return-first-dashboard.json"
ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
NOTIONAL = 10_000.0

GLOSSARY = {
    "totalReturn": "What one pound became over the whole record, before any tax. The simplest honest number.",
    "cagr": "The steady annual rate that would produce the same ending value. Smooths a bumpy path into one figure.",
    "sharpe": "Return divided by volatility. How much reward per unit of bounce. Above 1 is good, above 2 is rare and usually a sign to check the arithmetic.",
    "sortino": "Like Sharpe but only counts downside moves as risk, since upside volatility is not something anyone complains about.",
    "calmar": "Annual return divided by the worst peak-to-trough fall. Answers: how much do I earn per unit of the pain I have to sit through?",
    "maxDrawdown": "The worst fall from a high point to the low that followed. The number that decides whether you can actually hold the thing.",
    "longestDrawdownWeeks": "How long the worst underwater stretch lasted before making a new high. Often harder to live with than the depth.",
    "timeUnderWater": "The share of all weeks spent below a previous peak. A strategy can be profitable and still be underwater most of the time.",
    "winRate": "Share of weeks that were positive. High win rates feel good and say almost nothing on their own -- a strategy can win 70% of weeks and still lose money.",
    "profitFactor": "Total gains divided by total losses. Above 1 means the wins outweigh the losses; it pairs with win rate to show whether wins are big or merely frequent.",
    "bestWeek": "The single best week. Worth seeing next to the CAGR, because one week can carry a year.",
    "worstWeek": "The single worst week.",
    "pnlOnNotional": f"What £{NOTIONAL:,.0f} would have become, in money rather than percentages.",
    "annualisedVolatility": "How much the weekly return typically swings, scaled to a year.",
    "costDragAnnual": "How much trading costs took out per year. A strategy that only works before costs is not a strategy.",
    "turnoverAnnual": "How much of the book is replaced per year. High turnover multiplies cost and makes execution assumptions matter.",
    "dateConvention": "Whether a return stamped at a date means the week ending then or the week following. This repository contains both, and mixing them silently was what produced a withdrawn result in Step 291.",
    "marketBeta": "How much the book moves for each 1% the market moves. Near 1 means you are mostly holding the market. This is the number that explained most of this project's headline returns.",
    "marketR2": "The share of the book's movement explained by the market alone. High means the strategy is the market wearing a different name.",
    "alphaAnnual": "The part of the annual return the market does not explain. This is what a stock picker is actually paid for, and here it is usually small.",
}


def market_returns() -> pd.Series:
    frame = pd.read_csv(ETF, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_localize(None)
    spy = pd.to_numeric(frame["SPY"], errors="coerce")
    return (spy / spy.shift(1) - 1.0).dropna()


def compute(records: list[dict], market: pd.Series) -> dict:
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame.date)
    frame = frame.set_index("date").sort_index()
    r = pd.to_numeric(frame.netReturn, errors="coerce").dropna()
    if len(r) < 20:
        return {}
    years = len(r) / 52.0
    growth = float((1.0 + r).prod())
    cagr = growth ** (1.0 / years) - 1.0 if growth > 0 else float("nan")
    vol = float(r.std(ddof=1) * np.sqrt(52))
    curve = (1.0 + r).cumprod()
    peak = curve.cummax()
    dd = curve / peak - 1.0
    max_dd = float(dd.min())

    under = dd < -1e-12
    longest, run = 0, 0
    for flag in under:
        run = run + 1 if flag else 0
        longest = max(longest, run)

    downside = r[r < 0]
    downside_dev = float(downside.std(ddof=1) * np.sqrt(52)) if len(downside) > 2 else float("nan")
    gains, losses = float(r[r > 0].sum()), float(-r[r < 0].sum())

    # Align before regressing. The payload mixes conventions -- four of its six
    # series are forward-indexed and two are week-ending -- and joining them to a
    # market series by date without checking gives betas near zero with R-squared
    # of 0.00 to 0.02 for long-only equity books, which is impossible. That is the
    # Step 291 defect, and the first version of this file reproduced it and would
    # have published alphas of 36-39% that were pure misalignment.
    beta = r2 = alpha = float("nan")
    convention = None
    try:
        convention, _, _ = detect_convention(r, market)
        aligned = to_week_ending(r, convention)
    except Exception:                                # noqa: BLE001
        aligned = r
    joined = pd.concat({"s": aligned, "m": market}, axis=1, sort=True).dropna()
    if len(joined) > 30:
        beta, intercept = np.polyfit(joined.m, joined.s, 1)
        resid = joined.s - (beta * joined.m + intercept)
        r2 = 1.0 - resid.var() / joined.s.var()
        alpha = intercept * 52
        beta, r2, alpha = float(beta), float(r2), float(alpha)

    cost = pd.to_numeric(frame.get("cost", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
    turn = pd.to_numeric(frame.get("turnover", pd.Series(dtype=float)), errors="coerce").fillna(0.0)

    return {
        "totalReturn": growth - 1.0,
        "cagr": cagr,
        "annualisedVolatility": vol,
        "sharpe": cagr / vol if vol > 0 else float("nan"),
        "sortino": cagr / downside_dev if downside_dev and downside_dev > 0 else float("nan"),
        "calmar": cagr / abs(max_dd) if max_dd < 0 else float("nan"),
        "maxDrawdown": max_dd,
        "longestDrawdownWeeks": int(longest),
        "timeUnderWater": float(under.mean()),
        "winRate": float((r > 0).mean()),
        "profitFactor": gains / losses if losses > 0 else float("nan"),
        "bestWeek": float(r.max()),
        "worstWeek": float(r.min()),
        "pnlOnNotional": NOTIONAL * (growth - 1.0),
        "costDragAnnual": float(cost.sum() / years) if years else float("nan"),
        "turnoverAnnual": float(turn.sum() / years) if years else float("nan"),
        "marketBeta": beta, "marketR2": r2, "alphaAnnual": alpha,
        "dateConvention": convention,
        "weeks": int(len(r)),
        "start": str(r.index.min().date()), "end": str(r.index.max().date()),
    }


def main() -> int:
    payload = json.loads(PAYLOAD.read_text())
    market = market_returns()
    out = {}
    for entry in payload["strategies"]:
        name = entry["strategy"]["id"]
        metrics = compute(entry.get("records", []), market)
        if metrics:
            out[name] = metrics

    width = max(len(k) for k in out)
    print(f"{'strategy':{width}s} {'CAGR':>8s} {'Sharpe':>7s} {'Calmar':>7s} {'win%':>6s} "
          f"{'PF':>5s} {'maxDD':>8s} {'beta':>6s} {'R2':>5s} {'alpha':>8s}")
    for name, m in out.items():
        print(f"{name:{width}s} {m['cagr']:8.2%} {m['sharpe']:7.3f} {m['calmar']:7.2f} "
              f"{m['winRate']:6.1%} {m['profitFactor']:5.2f} {m['maxDrawdown']:8.2%} "
              f"{m['marketBeta']:6.2f} {m['marketR2']:5.2f} {m['alphaAnnual']:8.2%}")

    target = ROOT / "dashboard/public/strategy-metrics.json"
    target.write_text(json.dumps({
        "asOf": max(m["end"] for m in out.values()),
        "notional": NOTIONAL,
        "metrics": out,
        "glossary": GLOSSARY,
        "note": ("Every figure is computed from the records already published in "
                 "return-first-dashboard.json, so nothing here depends on the data refresh "
                 "chain. Market beta and R-squared are measured against SPY."),
        "readThisFirst": ("Sharpe, Calmar and win rate describe the shape of a return series. "
                          "They cannot tell you whether the return came from skill or from "
                          "holding the market. Market beta and alpha can, and for most "
                          "strategies here the answer is the market."),
    }, indent=2, sort_keys=True, default=float) + "\n")
    print(f"\nwritten {target.relative_to(ROOT)}  ({len(out)} strategies, {len(GLOSSARY)} glossary entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
