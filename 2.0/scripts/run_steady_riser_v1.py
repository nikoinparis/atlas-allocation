#!/usr/bin/env python3
"""Can 'stocks that are constantly on the rise' be picked in advance and held a year?

Pre-registered in config/steady_riser_registry_v1.json. Two signals -- plain 12-1
momentum and a 'steady riser' score (annualised log-price slope x R-squared) --
judged the way the owner would use them: buy the top 20, hold 52 weeks, rebalance
once a year.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config/steady_riser_registry_v1.json"
PRICES = ROOT / "data/clean_full_history_prices_v1/weekly_adjusted_prices_clean.csv.gz"
VOLUME = ROOT / "data/us_daily_volume_v1"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
FF = sorted((ROOT / "data/fama_french_factor_vintages").glob("*-ff5-mom-daily"))[-1]
OUTPUT = ROOT / "evidence/steady_riser_v1"
LOOKBACK, SKIP, HORIZON, STEP, TOP = 52, 4, 52, 13, 20
MIN_PRICE, MIN_DOLLAR_VOLUME = 5.0, 5_000_000.0
BAR, PLACEBO = 0.025, 200
REGIMES = {"2012-2019": ("2012", "2019"), "2020": ("2020", "2020"), "2021-2022": ("2021", "2022"),
           "2023-2026": ("2023", "2026")}


def load():
    prices = pd.read_csv(PRICES, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    prices.index = pd.to_datetime(prices.index, utc=True).tz_localize(None).normalize()
    prices.columns = [str(c).zfill(10) for c in prices.columns]
    close = pd.read_csv(VOLUME / "daily_close.csv.gz", index_col=0, parse_dates=True)
    volume = pd.read_csv(VOLUME / "daily_volume.csv.gz", index_col=0, parse_dates=True)
    dollar = (close * volume).rolling(63, min_periods=40).median()
    dollar.columns = [str(c).zfill(10) for c in dollar.columns]
    return prices, dollar


def signals(block: pd.DataFrame) -> pd.DataFrame:
    """block: LOOKBACK+1 weekly closes ending at the decision, complete columns only."""
    mom = block.iloc[-1 - SKIP] / block.iloc[0] - 1.0
    y = np.log(block.iloc[-LOOKBACK:].to_numpy())
    t = np.arange(len(y), dtype=float)
    tc = t - t.mean()
    yc = y - y.mean(0)
    slope = (tc[:, None] * yc).sum(0) / (tc ** 2).sum()
    fitted = slope[None, :] * tc[:, None]
    r2 = 1 - ((yc - fitted) ** 2).sum(0) / (yc ** 2).sum(0)
    steady = (np.exp(slope * 52) - 1) * r2
    return pd.DataFrame({"S1_momentum_12_1": mom.to_numpy(), "S2_steady_riser": steady}, index=block.columns)


def eligible(prices, dollar, pos):
    block = prices.iloc[pos - LOOKBACK:pos + 1]
    ok = block.notna().all() & (block.iloc[-1] >= MIN_PRICE)
    when = prices.index[pos]
    dv = dollar[dollar.index <= when]
    if dv.empty:
        return block.loc[:, []]
    liquid = dv.iloc[-1].reindex(block.columns) >= MIN_DOLLAR_VOLUME
    return block.loc[:, ok & liquid.fillna(False)]


def screen(prices, dollar, rng):
    returns = prices.pct_change(fill_method=None).where(lambda r: r.abs() <= 1.0)
    rows = {k: [] for k in ("S1_momentum_12_1", "S2_steady_riser")}
    for pos in range(LOOKBACK, len(prices) - HORIZON - 1, STEP):
        block = eligible(prices, dollar, pos)
        if block.shape[1] < 100:
            continue
        sig = signals(block)
        fwd = (1 + returns.iloc[pos + 1:pos + 1 + HORIZON]).prod(min_count=HORIZON // 2) - 1
        for name in rows:
            frame = pd.DataFrame({"s": sig[name], "f": fwd.reindex(sig.index)}).dropna()
            if len(frame) < 100:
                continue
            ic = frame.s.rank().corr(frame.f.rank())
            dec = pd.qcut(frame.s.rank(method="first"), 10, labels=False)
            means = frame.f.groupby(dec).mean()
            mono = pd.Series(means.index).corr(pd.Series(means.to_numpy()), method="spearman")
            rows[name].append({"date": prices.index[pos], "n": len(frame), "ic": ic,
                               "spread": means.iloc[-1] - means.iloc[0], "mono": mono,
                               "top": means.iloc[-1], "bottom": means.iloc[0]})
    out = {}
    for name, r in rows.items():
        d = pd.DataFrame(r)
        ics = d.ic.to_numpy()
        draws = []
        for _ in range(4000):
            starts = rng.integers(0, max(1, len(ics) - 4), size=int(np.ceil(len(ics) / 4)))
            draws.append(np.concatenate([ics[i:i + 4] for i in starts])[:len(ics)].mean() - ics.mean())
        half = len(d) // 2
        out[name] = {"decisions": len(d), "independent_windows": len(d) // 4,
                     "median_names": float(d.n.median()), "mean_ic": float(ics.mean()),
                     "p": float((np.abs(draws) >= abs(ics.mean())).mean()),
                     "decile_spread_52w": float(d.spread.mean()),
                     "top_decile_52w": float(d.top.mean()), "bottom_decile_52w": float(d.bottom.mean()),
                     "monotonicity": float(d.mono.mean()),
                     "first_half_ic": float(d.ic.iloc[:half].mean()), "second_half_ic": float(d.ic.iloc[half:].mean())}
    return out


def book_paths(prices, dollar, rng, catalogue):
    returns = prices.pct_change(fill_method=None).where(lambda r: r.abs() <= 1.0)
    years = list(range(LOOKBACK, len(prices) - 1, HORIZON))
    books = {"S1_momentum_12_1": [], "S2_steady_riser": [], "universe": []}
    placebo = [[] for _ in range(PLACEBO)]
    holdings, turnover = {k: [] for k in books}, {k: [] for k in books}
    contrib = {k: {} for k in books}
    prev = {k: set() for k in books}
    for pos in years:
        block = eligible(prices, dollar, pos)
        sig = signals(block)
        stop = min(pos + 1 + HORIZON, len(prices))
        window = returns.iloc[pos + 1:stop].fillna(0.0)        # a name that stops trading sits in cash
        picks = {"S1_momentum_12_1": list(sig.S1_momentum_12_1.nlargest(TOP).index),
                 "S2_steady_riser": list(sig.S2_steady_riser.nlargest(TOP).index),
                 "universe": list(block.columns)}
        for key, names in picks.items():
            growth = (1 + window[names]).cumprod()
            value = growth.mean(axis=1)
            path = value / value.shift(1).fillna(1.0) - 1
            books[key].append(path)
            new = set(names)
            turnover[key].append(1.0 if not prev[key] else len(new - prev[key]) / len(new))
            prev[key] = new
            for n in names:
                contrib[key][n] = contrib[key].get(n, 0.0) + float(growth[n].iloc[-1] - 1) / len(names)
            if key != "universe":
                holdings[key].append({"date": str(prices.index[pos].date()),
                                      "names": [catalogue.get(n, n) for n in names]})
        for i in range(PLACEBO):
            names = list(rng.choice(block.columns, size=TOP, replace=False))
            value = (1 + window[names]).cumprod().mean(axis=1)
            placebo[i].append(value / value.shift(1).fillna(1.0) - 1)
    paths = {k: pd.concat(v) for k, v in books.items()}
    plac = [pd.concat(p) for p in placebo]
    return paths, plac, holdings, turnover, contrib


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    w = (1 + r).cumprod()
    yrs = len(r) / 52
    cagr = w.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * np.sqrt(52)
    return {"cagr": float(cagr), "vol": float(vol), "sharpe": float(cagr / vol) if vol > 0 else None,
            "max_dd": float((w / w.cummax() - 1).min()), "total": float(w.iloc[-1] - 1), "weeks": len(r)}


def with_costs(r: pd.Series, turns: list[float], bps: float) -> pd.Series:
    r = r.copy()
    starts = [i for i in range(0, len(r), HORIZON)]
    for i, t in zip(starts, turns):
        r.iloc[i] -= 2 * t * bps / 1e4      # sell the leavers and buy the joiners
    return r


def main() -> int:
    json.loads(REGISTRY.read_text())
    rng = np.random.default_rng(20261012)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices, dollar = load()
    cat = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows").drop_duplicates("cik10", keep="last")
    catalogue = dict(zip(cat.cik10, cat.symbol))

    scr = screen(prices, dollar, rng)
    print("== screen: does the ranking predict the next 52 weeks?")
    for k, v in scr.items():
        print(f"  {k:18s} decisions {v['decisions']} (indep {v['independent_windows']}), names {v['median_names']:.0f}: "
              f"IC {v['mean_ic']:+.4f} p {v['p']:.3f} | top decile {v['top_decile_52w']:+.1%} bottom {v['bottom_decile_52w']:+.1%} "
              f"spread {v['decile_spread_52w']:+.1%} | monotonicity {v['monotonicity']:+.2f} | halves {v['first_half_ic']:+.3f}/{v['second_half_ic']:+.3f}")

    paths, plac, holdings, turnover, contrib = book_paths(prices, dollar, rng, catalogue)
    spy = yf.download("SPY", start=str(prices.index[0].date()), auto_adjust=True, progress=False)["Close"].squeeze()
    spy.index = pd.to_datetime(spy.index).tz_localize(None)
    spy_w = spy.resample("W-FRI").last().pct_change().reindex(paths["universe"].index)
    plac50 = np.array([metrics(with_costs(p, [1.0] * 20, 50))["cagr"] for p in plac])

    result = {"screen": scr, "books": {}, "placebo_cagr_50bps": {"mean": float(plac50.mean()),
              "p95": float(np.percentile(plac50, 95))}}
    print(f"\n== books: top {TOP}, hold 52 weeks, rebalance yearly  ({paths['universe'].index[0].date()} to {paths['universe'].index[-1].date()})")
    print(f"  random 20-name books at 50 bps: mean CAGR {plac50.mean():+.1%}, 95th pct {np.percentile(plac50, 95):+.1%}")
    series = {"SPY": spy_w, **{k: v for k, v in paths.items()}}
    for key, r in series.items():
        turns = turnover.get(key, [0.0] * 20)
        row = {f"{b}bps": metrics(with_costs(r, turns, b) if key != "SPY" else r) for b in (0, 10, 50, 100)}
        r50 = with_costs(r, turns, 50) if key != "SPY" else r
        row["regimes_50bps"] = {g: metrics(r50[(r50.index >= f"{a}-01-01") & (r50.index <= f"{b}-12-31")])
                                for g, (a, b) in REGIMES.items()}
        row["avg_turnover"] = float(np.mean(turns[1:])) if key in turnover else 0.0
        if key in contrib and key != "universe":
            c = pd.Series(contrib[key]).sort_values(ascending=False)
            row["top_contributors"] = [(catalogue.get(n, n), round(v, 3)) for n, v in c.head(5).items()]
        result["books"][key] = row
        m = row["50bps"]
        reg = " ".join(f"{g} {row['regimes_50bps'][g]['cagr']:+.1%}" for g in REGIMES)
        print(f"  {key:18s} @50bps CAGR {m['cagr']:+.1%} Sharpe {m['sharpe']:.2f} vol {m['vol']:.1%} maxDD {m['max_dd']:+.1%} "
              f"| turnover/yr {row['avg_turnover']:.0%} | {reg}")
        if "top_contributors" in row:
            print(f"      biggest contributors (sum of yearly gains / 20): {row['top_contributors']}")
        costs = " ".join(f"{b}bps {row[f'{b}bps']['cagr']:+.1%}" for b in (0, 10, 50, 100))
        print(f"      cost ladder: {costs}")

    # Leave the largest contributor out: zero its contribution, crude but direct.
    for key in ("S1_momentum_12_1", "S2_steady_riser"):
        c = pd.Series(contrib[key]).sort_values(ascending=False)
        result["books"][key]["largest_contributor_sum"] = float(c.iloc[0])

    # Same-risk and factor alpha at 50 bps.
    ff = pd.read_csv(next(FF.glob("F-F_Research_Data_5*daily.csv")), skiprows=3, index_col=0)
    ff = ff[ff.index.astype(str).str.len() == 8].astype(float) / 100
    ff.index = pd.to_datetime(ff.index.astype(str))
    mom = pd.read_csv(next(FF.glob("F-F_Momentum*daily.csv")), skiprows=13, index_col=0)
    mom = mom[mom.index.astype(str).str.strip().str.len() == 8].astype(float) / 100
    mom.index = pd.to_datetime(mom.index.astype(str).str.strip())
    ff = ff.join(mom, how="inner")
    ff.columns = [c.strip() for c in ff.columns]
    wk = (1 + ff).resample("W-FRI").prod() - 1
    for key in ("S1_momentum_12_1", "S2_steady_riser", "universe"):
        r = with_costs(paths[key], turnover[key], 50)
        j = pd.concat({"r": r}, axis=1).join(wk, how="inner").dropna()
        y = j.r - j.RF
        out = {}
        for label, cols in (("capm", ["Mkt-RF"]), ("ff6", ["Mkt-RF", "SMB", "HML", "RMW", "CMA", j.columns[-1]])):
            X = np.column_stack([np.ones(len(j))] + [j[c] for c in cols])
            beta, *_ = np.linalg.lstsq(X, y.to_numpy(), rcond=None)
            resid = y.to_numpy() - X @ beta
            se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * resid.var(ddof=X.shape[1]))
            out[label] = {"alpha_annual": float((1 + beta[0]) ** 52 - 1), "t": float(beta[0] / se[0]),
                          "market_beta": float(beta[1])}
        result["books"][key]["alpha"] = out
        print(f"  {key:18s} alpha @50bps: CAPM {out['capm']['alpha_annual']:+.1%} (t {out['capm']['t']:+.2f}, beta {out['capm']['market_beta']:.2f}) "
              f"| FF6 {out['ff6']['alpha_annual']:+.1%} (t {out['ff6']['t']:+.2f})")

    result["holdings"] = holdings
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=1, default=str) + "\n")
    print("\nholdings, steady riser, last 3 years:")
    for h in holdings["S2_steady_riser"][-3:]:
        print(" ", h["date"], ", ".join(h["names"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
