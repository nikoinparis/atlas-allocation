#!/usr/bin/env python3
"""Queue item A27: does earnings confirmation catch the main wave earlier, with fewer false starts?

Pre-registered in config/boom_earnings_confirmation_registry_v1.json (committed before this ran).
Q1: among Step 359's price-alarm firings, do industries whose earnings are also beating (top-third
    mean SUE) outperform the unconfirmed ones?
Q2: do industries whose earnings beat two quarters running, before their price has moved,
    outperform over the next 12 months?
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/boom_earnings_confirmation_registry_v1.json"
SUE = ROOT / "evidence/extended_sue_panel_v1/sue_panel.csv.gz"
ALARMS = ROOT / "evidence/wave_anatomy_v1/detector_events.csv"
OUTPUT = ROOT / "evidence/boom_earnings_confirmation_v1"
BAR, MIN_MEMBERS = 0.025, 5
HALVES = {"2012-2018": ("2012-01-01", "2018-12-31"), "2019-2026": ("2019-01-01", "2026-12-31")}


def industry_index(daily, sic, dollar):
    monthly = daily.resample("ME").last()
    dv = dollar.resample("ME").last().reindex(monthly.index)
    ret = monthly.pct_change(fill_method=None)
    ret = ret.where(ret.abs() < 3)
    months = monthly.index[monthly.index >= "2011-06-30"]
    rows = []
    for m_prev, m in zip(months[:-1], months[1:]):
        liquid = (monthly.loc[m_prev] >= 5) & (dv.loc[m_prev] >= 5e6)
        groups = a19.sic_as_of(sic, m_prev).reindex(monthly.columns).str[:3]
        r = ret.loc[m][liquid & groups.notna()]
        univ = r.mean()
        g = r.groupby(groups[r.index])
        st = pd.DataFrame({"ret": g.mean(), "n": g.count()})
        st = st[st.n >= MIN_MEMBERS]
        for code, row in st.iterrows():
            rows.append((m, code, (1 + row.ret) / (1 + univ) - 1))
    rel = pd.DataFrame(rows, columns=["month", "sic3", "x"]).pivot(index="month", columns="sic3", values="x")
    return (1 + rel.fillna(0)).cumprod().where(rel.notna().cummax()), monthly, dv


def block_diff_p(groups: dict, block: int, rng) -> tuple[float, float]:
    """groups: period -> (event_values, base_values). Pooled difference in means; centered block bootstrap."""
    keys = sorted(groups)

    def diff(ks):
        ev = np.concatenate([groups[k][0] for k in ks]) if ks else np.array([])
        ba = np.concatenate([groups[k][1] for k in ks]) if ks else np.array([])
        return (ev.mean() - ba.mean()) if len(ev) and len(ba) else np.nan

    obs = diff(keys)
    draws = []
    for _ in range(4000):
        starts = rng.integers(0, max(1, len(keys) - block), size=int(np.ceil(len(keys) / block)))
        ks = [keys[s + o] for s in starts for o in range(block) if s + o < len(keys)][:len(keys)]
        d = diff(ks)
        if np.isfinite(d):
            draws.append(d - obs)
    draws = np.array(draws)
    return float(obs), float((np.abs(draws) >= abs(obs)).mean())


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261017)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    daily = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(daily.columns)
    index, monthly, dv = industry_index(daily, sic, dollar)

    # Industry earnings score at each SUE date.
    sue = pd.read_csv(SUE, parse_dates=["decision_at"])
    sue["cik10"] = sue.cik10.astype("int64").astype(str).str.zfill(10)
    scores = []
    for d, panel in sue.groupby("decision_at"):
        e = d - pd.Timedelta(days=1)                         # month-end before the SUE date
        if e not in monthly.index:
            e = monthly.index[monthly.index <= e][-1]
        liquid = (monthly.loc[e] >= 5) & (dv.loc[e] >= 5e6)
        groups = a19.sic_as_of(sic, e).reindex(monthly.columns).str[:3]
        s = panel.set_index("cik10").standardized_unexpected_earnings.reindex(monthly.columns)
        ok = liquid & groups.notna() & s.notna()
        g = s[ok].groupby(groups[ok])
        st = pd.DataFrame({"mean_sue": g.mean(), "n": g.count(), "breadth": s[ok].gt(0).groupby(groups[ok]).mean()})
        st = st[st.n >= MIN_MEMBERS]
        st["top_third"] = st.mean_sue.rank(pct=True) > 2 / 3
        st["sue_date"], st["month_end"] = d, e
        scores.append(st.rename_axis("sic3").reset_index())
    scores = pd.DataFrame(pd.concat(scores, ignore_index=True))
    scores.to_csv(OUTPUT / "industry_earnings_scores.csv", index=False)
    sue_dates = sorted(scores.sue_date.unique())

    # ---------------- Q1
    alarms = pd.read_csv(ALARMS, parse_dates=["month"], dtype={"sic3": str})
    alarms["sic3"] = alarms.sic3.str.zfill(3)
    scores["sic3"] = scores.sic3.astype(str).str.zfill(3)
    conf = []
    for a in alarms.itertuples():
        prior = [d for d in sue_dates if d <= a.month + pd.Timedelta(days=1)]
        if not prior:
            conf.append(np.nan); continue
        row = scores[(scores.sue_date == prior[-1]) & (scores.sic3 == a.sic3)]
        conf.append(float(row.top_third.iloc[0]) if len(row) else np.nan)
    alarms["confirmed"] = conf
    q1 = alarms.dropna(subset=["confirmed", "fwd_12m_excess"]).copy()
    q1["period"] = q1.month.dt.to_period("M")
    groups = {p: (g[g.confirmed == 1].fwd_12m_excess.to_numpy(), g[g.confirmed == 0].fwd_12m_excess.to_numpy())
              for p, g in q1.groupby("period")}
    q1_diff, q1_p = block_diff_p(groups, 3, rng)
    q1_halves = {}
    for lab, (a, b) in HALVES.items():
        s = q1[(q1.month >= a) & (q1.month <= b)]
        q1_halves[lab] = {"confirmed_n": int((s.confirmed == 1).sum()), "unconfirmed_n": int((s.confirmed == 0).sum()),
                          "confirmed_mean": float(s[s.confirmed == 1].fwd_12m_excess.mean()),
                          "unconfirmed_mean": float(s[s.confirmed == 0].fwd_12m_excess.mean()),
                          "confirmed_became_wave": float(s[s.confirmed == 1].became_wave.mean()),
                          "unconfirmed_became_wave": float(s[s.confirmed == 0].became_wave.mean()),
                          "confirmed_share_positive": float((s[s.confirmed == 1].fwd_12m_excess > 0).mean()),
                          "unconfirmed_share_positive": float((s[s.confirmed == 0].fwd_12m_excess > 0).mean())}
    q1_pass = q1_diff > 0 and q1_p < BAR and all(h["confirmed_mean"] > 0 for h in q1_halves.values())

    # ---------------- Q2
    ev_rows, base_rows = [], []
    for k in range(1, len(sue_dates)):
        d0, d1 = sue_dates[k - 1], sue_dates[k]
        s0 = scores[scores.sue_date == d0].set_index("sic3")
        s1 = scores[scores.sue_date == d1].set_index("sic3")
        e = s1.month_end.iloc[0] if len(s1) else None
        if e is None:
            continue
        pos = index.index.get_indexer([e])[0]
        if pos < 6 or pos + 12 >= len(index):
            continue
        for code in s1.index:
            if code not in index.columns:
                continue
            fwd = index[code].iloc[pos + 12] / index[code].iloc[pos] - 1
            trail = index[code].iloc[pos] / index[code].iloc[pos - 6] - 1
            if not np.isfinite(fwd):
                continue
            base_rows.append({"sue_date": d1, "sic3": code, "fwd12": fwd})
            if s1.at[code, "top_third"] and code in s0.index and s0.at[code, "top_third"] and trail < 0.10:
                later_alarm = alarms[(alarms.sic3 == code) & (alarms.month > e) & (alarms.month <= e + pd.DateOffset(months=12))]
                ev_rows.append({"sue_date": d1, "sic3": code, "fwd12": fwd, "trail6": trail,
                                "alarm_within_12m": bool(len(later_alarm))})
    ev, base = pd.DataFrame(ev_rows), pd.DataFrame(base_rows)
    ev.to_csv(OUTPUT / "q2_events.csv", index=False)
    groups2 = {d: (ev[ev.sue_date == d].fwd12.to_numpy(), base[base.sue_date == d].fwd12.to_numpy())
               for d in base.sue_date.unique()}
    groups2 = {k: v for k, v in groups2.items() if len(v[0])}
    q2_diff, q2_p = block_diff_p(groups2, 2, rng)
    q2_halves = {}
    for lab, (a, b) in HALVES.items():
        s, bb = ev[(ev.sue_date >= a) & (ev.sue_date <= b)], base[(base.sue_date >= a) & (base.sue_date <= b)]
        q2_halves[lab] = {"events": int(len(s)), "events_mean": float(s.fwd12.mean()), "all_mean": float(bb.fwd12.mean()),
                          "difference": float(s.fwd12.mean() - bb.fwd12.mean()),
                          "events_share_positive": float((s.fwd12 > 0).mean())}
    q2_pass = q2_diff > 0 and q2_p < BAR and all(h["difference"] > 0 for h in q2_halves.values())

    print(f"Q1 earnings-confirmed price alarms: {len(q1)} firings with a score "
          f"({int((q1.confirmed == 1).sum())} confirmed, {int((q1.confirmed == 0).sum())} not)")
    print(f"  confirmed minus unconfirmed, next-12m excess: {q1_diff:+.2%}  p {q1_p:.4f}")
    for lab, h in q1_halves.items():
        print(f"  {lab}: confirmed n={h['confirmed_n']} mean {h['confirmed_mean']:+.2%} positive {h['confirmed_share_positive']:.0%} "
              f"became-wave {h['confirmed_became_wave']:.0%} | unconfirmed n={h['unconfirmed_n']} mean {h['unconfirmed_mean']:+.2%} "
              f"positive {h['unconfirmed_share_positive']:.0%} became-wave {h['unconfirmed_became_wave']:.0%}")
    print(f"  Q1 {'PASSES' if q1_pass else 'FAILS'}")
    print(f"\nQ2 earnings beat two quarters running, price not yet moved: {len(ev)} industry-quarters "
          f"(of {len(base)}); followed by a price alarm within 12m: {ev.alarm_within_12m.mean():.0%}")
    print(f"  events minus all industry-quarters, next-12m excess: {q2_diff:+.2%}  p {q2_p:.4f}")
    for lab, h in q2_halves.items():
        print(f"  {lab}: events {h['events']} mean {h['events_mean']:+.2%} (all {h['all_mean']:+.2%}) "
              f"difference {h['difference']:+.2%} positive {h['events_share_positive']:.0%}")
    print(f"  Q2 {'PASSES' if q2_pass else 'FAILS'}")
    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)),
        "Q1": {"firings": int(len(q1)), "difference": q1_diff, "p": q1_p, "halves": q1_halves, "passes": q1_pass},
        "Q2": {"events": int(len(ev)), "base": int(len(base)), "difference": q2_diff, "p": q2_p, "halves": q2_halves,
               "alarm_within_12m": float(ev.alarm_within_12m.mean()) if len(ev) else None, "passes": q2_pass},
        "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
