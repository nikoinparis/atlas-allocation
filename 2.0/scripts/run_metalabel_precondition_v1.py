"""Meta-labeling precondition test (Lopez de Prado, AFML ch. 3).

Meta-labeling only helps if a strategy's WHEN-IT-WORKS is predictable from state
known beforehand. This does not build a meta-model. It asks the cheaper question:
is there any conditional structure in the strategies' returns for a meta-model to
find? If every feature is at zero IC after correction, the build is not worth a week.

Causality: every feature is computed from data up to t-1 and matched to the return
realised at t. Significance: moving-block bootstrap, then Bonferroni over the full
trial count of this run stacked on the project's cumulative count.
"""
import json, math, numpy as np, pandas as pd
from pathlib import Path
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "metalabel_precondition_v1"; OUT.mkdir(parents=True, exist_ok=True)
CUMULATIVE_PRIOR_TRIALS = 402
RNG = np.random.default_rng(20260902)
BLOCK, NBOOT = 13, 2000

P = pd.read_csv(ROOT/"data/clean_weekly_prices_v1/weekly_adjusted_prices_clean.csv.gz", index_col=0)
P.index = pd.to_datetime(P.index)
R = P.pct_change().replace([np.inf, -np.inf], np.nan)
live = P.notna()

# ---- universe-level state, all backward-looking -------------------------------
W = live.div(live.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
uni_ret = (W.shift(1).fillna(0.0) * R.fillna(0.0)).sum(axis=1)
above = (P > P.rolling(26, min_periods=13).mean()).where(live)
state = pd.DataFrame(index=P.index)
state["uni_breadth"]   = above.sum(axis=1) / live.sum(axis=1).replace(0, np.nan)
state["uni_disp"]      = R.std(axis=1)
state["uni_ret_13w"]   = uni_ret.rolling(13).sum()
state["uni_vol_13w"]   = uni_ret.rolling(13).std()
state["uni_vol_ratio"] = uni_ret.rolling(4).std() / uni_ret.rolling(26).std()
state["uni_dd"]        = (1+uni_ret).cumprod() / (1+uni_ret).cumprod().cummax() - 1

# ---- strategy return series, unlevered ---------------------------------------
d = json.loads((ROOT/"dashboard/public/return-first-dashboard.json").read_text())
series = {"equal_weight_universe": uni_ret.iloc[52:]}
for it in d["strategies"]:
    idx = pd.DatetimeIndex([pd.Timestamp(r["date"]) for r in it["records"]])
    g = pd.Series([float(r["grossReturn"]) for r in it["records"]], index=idx)
    ex = max(1.0, max(sum(abs(h["weight"]) for h in r["holdings"]
                          if not h["symbol"].startswith("cash")) for r in it["records"]))
    series[it["strategy"]["shortName"]] = g / ex

def block_boot_p(x, y, obs):
    """Two-sided p for Spearman IC under a moving-block bootstrap of the label."""
    n = len(y); nb = int(np.ceil(n / BLOCK)); hits = 0
    starts_pool = np.arange(0, max(1, n - BLOCK + 1))
    for _ in range(NBOOT):
        s = RNG.choice(starts_pool, size=nb)
        perm = np.concatenate([y[i:i+BLOCK] for i in s])[:n]
        if abs(stats.spearmanr(x, perm).statistic) >= abs(obs): hits += 1
    return (hits + 1) / (NBOOT + 1)

rows = []
for name, base in series.items():
    r = base.dropna()
    own = pd.DataFrame(index=r.index)
    own["own_ret_4w"]   = r.rolling(4).sum()
    own["own_ret_13w"]  = r.rolling(13).sum()
    own["own_vol_13w"]  = r.rolling(13).std()
    own["own_vol_ratio"]= r.rolling(4).std() / r.rolling(26).std()
    own["own_dd"]       = (1+r).cumprod() / (1+r).cumprod().cummax() - 1
    feats = own.join(state.reindex(r.index), how="left")
    for col in feats.columns:
        x = feats[col].shift(1)                       # known at t-1
        ok = x.notna() & r.notna()
        if ok.sum() < 60: continue
        xv, yv = x[ok].to_numpy(), r[ok].to_numpy()
        ic = stats.spearmanr(xv, yv).statistic
        rows.append({"series": name, "feature": col, "n": int(ok.sum()),
                     "ic": float(ic), "p": float(block_boot_p(xv, yv, ic))})

df = pd.DataFrame(rows)
K = len(df)
df["p_bonf_run"] = (df["p"] * K).clip(upper=1.0)
df["p_bonf_cum"] = (df["p"] * (K + CUMULATIVE_PRIOR_TRIALS)).clip(upper=1.0)
df = df.reindex(df["ic"].abs().sort_values(ascending=False).index)
df.to_csv(OUT/"feature_ic.csv", index=False)

print(f"trials this run: {K}   cumulative denominator: {K + CUMULATIVE_PRIOR_TRIALS}\n")
print(f"  {'series':<26}{'feature':<16}{'IC':>8}{'raw p':>9}{'p(run)':>9}{'p(cum)':>9}")
for _, x in df.head(15).iterrows():
    print(f"  {x['series']:<26}{x['feature']:<16}{x['ic']:>+8.3f}{x['p']:>9.4f}{x['p_bonf_run']:>9.3f}{x['p_bonf_cum']:>9.3f}")

surv_run = df[df["p_bonf_run"] < 0.05]; surv_cum = df[df["p_bonf_cum"] < 0.05]
print(f"\n  |IC| > 0.10                     : {int((df['ic'].abs()>0.10).sum())} / {K}")
print(f"  significant, uncorrected        : {int((df['p']<0.05).sum())} / {K}")
print(f"  significant, Bonferroni this run: {len(surv_run)} / {K}")
print(f"  significant, cumulative trials  : {len(surv_cum)} / {K}")
if len(surv_cum):
    print("\n  survivors:")
    for _, x in surv_cum.iterrows():
        print(f"    {x['series']:<26}{x['feature']:<16}IC {x['ic']:+.3f}  p {x['p_bonf_cum']:.4f}")
verdict = ("PRECONDITION MET - conditional structure survives correction; meta-model build is justified"
           if len(surv_cum) else
           "PRECONDITION FAILED - no feature predicts strategy returns after correction; do not build")
print("\n  " + verdict)
json.dump({"trials_this_run": K, "cumulative_denominator": K + CUMULATIVE_PRIOR_TRIALS,
           "survivors_run": len(surv_run), "survivors_cumulative": len(surv_cum),
           "max_abs_ic": float(df["ic"].abs().max()), "verdict": verdict},
          open(OUT/"final_result.json","w"), indent=2)
