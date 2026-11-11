"""Fresh-eyes V2: six pre-registered trials (config/fresh_eyes_v2_registry_v1.json, commit 19f0029).

Run:  .venv/bin/python scripts/run_fresh_eyes_v2.py
Writes evidence/fresh_eyes_v2/results.json and prints every table.
"""
import glob
import itertools
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COSTS = [0, 10, 50, 100]
REGIMES = [("2012-2019", "2012-01", "2019-12"), ("2020", "2020-01", "2020-12"),
           ("2021-2022", "2021-01", "2022-12"), ("2023-2026", "2023-01", "2026-12")]
ALPHA = 0.05 / 6
OUT = {}


# ---------------------------------------------------------------- data
def load():
    d = pd.read_csv(f"{ROOT}/data/fresh_eyes_v2_prices_v1/daily_adjusted_close.csv.gz",
                    index_col=0, parse_dates=True)
    ff = glob.glob(f"{ROOT}/data/fama_french_factor_vintages/*/F-F_Research_Data_5_Factors_2x3_daily.csv")[-1]
    f = pd.read_csv(ff, skiprows=4)
    f = f[pd.to_numeric(f.iloc[:, 0], errors="coerce").notna()]
    rf = pd.Series(f["RF"].astype(float).values / 100,
                   index=pd.to_datetime(f.iloc[:, 0].astype(int).astype(str)))
    r = d.pct_change(fill_method=None)
    cash = r["BIL"].copy()
    early = cash.index < "2007-06-01"
    cash[early] = rf.reindex(cash.index)[early]
    r["CASH"] = cash.fillna(0.0)
    return d, r


def monthly(r):
    m = (1 + r.fillna(0)).resample("ME").prod() - 1
    live = r.notna().resample("ME").sum()
    m = m.where(live >= 15)          # a month counts only with >= 15 trading days of data
    m["CASH"] = (1 + r["CASH"]).resample("ME").prod() - 1
    return m


# ---------------------------------------------------------------- engine
def simulate(R, W, bps, drag=0.0):
    """R: period returns (T x N). W: target weights for each period, decided before it.
    Rebalance to target at the start of every period where W row is not NaN; otherwise drift.
    Cost = bps one-way x sum |trade|. Returns (net return series, annual turnover)."""
    cols = list(W.columns)
    R = R[cols].reindex(W.index)
    w = None
    out, tov = [], []
    for t in W.index:
        tgt = W.loc[t].values
        if w is None:
            trade = np.abs(tgt[~np.isnan(tgt)]).sum() if not np.isnan(tgt).all() else 0.0
            w = np.nan_to_num(tgt)
        elif not np.isnan(tgt).any():
            trade = np.abs(tgt - w).sum()
            w = tgt.copy()
        else:
            trade = 0.0
        r = np.nan_to_num(R.loc[t].values)
        pr = float(w @ r)
        out.append(pr - trade * bps / 1e4 - drag)
        tov.append(trade)
        w = w * (1 + r) / (1 + pr)
    return pd.Series(out, index=W.index), pd.Series(tov, index=W.index)


def stats(r, cash, ppy, spy=None, tov=None):
    r = r.dropna()
    c = cash.reindex(r.index)
    ex = r - c
    wealth = (1 + r).cumprod()
    s = dict(n=int(len(r)),
             CAGR=float(wealth.iloc[-1] ** (ppy / len(r)) - 1),
             vol=float(r.std() * np.sqrt(ppy)),
             Sharpe=float(ex.mean() / ex.std() * np.sqrt(ppy)) if ex.std() > 0 else float("nan"),
             maxDD=float((wealth / wealth.cummax() - 1).min()))
    if spy is not None:
        x = (spy.reindex(r.index) - c)
        s["beta"] = float(np.cov(ex, x)[0, 1] / x.var())
    if tov is not None:
        s["turnover_yr"] = float(tov.reindex(r.index).sum() / (len(r) / ppy))
    return s


