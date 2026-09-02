"""Follow-up to the meta-labeling precondition: FDR, sign consistency, and a
symmetric overlay test.

Bonferroni assumes independent tests. These 77 are not: the features are mutually
correlated and the seven series share holdings (project effective breadth ~1.15),
so Bonferroni over-corrects. FDR is the pre-authorized alternative named in
CLAUDE.md, not a post-hoc relaxation chosen because the first answer was
unwelcome, so both are reported.

The overlay test is deliberately SYMMETRIC. Both directions of each signal are
scored against the same null (constant exposure at matched average), so the
result cannot be an artifact of picking the direction after seeing the loser.
"""
import json, math, numpy as np, pandas as pd
from pathlib import Path
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"evidence"/"metalabel_precondition_v1"
df = pd.read_csv(OUT/"feature_ic.csv")

# ---- 1. Benjamini-Hochberg FDR ------------------------------------------------
d = df.sort_values("p").reset_index(drop=True); m = len(d)
d["bh_crit"] = 0.05 * (d.index + 1) / m
below = np.where(d["p"] <= d["bh_crit"])[0]
kmax = below.max() if len(below) else -1
d["fdr_pass"] = d.index <= kmax
print(f"FDR (Benjamini-Hochberg, q=0.05): {int(d['fdr_pass'].sum())} / {m} features pass")
print(f"Bonferroni, cumulative trials   : 0 / {m}   (reported for contrast)\n")

# ---- 2. sign consistency across the seven series ------------------------------
print("Sign consistency per feature across all 7 series:")
print(f"  {'feature':<16}{'+':>4}{'-':>4}{'mean IC':>10}{'sign-test p':>13}   (series are correlated:")
piv = df.pivot(index="feature", columns="series", values="ic")
cons = []
for f in piv.index:
    v = piv.loc[f].dropna(); pos, neg = int((v>0).sum()), int((v<0).sum()); n = pos+neg
    p = stats.binomtest(max(pos,neg), n, 0.5).pvalue if n else 1.0
    cons.append({"feature": f, "pos": pos, "neg": neg, "mean_ic": v.mean(), "sign_p": p})
    print(f"  {f:<16}{pos:>4}{neg:>4}{v.mean():>+10.3f}{p:>13.4f}")
print("   this p is descriptive only, NOT independent evidence)\n")

# ---- 3. symmetric overlay test ------------------------------------------------
P = pd.read_csv(ROOT/"data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz", index_col=0)
P.index = pd.to_datetime(P.index)
R = P.pct_change().replace([np.inf,-np.inf], np.nan); live = P.notna()
W = live.div(live.sum(axis=1).replace(0,np.nan), axis=0).fillna(0.0)
uni = (W.shift(1).fillna(0.0)*R.fillna(0.0)).sum(axis=1)
above = (P > P.rolling(26, min_periods=13).mean()).where(live)
breadth = (above.sum(axis=1)/live.sum(axis=1).replace(0,np.nan))

d2 = json.loads((ROOT/"dashboard/public/return-first-dashboard.json").read_text())
series = {"equal_weight_universe": uni.iloc[52:]}
for it in d2["strategies"]:
    idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in it["records"]])
    g = pd.Series([float(r["grossReturn"]) for r in it["records"]], index=idx)
    ex = max(1.0, max(sum(abs(h["weight"]) for h in r["holdings"]
                          if not h["symbol"].startswith("cash")) for r in it["records"]))
    series[it["strategy"]["shortName"]] = g/ex

sharpe = lambda v: v.mean()/v.std(ddof=1)*math.sqrt(52)
print("Symmetric overlay test. 'timing gain' = Sharpe(timed) - Sharpe(constant at same avg exposure).")
print("Positive means the TIMING earned something beyond simply holding less.\n")
print(f"  {'series':<26}{'risk-off when LOW':>19}{'risk-off when HIGH':>20}")
gl, gh = [], []
for name, base in series.items():
    b = breadth.reindex(base.index).ffill().shift(1)      # causal
    row = []
    for lowside in (True, False):
        sc = pd.Series(np.where((b < 0.40) if lowside else (b > 0.60), 0.5, 1.0), index=base.index)
        ov = (base*sc).dropna(); const = (base*sc.mean()).dropna()
        row.append(sharpe(ov) - sharpe(const))
    gl.append(row[0]); gh.append(row[1])
    print(f"  {name:<26}{row[0]:>+19.3f}{row[1]:>+20.3f}")
print(f"\n  {'MEAN':<26}{np.mean(gl):>+19.3f}{np.mean(gh):>+20.3f}")
print("\n  Neither direction is a free lunch; a positive mean is a hypothesis, not a result.")
json.dump({"fdr_pass": int(d["fdr_pass"].sum()), "bonferroni_cum_pass": 0,
           "sign_consistency": cons,
           "mean_timing_gain_riskoff_low": float(np.mean(gl)),
           "mean_timing_gain_riskoff_high": float(np.mean(gh))},
          open(OUT/"signstructure_result.json","w"), indent=2, default=float)
