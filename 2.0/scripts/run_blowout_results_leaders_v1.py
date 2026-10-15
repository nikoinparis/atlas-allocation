#!/usr/bin/env python3
"""Queue item A28: buy the leader itself after a blowout results day, hold for months.

Pre-registered in config/blowout_results_leaders_registry_v1.json (committed before the results
dates were acquired). The main wave rather than its peers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_news_jump_followers_v1 as a24  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/blowout_results_leaders_registry_v1.json"
EVENTS = ROOT / "data/results_dates_v1/results_8k_events.csv"
OUTPUT = ROOT / "evidence/blowout_results_leaders_v1"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
JUMP, TOP, N_CONTROLS, BAR = 0.10, 500, 50, 0.025
HORIZONS = {"T1_blowout_leader_63d": 63, "T2_blowout_leader_126d": 126}
DESIGN, HOLDOUT = ("2012-01-01", "2018-12-31"), ("2019-01-01", "2025-06-30")


def reaction_days(events: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
    t = pd.to_datetime(events.available_at, utc=True).dt.tz_convert("America/New_York")
    day = t.dt.tz_localize(None).dt.normalize()
    after_close = t.dt.hour >= 16
    pos = dates.searchsorted(day)                                   # first trading day >= calendar day
    same_day_ok = (pos < len(dates)) & (dates[np.minimum(pos, len(dates) - 1)] == day) & ~after_close
    pos = np.where(same_day_ok, pos, dates.searchsorted(day, side="right"))
    out = events.assign(reaction_pos=pos)
    return out[out.reaction_pos < len(dates)]


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261019)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    tick = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False) \
        .drop_duplicates("cik10").set_index("cik10").symbol
    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    px, dv = prices.to_numpy(), dollar.to_numpy()
    R = np.vstack([np.full(len(cols), np.nan), px[1:] / px[:-1] - 1.0])
    R = np.where(np.abs(R) < 1.0, R, np.nan)

    raw = pd.read_csv(EVENTS, dtype={"cik10": str})
    raw = raw[raw.cik10.isin(col_pos)]
    rd = reaction_days(raw, dates)
    results_days = set(zip(rd.cik10.map(col_pos), rd.reaction_pos))

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
            pool = [k for k in liquid_idx if sic2[k] == sic2[i] and k != i] if isinstance(sic2[i], str) else []
            if len(pool) < 5:
                continue
            ctrl = rng.choice(pool, size=N_CONTROLS, replace=True)
            row = {"date": when, "month": when.strftime("%Y-%m"), "leader": tick.get(cols[i], cols[i]),
                   "reaction": float(R[t, i] - ew), "results_day": (i, t) in results_days}
            for name, h in HORIZONS.items():
                f = px[t + 1 + h, i] / px[t + 1, i] - 1.0
                c = np.nanmean(px[t + 1 + h, ctrl] / px[t + 1, ctrl] - 1.0)
                row[name] = f - c if np.isfinite(f) and np.isfinite(c) else np.nan
            rows.append(row)
    ev = pd.DataFrame(rows)
    ev.to_csv(OUTPUT / "events.csv", index=False)
    blow = ev[ev.results_day & (ev.reaction >= JUMP)]
    print(f"results days found: {len(rd):,} for {rd.cik10.nunique()} issuers; top-500 moves >= 10%: {len(ev):,}; "
          f"blowout results days: {len(blow):,}")
    win = lambda f, a, b: f[(f.date >= a) & (f.date <= b)]          # noqa: E731
    results = {}
    for name in HORIZONS:
        d, h = a24.summarise(win(blow, *DESIGN), name, rng), a24.summarise(win(blow, *HOLDOUT), name, rng)
        res = {"design": d, "holdout": h,
               "regimes": {lab: a24.summarise(win(blow, a, b), name, rng) for lab, (a, b) in a24.REGIMES.items()},
               "diagnostic_non_results_jumps": {lab: a24.summarise(win(ev[~ev.results_day & (ev.reaction >= JUMP)], *w), name, rng)
                                                for lab, w in (("design", DESIGN), ("holdout", HOLDOUT))},
               "diagnostic_blowdown_results_days": {lab: a24.summarise(win(ev[ev.results_day & (ev.reaction <= -JUMP)], *w), name, rng)
                                                    for lab, w in (("design", DESIGN), ("holdout", HOLDOUT))}}
        res["criteria"] = {"design_mean_positive_p_below_bar": d["mean"] > 0 and d["bootstrap_p"] < BAR,
                           "holdout_mean_positive": h["mean"] > 0,
                           "design_survives_dropping_top10_events": d["mean_without_top10_events"] > 0,
                           "design_mean_above_50bps": d["mean"] > 0.005}
        res["passes"] = all(res["criteria"].values())
        results[name] = res
        print(f"\n== {name}")
        for lab in ("design", "holdout"):
            s = res[lab]
            print(f"  {lab:8s} events {s['events']:4d} names {s['leaders']:4d} mean {s['mean']:+.2%} median {s['median']:+.2%} "
                  f"positive {s['share_positive']:.0%} p {s['bootstrap_p']:.4f} without top-10 {s['mean_without_top10_events']:+.2%}")
        for lab, s in res["regimes"].items():
            if not s.get("inconclusive"):
                print(f"    {lab:12s} events {s['events']:4d} mean {s['mean']:+.2%} p {s['bootstrap_p']:.3f}")
        for lab in ("design", "holdout"):
            nr, bd = res["diagnostic_non_results_jumps"][lab], res["diagnostic_blowdown_results_days"][lab]
            print(f"  diagnostic {lab}: non-results jumps mean {nr.get('mean', float('nan')):+.2%} (n {nr['events']}); "
                  f"results blow-downs mean {bd.get('mean', float('nan')):+.2%} (n {bd['events']})")
        for c, v in res["criteria"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {c}")
        print(f"  {name} {'PASSES' if res['passes'] else 'FAILS'}")
    print("\nlargest blowout results days (126d outcome):")
    print(blow.sort_values("reaction", ascending=False).head(20)[["date", "leader", "reaction", "T2_blowout_leader_126d"]]
          .to_string(index=False))
    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "results_days": int(len(rd)), "blowouts": int(len(blow)),
        "results": results, "live_trading_enabled": False, "strategy_promotion_authorized": False},
        indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
