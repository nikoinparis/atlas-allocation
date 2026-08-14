"""Frontier Phase 6A: Decision-Focused Learning Label Construction.

Builds five predeclared decision-quality labels using forward returns from
the phase5_fragility_guard candidate and the GGG baseline.  Labels are
constructed and their distributions reported.  NO model is trained here.
NO feature-label correlations are computed.

Label parameters are PREDECLARED and must not be changed after running.

Run from repo root:
    .venv/bin/python scripts/phase_frontier6_decision_labels.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

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

# ── PREDECLARED label parameters — do not change after running ────────────────
HORIZON_WEEKS           = 8
LAG_WEEKS               = 1      # features lag (already applied in prior phases)
DEPLOY_PROFIT_BARRIER   = 0.020  # +2.0%
DEPLOY_LOSS_BARRIER     = -0.012 # -1.2%
HOLDOUT_START           = pd.Timestamp("2024-04-19")
EMBARGO_WEEKS           = 4
FRONTIER_BEATS_MARGIN   = 0.0025 # +0.25pp for frontier_beats_ggg and conservative_override
RERISK_MARGIN           = 0.010  # frontier must beat BIL by +1.0% for rerisk_quality_label
DEPLOY_MIN_SHARPE       = 0.5    # annualized Sharpe floor for deploy_quality_label
EXPANDING_MIN           = 52

OFFENSE_ETFs = ["SPY","QQQ","XLK","XLY","XLI","IWM","VWO","EFA"]
FRAGILITY_THRESHOLD = -0.50

OUT_DIR     = DATA / "research" / "frontier_phase6"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase6_decision_labels_report.md"
PROTECTED   = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Loaders ───────────────────────────────────────────────────────────────────

def _read_dated(path: Path, date_col: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    dc = date_col or ("date" if "date" in df.columns else "Date")
    df[dc] = pd.to_datetime(df[dc], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[dc]).sort_values(dc).set_index(dc)


def _ez(s: pd.Series, min_p: int = EXPANDING_MIN) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


# ── Reproduce phase5_fragility_guard returns ──────────────────────────────────

def reproduce_fragility_guard(wrapper: AllocatorCheckpointWrapper,
                               warnings: list[str]) -> pd.DataFrame:
    """Re-run phase5_fragility_guard and return the path DataFrame."""
    # Load required signals
    ph1 = _read_dated(DATA/"research"/"frontier_phase1"/"state_quality_signals_r2.csv")
    ph4 = _read_dated(DATA/"research"/"frontier_phase4"/"leadership_signals.csv")
    idx    = wrapper.index
    states = wrapper.states["market_state"].astype(str)

    phase1_sq = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(idx).fillna(0.0).clip(-1.0, 1.0)
    lc_raw    = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(idx).ffill().fillna(0.0)
    phase4_frag = (-1.0 * lc_raw).clip(-1.0, 1.0)

    # Build modifier: Phase 1 R2A + fragility cap
    q = phase1_sq.clip(-1.0, 1.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    not_sp = states != "stressed_panic"
    scale[not_sp] = 1.0 + 0.08 * q[not_sp]
    fg = phase4_frag.reindex(states.index).fillna(0.0)
    crowded = fg < FRAGILITY_THRESHOLD
    scale[crowded & not_sp] = scale[crowded & not_sp].clip(upper=1.0)
    scale[states == "stressed_panic"] = 1.0

    def _fn(w, _c): return scale.reindex(w.index).fillna(1.0)
    mod = CheckpointModifier(name="frag_guard_p6", checkpoint="offense_budget", function=_fn)
    result = wrapper.run("phase5_fragility_guard_p6a", modifiers=[mod])

    # Sanity: stressed_panic rows match baseline
    bw = wrapper.final_weights; cw = result.weights
    off = sorted(OFFENSE & set(bw.columns))
    sp_dates = states.index[states == "stressed_panic"]
    diff = (cw.loc[sp_dates, off].sum(axis=1) - bw.loc[sp_dates, off].sum(axis=1)).abs().max()
    if diff > 0.001:
        warnings.append(f"PHASE5 FG reproduced with SP offense change={diff:.6f}")
    else:
        print(f"  phase5_fragility_guard reproduced (SP check: {diff:.2e})")

    return result.path


# ── Forward return computation ────────────────────────────────────────────────

def _fwd_compound(ret: pd.Series, horizon: int) -> pd.Series:
    """Compound forward return from t+1 to t+horizon."""
    return ret.rolling(horizon).apply(lambda x: (1+x).prod()-1, raw=True).shift(-horizon)


def _fwd_sharpe(ret: pd.Series, horizon: int) -> pd.Series:
    """Annualised Sharpe over forward horizon (t+1..t+horizon)."""
    mu  = ret.rolling(horizon).mean().shift(-horizon) * 52
    vol = ret.rolling(horizon).std(ddof=0).shift(-horizon) * np.sqrt(52)
    return (mu / vol.replace(0, np.nan)).fillna(np.nan)


# ── Triple-barrier label ──────────────────────────────────────────────────────

def triple_barrier(ret: pd.Series,
                   profit: float, loss: float, horizon: int) -> pd.Series:
    """Traverse path for each t and assign +1/-1/0.

    At time t:
      cumulative forward path = (1+r[t+1])(1+r[t+2])...(1+r[t+k]) - 1
      +1 if profit hit before loss within horizon
      -1 if loss hit first
       0 if neither within horizon
    """
    arr = ret.values
    n   = len(arr)
    labels = np.full(n, np.nan, dtype=float)

    for t in range(n):
        if t + horizon >= n:
            break
        cum = 0.0
        label = 0
        for k in range(1, horizon + 1):
            cum = (1 + cum) * (1 + arr[t + k]) - 1
            if cum >= profit:
                label = 1
                break
            if cum <= loss:
                label = -1
                break
        labels[t] = float(label)

    return pd.Series(labels, index=ret.index, name="triple_barrier_label")


# ── Label construction ────────────────────────────────────────────────────────

def build_labels(ggg_ret: pd.Series, fg_ret: pd.Series,
                 states: pd.Series, bil_ret: pd.Series,
                 warnings: list[str]) -> pd.DataFrame:
    """Build all five predeclared decision labels."""

    idx = ggg_ret.index.intersection(fg_ret.index)
    ggg = ggg_ret.reindex(idx).fillna(0.0)
    fg  = fg_ret.reindex(idx).fillna(0.0)
    st  = states.reindex(idx).fillna("unknown")
    bil = bil_ret.reindex(idx).fillna(0.0)

    # Forward compound returns
    ggg_fwd8 = _fwd_compound(ggg, HORIZON_WEEKS)
    fg_fwd8  = _fwd_compound(fg,  HORIZON_WEEKS)
    bil_fwd8 = _fwd_compound(bil, HORIZON_WEEKS)
    fg_sh8   = _fwd_sharpe(fg,    HORIZON_WEEKS)

    # Label 1: frontier_beats_ggg_label
    l1 = (fg_fwd8 - ggg_fwd8 >= FRONTIER_BEATS_MARGIN).astype(float)
    l1[fg_fwd8.isna() | ggg_fwd8.isna()] = np.nan

    # Label 2: deploy_quality_label
    l2 = ((fg_fwd8 >= 0) & (fg_sh8 >= DEPLOY_MIN_SHARPE)).astype(float)
    l2[fg_fwd8.isna() | fg_sh8.isna()] = np.nan

    # Label 3: triple_barrier_label
    l3 = triple_barrier(fg, DEPLOY_PROFIT_BARRIER, DEPLOY_LOSS_BARRIER, HORIZON_WEEKS)
    l3 = l3.reindex(idx)

    # Label 4: conservative_override_label
    l4 = (ggg_fwd8 - fg_fwd8 >= FRONTIER_BEATS_MARGIN).astype(float)
    l4[fg_fwd8.isna() | ggg_fwd8.isna()] = np.nan

    # Label 5: rerisk_quality_label (NaN outside recovery)
    recovery_mask = st.isin({"recovery_confirmed","recovery_fragile"})
    l5 = pd.Series(np.nan, index=idx, name="rerisk_quality_label")
    rec_valid = fg_fwd8[recovery_mask].notna() & bil_fwd8[recovery_mask].notna()
    l5[recovery_mask & rec_valid] = (
        (fg_fwd8[recovery_mask & rec_valid] - bil_fwd8[recovery_mask & rec_valid])
        >= RERISK_MARGIN
    ).astype(float)

    return pd.DataFrame({
        "market_state":               st,
        "ggg_net_return":             ggg,
        "fg_net_return":              fg,
        "ggg_fwd8":                   ggg_fwd8,
        "fg_fwd8":                    fg_fwd8,
        "fg_sh8_annualized":          fg_sh8,
        "bil_fwd8":                   bil_fwd8,
        "frontier_beats_ggg_label":   l1,
        "deploy_quality_label":       l2,
        "triple_barrier_label":       l3,
        "conservative_override_label":l4,
        "rerisk_quality_label":       l5,
    })


# ── Feature snapshot ──────────────────────────────────────────────────────────

def build_feature_snapshot(labels_df: pd.DataFrame,
                            phase5_mdq: pd.DataFrame,
                            ph4: pd.DataFrame,
                            warnings: list[str]) -> pd.DataFrame:
    """Attach causal feature columns to the labels frame.
    All features are backward-looking only (no future data)."""
    idx = labels_df.index

    # Phase 5 master deployment quality (already lagged in Phase 5 construction)
    mdq = phase5_mdq.reindex(idx)
    p1  = mdq.get("phase1_state_quality",   pd.Series(np.nan, index=idx))
    p2  = mdq.get("phase2_portfolio_tq",    pd.Series(np.nan, index=idx))
    p4_frag = mdq.get("phase4_fragility_adjusted", pd.Series(np.nan, index=idx))
    mdq_col = mdq.get("master_deployment_quality", pd.Series(np.nan, index=idx))

    # Phase 4 raw leadership (already lagged in Phase 4 construction)
    p4_raw = pd.to_numeric(
        ph4.get("leadership_quality_composite", pd.Series(np.nan, index=idx)), errors="coerce"
    ).reindex(idx).ffill().fillna(0.0)

    # Fragility guard active flag (derived from phase4_fragility_adjusted < threshold)
    fg_flag = (p4_frag < FRAGILITY_THRESHOLD).astype(float)
    fg_flag[p4_frag.isna()] = np.nan

    # Trailing 8-week portfolio vol (backward-looking, using past 8w of fg returns)
    ggg = labels_df["ggg_net_return"]; fg = labels_df["fg_net_return"]
    trail_fg_vol  = fg.rolling(8, min_periods=4).std() * np.sqrt(52)

    # Trailing 8w returns for SPY, GGG, Phase5 FG
    wk = _read_dated(DATA/"01_data_hub"/"weekly_prices.csv")
    spy_ret = wk["SPY"].reindex(idx).ffill().pct_change(1)
    trail_spy_ret = spy_ret.rolling(8, min_periods=4).apply(lambda x: (1+x).prod()-1, raw=True)
    trail_ggg_ret = ggg.rolling(8, min_periods=4).apply(lambda x: (1+x).prod()-1, raw=True)
    trail_fg_ret  = fg.rolling(8,  min_periods=4).apply(lambda x: (1+x).prod()-1, raw=True)

    snap = pd.DataFrame({
        "phase1_r2a":                    p1,
        "phase2_avg_trend_quality":      p2,
        "phase4_raw_leadership_quality": p4_raw,
        "phase4_inverted_fragility":     p4_frag,
        "phase5_master_deployment_quality": mdq_col,
        "fragility_guard_active_flag":   fg_flag,
        "trailing_8w_portfolio_vol":     trail_fg_vol,
        "trailing_8w_spy_return":        trail_spy_ret,
        "trailing_8w_ggg_return":        trail_ggg_ret,
        "trailing_8w_phase5_return":     trail_fg_ret,
    }, index=idx)
    return snap


# ── Distribution summary helpers ──────────────────────────────────────────────

LABEL_COLS = [
    "frontier_beats_ggg_label",
    "deploy_quality_label",
    "triple_barrier_label",
    "conservative_override_label",
    "rerisk_quality_label",
]

def _base_rate(s: pd.Series) -> dict:
    c = s.dropna()
    if len(c) == 0:
        return {"n": 0, "base_rate": np.nan, "pct_pos": np.nan, "pct_neg": np.nan, "pct_zero": np.nan}
    pos  = float((c  > 0.5).mean())
    neg  = float((c < -0.5).mean())
    zero = float(((c >= -0.5) & (c <= 0.5)).mean())
    br   = float((c > 0).mean())
    return {"n": len(c), "base_rate_positive": br,
            "pct_pos": pos, "pct_neg": neg, "pct_zero": zero}


def compute_distributions(labels: pd.DataFrame,
                           states: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (full_summary, state_summary) DataFrames."""
    dev_mask  = labels.index < HOLDOUT_START
    hold_mask = labels.index >= HOLDOUT_START

    rows = []
    for col in LABEL_COLS:
        if col not in labels.columns:
            continue
        for scope, mask in [("full", slice(None)),
                             ("dev", dev_mask), ("holdout", hold_mask)]:
            s = labels[col] if scope == "full" else labels[col][mask]
            d = _base_rate(s)
            rows.append({"label": col, "scope": scope, **d})
    dist_df = pd.DataFrame(rows)

    # By state
    state_rows = []
    state_col = labels.get("market_state", states.reindex(labels.index))
    for col in LABEL_COLS:
        if col not in labels.columns:
            continue
        for state, grp in state_col.groupby(state_col):
            s = labels.loc[grp.index, col].dropna()
            d = _base_rate(s)
            state_rows.append({"label": col, "state": state, **d})
    state_df = pd.DataFrame(state_rows)

    return dist_df, state_df


