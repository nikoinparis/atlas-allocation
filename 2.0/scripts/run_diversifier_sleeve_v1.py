#!/usr/bin/env python3
"""Diversifier-sleeve evaluation on live funds' records (A30 stage 1: merger arbitrage).

Pre-registered in config/merger_arb_sleeve_registry_v1.json. Not a signal test: correlation, crisis
behaviour and what a 20% sleeve does to a portfolio, over each fund's full public record. The exact
downloaded prices are frozen to the evidence folder with a sha256 so the result is reproducible.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_synthetic_boom_calls_v1 as calls  # noqa: E402  (Fama-French RF loader)

REGISTRY = ROOT / "config/merger_arb_sleeve_registry_v1.json"
OUTPUT = ROOT / "evidence/merger_arb_sleeve_v1"
FUNDS = ["MERFX", "ARBFX", "MNA"]
END = "2026-08-31"
CRISES = {"2000-02": ("2000-09", "2002-09"), "2007-09": ("2007-10", "2009-02"), "2011": ("2011-05", "2011-09"),
          "2015-16": ("2015-06", "2016-02"), "2018Q4": ("2018-10", "2018-12"), "2020": ("2020-02", "2020-03"),
          "2022": ("2022-01", "2022-09")}


def monthly_total_returns(tickers: list[str]) -> pd.DataFrame:
    raw = yf.download(tickers, start="1990-01-01", end="2026-09-01", auto_adjust=True, progress=False)["Close"]
    raw = raw[tickers].dropna(how="all")
    raw.to_csv(OUTPUT / "daily_adjusted_closes.csv.gz")
    m = raw.resample("ME").last()
    return m.pct_change(fill_method=None)


def stats(r: pd.Series, rf: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 24:
        return {"months": int(len(r))}
    ex = r - rf.reindex(r.index).fillna(0)
    w = (1 + r).cumprod()
    return {"months": int(len(r)), "start": str(r.index[0].date()), "cagr": float(w.iloc[-1] ** (12 / len(r)) - 1),
            "vol": float(r.std() * np.sqrt(12)), "sharpe": float(ex.mean() / ex.std() * np.sqrt(12)),
            "max_dd": float((w / w.cummax() - 1).min())}


def window_return(r: pd.Series, a: str, b: str) -> float:
    x = r[(r.index >= pd.Timestamp(a)) & (r.index <= pd.Timestamp(b) + pd.offsets.MonthEnd(0))].dropna()
    return float((1 + x).prod() - 1) if len(x) else float("nan")


def boot_sharpe_diff(a: pd.Series, b: pd.Series, rf: pd.Series, rng, block: int = 12) -> float:
    df = pd.concat([a, b], axis=1).dropna()
    ex = df.sub(rf.reindex(df.index).fillna(0), axis=0).to_numpy()
    def sh(x): return x.mean(0) / x.std(0) * np.sqrt(12)
    obs = sh(ex)[0] - sh(ex)[1]
    draws = []
    for _ in range(4000):
        starts = rng.integers(0, len(ex) - block, size=int(np.ceil(len(ex) / block)))
        idx = np.concatenate([np.arange(s, s + block) for s in starts])[:len(ex)]
        s = sh(ex[idx])
        draws.append(s[0] - s[1] - obs)
    return float((np.abs(np.array(draws)) >= abs(obs)).mean())


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261019)
    r = monthly_total_returns(FUNDS + ["SPY", "GLD", "SHY"])
    r = r[r.index <= END]
    digest = hashlib.sha256((OUTPUT / "daily_adjusted_closes.csv.gz").read_bytes()).hexdigest()
    rf_d = calls.load_rf(pd.date_range("1990-01-01", END, freq="B"))
    rf = (1 + rf_d).resample("ME").prod() - 1
    base = (r[["SPY", "GLD", "SHY"]].mean(axis=1)).where(r[["SPY", "GLD", "SHY"]].notna().all(axis=1))
    out = {"prices_sha256": digest, "funds": {}}
    for f in FUNDS:
        x = r[f].dropna()
        spy = r.SPY.reindex(x.index)
        down = spy < 0
        res = {"standalone": stats(x, rf), "spy_same_months": stats(spy, rf),
               "corr_spy": float(x.corr(spy)), "corr_spy_down_months": float(x[down].corr(spy[down])),
               "beta_spy": float(np.cov(x, spy.fillna(0))[0, 1] / spy.var()),
               "crises": {k: {"fund": window_return(x, a, b), "spy": window_return(r.SPY, a, b)} for k, (a, b) in CRISES.items()
                          if pd.Timestamp(a) >= x.index[0]}}
        mix = 0.8 * base + 0.2 * x
        ov = pd.concat([base, mix], axis=1, keys=["base", "mix"]).dropna()
        halves = {}
        for lab, (a, b) in {"full": (ov.index[0], ov.index[-1]), "first_half": (ov.index[0], ov.index[len(ov) // 2 - 1]),
                            "second_half": (ov.index[len(ov) // 2], ov.index[-1])}.items():
            sub = ov[(ov.index >= a) & (ov.index <= b)]
            halves[lab] = {"base": stats(sub["base"], rf), "with_20pct": stats(sub["mix"], rf)}
        res["portfolio_vs_spy_gld_shy"] = halves
        res["sharpe_diff_bootstrap_p"] = boot_sharpe_diff(ov["mix"], ov["base"], rf, rng)
        out["funds"][f] = res

    m = out["funds"]["MERFX"]
    crisis_ok = sum(1 for c in m["crises"].values() if c["fund"] >= 0 or c["fund"] > 0.5 * c["spy"])
    port = m["portfolio_vs_spy_gld_shy"]
    def better(h): return h["with_20pct"]["sharpe"] > h["base"]["sharpe"] and h["with_20pct"]["max_dd"] >= h["base"]["max_dd"]
    crit = {"corr_below_0.5": m["corr_spy"] < 0.5,
            "crises_ok_5_of_7": crisis_ok >= 5,
            "portfolio_better_full_and_both_halves": all(better(port[k]) for k in ("full", "first_half", "second_half")),
            "arbfx_and_mna_agree": all(out["funds"][f]["portfolio_vs_spy_gld_shy"]["full"]["with_20pct"]["sharpe"]
                                       > out["funds"][f]["portfolio_vs_spy_gld_shy"]["full"]["base"]["sharpe"] for f in ("ARBFX", "MNA"))}
    out["criteria"], out["crises_ok_count"], out["passes"] = crit, crisis_ok, all(crit.values())

    for f, res in out["funds"].items():
        s, q = res["standalone"], res["spy_same_months"]
        print(f"\n== {f} from {s['start']}: CAGR {s['cagr']:+.2%} vol {s['vol']:.1%} Sharpe {s['sharpe']:.2f} maxDD {s['max_dd']:+.1%} | "
              f"SPY same months: CAGR {q['cagr']:+.2%} Sharpe {q['sharpe']:.2f} maxDD {q['max_dd']:+.1%}")
        print(f"   corr SPY {res['corr_spy']:+.2f} (down months {res['corr_spy_down_months']:+.2f}), beta {res['beta_spy']:+.2f}")
        print("   crises (fund / SPY): " + "; ".join(f"{k} {c['fund']:+.1%}/{c['spy']:+.1%}" for k, c in res["crises"].items()))
        for lab, h in res["portfolio_vs_spy_gld_shy"].items():
            b, w = h["base"], h["with_20pct"]
            print(f"   {lab:11s} SPY/GLD/SHY: Sharpe {b['sharpe']:.2f} maxDD {b['max_dd']:+.1%} CAGR {b['cagr']:+.2%} | "
                  f"+20% {f}: Sharpe {w['sharpe']:.2f} maxDD {w['max_dd']:+.1%} CAGR {w['cagr']:+.2%}")
        print(f"   Sharpe-difference bootstrap p {res['sharpe_diff_bootstrap_p']:.3f} (reported, not required)")
    for k, v in crit.items():
        print(f"[{'PASS' if v else 'FAIL'}] {k}")
    print(f"A30 stage 1 {'PASSES' if out['passes'] else 'FAILS'} (crises ok {crisis_ok} of {len(m['crises'])})")
    (OUTPUT / "result.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
