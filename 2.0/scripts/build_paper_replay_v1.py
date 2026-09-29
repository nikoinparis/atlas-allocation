#!/usr/bin/env python3
"""What-if replay: $10,000 in each strategy from its start, marked daily.

This answers "if we had run it live from the start, what would we have by now"
using only books that were already decided before the days they are marked on:

- the six dashboard strategies hold their 2026-08-07 book (the last one their
  backtests decided) unchanged, as a buy-and-hold position that drifts with prices;
- the forward clocks follow the target weights recorded in their hash-chained
  decision logs, rebalancing at each recorded decision's close and paying that
  record's modeled cost. A missed decision (2026-09-18) is treated as "kept the
  previous book", which is what a live account would have done by default.

It is a replay computed after the fact, so it is NOT forward evidence and is never
written into any forward log. It reads those logs; it does not touch them.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "evidence/dashboard_last_books_v1/last_books.csv"
INVENTORY = ROOT / "data/sec_broad_panel_inputs_v3/price_source_inventory.csv"
OUTPUT = ROOT / "evidence/paper_replay_v1"
NOTIONAL = 10_000.0
FINANCING_ANNUAL = 0.05          # the levered books' own stated rate on borrowed cash
BENCHMARKS = ["SPY", "QQQ"]
ETF_CLOCKS = {"breadth_confirmed_trend_return_ceiling_v3", "past_only_consensus_selector_return_v1",
              "return_first_60_40_blend_v1", "covariance_minimum_variance_v1"}

DASHBOARD_LABELS = {
    "sec-residual-controlled-1.25x-5pct-v1": "Residual-Controlled 1.25x",
    "sec-sector-ensemble-fragile-1.35x-v1": "Sector Ensemble 1.35x",
    "sec-sector-aware-signal-ensemble-v1": "Sector-Aware Ensemble",
    "sec-cash-conversion-breadth20-dynamic-v1": "Cash Conversion B20",
    "sec-growth-survivorship-aware-v1": "Growth Top-Five",
    "candidate-return-first-60-40-forward-v1": "ETF 60/40 (dashboard)",
}
CLOCKS = {
    "breadth_confirmed_trend_return_ceiling_v3": "Breadth-Confirmed Trend (clock)",
    "past_only_consensus_selector_return_v1": "Past-Only Consensus (clock)",
    "return_first_60_40_blend_v1": "60/40 Blend (clock)",
    "covariance_minimum_variance_v1": "Minimum Variance (clock)",
    "valuation_earnings_yield_v1": "Valuation Earnings Yield (clock)",
    "sue_quarterly_v1": "SUE Quarterly (clock)",
}


def last_closed_session(now: datetime) -> pd.Timestamp:
    """The latest US session whose 16:00 ET close (21:00 UTC, conservatively) has passed."""
    day = pd.Timestamp(now.date())
    if now.hour < 21:
        day -= pd.Timedelta(days=1)
    while day.weekday() > 4:
        day -= pd.Timedelta(days=1)
    return day


def cik_tickers() -> dict[str, str]:
    inventory = pd.read_csv(INVENTORY, dtype={"cik10": str})
    inventory = inventory[inventory["kind"] == "price"]
    return {row.cik10: Path(str(row.path)).name.split(".", 1)[0] for row in inventory.itertuples()}


def segments() -> dict[str, list[tuple[pd.Timestamp, dict[str, float], float]]]:
    plans: dict[str, list] = {}
    books = pd.read_csv(BOOKS)
    for strategy, group in books.groupby("strategy_id"):
        weights = {str(r.symbol): float(r.weight) for r in group.itertuples()}
        plans[strategy] = [(pd.Timestamp(group["as_of"].iloc[0]), weights, 0.0)]
    tickers = cik_tickers()
    for clock in CLOCKS:
        rows = [json.loads(line) for line in (ROOT / f"evidence/forward_{clock}/decisions.jsonl").read_text().splitlines() if line.strip()]
        plan = []
        for row in rows:
            weights = {tickers.get(k, k): float(v) for k, v in row["target_weights"].items()}
            plan.append((pd.Timestamp(row["decision_date"]), weights, float(row.get("modeled_cost") or 0.0)))
        plans[clock] = plan
    return plans


def replay(plan, closes: pd.DataFrame, end: pd.Timestamp) -> tuple[pd.DataFrame, list[str]]:
    dates = closes.index[(closes.index >= plan[0][0]) & (closes.index <= end)]
    nav, units, cash, levered = NOTIONAL, {}, 0.0, False
    rows, unpriced = [], set()
    starts = {d: (w, c) for d, w, c in plan}
    previous = None
    for day in dates:
        if previous is not None:
            if cash < 0:                                  # borrowed cash accrues financing daily
                cash *= 1 + FINANCING_ANNUAL / 252
            value = cash + sum(count * closes.at[day, symbol] for symbol, count in units.items())
            rows.append({"date": day, "nav": value, "daily_pnl": value - nav, "daily_return": value / nav - 1})
            nav = value
        if day in starts:                                 # rebalance at this close
            weights, cost = starts[day]
            nav *= (1 - cost)
            units, cash = {}, 0.0
            for symbol, weight in weights.items():
                if symbol.startswith("cash"):
                    cash += weight * nav
                elif symbol in closes.columns and pd.notna(closes.at[day, symbol]):
                    units[symbol] = weight * nav / closes.at[day, symbol]
                else:
                    unpriced.add(symbol)
                    cash += weight * nav                  # unpriced name held as flat cash, and reported
        previous = day
    return pd.DataFrame(rows), sorted(unpriced)


def write_dashboard_payload(daily: pd.DataFrame, summary: list[dict], closes: pd.DataFrame, end: pd.Timestamp) -> None:
    """One group per shared start date, so every line in a chart starts at the same $10,000."""
    rows = {row["strategy"]: row for row in summary if row["kind"] != "benchmark"}
    groups = []
    for start in sorted({row["start"] for row in rows.values()}):
        members = [key for key, row in rows.items() if row["start"] == start]
        kind = "dashboard" if all(k in DASHBOARD_LABELS for k in members) else "clocks"
        strategies = []
        for key in sorted(members, key=lambda k: -rows[k]["final_value"]):
            frame = daily[daily["strategy"] == key]
            strategies.append({
                **{k: v for k, v in rows[key].items() if k != "strategy"}, "id": key,
                "daily": [{"date": start, "nav": NOTIONAL, "pnl": 0.0, "ret": 0.0}] + [
                    {"date": r.date, "nav": round(r.nav, 2), "pnl": round(r.daily_pnl, 2), "ret": r.daily_return}
                    for r in frame.itertuples()],
            })
        benchmarks = {}
        for symbol in BENCHMARKS:
            window = closes[symbol].loc[start:end].dropna()
            benchmarks[symbol] = [{"date": d.strftime("%Y-%m-%d"), "nav": round(NOTIONAL * v / window.iloc[0], 2)} for d, v in window.items()]
        title = ("Dashboard strategies" if kind == "dashboard"
                 else "ETF clocks" if all(k in ETF_CLOCKS for k in members) else "Stock clocks")
        groups.append({"id": f"{kind}-{start}", "title": title, "start": start, "strategies": strategies, "benchmarks": benchmarks})
    payload = {
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(), "through": str(end.date()), "notional": NOTIONAL,
        "whatThisIs": "A what-if replay: $10,000 in each strategy, marked on every trading day since its start, using only books decided before the days they are marked on.",
        "whatThisIsNot": "Forward evidence. It is computed after the fact, so it cannot prove nothing was chosen with hindsight, and it is never written into the hash-chained forward logs.",
        "method": "Dashboard strategies hold their 2026-08-07 book unchanged, drifting with prices; their weekly sleeve and leverage overlays are not replayed. Clocks follow the target weights in their decision logs and pay each record's modeled cost. The missed 2026-09-18 decision keeps the previous book, as a live account would. Levered books pay 5% a year on borrowed cash. Prices are Yahoo daily closes, dividend-adjusted.",
        "groups": groups,
    }
    (ROOT / "dashboard/public/paper-replay.json").write_text(json.dumps(payload, separators=(",", ":")) + "\n")


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    end = last_closed_session(datetime.now(timezone.utc))
    plans = segments()
    symbols = sorted({s for plan in plans.values() for _, w, _ in plan for s in w if not s.startswith("cash")} | set(BENCHMARKS))
    first = min(plan[0][0] for plan in plans.values())
    raw = yf.download(symbols, start=str((first - pd.Timedelta(days=7)).date()), end=str((end + pd.Timedelta(days=1)).date()),
                      interval="1d", auto_adjust=True, progress=False, threads=True)["Close"]
    closes = raw.sort_index().ffill(limit=3)          # a halted day carries its last price, never more than 3
    closes.index = pd.to_datetime(closes.index).tz_localize(None)

    frames, summary = [], []
    labels = {**DASHBOARD_LABELS, **CLOCKS}
    for key, plan in plans.items():
        frame, unpriced = replay(plan, closes, end)
        if frame.empty:
            continue
        frame.insert(0, "strategy", key)
        frames.append(frame)
        gains = frame["daily_pnl"]
        summary.append({
            "strategy": key, "label": labels.get(key, key),
            "kind": "dashboard held book" if key in DASHBOARD_LABELS else "forward clock decisions",
            "start": str(plan[0][0].date()), "end": str(frame["date"].iloc[-1].date()), "days": int(len(frame)),
            "rebalances": int(len(plan) - 1), "final_value": float(frame["nav"].iloc[-1]),
            "total_pnl": float(frame["nav"].iloc[-1] - NOTIONAL), "total_return": float(frame["nav"].iloc[-1] / NOTIONAL - 1),
            "up_days": int((gains > 0).sum()), "best_day": float(frame["daily_return"].max()),
            "worst_day": float(frame["daily_return"].min()),
            "max_drawdown": float((frame["nav"] / frame["nav"].cummax().clip(lower=NOTIONAL) - 1).min()),
            "unpriced_held_as_cash": unpriced,
        })
    for symbol in BENCHMARKS:
        for start in sorted({s["start"] for s in summary}):
            window = closes[symbol].loc[start:end].dropna()
            summary_key = f"{symbol}_from_{start}"
            summary.append({"strategy": summary_key, "label": f"{symbol} from {start}", "kind": "benchmark",
                            "start": start, "end": str(window.index[-1].date()),
                            "total_return": float(window.iloc[-1] / window.iloc[0] - 1),
                            "final_value": float(NOTIONAL * window.iloc[-1] / window.iloc[0])})

    daily = pd.concat(frames, ignore_index=True)
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily.to_csv(OUTPUT / "daily_nav.csv", index=False)
    (OUTPUT / "summary.json").write_text(json.dumps({
        "what_this_is": "a what-if replay of already-decided books, marked daily with $10,000 each",
        "what_this_is_not": "forward evidence; it is computed after the fact and is never written into a forward log",
        "missed_decision_treatment": "a missed weekly decision keeps the previous book, as a live account would",
        "prices": "Yahoo daily closes, dividend-adjusted",
        "through": str(end.date()), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "strategies": summary,
    }, indent=2) + "\n")
    write_dashboard_payload(daily, summary, closes, end)
    for row in summary:
        print(f"{row['label']:36s} {row['start']} -> {row['end']}  ${row['final_value']:>9,.0f}  {row['total_return']:+.2%}"
              + (f"  worst day {row['worst_day']:+.2%}  unpriced {row['unpriced_held_as_cash']}" if 'worst_day' in row else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
