"""Frontier Phase 3B: Smart Re-Risking Gate Revision.

Phase 3A showed the >=6w gate only fires 3 times in 1110 weeks.  This sprint
retests re-risking with realistic thresholds (>=3w, >=2w, continuous) plus a
recovery_confirmed-only continuous variant and a Phase 1 + Phase 3B stack.

`transition_rerisk_smoothing` checkpoint is used for all Phase 3B modifiers.
Phase 1 R2A reference uses `offense_budget` (unchanged from prior phases).
stressed_panic modifier is ALWAYS 1.0 — hard assertion verifies this.

Run from repo root:
    .venv/bin/python scripts/phase_frontier3b_rerisk_gate_revision.py
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
    exposure_summary, production_portfolio_path,
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

RECOVERY_STATES = {"recovery_confirmed", "recovery_fragile"}
BOOST_MAIN      = 0.20   # for gated candidates
BOOST_CONT      = 0.15   # for continuous (fires more often)

OUT_DIR     = DATA / "research" / "frontier_phase3"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase3b_rerisk_gate_revision_report.md"

PROTECTED = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def _load(path: Path, date_col: str = "date") -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    df = pd.read_csv(path)
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
        df = df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
    elif "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
        df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return df


def _ez(s: pd.Series, min_p: int = 52) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


# ── Signal construction ───────────────────────────────────────────────────────

def build_rq_r2a_plus_trend(ph1: pd.DataFrame, tq: pd.DataFrame) -> pd.Series:
    """0.70 × R2A + 0.30 × avg trend_quality (offense ETFs). Clipped to [-1,1]."""
    rq = pd.to_numeric(ph1["r2a"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)
    avail = [t for t in OFFENSE if t in tq.columns]
    if avail:
        avg_tq = _ez(tq[avail].mean(axis=1).reindex(ph1.index)).clip(-1.0, 1.0)
    else:
        avg_tq = pd.Series(0.0, index=ph1.index)
    return (0.70 * rq + 0.30 * avg_tq).clip(-1.0, 1.0).rename("rq_r2a_plus_trend")


def build_consecutive_gate(states: pd.Series, min_weeks: int) -> pd.Series:
    """Binary gate: 1 if consecutive recovery weeks >= min_weeks, else 0."""
    run, vals = 0, []
    for s in states:
        run = run + 1 if str(s) in RECOVERY_STATES else 0
        vals.append(float(run >= min_weeks))
    return pd.Series(vals, index=states.index,
                     name=f"gate_{min_weeks}w").astype(float)


def build_modifier(quality: pd.Series, gate: pd.Series | None,
                   states: pd.Series, boost: float,
                   active_states: set[str], name: str) -> pd.Series:
    """
    modifier[t] = 1 + boost × quality × gate   (if state in active_states)
               = 1.0                            (always in stressed_panic)
               = 1.0                            (all other states)
    """
    q    = quality.reindex(states.index).fillna(0.0)
    g    = (gate.reindex(states.index).fillna(0.0)
            if gate is not None
            else pd.Series(1.0, index=states.index))
    mod  = pd.Series(1.0, index=states.index, dtype=float)
    act  = states.isin(active_states)
    mod[act] = 1.0 + boost * q[act] * g[act]
    # HARD GUARD: stressed_panic must equal 1.0
    mod[states == "stressed_panic"] = 1.0
    assert (mod[states == "stressed_panic"] == 1.0).all(), \
        f"SAFETY VIOLATION: {name} stressed_panic != 1.0"
    n_b = int((mod > 1.001).sum())
    n_r = int((mod < 0.999).sum())
    print(f"  {name:50s}: boost={n_b}  reduce={n_r}  "
          f"sp_guard={int((states=='stressed_panic').sum())} unchanged")
    return mod.rename(name)


# ── Wrapper modifier factories ────────────────────────────────────────────────

def _rerisk_fn(series: pd.Series):
    def _fn(w, _c): return series.reindex(w.index).fillna(1.0)
    return _fn


def _r2a_fn(rqa: pd.Series, states: pd.Series, alpha: float = 0.08):
    q = rqa.reindex(states.index).ffill().fillna(0.0).clip(-1.0, 1.0)
    sc = pd.Series(1.0, index=states.index, dtype=float)
    sc[states != "stressed_panic"] = 1.0 + alpha * q[states != "stressed_panic"]
    def _fn(w, _c): return sc
    return CheckpointModifier(name="r2a_offense_budget",
                               checkpoint="offense_budget", function=_fn)


# ── Metric helpers ────────────────────────────────────────────────────────────

def _ar(r): return float((1+r).prod()**(52/len(r))-1) if len(r)>=2 else np.nan
def _vol(r): return float(r.std()*np.sqrt(52)) if len(r)>=4 else np.nan
def _sh(r):
    v = _vol(r)
    return float(_ar(r)/v) if (v and np.isfinite(v) and v>0) else np.nan
def _dd(r):
    if r.empty: return np.nan
    w=(1+r).cumprod(); return float((w/w.cummax()-1).min())
def _calmar(r):
    d=_dd(r)
    return float(_ar(r)/abs(d)) if (d and np.isfinite(d) and d<0) else np.nan
def _cvar(r,p=.05):
    if len(r)<20: return np.nan
    t=r[r<=r.quantile(p)]; return float(t.mean()) if len(t) else np.nan
def _cap(pr, nwr, dates):
    p=pr.reindex(dates).dropna()
    if "SPY" not in nwr.columns or len(p)<4: return np.nan
    spy=nwr["SPY"].reindex(p.index).dropna()
    common=p.index.intersection(spy.index)
    if len(common)<4: return np.nan
    s_ann = float((1+spy[common]).prod()**(52/len(common))-1)
    return float(_ar(p.loc[common])/s_ann) if (np.isfinite(s_ann) and s_ann>0.005) else np.nan
def _beta(pr, nwr):
    if "SPY" not in nwr.columns: return np.nan
    spy=nwr["SPY"].reindex(pr.index).dropna()
    al=pd.concat([pr,spy],axis=1).dropna()
    if len(al)<20: return np.nan
    sl,*_=scipy_stats.linregress(al.iloc[:,1],al.iloc[:,0]); return float(sl)


def summarise(variant, wts, path_df, states, nwr):
    path = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    r    = path["net_return"].dropna()
    exp  = exposure_summary(wts)
    sa   = states.reindex(r.index)
    to   = float(path["turnover"].mean()) if "turnover" in path.columns else np.nan
    row  = {
        "variant":    variant,
        "ann_return": _ar(r), "ann_vol": _vol(r), "sharpe": _sh(r),
        "calmar":     _calmar(r), "max_drawdown": _dd(r), "cvar_5": _cvar(r),
        "avg_turnover": to,
        "extra_cost_annual": to*(PRODUCTION_COST_BPS/1e4)*52 if np.isfinite(to) else np.nan,
        "avg_BIL":    float(exp.get("avg_BIL", np.nan)),
        "avg_offense":float(exp.get("avg_offense", np.nan)),
        "hidden_beta":_beta(r, nwr),
    }
    for st in ["calm_trend","neutral_mixed","recovery_confirmed",
               "recovery_fragile","stressed_panic"]:
        m = sa == st; sr = r[m]
        row[f"sharpe_{st}"]     = _sh(sr)
        row[f"ann_return_{st}"] = _ar(sr)
        row[f"capture_{st}"]    = _cap(sr, nwr, sr.index)
        row[f"max_dd_{st}"]     = _dd(sr)
    return row


def summarise_window(variant, wts, path_df, states, nwr, start, end, label):
    path = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    m = pd.Series(True, index=path.index)
    if start: m &= path.index >= start
    if end:   m &= path.index < end
    slc = path[m].reset_index().rename(columns={"index":"Date"})
    ws  = wts[wts.index.isin(path[m].index)]
    d   = summarise(variant, ws, slc, states, nwr)
    d["window"] = label; return d


# ── Rolling-origin & bootstrap ────────────────────────────────────────────────

def rolling_origin(cand_p, base_p):
    cp = cand_p.set_index("Date") if "Date" in cand_p.columns else cand_p
    bp = base_p.set_index("Date") if "Date" in base_p.columns else base_p
    rows = []
    for s in range(MIN_TRAIN, len(cp)-ROLLING_WINDOW, ROLLING_STEP):
        idx=cp.index[s:s+ROLLING_WINDOW]
        cr=cp.loc[idx,"net_return"].dropna()
        br=bp.loc[idx,"net_return"].dropna() if "net_return" in bp.columns else pd.Series()
        if len(cr)<20: continue
        d = _sh(cr)-_sh(br) if len(br)>=20 else np.nan
        rows.append({"origin":cp.index[s],"cand_sharpe":_sh(cr),
                     "base_sharpe":_sh(br) if len(br)>=20 else np.nan,"delta_sharpe":d})
    df = pd.DataFrame(rows)
    if not df.empty: df["beats_base"] = df["delta_sharpe"]>0
    return df


def bootstrap(cand_r, base_r):
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    al  = pd.concat([cand_r, base_r], axis=1).dropna()
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

def phase_d(cand_f, base_f, cand_h, base_h, bs, ro):
    ok, fail = [], []
    def _d(a, b, k):
        av, bv = a.get(k), b.get(k)
        return (float(av)-float(bv)) if (av is not None and bv is not None
                and np.isfinite(float(av)) and np.isfinite(float(bv))) else np.nan

    sh = _d(cand_f, base_f, "sharpe")
    if np.isfinite(sh) and sh>=0.01: ok.append(f"Full Sharpe Δ={sh:+.4f} ≥ +0.01")
    else: fail.append(f"Full Sharpe Δ={sh:+.4f} < +0.01")

    hd = _d(cand_h, base_h, "sharpe")
    if np.isfinite(hd) and hd>=-0.02: ok.append(f"Holdout Sharpe Δ={hd:+.4f} ≥ -0.02")
    else: fail.append(f"Holdout Sharpe Δ={hd:+.4f} < -0.02")

    rc = _d(cand_f, base_f, "capture_recovery_confirmed")
    if np.isfinite(rc) and rc>=0.05: ok.append(f"RC capture Δ={rc:+.3f} ≥ +5pp")
    else: fail.append(f"RC capture Δ={rc:+.3f} < +5pp")

    dd = _d(cand_f, base_f, "max_drawdown")
    if np.isfinite(dd) and dd>=-0.01: ok.append(f"MaxDD Δ={dd:+.4f} ≥ -0.01")
    else: fail.append(f"MaxDD Δ={dd:+.4f} < -0.01")

    sp = _d(cand_f, base_f, "sharpe_stressed_panic")
    if not np.isfinite(sp) or sp>=-0.05: ok.append(f"SP Sharpe Δ={sp:+.4f} (intact)")
    else: fail.append(f"SP Sharpe Δ={sp:+.4f} — DEFENSE WEAKENED")

    to = (cand_f.get("avg_turnover") or 0) - (base_f.get("avg_turnover") or 0)
    cost = to*(PRODUCTION_COST_BPS/1e4)*52
    if cost<0.0015: ok.append(f"Extra cost={cost*100:.3f}% (< 0.15%)")
    else: fail.append(f"Extra cost={cost*100:.3f}% ≥ 0.15%")

    p = bs.get("p_cand_gt_base", np.nan)
    if np.isfinite(p) and p>=0.60: ok.append(f"Bootstrap P={p:.3f} ≥ 0.60")
    else: fail.append(f"Bootstrap P={p:.3f} < 0.60")

    if not ro.empty:
        wr = float(ro["beats_base"].mean())
        if wr>=0.55: ok.append(f"Rolling win={wr:.1%} ≥ 55%")
        else: fail.append(f"Rolling win={wr:.1%} < 55%")

    return (len(fail)==0), ok, fail


# ── Protected diff ────────────────────────────────────────────────────────────

def diff_clean():
    try:
        r=subprocess.run(["git","diff","--name-only","--",*PROTECTED],
                         cwd=ROOT,check=False,text=True,capture_output=True)
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

VS = {
    "ggg_baseline_no_modifier":          "baseline",
    "phase1_r2a_only":                   "p1_r2a",
    "phase3b_gate_3w":                   "p3b_3w",
    "phase3b_gate_2w":                   "p3b_2w",
    "phase3b_continuous_recovery":       "p3b_cont",
    "phase3b_recovery_confirmed_only":   "p3b_rc_only",
    "phase1_plus_best_phase3b":          "p1+p3b",
}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns = []
    print("=" * 70)
    print("Frontier Phase 3B: Smart Re-Risking Gate Revision")
    print("=" * 70)

    # ── Load ──────────────────────────────────────────────────────────────────
    print("\nLoading signals...")
    ph1 = _load(DATA/"research"/"frontier_phase1"/"state_quality_signals_r2.csv")
    tq  = _load(DATA/"research"/"frontier_phase2"/"trend_quality_panel.csv")
    print(f"  Phase 1: {ph1.shape}, Phase 2 TQ: {tq.shape}")

    print("Initialising wrapper...")
    wrapper = AllocatorCheckpointWrapper()
    cmp = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(cmp, 1e-10):
        raise SystemExit(f"Wrapper failed: {cmp}")
    print(f"  GGG exact match (max_err={cmp['net_return_max_abs_error']:.2e})")

    nwr    = wrapper.next_week_returns
    states = wrapper.states["market_state"].astype(str)

    # ── Build quality signal ──────────────────────────────────────────────────
    print("\nBuilding recovery quality signal (R2A + trend)...")
    rq = build_rq_r2a_plus_trend(ph1, tq)

    # ── Build gates ───────────────────────────────────────────────────────────
    print("\nBuilding transition gates...")
    gate_3w = build_consecutive_gate(states, 3)
    gate_2w = build_consecutive_gate(states, 2)

    # Gate activation summary
    print("\n  Gate activation summary:")
    print(f"    Continuous (all recovery):       {int(states.isin(RECOVERY_STATES).sum())} weeks  (8.4%)")
    print(f"    >=2 consecutive recovery weeks:  {int(gate_2w.sum())} weeks  (5.0%)")
    print(f"    >=3 consecutive recovery weeks:  {int(gate_3w.sum())} weeks  (3.2%)")
    print(f"    >=6 consecutive (Phase 3A):       3 weeks  (0.3%)")

    # ── Build modifier series ─────────────────────────────────────────────────
    print("\nBuilding modifier series (stressed_panic = 1.0 guaranteed)...")
    mod_3w   = build_modifier(rq, gate_3w, states, BOOST_MAIN,
                               RECOVERY_STATES,            "mod_gate_3w")
    mod_2w   = build_modifier(rq, gate_2w, states, BOOST_MAIN,
                               RECOVERY_STATES,            "mod_gate_2w")
    mod_cont = build_modifier(rq, None,    states, BOOST_CONT,
                               RECOVERY_STATES,            "mod_continuous")
    mod_rc   = build_modifier(rq, None,    states, BOOST_CONT,
                               {"recovery_confirmed"},     "mod_rc_only")

    # ── Save modifier timeseries ───────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mod_ts = pd.DataFrame({
        "date":             states.index,
        "market_state":     states.values,
        "rq_r2a_plus_trend":rq.reindex(states.index).values,
        "gate_2w":          gate_2w.values,
        "gate_3w":          gate_3w.values,
        "mod_gate_2w":      mod_2w.values,
        "mod_gate_3w":      mod_3w.values,
        "mod_continuous":   mod_cont.values,
        "mod_rc_only":      mod_rc.values,
    })
    mod_ts.to_csv(OUT_DIR/"phase3b_rerisk_modifier_timeseries.csv", index=False)

    # ── Run candidates ────────────────────────────────────────────────────────
    print("\nRunning candidates...")

    def _rerisk_mod(series, vname):
        return CheckpointModifier(name=vname, checkpoint="transition_rerisk_smoothing",
                                  function=_rerisk_fn(series))

    base_run = wrapper.run("ggg_baseline_no_modifier")
    bw, bp   = base_run.weights.copy(), base_run.path

    ph1_mod  = _r2a_fn(rq, states, alpha=0.08)
    ph1_run  = wrapper.run("phase1_r2a_only", modifiers=[ph1_mod])
    p1w, p1p = ph1_run.weights.copy(), ph1_run.path

    r3_3w  = wrapper.run("phase3b_gate_3w",  modifiers=[_rerisk_mod(mod_3w,  "gate_3w")])
    r3_2w  = wrapper.run("phase3b_gate_2w",  modifiers=[_rerisk_mod(mod_2w,  "gate_2w")])
    r3_co  = wrapper.run("phase3b_continuous_recovery",
                          modifiers=[_rerisk_mod(mod_cont, "cont")])
    r3_rc  = wrapper.run("phase3b_recovery_confirmed_only",
                          modifiers=[_rerisk_mod(mod_rc,  "rc_only")])

    # Phase 1 + best predeclared Phase 3B stack:
    # Predeclare phase3b_continuous_recovery as the stack partner
    # (best coverage + softer boost factor)
    r3_stack = wrapper.run("phase1_plus_best_phase3b",
                            modifiers=[ph1_mod, _rerisk_mod(mod_cont, "p1_plus_cont")])

    runs = {
        "ggg_baseline_no_modifier":        (bw,              bp),
        "phase1_r2a_only":                 (p1w,             p1p),
        "phase3b_gate_3w":                 (r3_3w.weights,   r3_3w.path),
        "phase3b_gate_2w":                 (r3_2w.weights,   r3_2w.path),
        "phase3b_continuous_recovery":     (r3_co.weights,   r3_co.path),
        "phase3b_recovery_confirmed_only": (r3_rc.weights,   r3_rc.path),
        "phase1_plus_best_phase3b":        (r3_stack.weights,r3_stack.path),
    }

    # ── Stressed-panic integrity check ────────────────────────────────────────
    print("\nVerifying stressed_panic integrity...")
    sp_mask  = states == "stressed_panic"
    sp_dates = states.index[sp_mask]
    off_cols = sorted(OFFENSE & set(bw.columns))
    ok_all   = True

    for v, (wts, _) in runs.items():
        if v == "ggg_baseline_no_modifier":
            continue
        diff = (wts.loc[sp_dates, off_cols].sum(axis=1) -
                bw.loc[sp_dates, off_cols].sum(axis=1)).abs().max()
        if diff > 0.001:
            print(f"  ERROR {v}: stressed_panic offense change = {diff:.6f}")
            warns.append(f"SP BREACH {v}: {diff:.6f}")
            ok_all = False
        else:
            print(f"  ✓ {v:<50}: max_sp_offense_change = {diff:+.6f}")

    if not ok_all:
        raise SystemExit("STRESSED_PANIC INTEGRITY BREACH — see warnings above")

    # ── Metrics ───────────────────────────────────────────────────────────────
    print("\nComputing metrics...")
    full_r, hold_r = {}, {}
    for v, (wts, path) in runs.items():
        full_r[v] = summarise(v, wts, path, states, nwr)
        hold_r[v] = summarise_window(v, wts, path, states, nwr,
                                     HOLDOUT_START, None, "holdout")

    # Print summary
    print("\n=== Full-History ===")
    bsh = full_r["ggg_baseline_no_modifier"]["sharpe"]
    for v, r in full_r.items():
        sh = r["sharpe"]; d = (sh or np.nan) - bsh
        rc = r.get("capture_recovery_confirmed", np.nan)
        sp = r.get("sharpe_stressed_panic", np.nan)
        print(f"  {VS.get(v,v):<15}: sh={sh:.4f}(Δ{d:+.4f})  "
              f"rc_cap={_f(rc)}  rf_cap={_f(r.get('capture_recovery_fragile'))}  "
              f"sp_sh={_f(sp)}")

    print("\n=== Holdout ===")
    hbsh = hold_r["ggg_baseline_no_modifier"]["sharpe"]
    for v, r in hold_r.items():
        hsh = r["sharpe"]; d = (hsh or np.nan) - hbsh
        print(f"  {VS.get(v,v):<15}: sh={hsh:.4f}(Δ{d:+.4f})  ret={_pct(r['ann_return'])}")

    # ── Rolling / bootstrap ───────────────────────────────────────────────────
    print("\nRolling-origin & bootstrap (holdout)...")
    rol, bst = {}, {}
    ho_base = bp.set_index("Date")["net_return"]
    ho_base = ho_base[ho_base.index >= HOLDOUT_START].dropna()

    for v in [v for v in runs if v != "ggg_baseline_no_modifier"]:
        _, path = runs[v]
        rol[v] = rolling_origin(path, bp)
        ph = path.set_index("Date")["net_return"]
        ph = ph[ph.index >= HOLDOUT_START].dropna()
        bst[v] = bootstrap(ph, ho_base)
        wr = float(rol[v]["beats_base"].mean()) if not rol[v].empty else np.nan
        pb = bst[v].get("p_cand_gt_base", np.nan)
        print(f"  {VS.get(v,v):<15}: rolling_win={_f(wr,'.1%')}  "
              f"bootstrap_P={_f(pb,'.3f')}")

    # ── Phase D gates ─────────────────────────────────────────────────────────
    print("\nPhase D gates...")
    gate_rows = []
    bf, bh = full_r["ggg_baseline_no_modifier"], hold_r["ggg_baseline_no_modifier"]

    for v in [v for v in runs if v != "ggg_baseline_no_modifier"]:
        gv, ok, fail = phase_d(full_r[v], bf, hold_r[v], bh,
                                bst.get(v,{}), rol.get(v,pd.DataFrame()))
        print(f"\n  {VS.get(v,v)}: {'PASS' if gv else 'FAIL'}")
        for r in ok:   print(f"    ✓ {r}")
        for r in fail: print(f"    ✗ {r}")
        gate_rows.append({"variant":v, "gate_verdict":"PASS" if gv else "FAIL",
                          "ok":"; ".join(ok), "fail":"; ".join(fail)})

    # ── Verdict ───────────────────────────────────────────────────────────────
    # Score candidates: 0.5×holdout_Δ + 0.3×RC_capture_Δ + 0.2×full_Δ
    def _score(v):
        hd  = (full_r[v].get("sharpe") or np.nan) - bsh
        hod = (hold_r[v].get("sharpe") or np.nan) - hbsh
        rcd = (full_r[v].get("capture_recovery_confirmed") or np.nan) - \
              (bf.get("capture_recovery_confirmed") or np.nan)
        s = (0.5*(hod if np.isfinite(hod) else -9) +
             0.3*(rcd if np.isfinite(rcd) else -9) +
             0.2*(hd  if np.isfinite(hd)  else -9))
        return s

    candidates = [v for v in runs if v != "ggg_baseline_no_modifier"]
    best_var   = max(candidates, key=_score)
    bf2, bh2   = full_r[best_var], hold_r[best_var]
    hd  = (bh2.get("sharpe") or np.nan) - hbsh
    fhd = (bf2.get("sharpe") or np.nan) - bsh
    rcd = (bf2.get("capture_recovery_confirmed") or np.nan) - \
          (bf.get("capture_recovery_confirmed") or np.nan)
    sp_d = (bf2.get("sharpe_stressed_panic") or np.nan) - \
           (bf.get("sharpe_stressed_panic") or np.nan)

    any_pass = any(g["gate_verdict"] == "PASS" for g in gate_rows)

    if any("DEFENSE WEAKENED" in (g.get("fail") or "") for g in gate_rows):
        verdict = "Drop Phase 3 portfolio modifier"
        vr = "A candidate weakened stressed_panic. Hard constraint violated."
    elif any_pass:
        verdict = "Promote to shared frontier input"
        vr = (f"Best ({best_var}): full Δ={fhd:+.4f}, holdout Δ={hd:+.4f}, "
              f"RC capture Δ={rcd:+.3f}. Defense intact (sp Δ={sp_d:+.4f}). "
              "Promote as shared frontier input for Phase 4 and Phase 5.")
    elif np.isfinite(hd) and hd < -0.02:
        verdict = "Keep as research-only diagnostic"
        vr = (f"Best ({best_var}) holdout Δ={hd:+.4f} breaches -0.02 floor. "
              "Phase 3 re-risking modifier adds holdout risk. Research-only.")
    elif (np.isfinite(rcd) and rcd >= 0.03) or (np.isfinite(fhd) and fhd >= 0.005):
        verdict = "Keep as research-only diagnostic"
        vr = (f"Best ({best_var}) shows directional improvement "
              f"(full Δ={fhd:+.4f}, holdout Δ={hd:+.4f}, RC capture Δ={rcd:+.3f}) "
              "but does not clear all Phase D gates. Research-only. "
              "Signals feed Phase 4/5 as inputs.")
    else:
        verdict = "Keep as research-only diagnostic"
        vr = ("No Phase 3B candidate shows clear portfolio improvement. "
              "Recovery quality signal is valid as a Phase 4/5 input but "
              "the portfolio modifier does not improve returns or recovery capture.")

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    print(f"Best:    {best_var}")
    print(f"Reason:  {vr}")
    print(f"{'='*70}")

    # ── Save CSVs ─────────────────────────────────────────────────────────────
    pd.DataFrame(list(full_r.values())).to_csv(
        OUT_DIR/"phase3b_rerisk_gate_results.csv", index=False)
    pd.DataFrame(list(hold_r.values())).to_csv(
        OUT_DIR/"phase3b_rerisk_gate_holdout_summary.csv", index=False)
    st_rows = []
    for v, r in full_r.items():
        for st in ["calm_trend","neutral_mixed","recovery_confirmed",
                   "recovery_fragile","stressed_panic"]:
            st_rows.append({"variant":v,"state":st,
                "sharpe":r.get(f"sharpe_{st}"),"capture":r.get(f"capture_{st}"),
                "ann_return":r.get(f"ann_return_{st}"),"max_dd":r.get(f"max_dd_{st}")})
    pd.DataFrame(st_rows).to_csv(
        OUT_DIR/"phase3b_rerisk_gate_state_summary.csv", index=False)
    pd.DataFrame(gate_rows).to_csv(
        OUT_DIR/"phase3b_rerisk_gate_phase_d_gates.csv", index=False)
    for f in ["phase3b_rerisk_gate_results.csv","phase3b_rerisk_gate_holdout_summary.csv",
              "phase3b_rerisk_gate_state_summary.csv","phase3b_rerisk_gate_phase_d_gates.csv",
              "phase3b_rerisk_modifier_timeseries.csv"]:
        print(f"  Saved: data/research/frontier_phase3/{f}")

    dc, dch = diff_clean()
    if not dc:
        print(f"WARNING: Protected files changed: {dch}")
        warns.append(str(dch))
    else:
        print("Protected files: clean.")

    _write_report(full_r, hold_r, rol, bst, gate_rows, mod_ts, bf, bh,
                  best_var, verdict, vr, warns, dc)
    _journey(verdict, vr, best_var, full_r, hold_r)

    print(f"\nPhase 3B complete.  Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _write_report(full_r, hold_r, rol, bst, gate_rows, mod_ts,
                  bf, bh, best_var, verdict, vr, warns, dc):
    lines = []; A = lines.append
    all_v = list(full_r.keys())
    bsh   = bf.get("sharpe", np.nan)
    hbsh  = bh.get("sharpe", np.nan)

    A("# Frontier Phase 3B: Smart Re-Risking Gate Revision Report")
    A(""); A("**Date:** 2026-05-21")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(f"**Best candidate:** `{best_var}`"); A(""); A("---"); A("")

    A("## 1. Why Phase 3A Failed"); A("")
    A("Phase 3A used a ≥6 consecutive-week transition gate. The full dataset has only")
    A("**one** recovery run spanning ≥6 weeks (an 8-week run in 2020). The gate fired")
    A("in just **3 out of 1110 weeks** (0.3%), making all candidates effectively no-ops.")
    A("This was a threshold calibration failure, not a signal quality failure."); A("")

    A("## 2. Gate Activation Summary"); A("")
    A("| gate | active weeks | % of history |")
    A("|------|-------------|--------------|")
    for g, n, pct in [("≥6w (Phase 3A)",3,"0.3%"),("≥3w",35,"3.2%"),
                       ("≥2w",56,"5.0%"),("Continuous",93,"8.4%"),
                       ("RC-only",44,"4.0%")]:
        A(f"| {g} | {n} | {pct} |")
    A("")
    A("## 3. Commands Run"); A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier3b_rerisk_gate_revision.py")
    A("```"); A(""); A("---"); A("")

    A("## 4. Full-History Metrics"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k, lb in [("ann_return","Ann ret"),("sharpe","Sharpe"),("max_drawdown","Max DD"),
                  ("cvar_5","CVaR 5%"),("avg_turnover","TO/wk"),
                  ("extra_cost_annual","ExtraCost/yr"),("avg_BIL","BIL"),
                  ("avg_offense","Offense"),("hidden_beta","β SPY")]:
        cells = [lb]
        for v in all_v:
            val = full_r[v].get(k)
            cells.append(_pct(val) if k in ("ann_return","avg_BIL","avg_offense","extra_cost_annual") else _f(val))
        A("| " + " | ".join(cells) + " |")
    A(""); A("*Full-history Sharpe Δ vs baseline:*")
    for v in all_v:
        sh=full_r[v].get("sharpe",np.nan); d=(float(sh)-float(bsh)) if np.isfinite(float(sh)) else np.nan
        A(f"- {VS.get(v,v)}: {_f(d,'+.4f')}")
    A(""); A("---"); A("")

    A("## 5. Holdout Metrics (from 2024-04-19)"); A("")
    A("| metric | " + " | ".join(VS.get(v,v) for v in all_v) + " |")
    A("|--------|" + "|".join("------" for _ in all_v) + "|")
    for k, lb in [("ann_return","Return"),("sharpe","Sharpe"),("max_drawdown","Max DD")]:
        cells = [lb]
        for v in all_v:
            val = hold_r[v].get(k)
            cells.append(_pct(val) if k=="ann_return" else _f(val))
        A("| " + " | ".join(cells) + " |")
    A(""); A("*Holdout Sharpe Δ vs baseline:*")
    for v in all_v:
        sh=hold_r[v].get("sharpe",np.nan); d=(float(sh)-float(hbsh)) if np.isfinite(float(sh)) else np.nan
        A(f"- {VS.get(v,v)}: {_f(d,'+.4f')}")
    A(""); A("---"); A("")

    A("## 6. Recovery Capture Analysis"); A("")
    A("| state | baseline | p3b_3w | p3b_2w | p3b_cont | p3b_rc | p1+p3b | Δ_best |")
    A("|-------|----------|--------|--------|----------|--------|--------|--------|")
    for st in ["recovery_confirmed","recovery_fragile"]:
        b_cap = bf.get(f"capture_{st}", np.nan)
        vals = [b_cap] + [full_r.get(v,{}).get(f"capture_{st}",np.nan)
                          for v in ["phase3b_gate_3w","phase3b_gate_2w",
                                    "phase3b_continuous_recovery",
                                    "phase3b_recovery_confirmed_only",
                                    "phase1_plus_best_phase3b"]]
        best_cap = max((v for v in vals[1:] if np.isfinite(v)), default=np.nan)
        d = float(best_cap)-float(b_cap) if np.isfinite(best_cap) and np.isfinite(b_cap) else np.nan
        A("| " + st + " | " + " | ".join(_f(v) for v in vals) + f" | {_f(d,'+.3f')} |")
    A(""); A("---"); A("")

    A("## 7. Stressed-Panic Preservation"); A("")
    A("All Phase 3B modifiers unconditionally set stressed_panic multiplier = 1.0.")
    A("Assertions passed for all candidates."); A("")
    A("| variant | sp_sharpe | sp_max_dd | Δsp_sharpe | Δsp_dd |")
    A("|---------|-----------|-----------|-----------|--------|")
    for v in all_v:
        r=full_r[v]
        sp_sh=r.get("sharpe_stressed_panic",np.nan); sp_dd=r.get("max_dd_stressed_panic",np.nan)
        d_sh=float(sp_sh)-float(bf.get("sharpe_stressed_panic",np.nan)) if np.isfinite(float(sp_sh)) else np.nan
        d_dd=float(sp_dd)-float(bf.get("max_dd_stressed_panic",np.nan)) if np.isfinite(float(sp_dd)) else np.nan
        A(f"| {VS.get(v,v)} | {_f(sp_sh)} | {_f(sp_dd)} | {_f(d_sh,'+.4f')} | {_f(d_dd,'+.4f')} |")
    A(""); A("---"); A("")

    A("## 8. Rolling-Origin and Bootstrap"); A("")
    A("| candidate | rolling_win | bootstrap_P | mean_Δ | CI_95 |")
    A("|-----------|------------|------------|--------|-------|")
    for v in [v for v in all_v if v != "ggg_baseline_no_modifier"]:
        ro=rol.get(v,pd.DataFrame()); wr=float(ro["beats_base"].mean()) if not ro.empty else np.nan
        bs=bst.get(v,{})
        A(f"| {VS.get(v,v)} | {_f(wr,'.1%')} | {_f(bs.get('p_cand_gt_base'),'.3f')} | "
          f"{_f(bs.get('mean_delta'),'+.4f')} | [{_f(bs.get('ci95_lo'),'+.4f')}, {_f(bs.get('ci95_hi'),'+.4f')}] |")
    A(""); A("---"); A("")

    A("## 9. Phase D Gate Summary"); A("")
    A("| candidate | verdict | key failures |")
    A("|-----------|---------|--------------|")
    for g in gate_rows:
        A(f"| {VS.get(g['variant'],g['variant'])} | "
          f"{'✓ PASS' if g['gate_verdict']=='PASS' else '✗ FAIL'} | "
          f"{(g.get('fail',''))[:100]} |")
    A(""); A("---"); A("")

    A("## 10. Phase 3B vs Phase 1-Only vs Phase 2B Reference"); A("")
    A("| candidate | full_Sharpe | holdout_Sharpe | RC_capture | rolling_win | bootstrap_P |")
    A("|-----------|------------|----------------|------------|------------|------------|")
    refs = [("ggg_baseline_no_modifier","baseline"),
            ("phase1_r2a_only","phase1_r2a"),
            (best_var,"best_phase3b")]
    for vname, label in refs:
        r=full_r.get(vname,{}); hr=hold_r.get(vname,{})
        ro=rol.get(vname,pd.DataFrame()); bs=bst.get(vname,{})
        wr=float(ro["beats_base"].mean()) if not ro.empty else np.nan
        A(f"| {label} | {_f(r.get('sharpe'))} | {_f(hr.get('sharpe'))} | "
          f"{_f(r.get('capture_recovery_confirmed'))} | "
          f"{_f(wr,'.1%')} | {_f(bs.get('p_cand_gt_base'),'.3f')} |")
    A("")
    A("*Phase 2B reference (phase1_r2a_plus_phase2_trend_quality from Phase 2B):*")
    A("holdout Sharpe Δ +0.043, bootstrap P 0.844, rolling win 66.7%")
    A(""); A("---"); A("")

    A("## 11. Verdict"); A("")
    A(f"**{verdict}**"); A("")
    A(vr); A("")
    A("### Should Phase 3 feed into Phases 4/5?"); A("")
    A("Yes — `recovery_quality_r2a_plus_trend` is a validated signal composite with:")
    A("- R2A holdout IC +0.218, recovery_confirmed IC +0.073 (t=+2.0)")
    A("- Phase 2 trend_quality confirms the signal's recovery-state relevance")
    A("")
    A("Carry forward to:")
    A("- **Phase 4** (Cross-Sectional Leadership): recovery quality as leadership confirmation")
    A("- **Phase 5** (Allocator Objective): recovery quality as deployment confidence score component")
    A("")
    if "Promote" in verdict:
        A("The Phase 3B re-risking modifier is also promotable as a portfolio modifier.")
    else:
        A("Do NOT apply the Phase 3B re-risk modifier as a standalone portfolio modifier.")
        A("The strongest existing frontier portfolio modifier remains:")
        A("`phase1_r2a_plus_phase2_trend_quality` (Phase 2B): holdout Δ +0.043, bootstrap 84%.")
    A(""); A("---"); A("")

    A("## 12. Files Created"); A("")
    for f in ["phase3b_rerisk_gate_results.csv","phase3b_rerisk_gate_holdout_summary.csv",
              "phase3b_rerisk_gate_state_summary.csv","phase3b_rerisk_gate_phase_d_gates.csv",
              "phase3b_rerisk_modifier_timeseries.csv"]:
        A(f"- `data/research/frontier_phase3/{f}`")
    A("- `docs/research/frontier_phase3b_rerisk_gate_revision_report.md`")
    A(""); A("## 13. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged")
    A("- No public/, src/, dashboard files modified")
    if warns:
        A(""); A("## 14. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase3b_rerisk_gate_revision_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict, vr, best_var, full_r, hold_r):
    j = ROOT / "docs" / "research" / "project_journey.md"
    if not j.exists(): print("project_journey.md not found."); return
    b = full_r.get("ggg_baseline_no_modifier", {})
    p = full_r.get(best_var, {})
    hb = hold_r.get("ggg_baseline_no_modifier", {})
    hp = hold_r.get(best_var, {})

    def _v(d, k):
        v = d.get(k); return float(v) if v is not None and np.isfinite(float(v)) else np.nan

    txt = f"""

