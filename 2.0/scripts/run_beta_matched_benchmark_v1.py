#!/usr/bin/env python3
"""S20 -- does any dashboard book beat a passive portfolio with the same market exposure?

Pre-registered in docs/S20_BETA_MATCHED_BENCHMARK_PREREGISTRATION_V1.md, committed before this
file computed anything. Unlevered books only. Betas are expanding-window and past-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.systematic_trader.return_conventions import detect_convention, to_week_ending  # noqa: E402

PAYLOAD = ROOT / "dashboard/public/return-first-dashboard.json"
ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
EW = ROOT / "evidence/full_history_out_of_sample_v1"
OUT = ROOT / "evidence/beta_matched_benchmark_v1"

BREAK = pd.Timestamp("2025-04-04")
MIN_WEEKS, BLOCK, DRAWS, SEED = 26, 8, 10_000, 20261006
BONFERRONI = 0.05 / 10
NULLS = {"N1_SPY": ["SPY"], "N2_XLK_XLE": ["XLK", "XLE"]}
DASHBOARD_BOOKS = {
    "sector_aware_ensemble": "sec-sector-aware-signal-ensemble-v1",
    "cash_conversion_b20_dynamic": "sec-cash-conversion-breadth20-dynamic-v1",
    "growth_survivorship": "sec-growth-survivorship-aware-v1",
    "etf_60_40_return_first": "candidate-return-first-60-40-forward-v1",
}


def etf_returns() -> pd.DataFrame:
    px = pd.read_csv(ETF, index_col=0, parse_dates=True)
    px.index = pd.to_datetime(px.index, utc=True).tz_localize(None)
    return px.apply(pd.to_numeric, errors="coerce").pct_change().iloc[1:]


def books(spy: pd.Series) -> dict[str, pd.Series]:
    payload = json.load(open(PAYLOAD))["strategies"]
    by_id = {s["strategy"]["id"]: s["records"] for s in payload}
    raw = {}
    for name, sid in DASHBOARD_BOOKS.items():
        frame = pd.DataFrame(by_id[sid])
        raw[name] = pd.Series(frame.netReturn.values,
                              index=pd.to_datetime(frame.date)).astype(float)
    p = pd.read_csv(ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv")
    raw["residual_controlled_1x"] = pd.Series(
        p.net_return.values,
        index=pd.to_datetime(p.Date, utc=True).dt.tz_localize(None).dt.normalize())
    aligned = {}
    for name, r in raw.items():
        r = r[r.index >= r[r != 0].index.min()]       # drop the cash-only warm-up weeks
        convention, beta, r2 = detect_convention(r, spy)
        aligned[name] = to_week_ending(r, convention).dropna()
        print(f"  {name:30s} {convention:12s} beta {beta:.2f} R2 {r2:.2f} weeks {len(r)}")
    return aligned


def past_only_alpha(book: pd.Series, etf: pd.DataFrame, factors: list[str]) -> pd.DataFrame:
    frame = pd.concat({"b": book, "rf": etf["BIL"], **{f: etf[f] for f in factors}},
                      axis=1).dropna()
    y = (frame.b - frame.rf).values
    X = np.column_stack([frame[f] - frame.rf for f in factors] + [np.ones(len(frame))])
    rows = []
    for t in range(MIN_WEEKS, len(frame)):
        coef, *_ = np.linalg.lstsq(X[:t], y[:t], rcond=None)
        beta = coef[:-1]
        exposure = float(X[t, :-1] @ beta)
        rows.append({"date": frame.index[t], "book": frame.b.iloc[t],
                     "matched": frame.rf.iloc[t] + exposure,
                     "alpha": y[t] - exposure, "beta_sum": float(beta.sum())})
    return pd.DataFrame(rows).set_index("date")


def block_p(alpha: np.ndarray, rng: np.random.Generator) -> float:
    """One-sided p for mean > 0, stationary bootstrap of the recentred series."""
    n, centred, observed = len(alpha), alpha - alpha.mean(), alpha.mean()
    hits = 0
    for _ in range(DRAWS):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(n)
        jumps = rng.random(n) < 1.0 / BLOCK
        starts = rng.integers(n, size=n)
        for i in range(1, n):
            idx[i] = starts[i] if jumps[i] else (idx[i - 1] + 1) % n
        hits += centred[idx].mean() >= observed
    return (hits + 1) / (DRAWS + 1)


def cagr(r: pd.Series) -> float:
    return float((1 + r).prod() ** (52 / len(r)) - 1) if len(r) else float("nan")


def sharpe(r: pd.Series) -> float:
    return float(r.mean() / r.std() * np.sqrt(52)) if len(r) > 2 else float("nan")


def maxdd(r: pd.Series) -> float:
    w = (1 + r).cumprod()
    return float((w / w.cummax() - 1).min())


def summarise(path: pd.DataFrame) -> dict:
    return {"weeks": len(path), "book_cagr": cagr(path.book), "matched_cagr": cagr(path.matched),
            "book_sharpe": sharpe(path.book), "matched_sharpe": sharpe(path.matched),
            "book_maxdd": maxdd(path.book), "matched_maxdd": maxdd(path.matched),
            "alpha_annual": float(path.alpha.mean() * 52),
            "mean_beta_sum": float(path.beta_sum.mean())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    etf = etf_returns()
    print("alignment:")
    series = books(etf["SPY"])
    rng = np.random.default_rng(SEED)
    rows = []
    for name, r in series.items():
        for null, factors in NULLS.items():
            path = past_only_alpha(r, etf, factors)
            path.to_csv(OUT / f"path__{name}__{null}.csv")
            windows = {"full": path, "pre_break": path[path.index < BREAK],
                       "post_break": path[path.index >= BREAK]}
            if name == "etf_60_40_return_first":
                windows["2008_2009"] = path["2008-01-01":"2009-12-31"]
                windows["2020"] = path["2020-01-01":"2020-12-31"]
            p = block_p(path.alpha.values, rng)
            for w, sub in windows.items():
                if len(sub) < 10:
                    continue
                rows.append({"book": name, "null": null, "window": w, **summarise(sub),
                             "p_one_sided": p if w == "full" else None})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "results.csv", index=False)

    verdicts = {}
    for (name, null), g in table.groupby(["book", "null"]):
        g = g.set_index("window")
        full, pre, post = (g.loc[w, "alpha_annual"] if w in g.index else float("nan")
                           for w in ("full", "pre_break", "post_break"))
        p = g.loc["full", "p_one_sided"]
        verdicts[f"{name}|{null}"] = {
            "alpha_full": full, "p": p, "alpha_pre": pre, "alpha_post": post,
            "PASS": bool(full > 0 and p < BONFERRONI and pre > 0 and post > 0)}

    # Secondary, not in the pass rule: equal-weight universe paths, common window only.
    secondary = {}
    for ew in ("narrow", "broad"):
        e = pd.read_csv(EW / f"path__equal_weight_{ew}__base.csv")
        e = pd.Series(e.net_return.values, index=pd.to_datetime(e.Date, utc=True)
                      .dt.tz_localize(None).dt.normalize())
        conv, _, _ = detect_convention(e, etf["SPY"])
        e = to_week_ending(e, conv).dropna()
        for name, r in series.items():
            if name == "etf_60_40_return_first":
                continue
            j = pd.concat({"b": r, "e": e}, axis=1).dropna()
            secondary[f"{name}|ew_{ew}"] = {
                "weeks": len(j), "start": str(j.index.min().date()),
                "book_cagr": cagr(j.b), "ew_cagr": cagr(j.e),
                "book_sharpe": sharpe(j.b), "ew_sharpe": sharpe(j.e)}

    result = {"preregistration": "docs/S20_BETA_MATCHED_BENCHMARK_PREREGISTRATION_V1.md",
              "trials": 10, "bonferroni": BONFERRONI, "verdicts": verdicts,
              "secondary_equal_weight": secondary,
              "passes": sum(v["PASS"] for v in verdicts.values())}
    json.dump(result, open(OUT / "result.json", "w"), indent=2, default=float)

    pd.set_option("display.width", 220)
    show = table.copy()
    for c in ("book_cagr", "matched_cagr", "book_maxdd", "matched_maxdd", "alpha_annual"):
        show[c] = (show[c] * 100).round(1)
    for c in ("book_sharpe", "matched_sharpe", "mean_beta_sum"):
        show[c] = show[c].round(2)
    print(show.to_string(index=False))
    print("\nverdicts:")
    for k, v in verdicts.items():
        print(f"  {k:45s} alpha {v['alpha_full']*100:+6.1f}%  p {v['p']:.4f}  "
              f"pre {v['alpha_pre']*100:+6.1f}%  post {v['alpha_post']*100:+6.1f}%  "
              f"{'PASS' if v['PASS'] else 'fail'}")
    print("\nsecondary (equal-weight universe, common window):")
    for k, v in secondary.items():
        print(f"  {k:45s} from {v['start']} book {v['book_cagr']*100:5.1f}% (Sh {v['book_sharpe']:.2f})"
              f"  ew {v['ew_cagr']*100:5.1f}% (Sh {v['ew_sharpe']:.2f})")
    print(f"\nPASSES: {result['passes']} of 10")


if __name__ == "__main__":
    main()
