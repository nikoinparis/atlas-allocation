#!/usr/bin/env python3
"""Atlas Offensive R00 — per-instrument cost library v1.

Measures effective bid-ask spreads for the 35-ETF traded universe (includes
SPY/QQQ) and retires the 10 bps flat one-way assumption for Atlas Offensive
research runs.

Primary measurement: quiet-minute range proxy. In a quiet minute the traded
high-low range of a liquid ETF collapses toward its bid-ask spread, so the
10th percentile of regular-trading-hours 1-minute (high-low)/mid over recent
sessions is a tight upper bound on the effective spread. Daily-bar estimators
(Corwin-Schultz 2012 with overnight-gap adjustment, Abdi-Ranaldo 2017, Roll
1984) cannot resolve spreads below ~10 bps and are recorded as labeled upper
bounds only. A closing-quote NBBO snapshot is recorded and used when it is
valid and tighter than the minute proxy.

Recommended one-way cost = max(floor, min(quiet-minute proxy, valid quote)/2).

Holdout note (see offensive_holdout_declaration.md): daily estimators use the
pre-holdout 2024-01-01..2025-12-31 window; minute bars and quotes are
current-market microstructure measurements, which the declaration explicitly
permits because spread widths carry no forward return information.

Live measured fills (R46) supersede this file.

Output: data/research/atlas_offensive_cost_library.csv
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_HUB = ROOT / "data" / "01_data_hub"
OUT_PATH = ROOT / "data" / "research" / "atlas_offensive_cost_library.csv"

DAILY_START = "2024-01-01"
DAILY_END = "2025-12-31"  # pre-holdout window for daily estimators
MEASURED_DATE = "2026-07-21"
RETIRED_FLAT_BPS = 10.0
ONE_WAY_FLOOR_BPS = 0.25
QUOTE_PLAUSIBLE_MAX = 0.002  # reject stale/after-hours quotes wider than 20 bps


def gap_adjust(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Corwin-Schultz overnight adjustment: shift each day's log range onto prior close."""
    h, l, c = np.log(high), np.log(low), np.log(close)
    h_adj, l_adj = h.copy(), l.copy()
    for t in range(1, len(h)):
        if l[t] > c[t - 1]:
            g = l[t] - c[t - 1]
            h_adj[t] -= g
            l_adj[t] -= g
        elif h[t] < c[t - 1]:
            g = h[t] - c[t - 1]
            h_adj[t] -= g
            l_adj[t] -= g
    return h_adj, l_adj


def corwin_schultz_spread(h: np.ndarray, l: np.ndarray) -> float:
    hl_sq = (h - l) ** 2
    beta = hl_sq[:-1] + hl_sq[1:]
    h2 = np.maximum(h[:-1], h[1:])
    l2 = np.minimum(l[:-1], l[1:])
    gamma = (h2 - l2) ** 2
    denom = 3.0 - 2.0 * np.sqrt(2.0)
    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)
    alpha = np.maximum(alpha, 0.0)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    spread = spread[np.isfinite(spread)]
    return float(np.mean(spread)) if spread.size else np.nan


def abdi_ranaldo_spread(c_log: np.ndarray, h: np.ndarray, l: np.ndarray) -> float:
    eta = (h + l) / 2.0
    s_sq = 4.0 * (c_log[:-1] - eta[:-1]) * (c_log[:-1] - eta[1:])
    s_sq = s_sq[np.isfinite(s_sq)]
    if not s_sq.size:
        return np.nan
    return float(np.sqrt(max(np.mean(s_sq), 0.0)))


def roll_spread(adj_close: pd.Series) -> float:
    dp = np.diff(np.log(adj_close.dropna().values))
    if dp.size < 60:
        return np.nan
    cov = np.cov(dp[:-1], dp[1:])[0, 1]
    if cov >= 0:
        return np.nan
    return float(2.0 * np.sqrt(-cov))


def quiet_minute_proxy(minute_df: pd.DataFrame) -> tuple[float, float, int]:
    """(P10, P50, n) of RTH 1-minute (high-low)/mid — spread proxy in decimal."""
    df = minute_df.dropna(subset=["High", "Low"])
    if df.empty:
        return np.nan, np.nan, 0
    idx = df.index.tz_convert("America/New_York")
    rth = df[(idx.time >= pd.Timestamp("09:35").time()) & (idx.time <= pd.Timestamp("15:55").time())]
    if len(rth) < 200:
        return np.nan, np.nan, len(rth)
    mid = (rth["High"] + rth["Low"]) / 2.0
    rel_range = ((rth["High"] - rth["Low"]) / mid).values
    rel_range = rel_range[np.isfinite(rel_range) & (rel_range >= 0)]
    return float(np.percentile(rel_range, 10)), float(np.percentile(rel_range, 50)), len(rel_range)