def fmt(s):
    t = f"CAGR {s['CAGR']:7.2%}  vol {s['vol']:6.2%}  Sharpe {s['Sharpe']:5.2f}  maxDD {s['maxDD']:7.2%}"
    if "beta" in s:
        t += f"  beta {s['beta']:+.2f}"
    if "turnover_yr" in s:
        t += f"  turnover {s['turnover_yr']:6.2f}x"
    return t + f"  n={s['n']}"


def sharpe(x, ppy):
    return x.mean() / x.std() * np.sqrt(ppy)


def boot_p(a, b, cash, ppy, block, draws=5000, seed=0):
    """One-sided paired circular block bootstrap: P(Sharpe(a) - Sharpe(b) >= observed | null of zero)."""
    idx = a.dropna().index.intersection(b.dropna().index)
    xa = (a - cash).reindex(idx).values
    xb = (b - cash).reindex(idx).values
    n = len(idx)
    obs = sharpe(xa, ppy) - sharpe(xb, ppy)
    rng = np.random.default_rng(seed)
    k = int(np.ceil(n / block))
    D = np.empty(draws)
    for i in range(draws):
        st = rng.integers(0, n, k)
        ix = (st[:, None] + np.arange(block)[None, :]).ravel()[:n] % n
        D[i] = sharpe(xa[ix], ppy) - sharpe(xb[ix], ppy)
    return float(obs), float(np.mean(D - D.mean() >= obs))


def regime_table(series, cash, ppy):
    rows = {}
    for name, a, b in REGIMES:
        rows[name] = {k: stats(v[a:b], cash, ppy) for k, v in series.items() if len(v[a:b].dropna()) > 3}
    return rows


def print_regimes(rows):
    for name, d in rows.items():
        print(f"  {name}: " + " | ".join(f"{k} {v['CAGR']:+.1%} Sh {v['Sharpe']:.2f} DD {v['maxDD']:.1%}"
                                         for k, v in d.items()))


def const_w(index, weights):
    return pd.DataFrame([weights] * len(index), index=index)


def bench_w(index):
    return const_w(index, {"SPY": 1 / 3, "GLD": 1 / 3, "SHY": 1 / 3})


# ---------------------------------------------------------------- controls
def controls(d, r, m):
    print("=== POSITIVE CONTROLS ===")
    res = {}
    p = pd.read_csv(f"{ROOT}/data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz", index_col=0, parse_dates=True)
    p.index = p.index.tz_localize(None)
    for t in ["SPY", "GLD", "SHY", "IEF"]:
        a = p[t].pct_change()
        b = d[t].reindex(p.index, method="ffill").pct_change()
        c = float(pd.concat([a, b], axis=1).dropna().corr().iloc[0, 1])
        res[f"download_vs_disk_weekly_corr_{t}"] = c
        print(f" download vs on-disk weekly returns, {t}: corr {c:.4f}")
    x = pd.concat([m["BTAL"], m["SPY"]], axis=1).dropna()
    res["btal_beta_to_spy"] = float(np.cov(x.iloc[:, 0], x.iloc[:, 1])[0, 1] / x.iloc[:, 1].var())
    print(f" BTAL monthly beta to SPY: {res['btal_beta_to_spy']:+.2f} (must be clearly negative)")
    tc = m[["AQMIX", "ASFYX", "PQTIX", "DBMF", "KMLM"]].mean(axis=1)
    res["trend_2022"] = float((1 + tc["2022"]).prod() - 1)
    res["trend_2008_n/a"] = "funds start 2010"
    print(f" trend composite 2022 return: {res['trend_2022']:+.1%} (trend funds are known to have gained in 2022)")
    print(f" MERFX monthly beta to SPY: {np.cov(m['MERFX'].dropna(), m['SPY'].reindex(m['MERFX'].dropna().index))[0,1]/m['SPY'].var():+.2f} (merger arb: small positive)")
    # planted-effect controls for T1 and T3 machinery
    rng = np.random.default_rng(1)
    fake = pd.Series(rng.normal(0.0, 0.04, len(m)), index=m.index)
    fake[fake.index.month.isin([11, 12, 1, 2, 3, 4])] += 0.02
    rk = halloween_rank(fake, pd.Series(0.0, index=m.index), 10)[1]
    res["t1_planted_rank_p"] = rk
    print(f" T1 placebo machinery on a planted Nov-Apr effect: rank p = {rk:.4f} (must be near 0)")
    fd = pd.Series(rng.normal(0, 0.004, len(r)), index=r.index)
    k = days_from_month_end(fd.index)
    fd[k <= 3] += 0.002
    tt = slot_table(fd, k)
    res["t3_planted_first"] = bool(tt["mean"].idxmax() == 0)
    print(f" T3 slot machinery on a planted month-end effect: best slot offset = {tt['mean'].idxmax()} (must be 0)")
    OUT["controls"] = res


