#!/usr/bin/env python3
"""The rising-stocks program: signals x rebalance cadence x safety nets.

Pre-registered in config/rising_stocks_program_registry_v1.json. Two phases, run as
two separate invocations so the holdout cannot leak into the choice:

    --phase design   simulate all 45 configurations, rank them on 2012-2019 only,
                     write the single chosen configuration to choice.json
    --phase holdout  refuse to run unless choice.json exists; then report 2020-2026
                     for the chosen one with every control, and every other
                     configuration's holdout for transparency
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_steady_riser_v1 as sr                                          # noqa: E402

REGISTRY = ROOT / "config/rising_stocks_program_registry_v1.json"
OUTPUT = ROOT / "evidence/rising_stocks_program_v1"
FSDS = ROOT / "data/sec_fsds_history_v1"
DESIGN = ("2012-01-01", "2019-12-31")
HOLDOUT = ("2020-01-01", "2026-12-31")
SIGNALS = ["A_steady_riser", "B_theme_rotation", "C_residual_momentum"]
CADENCES = [4, 13, 52]
NETS = ["none", "market_trend", "stock_exit", "vol_target", "trend_plus_exit"]
TOP, BPS, VOL_TARGET = 20, 50.0, 0.20


# ----------------------------------------------------------------------------- data
def load_sic() -> pd.DataFrame:
    frames = []
    for path in sorted(FSDS.glob("*.zip")):
        try:
            with zipfile.ZipFile(path) as archive, archive.open("sub.txt") as handle:
                sub = pd.read_csv(io.TextIOWrapper(handle, "utf-8", errors="replace"), sep="\t",
                                  usecols=["cik", "sic", "filed"], low_memory=False)
        except Exception:                                                  # noqa: BLE001
            continue
        frames.append(sub.dropna())
    sic = pd.concat(frames)
    sic["cik10"] = sic.cik.astype("int64").astype(str).str.zfill(10)
    sic["sic3"] = sic.sic.astype("int64").astype(str).str.zfill(4).str[:3]
    sic["available"] = pd.to_datetime(sic.filed.astype("int64").astype(str), format="%Y%m%d") + pd.Timedelta(days=1)
    return sic.sort_values("available")[["cik10", "sic3", "available"]]


def weekly_rf() -> pd.Series:
    ff = pd.read_csv(next(sr.FF.glob("F-F_Research_Data_5*daily.csv")), skiprows=3, index_col=0)
    ff = ff[ff.index.astype(str).str.len() == 8].astype(float) / 100
    ff.index = pd.to_datetime(ff.index.astype(str))
    return (1 + ff["RF"]).resample("W-FRI").prod() - 1


def factors_weekly() -> pd.DataFrame:
    ff = pd.read_csv(next(sr.FF.glob("F-F_Research_Data_5*daily.csv")), skiprows=3, index_col=0)
    ff = ff[ff.index.astype(str).str.len() == 8].astype(float) / 100
    ff.index = pd.to_datetime(ff.index.astype(str))
    mom = pd.read_csv(next(sr.FF.glob("F-F_Momentum*daily.csv")), skiprows=13, index_col=0)
    mom = mom[mom.index.astype(str).str.strip().str.len() == 8].astype(float) / 100
    mom.index = pd.to_datetime(mom.index.astype(str).str.strip())
    ff = ff.join(mom, how="inner")
    ff.columns = [c.strip() for c in ff.columns]
    return (1 + ff).resample("W-FRI").prod() - 1


class Signals:
    def __init__(self, prices, dollar, sic):
        self.prices, self.dollar, self.sic = prices, dollar, sic
        self.returns = prices.pct_change(fill_method=None).where(lambda r: r.abs() <= 1.0)
        self.cache = {}

    def at(self, pos: int) -> dict[str, list[str]]:
        if pos in self.cache:
            return self.cache[pos]
        block = sr.eligible(self.prices, self.dollar, pos)
        out = {"universe": list(block.columns)}
        if block.shape[1] < 60:
            self.cache[pos] = {**out, **{s: [] for s in SIGNALS}}
            return self.cache[pos]
        base = sr.signals(block)["S2_steady_riser"]
        out["A_steady_riser"] = list(base.nlargest(TOP).index)

        when = self.prices.index[pos]
        known = self.sic[self.sic.available <= when].groupby("cik10").sic3.last()
        ind = known.reindex(block.columns)
        r26 = block.iloc[-1] / block.iloc[-27] - 1
        frame = pd.DataFrame({"ind": ind, "r26": r26, "score": base}).dropna(subset=["ind"])
        sizes = frame.groupby("ind").r26.transform("size")
        industry = frame[sizes >= 5].groupby("ind").r26.mean()
        hot = industry[industry >= industry.quantile(0.8)].index
        out["B_theme_rotation"] = list(frame[frame.ind.isin(hot)].score.nlargest(TOP).index)

        r = self.returns.iloc[pos - 51:pos + 1][block.columns].fillna(0.0).to_numpy()
        m = r.mean(axis=1, keepdims=True)
        mc = m - m.mean()
        beta = ((r - r.mean(0)) * mc).sum(0) / (mc ** 2).sum()
        resid = r - r.mean(0) - beta * mc
        window = resid[:-4]
        score = window.sum(0) / (window.std(0, ddof=1) + 1e-12)
        out["C_residual_momentum"] = list(pd.Series(score, index=block.columns).nlargest(TOP).index)
        self.cache[pos] = out
        return out


# ----------------------------------------------------------------------------- engine
def simulate(sig: Signals, signal: str, cadence: int, net: str, spy: pd.DataFrame, rf: pd.Series,
             rng: np.random.Generator | None = None) -> tuple[pd.Series, dict]:
    prices, returns = sig.prices, sig.returns
    ma20 = prices.rolling(20).mean()
    dates = prices.index
    rf = rf.reindex(dates).fillna(0.0)
    spy_off = (spy.close < spy.ma40).reindex(dates).fillna(False)
    start = sr.LOOKBACK
    pos_val: dict[str, float] = {}
    cash, picks, exited = 1.0, [], set()
    market_out = False
    sleeve_hist: list[float] = []
    out, contrib, traded = [], {}, 0.0
    last_value = 1.0          # end-of-week value; every return is measured from it, so costs land in returns

    def trade(amount: float) -> float:
        nonlocal traded
        traded += abs(amount) / max(cash + sum(pos_val.values()), 1e-12)
        return abs(amount) * BPS / 1e4

    for pos in range(start, len(dates) - 1):
        total = cash + sum(pos_val.values())
        # ---- decisions at the close of week `pos`, applied to week pos+1
        if (pos - start) % cadence == 0:
            names = sig.at(pos)["universe"] if rng is not None else sig.at(pos)[signal]
            if rng is not None and names:
                names = list(rng.choice(names, size=min(TOP, len(names)), replace=False))
            picks, exited = names, set()
            target = {} if (net in ("market_trend", "trend_plus_exit") and spy_off.iloc[pos]) or not picks \
                else {n: total / len(picks) for n in picks}
            cost = sum(trade(target.get(n, 0) - pos_val.get(n, 0)) for n in set(target) | set(pos_val))
            scale = (total - cost) / total
            pos_val = {n: v * scale for n, v in target.items()}
            cash = total - cost - sum(pos_val.values())
            market_out = net in ("market_trend", "trend_plus_exit") and bool(spy_off.iloc[pos])
        else:
            if net in ("stock_exit", "trend_plus_exit"):
                for n in [n for n in pos_val if prices[n].iloc[pos] < ma20[n].iloc[pos]]:
                    cash += pos_val[n] - trade(pos_val[n])
                    del pos_val[n]
                    exited.add(n)
            if net in ("market_trend", "trend_plus_exit"):
                off = bool(spy_off.iloc[pos])
                if off and not market_out:
                    cash += sum(pos_val.values()) - sum(trade(v) for v in pos_val.values())
                    pos_val, market_out = {}, True
                elif not off and market_out:
                    live = [n for n in picks if n not in exited and pd.notna(prices[n].iloc[pos])]
                    if live:
                        cost = sum(trade(cash / len(live)) for _ in live)
                        each = (cash - cost) / len(live)
                        pos_val = {n: each for n in live}
                        cash = 0.0
                    market_out = False
        if net == "vol_target" and pos_val and len(sleeve_hist) >= 13:
            vol = np.std(sleeve_hist[-13:], ddof=1) * math.sqrt(52)
            want = min(1.0, VOL_TARGET / vol) if vol > 0 else 1.0
            total = cash + sum(pos_val.values())
            have = sum(pos_val.values()) / total
            if abs(want - have) > 0.10:
                scale = want * total / sum(pos_val.values())
                delta = sum(v * (scale - 1) for v in pos_val.values())
                cost = trade(delta)
                pos_val = {n: v * scale for n, v in pos_val.items()}
                cash -= delta + cost
        # ---- week pos+1 returns, measured from last week's closing value (costs included)
        before = last_value
        risky_before = sum(pos_val.values())
        for n in list(pos_val):
            r = returns[n].iloc[pos + 1]
            r = 0.0 if pd.isna(r) else r
            contrib[n] = contrib.get(n, 0.0) + pos_val[n] * r / max(cash + sum(pos_val.values()), 1e-12)
            pos_val[n] *= 1 + r
        cash *= 1 + rf.iloc[pos + 1]
        after = cash + sum(pos_val.values())
        if risky_before > 0:
            sleeve_hist.append(sum(pos_val.values()) / risky_before - 1)
        out.append((dates[pos + 1], after / before - 1))
        last_value = after
    path = pd.Series(dict(out))
    return path, {"contrib": contrib, "traded_per_year": traded / (len(out) / 52)}


def metrics(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 10:
        return {}
    w = (1 + r).cumprod()
    yrs = len(r) / 52
    cagr = float(w.iloc[-1] ** (1 / yrs) - 1)
    vol = float(r.std() * math.sqrt(52))
    return {"cagr": cagr, "vol": vol, "sharpe": cagr / vol if vol > 0 else float("nan"),
            "max_dd": float((w / w.cummax() - 1).min()), "total": float(w.iloc[-1] - 1), "weeks": len(r)}


def window(r: pd.Series, span) -> pd.Series:
    return r[(r.index >= span[0]) & (r.index <= span[1])]


def spy_frame(index) -> pd.DataFrame:
    s = yf.download("SPY", start="2009-01-01", auto_adjust=True, progress=False)["Close"].squeeze()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    w = s.resample("W-FRI").last()
    return pd.DataFrame({"close": w, "ma40": w.rolling(40).mean(), "ret": w.pct_change()})


def deflated_sharpe(sr_obs: float, sr_trials: list[float], n: int, skew: float, kurt: float) -> float:
    """Bailey & Lopez de Prado; Sharpe in per-period units. From general knowledge of AFML ch. 14."""
    from statistics import NormalDist
    nd = NormalDist()
    k = len(sr_trials)
    var = float(np.var(sr_trials, ddof=1))
    gamma = 0.5772156649
    sr0 = math.sqrt(var) * ((1 - gamma) * nd.inv_cdf(1 - 1 / k) + gamma * nd.inv_cdf(1 - 1 / (k * math.e)))
    denom = math.sqrt(max(1e-12, 1 - skew * sr_obs + (kurt - 1) / 4 * sr_obs ** 2))
    return nd.cdf((sr_obs - sr0) * math.sqrt(n - 1) / denom)


# ----------------------------------------------------------------------------- phases
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["design", "holdout"], required=True)
    args = parser.parse_args()
    json.loads(REGISTRY.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices, dollar = sr.load()
    sig = Signals(prices, dollar, load_sic())
    spy = spy_frame(prices.index)
    rf = weekly_rf()
    configs = [(s, c, n) for s in SIGNALS for c in CADENCES for n in NETS]

    if args.phase == "design":
        rows, paths = [], {}
        for s, c, n in configs:
            path, info = simulate(sig, s, c, n, spy, rf)
            key = f"{s}|{c}w|{n}"
            paths[key] = path
            m = metrics(window(path, DESIGN))
            rows.append({"config": key, **{f"design_{k}": v for k, v in m.items()},
                         "traded_per_year": info["traded_per_year"]})
            print(f"{key:42s} design CAGR {m['cagr']:+.1%} Sharpe {m['sharpe']:.2f} DD {m['max_dd']:+.1%} "
                  f"traded/yr {info['traded_per_year']:.1f}x", flush=True)
        table = pd.DataFrame(rows).sort_values(["design_sharpe", "design_max_dd"], ascending=[False, False])
        table.to_csv(OUTPUT / "design_table.csv", index=False)
        pd.DataFrame(paths).to_csv(OUTPUT / "all_paths.csv.gz")
        spy_design = metrics(window(spy.ret.reindex(paths[table.config.iloc[0]].index), DESIGN))
        choice = {"config": table.config.iloc[0], "design": table.iloc[0].to_dict(),
                  "spy_design": spy_design, "chosen_by": "highest design Sharpe at 50 bps, tie -> lower drawdown",
                  "chosen_before_holdout_was_computed": True}
        (OUTPUT / "choice.json").write_text(json.dumps(choice, indent=1, default=float) + "\n")
        print(f"\nSPY design: CAGR {spy_design['cagr']:+.1%} Sharpe {spy_design['sharpe']:.2f} DD {spy_design['max_dd']:+.1%}")
        print(f"CHOSEN: {choice['config']}")
        return 0

    choice_file = OUTPUT / "choice.json"
    if not choice_file.is_file():
        raise SystemExit("no choice.json: run --phase design first")
    choice = json.loads(choice_file.read_text())
    s, c, n = choice["config"].split("|")
    c = int(c.rstrip("w"))
    paths = pd.read_csv(OUTPUT / "all_paths.csv.gz", index_col=0, parse_dates=True)
    chosen = paths[choice["config"]]
    hold = window(chosen, HOLDOUT)
    spy_r = spy.ret.reindex(chosen.index)
    res = {"config": choice["config"], "holdout": metrics(hold), "spy_holdout": metrics(window(spy_r, HOLDOUT)),
           "design": metrics(window(chosen, DESIGN)), "spy_design": metrics(window(spy_r, DESIGN))}

    # costs at other levels for the chosen config
    ladder = {}
    global BPS
    for b in (0, 10, 100):
        BPS = b
        p, _ = simulate(sig, s, c, n, spy, rf)
        ladder[f"{b}bps"] = metrics(window(p, HOLDOUT))
    BPS = 50.0
    res["holdout_cost_ladder"] = ladder
    _, info = simulate(sig, s, c, n, spy, rf)
    contrib = pd.Series(info["contrib"]).sort_values(ascending=False)
    cat = pd.read_csv(sr.CATALOGUE, dtype={"cik10": str}).sort_values("rows").drop_duplicates("cik10", keep="last")
    sym = dict(zip(cat.cik10, cat.symbol))
    res["top_contributors_full"] = [(sym.get(k, k), round(v, 3)) for k, v in contrib.head(8).items()]
    res["traded_per_year"] = info["traded_per_year"]

    # regimes
    res["regimes"] = {g: {"book": metrics(window(chosen, (a, b))), "spy": metrics(window(spy_r, (a, b)))}
                      for g, (a, b) in {"2020": ("2020-01-01", "2020-12-31"), "2021-2022": ("2021-01-01", "2022-12-31"),
                                        "2023-2026": ("2023-01-01", "2026-12-31")}.items()}
    # factor alpha on holdout
    fw = factors_weekly()
    j = pd.concat({"r": hold}, axis=1).join(fw, how="inner").dropna()
    y = (j.r - j.RF).to_numpy()
    cols = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", j.columns[-1]]
    X = np.column_stack([np.ones(len(j))] + [j[k] for k in cols])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * e.var(ddof=X.shape[1]))
    res["ff6_holdout"] = {"alpha_annual": float((1 + beta[0]) ** 52 - 1), "t": float(beta[0] / se[0]),
                          "market_beta": float(beta[1]), "weeks": int(len(j))}
    # placebo: random 20 from the same universe, same cadence and net
    rng = np.random.default_rng(20261013)
    plac = []
    for _ in range(200):
        p, _ = simulate(sig, s, c, n, spy, rf, rng=rng)
        plac.append(metrics(window(p, HOLDOUT))["cagr"])
    res["placebo_holdout_cagr"] = {"mean": float(np.mean(plac)), "p95": float(np.percentile(plac, 95))}
    # deflated Sharpe over the 45 design trials (weekly units)
    design_srs = []
    for col in paths.columns:
        r = window(paths[col], DESIGN).dropna()
        design_srs.append(r.mean() / r.std())
    rd = window(chosen, DESIGN).dropna()
    res["deflated_sharpe_design"] = deflated_sharpe(rd.mean() / rd.std(), design_srs, len(rd),
                                                    float(rd.skew()), float(rd.kurt() + 3))
    rh = hold.dropna()
    res["deflated_sharpe_holdout_single_trial"] = deflated_sharpe(rh.mean() / rh.std(), [0, 1e-9], len(rh),
                                                                  float(rh.skew()), float(rh.kurt() + 3))
    # holdings now
    last_pos = sr.LOOKBACK + ((len(prices) - 2 - sr.LOOKBACK) // c) * c
    res["latest_rebalance"] = {"date": str(prices.index[last_pos].date()),
                               "names": [sym.get(k, k) for k in sig.at(last_pos)[s]]}
    # transparency: every config's holdout
    res["all_configs_holdout"] = {col: metrics(window(paths[col], HOLDOUT)) for col in paths.columns}

    h, sh = res["holdout"], res["spy_holdout"]
    criteria = {
        "sharpe_ge_spy": h["sharpe"] >= sh["sharpe"],
        "cagr_ge_spy": h["cagr"] >= sh["cagr"],
        "ff6_alpha_t_ge_2": res["ff6_holdout"]["t"] >= 2.0,
        "beats_random_books_p95": h["cagr"] > res["placebo_holdout_cagr"]["p95"],
        "max_dd_no_worse_than_-35pct": h["max_dd"] >= -0.35,
    }
    res["criteria"], res["passes"] = criteria, all(criteria.values())
    (OUTPUT / "holdout_result.json").write_text(json.dumps(res, indent=1, default=float) + "\n")
    print(json.dumps({k: res[k] for k in ("config", "design", "spy_design", "holdout", "spy_holdout", "ff6_holdout",
                                          "placebo_holdout_cagr", "deflated_sharpe_design", "regimes",
                                          "holdout_cost_ladder", "top_contributors_full", "traded_per_year",
                                          "criteria", "passes", "latest_rebalance")}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