def closing_quote(ticker: str) -> float:
    import yfinance as yf

    try:
        info = yf.Ticker(ticker).info
        bid, ask = info.get("bid"), info.get("ask")
        if not bid or not ask or bid <= 0 or ask <= bid:
            return np.nan
        spread = (ask - bid) / ((bid + ask) / 2.0)
        return spread if spread < QUOTE_PLAUSIBLE_MAX else np.nan
    except Exception:
        return np.nan


def main() -> None:
    import yfinance as yf

    universe = json.load(open(DATA_HUB / "universe.json"))
    tickers = universe["all"]
    asset_class = universe["asset_class_map"]

    daily = yf.download(
        tickers, start=DAILY_START, end="2026-01-01",
        progress=False, auto_adjust=False, group_by="ticker",
    )
    minute = yf.download(
        tickers, interval="1m", period="5d",
        progress=False, auto_adjust=False, group_by="ticker", prepost=False,
    )
    repo_close = pd.read_csv(DATA_HUB / "daily_prices.csv", index_col=0, parse_dates=True)
    repo_close = repo_close.loc[DAILY_START:DAILY_END]

    rows = []
    for ticker in tickers:
        try:
            ddf = daily[ticker].dropna(subset=["High", "Low", "Close"])
        except KeyError:
            ddf = pd.DataFrame()
        ddf = ddf[ddf.index <= DAILY_END]
        cs = ar = np.nan
        if len(ddf) >= 120:
            h_adj, l_adj = gap_adjust(ddf["High"].values, ddf["Low"].values, ddf["Close"].values)
            cs = corwin_schultz_spread(h_adj, l_adj)
            ar = abdi_ranaldo_spread(np.log(ddf["Close"].values), h_adj, l_adj)
        roll = roll_spread(repo_close[ticker]) if ticker in repo_close.columns else np.nan

        try:
            p10, p50, n_min = quiet_minute_proxy(minute[ticker])
        except KeyError:
            p10, p50, n_min = np.nan, np.nan, 0
        quote = closing_quote(ticker)

        # P10==0 means single-trade minutes dominate (range understates spread) -> fall back to P50
        if np.isfinite(p10) and p10 > 0:
            p_eff, p_label = p10, "QUIET_MINUTE_PROXY"
        elif np.isfinite(p50) and p50 > 0:
            p_eff, p_label = p50, "QUIET_MINUTE_P50_FALLBACK"
        else:
            p_eff, p_label = np.nan, ""
        candidates = [v for v in (p_eff, quote) if np.isfinite(v)]
        if candidates:
            full_spread = min(candidates)
            quality = "MEASURED_QUOTE" if (np.isfinite(quote) and quote <= (p_eff if np.isfinite(p_eff) else np.inf)) else p_label
        elif np.isfinite(cs) or np.isfinite(ar):
            full_spread = np.nanmin([cs, ar])
            quality = "DAILY_ESTIMATOR_UPPER_BOUND"
        else:
            full_spread = np.nan
            quality = "UNMEASURED"
        one_way = max(full_spread / 2.0, ONE_WAY_FLOOR_BPS / 1e4) if np.isfinite(full_spread) else np.nan

        rows.append(
            {
                "ticker": ticker,
                "asset_class": asset_class.get(ticker, ""),
                "quiet_minute_p10_spread_bps": round(p10 * 1e4, 2) if np.isfinite(p10) else "",
                "quiet_minute_p50_range_bps": round(p50 * 1e4, 2) if np.isfinite(p50) else "",
                "minute_bars_used": n_min,
                "closing_quote_spread_bps": round(quote * 1e4, 2) if np.isfinite(quote) else "",
                "cs_daily_upper_bound_bps": round(cs * 1e4, 2) if np.isfinite(cs) else "",
                "ar_daily_upper_bound_bps": round(ar * 1e4, 2) if np.isfinite(ar) else "",
                "roll_crosscheck_bps": round(roll * 1e4, 2) if np.isfinite(roll) else "",
                "est_full_spread_bps": round(full_spread * 1e4, 2) if np.isfinite(full_spread) else "",
                "one_way_cost_bps": round(one_way * 1e4, 2) if np.isfinite(one_way) else "",
                "one_way_cost_2x_bps": round(one_way * 2e4, 2) if np.isfinite(one_way) else "",
                "commission_usd": 0.0,
                "cost_quality": quality,
                "daily_estimator_window": f"{DAILY_START}..{DAILY_END}",
                "minute_window": "last 5 sessions to 2026-07-21",
                "measured_date": MEASURED_DATE,
                "retired_assumption_bps": RETIRED_FLAT_BPS,
                "notes": "one_way=max(floor 0.25bp, min(quiet-minute P10, valid close quote)/2); superseded by live fills in R46",
            }
        )

    out = pd.DataFrame(rows)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)} ({len(out)} instruments)")
    print(
        out[
            [
                "ticker",
                "quiet_minute_p10_spread_bps",
                "closing_quote_spread_bps",
                "cs_daily_upper_bound_bps",
                "one_way_cost_bps",
                "cost_quality",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