# ---------------------------------------------------------------- T1
def halloween_rank(spy, cash, bps):
    idx = spy.dropna().index
    R = pd.concat([spy, cash], axis=1, keys=["SPY", "CASH"]).reindex(idx)
    res = {}
    for combo in itertools.combinations(range(1, 13), 6):
        on = idx.month.isin(combo)
        W = pd.DataFrame({"SPY": on.astype(float), "CASH": 1 - on.astype(float)}, index=idx)
        s, _ = simulate(R, W, bps)
        res[combo] = sharpe((s - cash.reindex(idx)).values, 12)
    target = res[(1, 2, 3, 4, 11, 12)]
    p = float(np.mean([v >= target for v in res.values()]))
    return target, p


def t1(m):
    print("\n=== T1 Halloween: SPY Nov-Apr, cash May-Oct, vs 50/50 ===")
    R = m[["SPY", "CASH"]].dropna()
    res = {}
    for label, a, b in [("decision 2003-01..2026-08", "2003-01", "2026-08"), ("context 1993-02..2002-12", "1993-02", "2002-12")]:
        Rw = R[a:b]
        on = Rw.index.month.isin([11, 12, 1, 2, 3, 4]).astype(float)
        Wsw = pd.DataFrame({"SPY": on, "CASH": 1 - on}, index=Rw.index)
        Wc = const_w(Rw.index, {"SPY": 0.5, "CASH": 0.5})
        print(f" {label}")
        res[label] = {}
        for bps in COSTS:
            s, ts_ = simulate(Rw, Wsw, bps)
            c, tc_ = simulate(Rw, Wc, bps)
            ss, sc = stats(s, Rw["CASH"], 12, Rw["SPY"], ts_), stats(c, Rw["CASH"], 12, Rw["SPY"], tc_)
            res[label][bps] = {"switch": ss, "mix": sc}
            print(f"  {bps:>3} bps  switch {fmt(ss)}\n           50/50  {fmt(sc)}")
        print("  SPY buy-and-hold  " + fmt(stats(Rw["SPY"], Rw["CASH"], 12)))
    Rw = R["2003-01":"2026-08"]
    on = Rw.index.month.isin([11, 12, 1, 2, 3, 4]).astype(float)
    s, _ = simulate(Rw, pd.DataFrame({"SPY": on, "CASH": 1 - on}, index=Rw.index), 10)
    c, _ = simulate(Rw, const_w(Rw.index, {"SPY": 0.5, "CASH": 0.5}), 10)
    diff, p_boot = boot_p(s, c, Rw["CASH"], 12, 12)
    _, p_rank = halloween_rank(Rw["SPY"], Rw["CASH"], 10)
    rg = regime_table({"switch": s, "mix": c}, Rw["CASH"], 12)
    print_regimes(rg)
    wins = sum(v["switch"]["Sharpe"] > v["mix"]["Sharpe"] for v in rg.values())
    summer = Rw["SPY"][Rw.index.month.isin([5, 6, 7, 8, 9, 10])] - Rw["CASH"][Rw.index.month.isin([5, 6, 7, 8, 9, 10])]
    winter = Rw["SPY"][on == 1] - Rw["CASH"][on == 1]
    print(f"  mean monthly excess: Nov-Apr {winter.mean():+.2%}, May-Oct {summer.mean():+.2%}")
    verdict = diff >= 0.10 and p_rank < ALPHA and wins >= 3
    print(f"  Sharpe diff {diff:+.3f} (bootstrap p {p_boot:.3f}); placebo rank p {p_rank:.4f} of 924; regimes won {wins}/4 -> PASS={verdict}")
    res.update(sharpe_diff=diff, boot_p=p_boot, placebo_rank_p=p_rank, regimes=rg, regimes_won=wins, passed=bool(verdict),
               winter_mean=float(winter.mean()), summer_mean=float(summer.mean()))
    OUT["T1_halloween"] = res