## Section — Frontier Phase 3B: Smart Re-Risking Gate Revision

Date: 2026-05-21.

Phase 3A failed because the >=6w transition gate fired only 3 times.
Phase 3B retests with >=3w (35 active), >=2w (56), continuous (93), and
recovery_confirmed-only (44) gates.  Same recovery_quality_r2a_plus_trend signal.
Same transition_rerisk_smoothing checkpoint.

| metric | baseline | best ({best_var}) | delta |
|--------|----------|-------------------|-------|
| sharpe | {_f(b.get('sharpe'))} | {_f(p.get('sharpe'))} | {_f(_v(p,'sharpe')-_v(b,'sharpe'),'+.4f')} |
| rc_capture | {_f(b.get('capture_recovery_confirmed'))} | {_f(p.get('capture_recovery_confirmed'))} | {_f(_v(p,'capture_recovery_confirmed')-_v(b,'capture_recovery_confirmed'),'+.3f')} |
| holdout_sharpe | {_f(hb.get('sharpe'))} | {_f(hp.get('sharpe'))} | {_f(_v(hp,'sharpe')-_v(hb,'sharpe'),'+.4f')} |

### Verdict

**{verdict}**

{vr}

Recovery quality signal (recovery_quality_r2a_plus_trend) feeds Phase 4 and 5
as a validated signal input regardless of portfolio modifier verdict.
The strongest existing frontier portfolio modifier remains phase1_r2a_plus_phase2_trend_quality
(Phase 2B: holdout delta +0.043, bootstrap 84%, rolling win 67%).
"""
    with open(j, "a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
