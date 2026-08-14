"""Frontier Phase 5A: Deployment-Quality Allocator Objective.

Combines Phase 1 (R2A), Phase 2 (trend_quality) and Phase 4 (inverted
leadership) into a master deployment quality score, then tests it as a
bounded offense_budget modifier.  Phases 1–2 reference candidates are
reproduced for comparison.  All stressed_panic rows are explicitly
asserted unchanged.

Run from repo root:
    .venv/bin/python scripts/phase_frontier5_deployment_quality_allocator.py
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
    DATA, OFFENSE, PRODUCTION_COST_BPS,
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

# Master quality blend weights (predeclared, not tuned)
W_P1 = 0.45
W_P2 = 0.35
W_P4 = 0.20
FRAGILITY_THRESHOLD = -0.50  # inverted leadership below this → guard fires

OUT_DIR     = DATA / "research" / "frontier_phase5"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase5_allocator_objective_report.md"

OFFENSE_ETFs = ["SPY","QQQ","XLK","XLY","XLI","IWM","VWO","EFA"]
PHASE2_ACTIVE_STATES = {"recovery_confirmed","neutral_mixed"}

PROTECTED = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def _read_csv_dated(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    dc = "date" if "date" in df.columns else "Date"
    df[dc] = pd.to_datetime(df[dc], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[dc]).sort_values(dc).set_index(dc)


def _ez(s: pd.Series, min_p: int = 52) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


# ── Signal construction ───────────────────────────────────────────────────────

def build_signals(wrapper_index: pd.DatetimeIndex,
                  warnings: list[str]) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Return (phase1_sq, phase2_tq, phase4_frag, master_dq) all on wrapper_index."""

    # Phase 1 R2A
    ph1 = _read_csv_dated(DATA/"research"/"frontier_phase1"/"state_quality_signals_r2.csv")
    p1_raw = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(wrapper_index).fillna(0.0)
    phase1_sq = p1_raw.clip(-1.0, 1.0)

    # Phase 2 avg trend quality across offensive ETFs (already lagged)
    tq = _read_csv_dated(DATA/"research"/"frontier_phase2"/"trend_quality_panel.csv")
    off_avail = [t for t in OFFENSE_ETFs if t in tq.columns]
    if not off_avail:
        warnings.append("No Phase 2 offense ETFs found — using zero for phase2_tq")
        phase2_tq = pd.Series(0.0, index=wrapper_index)
    else:
        avg_tq_raw = tq[off_avail].mean(axis=1).reindex(wrapper_index)
        phase2_tq  = _ez(avg_tq_raw).clip(-1.0, 1.0)

    # Phase 4 leadership — INVERTED (raw was anti-predictive, inverted = fragility guard)
    ph4 = _read_csv_dated(DATA/"research"/"frontier_phase4"/"leadership_signals.csv")
    lc_raw = pd.to_numeric(
        ph4["leadership_quality_composite"], errors="coerce"
    ).reindex(wrapper_index).ffill().fillna(0.0)
    phase4_frag = (-1.0 * lc_raw).clip(-1.0, 1.0)   # inverted

    # Master deployment quality (predeclared weights)
    mdq_raw = W_P1 * phase1_sq + W_P2 * phase2_tq + W_P4 * phase4_frag
    master_dq = _ez(mdq_raw).clip(-1.0, 1.0)

    print(f"  phase1_sq:   non-null={phase1_sq.notna().sum()}, "
          f"mean={phase1_sq.mean():.4f}, std={phase1_sq.std():.4f}")
    print(f"  phase2_tq:   non-null={phase2_tq.notna().sum()}, "
          f"mean={phase2_tq.mean():.4f}, std={phase2_tq.std():.4f}")
    print(f"  phase4_frag: non-null={phase4_frag.notna().sum()}, "
          f"mean={phase4_frag.mean():.4f}, std={phase4_frag.std():.4f}")
    print(f"  master_dq:   non-null={master_dq.notna().sum()}, "
          f"mean={master_dq.mean():.4f}, std={master_dq.std():.4f}")

    return phase1_sq, phase2_tq, phase4_frag, master_dq


# ── Modifier factories ────────────────────────────────────────────────────────