# ---------------------------------------------------------------- T2
def t2(m):
    print("\n=== T2 BTAL sleeve: 80% benchmark + 20% BTAL ===")
    R = m[["SPY", "GLD", "SHY", "BTAL", "CASH"]]["2011-10":"2026-10"].dropna()
    th = 1 / 3
    books = {"benchmark": {"SPY": th, "GLD": th, "SHY": th, "BTAL": 0, "CASH": 0},
             "80/20 BTAL": {"SPY": .8 * th, "GLD": .8 * th, "SHY": .8 * th, "BTAL": .2, "CASH": 0},
             "80/20 cash": {"SPY": .8 * th, "GLD": .8 * th, "SHY": .8 * th, "BTAL": 0, "CASH": .2}}
    res, ser = {}, {}
    for bps in COSTS:
        res[bps] = {}
        print(f" {bps} bps")
        for k, w in books.items():
            s, tv = simulate(R, const_w(R.index, w), bps)
            res[bps][k] = stats(s, R["CASH"], 12, R["SPY"], tv)
            if bps == 10:
                ser[k] = s
            print(f"  {k:12s} {fmt(res[bps][k])}")
    print("  BTAL alone   " + fmt(stats(R["BTAL"], R["CASH"], 12, R["SPY"])))
    print("  SPY          " + fmt(stats(R["SPY"], R["CASH"], 12)))
    d1, p1 = boot_p(ser["80/20 BTAL"], ser["benchmark"], R["CASH"], 12, 12)
    d2, p2 = boot_p(ser["80/20 BTAL"], ser["80/20 cash"], R["CASH"], 12, 12)
    rg = regime_table(ser, R["CASH"], 12)
    print_regimes(rg)
    for nm, a, b in [("2020-02..03", "2020-02", "2020-03"), ("2022", "2022-01", "2022-12")]:
        print(f"  crisis {nm}: " + " | ".join(f"{k} {(1 + v[a:b]).prod() - 1:+.1%}" for k, v in {**ser, 'BTAL': R['BTAL']}.items()))
    dd_ok = res[10]["80/20 BTAL"]["maxDD"] >= res[10]["benchmark"]["maxDD"]
    verdict = d1 >= 0.05 and d2 >= 0.05 and p1 < ALPHA and dd_ok
    print(f"  Sharpe diff vs benchmark {d1:+.3f} (p {p1:.3f}); vs 80/20 cash {d2:+.3f} (p {p2:.3f}); DD no deeper {dd_ok} -> PASS={verdict}")
    OUT["T2_btal"] = dict(grid=res, diff_vs_bench=d1, p_vs_bench=p1, diff_vs_cash=d2, p_vs_cash=p2, regimes=rg, passed=bool(verdict))


# ---------------------------------------------------------------- T3
def days_from_month_end(index):
    """k = 1 for the last trading day of its month, 2 for the one before, ... (calendar only, no prices)."""
    s = pd.Series(1, index=index)
    return s.groupby([index.year, index.month]).transform(lambda x: np.arange(len(x), 0, -1)).values


def slot_table(ex, k):
    rows = []
    ym = ex.index.to_period("M")
    for j in range(0, 16):
        sel = (k >= j + 1) & (k <= j + 3)
        per = ex[sel].groupby(ym[sel]).sum()
        rows.append(dict(offset=j, mean=per.mean(), t=per.mean() / per.std() * np.sqrt(len(per)), n=len(per)))
    return pd.DataFrame(rows).set_index("offset")


