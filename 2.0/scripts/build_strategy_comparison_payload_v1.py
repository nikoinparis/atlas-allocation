#!/usr/bin/env python3
"""Side-by-side comparison of every dashboard strategy, for the /compare page.

Three windows per strategy, kept apart because they mean different things:

    common backtest   2023-01-06 to 2026-08-07, the one window all five books
                      share, from each book's published weekly net path (50 bps).
                      The 60/40's own history runs from 2005 and is longer, which
                      flatters nothing but makes a full-history CAGR incomparable.
    break split       the same path before and after 2025-04-04 (Step 261's date).
    since creation    every book was created between 2026-08-14 and 2026-08-26 on
                      data ending 2026-08-07. This marks the last decided book
                      (evidence/dashboard_last_books_v1) DAILY at fresh Yahoo
                      closes to the latest completed session, held: no
                      rebalancing, no costs, no financing. It is what the book did
                      after the strategy existed, not what the strategy would have
                      done -- each would have rebalanced at least once since.

Nothing here can change a frozen config, a strategy, or a forward record.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "dashboard/public/return-first-dashboard.json"
METRICS = ROOT / "dashboard/public/strategy-metrics.json"
BOOKS = ROOT / "evidence/dashboard_last_books_v1/last_books.csv"
TARGET = ROOT / "dashboard/public/strategy-comparison.json"
EVIDENCE = ROOT / "evidence/strategy_comparison_v1"
COMMON_START, COMMON_END, BREAK = "2023-01-06", "2026-08-07", "2025-04-04"
BENCHMARK = "SPY"
CREATED = {  # first commit of each strategy's evidence directory
    "sec-residual-controlled-1x-v1": "2026-08-23",
    "candidate-return-first-60-40-forward-v1": "2026-08-14",
    "sec-growth-survivorship-aware-v1": "2026-08-14",
    "sec-cash-conversion-breadth20-dynamic-v1": "2026-08-14",
    "sec-sector-aware-signal-ensemble-v1": "2026-08-26",
}


def path_metrics(r: pd.Series, periods: float) -> dict:
    r = r.dropna()
    if len(r) < 2:
        return {}
    wealth = (1 + r).cumprod()
    years = len(r) / periods
    cagr = float(wealth.iloc[-1] ** (1 / years) - 1)
    vol = float(r.std(ddof=1) * np.sqrt(periods))
    return {"periods": int(len(r)), "totalReturn": float(wealth.iloc[-1] - 1), "cagr": cagr,
            "volatility": vol, "sharpe": cagr / vol if vol > 0 else None,
            "maxDrawdown": float((wealth / wealth.cummax() - 1).min()),
            "winRate": float((r > 0).mean())}


def weekly_path(item: dict) -> pd.Series:
    rows = item["records"]
    return pd.Series({pd.Timestamp(x["date"]): float(x["netReturn"]) for x in rows}).sort_index()


def fetch(symbols: list[str]) -> pd.DataFrame:
    end = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=1)).date().isoformat()
    frame = yf.download(sorted(symbols), start="2026-08-01", end=end, auto_adjust=True,
                        progress=False, threads=True)["Close"]
    frame.index = pd.to_datetime(frame.index).tz_localize(None).normalize()
    now = datetime.now(timezone.utc)
    if frame.index[-1].date() >= now.date() and now.hour < 21:   # today's session not closed
        frame = frame[frame.index.date < now.date()]
    return frame


def main() -> int:
    payload = json.loads(PAYLOAD.read_text())["strategies"]
    metrics = json.loads(METRICS.read_text())["metrics"]
    books = pd.read_csv(BOOKS)
    books = books[~books.symbol.str.startswith("cash::")]       # cash is the residual below
    prices = fetch(sorted(set(books.symbol) | {BENCHMARK}))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    prices.to_csv(EVIDENCE / "daily_prices.csv")
    last = prices.index[-1]

    out, curves = [], {}
    for item in payload:
        sid = item["strategy"]["id"]
        weekly = weekly_path(item)
        common = weekly[(weekly.index >= COMMON_START) & (weekly.index <= COMMON_END)]
        before, after = common[common.index < BREAK], common[common.index >= BREAK]

        book = books[books.strategy_id == sid]
        as_of = pd.Timestamp(book.as_of.iloc[0])
        block = prices[prices.index >= as_of]
        value = pd.Series(1.0 - book.weight.sum(), index=block.index)       # uninvested cash
        contrib = {}
        for row in book.itertuples():
            series = block[row.symbol].ffill()
            rel = series / series.iloc[0]
            value += row.weight * rel
            contrib[row.symbol] = float(row.weight * (rel.iloc[-1] - 1))
        daily = value.pct_change().dropna()
        spy = block[BENCHMARK] / block[BENCHMARK].iloc[0]
        top = max(contrib, key=contrib.get)
        curves[sid] = value - 1

        since = path_metrics(daily, 252.0)
        since.update({
            "created": CREATED.get(sid), "bookAsOf": str(as_of.date()), "through": str(last.date()),
            "tradingDays": int(len(daily)), "spyReturn": float(spy.iloc[-1] - 1),
            "excessVsSpy": float(value.iloc[-1] - spy.iloc[-1]),
            "upDays": int((daily > 0).sum()), "downDays": int((daily < 0).sum()),
            "bestDay": float(daily.max()), "worstDay": float(daily.min()),
            "topContributor": top, "topContribution": float(contrib[top]),
            "returnWithoutTop": float(value.iloc[-1] - 1 - contrib[top]),
            "names": int(len(book)), "largestWeight": float(book.weight.max()),
            "largestWeightSymbol": str(book.loc[book.weight.idxmax(), "symbol"]),
        })
        bm = item["strategy"].get("betaMatched", {})
        m = metrics.get(sid, {})
        out.append({
            "id": sid, "name": item["strategy"]["name"], "subtitle": item["strategy"]["subtitle"],
            "commonBacktest": path_metrics(common, 52.0),
            "beforeBreak": path_metrics(before, 52.0), "afterBreak": path_metrics(after, 52.0),
            "fullHistory": {"start": m.get("start"), "cagr": m.get("cagr"), "sharpe": m.get("sharpe"),
                            "maxDrawdown": m.get("maxDrawdown"), "marketBeta": m.get("marketBeta"),
                            "turnoverAnnual": m.get("turnoverAnnual"), "costDragAnnual": m.get("costDragAnnual")},
            "sameRiskAlpha": {"alpha": bm.get("alphaFull"), "pValue": bm.get("pValue"),
                              "before": bm.get("alphaBeforeBreak"), "after": bm.get("alphaAfterBreak"),
                              "passed": bm.get("passed")},
            "sinceCreation": since,
        })

    curves_frame = pd.DataFrame(curves)
    curves_frame[BENCHMARK] = prices[BENCHMARK][prices.index >= curves_frame.index[0]] / \
        prices[BENCHMARK][prices.index >= curves_frame.index[0]].iloc[0] - 1
    curves_frame.to_csv(EVIDENCE / "daily_cumulative.csv")
    bundle = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "through": str(last.date()),
        "commonWindow": [COMMON_START, COMMON_END], "breakDate": BREAK, "benchmark": BENCHMARK,
        "strategies": out,
        "daily": {"dates": [d.strftime("%Y-%m-%d") for d in curves_frame.index],
                  "series": {k: [None if pd.isna(v) else round(float(v), 6) for v in curves_frame[k]]
                             for k in curves_frame.columns}},
        "readThisFirst": ("Backtest columns are research paths chosen on the window they report. "
                          "'Since creation' holds each strategy's last decided book from 2026-08-07, "
                          "marked daily with no rebalancing, costs or financing. None of these books "
                          "uses leverage or short positions."),
        "liveTradingEnabled": False,
    }
    TARGET.write_text(json.dumps(bundle, indent=1) + "\n")
    (EVIDENCE / "summary.json").write_text(json.dumps(bundle, indent=1) + "\n")
    for s in out:
        c, sc = s["commonBacktest"], s["sinceCreation"]
        print(f"{s['id'][:40]:40s} common CAGR {c['cagr']:+.1%} Sharpe {c['sharpe']:.2f} DD {c['maxDrawdown']:+.1%} | "
              f"since {sc['bookAsOf']}: {sc['totalReturn']:+.2%} vs SPY {sc['spyReturn']:+.2%}, DD {sc['maxDrawdown']:+.2%}, "
              f"top {sc['topContributor']} {sc['topContribution']:+.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