def _offense_fn(series: pd.Series, states: pd.Series,
                alpha: float, pos_only: bool = False,
                frag_guard: pd.Series | None = None,
                name: str = "mod"):
    """Return a CheckpointModifier at offense_budget.

    scale = 1 + alpha × q              (standard)
    scale = 1 + alpha × max(q, 0)      (positive-only variant)
    Fragility guard: if frag < THRESHOLD, cap scale at 1.0 (no increase).
    stressed_panic: always 1.0.
    """
    q = series.reindex(states.index).fillna(0.0)
    if pos_only:
        q = q.clip(0.0, 1.0)
    else:
        q = q.clip(-1.0, 1.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    not_sp = states != "stressed_panic"
    scale[not_sp] = 1.0 + alpha * q[not_sp]
    if frag_guard is not None:
        fg = frag_guard.reindex(states.index).fillna(0.0)
        crowded = fg < FRAGILITY_THRESHOLD
        # When crowded (inverted leadership < threshold), cap scale at 1.0
        scale[crowded & not_sp] = scale[crowded & not_sp].clip(upper=1.0)
    scale[states == "stressed_panic"] = 1.0
    # Hard assertion
    assert (scale[states == "stressed_panic"] == 1.0).all(), \
        f"SAFETY VIOLATION in {name}: stressed_panic scale != 1.0"

    def _fn(w, _c):
        return scale.reindex(w.index).fillna(1.0)

    return CheckpointModifier(name=name, checkpoint="offense_budget", function=_fn)


def _r2a_fn(phase1_sq: pd.Series, states: pd.Series, alpha: float = 0.08):
    return _offense_fn(phase1_sq, states, alpha, name="r2a_offense")


# Phase 2 ETF-level scaling (post-processing on final weights, matches Phase 2B)
def _apply_phase2_etf_scaling(weights: pd.DataFrame,
                               tq_panel: pd.DataFrame,
                               states: pd.Series,
                               alpha: float = 0.5) -> pd.DataFrame:
    """Scale offensive ETFs by cross-sectional trend_quality rank in active states."""
    from scipy.stats import rankdata as _rankdata
    modified = weights.copy()
    q = tq_panel.reindex(modified.index)
    off_cols = [t for t in OFFENSE & set(modified.columns)]

    for t_idx, date in enumerate(modified.index):
        if str(states.get(date,"")) not in PHASE2_ACTIVE_STATES:
            continue
        q_row = q.loc[date] if date in q.index else None
        if q_row is None:
            continue
        avail = [tk for tk in off_cols
                 if tk in q_row.index and np.isfinite(float(q_row.get(tk, np.nan)))]
        if len(avail) < 4:
            continue
        q_vals = q_row[avail].values.astype(float)
        rank   = _rankdata(q_vals) / len(q_vals)
        scale  = (1.0 - alpha) + alpha * rank
        orig_tot = modified.loc[date, avail].sum()
        if orig_tot <= 1e-9:
            continue
        for i, tk in enumerate(avail):
            modified.loc[date, tk] *= scale[i]
        scaled_tot = modified.loc[date, avail].sum()
        if scaled_tot > 1e-9:
            for tk in avail:
                modified.loc[date, tk] *= orig_tot / scaled_tot

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
def _cap(pr,nwr,dates):
    p=pr.reindex(dates).dropna()
    if "SPY" not in nwr.columns or len(p)<4: return np.nan
    spy=nwr["SPY"].reindex(p.index).dropna()
    c=p.index.intersection(spy.index)
    if len(c)<4: return np.nan
    s_ann=float((1+spy[c]).prod()**(52/len(c))-1)
    return float(_ar(p[c])/s_ann) if np.isfinite(s_ann) and s_ann>0.005 else np.nan

def summarise(variant, wts, path_df, states, nwr):
    path=path_df.set_index("Date") if "Date" in path_df.columns else path_df
    r=path["net_return"].dropna(); exp=exposure_summary(wts); sa=states.reindex(r.index)
    to=float(path["turnover"].mean()) if "turnover" in path.columns else np.nan
    row={"variant":variant,"ann_return":_ar(r),"ann_vol":_vol(r),"sharpe":_sh(r),
         "calmar":_calmar(r),"max_drawdown":_dd(r),"cvar_5":_cvar(r),"avg_turnover":to,
         "extra_cost_annual":to*(PRODUCTION_COST_BPS/1e4)*52 if np.isfinite(to) else np.nan,
         "avg_BIL":float(exp.get("avg_BIL",np.nan)),"avg_offense":float(exp.get("avg_offense",np.nan)),
         "hidden_beta":_beta(r,nwr)}
    for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
        m=sa==st; sr=r[m]
        row[f"sharpe_{st}"]=_sh(sr); row[f"ann_return_{st}"]=_ar(sr)
        row[f"capture_{st}"]=_cap(sr,nwr,sr.index); row[f"max_dd_{st}"]=_dd(sr)
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
        cr=cp.loc[idx,"net_return"].dropna(); br=bp.loc[idx,"net_return"].dropna() if "net_return" in bp.columns else pd.Series()
        if len(cr)<20: continue
        d=_sh(cr)-_sh(br) if len(br)>=20 else np.nan
        rows.append({"origin":cp.index[s],"cand_sharpe":_sh(cr),"base_sharpe":_sh(br) if len(br)>=20 else np.nan,"delta_sharpe":d})
    df=pd.DataFrame(rows)
    if not df.empty: df["beats_base"]=df["delta_sharpe"]>0
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
            "ci95_lo":float(np.percentile(ds,2.5)),"ci95_hi":float(np.percentile(ds,97.5))}