def t3(r):
    print("\n=== T3 Treasury month-end: IEF in the last 3 trading days of each month ===")
    res = {}
    full = r[["IEF", "TLT", "CASH"]].dropna()
    last = full.index[-1]
    full = full[full.index < last.to_period("M").to_timestamp()]   # complete months only
    k_all = days_from_month_end(full.index)
    for label, a, b in [("decision 2019-01..2026-10", "2019-01", "2026-10"), ("design 2002-08..2018-12", "2002-08", "2018-12")]:
        w = full[a:b]
        k = k_all[(full.index >= w.index[0]) & (full.index <= w.index[-1])]
        res[label] = {}
        for asset in ["IEF", "TLT"]:
            ex = w[asset] - w["CASH"]
            tab = slot_table(ex, k)
            rank = int((tab["mean"] > tab.loc[0, "mean"]).sum() + 1)
            other = ex[k > 3]
            print(f" {label} {asset}: month-end slot mean {tab.loc[0,'mean']:+.3%} per month, t {tab.loc[0,'t']:.2f}, rank {rank}/16; "
                  f"avg daily excess last-3 {ex[k<=3].mean()*1e4:+.2f} bp vs other days {other.mean()*1e4:+.2f} bp")
            hold = (k <= 3).astype(float)
            grid = {}
            for bps in COSTS:
                net = hold * w[asset] + (1 - hold) * w["CASH"]
                net = net - (pd.Series(k, index=w.index).isin([3, 1]) * 0).values  # placeholder for clarity
                cost = pd.Series(0.0, index=w.index)
                cost[k == 3] += bps / 1e4      # buy at the close before day k=3 -> charge on that day
                cost[k == 1] += bps / 1e4      # sell at the last close
                s = net - cost
                grid[bps] = stats(s, w["CASH"], 252)
                grid[bps]["excess_over_cash_yr"] = float((s - w["CASH"]).mean() * 252)
            print("   strategy excess over cash per year at 0/10/50/100 bps: " +
                  " / ".join(f"{grid[b_]['excess_over_cash_yr']:+.2%}" for b_ in COSTS) +
                  f"   Sharpe at 10 bps {grid[10]['Sharpe']:.2f}, maxDD {grid[10]['maxDD']:.2%}; buy-and-hold {asset} Sharpe {stats(w[asset], w['CASH'], 252)['Sharpe']:.2f}")
            res[label][asset] = dict(slot_mean=float(tab.loc[0, "mean"]), t=float(tab.loc[0, "t"]), rank=rank,
                                     slots=tab.round(5).to_dict("index"), grid=grid)
    dsn = res["decision 2019-01..2026-10"]["IEF"]
    verdict = dsn["slot_mean"] > 0 and dsn["t"] > 2.64 and dsn["rank"] == 1 and dsn["grid"][10]["excess_over_cash_yr"] > 0
    print(f"  PASS={verdict}")
    res["passed"] = bool(verdict)
    OUT["T3_treasury_month_end"] = res


