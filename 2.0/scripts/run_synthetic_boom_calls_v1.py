#!/usr/bin/env python3
"""P4 feasibility screen: would call options on boom leaders beat holding the shares?

Pre-registered in config/synthetic_boom_calls_registry_v1.json. Options are PRICED BY MODEL
(Black-Scholes at markup x trailing realised volatility), because real historical option prices are
paid data. This decides whether buying that data is worth it; it is not evidence on its own.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_tnic_peer_gap_screen_v1 as a19  # noqa: E402

REGISTRY = ROOT / "config/synthetic_boom_calls_registry_v1.json"
ALARMS = ROOT / "evidence/wave_anatomy_v1/detector_events.csv"
FF = ROOT / "data/fama_french_factor_vintages/20261010T173855Z-ff5-mom-daily/F-F_Research_Data_5_Factors_2x3_daily.csv"
CATALOGUE = ROOT / "data/broad_full_history_price_vintages/20261010T135148Z-broad-full-history-v1/history_catalogue.csv"
OUTPUT = ROOT / "evidence/synthetic_boom_calls_v1"
HORIZONS = {"H6": 126, "H12": 252}
MARKUPS, SPREADS, STRIKE, LEADERS = [1.0, 1.25, 1.5], [0.05, 0.10], 1.10, 3
HALVES = {"2012-2018": ("2012-01-01", "2018-12-31"), "2019-2026": ("2019-01-01", "2026-12-31")}


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_call(s: float, k: float, t: float, r: float, vol: float) -> tuple[float, float]:
    d1 = (math.log(s / k) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    d2 = d1 - vol * math.sqrt(t)
    return s * norm_cdf(d1) - k * math.exp(-r * t) * norm_cdf(d2), norm_cdf(d1)


def load_rf(index: pd.DatetimeIndex) -> pd.Series:
    rows = []
    for line in FF.read_text().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 7 and parts[0].isdigit() and len(parts[0]) == 8:
            rows.append((pd.Timestamp(parts[0]), float(parts[6]) / 100.0))
    rf = pd.Series(dict(rows))
    return rf.reindex(index).ffill().fillna(0.0)


def stats(x: pd.Series) -> dict:
    x = x.dropna()
    if len(x) < 5:
        return {"n": int(len(x))}
    return {"n": int(len(x)), "mean": float(x.mean()), "median": float(x.median()), "share_positive": float((x > 0).mean()),
            "p10": float(x.quantile(0.10)), "worst": float(x.min()), "mean_over_std": float(x.mean() / x.std(ddof=1))}


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_any_result_existed"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prices = a19.load_daily()
    sic = a19.load_sic()
    dollar = a19.load_dollar_volume(prices.columns).reindex(prices.index).ffill()
    rf = load_rf(prices.index)
    tick = pd.read_csv(CATALOGUE, dtype={"cik10": str}).sort_values("rows", ascending=False) \
        .drop_duplicates("cik10").set_index("cik10").symbol
    dates, cols = prices.index, np.array(prices.columns)
    px, dv = prices.to_numpy(), dollar.to_numpy()
    logret = np.log(px[1:] / px[:-1])
    alarms = pd.read_csv(ALARMS, parse_dates=["month"], dtype={"sic3": str})
    alarms["sic3"] = alarms.sic3.str.zfill(3)

    rows = []
    for a in alarms.itertuples():
        t = dates.searchsorted(a.month, side="right") - 1        # last trading day of the firing month
        if t < 130:
            continue
        groups = a19.sic_as_of(sic, dates[t]).reindex(cols).str[:3].to_numpy(dtype=object)
        liquid = (px[t] >= 5) & (dv[t] >= 5e6) & (groups == a.sic3)
        idx = np.flatnonzero(liquid & np.isfinite(px[t - 126]))
        if len(idx) == 0:
            continue
        r6 = px[t, idx] / px[t - 126, idx] - 1.0
        leaders = idx[np.argsort(-r6)][:LEADERS]
        r_annual = float(rf.iloc[t - 20:t + 1].mean() * 252)
        for h_name, h in HORIZONS.items():
            if t + h >= len(dates):
                continue
            rf_h = float(np.prod(1 + rf.iloc[t + 1:t + h + 1].to_numpy()) - 1)
            share, calls = [], {(m, s): [] for m in MARKUPS for s in SPREADS}
            for j in leaders:
                s0, st = px[t, j], px[t + h, j]
                if not (np.isfinite(s0) and np.isfinite(st)):
                    continue
                vol = float(np.nanstd(logret[t - 63:t, j], ddof=1) * math.sqrt(252))
                if not vol > 0:
                    continue
                share.append(st / s0 - 1.0)
                k, T = STRIKE * s0, h / 252.0
                for m in MARKUPS:
                    value, delta = bs_call(s0, k, T, r_annual, m * vol)
                    for sp in SPREADS:
                        premium = value * (1 + sp)
                        n = 1.0 / (delta * s0)                    # same starting exposure as $1 of shares
                        spent = n * premium
                        calls[(m, sp)].append((1.0 - spent) * (1 + rf_h) + n * max(st - k, 0.0) - 1.0)
            if not share:
                continue
            row = {"month": a.month, "sic3": a.sic3, "horizon": h_name, "leaders": "|".join(tick.get(cols[j], cols[j]) for j in leaders),
                   "shares": float(np.mean(share))}
            for (m, sp), v in calls.items():
                row[f"calls_m{m}_s{int(sp * 100)}"] = float(np.mean(v)) if v else np.nan
            rows.append(row)
    ev = pd.DataFrame(rows)
    ev.to_csv(OUTPUT / "events.csv", index=False)

    out = {}
    print("EVENT-LEVEL RETURNS (each firing: 3 leaders, equal weight). Calls priced by MODEL, not market data.\n")
    for h_name in HORIZONS:
        for half, (a, b) in HALVES.items():
            sub = ev[(ev.horizon == h_name) & (ev.month >= a) & (ev.month <= b)]
            false_start, wave = sub.shares < -0.20, sub.shares > 0.50
            block = {"shares": {**stats(sub.shares), "false_start_mean": float(sub.shares[false_start].mean()),
                                "wave_mean": float(sub.shares[wave].mean()),
                                "false_starts": int(false_start.sum()), "waves": int(wave.sum())}}
            for m in MARKUPS:
                for sp in SPREADS:
                    col = f"calls_m{m}_s{int(sp * 100)}"
                    block[col] = {**stats(sub[col]), "false_start_mean": float(sub[col][false_start].mean()),
                                  "wave_mean": float(sub[col][wave].mean())}
            out[f"{h_name} {half}"] = block
            print(f"== {h_name} {half}: {len(sub)} firings, {int(false_start.sum())} false starts (shares < -20%), "
                  f"{int(wave.sum())} waves (shares > +50%)")
            for name, s in block.items():
                if name.endswith("s10"):
                    continue
                print(f"   {name:16s} mean {s.get('mean', float('nan')):+7.1%} median {s.get('median', float('nan')):+7.1%} "
                      f"positive {s.get('share_positive', float('nan')):4.0%} p10 {s.get('p10', float('nan')):+7.1%} "
                      f"mean/std {s.get('mean_over_std', float('nan')):+.2f} | false-start mean {s['false_start_mean']:+7.1%} "
                      f"| wave mean {s['wave_mean']:+7.1%}")
    def rule(markup):
        col = f"calls_m{markup}_s5"
        ok = True
        for half in HALVES:
            blk = out[f"H12 {half}"]
            ok &= blk[col]["mean_over_std"] > blk["shares"]["mean_over_std"]
            ok &= blk[col]["false_start_mean"] >= 0.5 * blk["shares"]["false_start_mean"]
        return bool(ok)
    verdict = ("RECOMMEND buying real options data" if rule(1.25) else
               "DO NOT recommend buying options data" if not rule(1.0) else "INCONCLUSIVE (passes only at markup 1.0)")
    print(f"\ndecision rule: markup 1.25 passes {rule(1.25)}, markup 1.0 passes {rule(1.0)} -> {verdict}")
    (OUTPUT / "result.json").write_text(json.dumps({"registry": str(REGISTRY.relative_to(ROOT)), "results": out,
                                                    "rule_markup_1_25": rule(1.25), "rule_markup_1_0": rule(1.0),
                                                    "verdict": verdict, "options_priced_by_model": True,
                                                    "live_trading_enabled": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
