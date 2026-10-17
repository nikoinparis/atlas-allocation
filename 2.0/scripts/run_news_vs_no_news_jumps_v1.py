#!/usr/bin/env python3
"""Queue item A29: do big moves WITH company news drift, and big moves WITHOUT news reverse?

Pre-registered in config/news_vs_no_news_jumps_registry_v1.json (committed before the 8-K items
were extracted). Chan (2003) split, on EDGAR 8-K filings, for the 500 most liquid stocks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import acquire_results_dates_v1 as ard  # noqa: E402
import acquire_sec_earnings_8k_v1 as e8k  # noqa: E402
import run_blowout_results_leaders_v1 as a28  # noqa: E402
import run_news_jump_followers_v1 as a24  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/news_vs_no_news_jumps_registry_v1.json"
OUTPUT = ROOT / "evidence/news_vs_no_news_jumps_v1"
NEWS_ITEMS = {"1.01", "1.02", "2.01", "2.03", "3.02", "7.01", "8.01"}
JUMP, TOP, N_CONTROLS, BAR = 0.10, 500, 50, 0.025
HORIZONS = {"d21": 21, "d126": 126}
DESIGN, HOLDOUT = ("2012-01-01", "2018-12-31"), ("2019-01-01", "2025-06-30")


def all_8k(ciks: list[str]) -> pd.DataFrame:
    config = json.loads(e8k.CONFIG.read_text())
    fetcher = e8k.Fetcher(e8k.DEFAULT_CACHE, ard.UA, config["minimum_seconds_between_requests"],
                          config["request_timeout_seconds"], config["maximum_attempts"])
    rows = []
    for cik in ciks:
        main, _, _ = fetcher.json(config["source_endpoint"].format(cik10=cik), f"submissions_{cik}")
        payloads = [main]
        for filename in e8k.overlapping_history_files(main, ard.START):
            p, _, _ = fetcher.json(config["historical_source_endpoint"].format(filename=filename),
                                   f"submissions_{cik}_{filename.removesuffix('.json')}")
            payloads.append(p)
        for payload in payloads:
            for r in e8k.columnar_rows(payload):
                if r.get("form") in {"8-K", "8-K/A"} and str(r.get("filingDate") or "") >= ard.START:
                    rows.append({"cik10": cik, "available_at": r.get("acceptanceDateTime"),
                                 "items": str(r.get("items") or ""), "form": r["form"]})
    return pd.DataFrame(rows).dropna(subset=["available_at"]).drop_duplicates()


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261018)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    status = pd.read_csv(ROOT / "data/results_dates_v1/issuer_status.csv", dtype={"cik10": str})
    filings = all_8k(list(status[status.status == "complete"].cik10))
    filings = filings[filings.cik10.isin(col_pos)]
    rd = a28.reaction_days(filings, dates)
    rd["item_set"] = rd["items"].str.split(",").apply(lambda xs: {x.strip() for x in xs if x.strip()})
    any_day, results_day, news_day = set(), set(), {}
    for r in rd.itertuples():
        key = (col_pos[r.cik10], int(r.reaction_pos))
        any_day.add(key)
        if "2.02" in r.item_set:
            results_day.add(key)
        hit = r.item_set & NEWS_ITEMS
        if hit:
            news_day.setdefault(key, set()).update(hit)
    print(f"8-K filings {len(rd):,} for {rd.cik10.nunique()} issuers; news-item reaction days {len(news_day):,}")

    px, dv = prices.to_numpy(), dollar.to_numpy()
    R = np.vstack([np.full(len(cols), np.nan), px[1:] / px[:-1] - 1.0])
    R = np.where(np.abs(R) < 1.0, R, np.nan)
    tick = pd.read_csv(a28.CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False) \
        .drop_duplicates("cik10").set_index("cik10").symbol
    rows, sic_cache = [], {}
    start, end = dates.searchsorted(pd.Timestamp(DESIGN[0])), dates.searchsorted(pd.Timestamp(HOLDOUT[1]), side="right")
    for t in range(max(start, 64), end):
        if t + 1 + max(HORIZONS.values()) >= len(dates):
            break
        liquid = (px[t - 1] >= 5) & (dv[t - 1] >= 5e6) & np.isfinite(R[t])
        if liquid.sum() < 300:
            continue
        ew = np.nanmean(R[t][liquid])
        top = np.argsort(-np.where(liquid, dv[t - 1], -np.inf))[:TOP]
        movers = [i for i in top if abs(R[t, i] - ew) >= JUMP]
        if not movers:
            continue
        when = dates[t]
        key = (when.year, when.month)
        if key not in sic_cache:
            sic_cache[key] = a19.sic_as_of(sic, when).reindex(cols).str[:2].to_numpy(dtype=object)
        sic2 = sic_cache[key]
        liquid_idx = np.flatnonzero(liquid)
        for i in movers:
            if (i, t) in results_day:
                kind = "results"
            elif (i, t) in news_day:
                kind = "news"
            elif (i, t) not in any_day and (i, t - 1) not in any_day:
                kind = "no_news"
            else:
                kind = "other_filing"
            pool = [k for k in liquid_idx if sic2[k] == sic2[i] and k != i] if isinstance(sic2[i], str) else []
            if len(pool) < 5:
                continue
            ctrl = rng.choice(pool, size=N_CONTROLS, replace=True)
            move = float(R[t, i] - ew)
            row = {"date": when, "month": when.strftime("%Y-%m"), "leader": tick.get(cols[i], cols[i]), "move": move,
                   "direction": "up" if move > 0 else "down", "kind": kind,
                   "items": ",".join(sorted(news_day.get((i, t), set())))}
            for name, h in HORIZONS.items():
                f = px[t + 1 + h, i] / px[t + 1, i] - 1.0
                c = np.nanmean(px[t + 1 + h, ctrl] / px[t + 1, ctrl] - 1.0)
                row[name] = f - c if np.isfinite(f) and np.isfinite(c) else np.nan
            rows.append(row)
    ev = pd.DataFrame(rows)
    ev.to_csv(OUTPUT / "events.csv", index=False)
    win = lambda f, a, b: f[(f.date >= a) & (f.date <= b)]  # noqa: E731

    def cell(kind, direction, col, w):
        return a24.summarise(win(ev[(ev.kind == kind) & (ev.direction == direction)], *w), col, rng)

    print("\nevent counts:\n", ev.groupby(["direction", "kind"]).size().to_string())
    results = {}
    for trial, kind, sign in (("T1_news_up_126d", "news", +1), ("T2_no_news_up_126d", "no_news", -1)):
        d, h = cell(kind, "up", "d126", DESIGN), cell(kind, "up", "d126", HOLDOUT)
        crit = {"design_sign_and_p": sign * d["mean"] > 0 and d["bootstrap_p"] < BAR,
                "holdout_sign": sign * h["mean"] > 0,
                "design_survives_top10": sign * d["mean_without_top10_events"] > 0,
                "design_magnitude_above_50bps": sign * d["mean"] > 0.005}
        results[trial] = {"design": d, "holdout": h, "criteria": crit, "passes": all(crit.values()),
                          "regimes": {lab: a24.summarise(win(ev[(ev.kind == kind) & (ev.direction == "up")], a, b), "d126", rng)
                                      for lab, (a, b) in a24.REGIMES.items()}}
        print(f"\n== {trial} (declared {'POSITIVE' if sign > 0 else 'NEGATIVE'})")
        for lab, s in (("design", d), ("holdout", h)):
            print(f"  {lab:8s} events {s['events']:4d} mean {s['mean']:+.2%} median {s['median']:+.2%} positive {s['share_positive']:.0%} "
                  f"p {s['bootstrap_p']:.4f} without top-10 {s['mean_without_top10_events']:+.2%}")
        for lab, s in results[trial]["regimes"].items():
            if not s.get("inconclusive"):
                print(f"    {lab:12s} events {s['events']:4d} mean {s['mean']:+.2%} p {s['bootstrap_p']:.3f}")
        for k, v in crit.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
        print(f"  {trial} {'PASSES' if results[trial]['passes'] else 'FAILS'}")
    print("\ndiagnostics (126d, design | holdout):")
    diag = {}
    for kind in ("news", "no_news", "results", "other_filing"):
        for direction in ("up", "down"):
            d, h = cell(kind, direction, "d126", DESIGN), cell(kind, direction, "d126", HOLDOUT)
            diag[f"{kind}_{direction}"] = {"design": d, "holdout": h}
            if not d.get("inconclusive") and not h.get("inconclusive"):
                print(f"  {kind:12s} {direction:4s} n {d['events']:4d} mean {d['mean']:+6.2%} p {d['bootstrap_p']:.3f} | "
                      f"n {h['events']:4d} mean {h['mean']:+6.2%} p {h['bootstrap_p']:.3f}")
    (OUTPUT / "result.json").write_text(json.dumps({"registry": str(REGISTRY.relative_to(ROOT)), "results": results,
                                                    "diagnostics": diag, "live_trading_enabled": False,
                                                    "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