# ---------------------------------------------------------------- T4
def t4():
    print("\n=== T4 Rebalancing rules for the benchmark (weekly panel) ===")
    p = pd.read_csv(f"{ROOT}/data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz", index_col=0, parse_dates=True)
    p.index = p.index.tz_localize(None)
    R = p[["SPY", "GLD", "SHY", "BIL"]].pct_change(fill_method=None)
    R = R[R["GLD"].notna()]
    cash = R["BIL"].fillna(R["SHY"])          # weekly panel has no bill series before 2007; SHY stands in
    R = R[["SPY", "GLD", "SHY"]]
    th = np.array([1 / 3] * 3)
    idx = R.index
    rules = {}
    rules["weekly reset"] = bench_w(idx)
    mo = bench_w(idx).astype(float)
    mo[~(pd.Series(idx.month, index=idx) != pd.Series(idx.month, index=idx).shift(1)).values] = np.nan
    rules["monthly reset"] = mo
    yr = bench_w(idx).astype(float)
    yr[~(pd.Series(idx.year, index=idx) != pd.Series(idx.year, index=idx).shift(1)).values] = np.nan
    yr.iloc[0] = th
    rules["annual reset"] = yr
    res = {}
    # band rule needs path dependence
    def band(bps):
        w = th.copy(); out = []; tov = []
        for t in idx:
            trade = 0.0
            if np.abs(w - th).max() > 0.05:
                trade = np.abs(th - w).sum(); w = th.copy()
            r = R.loc[t].values; pr = float(w @ r)
            out.append(pr - trade * bps / 1e4); tov.append(trade)
            w = w * (1 + r) / (1 + pr)
        return pd.Series(out, index=idx), pd.Series(tov, index=idx)
    for bps in COSTS:
        res[bps] = {}
        print(f" {bps} bps")
        for k, W in rules.items():
            s, tv = simulate(R, W, bps)
            res[bps][k] = stats(s, cash, 52, R["SPY"], tv)
            print(f"  {k:14s} {fmt(res[bps][k])}")
        s, tv = band(bps)
        res[bps]["5pp band"] = stats(s, cash, 52, R["SPY"], tv)
        res[bps]["5pp band"]["rebalances"] = int((tv > 0).sum())
        print(f"  {'5pp band':14s} {fmt(res[bps]['5pp band'])}  ({int((tv > 0).sum())} rebalances in {len(idx)/52:.1f} years)")
    base = res[10]["weekly reset"]
    rec = {}
    for k in ["monthly reset", "annual reset", "5pp band"]:
        v = res[10][k]
        rec[k] = bool(v["turnover_yr"] <= 0.5 * base["turnover_yr"] and abs(v["Sharpe"] - base["Sharpe"]) <= 0.03
                      and abs(v["maxDD"] - base["maxDD"]) <= 0.02)
        print(f"  {k}: turnover {v['turnover_yr']:.2f}x vs {base['turnover_yr']:.2f}x, Sharpe {v['Sharpe']:.3f} vs {base['Sharpe']:.3f}, "
              f"maxDD {v['maxDD']:.2%} vs {base['maxDD']:.2%} -> RECOMMENDED={rec[k]}")
    OUT["T4_bands"] = dict(grid=res, recommended=rec)


# ---------------------------------------------------------------- T5
def trend_composite(m):
    return m[["AQMIX", "ASFYX", "PQTIX", "DBMF", "KMLM"]].mean(axis=1, skipna=True)


