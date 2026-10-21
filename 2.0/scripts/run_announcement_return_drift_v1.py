#!/usr/bin/env python3
"""A32: results-day jump drift (Chan, Jegadeesh & Lakonishok 1996), calibrated against survivorship-free OSAP.

Pre-registered in config/announcement_return_drift_registry_v1.json.
    python scripts/run_announcement_return_drift_v1.py calibrate   # stage 1: our panel vs OSAP, gate
    python scripts/run_announcement_return_drift_v1.py screen      # stage 2: long-only, net of spreads (only if gate passed)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_blowout_results_leaders_v1 as a28  # noqa: E402
import run_synthetic_boom_calls_v1 as calls  # noqa: E402
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/announcement_return_drift_registry_v1.json"
EVENTS = ROOT / "data/results_dates_v2/results_8k_events.csv"
OHLC = ROOT / "data/daily_ohlc_v1"
OSAP = ROOT / "data/osap_vintages/20260905T082446Z-osap-oct2025/long_short_returns_wide.csv"
FF = ROOT / "data/fama_french_factor_vintages/20261010T173855Z-ff5-mom-daily"
OUTPUT = ROOT / "evidence/announcement_return_drift_v1"
DESIGN, HOLDOUT = ("2013-01-01", "2019-12-31"), ("2020-01-01", "2025-12-31")


def load_base():
    prices = a19.load_daily()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    dates, cols = prices.index, np.array(prices.columns)
    px = prices.to_numpy()
    R = np.vstack([np.full(len(cols), np.nan), px[1:] / px[:-1] - 1.0])
    R = np.where(np.abs(R) < 1.0, R, np.nan)
    ev = pd.read_csv(EVENTS, dtype={"cik10": str})
    ev = ev[ev.cik10.isin(set(cols))]
    rd = a28.reaction_days(ev, dates)
    col_pos = {c: i for i, c in enumerate(cols)}
    reactions = {}
    for r in rd.itertuples():
        reactions.setdefault(col_pos[r.cik10], []).append(int(r.reaction_pos))
    for k in reactions:
        reactions[k] = np.array(sorted(set(reactions[k])))
    return prices, dollar, dates, cols, px, R, reactions


def month_ends(dates, a="2012-12-01", b="2025-12-31"):
    me = pd.Series(dates, index=dates).groupby([dates.year, dates.month]).last()
    return [dates.get_loc(d) for d in me if pd.Timestamp(a) <= d <= pd.Timestamp(b)]


def ear_at(m, R, ew, reactions, n):
    """3-day abnormal return around each issuer's latest reaction day in the 63 trading days up to m."""
    out = np.full(n, np.nan)
    for i, days in reactions.items():
        k = days[(days <= m - 1) & (days >= m - 63)]
        if len(k) == 0:
            continue
        t = k[-1]
        win = R[t - 1:t + 2, i]
        if np.isfinite(win).all():
            out[i] = np.prod(1 + win) - np.prod(1 + ew[t - 1:t + 2])
    return out


