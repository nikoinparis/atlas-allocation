#!/usr/bin/env python3
"""Is 1.0's phase5_fragility_guard a better strategy than the best 2.0 book?

No search: every strategy compared here is already fixed. phase5 is rebuilt on the causal GGG
base (Step 68's lookahead fix, Step 59's bundle) using the wrapper rule Step 65 reproduced
exactly: offense ETFs scaled by the saved weekly offense_scale, residual to BIL. The saved scale
ends 2026-04-10; after that the scale is 1.0 and the strategy is plain causal GGG.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader.ggg_independent import next_week_returns, portfolio_path, run_from_artifacts  # noqa: E402
from src.systematic_trader.return_conventions import detect_convention, to_week_ending  # noqa: E402

BUNDLE = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a"
SCALE = ROOT / "evidence/v1_wrapper_equivalence_batch_41/scale_history.csv"
LINEAGE = ROOT / "config/v1_wrapper_equivalence_lineage_v1.json"
ETF = ROOT / "data/etf_weekly_panel_v1/weekly_adjusted_prices.csv.gz"
OUT = ROOT / "evidence/v1_phase5_vs_2_0_v1"
BREAK = "2025-04-04"


def bil_normalize(w: pd.DataFrame) -> pd.DataFrame:
    w = w.clip(lower=0.0).copy()
    if "BIL" not in w:
        w["BIL"] = 0.0
    risky = [c for c in w if c != "BIL"]
    total = w[risky].sum(axis=1)
    over = total > 1.0
    w.loc[over, risky] = w.loc[over, risky].div(total[over], axis=0)
    w["BIL"] = (1.0 - w[risky].sum(axis=1)).clip(lower=0.0)
    return w


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    if len(r) < 4:
        return {"weeks": len(r)}
    w = (1 + r).cumprod()
    return {"weeks": len(r), "cagr": float(w.iloc[-1] ** (52 / len(r)) - 1),
            "total": float(w.iloc[-1] - 1),
            "sharpe": float(r.mean() / r.std() * np.sqrt(52)) if r.std() else float("nan"),
            "maxdd": float((w / w.cummax() - 1).min())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    px = pd.read_csv(ETF, index_col=0, parse_dates=True)
    px.index = pd.to_datetime(px.index, utc=True).tz_localize(None).normalize()
    etf = px.apply(pd.to_numeric, errors="coerce").pct_change()
    spy = etf["SPY"]

    result = run_from_artifacts(BUNDLE, causal_training=True, legacy_terminal_rebalance=False)
    base_w = result.stages["final_etf_weights"]
    prices = pd.read_csv(BUNDLE / "data/01_data_hub/weekly_prices.csv", index_col=0, parse_dates=True)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    forward = next_week_returns(prices.apply(pd.to_numeric, errors="coerce"))
    scale = pd.read_csv(SCALE, index_col=0, parse_dates=True)["offense_scale"].reindex(base_w.index).fillna(1.0)
    offense = [a for a in json.load(open(LINEAGE))["independent_reconstruction"]["offense_assets"] if a in base_w]
    p5_w = base_w.copy()
    p5_w[offense] = p5_w[offense].mul(scale, axis=0)
    p5_w = bil_normalize(p5_w)

    raw = {}
    for name, w in (("1.0_phase5_fragility_guard", p5_w), ("1.0_ggg_base_causal", base_w)):
        for cost in (10, 50):
            raw[f"{name}@{cost}bps"] = portfolio_path(w, forward, float(cost))["net_return"].dropna()
    series = {}
    for name, r in raw.items():
        conv, beta, r2 = detect_convention(r, spy)
        series[name] = to_week_ending(r, conv).dropna()
        print(f"  {name:38s} {conv:12s} beta {beta:.2f} R2 {r2:.2f} {r.index.min().date()}..{r.index.max().date()}")

    # 2.0 headline book, unlevered: Step 290 out-of-sample 2013-2022, then in-sample 2023-.
    def load(path: Path) -> pd.Series:
        f = pd.read_csv(path)
        s = pd.Series(f.net_return.values, index=pd.to_datetime(f.Date, utc=True).dt.tz_localize(None).dt.normalize())
        s = s[s.index >= s[s != 0].index.min()]
        conv, _, _ = detect_convention(s, spy)
        return to_week_ending(s, conv).dropna()
    oos = load(ROOT / "evidence/composites_out_of_sample_v1/path__residual_composite__50bps.csv")
    ins = load(ROOT / "evidence/sec_residual_controlled_sleeve_v1/candidate_path.csv")
    book = pd.concat([oos[:"2022-12-31"], ins["2023-01-01":]]).sort_index()
    series["2.0_residual_book@50bps"] = book[~book.index.duplicated()]
    series["SPY"] = spy.dropna()
    thirds = etf[["SPY", "GLD", "SHY"]].dropna()
    series["SPY_GLD_SHY_static"] = thirds.mean(axis=1)

    end = min(series["1.0_phase5_fragility_guard@50bps"].index.max(), spy.index.max())
    windows = {
        "full 2005-": ("2005-01-01", end), "GFC 2007-10..2009-03": ("2007-10-01", "2009-03-31"),
        "2011 Aug-Sep": ("2011-07-22", "2011-10-07"), "2018 Q4": ("2018-10-01", "2018-12-31"),
        "COVID 2020-02..03": ("2020-02-14", "2020-03-27"), "2022": ("2022-01-01", "2022-12-31"),
        "2013-2022": ("2013-04-05", "2022-12-31"), "2023..2025-04-03": ("2023-01-01", "2025-04-03"),
        "2025-04-04..": (BREAK, end), "common 2013-04..": ("2013-04-05", end),
    }
    rows = []
    for name, s in series.items():
        for w, (a, b) in windows.items():
            rows.append({"series": name, "window": w, **stats(s[a:b])})
    table = pd.DataFrame(rows)
    table.to_csv(OUT / "comparison.csv", index=False)

    # Weeks when SPY lost big: SPY's worst 5% of weeks, 2005-.
    s = spy["2005-01-01":end].dropna()
    bad = s[s <= s.quantile(0.05)].index
    down = {name: float(x.reindex(bad).mean()) for name, x in series.items()}
    down_n = {name: int(x.reindex(bad).notna().sum()) for name, x in series.items()}

    # Beta-matched alpha vs SPY (S20 method, expanding past-only beta, rf = BIL).
    alpha = {}
    for name in ("1.0_phase5_fragility_guard@50bps", "2.0_residual_book@50bps"):
        f = pd.concat({"b": series[name], "m": spy, "rf": etf["BIL"]}, axis=1, sort=True).dropna()
        y, x = (f.b - f.rf).values, (f.m - f.rf).values
        a = [y[t] - np.polyfit(x[:t], y[:t], 1)[0] * x[t] for t in range(26, len(f))]
        a = pd.Series(a, index=f.index[26:])
        alpha[name] = {w: float(a[lo:hi].mean() * 52) for w, (lo, hi) in
                       (("full", ("2000", end)), ("2013-2022", ("2013-04-05", "2022-12-31")),
                        ("2023..2025-04-03", ("2023-01-01", "2025-04-03")), ("2025-04-04..", (BREAK, end)))}

    json.dump({"bundle": str(BUNDLE.name), "scale_ends": "2026-04-10", "end": str(end.date()),
               "spy_worst_5pct_weeks_mean": down, "spy_worst_5pct_weeks_n": down_n,
               "beta_matched_alpha_vs_spy": alpha}, open(OUT / "result.json", "w"), indent=2)
    pd.set_option("display.width", 250)
    show = table.copy()
    for c in ("cagr", "total", "maxdd"):
        show[c] = (show[c] * 100).round(1)
    show["sharpe"] = show.sharpe.round(2)
    print(show.pivot_table(index="window", columns="series", values=["cagr"], sort=False).to_string())
    print(show.pivot_table(index="window", columns="series", values=["sharpe"], sort=False).to_string())
    print(show.pivot_table(index="window", columns="series", values=["maxdd"], sort=False).to_string())
    print("\nSPY worst 5% weeks, mean weekly return:", {k: f"{v*100:+.2f}% (n={down_n[k]})" for k, v in down.items()})
    print("beta-matched alpha vs SPY:", json.dumps(alpha, indent=1))


if __name__ == "__main__":
    main()