def t5(m):
    print("\n=== T5 Stacked trend: 100% benchmark + 20% trend overlay ===")
    M = m.copy(); M["TC"] = trend_composite(m)
    R = M[["SPY", "GLD", "SHY", "TC", "CASH"]]["2013-01":"2026-10"].dropna()
    th = 1 / 3
    books = {"benchmark": ({"SPY": th, "GLD": th, "SHY": th, "TC": 0, "CASH": 0}, 0.0),
             "80/20 unstacked": ({"SPY": .8 * th, "GLD": .8 * th, "SHY": .8 * th, "TC": .2, "CASH": 0}, 0.0),
             "stacked 100+20": ({"SPY": th, "GLD": th, "SHY": th, "TC": .2, "CASH": -.2}, 0.2 * 0.005 / 12)}
    res, ser = {}, {}
    for bps in COSTS:
        res[bps] = {}
        print(f" {bps} bps")
        for k, (w, drag) in books.items():
            s, tv = simulate(R, const_w(R.index, w), bps, drag)
            res[bps][k] = stats(s, R["CASH"], 12, R["SPY"], tv)
            if bps == 10:
                ser[k] = s
            print(f"  {k:16s} {fmt(res[bps][k])}")
    print("  trend composite  " + fmt(stats(R["TC"], R["CASH"], 12, R["SPY"])))
    print("  SPY              " + fmt(stats(R["SPY"], R["CASH"], 12)))
    d1, p1 = boot_p(ser["stacked 100+20"], ser["benchmark"], R["CASH"], 12, 12)
    rg = regime_table(ser, R["CASH"], 12)
    print_regimes(rg)
    for nm, a, b in [("2020-02..03", "2020-02", "2020-03"), ("2022", "2022-01", "2022-12")]:
        print(f"  crisis {nm}: " + " | ".join(f"{k} {(1 + v[a:b]).prod() - 1:+.1%}" for k, v in {**ser, 'trend': R['TC']}.items()))
    b, s8, st = res[10]["benchmark"], res[10]["80/20 unstacked"], res[10]["stacked 100+20"]
    sup = st["CAGR"] > b["CAGR"] and st["Sharpe"] >= b["Sharpe"] and st["maxDD"] >= b["maxDD"] and st["CAGR"] > s8["CAGR"]
    print(f"  stacked vs benchmark: Sharpe diff {d1:+.3f}, bootstrap p {p1:.3f} (alpha {ALPHA:.4f}) -> SUPPORTED AS CONSTRUCTION={sup}; significant={p1 < ALPHA}")
    # manager dispersion, descriptive
    disp = {}
    Rd = M["2019-06":"2026-10"]
    for f_ in ["AQMIX", "ASFYX", "PQTIX", "DBMF"]:
        disp[f_] = stats(Rd[f_].dropna(), Rd["CASH"], 12)
    disp["composite"] = stats(Rd["TC"].dropna(), Rd["CASH"], 12)
    print("  single funds since 2019-06 (descriptive): " + " | ".join(f"{k} CAGR {v['CAGR']:+.1%} Sh {v['Sharpe']:.2f} DD {v['maxDD']:.0%}" for k, v in disp.items()))
    OUT["T5_stacked_trend"] = dict(grid=res, diff_vs_bench=d1, p_vs_bench=p1, regimes=rg, supported=bool(sup), dispersion=disp)


# ---------------------------------------------------------------- T6
def t6_weights(M, sleeves, bench):
    """Past-only inverse-vol weights, scaled with cash to the benchmark's trailing vol, cap 100%."""
    X = M[sleeves]
    rows = {}
    for i, t in enumerate(X.index):
        hist = X.iloc[max(0, i - 36):i]
        bh = bench.iloc[max(0, i - 36):i]
        ok = hist.dropna()
        if len(ok) < 12:
            w = np.array([1 / len(sleeves)] * len(sleeves)); k = np.nan
        else:
            iv = 1 / ok.std().values
            w = iv / iv.sum()
            pv = np.sqrt(w @ ok.cov().values @ w)
            k = min(1.0, bh.dropna().std() / pv)
            w = w * k
        rows[t] = w
    W = pd.DataFrame(rows, index=sleeves).T
    W["CASH"] = 1 - W.sum(axis=1)
    return W


def enb(corr):
    lam = np.linalg.eigvalsh(corr)
    p = lam / lam.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


