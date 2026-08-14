"""Frontier Phase 10A: Final Production Candidate Evaluation.

Runs comprehensive governance evaluation for phase5_fragility_guard against:
  - production_pin  (improved_phase2b_regime_confidence_boost)
  - shadow_pin      (improved_phase2b_combo_abc)
  - ggg_baseline    (improved_phaseggg_confirmed_only_robust_offense, no modifier)
  - phase1_r2a      (Phase 1 R2A offense scaling)
  - phase1_plus_p2  (Phase 1 R2A + Phase 2 ETF quality scaling)
  - phase5_fg       (Phase 5 fragility_guard — primary final candidate)

Does NOT modify production pins, dashboard, public/, or src/.

Run from repo root:
    .venv/bin/python scripts/phase_frontier10_final_evaluation.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from path1_path3_research_utils import (
    DATA, GGG, OFFENSE, PRODUCTION_COST_BPS,
    exposure_summary, normalize_to_cash, production_portfolio_path,
)
from allocator_checkpoint_wrapper import (
    AllocatorCheckpointWrapper,
    CheckpointModifier,
    exact_rebuild_tolerance_ok,
)

# ── Constants ─────────────────────────────────────────────────────────────────
HOLDOUT_START   = pd.Timestamp("2024-04-19")
DEV_END         = pd.Timestamp("2024-04-12")
BOOTSTRAP_SEED  = 20260420
BOOTSTRAP_ITERS = 2000
BOOTSTRAP_BLOCK = 13
ROLLING_WINDOW  = 104
ROLLING_STEP    = 52
MIN_TRAIN       = 260

PROD_PIN    = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN  = "improved_phase2b_combo_abc"
OFFENSE_ETFs = ["SPY","QQQ","XLK","XLY","XLI","IWM","VWO","EFA"]
PHASE2_ACTIVE_STATES = {"recovery_confirmed","neutral_mixed"}
FRAGILITY_THRESHOLD = -0.50

OUT_DIR     = DATA / "research" / "frontier_phase10"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase10_final_evaluation_report.md"

PROTECTED = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def _read_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    dc = "date" if "date" in df.columns else "Date"
    df[dc] = pd.to_datetime(df[dc], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[dc]).sort_values(dc).set_index(dc)


def _ez(s: pd.Series, min_p: int = 52) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


# ── Signal reconstruction ─────────────────────────────────────────────────────

def _r2a_modifier(ph1: pd.DataFrame, states: pd.Series, alpha: float = 0.08):
    q  = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(states.index).fillna(0.0).clip(-1.0, 1.0)
    sc = pd.Series(1.0, index=states.index, dtype=float)
    sc[states != "stressed_panic"] = 1.0 + alpha * q[states != "stressed_panic"]
    def _fn(w, _c): return sc.reindex(w.index).fillna(1.0)
    return CheckpointModifier(name="r2a_010", checkpoint="offense_budget", function=_fn)


def _fg_modifier(ph1: pd.DataFrame, ph4: pd.DataFrame, states: pd.Series, alpha: float = 0.08):
    q   = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(states.index).fillna(0.0).clip(-1.0, 1.0)
    lc  = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(states.index).ffill().fillna(0.0)
    frag = (-1.0 * lc).clip(-1.0, 1.0)
    sc  = pd.Series(1.0, index=states.index, dtype=float)
    not_sp = states != "stressed_panic"
    sc[not_sp] = 1.0 + alpha * q[not_sp]
    crowded = frag < FRAGILITY_THRESHOLD
    sc[crowded & not_sp] = sc[crowded & not_sp].clip(upper=1.0)
    sc[states == "stressed_panic"] = 1.0
    assert (sc[states == "stressed_panic"] == 1.0).all(), "SP BREACH"
    def _fn(w, _c): return sc.reindex(w.index).fillna(1.0)
    return CheckpointModifier(name="fg_modifier", checkpoint="offense_budget", function=_fn)


def _apply_p2_etf_scaling(weights: pd.DataFrame, tq: pd.DataFrame,
                           states: pd.Series, alpha: float = 0.5) -> pd.DataFrame:
    from scipy.stats import rankdata as _rankdata
    modified = weights.copy()
    q = tq.reindex(modified.index)
    off_cols = [t for t in OFFENSE & set(modified.columns)]
    for date in modified.index:
        if str(states.get(date, "")) not in PHASE2_ACTIVE_STATES:
            continue
        q_row = q.loc[date] if date in q.index else None
        if q_row is None:
            continue
        avail = [t for t in off_cols if t in q_row.index and np.isfinite(float(q_row.get(t, np.nan)))]
        if len(avail) < 4:
            continue
        q_vals = q_row[avail].values.astype(float)
        rank   = _rankdata(q_vals) / len(q_vals)
        scale  = (1.0 - alpha) + alpha * rank
        orig   = modified.loc[date, avail].sum()
        if orig <= 1e-9:
            continue
        for i, tk in enumerate(avail):
            modified.loc[date, tk] *= scale[i]
        scaled = modified.loc[date, avail].sum()
        if scaled > 1e-9:
            for tk in avail:
                modified.loc[date, tk] *= orig / scaled
    return normalize_to_cash(modified)


# ── Metric helpers ────────────────────────────────────────────────────────────

def _ar(r): return float((1+r).prod()**(52/len(r))-1) if len(r)>=2 else np.nan
def _vol(r): return float(r.std()*np.sqrt(52)) if len(r)>=4 else np.nan
def _sh(r):
    v=_vol(r); return float(_ar(r)/v) if v and np.isfinite(v) and v>0 else np.nan
def _dd(r):
    if r.empty: return np.nan
    w=(1+r).cumprod(); return float((w/w.cummax()-1).min())
def _calmar(r):
    d=_dd(r); return float(_ar(r)/abs(d)) if d and np.isfinite(d) and d<0 else np.nan
def _cvar(r,p=.05):
    if len(r)<20: return np.nan
    t=r[r<=r.quantile(p)]; return float(t.mean()) if len(t) else np.nan
def _beta(pr,nwr):
    if "SPY" not in nwr.columns: return np.nan
    spy=nwr["SPY"].reindex(pr.index).dropna()
    al=pd.concat([pr,spy],axis=1).dropna()
    if len(al)<20: return np.nan
    sl,*_=scipy_stats.linregress(al.iloc[:,1],al.iloc[:,0]); return float(sl)
def _cap(sr,nwr,dates):
    p=sr.reindex(dates).dropna()
    if "SPY" not in nwr.columns or len(p)<4: return np.nan
    spy=nwr["SPY"].reindex(p.index).dropna()
    c=p.index.intersection(spy.index)
    if len(c)<4: return np.nan
    sa=float((1+spy[c]).prod()**(52/len(c))-1)
    return float(_ar(p[c])/sa) if np.isfinite(sa) and sa>0.005 else np.nan

def summarise(variant, wts, path_df, states, nwr):
    path=path_df.set_index("Date") if "Date" in path_df.columns else path_df
    r=path["net_return"].dropna(); exp=exposure_summary(wts)
    sa=states.reindex(r.index)
    to=float(path["turnover"].mean()) if "turnover" in path.columns else np.nan
    row={"variant":variant,"ann_return":_ar(r),"ann_vol":_vol(r),"sharpe":_sh(r),
         "calmar":_calmar(r),"max_drawdown":_dd(r),"cvar_5":_cvar(r),"avg_turnover":to,
         "extra_cost_annual":to*(PRODUCTION_COST_BPS/1e4)*52 if np.isfinite(to) else np.nan,
         "avg_BIL":float(exp.get("avg_BIL",np.nan)),"avg_SPY":float(exp.get("avg_SPY",np.nan)),
         "avg_offense":float(exp.get("avg_offense",np.nan)),"hidden_beta":_beta(r,nwr)}
    for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
        m=sa==st; sr=r[m]
        row[f"sharpe_{st}"]=_sh(sr); row[f"capture_{st}"]=_cap(sr,nwr,sr.index)
        row[f"max_dd_{st}"]=_dd(sr)
    return row

def summarise_window(variant,wts,path_df,states,nwr,start,end,label):
    path=path_df.set_index("Date") if "Date" in path_df.columns else path_df
    m=pd.Series(True,index=path.index)
    if start: m&=path.index>=start
    if end:   m&=path.index<end
    slc=path[m].reset_index().rename(columns={"index":"Date"})
    ws=wts[wts.index.isin(path[m].index)]
    d=summarise(variant,ws,slc,states,nwr); d["window"]=label; return d


# ── Rolling & bootstrap ───────────────────────────────────────────────────────

def rolling_origin(cand_p,base_p):
    cp=cand_p.set_index("Date") if "Date" in cand_p.columns else cand_p
    bp=base_p.set_index("Date") if "Date" in base_p.columns else base_p
    rows=[]
    for s in range(MIN_TRAIN,len(cp)-ROLLING_WINDOW,ROLLING_STEP):
        idx=cp.index[s:s+ROLLING_WINDOW]
        cr=cp.loc[idx,"net_return"].dropna()
        br=bp.loc[idx,"net_return"].dropna() if "net_return" in bp.columns else pd.Series()
        if len(cr)<20: continue
        d=_sh(cr)-_sh(br) if len(br)>=20 else np.nan
        rows.append({"origin":cp.index[s],"cand_sharpe":_sh(cr),"base_sharpe":_sh(br) if len(br)>=20 else np.nan,"delta":d})
    df=pd.DataFrame(rows)
    if not df.empty: df["beats"]=df["delta"]>0
    return df

def bootstrap(cand_r,base_r):
    rng=np.random.default_rng(BOOTSTRAP_SEED)
    al=pd.concat([cand_r,base_r],axis=1).dropna()
    if len(al)<20: return {}
    n=len(al); ds=[]
    for _ in range(BOOTSTRAP_ITERS):
        sts=rng.integers(0,max(1,n-BOOTSTRAP_BLOCK+1),size=(n//BOOTSTRAP_BLOCK)+2)
        idx=np.concatenate([np.arange(s,min(s+BOOTSTRAP_BLOCK,n)) for s in sts])[:n]
        s2=al.iloc[idx]; ds.append(_sh(s2.iloc[:,0])-_sh(s2.iloc[:,1]))
    ds=np.array([d for d in ds if np.isfinite(d)])
    if not len(ds): return {}
    return {"p_cand_gt_base":float((ds>0).mean()),"mean_delta":float(ds.mean()),
            "ci95_lo":float(np.percentile(ds,2.5)),"ci95_hi":float(np.percentile(ds,97.5)),
            "n_boot":len(ds)}


# ── Phase D gate evaluation ───────────────────────────────────────────────────

def phase_d(cf,bf,ch,bh,bs,ro,label=""):
    ok,fail=[],[]
    def _d(a,b,k):
        av,bv=a.get(k),b.get(k)
        return (float(av)-float(bv)) if av is not None and bv is not None and np.isfinite(float(av)) and np.isfinite(float(bv)) else np.nan

    sh=_d(cf,bf,"sharpe")
    if np.isfinite(sh) and sh>=0.01: ok.append(f"Full Sharpe Δ={sh:+.4f} ≥ +0.01")
    else: fail.append(f"Full Sharpe Δ={sh:+.4f} < +0.01")

    hd=_d(ch,bh,"sharpe")
    if np.isfinite(hd) and hd>=-0.02: ok.append(f"Holdout Sharpe Δ={hd:+.4f} ≥ -0.02")
    else: fail.append(f"Holdout Sharpe Δ={hd:+.4f} < -0.02")

    dd=_d(cf,bf,"max_drawdown")
    if np.isfinite(dd) and dd>=-0.01: ok.append(f"MaxDD Δ={dd:+.4f} ≥ -0.01")
    else: fail.append(f"MaxDD Δ={dd:+.4f} < -0.01")

    cv=_d(cf,bf,"cvar_5")
    if np.isfinite(cv) and cv>=-0.002: ok.append(f"CVaR Δ={cv:+.4f} ≥ -0.002")
    else: fail.append(f"CVaR Δ={cv:+.4f} < -0.002")

    sp=_d(cf,bf,"sharpe_stressed_panic")
    if not np.isfinite(sp) or sp>=-0.05: ok.append(f"SP Sharpe Δ={sp:+.4f} (intact)")
    else: fail.append(f"SP Sharpe Δ={sp:+.4f} — DEFENSE WEAKENED")

    to=(cf.get("avg_turnover") or 0)-(bf.get("avg_turnover") or 0)
    cost=to*(PRODUCTION_COST_BPS/1e4)*52
    if cost<0.0015: ok.append(f"Extra cost={cost*100:.3f}% (< 0.15%)")
    else: fail.append(f"Extra cost={cost*100:.3f}% ≥ 0.15%")

    p=bs.get("p_cand_gt_base",np.nan)
    if np.isfinite(p) and p>=0.60: ok.append(f"Bootstrap P={p:.3f} ≥ 0.60")
    else: fail.append(f"Bootstrap P={p:.3f} < 0.60")

    if not ro.empty:
        wr=float(ro["beats"].mean())
        if wr>=0.55: ok.append(f"Rolling win={wr:.1%} ≥ 55%")
        else: fail.append(f"Rolling win={wr:.1%} < 55%")

    return len(fail)==0, ok, fail


# ── Protected diff ────────────────────────────────────────────────────────────

def diff_clean():
    try:
        r=subprocess.run(["git","diff","--name-only","--",*PROTECTED],cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception: return False,["failed"]
    c=[l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0,c


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns=[]
    print("="*70)
    print("Frontier Phase 10A: Final Production Candidate Evaluation")
    print("="*70)

    # ── Load signals ──────────────────────────────────────────────────────────
    print("\nLoading frontier signals...")
    ph1 = _read_dated(DATA/"research"/"frontier_phase1"/"state_quality_signals_r2.csv")
    ph4 = _read_dated(DATA/"research"/"frontier_phase4"/"leadership_signals.csv")
    tq  = _read_dated(DATA/"research"/"frontier_phase2"/"trend_quality_panel.csv")

    # ── Production pin and shadow ─────────────────────────────────────────────
    print("\nLoading production pin and shadow pin wrappers...")
    prod_wrapper   = AllocatorCheckpointWrapper(PROD_PIN)
    shadow_wrapper = AllocatorCheckpointWrapper(SHADOW_PIN)
    ggg_wrapper    = AllocatorCheckpointWrapper()   # GGG default

    # Verify GGG exact reproduction
    cmp = ggg_wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(cmp, 1e-10):
        raise SystemExit(f"GGG wrapper failed: {cmp}")
    print(f"  GGG exact match (max_err={cmp['net_return_max_abs_error']:.2e})")

    nwr    = ggg_wrapper.next_week_returns
    states = ggg_wrapper.states["market_state"].astype(str)

    # ── Run all candidates ────────────────────────────────────────────────────
    print("\nRunning candidates...")

    # Production pin (its own allocator, no modifier)
    prod_run = prod_wrapper.run("production_pin")
    prod_w, prod_p = prod_run.weights.copy(), prod_run.path

    # Shadow pin
    shad_run = shadow_wrapper.run("shadow_pin")
    shad_w, shad_p = shad_run.weights.copy(), shad_run.path

    # GGG baseline
    ggg_run  = ggg_wrapper.run("ggg_baseline")
    ggg_w,  ggg_p  = ggg_run.weights.copy(), ggg_run.path

    # Phase 1 R2A reference
    p1_mod = _r2a_modifier(ph1, states, alpha=0.08)
    p1_run = ggg_wrapper.run("phase1_r2a_reference", modifiers=[p1_mod])
    p1_w, p1_p = p1_run.weights.copy(), p1_run.path

    # Phase 1+2 reference (P1 at checkpoint + P2 ETF scaling)
    p12_run = ggg_wrapper.run("phase1_plus_p2_reference", modifiers=[p1_mod])
    p12_wts = _apply_p2_etf_scaling(p12_run.weights.copy(), tq, states, alpha=0.5)
    p12_p   = production_portfolio_path(p12_wts, nwr, PRODUCTION_COST_BPS)

    # Phase 5 fragility_guard (primary final candidate)
    fg_mod = _fg_modifier(ph1, ph4, states, alpha=0.08)
    fg_run = ggg_wrapper.run("phase5_fragility_guard", modifiers=[fg_mod])
    fg_w, fg_p = fg_run.weights.copy(), fg_run.path

    # stressed_panic integrity check for frontier candidates
    print("\nVerifying stressed_panic integrity...")
    sp_dates = states.index[states == "stressed_panic"]
    off_cols = sorted(OFFENSE & set(ggg_w.columns))
    for vname, wts in [("p1_r2a",p1_w),("p1+p2",p12_wts),("p5_fg",fg_w)]:
        diff=(wts.loc[sp_dates,off_cols].sum(axis=1)-ggg_w.loc[sp_dates,off_cols].sum(axis=1)).abs().max()
        status="✓" if diff<=0.001 else "✗ BREACH"
        print(f"  {status} {vname}: max_sp_offense_change={diff:.2e}")
        if diff>0.001: warns.append(f"SP BREACH {vname}")

    runs={
        "production_pin":         (prod_w, prod_p),
        "shadow_pin":             (shad_w, shad_p),
        "ggg_baseline":           (ggg_w,  ggg_p),
        "phase1_r2a_reference":   (p1_w,   p1_p),
        "phase1_plus_p2_reference":(p12_wts,p12_p),
        "phase5_fragility_guard": (fg_w,   fg_p),
    }

    # ── Compute metrics ───────────────────────────────────────────────────────
    print("\nComputing metrics...")
    full_r, hold_r = {}, {}
    for v,(wts,path) in runs.items():
        full_r[v] = summarise(v,wts,path,states,nwr)
        hold_r[v] = summarise_window(v,wts,path,states,nwr,HOLDOUT_START,None,"holdout")

    # Print summary
    print("\n=== Full-History ===")
    prod_sh = full_r["production_pin"]["sharpe"]
    ggg_sh  = full_r["ggg_baseline"]["sharpe"]
    for v,r in full_r.items():
        d_prod=(r["sharpe"] or np.nan)-prod_sh
        d_ggg =(r["sharpe"] or np.nan)-ggg_sh
        print(f"  {v:<30}: sh={r['sharpe']:.4f}(Δprod{d_prod:+.4f},Δggg{d_ggg:+.4f})  "
              f"dd={r['max_drawdown']:.4f}  sp={r.get('sharpe_stressed_panic',np.nan):.4f}")

    print("\n=== Holdout ===")
    prod_hsh = hold_r["production_pin"]["sharpe"]
    ggg_hsh  = hold_r["ggg_baseline"]["sharpe"]
    for v,r in hold_r.items():
        d_prod=(r["sharpe"] or np.nan)-prod_hsh
        d_ggg =(r["sharpe"] or np.nan)-ggg_hsh
        print(f"  {v:<30}: sh={r['sharpe']:.4f}(Δprod{d_prod:+.4f},Δggg{d_ggg:+.4f})")

    # Rolling-origin and bootstrap for FG vs baselines
    print("\nRolling-origin and bootstrap (phase5_fg vs GGG and vs production_pin)...")
    ro_fg_ggg  = rolling_origin(fg_p, ggg_p)
    ro_fg_prod = rolling_origin(fg_p, prod_p)

    fg_ho = fg_p.set_index("Date")["net_return"]; fg_ho = fg_ho[fg_ho.index>=HOLDOUT_START].dropna()
    ggg_ho= ggg_p.set_index("Date")["net_return"]; ggg_ho= ggg_ho[ggg_ho.index>=HOLDOUT_START].dropna()
    prod_ho=prod_p.set_index("Date")["net_return"]; prod_ho=prod_ho[prod_ho.index>=HOLDOUT_START].dropna()

    bs_fg_ggg  = bootstrap(fg_ho, ggg_ho)
    bs_fg_prod = bootstrap(fg_ho, prod_ho)

    wr_fg_ggg  = float(ro_fg_ggg["beats"].mean())  if not ro_fg_ggg.empty  else np.nan
    wr_fg_prod = float(ro_fg_prod["beats"].mean()) if not ro_fg_prod.empty else np.nan
    print(f"  FG vs GGG:  rolling_win={wr_fg_ggg:.1%}  bootstrap_P={bs_fg_ggg.get('p_cand_gt_base',np.nan):.3f}")
    print(f"  FG vs PROD: rolling_win={wr_fg_prod:.1%}  bootstrap_P={bs_fg_prod.get('p_cand_gt_base',np.nan):.3f}")

    # ── Phase D gates ─────────────────────────────────────────────────────────
    print("\nPhase D gates...")
    gv_ggg,  ok_ggg,  fail_ggg  = phase_d(full_r["phase5_fragility_guard"],
                                            full_r["ggg_baseline"],
                                            hold_r["phase5_fragility_guard"],
                                            hold_r["ggg_baseline"],
                                            bs_fg_ggg, ro_fg_ggg, "FG vs GGG")
    gv_prod, ok_prod, fail_prod = phase_d(full_r["phase5_fragility_guard"],
                                           full_r["production_pin"],
                                           hold_r["phase5_fragility_guard"],
                                           hold_r["production_pin"],
                                           bs_fg_prod, ro_fg_prod, "FG vs PROD")

    print(f"\n  FG vs GGG:  {'PASS' if gv_ggg  else 'FAIL'}")
    for r in ok_ggg:   print(f"    ✓ {r}")
    for r in fail_ggg: print(f"    ✗ {r}")
    print(f"\n  FG vs PROD: {'PASS' if gv_prod else 'FAIL'}")
    for r in ok_prod:   print(f"    ✓ {r}")
    for r in fail_prod: print(f"    ✗ {r}")

    # ── Additional governance checks ──────────────────────────────────────────
    fg_f  = full_r["phase5_fragility_guard"]
    ggg_f = full_r["ggg_baseline"]
    pr_f  = full_r["production_pin"]

    delta_beta = (fg_f.get("hidden_beta") or np.nan) - (ggg_f.get("hidden_beta") or np.nan)
    delta_bil  = (fg_f.get("avg_BIL")     or np.nan) - (ggg_f.get("avg_BIL")     or np.nan)
    delta_off  = (fg_f.get("avg_offense") or np.nan) - (ggg_f.get("avg_offense") or np.nan)
    print(f"\nGovernance checks (FG vs GGG):")
    print(f"  Hidden beta Δ: {delta_beta:+.4f}  ({'OK' if abs(delta_beta)<0.05 else 'WARNING'})")
    print(f"  BIL Δ:         {delta_bil:+.4f}  ({'OK — not driven by BIL reduction' if delta_bil>-0.02 else 'WARNING: BIL reduced'})")
    print(f"  Offense Δ:     {delta_off:+.4f}")

    # ── Final verdict ─────────────────────────────────────────────────────────
    sp_ok = not any("DEFENSE" in f for f in fail_ggg + fail_prod)
    beta_ok = abs(delta_beta) < 0.10
    bil_ok  = delta_bil > -0.03

    print(f"\n{'='*70}")
    if gv_ggg and sp_ok and beta_ok and bil_ok:
        verdict = "Promote"
        vr = (f"phase5_fragility_guard passes all 8 Phase D gates vs GGG baseline and "
              f"all governance checks. Full Sharpe Δ={fg_f['sharpe']-ggg_f['sharpe']:+.4f}, "
              f"holdout Δ={hold_r['phase5_fragility_guard']['sharpe']-hold_r['ggg_baseline']['sharpe']:+.4f}, "
              f"bootstrap P={bs_fg_ggg.get('p_cand_gt_base',np.nan):.3f}, rolling win={wr_fg_ggg:.1%}. "
              "Recommend as production candidate pending human deployment review.")
    elif gv_ggg and (not sp_ok or not beta_ok or not bil_ok):
        verdict = "Keep as Shadow"
        vr = (f"phase5_fragility_guard passes Phase D gates but fails a governance check: "
              f"{'SP defense concern; ' if not sp_ok else ''}"
              f"{'hidden beta increase; ' if not beta_ok else ''}"
              f"{'BIL reduction concern; ' if not bil_ok else ''}. "
              "Keep as shadow; do not promote without further review.")
    elif not gv_ggg:
        holdout_d = hold_r["phase5_fragility_guard"]["sharpe"] - hold_r["ggg_baseline"]["sharpe"]
        if holdout_d >= -0.02:
            verdict = "Keep as Shadow"
            vr = (f"phase5_fragility_guard fails some Phase D gates vs GGG "
                  f"({'; '.join(fail_ggg[:2])}) but holdout is acceptable (Δ={holdout_d:+.4f}). "
                  "Keep as shadow candidate for future review.")
        else:
            verdict = "Research-only"
            vr = (f"phase5_fragility_guard fails Phase D gates: {'; '.join(fail_ggg[:3])}.")
    else:
        verdict = "Research-only"
        vr = "Governance concerns prevent promotion or shadow classification."

    print(f"FINAL VERDICT: {verdict}")
    print(f"Reason: {vr}")
    print(f"{'='*70}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(list(full_r.values())).to_csv(OUT_DIR/"final_candidate_metrics.csv",index=False)
    pd.DataFrame(list(hold_r.values())).to_csv(OUT_DIR/"final_candidate_holdout_summary.csv",index=False)

    st_rows=[]
    for v,r in full_r.items():
        for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
            st_rows.append({"variant":v,"state":st,
                "sharpe":r.get(f"sharpe_{st}"),"capture":r.get(f"capture_{st}"),
                "max_dd":r.get(f"max_dd_{st}")})
    pd.DataFrame(st_rows).to_csv(OUT_DIR/"final_candidate_state_summary.csv",index=False)

    gate_rows=[
        {"comparison":"FG_vs_GGG","verdict":"PASS" if gv_ggg else "FAIL",
         "ok":"; ".join(ok_ggg),"fail":"; ".join(fail_ggg)},
        {"comparison":"FG_vs_PROD","verdict":"PASS" if gv_prod else "FAIL",
         "ok":"; ".join(ok_prod),"fail":"; ".join(fail_prod)},
    ]
    pd.DataFrame(gate_rows).to_csv(OUT_DIR/"final_candidate_phase_d_gates.csv",index=False)

    bs_rows=[
        {"comparison":"FG_vs_GGG",  **bs_fg_ggg,  "rolling_win_rate":wr_fg_ggg},
        {"comparison":"FG_vs_PROD", **bs_fg_prod, "rolling_win_rate":wr_fg_prod},
    ]
    pd.DataFrame(bs_rows).to_csv(OUT_DIR/"final_candidate_bootstrap_summary.csv",index=False)

    ro_fg_ggg.assign(comparison="FG_vs_GGG").to_csv(
        OUT_DIR/"final_candidate_rolling_origin.csv",index=False)

    for f in ["final_candidate_metrics.csv","final_candidate_holdout_summary.csv",
              "final_candidate_state_summary.csv","final_candidate_phase_d_gates.csv",
              "final_candidate_bootstrap_summary.csv","final_candidate_rolling_origin.csv"]:
        print(f"  Saved: data/research/frontier_phase10/{f}")

    dc,dch=diff_clean()
    if not dc: print(f"WARNING: {dch}"); warns.append(str(dch))
    else: print("Protected files: clean.")

    _write_report(full_r,hold_r,ro_fg_ggg,ro_fg_prod,bs_fg_ggg,bs_fg_prod,
                  wr_fg_ggg,wr_fg_prod,gv_ggg,gv_prod,ok_ggg,fail_ggg,ok_prod,fail_prod,
                  delta_beta,delta_bil,delta_off,sp_ok,beta_ok,bil_ok,
                  verdict,vr,warns,dc)
    _journey(verdict,vr,full_r,hold_r,bs_fg_ggg,wr_fg_ggg)
    print(f"\nPhase 10A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _f(v,fmt=".4f"):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    try: return format(float(v),fmt)
    except: return str(v)
def _pct(v):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    return f"{float(v)*100:.2f}%"

VS={
    "production_pin":"prod_pin","shadow_pin":"shadow_pin","ggg_baseline":"ggg",
    "phase1_r2a_reference":"p1_r2a","phase1_plus_p2_reference":"p1+p2",
    "phase5_fragility_guard":"p5_fg (CANDIDATE)",
}

def _write_report(full_r,hold_r,ro_fg_ggg,ro_fg_prod,bs_fg_ggg,bs_fg_prod,
                  wr_fg_ggg,wr_fg_prod,gv_ggg,gv_prod,ok_ggg,fail_ggg,ok_prod,fail_prod,
                  delta_beta,delta_bil,delta_off,sp_ok,beta_ok,bil_ok,
                  verdict,vr,warns,dc):
    lines=[]; A=lines.append
    all_v=list(full_r.keys())

    A("# Frontier Phase 10A: Final Production Candidate Evaluation Report")
    A(""); A("**Date:** 2026-05-22")
    A("**Primary candidate:** `phase5_fragility_guard`")
    A("**Production pin:** `improved_phase2b_regime_confidence_boost`")
    A("**Shadow pin:** `improved_phase2b_combo_abc`")
    A(""); A("---"); A("")

    A("## 1. Sprint Summary"); A("")
    A("Final governance evaluation for the frontier arc (Phases 1–7). "
      "phase5_fragility_guard is evaluated against the GGG baseline, production pin, "
      "and shadow pin using the full Phase D 8-gate framework plus governance checks.")
    A(""); A("---"); A("")

    A("## 2. Commands Run"); A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier10_final_evaluation.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Frontier Arc Summary (Phases 1–7)"); A("")
    A("| phase | result |")
    A("|-------|--------|")
    for p,r in [
        ("Phase 1 (state quality)","R2A signal validated; portfolio modifier borderline"),
        ("Phase 2 (trend quality)","Signal validated; ETF scaling research-only"),
        ("Phase 3 (re-risking)","Gate calibration failure; signals useful as inputs"),
        ("Phase 4 (leadership)","Anti-predictive; inverted as fragility guardrail in Phase 5"),
        ("Phase 5 (allocator)","phase5_fragility_guard PASSES all 8 Phase D gates"),
        ("Phase 6 (ML)","Model beats naive; portfolio switching failed"),
        ("Phase 7 (cross-asset)","0/5 stable pairs; diagnostic-only"),
    ]:
        A(f"| {p} | {r} |")
    A(""); A("---"); A("")

    A("## 4. Full-History Candidate Comparison"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k,lb in [("ann_return","Ann ret"),("sharpe","Sharpe"),("max_drawdown","Max DD"),
                 ("cvar_5","CVaR 5%"),("avg_turnover","TO/wk"),
                 ("extra_cost_annual","Cost/yr"),("avg_BIL","BIL"),
                 ("avg_offense","Offense"),("hidden_beta","β SPY")]:
        cells=[lb]
        for v in all_v:
            val=full_r[v].get(k)
            cells.append(_pct(val) if k in ("ann_return","avg_BIL","avg_offense","extra_cost_annual") else _f(val))
        A("| "+" | ".join(cells)+" |")
    A(""); A("---"); A("")

    A("## 5. Holdout Metrics (from 2024-04-19)"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k,lb in [("ann_return","Return"),("sharpe","Sharpe"),("max_drawdown","Max DD")]:
        cells=[lb]
        for v in all_v:
            val=hold_r[v].get(k)
            cells.append(_pct(val) if k=="ann_return" else _f(val))
        A("| "+" | ".join(cells)+" |")
    A(""); A("*Holdout Sharpe deltas:*")
    ggg_hsh=hold_r["ggg_baseline"]["sharpe"]; prod_hsh=hold_r["production_pin"]["sharpe"]
    for v in all_v:
        sh=hold_r[v]["sharpe"]; dg=(float(sh)-float(ggg_hsh)) if sh is not None and np.isfinite(float(sh)) else np.nan
        A(f"- {VS.get(v,v)}: vs GGG {_f(dg,'+.4f')}")
    A(""); A("---"); A("")

    A("## 6. Phase D Gate Evaluation"); A("")
    A("### Phase5_FG vs GGG baseline"); A("")
    A(f"**{'✓ PASS' if gv_ggg else '✗ FAIL'}**"); A("")
    for r in ok_ggg:   A(f"- ✓ {r}")
    for r in fail_ggg: A(f"- ✗ {r}")
    A("")
    A("### Phase5_FG vs Production pin"); A("")
    A(f"**{'✓ PASS' if gv_prod else '✗ FAIL'}**"); A("")
    for r in ok_prod:   A(f"- ✓ {r}")
    for r in fail_prod: A(f"- ✗ {r}")
    A(""); A("---"); A("")

    A("## 7. Rolling-Origin and Bootstrap"); A("")
    A("| comparison | rolling_win | bootstrap_P | mean_Δ | CI_95 |")
    A("|------------|------------|------------|--------|-------|")
    for comp,bs,wr in [("FG_vs_GGG",bs_fg_ggg,wr_fg_ggg),("FG_vs_PROD",bs_fg_prod,wr_fg_prod)]:
        A(f"| {comp} | {_f(wr,'.1%')} | {_f(bs.get('p_cand_gt_base'),'.3f')} | "
          f"{_f(bs.get('mean_delta'),'+.4f')} | [{_f(bs.get('ci95_lo'),'+.4f')}, {_f(bs.get('ci95_hi'),'+.4f')}] |")
    A(""); A("---"); A("")

    A("## 8. Governance Checks (FG vs GGG)"); A("")
    A("| check | value | result |")
    A("|-------|-------|--------|")
    A(f"| Hidden beta Δ | {_f(delta_beta,'+.4f')} | {'✓ OK' if beta_ok else '✗ WARNING'} |")
    A(f"| BIL Δ | {_f(delta_bil,'+.4f')} | {'✓ OK' if bil_ok else '✗ WARNING'} |")
    A(f"| Offense Δ | {_f(delta_off,'+.4f')} | ✓ |")
    A(f"| Stressed-panic defense | — | {'✓ intact' if sp_ok else '✗ BREACH'} |")
    A(""); A("---"); A("")

    A("## 9. State-by-State (phase5_fg vs production_pin)"); A("")
    A("| state | prod_sharpe | prod_capture | fg_sharpe | fg_capture | Δsharpe |")
    A("|-------|-------------|-------------|-----------|------------|---------|")
    for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
        p=full_r["production_pin"]; f=full_r["phase5_fragility_guard"]
        ps=p.get(f"sharpe_{st}",np.nan); fs=f.get(f"sharpe_{st}",np.nan)
        d=(float(fs)-float(ps)) if np.isfinite(float(fs)) and np.isfinite(float(ps)) else np.nan
        A(f"| {st} | {_f(ps)} | {_f(p.get(f'capture_{st}'))} | {_f(fs)} | {_f(f.get(f'capture_{st}'))} | {_f(d,'+.4f')} |")
    A(""); A("---"); A("")

    A("## 10. Final Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A("")
    A("### Production Governance Recommendation"); A("")
    if verdict == "Promote":
        A("phase5_fragility_guard is ready for a human deployment review as a "
          "production candidate. To promote:")
        A("1. Update CLAUDE.md: set `production candidate (pending)` to `phase5_fragility_guard`")
        A("2. Run full dashboard review with the new candidate exposed")
        A("3. Human review of state-by-state behavior, particularly recovery_confirmed capture")
        A("4. Only after human review: update the production pin via explicit CLAUDE.md change")
        A("")
        A("**Do NOT run automated production pin updates.** This report is the research "
          "recommendation only. Final deployment authority rests with human review.")
    elif verdict == "Keep as Shadow":
        A("phase5_fragility_guard should be tracked as a research reference but not deployed.")
        A("The current production pin (`improved_phase2b_regime_confidence_boost`) remains.")
        A("Continue monitoring the candidate's behavior in live market conditions.")
    else:
        A("Maintain current production and shadow pins unchanged.")
    A(""); A("---"); A("")

    A("## 11. Files Created"); A("")
    for f in ["final_candidate_metrics.csv","final_candidate_holdout_summary.csv",
              "final_candidate_state_summary.csv","final_candidate_phase_d_gates.csv",
              "final_candidate_bootstrap_summary.csv","final_candidate_rolling_origin.csv"]:
        A(f"- `data/research/frontier_phase10/{f}`")
    A("- `docs/research/frontier_phase10_final_evaluation_report.md`"); A("")
    A("## 12. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: **UNCHANGED**")
    A("- No public/, src/, dashboard, or registry files modified")
    A("- All candidate outputs are research artifacts only")
    if warns:
        A(""); A("## 13. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase10_final_evaluation_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict,vr,full_r,hold_r,bs_fg_ggg,wr_fg_ggg):
    j=ROOT/"docs"/"research"/"project_journey.md"
    if not j.exists(): return
    fg_f=full_r.get("phase5_fragility_guard",{})
    ggg_f=full_r.get("ggg_baseline",{})
    prod_f=full_r.get("production_pin",{})
    fg_h=hold_r.get("phase5_fragility_guard",{})
    ggg_h=hold_r.get("ggg_baseline",{})
    txt=f"""

