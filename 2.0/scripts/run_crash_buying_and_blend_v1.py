#!/usr/bin/env python3
"""Crash-buying rule and a 1.0 + 2.0 blend.

Pre-registered in docs/CRASH_BUYING_AND_BLEND_PREREGISTRATION_V1.md, committed before this file
computed anything. No financing: weights never exceed 100% and never go negative.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.systematic_trader.return_conventions import detect_convention, to_week_ending  # noqa: E402

ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
OUT = ROOT / "evidence/crash_buying_and_blend_v1"
SEED, PLACEBO_DRAWS = 20261006, 2000
TRIGGERS, HOLDS = (0.10, 0.20, 0.30), (13, 26, 52)
BONFERRONI = 0.05 / 9
BREAK = pd.Timestamp("2025-04-04")
EVENTS = {"9/11": "2001-09-21", "Lehman": "2008-09-19", "Fukushima": "2011-03-11",
          "US downgrade": "2011-08-05", "Brexit vote": "2016-06-24",
          "COVID first crash week": "2020-02-28", "Ukraine invasion": "2022-02-25",
          "SVB failure": "2023-03-10", "Tariff announcement": "2025-04-04"}


def prices() -> pd.DataFrame:
    px = pd.read_csv(ETF, index_col=0, parse_dates=True)
    px.index = pd.to_datetime(px.index, utc=True).tz_localize(None).normalize()
    return px.apply(pd.to_numeric, errors="coerce")


def simulate(target: pd.DataFrame, rets: pd.DataFrame, cost_bps: float) -> pd.Series:
    """target.loc[t] is decided at the close of t and earns rets.loc[t+1]."""
    cols = list(target.columns)
    W = target.values
    R = rets.reindex(target.index)[cols].values
    held = np.zeros(len(cols))
    out = np.empty(len(target) - 1)
    for i in range(len(target) - 1):
        want, r = W[i], R[i + 1]
        turnover = np.abs(want - held).sum() if i else want.sum()
        gross = float(want @ r)
        out[i] = gross - turnover * cost_bps / 1e4
        held = want * (1 + r) / (1 + gross) if (1 + gross) else want
    return pd.Series(out, index=target.index[1:])


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 8:
        return {"weeks": len(r)}
    w = (1 + r).cumprod()
    return {"weeks": len(r), "cagr": float(w.iloc[-1] ** (52 / len(r)) - 1),
            "sharpe": float(r.mean() / r.std() * np.sqrt(52)),
            "maxdd": float((w / w.cummax() - 1).min())}


def cal(r: pd.Series, a: str, b: str) -> float:
    s = r[a:b]
    return float((1 + s).prod() - 1) if len(s) else float("nan")


# ---------------------------------------------------------------- Part A
def crash_state(dd: pd.Series, trigger: float, hold: int) -> pd.Series:
    state = np.zeros(len(dd), dtype=bool)
    below = (dd <= -trigger).values
    i = 1
    while i < len(dd):
        if below[i] and not below[i - 1]:
            state[i:i + hold] = True
            i += hold
            # require a fresh crossing: skip until no longer below
            while i < len(dd) and below[i]:
                i += 1
        else:
            i += 1
    return pd.Series(state, index=dd.index)


def weights_from_state(state: pd.Series) -> pd.DataFrame:
    spy = np.where(state, 1.0, 0.7)
    return pd.DataFrame({"SPY": spy, "SHY": 1 - spy}, index=state.index)


def placebo_state(n: int, entries: int, hold: int, rng) -> pd.Series:
    state = np.zeros(n, dtype=bool)
    for s in rng.choice(np.arange(52, n - 1), size=entries, replace=False):
        state[s:s + hold] = True
    return state


def part_a(px: pd.DataFrame, rets: pd.DataFrame) -> dict:
    spy_px = px["SPY"]
    dd = spy_px / spy_px.rolling(52, min_periods=52).max() - 1
    win = rets.index >= "2003-01-01"
    idx = rets.index[win]
    dd = dd.reindex(idx)
    sub = rets.loc[idx]

    # A1 descriptive event study
    spy_r = rets["SPY"]
    events = []
    for name, d in EVENTS.items():
        t = spy_r.index.get_indexer([pd.Timestamp(d)], method="nearest")[0]
        row = {"event": name, "week": str(spy_r.index[t].date())}
        for h in (4, 13, 26, 52):
            row[f"fwd_{h}w"] = float((1 + spy_r.iloc[t + 1:t + 1 + h]).prod() - 1) \
                if t + h < len(spy_r) else None
        events.append(row)
    base = {f"avg_{h}w": float(np.mean([(1 + spy_r.iloc[i + 1:i + 1 + h]).prod() - 1
                                        for i in range(len(spy_r) - h)]))
            for h in (4, 13, 26, 52)}

    rng = np.random.default_rng(SEED)
    rows = []
    for trig in TRIGGERS:
        for hold in HOLDS:
            st = crash_state(dd, trig, hold)
            entries = int((st & ~st.shift(1, fill_value=False)).sum())
            w = weights_from_state(st)
            rule10, rule50 = simulate(w, sub, 10), simulate(w, sub, 50)
            avg = float(w.SPY.iloc[:-1].mean())
            null = simulate(pd.DataFrame({"SPY": avg, "SHY": 1 - avg}, index=idx), sub, 10)
            sh_rule = stats(rule10)["sharpe"]
            hits = 0
            for _ in range(PLACEBO_DRAWS):
                ps = pd.Series(placebo_state(len(idx), entries, hold, rng), index=idx)
                hits += stats(simulate(weights_from_state(ps), sub, 10))["sharpe"] >= sh_rule
            p = (hits + 1) / (PLACEBO_DRAWS + 1)
            h1 = stats(rule10[:"2014-12-31"])["cagr"] - stats(null[:"2014-12-31"])["cagr"]
            h2 = stats(rule10["2015-01-01":])["cagr"] - stats(null["2015-01-01":])["cagr"]
            r, n = stats(rule10), stats(null)
            rows.append({
                "trigger": trig, "hold": hold, "entries": entries, "avg_spy": avg,
                "rule_cagr": r["cagr"], "rule_sharpe": r["sharpe"], "rule_maxdd": r["maxdd"],
                "rule_cagr_50bps": stats(rule50)["cagr"],
                "null_cagr": n["cagr"], "null_sharpe": n["sharpe"], "null_maxdd": n["maxdd"],
                "edge_2003_2014": h1, "edge_2015_2026": h2, "placebo_p": p,
                "rule_2008": cal(rule10, "2008-01-01", "2008-12-31"),
                "null_2008": cal(null, "2008-01-01", "2008-12-31"),
                "rule_2022": cal(rule10, "2022-01-01", "2022-12-31"),
                "null_2022": cal(null, "2022-01-01", "2022-12-31"),
                "PASS": bool(r["sharpe"] > n["sharpe"] and r["cagr"] > n["cagr"]
                             and p < BONFERRONI and h1 > 0 and h2 > 0)})
    spy_bh = stats(sub["SPY"].iloc[1:])
    return {"events": events, "unconditional": base, "grid": rows, "spy_buy_hold": spy_bh}


# ---------------------------------------------------------------- Part B
def load_path(path: Path, spy: pd.Series) -> pd.Series:
    f = pd.read_csv(path)
    s = pd.Series(f.net_return.values,
                  index=pd.to_datetime(f.Date, utc=True).dt.tz_localize(None).dt.normalize())
    s = s[s.index >= s[s != 0].index.min()]
    conv, beta, r2 = detect_convention(s, spy)
    print(f"  {path.name}: {conv}, beta {beta:.2f}, R2 {r2:.2f}")
    return to_week_ending(s, conv).dropna()


def part_b(rets: pd.DataFrame) -> dict:
    spy = rets["SPY"]
    oos = load_path(ROOT / "evidence/composites_out_of_sample_v1/path__residual_composite__50bps.csv", spy)
    ins = load_path(ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv", spy)
    book = pd.concat([oos[:"2022-12-31"], ins["2023-01-01":]]).sort_index()
    book = book[~book.index.duplicated()]
    frame = rets[["SPY", "GLD", "SHY"]].copy()
    frame["BOOK"] = book
    frame = frame.dropna()
    one = pd.DataFrame({"SPY": 1 / 3, "GLD": 1 / 3, "SHY": 1 / 3}, index=frame.index)
    blend_w = pd.DataFrame({"SPY": 1 / 6, "GLD": 1 / 6, "SHY": 1 / 6, "BOOK": 0.5}, index=frame.index)
    null_w = pd.DataFrame({"SPY": 1 / 6 + 0.5, "GLD": 1 / 6, "SHY": 1 / 6}, index=frame.index)
    series = {
        "blend_1.0+2.0": simulate(blend_w, frame, 10),
        "null_1.0+SPY": simulate(null_w, frame, 10),
        "1.0_SPY_GLD_SHY": simulate(one, frame, 10),
        "2.0_residual_book": frame.BOOK.iloc[1:],
        "SPY": frame.SPY.iloc[1:],
    }
    windows = {"2013-2022 (2.0 out of sample)": ("2013-01-01", "2022-12-31"),
               "2023-01 to 2025-04-03": ("2023-01-01", "2025-04-03"),
               "2025-04-04 to end": ("2025-04-04", "2030-01-01"),
               "full": ("2000-01-01", "2030-01-01")}
    table = []
    for name, s in series.items():
        for w, (a, b) in windows.items():
            table.append({"series": name, "window": w, **stats(s[a:b])})
        table.append({"series": name, "window": "2020 total", "cagr": cal(s, "2020-01-01", "2020-12-31")})
        table.append({"series": name, "window": "2022 total", "cagr": cal(s, "2022-01-01", "2022-12-31")})
    sh = {w: (stats(series["blend_1.0+2.0"][a:b])["sharpe"], stats(series["null_1.0+SPY"][a:b])["sharpe"])
          for w, (a, b) in list(windows.items())[:3]}
    return {"start": str(frame.index[0].date()), "table": table,
            "sharpe_blend_vs_null": sh, "PASS": all(b > n for b, n in sh.values())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    px = prices()
    rets = px.pct_change().iloc[1:]
    a = part_a(px, rets)
    print("alignment:")
    b = part_b(rets)
    json.dump({"part_a": a, "part_b": b}, open(OUT / "result.json", "w"), indent=2, default=float)
    pd.DataFrame(a["grid"]).to_csv(OUT / "crash_rule_grid.csv", index=False)
    pd.DataFrame(b["table"]).to_csv(OUT / "blend_table.csv", index=False)

    pd.set_option("display.width", 250)
    print("\nA1 named events: SPY forward return from event-week close")
    print(pd.DataFrame(a["events"]).to_string(index=False))
    print("unconditional averages:", {k: round(v, 4) for k, v in a["unconditional"].items()})
    print("\nA2 crash rule grid (10 bps):")
    g = pd.DataFrame(a["grid"])
    print(g.round(4).to_string(index=False))
    print("SPY buy-and-hold same window:", a["spy_buy_hold"])
    print(f"A2 passes: {int(g.PASS.sum())} of 9")
    print(f"\nB blend, start {b['start']}:")
    print(pd.DataFrame(b["table"]).round(4).to_string(index=False))
    print("Sharpe blend vs null:", b["sharpe_blend_vs_null"], "PASS" if b["PASS"] else "fail")


if __name__ == "__main__":
    main()
