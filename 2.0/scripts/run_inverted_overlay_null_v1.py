"""Is 'risk-off when breadth is HIGH' skill, or would ANY de-risking schedule
with the same duty cycle have scored the same on this sample path?

The null is a moving-block shuffle of the risk-off schedule itself: same number
of risk-off weeks, same clustering, no relationship to breadth. If the real
schedule does not beat that, the breadth signal contributes nothing and the
+0.134 mean timing gain is a property of the sample path.

Returns and drawdowns are reported next to Sharpe deliberately. A rule that
de-risks during strong breadth will shed return in a bull-dominated sample, and
the owner's criteria weight recent return at 45%.
"""
import json, math, numpy as np, pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"evidence"/"inverted_overlay_null_v1"; OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20260902); NBOOT, BLOCK = 2000, 8

P = pd.read_csv(ROOT/"data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz", index_col=0)
P.index = pd.to_datetime(P.index)
R = P.pct_change().replace([np.inf,-np.inf], np.nan); live = P.notna()
W = live.div(live.sum(axis=1).replace(0,np.nan), axis=0).fillna(0.0)
uni = (W.shift(1).fillna(0.0)*R.fillna(0.0)).sum(axis=1)
above = (P > P.rolling(26, min_periods=13).mean()).where(live)
breadth = above.sum(axis=1)/live.sum(axis=1).replace(0,np.nan)

d = json.loads((ROOT/"dashboard/public/return-first-dashboard.json").read_text())
series = {"equal_weight_universe": uni.iloc[52:]}
for it in d["strategies"]:
    idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in it["records"]])
    g = pd.Series([float(r["grossReturn"]) for r in it["records"]], index=idx)
    ex = max(1.0, max(sum(abs(h["weight"]) for h in r["holdings"]
                          if not h["symbol"].startswith("cash")) for r in it["records"]))
    series[it["strategy"]["shortName"]] = g/ex

sharpe = lambda v: v.mean()/v.std(ddof=1)*math.sqrt(52)
def cagr(v): return (1+v).prod()**(52/len(v)) - 1
def mdd(v):
    c = (1+v).cumprod(); return float((c/c.cummax()-1).min())
def gain(base, flag):
    sc = pd.Series(np.where(flag, 0.5, 1.0), index=base.index)
    return sharpe((base*sc).dropna()) - sharpe((base*sc.mean()).dropna())

def shuffle_blocks(flag):
    n = len(flag); nb = int(np.ceil(n/BLOCK))
    starts = RNG.choice(np.arange(0, max(1, n-BLOCK+1)), size=nb)
    return np.concatenate([flag[i:i+BLOCK] for i in starts])[:n]

print(f"{'series':<26}{'CAGR base':>11}{'CAGR ovl':>10}{'maxDD base':>12}{'maxDD ovl':>11}"
      f"{'timing':>9}{'p vs random':>13}")
rows = []
for name, base in series.items():
    b = breadth.reindex(base.index).ffill().shift(1)
    flag = (b > 0.60).fillna(False).to_numpy()
    obs = gain(base, flag)
    null = np.array([gain(base, shuffle_blocks(flag)) for _ in range(NBOOT)])
    p = float(((null >= obs).sum()+1)/(NBOOT+1))
    sc = pd.Series(np.where(flag, 0.5, 1.0), index=base.index)
    ov = (base*sc).dropna()
    rows.append({"series": name, "cagr_base": cagr(base), "cagr_overlay": cagr(ov),
                 "mdd_base": mdd(base), "mdd_overlay": mdd(ov),
                 "timing_gain": obs, "p_vs_random_schedule": p})
    print(f"{name:<26}{cagr(base):>10.1%}{cagr(ov):>10.1%}{mdd(base):>12.1%}{mdd(ov):>11.1%}"
          f"{obs:>+9.3f}{p:>13.4f}")

df = pd.DataFrame(rows); df.to_csv(OUT/"result.csv", index=False)
np_ = int((df["p_vs_random_schedule"] < 0.05).sum())
print(f"\n  beats a random schedule of matched duty cycle : {np_} / {len(df)} series")
print(f"  mean CAGR given up                            : {(df['cagr_overlay']-df['cagr_base']).mean():+.1%}")
print(f"  mean drawdown change                          : {(df['mdd_overlay']-df['mdd_base']).mean():+.1%}")
verdict = ("breadth adds timing information beyond a random schedule" if np_ >= 5 else
           "the schedule is not distinguishable from random de-risking; breadth adds nothing")
print(f"\n  VERDICT: {verdict}")
json.dump({"series_beating_random": np_, "n": len(df), "verdict": verdict,
           "mean_cagr_delta": float((df['cagr_overlay']-df['cagr_base']).mean()),
           "mean_mdd_delta": float((df['mdd_overlay']-df['mdd_base']).mean())},
          open(OUT/"final_result.json","w"), indent=2)
