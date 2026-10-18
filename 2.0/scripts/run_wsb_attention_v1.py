#!/usr/bin/env python3
"""B17: does a WallStreetBets attention surge mark a stock to AVOID?

Pre-registered in config/wsb_attention_registry_v1.json (committed before any Reddit data).
    python scripts/run_wsb_attention_v1.py acquire     # Arctic Shift weekly counts, cached, resumable
    python scripts/run_wsb_attention_v1.py screen
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_news_jump_followers_v1 as a24  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/wsb_attention_registry_v1.json"
CACHE = ROOT / "data/wsb_attention_v1"
OUTPUT = ROOT / "evidence/wsb_attention_v1"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
API = "https://arctic-shift.photon-reddit.com/api/posts/search/aggregate"
UA = "PortfolioOptimizerResearch/2.0 contact=local-research"
HORIZONS = {"T1_hype_21d": 21, "T2_hype_63d": 63}
DESIGN, HOLDOUT, BAR = ("2017-01-01", "2020-12-31"), ("2021-01-01", "2025-12-31"), 0.025


def universe() -> pd.DataFrame:
    prices = a19.load_daily()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    mask = (prices.index >= "2017-01-01") & (prices.index <= "2025-12-31")
    px, dv = prices.to_numpy()[mask], dollar.to_numpy()[mask]
    ever = np.zeros(px.shape[1], dtype=bool)
    for t in range(0, len(px), 5):
        ok = px[t] >= 5
        ever[np.argsort(-np.where(ok, np.nan_to_num(dv[t], nan=-1), -1))[:1000]] = True
    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False).drop_duplicates("cik10")
    sym = cat.set_index("cik10").symbol
    words = {w.strip() for w in Path("/usr/share/dict/words").read_text().splitlines() if w.strip().islower()}
    rows = []
    for c in np.array(prices.columns)[ever]:
        s = str(sym.get(c, ""))
        if s.isalpha() and len(s) >= 3 and s.lower() not in words:
            rows.append({"cik10": c, "ticker": s})
    return pd.DataFrame(rows)


def fetch(ticker: str, after: str, before: str) -> list | None:
    params = urllib.parse.urlencode({"aggregate": "created_utc", "frequency": "week", "subreddit": "wallstreetbets",
                                     "title": ticker, "after": after, "before": before})
    for attempt in range(5):
        try:
            req = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read())
            if data.get("data") is not None:
                return data["data"]
            time.sleep(3 * (attempt + 1))                         # "Timeout. Maybe slow down a bit"
        except Exception:                                         # noqa: BLE001
            time.sleep(5 * (attempt + 1))
    return None


def stage_acquire() -> int:
    json.loads(REGISTRY.read_text())
    CACHE.mkdir(parents=True, exist_ok=True)
    uni = universe()
    uni.to_csv(CACHE / "universe.csv", index=False)
    print(f"{len(uni)} tickers in the universe", flush=True)
    failed = 0
    for n, r in enumerate(uni.itertuples(), 1):
        path = CACHE / f"{r.ticker}.json"
        if path.exists():
            continue
        out, ok = [], True
        for year in range(2017, 2026):
            got = fetch(r.ticker, f"{year}-01-01", f"{year + 1}-01-01")
            if got is None:                                       # split a heavy year into quarters
                for qs, qe in (("01-01", "04-01"), ("04-01", "07-01"), ("07-01", "10-01"), ("10-01", "12-31")):
                    part = fetch(r.ticker, f"{year}-{qs}", f"{year}-{qe}" if qe != "12-31" else f"{year + 1}-01-01")
                    if part is None:
                        ok = False
                        break
                    out += part
            else:
                out += got
            if not ok:
                break
            time.sleep(0.3)
        path.write_text(json.dumps({"ticker": r.ticker, "cik10": r.cik10, "complete": ok, "weeks": out}))
        failed += not ok
        if n % 100 == 0:
            print(f"  {n}/{len(uni)} tickers, {failed} incomplete", flush=True)
    print(f"done: {len(uni)} tickers, {failed} incomplete (excluded)")
    return 0


def stage_crawl() -> int:
    """Amendment 2026-10-18: crawl every r/wallstreetbets post (created_utc, title); polite and resumable."""
    import gzip
    folder = CACHE / "posts"
    folder.mkdir(parents=True, exist_ok=True)
    state = folder / "state.json"
    after = json.loads(state.read_text())["after"] if state.exists() else int(pd.Timestamp("2017-01-01", tz="UTC").timestamp())
    end = int(pd.Timestamp("2026-01-01", tz="UTC").timestamp())
    n = 0
    while after < end:
        url = ("https://arctic-shift.photon-reddit.com/api/posts/search?subreddit=wallstreetbets&limit=100&sort=asc"
               f"&fields=created_utc,title&after={after}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read()).get("data")
        except urllib.error.HTTPError as exc:
            wait = int(exc.headers.get("x-ratelimit-reset", "15") or 15)
            time.sleep(max(15, wait + 2))
            continue
        except Exception:                                         # noqa: BLE001
            time.sleep(30)
            continue
        if data is None:
            time.sleep(20)
            continue
        if not data:
            break
        by_month = {}
        for p in data:
            month = pd.Timestamp(int(p["created_utc"]), unit="s").strftime("%Y-%m")
            by_month.setdefault(month, []).append(json.dumps({"t": int(p["created_utc"]), "title": p.get("title", "")}))
        for month, lines in by_month.items():
            with gzip.open(folder / f"{month}.jsonl.gz", "at") as handle:
                handle.write("\n".join(lines) + "\n")
        after = max(int(p["created_utc"]) for p in data)
        state.write_text(json.dumps({"after": after}))
        n += 1
        if n % 500 == 0:
            print(f"  {n} pages, now at {pd.Timestamp(after, unit='s')}", flush=True)
        time.sleep(1.5)
    print(f"done crawling: {n} pages this run, reached {pd.Timestamp(after, unit='s')}")
    return 0


def stage_screen() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261019)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    px, dv = prices.to_numpy(), dollar.to_numpy()
    R = np.vstack([np.full(len(cols), np.nan), px[1:] / px[:-1] - 1.0])

    events, incomplete = [], 0
    for path in sorted(CACHE.glob("*.json")):
        if path.name == "universe.json":
            continue
        d = json.loads(path.read_text())
        if not d["complete"]:
            incomplete += 1
            continue
        s = pd.Series({pd.Timestamp(w["created_utc"]).tz_convert(None).normalize(): int(w["count"]) for w in d["weeks"]})
        s = s.groupby(level=0).sum().sort_index()
        prior = s.shift(1).rolling(26, min_periods=26).mean().clip(lower=1.0)
        hype = s[(s >= 10) & (s >= 5 * prior)]
        last = None
        for week, count in hype.items():
            if last is not None and (week - last).days < 91:
                continue
            last = week
            events.append({"cik10": d["cik10"], "ticker": d["ticker"], "week_start": week, "posts": int(count),
                           "prior_mean": float(prior[week])})
    ev = pd.DataFrame(events)
    print(f"hype events {len(ev)} across {ev.ticker.nunique()} tickers; {incomplete} tickers excluded as incomplete")

    sic_cache, rows = {}, []
    event_weeks = ev.groupby("week_start").cik10.apply(set).to_dict()
    for e in ev.itertuples():
        if e.cik10 not in col_pos:
            continue
        i = col_pos[e.cik10]
        t = dates.searchsorted(e.week_start + pd.Timedelta(days=8))  # first trading day >= week end + 1 day
        if t + max(HORIZONS.values()) >= len(dates) or t < 70:
            continue
        liquid = (px[t] >= 5) & (dv[t] >= 5e6)
        key = (dates[t].year, dates[t].month)
        if key not in sic_cache:
            sic_cache[key] = a19.sic_as_of(sic, dates[t]).reindex(cols).str[:2].to_numpy(dtype=object)
        sic2 = sic_cache[key]
        if not isinstance(sic2[i], str):
            continue
        busy = {col_pos[c] for c in event_weeks.get(e.week_start, set()) if c in col_pos}
        pool = [k for k in np.flatnonzero(liquid & (sic2 == sic2[i])) if k != i and k not in busy]
        if len(pool) < 5:
            continue
        ctrl = rng.choice(pool, size=50, replace=True)
        w0 = dates.searchsorted(e.week_start)
        hype_week_abs = float(np.nanmean(np.abs(R[w0:t, i]))) if t > w0 else np.nan
        typical_abs = float(np.nanmean(np.abs(R[t - 70:w0, i]))) if w0 > t - 70 else np.nan
        row = {"date": dates[t], "month": dates[t].strftime("%Y-%m"), "leader": e.ticker, "posts": e.posts,
               "hype_week_abs_daily_return": hype_week_abs, "typical_abs_daily_return": typical_abs}
        for name, h in HORIZONS.items():
            f = px[t + h, i] / px[t, i] - 1.0
            c = np.nanmean(px[t + h, ctrl] / px[t, ctrl] - 1.0)
            row[name] = f - c if np.isfinite(f) and np.isfinite(c) else np.nan
        rows.append(row)
    out = pd.DataFrame(rows)
    out.to_csv(OUTPUT / "events.csv", index=False)
    pc = {"hype_week_abs": float(out.hype_week_abs_daily_return.mean()), "typical_abs": float(out.typical_abs_daily_return.mean())}
    print(f"positive control: mean |daily return| in the hype week {pc['hype_week_abs']:.2%} vs typical {pc['typical_abs']:.2%}")
    win = lambda f, a, b: f[(f.date >= a) & (f.date <= b)]  # noqa: E731
    results = {}
    for name in HORIZONS:
        d, h = a24.summarise(win(out, *DESIGN), name, rng), a24.summarise(win(out, *HOLDOUT), name, rng)
        dsub = win(out, *DESIGN).dropna(subset=[name])
        without_worst = float(dsub[name].drop(dsub[name].nsmallest(10).index).mean()) if len(dsub) > 10 else float("nan")
        crit = {"design_negative_p_below_bar": d.get("mean", 0) < 0 and d.get("bootstrap_p", 1) < BAR,
                "holdout_negative": h.get("mean", 0) < 0,
                "design_negative_without_10_worst": without_worst < 0,
                "design_magnitude_above_50bps": d.get("mean", 0) < -0.005}
        results[name] = {"design": d, "holdout": h, "design_without_10_most_negative": without_worst,
                         "criteria": crit, "passes": all(crit.values()),
                         "by_year": {str(y): a24.summarise(out[out.date.dt.year == y], name, rng) for y in range(2017, 2026)}}
        print(f"\n== {name} (declared NEGATIVE: an avoid rule)")
        for lab, s in (("design", d), ("holdout", h)):
            if s.get("inconclusive"):
                print(f"  {lab}: inconclusive ({s['events']} events)"); continue
            print(f"  {lab:8s} events {s['events']:4d} tickers {s['leaders']:4d} mean {s['mean']:+.2%} median {s['median']:+.2%} "
                  f"positive {s['share_positive']:.0%} p {s['bootstrap_p']:.4f}")
        print(f"  design mean without the 10 most negative events {without_worst:+.2%}")
        for y, s in results[name]["by_year"].items():
            if not s.get("inconclusive"):
                print(f"    {y} events {s['events']:4d} mean {s['mean']:+.2%}")
        for k, v in crit.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print(f"  {name} {'PASSES' if results[name]['passes'] else 'FAILS'}")
    (OUTPUT / "result.json").write_text(json.dumps({"registry": str(REGISTRY.relative_to(ROOT)), "positive_control": pc,
                                                    "events": int(len(out)), "results": results,
                                                    "live_trading_enabled": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit({"acquire": stage_acquire, "crawl": stage_crawl, "screen": stage_screen}[sys.argv[1]]())