def stage_calibrate() -> int:
    json.loads(REGISTRY.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices, dollar, dates, cols, px, R, reactions = load_base()
    ew = np.nanmean(np.where(px >= 5, R, np.nan), axis=1)
    mes = month_ends(dates)
    rows = []
    for a, b in zip(mes[:-1], mes[1:]):
        ear = ear_at(a, R, ew, reactions, len(cols))
        ok = np.isfinite(ear) & (px[a] >= 5)
        if ok.sum() < 100:
            continue
        fwd = px[b] / px[a] - 1
        ok &= np.isfinite(fwd)
        dec = pd.qcut(pd.Series(ear[ok]).rank(method="first"), 10, labels=False).to_numpy()
        f = fwd[ok]
        rows.append({"month": dates[b] + pd.offsets.MonthEnd(0), "ls": float(f[dec == 9].mean() - f[dec == 0].mean()),
                     "top": float(f[dec == 9].mean()), "names": int(ok.sum())})
    ours = pd.DataFrame(rows).set_index("month")
    osap = pd.read_csv(OSAP, parse_dates=["date"]).set_index("date")["AnnouncementReturn"] / 100.0
    osap.index = osap.index + pd.offsets.MonthEnd(0)
    j = pd.concat([ours.ls, osap.rename("osap")], axis=1).dropna()
    j = j[(j.index >= "2013-01-01") & (j.index <= "2024-12-31")]
    corr, ratio = float(j.ls.corr(j.osap)), float(j.ls.mean() / j.osap.mean())
    gate = corr >= 0.50 and 0.5 <= ratio <= 1.5
    ours.to_csv(OUTPUT / "stage1_our_long_short.csv")
    res = {"months": int(len(j)), "corr_with_osap": corr, "our_mean_annual": float(j.ls.mean() * 12),
           "osap_mean_annual": float(j.osap.mean() * 12), "mean_ratio": ratio, "median_names": float(ours.names.median()),
           "gate_passes": gate}
    (OUTPUT / "stage1_calibration.json").write_text(json.dumps(res, indent=2) + "\n")
    print(f"stage 1: {len(j)} months 2013-2024, median names {ours.names.median():.0f}")
    print(f"  our long-short {j.ls.mean() * 12:+.2%}/yr vs OSAP {j.osap.mean() * 12:+.2%}/yr (ratio {ratio:.2f}); "
          f"monthly correlation {corr:+.2f}")
    print(f"  gate (corr >= 0.50 and ratio 0.5-1.5): {'PASS' if gate else 'FAIL'}")
    return 0


def abdi_ranaldo(high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    """Rolling 21-day Abdi-Ranaldo (2017) effective spread estimate, as a fraction of price."""
    c = np.log(close)
    eta = (np.log(high) + np.log(low)) / 2
    prod = (c - eta) * (c - eta.shift(-1))
    s2 = 4 * prod.rolling(21, min_periods=15).mean().shift(1)            # only past days
    return np.sqrt(s2.clip(lower=0))


def ff_factors(index: pd.DatetimeIndex) -> pd.DataFrame:
    def read(path, cols):
        rows = []
        for line in path.read_text().splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) == len(cols) + 1 and p[0].isdigit() and len(p[0]) == 8:
                rows.append([pd.Timestamp(p[0])] + [float(v) / 100 for v in p[1:]])
        return pd.DataFrame(rows, columns=["date"] + cols).set_index("date")
    f5 = read(FF / "F-F_Research_Data_5_Factors_2x3_daily.csv", ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"])
    mom = read(FF / "F-F_Momentum_Factor_daily.csv", ["Mom"])
    d = f5.join(mom, how="inner")
    return ((1 + d).resample("ME").prod() - 1).reindex(index)


def nw_alpha_t(y: pd.Series, X: pd.DataFrame, lags: int = 6) -> tuple[float, float]:
    df = pd.concat([y.rename("y"), X], axis=1).dropna()
    Xm = np.column_stack([np.ones(len(df)), df[X.columns].to_numpy()])
    b = np.linalg.lstsq(Xm, df.y.to_numpy(), rcond=None)[0]
    u = df.y.to_numpy() - Xm @ b
    xu = Xm * u[:, None]
    s = xu.T @ xu
    for L in range(1, lags + 1):
        g = xu[L:].T @ xu[:-L]
        s += (1 - L / (lags + 1)) * (g + g.T)
    inv = np.linalg.inv(Xm.T @ Xm)
    return float(b[0] * 12), float(b[0] / np.sqrt((inv @ s @ inv)[0, 0]))


def stage_screen() -> int:
    cal = json.loads((OUTPUT / "stage1_calibration.json").read_text())
    if not cal["gate_passes"]:
        print("stage 1 gate failed: stage 2 does not run, as registered")
        return 0
    rng = np.random.default_rng(20261022)
    prices, dollar, dates, cols, px, R, reactions = load_base()
    hi = pd.read_csv(OHLC / "daily_high.csv.gz", index_col=0, parse_dates=True).reindex(index=dates, columns=cols)
    lo = pd.read_csv(OHLC / "daily_low.csv.gz", index_col=0, parse_dates=True).reindex(index=dates, columns=cols)
    cl = pd.read_csv(OHLC / "daily_close.csv.gz", index_col=0, parse_dates=True).reindex(index=dates, columns=cols)
    spread = abdi_ranaldo(hi, lo, cl).to_numpy()
    dv = dollar.to_numpy()
    ew_all = np.nanmean(np.where(px >= 5, R, np.nan), axis=1)
    mes = month_ends(dates)
    bands = {"T1_small_band_net": lambda a: (dv[a] >= 5e5) & (dv[a] < 5e6) & (px[a] >= 3),
             "T2_liquid_band_net": lambda a: (dv[a] >= 5e6) & (px[a] >= 5)}
    out = {}
    for name, band in bands.items():
        held, rows, contrib = {}, [], {}
        for a, b in zip(mes[:-1], mes[1:]):
            ear = ear_at(a, R, ew_all, reactions, len(cols))
            uni = band(a) & np.isfinite(px[a]) & np.isfinite(px[b])
            cand = uni & np.isfinite(ear)
            if cand.sum() < 50:
                held = {}
                continue
            idx = np.flatnonzero(cand)
            top = idx[ear[idx] >= np.quantile(ear[idx], 0.9)]
            target = {i: 1.0 / len(top) for i in top}
            trade = sum(abs(target.get(i, 0) - held.get(i, 0)) for i in set(target) | set(held))
            cost = sum(abs(target.get(i, 0) - held.get(i, 0)) * (np.nan_to_num(spread[a, i], nan=0.02) / 2 + 0.0005)
                       for i in set(target) | set(held))
            fwd = px[b] / px[a] - 1
            gross = float(np.mean(fwd[top]))
            bench = float(np.nanmean(fwd[np.flatnonzero(uni)]))
            for i in top:
                contrib[i] = contrib.get(i, 0) + (fwd[i] - bench) / len(top)
            grown = {i: target[i] * (1 + fwd[i]) for i in top}
            tot = sum(grown.values())
            held = {i: v / tot for i, v in grown.items()}
            rows.append({"month": dates[b] + pd.offsets.MonthEnd(0), "gross": gross, "net": gross - cost, "bench": bench,
                         "turnover": trade, "cost": cost, "names": len(top)})
        df = pd.DataFrame(rows).set_index("month")
        df["excess_net"] = df.net - df.bench
        df.to_csv(OUTPUT / f"{name}_monthly.csv")
        ff = ff_factors(df.index)

        def summary(x):
            e = x.excess_net
            w = (1 + x.net).cumprod()
            starts_draws = []
            keys = np.arange(len(e))
            for _ in range(4000):
                s = rng.integers(0, max(1, len(e) - 6), size=int(np.ceil(len(e) / 6)))
                pick = np.concatenate([keys[k:k + 6] for k in s])[:len(e)]
                starts_draws.append(e.iloc[pick].mean() - e.mean())
            p = float((np.abs(np.array(starts_draws)) >= abs(e.mean())).mean())
            a, t = nw_alpha_t(x.net - ff.reindex(x.index)["RF"], ff.reindex(x.index)[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]])
            vol = x.net.std() * np.sqrt(12)
            return {"months": int(len(x)), "net_excess_annual": float(e.mean() * 12), "gross_excess_annual": float((x.gross - x.bench).mean() * 12),
                    "cost_drag_annual": float(x.cost.mean() * 12), "turnover_annual": float(x.turnover.mean() * 12),
                    "p": p, "ff6_alpha_annual": a, "ff6_alpha_t": t, "cagr_net": float(w.iloc[-1] ** (12 / len(x)) - 1),
                    "vol": float(vol), "sharpe_net": float((x.net - ff.reindex(x.index)["RF"]).mean() * 12 / vol),
                    "max_dd": float((w / w.cummax() - 1).min()), "median_names": float(x.names.median()),
                    "bench_cagr": float((1 + x.bench).prod() ** (12 / len(x)) - 1)}
        d = summary(df[(df.index >= DESIGN[0]) & (df.index <= DESIGN[1])])
        h = summary(df[(df.index >= HOLDOUT[0]) & (df.index <= HOLDOUT[1])])
        top10 = sorted(contrib, key=contrib.get, reverse=True)[:10]
        crit = {"design_net_excess_positive_p_below_bar": d["net_excess_annual"] > 0 and d["p"] < 0.025,
                "holdout_net_excess_positive": h["net_excess_annual"] > 0,
                "design_ff6_alpha_t_ge_2": d["ff6_alpha_t"] >= 2,
                "top10_contributors": [str(cols[i]) for i in top10]}
        crit_pass = all(v for k, v in crit.items() if k != "top10_contributors")
        out[name] = {"design": d, "holdout": h, "criteria": crit, "passes_before_leave_out": crit_pass,
                     "by_year": {str(y): float(df[df.index.year == y].excess_net.sum()) for y in sorted(set(df.index.year))}}
        print(f"\n== {name}")
        for lab, s in (("design 2013-19", d), ("holdout 2020-25", h)):
            print(f"  {lab}: net excess {s['net_excess_annual']:+.2%}/yr (gross {s['gross_excess_annual']:+.2%}, cost drag "
                  f"{s['cost_drag_annual']:.2%}, turnover {s['turnover_annual']:.1f}x) p {s['p']:.4f} | FF6 alpha "
                  f"{s['ff6_alpha_annual']:+.2%} t {s['ff6_alpha_t']:+.2f} | CAGR net {s['cagr_net']:+.2%} vs band {s['bench_cagr']:+.2%}, "
                  f"Sharpe {s['sharpe_net']:.2f}, maxDD {s['max_dd']:+.1%}, ~{s['median_names']:.0f} names")
        print("  by year (net excess): " + " ".join(f"{y}:{v:+.1%}" for y, v in out[name]["by_year"].items()))
        for k, v in crit.items():
            if k != "top10_contributors":
                print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    (OUTPUT / "stage2_result.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit({"calibrate": stage_calibrate, "screen": stage_screen}[sys.argv[1]]())
