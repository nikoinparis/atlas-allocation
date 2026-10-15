#!/usr/bin/env python3
"""Queue item A24: when a big stock jumps on news, do its unmoved product peers catch up?

Pre-registered in config/news_jump_followers_registry_v1.json (committed before computing).
Event-driven, fast entry (close of the day after the jump), held 21 or 126 trading days, measured
against random same-SIC2 firms that are not linked to the leader.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_network_peer_screen_v1 as net  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/news_jump_followers_registry_v1.json"
OUTPUT = ROOT / "evidence/news_jump_followers_v1"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
JUMP, TOP_LEADERS, N_FOLLOWERS, N_CONTROLS = 0.10, 500, 10, 50
HORIZONS = {"T1_followers_21d": 21, "T2_followers_126d": 126}
BAR = 0.025
DESIGN, HOLDOUT = ("2012-01-01", "2018-12-31"), ("2019-01-01", "2025-06-30")
REGIMES = {"2012-2019": ("2012-01-01", "2019-12-31"), "2020": ("2020-01-01", "2020-12-31"),
           "2021-2022": ("2021-01-01", "2022-12-31"), "2023-2025H1": ("2023-01-01", "2025-06-30")}


def bootstrap_p(values: pd.Series, months: pd.Series, rng, block: int = 3) -> float:
    by_month = values.groupby(months).apply(list)
    keys = list(by_month.index)
    obs = values.mean()
    draws = np.empty(4000)
    for k in range(4000):
        starts = rng.integers(0, max(1, len(keys) - block), size=int(np.ceil(len(keys) / block)))
        pick = [keys[s + o] for s in starts for o in range(block) if s + o < len(keys)][:len(keys)]
        sample = np.concatenate([by_month[m] for m in pick])
        draws[k] = sample.mean() - obs
    return float((np.abs(draws) >= abs(obs)).mean())


def summarise(ev: pd.DataFrame, col: str, rng) -> dict:
    ev = ev.dropna(subset=[col])
    if len(ev) < 30:
        return {"events": int(len(ev)), "inconclusive": True}
    contrib = ev[col].sort_values(ascending=False)
    without_top10 = float(ev[col].drop(contrib.index[:10]).mean())
    return {"events": int(len(ev)), "leaders": int(ev.leader.nunique()), "mean": float(ev[col].mean()),
            "median": float(ev[col].median()), "share_positive": float((ev[col] > 0).mean()),
            "t_naive": float(ev[col].mean() / (ev[col].std(ddof=1) / np.sqrt(len(ev)))),
            "bootstrap_p": bootstrap_p(ev[col], ev.month, rng), "mean_without_top10_events": without_top10}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261015)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    pairs = net.load_pairs(net.EXPERIMENTS["etnic"])
    links = pd.read_csv(a19.LINKS, dtype={"gvkey": str})
    links["gvkey"] = links.gvkey.astype(int)
    links["cik10"] = links.cik.astype("int64").astype(str).str.zfill(10)
    links["first_date"] = pd.to_datetime(links.first_date)
    links["last_date"] = pd.to_datetime(links.last_date)
    tick = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False) \
        .drop_duplicates("cik10").set_index("cik10").symbol

    dates, cols = prices.index, np.array(prices.columns)
    col_pos = {c: i for i, c in enumerate(cols)}
    px = prices.to_numpy()
    R = np.vstack([np.full(len(cols), np.nan), px[1:] / px[:-1] - 1.0])
    R = np.where(np.abs(R) < 1.0, R, np.nan)
    dv = dollar.to_numpy()

    net_cache, sic_cache, events, followers_log = {}, {}, [], []
    start = dates.searchsorted(pd.Timestamp(DESIGN[0]))
    end = dates.searchsorted(pd.Timestamp(HOLDOUT[1]), side="right")
    for t in range(max(start, 64), end):
        if t + 1 + max(HORIZONS.values()) >= len(dates):
            break
        liquid = (px[t - 1] >= a19.MIN_PRICE) & (dv[t - 1] >= a19.MIN_DOLLAR_VOLUME) & np.isfinite(R[t])
        if liquid.sum() < 300:
            continue
        ew = np.nanmean(R[t][liquid])
        rank_dv = np.where(liquid, dv[t - 1], -np.inf)
        leaders_pool = np.argsort(-rank_dv)[:TOP_LEADERS]
        jumpers = [i for i in leaders_pool if R[t, i] - ew >= JUMP]
        if not jumpers:
            continue
        when = dates[t]
        year = a19.tnic_year_for(when)
        if year not in net_cache:
            mapping = a19.gvkey_to_cik(links, pd.Timestamp(f"{year + 1}-07-01"))
            e = pairs[pairs.year == year]
            c1, c2 = e.gvkey1.map(mapping), e.gvkey2.map(mapping)
            keep = c1.isin(col_pos) & c2.isin(col_pos) & (c1 != c2)
            ed = pd.DataFrame({"i": c1[keep].map(col_pos).to_numpy(), "j": c2[keep].map(col_pos).to_numpy(),
                               "w": e.score[keep].to_numpy()}).sort_values("w", ascending=False)
            net_cache[year] = {i: g.j.to_numpy() for i, g in ed.groupby("i")}
        peers_of = net_cache[year]
        mkey = (when.year, when.month)
        if mkey not in sic_cache:
            sic_cache[mkey] = a19.sic_as_of(sic, when).reindex(cols).str[:2].to_numpy(dtype=object)
        sic2 = sic_cache[mkey]
        liquid_idx = np.flatnonzero(liquid)
        by_sic2 = pd.Series(liquid_idx).groupby(pd.Series(sic2[liquid_idx])).apply(np.array).to_dict()
        for i in jumpers:
            all_peers = peers_of.get(i)
            if all_peers is None:
                continue
            liquid_peers = [j for j in all_peers if liquid[j] and R[t, j] - ew < JUMP][:N_FOLLOWERS]
            if not liquid_peers:
                continue
            peer_set = set(all_peers) | {i}
            rows = []
            for j in liquid_peers:
                pool = by_sic2.get(sic2[j])
                if pool is None:
                    continue
                pool = np.array([k for k in pool if k not in peer_set])
                if len(pool) < 5:
                    continue
                ctrl = rng.choice(pool, size=N_CONTROLS, replace=True)
                row = {"j": j, "moved": bool(R[t, j] >= 0.5 * R[t, i]),
                       "day0": R[t, j] - np.nanmean(R[t, ctrl])}
                for name, h in HORIZONS.items():
                    f = px[t + 1 + h, j] / px[t + 1, j] - 1.0
                    c = np.nanmean(px[t + 1 + h, ctrl] / px[t + 1, ctrl] - 1.0)
                    row[name] = f - c if np.isfinite(f) and np.isfinite(c) else np.nan
                rows.append(row)
            if not rows:
                continue
            fr = pd.DataFrame(rows)
            unmoved = fr[~fr.moved]
            ev = {"date": when, "month": when.strftime("%Y-%m"), "leader": tick.get(cols[i], cols[i]),
                  "leader_jump": float(R[t, i] - ew), "followers": int(len(unmoved)), "moved_followers": int(fr.moved.sum()),
                  "day0_followers_vs_control": float(unmoved.day0.mean()) if len(unmoved) else np.nan}
            for name, h in HORIZONS.items():
                ev[name] = float(unmoved[name].mean()) if len(unmoved) else np.nan
                ev[name + "_moved"] = float(fr[fr.moved][name].mean()) if fr.moved.any() else np.nan
                lf = px[t + 1 + h, i] / px[t + 1, i] - 1.0
                ew_cum = np.nanmean(px[t + 1 + h, liquid_idx] / px[t + 1, liquid_idx] - 1.0)
                ev[name + "_leader_drift"] = float(lf - ew_cum) if np.isfinite(lf) else np.nan
            events.append(ev)
    ev = pd.DataFrame(events)
    ev.to_csv(OUTPUT / "events.csv", index=False)

    def win(a, b):
        return ev[(ev.date >= a) & (ev.date <= b)]

    print(f"events {len(ev)}, distinct leaders {ev.leader.nunique()}, median unmoved followers per event {ev.followers.median():.0f}")
    pc = {lab: float(win(*w).day0_followers_vs_control.mean()) for lab, w in {"design": DESIGN, "holdout": HOLDOUT}.items()}
    print(f"positive control: unmoved followers' day-0 return minus same-SIC2 controls: design {pc['design']:+.2%}, holdout {pc['holdout']:+.2%}")
    results = {}
    for name in HORIZONS:
        d, h = summarise(win(*DESIGN), name, rng), summarise(win(*HOLDOUT), name, rng)
        res = {"design": d, "holdout": h,
               "regimes": {lab: summarise(win(a, b), name, rng) for lab, (a, b) in REGIMES.items()},
               "diagnostic_moved_followers_design": summarise(win(*DESIGN).rename(columns={name: "_x", name + "_moved": name}), name, rng),
               "diagnostic_leader_drift_design": float(win(*DESIGN)[name + "_leader_drift"].mean()),
               "diagnostic_leader_drift_holdout": float(win(*HOLDOUT)[name + "_leader_drift"].mean())}
        res["criteria"] = {
            "design_mean_positive_p_below_bar": d["mean"] > 0 and d["bootstrap_p"] < BAR,
            "holdout_mean_positive": h["mean"] > 0,
            "design_survives_dropping_top10_events": d["mean_without_top10_events"] > 0,
            "design_mean_above_50bps": d["mean"] > 0.005,
        }
        res["passes"] = all(res["criteria"].values())
        results[name] = res
        print(f"\n== {name}")
        for lab in ("design", "holdout"):
            s = res[lab]
            print(f"  {lab:8s} events {s['events']:5d} leaders {s['leaders']:4d}  mean {s['mean']:+.2%} median {s['median']:+.2%} "
                  f"positive {s['share_positive']:.0%}  p {s['bootstrap_p']:.4f}  without top-10 {s['mean_without_top10_events']:+.2%}")
        for lab, s in res["regimes"].items():
            if not s.get("inconclusive"):
                print(f"    {lab:12s} events {s['events']:5d} mean {s['mean']:+.2%} p {s['bootstrap_p']:.3f}")
        m = res["diagnostic_moved_followers_design"]
        print(f"  diagnostic: followers that DID move day 0, design mean {m.get('mean', float('nan')):+.2%}; "
              f"leader's own drift design {res['diagnostic_leader_drift_design']:+.2%}, holdout {res['diagnostic_leader_drift_holdout']:+.2%}")
        for c, v in res["criteria"].items():
            print(f"  [{'PASS' if v else 'FAIL'}] {c}")
        print(f"  {name} {'PASSES' if res['passes'] else 'FAILS'}")
    top = ev.sort_values("T2_followers_126d", ascending=False).head(8)[["date", "leader", "leader_jump", "T2_followers_126d"]]
    print("\nlargest follower catch-ups (126d), for inspection:")
    print(top.to_string(index=False))
    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)), "events": int(len(ev)), "positive_control_day0": pc,
        "results": results, "live_trading_enabled": False, "strategy_promotion_authorized": False},
        indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