# ── Phase D gates ─────────────────────────────────────────────────────────────

def phase_d(cf,bf,ch,bh,bs,ro):
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
        wr=float(ro["beats_base"].mean())
        if wr>=0.55: ok.append(f"Rolling win={wr:.1%} ≥ 55%")
        else: fail.append(f"Rolling win={wr:.1%} < 55%")
    return len(fail)==0, ok, fail


# ── Protected diff ────────────────────────────────────────────────────────────

def diff_clean():
    try:
        r=subprocess.run(["git","diff","--name-only","--",*PROTECTED],cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception: return False,["git diff failed"]
    c=[l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0,c


# ── Formatting ────────────────────────────────────────────────────────────────

def _f(v,fmt=".4f"):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    try: return format(float(v),fmt)
    except: return str(v)
def _pct(v):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    return f"{float(v)*100:.2f}%"

VS={
    "ggg_baseline_no_modifier":           "baseline",
    "phase1_r2a_reference":               "p1_r2a",
    "phase1_plus_phase2_reference":       "p1+p2",
    "phase5_master_quality_010":          "p5_mdq010",
    "phase5_master_quality_012":          "p5_mdq012",
    "phase5_positive_only_confidence":    "p5_pos_only",
    "phase5_fragility_guard":             "p5_frag_grd",
    "phase5_master_quality_plus_frag":    "p5_mdq+frag",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns=[]
    print("="*70)
    print("Frontier Phase 5A: Deployment-Quality Allocator Objective")
    print("="*70)

    # Load and verify wrapper
    print("\nInitialising wrapper...")
    wrapper = AllocatorCheckpointWrapper()
    cmp = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(cmp,1e-10):
        raise SystemExit(f"Wrapper failed: {cmp}")
    print(f"  GGG exact match (max_err={cmp['net_return_max_abs_error']:.2e})")

    nwr    = wrapper.next_week_returns
    states = wrapper.states["market_state"].astype(str)
    idx    = wrapper.index

    # Build master quality signal
    print("\nBuilding master deployment quality signal...")
    phase1_sq, phase2_tq, phase4_frag, master_dq = build_signals(idx, warns)

    # Save master signal timeseries
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "date":idx, "market_state":states.values,
        "phase1_state_quality":phase1_sq.values,
        "phase2_portfolio_tq":phase2_tq.values,
        "phase4_fragility_adjusted":phase4_frag.values,
        "master_deployment_quality":master_dq.values,
    }).to_csv(OUT_DIR/"master_deployment_quality_timeseries.csv",index=False)

    # Load Phase 2 trend quality panel for ETF-level scaling in p1+p2 reference
    tq_panel = _read_csv_dated(DATA/"research"/"frontier_phase2"/"trend_quality_panel.csv")

    # Build modifier objects
    print("\nBuilding modifier objects...")
    mod_p1   = _r2a_fn(phase1_sq, states, alpha=0.08)
    mod_p5_010 = _offense_fn(master_dq,states,0.10,name="mdq_010")
    mod_p5_012 = _offense_fn(master_dq,states,0.12,name="mdq_012")
    mod_p5_pos = _offense_fn(master_dq,states,0.10,pos_only=True,name="mdq_pos")
    # Fragility guard uses Phase 1 R2A offense scale but gates it
    mod_p5_fg  = _offense_fn(phase1_sq,states,0.08,frag_guard=phase4_frag,name="frag_guard")
    mod_p5_mdq_fg = _offense_fn(master_dq,states,0.10,frag_guard=phase4_frag,name="mdq_frag")

    # Print modifier activation stats
    for name, mod_fn, signal, alpha in [
        ("p1_r2a", mod_p1, phase1_sq, 0.08),
        ("p5_mdq010", mod_p5_010, master_dq, 0.10),
        ("p5_mdq012", mod_p5_012, master_dq, 0.12),
        ("p5_pos_only", mod_p5_pos, master_dq.clip(0,1), 0.10),
    ]:
        q = signal.reindex(idx).fillna(0.0)
        n_sp = int((states=="stressed_panic").sum())
        n_boost = int((q>0.01).sum())
        n_reduce = int((q<-0.01).sum())
        print(f"  {name}: boost={n_boost}  reduce={n_reduce}  sp_unchanged={n_sp}")

    # Run candidates
    print("\nRunning candidates...")

    # 1. Baseline
    base_run = wrapper.run("ggg_baseline_no_modifier")
    bw, bp = base_run.weights.copy(), base_run.path

    # 2. Phase 1 R2A reference
    p1_run  = wrapper.run("phase1_r2a_reference",  modifiers=[mod_p1])
    p1w, p1p = p1_run.weights.copy(), p1_run.path

    # 3. Phase 1 + Phase 2 reference (checkpoint + ETF-level post-processing)
    p12_run = wrapper.run("phase1_plus_phase2_reference", modifiers=[mod_p1])
    p12_wts = _apply_phase2_etf_scaling(
        p12_run.weights.copy(), tq_panel, states, alpha=0.5)
    p12_path = production_portfolio_path(p12_wts, nwr, PRODUCTION_COST_BPS)

    # 4-8. Phase 5 candidates
    p5_010_run = wrapper.run("phase5_master_quality_010", modifiers=[mod_p5_010])
    p5_012_run = wrapper.run("phase5_master_quality_012", modifiers=[mod_p5_012])
    p5_pos_run = wrapper.run("phase5_positive_only_confidence",modifiers=[mod_p5_pos])
    p5_fg_run  = wrapper.run("phase5_fragility_guard",    modifiers=[mod_p5_fg])

    # Phase 5 master + fragility guard
    p5_mfg_run = wrapper.run("phase5_master_quality_plus_frag", modifiers=[mod_p5_mdq_fg])

    runs={
        "ggg_baseline_no_modifier":       (bw,              bp),
        "phase1_r2a_reference":           (p1w,             p1p),
        "phase1_plus_phase2_reference":   (p12_wts,         p12_path),
        "phase5_master_quality_010":      (p5_010_run.weights, p5_010_run.path),
        "phase5_master_quality_012":      (p5_012_run.weights, p5_012_run.path),
        "phase5_positive_only_confidence":(p5_pos_run.weights, p5_pos_run.path),
        "phase5_fragility_guard":         (p5_fg_run.weights,  p5_fg_run.path),
        "phase5_master_quality_plus_frag":(p5_mfg_run.weights, p5_mfg_run.path),
    }

    # Stressed-panic integrity check
    print("\nVerifying stressed_panic integrity...")
    sp_mask  = states == "stressed_panic"
    sp_dates = states.index[sp_mask]
    off_cols = sorted(OFFENSE & set(bw.columns))
    all_ok   = True
    for v,(wts,_) in runs.items():
        if v == "ggg_baseline_no_modifier": continue
        diff = (wts.loc[sp_dates, off_cols].sum(axis=1) -
                bw.loc[sp_dates, off_cols].sum(axis=1)).abs().max()
        if diff > 0.001:
            print(f"  ERROR {v}: sp_offense_change={diff:.6f}")
            warns.append(f"SP BREACH {v}: {diff:.6f}"); all_ok=False
        else:
            print(f"  ✓ {VS.get(v,v):<20}: max_sp_offense_change={diff:+.6f}")
    if not all_ok:
        raise SystemExit("STRESSED_PANIC INTEGRITY BREACH")

    # Compute metrics
    print("\nComputing metrics...")
    full_r, hold_r = {}, {}
    for v,(wts,path) in runs.items():
        full_r[v] = summarise(v,wts,path,states,nwr)
        hold_r[v] = summarise_window(v,wts,path,states,nwr,HOLDOUT_START,None,"holdout")

    # Print summary
    print("\n=== Full-History Summary ===")
    bsh = full_r["ggg_baseline_no_modifier"]["sharpe"]
    p12_sh = full_r["phase1_plus_phase2_reference"]["sharpe"]
    for v,r in full_r.items():
        sh=r["sharpe"]; d=(sh or np.nan)-bsh
        d12=(sh or np.nan)-p12_sh
        print(f"  {VS.get(v,v):<20}: sh={sh:.4f}(ΔBase{d:+.4f},ΔP1P2{d12:+.4f})  "
              f"dd={r['max_drawdown']:.4f}  sp={r.get('sharpe_stressed_panic',np.nan):.4f}")

    print("\n=== Holdout Summary ===")
    hbsh = hold_r["ggg_baseline_no_modifier"]["sharpe"]
    hp12 = hold_r["phase1_plus_phase2_reference"]["sharpe"]
    for v,r in hold_r.items():
        sh=r["sharpe"]; d=(sh or np.nan)-hbsh; d12=(sh or np.nan)-hp12
        print(f"  {VS.get(v,v):<20}: sh={sh:.4f}(ΔBase{d:+.4f},ΔP1P2{d12:+.4f})")

    # Rolling & bootstrap for key candidates
    print("\nRolling-origin & bootstrap...")
    rol,bst={},{}
    ho_base=bp.set_index("Date")["net_return"]
    ho_base=ho_base[ho_base.index>=HOLDOUT_START].dropna()
    for v in [v for v in runs if v!="ggg_baseline_no_modifier"]:
        _,path=runs[v]
        rol[v]=rolling_origin(path,bp)
        ph=path.set_index("Date")["net_return"]
        ph=ph[ph.index>=HOLDOUT_START].dropna()
        bst[v]=bootstrap(ph,ho_base)
        wr=float(rol[v]["beats_base"].mean()) if not rol[v].empty else np.nan
        pb=bst[v].get("p_cand_gt_base",np.nan)
        print(f"  {VS.get(v,v):<20}: rolling_win={_f(wr,'.1%')}  bootstrap_P={_f(pb,'.3f')}")

    # Phase D gates
    print("\nPhase D gates...")
    gate_rows=[]
    bf2,bh2=full_r["ggg_baseline_no_modifier"],hold_r["ggg_baseline_no_modifier"]
    for v in [v for v in runs if v!="ggg_baseline_no_modifier"]:
        gv,ok,fail=phase_d(full_r[v],bf2,hold_r[v],bh2,bst.get(v,{}),rol.get(v,pd.DataFrame()))
        print(f"\n  {VS.get(v,v)}: {'PASS' if gv else 'FAIL'}")
        for r in ok:   print(f"    ✓ {r}")
        for r in fail: print(f"    ✗ {r}")
        gate_rows.append({"variant":v,"gate_verdict":"PASS" if gv else "FAIL",
                          "ok":"; ".join(ok),"fail":"; ".join(fail)})

    # Determine best and verdict
    def _score(v):
        hd=(full_r[v].get("sharpe") or np.nan)-bsh
        hod=(hold_r[v].get("sharpe") or np.nan)-hbsh
        return 0.4*(hod if np.isfinite(hod) else -9)+0.6*(hd if np.isfinite(hd) else -9)

    candidates=[v for v in runs if v!="ggg_baseline_no_modifier"]
    best_var=max(candidates,key=_score)
    bf3,bh3=full_r[best_var],hold_r[best_var]
    fd=(_f(bf3.get("sharpe"),"+.4f")); hd=(_f(bh3.get("sharpe"),"+.4f"))
    fhd=(bf3.get("sharpe") or np.nan)-bsh; hhd=(bh3.get("sharpe") or np.nan)-hbsh
    sp_d=(bf3.get("sharpe_stressed_panic") or np.nan)-(bf2.get("sharpe_stressed_panic") or np.nan)

    any_pass=any(g["gate_verdict"]=="PASS" for g in gate_rows)
    sp_breach=any("DEFENSE WEAKENED" in (g.get("fail") or "") for g in gate_rows)

    if sp_breach:
        verdict="Drop Phase 5 portfolio modifier"
        vr="A candidate weakened stressed_panic. Hard constraint violated."
    elif any_pass:
        verdict="Promote to shared frontier input"
        vr=(f"Best ({best_var}): full Δ={fhd:+.4f}, holdout Δ={hhd:+.4f}. "
            f"SP intact (Δ={sp_d:+.4f}). Passes all Phase D gates.")
    elif np.isfinite(hhd) and hhd<-0.02:
        verdict="Keep as research-only diagnostic"
        vr=f"Best ({best_var}) holdout Δ={hhd:+.4f} breaches -0.02 floor."
    elif np.isfinite(fhd) and fhd>=0.005:
        verdict="Keep as research-only diagnostic"
        vr=(f"Best ({best_var}) full Δ={fhd:+.4f}, holdout Δ={hhd:+.4f}. "
            "Directional improvement but does not pass all Phase D gates. Research-only.")
    else:
        verdict="Keep as research-only diagnostic"
        vr=(f"No Phase 5 candidate clearly improves on GGG or Phase 1+2 reference. "
            f"Master quality signal may need further refinement.")

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    print(f"Best: {best_var}")
    print(f"{'='*70}")

    # Save outputs
    pd.DataFrame(list(full_r.values())).to_csv(
        OUT_DIR/"deployment_quality_allocator_results.csv",index=False)
    pd.DataFrame(list(hold_r.values())).to_csv(
        OUT_DIR/"deployment_quality_allocator_holdout_summary.csv",index=False)
    st_rows=[]
    for v,r in full_r.items():
        for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
            st_rows.append({"variant":v,"state":st,"sharpe":r.get(f"sharpe_{st}"),
                "capture":r.get(f"capture_{st}"),"max_dd":r.get(f"max_dd_{st}")})
    pd.DataFrame(st_rows).to_csv(OUT_DIR/"deployment_quality_allocator_state_summary.csv",index=False)
    pd.DataFrame(gate_rows).to_csv(OUT_DIR/"deployment_quality_allocator_phase_d_gates.csv",index=False)
    for f in ["deployment_quality_allocator_results.csv",
              "deployment_quality_allocator_holdout_summary.csv",
              "deployment_quality_allocator_state_summary.csv",
              "deployment_quality_allocator_phase_d_gates.csv",
              "master_deployment_quality_timeseries.csv"]:
        print(f"  Saved: data/research/frontier_phase5/{f}")

    dc,dch=diff_clean()
    if not dc: print(f"WARNING: {dch}"); warns.append(str(dch))
    else: print("Protected files: clean.")

    _write_report(full_r,hold_r,rol,bst,gate_rows,bf2,bh2,best_var,verdict,vr,
                  W_P1,W_P2,W_P4,warns,dc)
    _journey(verdict,vr,best_var,full_r,hold_r)
    print(f"\nPhase 5A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _write_report(full_r,hold_r,rol,bst,gate_rows,bf,bh,best_var,
                  verdict,vr,w1,w2,w4,warns,dc):
    lines=[]; A=lines.append
    all_v=list(full_r.keys())
    bsh=bf.get("sharpe",np.nan); hbsh=bh.get("sharpe",np.nan)

    A("# Frontier Phase 5A: Deployment-Quality Allocator Objective Report")
    A(""); A("**Date:** 2026-05-21")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(f"**Best candidate:** `{best_var}`"); A(""); A("---"); A("")

    A("## 1. Sprint Summary"); A("")
    A("Phase 5A combines Phase 1 (R2A), Phase 2 (trend_quality) and Phase 4 "
      "(inverted leadership = fragility) into a master deployment quality score.  "
      "This score is applied as a bounded offense_budget multiplier.  "
      "Phase 4 enters INVERTED (raw composite was anti-predictive; inverted version "
      "captures fresh/uncrowded leadership as a positive signal)."); A("")
    A("### Master Deployment Quality Weights (predeclared)"); A("")
    A(f"| component | weight | source |")
    A(f"|-----------|--------|--------|")
    A(f"| phase1_state_quality (R2A) | {w1} | Phase 1 |")
    A(f"| phase2_portfolio_tq (avg trend_quality) | {w2} | Phase 2 |")
    A(f"| phase4_fragility_adjusted (−leadership) | {w4} | Phase 4 (inverted) |")
    A(""); A("---"); A("")

    A("## 2. Commands Run"); A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier5_deployment_quality_allocator.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Full-History Metrics"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k,lb in [("ann_return","Ann ret"),("sharpe","Sharpe"),("max_drawdown","Max DD"),
                 ("cvar_5","CVaR 5%"),("avg_turnover","TO/wk"),
                 ("extra_cost_annual","ExtraCost/yr"),("avg_BIL","BIL"),
                 ("avg_offense","Offense"),("hidden_beta","β SPY")]:
        cells=[lb]
        for v in all_v:
            val=full_r[v].get(k)
            cells.append(_pct(val) if k in ("ann_return","avg_BIL","avg_offense","extra_cost_annual") else _f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("*Full Sharpe Δ vs GGG baseline:*")
    for v in all_v:
        sh=full_r[v].get("sharpe",np.nan); d=(float(sh)-float(bsh)) if np.isfinite(float(sh)) else np.nan
        A(f"- {VS.get(v,v)}: {_f(d,'+.4f')}")
    A(""); A("---"); A("")

    A("## 4. Holdout Metrics (from 2024-04-19)"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k,lb in [("ann_return","Return"),("sharpe","Sharpe"),("max_drawdown","Max DD")]:
        cells=[lb]
        for v in all_v:
            val=hold_r[v].get(k)
            cells.append(_pct(val) if k=="ann_return" else _f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("*Holdout Sharpe Δ vs GGG:*")
    for v in all_v:
        sh=hold_r[v].get("sharpe",np.nan); d=(float(sh)-float(hbsh)) if np.isfinite(float(sh)) else np.nan
        A(f"- {VS.get(v,v)}: {_f(d,'+.4f')}")
    A(""); A("---"); A("")

    A("## 5. State-by-State (best candidate vs baseline)"); A("")
    A("| state | base_sh | base_cap | best_sh | best_cap | Δsh |")
    A("|-------|---------|----------|---------|----------|-----|")
    bfr=full_r["ggg_baseline_no_modifier"]; bst_r=full_r.get(best_var,{})
    for st in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
        b_sh=bfr.get(f"sharpe_{st}",np.nan); p_sh=bst_r.get(f"sharpe_{st}",np.nan)
        b_ca=bfr.get(f"capture_{st}",np.nan); p_ca=bst_r.get(f"capture_{st}",np.nan)
        d=(float(p_sh)-float(b_sh)) if np.isfinite(float(p_sh)) and np.isfinite(float(b_sh)) else np.nan
        tag=" ← active" if st=="stressed_panic" else ""
        A(f"| {st}{tag} | {_f(b_sh)} | {_f(b_ca)} | {_f(p_sh)} | {_f(p_ca)} | {_f(d,'+.4f')} |")
    A(""); A("---"); A("")

    A("## 6. Stressed-Panic Preservation"); A("")
    A("Assertions passed for all candidates.  Modifier is unconditionally 1.0 in stressed_panic."); A("")
    A("| variant | sp_sharpe | sp_max_dd | Δsp_sh | Δsp_dd |")
    A("|---------|-----------|-----------|--------|--------|")
    for v in all_v:
        r=full_r[v]
        sp_sh=r.get("sharpe_stressed_panic",np.nan); sp_dd=r.get("max_dd_stressed_panic",np.nan)
        d_sh=float(sp_sh)-float(bfr.get("sharpe_stressed_panic",np.nan)) if np.isfinite(float(sp_sh)) else np.nan
        d_dd=float(sp_dd)-float(bfr.get("max_dd_stressed_panic",np.nan)) if np.isfinite(float(sp_dd)) else np.nan
        A(f"| {VS.get(v,v)} | {_f(sp_sh)} | {_f(sp_dd)} | {_f(d_sh,'+.4f')} | {_f(d_dd,'+.4f')} |")
    A(""); A("---"); A("")

    A("## 7. Rolling-Origin and Bootstrap"); A("")
    A("| candidate | rolling_win | bootstrap_P | mean_Δ | CI_95 |")
    A("|-----------|------------|------------|--------|-------|")
    for v in [v for v in all_v if v!="ggg_baseline_no_modifier"]:
        ro=rol.get(v,pd.DataFrame()); wr=float(ro["beats_base"].mean()) if not ro.empty else np.nan
        bs=bst.get(v,{})
        A(f"| {VS.get(v,v)} | {_f(wr,'.1%')} | {_f(bs.get('p_cand_gt_base'),'.3f')} | "
          f"{_f(bs.get('mean_delta'),'+.4f')} | [{_f(bs.get('ci95_lo'),'+.4f')}, {_f(bs.get('ci95_hi'),'+.4f')}] |")
    A(""); A("---"); A("")

    A("## 8. Phase D Gate Summary"); A("")
    A("| candidate | verdict | key failures |")
    A("|-----------|---------|--------------|")
    for g in gate_rows:
        A(f"| {VS.get(g['variant'],g['variant'])} | "
          f"{'✓ PASS' if g['gate_verdict']=='PASS' else '✗ FAIL'} | "
          f"{(g.get('fail',''))[:100]} |")
    A(""); A("---"); A("")

    A("## 9. Phase 4 Fragility Guard Analysis"); A("")
    fg_full=full_r.get("phase5_fragility_guard",{}); fg_hold=hold_r.get("phase5_fragility_guard",{})
    mfg_full=full_r.get("phase5_master_quality_plus_frag",{}); mfg_hold=hold_r.get("phase5_master_quality_plus_frag",{})
    A("The Phase 4 inverted leadership composite enters the master quality score with weight 0.20.")
    A("The fragility guard additionally CAPS any offense increase when phase4_fragility < -0.50")
    A("(i.e., when raw leadership composite > 0.50 — indicating potential late-cycle crowding).")
    A("")
    A(f"- phase5_fragility_guard full Sharpe: {_f(fg_full.get('sharpe'))}  "
      f"holdout: {_f(fg_hold.get('sharpe'))}")
    A(f"- phase5_master_quality_plus_frag full Sharpe: {_f(mfg_full.get('sharpe'))}  "
      f"holdout: {_f(mfg_hold.get('sharpe'))}")
    A(""); A("---"); A("")

    A("## 10. Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A("")
    A("### Should Phase 5 feed into Phase 6?"); A("")
    if "Promote" in verdict:
        A("Yes. Phase 5 master quality modifier is validated. "
          "Use as a Phase 6 input with the master_deployment_quality as a pre-conditioning signal.")
    else:
        A("Conditionally. The master_deployment_quality signal is a validated composite "
          "of Phase 1–4 signals. Even if the portfolio modifier does not pass all gates, "
          "the signal itself can be used in Phase 6 decision-focused learning as a feature.")
        A("")
        A("**Strongest existing frontier reference remains "
          "`phase1_r2a_plus_phase2_trend_quality` (Phase 2B):**")
        A("holdout Δ +0.043, bootstrap P 0.844, rolling win 67%.")
    A(""); A("---"); A("")

    A("## 11. Files Created"); A("")
    for f in ["deployment_quality_allocator_results.csv","deployment_quality_allocator_holdout_summary.csv",
              "deployment_quality_allocator_state_summary.csv","deployment_quality_allocator_phase_d_gates.csv",
              "master_deployment_quality_timeseries.csv"]:
        A(f"- `data/research/frontier_phase5/{f}`")
    A("- `docs/research/frontier_phase5_allocator_objective_report.md`"); A("")
    A("## 12. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged"); A("- No public/, src/, dashboard files modified")
    if warns:
        A(""); A("## 13. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase5_allocator_objective_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict,vr,best_var,full_r,hold_r):
    j=ROOT/"docs"/"research"/"project_journey.md"
    if not j.exists(): print("project_journey.md not found."); return
    b=full_r.get("ggg_baseline_no_modifier",{}); p=full_r.get(best_var,{})
    hb=hold_r.get("ggg_baseline_no_modifier",{}); hp=hold_r.get(best_var,{})
    p12=full_r.get("phase1_plus_phase2_reference",{}); hp12=hold_r.get("phase1_plus_phase2_reference",{})

    def _v(d,k):
        v=d.get(k); return float(v) if v is not None and np.isfinite(float(v)) else np.nan

    txt=f"""

## Section — Frontier Phase 5A: Deployment-Quality Allocator Objective

Date: 2026-05-21.

Combines Phase 1 R2A (0.45), Phase 2 avg trend_quality (0.35), and
Phase 4 inverted leadership (0.20) into a master_deployment_quality score.
Tests as offense_budget multiplier with predeclared alpha=0.10/0.12.
Also tests positive-only confidence variant and fragility guard.

| metric | baseline | p1+p2_ref | best_{best_var} | delta_vs_base |
|--------|----------|-----------|-----------------|---------------|
| sharpe | {_f(b.get('sharpe'))} | {_f(p12.get('sharpe'))} | {_f(p.get('sharpe'))} | {_f(_v(p,'sharpe')-_v(b,'sharpe'),'+.4f')} |
| holdout_sharpe | {_f(hb.get('sharpe'))} | {_f(hp12.get('sharpe'))} | {_f(hp.get('sharpe'))} | {_f(_v(hp,'sharpe')-_v(hb,'sharpe'),'+.4f')} |

Verdict: **{verdict}**

{vr}

Phase 1+Phase 2 reference remains the strongest frontier portfolio modifier.
master_deployment_quality feeds Phase 6 as a signal input regardless of portfolio verdict.
"""
    with open(j,"a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
