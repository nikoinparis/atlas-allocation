#!/usr/bin/env python3
"""Daily what-if histories for the forward clocks: each clock's frozen rule applied to the past,
then its own recorded forward decisions, marked at daily closes through the latest session.

For each clock:
- BACKTEST segment (before its first recorded decision): the clock's own frozen rule, computed
  with the clock's own code where it exists (the recorders' `book_for`, `form_book`, the
  min-variance recorder's `compute_snapshot_state`, Batch 65's `dynamic_weights`) or its frozen
  weights artifact. These rules were chosen after seeing much of this history, so the
  backtest segment is a retrospective illustration, not evidence.
- FORWARD segment (from its first recorded decision): the target weights read from the clock's
  hash-chained decision log. The log is read, never written.

Every book is marked daily: positions drift with daily adjusted closes between rebalances and
trade at the decision day's close. Costs are charged on one-way turnover at each rebalance:
10 bps for the ETF clocks (their protocols state no forward cost), 50 bps for the stock books
(their protocols' own figure), none for the equal-weight benchmark (its recorder charges none).

Prices: the newest ETF snapshot in data/vintages and the newest daily stock history vintage in
data/broad_full_history_price_vintages, spliced by return with Yahoo closes for the days after
those vintages end (only for names held then). The stock histories hold mostly survivors
(44.6% of the 2012 filer roster has prices), so the stock clocks' backtest segments are
flattered; this is stated on the dashboard.

Writes evidence/clock_histories_v1/ and dashboard/public/clock-histories.json. Read-only
against every forward log. Run from the 2.0 directory.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "evidence/clock_histories_v1"
DASH = ROOT / "dashboard/public/clock-histories.json"
CASH = "cash::USD"
ETF_BPS, STOCK_BPS = 10.0, 50.0


# ----------------------------------------------------------------------------- prices

def newest(path: Path) -> Path:
    return sorted(p for p in path.iterdir() if p.is_dir())[-1]


def last_closed_session(now: datetime) -> pd.Timestamp:
    day = pd.Timestamp(now.date())
    if now.hour < 21:
        day -= pd.Timedelta(days=1)
    while day.weekday() > 4:
        day -= pd.Timedelta(days=1)
    return day


class Prices:
    """Daily simple returns by symbol, spliced: vintage returns, then Yahoo returns after."""

    def __init__(self) -> None:
        self.etf_vintage = newest(ROOT / "data/vintages")
        etf = pd.read_csv(self.etf_vintage / "payload/prices.csv",
                          usecols=["observation_date", "ticker", "adjusted_close"])
        etf["observation_date"] = pd.to_datetime(etf.observation_date)
        self.etf = etf.pivot_table(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
        self.stock_vintage = newest(ROOT / "data/broad_full_history_price_vintages")
        catalogue = pd.read_csv(self.stock_vintage / "history_catalogue.csv", dtype={"cik10": str})
        self.cik_symbol = (catalogue.sort_values("rows", ascending=False).drop_duplicates("cik10")
                           .set_index("cik10").symbol.to_dict())
        self.stock_symbols = set(catalogue.symbol)
        self.vintage_end = min(self.etf.index.max(), pd.Timestamp(catalogue["last"].max()))
        self.end = last_closed_session(datetime.now(timezone.utc))
        self.calendar = self.etf["SPY"].dropna().index
        self.returns = pd.DataFrame(index=self.calendar)
        self.topped_up: set[str] = set()

    def symbol(self, key: str) -> str:
        return self.cik_symbol.get(key, key) if key[:1].isdigit() else key

    def ensure(self, symbols: set[str]) -> None:
        need = sorted(s for s in symbols if s != CASH and s not in self.returns.columns)
        if not need:
            return
        cols = {}
        for s in need:
            if s in self.etf.columns:
                series = self.etf[s]
            elif s in self.stock_symbols:
                path = self.stock_vintage / "histories" / f"{s}.csv.gz"
                frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")["adjusted_close"]
                series = frame
            else:
                continue                                    # e.g. DBMF: Yahoo only, added by top_up
            cols[s] = series.pct_change(fill_method=None)
        if cols:
            frame = pd.DataFrame(cols).reindex(self.returns.index.union(pd.DatetimeIndex([])))
            self.returns = pd.concat([self.returns, frame], axis=1)

    def top_up(self, symbols: set[str], full_history: set[str] = frozenset()) -> None:
        """Yahoo returns after the vintage end (and full history for symbols named in full_history)."""
        import yfinance as yf
        wanted = sorted({s for s in symbols if s != CASH} - self.topped_up)
        if not wanted or self.end <= self.vintage_end and not full_history:
            return
        start = pd.Timestamp("2004-12-01") if full_history else self.vintage_end - pd.Timedelta(days=10)
        raw = yf.download(wanted, start=str(start.date()), end=str((self.end + pd.Timedelta(days=1)).date()),
                          interval="1d", auto_adjust=True, progress=False, threads=True)["Close"]
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(wanted[0])
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        yret = raw.sort_index().pct_change(fill_method=None)
        new_days = yret.index[(yret.index > self.vintage_end) & (yret.index <= self.end)]
        calendar = self.returns.index.union(new_days)
        self.returns = self.returns.reindex(calendar)
        for s in wanted:
            if s not in yret.columns:
                continue
            if s in full_history:
                self.returns[s] = yret[s].reindex(calendar)
            else:
                if s not in self.returns.columns:
                    self.returns[s] = np.nan
                self.returns.loc[new_days, s] = yret[s].reindex(new_days).to_numpy()
        self.topped_up |= set(wanted)


# ----------------------------------------------------------------------------- engine

def trading_day_at_or_before(index: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp | None:
    position = index.searchsorted(day, side="right") - 1
    return index[position] if position >= 0 else None


def run_path(events: list[tuple[pd.Timestamp, dict[str, float]]], returns: pd.DataFrame,
             cost_bps: float, end: pd.Timestamp) -> tuple[pd.Series, list[dict]]:
    """Daily returns of a book that trades to each event's weights at that day's close."""
    index = returns.index[returns.index <= end]
    merged: dict[pd.Timestamp, dict[str, float]] = {}
    for day, weights in events:
        traded = trading_day_at_or_before(index, pd.Timestamp(day))
        if traded is not None:
            merged[traded] = weights                       # a later decision on the same close wins
    dates = sorted(merged)
    first_seen = returns.apply(lambda column: column.first_valid_index())
    held: dict[str, float] = {}
    pieces, ledger = [], []
    for k, day in enumerate(dates):
        target = {s: float(w) for s, w in merged[day].items() if abs(float(w)) > 1e-12}
        priced = {s: w for s, w in target.items() if s != CASH and s in first_seen.index
                  and first_seen[s] is not None and pd.notna(first_seen[s]) and first_seen[s] <= day}
        cash = 1.0 - sum(priced.values())                  # cash and unpriced names held flat
        turnover = 0.5 * sum(abs(priced.get(s, 0.0) - held.get(s, 0.0)) for s in set(priced) | set(held) if s != CASH)
        turnover += 0.5 * abs(cash - held.get(CASH, 0.0)) if held else 0.0
        if not held:
            turnover = 1.0 - cash if cash < 1 else 0.0
        cost = cost_bps / 1e4 * turnover
        nxt = dates[k + 1] if k + 1 < len(dates) else end
        window = returns.loc[(returns.index > day) & (returns.index <= nxt), list(priced)].fillna(0.0)
        ledger.append({"date": day, "weights": target, "turnover": turnover, "cost": cost})
        if window.empty:
            continue
        weights = pd.Series(priced, dtype=float)
        growth = (1.0 + window).cumprod()
        value = growth.mul(weights, axis=1).sum(axis=1) + cash
        daily = value / value.shift(1, fill_value=1.0) - 1.0
        daily.iloc[0] = (1.0 - cost) * (1.0 + daily.iloc[0]) - 1.0
        pieces.append(daily)
        last = growth.iloc[-1].mul(weights) / value.iloc[-1]
        held = {**last.to_dict(), CASH: cash / value.iloc[-1]}
    series = pd.concat(pieces).sort_index() if pieces else pd.Series(dtype=float)
    return series[~series.index.duplicated(keep="first")], ledger


def fridays(index: pd.DatetimeIndex, start: pd.Timestamp, stop: pd.Timestamp) -> list[pd.Timestamp]:
    """The last trading day of each week from start to stop (exclusive)."""
    days = index[(index >= start) & (index < stop)]
    weeks = pd.Series(days, index=days).groupby(days.to_period("W-FRI")).max()
    return list(weeks)


def log(clock: str) -> list[dict]:
    path = ROOT / f"evidence/forward_{clock}/decisions.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def logged_events(clock: str, px: Prices, key: str = "target_weights", only_new: str | None = None):
    events = []
    for row in log(clock):
        if only_new and not row.get(only_new, True) and events:
            continue
        weights = row.get(key) or {}
        events.append((pd.Timestamp(row["decision_date"]), {px.symbol(str(s)) if s != CASH else CASH: float(w)
                                                           for s, w in weights.items()}))
    return events


# ----------------------------------------------------------------------------- clocks

def naive(day) -> pd.Timestamp:
    day = pd.Timestamp(day)
    return (day.tz_convert(None) if day.tzinfo else day).normalize()


def frozen_history(path: Path) -> list[tuple[pd.Timestamp, dict[str, float]]]:
    frame = pd.read_csv(path)
    frame[frame.columns[0]] = pd.to_datetime(frame[frame.columns[0]])
    frame = frame.set_index(frame.columns[0]).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return [(day, {s: float(w) for s, w in row.items() if abs(w) > 1e-12}) for day, row in frame.iterrows()]


def breadth_history() -> list[tuple[pd.Timestamp, dict[str, float]]]:
    import run_breadth_ceiling_adversarial_validation_batch_65 as b65
    config = json.loads(b65.CONFIG_PATH.read_text())
    prices = b65.read_dated_csv(b65.BUNDLE / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    core = b65.read_dated_csv(b65.CORE_PATH).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    b63 = json.loads(b65.BATCH63_CONFIG.read_text())
    trend = b65.build_sources(prices, b63)["trend_consistency_top3"]
    breadth = b65.cross_asset_features(prices, b63["discovery_assets"]).breadth_positive_13
    rule = config["frozen_rule"]
    weights = b65.dynamic_weights(core, trend, breadth, rule["breadth_threshold"],
                                  rule["trend_weight_when_confirmed"], rule["trend_weight_otherwise"])
    frozen = pd.read_csv(b65.OUTPUT / "current_holdings.csv", index_col=0).iloc[:, 0]
    last = weights.iloc[-1][lambda x: x > 1e-12]
    gap = (last.reindex(frozen.index).fillna(0) - frozen).abs().max()
    if gap > 1e-9 or set(last.index) != set(frozen.index):
        raise SystemExit(f"breadth reconstruction does not reproduce its frozen holdings (gap {gap})")
    return [(naive(day), {s: float(w) for s, w in row.items() if w > 1e-12})
            for day, row in weights.iterrows()]


def min_variance_history(first_snapshot: str) -> list[tuple[pd.Timestamp, dict[str, float]]]:
    import record_forward_portfolio_evidence as mv
    protocol = mv.load_protocol()
    state = mv.compute_snapshot_state(first_snapshot, protocol)
    out = []
    for day, row in state["weights"].items():
        out.append((pd.Timestamp(day), {s: float(w) for s, w in row.items() if w and abs(w) > 1e-12}))
    return sorted(out)


def block_book_history(module_name: str, first_forward: pd.Timestamp, px: Prices):
    """Valuation and SUE: a new book on the first Friday each new quarterly score block is available."""
    module = __import__(module_name)
    weekly = module.load_prices()
    events, last_block = [], None
    for friday in weekly.index:
        decision = pd.Timestamp(friday)
        if naive(decision) >= first_forward:
            break
        try:
            block_at, target = module.book_for(decision, module.tradable_at(weekly, decision))
        except Exception:
            continue
        if block_at != last_block:
            events.append((naive(decision), {px.symbol(c): w for c, w in target.items()}))
            last_block = block_at
    return events


def riser_leg_history(first_forward: pd.Timestamp, px: Prices):
    import record_spy_riser_5050_forward_v1 as rr
    prices, dollar = rr.sr.load()
    formations, day = [], first_forward - pd.Timedelta(weeks=52)
    while True:
        candidates = prices.index[prices.index <= day]
        if not len(candidates):
            break
        decision = candidates[-1]
        try:
            book = rr.form_book(prices, dollar, decision)
        except Exception:
            break
        formations.append((decision, {px.symbol(c): float(w) for c, w in zip(book.cik10, book.weight)}))
        day = decision - pd.Timedelta(weeks=52)
    return sorted(formations)


def equal_weight_events(px: Prices, end: pd.Timestamp):
    import record_equal_weight_benchmark_forward_v1 as ew

    def load(path: Path) -> pd.DataFrame:
        frame = pd.read_csv(path, dtype={"cik10": str})
        frame["decision_at"] = pd.to_datetime(frame.decision_at, utc=True, errors="coerce").dt.tz_localize(None)
        flag = next(c for c in ("tradable_member", "validated_price_available", "execution_price_available") if c in frame)
        return frame[frame[flag].astype(bool)]

    narrow, broad = load(ew.NARROW_MEMBERSHIP), load(ew.BROAD_MEMBERSHIP)
    quarters = sorted(narrow.decision_at.dropna().unique())
    rosters = {q: ([px.symbol(c) for c in sorted(set(narrow[narrow.decision_at == q].cik10))],
                   [px.symbol(c) for c in sorted(set(broad[broad.decision_at == q].cik10))]) for q in quarters}
    px.ensure({s for a, b in rosters.values() for s in a + b})
    events = []
    available = px.returns.notna().astype(np.int8).rolling(30, min_periods=1).max().astype(bool)
    for friday in fridays(px.returns.index, pd.Timestamp(quarters[0]), end + pd.Timedelta(days=1)):
        q = max(x for x in quarters if x <= friday)
        row = available.loc[friday]
        weights: dict[str, float] = {}
        for members, share in ((rosters[q][0], 0.8), (rosters[q][1], 0.2)):
            live = [s for s in members if s in row.index and row[s]]
            for s in live:
                weights[s] = weights.get(s, 0.0) + share / len(live)
        events.append((friday, weights))
    return events


# ----------------------------------------------------------------------------- payload

def stats(r: pd.Series) -> dict[str, float]:
    wealth = (1 + r).cumprod()
    years = max((r.index[-1] - r.index[0]).days / 365.25, 1e-9)
    return {"cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
            "sharpe": float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0.0,
            "maxDrawdown": float((wealth / wealth.cummax() - 1).min()),
            "totalReturn": float(wealth.iloc[-1] - 1)}


def entry(clock: dict, daily: pd.Series, ledger: list[dict]) -> dict:
    forward_from = clock["forward_from"]
    daily = daily.dropna()
    start = daily.index[0] - pd.Timedelta(days=1)
    full = stats(daily)
    fwd = daily[daily.index > forward_from]
    fwd_stats = stats(fwd) if len(fwd) > 1 else {"cagr": 0.0, "sharpe": 0.0, "maxDrawdown": 0.0, "totalReturn": 0.0}
    status = json.loads((ROOT / f"evidence/forward_{clock['id']}/status.json").read_text())
    daily_records = [{"date": str(start.date()), "netReturn": 0.0, "rebalance": True, "tradingDay": True}]
    rebal = {str(row["date"].date()) for row in ledger}
    daily_records += [{"date": str(d.date()), "netReturn": round(float(v), 7), "rebalance": str(d.date()) in rebal,
                       "tradingDay": True, **({"forward": True} if d > forward_from else {})} for d, v in daily.items()]
    wealth = (1 + daily).cumprod()
    peak = wealth.cummax()
    records, previous = [], {}
    keep_holdings = clock.get("holdings", True)
    for row in ledger:
        day = row["date"]
        if day > daily.index[-1]:
            continue
        w = wealth.loc[:day].iloc[-1] if len(wealth.loc[:day]) else 1.0
        dd = (wealth.loc[:day] / peak.loc[:day] - 1).iloc[-1] if len(wealth.loc[:day]) else 0.0
        holdings = []
        if keep_holdings:
            for s in set(row["weights"]) | set(previous):
                weight, change = row["weights"].get(s, 0.0), row["weights"].get(s, 0.0) - previous.get(s, 0.0)
                if abs(weight) > 1e-10 or abs(change) > 1e-10:
                    holdings.append({"symbol": s, "weight": round(weight, 6), "change": round(change, 6)})
            holdings.sort(key=lambda h: -abs(h["weight"]))
        records.append({"date": str(day.date()), "grossReturn": 0.0, "netReturn": 0.0,
                        "turnover": round(row["turnover"], 6), "cost": round(row["cost"], 8),
                        "wealth": round(float(w), 6), "drawdown": round(float(dd), 6),
                        "rebalance": bool(row["turnover"] > 1e-6 or not records), "holdings": holdings})
        previous = row["weights"]
    observed = int(status.get("observed_weeks") or 0)
    return {
        "strategy": {
            "id": f"clock-{clock['id']}", "name": clock["name"], "shortName": clock["short"],
            "subtitle": clock["subtitle"], "badge": "Forward clock",
            "asOf": str(ledger[-1]["date"].date()),
            "retrospectiveHoldout": {"cagr": fwd_stats["cagr"], "sharpe": fwd_stats["sharpe"],
                                     "maxDrawdown": fwd_stats["maxDrawdown"], "start": str(forward_from.date())},
            "fullHistory": {"cagr": full["cagr"], "maxDrawdown": full["maxDrawdown"], "start": str(start.date())},
            "featuredMetric": {"label": "Backtest CAGR from start", "value": full["cagr"],
                               "note": f"Since {start.date()}; the clock itself only from {forward_from.date()}."},
            "forward": {"status": "running", "observedWeeks": observed, "requiredWeeks": 52,
                        "firstDecision": str(forward_from.date()),
                        "firstRealization": str((forward_from + pd.Timedelta(days=7)).date()),
                        "note": f"{observed} of 52 untouched weeks recorded."},
            "disclosures": {"researchOnly": True, "liveTradingEnabled": False, "costBps": clock["bps"],
                            "returnConvention": clock["convention"]},
            "dailyThrough": str(daily.index[-1].date()),
            "clockHistory": {"backtestStart": str(start.date()), "forwardFrom": str(forward_from.date()),
                             "through": str(daily.index[-1].date()), "survivorship": clock.get("survivorship", False)},
        },
        "records": records,
        "dailyRecords": daily_records,
    }


BASE = ("Before {fwd}: the clock's frozen rule applied to past data (a backtest chosen with hindsight, "
        "not evidence). From {fwd}: the clock's own recorded decisions. Marked at daily adjusted closes, "
        "trading at each decision day's close; {cost}.")
SURVIVOR = " The stock price history holds mostly survivors, so the backtest part is flattered."


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    px = Prices()
    end = px.end
    clocks: list[dict] = []

    def add(clock_id, name, short, subtitle, history, forward, bps, *, survivorship=False, holdings=True,
            cost_text=None):
        forward_from = forward[0][0] if forward else end
        events = [e for e in history if e[0] < forward_from] + forward
        clocks.append({"id": clock_id, "name": name, "short": short, "subtitle": subtitle, "events": events,
                       "bps": bps, "forward_from": forward_from, "survivorship": survivorship, "holdings": holdings,
                       "convention": BASE.format(fwd=forward_from.date(), cost=cost_text or f"{bps:g} bps on one-way turnover at each rebalance")
                       + (SURVIVOR if survivorship else "")})

    spy_fridays = lambda start: fridays(px.calendar, pd.Timestamp(start), pd.Timestamp("2100-01-01"))
    thirds = {"SPY": 1 / 3, "GLD": 1 / 3, "SHY": 1 / 3}
    add("static_spy_gld_shy_v1", "Benchmark — SPY / GLD / SHY equal thirds", "Benchmark thirds (clock)",
        "Equal thirds SPY, GLD, SHY, reset weekly · the benchmark to beat",
        [(d, thirds) for d in spy_fridays("2005-01-07")], logged_events("static_spy_gld_shy_v1", px), ETF_BPS)
    trend_w = json.loads((ROOT / "config/forward/trend_sleeve_8020_v1.json").read_text())["rule"]["weights"]
    add("trend_sleeve_8020_v1", "Trend Sleeve 80/20 — thirds + managed futures", "Trend sleeve 80/20 (clock)",
        "80% equal thirds SPY/GLD/SHY + 20% DBMF, reset weekly · history starts when DBMF does (2019)",
        [(d, trend_w) for d in spy_fridays("2019-05-17")],
        logged_events("trend_sleeve_8020_v1", px, key="weights"), ETF_BPS)
    add("return_first_60_40_blend_v1", "60/40 Return-First Blend", "60/40 blend (clock)",
        "Frozen weekly ETF book through 2026-08-07, then held as recorded",
        frozen_history(ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"),
        logged_events("return_first_60_40_blend_v1", px), ETF_BPS)
    add("past_only_consensus_selector_return_v1", "Past-Only Consensus Selector", "Past-only consensus (clock)",
        "Frozen weekly ETF selector through 2026-08-07, then held as recorded",
        frozen_history(ROOT / "evidence/exhaustive_return_first_discovery_batch_66/retrospective_ceiling_adversarial/past_only_selector_weights.csv"),
        logged_events("past_only_consensus_selector_return_v1", px), ETF_BPS)
    add("breadth_confirmed_trend_return_ceiling_v3", "Breadth-Confirmed Trend", "Breadth trend (clock)",
        "Batch 65 rule rebuilt in memory and checked against its frozen holdings, then held as recorded",
        breadth_history(), logged_events("breadth_confirmed_trend_return_ceiling_v3", px), ETF_BPS)
    first_mv = log("covariance_minimum_variance_v1")[0]["decision_snapshot_id"]
    add("covariance_minimum_variance_v1", "Covariance Minimum Variance", "Minimum variance (clock)",
        "Monthly minimum-variance mix of a trend and a defensive ETF sleeve, recomputed by the clock each week",
        min_variance_history(first_mv), logged_events("covariance_minimum_variance_v1", px), ETF_BPS)

    stock_first = {c: pd.Timestamp(log(c)[0]["decision_date"]) for c in
                   ["valuation_earnings_yield_v1", "sue_quarterly_v1", "spy_riser_5050_v1", "equal_weight_benchmark_v1"]}
    add("valuation_earnings_yield_v1", "Valuation — Earnings Yield Top 20", "Earnings yield (clock)",
        "20 highest earnings-yield stocks, equal weight, new book each quarter",
        block_book_history("record_valuation_earnings_yield_forward_v1", stock_first["valuation_earnings_yield_v1"], px),
        logged_events("valuation_earnings_yield_v1", px, only_new="score_block_is_new"), STOCK_BPS, survivorship=True)
    add("sue_quarterly_v1", "SUE — Earnings Surprise Top 50", "SUE quarterly (clock)",
        "50 highest standardized-earnings-surprise stocks, equal weight, new book each quarter",
        block_book_history("record_sue_quarterly_forward_v1", stock_first["sue_quarterly_v1"], px),
        logged_events("sue_quarterly_v1", px, only_new="score_block_is_new"), STOCK_BPS, survivorship=True)

    # The 50/50: a riser leg (annual books, drifting) blended 50/50 with SPY, reset weekly.
    riser_first = stock_first["spy_riser_5050_v1"]
    leg_events = riser_leg_history(riser_first, px)
    for row in log("spy_riser_5050_v1"):
        if row.get("formed_new_book"):
            book = pd.read_csv(ROOT / row["book_file"], dtype={"cik10": str})
            leg_events.append((pd.Timestamp(row["decision_date"]),
                               {px.symbol(c): float(w) for c, w in zip(book.cik10, book.weight)}))
    clocks.append({"id": "spy_riser_5050_v1", "special": "riser", "leg_events": leg_events,
                   "name": "50% SPY + 50% Steady Risers", "short": "SPY + risers 50/50 (clock)",
                   "subtitle": "Half SPY, half the 20 steadiest 52-week risers held a year, reset 50/50 weekly",
                   "bps": STOCK_BPS, "forward_from": riser_first, "survivorship": True, "holdings": True,
                   "convention": BASE.format(fwd=riser_first.date(), cost="50 bps on the riser leg's traded notional at each yearly formation, none on the weekly 50/50 reset") + SURVIVOR})
    ew_events = equal_weight_events(px, end)
    clocks.append({"id": "equal_weight_benchmark_v1", "name": "Equal-Weight Stock Benchmark",
                   "short": "Equal-weight stocks (clock)",
                   "subtitle": "Every tradable roster member, equal weight, 80% narrow + 20% broad roster, reset weekly",
                   "events": ew_events, "bps": 0.0, "forward_from": stock_first["equal_weight_benchmark_v1"],
                   "survivorship": True, "holdings": False, "stop_at_vintage": True,
                   "convention": BASE.format(fwd=stock_first["equal_weight_benchmark_v1"].date(),
                                             cost="no cost, as its recorder charges none")
                   + SURVIVOR + " Ends at the stock price vintage's last day; thousands of names are not re-downloaded mid-week."})

    # Prices: load every symbol any book holds; top up Yahoo after the vintage for books held then.
    held = set()
    for clock in clocks:
        for _, w in clock.get("events", []) + clock.get("leg_events", []):
            held |= set(w)
    held.discard(CASH)
    px.ensure(held | {"SPY"})
    px.top_up({"DBMF"}, full_history={"DBMF"})
    recent = set()
    for clock in clocks:
        if clock.get("stop_at_vintage"):
            continue
        evs = clock.get("events", []) + clock.get("leg_events", [])
        if evs:
            recent |= set(sorted(evs, key=lambda e: e[0])[-1][1])
    recent |= {"SPY", "GLD", "SHY", "DBMF"}
    px.top_up(recent - {CASH})

    summary, rows = [], []
    for clock in clocks:
        stop = px.vintage_end if clock.get("stop_at_vintage") else end
        if clock.get("special") == "riser":
            leg, leg_ledger = run_path(sorted(clock["leg_events"], key=lambda e: e[0]), px.returns, STOCK_BPS, stop)
            pair = pd.DataFrame({"SPY": px.returns["SPY"], "LEG::risers": leg}).reindex(px.returns.index)
            weekly = [(d, {"SPY": 0.5, "LEG::risers": 0.5}) for d in fridays(pair.index, leg.index[0] - pd.Timedelta(days=1), stop + pd.Timedelta(days=1))]
            weekly = [(leg_ledger[0]["date"], {"SPY": 0.5, "LEG::risers": 0.5})] + [e for e in weekly if e[0] > leg_ledger[0]["date"]]
            daily, _ = run_path(weekly, pair, 0.0, stop)
            ledger = [{"date": r["date"], "weights": {"SPY": 0.5, **{s: 0.5 * w for s, w in r["weights"].items()}},
                       "turnover": r["turnover"] * 0.5, "cost": r["cost"] * 0.5} for r in leg_ledger]
        else:
            daily, ledger = run_path(sorted(clock["events"], key=lambda e: e[0]), px.returns, clock["bps"], stop)
        payload = entry(clock, daily, ledger)
        s = payload["strategy"]
        rows.append(payload)
        fwd = daily[daily.index > clock["forward_from"]]
        summary.append({"clock": clock["id"], "start": s["fullHistory"]["start"], "through": s["dailyThrough"],
                        "forward_from": str(clock["forward_from"].date()), **stats(daily.dropna()),
                        "up_day_share": float((daily > 0).mean()),
                        "forward_return": float((1 + fwd).prod() - 1), "rebalances": len(ledger)})
        pd.DataFrame({"date": daily.index.strftime("%Y-%m-%d"), "daily_return": daily.to_numpy(),
                      "segment": np.where(daily.index > clock["forward_from"], "forward", "backtest")}) \
            .to_csv(OUT / f"daily_{clock['id']}.csv", index=False)
        print(f"{clock['id']:44s} {s['fullHistory']['start']} -> {s['dailyThrough']}  CAGR {summary[-1]['cagr']:6.1%}  "
              f"Sharpe {summary[-1]['sharpe']:.2f}  maxDD {summary[-1]['maxDrawdown']:6.1%}  since clock start {summary[-1]['forward_return']:+.2%}")

    generated = datetime.now(timezone.utc).isoformat()
    meta = {"generated_at_utc": generated, "through": str(end.date()), "etf_vintage": px.etf_vintage.name,
            "stock_vintage": px.stock_vintage.name, "vintage_end": str(px.vintage_end.date()),
            "what_this_is": "each forward clock's frozen rule applied to the past, then its recorded decisions, marked daily",
            "what_this_is_not": "forward evidence before each clock's first decision; it never writes to a forward log",
            "clocks": summary}
    (OUT / "summary.json").write_text(json.dumps(meta, indent=2) + "\n")
    DASH.write_text(json.dumps({"generatedAtUtc": generated, "through": str(end.date()), "strategies": rows},
                               separators=(",", ":")) + "\n")
    for payload in rows:                                   # the page fetches /prices/<id>.json per strategy;
        stub = DASH.parent / "prices" / f"{payload['strategy']['id']}.json"   # clocks carry no per-asset prices yet
        if not stub.exists():
            stub.write_text("{}\n")
    print(f"wrote {DASH.relative_to(ROOT)} ({DASH.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
