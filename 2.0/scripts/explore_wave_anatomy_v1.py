#!/usr/bin/env python3
"""EXPLORATORY, owner-requested (2026-10-15): the anatomy of past booms. Not a strategy trial.

The owner asked to look back, accepting some overfitting, at which sectors and stocks rose fastest,
to understand how waves start and why rules here catch them late. This is hypothesis generation:
nothing below selects a strategy, and any rule it suggests must be tested on data it was not
derived from (a later window or forward) before it counts.

A. Industry waves (SIC3, equal weight, relative to the equal-weight liquid universe): trough-to-peak
   rises of >= +50% with no intervening fall of more than 25% from the running peak.
B. Detection lag: when a simple detector (trailing 6-month excess >= +20%) first fired inside each
   wave, and how much of the wave was left.
C. False starts: every time the detector fires, what happened next -- the base rate that decides
   whether "buy what has started rising" pays.
D. Stock multi-baggers: stocks that tripled within 36 months; how many were flagged by momentum,
   when, and how much was left.

Survivorship: delisted names are largely missing from the panel (Step 343), which flatters
crashes-to-zero out of the record. Read the false-start rates as optimistic.
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

OUTPUT = ROOT / "evidence/wave_anatomy_v1"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
WAVE_RISE, WAVE_BREAK, DETECT, MIN_MEMBERS = 0.50, 0.25, 0.20, 5


def zigzag_waves(index: pd.Series) -> list[dict]:
    """Rises of >= WAVE_RISE from a running trough, ended by a WAVE_BREAK fall from the peak."""
    waves, trough_t, trough_v, peak_t, peak_v, active = [], index.index[0], index.iloc[0], None, None, False
    for t, v in index.items():
        if not active:
            if v < trough_v:
                trough_t, trough_v = t, v
            elif v / trough_v - 1 >= WAVE_RISE:
                active, peak_t, peak_v = True, t, v
        else:
            if v > peak_v:
                peak_t, peak_v = t, v
            elif v / peak_v - 1 <= -WAVE_BREAK:
                waves.append({"trough": trough_t, "peak": peak_t, "rise": peak_v / trough_v - 1})
                active, trough_t, trough_v = False, t, v
    if active:
        waves.append({"trough": trough_t, "peak": peak_t, "rise": peak_v / trough_v - 1, "ongoing": True})
    return waves


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    daily = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(daily.columns)
    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False).drop_duplicates("cik10")
    tick = cat.set_index("cik10").symbol

    monthly = daily.resample("ME").last()
    dv = dollar.resample("ME").last().reindex(monthly.index)
    ret = monthly.pct_change(fill_method=None)
    ret = ret.where(ret.abs() < 3)
    months = monthly.index[monthly.index >= "2012-01-31"]

    # ------------------------------------------------------------- industry panel (SIC3)
    ind_rows = []
    for m_prev, m in zip(months[:-1], months[1:]):
        liquid = (monthly.loc[m_prev] >= 5) & (dv.loc[m_prev] >= 5e6)
        groups = a19.sic_as_of(sic, m_prev).reindex(monthly.columns).str[:3]
        r = ret.loc[m][liquid & groups.notna()]
        univ = r.mean()
        g = r.groupby(groups[r.index])
        stats = pd.DataFrame({"ret": g.mean(), "n": g.count()})
        stats = stats[stats.n >= MIN_MEMBERS]
        for code, row in stats.iterrows():
            ind_rows.append({"month": m, "sic3": code, "excess": (1 + row.ret) / (1 + univ) - 1, "n": int(row.n)})
    ind = pd.DataFrame(ind_rows)
    rel = ind.pivot(index="month", columns="sic3", values="excess")
    members = ind.pivot(index="month", columns="sic3", values="n")

    waves = []
    for code in rel.columns:
        x = rel[code].dropna()
        if len(x) < 24:
            continue
        index = (1 + x).cumprod()
        for w in zigzag_waves(index):
            trail6 = index / index.shift(6) - 1
            inside = trail6[(trail6.index > w["trough"]) & (trail6.index <= w["peak"])]
            fired = inside[inside >= DETECT]
            det = fired.index[0] if len(fired) else None
            peak_v, trough_v = index[w["peak"]], index[w["trough"]]
            captured = (np.log(peak_v / index[det]) / np.log(peak_v / trough_v)) if det is not None else np.nan
            top = []
            groups = a19.sic_as_of(sic, w["peak"]).reindex(monthly.columns).str[:3]
            names = groups[groups == code].index
            span = monthly.loc[w["trough"]:w["peak"], names]
            if len(span) > 1:
                gain = (span.iloc[-1] / span.iloc[0] - 1).dropna().sort_values(ascending=False)
                top = [f"{tick.get(c, c)} {g:+.0%}" for c, g in gain.head(5).items()]
            waves.append({"sic3": code, "trough": w["trough"].date(), "peak": w["peak"].date(),
                          "months": int(round((w["peak"] - w["trough"]).days / 30.4)),
                          "excess_rise": w["rise"], "ongoing": w.get("ongoing", False),
                          "median_members": float(members[code].loc[w["trough"]:w["peak"]].median()),
                          "detected": det.date() if det is not None else None,
                          "detect_lag_months": int(round((det - w["trough"]).days / 30.4)) if det is not None else None,
                          "share_of_wave_left_after_detection": captured, "top_members": top})
    waves = pd.DataFrame(waves).sort_values("excess_rise", ascending=False)
    waves.to_csv(OUTPUT / "industry_waves.csv", index=False)

    # ------------------------------------------------------------- detector base rates
    events = []
    for code in rel.columns:
        x = rel[code].dropna()
        index = (1 + x).cumprod()
        trail6 = index / index.shift(6) - 1
        fire = (trail6 >= DETECT) & (trail6.shift(1) < DETECT)
        for t in fire[fire].index:
            fwd = index.loc[t:]
            out = {"sic3": code, "month": t.date()}
            for h in (6, 12, 24):
                out[f"fwd_{h}m_excess"] = float(fwd.iloc[h] / fwd.iloc[0] - 1) if len(fwd) > h else np.nan
            path = fwd.iloc[:25] / fwd.iloc[0]
            out["max_rise_24m"] = float(path.max() - 1)
            out["crash_40pct_24m"] = bool((path / path.cummax()).min() <= 0.60)
            out["became_wave"] = any((w.sic3 == code) and (pd.Timestamp(w.trough) <= t <= pd.Timestamp(w.peak))
                                     for w in waves.itertuples())
            events.append(out)
    events = pd.DataFrame(events)
    events.to_csv(OUTPUT / "detector_events.csv", index=False)
    all_months = []
    for code in rel.columns:
        index = (1 + rel[code].dropna()).cumprod()
        for h in (12,):
            all_months.append((index.shift(-h) / index - 1).dropna())
    base_12 = float(pd.concat(all_months).mean())

    # ------------------------------------------------------------- stock multi-baggers
    mom = monthly.shift(1) / monthly.shift(12) - 1
    rows = []
    for t in months[months <= months[-1] - pd.DateOffset(months=36)]:
        liquid = (monthly.loc[t] >= 5) & (dv.loc[t] >= 5e6)
        fwd36 = monthly.shift(-36).loc[t] / monthly.loc[t] - 1
        m = mom.loc[t][liquid]
        dec = pd.qcut(m.rank(method="first"), 10, labels=False) if m.notna().sum() > 100 else None
        if dec is None:
            continue
        frame = pd.DataFrame({"fwd36": fwd36[m.index], "decile": dec})
        frame["tripled"] = frame.fwd36 >= 2.0
        frame["month"] = t
        rows.append(frame.dropna(subset=["fwd36"]))
    stocks = pd.concat(rows)
    by_decile = stocks.groupby("decile").agg(stock_months=("tripled", "size"), tripled_rate=("tripled", "mean"),
                                             mean_fwd36=("fwd36", "mean"), median_fwd36=("fwd36", "median"))

    # When did momentum first flag each distinct triple, and how much was left?
    flags = []
    long = stocks.rename_axis("cik").reset_index()
    dec_piv = long.pivot_table(index="month", columns="cik", values="decile", aggfunc="first")
    first_starts = long[long.tripled].sort_values("month").drop_duplicates("cik")
    for row in first_starts.itertuples():
        t0, end = row.month, row.month + pd.DateOffset(months=36)
        d = dec_piv[row.cik].loc[t0:end] if row.cik in dec_piv else pd.Series(dtype=float)
        hit = d[d == 9]
        p0, p_end = monthly.at[t0, row.cik], monthly[row.cik].loc[t0:end].max()
        left, fm = np.nan, None
        if len(hit):
            fm = hit.index[0]
            pf = monthly.at[fm, row.cik]
            left = float(np.log(p_end / pf) / np.log(p_end / p0)) if p_end > p0 else np.nan
        flags.append({"cik": row.cik, "ticker": tick.get(row.cik, row.cik), "start": t0.date(),
                      "flagged_top_momentum_decile": fm.date() if fm is not None else None,
                      "months_to_flag": int(round((fm - t0).days / 30.4)) if fm is not None else None,
                      "share_of_move_left_after_flag": left})
    flags = pd.DataFrame(flags)
    flags.to_csv(OUTPUT / "triplers_momentum_flag.csv", index=False)

    # ------------------------------------------------------------- print
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 90)
    print(f"EXPLORATORY -- industry waves (SIC3 excess over EW universe >= +{WAVE_RISE:.0%}), 2012-2026: {len(waves)}")
    show = waves.head(30).copy()
    show["excess_rise"] = show.excess_rise.map("{:+.0%}".format)
    show["left"] = show.share_of_wave_left_after_detection.map(lambda v: "" if pd.isna(v) else f"{v:.0%}")
    print(show[["sic3", "trough", "peak", "months", "excess_rise", "median_members", "detect_lag_months", "left",
                "top_members"]].to_string(index=False))
    d = waves.share_of_wave_left_after_detection.dropna()
    print(f"\nwaves detected by trailing-6m >= +20%: {waves.detected.notna().sum()} of {len(waves)}; "
          f"median lag {waves.detect_lag_months.median():.0f} months; median share of wave left after detection {d.median():.0%}")
    print(f"\ndetector firings: {len(events)}; became part of a wave: {events.became_wave.mean():.0%}; "
          f"crashed 40% within 24m: {events.crash_40pct_24m.mean():.0%}")
    print(f"  mean forward excess after firing: 6m {events.fwd_6m_excess.mean():+.1%}, 12m {events.fwd_12m_excess.mean():+.1%} "
          f"(all industry-months 12m: {base_12:+.1%}), 24m {events.fwd_24m_excess.mean():+.1%}")
    print(f"  median forward 12m excess {events.fwd_12m_excess.median():+.1%}; share positive {(events.fwd_12m_excess > 0).mean():.0%}")
    print("\nstocks: probability of tripling within 36 months, by 12-1 momentum decile at the start (liquid universe)")
    print(by_decile.assign(tripled_rate=by_decile.tripled_rate.map("{:.1%}".format),
                           mean_fwd36=by_decile.mean_fwd36.map("{:+.0%}".format),
                           median_fwd36=by_decile.median_fwd36.map("{:+.0%}".format)).to_string())
    f = flags.dropna(subset=["months_to_flag"])
    print(f"\ndistinct triplers {len(flags)}; ever in top momentum decile within the window {len(f)} ({len(f)/len(flags):.0%}); "
          f"median months to flag {f.months_to_flag.median():.0f}; median share of move left after flag "
          f"{f.share_of_move_left_after_flag.median():.0%}")
    (OUTPUT / "result.json").write_text(json.dumps({
        "exploratory_not_a_trial": True, "owner_request": "2026-10-15",
        "waves": int(len(waves)), "detected": int(waves.detected.notna().sum()),
        "median_detect_lag_months": float(waves.detect_lag_months.median()),
        "median_share_left_after_detection": float(d.median()),
        "detector_firings": int(len(events)), "firings_became_wave": float(events.became_wave.mean()),
        "firings_crashed_40pct_24m": float(events.crash_40pct_24m.mean()),
        "fwd_excess_after_firing": {h: float(events[f"fwd_{h}m_excess"].mean()) for h in (6, 12, 24)},
        "all_industry_months_fwd_12m": base_12,
        "triple_rate_by_momentum_decile": by_decile.tripled_rate.to_dict(),
        "triplers": int(len(flags)), "triplers_flagged": int(len(f)),
        "median_months_to_flag": float(f.months_to_flag.median()),
        "median_share_left_after_flag": float(f.share_of_move_left_after_flag.median()),
        "survivorship_note": "delisted names largely missing; false-start and crash rates are optimistic"},
        indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
