#!/usr/bin/env python3
"""Queue item A22: does last month's commodity move predict next month's exposed stocks?

Pre-registered in config/commodity_lead_lag_registry_v1.json (committed before anything was
computed). The owner's simplest theme chain ("AI booms, then metal rises") in testable form.

T1  hand-mapped producer groups (energy, precious metals, copper/base metals, grains) vs their
    commodity's last 4 weeks, pooled time-series slope.
T2  data-driven exposure: each stock's 104-week commodity betas x last-4-week commodity returns,
    cross-sectional screen exactly as A19.
T3  Driesprong, Jacobsen & Maat (2008) replication: last 4 weeks of oil vs next 4 weeks of the
    S&P 500 future, declared negative.
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

REGISTRY = ROOT / "config/commodity_lead_lag_registry_v1.json"
FUTURES = ROOT / "data/futures_roll_repaired_v1/weekly_returns_repaired.csv.gz"
OUTPUT = ROOT / "evidence/commodity_lead_lag_v1"
BAR = 0.0167
STEP, WINDOW, PLACEBO_RUNS = 4, 104, 200
COMMODITIES = ["CL=F", "NG=F", "HG=F", "GC=F", "SI=F", "ZC=F", "ZS=F", "ZW=F"]
GROUPS = {
    "energy": (["CL=F", "NG=F"], [(1311, 1311), (1381, 1382), (1389, 1389)]),
    "precious": (["GC=F", "SI=F"], [(1040, 1049)]),
    "base_metals": (["HG=F"], [(1000, 1039), (1090, 1099), (3330, 3339)]),
    "grains": (["ZC=F", "ZS=F", "ZW=F"], [(100, 199), (2870, 2879), (3523, 3523)]),
}


def compound(block: np.ndarray) -> np.ndarray:
    """Compounded return over rows; NaN if any week is missing."""
    return np.prod(1.0 + block, axis=0) - 1.0


def group_of(sic4: pd.Series) -> pd.Series:
    code = pd.to_numeric(sic4, errors="coerce")
    out = pd.Series(np.nan, index=sic4.index, dtype=object)
    for name, (_, ranges) in GROUPS.items():
        for a, b in ranges:
            out[(code >= a) & (code <= b)] = name
    return out


def slope(x: np.ndarray, y: np.ndarray) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 10:
        return float("nan")
    return float(np.polyfit(x[ok], y[ok], 1)[0])


def block_bootstrap_slope(frame: pd.DataFrame, rng, block: int = 6) -> float:
    """Centered block bootstrap over decision dates, groups kept together. Two-sided p."""
    dates = np.array(sorted(frame.date.unique()))
    by_date = {d: g for d, g in frame.groupby("date")}
    obs = slope(frame.x.to_numpy(), frame.y.to_numpy())
    draws = np.empty(4000)
    for k in range(4000):
        starts = rng.integers(0, max(1, len(dates) - block), size=int(np.ceil(len(dates) / block)))
        pick = np.concatenate([dates[s:s + block] for s in starts])[:len(dates)]
        sample = pd.concat([by_date[d] for d in pick])
        draws[k] = slope(sample.x.to_numpy(), sample.y.to_numpy()) - obs
    return float((np.abs(draws) >= abs(obs)).mean())


def newey_west_t(x: np.ndarray, y: np.ndarray, lags: int = 3) -> float:
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    u = y - X @ beta
    xu = X * u[:, None]
    s = xu.T @ xu
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        g = xu[lag:].T @ xu[:-lag]
        s += w * (g + g.T)
    inv = np.linalg.inv(X.T @ X)
    cov = inv @ s @ inv
    return float(beta[1] / np.sqrt(cov[1, 1]))


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    rng = np.random.default_rng(20261022)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    fut = pd.read_csv(FUTURES, index_col=0, parse_dates=True)
    daily = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(daily.columns)
    weekly = daily.resample("W-FRI").last().reindex(fut.index)
    cols = np.array(weekly.columns)
    wp = weekly.to_numpy()
    wr = wp[1:] / wp[:-1] - 1.0
    wr = np.vstack([np.full(len(cols), np.nan), wr])
    wr = np.where(np.abs(wr) <= 1.0, wr, np.nan)
    fr = fut[COMMODITIES + ["ES=F"]].to_numpy()
    dates = fut.index
    print(f"futures {dates[0].date()}..{dates[-1].date()}; stocks {len(cols)}")

    # ------------------------------------------------------------------ T3 (futures only)
    t3 = []
    for k in range(STEP, len(dates) - STEP, STEP):
        oil = compound(fr[k - STEP + 1:k + 1, COMMODITIES.index("CL=F")])
        es = compound(fr[k + 1:k + 1 + STEP, -1])
        t3.append({"date": dates[k], "x": oil, "y": es})
    t3 = pd.DataFrame(t3).dropna()
    t3_res = {}
    for label, (a, b) in {"design 2005-2015": ("2005", "2015"), "holdout 2016-2026": ("2016", "2026"),
                          "full": ("2005", "2026")}.items():
        sub = t3[(t3.date >= f"{a}-01-01") & (t3.date <= f"{b}-12-31")]
        t3_res[label] = {"n": int(len(sub)), "slope": slope(sub.x.to_numpy(), sub.y.to_numpy()),
                         "nw_t": newey_west_t(sub.x.to_numpy(), sub.y.to_numpy()),
                         "bootstrap_p": block_bootstrap_slope(sub, rng)}
    d, h = t3_res["design 2005-2015"], t3_res["holdout 2016-2026"]
    t3_pass = d["slope"] < 0 and d["bootstrap_p"] < BAR and h["slope"] < 0

    # ------------------------------------------------------------------ T1 and T2
    t1_rows, rows, placebo = [], [], []
    first = dates.get_indexer([pd.Timestamp("2012-01-06")], method="bfill")[0]
    for k in range(first, len(dates) - STEP, STEP):
        when = dates[k]
        if when > pd.Timestamp("2026-08-07"):
            break
        groups = a19.sic_as_of(sic, when).reindex(cols)
        sic2 = groups.str[:2].to_numpy(dtype=object)
        p0 = wp[k]
        own4 = p0 / wp[k - 4] - 1.0
        mom = wp[k - 4] / wp[k - 52] - 1.0 if k >= 52 else np.full(len(cols), np.nan)
        fwd = wp[k + STEP] / p0 - 1.0
        dpos = dollar.index.get_indexer([when], method="pad")[0]
        dv = dollar.iloc[dpos].to_numpy() if dpos >= 0 else np.full(len(cols), np.nan)
        liquid = np.isfinite(p0) & (p0 >= a19.MIN_PRICE) & (dv >= a19.MIN_DOLLAR_VOLUME) & pd.notna(groups).to_numpy()
        comm4 = {c: compound(fr[k - STEP + 1:k + 1, i]) for i, c in enumerate(COMMODITIES)}

        # T1: group excess returns.
        univ_fwd = np.nanmean(np.where(liquid, fwd, np.nan))
        gmap = group_of(groups).to_numpy(dtype=object)
        for name, (comms, _) in GROUPS.items():
            members = liquid & (gmap == name) & np.isfinite(fwd)
            x = np.nanmean([comm4[c] for c in comms])
            if members.sum() >= 3 and np.isfinite(x):
                t1_rows.append({"date": when, "group": name, "n": int(members.sum()), "x": float(x),
                                "y": float(fwd[members].mean() - univ_fwd)})

        # T2: exposures from the last 104 weekly returns.
        if k < WINDOW + 1 or when < pd.Timestamp("2013-01-01"):
            continue
        R = wr[k - WINDOW + 1:k + 1]
        ok = liquid & np.isfinite(R).all(axis=0) & np.isfinite(own4) & np.isfinite(mom)
        if ok.sum() < 100:
            continue
        R = R[:, ok]
        es = fr[k - WINDOW + 1:k + 1, -1]
        betas = {}
        for i, c in enumerate(COMMODITIES):
            x = fr[k - WINDOW + 1:k + 1, i]
            good = np.isfinite(x) & np.isfinite(es)
            if good.sum() < 80:
                continue
            X = np.column_stack([np.ones(good.sum()), es[good], x[good]])
            betas[c] = np.linalg.lstsq(X, R[good], rcond=None)[0][2]
        frame = pd.DataFrame({"sic2": sic2[ok], "r": own4[ok]})
        g = frame.groupby("sic2").r
        sic2_ret = ((g.transform("sum") - frame.r) / (g.transform("count") - 1)).where(g.transform("count") > 1).to_numpy()
        controls = np.column_stack([own4[ok], mom[ok], sic2_ret])

        def score_for(c4: dict) -> np.ndarray:
            s = np.zeros(ok.sum())
            for c, b in betas.items():
                if np.isfinite(c4[c]):
                    s += b * c4[c]
            return s

        raw = score_for(comm4)
        resid = a19.residualise(raw, controls)
        rows.append({"date": when, "cik": cols[ok], "sic2": sic2[ok],
                     "T2": {"raw": raw, "resid": resid, "fwd": fwd[ok]}})
        if when <= pd.Timestamp("2018-12-31"):
            draws = []
            for _ in range(PLACEBO_RUNS):
                j = int(rng.integers(STEP, k - STEP))
                c4 = {c: compound(fr[j - STEP + 1:j + 1, i]) for i, c in enumerate(COMMODITIES)}
                draws.append(a19.rank_ic(a19.residualise(score_for(c4), controls), fwd[ok]))
            placebo.append(draws)

    # T1 evaluation
    t1 = pd.DataFrame(t1_rows)
    t1.to_csv(OUTPUT / "t1_group_panel.csv", index=False)
    t1_res = {}
    for label, (a, b) in {"design 2012-2018": ("2012", "2018"), "holdout 2019-2026": ("2019", "2026")}.items():
        sub = t1[(t1.date >= f"{a}-01-01") & (t1.date <= f"{b}-12-31")]
        t1_res[label] = {"n": int(len(sub)), "pooled_slope": slope(sub.x.to_numpy(), sub.y.to_numpy()),
                         "bootstrap_p": block_bootstrap_slope(sub, rng),
                         "by_group": {grp: {"slope": slope(s.x.to_numpy(), s.y.to_numpy()), "periods": int(len(s)),
                                            "median_members": float(s.n.median())}
                                      for grp, s in sub.groupby("group")}}
    d1, h1 = t1_res["design 2012-2018"], t1_res["holdout 2019-2026"]
    positive_groups = sum(v["slope"] > 0 for v in d1["by_group"].values())
    t1_pass = d1["pooled_slope"] > 0 and d1["bootstrap_p"] < BAR and positive_groups >= 3 and h1["pooled_slope"] > 0

    # T2 evaluation, A19's machinery
    daily_ic = a19.per_decision(rows, "T2")
    design = daily_ic[(daily_ic.date >= "2013-01-01") & (daily_ic.date <= "2018-12-31")]
    hold = daily_ic[daily_ic.date >= "2019-01-01"]
    a19.BAR = BAR
    t2 = {"design": a19.summarise(design, 6, 20, rng, seed=1), "holdout": a19.summarise(hold, 6, 20, rng, seed=2),
          "regimes": {lab: a19.summarise(daily_ic[(daily_ic.date >= a) & (daily_ic.date <= b)], 6, 20, rng, seed=3)
                      for lab, (a, b) in {"2013-2019": ("2013-01-01", "2019-12-31"), "2020": ("2020-01-01", "2020-12-31"),
                                          "2021-2022": ("2021-01-01", "2022-12-31"), "2023-2026": ("2023-01-01", "2026-12-31")}.items()}}
    plac = np.nanmean(np.array(placebo), axis=0)
    t2["placebo_time_shuffle"] = {"mean": float(plac.mean()), "p95": float(np.percentile(plac, 95))}
    design_rows = [r for r in rows if r["date"] <= pd.Timestamp("2018-12-31")]
    t2["leave_out"] = a19.leave_out(rows, "T2", design_rows)
    dd, hh = t2["design"], t2["holdout"]
    t2["criteria"] = {
        "design_ic_positive_p_below_bar": dd["mean_ic"] > 0 and dd["bootstrap_p"] < BAR,
        "design_ladder_clears_positive": dd["clears"] and dd["monotonicity"] > 0,
        "design_ladder_clears_calibrated": bool(dd["clears_calibrated"]) and dd["monotonicity"] > 0,
        "design_ic_above_placebo_p95": dd["mean_ic"] > t2["placebo_time_shuffle"]["p95"],
        "design_leave_outs_positive": t2["leave_out"]["min_leave_one_sic2_out_ic"] > 0
                                      and t2["leave_out"]["ic_without_top10_names"] > 0,
        "holdout_ic_positive_and_ladder_clears": hh["mean_ic"] > 0 and hh["clears"] and hh["monotonicity"] > 0,
    }
    t2_pass = all(t2["criteria"].values())

    print("\n== T3 oil -> S&P 500 next 4 weeks (declared NEGATIVE)")
    for lab, s in t3_res.items():
        print(f"  {lab:18s} n={s['n']:3d} slope {s['slope']:+.4f} NW t {s['nw_t']:+.2f} boot p {s['bootstrap_p']:.4f}")
    print(f"  T3 {'PASSES' if t3_pass else 'FAILS'}")
    print("\n== T1 producer groups vs own commodity (declared POSITIVE)")
    for lab, s in t1_res.items():
        print(f"  {lab:18s} n={s['n']:3d} pooled slope {s['pooled_slope']:+.4f} boot p {s['bootstrap_p']:.4f}")
        for grp, v in s["by_group"].items():
            print(f"      {grp:12s} slope {v['slope']:+.4f} periods {v['periods']} median members {v['median_members']:.0f}")
    print(f"  T1 {'PASSES' if t1_pass else 'FAILS'}")
    print("\n== T2 estimated commodity exposure x last-4-week commodity move (declared POSITIVE)")
    for lab in ("design", "holdout"):
        s = t2[lab]
        print(f"  {lab:8s} n={s['decisions']:3d} names~{s['median_names']:.0f} IC {s['mean_ic']:+.4f} t {s['t_stat']:+.2f} "
              f"p {s['bootstrap_p']:.4f} spread/yr {s['decile_spread_annualised']:+.2%} mono {s['monotonicity']:+.3f} "
              f"mid8 {s['monotonicity_middle_8']:+.3f} calib p {s['calibrated']['p']:.3f}")
    for lab, s in t2["regimes"].items():
        if not s.get("inconclusive"):
            print(f"    {lab:10s} n={s['decisions']:3d} IC {s['mean_ic']:+.4f} p {s['bootstrap_p']:.3f} "
                  f"spread/yr {s['decile_spread_annualised']:+.2%} mono {s['monotonicity']:+.3f} mid8 {s['monotonicity_middle_8']:+.3f}")
    print(f"  placebo (time-shuffled commodity moves) mean {t2['placebo_time_shuffle']['mean']:+.4f} p95 {t2['placebo_time_shuffle']['p95']:+.4f}")
    lo = t2["leave_out"]
    print(f"  leave-one-SIC2-out min {lo['min_leave_one_sic2_out_ic']:+.4f} (drop {lo['worst_sic2_removed']}), without top-10 {lo['ic_without_top10_names']:+.4f}")
    for k_, v in t2["criteria"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k_}")
    print(f"  T2 {'PASSES' if t2_pass else 'FAILS'}")

    (OUTPUT / "result.json").write_text(json.dumps({
        "registry": str(REGISTRY.relative_to(ROOT)),
        "T1": {"results": t1_res, "positive_groups_design": positive_groups, "passes": t1_pass},
        "T2": {**t2, "passes": t2_pass}, "T3": {"results": t3_res, "passes": t3_pass},
        "live_trading_enabled": False, "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