def t6(m):
    print("\n=== T6 Combination: six sleeves, inverse-vol, matched to the benchmark's risk ===")
    M = m.copy(); M["TC"] = trend_composite(m)
    sleeves = ["SPY", "GLD", "IEF", "TC", "MERFX", "BTAL"]
    M = M["2011-10":"2026-10"]
    bench_raw = M[["SPY", "GLD", "SHY"]].mean(axis=1)
    W = t6_weights(M, sleeves, bench_raw)
    # prefix-invariance: perturb the future, earlier weights must not change
    M2 = M.copy(); cut = M.index[100]
    M2.loc[M2.index > cut, sleeves] = M2.loc[M2.index > cut, sleeves] * 3 + 0.01
    W2 = t6_weights(M2, sleeves, M2[["SPY", "GLD", "SHY"]].mean(axis=1))
    inv = bool(np.allclose(W.loc[:cut].fillna(0).values, W2.loc[:cut].fillna(0).values)
               and np.allclose(W.loc[M.index[101]].values, W2.loc[M.index[101]].values))
    print(f" prefix-invariance of weights (future perturbed after {cut.date()}): {'PASS' if inv else 'FAIL'}")
    win = slice("2013-01", "2026-10")
    R = M[sleeves + ["CASH", "SHY"]][win]
    Ww = W[win]
    res, ser = {}, {}
    for bps in COSTS:
        res[bps] = {}
        print(f" {bps} bps")
        s, tv = simulate(R, Ww, bps)
        b, tb = simulate(R.assign(), const_w(R.index, {"SPY": 1 / 3, "GLD": 1 / 3, "SHY": 1 / 3}), bps)
        e, te = simulate(R, const_w(R.index, {k: 1 / 6 for k in sleeves}), bps)
        for k, (x, t_) in {"combination": (s, tv), "benchmark": (b, tb), "equal-weight six": (e, te)}.items():
            res[bps][k] = stats(x, R["CASH"], 12, R["SPY"], t_)
            if bps == 10:
                ser[k] = x
            print(f"  {k:17s} {fmt(res[bps][k])}")
    print("  SPY               " + fmt(stats(R["SPY"], R["CASH"], 12)))
    print(f"  average weights: " + ", ".join(f"{c} {Ww[c].mean():.0%}" for c in Ww.columns))
    corr = R[sleeves].corr()
    print("  sleeve correlations (monthly, 2013-2026):")
    print(corr.round(2).to_string())
    e_six, e_bench = enb(corr.values), enb(R[["SPY", "GLD", "SHY"]].corr().values)
    print(f"  effective number of bets: six sleeves {e_six:.2f} of 6; SPY/GLD/SHY {e_bench:.2f} of 3")
    d1, p1 = boot_p(ser["combination"], ser["benchmark"], R["CASH"], 12, 12)
    rg = regime_table(ser, R["CASH"], 12)
    print_regimes(rg)
    wins = sum(v["combination"]["Sharpe"] > v["benchmark"]["Sharpe"] for v in rg.values())
    for nm, a, b_ in [("2020-02..03", "2020-02", "2020-03"), ("2022", "2022-01", "2022-12")]:
        print(f"  crisis {nm}: " + " | ".join(f"{k} {(1 + v[a:b_]).prod() - 1:+.1%}" for k, v in ser.items()))
    loo = {}
    for drop in sleeves:
        keep = [x for x in sleeves if x != drop]
        Wd = t6_weights(M, keep, bench_raw)[win]
        s, _ = simulate(R, Wd, 10)
        loo[drop] = stats(s, R["CASH"], 12)["Sharpe"]
    print("  leave-one-sleeve-out Sharpe: " + ", ".join(f"no {k} {v:.2f}" for k, v in loo.items()) +
          f"  (all six {res[10]['combination']['Sharpe']:.2f}, benchmark {res[10]['benchmark']['Sharpe']:.2f})")
    dd_ok = res[10]["combination"]["maxDD"] >= res[10]["benchmark"]["maxDD"]
    verdict = d1 >= 0.10 and p1 < ALPHA and dd_ok and wins >= 3
    print(f"  Sharpe diff {d1:+.3f}, bootstrap p {p1:.3f}; DD no deeper {dd_ok}; regimes won {wins}/4 -> PASS={verdict}")
    OUT["T6_combination"] = dict(grid=res, diff=d1, p=p1, regimes=rg, regimes_won=wins, loo=loo, enb_six=e_six, enb_bench=e_bench,
                                 corr=corr.round(3).to_dict(), avg_weights=Ww.mean().round(3).to_dict(), prefix_invariant=inv,
                                 passed=bool(verdict))


if __name__ == "__main__":
    d, r = load()
    m = monthly(r)
    controls(d, r, m)
    t1(m); t2(m); t3(r); t4(); t5(m); t6(m)
    os.makedirs(f"{ROOT}/evidence/fresh_eyes_v2", exist_ok=True)
    json.dump(OUT, open(f"{ROOT}/evidence/fresh_eyes_v2/results.json", "w"), indent=1, default=str)
    print("\nwrote evidence/fresh_eyes_v2/results.json")