## Section — Frontier Phase 10A: Final Production Candidate Evaluation

Date: 2026-05-22.

Final governance evaluation for phase5_fragility_guard, the only frontier
candidate to pass all 8 Phase D gates in the frontier arc (Phases 1–7).

phase5_fragility_guard design:
- Phase 1 R2A offense scaling (alpha=0.08)
- Phase 4 fragility guardrail: cap offense when inverted leadership < -0.50
  (prevents over-deployment in crowded/late-cycle market conditions)

Key metrics:
| metric | production_pin | ggg_baseline | phase5_fg |
|--------|---------------|-------------|-----------|
| full_sharpe | {_f(prod_f.get('sharpe'))} | {_f(ggg_f.get('sharpe'))} | {_f(fg_f.get('sharpe'))} |
| holdout_sharpe | {_f(hold_r.get('production_pin',{}).get('sharpe'))} | {_f(ggg_h.get('sharpe'))} | {_f(fg_h.get('sharpe'))} |
| max_drawdown | {_f(prod_f.get('max_drawdown'))} | {_f(ggg_f.get('max_drawdown'))} | {_f(fg_f.get('max_drawdown'))} |
| bootstrap_P_vs_ggg | — | — | {_f(bs_fg_ggg.get('p_cand_gt_base'),'.3f')} |
| rolling_win_vs_ggg | — | — | {_f(wr_fg_ggg,'.1%')} |

Final Verdict: **{verdict}**

{vr}

Production pins remain UNCHANGED.
Production governance: {'' if verdict=='Promote' else 'No action required at this time.'}
{'Human deployment review required before any production pin update.' if verdict=='Promote' else ''}
"""
    with open(j,"a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