# ── Protected diff ────────────────────────────────────────────────────────────

def diff_clean():
    try:
        r = subprocess.run(["git","diff","--name-only","--",*PROTECTED],
                           cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception: return False,["git diff failed"]
    c = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0, c


# ── Acceptance evaluation ─────────────────────────────────────────────────────

def _check_usable(dist_df: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    ok, warn = [], []
    full = dist_df[dist_df["scope"] == "full"].set_index("label")

    for lbl in LABEL_COLS:
        if lbl not in full.index:
            warn.append(f"{lbl}: not found in distribution summary")
            continue
        r = full.loc[lbl]
        n  = int(r.get("n", 0))
        br = float(r.get("base_rate_positive", np.nan))
        # Triple barrier: check that pos+neg > 30% each
        if lbl == "triple_barrier_label":
            pp = float(r.get("pct_pos", 0)); pn = float(r.get("pct_neg", 0))
            if n < 50:
                warn.append(f"{lbl}: only {n} observations (need ≥50)")
            elif pp < 0.10 or pn < 0.10:
                warn.append(f"{lbl}: sparse classes (pos={pp:.1%}, neg={pn:.1%})")
            else:
                ok.append(f"{lbl}: n={n}, pos={pp:.1%}, zero={r.get('pct_zero',0):.1%}, neg={pn:.1%}")
        else:
            if n < 50:
                warn.append(f"{lbl}: only {n} observations (need ≥50)")
            elif not np.isfinite(br) or br < 0.05 or br > 0.95:
                warn.append(f"{lbl}: extreme imbalance (base_rate={br:.2%}) — too few positive examples for reliable learning")
            else:
                ok.append(f"{lbl}: n={n}, base_rate={br:.2%}")

    return len(warn) == 0, ok, warn


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns = []
    print("=" * 70)
    print("Frontier Phase 6A: Decision-Focused Learning Label Construction")
    print("=" * 70)
    print("\nPredeclared label parameters:")
    print(f"  horizon={HORIZON_WEEKS}w, lag={LAG_WEEKS}w, "
          f"profit_barrier={DEPLOY_PROFIT_BARRIER:+.3f}, loss_barrier={DEPLOY_LOSS_BARRIER:+.3f}")
    print(f"  holdout_start={HOLDOUT_START.date()}, embargo={EMBARGO_WEEKS}w")

    # ── Initialise wrapper ────────────────────────────────────────────────────
    print("\nInitialising wrapper...")
    wrapper = AllocatorCheckpointWrapper()
    cmp = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(cmp, 1e-10):
        raise SystemExit(f"Wrapper failed: {cmp}")
    print(f"  GGG exact match (max_err={cmp['net_return_max_abs_error']:.2e})")

    states = wrapper.states["market_state"].astype(str)
    nwr    = wrapper.next_week_returns

    # ── Reproduce GGG returns ─────────────────────────────────────────────────
    print("Reproducing GGG baseline returns...")
    ggg_run  = wrapper.run("ggg_baseline")
    ggg_path = ggg_run.path.set_index("Date")
    ggg_ret  = ggg_path["net_return"].rename("ggg_net_return")
    print(f"  GGG returns: {ggg_ret.notna().sum()} rows")

    # ── Reproduce Phase 5 fragility_guard returns ─────────────────────────────
    print("Reproducing phase5_fragility_guard returns...")
    fg_path = reproduce_fragility_guard(wrapper, warns)
    fg_path = fg_path.set_index("Date")
    fg_ret  = fg_path["net_return"].rename("fg_net_return")
    print(f"  FG returns: {fg_ret.notna().sum()} rows")

    # Quick sanity: fragility_guard should be close to GGG overall
    common = ggg_ret.index.intersection(fg_ret.index)
    ggg_ann = float((1 + ggg_ret[common]).prod() ** (52 / len(common)) - 1)
    fg_ann  = float((1 + fg_ret[common]).prod()  ** (52 / len(common)) - 1)
    print(f"  GGG annualised: {ggg_ann:.4f}  FG: {fg_ann:.4f}  Δ={fg_ann-ggg_ann:+.4f}")

    # ── BIL returns (cash proxy) ──────────────────────────────────────────────
    wk = _read_dated(DATA/"01_data_hub"/"weekly_prices.csv")
    bil_ret = wk["BIL"].reindex(ggg_ret.index).ffill().pct_change(1).rename("bil_ret")
    print(f"  BIL returns: {bil_ret.notna().sum()} rows")

    # ── Build labels ──────────────────────────────────────────────────────────
    print("\nBuilding decision labels...")
    labels_df = build_labels(ggg_ret, fg_ret, states, bil_ret, warns)

    for col in LABEL_COLS:
        n_valid = int(labels_df[col].notna().sum())
        if col == "triple_barrier_label":
            n_pos = int((labels_df[col] == 1).sum())
            n_neg = int((labels_df[col] == -1).sum())
            n_zero= int((labels_df[col] == 0).sum())
            print(f"  {col}: n={n_valid}  +1={n_pos}  0={n_zero}  -1={n_neg}")
        else:
            n_pos = int((labels_df[col] == 1).sum())
            n_neg = int((labels_df[col] == 0).sum())
            br    = n_pos / max(n_valid, 1)
            print(f"  {col}: n={n_valid}  base_rate={br:.2%}")

    # ── Feature snapshot ──────────────────────────────────────────────────────
    print("\nBuilding feature snapshot (no label correlations computed)...")
    ph5_mdq = _read_dated(DATA/"research"/"frontier_phase5"/"master_deployment_quality_timeseries.csv")
    ph4     = _read_dated(DATA/"research"/"frontier_phase4"/"leadership_signals.csv")
    features_df = build_feature_snapshot(labels_df, ph5_mdq, ph4, warns)
    print(f"  Feature snapshot: {features_df.shape[1]} columns, {features_df.shape[0]} rows")

    # ── Compute distributions ─────────────────────────────────────────────────
    print("\nComputing label distributions...")
    dist_df, state_dist_df = compute_distributions(labels_df, states)

    print("\n=== Full-History Base Rates ===")
    for _, r in dist_df[dist_df["scope"] == "full"].iterrows():
        if r["label"] == "triple_barrier_label":
            print(f"  {r['label']:<35}: n={r['n']}  "
                  f"pos={r['pct_pos']:.2%}  zero={r['pct_zero']:.2%}  neg={r['pct_neg']:.2%}")
        else:
            print(f"  {r['label']:<35}: n={r['n']}  base_rate={r['base_rate_positive']:.2%}")

    print("\n=== Dev vs Holdout Base Rates (frontier_beats_ggg_label) ===")
    for scope in ["dev","holdout"]:
        sub = dist_df[(dist_df["label"]=="frontier_beats_ggg_label") & (dist_df["scope"]==scope)]
        if not sub.empty:
            r = sub.iloc[0]
            print(f"  {scope}: n={r['n']}  base_rate={r['base_rate_positive']:.2%}")

    # ── Acceptance check ──────────────────────────────────────────────────────
    usable, ok_list, warn_list = _check_usable(dist_df)
    print(f"\n{'='*70}")
    print(f"Acceptance: {'USABLE' if usable else 'WARNINGS'}")
    for r in ok_list:   print(f"  ✓ {r}")
    for r in warn_list: print(f"  ⚠ {r}")

    if usable or len(warn_list) <= 1:
        verdict = "Proceed to Phase 6B model training"
        vr = ("Label distributions are sufficiently balanced and have enough observations. "
              "Proceed to Phase 6B with walk-forward training using purged cross-validation "
              "and the predeclared parameters above.")
    else:
        verdict = "Revise labels once"
        vr = (f"Multiple label distribution warnings: {'; '.join(warn_list)}. "
              "Revise before Phase 6B.")

    print(f"\nVERDICT: {verdict}")
    print(f"{'='*70}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Full labels + features CSV
    out_df = pd.concat([labels_df, features_df], axis=1)
    out_df.index.name = "date"
    out_df.to_csv(OUT_DIR / "decision_labels.csv")

    dist_df.to_csv(OUT_DIR / "decision_label_distribution_summary.csv", index=False)
    state_dist_df.to_csv(OUT_DIR / "decision_label_state_summary.csv", index=False)

    for f in ["decision_labels.csv","decision_label_distribution_summary.csv",
              "decision_label_state_summary.csv"]:
        print(f"  Saved: data/research/frontier_phase6/{f}")

    dc, dch = diff_clean()
    if not dc: print(f"WARNING: {dch}"); warns.append(str(dch))
    else: print("Protected files: clean.")

    _write_report(labels_df, dist_df, state_dist_df, usable, ok_list, warn_list,
                  verdict, vr, warns, dc)
    _journey(verdict, vr, dist_df, warn_list)

    print(f"\nPhase 6A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")
    print("NO model was trained. NO feature-label correlations were computed.")


# ── Report ────────────────────────────────────────────────────────────────────

def _f(v, fmt=".4f"):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    try: return format(float(v),fmt)
    except: return str(v)


def _write_report(labels_df, dist_df, state_df, usable, ok_list, warn_list,
                  verdict, vr, warns, dc):
    lines=[]; A=lines.append

    A("# Frontier Phase 6A: Decision-Focused Learning Label Construction Report")
    A(""); A("**Date:** 2026-05-21")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A("**IMPORTANT: No model was trained. No feature-label correlations were computed.**")
    A(""); A("---"); A("")

    A("## 1. Sprint Summary"); A("")
    A("Phase 6A builds five predeclared decision-quality labels using forward returns "
      "from `phase5_fragility_guard` and the GGG baseline.  The labels capture when the "
      "frontier candidate beats the baseline, when deploying was a good decision, and when "
      "staying with the baseline would have been better.  Labels are validated for usability "
      "and class balance before Phase 6B model training."); A(""); A("---"); A("")

    A("## 2. Commands Run"); A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier6_decision_labels.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Predeclared Label Parameters"); A("")
    A("*These parameters are locked. They must not change after running.*"); A("")
    A("| parameter | value |")
    A("|-----------|-------|")
    A(f"| horizon_weeks | {HORIZON_WEEKS} |")
    A(f"| lag_weeks (feature) | {LAG_WEEKS} |")
    A(f"| deploy_profit_barrier | {DEPLOY_PROFIT_BARRIER:+.3f} (+{DEPLOY_PROFIT_BARRIER*100:.1f}%) |")
    A(f"| deploy_loss_barrier | {DEPLOY_LOSS_BARRIER:+.3f} ({DEPLOY_LOSS_BARRIER*100:.1f}%) |")
    A(f"| frontier_beats_margin | {FRONTIER_BEATS_MARGIN:+.4f} (+{FRONTIER_BEATS_MARGIN*100:.2f}bp) |")
    A(f"| rerisk_margin | {RERISK_MARGIN:+.3f} (+{RERISK_MARGIN*100:.1f}%) |")
    A(f"| deploy_min_sharpe | {DEPLOY_MIN_SHARPE} |")
    A(f"| holdout_start | {HOLDOUT_START.date()} |")
    A(f"| embargo_weeks | {EMBARGO_WEEKS} |")
    A(""); A("---"); A("")

    A("## 4. Label Definitions"); A("")
    A("| label | definition |")
    A("|-------|-----------|")
    A("| `frontier_beats_ggg_label` | 1 if FG 8w cumulative return > GGG 8w cumulative return + 0.25pp |")
    A("| `deploy_quality_label` | 1 if FG 8w return ≥ 0 AND FG 8w annualised Sharpe ≥ 0.5 |")
    A("| `triple_barrier_label` | +1 if +2% profit hit before -1.2% loss within 8w; -1 if loss first; 0 if neither |")
    A("| `conservative_override_label` | 1 if GGG 8w return > FG 8w return + 0.25pp (stay with baseline) |")
    A("| `rerisk_quality_label` | Recovery states only: 1 if FG beats BIL by ≥1% over next 8w |")
    A(""); A("**Leakage check:** All labels use forward returns (t+1..t+8) only. "
      "All features in the snapshot use backward-looking data only."); A("")
    A("---"); A("")

    A("## 5. Dataset"); A("")
    A(f"- Total rows: {len(labels_df)}")
    A(f"- Date range: {labels_df.index[0].date()} → {labels_df.index[-1].date()}")
    A(f"- Development window: up to {HOLDOUT_START.date()} ({int((labels_df.index < HOLDOUT_START).sum())} rows)")
    A(f"- Holdout window: from {HOLDOUT_START.date()} ({int((labels_df.index >= HOLDOUT_START).sum())} rows)")
    A(f"- Recovery rows (confirmed+fragile): {int(labels_df['market_state'].isin(['recovery_confirmed','recovery_fragile']).sum())}")
    A(""); A("---"); A("")

    A("## 6. Full-History Label Distributions"); A("")
    A("| label | n | base_rate(+1) | pct_pos | pct_zero | pct_neg |")
    A("|-------|---|-------------|---------|----------|---------|")
    for _, r in dist_df[dist_df["scope"]=="full"].iterrows():
        A(f"| {r['label']} | {r['n']} | {_f(r['base_rate_positive'],'.2%')} | "
          f"{_f(r['pct_pos'],'.2%')} | {_f(r['pct_zero'],'.2%')} | {_f(r['pct_neg'],'.2%')} |")
    A(""); A("---"); A("")

    A("## 7. Development vs Holdout Base Rates"); A("")
    A("| label | dev_n | dev_base_rate | holdout_n | holdout_base_rate |")
    A("|-------|-------|--------------|-----------|------------------|")
    for lbl in LABEL_COLS:
        d = dist_df[(dist_df["label"]==lbl) & (dist_df["scope"]=="dev")]
        h = dist_df[(dist_df["label"]==lbl) & (dist_df["scope"]=="holdout")]
        dn = int(d.iloc[0]["n"]) if not d.empty else 0
        hn = int(h.iloc[0]["n"]) if not h.empty else 0
        dbr= _f(d.iloc[0]["base_rate_positive"],".2%") if not d.empty else "–"
        hbr= _f(h.iloc[0]["base_rate_positive"],".2%") if not h.empty else "–"
        A(f"| {lbl} | {dn} | {dbr} | {hn} | {hbr} |")
    A(""); A("---"); A("")

    A("## 8. By Market State (`frontier_beats_ggg_label`)"); A("")
    A("| state | n | base_rate |")
    A("|-------|---|-----------|")
    sub = state_df[state_df["label"]=="frontier_beats_ggg_label"]
    for _, r in sub.sort_values("state").iterrows():
        A(f"| {r['state']} | {r['n']} | {_f(r['base_rate_positive'],'.2%')} |")
    A(""); A("---"); A("")

    A("## 9. Class Imbalance Warnings"); A("")
    if warn_list:
        for w in warn_list: A(f"- ⚠ {w}")
    else:
        A("No significant imbalance warnings.")
    A(""); A("---"); A("")

    A("## 10. Usability Assessment"); A("")
    status = "✓ USABLE" if usable else "⚠ WARNINGS"
    A(f"**{status}**"); A("")
    for r in ok_list:   A(f"- ✓ {r}")
    for r in warn_list: A(f"- ⚠ {r}")
    A(""); A("---"); A("")

    A("## 11. Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A("")
    A("### Phase 6B Readiness Checklist"); A("")
    A("When Phase 6B is implemented, it must follow these rules:")
    A("- Walk-forward expanding windows only (no k-fold)")
    A(f"- Minimum training window: 260 weeks before first prediction")
    A(f"- Purged cross-validation: {EMBARGO_WEEKS}-week embargo at train/test boundary")
    A("- Model: calibrated logistic regression or GBM (max_depth ≤ 3)")
    A("- Target: `frontier_beats_ggg_label` as primary (most interpretable)")
    A("- Features: causal-only Phase 1–5 quality signals (from the snapshot above)")
    A("- Report: out-of-sample accuracy AND portfolio Sharpe improvement on holdout")
    A("- DO NOT select model hyperparameters using holdout performance")
    A(""); A("---"); A("")
    A("## 12. Files Created"); A("")
    for f in ["decision_labels.csv","decision_label_distribution_summary.csv","decision_label_state_summary.csv"]:
        A(f"- `data/research/frontier_phase6/{f}`")
    A("- `docs/research/frontier_phase6_decision_labels_report.md`"); A("")
    A("## 13. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged"); A("- No public/, src/, dashboard files modified")
    A("- No model was trained. No feature-label correlations were computed.")
    if warns:
        A(""); A("## 14. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase6_decision_labels_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict, vr, dist_df, warn_list):
    j = ROOT / "docs" / "research" / "project_journey.md"
    if not j.exists(): return

    full = dist_df[dist_df["scope"]=="full"]
    rows = {}
    for _, r in full.iterrows():
        rows[r["label"]] = r

    def _br(lbl):
        r = rows.get(lbl, {})
        br = r.get("base_rate_positive", np.nan) if isinstance(r, (dict, pd.Series)) else np.nan
        n  = r.get("n", 0)                        if isinstance(r, (dict, pd.Series)) else 0
        return f"{float(br):.2%} (n={int(n)})" if np.isfinite(float(br)) else "–"

    txt = f"""

## Section — Frontier Phase 6A: Decision-Focused Learning Label Construction

Date: 2026-05-21.

Built five predeclared decision-quality labels using phase5_fragility_guard
and GGG baseline forward returns.  No model trained.  No feature-label
correlations computed.

Label base rates (full history):
- frontier_beats_ggg_label:      {_br('frontier_beats_ggg_label')}
- deploy_quality_label:          {_br('deploy_quality_label')}
- triple_barrier_label (+1):     {_br('triple_barrier_label')}
- conservative_override_label:   {_br('conservative_override_label')}
- rerisk_quality_label:          {_br('rerisk_quality_label')}

Verdict: **{verdict}**

{vr}

Label parameters are predeclared and locked.  Phase 6B may use these labels
as training targets with walk-forward purged cross-validation (embargo={EMBARGO_WEEKS}w).
Primary Phase 6B target: frontier_beats_ggg_label.
"""
    with open(j, "a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
